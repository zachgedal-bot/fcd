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
 *   ODDS_REFRESH_TOKEN       optional ops token. Set -> GET /api/fixtures?refresh=1 with header x-refresh-token forces a refresh. Unset -> refresh=1 is ignored.
 *   ODDS_MIN_REFRESH_SECONDS default 60. Floor between forced refreshes, whoever asks, so the force path cannot drain the quota.
 *   API_RATE_LIMIT           default 60. Max /api/fixtures + /api/props requests per client IP per minute (429 beyond).
 *   AFTER_HOURS_INVITE_CODES comma list. Set -> the page and API require a session cookie obtained at /enter with a code + 18+ attestation.
 *   SESSION_SECRET           HMAC secret for the session cookie (required when invite codes are set)
 *   SESSION_HOURS            default 168
 *   HOME_URL                 where "<- AthleMix" points, default https://athlemix.com
 *   TRUST_PROXY              number of trusted reverse-proxy hops in front of this server: 1 for Render/Fly/Railway alone,
 *                            2 with Cloudflare in front of them. The client IP is the X-Forwarded-For entry that many hops
 *                            from the RIGHT; anything left of it is client-supplied. 0/unset = no proxy.
 *   CLIENT_IP_HEADER         optional authenticated client-IP header from the platform, e.g. fly-client-ip, true-client-ip,
 *                            cf-connecting-ip, x-real-ip. Preferred over X-Forwarded-For when set.
 */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { URL } = require('url');
const net = require('net');
const A = require('./adapter');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PORT || 8080);
const ODDS_BASE = (process.env.ODDS_API_BASE || 'https://api.the-odds-api.com').replace(/\/$/, '');
const REGIONS = process.env.ODDS_REGIONS || 'us,eu';
const CACHE_S = Number(process.env.ODDS_CACHE_SECONDS || 300);
const REFRESH_TOKEN = process.env.ODDS_REFRESH_TOKEN || '';
const MIN_REFRESH_S = Number(process.env.ODDS_MIN_REFRESH_SECONDS || 60);
const API_RATE_LIMIT = Number(process.env.API_RATE_LIMIT || 60);
const SPORT_KEYS = (process.env.ODDS_SPORT_KEYS || '').split(',').map(s => s.trim()).filter(Boolean);
const INVITES = (process.env.AFTER_HOURS_INVITE_CODES || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
const GATED = INVITES.length > 0;
const SECRET = process.env.SESSION_SECRET || '';
const SESSION_HOURS = Number(process.env.SESSION_HOURS || 168);
const HOME_URL = process.env.HOME_URL || 'https://athlemix.com';
const TRUST_HOPS = /^\d+$/.test(process.env.TRUST_PROXY || '') ? Number(process.env.TRUST_PROXY) : 0;
const TRUST_PROXY = TRUST_HOPS > 0;
const CLIENT_IP_HEADER = (process.env.CLIENT_IP_HEADER || '').trim().toLowerCase();

if (GATED && SECRET.length < 16) {
  console.error('AFTER_HOURS_INVITE_CODES is set but SESSION_SECRET is missing or shorter than 16 chars. Refusing to start gated without a real secret.');
  process.exit(1);
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml', '.csv': 'text/csv; charset=utf-8', '.md': 'text/markdown; charset=utf-8' };
// Only these paths are served. Python sources, tests and docs stay private.
// Served before the gate check; everything else is per-session and must never sit in a shared cache.
const PRE_GATE = new Set(['/enter.html', '/after-hours.css']);
const STATIC_ALLOW = [/^\/after-hours\.(html|css|js)$/, /^\/after-hours-ui\.js$/, /^\/enter\.html$/, /^\/altitude_edge\/(venues|fc_ratings_nwsl|fixtures_demo)\.json$/, /^\/altitude_fc\/altitude_fc_cards\.html$/, /^\/altitude_fc\/evidence_table\.(json|csv|md)$/, /^\/altitude_fc\/model_hir_curves\.png$/];

// ---------- helpers ----------
const json = (res, status, obj) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
const text = (res, status, s, type = 'text/plain; charset=utf-8') => { res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store' }); res.end(s); };
const redirect = (res, to, extra = {}) => { res.writeHead(303, Object.assign({ Location: to, 'Cache-Control': 'no-store' }, extra)); res.end(); };
const secure = req => TRUST_PROXY ? (req.headers['x-forwarded-proto'] || '').split(',')[0].trim() === 'https' : !!req.socket.encrypted;
// Client IP: the platform's authenticated header if configured, else the X-Forwarded-For entry appended by the outermost
// trusted proxy (TRUST_HOPS from the right). The leftmost XFF entry is client-controlled and is never used.
const clientIp = req => {
  if (TRUST_PROXY) {
    if (CLIENT_IP_HEADER) { const h = String(req.headers[CLIENT_IP_HEADER] || '').split(',')[0].trim(); if (h && net.isIP(h)) return h; }
    const xff = String(req.headers['x-forwarded-for'] || '').split(',').map(x => x.trim()).filter(Boolean);
    const ip = xff[xff.length - TRUST_HOPS];
    if (ip && net.isIP(ip)) return ip;
  }
  return req.socket.remoteAddress || '?';
};
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

// per-IP sliding-window limiters. /enter: 10 attempts per 10 minutes. Metered API (/api/fixtures, /api/props):
// API_RATE_LIMIT per minute, so client traffic cannot translate 1:1 into paid provider calls.
const MAX_TRACKED_IPS = 10000;   // hard bound: a flood of distinct IPs evicts the least recently seen instead of growing the Map
function makeLimiter(max, windowMs) {
  const hits = new Map();
  setInterval(() => { const now = Date.now(); for (const [ip, a] of hits) if (!a.some(t => now - t < windowMs)) hits.delete(ip); }, windowMs).unref();
  return ip => {
    const now = Date.now(); const a = (hits.get(ip) || []).filter(t => now - t < windowMs);
    hits.delete(ip);   // re-insert so Map iteration order is least-recently-seen first
    if (hits.size >= MAX_TRACKED_IPS) hits.delete(hits.keys().next().value);
    hits.set(ip, a);
    if (a.length >= max) return true; a.push(now); return false;
  };
}
const limited = makeLimiter(10, 600e3);
const meteredLimited = makeLimiter(API_RATE_LIMIT, 60e3);

function readBody(req, limit = 4096) {
  return new Promise((resolve, reject) => { let d = ''; req.on('data', c => { d += c; if (d.length > limit) { reject(new Error('body too large')); req.destroy(); } }); req.on('end', () => resolve(d)); req.on('error', reject); });
}

// ---------- provider ----------
const cache = { sports: { at: 0, data: null }, fixtures: { at: 0, data: null, meta: null }, props: new Map() };
let lastQuota = null, lastError = null;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const fail = (code, msg, status) => { const e = new Error(msg || code); e.code = code; if (status) e.status = status; return e; };

async function provider(pathname, params = {}, attempt = 0) {
  if (!process.env.ODDS_API_KEY) throw fail('provider_not_configured');
  const u = new URL(ODDS_BASE + pathname);
  u.searchParams.set('apiKey', process.env.ODDS_API_KEY);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  let res;
  try { res = await fetch(u, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(15000) }); }
  catch (err) { throw fail(err && err.name === 'TimeoutError' ? 'provider_timeout' : 'provider_unreachable', err && err.message); }
  lastQuota = A.quotaFromHeaders(res.headers);
  if (!res.ok) {
    let body = null; try { body = await res.json(); } catch { /* non-JSON error body */ }
    // The provider answers 429 for two conditions: OUT_OF_USAGE_CREDITS (monthly quota, fatal for the period) and
    // EXCEEDED_FREQ_LIMIT (>30 calls/s, transient). Only the former is quota exhaustion.
    if (res.status === 429 && body && body.error_code === 'EXCEEDED_FREQ_LIMIT') {
      if (attempt < 2) { await sleep(1000 * (attempt + 1)); return provider(pathname, params, attempt + 1); }
      throw fail('provider_rate_limited', 'provider rate limited', 429);
    }
    throw fail(res.status === 401 ? 'provider_unauthorized' : res.status === 429 ? 'provider_quota_exhausted' : 'provider_error', `provider ${res.status}`, res.status);
  }
  try { return await res.json(); } catch (err) { throw fail(err && err.name === 'TimeoutError' ? 'provider_timeout' : 'provider_error', err && err.message); }
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
  // A forced refresh only bypasses the cache once per MIN_REFRESH_S, so even the token holder cannot loop it into a quota drain.
  const ttl = (force ? Math.min(MIN_REFRESH_S, CACHE_S) : CACHE_S) * 1e3;
  if (cache.fixtures.data && Date.now() - cache.fixtures.at < ttl) return { rows: cache.fixtures.data, meta: cache.fixtures.meta, cached: true };
  if (inflight) return inflight;   // collapse concurrent refreshes so one burst costs one fetch
  inflight = (async () => {
    const leagues = await sports();
    const rows = [], errors = [];
    for (const s of leagues) {
      try {
        const events = await provider(`/v4/sports/${encodeURIComponent(s.key)}/odds/`, { regions: REGIONS, markets: 'h2h,totals', oddsFormat: 'decimal', dateFormat: 'iso', commenceTimeFrom: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') });
        rows.push(...A.normaliseEvents(events));   // also drops anything already kicked off: in-play prices are not pre-match lines
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
  // Only events on the current board are priced: bounds the metered key space to the real fixture set
  // instead of letting a caller spend credits on arbitrary ids.
  const { rows } = await fixtures();
  if (!rows.some(r => r.id === eventId && r.sport_key === sportKey)) { const e = new Error('unknown_event'); e.code = 'unknown_event'; throw e; }
  const ev = await provider(`/v4/sports/${encodeURIComponent(sportKey)}/events/${encodeURIComponent(eventId)}/odds/`, { regions: 'us', markets: 'player_shots,player_shots_on_target,player_goal_scorer_anytime', oddsFormat: 'decimal', dateFormat: 'iso' });
  const data = A.normalisePlayerProps(ev);
  if (cache.props.size > 500) cache.props.delete(cache.props.keys().next().value);   // evict the oldest entry, never the whole cache
  cache.props.set(k, { at: Date.now(), data });
  return data;
}

const PROVIDER_MESSAGES = {
  provider_not_configured: 'No odds provider key is configured on the server (ODDS_API_KEY). Lines are unavailable; nothing is simulated.',
  provider_unauthorized: 'The odds provider rejected the configured key.',
  provider_quota_exhausted: 'The odds provider quota for this period is exhausted.',
  provider_rate_limited: 'The odds provider is rate limiting requests. Try again in a few seconds.',
  provider_timeout: 'The odds provider did not answer within 15 seconds.',
  provider_unreachable: 'The odds provider could not be reached.',
};
function providerError(res, e) {
  lastError = e.code || e.message;
  if (e.code === 'provider_rate_limited') res.setHeader('Retry-After', '2');
  const status = ['provider_not_configured', 'provider_quota_exhausted', 'provider_rate_limited'].includes(e.code) ? 503 : 502;
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
  if (p === '/leave') { res.setHeader('Cache-Control', 'no-store'); return redirect(res, '/enter.html', { 'Set-Cookie': 'ah_session=; Path=/; HttpOnly; Max-Age=0' }); }
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
  // metered endpoints: throttle per client IP before anything can reach the paid provider
  if ((p === '/api/fixtures' || p === '/api/props') && meteredLimited(clientIp(req))) { res.setHeader('Retry-After', '60'); return json(res, 429, { error: 'rate_limited', message: 'Too many requests. Try again in a minute.' }); }
  if (p === '/api/fixtures') {
    // refresh=1 is an ops knob: honoured only with the configured token, and fixtures() floors it to one refresh per ODDS_MIN_REFRESH_SECONDS.
    const force = url.searchParams.get('refresh') === '1' && !!REFRESH_TOKEN && timingEqual(REFRESH_TOKEN, req.headers['x-refresh-token'] || '');
    try { const r = await fixtures(force); return json(res, 200, { fixtures: r.rows, meta: Object.assign({}, r.meta, { cached: r.cached }) }); }
    catch (e) { return providerError(res, e); }
  }
  if (p === '/api/props') {
    const sport = url.searchParams.get('sport'), id = url.searchParams.get('event');
    if (!sport || !id || !/^[a-z0-9_]+$/.test(sport) || !/^[A-Za-z0-9_-]+$/.test(id)) return json(res, 400, { error: 'bad_request', message: 'sport and event are required' });
    try { return json(res, 200, await eventProps(sport, id)); }
    catch (e) { return e.code === 'unknown_event' ? json(res, 404, { error: 'unknown_event', message: 'That event is not on the current board.' }) : providerError(res, e); }
  }
  if (p.startsWith('/api/')) return json(res, 404, { error: 'not_found' });

  // static
  // Canonical URL is /. The page uses relative asset paths (so it also works as a plain static folder), so at
  // /after-hours/ the browser would resolve them under /after-hours/ and 404. Redirect, keeping ?home=&away= deep links.
  if (p === '/after-hours' || p === '/after-hours/') return redirect(res, '/' + url.search);
  if (p === '/') return serveFile(res, '/after-hours.html');
  return serveFile(res, p);
});

function serveFile(res, p) {
  if (!STATIC_ALLOW.some(rx => rx.test(p))) return text(res, 404, 'Not found');
  const fp = path.join(ROOT, p);
  if (!fp.startsWith(ROOT + path.sep)) return text(res, 403, 'Forbidden');
  fs.readFile(fp, (err, data) => {
    if (err) return text(res, 404, 'Not found');
    const scope = GATED && !PRE_GATE.has(p) ? 'private' : 'public';
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(fp)] || 'application/octet-stream', 'Cache-Control': `${scope}, max-age=${p.endsWith('.json') ? 300 : 60}` });
    res.end(data);
  });
}

if (require.main === module) {
  server.listen(PORT, () => console.log(`After Hours on :${PORT} gated=${GATED} provider=${process.env.ODDS_API_KEY ? 'configured' : 'NOT configured'} regions=${REGIONS} cache=${CACHE_S}s`));
}
module.exports = { server };
