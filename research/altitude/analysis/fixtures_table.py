"""Build the verified watchlist table from the fixture workflow output (output/fixtures_workflow.json).
Kickoffs converted to America/Los_Angeles with the correct DST offset per date (PDT until 2026-11-01 02:00, then PST).
"""
import os, sys, json, re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import OUT, REG
THRESH = 2500.0
WINDOW = ('2026-09-29', '2026-11-28')

def num(s):
    if s is None: return None
    m = re.search(r'(-?\d[\d,\.]*)', str(s).replace(',', ''))
    try: return float(m.group(1)) if m else None
    except Exception: return None

def to_pt(date_local, kick_local, tz):
    if not kick_local or kick_local.upper() == 'TBD' or not re.match(r'^\d{1,2}:\d{2}', kick_local): return 'TBD'
    try:
        dt = datetime.strptime(f'{date_local} {kick_local[:5]}', '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo(tz))
        pt = dt.astimezone(ZoneInfo('America/Los_Angeles'))
        return pt.strftime('%Y-%m-%d %H:%M ') + pt.tzname()
    except Exception as e:
        return f'TBD (unparsed: {kick_local})'

def main():
    fx = json.load(open(os.path.join(OUT, 'fixtures_workflow.json')))
    rows = []
    for item in fx['fixtures']:
        c = item['candidate']; v = item.get('verification') or {}
        date = v.get('corrected_date_local') or c['date_local']; kick = v.get('corrected_kickoff_local') or c['kickoff_local']
        venue = v.get('corrected_venue') or c['venue']
        ve = num(v.get('venue_elevation_m_with_source')) or num(c.get('venue_elevation_m'))
        ab = num(v.get('away_base_elevation_m_with_source')) or num(c.get('away_base_elevation_m'))
        gap = (ve - ab) if (ve is not None and ab is not None) else None
        status = v.get('verification_status') or c.get('verification_status')
        exists = v.get('exists', 'unknown')
        rows.append(dict(date=date, kickoff_pt=to_pt(date, kick, c['local_timezone']), kickoff_local=f"{kick} ({c['local_timezone']})", competition=f"{c['competition']} — {v.get('corrected_competition_round') or c['round_or_stage']}",
                         home=c['home_team'], away=c['away_team'], venue=venue, venue_elev=ve, visitor_base=f"{c['away_team_usual_base']} — {v.get('away_base_elevation_m_with_source') or c['away_base_elevation_m']}",
                         visitor_base_elev=ab, net_gap=gap, exposure=v.get('recent_altitude_exposure_of_visitor') or c['known_arrival_or_recent_altitude_exposure'], status=status, exists=exists,
                         home_acclimatized=v.get('home_team_acclimatized', ''), relocation=v.get('relocation_or_postponement') or c['relocation_or_neutral_notes'], sources=sorted(set((c.get('sources') or []) + (v.get('sources') or []))),
                         family=c['family'], borderline=bool(c.get('borderline_flag')) or (gap is not None and abs(gap - THRESH) <= 150), notes=(v.get('notes') or '') + ' | ' + (c.get('notes') or '')))
    df = pd.DataFrame(rows)
    df = df[(df['date'] >= WINDOW[0]) & (df['date'] <= WINDOW[1])].sort_values(['date', 'kickoff_pt'])
    df['qualifies'] = (df['net_gap'] > THRESH) & (~df['exists'].isin(['not_found', 'contradicted']))
    df.to_csv(os.path.join(OUT, 'watchlist_all_candidates.csv'), index=False)
    def table(sub):
        lines = ['| Date | Kickoff (America/Los_Angeles) | Competition | Home team | Away team | Confirmed venue | Venue elevation | Visitor baseline elevation and basis | Net gap | Known arrival/recent altitude exposure | Verification status | Sources |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
        for r in sub.itertuples(index=False):
            src = '; '.join(r.sources[:4]) if isinstance(r.sources, list) else ''
            ve = f'{r.venue_elev:.0f} m' if pd.notna(r.venue_elev) else 'unknown'; gap = f'{r.net_gap:.0f} m' if pd.notna(r.net_gap) else 'unknown'
            lines.append(f'| {r.date} | {r.kickoff_pt} | {r.competition} | {r.home} | {r.away} | {r.venue} | {ve} | {r.visitor_base} | {gap}{" (borderline)" if r.borderline else ""} | {r.exposure} | {r.status}; exists={r.exists}; home acclimatized: {r.home_acclimatized} | {src} |')
        return '\n'.join(lines)
    conf = df[df['qualifies'] & df['status'].isin(['confirmed_two_sources', 'confirmed_one_source', 'date_confirmed_time_tbd']) & ~df['borderline']]
    prov = df[(df['qualifies'] & (df['status'].isin(['unconfirmed']) | df['borderline'])) | ((df['net_gap'].isna()) & ~df['exists'].isin(['not_found', 'contradicted']))]
    below = df[(df['net_gap'] <= THRESH) & df['net_gap'].notna()]
    md = []
    for title, sub in [('Confirmed qualifying fixtures (net gap > 2,500 m, home side acclimatized, date verified)', conf[conf['family'] != 'bolivia']), ('Bolivia: confirmed qualifying fixtures', conf[conf['family'] == 'bolivia']),
                       ('Provisional candidates (unconfirmed date/venue, missing elevation, or borderline within 150 m of the threshold)', prov[prov['family'] != 'bolivia']), ('Bolivia: provisional candidates', prov[prov['family'] == 'bolivia']),
                       ('Checked and excluded (net gap at or below 2,500 m)', below)]:
        md.append(f'### {title}\n\n' + (table(sub) if len(sub) else '_None found._') + '\n')
    open(os.path.join(OUT, 'watchlist_tables.md'), 'w').write('\n'.join(md))
    print(f'candidates {len(df)}, confirmed {len(conf)}, provisional {len(prov)}, excluded {len(below)}')

if __name__ == '__main__':
    main()
