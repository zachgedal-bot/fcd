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


def render_tables(df, lib, P):
    THR = THRESH
    cols = '| Date | Kickoff (America/Los_Angeles) | Competition | Home team | Away team | Confirmed venue | Venue elevation | Visitor baseline elevation and basis | Net gap | Known arrival/recent altitude exposure | Verification status | Sources |'
    sep = '|' + '---|' * 12
    def row(r):
        ve = f"{r.venue_elev:.0f} m ({r.venue_elev_basis})" if pd.notna(r.venue_elev) else 'unknown'
        vb = f"{r.visitor_base} — {r.visitor_base_elev:.0f} m ({r.visitor_base_basis})" if pd.notna(r.visitor_base_elev) else f"{r.visitor_base} — unknown"
        gap = f"{r.net_gap:.0f} m" if pd.notna(r.net_gap) else 'unknown'
        if pd.notna(r.net_gap) and abs(r.net_gap - THR) <= 150: gap += ' (borderline)'
        src = '; '.join(r.sources[:5]) if isinstance(r.sources, list) else str(r.sources)
        return f"| {r.date} | {r.kickoff_pt} | {r.competition} | {r.home} | {r.away} | {r.venue} | {ve} | {vb} | {gap} | {str(r.exposure)[:220]} | {r.status} (found by live search before the cut-off; not re-verified) | {src} |"
    md = []
    conf = df[(df['net_gap'] > THR) & df['status'].str.startswith('confirmed') & ~df['home'].str.contains('PROVISIONAL')]
    prov = df[((df['net_gap'] > THR) | df['net_gap'].isna()) & ~df.index.isin(conf.index)]
    excl = df[(df['net_gap'] <= THR)]
    for title, sub in [('Qualifying fixtures with a dated source (net gap > 2,500 m)', conf[conf['family'] != 'bolivia']), ('Bolivia: qualifying fixtures with a dated source', conf[conf['family'] == 'bolivia']), ('Provisional candidates', prov[prov['family'] != 'bolivia']), ('Bolivia: provisional candidates', prov[prov['family'] == 'bolivia']), ('Checked and excluded (net gap at or below 2,500 m)', excl)]:
        md.append(f'### {title}\n\n' + ('\n'.join([cols, sep] + [row(r) for r in sub.itertuples(index=False)]) if len(sub) else '_None located._') + '\n')
    open(os.path.join(OUT, 'watchlist_tables.md'), 'w').write('\n'.join(md))
    notes = ['### CONMEBOL knockout calendar (dates only; pairings not yet in the dataset)\n', 'From `openfootball/south-america` (auto-updated 2026-09-21), the 2026 Copa Libertadores lists semifinal match dates of Tue 13 Oct and Tue 20 Oct 2026 (legs in those weeks) and the final on Sat 28 Nov 2026; the round-of-16 and quarter-final pairings and results were not yet filled in the mirror, so which clubs remain, and whether a highland club (for example LDU de Quito, which reached the round of 16 against Mirassol) hosts a semifinal, could not be determined. A single-venue final makes both finalists visitors; it would not qualify. The 2026 Copa Sudamericana file was not present in the mirror.\n']
    for x in lib: notes.append(f"```\n{x['stage']}\n{x['text']}\n```\n")
    notes.append('\n### Structural pairing matrix for competitions whose 2026 schedules could not be retrieved\n\nPairs of host and visitor (both in the latest season of the data) whose usual venues differ by more than 2,350 m, with DEM elevations. Apply the official Peru Liga 1 Clausura, Ecuador LigaPro, Colombia Liga BetPlay 2026-II, Bolivia and Liga MX schedules to this table: a listed pair playing at the host\'s usual venue in the window is a qualifying fixture; a pair marked borderline needs a venue-level check. Clubs promoted for 2026 are absent, relegated clubs may still be listed (last season shown).\n')
    notes.append('| Country | Host | Host venue (DEM m) | Visitor | Visitor usual venue (DEM m) | Net gap | Status | Last season in data (host / visitor) |\n|---|---|---|---|---|---|---|---|')
    for r in P.itertuples(index=False):
        notes.append(f"| {r.country} | {r.host} | {r.host_venue} ({r.host_elev}) | {r.visitor} | {r.visitor_base} ({r.visitor_elev}) | {r.net_gap} | {r.status} | {r.host_last_season} / {r.visitor_last_season} |")
    open(os.path.join(OUT, 'watchlist_notes.md'), 'w').write('\n'.join(notes))

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
    render_tables(df, lib, P[(P['host_last_season'] >= 2025) & (P['visitor_last_season'] >= 2025)])
    print(df[['date', 'kickoff_pt', 'home', 'away', 'venue_elev', 'visitor_base_elev', 'net_gap', 'status', 'qualifies']].to_string(index=False))
    print(P.groupby(['country', 'status']).size())

if __name__ == '__main__':
    main()
