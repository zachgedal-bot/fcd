# athlemix.com: dead-end audit (2026-09-30)

Source of evidence: two screenshots of the live site taken by the owner on
2026-09-19 (the `/markets` page signed in, and the home feed signed out), plus
the route inspection ChatGPT ran against the public site on 2026-09-20. The
site itself is denied by this session's network policy, so nothing below was
re-fetched. Items are marked **confirmed** (visible in the evidence) or
**verify** (needs the auditor run: `node tools/site-audit.js https://athlemix.com <pages>`).

## Confirmed dead ends

| # | Where | What a user hits | Fix |
|---|---|---|---|
| 1 | `/markets` · Matches tab | "Live feed isn't connected yet. The MLS odds and PrizePicks adapter is ready for a provider account. No odds, lines, or rankings are being simulated." The tab's only content is an error state. | Replace the tab with a link to the After Hours service (`DEPLOY.md`), or wire the app's adapter to the same provider key. Until then hide the tab from navigation rather than landing users on an error. |
| 2 | `/markets` · "Refresh data ↻" | Refreshes a feed that has no source; the page state cannot change. | Hide the control while no provider is configured. |
| 3 | `/markets` · "View sourced player performance →" | Links out of an empty page to a page that does not exist in the evidence. | Point it at the Plus profile screen (`premium/index.html`) or remove it until the target exists. |
| 4 | `/markets` · "Team odds" and "PrizePicks props" tabs | Same adapter as the Matches tab; nothing can render behind them. | Same as 1. |
| 5 | Home (signed out) · "Scout players ↗", "Pro ↗", "College ↗", "Youth ↗" chips | Arrow chips imply an external link; on the same site they should be internal navigation. Signed-out users likely land on Sign in with no return path. | Use in-app routes and preserve the intended destination through sign-in. |
| 6 | Home · "From clubs, colleges and soccer publishers" feed | Every visible card is an ESPN Premier League or LaLiga story; none is club, college or youth content, and none relates to the recruiting audience. | Filter the feed to the leagues the audience follows (NWSL, MLS, ECNL, college) or change the copy. |
| 7 | `/markets` · "ADULT ACCOUNTS · 18+" label | The label is the only age control visible; there is no attestation step in the evidence. | Gate the route behind a real 18+ attestation on the account (see `premium/IMPLEMENTATION.md` §4). |

## Verify with the auditor

| # | Route | Why it is suspect |
|---|---|---|
| 8 | `/scout` · Players, Teams, Coaches, All rosters tabs | The Scout header was rendered with the Markets panel beneath it in the screenshot; unclear whether the four tabs have content. |
| 9 | Sidebar · Rankings, College radar, Reels, Community, Records archive | Five destinations with no evidence of content; the classic "void" candidates on a young app. |
| 10 | `/inbox` and `/profile` signed out | Should redirect to Sign in and back; verify no blank page. |
| 11 | "Your profile" button on `/markets` | Visible while the header shows Sign in on the home page; verify it does not open an empty profile for anonymous users. |
| 12 | Footer, legal, privacy, terms | Not visible in either screenshot; a betting-adjacent page with no terms link is a compliance gap. |
| 13 | Every `↗` chip and "Read story ↗" link | Confirm each opens the intended target and external ones open in a new tab. |

## How to run the full walk

```
npm i playwright-core
node tools/site-audit.js https://athlemix.com / /scout /markets /inbox /profile /rankings /college-radar /reels /community /records
```

The auditor reports console errors, failed requests, 4xx/5xx responses, broken
links and anchors, buttons that do nothing when clicked, empty panels or
canvases, and horizontal overflow, at desktop and phone width, per page.
Adjust the route list to the app's real paths; unknown routes show up as 404s
in the report, which is itself a finding.
