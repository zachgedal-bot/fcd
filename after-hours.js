/* Athlemix After Hours — browser port of altitude_edge/model.py + physio.py.
   Kept dependency-free so it runs from file:// or any static host, and under Node for cross-checks. */
(function (root) {
  'use strict';

  // ---------- physiology: Altitude FC model (altitude_fc/altitude_model.py) ----------
  const PHYSIO = { vo2max_pct_per_1000m: 6.3, vo2max_threshold_m: 300, hir_per_vo2_fraction: 0.7, rsa_per_vo2_fraction: 0.3, sprint_pct_per_1000m: 0.3,
    acclim_fast_tau_days: 3.5, acclim_fast_fraction: 0.40, acclim_slow_tau_days: 21.0, acclim_slow_fraction: 0.25, individual_spread_fraction: 0.25 };
  const RATING = { baseline: 80, sensitivity: 0.4, max_delta: 15, weights: {
    PAC: { single_sprint_speed: 0.5, repeated_sprint_recovery: 0.5 }, SHO: {}, PAS: {}, DRI: {},
    DEF: { high_intensity_running: 0.5, repeated_sprint_recovery: 0.5 }, PHY: { vo2max: 0.3, high_intensity_running: 0.7 },
    STAMINA: { vo2max: 0.4, high_intensity_running: 0.6 }, REPEATED_EFFORT: { repeated_sprint_recovery: 1.0 }, SPRINT_SPEED: { single_sprint_speed: 1.0 } } };
  function acclimFraction(days, p = PHYSIO) { if (days <= 0) return 0; return p.acclim_fast_fraction * (1 - Math.exp(-days / p.acclim_fast_tau_days)) + p.acclim_slow_fraction * (1 - Math.exp(-days / p.acclim_slow_tau_days)); }
  const vo2Deficit = (alt, p = PHYSIO) => -p.vo2max_pct_per_1000m * Math.max(0, alt - p.vo2max_threshold_m) / 1000;
  function physEffects(matchAlt, homeAlt, days, p = PHYSIO) {
    const vm = vo2Deficit(matchAlt, p), vh = vo2Deficit(homeAlt, p);
    let vo2 = 0, status = 'home', acclim = 1;
    if (matchAlt > homeAlt + 1e-9) { acclim = acclimFraction(days, p); vo2 = (vm - vh) * (1 - acclim); status = 'ascending'; }
    else if (matchAlt < homeAlt - 1e-9) status = 'descending_or_home';
    return { vo2max: vo2, high_intensity_running: p.hir_per_vo2_fraction * vo2, repeated_sprint_recovery: p.rsa_per_vo2_fraction * vo2,
      single_sprint_speed: p.sprint_pct_per_1000m * (matchAlt - homeAlt) / 1000, technical_execution: null, decision_making: null,
      _meta: { status, acclim, sleep_recovery_flag: status === 'ascending' && matchAlt - homeAlt >= 1500 && days < 14 } };
  }
  function ratingsFromPhys(eff, rp = RATING) {
    const out = {};
    for (const [cat, w] of Object.entries(rp.weights)) {
      const ks = Object.keys(w); if (!ks.length) { out[cat] = { baseline: rp.baseline, adjusted: null, delta: null, status: 'insufficient evidence' }; continue; }
      let pct = 0; for (const k of ks) if (eff[k] != null) pct += w[k] * eff[k];
      const delta = Math.max(-rp.max_delta, Math.min(rp.max_delta, rp.sensitivity * pct));
      out[cat] = { baseline: rp.baseline, adjusted: Math.round(rp.baseline + delta), delta, weighted_pct: pct, status: 'modelled' };
    }
    return out;
  }
  const hirDecrement = (matchAlt, resAlt, days = 1, p = PHYSIO) => -physEffects(matchAlt, resAlt, days, p).high_intensity_running;
  const remaining = (days, p = PHYSIO) => 1 - acclimFraction(days, p);

  // real-card adjustment (match_cards.py): six face stats + OVR
  const FACE = ['pac', 'sho', 'pas', 'dri', 'def', 'phy'];
  const FACE_FROM_CARD = { pac: 'PAC', def: 'DEF', phy: 'PHY' };
  const OVR_WEIGHTS = { pac: 0.15, def: 0.15, phy: 0.30, STAMINA: 0.40 };
  function teamCard(xi) { const c = {}; for (const k of FACE) c[k] = xi.reduce((a, p) => a + (+p[k] || 0), 0) / xi.length; c.ovr = xi.reduce((a, p) => a + (+p.ovr), 0) / xi.length; return c; }
  function adjustedCard(card, matchAlt, homeAlt, days, sensitivity = RATING.sensitivity) {
    const eff = physEffects(matchAlt, homeAlt, days), deltas = ratingsFromPhys(eff, Object.assign({}, RATING, { sensitivity }));
    const adj = Object.assign({}, card);
    for (const [face, cat] of Object.entries(FACE_FROM_CARD)) if (deltas[cat].delta != null) adj[face] = card[face] + deltas[cat].delta;
    adj.ovr = card.ovr + OVR_WEIGHTS.pac * (adj.pac - card.pac) + OVR_WEIGHTS.def * (adj.def - card.def) + OVR_WEIGHTS.phy * (adj.phy - card.phy) + OVR_WEIGHTS.STAMINA * (deltas.STAMINA.delta || 0);
    return { adj, eff, deltas };
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


  // ---------- FC ratings squads ----------
  const GROUPS = { GK: 'GK', CB: 'DF', LB: 'DF', RB: 'DF', LWB: 'DF', RWB: 'DF', CDM: 'MF', CM: 'MF', CAM: 'MF', LM: 'MF', RM: 'MF', ST: 'FW', CF: 'FW', LW: 'FW', RW: 'FW' };
  const FORMATIONS = { '4-3-3': { GK: 1, DF: 4, MF: 3, FW: 3 }, '4-4-2': { GK: 1, DF: 4, MF: 4, FW: 2 }, '4-2-3-1': { GK: 1, DF: 4, MF: 5, FW: 1 }, '3-5-2': { GK: 1, DF: 3, MF: 5, FW: 2 }, '3-4-3': { GK: 1, DF: 3, MF: 4, FW: 3 } };
  const playerGroup = p => GROUPS[p.p] || 'MF';
  function bestXIByFormation(squad, formation = '4-3-3', out = []) {
    const outn = new Set(out.map(norm));
    const pool = squad.filter(p => !outn.has(norm(p.n))).map(p => Object.assign({}, p, { rating: p.ovr, name: p.n, pos: p.p }));
    const need = Object.assign({}, FORMATIONS[formation]); const xi = [];
    for (const g of Object.keys(need)) { const c = pool.filter(p => playerGroup(p) === g && !xi.includes(p)).sort((a, b) => b.ovr - a.ovr).slice(0, need[g]); xi.push(...c); need[g] -= c.length; }
    const short = Object.values(need).reduce((a, b) => a + b, 0);
    if (short > 0) xi.push(...pool.filter(p => !xi.includes(p) && playerGroup(p) !== 'GK').sort((a, b) => b.ovr - a.ovr).slice(0, short));
    return xi;
  }

  const api = { RATING, physEffects, ratingsFromPhys, acclimFraction, teamCard, adjustedCard, FACE, GROUPS, FORMATIONS, bestXIByFormation, playerGroup, LINEUP_DEFAULT, PROPS_DEFAULT, XG_PER_SHOT, xiRating, bestXI, lineupAdjustment, priceLineups, shotsMeanFromLine, playerXg, teamXg, priceProps, defaultCoverage, PHYSIO, DEFAULT_PARAMS, hirDecrement, remaining, outcomeProbs, devig, impliedLambdas, altitudeAdjustment, priceFixture, makeLookup, norm, courtside };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.AfterHoursModel = api;
})(typeof window !== 'undefined' ? window : globalThis);
