export const meta = {
  name: 'altitude-science-review',
  description: 'Literature sweep (EN+ES) on altitude and soccer performance, adversarial verification of each study, then synthesis',
  phases: [
    { title: 'Find', detail: 'nine lenses, English and Spanish' },
    { title: 'Verify', detail: 'two independent checkers per study' },
    { title: 'Synthesize', detail: 'evidence table and narrative' },
  ],
}

const ENV = `
ENVIRONMENT NOTES (read carefully):
- Today is 2026-09-29. You are a research subagent; your final output is raw data for a script, not a message to a human.
- The ONLY working web tool is WebSearch. Load it first with ToolSearch query "select:WebSearch". WebFetch and curl are blocked for nearly every host (Wikipedia, PubMed, journals, Google Scholar, etc.), so do NOT try to fetch pages; instead run MANY targeted WebSearch queries (15-40 per task is normal) and read the result snippets/summaries carefully. Quote-search exact titles to confirm bibliographic details. Use site: filters (site:pubmed.ncbi.nlm.nih.gov, site:scielo.org, site:researchgate.net, site:bjsm.bmj.com, site:onlinelibrary.wiley.com, site:journals.humankinetics.com, site:tandfonline.com, site:dialnet.unirioja.es, site:redalyc.org) when useful.
- Never invent a study, number, author, or URL. If a detail cannot be confirmed from search results, write "not confirmed" for that field and lower confidence. A result you could not find is a valid result.
- Distinguish: professional club match evidence, national-team match evidence, field/training-camp studies, laboratory studies, reviews/consensus statements, and non-peer-reviewed analyses (blogs, student papers). Report each study's population, sample size, altitude range, measured effect (with numbers if available), uncertainty (CI/p-values/effect sizes if reported), and limitations. Flag any extrapolation beyond the studied conditions.
- Context of the parent research question: a bettor wants to know whether backing HOME teams whose match venue is more than 2,500 m above the VISITING team's usual playing/training elevation carries value beyond ordinary home advantage and market prices. Altitude bands of interest: 2,500-4,100 m venues (Mexico Toluca 2,660 m; Bogotá 2,600 m; Quito 2,800 m; Cusco 3,400 m; Huancayo 3,250 m; La Paz 3,600 m; El Alto 4,080 m; Potosí 3,960 m) with visitors from near sea level, plus the moderate-altitude literature (1,200-2,300 m) that is often extrapolated to these venues.
`

const STUDY_SCHEMA = {
  type: 'object',
  properties: {
    studies: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string', description: 'short unique key like firstauthor_year_topic' },
          title: { type: 'string' },
          authors: { type: 'string' },
          year: { type: 'integer' },
          published_in: { type: 'string' },
          language: { type: 'string' },
          study_type: { type: 'string', enum: ['pro_club_matches', 'national_team_matches', 'mixed_match_results', 'field_training_camp', 'laboratory', 'review_or_consensus', 'ball_physics', 'betting_market', 'non_peer_reviewed'] },
          population: { type: 'string' },
          sample_size: { type: 'string' },
          altitude_range_m: { type: 'string' },
          design_and_measures: { type: 'string' },
          measured_effects: { type: 'string', description: 'numbers where available' },
          uncertainty: { type: 'string', description: 'CIs, p-values, effect sizes, or "not reported"' },
          limitations: { type: 'string' },
          relevance_to_2500m_filter: { type: 'string', description: 'incl. any extrapolation needed' },
          source_urls: { type: 'array', items: { type: 'string' } },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['key', 'title', 'authors', 'year', 'published_in', 'language', 'study_type', 'population', 'sample_size', 'altitude_range_m', 'design_and_measures', 'measured_effects', 'uncertainty', 'limitations', 'relevance_to_2500m_filter', 'source_urls', 'confidence'],
      },
    },
    search_log: { type: 'string', description: 'the queries you ran and what each yielded, briefly' },
    gaps: { type: 'string', description: 'what you looked for and could not find' },
  },
  required: ['studies', 'search_log', 'gaps'],
}

const LENSES = [
  { key: 'physiology_field', prompt: `Find ORIGINAL peer-reviewed field studies of soccer players' physical/match performance after acute arrival at moderate or high altitude, including the ISA3600 project (La Paz, 3,600 m: Aughey 2013, Buchheit 2013, Wachsmuth 2013, Girard 2013, Gore 2013 etc. in BJSM), Garvican 2014 (1,600 m, international footballers, GPS running), Nassis 2013 (2010 FIFA World Cup data), Bohner 2015 (women's collegiate soccer at moderate altitude), McLean/Aughey Australian football at 2,130 m, Levine, Stray-Gundersen & Mehta 2008, Gore et al 2008 Scand J Med Sci Sports altitude supplement. Extract: total distance, high-intensity running, repeated-sprint decrements, RPE, SpO2, time course over days 1-14, first vs second half if reported. Also search for any study measuring decision-making/cognition or technical skill in soccer at altitude.` },
  { key: 'match_results_stats', prompt: `Find ORIGINAL statistical analyses of match OUTCOMES and altitude: McSharry 2007 BMJ (South American international results 1900-2004, altitude-difference effect on goals and win probability), Chumacero 2009 Journal of Sports Economics 'Altitude or hot air?', any replications or rebuttals, Pollard & Armatas 2017 (home advantage in World Cup qualification incl. altitude), studies of Bolivian, Ecuadorian, Colombian, Peruvian or Mexican club leagues and Copa Libertadores home advantage at altitude, Kraus/Sanchez/van Damme style papers on altitude difference and results, and analyses that used CLUB matches specifically. Extract the effect sizes exactly (e.g., goals per 1,000 m of elevation difference, probability shifts), the sample, the controls used (team quality, home advantage), and whether the effect survived quality controls.` },
  { key: 'spanish_language', prompt: `Search IN SPANISH for original research on altitude and football performance/results: queries such as "efecto de la altura en el rendimiento del fútbol estudio", "ventaja de localía altura Bolivia estudio", "aclimatación altitud futbolistas hipoxia rendimiento partido", "análisis estadístico resultados fútbol altura Sudamérica", "Copa Libertadores altura ventaja estudio", "Estadio Hernando Siles ventaja científica", "altura fútbol Quito Bogotá estudio rendimiento", "hipoxia hipobárica futbolistas sprint repetido", "tesis altura fútbol rendimiento La Paz", "Cusco altura fútbol estudio". Look on scielo.org, redalyc.org, dialnet.unirioja.es, researchgate, university repositories (UMSA, PUCP, Universidad de los Andes, Universidad San Francisco de Quito), and Spanish-language sports-science journals (Apunts, RICYDE, Retos, Revista Andaluza de Medicina del Deporte, Archivos de Medicina del Deporte). Report each study in English but keep the original Spanish title.` },
  { key: 'timing_within_match', prompt: `Find evidence on WHEN within a match the altitude disadvantage appears: first half vs second half running distance or goals, late goals against unacclimatized visitors, fatigue accumulation, and time-of-match goal distributions at altitude (La Paz, Quito, Bogotá, Toluca, Cusco). Sources may include Nassis 2013 (World Cup 2010 half splits), Garvican 2014, ISA3600 papers, McSharry 2007 (if it analysed goal timing), Bolivian/Ecuadorian national-team goal-timing analyses, and any analytics blogs (e.g., StatsBomb, FiveThirtyEight, The Athletic, Fun Stats) that examined half-specific or late-goal patterns at altitude. Distinguish peer-reviewed from non-peer-reviewed sources. If nothing rigorous exists, say so.` },
  { key: 'acclimatization_strategy', prompt: `Find research and official guidance on acclimatization strategy for football at altitude: FIFA/F-MARC consensus statement (Bärtsch, Saltin, Dvorak 2008, Scand J Med Sci Sports 18 Suppl 1), recommendations on arrival timing (arrive within hours vs 3-5 days vs 2 weeks), the acute-mountain-sickness time course, live-high train-low, pre-acclimatization camps, effects of recent altitude exposure and of regular altitude exposure (altitude-native players, players based at Mexico City/Bogotá), and evidence on whether same-day arrival mitigates performance loss. Also find documentation of what national teams and clubs actually do when visiting La Paz/Quito/Bogotá (arrive same day, oxygen, etc.) and any evidence that these strategies changed results. Report which claims are evidence-based and which are expert opinion.` },
  { key: 'ball_flight_environment', prompt: `Find research on match-environment changes at altitude that affect BOTH teams: reduced air density and ball aerodynamics (drag, Magnus effect, ball travels further and swerves less), effects on shooting distance, goalkeeping, long passes and crosses; temperature, humidity and UV at altitude venues; Jabulani/2010 World Cup altitude physics; and any work distinguishing symmetric environmental effects from the asymmetric physiological effect on unacclimatized visitors. Include physics papers (e.g., Goff, Asai, Mehta on soccer ball aerodynamics) and applied sport-science reviews. Report quantitative estimates (e.g., percent drag reduction at 2,600 m and 3,600 m) with sources.` },
  { key: 'home_advantage_literature', prompt: `Find the home-advantage literature relevant to altitude: Pollard 2006 'Worldwide regional variations in home advantage' and Pollard & Gómez global/country studies (Bolivia, Ecuador, Colombia, Peru, Mexico home-advantage magnitudes), Pollard, Prieto & Gómez, Leite & Pollard, Van Damme & Baert 2019 (which dimension of distance matters), Pollard & Armatas 2017 World Cup qualification home advantage (altitude, distance, crowd), Copa Libertadores home advantage studies, and any paper estimating how much of Andean home advantage is attributable to altitude vs travel, crowd, or refereeing. Extract country-level home-advantage figures and the altitude coefficients reported.` },
  { key: 'betting_market_efficiency', prompt: `Find any evidence on whether BETTING MARKETS price altitude: academic papers on betting-market efficiency for home advantage, travel distance or altitude in South American football; FiveThirtyEight SPI methodology altitude adjustment (they added an altitude adjustment for club matches - find the details), Elo/rating systems with altitude terms (e.g., World Football Elo Ratings, ClubElo, Opta, Massey), analytics blogs or papers backtesting bets on Bolivian/Ecuadorian/Colombian/Mexican home teams at altitude, and bookmaker or trader commentary on altitude pricing. Also find whether any published backtest reported closing-line value or ROI for altitude-based strategies. Separate peer-reviewed evidence from practitioner commentary, and note where profitability is simply untested.` },
  { key: 'regulation_and_thresholds', prompt: `Find the history and evidence behind ALTITUDE THRESHOLDS in football regulation: the 2007 FIFA ban on internationals above 2,500 m (later 2,750 m then 3,000 m, then suspended in 2008), the medical rationale FIFA cited, CONMEBOL positions, the 2,500 m and 3,000 m figures' scientific origin (e.g., altitude classification: low <500 m, moderate 1,500-2,500 m, high 2,500-3,500 m, very high >3,500 m per Bärtsch & Saltin), and any evidence that performance effects change sharply near 2,500 m versus increasing gradually. Also find studies from other altitude leagues worldwide (Ethiopia, Mexico Toluca, Kunming, Nairobi, Johannesburg 2010 World Cup) that report result or performance effects. Extract the exact thresholds and the reasoning given.` },
]

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    exists: { type: 'string', enum: ['confirmed', 'likely', 'not_found', 'refuted'] },
    bibliographic_corrections: { type: 'string' },
    numbers_check: { type: 'string', description: 'which reported numbers/effects you could confirm, correct, or could not verify' },
    corrected_measured_effects: { type: 'string' },
    corrected_sample_size: { type: 'string' },
    corrected_altitude_range_m: { type: 'string' },
    additional_limitations: { type: 'string' },
    verdict: { type: 'string', enum: ['confirmed', 'corrected', 'unverifiable', 'refuted'] },
    evidence_urls: { type: 'array', items: { type: 'string' } },
  },
  required: ['key', 'exists', 'bibliographic_corrections', 'numbers_check', 'corrected_measured_effects', 'corrected_sample_size', 'corrected_altitude_range_m', 'additional_limitations', 'verdict', 'evidence_urls'],
}

phase('Find')
log(`Launching ${LENSES.length} literature finders`)
const found = await parallel(LENSES.map(l => () =>
  agent(`${ENV}\nYOUR LENS: ${l.key}\n${l.prompt}\nReturn every relevant ORIGINAL study or authoritative document you can confirm (aim for completeness, 5-15 items), each as a structured record. Include the exact title so it can be re-searched.`,
    { label: `find:${l.key}`, phase: 'Find', schema: STUDY_SCHEMA })
))

const all = found.filter(Boolean).flatMap(r => r.studies || [])
const gapsByLens = found.filter(Boolean).map((r, i) => ({ lens: LENSES[i] ? LENSES[i].key : String(i), gaps: r.gaps, search_log: r.search_log }))
function normTitle(t) { return (t || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 70) }
const byTitle = new Map()
for (const s of all) {
  const k = normTitle(s.title)
  if (!k) continue
  if (!byTitle.has(k)) byTitle.set(k, { ...s, seen_in: [s.key] })
  else byTitle.get(k).seen_in.push(s.key)
}
const unique = Array.from(byTitle.values())
log(`Found ${all.length} records, ${unique.length} unique titles; verifying each with two lenses`)

phase('Verify')
const NOWEB = [
  'IMPORTANT ENVIRONMENT CHANGE: this session has NO working web access any more (the WebSearch budget is exhausted and WebFetch is blocked). Do NOT call WebSearch or WebFetch.',
  'Answer strictly from your own knowledge of the sports-science and sports-economics literature. Be conservative: if you do not specifically recall the publication, say so rather than guessing. A paper you cannot recall is NOT thereby refuted; a paper whose details you recall differently should be corrected.',
  'Your output is raw data for a script.',
].join('\n')
const RECALL_SCHEMA = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    recall: { type: 'string', enum: ['recall_confident', 'recall_partial', 'no_recall', 'believe_incorrect'] },
    what_i_recall: { type: 'string', description: 'authors, year, journal, design, sample, altitude, main findings as you recall them' },
    corrections: { type: 'string', description: 'fields in the finder record that conflict with your recall, and the values you believe are right' },
    overstatement_or_extrapolation: { type: 'string' },
    additional_limitations: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
  required: ['key', 'recall', 'what_i_recall', 'corrections', 'overstatement_or_extrapolation', 'additional_limitations', 'confidence'],
}
const LENS_TXT = {
  bibliographic: 'LENS: bibliographic identity. Do you recall this exact publication (authors, year, journal/venue, title)? Correct any detail you recall differently.',
  methods: 'LENS: population and design. Do you recall who was studied (professional/elite/amateur, club vs national team, men/women/youth), the sample size, the altitude(s), the design (match data, field camp, lab), and the measures?',
  effects: 'LENS: reported effects. Do you recall the direction and magnitude of the main findings and their uncertainty? Is the finder overstating, or extrapolating beyond the studied altitude or population?',
}
const verified = await pipeline(unique,
  s => parallel(Object.keys(LENS_TXT).map(lens => () =>
    agent(NOWEB + '\n' + LENS_TXT[lens] + '\nFinder record (the finder may or may not have had live web results; see confidence and source_urls):\n' + JSON.stringify(s, null, 2),
      { label: 'recall-' + lens + ':' + s.key, phase: 'Verify', schema: RECALL_SCHEMA })
  )).then(vs => ({ study: s, checks: vs.filter(Boolean) }))
)
function score(v) { return v.checks.filter(c => c.recall === 'recall_confident' || c.recall === 'recall_partial').length }
const kept = verified.filter(Boolean).filter(v => score(v) >= 2 && !v.checks.some(c => c.recall === 'believe_incorrect' && c.confidence === 'high'))
const unconfirmed = verified.filter(Boolean).filter(v => !kept.includes(v)).map(v => ({ key: v.study.key, title: v.study.title, seen_in: v.study.seen_in, checks: v.checks.map(c => c.recall + ' (' + c.confidence + '): ' + c.corrections.slice(0, 200)) }))
log('Recall cross-check kept ' + kept.length + '/' + verified.filter(Boolean).length + ' studies; ' + unconfirmed.length + ' unconfirmed')

phase('Synthesize')
const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    evidence_table_markdown: { type: 'string', description: 'Markdown table: Study | Type | Population & n | Altitude | Measured effect | Uncertainty | Limitations | Verification status in this session | Relevance/extrapolation to >2,500 m filter' },
    physical_performance_md: { type: 'string' },
    acclimatization_md: { type: 'string' },
    timing_within_match_md: { type: 'string' },
    environment_ball_flight_md: { type: 'string' },
    match_results_evidence_md: { type: 'string' },
    market_evidence_md: { type: 'string' },
    thresholds_md: { type: 'string' },
    what_is_established_md: { type: 'string' },
    what_is_uncertain_md: { type: 'string' },
    citations: { type: 'array', items: { type: 'object', properties: { key: { type: 'string' }, citation: { type: 'string' }, url: { type: 'string' }, verification: { type: 'string' } }, required: ['key', 'citation', 'url', 'verification'] } },
  },
  required: ['evidence_table_markdown', 'physical_performance_md', 'acclimatization_md', 'timing_within_match_md', 'environment_ball_flight_md', 'match_results_evidence_md', 'market_evidence_md', 'thresholds_md', 'what_is_established_md', 'what_is_uncertain_md', 'citations'],
}
const webLenses = ['physiology_field', 'match_results_stats']
const synthesis = await agent(NOWEB + '\nSYNTHESIS TASK. Write the scientific-evidence section of a research report for a bettor evaluating the rule "back home teams whose venue is >2,500 m above the visiting team usual base". Inputs: (1) study records found by nine finder lenses - the lenses ' + webLenses.join(', ') + ' had live web results for their first ~45 queries, all other lenses worked from model recall only; (2) three independent recall-based cross-checks per study (this session lost web access, so no study could be re-verified online - say this plainly in the section and mark each citation "web-confirmed by finder", "recall-only (verify before relying)" or "unconfirmed"). Rules: cite at point of use with [key]; use cross-check corrections where they conflict with the finder; never extrapolate beyond studied conditions without flagging it; distinguish professional club matches, national-team matches, field camps, and lab studies; state where evidence is missing (e.g. rigorous half-split evidence). Keep it factual and tight.\n\nKEPT RECORDS:\n' + JSON.stringify(kept.map(v => ({ study: v.study, checks: v.checks })), null, 1).slice(0, 170000) + '\n\nUNCONFIRMED:\n' + JSON.stringify(unconfirmed, null, 1).slice(0, 12000) + '\n\nFINDER GAP NOTES:\n' + JSON.stringify(gapsByLens, null, 1).slice(0, 15000),
  { label: 'synthesize-science', phase: 'Synthesize', schema: SYNTH_SCHEMA, effort: 'high' })

return { synthesis, kept, unconfirmed, gapsByLens, counts: { found: all.length, unique: unique.length, kept: kept.length } }
