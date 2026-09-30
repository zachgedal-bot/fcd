# Deploying After Hours as its own service

The Athlemix site is built in ChatGPT Sites, whose source is not reachable from
outside that editor. Rather than porting into it, After Hours runs as a small
standalone service and athlemix.com links to it (or a subdomain points at it).

The service is `server/server.js`: plain Node 18+, no dependencies. It serves
the desks, gates them server-side with an invite code plus an 18+ attestation,
and exposes `/api/fixtures` and `/api/props`, which call The Odds API with a key
that never leaves the server.

## 1. Pick a host and deploy

Any of these works from this repo as-is:

| Host | How |
|---|---|
| Render | New → Blueprint → this repo. `render.yaml` defines the service. Set `ODDS_API_KEY` and `AFTER_HOURS_INVITE_CODES` in the dashboard when prompted. |
| Fly.io | `fly launch --copy-config --no-deploy`, then `fly secrets set ODDS_API_KEY=... AFTER_HOURS_INVITE_CODES=... SESSION_SECRET=$(openssl rand -hex 32)`, then `fly deploy`. |
| Railway / anything with Docker | Build the `Dockerfile`; set the env vars from `.env.example`. |
| Bare VPS | `node server/server.js` behind Caddy or nginx with TLS; set `TRUST_PROXY=1` and `CLIENT_IP_HEADER=x-real-ip`. |

`TRUST_PROXY` is the number of proxy hops in front of the service (1 for the host alone, 2 with Cloudflare in front); the client IP used for rate limiting is read that many X-Forwarded-For entries from the right, never the client-supplied left end. Set `CLIENT_IP_HEADER` to the platform's authenticated header when it has one.

Health check: `GET /healthz` returns `{ok, gated, provider_configured}`.

## 2. Odds provider

Get a key at https://the-odds-api.com. The free tier (500 requests/month) is
enough to smoke-test but not to run: each refresh costs `markets × regions`
credits per league, so with `h2h,totals` and `us,eu` that is 4 credits per
league per refresh. With the 300-second cache and roughly six leagues in
season, a day of continuous traffic is about 7,000 credits, so the 20K/month
plan is the realistic floor. Player props on `/api/props?sport=<key>&event=<id>` cost extra per event and, per the provider's coverage notes, soccer player props are posted only for EPL, Ligue 1, Bundesliga, Serie A, La Liga and MLS by US books. The Props Desk's "Pull from feed" button calls this endpoint for a match on the board and reports an empty answer as exactly that; for Liga MX and the Andean leagues expect empty. The provider does not tag players by team, so pulled lines land in the home box with a note to move the away side across.

Leagues are discovered at start from the provider's `/v4/sports` list (free
call) using the patterns in `server/adapter.js`; pin them with
`ODDS_SPORT_KEYS=soccer_mexico_ligamx,soccer_conmebol_copa_libertadores` if you
want a fixed set. `GET /api/status` shows which leagues matched and the quota.

### Coverage, honestly

Verified against the provider's sports list and community mirrors (Sept 2026):

| League | On The Odds API? |
|---|---|
| Liga MX | yes, `soccer_mexico_ligamx` |
| Copa Libertadores / Sudamericana | yes |
| MLS | yes |
| CONMEBOL World Cup qualifiers | yes, in season only |
| **NWSL** | **no** |
| **Bolivia, Ecuador, Colombia, Peru domestic** | **no** |

So out of the box the live Altitude Book covers Liga MX and the CONMEBOL
cups. For NWSL and the Andean domestic leagues you need a second provider
(OddsAPI.io, BetsAPI, OpticOdds or Sportradar all list them) and a second
adapter in `server/adapter.js` with the same `normaliseEvent` output shape;
the page needs no change. Plan prices as of Sept 2026: free 500 credits,
$30 for 20K, $59 for 100K, $119 for 5M per month, resetting on the 1st.

## 3. Gate

Set `AFTER_HOURS_INVITE_CODES=CODE1,CODE2` and a long `SESSION_SECRET`. The
server refuses to start gated without a real secret. Sessions are HttpOnly,
SameSite=Lax, Secure behind TLS, signed with HMAC-SHA256, and last
`SESSION_HOURS` (default 7 days). `/leave` clears one. Ten failed attempts per
IP per ten minutes are allowed.

This gate controls access; it is not age verification. If Athlemix has real
account-level 18+ verification, front this service with it (reverse proxy
behind the app's session) and leave the codes unset.

## 4. Link it from Athlemix

Either add a nav item on athlemix.com pointing at the service URL, or create a
CNAME `afterhours.athlemix.com` to the host and set `HOME_URL=https://athlemix.com`
so the "← AthleMix" link returns home.

## 5. Verify

```
curl -s https://<host>/healthz
curl -s https://<host>/api/status -b "ah_session=..."   # after entering once in a browser
npm test                                                # adapter unit tests
```
Without a key, `/api/fixtures` answers 503 `provider_not_configured` and the
book shows "Lines unavailable". That is the intended state, not a bug.
