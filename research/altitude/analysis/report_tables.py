"""Render markdown tables from the analysis JSON outputs (club backtest, odds backtest, national teams)."""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT

def raw_rows(d, label_key='group'):
    cols = ['n', 'home_win', 'draw', 'away_win', 'home_unbeaten', 'home_ppg', 'gd', 'hg', 'ag', 'total', 'over25', 'hosts', 'venues', 'seasons']
    lines = ['| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |', '|' + '---|' * 15]
    for k, v in d.items():
        if not isinstance(v, dict) or v.get('n', 0) == 0: continue
        vals = [v.get(c, '') for c in cols]
        def f(x, pct=False):
            if x == '' or x is None: return ''
            return f'{x:.1%}' if pct else (f'{x:.2f}' if isinstance(x, float) else str(x))
        lines.append(f'| {k} | {vals[0]} | {f(vals[1],1)} | {f(vals[2],1)} | {f(vals[3],1)} | {f(vals[4],1)} | {f(vals[5])} | {f(vals[6])} | {f(vals[7])} | {f(vals[8])} | {f(vals[9])} | {f(vals[10],1)} | {vals[11]} | {vals[12]} | {vals[13]} |')
    return '\n'.join(lines)

def coef_row(name, c, transform=None):
    if not c: return f'| {name} | n/a | | | |'
    b = c['coef']; lo, hi = c['ci']
    extra = ''
    if transform == 'odds': extra = f' (odds ratio {2.718281828**b:.2f})'
    if transform == 'rate': extra = f' (rate ratio {2.718281828**b:.3f})'
    return f'| {name} | {b:.3f}{extra} | {lo:.3f} to {hi:.3f} | {c["se"]:.3f} | {c["p"]:.3g} |'

def club_tables():
    r = json.load(open(os.path.join(OUT, 'club_backtest_results.json')))
    md = []
    md.append('#### Coverage\n')
    md.append('| Competition | Matches | With computable gap | Seasons |\n|---|---|---|---|')
    for row in r['coverage']['by_comp']: md.append(f"| {row['comp']} | {row['n']} | {row['with_gap']} | {row['seasons']} |")
    md.append(f"\nQualifying sample (net gap > 2,500 m): {r['sample']['qualifying_all']} matches, of which {r['sample']['qualifying_home_acclimatized']} with an acclimatized host (main sample) and {r['sample']['home_not_acclimatized']} where the nominal host was itself far from its usual elevation (excluded).\n")
    md.append('#### Raw results, qualifying sample by competition type\n'); md.append(raw_rows(r['raw']['qualifying_by_comp_type']))
    md.append('\n#### Raw results, qualifying sample by competition\n'); md.append(raw_rows(r['raw']['qualifying_by_comp']))
    md.append('\n#### Raw results, qualifying sample by host country\n'); md.append(raw_rows(r['raw']['qualifying_by_home_country']))
    md.append('\n#### Raw results by 500 m net-gap bin (all matches, acclimatized hosts)\n'); md.append(raw_rows(r['raw']['by_gap_bin']))
    md.append('\n#### Comparison groups\n'); md.append(raw_rows({'Same hosts vs visitors from similar elevation (|gap| <= 500 m)': r['raw']['same_hosts_vs_similar_elevation_visitors'], 'Same hosts, all home matches': r['raw']['same_hosts_all_home_matches']}))
    md.append('\n#### Qualifying sample by visitor recent altitude exposure (any match at >= 2,000 m in prior 14 days)\n'); md.append(raw_rows({('visitor recently at altitude' if k == 'True' else 'visitor not recently at altitude'): v for k, v in r['raw']['qualifying_by_visitor_recent_altitude'].items()}))
    md.append('\n#### Qualifying sample by period\n'); md.append(raw_rows(r['raw']['qualifying_by_period']))
    md.append('\n#### Qualifying sample, most frequent hosts (25+ matches)\n'); md.append(raw_rows(r['raw']['qualifying_by_host_top']))
    md.append('\n#### Qualifying sample, most frequent venues (25+ matches)\n'); md.append(raw_rows(r['raw']['qualifying_by_venue_top']))
    md.append('\n#### League-wide baselines (all matches with computable gap, by competition)\n'); md.append(raw_rows(r['raw']['all_matches_by_comp']))
    a = r['adjusted']
    md.append(f"\n#### Adjusted estimates (seasons 2015-2025, acclimatized hosts, N = {a['ordered_logit']['n']})\n")
    md.append('| Model / term | Coefficient | 95% CI | SE | p |\n|---|---|---|---|---|')
    md.append(coef_row('Ordered logit: Elo difference per 100 points', a['ordered_logit']['continuous']['elo_diff100']))
    md.append(coef_row('Ordered logit: net gap per 1,000 m above visitor base (continuous)', a['ordered_logit']['continuous']['gap_pos_km']))
    md.append(coef_row('Ordered logit: venue below visitor base, per 1,000 m', a['ordered_logit']['continuous']['gap_neg_km']))
    md.append(coef_row('Ordered logit: indicator net gap > 2,500 m', a['ordered_logit']['indicator']['q2500'], 'odds'))
    md.append(coef_row('Ordered logit: continuous + indicator jointly, continuous term', a['ordered_logit']['both']['gap_pos_km']))
    md.append(coef_row('Ordered logit: continuous + indicator jointly, indicator term', a['ordered_logit']['both']['q2500']))
    md.append(coef_row('Ordered logit: visitor recently at altitude (with continuous gap)', a['ordered_logit']['with_recent_exposure']['away_recent_alt']))
    md.append(coef_row('Logit home win (cluster SE): net gap per 1,000 m', a['logit_home_win']['gap_pos_km'], 'odds'))
    md.append(coef_row('Logit home win (cluster SE): indicator > 2,500 m', a['logit_home_win']['q2500'], 'odds'))
    md.append(coef_row('Logit home-or-draw (cluster SE): net gap per 1,000 m', a['logit_home_or_draw']['gap_pos_km'], 'odds'))
    md.append(coef_row('Logit home-or-draw (cluster SE): indicator > 2,500 m', a['logit_home_or_draw']['q2500'], 'odds'))
    md.append(coef_row('Poisson home goals (cluster SE): net gap per 1,000 m', a['poisson_home_goals']['gap_pos_km'], 'rate'))
    md.append(coef_row('Poisson home goals: indicator > 2,500 m', a['poisson_home_goals']['q2500'], 'rate'))
    md.append(coef_row('Poisson away goals (cluster SE): net gap per 1,000 m', a['poisson_away_goals']['gap_pos_km'], 'rate'))
    md.append(coef_row('Poisson away goals: indicator > 2,500 m', a['poisson_away_goals']['q2500'], 'rate'))
    md.append(coef_row('Poisson total goals: net gap per 1,000 m', a['poisson_total_goals']['gap_pos_km'], 'rate'))
    md.append(coef_row('Poisson total goals: indicator > 2,500 m', a['poisson_total_goals']['q2500'], 'rate'))
    fe = a['fixed_effects_poisson']
    md.append(coef_row('FE Poisson (team attack/defence + host home-advantage FE): home goals, gap per 1,000 m', fe['continuous']['gapH'], 'rate'))
    md.append(coef_row('FE Poisson: away goals, gap per 1,000 m', fe['continuous']['gapA'], 'rate'))
    md.append(coef_row('FE Poisson: home goals, indicator > 2,500 m', fe['indicator']['qH'], 'rate'))
    md.append(coef_row('FE Poisson: away goals, indicator > 2,500 m', fe['indicator']['qA'], 'rate'))
    md.append(f"\nElo-equivalent of a 2,500 m gap in the continuous ordered-logit model: about {a['ordered_logit']['elo_equivalent_of_2500m']} Elo points. The altitude-neutral rating iteration credited {r['elo']['altitude_neutral_gap_elo_points_per_km']} Elo points per 1,000 m of net gap to the venue.\n")
    md.append('#### Ordered logit by gap bin (reference: |gap| <= 500 m)\n')
    md.append('| Gap bin (m) | Coefficient | 95% CI | SE | p |\n|---|---|---|---|---|')
    for k, v in a['ordered_logit_gap_bins'].items(): md.append(coef_row(k, v))
    ip = a['implied_probabilities_in_qualifying_sample']
    md.append(f"\n#### Model-implied probabilities in the qualifying sample (N = {ip['n']})\n")
    md.append('| | Away win | Draw | Home win | Home DNB |\n|---|---|---|---|---|')
    md.append(f"| Actual | {ip['actual']['A']:.1%} | {ip['actual']['D']:.1%} | {ip['actual']['H']:.1%} | {ip['actual']['H']/(ip['actual']['H']+ip['actual']['A']):.1%} |")
    md.append(f"| Model with altitude term | {ip['with_altitude']['A']:.1%} | {ip['with_altitude']['D']:.1%} | {ip['with_altitude']['H']:.1%} | {ip['home_dnb_with']:.1%} |")
    md.append(f"| Same teams, altitude term set to zero (ordinary home advantage only) | {ip['same_teams_no_altitude']['A']:.1%} | {ip['same_teams_no_altitude']['D']:.1%} | {ip['same_teams_no_altitude']['H']:.1%} | {ip['home_dnb_without']:.1%} |")
    ex = a['excess_vs_no_altitude_baseline']; exp_ = a['excess_vs_no_altitude_baseline_plain_elo']
    md.append(f"\nExcess of actual over expected (baseline: ordinary home advantage + team strength, no altitude term), cluster-bootstrap 95% CI by host-season:\n")
    md.append('| Rating variant | Excess home-win rate | 95% CI | Excess points per game | 95% CI | Clusters |\n|---|---|---|---|---|---|')
    md.append(f"| Altitude-neutral Elo | {ex['excess_home_win']:+.3f} | {ex['ci_home_win'][0]:+.3f} to {ex['ci_home_win'][1]:+.3f} | {ex['excess_ppg']:+.3f} | {ex['ci_ppg'][0]:+.3f} to {ex['ci_ppg'][1]:+.3f} | {ex['clusters']} |")
    md.append(f"| Plain Elo (conservative) | {exp_['excess_home_win']:+.3f} | {exp_['ci_home_win'][0]:+.3f} to {exp_['ci_home_win'][1]:+.3f} | {exp_['excess_ppg']:+.3f} | {exp_['ci_ppg'][0]:+.3f} to {exp_['ci_ppg'][1]:+.3f} | {exp_['clusters']} |")
    md.append('\n#### Threshold robustness (indicator net gap > T; the 2,500 m row is the primary filter)\n')
    md.append('| Threshold T (m) | N above T | Raw home win | Raw home PPG | Ordered-logit indicator coef | 95% CI | p |\n|---|---|---|---|---|---|---|')
    for T, v in r['thresholds'].items():
        c = v['ordered_logit_indicator']; md.append(f"| {T} | {v['n']} | {v['raw_home_win']:.1%} | {v['raw_ppg']:.2f} | {c['coef']:.3f} | {c['ci'][0]:.3f} to {c['ci'][1]:.3f} | {c['p']:.3g} |")
    md.append('\n#### Sensitivity of the continuous gap effect (ordered logit, per 1,000 m)\n')
    md.append('| Subsample | N | N qualifying | Coefficient | 95% CI | p |\n|---|---|---|---|---|---|')
    for k, v in r['sensitivity'].items():
        c = v['gap_pos_km']; md.append(f"| {k} | {v.get('n', '')} | {v['n_qual']} | {c['coef']:.3f} | {c['ci'][0]:.3f} to {c['ci'][1]:.3f} | {c['p']:.3g} |")
    h = r['holdout']
    md.append(f"\n#### Out-of-sample predictive test (train {h['train_seasons']}, test {h['test_seasons']}; N test = {h['n_test']}, qualifying in test = {h['n_test_qualifying']})\n")
    md.append('| Metric | Baseline (Elo + competition) | Baseline + altitude terms |\n|---|---|---|')
    md.append(f"| Log-loss, all test matches | {h['all_matches']['logloss_baseline']:.4f} | {h['all_matches']['logloss_altitude']:.4f} |")
    md.append(f"| Brier, all test matches | {h['all_matches']['brier_baseline']:.4f} | {h['all_matches']['brier_altitude']:.4f} |")
    q = h['qualifying_matches']
    md.append(f"| Log-loss, qualifying test matches | {q['logloss_baseline']:.4f} | {q['logloss_altitude']:.4f} |")
    md.append(f"| Mean predicted home-win prob, qualifying test matches (actual {q['actual_home']:.1%}) | {q['pred_home_baseline']:.1%} | {q['pred_home_altitude']:.1%} |")
    md.append(f"| Mean predicted home-or-draw prob, qualifying test matches (actual {q['actual_hd']:.1%}) | {q['pred_hd_baseline']:.1%} | {q['pred_hd_altitude']:.1%} |")
    md.append('\nCalibration on the test seasons by gap bin:\n')
    md.append('| Gap bin (m) | N | Actual home win | Baseline prediction | Altitude-model prediction |\n|---|---|---|---|---|')
    for row in h['calibration_by_gap_bin']: md.append(f"| {row['gb']} | {row['n']} | {row['actual_home']:.1%} | {row['pred_baseline']:.1%} | {row['pred_altitude']:.1%} |")
    return '\n'.join(md)

def odds_tables():
    r = json.load(open(os.path.join(OUT, 'odds_backtest_results.json')))
    md = []
    j = r['join']; s = r['sample']
    md.append(f"Joined {j['joined']} of {j['odds_rows']} Liga MX price rows to venue-verified FBref matches (score agreement {j['score_agreement']:.1%}); seasons {s['seasons']}; qualifying matches with prices: {s['qualifying']}. Hosts: {s['qualifying_hosts']}. Visitors: {s['qualifying_visitors']}. Mean Bet365 1X2 overround {s['avg_overround_b365']:.3f}.\n")
    def block(name, b):
        if b.get('n', 0) == 0: return f'| {name} | 0 | | | | | | | |'
        return (f"| {name} | {b['n']} | {b['actual']['H']:.1%} / {b['actual']['D']:.1%} / {b['actual']['A']:.1%} | {b['implied_Odd_pow']['H']:.1%} / {b['implied_Odd_pow']['D']:.1%} / {b['implied_Odd_pow']['A']:.1%} | "
                f"{b['roi_bet365']['home_win']:+.1%} (SE {b['roi_bet365']['home_win_se']:.1%}) | {b['roi_best_price']['home_win']:+.1%} | {b['roi_best_price']['double_chance_1x_synth']:+.1%} | {b['roi_best_price']['dnb_synth']:+.1%} | {b['roi_best_price']['avg_home_odds']:.2f} |")
    md.append('| Sample | N | Actual H / D / A | Bet365 implied (power de-vig) H / D / A | ROI home win at Bet365 | ROI home win at best price | ROI double chance 1X (synthetic) | ROI draw-no-bet (synthetic) | Mean best home odds |\n|---|---|---|---|---|---|---|---|---|')
    m = r['market_vs_actual']
    for k in ['qualifying', 'qualifying_league_phase_only', 'toluca_home_all', 'toluca_home_vs_non_qualifying', 'mexico_city_hosts_vs_sea_level_visitors_gap2000_2500', 'all_matches']: md.append(block(k, m[k]))
    md.append('\nQualifying matches by season:\n')
    md.append('| Season | N | Actual H / D / A | Implied H / D / A | ROI home win (Bet365) | ROI home win (best) |\n|---|---|---|---|---|---|')
    for k, b in m['by_season_qualifying'].items():
        if b.get('n', 0): md.append(f"| {k} | {b['n']} | {b['actual']['H']:.0%} / {b['actual']['D']:.0%} / {b['actual']['A']:.0%} | {b['implied_Odd_pow']['H']:.0%} / {b['implied_Odd_pow']['D']:.0%} / {b['implied_Odd_pow']['A']:.0%} | {b['roi_bet365']['home_win']:+.1%} | {b['roi_best_price']['home_win']:+.1%} |")
    h = r['model_vs_market_holdout']
    md.append(f"\nModel versus market, out of sample (train {h['train']}, test {h['test']}, N test = {h['n_test']}, qualifying = {h['n_test_qualifying']}):\n")
    md.append('| Metric | Elo only | Elo + altitude | Bet365 (de-vigged) |\n|---|---|---|---|')
    md.append(f"| Log-loss, all test matches | {h['logloss_all']['elo_only']:.4f} | {h['logloss_all']['elo_plus_altitude']:.4f} | {h['logloss_all']['market_bet365_power_devig']:.4f} |")
    md.append(f"| Log-loss, qualifying test matches | {h['logloss_qualifying']['elo_only']:.4f} | {h['logloss_qualifying']['elo_plus_altitude']:.4f} | {h['logloss_qualifying']['market_bet365_power_devig']:.4f} |")
    qm = h['qualifying_test_matches']
    md.append(f"| Mean home-win prob, qualifying test matches (actual {qm['actual_home']:.1%}) | {qm['elo_home']:.1%} | {qm['elo_alt_home']:.1%} | {qm['market_home']:.1%} |")
    ma = h['market_anchored_logit']
    md.append(f"\nMarket-anchored test: a logit of home win on the de-vigged market probability plus the net gap (train {h['train']}) gives a gap coefficient of {ma['gap_pos_km_coef_train']:+.3f} per 1,000 m (SE {ma['gap_pos_km_se']:.3f}, p = {ma['gap_pos_km_p']:.3g}); test log-loss market-only {ma['logloss_home_win_test_market_only']:.4f} vs market + altitude {ma['logloss_home_win_test_market_plus_altitude']:.4f} (qualifying subset: {ma['logloss_qualifying_market_only']:.4f} vs {ma['logloss_qualifying_market_plus_altitude']:.4f}).\n")
    md.append('Value-bet simulation on the test seasons (back the home side at the best price when the Elo + altitude model probability exceeds the implied probability by the stated edge):\n')
    md.append('| Required edge | Bets | ROI | Bets in qualifying matches | ROI in qualifying matches |\n|---|---|---|---|---|')
    def pr(x): return 'n/a' if x is None else f'{x:+.1%}'
    for k, v in r['value_bet_simulation_holdout'].items(): md.append(f"| {k.replace('edge_', '')} | {v['bets']} | {pr(v['roi'])} | {v['bets_qualifying']} | {pr(v['roi_qualifying'])} |")
    return '\n'.join(md)

def nt_tables():
    r = json.load(open(os.path.join(OUT, 'national_team_results.json')))
    md = []
    def rr(d):
        lines = ['| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |', '|---|---|---|---|---|---|---|---|---|---|']
        for k, v in d.items():
            if isinstance(v, dict) and v.get('n', 0): lines.append(f"| {k} | {v['n']} | {v['home_win']:.1%} | {v['draw']:.1%} | {v['away_win']:.1%} | {v['unbeaten']:.1%} | {v['gd']:+.2f} | {v['hg']:.2f} | {v['ag']:.2f} | {v['total']:.2f} |")
        return '\n'.join(lines)
    raw = r['raw']
    md.append(rr({'Qualifying (gap > 2,500 m, host based at that elevation)': raw['qualifying_all'], 'Qualifying, competitive only': raw['qualifying_competitive'], 'Qualifying, friendlies only': raw['qualifying_friendly'], 'Qualifying without the host-base filter': raw['qualifying_without_host_acclimatization_filter'],
                  'Same hosts vs visitors from similar elevation': raw['same_hosts_low_gap'], 'Same hosts, competitive, similar elevation': raw['same_hosts_competitive_low_gap']}))
    md.append('\nBy host nation (qualifying):\n'); md.append(rr(raw['qualifying_by_home']))
    md.append('\nBy host nation without the host-base filter:\n'); md.append(rr(raw['qualifying_without_filter_by_home']))
    md.append('\nBy host city (qualifying):\n'); md.append(rr(raw['qualifying_by_city']))
    md.append('\nBy era (qualifying):\n'); md.append(rr(raw['qualifying_by_era']))
    md.append('\nBy net-gap bin (all matches with computable gap since 1990, hosts of the five countries):\n'); md.append(rr(raw['by_gap_bin']))
    a = r['adjusted']
    md.append(f"\nAdjusted (ordered logit with pre-match Elo, competitive flag; N = {a['n']}):\n")
    md.append('| Term | Coefficient | 95% CI | SE | p |\n|---|---|---|---|---|')
    for k in ['elo_diff100', 'gap_pos_km', 'gap_neg_km', 'q2500']: md.append(coef_row(k, a['ordered_logit'][k]))
    md.append(coef_row('Poisson home goals: gap per 1,000 m', a['poisson_home_score']['gap_pos_km'], 'rate'))
    md.append(coef_row('Poisson away goals: gap per 1,000 m', a['poisson_away_score']['gap_pos_km'], 'rate'))
    t = r['goal_timing']
    md.append('\nGoal timing (secondary; shares of each side\'s own goals):\n')
    md.append('| Sample | Goals | Home goals | Away goals | Home share 2nd half | Away share 2nd half | Home share after 75\' | Away share after 75\' |\n|---|---|---|---|---|---|---|---|')
    for k in ['qualifying', 'low_gap_same_hosts', 'all_five_countries']:
        v = t[k]; md.append(f"| {k} | {v['goals']} | {v['home_goals']} | {v['away_goals']} | {v['home_share_2nd_half']} | {v['away_share_2nd_half']} | {v['home_share_after_75']} | {v['away_share_after_75']} |")
    return '\n'.join(md)

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if which in ('club', 'all'): open(os.path.join(OUT, 'tables_club.md'), 'w').write(club_tables()); print('tables_club.md written')
    if which in ('odds', 'all'): open(os.path.join(OUT, 'tables_odds.md'), 'w').write(odds_tables()); print('tables_odds.md written')
    if which in ('nt', 'all'): open(os.path.join(OUT, 'tables_nt.md'), 'w').write(nt_tables()); print('tables_nt.md written')
