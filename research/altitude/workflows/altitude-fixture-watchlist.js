export const meta = {
  name: 'altitude-fixture-watchlist',
  description: 'Enumerate and verify upcoming (next 60 days) matches with a >2,500 m net elevation gap between venue and visitor base',
  phases: [
    { title: 'Enumerate', detail: 'one searcher per competition family' },
    { title: 'Verify', detail: 'independent re-check of each candidate fixture' },
  ],
}

const ENV = `
ENVIRONMENT NOTES (read carefully):
- Today is 2026-09-29 (Tuesday). The watch window is 2026-09-29 through 2026-11-28 inclusive.
- You are a research subagent; your final output is raw data for a script, not a message to a human.
- The ONLY working web tool is WebSearch. Load it first with ToolSearch query "select:WebSearch". WebFetch and curl are blocked for nearly every host (league sites, Wikipedia, ESPN, Flashscore, Sofascore, etc.), so do NOT try to fetch pages; run MANY targeted WebSearch queries (20-50 per task is normal), in Spanish AND English, and read the snippets/summaries carefully. Useful query shapes: "fixture <club> octubre 2026", "calendario <liga> fecha 12 2026", "<club> vs <club> 2026 estadio hora", "programación fecha <n> Clausura 2026 Liga 1", "<club> próximos partidos", "site:conmebol.com", "site:ligamx.net", "site:ligaprofesional.ec", "site:dimayor.com.co", "site:fbf.com.bo", "site:ligafutprof.gob.pe".
- Never invent a fixture, date, kickoff time, venue or elevation. If the kickoff time is not published, write "TBD". If you cannot confirm a fixture from at least one dated source, mark verification_status "unconfirmed". A candidate you cannot confirm is still worth listing as provisional with the reason.
- Elevation rule used by the parent research: net gap = actual match venue elevation minus the VISITING team's usual playing/training elevation; the primary filter is net gap > 2,500 m. Venues that qualify against near-sea-level visitors include: La Paz Hernando Siles (~3,600 m), El Alto Villa Ingenio (~4,080 m), Oruro Jesús Bermúdez (~3,700 m), Potosí Víctor Agustín Ugarte (~3,950 m), Sucre Olímpico Patria (~2,800 m), Cusco Inca Garcilaso (~3,400 m), Huancayo (~3,250 m), Juliaca (~3,825 m), Cajamarca (~2,750 m), Ayacucho (~2,750 m), Tarma (~3,050 m), Andahuaylas (~2,900 m), Quito Rodrigo Paz/Atahualpa/Gonzalo Pozo (~2,800-2,850 m), Mushuc Runa Echaleche (~3,000 m), Bogotá El Campín/Techo (~2,600 m), Tunja La Independencia (~2,800 m), Ipiales (~2,900 m), Toluca Nemesio Díez (~2,660 m). Borderline (within ~150 m of the threshold against sea-level visitors): Cochabamba (~2,560 m), Cuenca (~2,550 m), Ambato (~2,570 m), Pasto (~2,530 m), Sangolquí/IDV (~2,400-2,500 m), Pachuca (~2,430 m), Cutervo (~2,600 m). Visitors from Mexico City (~2,240 m), Bogotá, Medellín (~1,500 m), Cali (~1,000 m), Arequipa (~2,335 m), Tarija (~1,850 m), Cochabamba, Guadalajara (~1,560 m) etc. usually do NOT produce a >2,500 m gap; visitors from Guayaquil, Lima, the Peruvian coast, Santa Cruz de la Sierra, Trinidad, Riberalta, Yacuiba, Barranquilla, Cartagena, Santa Marta, Montería, Cúcuta, Valledupar, Tijuana, Mazatlán, Monterrey (~540 m, gap from Toluca only ~2,120 m so NO), Culiacán do. Report BOTH the venue elevation and the visitor's usual base so the parent script can compute the gap; do not pre-filter borderline cases out, just label them.
- Check for relocated matches, neutral grounds, temporary stadiums (e.g., clubs playing away from their normal city because of stadium works or sanctions), and postponements. Also verify the home team actually trains/plays at that altitude (e.g., a Lima-based club nominally 'hosting' in Cusco would NOT be acclimatized).
`

const CAND_SCHEMA = {
  type: 'object',
  properties: {
    fixtures: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          date_local: { type: 'string', description: 'YYYY-MM-DD in venue local date' },
          kickoff_local: { type: 'string', description: 'HH:MM 24h local time or TBD' },
          local_timezone: { type: 'string', description: 'IANA tz, e.g. America/La_Paz' },
          competition: { type: 'string' },
          round_or_stage: { type: 'string' },
          home_team: { type: 'string' },
          away_team: { type: 'string' },
          venue: { type: 'string' },
          venue_city: { type: 'string' },
          venue_elevation_m: { type: 'string', description: 'number with source or "unknown"' },
          home_team_usual_base: { type: 'string', description: 'city/stadium where the home team normally plays and trains; note if venue is not their usual ground' },
          away_team_usual_base: { type: 'string', description: 'city/stadium where the away team normally plays and trains' },
          away_base_elevation_m: { type: 'string', description: 'number with source or "unknown"' },
          relocation_or_neutral_notes: { type: 'string' },
          postponement_notes: { type: 'string' },
          known_arrival_or_recent_altitude_exposure: { type: 'string', description: 'e.g. away team played at altitude in the previous week, or "unknown"' },
          verification_status: { type: 'string', enum: ['confirmed_two_sources', 'confirmed_one_source', 'unconfirmed', 'date_confirmed_time_tbd'] },
          sources: { type: 'array', items: { type: 'string' } },
          borderline_flag: { type: 'boolean' },
          notes: { type: 'string' },
        },
        required: ['date_local', 'kickoff_local', 'local_timezone', 'competition', 'round_or_stage', 'home_team', 'away_team', 'venue', 'venue_city', 'venue_elevation_m', 'home_team_usual_base', 'away_team_usual_base', 'away_base_elevation_m', 'relocation_or_neutral_notes', 'postponement_notes', 'known_arrival_or_recent_altitude_exposure', 'verification_status', 'sources', 'borderline_flag', 'notes'],
      },
    },
    competition_status_notes: { type: 'string', description: 'format/stage of the competition in this window, which clubs are in the division this season, schedule-release conventions, anything that limits certainty' },
    club_identity_notes: { type: 'string', description: 'current names, divisions, stadiums, and any temporary venue arrangements of the relevant clubs' },
    search_log: { type: 'string' },
  },
  required: ['fixtures', 'competition_status_notes', 'club_identity_notes', 'search_log'],
}

const FAMILIES = [
  { key: 'liga_mx', prompt: `LIGA MX (Mexico) Apertura 2026 regular season (Jornadas through early/mid-November 2026) plus Play-In and Liguilla dates that fall before 2026-11-28. Home matches of Deportivo Toluca at Estadio Nemesio Díez (2,660 m). Which visitors are near sea level: Tijuana (Xolos), Mazatlán, Juárez? (1,140 m: NO), Monterrey/Tigres (~540 m: gap only ~2,120, NO), Santos Laguna (1,120 m NO). Also check Pachuca (Estadio Hidalgo ~2,430 m) home games vs Tijuana/Mazatlán as BORDERLINE (gap ~2,400 m) and note them with borderline_flag=true. Confirm Toluca's exact Apertura 2026 home schedule for Oct 1 - Nov 28, kickoff times (Mexico has no DST; UTC-6), and whether any match was moved (e.g., Estadio Azteca/2026 World Cup aftermath relocations of Mexico City clubs do not matter unless they visit Toluca). Also check Liga de Expansión MX only if a Toluca-based or Nemesio Díez-hosted match exists.` },
  { key: 'bolivia', prompt: `BOLIVIA División Profesional 2026 (all stages in the window, including any Copa/ playoff) plus any Copa Bolivia matches. Identify the 2026 top-flight clubs and their home venues: La Paz (Bolívar, The Strongest at Hernando Siles ~3,600 m; La Paz FC?), El Alto (Always Ready at Villa Ingenio ~4,080 m; any other El Alto club), Oruro (San José/GV San José at Jesús Bermúdez ~3,700 m), Potosí (Nacional Potosí, Real Potosí at Víctor Agustín Ugarte ~3,950 m - verify whether Real Potosí is currently in the top flight or the Copa Simón Bolívar), Sucre (Universitario de Sucre, Independiente Petrolero at Olímpico Patria ~2,800 m), Cochabamba (Wilstermann, Aurora at Félix Capriles ~2,560 m: borderline against sea-level visitors). Lowland visitors: Santa Cruz clubs (Oriente Petrolero, Blooming, Royal Pari, Real Santa Cruz, Guabirá of Montero, Sport Boys Warnes, San Antonio Bulo Bulo), Trinidad (Vaca Díez? Real Trinidad?), Riberalta, Yacuiba (Petrolero del Chaco), Tarija (Real Tomayapo, Ciclón: ~1,850 m so gap from La Paz ~1,750 = NO, from El Alto ~2,230 = NO, from Potosí ~2,100 = NO). List EVERY top-flight fixture in the window where a highland host (>2,500 m gap) receives a lowland visitor, with the published date/kickoff (Bolivia UTC-4). Note that Bolivian fixtures are often only firmed up 1-2 weeks ahead, so many will be date-only or TBD.` },
  { key: 'peru', prompt: `PERU Liga 1 2026 Torneo Clausura remaining rounds and the season play-offs/finals that fall before 2026-11-28. Highland hosts: Cusco FC and Cienciano and Deportivo Garcilaso (Cusco, Estadio Inca Garcilaso de la Vega ~3,400 m - check which clubs actually use it and whether any plays in Urcos or elsewhere), Sport Huancayo (Estadio Huancayo ~3,250 m), ADT (Tarma, Unión Tarma ~3,050 m), Los Chankas (Andahuaylas ~2,900 m), UTC (Cajamarca ~2,750 m), Ayacucho FC (Ciudad de Cumaná ~2,750 m; verify whether in Liga 1 in 2026), Binacional (Juliaca ~3,825 m; verify status), Comerciantes Unidos (Cutervo ~2,600 m: borderline), Alianza Universidad (Huánuco ~1,900 m: NO), Melgar (Arequipa ~2,335 m: NO). Lowland visitors: Lima/Callao clubs (Alianza Lima, Universitario, Sporting Cristal, Deportivo Municipal, Sport Boys, Cantolao, Universidad San Martín, Juan Pablo II if Lima-based, etc.), Trujillo (Carlos A. Mannucci, César Vallejo), Chiclayo (Juan Aurich), Sullana (Alianza Atlético), Piura (Atlético Grau), Moquegua? etc. List EVERY fixture in the window where a highland host receives a lowland visitor, with date and published kickoff (Peru UTC-5), venue, and any relocation (e.g., a club sanctioned to play elsewhere, or Garcilaso/Cusco using a different stadium).` },
  { key: 'ecuador', prompt: `ECUADOR LigaPro Serie A 2026 (second stage rounds and the hexagonal/cuadrangular phases before 2026-11-28) plus Copa Ecuador 2026 rounds in the window. Highland hosts: LDU Quito (Rodrigo Paz Delgado ~2,780 m), Aucas (Gonzalo Pozo Ripalda ~2,800 m), Universidad Católica and El Nacional (Olímpico Atahualpa ~2,780 m or wherever they play in 2026 - verify), Mushuc Runa (Estadio Echaleche, Píllaro ~3,000 m), Independiente del Valle (Sangolquí, Banco Guayaquil ~2,400-2,500 m: BORDERLINE, flag), Deportivo Cuenca (~2,550 m: borderline), Macará/Técnico Universitario (Ambato ~2,577 m: borderline), Cumbayá (~2,300 m: NO), Libertad (Loja ~2,060 m: NO), Orense? (Machala, lowland). Lowland visitors: Barcelona SC, Emelec, Guayaquil City (Guayaquil ~4 m), Delfín and Manta FC (Manta), Orense (Machala), Libertad? no, Vinotinto? (Quito-based? verify), Leones del Norte? etc. Verify the 2026 club list and stadiums. List EVERY fixture in the window where a highland host receives a lowland visitor (Ecuador UTC-5).` },
  { key: 'colombia', prompt: `COLOMBIA Liga BetPlay Dimayor 2026-II (Finalización: remaining all-play-all rounds and the cuadrangulares that start in November), Copa BetPlay 2026 rounds in the window, and Primera B (Torneo BetPlay) only for Tunja/Bogotá/Ipiales hosts. Highland hosts: Santa Fe and Millonarios (El Campín, Bogotá ~2,600 m), Fortaleza CEIF and La Equidad/Internacional de Bogotá (Techo ~2,600 m; verify current club names and venues in 2026), Boyacá Chicó and Patriotas (Tunja, La Independencia ~2,800 m), Deportivo Pasto (Departamental Libertad ~2,530 m: BORDERLINE vs sea-level; Ipiales ~2,900 m if used), Once Caldas (Manizales ~2,150 m: NO), Águilas (Rionegro ~2,125 m: NO). Lowland visitors: Junior (Barranquilla), Unión Magdalena (Santa Marta), Real Cartagena, Jaguares (Montería), Alianza FC (Valledupar ~170 m: from Bogotá the gap is ~2,430 = NO but from Tunja ~2,650 = YES), Cúcuta Deportivo (~320 m: from Bogotá NO, from Tunja borderline ~2,500), Alianza Petrolera/Barrancabermeja (~75 m: from Bogotá ~2,525 borderline-yes), Llaneros (Villavicencio ~470 m: NO), Atlético Huila (Neiva ~440 m: NO), Boyacá? no. Verify the 2026-II club list and each club's 2026 venue. List EVERY fixture in the window where a highland host receives a lowland visitor (Colombia UTC-5).` },
  { key: 'conmebol_clubs', prompt: `CONMEBOL club competitions in the window: Copa Libertadores 2026 semifinals (October) and final (late November - verify the date and the host city/stadium and its elevation), Copa Sudamericana 2026 semifinals and final (verify date/venue), and any CONMEBOL women's Copa Libertadores 2026 matches at altitude. Identify which clubs are still alive in each competition as of 2026-09-29 and whether any semifinal leg is hosted at altitude (La Paz, El Alto, Quito, Bogotá, Cusco, Toluca not eligible (CONCACAF)) against a lowland visitor. Also check whether the 2026 finals are at a neutral high-altitude venue (that would make BOTH teams visitors - note that explicitly, it would not qualify as a home team with altitude advantage).` },
  { key: 'national_teams_and_other', prompt: `(A) NATIONAL TEAMS in the FIFA windows 5-13 October 2026 and 9-17 November 2026 (post-World Cup friendlies and any CONMEBOL/CONCACAF competitive matches): does Bolivia host in La Paz or El Alto, Ecuador in Quito, Colombia in Bogotá, Peru in Cusco, Mexico in Toluca? Identify opponents and their usual base elevation (e.g., a national team is 'based' where its players play; label the basis). Keep these clearly labelled as national-team fixtures. (B) OTHER LEAGUES WORLDWIDE with venues that could produce a >2,500 m gap: Bolivian Copa Simón Bolívar (second tier) if hosted in Potosí/Oruro/La Paz vs lowland clubs, Peru Liga 2 highland hosts (e.g., Cusco, Huancayo second teams), Ecuador Serie B (e.g., Quito/Ambato hosts), Colombia Primera B (Tunja, Bogotá, Ipiales hosts vs coastal clubs), Mexico Liga de Expansión (Toluca-area hosts?), Ethiopia (Addis Ababa ~2,355 m: NO unless visitor near sea level AND venue >2,500 m - check Bahir Dar/Addis venues), China (any Lhasa-based club in professional tiers), Guatemala (Xelajú ~2,330 m: NO), Bhutan/Nepal/Kenya/Rwanda (NO if <2,500 m gap). Report only what you can verify; say explicitly which of these produce no qualifying fixture.` },
]

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    fixture_id: { type: 'string' },
    exists: { type: 'string', enum: ['confirmed', 'likely', 'not_found', 'contradicted'] },
    corrected_date_local: { type: 'string' },
    corrected_kickoff_local: { type: 'string', description: 'HH:MM local or TBD' },
    corrected_venue: { type: 'string' },
    corrected_competition_round: { type: 'string' },
    venue_elevation_m_with_source: { type: 'string' },
    away_base_elevation_m_with_source: { type: 'string' },
    home_team_acclimatized: { type: 'string', description: 'yes/no/unclear and why (does the home team normally train and play at this venue elevation?)' },
    relocation_or_postponement: { type: 'string' },
    recent_altitude_exposure_of_visitor: { type: 'string', description: 'visitor matches at >2,000 m in the prior 14 days if findable, else unknown' },
    verification_status: { type: 'string', enum: ['confirmed_two_sources', 'confirmed_one_source', 'unconfirmed', 'date_confirmed_time_tbd', 'contradicted'] },
    sources: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['fixture_id', 'exists', 'corrected_date_local', 'corrected_kickoff_local', 'corrected_venue', 'corrected_competition_round', 'venue_elevation_m_with_source', 'away_base_elevation_m_with_source', 'home_team_acclimatized', 'relocation_or_postponement', 'recent_altitude_exposure_of_visitor', 'verification_status', 'sources', 'notes'],
}

phase('Enumerate')
log(`Launching ${FAMILIES.length} fixture enumerators`)
const enumerated = await parallel(FAMILIES.map(f => () =>
  agent(`${ENV}\nCOMPETITION FAMILY: ${f.key}\n${f.prompt}\nReturn every candidate fixture in the window (2026-09-29 to 2026-11-28) with the fields requested. Include fixtures whose date is known but time is not (kickoff_local = "TBD"). Include borderline cases with borderline_flag=true. Do not include fixtures outside the window.`,
    { label: `enumerate:${f.key}`, phase: 'Enumerate', schema: CAND_SCHEMA })
))

const candidates = []
enumerated.forEach((r, i) => {
  if (!r) return
  for (const f of (r.fixtures || [])) candidates.push({ ...f, family: FAMILIES[i].key, fixture_id: `${FAMILIES[i].key}|${f.date_local}|${f.home_team}|${f.away_team}` })
})
const familyNotes = enumerated.map((r, i) => ({ family: FAMILIES[i].key, competition_status_notes: r ? r.competition_status_notes : 'agent failed', club_identity_notes: r ? r.club_identity_notes : '', search_log: r ? r.search_log : '' }))
const seen = new Set(); const uniqueCands = []
for (const c of candidates) { const k = `${c.date_local}|${(c.home_team || '').toLowerCase()}|${(c.away_team || '').toLowerCase()}`; if (seen.has(k)) continue; seen.add(k); uniqueCands.push(c) }
log(`Enumerated ${candidates.length} candidates (${uniqueCands.length} unique); verifying each independently`)

phase('Verify')
const verified = await pipeline(uniqueCands,
  c => agent(`${ENV}\nINDEPENDENT VERIFICATION of one candidate fixture reported by another agent:\n${JSON.stringify(c, null, 2)}\nRe-derive from scratch with your own WebSearch queries (Spanish and English; official league/club sites, major sports media such as ESPN, Marca, Ovación, El Comercio, Depor, Líbero, El Universo, Primicias, El Tiempo, Futbolred, Gol Caracol, La Razón, El Deber, Diez.bo, Mediotiempo, Récord) whether this fixture exists on that date, its kickoff time (local; TBD if not published), the confirmed venue (watch for relocations, neutral venues, closed stadiums, sanctions), the venue elevation and the away team's usual base elevation (with the source for each), whether the home team really trains/plays at that altitude, and any recent altitude exposure of the visitor. Mark 'contradicted' if sources disagree with the candidate's date/venue in a way that changes qualification.`,
    { label: `verify:${c.home_team} v ${c.away_team} ${c.date_local}`, phase: 'Verify', schema: VERIFY_SCHEMA })
    .then(v => ({ candidate: c, verification: v }))
)

return { fixtures: verified.filter(Boolean), familyNotes, counts: { candidates: candidates.length, unique: uniqueCands.length } }
