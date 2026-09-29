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