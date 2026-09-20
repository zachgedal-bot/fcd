# NWSL courtside model

`python3 courtside_model.py` prints per-match and per-season EV for trading NWSL
live markets from inside the stadium, ahead of the broadcast, using
`params.json`. Parameters are set from the 2026-09-20 research sweep (five
completed agents; verification and synthesis stages did not run, so the rows
below are unverified against primary pages, which were blocked from the sandbox).

net per match = goals × f × L × r × (1 − fee) − travel − risk

| Parameter | Low | Base | High | What it rests on |
|---|---|---|---|---|
| f, share of goals you get filled on at a stale price | 0.10 | 0.35 | 0.60 | Polymarket US (polymarket.us, CFTC DCM) documents **no in-game order delay**; the only latency rule is a 5-second stale-order rejection. A first-hand Sept 2026 test saw polymarket.us fills in 60-120 ms. Polymarket global (polymarket.com) has a 3-second sports taker delay and cancels resting orders at kickoff; Crypto.com delays retail 3 s; Kalshi filed for delay authority (Dec 2025) with no confirmed rollout. Against that: designated market makers under the 2026 Market Maker Program quote in-play off Pinnacle/OpticOdds and Sportradar official data (Sportradar holds NWSL's official data rights via IMG Arena), a professional Polymarket maker says in-stadium observers hold an edge of seconds, a Reddit courtsider puts it at 0.5-3 s, and NBA in-game arbs on Polymarket global are corrected by bots in a median 3.6 s. |
| L, dollars resting at the stale price per goal | 30 | 150 | 800 | No NWSL live-depth measurement exists on Polymarket US. Kalshi NWSL game markets (Aug 2026): 539-1,239 contracts deployable at a 5-7c spread with $6-$46 of 24-hour volume; 84.8% of Kalshi markets had zero 24h volume. Polymarket global NWSL: ~$0.5-0.6M per team per season across ~170-190 markets, single-match markets as low as $79. Observed Polymarket US live depth ranged from 7/13 contracts (an NFL total) to 1,155 at the touch (an MLB moneyline). Per-game live exposure caps exist (e.g. WNBA cut to $2,000). |
| r, return per dollar filled | 0.25 | 0.45 | 0.70 | Matched at ~2.5 before the goal, hedged at ~1.65 after; Polymarket US prices were seen lagging Kalshi by up to 5 s after scoring plays, so a fill against a stale quote is plausible but the size is the problem, not the price. |
| fee | | 0.017 | | Polymarket US taker fee 0.0695 × p × (1 − p) per contract (Sept 17, 2026 schedule): 1.7% of notional at p = 0.5. |
| risk cost per match | 50 | 100 | 400 | Courtsiding is not a crime in the US; venue tickets are revocable licences (Kansas City Current, Washington Spirit terms bar transmitting live data), enforcement is ejection and bans (USTA: 20-year bans in 2016). Polymarket US rules bar trading on confidential information in breach of a duty, which observing a public goal is not. State exposure: Polymarket US is unavailable or contested in NV, MI, MA, MD, OH, MT, IL, AZ, TN and Missouri issued cease-and-desists on Sept 18, 2026, which takes Boston, Chicago and Kansas City home games off the table. |

## Result

| Case | f | L | r | Net per match, flying | Net per match, local |
|---|---|---|---|---|---|
| Low | 0.10 | $30 | 0.25 | about −$750 | about −$110 |
| Base | 0.35 | $150 | 0.45 | about −$730 | about −$90 |
| High | 0.60 | $800 | 0.70 | about +$125 | about +$1,140 |

The user's mechanics point stands: Polymarket US is a no-delay order book and
the exchanges that added delays did so because the latency edge is real.
What kills the trade is NWSL depth, not the latency. Break-even needs roughly
$1,000-4,000 of stale liquidity per goal at these capture rates, and NWSL live
books are two orders of magnitude thinner. The same trade on a deep market
(NBA, NFL, MLB) is what the profitable Polymarket accounts run, and they run it
with bots on data feeds, not from a seat.
