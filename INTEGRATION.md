# Porting After Hours into the AthleMix app

Source of truth: branch `claude/serene-wozniak-48yawh` of the public repo
https://github.com/zachgedal-bot/fcd (pull request #4). Everything After Hours
needs is static: no build step, no server code, no secrets, no npm packages.
It runs from any static path and talks to no backend unless you wire one.

## Files to copy (keep the relative layout)

| Path | Role |
|---|---|
| `after-hours.html` | The page. Sections: Altitude Book, Match Cards, Props Desk, High Ground, Courtside, House Rules. |
| `after-hours.css` | Styles. Self-contained; uses two Google Fonts (Cormorant Garamond, IBM Plex Mono) via a `<link>`; falls back to Georgia/monospace if blocked. |
| `after-hours.js` | The model, dependency-free. Exposes `window.AfterHoursModel`. Same math as the Python in `altitude_edge/` (verified to 3 decimals). |
| `after-hours-ui.js` | Page wiring. Fetches the JSON files below by relative path. |
| `altitude_edge/venues.json` | Home-venue altitudes for Liga MX, Bolivia, Ecuador, Colombia, Peru, NWSL, CONMEBOL cup clubs and national teams. |
| `altitude_edge/fc_ratings_nwsl.json` | EA SPORTS FC 25 women's ratings for 347 NWSL players, 14 clubs, positions and face stats. |
| `altitude_edge/fixtures_demo.json` | Demo lines for the Altitude Book. Replace with a live feed (format below). |
| `altitude_fc/altitude_fc_cards.html` | The Altitude FC two-team lab, linked from the nav as "The lab". Standalone page with its own inline CSS/JS. |

Optional, for reference only (not needed at runtime): `altitude_edge/*.py`,
`altitude_fc/altitude_model.py`, `altitude_fc/evidence_table.*`,
`nwsl_courtside/`, `AFTER_HOURS.md`, `altitude_edge/PARAMETERS.md`.

## Mounting it

All port-specific settings live in one block at the bottom of `after-hours.html`:

```html
window.AFTER_HOURS_CONFIG = {
  gate: true,            // set false: the host app's own account/adult guard protects the route
  fixturesUrl: '...',    // the adapter endpoint; used by the boot load AND the Reload button
  dataBase: '',          // prefix if altitude_edge/*.json is served from elsewhere
  homeUrl: 'index.html', // the app's real home route, e.g. '/'
  labUrl: 'altitude_fc/altitude_fc_cards.html'
};
```

When `fixturesUrl` fails or returns nothing the book shows an explicit
"Lines unavailable" row; nothing is simulated.

1. Copy the files into a static folder served by the app, e.g. `public/after-hours/`, preserving `altitude_edge/` and `altitude_fc/` as subfolders next to `after-hours.html`.
2. Add a route or link to `/after-hours/after-hours.html` from the existing navigation. Do not change existing pages.
3. The invite gate is front-end only (browser codes and localStorage). In the app, set `gate: false` and protect the route with the app's real account and adult-access guard; hiding the nav link is not enough.
4. If the app already restricts market pages to adult accounts, apply the same guard to this route.

## Feeding the Altitude Book from the existing odds adapter

Set `fixturesUrl` to an endpoint served by the app's odds adapter that returns
this shape (an array, or `{"fixtures": [...]}`); both the boot load and the
Reload button use it:

```json
[
  {"date": "2026-09-26", "league": "Liga MX", "home": "Cruz Azul", "away": "Toluca",
   "odds_h": "1.95", "odds_d": "3.40", "odds_a": "3.90",
   "odds_over25": "1.85", "odds_under25": "1.95",
   "days_since_arrival": "1", "venue_alt": "", "note": "provider name, timestamp"}
]
```

Decimal odds as strings or numbers; empty odds are allowed (the row shows
"needs odds"). Team names are matched against `venues.json` with alias and
substring fallback; add missing clubs to `altitude_edge/venues.py` and
regenerate `venues.json` (`python3 -c "import venues"` block at the bottom of
`venues.py` shows how), or extend the `aliases` map in the JSON directly.

Keep the provider key on the server. The page should only ever receive the
JSON above. Show an honest "needs odds" or error state when the feed is empty;
do not substitute sample data and label it live.

## Match Cards and Props Desk inputs

Connecting `fixturesUrl` makes only the Altitude Book live. Match Cards reads
`fc_ratings_nwsl.json` and the venue table but its odds are typed in; Props
Desk takes player lines typed or pasted (format in the page copy). Both can be fed from the adapter later through the same
`window.AfterHoursModel` functions: `priceFixture`, `priceLineups`,
`priceProps`, `adjustedCard` (see the bottom of `after-hours.js` for the API).

## Verifying the port

Open the page over HTTP (not `file://`), enter the code, and check:
Altitude Book shows the demo rows; Match Cards lets you pick Utah Royals FC
vs KC Current and shows KC's altitude-adjusted OVR below its reference;
The lab link opens `altitude_fc/altitude_fc_cards.html`. Console should be
clean; the only network calls are the three JSON files and the fonts.
