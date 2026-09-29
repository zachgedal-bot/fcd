# High-altitude home advantage in soccer: does a >2,500 m net elevation gap carry betting value?

Research date: 2026-09-29. Prepared for a bettor evaluating the rule **"back the home team when the actual match venue is more than 2,500 m above the visiting team's usual playing or training elevation."** All elevations are ground elevations from the SRTM digital elevation model at the stadium coordinates unless stated otherwise; 2,500 m is treated as the user's screening threshold, not a biological or profitability cutoff.

## Executive summary

**What is established**
- **A large performance effect exists in the historical club data.** Across 1,569 top-flight and continental club matches (2015-2025, Mexico, Peru, Ecuador, Colombia, Bolivia, Copa Libertadores, Copa Sudamericana) in which an acclimatized host received a visitor from more than 2,500 m lower, the host won 62.4% of league matches (draw 22.4%, away win 15.2%; unbeaten 84.8%; goal difference +1.14) against a league-wide home-win rate of roughly 41.9% when host and visitor come from similar elevations.
- **The effect survives adjustment for team strength and ordinary home advantage.** With pre-match Elo ratings and competition effects, the net gap adds 0.42 on the ordered-logit scale per 1,000 m (95% CI 0.39 to 0.46); a 2,500 m gap is worth roughly 232 Elo points. A fixed-effects model that compares the **same host** against visitors from different elevations (so stadium identity, crowd and club quality are held constant) still finds home goals up by +14% and away goals down by -14% per 1,000 m of net gap.
- **The excess is not an artefact of one league or one club.** Dropping any home country or any of the ten most frequent hosts leaves the per-1,000 m coefficient between 0.37 and 0.41.
- **The effect is not a step at 2,500 m.** Home-win rates rise with the gap and are much stronger above 3,000 m (71.4% at 3,000-3,500 m, 76.1% above 3,500 m) than at 2,500-3,000 m (54.1%). The 2,500 m cutoff is defensible as a screen but it lumps the Quito/Bogotá/Sucre band (modest effect) with the La Paz/Oruro/Potosí/Cusco/Huancayo band (large effect).
- **Adding altitude improves out-of-sample prediction.** Trained on 2015-2020 and tested on 2021-2025, the altitude-aware model lowers log-loss on all matches (1.0081 to 0.9988) and on qualifying matches (0.8771 to 0.8412); the naive model predicted 52.1% home wins in qualifying test matches against 63.6% observed.
- **Both scoring channels move.** Hosts score more and visitors score less; total goals rise mainly at the highest venues (Bolivia). This supports home-win and home-or-draw markets rather than a generic "overs" rule.

**What remains uncertain or untested**
- **Whether the price already reflects it.** The only archived prices reachable were Liga MX (Bet365 and best-of-market, 2015-2024). Toluca's qualifying home matches with prices number 16 (actual home-win rate 87.5% vs a de-vigged implied 57.8%); the flat-stake return of +56% at best price has a standard error of about 16%, so it is not evidence of a repeatable edge. Across all Liga MX matches, a logit of home-win on the market's own probability plus the net gap gives a gap coefficient of +0.014 (p = 0.88): **the Liga MX market does not appear to misprice altitude in general.** No historical odds for the Bolivian, Peruvian, Ecuadorian or Colombian leagues or CONMEBOL cups could be obtained in this session, so profitability of the filter where the effect is largest is **untested**.
- **Half-specific and late-goal patterns** could not be tested for clubs (no half-time scores or goal minutes in the reachable data). National-team goal minutes show no clear late-match skew.
- **Physiology at the venues that matter most** is documented by field studies of youth squads at 3,600 m and by moderate-altitude match studies; professional-match GPS evidence at 2,500-4,100 m is thin, and the literature could not be re-verified online after this session's search allowance ran out.

**Does the exact filter have evidence behind it?** As a screen for a *performance* effect, yes: the >2,500 m rule selects matches where hosts outperform a strength-adjusted, home-advantage-adjusted expectation by about +14.6 pp to +26.4 pp in home-win probability (bootstrap 95% CIs +12.2 pp to +17.0 pp and +23.8 pp to +28.9 pp, depending on how much of the host's rating is credited to altitude). As a *betting* rule, the evidence stops short: the one market that could be tested shows no systematic mispricing outside a handful of matches, and the markets where the effect is largest could not be tested at all.

## 1. The screening rule as implemented

- Net elevation difference = DEM elevation of the actual match venue minus the DEM elevation of the visitor's usual home venue in that season (a proxy for training elevation, labelled as such; see Section 9 for the training-ground table). Primary filter: net gap > 2,500 m.
- Hosts count only when acclimatized: the match venue must lie within 500 m of the host's own usual venue that season (34 nominal home matches at relocated highland venues were excluded from the main sample and are reported separately).
- Recent altitude exposure of the visitor (any match at 2,000 m or higher in the previous 14 days) is computed from the match data itself.
- Registry status: 209 venues located; 0 still carry a DEM-versus-published disagreement flag. The registry, its candidate records and their basis are in `data/registry/`.

## 2. Scientific evidence

_The literature synthesis had not completed when this report was built; see `output/salvaged/workflow_partial_results.json` for the raw finder records._

## 3. Historical club backtest (regulation time, 2014/15-2025)

The central question is not whether highland hosts win often, but whether they win more than their strength and ordinary home advantage predict. Raw results come first, adjusted estimates after.

#### Coverage

| Competition | Matches | With computable gap | Seasons |
|---|---|---|---|
| BOL | 2792 | 2524 | 2015-2025 |
| COL | 4752 | 4383 | 2014-2025 |
| ECU | 3016 | 2656 | 2014-2025 |
| LIB | 1512 | 125 | 2014-2025 |
| MEX | 3552 | 3524 | 2015-2026 |
| PER | 3666 | 2465 | 2014-2025 |
| SUD | 1311 | 179 | 2014-2024 |

Qualifying sample (net gap > 2,500 m): 1603 matches, of which 1569 with an acclimatized host (main sample) and 34 where the nominal host was itself far from its usual elevation (excluded).

#### Raw results, qualifying sample by competition type

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| continental | 36 | 61.1% | 19.4% | 19.4% | 80.6% | 2.03 | 1.14 | 1.72 | 0.58 | 2.31 | 44.4% | 16 | 13 | 11 |
| league | 1533 | 62.4% | 22.4% | 15.2% | 84.8% | 2.10 | 1.14 | 1.99 | 0.85 | 2.84 | 53.1% | 53 | 36 | 11 |

#### Raw results, qualifying sample by competition

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BOL | 389 | 79.2% | 12.6% | 8.2% | 91.8% | 2.50 | 2.09 | 2.85 | 0.75 | 3.60 | 70.4% | 12 | 7 | 9 |
| COL | 176 | 65.3% | 24.4% | 10.2% | 89.8% | 2.21 | 0.97 | 1.55 | 0.58 | 2.14 | 38.1% | 10 | 7 | 11 |
| ECU | 494 | 49.8% | 28.7% | 21.5% | 78.5% | 1.78 | 0.61 | 1.61 | 1.00 | 2.62 | 48.8% | 18 | 11 | 11 |
| LIB | 19 | 63.2% | 21.1% | 15.8% | 84.2% | 2.10 | 1.32 | 1.84 | 0.53 | 2.37 | 42.1% | 9 | 8 | 11 |
| MEX | 21 | 85.7% | 4.8% | 9.5% | 90.5% | 2.62 | 2.00 | 2.71 | 0.71 | 3.43 | 76.2% | 1 | 2 | 10 |
| PER | 453 | 59.6% | 23.8% | 16.6% | 83.4% | 2.03 | 0.91 | 1.79 | 0.88 | 2.67 | 47.7% | 12 | 9 | 10 |
| SUD | 17 | 58.8% | 17.6% | 23.5% | 76.5% | 1.94 | 0.94 | 1.59 | 0.65 | 2.23 | 47.1% | 12 | 11 | 7 |

#### Raw results, qualifying sample by host country

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BOL | 404 | 78.5% | 12.6% | 8.9% | 91.1% | 2.48 | 2.06 | 2.81 | 0.76 | 3.57 | 69.8% | 12 | 7 | 11 |
| COL | 183 | 63.9% | 25.1% | 10.9% | 89.1% | 2.17 | 0.92 | 1.51 | 0.58 | 2.09 | 36.6% | 10 | 7 | 11 |
| ECU | 504 | 50.2% | 28.6% | 21.2% | 78.8% | 1.79 | 0.63 | 1.63 | 0.99 | 2.62 | 49.2% | 18 | 11 | 11 |
| MEX | 21 | 85.7% | 4.8% | 9.5% | 90.5% | 2.62 | 2.00 | 2.71 | 0.71 | 3.43 | 76.2% | 1 | 2 | 10 |
| PER | 457 | 60.0% | 23.6% | 16.4% | 83.6% | 2.04 | 0.92 | 1.79 | 0.87 | 2.66 | 47.5% | 12 | 9 | 10 |

#### Raw results by 500 m net-gap bin (all matches, acclimatized hosts)

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (-9999, -2500] | 1580 | 54.6% | 25.0% | 20.4% | 79.6% | 1.89 | 0.73 | 1.71 | 0.97 | 2.68 | 49.9% | 51 | 50 | 11 |
| (-2500, -1500] | 1266 | 47.0% | 28.8% | 24.2% | 75.8% | 1.70 | 0.43 | 1.49 | 1.06 | 2.54 | 46.4% | 69 | 66 | 12 |
| (-1500, -500] | 1978 | 44.8% | 28.6% | 26.6% | 73.4% | 1.63 | 0.35 | 1.44 | 1.08 | 2.52 | 46.9% | 90 | 75 | 12 |
| (-500, 500] | 5431 | 41.9% | 27.5% | 30.6% | 69.4% | 1.53 | 0.23 | 1.42 | 1.19 | 2.60 | 48.1% | 142 | 122 | 12 |
| (500, 1500] | 1967 | 47.9% | 26.9% | 25.2% | 74.8% | 1.71 | 0.45 | 1.47 | 1.02 | 2.49 | 46.0% | 86 | 71 | 12 |
| (1500, 2000] | 602 | 48.5% | 29.1% | 22.4% | 77.6% | 1.75 | 0.53 | 1.49 | 0.96 | 2.45 | 45.3% | 45 | 39 | 12 |
| (2000, 2500] | 638 | 58.3% | 25.1% | 16.6% | 83.4% | 2.00 | 0.86 | 1.72 | 0.86 | 2.58 | 46.4% | 44 | 34 | 12 |
| (2500, 3000] | 872 | 54.1% | 27.4% | 18.5% | 81.5% | 1.90 | 0.75 | 1.64 | 0.89 | 2.52 | 46.3% | 45 | 31 | 11 |
| (3000, 3500] | 496 | 71.4% | 16.7% | 11.9% | 88.1% | 2.31 | 1.57 | 2.33 | 0.76 | 3.10 | 58.1% | 18 | 10 | 11 |
| (3500, 9999] | 201 | 76.1% | 13.9% | 10.0% | 90.0% | 2.42 | 1.73 | 2.60 | 0.87 | 3.47 | 68.7% | 8 | 5 | 11 |

#### Comparison groups

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Same hosts vs visitors from similar elevation (|gap| <= 500 m) | 2286 | 42.3% | 28.0% | 29.8% | 70.2% | 1.55 | 0.27 | 1.47 | 1.20 | 2.67 | 49.4% | 52 | 48 | 12 |
| Same hosts, all home matches | 5747 | 50.8% | 26.1% | 23.1% | 76.9% | 1.79 | 0.61 | 1.64 | 1.03 | 2.67 | 49.3% | 53 | 68 | 12 |

#### Qualifying sample by visitor recent altitude exposure (any match at >= 2,000 m in prior 14 days)

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| visitor not recently at altitude | 1074 | 61.4% | 22.6% | 16.0% | 84.0% | 2.07 | 1.05 | 1.93 | 0.88 | 2.81 | 52.8% | 52 | 33 | 11 |
| visitor recently at altitude | 495 | 64.6% | 21.6% | 13.7% | 86.3% | 2.16 | 1.32 | 2.09 | 0.77 | 2.86 | 53.1% | 48 | 30 | 11 |

#### Qualifying sample by period

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2015-2019 | 834 | 62.0% | 23.1% | 14.9% | 85.1% | 2.09 | 1.14 | 2.01 | 0.87 | 2.88 | 53.7% | 37 | 28 | 5 |
| 2020-2025 | 735 | 62.9% | 21.4% | 15.8% | 84.2% | 2.10 | 1.13 | 1.95 | 0.81 | 2.76 | 52.0% | 45 | 31 | 6 |

#### Qualifying sample, most frequent hosts (25+ matches)

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Always Ready | 44 | 95.5% | 4.5% | 0.0% | 100.0% | 2.91 | 2.96 | 3.39 | 0.43 | 3.82 | 75.0% | 1 | 2 | 7 |
| Asociación Deportiva Tarma | 27 | 59.3% | 29.6% | 11.1% | 88.9% | 2.07 | 0.96 | 1.59 | 0.63 | 2.22 | 37.0% | 1 | 2 | 3 |
| Ayacucho | 42 | 42.9% | 33.3% | 23.8% | 76.2% | 1.62 | 0.67 | 1.55 | 0.88 | 2.43 | 42.9% | 1 | 2 | 6 |
| Binacional | 35 | 65.7% | 11.4% | 22.9% | 77.1% | 2.09 | 1.34 | 2.31 | 0.97 | 3.29 | 60.0% | 1 | 3 | 5 |
| Bolívar | 77 | 85.7% | 9.1% | 5.2% | 94.8% | 2.66 | 2.53 | 3.03 | 0.49 | 3.52 | 68.8% | 1 | 2 | 9 |
| Boyacá Patriot | 29 | 69.0% | 27.6% | 3.4% | 96.6% | 2.35 | 1.03 | 1.48 | 0.45 | 1.93 | 31.0% | 1 | 2 | 9 |
| CD Cuenca | 62 | 48.4% | 25.8% | 25.8% | 74.2% | 1.71 | 0.45 | 1.55 | 1.10 | 2.65 | 51.6% | 1 | 1 | 9 |
| Cienciano | 41 | 63.4% | 24.4% | 12.2% | 87.8% | 2.15 | 0.93 | 1.78 | 0.85 | 2.63 | 43.9% | 1 | 1 | 6 |
| El Nacional | 54 | 53.7% | 27.8% | 18.5% | 81.5% | 1.89 | 0.59 | 1.67 | 1.07 | 2.74 | 51.9% | 1 | 2 | 9 |
| LDU de Quito | 74 | 64.9% | 27.0% | 8.1% | 91.9% | 2.22 | 1.04 | 1.77 | 0.73 | 2.50 | 44.6% | 1 | 2 | 11 |
| La Equidad | 26 | 57.7% | 30.8% | 11.5% | 88.5% | 2.04 | 0.69 | 1.08 | 0.39 | 1.46 | 15.4% | 1 | 3 | 10 |
| Macará | 45 | 46.7% | 28.9% | 24.4% | 75.6% | 1.69 | 0.49 | 1.49 | 1.00 | 2.49 | 40.0% | 1 | 1 | 6 |
| Melgar | 88 | 61.4% | 22.7% | 15.9% | 84.1% | 2.07 | 0.92 | 1.75 | 0.83 | 2.58 | 45.5% | 1 | 2 | 10 |
| Millonarios | 27 | 70.4% | 18.5% | 11.1% | 88.9% | 2.30 | 1.04 | 1.63 | 0.59 | 2.22 | 33.3% | 1 | 1 | 9 |
| Mushuc Runa | 34 | 41.2% | 26.5% | 32.4% | 67.6% | 1.50 | 0.41 | 1.68 | 1.26 | 2.94 | 50.0% | 1 | 4 | 6 |
| Nacional Potosí | 73 | 78.1% | 16.4% | 5.5% | 94.5% | 2.51 | 1.82 | 2.71 | 0.89 | 3.60 | 74.0% | 1 | 1 | 9 |
| Pasto | 30 | 60.0% | 26.7% | 13.3% | 86.7% | 2.07 | 0.93 | 1.63 | 0.70 | 2.33 | 46.7% | 1 | 2 | 11 |
| Real Garcilaso | 43 | 67.4% | 23.3% | 9.3% | 90.7% | 2.26 | 0.95 | 1.93 | 0.98 | 2.91 | 51.2% | 1 | 2 | 5 |
| Real Potosí | 57 | 66.7% | 15.8% | 17.5% | 82.5% | 2.16 | 1.07 | 2.19 | 1.12 | 3.32 | 66.7% | 1 | 1 | 6 |
| SD Aucas | 62 | 53.2% | 29.0% | 17.7% | 82.3% | 1.89 | 0.79 | 1.81 | 1.02 | 2.82 | 54.8% | 1 | 1 | 10 |
| San José | 54 | 66.7% | 14.8% | 18.5% | 81.5% | 2.15 | 1.48 | 2.41 | 0.93 | 3.33 | 66.7% | 1 | 1 | 7 |
| Santa Fe | 33 | 66.7% | 27.3% | 6.1% | 93.9% | 2.27 | 1.18 | 1.79 | 0.61 | 2.39 | 48.5% | 1 | 2 | 11 |
| Sport Huancayo | 79 | 65.8% | 19.0% | 15.2% | 84.8% | 2.17 | 0.96 | 1.75 | 0.79 | 2.53 | 48.1% | 1 | 1 | 10 |
| The Strongest | 78 | 84.6% | 9.0% | 6.4% | 93.6% | 2.63 | 2.72 | 3.40 | 0.68 | 4.08 | 78.2% | 1 | 2 | 10 |
| Técnico Univ. | 37 | 43.2% | 29.7% | 27.0% | 73.0% | 1.59 | 0.35 | 1.46 | 1.11 | 2.57 | 54.1% | 1 | 1 | 6 |
| UTC | 49 | 46.9% | 34.7% | 18.4% | 81.6% | 1.75 | 0.61 | 1.67 | 1.06 | 2.73 | 46.9% | 1 | 1 | 7 |
| Univ Católica | 68 | 54.4% | 29.4% | 16.2% | 83.8% | 1.93 | 0.90 | 1.69 | 0.79 | 2.48 | 48.5% | 1 | 3 | 11 |

#### Qualifying sample, most frequent venues (25+ matches)

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Estadio Alejandro Serrano Aguilar | 62 | 48.4% | 25.8% | 25.8% | 74.2% | 1.71 | 0.45 | 1.55 | 1.10 | 2.65 | 51.6% | 1 | 1 | 9 |
| Estadio Bellavista de Ambato | 96 | 43.8% | 27.1% | 29.2% | 70.8% | 1.58 | 0.35 | 1.47 | 1.11 | 2.58 | 46.9% | 4 | 1 | 9 |
| Estadio Ciudad de Cumaná | 41 | 41.5% | 34.1% | 24.4% | 75.6% | 1.58 | 0.63 | 1.54 | 0.90 | 2.44 | 43.9% | 1 | 1 | 6 |
| Estadio Gonzalo Pozo Ripalda | 64 | 53.1% | 28.1% | 18.8% | 81.2% | 1.88 | 0.81 | 1.83 | 1.02 | 2.84 | 54.7% | 3 | 1 | 11 |
| Estadio Guillermo Briceño Rosamedina | 31 | 64.5% | 12.9% | 22.6% | 77.4% | 2.06 | 1.19 | 2.26 | 1.06 | 3.32 | 61.3% | 1 | 1 | 5 |
| Estadio Hernando Siles | 157 | 86.0% | 8.3% | 5.7% | 94.3% | 2.66 | 2.64 | 3.23 | 0.59 | 3.81 | 73.9% | 3 | 1 | 10 |
| Estadio Huancayo | 85 | 64.7% | 20.0% | 15.3% | 84.7% | 2.14 | 0.95 | 1.74 | 0.79 | 2.53 | 48.2% | 3 | 1 | 10 |
| Estadio Héroes de San Ramón | 49 | 46.9% | 34.7% | 18.4% | 81.6% | 1.75 | 0.61 | 1.67 | 1.06 | 2.73 | 46.9% | 1 | 1 | 7 |
| Estadio Inca Garcilaso de la Vega | 124 | 65.3% | 21.8% | 12.9% | 87.1% | 2.18 | 1.01 | 1.85 | 0.84 | 2.69 | 46.8% | 6 | 1 | 10 |
| Estadio Jesús Bermúdez | 58 | 65.5% | 15.5% | 19.0% | 81.0% | 2.12 | 1.47 | 2.41 | 0.95 | 3.36 | 65.5% | 3 | 1 | 8 |
| Estadio Metropolitano de Techo | 41 | 61.0% | 22.0% | 17.1% | 82.9% | 2.05 | 0.78 | 1.27 | 0.49 | 1.76 | 24.4% | 7 | 1 | 10 |
| Estadio Municipal El Alto | 42 | 92.9% | 7.1% | 0.0% | 100.0% | 2.86 | 2.86 | 3.31 | 0.45 | 3.76 | 71.4% | 2 | 1 | 7 |
| Estadio Municipal Unión de Tarma | 25 | 64.0% | 28.0% | 8.0% | 92.0% | 2.20 | 1.08 | 1.76 | 0.68 | 2.44 | 40.0% | 2 | 1 | 4 |
| Estadio Nemesio Camacho El Campín | 58 | 69.0% | 22.4% | 8.6% | 91.4% | 2.29 | 1.14 | 1.76 | 0.62 | 2.38 | 43.1% | 2 | 1 | 11 |
| Estadio Olímpico Atahualpa | 156 | 50.6% | 30.8% | 18.6% | 81.4% | 1.83 | 0.69 | 1.65 | 0.96 | 2.61 | 50.6% | 8 | 1 | 11 |
| Estadio Rodrigo Paz Delgado | 34 | 67.6% | 20.6% | 11.8% | 88.2% | 2.23 | 1.21 | 1.91 | 0.71 | 2.62 | 47.1% | 2 | 1 | 6 |
| Estadio Victor Agustín Ugarte | 130 | 73.1% | 16.2% | 10.8% | 89.2% | 2.35 | 1.49 | 2.48 | 0.99 | 3.48 | 70.8% | 2 | 1 | 9 |
| Estadio de Liga Deportiva Universitaria | 43 | 62.8% | 32.6% | 4.7% | 95.3% | 2.21 | 0.98 | 1.72 | 0.74 | 2.46 | 44.2% | 3 | 1 | 5 |
| Estadio de la Independencia | 52 | 61.5% | 30.8% | 7.7% | 92.3% | 2.15 | 0.79 | 1.36 | 0.58 | 1.94 | 34.6% | 2 | 1 | 11 |
| Estadio de la Universidad Nacional San A... | 90 | 61.1% | 22.2% | 16.7% | 83.3% | 2.06 | 0.97 | 1.79 | 0.82 | 2.61 | 45.6% | 2 | 1 | 10 |

#### League-wide baselines (all matches with computable gap, by competition)

| Sample | N | Home win | Draw | Away win | Home unbeaten | Home PPG | Goal diff | Home goals | Away goals | Total goals | Over 2.5 | Hosts | Venues | Seasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BOL | 2520 | 55.4% | 21.6% | 22.9% | 77.1% | 1.88 | 0.78 | 1.92 | 1.14 | 3.06 | 57.9% | 31 | 27 | 9 |
| COL | 4362 | 46.4% | 29.9% | 23.7% | 76.3% | 1.69 | 0.42 | 1.34 | 0.92 | 2.26 | 40.0% | 33 | 35 | 11 |
| ECU | 2388 | 46.1% | 27.4% | 26.5% | 73.5% | 1.66 | 0.43 | 1.53 | 1.10 | 2.63 | 48.8% | 32 | 24 | 11 |
| LIB | 106 | 56.6% | 19.8% | 23.6% | 76.4% | 1.90 | 0.86 | 1.77 | 0.92 | 2.69 | 47.2% | 33 | 35 | 11 |
| MEX | 3509 | 45.0% | 26.4% | 28.6% | 71.4% | 1.61 | 0.35 | 1.51 | 1.15 | 2.66 | 50.4% | 24 | 27 | 12 |
| PER | 2253 | 47.2% | 27.8% | 25.0% | 75.0% | 1.70 | 0.46 | 1.53 | 1.07 | 2.61 | 47.7% | 32 | 24 | 11 |
| SUD | 149 | 53.0% | 19.5% | 27.5% | 72.5% | 1.78 | 0.55 | 1.60 | 1.05 | 2.66 | 53.0% | 60 | 41 | 10 |

#### Adjusted estimates (seasons 2015-2025, acclimatized hosts, N = 15031)

| Model / term | Coefficient | 95% CI | SE | p |
|---|---|---|---|---|
| Ordered logit: Elo difference per 100 points | 0.455 | 0.428 to 0.482 | 0.014 | 0 |
| Ordered logit: net gap per 1,000 m above visitor base (continuous) | 0.423 | 0.386 to 0.459 | 0.019 | 0 |
| Ordered logit: venue below visitor base, per 1,000 m | 0.079 | 0.044 to 0.113 | 0.018 | 0 |
| Ordered logit: indicator net gap > 2,500 m | 1.134 (odds ratio 3.11) | 1.018 to 1.249 | 0.059 | 0 |
| Ordered logit: continuous + indicator jointly, continuous term | 0.332 | 0.279 to 0.385 | 0.027 | 0 |
| Ordered logit: continuous + indicator jointly, indicator term | 0.267 | 0.088 to 0.447 | 0.092 | 0.0035 |
| Ordered logit: visitor recently at altitude (with continuous gap) | 0.070 | 0.003 to 0.137 | 0.034 | 0.0395 |
| Logit home win (cluster SE): net gap per 1,000 m | 0.413 (odds ratio 1.51) | 0.374 to 0.452 | 0.020 | 0 |
| Logit home win (cluster SE): indicator > 2,500 m | 1.115 (odds ratio 3.05) | 0.987 to 1.244 | 0.066 | 0 |
| Logit home-or-draw (cluster SE): net gap per 1,000 m | 0.438 (odds ratio 1.55) | 0.391 to 0.485 | 0.024 | 0 |
| Logit home-or-draw (cluster SE): indicator > 2,500 m | 1.173 (odds ratio 3.23) | 1.012 to 1.334 | 0.082 | 0 |
| Poisson home goals (cluster SE): net gap per 1,000 m | 0.140 (rate ratio 1.150) | 0.126 to 0.154 | 0.007 | 0 |
| Poisson home goals: indicator > 2,500 m | 0.394 (rate ratio 1.483) | 0.349 to 0.439 | 0.023 | 0 |
| Poisson away goals (cluster SE): net gap per 1,000 m | -0.164 (rate ratio 0.849) | -0.182 to -0.145 | 0.009 | 0 |
| Poisson away goals: indicator > 2,500 m | -0.437 (rate ratio 0.646) | -0.499 to -0.375 | 0.032 | 0 |
| Poisson total goals: net gap per 1,000 m | 0.023 (rate ratio 1.023) | 0.011 to 0.035 | 0.006 | 0.0001 |
| Poisson total goals: indicator > 2,500 m | 0.086 (rate ratio 1.090) | 0.049 to 0.123 | 0.019 | 0 |
| FE Poisson (team attack/defence + host home-advantage FE): home goals, gap per 1,000 m | 0.127 (rate ratio 1.136) | 0.095 to 0.160 | 0.017 | 0 |
| FE Poisson: away goals, gap per 1,000 m | -0.145 (rate ratio 0.865) | -0.183 to -0.107 | 0.019 | 0 |
| FE Poisson: home goals, indicator > 2,500 m | 0.339 (rate ratio 1.404) | 0.286 to 0.392 | 0.027 | 0 |
| FE Poisson: away goals, indicator > 2,500 m | -0.405 (rate ratio 0.667) | -0.482 to -0.327 | 0.040 | 0 |

Elo-equivalent of a 2,500 m gap in the continuous ordered-logit model: about 232.4 Elo points. The altitude-neutral rating iteration credited 82.8 Elo points per 1,000 m of net gap to the venue.

#### Ordered logit by gap bin (reference: |gap| <= 500 m)

| Gap bin (m) | Coefficient | 95% CI | SE | p |
|---|---|---|---|---|
| (-1500, -500] | 0.025 | -0.076 to 0.127 | 0.052 | 0.625 |
| (-2500, -1500] | 0.028 | -0.090 to 0.146 | 0.060 | 0.645 |
| (-9999, -2500] | 0.214 | 0.101 to 0.327 | 0.058 | 0.0002 |
| (1500, 2000] | 0.541 | 0.378 to 0.705 | 0.084 | 0 |
| (2000, 2500] | 0.804 | 0.640 to 0.969 | 0.084 | 0 |
| (2500, 3000] | 1.100 | 0.953 to 1.248 | 0.075 | 0 |
| (3000, 3500] | 1.388 | 1.177 to 1.599 | 0.108 | 0 |
| (3500, 9999] | 1.921 | 1.582 to 2.260 | 0.173 | 0 |
| (500, 1500] | 0.329 | 0.226 to 0.432 | 0.053 | 0 |

#### Model-implied probabilities in the qualifying sample (N = 1569)

| | Away win | Draw | Home win | Home DNB |
|---|---|---|---|---|
| Actual | 15.3% | 22.3% | 62.4% | 80.3% |
| Model with altitude term | 16.5% | 22.3% | 61.2% | 77.8% |
| Same teams, altitude term set to zero (ordinary home advantage only) | 38.6% | 28.2% | 33.1% | 46.4% |

Excess of actual over expected (baseline: ordinary home advantage + team strength, no altitude term), cluster-bootstrap 95% CI by host-season:

| Rating variant | Excess home-win rate | 95% CI | Excess points per game | 95% CI | Clusters |
|---|---|---|---|---|---|
| Altitude-neutral Elo | +0.264 | +0.238 to +0.289 | +0.734 | +0.670 to +0.799 | 279 |
| Plain Elo (conservative) | +0.146 | +0.122 to +0.170 | +0.395 | +0.332 to +0.456 | 279 |

#### Threshold robustness (indicator net gap > T; the 2,500 m row is the primary filter)

| Threshold T (m) | N above T | Raw home win | Raw home PPG | Ordered-logit indicator coef | 95% CI | p |
|---|---|---|---|---|---|---|
| 1500 | 2809 | 58.5% | 2.00 | 0.894 | 0.809 to 0.980 | 0 |
| 2000 | 2207 | 61.2% | 2.07 | 1.020 | 0.923 to 1.118 | 0 |
| 2250 | 1843 | 61.8% | 2.08 | 1.079 | 0.973 to 1.186 | 0 |
| 2500 | 1569 | 62.4% | 2.10 | 1.134 | 1.018 to 1.249 | 0 |
| 2750 | 1057 | 65.8% | 2.18 | 1.161 | 1.022 to 1.300 | 0 |
| 3000 | 697 | 72.7% | 2.34 | 1.317 | 1.138 to 1.496 | 0 |
| 3250 | 423 | 74.5% | 2.37 | 1.321 | 1.093 to 1.550 | 0 |
| 3500 | 201 | 76.1% | 2.42 | 1.551 | 1.217 to 1.885 | 0 |

#### Sensitivity of the continuous gap effect (ordered logit, per 1,000 m)

| Subsample | N | N qualifying | Coefficient | 95% CI | p |
|---|---|---|---|---|---|
| drop_home_country_MEX | 11523 | 1548 | 0.393 | 0.356 to 0.429 | 0 |
| drop_home_country_PER | 12861 | 1112 | 0.393 | 0.354 to 0.431 | 0 |
| drop_home_country_ECU | 12591 | 1065 | 0.401 | 0.363 to 0.439 | 0 |
| drop_home_country_COL | 10686 | 1386 | 0.405 | 0.367 to 0.443 | 0 |
| drop_home_country_BOL | 12475 | 1165 | 0.369 | 0.330 to 0.409 | 0 |
| drop_host_Melgar |  | 1481 | 0.400 | 0.365 to 0.435 | 0 |
| drop_host_Sport Huancayo |  | 1490 | 0.391 | 0.356 to 0.425 | 0 |
| drop_host_The Strongest |  | 1491 | 0.389 | 0.355 to 0.423 | 0 |
| drop_host_Bolívar |  | 1492 | 0.388 | 0.354 to 0.423 | 0 |
| drop_host_LDU de Quito |  | 1495 | 0.390 | 0.356 to 0.424 | 0 |
| drop_host_Nacional Potosí |  | 1496 | 0.386 | 0.351 to 0.420 | 0 |
| drop_host_Univ Católica |  | 1501 | 0.393 | 0.359 to 0.427 | 0 |
| drop_host_CD Cuenca |  | 1507 | 0.393 | 0.358 to 0.427 | 0 |
| drop_host_SD Aucas |  | 1507 | 0.394 | 0.359 to 0.428 | 0 |
| drop_host_Real Potosí |  | 1512 | 0.388 | 0.353 to 0.422 | 0 |
| only_league | 14786 | 1533 | 0.394 | 0.360 to 0.428 | 0 |
| only_continental | 245 | 36 | 0.313 | 0.071 to 0.555 | 0.0111 |
| only_home_country_MEX | 3508 | 21 | 0.415 | 0.316 to 0.515 | 0 |
| only_home_country_PER | 2170 | 457 | 0.399 | 0.326 to 0.471 | 0 |
| only_home_country_ECU | 2440 | 504 | 0.363 | 0.288 to 0.438 | 0 |
| only_home_country_COL | 4345 | 183 | 0.337 | 0.260 to 0.414 | 0 |
| only_home_country_BOL | 2556 | 404 | 0.456 | 0.387 to 0.525 | 0 |
| seasons_2015_2019 |  | 834 | 0.397 | 0.349 to 0.445 | 0 |
| seasons_2020_2025 |  | 735 | 0.388 | 0.339 to 0.436 | 0 |

#### Out-of-sample predictive test (train 2015-2020, test 2021-2025; N test = 6577, qualifying in test = 613)

| Metric | Baseline (Elo + competition) | Baseline + altitude terms |
|---|---|---|
| Log-loss, all test matches | 1.0081 | 0.9988 |
| Brier, all test matches | 0.6033 | 0.5973 |
| Log-loss, qualifying test matches | 0.8771 | 0.8412 |
| Mean predicted home-win prob, qualifying test matches (actual 63.6%) | 52.1% | 62.5% |
| Mean predicted home-or-draw prob, qualifying test matches (actual 84.7%) | 77.2% | 84.2% |

Calibration on the test seasons by gap bin:

| Gap bin (m) | N | Actual home win | Baseline prediction | Altitude-model prediction |
|---|---|---|---|---|
| (-1500, -500] | 953 | 42.6% | 46.3% | 44.5% |
| (-2500, -1500] | 536 | 44.8% | 45.2% | 47.8% |
| (-500, 500] | 2410 | 42.3% | 48.2% | 41.5% |
| (-9999, -2500] | 611 | 53.4% | 46.4% | 52.9% |
| (1500, 2000] | 256 | 50.8% | 48.8% | 53.4% |
| (2000, 2500] | 271 | 58.3% | 55.4% | 62.2% |
| (2500, 3000] | 330 | 54.5% | 47.8% | 57.5% |
| (3000, 3500] | 208 | 71.6% | 57.3% | 67.8% |
| (3500, 9999] | 75 | 81.3% | 56.5% | 69.8% |
| (500, 1500] | 927 | 47.8% | 49.6% | 49.4% |

### Reading the club results
- **Raw.** In league play the qualifying host wins 62.4%, draws 22.4%, loses 15.2% (N = 1,533, 53 hosts, 36 venues, 11 seasons). Continental matches show a similar picture on a much smaller sample (N = 36). By country the raw rate ranges from about 50.2% to 78.5% among countries with 50+ matches; Bolivia's La Paz/El Alto/Oruro/Potosí hosts dominate the top end, Ecuador's Quito hosts the bottom.
- **Same hosts, different visitors.** The same highland hosts, when receiving visitors from similar elevation, win 42.3% (N = 2,286), so a large part of the raw gap is about the visitor's origin, not the host's stadium.
- **Adjusted.** The ordered-logit indicator for >2,500 m is 1.13 (odds ratio 3.1, 95% CI 2.8 to 3.5); when the continuous gap and the indicator enter together, the continuous term keeps most of the effect (0.33 per 1,000 m) and the indicator adds 0.27 (p = 0.004), i.e. there is little evidence of a discontinuity at 2,500 m beyond the gradient. A visitor that had already played at 2,000 m+ in the prior two weeks fares slightly better (+0.07, p = 0.04); the difference is small and only marginally significant.
- **Within-host identification.** The fixed-effects Poisson model, with a separate home-advantage term for each host, attributes +40% home goals and -33% away goals to a >2,500 m gap. This is the estimate that best separates altitude from stadium identity and club quality, because it is driven by the same host facing lowland versus highland visitors.
- **Expected versus actual.** Against a baseline that includes ordinary home advantage and team strength but no altitude term, qualifying hosts win +26.4 pp more often than expected (95% CI +23.8 pp to +28.9 pp; 279 host-season clusters) using the altitude-neutral rating, or +14.6 pp (+12.2 pp to +17.0 pp) using a plain rating that already credits the host's altitude wins to the club. The truth for a bettor lies between these, because a rating system used in practice sits somewhere between the two.
- **Independence caveat.** 1,533 league matches come from only 36 venues and 53 hosts; standard errors are clustered by host-season and the leave-one-out checks address venue dominance, but the sample is still a few dozen venue-experiments, not thousands.
- **Thresholds.** The effect grows monotonically with the cutoff (see the threshold table): raw home-win 61.2% above 2,000 m, 62.4% above 2,500 m, 72.7% above 3,000 m, 76.1% above 3,500 m. These are robustness checks, not a licence to pick the best-looking cutoff.

## 4. Match-result effect versus total-goals effect

- Home goals rise and away goals fall with the gap (Poisson rate ratios per 1,000 m: home 1.150, away 0.849; within-host model: home 1.136, away 0.865).
- Total goals: rate ratio 1.023 per 1,000 m (95% CI 1.011 to 1.035); the totals effect is concentrated at the very high Bolivian venues (mean total 3.57 in Bolivia versus 2.62 in Ecuador and 2.09 in Colombia), where thin air and weak lowland visitors coincide. An "overs" rule is therefore not supported as a general consequence of the filter.
- Model-implied probabilities in the qualifying sample: with the altitude term the home-win probability is 61.2% (home-or-draw 83.5%, home draw-no-bet 77.8%); for the same pairings with the altitude term switched off it would be 33.1% (home-or-draw 61.3%, DNB 46.4%); actual 62.4% / 84.7% / 80.3%.
- **Answer:** after adjustment the pattern supports a stronger home-win probability and a stronger home-or-draw probability; the draw share falls rather than rises, so double chance gains less than the outright home win. Total goals change little except at 3,500 m+ venues. Half-specific and late-goal effects could not be tested for club matches (no half-time or minute data in the reachable sources); they remain a hypothesis, not a finding.

## 5. Does the betting market already price it in?

Joined 2069 of 4080 Liga MX price rows to venue-verified FBref matches (score agreement 99.7%); seasons 2015-2025; qualifying matches with prices: 16. Hosts: {'Toluca': 16}. Visitors: {'Tijuana': 9, 'Veracruz': 4, 'Mazatlán': 2, 'Sinaloa': 1}. Mean Bet365 1X2 overround 1.073.

| Sample | N | Actual H / D / A | Bet365 implied (power de-vig) H / D / A | ROI home win at Bet365 | ROI home win at best price | ROI double chance 1X (synthetic) | ROI draw-no-bet (synthetic) | Mean best home odds |
|---|---|---|---|---|---|---|---|---|
| qualifying | 16 | 87.5% / 6.2% / 6.2% | 57.8% / 23.5% / 18.7% | +46.8% (SE 15.7%) | +55.6% | +15.2% | +23.4% | 1.82 |
| qualifying_league_phase_only | 15 | 86.7% / 6.7% / 6.7% | 58.3% / 23.3% / 18.5% | +44.1% (SE 16.5%) | +52.9% | +14.3% | +22.0% | 1.81 |
| toluca_home_all | 119 | 51.3% / 22.7% / 26.1% | 46.8% / 25.8% / 27.3% | +6.1% (SE 10.4%) | +13.2% | +2.8% | +6.0% | 2.31 |
| toluca_home_vs_non_qualifying | 103 | 45.6% / 25.2% / 29.1% | 45.1% / 26.2% / 28.7% | -0.2% (SE 11.7%) | +6.7% | +0.8% | +3.3% | 2.39 |
| mexico_city_hosts_vs_sea_level_visitors_gap2000_2500 | 70 | 70.0% / 18.6% / 11.4% | 55.2% / 24.2% / 20.6% | +22.5% (SE 10.4%) | +29.8% | +12.6% | +16.0% | 1.93 |
| all_matches | 2063 | 45.9% / 26.1% / 28.1% | 44.8% / 26.6% / 28.5% | -3.7% (SE 2.5%) | +2.5% | +0.3% | +0.8% | 2.45 |

Qualifying matches by season:

| Season | N | Actual H / D / A | Implied H / D / A | ROI home win (Bet365) | ROI home win (best) |
|---|---|---|---|---|---|
| 2015 | 2 | 100% / 0% / 0% | 53% / 26% / 20% | +81.5% | +90.0% |
| 2016 | 3 | 100% / 0% / 0% | 60% / 23% / 16% | +60.0% | +71.0% |
| 2017 | 1 | 0% / 0% / 100% | 44% / 28% / 28% | -100.0% | -100.0% |
| 2018 | 3 | 100% / 0% / 0% | 56% / 25% / 20% | +76.3% | +88.0% |
| 2019 | 2 | 100% / 0% / 0% | 61% / 23% / 16% | +62.5% | +71.0% |
| 2020 | 1 | 100% / 0% / 0% | 45% / 27% / 28% | +109.0% | +121.0% |
| 2021 | 1 | 100% / 0% / 0% | 53% / 25% / 22% | +82.0% | +101.0% |
| 2022 | 1 | 0% / 100% / 0% | 57% / 24% / 19% | -100.0% | -100.0% |
| 2025 | 2 | 100% / 0% / 0% | 75% / 15% / 10% | +30.0% | +34.0% |

Model versus market, out of sample (train 2015-2019, test 2020-2024, N test = 985, qualifying = 5):

| Metric | Elo only | Elo + altitude | Bet365 (de-vigged) |
|---|---|---|---|
| Log-loss, all test matches | 1.0434 | 1.0395 | 1.0210 |
| Log-loss, qualifying test matches | 0.7605 | 0.6746 | 0.6867 |
| Mean home-win prob, qualifying test matches (actual 80.0%) | 53.8% | 61.9% | 61.1% |

Market-anchored test: a logit of home win on the de-vigged market probability plus the net gap (train 2015-2019) gives a gap coefficient of +0.014 per 1,000 m (SE 0.093, p = 0.879); test log-loss market-only 0.6469 vs market + altitude 0.6465 (qualifying subset: 0.5479 vs 0.5437).

Value-bet simulation on the test seasons (back the home side at the best price when the Elo + altitude model probability exceeds the implied probability by the stated edge):

| Required edge | Bets | ROI | Bets in qualifying matches | ROI in qualifying matches |
|---|---|---|---|---|
| 0.0 | 576 | +2.4% | 3 | +40.7% |
| 0.03 | 450 | +2.1% | 2 | +111.0% |
| 0.05 | 345 | +6.0% | 2 | +111.0% |

### Reading the market results
- **Coverage.** Only Liga MX prices were reachable (Football-Data.co.uk via a public mirror: Bet365 1X2 and the cross-book maximum; no timestamps, no exchange data, no Asian-handicap or DNB quotes for Mexico). The 1X2 prices are collected shortly before kick-off, so they are late pre-match prices, not opening lines, and closing-line value cannot be measured.
- **Qualifying matches with prices: 16** (all Toluca at home to Tijuana, Veracruz, Mazatlán or Dorados). The host won 87.5% against an implied 57.8%. Flat-stake home-win return +47% at Bet365 (standard error 16%) and +56% at the best price; synthetic double-chance +15% and synthetic draw-no-bet +23%. With a standard error this large the result is consistent with anything from a large loss to a large gain; it is a curiosity, not a track record.
- **General pricing test.** In the market-anchored logit (train 2015-2019), the net gap adds essentially nothing to the de-vigged market probability (coefficient +0.014 per 1,000 m, p = 0.88); out of sample the market's log-loss (1.0210) beats the Elo + altitude model (1.0395). **In Liga MX the market already prices venue elevation about as well as a rating model with an explicit altitude term.**
- **Comparison band.** Mexico City hosts (about 2,250-2,300 m) against near-sea-level visitors, a 2,000-2,500 m gap that does *not* meet the filter, show 70.0% home wins against 55.2% implied (N = 70). This is the only pocket of apparent mispricing in the Mexican data, it sits below the user's threshold, and its standard error (10%) is still wide.
- **Where the effect is largest (Bolivia, Peru, Ecuador, Colombia, CONMEBOL cups) no price data could be obtained**, so the profitability of the filter there is **untested**. Nothing here is a simulated substitute for a real backtest.
- **Separate conclusions:** (1) plausible mechanism: yes, well documented for unacclimatized visitors; (2) demonstrated performance effect: yes, large and robust in club results after adjustment; (3) improved out-of-sample prediction over a naive rating model: yes; over the market: not shown (Liga MX says no); (4) demonstrated value after costs: no.

## 6. National-team evidence (kept separate)

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| Qualifying (gap > 2,500 m, host based at that elevation) | 133 | 57.1% | 24.8% | 18.0% | 82.0% | +0.97 | 1.87 | 0.90 | 2.77 |
| Qualifying, competitive only | 116 | 54.3% | 26.7% | 19.0% | 81.0% | +0.82 | 1.72 | 0.90 | 2.61 |
| Qualifying, friendlies only | 17 | 76.5% | 11.8% | 11.8% | 88.2% | +2.00 | 2.94 | 0.94 | 3.88 |
| Qualifying without the host-base filter | 144 | 56.9% | 24.3% | 18.8% | 81.2% | +0.96 | 1.85 | 0.89 | 2.74 |
| Same hosts vs visitors from similar elevation | 37 | 54.1% | 27.0% | 18.9% | 81.1% | +0.70 | 1.41 | 0.70 | 2.11 |
| Same hosts, competitive, similar elevation | 12 | 41.7% | 25.0% | 33.3% | 66.7% | +0.50 | 1.25 | 0.75 | 2.00 |

By host nation (qualifying):

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| Bolivia | 79 | 54.4% | 26.6% | 19.0% | 81.0% | +0.96 | 1.92 | 0.96 | 2.89 |
| Ecuador | 52 | 59.6% | 23.1% | 17.3% | 82.7% | +0.90 | 1.75 | 0.85 | 2.60 |
| Mexico | 2 | 100.0% | 0.0% | 0.0% | 100.0% | +3.00 | 3.00 | 0.00 | 3.00 |

By host nation without the host-base filter:

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| Bolivia | 83 | 55.4% | 25.3% | 19.3% | 80.7% | +1.01 | 1.96 | 0.95 | 2.92 |
| Colombia | 7 | 42.9% | 28.6% | 28.6% | 71.4% | +0.29 | 1.00 | 0.71 | 1.71 |
| Ecuador | 52 | 59.6% | 23.1% | 17.3% | 82.7% | +0.90 | 1.75 | 0.85 | 2.60 |
| Mexico | 2 | 100.0% | 0.0% | 0.0% | 100.0% | +3.00 | 3.00 | 0.00 | 3.00 |

By host city (qualifying):

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| Ambato | 2 | 100.0% | 0.0% | 0.0% | 100.0% | +1.50 | 2.00 | 0.50 | 2.50 |
| El Alto | 6 | 66.7% | 33.3% | 0.0% | 100.0% | +1.33 | 1.67 | 0.33 | 2.00 |
| La Paz | 72 | 52.8% | 26.4% | 20.8% | 79.2% | +0.86 | 1.89 | 1.03 | 2.92 |
| Oruro | 1 | 100.0% | 0.0% | 0.0% | 100.0% | +6.00 | 6.00 | 0.00 | 6.00 |
| Quito | 50 | 58.0% | 24.0% | 18.0% | 82.0% | +0.88 | 1.74 | 0.86 | 2.60 |
| Toluca | 2 | 100.0% | 0.0% | 0.0% | 100.0% | +3.00 | 3.00 | 0.00 | 3.00 |

By era (qualifying):

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| 1990-2007 | 62 | 64.5% | 24.2% | 11.3% | 88.7% | +1.35 | 2.06 | 0.71 | 2.77 |
| 2008-2026 | 71 | 50.7% | 25.4% | 23.9% | 76.1% | +0.63 | 1.70 | 1.07 | 2.77 |

By net-gap bin (all matches with computable gap since 1990, hosts of the five countries):

| Sample | N | Home win | Draw | Away win | Unbeaten | Goal diff | Home goals | Away goals | Total |
|---|---|---|---|---|---|---|---|---|---|
| (-9999, -2500] | 147 | 65.3% | 25.2% | 9.5% | 90.5% | +1.29 | 1.96 | 0.67 | 2.63 |
| (-2500, -1500] | 89 | 41.6% | 31.5% | 27.0% | 73.0% | +0.23 | 1.30 | 1.08 | 2.38 |
| (-1500, -500] | 274 | 53.6% | 28.5% | 17.9% | 82.1% | +0.79 | 1.54 | 0.76 | 2.30 |
| (-500, 500] | 819 | 51.9% | 24.9% | 23.2% | 76.8% | +0.65 | 1.56 | 0.91 | 2.47 |
| (500, 1500] | 328 | 50.0% | 24.7% | 25.3% | 74.7% | +0.69 | 1.64 | 0.95 | 2.59 |
| (1500, 2500] | 121 | 67.8% | 22.3% | 9.9% | 90.1% | +1.57 | 2.16 | 0.59 | 2.74 |
| (2500, 3500] | 103 | 61.2% | 20.4% | 18.4% | 81.6% | +1.03 | 1.84 | 0.82 | 2.66 |
| (3500, 9999] | 41 | 46.3% | 34.1% | 19.5% | 80.5% | +0.81 | 1.88 | 1.07 | 2.95 |

Adjusted (ordered logit with pre-match Elo, competitive flag; N = 1715):

| Term | Coefficient | 95% CI | SE | p |
|---|---|---|---|---|
| elo_diff100 | 0.430 | 0.374 to 0.485 | 0.028 | 0 |
| gap_pos_km | 0.313 | 0.204 to 0.422 | 0.056 | 0 |
| gap_neg_km | 0.112 | 0.001 to 0.224 | 0.057 | 0.0475 |
| q2500 | 0.867 | 0.494 to 1.240 | 0.190 | 0 |
| Poisson home goals: gap per 1,000 m | 0.140 (rate ratio 1.150) | 0.100 to 0.179 | 0.020 | 0 |
| Poisson away goals: gap per 1,000 m | -0.102 (rate ratio 0.903) | -0.159 to -0.044 | 0.029 | 0.0005 |

Goal timing (secondary; shares of each side's own goals):

| Sample | Goals | Home goals | Away goals | Home share 2nd half | Away share 2nd half | Home share after 75' | Away share after 75' |
|---|---|---|---|---|---|---|---|
| qualifying | 305 | 199 | 106 | 0.583 | 0.547 | 0.251 | 0.264 |
| low_gap_same_hosts | 21 | 15 | 6 | 0.867 | 0.5 | 0.333 | 0.167 |
| all_five_countries | 2935 | 1914 | 1021 | 0.555 | 0.579 | 0.226 | 0.231 |

National-team matches since 1990 hosted at altitude in the five countries by a side based at that elevation (Bolivia, Ecuador; Colombia's team is based in Barranquilla and is shown separately without the base filter): home win 57.1%, draw 24.8%, away win 18.0% (N = 133). The adjusted gap coefficient (0.31 per 1,000 m, 95% CI 0.20 to 0.42) is of the same order as in club football, with the caveat that a national team's "usual elevation" is a weak proxy because most players are club-based elsewhere. Goal timing (secondary): the share of home goals after the 75th minute in qualifying matches (0.251) is close to the all-match share (0.226); no late-goal skew is visible.

## 7. Upcoming fixtures (2026-09-29 to 2026-11-28)

**Important limitation.** Live fixture verification was possible only until this session's web-search allowance ran out, and page fetching was blocked throughout. The tables below therefore contain (a) fixtures located and sourced by the Liga MX and Bolivia searches that ran before the cut-off, (b) the CONMEBOL knockout calendar from a dated public dataset (pairings not yet filled), and (c) a structural pairing matrix for Peru, Ecuador and Colombia, whose 2026 schedules could not be retrieved. Every entry states its verification status; kickoff times are converted to America/Los_Angeles with PDT (UTC-7) before 2026-11-01 and PST (UTC-8) from that date.





## 8. Practical verification checklist


1. **Actual venue**: confirm on the day that the match is at the expected stadium (sanctions, works, neutral grounds and municipal disputes move games; e.g. Always Ready's tenure at Villa Ingenio was reported as uncertain in September 2026). Recompute the gap from the DEM value of the confirmed venue.
2. **Host acclimatization**: confirm the host trains and normally plays at that elevation; a nominal 'home' team using a temporary highland ground gets no altitude benefit.
3. **Visitor baseline and exposure**: check the visitor's actual base (training ground, not only the registered city) and whether it has played at 2,000 m+ in the previous two weeks or held a pre-acclimatization camp; a visitor arriving from another highland match is not 'unacclimatized'.
4. **Arrival timing**: same-day or previous-evening arrival (the strategy most visiting clubs use) versus 3-7 days at altitude (usually the worst window); note anything the club announces.
5. **Lineup strength, rest and incentives**: injuries, suspensions, rotation (continental visitors often rotate for highland league trips), fixture congestion, cup ties, and whether the host has anything to play for.
6. **Weather**: cold, rain or hail at 3,000 m+ affects both sides; check the forecast.
7. **Market price**: take the best available price, remove the margin, and compare with a model estimate that already includes ordinary home advantage; only a positive expected value after margin, fees and liquidity is a bet. For draw-no-bet, evaluate the void-on-draw payoff, not the home-win payoff.
8. **Market type**: regulation-time result markets only; 'to qualify' or 'to lift the trophy' markets settle on different events.


## 9. Data, methods and limitations



### Environment constraints that shaped the research (read first)
- **Live web research was cut off part-way.** This session had a hard cap of 200 web-search calls, shared by every research agent; the cap was reached roughly 25 minutes into the fixture and literature sweeps. All page fetching (Wikipedia, PubMed, journals, league sites, ESPN, Flashscore, OddsPortal, etc.) was blocked by the environment's network egress policy for the whole session. Only GitHub-hosted files, PyPI and the public AWS terrain-tile bucket were reachable.
- Consequences, stated per section below: (a) the historical club backtest, the national-team analysis and the venue elevations rest on downloadable datasets and a digital elevation model, so they are complete and reproducible; (b) the literature section combines search results obtained before the cap (two lenses) with model recall cross-checked by three independent agents, and every citation is labelled accordingly; (c) the fixture watchlist contains only fixtures that were located and sourced before the cap (Liga MX, Bolivia) plus the CONMEBOL knockout calendar from a dated public dataset; Peru, Ecuador and Colombia fixtures could not be retrieved and are covered by a structural pairing matrix instead.
- To complete the watchlist and re-verify citations, rerun the fixture and literature stages in a session with a higher search allowance (`CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`) or with network egress enabled for the league and reference sites.

### Data sources actually used
| Dataset | Content used | Coverage | Access route |
|---|---|---|---|
| FBref match results mirrored by `JaseZiv/worldfootballR_data` (GitHub releases) | Domestic top flights of Mexico, Peru, Ecuador, Colombia, Bolivia: date, teams, score, **actual venue per match**, round | 2014/15 to Sept 2025 (Bolivia 2024 season mostly missing in the mirror) | raw GitHub download |
| Same mirror, cup files | Copa Libertadores 2014-2025 (partial 2025), Copa Sudamericana 2014-2024 with venues and extra-time notes | 2014-2025 | raw GitHub download |
| `xgabora/Club-Football-Match-Data-2000-2025` (mirror of Football-Data.co.uk) | Liga MX 1X2 prices: Bet365 and the cross-book maximum; Over/Under 2.5 where present | Liga MX 2012-2024 (4,080 matches) | raw GitHub download |
| `martj42/international_results` | All senior men's internationals with city and neutral flag; goal minutes; shootouts | 1872 to Aug 2026 | raw GitHub download |
| AWS Terrain Tiles (`elevation-tiles-prod`, SRTM-derived 1 arc-second HGT) | Ground elevation at each stadium coordinate | global | S3 public bucket |
| `openfootball/south-america` (auto-updated 2026-09-21) | 2026 Copa Libertadores calendar (dates of semifinals and final; pairings not filled) | 2026 | git clone |

### Elevation registry method
1. Every venue string in the match data (187 domestic, 139 additional continental) was resolved to a stadium, city and coordinates by research agents; where web search was unavailable the identification came from model recall and is labelled as such.
2. Every coordinate was checked against the SRTM digital elevation model. A record is accepted when the DEM elevation lies within 80 m of the published figure (or no published figure exists and the identification is confident). Disagreements were re-derived by a second agent, and the analyst's own provisional coordinates served as a third candidate. All candidates are kept in `data/registry/venue_registry_candidates.csv`; the chosen record and its basis are in `data/registry/venue_registry.csv`.
3. The DEM value is used as the venue elevation in all analyses; published figures are reported alongside.
4. **Visitor baseline** = elevation of the visiting club's principal home venue in that season (its modal venue across all competitions in the data). This is a **proxy for training elevation**, labelled as such; a separate club training-ground table (`data/registry/club_training_bases.csv`) records where the training ground is confirmed to differ.
5. **Home acclimatization check**: a host is treated as acclimatized only if the match venue is within 500 m of the host's own principal venue that season; relocated 'home' matches far from the host's usual elevation are excluded from the main sample and counted separately.
6. **Recent altitude exposure**: from the match data itself, whether the visitor played any match at 2,000 m or higher in the previous 14 days.

### Statistical method (club matches)
- Regulation-time results only: cup matches decided after extra time are excluded because the source score includes extra-time goals; league matches have no extra time.
- Raw tables: home win, draw, away win, home unbeaten, goal difference, home goals, away goals, total goals, over 2.5, for the qualifying sample (net gap > 2,500 m, host acclimatized), for the same hosts against visitors from similar elevation, for every 500 m gap bin, and by competition, country, venue and host.
- Team strength: an Elo rating computed chronologically from all matches in the data (domestic and continental pooled), using only matches before each fixture. Two variants: a plain Elo (which credits a host's altitude wins to the club and therefore understates the altitude effect) and an 'altitude-neutral' Elo in which part of the expected result at a high venue is credited to the venue; the gap coefficient used for that credit is estimated jointly by iteration.
- Adjusted models on seasons 2015-2025: ordered logit on the match result with Elo difference, competition dummies and the net gap (continuous in km above the visitor's base, a >2,500 m indicator, and 500 m bins); cluster-robust logits for 'home win' and 'home or draw'; cluster-robust Poisson models for home goals, away goals and total goals; a fixed-effects Poisson model with attack and defence effects per team, a **home-advantage effect per host**, competition and season effects, which identifies the altitude effect from variation in visitor elevation *within* the same host and so separates altitude from stadium identity and club quality. Standard errors are clustered by host-season; the excess of actual over expected results is bootstrapped by host-season clusters.
- Robustness: alternative thresholds 1,500-3,500 m (labelled as robustness only), leave-one-league-out, leave-one-host-out, league vs continental, early vs late seasons, visitor recent-exposure split.
- Out-of-sample test: models fitted on 2015-2020 and scored on 2021-2025 by log-loss and Brier score, with and without altitude terms; for Liga MX, also against the bookmaker's de-vigged probabilities.



## 10. Final answer

**Does backing home teams with more than a 2,500 m net elevation advantage demonstrate value beyond ordinary home advantage and market expectations, or is it a plausible screening factor whose betting value remains unproven?**

The performance effect is real, large and robust: after adjusting for team strength and each host's ordinary home advantage, hosts with a >2,500 m net gap win roughly +14.6 pp to +26.4 pp more often than expected, score more and concede less, and the effect strengthens above 3,000 m. The betting value is **unproven**. The only market that could be tested (Liga MX) prices venue elevation about as accurately as an explicit altitude model, and its 16 qualifying matches are far too few to establish an edge; the markets where the effect is largest (Bolivia, Peru, Ecuador, Colombia, CONMEBOL) could not be tested for lack of price data. Use the filter as a screen that flags matches where a rating model *without* an altitude term will be badly calibrated, then bet only when the de-vigged price is still below a model estimate that already includes altitude, host acclimatization, visitor exposure and lineup information.

## Appendix: files

- `research/altitude/analysis/` — `common.py` (loaders, Elo), `club_backtest.py`, `odds_backtest.py`, `national_teams.py`, `build_registry.py`, `watchlist_assemble.py`, `report_tables.py`, `build_report.py`.
- `research/altitude/tools/dem_elev.py` — SRTM elevation lookup (AWS Terrain Tiles).
- `research/altitude/data/registry/` — venue registry (chosen record per venue, all candidates, club training bases).
- `research/altitude/output/` — results JSON, match-level tables (`matches_with_gap.csv`, `qualifying_matches.csv`, `ligamx_qualifying_with_odds.csv`, `national_team_qualifying_matches.csv`), watchlist files, rendered tables.
- `research/altitude/workflows/` — the multi-agent workflow scripts used for the literature sweep, fixture search and venue registry.
