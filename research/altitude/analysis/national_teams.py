"""National-team altitude analysis, kept separate from club evidence.
Data: martj42/international_results (results.csv, goalscorers.csv). Scores are full-time including extra time,
so knockout matches that could have had extra time are excluded when an extra-time goal or shootout is recorded.
Visitor baseline = the visiting nation's usual home stadium elevation (a PROXY: many players are club-based abroad).
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
import statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RAW, REG, OUT
warnings.filterwarnings('ignore')
THRESH = 2500.0
START = '1990-01-01'

def main():
    r = pd.read_csv(os.path.join(RAW, 'international_results.csv')); r['date'] = pd.to_datetime(r['date'])
    gs = pd.read_csv(os.path.join(RAW, 'international_goalscorers.csv')); gs['date'] = pd.to_datetime(gs['date'])
    so = pd.read_csv(os.path.join(RAW, 'international_shootouts.csv')); so['date'] = pd.to_datetime(so['date'])
    reg = pd.read_csv(os.path.join(REG, 'venue_registry.csv'))
    reg['elev'] = reg['dem_elevation_m'].where(reg['dem_elevation_m'].notna(), reg['reported_elevation_m'])
    host = reg[reg['venue_fbref_name'].str.startswith('NT:')].copy(); host['city'] = host['venue_fbref_name'].str.replace('NT:', '', regex=False)
    host_elev = host.groupby('city')['elev'].mean().to_dict()
    vis = reg[reg['venue_fbref_name'].str.startswith('NTV:')].copy(); vis['nation'] = vis['venue_fbref_name'].str.split(':').str[1]; vis['city'] = vis['venue_fbref_name'].str.split(':').str[2]
    # visitor baseline: modal home city per nation (from results) -> registry elevation; fallback: mean over the nation's listed stadiums
    r = r[r['date'] >= START].copy()
    home_city = r[~r['neutral']].groupby(['home_team', 'city']).size().reset_index(name='n').sort_values('n', ascending=False).groupby('home_team').head(1).set_index('home_team')['city'].to_dict()
    vis_lut = {}
    for nation, g in vis.groupby('nation'):
        c = home_city.get(nation); row = g[g['city'] == c]
        vis_lut[nation] = float(row['elev'].iloc[0]) if len(row) else float(g['elev'].mean())
    city_elev = {**host_elev, **vis.set_index('city')['elev'].to_dict()}
    r['venue_elev'] = r['city'].map(city_elev)
    r['away_base_elev'] = r['away_team'].map(vis_lut); r['home_base_elev'] = r['home_team'].map(vis_lut)
    r['net_gap'] = r['venue_elev'] - r['away_base_elev']; r['home_gap'] = r['venue_elev'] - r['home_base_elev']
    r['result'] = np.select([r['home_score'] > r['away_score'], r['home_score'] == r['away_score']], ['H', 'D'], 'A')
    # extra time / shootout exclusion
    et_dates = set(zip(gs[gs['minute'] > 90]['date'], gs[gs['minute'] > 90]['home_team'], gs[gs['minute'] > 90]['away_team']))
    so_keys = set(zip(so['date'], so['home_team'], so['away_team']))
    r['et_or_so'] = [((d, h, a) in et_dates) or ((d, h, a) in so_keys) for d, h, a in zip(r['date'], r['home_team'], r['away_team'])]
    # Elo (World Football Elo style) over all internationals since 1980 for pre-match strength
    allr = pd.read_csv(os.path.join(RAW, 'international_results.csv')); allr['date'] = pd.to_datetime(allr['date']); allr = allr[allr['date'] >= '1980-01-01'].sort_values('date').reset_index(drop=True)
    def kfac(t):
        t = str(t)
        if 'FIFA World Cup' in t and 'qual' not in t: return 60
        if 'Copa América' in t or 'European Championship' in t or 'Gold Cup' in t or 'Asian Cup' in t or 'African Cup' in t or 'Confederations' in t: return 50
        if 'qualification' in t or 'Nations League' in t: return 40
        if 'Friendly' in t: return 20
        return 30
    R = {}; pre_h = np.empty(len(allr)); pre_a = np.empty(len(allr))
    for i, x in enumerate(allr.itertuples(index=False)):
        rh, ra = R.get(x.home_team, 1500.0), R.get(x.away_team, 1500.0); pre_h[i], pre_a[i] = rh, ra
        hfa = 0 if x.neutral else 100
        e = 1 / (1 + 10 ** (-(rh + hfa - ra) / 400)); s = 1.0 if x.home_score > x.away_score else (0.5 if x.home_score == x.away_score else 0.0)
        gd = abs(x.home_score - x.away_score); g = 1 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
        delta = kfac(x.tournament) * g * (s - e); R[x.home_team] = rh + delta; R[x.away_team] = ra - delta
    allr['elo_h'] = pre_h; allr['elo_a'] = pre_a
    r = r.merge(allr[['date', 'home_team', 'away_team', 'elo_h', 'elo_a']], on=['date', 'home_team', 'away_team'], how='left')
    r['elo_diff100'] = (r['elo_h'] - r['elo_a']) / 100
    base = r[(~r['neutral']) & r['net_gap'].notna() & (~r['et_or_so'])].copy()
    base['competitive'] = ~base['tournament'].str.contains('Friendly')
    out = {'coverage': dict(matches_since_1990_in_five_countries=int(len(r)), with_gap=int(len(base)), host_cities_with_elev=sorted(host_elev.keys()), visitor_nations_with_baseline=len(vis_lut))}
    def raw(df):
        n = len(df)
        if n == 0: return dict(n=0)
        return dict(n=int(n), home_win=round(float((df['result'] == 'H').mean()), 3), draw=round(float((df['result'] == 'D').mean()), 3), away_win=round(float((df['result'] == 'A').mean()), 3), unbeaten=round(float((df['result'] != 'A').mean()), 3),
                    gd=round(float((df['home_score'] - df['away_score']).mean()), 3), hg=round(float(df['home_score'].mean()), 3), ag=round(float(df['away_score'].mean()), 3), total=round(float((df['home_score'] + df['away_score']).mean()), 3))
    Q = base[(base['net_gap'] > THRESH) & (base['home_gap'].abs() <= 600)]
    Qall = base[(base['net_gap'] > THRESH)]
    out['raw'] = dict(qualifying_all=raw(Q), qualifying_without_host_acclimatization_filter=raw(Qall), qualifying_without_filter_by_home={k: raw(g) for k, g in Qall.groupby('home_team')},
                      qualifying_by_era={k: raw(g) for k, g in Q.groupby(np.where(Q['date'] < '2008-01-01', '1990-2007', '2008-2026'))}, qualifying_competitive=raw(Q[Q['competitive']]), qualifying_friendly=raw(Q[~Q['competitive']]),
                      qualifying_by_home=({k: raw(g) for k, g in Q.groupby('home_team')}), qualifying_by_city={k: raw(g) for k, g in Q.groupby('city')},
                      same_hosts_low_gap=raw(base[(base['home_team'].isin(Q['home_team'].unique())) & (base['net_gap'].abs() <= 500)]),
                      same_hosts_competitive_low_gap=raw(base[(base['home_team'].isin(Q['home_team'].unique())) & (base['net_gap'].abs() <= 500) & base['competitive']]),
                      by_gap_bin={str(k): raw(g) for k, g in base.groupby(pd.cut(base['net_gap'], [-9999, -2500, -1500, -500, 500, 1500, 2500, 3500, 9999]), observed=True)})
    # adjusted: ordered logit with Elo diff, competitive flag, and gap
    A = base[base['elo_diff100'].notna() & (base['home_gap'].abs() <= 600)].copy()
    A['gap_pos_km'] = A['net_gap'].clip(lower=0) / 1000; A['gap_neg_km'] = (-A['net_gap'].clip(upper=0)) / 1000; A['q2500'] = (A['net_gap'] > THRESH).astype(float); A['comp'] = A['competitive'].astype(float)
    y = pd.Series(pd.Categorical(A['result'], categories=['A', 'D', 'H'], ordered=True), index=A.index)
    def oc(res, k): b = float(res.params[k]); se = float(res.bse[k]); return dict(coef=round(b, 4), se=round(se, 4), ci=[round(b - 1.96 * se, 4), round(b + 1.96 * se, 4)], p=round(float(res.pvalues[k]), 4))
    o1 = OrderedModel(y, A[['elo_diff100', 'comp', 'gap_pos_km', 'gap_neg_km']], distr='logit').fit(method='bfgs', maxiter=400, disp=False)
    o2 = OrderedModel(y, A[['elo_diff100', 'comp', 'q2500']], distr='logit').fit(method='bfgs', maxiter=400, disp=False)
    out['adjusted'] = dict(n=int(len(A)), ordered_logit=dict(elo_diff100=oc(o1, 'elo_diff100'), gap_pos_km=oc(o1, 'gap_pos_km'), gap_neg_km=oc(o1, 'gap_neg_km'), q2500=oc(o2, 'q2500')),
                           note='Elo computed from all internationals since 1980 with 100-point home advantage; the home nation Elo already embeds its altitude wins, so the gap coefficient is conservative')
    for tgt in ['home_score', 'away_score']:
        p = sm.GLM(A[tgt], sm.add_constant(A[['elo_diff100', 'comp', 'gap_pos_km', 'gap_neg_km']]), family=sm.families.Poisson()).fit()
        out['adjusted'][f'poisson_{tgt}'] = dict(gap_pos_km=oc(p, 'gap_pos_km'), gap_neg_km=oc(p, 'gap_neg_km'))
    # goal timing (secondary): share of goals after 75' and by half, qualifying vs low-gap matches of the same hosts
    g2 = gs[gs['date'] >= START].merge(base[['date', 'home_team', 'away_team', 'net_gap', 'competitive']], on=['date', 'home_team', 'away_team'])
    g2 = g2[g2['minute'].notna() & (g2['minute'] <= 90)]
    g2['scored_by_home'] = g2['team'] == g2['home_team']; g2['late'] = g2['minute'] > 75; g2['second_half'] = g2['minute'] > 45
    def timing(df):
        n = len(df)
        if n == 0: return dict(goals=0)
        h = df[df['scored_by_home']]; a = df[~df['scored_by_home']]
        return dict(goals=int(n), home_goals=int(len(h)), away_goals=int(len(a)), home_share_1st_half=round(float((~h['second_half']).mean()), 3) if len(h) else None, home_share_2nd_half=round(float(h['second_half'].mean()), 3) if len(h) else None,
                    away_share_2nd_half=round(float(a['second_half'].mean()), 3) if len(a) else None, home_share_after_75=round(float(h['late'].mean()), 3) if len(h) else None, away_share_after_75=round(float(a['late'].mean()), 3) if len(a) else None)
    out['goal_timing'] = dict(qualifying=timing(g2[g2['net_gap'] > THRESH]), low_gap_same_hosts=timing(g2[(g2['net_gap'].abs() <= 500) & (g2['home_team'].isin(Q['home_team'].unique()))]), all_five_countries=timing(g2),
                              note='Secondary analysis; goal minutes from martj42 goalscorers.csv; shares are of each side own goals scored')
    Q.to_csv(os.path.join(OUT, 'national_team_qualifying_matches.csv'), index=False)
    json.dump(out, open(os.path.join(OUT, 'national_team_results.json'), 'w'), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:5000])

if __name__ == '__main__':
    main()
