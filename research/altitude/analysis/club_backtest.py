"""Historical club backtest: do hosts with a >2,500 m net elevation gap outperform expectation?
Outputs JSON + markdown tables in output/. Run after data/registry/venue_registry.csv exists.
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.miscmodels.ordinal_model import OrderedModel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
warnings.filterwarnings('ignore')
rng = np.random.default_rng(20260929)
THRESH = 2500.0

def raw_table(df):
    n = len(df)
    if n == 0:
        return dict(n=0)
    return dict(n=int(n), home_win=round((df['result'] == 'H').mean(), 3), draw=round((df['result'] == 'D').mean(), 3), away_win=round((df['result'] == 'A').mean(), 3),
                home_unbeaten=round((df['result'] != 'A').mean(), 3), home_ppg=round(np.where(df['result'] == 'H', 3, np.where(df['result'] == 'D', 1, 0)).mean(), 3),
                gd=round((df['hg'] - df['ag']).mean(), 3), hg=round(df['hg'].mean(), 3), ag=round(df['ag'].mean(), 3), total=round((df['hg'] + df['ag']).mean(), 3),
                over25=round(((df['hg'] + df['ag']) > 2.5).mean(), 3), btts=round(((df['hg'] > 0) & (df['ag'] > 0)).mean(), 3),
                hosts=int(df['home'].nunique()), venues=int(df['venue'].nunique()), seasons=int(df['season'].nunique()))

def gap_features(df):
    X = pd.DataFrame(index=df.index)
    X['elo_diff100'] = df['elo_diff'] / 100.0
    X['gap_pos_km'] = df['net_gap'].clip(lower=0) / 1000.0     # venue above visitor's base
    X['gap_neg_km'] = (-df['net_gap'].clip(upper=0)) / 1000.0  # venue below visitor's base
    X['q2500'] = (df['net_gap'] > THRESH).astype(float)
    X['away_recent_alt'] = df['away_recent_alt'].astype(float)
    present = sorted(df['comp'].unique())
    for c in present[1:]:   # first competition present is the reference category
        X[f'comp_{c}'] = (df['comp'] == c).astype(float)
    return X

def fit_ordered(df, cols):
    y = pd.Series(pd.Categorical(df['result'], categories=['A', 'D', 'H'], ordered=True), index=df.index)
    X = gap_features(df)[cols]
    mod = OrderedModel(y, X, distr='logit')
    res = mod.fit(method='bfgs', maxiter=400, disp=False)
    return res

def fit_binom(df, formula_rhs, target):
    d = df.copy(); X = gap_features(df); X = X[[c for c in X.columns if c not in d.columns]]; d = pd.concat([d, X], axis=1)
    d['y'] = (d['result'] == 'H').astype(int) if target == 'H' else (d['result'] != 'A').astype(int)
    d['cluster'] = d['home'].astype(str) + '|' + d['season'].astype(str)
    res = smf.glm('y ~ ' + formula_rhs, data=d, family=sm.families.Binomial()).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['cluster'])[0]})
    return res

def fit_poisson(df, formula_rhs, target):
    d = df.copy(); X = gap_features(df); X = X[[c for c in X.columns if c not in d.columns]]; d = pd.concat([d, X], axis=1)
    d['y'] = d[target]
    d['cluster'] = d['home'].astype(str) + '|' + d['season'].astype(str)
    res = smf.glm('y ~ ' + formula_rhs, data=d, family=sm.families.Poisson()).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['cluster'])[0]})
    return res

def coef(res, name):
    try:
        b = float(res.params[name]); se = float(res.bse[name]); return dict(coef=round(b, 4), se=round(se, 4), ci=[round(b - 1.96 * se, 4), round(b + 1.96 * se, 4)], p=round(float(res.pvalues[name]), 4))
    except KeyError:
        return None

def fe_poisson(df):
    """Team fixed effects (attack, defence), home-team-specific home advantage, competition and season dummies,
    altitude gap terms. Identifies the gap effect WITHIN home team (same host vs lowland and highland visitors)."""
    rows = []
    for r in df.itertuples(index=False):
        base = dict(match_id=r.match_id, comp=r.comp, season=r.season, cluster=f'{r.home}|{r.season}', gap_pos=max(r.net_gap, 0) / 1000.0, gap_neg=max(-r.net_gap, 0) / 1000.0, q2500=float(r.net_gap > THRESH))
        rows.append(dict(base, y=r.hg, att=f'{r.home}|{r.home_cc}', dfn=f'{r.away}|{r.away_cc}', is_home=1, hometeam=f'{r.home}|{r.home_cc}'))
        rows.append(dict(base, y=r.ag, att=f'{r.away}|{r.away_cc}', dfn=f'{r.home}|{r.home_cc}', is_home=0, hometeam='none'))
    d = pd.DataFrame(rows)
    # pool rare teams to keep the design tractable
    cnt = d['att'].value_counts(); rare = set(cnt[cnt < 20].index)
    d['att'] = d['att'].where(~d['att'].isin(rare), 'RARE'); d['dfn'] = d['dfn'].where(~d['dfn'].isin(rare), 'RARE')
    hc = d.loc[d['is_home'] == 1, 'hometeam'].value_counts(); rare_h = set(hc[hc < 30].index)
    d['hometeam'] = d['hometeam'].where(~d['hometeam'].isin(rare_h), 'RAREHOME')
    d['gapH'] = d['gap_pos'] * d['is_home']; d['gapA'] = d['gap_pos'] * (1 - d['is_home'])
    d['gapnegH'] = d['gap_neg'] * d['is_home']; d['gapnegA'] = d['gap_neg'] * (1 - d['is_home'])
    d['qH'] = d['q2500'] * d['is_home']; d['qA'] = d['q2500'] * (1 - d['is_home'])
    out = {}
    for tag, rhs in [('continuous', 'gapH + gapA + gapnegH + gapnegA'), ('indicator', 'qH + qA')]:
        f = f'y ~ C(att) + C(dfn) + C(hometeam) + C(comp) + C(season) + {rhs}'
        res = smf.glm(f, data=d, family=sm.families.Poisson()).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(d['cluster'])[0]})
        out[tag] = {k: coef(res, k) for k in rhs.replace(' ', '').split('+')}
        out[tag]['n_rows'] = int(len(d)); out[tag]['n_params'] = int(len(res.params))
    return out

def bootstrap_excess(df, exp_h, exp_pts, n=4000):
    """Cluster bootstrap (home team-season) of actual minus expected home-win rate and points (vectorised)."""
    d = df.assign(exp_h=exp_h, exp_pts=exp_pts, act_h=(df['result'] == 'H').astype(float), act_pts=np.where(df['result'] == 'H', 3, np.where(df['result'] == 'D', 1, 0)).astype(float))
    d['cl'] = pd.factorize(d['home'].astype(str) + '|' + d['season'].astype(str))[0]
    g = d.groupby('cl').agg(dh=('act_h', lambda s: 0.0), n=('act_h', 'size'))
    g['dh'] = (d['act_h'] - d['exp_h']).groupby(d['cl']).sum(); g['dp'] = (d['act_pts'] - d['exp_pts']).groupby(d['cl']).sum()
    dh, dp, cnt = g['dh'].values, g['dp'].values, g['n'].values.astype(float)
    G = len(g); idx = rng.integers(0, G, size=(n, G))
    sh = dh[idx].sum(1) / cnt[idx].sum(1); sp = dp[idx].sum(1) / cnt[idx].sum(1)
    return dict(excess_home_win=round(float((d['act_h'] - d['exp_h']).mean()), 4), ci_home_win=[round(float(x), 4) for x in np.percentile(sh, [2.5, 97.5])],
                excess_ppg=round(float((d['act_pts'] - d['exp_pts']).mean()), 4), ci_ppg=[round(float(x), 4) for x in np.percentile(sp, [2.5, 97.5])], clusters=int(G), n=int(len(d)))

import time
def main():
    t0 = time.time(); m = load_matches(); reg = load_registry()
    m, pv = attach_elevations(m, reg)
    m = add_recent_exposure(m)
    results = {'notes': []}
    results['coverage'] = dict(total_matches=int(len(m)), with_venue_elev=int(m['venue_elev'].notna().sum()), with_gap=int(m['net_gap'].notna().sum()),
                               by_comp=m.groupby('comp').agg(n=('match_id', 'size'), with_gap=('net_gap', lambda s: int(s.notna().sum())), seasons=('season', lambda s: f'{s.min()}-{s.max()}')).reset_index().to_dict('records'))
    m = m[~m['extra_time']].copy()   # regulation-time scores only (FBref cup scores include extra time)
    results['notes'].append('Matches decided after extra time were excluded because the source score includes extra-time goals.')
    a = m[m['net_gap'].notna()].copy()
    # ---- Elo: plain, then altitude-neutral (iterate: estimate gap effect, credit it to the venue in the rating update)
    a = elo_ratings(a, gap_coef=0.0)
    ord0 = fit_ordered(a[a['season'] >= 2015], ['elo_diff100', 'gap_pos_km'] + [c for c in gap_features(a).columns if c.startswith('comp_')])
    gap_logit = float(ord0.params['gap_pos_km']); elo_per_logit = 100.0 / float(ord0.params['elo_diff100'])
    gap_coef = gap_logit * elo_per_logit  # Elo points per km of positive gap
    for _ in range(3):
        a = elo_ratings(a, gap_coef=gap_coef)
        ordi = fit_ordered(a[a['season'] >= 2015], ['elo_diff100', 'gap_pos_km'] + [c for c in gap_features(a).columns if c.startswith('comp_')])
        gap_coef = float(ordi.params['gap_pos_km']) * 100.0 / float(ordi.params['elo_diff100'])
    results['elo'] = dict(altitude_neutral_gap_elo_points_per_km=round(gap_coef, 1), note='Elo points per 1,000 m of positive net gap credited to the venue rather than the club; hfa=70 Elo points used inside the rating update')
    a['elo_neutral_h'] = a['elo_h']; a['elo_neutral_a'] = a['elo_a']; a['elo_neutral_diff'] = a['elo_diff']
    # keep both rating variants
    plain = elo_ratings(a.copy(), gap_coef=0.0); a['elo_plain_diff'] = plain['elo_diff'].values
    an = a[a['season'] >= 2015].copy()   # first season used for rating burn-in
    an['elo_diff'] = an['elo_neutral_diff']
    # ---- samples
    Q = an[(an['net_gap'] > THRESH)]
    Qacc = Q[Q['home_acclimatized']]
    results['sample'] = dict(qualifying_all=int(len(Q)), qualifying_home_acclimatized=int(len(Qacc)), home_not_acclimatized=int(len(Q) - len(Qacc)))
    results['raw'] = {}
    results['raw']['qualifying_by_comp_type'] = {k: raw_table(g) for k, g in Qacc.groupby('comp_type')}
    results['raw']['qualifying_by_comp'] = {k: raw_table(g) for k, g in Qacc.groupby('comp')}
    results['raw']['qualifying_by_home_country'] = {k: raw_table(g) for k, g in Qacc.groupby('home_cc')}
    results['raw']['qualifying_by_venue_top'] = {k: raw_table(g) for k, g in Qacc.groupby('venue') if len(g) >= 25}
    results['raw']['qualifying_by_host_top'] = {k: raw_table(g) for k, g in Qacc.groupby('home') if len(g) >= 25}
    results['raw']['all_matches_by_comp'] = {k: raw_table(g) for k, g in an.groupby('comp')}
    hosts = set(Qacc['home'])
    ctrl = an[(an['home'].isin(hosts)) & (an['net_gap'].abs() <= 500) & an['home_acclimatized']]
    results['raw']['same_hosts_vs_similar_elevation_visitors'] = raw_table(ctrl)
    results['raw']['same_hosts_all_home_matches'] = raw_table(an[an['home'].isin(hosts)])
    bins = [-9999, -2500, -1500, -500, 500, 1500, 2000, 2500, 3000, 3500, 9999]
    an['gap_bin'] = pd.cut(an['net_gap'], bins=bins)
    results['raw']['by_gap_bin'] = {str(k): raw_table(g) for k, g in an[an['home_acclimatized']].groupby('gap_bin', observed=True)}
    results['raw']['qualifying_by_visitor_recent_altitude'] = {str(k): raw_table(g) for k, g in Qacc.groupby('away_recent_alt')}
    results['raw']['qualifying_by_period'] = {k: raw_table(g) for k, g in Qacc.groupby(np.where(Qacc['season'] <= 2019, '2015-2019', '2020-2025'))}
    # ---- adjusted models (seasons >= 2015, home acclimatized, all gaps)
    A = an[an['home_acclimatized']].copy()
    comps = [c for c in gap_features(A).columns if c.startswith('comp_')]
    results['adjusted'] = {}
    o_cont = fit_ordered(A, ['elo_diff100', 'gap_pos_km', 'gap_neg_km'] + comps)
    o_ind = fit_ordered(A, ['elo_diff100', 'q2500'] + comps)
    o_both = fit_ordered(A, ['elo_diff100', 'gap_pos_km', 'q2500'] + comps)
    o_exp = fit_ordered(A, ['elo_diff100', 'gap_pos_km', 'away_recent_alt'] + comps)
    def ocoef(res, k):
        b = float(res.params[k]); se = float(res.bse[k]); return dict(coef=round(b, 4), se=round(se, 4), ci=[round(b - 1.96 * se, 4), round(b + 1.96 * se, 4)], p=round(float(res.pvalues[k]), 4))
    results['adjusted']['ordered_logit'] = dict(
        n=int(len(A)), continuous=dict(elo_diff100=ocoef(o_cont, 'elo_diff100'), gap_pos_km=ocoef(o_cont, 'gap_pos_km'), gap_neg_km=ocoef(o_cont, 'gap_neg_km')),
        indicator=dict(q2500=ocoef(o_ind, 'q2500')), both=dict(gap_pos_km=ocoef(o_both, 'gap_pos_km'), q2500=ocoef(o_both, 'q2500')),
        with_recent_exposure=dict(gap_pos_km=ocoef(o_exp, 'gap_pos_km'), away_recent_alt=ocoef(o_exp, 'away_recent_alt')),
        elo_equivalent_of_2500m=round(float(o_cont.params['gap_pos_km']) * 2.5 * 100 / float(o_cont.params['elo_diff100']), 1))
    # gap bins (reference |gap|<=500)
    A['gb'] = pd.cut(A['net_gap'], bins=bins).astype(str)
    Xb = gap_features(A)[['elo_diff100'] + comps].copy()
    for b in sorted(A['gb'].unique()):
        if b != '(-500, 500]':
            Xb['bin_' + b] = (A['gb'] == b).astype(float)
    ob = OrderedModel(pd.Series(pd.Categorical(A['result'], categories=['A', 'D', 'H'], ordered=True), index=A.index), Xb, distr='logit').fit(method='bfgs', maxiter=400, disp=False)
    results['adjusted']['ordered_logit_gap_bins'] = {c.replace('bin_', ''): ocoef(ob, c) for c in Xb.columns if c.startswith('bin_')}
    # markets: home win, home-or-draw (cluster-robust logit)
    rhs = 'elo_diff100 + gap_pos_km + gap_neg_km + C(comp)'
    lh = fit_binom(A, rhs, 'H'); lhd = fit_binom(A, rhs, 'HD')
    lhq = fit_binom(A, 'elo_diff100 + q2500 + C(comp)', 'H'); lhdq = fit_binom(A, 'elo_diff100 + q2500 + C(comp)', 'HD')
    results['adjusted']['logit_home_win'] = dict(gap_pos_km=coef(lh, 'gap_pos_km'), q2500=coef(lhq, 'q2500'))
    results['adjusted']['logit_home_or_draw'] = dict(gap_pos_km=coef(lhd, 'gap_pos_km'), q2500=coef(lhdq, 'q2500'))
    # goals (cluster-robust Poisson)
    ph = fit_poisson(A, rhs, 'hg'); pa = fit_poisson(A, rhs, 'ag')
    phq = fit_poisson(A, 'elo_diff100 + q2500 + C(comp)', 'hg'); paq = fit_poisson(A, 'elo_diff100 + q2500 + C(comp)', 'ag')
    results['adjusted']['poisson_home_goals'] = dict(gap_pos_km=coef(ph, 'gap_pos_km'), gap_neg_km=coef(ph, 'gap_neg_km'), q2500=coef(phq, 'q2500'))
    results['adjusted']['poisson_away_goals'] = dict(gap_pos_km=coef(pa, 'gap_pos_km'), gap_neg_km=coef(pa, 'gap_neg_km'), q2500=coef(paq, 'q2500'))
    A['tot'] = A['hg'] + A['ag']; pt = fit_poisson(A, rhs, 'tot'); ptq = fit_poisson(A, 'elo_diff100 + q2500 + C(comp)', 'tot')
    results['adjusted']['poisson_total_goals'] = dict(gap_pos_km=coef(pt, 'gap_pos_km'), q2500=coef(ptq, 'q2500'))
    # implied probability shift at 2,500 m for a typical qualifying match (evaluate at the mean covariates of Qacc)
    def probs(res, X): return res.model.predict(res.params, exog=X)
    Xq = gap_features(Qacc.assign(elo_diff=Qacc['elo_neutral_diff']))[['elo_diff100', 'gap_pos_km', 'gap_neg_km'] + comps]
    p_with = probs(o_cont, Xq); Xq0 = Xq.copy(); Xq0['gap_pos_km'] = 0.0; p_without = probs(o_cont, Xq0)
    results['adjusted']['implied_probabilities_in_qualifying_sample'] = dict(
        n=int(len(Qacc)), with_altitude=dict(A=round(float(p_with[:, 0].mean()), 3), D=round(float(p_with[:, 1].mean()), 3), H=round(float(p_with[:, 2].mean()), 3)),
        same_teams_no_altitude=dict(A=round(float(p_without[:, 0].mean()), 3), D=round(float(p_without[:, 1].mean()), 3), H=round(float(p_without[:, 2].mean()), 3)),
        actual=dict(A=round(float((Qacc['result'] == 'A').mean()), 3), D=round(float((Qacc['result'] == 'D').mean()), 3), H=round(float((Qacc['result'] == 'H').mean()), 3)),
        home_dnb_with=round(float((p_with[:, 2] / (p_with[:, 2] + p_with[:, 0])).mean()), 3), home_dnb_without=round(float((p_without[:, 2] / (p_without[:, 2] + p_without[:, 0])).mean()), 3))
    # bootstrap excess vs no-altitude expectation (ordered logit baseline WITHOUT gap terms, fitted on non-qualifying matches with neutral Elo)
    base = fit_ordered(A[A['net_gap'] <= 1500], ['elo_diff100'] + comps)
    Xq_base = gap_features(Qacc.assign(elo_diff=Qacc['elo_neutral_diff']))[['elo_diff100'] + comps]
    pb = probs(base, Xq_base)
    results['adjusted']['excess_vs_no_altitude_baseline'] = bootstrap_excess(Qacc, pb[:, 2], 3 * pb[:, 2] + pb[:, 1])
    # the same with PLAIN Elo (which already credits altitude wins to the club -> conservative)
    Ap = A.copy(); Ap['elo_diff'] = Ap['elo_plain_diff']; base_p = fit_ordered(Ap[Ap['net_gap'] <= 1500], ['elo_diff100'] + comps)
    Qp = Qacc.copy(); Qp['elo_diff'] = Qp['elo_plain_diff']; pbp = probs(base_p, gap_features(Qp)[['elo_diff100'] + comps])
    results['adjusted']['excess_vs_no_altitude_baseline_plain_elo'] = bootstrap_excess(Qp, pbp[:, 2], 3 * pbp[:, 2] + pbp[:, 1])
    # ---- fixed-effects Poisson (within-host identification)
    results['adjusted']['fixed_effects_poisson'] = fe_poisson(A)
    # ---- threshold robustness
    results['thresholds'] = {}
    for T in [1500, 2000, 2250, 2500, 2750, 3000, 3250, 3500]:
        A['qT'] = (A['net_gap'] > T).astype(float)
        Xt = gap_features(A)[['elo_diff100'] + comps].copy(); Xt['qT'] = A['qT']
        ot = OrderedModel(pd.Series(pd.Categorical(A['result'], categories=['A', 'D', 'H'], ordered=True), index=A.index), Xt, distr='logit').fit(method='bfgs', maxiter=400, disp=False)
        sub = A[A['qT'] == 1]
        results['thresholds'][str(T)] = dict(n=int(len(sub)), raw_home_win=round(float((sub['result'] == 'H').mean()), 3), raw_ppg=round(float(np.where(sub['result'] == 'H', 3, np.where(sub['result'] == 'D', 1, 0)).mean()), 3), ordered_logit_indicator=ocoef(ot, 'qT'))
    # ---- sensitivity: leave one league / host / competition type out
    results['sensitivity'] = {}
    def gap_effect(sub):
        cs = [c for c in gap_features(sub).columns if c.startswith('comp_')]
        r = fit_ordered(sub, ['elo_diff100', 'gap_pos_km'] + cs); return ocoef(r, 'gap_pos_km')
    for cc in LEAGUES:
        sub = A[A['home_cc'] != cc]; results['sensitivity'][f'drop_home_country_{cc}'] = dict(n=int(len(sub)), n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    for host in Qacc['home'].value_counts().head(10).index:
        sub = A[A['home'] != host]; results['sensitivity'][f'drop_host_{host}'] = dict(n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    for ct in ['league', 'continental']:
        sub = A[A['comp_type'] == ct]; results['sensitivity'][f'only_{ct}'] = dict(n=int(len(sub)), n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    for cc in LEAGUES:
        sub = A[A['home_cc'] == cc]
        if (sub['net_gap'] > THRESH).sum() >= 20:
            results['sensitivity'][f'only_home_country_{cc}'] = dict(n=int(len(sub)), n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    sub = A[A['season'] <= 2019]; results['sensitivity']['seasons_2015_2019'] = dict(n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    sub = A[A['season'] >= 2020]; results['sensitivity']['seasons_2020_2025'] = dict(n_qual=int((sub['net_gap'] > THRESH).sum()), gap_pos_km=gap_effect(sub))
    # ---- out-of-sample predictive test (train <=2020, test >=2021): baseline (Elo + comp) vs + altitude
    tr = A[A['season'] <= 2020]; te = A[A['season'] >= 2021]
    trp = tr.copy(); trp['elo_diff'] = trp['elo_plain_diff']; tep = te.copy(); tep['elo_diff'] = tep['elo_plain_diff']
    b0 = fit_ordered(trp, ['elo_diff100'] + comps); b1 = fit_ordered(trp, ['elo_diff100', 'gap_pos_km', 'gap_neg_km'] + comps)
    y = pd.Categorical(te['result'], categories=['A', 'D', 'H']).codes
    def scores(res, X):
        P = res.model.predict(res.params, exog=X); P = np.clip(P, 1e-6, 1); P = P / P.sum(1, keepdims=True)
        ll = -np.log(P[np.arange(len(y)), y]).mean(); Y = np.eye(3)[y]; brier = ((P - Y) ** 2).sum(1).mean(); return ll, brier, P
    ll0, br0, P0 = scores(b0, gap_features(tep)[['elo_diff100'] + comps]); ll1, br1, P1 = scores(b1, gap_features(tep)[['elo_diff100', 'gap_pos_km', 'gap_neg_km'] + comps])
    qmask = (te['net_gap'] > THRESH).values
    results['holdout'] = dict(train_seasons='2015-2020', test_seasons='2021-2025', n_test=int(len(te)), n_test_qualifying=int(qmask.sum()),
                              all_matches=dict(logloss_baseline=round(ll0, 4), logloss_altitude=round(ll1, 4), brier_baseline=round(br0, 4), brier_altitude=round(br1, 4)),
                              qualifying_matches=dict(logloss_baseline=round(float(-np.log(P0[qmask, y[qmask]]).mean()), 4), logloss_altitude=round(float(-np.log(P1[qmask, y[qmask]]).mean()), 4),
                                                      pred_home_baseline=round(float(P0[qmask, 2].mean()), 3), pred_home_altitude=round(float(P1[qmask, 2].mean()), 3), actual_home=round(float((y[qmask] == 2).mean()), 3),
                                                      pred_hd_baseline=round(float((P0[qmask, 1] + P0[qmask, 2]).mean()), 3), pred_hd_altitude=round(float((P1[qmask, 1] + P1[qmask, 2]).mean()), 3), actual_hd=round(float((y[qmask] != 0).mean()), 3)),
                              note='plain Elo (no altitude neutralisation) used here so the baseline is a realistic naive model; ordered logit on result')
    # calibration on holdout by gap bin
    te2 = te.assign(p0=P0[:, 2], p1=P1[:, 2], act=(te['result'] == 'H').astype(float)); te2['gb'] = pd.cut(te2['net_gap'], bins=bins).astype(str)
    results['holdout']['calibration_by_gap_bin'] = te2.groupby('gb').agg(n=('act', 'size'), actual_home=('act', 'mean'), pred_baseline=('p0', 'mean'), pred_altitude=('p1', 'mean')).round(3).reset_index().to_dict('records')
    # save match-level table for the odds backtest and appendix
    keep = ['match_id', 'comp', 'comp_type', 'season', 'Date', 'round', 'home', 'away', 'hg', 'ag', 'result', 'venue', 'venue_elev', 'venue_elev_basis', 'away_base_venue', 'away_base_elev', 'home_base_venue', 'home_base_elev', 'net_gap', 'home_gap', 'home_acclimatized', 'away_recent_alt', 'elo_plain_diff', 'elo_neutral_diff']
    an[keep].to_csv(os.path.join(OUT, 'matches_with_gap.csv'), index=False)
    Qacc[keep].to_csv(os.path.join(OUT, 'qualifying_matches.csv'), index=False)
    results['runtime_s'] = round(time.time() - t0)
    json.dump(results, open(os.path.join(OUT, 'club_backtest_results.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: results[k] for k in ['coverage', 'sample', 'elo']}, indent=1, default=str))
    print('raw qualifying by comp type:', json.dumps(results['raw']['qualifying_by_comp_type'], indent=1))
    print('adjusted ordered logit:', json.dumps(results['adjusted']['ordered_logit'], indent=1))
    print('excess:', results['adjusted']['excess_vs_no_altitude_baseline'], results['adjusted']['excess_vs_no_altitude_baseline_plain_elo'])
    print('FE:', json.dumps(results['adjusted']['fixed_effects_poisson'], indent=1))
    print('holdout:', json.dumps(results['holdout'], indent=1, default=str))

if __name__ == '__main__':
    main()
