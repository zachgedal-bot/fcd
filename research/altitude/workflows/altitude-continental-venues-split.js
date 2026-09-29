export const meta = {
  name: 'altitude-continental-venues-split',
  description: 'Coordinates and DEM elevations for Copa Libertadores/Sudamericana venues outside the domestic registry (mostly lowland South America)',
  phases: [
    { title: 'Locate', detail: 'six batches of continental venues' },
    { title: 'Recheck', detail: 'flagged venues' },
  ],
}

const ENV = [
  'ENVIRONMENT NOTES (read carefully):',
  '- Today is 2026-09-29. You are a research subagent; your final output is raw data for a script, not a message to a human.',
  '- Web: NO web access is available in this session (the WebSearch budget is exhausted and WebFetch/curl are blocked). Do not call WebSearch or WebFetch. Identify stadiums and coordinates from your own knowledge and VALIDATE every coordinate with the DEM tool; state in coordinate_source that coordinates come from model recall. Give the commonly published elevation from memory when confident, otherwise null.',
  '- You have Bash. A DEM lookup tool exists: run   python3 /home/user/fcd/research/altitude/tools/dem_elev.py LAT LON   (decimal degrees; south and west are NEGATIVE). It prints the SRTM 1-arc-second terrain elevation at that point (public AWS Terrain Tiles) and the min/max within ~150 m. Use it for EVERY venue to validate coordinates: if the DEM disagrees with the expected elevation by more than ~80 m (or a coastal stadium shows hundreds of metres), your coordinates are wrong - search again. Report both the reported elevation (with source, or null if none published) and the DEM elevation.',
  '- Venue names come from FBref and are sometimes truncated with "..." or contain "(Neutral Site)"; resolve them using the home teams listed. Country codes: ar Argentina, br Brazil, cl Chile, py Paraguay, uy Uruguay, ve Venezuela, co Colombia, ec Ecuador, pe Peru, bo Bolivia.',
  '- Never invent coordinates or elevations. If you cannot find coordinates, set lat/lon to null and confidence "low".',
  '- Input file: /home/user/fcd/research/altitude/data/raw/continental_venues_to_research.json (fields: country (home country codes), venue_fbref_name, matches, seasons, main_home_teams).',
].join('\n')

const VENUE_SCHEMA = {
  type: 'object',
  properties: {
    venues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          country: { type: 'string' },
          venue_fbref_name: { type: 'string', description: 'exactly as in the input file' },
          canonical_name: { type: 'string' },
          city: { type: 'string' },
          lat: { type: ['number', 'null'] },
          lon: { type: ['number', 'null'] },
          coordinate_source: { type: 'string' },
          reported_elevation_m: { type: ['number', 'null'] },
          elevation_source: { type: 'string' },
          dem_elevation_m: { type: ['number', 'null'] },
          dem_window_min_max: { type: 'string' },
          agreement_note: { type: 'string' },
          notes: { type: 'string' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['country', 'venue_fbref_name', 'canonical_name', 'city', 'lat', 'lon', 'coordinate_source', 'reported_elevation_m', 'elevation_source', 'dem_elevation_m', 'dem_window_min_max', 'agreement_note', 'notes', 'confidence'],
      },
    },
    search_log: { type: 'string' },
  },
  required: ['venues', 'search_log'],
}

const N = 139
const SIZE = 24
const ALL = []
for (let s = 0; s < N; s += SIZE) ALL.push({ key: 'cont-' + (s / SIZE + 1), start: s, end: Math.min(s + SIZE, N) })
const BATCHES = ALL.filter(b => ((args && args.batches) || []).includes(b.key))

function batchPrompt(b) {
  return ENV + '\nTASK: resolve venues for batch ' + b.key + '. Read the input with Bash:\n  python3 -c "import json,sys; v=json.load(open(\'/home/user/fcd/research/altitude/data/raw/continental_venues_to_research.json\')); json.dump(v[' + b.start + ':' + b.end + '], sys.stdout, ensure_ascii=False, indent=1)"\nFor EACH venue in the slice (all of them) find canonical name, city, coordinates, reported elevation with source (null if not published), run the DEM tool, and report.'
}

phase('Locate')
log('Launching ' + BATCHES.length + ' continental venue batches')
const results = await parallel(BATCHES.map(b => () => agent(batchPrompt(b), { label: 'venues:' + b.key, phase: 'Locate', schema: VENUE_SCHEMA })))
const venues = results.filter(Boolean).flatMap(r => r.venues || [])
log('Located ' + venues.length + ' venues')
const flagged = venues.filter(v => v.lat == null || v.lon == null || v.dem_elevation_m == null || v.confidence === 'low' || (v.reported_elevation_m != null && v.dem_elevation_m != null && Math.abs(v.reported_elevation_m - v.dem_elevation_m) > 80))
log(flagged.length + ' venues flagged for recheck')

phase('Recheck')
const RECHECK_SCHEMA = {
  type: 'object',
  properties: {
    venue_fbref_name: { type: 'string' },
    canonical_name: { type: 'string' },
    city: { type: 'string' },
    lat: { type: ['number', 'null'] },
    lon: { type: ['number', 'null'] },
    coordinate_source: { type: 'string' },
    reported_elevation_m: { type: ['number', 'null'] },
    elevation_source: { type: 'string' },
    dem_elevation_m: { type: ['number', 'null'] },
    resolution: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['venue_fbref_name', 'canonical_name', 'city', 'lat', 'lon', 'coordinate_source', 'reported_elevation_m', 'elevation_source', 'dem_elevation_m', 'resolution', 'confidence'],
}
const rechecked = await pipeline(flagged,
  v => agent(ENV + '\nRECHECK TASK. This venue record was flagged (missing coordinates, low confidence, or >80 m DEM disagreement):\n' + JSON.stringify(v, null, 2) + '\nIndependently re-derive the stadium identity and coordinates, run the DEM tool again, and explain which value is right.',
    { label: 'recheck:' + v.venue_fbref_name, phase: 'Recheck', schema: RECHECK_SCHEMA })
)
return { venues, rechecked: rechecked.filter(Boolean), flaggedCount: flagged.length }
