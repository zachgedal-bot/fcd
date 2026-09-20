/* Athlemix After Hours — browser port of altitude_edge/model.py + physio.py.
   Kept dependency-free so it runs from file:// or any static host, and under Node for cross-checks. */
(function (root) {
  'use strict';

  // ---------- physiology ----------
  const PHYSIO = { threshold_m: 300, pct_per_1000: 5.4, never: 0.35, fast: 0.40, tau_fast: 2.0, slow: 0.25, tau_slow: 10.0, max_pct: 30 };
  function remaining(days, p = PHYSIO) {
    const d = Math.max(0, +days || 0);
    return p.never + p.fast * Math.exp(-d / p.tau_fast) + p.slow * Math.exp(-d / p.tau_slow);
  }
  function hirDecrement(matchAlt, resAlt, days = 1, p = PHYSIO) {
    const delta = Math.max(0, matchAlt - resAlt - p.threshold_m);
    return Math.min(p.max_pct, p.pct_per_1000 * delta / 1000 * remaining(days, p));
  }

  // ---------- model ----------
  const DEFAULT_PARAMS = {
    k_goals_per_10pct_hir: 0.35, conceded_share: 0.5, residual_share: 0.25, habituation_discount: 0.5,
    descending_goals: 0.15, descending_threshold_m: 1500, rho: -0.05, physio: PHYSIO,
  };
  const MAXG = 10;
  const FACT = [1]; for (let i = 1; i <= MAXG; i++) FACT[i] = FACT[i - 1] * i;
  const pois = (l, k) => Math.exp(-l) * Math.pow(l, k) / FACT[k];
  function dcTau(x, y, lh, la, rho) {
    if (x === 0 && y === 0) return 1 - lh * la * rho;
    if (x === 0 && y === 1) return 1 + lh * rho;
    if (x === 1 && y === 0) return 1 + la * rho;
    if (x === 1 && y === 1) return 1 - rho;
    return 1;
  }
  function outcomeProbs(lh, la, rho = 0) {
    let s = 0, ph = 0, pd = 0, over = 0;
    const m = [];
    for (let x = 0; x <= MAXG; x++) { m[x] = []; for (let y = 0; y <= MAXG; y++) { const v = pois(lh, x) * pois(la, y) * dcTau(x, y, lh, la, rho); m[x][y] = v; s += v; } }
    for (let x = 0; x <= MAXG; x++) for (let y = 0; y <= MAXG; y++) { const v = m[x][y] / s; if (x > y) ph += v; else if (x === y) pd += v; if (x + y > 2.5) over += v; }
    return { home: ph, draw: pd, away: 1 - ph - pd, over25: over, under25: 1 - over };
  }
  function devig(oh, od, oa) {
    const q = [1 / oh, 1 / od, 1 / oa];
    let lo = 0.5, hi = 2.0, k = 1;
    for (let i = 0; i < 60; i++) { k = (lo + hi) / 2; const s = q.reduce((a, x) => a + Math.pow(x, k), 0); if (s > 1) lo = k; else hi = k; }
    k = (lo + hi) / 2;
    return q.map(x => Math.pow(x, k));
  }
  function impliedLambdas(ph, pd, pa, rho = 0) {
    let lh = Math.max(0.2, 1.35 + 1.2 * (ph - pa)), la = Math.max(0.2, 1.35 - 1.2 * (ph - pa));
    const h = 1e-4;
    for (let it = 0; it < 40; it++) {
      const p = outcomeProbs(lh, la, rho);
      const f1 = p.home - ph, f2 = p.away - pa;
      if (Math.abs(f1) < 1e-7 && Math.abs(f2) < 1e-7) return [lh, la];
      const p1 = outcomeProbs(lh + h, la, rho), p2 = outcomeProbs(lh, la + h, rho);
      const j11 = (p1.home - p.home) / h, j12 = (p2.home - p.home) / h, j21 = (p1.away - p.away) / h, j22 = (p2.away - p.away) / h;
      const det = j11 * j22 - j12 * j21; if (Math.abs(det) < 1e-12) break;
      const dh = (-f1 * j22 + f2 * j12) / det, da = (-f2 * j11 + f1 * j21) / det;
      const scale = Math.max(1, Math.abs(dh) / 0.5, Math.abs(da) / 0.5);
      lh = Math.max(0.05, lh + dh / scale); la = Math.max(0.05, la + da / scale);
    }
    return [lh, la];
  }
  function altitudeAdjustment(matchAlt, homeRes, awayRes, days, homeHab, awayHab, P = DEFAULT_PARAMS) {
    const phys = P.physio || PHYSIO;
    let awayDec = hirDecrement(matchAlt, awayRes, days, phys);
    let homeDec = hirDecrement(matchAlt, homeRes, 1000, phys);
    if (awayHab) awayDec *= P.habituation_discount;
    if (homeHab) homeDec *= P.habituation_discount;
    const swA = P.k_goals_per_10pct_hir * awayDec / 10, swH = P.k_goals_per_10pct_hir * homeDec / 10;
    let dHome = swA * P.conceded_share - swH * (1 - P.conceded_share);
    let dAway = -swA * (1 - P.conceded_share) + swH * P.conceded_share;
    const descAway = awayRes - matchAlt > P.descending_threshold_m, descHome = homeRes - matchAlt > P.descending_threshold_m;
    if (descAway) dAway -= P.descending_goals;
    if (descHome) dHome -= P.descending_goals;
    const r = P.residual_share;
    return { away_hir_dec_pct: awayDec, home_hir_dec_pct: homeDec, d_lambda_home_full: dHome, d_lambda_away_full: dAway, d_lambda_home: dHome * r, d_lambda_away: dAway * r, away_descending: descAway, home_descending: descHome };
  }
  function priceFixture(oh, od, oa, matchAlt, homeRes, awayRes, days = 1, homeHab = false, awayHab = false, P = DEFAULT_PARAMS, o25, u25) {
    const [ph, pd, pa] = devig(oh, od, oa);
    const [lh, la] = impliedLambdas(ph, pd, pa, P.rho);
    const adj = altitudeAdjustment(matchAlt, homeRes, awayRes, days, homeHab, awayHab, P);
    const lh2 = Math.max(0.05, lh + adj.d_lambda_home), la2 = Math.max(0.05, la + adj.d_lambda_away);
    const pm = outcomeProbs(lh2, la2, P.rho);
    const mkt = { home: ph, draw: pd, away: pa }, odds = { home: oh, draw: od, away: oa };
    if (o25 && u25) { odds.over25 = o25; odds.under25 = u25; const q = [1 / o25, 1 / u25], s = q[0] + q[1]; mkt.over25 = q[0] / s; mkt.under25 = q[1] / s; }
    const edges = {};
    for (const k of Object.keys(odds)) { const o = odds[k]; const ev = pm[k] * o - 1; edges[k] = { model_p: pm[k], market_p: mkt[k], odds: o, ev, kelly: o > 1 ? Math.max(0, ev / (o - 1)) : 0 }; }
    return { market_lambda_home: lh, market_lambda_away: la, model_lambda_home: lh2, model_lambda_away: la2, model_probs: pm, market_probs: mkt, edges, adjustment: adj };
  }

  // ---------- venues ----------
  function norm(s) { return String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\./g, ' ').split(/\s+/).filter(Boolean).join(' '); }
  function makeLookup(vdata) {
    const idx = {};
    for (const k of Object.keys(vdata.venues)) idx[norm(k)] = k;
    for (const [a, k] of Object.entries(vdata.aliases || {})) idx[norm(a)] = k;
    const habitual = new Set(vdata.habitual_leagues || []);
    return function lookup(name) {
      const key = norm(name);
      let canon = idx[key];
      if (!canon) { for (const [k, v] of Object.entries(idx)) { if (k.includes(key) || key.includes(k)) { canon = v; break; } } }
      if (!canon) return null;
      const v = vdata.venues[canon];
      return { name: canon, city: v.city, alt: v.alt, league: v.league, habitual: habitual.has(v.league) };
    };
  }

  // ---------- courtside (NWSL) ----------
  function courtside({ goals = 2.8, f = 0.35, L = 150, r = 0.45, fee = 0.017, travel = 700, risk = 100 }) {
    const gross = goals * f * L * r * (1 - fee);
    return { gross, net: gross - travel - risk, breakevenL: (travel + risk) / (goals * f * r * (1 - fee)) };
  }


  // ---------- lineup desk ----------
  const LINEUP_DEFAULT = { goals_per_point: 0.10, own_share: 0.6, market_awareness: 0.0, skew_flag_points: 1.5 };
  function xiRating(players) { if (!players || !players.length) return null; let sw = 0, s = 0; for (const p of players) { const w = +p.weight || 1; sw += w; s += (+p.rating) * w; } return s / sw; }
  function bestXI(squad, n = 11) { return squad.slice().sort((a, b) => b.rating - a.rating).slice(0, n); }
  function lineupAdjustment(projected, reference, P = LINEUP_DEFAULT) {
    const d = xiRating(projected) - xiRating(reference), g = P.goals_per_point * (1 - P.market_awareness);
    return { d_rating: d, d_lambda_own: g * d * P.own_share, d_lambda_opp: -g * d * (1 - P.own_share), skewed: Math.abs(d) >= P.skew_flag_points };
  }
  function edgesFrom(pm, mkt, odds) { const e = {}; for (const k of Object.keys(odds)) { const o = odds[k], ev = pm[k] * o - 1; e[k] = { model_p: pm[k], market_p: mkt[k], odds: o, ev, kelly: o > 1 ? Math.max(0, ev / (o - 1)) : 0 }; } return e; }
  function priceLineups(oh, od, oa, homeProj, homeRef, awayProj, awayRef, P = LINEUP_DEFAULT, rho = -0.05) {
    const [ph, pd, pa] = devig(oh, od, oa); const [lh, la] = impliedLambdas(ph, pd, pa, rho);
    const H = lineupAdjustment(homeProj, homeRef, P), A = lineupAdjustment(awayProj, awayRef, P);
    const lh2 = Math.max(0.05, lh + H.d_lambda_own + A.d_lambda_opp), la2 = Math.max(0.05, la + A.d_lambda_own + H.d_lambda_opp);
    const pm = outcomeProbs(lh2, la2, rho);
    return { market_lambda_home: lh, market_lambda_away: la, model_lambda_home: lh2, model_lambda_away: la2, home: H, away: A, model_probs: pm, edges: edgesFrom(pm, { home: ph, draw: pd, away: pa }, { home: oh, draw: od, away: oa }) };
  }

  // ---------- props desk ----------
  const XG_PER_SHOT = { FW: 0.12, AM: 0.10, MF: 0.08, WB: 0.06, DF: 0.05, GK: 0.01 };
  const PROPS_DEFAULT = { coverage: null, blend: 0.5, rho: -0.05 };
  const defaultCoverage = n => Math.min(0.95, 0.13 + 0.12 * Math.max(0, n));
  function poisCdf(mu, k) { let s = 0; for (let i = 0; i <= k; i++) s += Math.exp(-mu) * Math.pow(mu, i) / FACT[Math.min(i, MAXG)] * (i > MAXG ? 0 : 1); return s; }
  function shotsMeanFromLine(line, oOver, oUnder) {
    const q = [1 / oOver, 1 / oUnder], pOver = q[0] / (q[0] + q[1]), k = Math.floor(line);
    let lo = 0.01, hi = 15;
    for (let i = 0; i < 60; i++) { const mu = (lo + hi) / 2; if (1 - poisCdf(mu, k) < pOver) lo = mu; else hi = mu; }
    return (lo + hi) / 2;
  }
  function playerXg(p) {
    let shots = p.shots; if (shots == null || shots === '') shots = shotsMeanFromLine(+p.line, +p.o_over, +p.o_under);
    const xps = +p.xg_per_shot || XG_PER_SHOT[(p.pos || 'MF').toUpperCase()] || 0.08, xg = (+shots) * xps;
    return { name: p.name || '?', pos: p.pos, shots: +shots, xg_per_shot: xps, xg, p_score: 1 - Math.exp(-xg) };
  }
  function teamXg(players, P = PROPS_DEFAULT) {
    const rows = players.map(playerXg), listed = rows.reduce((a, r) => a + r.xg, 0), cov = P.coverage || defaultCoverage(rows.length);
    return { players: rows, listed_xg: listed, coverage: cov, team_xg: cov > 0 ? listed / cov : listed };
  }
  function priceProps(oh, od, oa, homePlayers, awayPlayers, P = PROPS_DEFAULT, o25, u25, scorerOdds = {}) {
    const rho = P.rho; const [ph, pd, pa] = devig(oh, od, oa); const [lh, la] = impliedLambdas(ph, pd, pa, rho);
    const H = teamXg(homePlayers, P), A = teamXg(awayPlayers, P), b = P.blend;
    const lh2 = b * H.team_xg + (1 - b) * lh, la2 = b * A.team_xg + (1 - b) * la, pm = outcomeProbs(lh2, la2, rho);
    const odds = { home: oh, draw: od, away: oa }, mkt = { home: ph, draw: pd, away: pa };
    if (o25 && u25) { odds.over25 = o25; odds.under25 = u25; const q = [1 / o25, 1 / u25], s = q[0] + q[1]; mkt.over25 = q[0] / s; mkt.under25 = q[1] / s; }
    const scorers = [];
    for (const [side, T] of [['home', H], ['away', A]]) for (const r of T.players) { const o = +scorerOdds[r.name] || null; scorers.push({ side, ...r, odds: o, ev: o ? r.p_score * o - 1 : null }); }
    return { market_lambda_home: lh, market_lambda_away: la, props_xg_home: H.team_xg, props_xg_away: A.team_xg, coverage_home: H.coverage, coverage_away: A.coverage, model_lambda_home: lh2, model_lambda_away: la2, model_probs: pm, edges: edgesFrom(pm, mkt, odds), scorers };
  }

  const api = { LINEUP_DEFAULT, PROPS_DEFAULT, XG_PER_SHOT, xiRating, bestXI, lineupAdjustment, priceLineups, shotsMeanFromLine, playerXg, teamXg, priceProps, defaultCoverage, PHYSIO, DEFAULT_PARAMS, hirDecrement, remaining, outcomeProbs, devig, impliedLambdas, altitudeAdjustment, priceFixture, makeLookup, norm, courtside };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.AfterHoursModel = api;
})(typeof window !== 'undefined' ? window : globalThis);
