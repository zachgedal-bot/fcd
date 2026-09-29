"""Assemble REPORT.md from analysis outputs. Every number in the narrative is read from the JSON results so a rerun refreshes the report."""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, REG, ROOT

def load(name):
    p = os.path.join(OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None

def rd(name):
    p = os.path.join(OUT, name)
    return open(p).read() if os.path.exists(p) else '_not available_'

def pct(x): return f'{x:.1%}'
def pp(x): return f'{x*100:+.1f} pp'

def main():
    c = load('club_backtest_results.json'); o = load('odds_backtest_results.json'); n = load('national_team_results.json'); sci = load('science_synthesis.json'); wl = load('watchlist_assembled.json')
    reg = pd.read_csv(os.path.join(REG, 'venue_registry.csv'))
    q = c['raw']['qualifying_by_comp_type']; lg = q.get('league', {}); ct = q.get('continental', {})
    a = c['adjusted']; ol = a['ordered_logit']; ex = a['excess_vs_no_altitude_baseline']; exp_ = a['excess_vs_no_altitude_baseline_plain_elo']; fe = a['fixed_effects_poisson']; ip = a['implied_probabilities_in_qualifying_sample']; h = c['holdout']
    bins = c['raw']['by_gap_bin']; thr = c['thresholds']
    om = o['market_vs_actual']; oq = om['qualifying']; mv = o['model_vs_market_holdout']; ma = mv['market_anchored_logit']
    nq = n['raw']['qualifying_all']; nadj = n['adjusted']['ordered_logit']
    import math
    def orr(coef): return math.exp(coef)
    reg_flag = int(reg['basis'].astype(str).str.contains('flagged').sum()) if 'basis' in reg else 0
    S = []
    S.append(f"""# High-altitude home advantage in soccer: does a >2,500 m net elevation gap carry betting value?

Research date: 2026-09-29. Prepared for a bettor evaluating the rule **"back the home team when the actual match venue is more than 2,500 m above the visiting team's usual playing or training elevation."** All elevations are ground elevations from the SRTM digital elevation model at the stadium coordinates unless stated otherwise; 2,500 m is treated as the user's screening threshold, not a biological or profitability cutoff.

## Executive summary

**What is established**
- **A large performance effect exists in the historical club data.** Across {c['sample']['qualifying_home_acclimatized']:,} top-flight and continental club matches (2015-2025, Mexico, Peru, Ecuador, Colombia, Bolivia, Copa Libertadores, Copa Sudamericana) in which an acclimatized host received a visitor from more than 2,500 m lower, the host won {pct(lg.get('home_win', 0))} of league matches (draw {pct(lg.get('draw', 0))}, away win {pct(lg.get('away_win', 0))}; unbeaten {pct(lg.get('home_unbeaten', 0))}; goal difference {lg.get('gd', 0):+.2f}) against a league-wide home-win rate of roughly {pct(c['raw']['by_gap_bin'].get('(-500, 500]', {}).get('home_win', 0))} when host and visitor come from similar elevations.
- **The effect survives adjustment for team strength and ordinary home advantage.** With pre-match Elo ratings and competition effects, the net gap adds {ol['continuous']['gap_pos_km']['coef']:.2f} on the ordered-logit scale per 1,000 m (95% CI {ol['continuous']['gap_pos_km']['ci'][0]:.2f} to {ol['continuous']['gap_pos_km']['ci'][1]:.2f}); a 2,500 m gap is worth roughly {a['ordered_logit']['elo_equivalent_of_2500m']:.0f} Elo points. A fixed-effects model that compares the **same host** against visitors from different elevations (so stadium identity, crowd and club quality are held constant) still finds home goals up by {orr(fe['continuous']['gapH']['coef'])-1:+.0%} and away goals down by {orr(fe['continuous']['gapA']['coef'])-1:+.0%} per 1,000 m of net gap.
- **The excess is not an artefact of one league or one club.** Dropping any home country or any of the ten most frequent hosts leaves the per-1,000 m coefficient between {min(v['gap_pos_km']['coef'] for k, v in c['sensitivity'].items() if k.startswith('drop_')):.2f} and {max(v['gap_pos_km']['coef'] for k, v in c['sensitivity'].items() if k.startswith('drop_')):.2f}.
- **The effect is not a step at 2,500 m.** Home-win rates rise with the gap and are much stronger above 3,000 m ({pct(bins.get('(3000, 3500]', {}).get('home_win', 0))} at 3,000-3,500 m, {pct(bins.get('(3500, 9999]', {}).get('home_win', 0))} above 3,500 m) than at 2,500-3,000 m ({pct(bins.get('(2500, 3000]', {}).get('home_win', 0))}). The 2,500 m cutoff is defensible as a screen but it lumps the Quito/Bogotá/Sucre band (modest effect) with the La Paz/Oruro/Potosí/Cusco/Huancayo band (large effect).
- **Adding altitude improves out-of-sample prediction.** Trained on 2015-2020 and tested on 2021-2025, the altitude-aware model lowers log-loss on all matches ({h['all_matches']['logloss_baseline']:.4f} to {h['all_matches']['logloss_altitude']:.4f}) and on qualifying matches ({h['qualifying_matches']['logloss_baseline']:.4f} to {h['qualifying_matches']['logloss_altitude']:.4f}); the naive model predicted {pct(h['qualifying_matches']['pred_home_baseline'])} home wins in qualifying test matches against {pct(h['qualifying_matches']['actual_home'])} observed.
- **Both scoring channels move.** Hosts score more and visitors score less; total goals rise mainly at the highest venues (Bolivia). This supports home-win and home-or-draw markets rather than a generic "overs" rule.

**What remains uncertain or untested**
- **Whether the price already reflects it.** The only archived prices reachable were Liga MX (Bet365 and best-of-market, 2015-2024). Toluca's qualifying home matches with prices number {oq['n']} (actual home-win rate {pct(oq['actual']['H'])} vs a de-vigged implied {pct(oq['implied_Odd_pow']['H'])}); the flat-stake return of {oq['roi_best_price']['home_win']:+.0%} at best price has a standard error of about {oq['roi_bet365']['home_win_se']:.0%}, so it is not evidence of a repeatable edge. Across all Liga MX matches, a logit of home-win on the market's own probability plus the net gap gives a gap coefficient of {ma['gap_pos_km_coef_train']:+.3f} (p = {ma['gap_pos_km_p']:.2f}): **the Liga MX market does not appear to misprice altitude in general.** No historical odds for the Bolivian, Peruvian, Ecuadorian or Colombian leagues or CONMEBOL cups could be obtained in this session, so profitability of the filter where the effect is largest is **untested**.
- **Half-specific and late-goal patterns** could not be tested for clubs (no half-time scores or goal minutes in the reachable data). National-team goal minutes show no clear late-match skew.
- **Physiology at the venues that matter most** is documented by field studies of youth squads at 3,600 m and by moderate-altitude match studies; professional-match GPS evidence at 2,500-4,100 m is thin, and the literature could not be re-verified online after this session's search allowance ran out.

**Does the exact filter have evidence behind it?** As a screen for a *performance* effect, yes: the >2,500 m rule selects matches where hosts outperform a strength-adjusted, home-advantage-adjusted expectation by about {pp(exp_['excess_home_win'])} to {pp(ex['excess_home_win'])} in home-win probability (bootstrap 95% CIs {pp(exp_['ci_home_win'][0])} to {pp(exp_['ci_home_win'][1])} and {pp(ex['ci_home_win'][0])} to {pp(ex['ci_home_win'][1])}, depending on how much of the host's rating is credited to altitude). As a *betting* rule, the evidence stops short: the one market that could be tested shows no systematic mispricing outside a handful of matches, and the markets where the effect is largest could not be tested at all.

""")
    S.append("## 1. The screening rule as implemented\n\n")
    S.append(f"""- Net elevation difference = DEM elevation of the actual match venue minus the DEM elevation of the visitor's usual home venue in that season (a proxy for training elevation, labelled as such; see Section 9 for the training-ground table). Primary filter: net gap > 2,500 m.
- Hosts count only when acclimatized: the match venue must lie within 500 m of the host's own usual venue that season ({c['sample']['home_not_acclimatized']} nominal home matches at relocated highland venues were excluded from the main sample and are reported separately).
- Recent altitude exposure of the visitor (any match at 2,000 m or higher in the previous 14 days) is computed from the match data itself.
- Registry status: {len(reg)} venues located; {reg_flag} still carry a DEM-versus-published disagreement flag. The registry, its candidate records and their basis are in `data/registry/`.

## 2. Scientific evidence

""")
    if sci:
        s = sci['synthesis']
        S.append("_Verification note: two literature lenses (field physiology; match-result statistics) ran live web searches before the session's search allowance was exhausted; all other lenses and all cross-checks relied on model recall, and the labels below say which is which. Treat 'recall-only' citations as leads to verify before relying on them._\n\n")
        S.append("### Evidence table\n\n" + s['evidence_table_markdown'] + "\n\n")
        for title, key in [('Physical performance', 'physical_performance_md'), ('Acclimatization', 'acclimatization_md'), ('Timing within matches', 'timing_within_match_md'), ('Ball flight and match environment (symmetric effects)', 'environment_ball_flight_md'), ('Match-result studies', 'match_results_evidence_md'), ('Betting-market evidence', 'market_evidence_md'), ('Where the 2,500 m figure comes from', 'thresholds_md'), ('What is established', 'what_is_established_md'), ('What is uncertain', 'what_is_uncertain_md')]:
            S.append(f"### {title}\n\n{s[key]}\n\n")
        S.append("### Citations\n\n" + '\n'.join(f"- [{x['key']}] {x['citation']} {x['url']} — {x['verification']}" for x in s['citations']) + "\n\n")
    else:
        S.append("_The literature synthesis had not completed when this report was built; see `output/salvaged/workflow_partial_results.json` for the raw finder records._\n\n")
    S.append("## 3. Historical club backtest (regulation time, 2014/15-2025)\n\n")
    S.append(f"""The central question is not whether highland hosts win often, but whether they win more than their strength and ordinary home advantage predict. Raw results come first, adjusted estimates after.

""" + rd('tables_club.md') + "\n\n")
    S.append(f"""### Reading the club results
- **Raw.** In league play the qualifying host wins {pct(lg.get('home_win', 0))}, draws {pct(lg.get('draw', 0))}, loses {pct(lg.get('away_win', 0))} (N = {lg.get('n', 0):,}, {lg.get('hosts', 0)} hosts, {lg.get('venues', 0)} venues, {lg.get('seasons', 0)} seasons). Continental matches show a similar picture on a much smaller sample (N = {ct.get('n', 0)}). By country the raw rate ranges from about {pct(min(v['home_win'] for v in c['raw']['qualifying_by_home_country'].values() if v.get('n', 0) >= 50))} to {pct(max(v['home_win'] for v in c['raw']['qualifying_by_home_country'].values() if v.get('n', 0) >= 50))} among countries with 50+ matches; Bolivia's La Paz/El Alto/Oruro/Potosí hosts dominate the top end, Ecuador's Quito hosts the bottom.
- **Same hosts, different visitors.** The same highland hosts, when receiving visitors from similar elevation, win {pct(c['raw']['same_hosts_vs_similar_elevation_visitors'].get('home_win', 0))} (N = {c['raw']['same_hosts_vs_similar_elevation_visitors'].get('n', 0):,}), so a large part of the raw gap is about the visitor's origin, not the host's stadium.
- **Adjusted.** The ordered-logit indicator for >2,500 m is {ol['indicator']['q2500']['coef']:.2f} (odds ratio {orr(ol['indicator']['q2500']['coef']):.1f}, 95% CI {orr(ol['indicator']['q2500']['ci'][0]):.1f} to {orr(ol['indicator']['q2500']['ci'][1]):.1f}); when the continuous gap and the indicator enter together, the continuous term keeps most of the effect ({ol['both']['gap_pos_km']['coef']:.2f} per 1,000 m) and the indicator adds {ol['both']['q2500']['coef']:.2f} (p = {ol['both']['q2500']['p']:.3f}), i.e. there is little evidence of a discontinuity at 2,500 m beyond the gradient. A visitor that had already played at 2,000 m+ in the prior two weeks fares slightly better ({ol['with_recent_exposure']['away_recent_alt']['coef']:+.2f}, p = {ol['with_recent_exposure']['away_recent_alt']['p']:.2f}); the difference is small and only marginally significant.
- **Within-host identification.** The fixed-effects Poisson model, with a separate home-advantage term for each host, attributes {orr(fe['indicator']['qH']['coef'])-1:+.0%} home goals and {orr(fe['indicator']['qA']['coef'])-1:+.0%} away goals to a >2,500 m gap. This is the estimate that best separates altitude from stadium identity and club quality, because it is driven by the same host facing lowland versus highland visitors.
- **Expected versus actual.** Against a baseline that includes ordinary home advantage and team strength but no altitude term, qualifying hosts win {pp(ex['excess_home_win'])} more often than expected (95% CI {pp(ex['ci_home_win'][0])} to {pp(ex['ci_home_win'][1])}; {ex['clusters']} host-season clusters) using the altitude-neutral rating, or {pp(exp_['excess_home_win'])} ({pp(exp_['ci_home_win'][0])} to {pp(exp_['ci_home_win'][1])}) using a plain rating that already credits the host's altitude wins to the club. The truth for a bettor lies between these, because a rating system used in practice sits somewhere between the two.
- **Independence caveat.** {lg.get('n', 0):,} league matches come from only {lg.get('venues', 0)} venues and {lg.get('hosts', 0)} hosts; standard errors are clustered by host-season and the leave-one-out checks address venue dominance, but the sample is still a few dozen venue-experiments, not thousands.
- **Thresholds.** The effect grows monotonically with the cutoff (see the threshold table): raw home-win {pct(thr['2000']['raw_home_win'])} above 2,000 m, {pct(thr['2500']['raw_home_win'])} above 2,500 m, {pct(thr['3000']['raw_home_win'])} above 3,000 m, {pct(thr['3500']['raw_home_win'])} above 3,500 m. These are robustness checks, not a licence to pick the best-looking cutoff.

## 4. Match-result effect versus total-goals effect

- Home goals rise and away goals fall with the gap (Poisson rate ratios per 1,000 m: home {orr(a['poisson_home_goals']['gap_pos_km']['coef']):.3f}, away {orr(a['poisson_away_goals']['gap_pos_km']['coef']):.3f}; within-host model: home {orr(fe['continuous']['gapH']['coef']):.3f}, away {orr(fe['continuous']['gapA']['coef']):.3f}).
- Total goals: rate ratio {orr(a['poisson_total_goals']['gap_pos_km']['coef']):.3f} per 1,000 m (95% CI {orr(a['poisson_total_goals']['gap_pos_km']['ci'][0]):.3f} to {orr(a['poisson_total_goals']['gap_pos_km']['ci'][1]):.3f}); the totals effect is concentrated at the very high Bolivian venues (mean total {c['raw']['qualifying_by_home_country'].get('BOL', {}).get('total', 0):.2f} in Bolivia versus {c['raw']['qualifying_by_home_country'].get('ECU', {}).get('total', 0):.2f} in Ecuador and {c['raw']['qualifying_by_home_country'].get('COL', {}).get('total', 0):.2f} in Colombia), where thin air and weak lowland visitors coincide. An "overs" rule is therefore not supported as a general consequence of the filter.
- Model-implied probabilities in the qualifying sample: with the altitude term the home-win probability is {pct(ip['with_altitude']['H'])} (home-or-draw {pct(ip['with_altitude']['H']+ip['with_altitude']['D'])}, home draw-no-bet {pct(ip['home_dnb_with'])}); for the same pairings with the altitude term switched off it would be {pct(ip['same_teams_no_altitude']['H'])} (home-or-draw {pct(ip['same_teams_no_altitude']['H']+ip['same_teams_no_altitude']['D'])}, DNB {pct(ip['home_dnb_without'])}); actual {pct(ip['actual']['H'])} / {pct(ip['actual']['H']+ip['actual']['D'])} / {pct(ip['actual']['H']/(ip['actual']['H']+ip['actual']['A']))}.
- **Answer:** after adjustment the pattern supports a stronger home-win probability and a stronger home-or-draw probability; the draw share falls rather than rises, so double chance gains less than the outright home win. Total goals change little except at 3,500 m+ venues. Half-specific and late-goal effects could not be tested for club matches (no half-time or minute data in the reachable sources); they remain a hypothesis, not a finding.

## 5. Does the betting market already price it in?

""" + rd('tables_odds.md') + f"""

### Reading the market results
- **Coverage.** Only Liga MX prices were reachable (Football-Data.co.uk via a public mirror: Bet365 1X2 and the cross-book maximum; no timestamps, no exchange data, no Asian-handicap or DNB quotes for Mexico). The 1X2 prices are collected shortly before kick-off, so they are late pre-match prices, not opening lines, and closing-line value cannot be measured.
- **Qualifying matches with prices: {oq['n']}** (all Toluca at home to Tijuana, Veracruz, Mazatlán or Dorados). The host won {pct(oq['actual']['H'])} against an implied {pct(oq['implied_Odd_pow']['H'])}. Flat-stake home-win return {oq['roi_bet365']['home_win']:+.0%} at Bet365 (standard error {oq['roi_bet365']['home_win_se']:.0%}) and {oq['roi_best_price']['home_win']:+.0%} at the best price; synthetic double-chance {oq['roi_best_price']['double_chance_1x_synth']:+.0%} and synthetic draw-no-bet {oq['roi_best_price']['dnb_synth']:+.0%}. With a standard error this large the result is consistent with anything from a large loss to a large gain; it is a curiosity, not a track record.
- **General pricing test.** In the market-anchored logit (train 2015-2019), the net gap adds essentially nothing to the de-vigged market probability (coefficient {ma['gap_pos_km_coef_train']:+.3f} per 1,000 m, p = {ma['gap_pos_km_p']:.2f}); out of sample the market's log-loss ({mv['logloss_all']['market_bet365_power_devig']:.4f}) beats the Elo + altitude model ({mv['logloss_all']['elo_plus_altitude']:.4f}). **In Liga MX the market already prices venue elevation about as well as a rating model with an explicit altitude term.**
- **Comparison band.** Mexico City hosts (about 2,250-2,300 m) against near-sea-level visitors, a 2,000-2,500 m gap that does *not* meet the filter, show {pct(om['mexico_city_hosts_vs_sea_level_visitors_gap2000_2500']['actual']['H'])} home wins against {pct(om['mexico_city_hosts_vs_sea_level_visitors_gap2000_2500']['implied_Odd_pow']['H'])} implied (N = {om['mexico_city_hosts_vs_sea_level_visitors_gap2000_2500']['n']}). This is the only pocket of apparent mispricing in the Mexican data, it sits below the user's threshold, and its standard error ({om['mexico_city_hosts_vs_sea_level_visitors_gap2000_2500']['roi_bet365']['home_win_se']:.0%}) is still wide.
- **Where the effect is largest (Bolivia, Peru, Ecuador, Colombia, CONMEBOL cups) no price data could be obtained**, so the profitability of the filter there is **untested**. Nothing here is a simulated substitute for a real backtest.
- **Separate conclusions:** (1) plausible mechanism: yes, well documented for unacclimatized visitors; (2) demonstrated performance effect: yes, large and robust in club results after adjustment; (3) improved out-of-sample prediction over a naive rating model: yes; over the market: not shown (Liga MX says no); (4) demonstrated value after costs: no.

## 6. National-team evidence (kept separate)

""" + rd('tables_nt.md') + f"""

National-team matches since 1990 hosted at altitude in the five countries by a side based at that elevation (Bolivia, Ecuador; Colombia's team is based in Barranquilla and is shown separately without the base filter): home win {pct(nq['home_win'])}, draw {pct(nq['draw'])}, away win {pct(nq['away_win'])} (N = {nq['n']}). The adjusted gap coefficient ({nadj['gap_pos_km']['coef']:.2f} per 1,000 m, 95% CI {nadj['gap_pos_km']['ci'][0]:.2f} to {nadj['gap_pos_km']['ci'][1]:.2f}) is of the same order as in club football, with the caveat that a national team's "usual elevation" is a weak proxy because most players are club-based elsewhere. Goal timing (secondary): the share of home goals after the 75th minute in qualifying matches ({n['goal_timing']['qualifying']['home_share_after_75']}) is close to the all-match share ({n['goal_timing']['all_five_countries']['home_share_after_75']}); no late-goal skew is visible.

## 7. Upcoming fixtures (2026-09-29 to 2026-11-28)

**Important limitation.** Live fixture verification was possible only until this session's web-search allowance ran out, and page fetching was blocked throughout. The tables below therefore contain (a) fixtures located and sourced by the Liga MX and Bolivia searches that ran before the cut-off, (b) the CONMEBOL knockout calendar from a dated public dataset (pairings not yet filled), and (c) a structural pairing matrix for Peru, Ecuador and Colombia, whose 2026 schedules could not be retrieved. Every entry states its verification status; kickoff times are converted to America/Los_Angeles with PDT (UTC-7) before 2026-11-01 and PST (UTC-8) from that date.

""" + rd('watchlist_tables.md') + "\n\n" + rd('watchlist_notes.md') + f"""

## 8. Practical verification checklist

""" + rd('../report/section_methods_and_limits.md').split('### Practical verification checklist before backing any fixture')[1] + f"""

## 9. Data, methods and limitations

""" + rd('../report/section_methods_and_limits.md').split('### Practical verification checklist before backing any fixture')[0].replace('## Data, methods and what could not be done in this session', '') + f"""

## 10. Final answer

**Does backing home teams with more than a 2,500 m net elevation advantage demonstrate value beyond ordinary home advantage and market expectations, or is it a plausible screening factor whose betting value remains unproven?**

The performance effect is real, large and robust: after adjusting for team strength and each host's ordinary home advantage, hosts with a >2,500 m net gap win roughly {pp(exp_['excess_home_win'])} to {pp(ex['excess_home_win'])} more often than expected, score more and concede less, and the effect strengthens above 3,000 m. The betting value is **unproven**. The only market that could be tested (Liga MX) prices venue elevation about as accurately as an explicit altitude model, and its {oq['n']} qualifying matches are far too few to establish an edge; the markets where the effect is largest (Bolivia, Peru, Ecuador, Colombia, CONMEBOL) could not be tested for lack of price data. Use the filter as a screen that flags matches where a rating model *without* an altitude term will be badly calibrated, then bet only when the de-vigged price is still below a model estimate that already includes altitude, host acclimatization, visitor exposure and lineup information.

## Appendix: files

- `research/altitude/analysis/` — `common.py` (loaders, Elo), `club_backtest.py`, `odds_backtest.py`, `national_teams.py`, `build_registry.py`, `watchlist_assemble.py`, `report_tables.py`, `build_report.py`.
- `research/altitude/tools/dem_elev.py` — SRTM elevation lookup (AWS Terrain Tiles).
- `research/altitude/data/registry/` — venue registry (chosen record per venue, all candidates, club training bases).
- `research/altitude/output/` — results JSON, match-level tables (`matches_with_gap.csv`, `qualifying_matches.csv`, `ligamx_qualifying_with_odds.csv`, `national_team_qualifying_matches.csv`), watchlist files, rendered tables.
- `research/altitude/workflows/` — the multi-agent workflow scripts used for the literature sweep, fixture search and venue registry.
""")
    open(os.path.join(ROOT, 'REPORT.md'), 'w').write(''.join(S))
    print('REPORT.md written:', len(''.join(S)), 'chars')

if __name__ == '__main__':
    main()
