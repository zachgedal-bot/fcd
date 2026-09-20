/* Athlemix After Hours — page wiring. Model math lives in after-hours.js. */
(function () {
  'use strict';
  const M = window.AfterHoursModel;
  const $ = id => document.getElementById(id);
  const fmtP = p => (p * 100).toFixed(1);
  const fmtEV = ev => `<span class="${ev >= 0 ? 'pos' : 'neg'}">${ev >= 0 ? '+' : ''}${(ev * 100).toFixed(1)}%</span>`;
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };

  // ---------- velvet rope (cosmetic) ----------
  const CODES = ['4090', 'ELALTO', 'ELINFIERNO', 'AFTERHOURS'];
  const gate = $('gate');
  const urlCode = new URLSearchParams(location.search).get('code');
  if (urlCode && CODES.includes(urlCode.toUpperCase())) store.set('ah.member', true);
  if (store.get('ah.member', false)) gate.classList.add('gate--open');
  $('gate-code').addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const v = e.target.value.trim().toUpperCase().replace(/\s+/g, '');
    if (CODES.includes(v)) { store.set('ah.member', true); gate.classList.add('gate--open'); }
    else { $('gate-err').textContent = 'Not on the list.'; }
  });

  // ---------- data ----------
  let venues = null, lookup = null, fixtures = [], added = store.get('ah.added', []);
  async function loadJSON(path) { const r = await fetch(path); if (!r.ok) throw new Error(r.status); return r.json(); }

  function params() {
    return Object.assign({}, M.DEFAULT_PARAMS, {
      residual_share: +$('p-residual').value, k_goals_per_10pct_hir: +$('p-k').value,
      habituation_discount: +$('p-hab').value, descending_goals: +$('p-desc').value,
    });
  }

  function num(v) { const n = parseFloat(v); return Number.isFinite(n) ? n : null; }

  function scanRow(fx, P) {
    const H = lookup(fx.home), A = lookup(fx.away);
    if (!H || !A) return { skip: `unknown team: ${!H ? fx.home : fx.away}` };
    const venueAlt = num(fx.venue_alt) || H.alt;
    const days = num(fx.days_since_arrival) ?? +$('p-days').value;
    const diff = venueAlt - A.alt;
    if (Math.abs(diff) < +$('p-mindiff').value && Math.abs(venueAlt - H.alt) < +$('p-mindiff').value) return { skip: `differential ${diff.toFixed(0)} m below threshold` };
    const oh = num(fx.odds_h), od = num(fx.odds_d), oa = num(fx.odds_a);
    const base = { date: fx.date, home: H.name, away: A.name, venueAlt, awayAlt: A.alt, diff, days, note: fx.note || '' };
    if (!(oh && od && oa)) return Object.assign(base, { needsOdds: true, adj: M.altitudeAdjustment(venueAlt, H.alt, A.alt, days, H.habitual, A.habitual, P) });
    const r = M.priceFixture(oh, od, oa, venueAlt, H.alt, A.alt, days, H.habitual, A.habitual, P, num(fx.odds_over25), num(fx.odds_under25));
    let best = null; for (const [k, e] of Object.entries(r.edges)) if (!best || e.ev > best[1].ev) best = [k, e];
    return Object.assign(base, { needsOdds: false, r, best });
  }

  function renderAltitude() {
    if (!lookup) return;
    const P = params(); const body = $('altitude-body'); body.innerHTML = '';
    const rows = fixtures.concat(added).map(fx => scanRow(fx, P));
    const priced = rows.filter(r => !r.skip && !r.needsOdds).sort((a, b) => Math.abs(b.best[1].ev) - Math.abs(a.best[1].ev));
    const unpriced = rows.filter(r => !r.skip && r.needsOdds).sort((a, b) => Math.abs(b.adj.d_lambda_away) + Math.abs(b.adj.d_lambda_home) - Math.abs(a.adj.d_lambda_away) - Math.abs(a.adj.d_lambda_home));
    const skipped = rows.filter(r => r.skip);
    if (!priced.length && !unpriced.length) { body.innerHTML = '<tr><td colspan="11">No lines. Drop a CSV or add one below.</td></tr>'; }
    for (const r of priced) {
      const e = r.r.edges, a = r.r.adjustment;
      const tr = document.createElement('tr'); if (r.best[1].ev > 0) tr.className = 'row--hot';
      const pair = k => `${fmtP(e[k].market_p)}→<b>${fmtP(e[k].model_p)}</b>`;
      tr.innerHTML = `<td>${r.date || ''}</td><td>${r.home} v ${r.away}${a.away_descending ? '<span class="flag">descending</span>' : ''}</td><td class="num">${r.diff > 0 ? '+' : ''}${r.diff.toFixed(0)}</td><td class="num">−${a.away_hir_dec_pct.toFixed(1)}%</td><td class="num">${a.d_lambda_home >= 0 ? '+' : ''}${a.d_lambda_home.toFixed(2)} / ${a.d_lambda_away >= 0 ? '+' : ''}${a.d_lambda_away.toFixed(2)}</td><td class="num">${pair('home')}</td><td class="num">${pair('draw')}</td><td class="num">${pair('away')}</td><td>${r.best[0]} @ ${r.best[1].odds}</td><td class="num">${fmtEV(r.best[1].ev)}</td><td class="num">${(r.best[1].kelly * 100).toFixed(1)}%</td>`;
      body.appendChild(tr);
      const d = document.createElement('tr'); d.className = 'details';
      const vd = M.ratingsFromPhys(M.physEffects(r.venueAlt, r.awayAlt, r.days)); d.innerHTML = `<td colspan="11">venue ${r.venueAlt} m · visitor lives at ${r.awayAlt} m · day ${r.days} · visitor card STAMINA ${vd.STAMINA.adjusted} PHY ${vd.PHY.adjusted} PAC ${vd.PAC.adjusted} (80 baseline) · market λ ${r.r.market_lambda_home.toFixed(2)}–${r.r.market_lambda_away.toFixed(2)} → model λ ${r.r.model_lambda_home.toFixed(2)}–${r.r.model_lambda_away.toFixed(2)}${e.over25 ? ` · O2.5 ${fmtP(e.over25.market_p)}→${fmtP(e.over25.model_p)} EV ${fmtEV(e.over25.ev)}` : ''}${r.note ? ' · ' + r.note : ''}</td>`;
      body.appendChild(d);
    }
    for (const r of unpriced) {
      const a = r.adj; const tr = document.createElement('tr');
      tr.innerHTML = `<td>${r.date || ''}</td><td>${r.home} v ${r.away}${a.away_descending ? '<span class="flag">descending</span>' : ''}</td><td class="num">${r.diff > 0 ? '+' : ''}${r.diff.toFixed(0)}</td><td class="num">−${a.away_hir_dec_pct.toFixed(1)}%</td><td class="num">${a.d_lambda_home >= 0 ? '+' : ''}${a.d_lambda_home.toFixed(2)} / ${a.d_lambda_away >= 0 ? '+' : ''}${a.d_lambda_away.toFixed(2)}</td><td colspan="6"><span class="tag">needs odds</span> ${r.note}</td>`;
      body.appendChild(tr);
    }
    if (skipped.length) { const tr = document.createElement('tr'); tr.className = 'details'; tr.innerHTML = `<td colspan="11">skipped: ${skipped.map(s => s.skip).join(' · ')}</td>`; body.appendChild(tr); }
  }

  function parseCSV(text) {
    const lines = text.split(/\r?\n/).filter(l => l.trim()); if (!lines.length) return [];
    const split = l => { const out = []; let cur = '', q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === ',' && !q) { out.push(cur); cur = ''; } else cur += ch; } out.push(cur); return out.map(s => s.trim()); };
    const hdr = split(lines[0]);
    return lines.slice(1).map(l => { const v = split(l); const o = {}; hdr.forEach((h, i) => o[h] = v[i] ?? ''); return o; });
  }

  // controls
  for (const [id, out, dp] of [['p-residual', 'o-residual', 2], ['p-k', 'o-k', 2], ['p-hab', 'o-hab', 2], ['p-desc', 'o-desc', 2]]) {
    $(id).addEventListener('input', () => { $(out).textContent = (+$(id).value).toFixed(dp); renderAltitude(); });
  }
  $('p-days').addEventListener('input', renderAltitude); $('p-mindiff').addEventListener('input', renderAltitude);
  $('fx-file').addEventListener('change', e => { const f = e.target.files[0]; if (!f) return; f.text().then(t => { fixtures = parseCSV(t); renderAltitude(); }); });
  $('fx-reload').addEventListener('click', () => loadJSON('altitude_edge/fixtures_demo.json').then(d => { fixtures = d; renderAltitude(); }).catch(() => {}));
  $('fx-clear').addEventListener('click', () => { added = []; store.set('ah.added', added); renderAltitude(); });
  $('al-add').addEventListener('click', () => {
    const fx = { date: $('al-date').value, home: $('al-home').value, away: $('al-away').value, odds_h: $('al-oh').value, odds_d: $('al-od').value, odds_a: $('al-oa').value, days_since_arrival: $('al-days').value, venue_alt: $('al-venue').value, note: 'added on the floor' };
    if (!lookup(fx.home) || !lookup(fx.away)) { $('al-msg').textContent = 'Team not in the venue table. Add it to altitude_edge/venues.py.'; return; }
    added.push(fx); store.set('ah.added', added); $('al-msg').textContent = 'Added.'; renderAltitude();
  });

  // ---------- lineup desk ----------
  const parsePlayers = txt => txt.split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => { const p = l.split(',').map(s => s.trim()); const rating = parseFloat(p[p.length - 1]); return { name: p[0], pos: p.length > 2 ? p[1] : '', rating }; }).filter(p => Number.isFinite(p.rating));
  function refXI(txt, proj) { const r = parsePlayers(txt); if (!r.length) return proj; return r.length > 11 ? M.bestXI(r, 11) : r; }
  $('l-gpp').addEventListener('input', () => $('o-gpp').textContent = (+$('l-gpp').value).toFixed(2));
  $('l-aware').addEventListener('input', () => $('o-aware').textContent = (+$('l-aware').value).toFixed(2));
  $('l-run').addEventListener('click', () => {
    const P = Object.assign({}, M.LINEUP_DEFAULT, { goals_per_point: +$('l-gpp').value, market_awareness: +$('l-aware').value, skew_flag_points: +$('l-skew').value });
    const H = sideCards('home'), A = sideCards('away'); const fake = o => Array.from({ length: 11 }, () => ({ rating: o }));
    let hp, ap, r;
    if (H && A) { hp = fake(H.cardAdj.ovr); ap = fake(A.cardAdj.ovr); r = M.priceLineups(+$('l-oh').value, +$('l-od').value, +$('l-oa').value, hp, fake(H.cardRef.ovr), ap, fake(A.cardRef.ovr), P); }
    else {
      hp = parsePlayers($('l-hp').value); ap = parsePlayers($('l-ap').value);
      if (hp.length < 5 || ap.length < 5) { $('l-out').innerHTML = '<p class="lede">Pick two clubs or paste at least five rated players a side.</p>'; return; }
      r = M.priceLineups(+$('l-oh').value, +$('l-od').value, +$('l-oa').value, hp, refXI($('l-hr').value, hp), ap, refXI($('l-ar').value, ap), P);
    }
    const side = (label, s, proj) => `<div><div class="k">${label} XI ${M.xiRating(proj).toFixed(1)} vs ref ${(M.xiRating(proj) - s.d_rating).toFixed(1)}</div><div class="v ${s.d_rating < 0 ? 'neg' : 'pos'}">${s.d_rating >= 0 ? '+' : ''}${s.d_rating.toFixed(2)}${s.skewed ? '<span class="flag">skewed</span>' : ''}</div><div class="k">Δλ own ${s.d_lambda_own.toFixed(2)} · opp ${s.d_lambda_opp.toFixed(2)}</div></div>`;
    $('l-out').innerHTML = `<div class="stat">${side('Home', r.home, hp)}${side('Away', r.away, ap)}<div><div class="k">λ market → model</div><div class="v">${r.market_lambda_home.toFixed(2)}–${r.market_lambda_away.toFixed(2)} → ${r.model_lambda_home.toFixed(2)}–${r.model_lambda_away.toFixed(2)}</div></div></div>
      <div class="scroll"><table class="book" style="margin-top:12px"><thead><tr><th>Side</th><th class="num">Market</th><th class="num">Model</th><th class="num">Odds</th><th class="num">EV</th><th class="num">Kelly</th></tr></thead><tbody>${Object.entries(r.edges).map(([k, e]) => `<tr class="${e.ev > 0 ? 'row--hot' : ''}"><td>${k}</td><td class="num">${fmtP(e.market_p)}%</td><td class="num">${fmtP(e.model_p)}%</td><td class="num">${e.odds}</td><td class="num">${fmtEV(e.ev)}</td><td class="num">${(e.kelly * 100).toFixed(1)}%</td></tr>`).join('')}</tbody></table></div>`;
  });
  $('l-sample').addEventListener('click', () => {
    $('l-hp').value = ['GK1, GK, 82', 'RB, DF, 80', 'CB1, DF, 81', 'CB2, DF, 79', 'LB, DF, 78', 'CM1, MF, 79', 'CM2, MF, 78', 'AM, AM, 77', 'RW, FW, 76', 'ST (backup), FW, 73', 'LW (backup), FW, 71'].join('\n');
    $('l-hr').value = ['GK1, GK, 82', 'RB, DF, 80', 'CB1, DF, 81', 'CB2, DF, 79', 'LB, DF, 78', 'CM1, MF, 79', 'CM2, MF, 78', 'AM, AM, 77', 'RW, FW, 76', 'ST, FW, 84', 'LW, FW, 75'].join('\n');
    $('l-ap').value = ['GK, GK, 80', 'RB, DF, 79', 'CB1, DF, 78', 'CB2, DF, 78', 'LB, DF, 77', 'CM1, MF, 77', 'CM2, MF, 76', 'AM, AM, 76', 'RW, FW, 75', 'ST, FW, 74', 'LW, FW, 73'].join('\n');
    $('l-ar').value = '';
  });

  // ---------- lineup desk: FC ratings pickers ----------
  let fc = null; const outs = { home: new Set(), away: new Set() };
  const teamSel = { home: $('l-home-team'), away: $('l-away-team') };
  function fillPickers() {
    for (const side of ['home', 'away']) for (const t of Object.keys(fc.teams)) { const o = document.createElement('option'); o.value = t; o.textContent = t; teamSel[side].appendChild(o); }
    $('l-source').textContent = fc.source + '. ' + fc.note;
  }
  function renderSquad(side) {
    const el = $(`l-${side}-squad`); el.innerHTML = ''; const t = teamSel[side].value; if (!t) return;
    const squad = fc.teams[t], f = $('l-formation').value;
    const ref = M.bestXIByFormation(squad, f), proj = M.bestXIByFormation(squad, f, [...outs[side]]);
    const inXI = new Set(proj.map(p => p.n));
    for (const p of squad) {
      const c = document.createElement('div'); const isOut = outs[side].has(p.n);
      c.className = 'chip chip--player' + (isOut ? ' chip--out' : inXI.has(p.n) ? ' chip--xi' : '');
      c.innerHTML = `<b>${p.ovr}</b>${p.n} <span>${p.p}</span>`; c.title = isOut ? 'marked out; click to restore' : 'click to mark out';
      c.addEventListener('click', () => { if (isOut) outs[side].delete(p.n); else outs[side].add(p.n); renderSquad(side); });
      el.appendChild(c);
    }
    const line = xi => xi.map(p => `${p.n}, ${p.p}, ${p.ovr}`).join('\n');
    $(side === 'home' ? 'l-hp' : 'l-ap').value = line(proj); $(side === 'home' ? 'l-hr' : 'l-ar').value = line(ref);
    renderCards();
  }
  function venueAlt() { const v = num($('l-venue').value); if (v != null) return v; const t = teamSel.home.value; const L = lookup && t ? lookup(t) : null; return L ? L.alt : 0; }
  function sideCards(side) {
    const t = teamSel[side].value; if (!t || !fc) return null;
    const squad = fc.teams[t], f = $('l-formation').value, days = +$('l-days').value || 0, sens = +$('l-sens').value;
    const ref = M.bestXIByFormation(squad, f), proj = M.bestXIByFormation(squad, f, [...outs[side]]);
    const L = lookup ? lookup(t) : null, resAlt = L ? L.alt : 0, vAlt = venueAlt();
    const cardRef = M.teamCard(ref), cardProj = M.teamCard(proj), a = M.adjustedCard(cardProj, vAlt, resAlt, days, sens);
    return { team: t, ref, proj, cardRef, cardProj, cardAdj: a.adj, eff: a.eff, deltas: a.deltas, resAlt, vAlt, days };
  }
  function renderCards() {
    const el = $('l-cards'); el.innerHTML = '';
    for (const side of ['home', 'away']) {
      const s = sideCards(side); if (!s) continue;
      const row = (label, c, cls) => `<tr class="${cls || ''}"><td>${label}</td>${M.FACE.map(k => `<td>${c[k].toFixed(1)}</td>`).join('')}<td>${c.ovr.toFixed(2)}</td></tr>`;
      const d = s.cardAdj.ovr - s.cardRef.ovr;
      el.innerHTML += `<div class="fccard"><h3>${s.team}</h3><div class="meta">${side} · lives at ${s.resAlt} m · venue ${s.vAlt} m · day ${s.days}${s.eff._meta.sleep_recovery_flag ? ' · <span class="flag">sleep/recovery flag</span>' : ''}</div>
        <div class="ovr">${s.cardAdj.ovr.toFixed(1)}<small>adjusted OVR · ${d >= 0 ? '+' : ''}${d.toFixed(2)} vs reference ${s.cardRef.ovr.toFixed(1)}</small></div>
        <table style="margin-top:10px"><thead><tr><th>XI</th>${M.FACE.map(k => `<th>${k.toUpperCase()}</th>`).join('')}<th>OVR</th></tr></thead><tbody>
        ${row('reference', s.cardRef)}${row('projected', s.cardProj)}${row('altitude-adjusted', s.cardAdj, 'adj')}</tbody></table>
        <div class="phys">VO2max ${s.eff.vo2max.toFixed(1)}% · high-intensity running ${s.eff.high_intensity_running.toFixed(1)}% · repeated-sprint recovery ${s.eff.repeated_sprint_recovery.toFixed(1)}% · top speed ${s.eff.single_sprint_speed >= 0 ? '+' : ''}${s.eff.single_sprint_speed.toFixed(2)}% · STAMINA ${s.deltas.STAMINA.adjusted ?? '–'} / REPEATED EFFORT ${s.deltas.REPEATED_EFFORT.adjusted ?? '–'} on an 80 baseline · ${s.eff._meta.status.replace(/_/g, ' ')}</div></div>`;
    }
  }
  for (const side of ['home', 'away']) teamSel[side].addEventListener('change', () => { outs[side].clear(); renderSquad(side); });
  for (const id of ['l-venue', 'l-days']) $(id).addEventListener('input', renderCards);
  $('l-sens').addEventListener('input', () => { $('o-sens').textContent = (+$('l-sens').value).toFixed(2); renderCards(); });
  $('l-formation').addEventListener('change', () => { renderSquad('home'); renderSquad('away'); });
  loadJSON('altitude_edge/fc_ratings_nwsl.json').then(d => { fc = d; fillPickers(); const q = new URLSearchParams(location.search); for (const side of ['home', 'away']) { const t = q.get(side); if (t && fc.teams[t]) { teamSel[side].value = t; renderSquad(side); } } }).catch(() => { $('l-source').textContent = 'Could not load altitude_edge/fc_ratings_nwsl.json; paste XIs by hand.'; });

  // ---------- props desk ----------
  const parseProps = (txt, scorers) => txt.split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => {
    const p = l.split(',').map(s => s.trim()); const o = { name: p[0], pos: p[1] || 'MF' };
    const sm = p.slice(2).find(x => /^shots\s*=/.test(x)); if (sm) { o.shots = parseFloat(sm.split('=')[1]); return o; }
    o.line = parseFloat(p[2]); o.o_over = parseFloat(p[3]); o.o_under = parseFloat(p[4]); if (p[5]) scorers[o.name] = parseFloat(p[5]); return o;
  }).filter(o => Number.isFinite(o.shots) || (Number.isFinite(o.line) && Number.isFinite(o.o_over) && Number.isFinite(o.o_under)));
  $('pr-blend').addEventListener('input', () => $('o-blend').textContent = (+$('pr-blend').value).toFixed(2));
  $('pr-run').addEventListener('click', () => {
    const scorers = {}; const hp = parseProps($('pr-h').value, scorers), ap = parseProps($('pr-a').value, scorers);
    if (!hp.length || !ap.length) { $('pr-out').innerHTML = '<p class="lede">Need at least one line a side.</p>'; return; }
    const P = Object.assign({}, M.PROPS_DEFAULT, { blend: +$('pr-blend').value, coverage: +$('pr-cov').value || null });
    const r = M.priceProps(+$('pr-oh').value, +$('pr-od').value, +$('pr-oa').value, hp, ap, P, +$('pr-o25').value || null, +$('pr-u25').value || null, scorers);
    $('pr-out').innerHTML = `<div class="stat"><div><div class="k">Props-implied xG</div><div class="v">${r.props_xg_home.toFixed(2)}–${r.props_xg_away.toFixed(2)}</div><div class="k">coverage ${(r.coverage_home * 100).toFixed(0)}% / ${(r.coverage_away * 100).toFixed(0)}%</div></div><div><div class="k">Market λ</div><div class="v">${r.market_lambda_home.toFixed(2)}–${r.market_lambda_away.toFixed(2)}</div></div><div><div class="k">Blended λ</div><div class="v">${r.model_lambda_home.toFixed(2)}–${r.model_lambda_away.toFixed(2)}</div></div></div>
      <div class="scroll"><table class="book" style="margin-top:12px"><thead><tr><th>Market</th><th class="num">Market</th><th class="num">Model</th><th class="num">Odds</th><th class="num">EV</th></tr></thead><tbody>${Object.entries(r.edges).map(([k, e]) => `<tr class="${e.ev > 0 ? 'row--hot' : ''}"><td>${k}</td><td class="num">${fmtP(e.market_p)}%</td><td class="num">${fmtP(e.model_p)}%</td><td class="num">${e.odds}</td><td class="num">${fmtEV(e.ev)}</td></tr>`).join('')}</tbody></table></div>
      <div class="scroll"><table class="book" style="margin-top:12px"><thead><tr><th>Side</th><th>Player</th><th>Pos</th><th class="num">Exp. shots</th><th class="num">xG/shot</th><th class="num">xG</th><th class="num">P(score)</th><th class="num">Scorer odds</th><th class="num">EV</th></tr></thead><tbody>${r.scorers.map(s => `<tr class="${s.ev > 0 ? 'row--hot' : ''}"><td>${s.side}</td><td>${s.name}</td><td>${s.pos || ''}</td><td class="num">${s.shots.toFixed(2)}</td><td class="num">${s.xg_per_shot.toFixed(2)}</td><td class="num">${s.xg.toFixed(2)}</td><td class="num">${fmtP(s.p_score)}%</td><td class="num">${s.odds || '–'}</td><td class="num">${s.ev == null ? '–' : fmtEV(s.ev)}</td></tr>`).join('')}</tbody></table></div>`;
  });
  $('pr-sample').addEventListener('click', () => {
    $('pr-h').value = ['H9, FW, 2.5, 1.95, 1.85, 2.60', 'H10, AM, 1.5, 1.80, 2.00', 'H7, FW, 1.5, 2.10, 1.72', 'H8, MF, 0.5, 1.50, 2.50'].join('\n');
    $('pr-a').value = ['A9, FW, 1.5, 2.20, 1.65, 4.00', 'A11, FW, 1.5, 2.40, 1.55', 'A8, MF, 0.5, 1.70, 2.10'].join('\n');
  });

  // ---------- high ground ----------
  function renderGround() {
    const el = $('ground-chips'); el.innerHTML = '';
    Object.entries(venues.venues).filter(([, v]) => v.alt >= 2000 && v.league !== 'NT').sort((a, b) => b[1].alt - a[1].alt)
      .forEach(([n, v]) => { const c = document.createElement('div'); c.className = 'chip'; c.innerHTML = `<b>${v.alt} m</b>${n} <span>· ${v.city} · ${v.league}</span>`; el.appendChild(c); });
  }

  // ---------- courtside ----------
  function renderCourtside() {
    const g = { goals: +$('c-goals').value, f: +$('c-f').value, L: +$('c-L').value, r: +$('c-r').value, fee: +$('c-fee').value, travel: +$('c-travel').value, risk: +$('c-risk').value };
    $('o-goals').textContent = g.goals.toFixed(1); $('o-f').textContent = g.f.toFixed(2); $('o-L').textContent = g.L; $('o-r').textContent = g.r.toFixed(2); $('o-fee').textContent = g.fee.toFixed(3); $('o-travel').textContent = g.travel; $('o-risk').textContent = g.risk;
    const c = M.courtside(g); const money = v => (v < 0 ? '−' : '') + '$' + Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
    $('c-gross').textContent = money(c.gross); $('c-net').textContent = money(c.net); $('c-net').className = 'v ' + (c.net >= 0 ? 'pos' : 'neg');
    $('c-be').textContent = money(c.breakevenL); $('c-season').textContent = money(40 * c.net); $('c-season').className = 'v ' + (c.net >= 0 ? 'pos' : 'neg');
  }
  for (const id of ['c-goals', 'c-f', 'c-L', 'c-r', 'c-fee', 'c-travel', 'c-risk']) $(id).addEventListener('input', renderCourtside);
  renderCourtside();

  // ---------- boot ----------
  loadJSON('altitude_edge/venues.json').then(v => { venues = v; lookup = M.makeLookup(v); renderGround(); return loadJSON('altitude_edge/fixtures_demo.json'); })
    .then(d => { fixtures = d; renderAltitude(); })
    .catch(err => { $('altitude-body').innerHTML = `<tr><td colspan="11">Could not load altitude_edge/venues.json or fixtures (${err.message}). Serve the folder over HTTP (python3 -m http.server) rather than file://.</td></tr>`; });
})();
