# LAFC attacking-direction study: verified dataset, pilot status and plan

**Verdict (2026-09-29): insufficient verified data on attacking direction.** No LAFC home match in this file has a
verified physical attacking end, so the four-group (half × toward/away from the 3252) comparison cannot be run.
Everything that does not depend on direction has been built and analysed from source-linked match reports:
half-by-half scoring, first-half under rates, 15-minute buckets, and the 60th-minute game-state baselines.
Those numbers are in `out/summary.md` and reproduced below.

## What is in this folder

| File | Contents |
|---|---|
| `data/raw_events.jsonl` | One record per LAFC home match with goal minutes, scorers, penalties/own goals, red cards, HT/FT score, attendance, kickoff, source URLs, confidence and open to-dos. |
| `data/matches.csv` | One row per match (156): scores by half, red cards, venue, fans flag, `direction_status` (all `unavailable`). |
| `data/goals.csv` | One row per goal (498) with minute, added time, half, scorer, kind. |
| `data/direction_labels.csv` | Empty label sheet, one row per match, to be filled from kickoff footage. |
| `scripts/build_dataset.py` | Rebuilds the CSVs from the raw file. |
| `scripts/analyze.py` | Runs the analysis; computes the four-group split automatically once labels exist. |
| `scripts/youtube_kickoff_frames.py` | Video-to-frames pipeline for direction coding (needs YouTube access). |
| `out/summary.md` | Current analysis output. |

Coverage: MLS regular season and playoffs at Banc of California / BMO Stadium, 2018 through 2025 complete
(17 regular-season home games each season, 2020 shortened), 2026 through 9 September (11 of the season's home games;
the remaining 2026 home games were not collected because the session's search budget ran out).
Excluded: the 2024 Rose Bowl El Tráfico and the 2026 Coliseum opener (not at BMO), MLS is Back 2020 (Orlando),
away matches, most cup ties. The 2020 no-crowd games are kept and flagged (`fans = False`).
Extra time is excluded everywhere; stoppage-time goals are counted in the half they belong to.

Sources: ESPN match pages, lafc.com and opponent-club recaps, FOX Sports box scores, MLSsoccer.com recaps, reached
through web-search summaries (direct page access is blocked in this environment). 17 matches still have at least one
goal with an unknown minute (`todo` column); their half-time score is known in all but three cases, so half-level
figures are complete and only the 15-minute buckets and the 60' cut drop those matches.

No xG is included: no provider's half-level xG was reachable. Pre-match 1X2 odds for 2018–2024 exist in the
football-data.co.uk mirror used as a spine, but that file's dates are unreliable for MLS, so they were not joined.

## Stadium geometry (verified from multiple seating and stadium guides)

The 3252 supporters' section is the North End, behind the north goal. The South End is a single-tier stand.
Team benches are on the west sideline (LAFC in front of Field Club D, visitors in front of Field Club B). The open
"keyhole" corner with the downtown skyline is the north-east corner, which makes the north goal identifiable in footage:
it is the goal with the safe-standing terrace behind it and the open corner beside it. Attacking "toward the 3252"
therefore means attacking the north goal, and bench proximity does not change with the attacking end.

## Why direction is not in the data yet

Every event-data provider normalises coordinates so the attacking team plays left to right, so no feed records the
physical end. No match report, caption or fan post found in ~200 targeted searches stated the end LAFC attacked in a
specific half, and no documented club convention was found either. The only reliable route is footage: the first
clip of each highlight package or the kickoff of a full replay shows the end. This container's network policy blocks
youtube.com, googlevideo.com and every mirror tried, so the frame pipeline could not run here.

**To unblock:** in the cloud environment settings, allow `www.youtube.com`, `youtube.com`, `*.googlevideo.com`,
`i.ytimg.com`, then run `scripts/youtube_kickoff_frames.py` and code each match into `data/direction_labels.csv`
(status `verified` only with a video URL, timestamp and the landmark seen). Two coders, log disagreements.
Allowing `www.espn.com`, `site.api.espn.com` and `fbref.com` would also let the remaining minutes and per-match xG be
pulled directly.

## What the direction-agnostic data says

See `out/summary.md` for the full tables. Main points for MLS regular-season home games with fans (n = 129):

- Second halves at BMO are only slightly higher scoring than first halves: 1.62 vs 1.53 total goals per match,
  and 1.11 vs 1.03 LAFC goals. A large "second-half surge" is not a feature of LAFC home games in this sample.
- First-half under 1.5 hit 54% of the time (95% CI 46–63%); first-half 0-0 occurred 22.5% of the time. Season rates
  range from 29% (2019) to 71% (2025), so any pricing view must condition on the era.
- Goals cluster in 31'–HT (0.63 per match, half of them LAFC) and 76'–FT (0.60), not specifically late.
- When LAFC are tied or trailing at 60', they score again 61% of the time (n = 61). That is the baseline a
  "toward the 3252" split has to beat.
- The eight 2020 no-crowd games are too few to serve as a placebo test but are kept for that purpose.

## On the "Directional Illusion" document

Its four showcase rows can be checked against this file: the 2026-09-26 Dallas match was away (not in this file);
2019-08-25 vs Galaxy was 2–3 at half-time and 1–0 LAFC in the second half, not 1–2 and 2–1; 2022-10-09 vs Nashville
was 0–1 with no LAFC goal, not 1–1 in the second half. Its half-level npxG values and its 107/15 configuration split
have no verifiable source. Treat its coefficients as unmeasured.

## Pre-registered analysis, to run once labels exist

Primary outcome: LAFC goals minus opponent goals per half (npxG when a provider becomes available), model
`outcome ~ half * toward_3252 + score_state + opponent_strength + season` with match random intercepts. Report the
interaction term with a confidence interval, an 11-v-11-only sensitivity run, and leave-one-season-out checks.
Secondary: LAFC scoring rate, conceding rate and total goals separately; the 60'-tied-or-trailing cut; a chronological
holdout (train ≤ 2023, test 2024–2026) for the live-prediction check. No profitability claim without timestamped prices.
