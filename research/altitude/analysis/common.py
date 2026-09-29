"""Shared loaders for the altitude study.
Data: FBref match results mirrored by worldfootballR_data (domestic leagues MEX/PER/ECU/COL/BOL 2014-2025,
Copa Libertadores 2014-2025, Copa Sudamericana 2014-2024), plus the venue/club elevation registry built by
research agents and verified against SRTM (AWS Terrain Tiles).
"""
import os, re, json
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
REG = os.path.join(ROOT, 'data', 'registry')
OUT = os.path.join(ROOT, 'output')
os.makedirs(REG, exist_ok=True); os.makedirs(OUT, exist_ok=True)

LEAGUES = ['MEX', 'PER', 'ECU', 'COL', 'BOL']
CUPS = {'LIB': 'Copa Libertadores', 'SUD': 'Copa Sudamericana'}
CC_TO_LEAGUE = {'mx': 'MEX', 'pe': 'PER', 'ec': 'ECU', 'co': 'COL', 'bo': 'BOL'}

def strip_cc(name):
    if not isinstance(name, str):
        return name
    name = re.sub(r'\s[a-z]{2}$', '', name)
    name = re.sub(r'^[a-z]{2}\s', '', name)
    return name.strip()

def load_matches():
    """Unified completed-match table."""
    frames = []
    for lg in LEAGUES:
        df = pd.read_csv(os.path.join(RAW, f'{lg}_fbref_completed.csv'))
        df['comp'] = lg; df['comp_type'] = 'league'; df['home_cc'] = lg; df['away_cc'] = lg
        frames.append(df)
    for code in CUPS:
        df = pd.read_csv(os.path.join(RAW, f'{code}_fbref_completed.csv'))
        df['comp'] = code; df['comp_type'] = 'continental'
        df['home_cc'] = df['home_cc'].map(CC_TO_LEAGUE).fillna(df['home_cc'].str.upper())
        df['away_cc'] = df['away_cc'].map(CC_TO_LEAGUE).fillna(df['away_cc'].str.upper())
        df['Home'] = df['Home_clean']; df['Away'] = df['Away_clean']
        frames.append(df)
    m = pd.concat(frames, ignore_index=True, sort=False)
    m['Date'] = pd.to_datetime(m['Date'])
    m = m.rename(columns={'Season_End_Year': 'season', 'Home': 'home', 'Away': 'away', 'HomeGoals': 'hg', 'AwayGoals': 'ag', 'Venue': 'venue', 'Round': 'round', 'Notes': 'notes'})
    m['venue'] = m['venue'].fillna('').astype(str)
    m['notes'] = m['notes'].fillna('').astype(str)
    m['extra_time'] = m['notes'].str.contains('extra time', case=False)
    m['penalties'] = m['notes'].str.contains('penalt', case=False)
    m['neutral_flag'] = m['venue'].str.contains(r'\(Neutral Site\)', regex=True)
    m['hg'] = m['hg'].astype(int); m['ag'] = m['ag'].astype(int)
    m['result'] = np.select([m['hg'] > m['ag'], m['hg'] == m['ag']], ['H', 'D'], 'A')
    m['season'] = m['season'].astype(int)
    m = m.sort_values(['Date', 'comp']).reset_index(drop=True)
    m['match_id'] = np.arange(len(m))
    return m

def load_registry():
    """Venue registry: venue_fbref_name -> elevation (DEM primary, reported fallback)."""
    reg = pd.read_csv(os.path.join(REG, 'venue_registry.csv'))
    reg['elev'] = reg['dem_elevation_m'].where(reg['dem_elevation_m'].notna(), reg['reported_elevation_m'])
    reg['elev_basis'] = np.where(reg['dem_elevation_m'].notna(), 'DEM', np.where(reg['reported_elevation_m'].notna(), 'reported', 'missing'))
    return reg

def attach_elevations(m, reg):
    """Add venue elevation and each side's baseline (usual home venue that season, labelled proxy)."""
    lut = reg.set_index('venue_fbref_name')['elev'].to_dict()
    basis = reg.set_index('venue_fbref_name')['elev_basis'].to_dict()
    conf = reg.set_index('venue_fbref_name')['confidence'].to_dict()
    m['venue_elev'] = m['venue'].map(lut)
    m['venue_elev_basis'] = m['venue'].map(basis)
    m['venue_conf'] = m['venue'].map(conf)
    # principal (modal) home venue per club-season across all competitions, and its elevation
    home_rows = m[m['venue'] != ''].copy()
    home_rows['venue_elev'] = home_rows['venue'].map(lut)
    def modal_venue(s):
        vc = s.value_counts(); return vc.index[0]
    pv = home_rows.groupby(['home', 'home_cc', 'season'])['venue'].agg(modal_venue).reset_index().rename(columns={'venue': 'principal_venue', 'home': 'team', 'home_cc': 'cc'})
    pv['principal_elev'] = pv['principal_venue'].map(lut)
    # fallback for a club-season without home rows in our data: nearest other season of the same club
    key = pv.set_index(['team', 'cc', 'season'])
    def lookup(team, cc, season):
        try:
            r = key.loc[(team, cc, season)]
            return r['principal_venue'], r['principal_elev']
        except KeyError:
            sub = pv[(pv['team'] == team) & (pv['cc'] == cc)]
            if len(sub) == 0:
                return None, np.nan
            sub = sub.iloc[(sub['season'] - season).abs().argsort()]
            return sub.iloc[0]['principal_venue'], sub.iloc[0]['principal_elev']
    hb = [lookup(t, c, s) for t, c, s in zip(m['home'], m['home_cc'], m['season'])]
    ab = [lookup(t, c, s) for t, c, s in zip(m['away'], m['away_cc'], m['season'])]
    m['home_base_venue'] = [x[0] for x in hb]; m['home_base_elev'] = [x[1] for x in hb]
    m['away_base_venue'] = [x[0] for x in ab]; m['away_base_elev'] = [x[1] for x in ab]
    m['net_gap'] = m['venue_elev'] - m['away_base_elev']
    m['home_gap'] = m['venue_elev'] - m['home_base_elev']   # how far the home side is from ITS usual elevation
    m['home_acclimatized'] = m['home_gap'].abs() <= 500
    return m, pv

def add_recent_exposure(m, min_elev=2000, days=14):
    """Did the visitor (or home side) play at >= min_elev within the previous `days` days (any competition in the data)?"""
    long = pd.concat([
        m[['match_id', 'Date', 'home', 'home_cc', 'venue_elev']].rename(columns={'home': 'team', 'home_cc': 'cc'}),
        m[['match_id', 'Date', 'away', 'away_cc', 'venue_elev']].rename(columns={'away': 'team', 'away_cc': 'cc'}),
    ]).sort_values('Date')
    long['at_alt'] = long['venue_elev'] >= min_elev
    exp = {}
    for (team, cc), g in long.groupby(['team', 'cc']):
        dates = g['Date'].values; alt = g['at_alt'].values; mids = g['match_id'].values
        for i in range(len(g)):
            lo = dates[i] - np.timedelta64(days, 'D')
            mask = (dates < dates[i]) & (dates >= lo) & alt
            exp[(team, cc, mids[i])] = bool(mask.any())
    m['away_recent_alt'] = [exp.get((t, c, i), False) for t, c, i in zip(m['away'], m['away_cc'], m['match_id'])]
    m['home_recent_alt'] = [exp.get((t, c, i), False) for t, c, i in zip(m['home'], m['home_cc'], m['match_id'])]
    return m

def elo_ratings(m, k=20, hfa=70.0, gap_coef=0.0, start=1500.0):
    """Pre-match Elo for every match (chronological, all competitions pooled).
    Expected score uses league/continental home advantage `hfa` (Elo points) plus an altitude term
    gap_coef * max(net_gap,0)/1000 (Elo points per 1,000 m of positive net gap). gap_coef=0 gives a plain Elo;
    a non-zero value gives an 'altitude-neutral' rating in which altitude wins are partly credited to the venue,
    not to the club's strength. Goal-margin multiplier as in World Football Elo."""
    R = {}
    pre_h, pre_a, exp_h = np.empty(len(m)), np.empty(len(m)), np.empty(len(m))
    gaps = m['net_gap'].fillna(0).clip(lower=0).values / 1000.0
    for i, (h, a, hg, ag, hc, ac) in enumerate(zip(m['home'].values, m['away'].values, m['hg'].values, m['ag'].values, m['home_cc'].values, m['away_cc'].values)):
        kh, ka = (h, hc), (a, ac)
        rh, ra = R.get(kh, start), R.get(ka, start)
        pre_h[i], pre_a[i] = rh, ra
        dr = rh + hfa + gap_coef * gaps[i] - ra
        e = 1.0 / (1.0 + 10 ** (-dr / 400.0)); exp_h[i] = e
        s = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        gd = abs(hg - ag); g = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8.0)
        delta = k * g * (s - e)
        R[kh] = rh + delta; R[ka] = ra - delta
    m['elo_h'], m['elo_a'], m['elo_exp_h'] = pre_h, pre_a, exp_h
    m['elo_diff'] = m['elo_h'] - m['elo_a']
    return m

def result_probs_from_elo(elo_diff_with_hfa, draw_scale=0.28):
    """Not used for inference; kept for reference."""
    raise NotImplementedError
