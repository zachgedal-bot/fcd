# Altitude edge model: parameters and what they rest on

Research sweep run 2026-09-20 (two completed literature agents; the adversarial
verification stage did not run, so treat every row as unverified against full
text). Direct fetches of journals and bookmaker sites were blocked from the
research sandbox; figures come from indexed abstracts and previews.

| Parameter | Low | Base | High | What it rests on |
|---|---|---|---|---|
| Raw altitude effect (goals per km, home team) | 0.2 | 0.5 | 0.6 | McSharry 2007 BMJ: ~0.5 goal-difference per 1,000 m over 1,460 South American internationals (includes generic home advantage). Cabrera-Hernandez 2023 (2,039 Libertadores matches): home goals 1.89 when the visitor ascends ~3,600 m, home-win odds ratio 2.5. Van Damme & Baert 2019: +1.1 pp home-win per 100 m in UEFA club ties (low altitudes, other controls). Chumacero 2009 (72 WCQ): not significant once team quality is controlled. |
| `k_goals_per_10pct_hir` | 0.15 | 0.35 | 0.90 | Physiology layer gives ~5.4% HIR per km on arrival. Cabrera's ascending effect (~+0.6 goals over ~3.3 km) implies ~0.18 goals/km, i.e. ~0.35 goals per 10% HIR. McSharry's raw figure would imply ~0.9 but is confounded by home advantage. |
| `residual_share` (fraction of the effect NOT in the closing line) | 0.0 | 0.25 | 0.5 | No published study regresses results on bookmaker odds plus altitude, so this is a prior. Market evidence that altitude is priced heavily: Bolivia favourite at El Alto vs Uruguay (2.35-2.40) and near coin-flip vs Colombia; Bolivar 47.7% implied vs Flamengo in La Paz. Evidence it is not fully priced: Fischer & Haucap 2022 (Kyklos) show bookmakers lag structural home-advantage shifts; open-source CupCast model gains log-loss from an altitude term learned on 1,098 matches; LDU priced 3.3-3.55 v Palmeiras in Quito and won 3-0. Winkelmann et al. 2024: single-season inefficiencies are common and non-persistent. |
| `descending_goals` (penalty on an altitude team playing >1,500 m below home) | 0.0 | 0.15 | 0.40 | Cabrera-Hernandez 2023: descending three categories raised home goals to 2.62 and home-win odds ratio to 5.5, larger than the ascending effect. Cabrera 2021: descending hurt results more than ascending. Anecdotes 2025: Bolivar lost 2-4 in Asuncion and 1-2 in Lima; LDU lost 0-4 in Sao Paulo after 3-0 at home. Bookmakers are least likely to model this explicitly, so residual share for descending is plausibly higher than for ascending. |
| `habituation_discount` (Liga MX and Andean domestic leagues) | 0.3 | 0.5 | 0.8 | Alanis et al. 2022: one Liga MX club ran flat distances across altitude zones over 130 matches. Ecuador moved marquee qualifiers to Guayaquil because most of its squad now lives at low altitude, the reverse effect. |
| Physiology (`physio`) | | | | The Altitude FC model (`altitude_fc/altitude_model.py`, evidence IDs in `altitude_fc/evidence_table.csv`): VO2max -6.3%/km above 300 m (E18); HIR = 0.7 x VO2 deficit (anchored to E03/E04/E31); repeated-sprint recovery = 0.3 x (E22-E24); acclimatisation 0.40 fast (tau 3.5 d) + 0.25 slow (tau 21 d), 0.35 never recovered (E19, E02, E06); top speed +0.3%/km (E26/E27). |

## Where the residual edge is most plausible

1. **Regime changes.** Bolivia's move from La Paz (3,640 m) to El Alto (4,150 m) in Sept 2024: 4W-2D-0L at El Alto vs 1W-2L at La Paz, two wins as ~28% underdog (Colombia, Brazil). Ecuador moving big games to sea level. Fischer & Haucap's ghost-game evidence says books absorb such shifts with a lag.
2. **1X2 home-underdog prices at extreme altitude.** Whelan 2024: 1X2 carries favourite-longshot bias while Asian handicap is efficient. The anecdotal hits (Bolivia +250 v Brazil, LDU 3.4 v Palmeiras, Bolivar v Flamengo) are all altitude home dogs against sea-level giants. Small n; CLV, not ROI, is the test.
3. **Descending legs** of two-legged ties (see above).
4. **Arrival timing** is not quantified anywhere and is not visibly priced; it needs the days-since-arrival feature and club press reporting.

## What the research did not find

- Any odds-controlled altitude coefficient (the direct test). `backtest.py` runs it on football-data.co.uk Mexico data (Pinnacle closing odds from 2012). Do that before trusting `residual_share`.
- Second-half or late-goal evidence at altitude beyond anecdotes (Always Ready 6-1 v Sporting Cristal with five second-half goals).
- Exchange liquidity for Bolivian, Ecuadorian, Peruvian league matches. Assume limits are small.
- Per-venue Liga MX home-advantage splits (fetches blocked).

## Data sources for the backtest

- football-data.co.uk `new/MEX.csv`: Liga MX results with Pinnacle and average closing 1X2 odds since 2012. Free.
- the-odds-api.com historical endpoint: CONMEBOL, Bolivian, Ecuadorian leagues, paid tiers.
- Betfair historical data: per-market files, paid.
- Kalshi and Polymarket US APIs: current prices only.
