"""Assemble the watchlist from (a) fixtures the enumerator agents found with live web search before the
session's search budget was exhausted, (b) the openfootball 2026 Copa Libertadores schedule (dates only),
and (c) a structural pairing matrix of qualifying host/visitor pairs per competition built from the DEM registry.
No fixture is invented: entries without a dated source are labelled provisional or structural.
"""
import os, sys, json, re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, REG, RAW, load_registry
THRESH = 2500.0

def to_pt(date_local, kick_local, tz):
    if not kick_local or str(kick_local).upper().startswith('TBD') or not re.match(r'^\d{1,2}:\d{2}', str(kick_local)): return 'TBD'
    dt = datetime.strptime(f'{date_local} {kick_local[:5]}', '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo(tz))
    pt = dt.astimezone(ZoneInfo('America/Los_Angeles')); return pt.strftime('%Y-%m-%d %H:%M ') + pt.tzname()

def num(s):
    m = re.search(r'(\d[\d,]*)', str(s).replace('≈', '').replace('~', ''))
    return float(m.group(1).replace(',', '')) if m else None

def main():
    reg = load_registry(); lut = reg.set_index('venue_fbref_name')['elev'].to_dict()
    sal = json.load(open(os.path.join(OUT, 'salvaged', 'workflow_partial_results.json')))
    rows = []
    VEN = {'Estadio Nemesio Díez': 'Estadio Nemesio Díez', 'Estadio Hernando Siles': 'Estadio Hernando Siles', 'Estadio Jesús Bermúdez': 'Estadio Jesús Bermúdez'}
    BASE = {'Club Tijuana (Xolos)': 'Estadio Caliente', 'Atlético de San Luis': 'Estadio Alfonso Lastras Ramírez', 'CF Monterrey (Rayados)': 'Estadio BBVA Bancomer', 'Blooming': 'Estadio Ramón Aguilera Costas', 'Guabirá': 'Estadio Gilberto Parada'}
    for r in sal['fixtures']:
        for f in r.get('fixtures', []):
            vkey = next((k for k in VEN if k in f['venue']), None); ve = lut.get(VEN.get(vkey)) if vkey else None
            bkey = BASE.get(f['away_team']); ab = lut.get(bkey) if bkey else None
            if ve is None: ve = num(f['venue_elevation_m'])
            if ab is None: ab = num(f['away_base_elevation_m'])
            gap = ve - ab if (ve is not None and ab is not None) else None
            rows.append(dict(date=f['date_local'], kickoff_pt=to_pt(f['date_local'], f['kickoff_local'], f['local_timezone']), kickoff_local=f"{f['kickoff_local']} {f['local_timezone']}", competition=f"{f['competition']} — {f['round_or_stage']}", home=f['home_team'], away=f['away_team'],
                             venue=f['venue'], venue_elev=ve, venue_elev_basis=('DEM registry' if (vkey and VEN.get(vkey) in lut) else 'agent-reported'), visitor_base=f['away_team_usual_base'], visitor_base_elev=ab, visitor_base_basis=('DEM registry, usual home stadium (proxy for training elevation)' if (bkey in lut) else 'agent-reported'),
                             net_gap=gap, exposure=f['known_arrival_or_recent_altitude_exposure'], status=f['verification_status'], relocation=f['relocation_or_neutral_notes'], postponement=f['postponement_notes'], sources=f['sources'], notes=f['notes'], family=r['label'].replace('enumerate:', ''), borderline=bool(f.get('borderline_flag'))))
    df = pd.DataFrame(rows)
    df['qualifies'] = df['net_gap'] > THRESH
    df.to_csv(os.path.join(OUT, 'watchlist_salvaged.csv'), index=False)
    # Copa Libertadores 2026 knockout dates from openfootball (pairings not filled in the mirror)
    lib = []
    p = '/home/user/openfootball/south-america/copa-libertadores/2026_copal.txt'
    if os.path.exists(p):
        txt = open(p).read()
        for stage, pat in [('Semifinals', r'▪ Finals, Semifinals\n((?:.*\n){0,6})'), ('Final', r'▪ Finals, Final\n((?:.*\n){0,3})')]:
            m = re.search(pat, txt)
            if m: lib.append(dict(stage=stage, text=m.group(1).strip()))
    json.dump(dict(salvaged=rows, libertadores_2026_openfootball=lib), open(os.path.join(OUT, 'watchlist_assembled.json'), 'w'), ensure_ascii=False, indent=1)
    # structural pairing matrix: qualifying host venues vs lowland visitor bases (from 2025 principal venues + DEM registry)
    pv = pd.concat([pd.read_csv(os.path.join(RAW, f'{c}_club_principal_venue_by_season.csv')).assign(country=c) for c in ['MEX', 'PER', 'ECU', 'COL', 'BOL']])
    latest = pv.sort_values('Season_End_Year').groupby(['country', 'Home']).tail(1).copy()
    latest['elev'] = latest['Venue'].map(lut)
    latest = latest[latest['elev'].notna()]
    pairs = []
    for c, g in latest.groupby('country'):
        for h in g.itertuples(index=False):
            for a in g.itertuples(index=False):
                if h.Home == a.Home: continue
                gap = h.elev - a.elev
                if gap > THRESH - 150:
                    pairs.append(dict(country=c, host=h.Home, host_venue=h.Venue, host_elev=round(h.elev), visitor=a.Home, visitor_base=a.Venue, visitor_elev=round(a.elev), net_gap=round(gap), status=('qualifies' if gap > THRESH else 'borderline'), host_last_season=int(h.Season_End_Year), visitor_last_season=int(a.Season_End_Year)))
    P = pd.DataFrame(pairs).sort_values(['country', 'net_gap'], ascending=[True, False])
    P.to_csv(os.path.join(OUT, 'structural_pairing_matrix.csv'), index=False)
    print(df[['date', 'kickoff_pt', 'home', 'away', 'venue_elev', 'visitor_base_elev', 'net_gap', 'status', 'qualifies']].to_string(index=False))
    print(P.groupby(['country', 'status']).size())

if __name__ == '__main__':
    main()
