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
  const over = m.outcomes.find(o => /^over$/i.test(o.name) && Math.abs((o.point ?? line) - line) < 1e-9);
  const under = m.outcomes.find(o => /^under$/i.test(o.name) && Math.abs((o.point ?? line) - line) < 1e-9);
  if (!over || !under) return null;
  return { odds_over25: over.price, odds_under25: under.price };
}

/** Normalise one provider event into the fixtures row the Altitude Book reads. */
function normaliseEvent(ev, opts = {}) {
  const preferSharp = opts.preferSharp !== false;
  const h2hBook = preferSharp ? pickBook(ev.bookmakers, 'h2h') : null;
  const h2h = (h2hBook && h2hFromBook(h2hBook, ev.home_team, ev.away_team)) || consensusH2h(ev.bookmakers, ev.home_team, ev.away_team);
  const totBook = pickBook(ev.bookmakers, 'totals');
  const tot = totBook ? totalsFromBook(totBook) : null;
  return {
    id: ev.id,
    date: (ev.commence_time || '').slice(0, 10),
    kickoff: ev.commence_time || '',
    league: ev.sport_title || ev.sport_key || '',
    sport_key: ev.sport_key || '',
    home: ev.home_team, away: ev.away_team,
    odds_h: h2h ? h2h.odds_h : '', odds_d: h2h ? h2h.odds_d : '', odds_a: h2h ? h2h.odds_a : '',
    odds_over25: tot ? tot.odds_over25 : '', odds_under25: tot ? tot.odds_under25 : '',
    days_since_arrival: 1, venue_alt: '',
    note: h2h ? `${h2h.book}${h2h.updated ? ' ' + h2h.updated : ''}` : 'no h2h market posted',
  };
}

function normaliseEvents(events) {
  return (Array.isArray(events) ? events : []).map(normaliseEvent);
}

/** Player props from the event-odds endpoint -> Props Desk lines per side. */
function normalisePlayerProps(ev) {
  const players = new Map(); // player -> {name, line, o_over, o_under, scorer}
  const get = name => { if (!players.has(name)) players.set(name, { name, pos: 'MF' }); return players.get(name); };
  for (const b of ev.bookmakers || []) {
    for (const m of b.markets || []) {
      if (m.key === 'player_shots' || m.key === 'player_shots_on_target') {
        for (const o of m.outcomes || []) {
          const p = get(o.description || o.name);
          const bucket = m.key === 'player_shots' ? p : (p.sot = p.sot || {});
          if (/^over$/i.test(o.name) && bucket.o_over == null) { bucket.line = o.point; bucket.o_over = o.price; bucket.book = b.key; }
          if (/^under$/i.test(o.name) && bucket.o_under == null) { bucket.line = o.point; bucket.o_under = o.price; }
        }
      }
      if (m.key === 'player_goal_scorer_anytime') {
        for (const o of m.outcomes || []) {
          if (/^yes$/i.test(o.name) || !/^(no)$/i.test(o.name)) { const p = get(o.description || o.name); if (p.scorer == null) p.scorer = o.price; }
        }
      }
    }
  }
  return { id: ev.id, home: ev.home_team, away: ev.away_team, kickoff: ev.commence_time, players: [...players.values()] };
}

function quotaFromHeaders(h) {
  const g = k => { const v = typeof h.get === 'function' ? h.get(k) : h[k]; return v == null ? null : Number(v); };
  return { remaining: g('x-requests-remaining'), used: g('x-requests-used'), last_cost: g('x-requests-last') };
}

module.exports = { BOOK_PREFERENCE, DEFAULT_LEAGUE_PATTERNS, selectSoccerSports, pickBook, h2hFromBook, consensusH2h, totalsFromBook, normaliseEvent, normaliseEvents, normalisePlayerProps, quotaFromHeaders, median };
