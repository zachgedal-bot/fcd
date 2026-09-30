/**
 * Odds provider adapter: The Odds API v4 -> After Hours fixtures JSON.
 * Pure functions only (no network) so they can be unit-tested; server.js does the fetching.
 *
 * Provider contract (v4):
 *   GET {base}/v4/sports/?apiKey=K                                   -> [{key, group, title, active, has_outrights}]
 *   GET {base}/v4/sports/{sport}/odds/?apiKey=K&regions=us,eu&markets=h2h,totals&oddsFormat=decimal&dateFormat=iso
 *       -> [{id, sport_key, sport_title, commence_time, home_team, away_team,
 *            bookmakers:[{key,title,last_update,markets:[{key,last_update,outcomes:[{name,price,point?}]}]}]}]
 *   h2h outcomes are named home_team / away_team / "Draw"; totals outcomes "Over"/"Under" with point.
 *   GET {base}/v4/sports/{sport}/events/{eventId}/odds/?...&markets=player_shots,player_shots_on_target,player_goal_scorer_anytime
 *       -> one event; player outcomes: {name: "Over"|"Under"|"Yes", description: player, price, point?}
 *   Quota headers: x-requests-remaining, x-requests-used, x-requests-last. Cost = markets x regions per call.
 */
'use strict';

// Sharpest first. Pinnacle is in the eu region.
const BOOK_PREFERENCE = ['pinnacle', 'betfair_ex_eu', 'betfair_ex_uk', 'matchbook', 'draftkings', 'fanduel', 'betmgm', 'williamhill_us', 'bovada', 'betonlineag', 'unibet_eu', 'bet365', 'williamhill', 'onexbet', 'sport888', 'nordicbet', 'betsson', 'marathonbet'];

// Leagues the desks care about. Matched against provider sport key or title, case-insensitive.
const DEFAULT_LEAGUE_PATTERNS = [
  /ligamx|liga mx/i, /nwsl|women'?s soccer league/i, /libertadores/i, /sudamericana/i,
  /bolivia/i, /ecuador/i, /colombia/i, /peru/i, /copa america/i, /conmebol|south america/i, /usa_mls|\bmls\b/i,
];

function selectSoccerSports(sports, patterns = DEFAULT_LEAGUE_PATTERNS, explicitKeys = null) {
  const list = Array.isArray(sports) ? sports : [];
  if (explicitKeys && explicitKeys.length) {
    const want = new Set(explicitKeys);
    return list.filter(s => want.has(s.key));
  }
  return list.filter(s => (s.group === 'Soccer' || /^soccer_/.test(s.key || '')) && s.active !== false && !s.has_outrights &&
    patterns.some(p => p.test(s.key || '') || p.test(s.title || '')));
}

function median(xs) {
  const a = xs.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

function pickBook(bookmakers, marketKey, preference = BOOK_PREFERENCE) {
  const withMarket = (bookmakers || []).filter(b => (b.markets || []).some(m => m.key === marketKey));
  if (!withMarket.length) return null;
  for (const key of preference) {
    const b = withMarket.find(x => x.key === key);
    if (b) return b;
  }
  return withMarket[0];
}

function h2hFromBook(book, homeTeam, awayTeam) {
  const m = (book.markets || []).find(x => x.key === 'h2h');
  if (!m) return null;
  const find = name => m.outcomes.find(o => o.name === name);
  const h = find(homeTeam), a = find(awayTeam), d = m.outcomes.find(o => /^draw$/i.test(o.name));
  if (!h || !a || !d) return null;
  return { odds_h: h.price, odds_d: d.price, odds_a: a.price, book: book.key, updated: m.last_update || book.last_update };
}

function consensusH2h(bookmakers, homeTeam, awayTeam) {
  const rows = (bookmakers || []).map(b => h2hFromBook(b, homeTeam, awayTeam)).filter(Boolean);
  if (!rows.length) return null;
  return { odds_h: median(rows.map(r => r.odds_h)), odds_d: median(rows.map(r => r.odds_d)), odds_a: median(rows.map(r => r.odds_a)), book: `consensus(${rows.length})`, updated: null };
}

function totalsFromBook(book, line = 2.5) {
  const m = (book.markets || []).find(x => x.key === 'totals');
  if (!m) return null;
  const at = re => (m.outcomes || []).find(o => re.test(o.name) && Number.isFinite(o.point) && Math.abs(o.point - line) < 1e-9);
  const over = at(/^over$/i), under = at(/^under$/i);
  if (!over || !under) return null;
  return { odds_over25: over.price, odds_under25: under.price, book: book.key };
}

/** First book in preference order that actually posts Over/Under at `line`; then any book that does. */
function pickTotals(bookmakers, line = 2.5, preference = BOOK_PREFERENCE) {
  const books = bookmakers || [];
  for (const key of preference) { const b = books.find(x => x.key === key); const t = b && totalsFromBook(b, line); if (t) return t; }
  for (const b of books) { const t = totalsFromBook(b, line); if (t) return t; }
  return null;
}

/** Normalise one provider event into the fixtures row the Altitude Book reads. */
function normaliseEvent(ev, opts = {}) {
  const preferSharp = opts.preferSharp !== false;
  const h2hBook = preferSharp ? pickBook(ev.bookmakers, 'h2h') : null;
  const h2h = (h2hBook && h2hFromBook(h2hBook, ev.home_team, ev.away_team)) || consensusH2h(ev.bookmakers, ev.home_team, ev.away_team);
  const tot = pickTotals(ev.bookmakers, 2.5);
  return {
    id: ev.id,
    date: (ev.commence_time || '').slice(0, 10),
    kickoff: ev.commence_time || '',
    league: ev.sport_title || ev.sport_key || '',
    sport_key: ev.sport_key || '',
    home: ev.home_team, away: ev.away_team,
    odds_h: h2h ? h2h.odds_h : '', odds_d: h2h ? h2h.odds_d : '', odds_a: h2h ? h2h.odds_a : '',
    odds_over25: tot ? tot.odds_over25 : '', odds_under25: tot ? tot.odds_under25 : '',
    days_since_arrival: '', venue_alt: '',   // unknown: the page falls back to its 'default days since arrival' control
    note: h2h ? `${h2h.book}${h2h.updated ? ' ' + h2h.updated : ''}` : 'no h2h market posted',
  };
}

/** Pre-match rows only: events whose commence_time has passed carry in-play prices and are dropped. */
function normaliseEvents(events, now = Date.now()) {
  return (Array.isArray(events) ? events : [])
    .filter(ev => { const t = Date.parse(ev.commence_time); return !Number.isFinite(t) || t > now; })
    .map(normaliseEvent);
}

/** Player props from the event-odds endpoint -> Props Desk lines per side.
 *  A shots line is accepted only when ONE bookmaker posts both Over and Under at the SAME point, so the pair is a real
 *  two-way line; books are tried in BOOK_PREFERENCE order (then provider order) independently per player and market.
 *  The provider does not tag players by team, so `players` is one list; the desk asks the user to split sides. */
function normalisePlayerProps(ev, preference = BOOK_PREFERENCE) {
  const books = (ev.bookmakers || []).slice().sort((x, y) => { const ix = preference.indexOf(x.key), iy = preference.indexOf(y.key); return (ix < 0 ? 1e9 : ix) - (iy < 0 ? 1e9 : iy); });
  const players = new Map();
  const get = name => { if (!players.has(name)) players.set(name, { name, pos: 'MF' }); return players.get(name); };
  const bestLine = marketKey => {
    const out = new Map(); // player -> {line, o_over, o_under, book}
    for (const b of books) {
      const m = (b.markets || []).find(x => x.key === marketKey); if (!m) continue;
      const byPlayerPoint = new Map();
      for (const o of m.outcomes || []) {
        if (!Number.isFinite(o.point)) continue;
        const k = `${o.description || o.name}\u0000${o.point}`;
        const e = byPlayerPoint.get(k) || { player: o.description || o.name, point: o.point };
        if (/^over$/i.test(o.name)) e.over = o.price; else if (/^under$/i.test(o.name)) e.under = o.price;
        byPlayerPoint.set(k, e);
      }
      for (const e of byPlayerPoint.values()) {
        if (e.over == null || e.under == null || out.has(e.player)) continue;   // first (most preferred) complete pair wins
        out.set(e.player, { line: e.point, o_over: e.over, o_under: e.under, book: b.key });
      }
    }
    return out;
  };
  for (const [player, v] of bestLine('player_shots')) Object.assign(get(player), v);
  for (const [player, v] of bestLine('player_shots_on_target')) get(player).sot = v;
  for (const b of books) {
    const m = (b.markets || []).find(x => x.key === 'player_goal_scorer_anytime'); if (!m) continue;
    for (const o of m.outcomes || []) { if (/^yes$/i.test(o.name) || !/^no$/i.test(o.name)) { const p = get(o.description || o.name); if (p.scorer == null) p.scorer = o.price; } }
  }
  return { id: ev.id, home: ev.home_team, away: ev.away_team, kickoff: ev.commence_time, players: [...players.values()].filter(p => p.line != null || p.sot || p.scorer != null) };
}

function quotaFromHeaders(h) {
  const g = k => { const v = typeof h.get === 'function' ? h.get(k) : h[k]; return v == null ? null : Number(v); };
  return { remaining: g('x-requests-remaining'), used: g('x-requests-used'), last_cost: g('x-requests-last') };
}

module.exports = { BOOK_PREFERENCE, DEFAULT_LEAGUE_PATTERNS, selectSoccerSports, pickBook, h2hFromBook, consensusH2h, totalsFromBook, pickTotals, normaliseEvent, normaliseEvents, normalisePlayerProps, quotaFromHeaders, median };
