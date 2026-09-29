"""Merge the venue-registry workflow outputs (recall-based identification + SRTM DEM checks + rechecks) with the
provisional analyst registry into data/registry/venue_registry.csv, keeping every candidate in a long-form file.
Rule: a record is 'DEM-consistent' when the DEM elevation is within 80 m of the published figure (or no published
figure exists and confidence is not low). Preference order: recheck (if DEM-consistent) > batch record (if DEM-consistent)
> provisional analyst coordinates (if DEM-consistent with the batch record's published figure) > best available with flag.
"""
import os, sys, json, glob
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REG, RAW
WF = '/root/.claude/projects/-home-user-fcd/cacd5560-8166-516b-9c45-bff66f5c1d5a/subagents/workflows'
RUNS = ['wf_3975905a-6df', 'wf_07f80511-6be']

def load_journal(run):
    lab = {}; venues = []; clubs = []; rechecks = []
    for line in open(os.path.join(WF, run, 'journal.jsonl')):
        e = json.loads(line)
        if e.get('type') == 'started': lab[e['key']] = e.get('label', '')
        if e.get('type') == 'result' and isinstance(e.get('result'), dict):
            r = e['result']; l = lab.get(e['key'], '')
            if 'venues' in r: venues += [dict(v, agent=l) for v in r['venues']]
            if 'clubs' in r: clubs += [dict(c, agent=l) for c in r['clubs']]
            if l.startswith('recheck:') and 'venue_fbref_name' in r: rechecks.append(dict(r, agent=l))
    return venues, clubs, rechecks

def consistent(rec):
    d, rep = rec.get('dem_elevation_m'), rec.get('reported_elevation_m')
    if d is None or (isinstance(d, float) and np.isnan(d)): return False
    if rep is None or (isinstance(rep, float) and np.isnan(rep)): return rec.get('confidence') != 'low'
    return abs(float(d) - float(rep)) <= 80

def main():
    venues, clubs, rechecks = [], [], []
    for run in RUNS:
        v, c, r = load_journal(run); venues += v; clubs += c; rechecks += r
    prov = pd.read_csv(os.path.join(REG, 'venue_registry_provisional.csv'))
    prov_lut = prov.set_index('venue_fbref_name').to_dict('index')
    cands = []
    for v in venues: cands.append(dict(v, source_kind='batch'))
    for r in rechecks: cands.append(dict(r, source_kind='recheck'))
    for name, p in prov_lut.items(): cands.append(dict(venue_fbref_name=name, canonical_name=name, city='', lat=p['lat'], lon=p['lon'], reported_elevation_m=None, dem_elevation_m=p['dem_elevation_m'], confidence='provisional', coordinate_source='analyst provisional coordinates', elevation_source='', source_kind='provisional', country=p['country']))
    C = pd.DataFrame(cands)
    C.to_csv(os.path.join(REG, 'venue_registry_candidates.csv'), index=False)
    out = []
    for name, g in C.groupby('venue_fbref_name'):
        recs = g.to_dict('records')
        batch = [r for r in recs if r['source_kind'] == 'batch']; rc = [r for r in recs if r['source_kind'] == 'recheck']; pv = [r for r in recs if r['source_kind'] == 'provisional']
        chosen, basis = None, ''
        for r in rc:
            if consistent(r) and r.get('confidence') != 'low': chosen, basis = r, 'recheck agent (DEM-consistent)'; break
        if chosen is None:
            for r in batch:
                if consistent(r): chosen, basis = r, 'batch agent (DEM-consistent)'; break
        if chosen is None and pv and batch:
            rep = batch[0].get('reported_elevation_m')
            if rep is not None and not (isinstance(rep, float) and np.isnan(rep)) and abs(float(pv[0]['dem_elevation_m']) - float(rep)) <= 80:
                chosen = dict(batch[0]); chosen.update(lat=pv[0]['lat'], lon=pv[0]['lon'], dem_elevation_m=pv[0]['dem_elevation_m'], coordinate_source='analyst provisional coordinates (agent coordinates were DEM-inconsistent)'); basis = 'provisional coordinates, agent published figure (DEM-consistent)'
        if chosen is None:
            pool = rc + batch + pv
            pool = [r for r in pool if r.get('dem_elevation_m') is not None and not (isinstance(r.get('dem_elevation_m'), float) and np.isnan(r.get('dem_elevation_m')))]
            if pool: chosen, basis = pool[0], 'best available (NOT DEM-consistent or low confidence) - flagged'
        if chosen is None: continue
        rep = chosen.get('reported_elevation_m'); dem = chosen.get('dem_elevation_m')
        out.append(dict(country=chosen.get('country', ''), venue_fbref_name=name, canonical_name=chosen.get('canonical_name', ''), city=chosen.get('city', ''), lat=chosen.get('lat'), lon=chosen.get('lon'), dem_elevation_m=dem, reported_elevation_m=rep,
                        elevation_source=chosen.get('elevation_source', ''), coordinate_source=chosen.get('coordinate_source', ''), confidence=chosen.get('confidence', ''), basis=basis, n_candidates=len(recs),
                        dem_minus_reported=(None if rep is None or (isinstance(rep, float) and np.isnan(rep)) or dem is None else round(float(dem) - float(rep))), notes=str(chosen.get('notes', chosen.get('resolution', '')))[:300]))
    R = pd.DataFrame(out)
    R.to_csv(os.path.join(REG, 'venue_registry.csv'), index=False)
    pd.DataFrame(clubs).to_csv(os.path.join(REG, 'club_training_bases.csv'), index=False)
    print('venues in registry:', len(R), '| flagged:', int(R['basis'].str.contains('flagged').sum()), '| by basis:', R['basis'].value_counts().to_dict())
    print('clubs with training info:', len(clubs))
    need = set(json.load(open(os.path.join(RAW, 'venues_to_research.json')))[i]['venue_fbref_name'] for i in range(len(json.load(open(os.path.join(RAW, 'venues_to_research.json'))))))
    need |= set(x['venue_fbref_name'] for x in json.load(open(os.path.join(RAW, 'continental_venues_to_research.json'))))
    missing = sorted(need - set(R['venue_fbref_name']))
    print('venues still missing:', len(missing), missing[:40])

if __name__ == '__main__':
    main()
