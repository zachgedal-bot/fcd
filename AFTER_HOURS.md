# Athlemix After Hours

The members-only back room of AthleMix: `after-hours.html`. Three desks
and a calculator, all client-side, all illustrative until backtested.

Open it: serve the folder over HTTP (`python3 -m http.server`) and visit
`after-hours.html`. Invite code at the rope: the height in metres of the highest
ground in the book. `after-hours.html?code=4090` is a shareable invite link.
The rope is cosmetic; nothing behind it is protected.

## The desks

| Desk | What it does | Model source |
|---|---|---|
| Altitude Book | De-vigs the closing 1X2, backs out goal expectancies, applies the visitor's high-intensity-running loss at the venue as a goal shift scaled by the residual share you believe the market has not priced, and ranks lines by EV. Drop a fixtures CSV or add lines by hand. | `altitude_edge/model.py`, `physio.py`, `venues.py` |
| Lineup Desk | Paste each side's projected XI with ratings (EA FC, FCD score, any scale) and the reference XI the market is pricing. Weaker XI scores less and concedes more; big skews are flagged; EV vs the main line. | `altitude_edge/lineup_props.py` |
| Props Desk | Player shot lines to Poisson expected shots, to xG by position, to team xG, blended with the market's goal expectancies, re-priced against 1X2, totals and anytime-scorer odds. | `altitude_edge/lineup_props.py` |
| Courtside | Per-match EV of trading NWSL live markets from the stands. | `nwsl_courtside/courtside_model.py` |

The browser port in `after-hours.js` matches the Python to three decimals
(checked under Node for all three desks).

## Running the scanner off-line

```
cd altitude_edge
python3 fetch_espn.py --from 20260925 --to 20261005 --out fixtures.csv      # fixtures + ESPN BET odds where published
python3 fetch_polymarket.py --tags liga-mx col1 --out fixtures_pm.csv       # Polymarket mid prices
python3 scan.py --fixtures fixtures.csv --params params.json --min-diff 800  # ranked discrepancies
python3 backtest.py --results MEX.csv                                       # residual altitude effect after Pinnacle's closing line
```

The fetchers need open internet; they did not run from the authoring sandbox,
whose egress policy blocks ESPN, Polymarket, odds sites and journals. The demo
fixtures in `fixtures_demo.csv` were assembled from search results on
2026-09-20 and two of the three priced lines have back-filled draw/away odds.

## What the research said

Full notes with sources: `altitude_edge/PARAMETERS.md` and
`nwsl_courtside/README.md`. Short version:

- **Altitude is real and heavily priced.** Bookmakers make Bolivia favourite at
  El Alto against mid-table sides and price Bolivar above Flamengo in La Paz.
  No study has tested for a residual after the closing line; the base-case
  residual share of 0.25 is a prior, and `backtest.py` on football-data.co.uk's
  Liga MX file is the first real test.
- **Where residual edge is most plausible:** venue regime changes (Bolivia's
  2024 move to El Alto, Ecuador moving big games to Guayaquil), descending legs
  of two-legged ties, and 1X2 home-underdog prices at extreme altitude. Small
  samples; judge by closing-line value, not ROI.
- **Courtsiding NWSL on Polymarket US:** the mechanics favour it more than a
  Betfair-style exchange would (no documented in-game delay, fills in ~100 ms,
  prices seen lagging Kalshi by up to 5 s after scores), but NWSL live depth is
  tens to low hundreds of dollars against a break-even of one to four thousand
  per goal. Negative EV with travel in the base case.

## Not advice

Every number is a scenario. No bets are placed here. Venue terms, exchange
rules and state law apply to anything you do with it.
