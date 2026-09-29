"""Liga MX odds backtest (the only competition in the sample with archived pre-match prices).
Prices: Bet365 closing-ish 1X2 and the cross-book maximum, via Football-Data.co.uk as mirrored in the
Club-Football-Match-Data-2000-2025 dataset. No timestamps: Football-Data.co.uk collects odds shortly before kick-off
(Friday afternoon / day of match), so treat as late pre-match prices, not opening lines.
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
import statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
warnings.filterwarnings('ignore')
THRESH = 2500.0
NAME_MAP = {'Club Tijuana': 'Tijuana', 'Mazatlan FC': 'Mazatlán', 'Dorados de Sinaloa': 'Sinaloa', 'U.A.N.L.- Tigres': 'UANL', 'U.N.A.M.- Pumas': 'UNAM', 'Club America': 'América', 'Club Leon': 'León',
            'Atl. San Luis': 'Atlético', 'Guadalajara Chivas': 'Guadalajara', 'Monarcas': 'Morelia', 'Santos Laguna': 'Santos', 'Queretaro': 'Querétaro', 'Juarez': 'FC Juárez', 'Leones Negros': 'UdeG',
            'Chiapas': 'Chiapas', 'Lobos BUAP': 'Lobos BUAP', 'Atlas': 'Atlas', 'Cruz Azul': 'Cruz Azul', 'Monterrey': 'Monterrey', 'Necaxa': 'Necaxa', 'Pachuca': 'Pachuca', 'Puebla': 'Puebla', 'Toluca': 'Toluca', 'Veracruz': 'Veracruz', 'Atlante': 'Atlante'}

def devig_multiplicative(o):
    p = 1.0 / o; return p / p.sum(axis=1, keepdims=True)

def devig_power(o, tol=1e-9):
    """Power (Vovk) method: find k so that sum (1/o)^k = 1."""
    p = 1.0 / o; out = np.empty_like(p)
    for i in range(len(p)):
        lo, hi = 0.5, 3.0
        for _ in range(60):
            k = (lo + hi) / 2; s = (p[i] ** k).sum()
            if s > 1: lo = k
            else: hi = k
        out[i] = p[i] ** ((lo + hi) / 2)
    return out

def main():
    odds = pd.read_csv(os.path.join(RAW, 'MEX_football_data_via_xgabora.csv'))
    odds['Date'] = pd.to_datetime(odds['MatchDate'])
    odds['home'] = odds['HomeTeam'].map(NAME_MAP); odds['away'] = odds['AwayTeam'].map(NAME_MAP)
    g = pd.read_csv(os.path.join(OUT, 'matches_with_gap.csv')); g['Date'] = pd.to_datetime(g['Date'])
    g = g[g['comp'] == 'MEX']
    # join on date +/- 1 day and team names
    mm = []
    for r in odds.itertuples(index=False):
        cand = g[(g['home'] == r.home) & (g['away'] == r.away) & ((g['Date'] - r.Date).abs() <= pd.Timedelta(days=1))]
        if len(cand) == 1: mm.append(dict(cand.iloc[0].to_dict(), **{c: getattr(r, c) for c in ['OddHome', 'OddDraw', 'OddAway', 'MaxHome', 'MaxDraw', 'MaxAway', 'Over25', 'Under25', 'FTHome', 'FTAway', 'HomeElo', 'AwayElo']}))
    d = pd.DataFrame(mm)
    out = {'join': dict(odds_rows=int(len(odds)), fbref_rows=int(len(g)), joined=int(len(d)), unmatched_fbref_names=sorted(set(odds['HomeTeam'][odds['home'].isna()])))}
    ok = (d['FTHome'] == d['hg']) & (d['FTAway'] == d['ag']); out['join']['score_agreement'] = round(float(ok.mean()), 4)
    d = d[ok & d['net_gap'].notna() & d['OddHome'].notna()].copy()
    for src in ['Odd', 'Max']:
        o = d[[f'{src}Home', f'{src}Draw', f'{src}Away']].values.astype(float)
        d[f'{src}_overround'] = (1 / o).sum(1)
        pm = devig_multiplicative(o); pp = devig_power(o)
        d[f'{src}_pH_mult'], d[f'{src}_pD_mult'], d[f'{src}_pA_mult'] = pm[:, 0], pm[:, 1], pm[:, 2]
        d[f'{src}_pH_pow'], d[f'{src}_pD_pow'], d[f'{src}_pA_pow'] = pp[:, 0], pp[:, 1], pp[:, 2]
    d['H'] = (d['result'] == 'H').astype(float); d['HD'] = (d['result'] != 'A').astype(float); d['A'] = (d['result'] == 'A').astype(float)
    Q = d[(d['net_gap'] > THRESH) & d['home_acclimatized']].copy()
    out['sample'] = dict(all_joined=int(len(d)), qualifying=int(len(Q)), seasons=f"{int(d['season'].min())}-{int(d['season'].max())}",
                         qualifying_hosts=Q['home'].value_counts().to_dict(), qualifying_visitors=Q['away'].value_counts().to_dict(), avg_overround_b365=round(float(d['Odd_overround'].mean()), 4))
    def market_block(sub):
        n = len(sub)
        if n == 0: return dict(n=0)
        b = {}
        b['n'] = int(n)
        b['actual'] = dict(H=round(float(sub['H'].mean()), 3), D=round(float((sub['result'] == 'D').mean()), 3), A=round(float(sub['A'].mean()), 3))
        for src in ['Odd', 'Max']:
            for meth in ['mult', 'pow']:
                b[f'implied_{src}_{meth}'] = dict(H=round(float(sub[f'{src}_pH_{meth}'].mean()), 3), D=round(float(sub[f'{src}_pD_{meth}'].mean()), 3), A=round(float(sub[f'{src}_pA_{meth}'].mean()), 3))
        # flat-stake returns (1 unit per match)
        for src, lab in [('Odd', 'bet365'), ('Max', 'best_price')]:
            ret_h = np.where(sub['H'] == 1, sub[f'{src}Home'] - 1, -1.0)
            # double chance synthesised from 1X2 at the same book: fair odds from devigged probs, then the book's own overround re-applied
            p1x = sub[f'{src}_pH_mult'] + sub[f'{src}_pD_mult']; odds_1x = 1 / (p1x * sub[f'{src}_overround'] ** 0.5)
            ret_1x = np.where(sub['HD'] == 1, odds_1x - 1, -1.0)
            # draw no bet: stake returned on draw; synthesised odds = 1 / (pH/(pH+pA)) with the same margin treatment
            pdnb = sub[f'{src}_pH_mult'] / (sub[f'{src}_pH_mult'] + sub[f'{src}_pA_mult']); odds_dnb = 1 / (pdnb * sub[f'{src}_overround'] ** 0.5)
            ret_dnb = np.where(sub['H'] == 1, odds_dnb - 1, np.where(sub['A'] == 1, -1.0, 0.0))
            b[f'roi_{lab}'] = dict(home_win=round(float(ret_h.mean()), 4), home_win_se=round(float(ret_h.std(ddof=1) / np.sqrt(n)), 4), double_chance_1x_synth=round(float(ret_1x.mean()), 4), dnb_synth=round(float(ret_dnb.mean()), 4),
                                   avg_home_odds=round(float(sub[f'{src}Home'].mean()), 3), avg_synth_1x_odds=round(float(odds_1x.mean()), 3), avg_synth_dnb_odds=round(float(odds_dnb.mean()), 3))
        return b
    out['market_vs_actual'] = dict(qualifying=market_block(Q), qualifying_league_phase_only=market_block(Q[Q['round'].isna() | ~Q['round'].astype(str).str.contains('Final|Liguilla|Quarter|Semi|Play', case=False)]),
                                   all_matches=market_block(d), toluca_home_all=market_block(d[d['home'] == 'Toluca']), toluca_home_vs_non_qualifying=market_block(d[(d['home'] == 'Toluca') & (d['net_gap'] <= THRESH)]),
                                   mexico_city_hosts_vs_sea_level_visitors_gap2000_2500=market_block(d[(d['net_gap'] > 2000) & (d['net_gap'] <= THRESH)]),
                                   by_season_qualifying={int(k): market_block(v) for k, v in Q.groupby('season')})
    # ---- model vs market, out of sample: train ordered logit on 2015-2019 with Elo(plain) + gap, evaluate 2020-2024
    d['elo_diff100'] = d['elo_plain_diff'] / 100.0; d['gap_pos_km'] = d['net_gap'].clip(lower=0) / 1000.0; d['gap_neg_km'] = (-d['net_gap'].clip(upper=0)) / 1000.0
    tr = d[d['season'] <= 2019]; te = d[d['season'] >= 2020]
    ycat = lambda s: pd.Series(pd.Categorical(s['result'], categories=['A', 'D', 'H'], ordered=True), index=s.index)
    m0 = OrderedModel(ycat(tr), tr[['elo_diff100']], distr='logit').fit(method='bfgs', maxiter=400, disp=False)
    m1 = OrderedModel(ycat(tr), tr[['elo_diff100', 'gap_pos_km', 'gap_neg_km']], distr='logit').fit(method='bfgs', maxiter=400, disp=False)
    # market-anchored model: logit of market prob + gap (does altitude add information beyond the closing price?)
    tr2 = tr.assign(lmH=np.log(tr['Odd_pH_pow'] / (1 - tr['Odd_pH_pow']))); te2 = te.assign(lmH=np.log(te['Odd_pH_pow'] / (1 - te['Odd_pH_pow'])))
    mk0 = sm.GLM(tr2['H'], sm.add_constant(tr2[['lmH']]), family=sm.families.Binomial()).fit()
    mk1 = sm.GLM(tr2['H'], sm.add_constant(tr2[['lmH', 'gap_pos_km']]), family=sm.families.Binomial()).fit()
    y = pd.Categorical(te['result'], categories=['A', 'D', 'H']).codes
    P0 = m0.model.predict(m0.params, exog=te[['elo_diff100']]); P1 = m1.model.predict(m1.params, exog=te[['elo_diff100', 'gap_pos_km', 'gap_neg_km']])
    PM = te[['Odd_pA_pow', 'Odd_pD_pow', 'Odd_pH_pow']].values
    def ll(P): P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True); return round(float(-np.log(P[np.arange(len(y)), y]).mean()), 4)
    q = (te['net_gap'] > THRESH).values & te['home_acclimatized'].values
    def llq(P): P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True); return round(float(-np.log(P[q, y[q]]).mean()), 4)
    pmk0 = mk0.predict(sm.add_constant(te2[['lmH']])); pmk1 = mk1.predict(sm.add_constant(te2[['lmH', 'gap_pos_km']]))
    def llb(p, yy): p = np.clip(p, 1e-6, 1 - 1e-6); return round(float(-(yy * np.log(p) + (1 - yy) * np.log(1 - p)).mean()), 4)
    out['model_vs_market_holdout'] = dict(train='2015-2019', test='2020-2024', n_test=int(len(te)), n_test_qualifying=int(q.sum()),
        logloss_all=dict(elo_only=ll(P0), elo_plus_altitude=ll(P1), market_bet365_power_devig=ll(PM)),
        logloss_qualifying=dict(elo_only=llq(P0), elo_plus_altitude=llq(P1), market_bet365_power_devig=llq(PM)),
        market_anchored_logit=dict(gap_pos_km_coef_train=round(float(mk1.params['gap_pos_km']), 4), gap_pos_km_se=round(float(mk1.bse['gap_pos_km']), 4), gap_pos_km_p=round(float(mk1.pvalues['gap_pos_km']), 4),
                                   logloss_home_win_test_market_only=llb(pmk0.values, te2['H'].values), logloss_home_win_test_market_plus_altitude=llb(pmk1.values, te2['H'].values),
                                   logloss_qualifying_market_only=llb(pmk0.values[q], te2['H'].values[q]), logloss_qualifying_market_plus_altitude=llb(pmk1.values[q], te2['H'].values[q])),
        qualifying_test_matches=dict(actual_home=round(float(te['H'].values[q].mean()), 3), market_home=round(float(PM[q, 2].mean()), 3), elo_home=round(float(P0[q, 2].mean()), 3), elo_alt_home=round(float(P1[q, 2].mean()), 3)))
    # value-bet simulation on holdout: back home when model(elo+alt) prob exceeds best-price implied prob by >= edge
    sims = {}
    for edge in [0.0, 0.03, 0.05]:
        pick = (P1[:, 2] > 1 / te['MaxHome'].values + edge)
        ret = np.where(te['H'].values == 1, te['MaxHome'].values - 1, -1.0)
        sims[f'edge_{edge}'] = dict(bets=int(pick.sum()), roi=round(float(ret[pick].mean()), 4) if pick.sum() else None, bets_qualifying=int((pick & q).sum()), roi_qualifying=round(float(ret[pick & q].mean()), 4) if (pick & q).sum() else None)
    out['value_bet_simulation_holdout'] = sims
    Q[['season', 'Date', 'home', 'away', 'hg', 'ag', 'venue', 'net_gap', 'OddHome', 'OddDraw', 'OddAway', 'MaxHome', 'MaxDraw', 'MaxAway', 'Odd_pH_pow']].to_csv(os.path.join(OUT, 'ligamx_qualifying_with_odds.csv'), index=False)
    json.dump(out, open(os.path.join(OUT, 'odds_backtest_results.json'), 'w'), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:6000])

if __name__ == '__main__':
    main()
