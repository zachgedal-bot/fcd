/**
 * After Hours service: static desks + server-side odds adapter + server-side gate.
 * Plain Node, no dependencies. Node >= 18.
 *
 *   node server/server.js
 *
 * Environment (see .env.example):
 *   PORT                     default 8080
 *   ODDS_API_KEY             The Odds API key. Absent -> /api/fixtures answers 503 provider_not_configured; nothing is simulated.
 *   ODDS_API_BASE            default https://api.the-odds-api.com (override for tests)
 *   ODDS_REGIONS             default us,eu   (eu carries Pinnacle)
 *   ODDS_SPORT_KEYS          optional comma list to pin leagues; otherwise discovered from /v4/sports by league patterns
 *   ODDS_CACHE_SECONDS       default 300. Each refresh costs (markets x regions) credits per league.
 *   AFTER_HOURS_INVITE_CODES comma list. Set -> the page and API require a session cookie obtained at /enter with a code + 18+ attestation.
 *   SESSION_SECRET           HMAC secret for the session cookie (required when invite codes are set)
 *   SESSION_HOURS            default 168
 *   HOME_URL                 where "<- AthleMix" points, default https://athlemix.com
 *   TRUST_PROXY              "1" to read x-forwarded-proto / x-forwarded-for behind a TLS terminator
 */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { URL } = require('url');
const A = require('./adapter');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PORT || 8080);
const ODDS_BASE = (process.env.ODDS_API_BASE || 'https://api.the-odds-api.com').replace(/\/$/, '');
const REGIONS = process.env.ODDS_REGIONS || 'us,eu';
const CACHE_S = Number(process.env.ODDS_CACHE_SECONDS || 300);
const SPORT_KEYS = (process.env.ODDS_SPORT_KEYS || '').split(',').map(s => s.trim()).filter(Boolean);
const INVITES = (process.env.AFTER_HOURS_INVITE_CODES || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
const GATED = INVITES.length > 0;
const SECRET = process.env.SESSION_SECRET || '';
const SESSION_HOURS = Number(process.env.SESSION_HOURS || 168);
const HOME_URL = process.env.HOME_URL || 'https://athlemix.com';
const TRUST_PROXY = process.env.TRUST_PROXY === '1';

if (GATED && SECRET.length < 16) {
  console.error('AFTER_HOURS_INVITE_CODES is set but SESSION_SECRET is missing or shorter than 16 chars. Refusing to start gated without a real secret.');
  process.exit(1);
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.csv': 'text/csv; charset=utf-8', '.md': 'text/markdown; charset=utf-8' };
// Only these paths are served. Python sources, tests and docs stay private.
const STATIC_ALLOW = [/^\/after-hours\.(html|css|js)$/, /^\/after-hours-ui\.js$/, /^\/enter\.html$/, /^\/altitude_edge\/(venues|fc_ratings_nwsl|fixtures_demo)\.json$/, /^\/altitude_fc\/altitude_fc_cards\.html$/, /^\/altitude_fc\/evidence_table\.(json|csv|md)$/, /^\/altitude_fc\/model_hir_curves\.png$/];

// ---------- helpers ----------
const json = (res, status, obj) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
const text = (res, status, s, type = 'text/plain; charset=utf-8') => { res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store' }); res.end(s); };
const redirect = (res, to, extra = {}) => { res.writeHead(303, Object.assign({ Location: to }, extra)); res.end(); };
const secure = req => TRUST_PROXY ? (req.headers['x-forwarded-proto'] || '').split(',')[0].trim() === 'https' : !!req.socket.encrypted;
const clientIp = req => (TRUST_PROXY && (req.headers['x-forwarded-for'] || '').split(',')[0].trim()) || req.socket.remoteAddress || '?';
const sign = payload => crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');
const timingEqual = (a, b) => { const x = Buffer.from(String(a)), y = Buffer.from(String(b)); return x.length === y.length && crypto.timingSafeEqual(x, y); };

function makeSession() {
  const payload = Buffer.from(JSON.stringify({ exp: Date.now() + SESSION_HOURS * 3600e3, adult: true, n: crypto.randomBytes(8).toString('hex') })).toString('base64url');
  return `${payload}.${sign(payload)}`;
}
function readSession(req) {
  const m = /(?:^|;\s*)ah_session=([^;]+)/.exec(req.headers.cookie || '');
  if (!m) return null;
  const [payload, sig] = m[1].split('.');
  if (!payload || !sig || !timingEqual(sign(payload), sig)) return null;
  try { const s = JSON.parse(Buffer.from(payload, 'base64url').toString()); return s.exp > Date.now() && s.adult === true ? s : null; } catch { return null; }
}
const authed = req => !GATED || !!readSession(req);

// per-IP limiter for /enter attempts: 10 per 10 minutes
const attempts = new Map();
function limited(ip) {
  const now = Date.now(); const a = (attempts.get(ip) || []).filter(t => now - t < 600e3); attempts.set(ip, a);
  if (a.length >= 10) return true; a.push(now); return false;
}
setInterval(() => { const now = Date.now(); for (const [ip, a] of attempts) if (!a.some(t => now - t < 600e3)) attempts.delete(ip); }, 600e3).unref();

function readBody(req, limit = 4096) {
  return new Promise((resolve, reject) => { let d = ''; req.on('data', c => { d += c; if (d.length > limit) { reject(new Error('body too large')); req.destroy(); } }); req.on('end', () => resolve(d)); req.on('error', reject); });
}

// ---------- provider ----------
const cache = { sports: { at: 0, data: null }, fixtures: { at: 0, data: null, meta: null }, props: new Map() };
let lastQuota = null, lastError = null;

async function provider(pathname, params = {}) {
  if (!process.env.ODDS_API_KEY) { const e = new Error('provider_not_configured'); e.code = 'provider_not_configured'; throw e; }
  const u = new URL(ODDS_BASE + pathname);
  u.searchParams.set('apiKey', process.env.ODDS_API_KEY);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const res = await fetch(u, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(15000) });
  lastQuota = A.quotaFromHeaders(res.headers);
  if (!res.ok) { const e = new Error(`provider ${res.status}`); e.code = res.status === 401 ? 'provider_unauthorized' : res.status === 429 ? 'provider_quota_exhausted' : 'provider_error'; e.status = res.status; throw e; }
  return res.json();
}

async function sports() {
  if (cache.sports.data && Date.now() - cache.sports.at < 6 * 3600e3) return cache.sports.data;
  const all = await provider('/v4/sports/');          // free call: does not count against quota
  const picked = A.selectSoccerSports(all, undefined, SPORT_KEYS.length ? SPORT_KEYS : null);
  cache.sports = { at: Date.now(), data: picked };
  return picked;
}

let inflight = null;
async function fixtures(force = false) {
  if (!force && cache.fixtures.data && Date.now() - cache.fixtures.at < CACHE_S * 1e3) return { rows: cache.fixtures.data, meta: cache.fixtures.meta, cached: true };
  if (inflight) return inflight;   // collapse concurrent refreshes so one burst costs one fetch
  inflight = (async () => {
    const leagues = await sports();
    const rows = [], errors = [];
    for (const s of leagues) {
      try {
        const events = await provider(`/v4/sports/${encodeURIComponent(s.key)}/odds/`, { regions: REGIONS, markets: 'h2h,totals', oddsFormat: 'decimal', dateFormat: 'iso' });
        rows.push(...A.normaliseEvents(events));
      } catch (e) { errors.push({ league: s.key, error: e.code || e.message }); if (e.code === 'provider_quota_exhausted' || e.code === 'provider_unauthorized') throw e; }
    }
    const meta = { provider: 'the-odds-api', regions: REGIONS, leagues: leagues.map(l => ({ key: l.key, title: l.title })), fetched_at: new Date().toISOString(), quota: lastQuota, errors };
    cache.fixtures = { at: Date.now(), data: rows, meta };
    lastError = null;
    return { rows, meta, cached: false };
  })();
  try { return await inflight; } finally { inflight = null; }
}

async function eventProps(sportKey, eventId) {
  const k = `${sportKey}/${eventId}`; const c = cache.props.get(k);
  if (c && Date.now() - c.at < CACHE_S * 1e3) return c.data;
  const ev = await provider(`/v4/sports/${encodeURIComponent(sportKey)}/events/${encodeURIComponent(eventId)}/odds/`, { regions: 'us', markets: 'player_shots,player_shots_on_target,player_goal_scorer_anytime', oddsFormat: 'decimal', dateFormat: 'iso' });
  const data = A.normalisePlayerProps(ev);
  if (cache.props.size > 500) cache.props.clear();
  cache.props.set(k, { at: Date.now(), data });
  return data;
}

const PROVIDER_MESSAGES = {
  provider_not_configured: 'No odds provider key is configured on the server (ODDS_API_KEY). Lines are unavailable; nothing is simulated.',
  provider_unauthorized: 'The odds provider rejected the configured key.',
  provider_quota_exhausted: 'The odds provider quota for this period is exhausted.',
};
function providerError(res, e) {
  lastError = e.code || e.message;
  const status = e.code === 'provider_not_configured' || e.code === 'provider_quota_exhausted' ? 503 : 502;
  return json(res, status, { error: e.code || 'provider_error', message: PROVIDER_MESSAGES[e.code] || 'The odds provider request failed.', quota: lastQuota });
}

// ---------- routes ----------
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');

  if (p === '/healthz') return json(res, 200, { ok: true, gated: GATED, provider_configured: !!process.env.ODDS_API_KEY });

  if (p === '/config.js') {
    const cfg = { gate: false, fixturesUrl: '/api/fixtures', propsUrl: '/api/props', dataBase: '/', homeUrl: HOME_URL, labUrl: '/altitude_fc/altitude_fc_cards.html', serverGated: GATED };
    return text(res, 200, `window.AFTER_HOURS_CONFIG = ${JSON.stringify(cfg)};`, 'text/javascript; charset=utf-8');
  }

  // gate
  if (p === '/enter' && req.method === 'POST') {
    if (!GATED) return redirect(res, '/');
    if (limited(clientIp(req))) return text(res, 429, 'Too many attempts. Try again later.');
    let body; try { body = new URLSearchParams(await readBody(req)); } catch { return text(res, 400, 'Bad request'); }
    const code = (body.get('code') || '').trim().toUpperCase().replace(/\s+/g, '');
    const adult = body.get('adult') === 'on' || body.get('adult') === 'true';
    if (!adult) return redirect(res, '/enter.html?err=adult');
    if (!INVITES.some(c => timingEqual(c, code))) return redirect(res, '/enter.html?err=code');
    const cookie = `ah_session=${makeSession()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_HOURS * 3600}${secure(req) ? '; Secure' : ''}`;
    return redirect(res, '/', { 'Set-Cookie': cookie });
  }
  if (p === '/leave') return redirect(res, '/enter.html', { 'Set-Cookie': 'ah_session=; Path=/; HttpOnly; Max-Age=0' });
  if (p === '/enter.html') return authed(req) && GATED ? redirect(res, '/') : serveFile(res, '/enter.html');
  if (p === '/after-hours.css') return serveFile(res, p);   // the gate page needs the stylesheet

  if (!authed(req)) {
    if (p.startsWith('/api/')) return json(res, 401, { error: 'unauthorized', message: 'Enter with an invite code first.' });
    return redirect(res, '/enter.html');
  }

  // API
  if (p === '/api/status') {
    try { const leagues = process.env.ODDS_API_KEY ? await sports() : []; return json(res, 200, { provider: 'the-odds-api', provider_configured: !!process.env.ODDS_API_KEY, regions: REGIONS, leagues, cache_seconds: CACHE_S, quota: lastQuota, last_error: lastError, fixtures_cached_at: cache.fixtures.at ? new Date(cache.fixtures.at).toISOString() : null }); }
    catch (e) { return providerError(res, e); }
  }
  if (p === '/api/fixtures') {
    try { const r = await fixtures(url.searchParams.get('refresh') === '1'); return json(res, 200, { fixtures: r.rows, meta: Object.assign({}, r.meta, { cached: r.cached }) }); }
    catch (e) { return providerError(res, e); }
  }
  if (p === '/api/props') {
    const sport = url.searchParams.get('sport'), id = url.searchParams.get('event');
    if (!sport || !id || !/^[a-z0-9_]+$/.test(sport) || !/^[A-Za-z0-9_-]+$/.test(id)) return json(res, 400, { error: 'bad_request', message: 'sport and event are required' });
    try { return json(res, 200, await eventProps(sport, id)); } catch (e) { return providerError(res, e); }
  }
  if (p.startsWith('/api/')) return json(res, 404, { error: 'not_found' });

  // static
  if (p === '/' || p === '/after-hours' || p === '/after-hours/') return serveFile(res, '/after-hours.html');
  return serveFile(res, p);
});

function serveFile(res, p) {
  if (!STATIC_ALLOW.some(rx => rx.test(p))) return text(res, 404, 'Not found');
  const fp = path.join(ROOT, p);
  if (!fp.startsWith(ROOT + path.sep)) return text(res, 403, 'Forbidden');
  fs.readFile(fp, (err, data) => {
    if (err) return text(res, 404, 'Not found');
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(fp)] || 'application/octet-stream', 'Cache-Control': p.endsWith('.json') ? 'public, max-age=300' : 'public, max-age=60' });
    res.end(data);
  });
}

if (require.main === module) {
  server.listen(PORT, () => console.log(`After Hours on :${PORT} gated=${GATED} provider=${process.env.ODDS_API_KEY ? 'configured' : 'NOT configured'} regions=${REGIONS} cache=${CACHE_S}s`));
}
module.exports = { server };
