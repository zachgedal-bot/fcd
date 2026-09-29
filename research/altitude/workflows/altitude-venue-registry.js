export const meta = {
  name: 'altitude-venue-registry',
  description: 'Find coordinates and reported elevations for every venue in the match dataset, verify against SRTM DEM, and research club training bases',
  phases: [
    { title: 'Locate', detail: 'venue batches, national-team stadiums, club training grounds' },
    { title: 'Recheck', detail: 'venues whose DEM elevation disagrees with the reported one' },
  ],
}

const ENV = [
  'ENVIRONMENT NOTES (read carefully):',
  '- Today is 2026-09-29. You are a research subagent; your final output is raw data for a script, not a message to a human.',
  '- Web: the ONLY working web tool is WebSearch (load it with ToolSearch query "select:WebSearch"). WebFetch/curl are blocked for Wikipedia, Google Maps, OSM and most sites, so do not try to fetch pages. Run many targeted WebSearch queries; stadium coordinates usually appear in Wikipedia/Wikidata/OSM/latitude.to/mapcarta snippets (search "<stadium> coordinates", "<stadium> latitud longitud", "<stadium> wikidata"). Elevations appear in Wikipedia stadium/city articles ("altitud", "msnm", "metros sobre el nivel del mar").',
  '- You have Bash. A DEM lookup tool exists: run   python3 /home/user/fcd/research/altitude/tools/dem_elev.py LAT LON   (decimal degrees; south and west are NEGATIVE). It prints the SRTM 1-arc-second terrain elevation at that point (from the public AWS Terrain Tiles dataset) and the min/max within ~150 m. Use it for EVERY venue to validate your coordinates: if the DEM elevation disagrees with the reported/expected elevation by more than ~80 m, your coordinates are probably wrong (wrong sign, wrong city, wrong stadium) - search again. Report both the reported elevation (with source) and the DEM elevation. For a stadium the DEM is the authoritative geographic value; the reported figure is secondary.',
  '- The dataset venue names come from FBref and are sometimes truncated with "..." or slightly wrong; resolve them to the real stadium using the home teams listed (e.g. "Estadio de la Universidad Nacional San A..." used by Cusco clubs = Estadio Universitario UNSAAC, Cusco). If a venue name is clearly a data error (e.g. a European stadium listed for a Colombian club), say so in notes and still give your best resolution or mark unresolvable.',
  '- Never invent coordinates or elevations. If you cannot find coordinates, set lat/lon to null and confidence "low".',
  '- Data files you can read with Bash: /home/user/fcd/research/altitude/data/raw/venues_to_research.json (fields: country, venue_fbref_name, matches, seasons, main_home_teams) and /home/user/fcd/research/altitude/data/raw/team_venue_inventory.json.',
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
          dem_elevation_m: { type: ['number', 'null'], description: 'output of dem_elev.py nearest value' },
          dem_window_min_max: { type: 'string' },
          agreement_note: { type: 'string', description: 'reported vs DEM difference and what you did about it' },
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

const TRAINING_SCHEMA = {
  type: 'object',
  properties: {
    clubs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          country: { type: 'string' },
          club_fbref_name: { type: 'string' },
          club_full_name: { type: 'string' },
          home_city: { type: 'string' },
          usual_home_stadium: { type: 'string' },
          training_ground: { type: 'string' },
          training_city: { type: 'string' },
          training_lat: { type: ['number', 'null'] },
          training_lon: { type: ['number', 'null'] },
          training_dem_elevation_m: { type: ['number', 'null'] },
          training_elevation_basis: { type: 'string', enum: ['training_ground_confirmed', 'same_city_as_stadium_assumed', 'not_found'] },
          notable_relocations: { type: 'string', description: 'seasons in which the club played home matches away from its usual city/elevation and why' },
          source_urls: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['country', 'club_fbref_name', 'club_full_name', 'home_city', 'usual_home_stadium', 'training_ground', 'training_city', 'training_lat', 'training_lon', 'training_dem_elevation_m', 'training_elevation_basis', 'notable_relocations', 'source_urls', 'confidence'],
      },
    },
    search_log: { type: 'string' },
  },
  required: ['clubs', 'search_log'],
}

const BATCHES = [
  { key: 'BOL', country: 'BOL', start: 0, end: 29 },
  { key: 'COL-a', country: 'COL', start: 0, end: 19 },
  { key: 'COL-b', country: 'COL', start: 19, end: 38 },
  { key: 'ECU-a', country: 'ECU', start: 0, end: 19 },
  { key: 'ECU-b', country: 'ECU', start: 19, end: 38 },
  { key: 'MEX', country: 'MEX', start: 0, end: 30 },
  { key: 'PER-a', country: 'PER', start: 0, end: 18 },
  { key: 'PER-b', country: 'PER', start: 18, end: 36 },
  { key: 'PER-c', country: 'PER', start: 36, end: 52 },
]

const NT_LISTS = [
  { key: 'nt-hosts', prompt: 'National-team HOST stadiums used since 1990 in these cities (give the main stadium(s) used for senior men internationals in each, with coordinates, reported elevation and DEM elevation): Bolivia: La Paz (Hernando Siles), El Alto (Villa Ingenio), Santa Cruz (Ramon Tahuichi Aguilera), Cochabamba (Felix Capriles), Sucre (Olimpico Patria), Oruro, Potosi. Colombia: Barranquilla (Metropolitano), Bogota (El Campin), Medellin (Atanasio Girardot), Cali (Pascual Guerrero), Pereira, Armenia, Manizales. Ecuador: Quito (Olimpico Atahualpa, Rodrigo Paz Delgado), Guayaquil (Monumental, George Capwell), Cuenca, Ambato, Portoviejo, Machala. Mexico: Mexico City (Azteca), Guadalajara/Zapopan (Akron, Jalisco), Monterrey/Guadalupe (BBVA, Universitario), Puebla, Torreon, Queretaro, San Luis Potosi, Toluca, Tuxtla Gutierrez, Veracruz. Peru: Lima (Nacional, Monumental), Arequipa (UNSA), Tacna, Chiclayo, Trujillo, Piura, Cusco. Use venue_fbref_name = "NT:<City>" and canonical_name = the stadium.' },
  { key: 'nt-visitors', prompt: 'Usual HOME stadiums of visiting national teams (proxy for their baseline elevation), with coordinates, reported elevation and DEM elevation: Argentina (Buenos Aires Monumental; Cordoba; Mendoza), Brazil (Rio Maracana; Sao Paulo; Porto Alegre), Chile (Santiago Nacional), Uruguay (Montevideo Centenario), Paraguay (Asuncion Defensores del Chaco), Venezuela (San Cristobal Pueblo Nuevo; Maracaibo; Caracas), Peru (Lima Nacional), Colombia (Barranquilla Metropolitano), Ecuador (Quito Atahualpa; Guayaquil), Bolivia (La Paz Hernando Siles), Mexico (Azteca), United States (no single home - give Foxborough, Washington DC, Chicago), Canada (Toronto BMO), Costa Rica (San Jose Nacional), Honduras (San Pedro Sula Olimpico; Tegucigalpa), Panama (Panama City Rommel Fernandez), Jamaica (Kingston National), El Salvador (San Salvador Cuscatlan), Guatemala (Guatemala City Doroteo Guamuch), Trinidad and Tobago (Port of Spain Hasely Crawford), Haiti (Port-au-Prince Sylvio Cator), Cuba (Havana Pedro Marrero), Nicaragua (Managua), Curacao (Willemstad Ergilio Hato), Suriname (Paramaribo Andre Kamperveen). Use venue_fbref_name = "NTV:<Country>:<City>" and canonical_name = the stadium.' },
]

const COUNTRIES = ['MEX', 'PER', 'ECU', 'COL', 'BOL']

function batchPrompt(b) {
  return ENV + '\nTASK: resolve venues for batch ' + b.key + '. Read the input with Bash:\n  python3 -c "import json,sys; v=[x for x in json.load(open(\'/home/user/fcd/research/altitude/data/raw/venues_to_research.json\')) if x[\'country\']==\'' + b.country + '\']; json.dump(v[' + b.start + ':' + b.end + '], sys.stdout, ensure_ascii=False, indent=1)"\nFor EACH of those venues (all of them, none skipped) find canonical name, city, coordinates, reported elevation with source, run the DEM tool, and report. Work venue by venue; keep a log.'
}
function trainingPrompt(c) {
  return ENV + '\nTASK: club training bases for ' + c + '. Read the club list with Bash:\n  python3 -c "import json; d=json.load(open(\'/home/user/fcd/research/altitude/data/raw/team_venue_inventory.json\'))[\'' + c + '\']; print(d[\'teams\'])"\nFor EACH club in that list (top flight, seasons 2014-2025): full name, home city, usual home stadium, the TRAINING GROUND (name, city, coordinates if findable, DEM elevation via the tool), whether the training elevation is confirmed or merely assumed equal to the stadium city, and seasons in which the club played its home matches somewhere other than its usual city/elevation (relocations, sanctions, stadium works, temporary grounds) with the reason. Search in Spanish ("complejo deportivo", "ciudad deportiva", "sede de entrenamiento", "campo de entrenamiento") and English. Never invent; use "not_found" where unknown.'
}

phase('Locate')
log('Launching ' + BATCHES.length + ' venue batches, 2 national-team stadium lists, ' + COUNTRIES.length + ' training-ground researchers')
const results = await parallel([
  ...BATCHES.map(b => () => agent(batchPrompt(b), { label: 'venues:' + b.key, phase: 'Locate', schema: VENUE_SCHEMA })),
  ...NT_LISTS.map(n => () => agent(ENV + '\nTASK (' + n.key + '): ' + n.prompt + '\nFor EACH stadium: coordinates, reported elevation with source, and the DEM elevation from the tool. Set country to a short code of the stadium country.', { label: n.key, phase: 'Locate', schema: VENUE_SCHEMA })),
  ...COUNTRIES.map(c => () => agent(trainingPrompt(c), { label: 'training:' + c, phase: 'Locate', schema: TRAINING_SCHEMA })),
])

const venueAgents = results.slice(0, BATCHES.length + NT_LISTS.length).filter(Boolean)
const trainingAgents = results.slice(BATCHES.length + NT_LISTS.length).filter(Boolean)
const venues = venueAgents.flatMap(r => r.venues || [])
const clubs = trainingAgents.flatMap(r => r.clubs || [])
log('Located ' + venues.length + ' venues and ' + clubs.length + ' clubs')

const flagged = venues.filter(v => v.lat == null || v.lon == null || v.dem_elevation_m == null || v.confidence === 'low' || (v.reported_elevation_m != null && v.dem_elevation_m != null && Math.abs(v.reported_elevation_m - v.dem_elevation_m) > 80))
log(flagged.length + ' venues flagged for recheck (missing coordinates, low confidence, or >80 m disagreement)')

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
    resolution: { type: 'string', description: 'what was wrong before and what you now believe, with evidence' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['venue_fbref_name', 'canonical_name', 'city', 'lat', 'lon', 'coordinate_source', 'reported_elevation_m', 'elevation_source', 'dem_elevation_m', 'resolution', 'confidence'],
}
const rechecked = await pipeline(flagged,
  v => agent(ENV + '\nRECHECK TASK. A previous agent produced this venue record, which was flagged because coordinates are missing, confidence is low, or the DEM elevation disagrees with the reported elevation by more than 80 m:\n' + JSON.stringify(v, null, 2) + '\nIndependently re-derive the stadium identity and coordinates (try alternative names, the club Wikipedia article, Wikidata, OSM, mapcarta/latitude.to), run the DEM tool again, and explain which value is right. Remember that a real stadium sits on ground the DEM measures; a Wikipedia "elevation" may be the city nominal figure rather than the stadium. If the venue is a genuine data error in the source (impossible venue for that club), say so.',
    { label: 'recheck:' + v.venue_fbref_name, phase: 'Recheck', schema: RECHECK_SCHEMA })
)

return { venues, clubs, rechecked: rechecked.filter(Boolean), flaggedCount: flagged.length }
