# LAFC attacking-direction study: verified dataset, pilot status and plan

**Verdict (2026-09-29): still zero verified attacking ends, but the verification pipeline now exists and is tested.**
`scripts/verify_directions.py` was run over all 156 home matches in this file. Every row came back
`first_half_direction = Unverified` with `verification_note = network_blocked`, because this cloud environment's
network policy refuses connections to `youtube.com`, `www.youtube.com`, `*.googlevideo.com`, `i.ytimg.com` and
`googleapis.com` (the script stops searching after three consecutive network failures rather than hammer the proxy).
No direction was estimated or guessed. Section "Attacking-direction verification" below explains how to run it where
those hosts are reachable; the offline self-test (`scripts/selftest_verify_directions.py`) passes.

Everything that does not depend on direction has been built and analysed from source-linked match reports:
half-by-half scoring, first-half under rates, 15-minute buckets, and the 60th-minute game-state baselines.
Those numbers are in `out/summary.md` and reproduced below.

## What is in this folder

| File | Contents |
|---|---|
| `data/raw_events.jsonl` | One record per LAFC home match with goal minutes, scorers, penalties/own goals, red cards, HT/FT score, attendance, kickoff, source URLs, confidence and open to-dos. |
| `data/matches.csv` | One row per match (156): scores by half, red cards, venue, fans flag, plus the verification columns `first_half_direction` (North / South / Unverified), `verification_source` (YouTube URL with `&t=` of the frame used), `verification_note`, `first_half_screen_direction`, `verification_confidence`. Currently all `Unverified`. |
| `data/goals.csv` | One row per goal (498) with minute, added time, half, scorer, kind. |
| `data/direction_labels.csv` | Label sheet, one row per match; filled by `verify_directions.py` (coder = script) or by hand. A human `verified` row is never overwritten by the script. |
| `scripts/build_dataset.py` | Rebuilds the CSVs from the raw file, carrying over the verification columns and existing labels. |
| `scripts/analyze.py` | Runs the analysis; computes the four-group split automatically once labels exist. |
| `scripts/verify_directions.py` | **Direction verification pipeline**: YouTube search (yt-dlp) -> first 90 s of the official highlight -> OpenCV kickoff frames -> screen side -> North/South. Writes the columns below, `direction_labels.csv`, `out/verification_log.jsonl`, `out/frames/<date>/contact_sheet.jpg`, `out/direction_summary.md`. |
| `scripts/selftest_verify_directions.py` | Offline self-test of the pipeline on synthetic broadcast footage (no network needed). |
| `scripts/youtube_kickoff_frames.py` | Earlier frame-dump scaffold; superseded by `verify_directions.py`. |
| `data/video_overrides.csv` (optional) | `date,video,note`: pin a match to a YouTube URL or a local clip (manual-review path). |
| `data/kit_overrides.csv` (optional) | `date,lafc_kit`: matches where LAFC did not wear the black kit (`light` or `grey`). |
| `out/summary.md` | Current direction-agnostic analysis output. |
| `out/direction_summary.md` | Sequence A / Sequence B count per season from the latest verification run. |
| `out/verification_log.jsonl` | One evidence record per processed match: queries, candidate videos and why each was accepted or rejected, frame statistics, decision. |

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
`i.ytimg.com`, then run `scripts/verify_directions.py` as described in the next section. Allowing `www.espn.com`,
`site.api.espn.com` and `fbref.com` would also let the remaining minutes and per-match xG be pulled directly.

## Attacking-direction verification (`scripts/verify_directions.py`)

What it does for each row of `data/matches.csv`:

1. **Find the video.** Three yt-dlp searches (`LAFC vs <Opponent> <Month D, YYYY> highlights` and two variants).
   A candidate is used only if its title names both LAFC and the opponent, it was uploaded between the match day and
   14 days later, it is public, it is highlight length (< 25 min), and it comes from an official channel
   (Major League Soccer or LAFC; `--allow-club-channels` adds the opponent's club channel, `--allow-unofficial`
   anything). Every candidate and its verdict is written to `out/verification_log.jsonl`.
2. **Download the opening only.** `--download-sections 0-90s` at <= 480p through ffmpeg (system ffmpeg or the
   `imageio-ffmpeg` wheel), cached under `out/verify_cache/`.
3. **Read the kickoff.** Frames are sampled at 2 per second. A frame counts as a kickoff wide shot when the grass
   covers >= 35 % of it, a near-vertical white halfway line is found in the central band, and the two most common
   kit classes on the pitch (dark / light / grey / hue bucket) each have >= 80 % of their players on opposite sides
   of that line. LAFC are the `dark` class by default (black home kit; override per match in `kit_overrides.csv`).
   The side LAFC defend gives the screen side they attack. At least three agreeing frames are required, any
   conflicting frame makes the match `ambiguous_frames`, and an annotated contact sheet of every sampled frame is
   saved to `out/frames/<date>/contact_sheet.jpg` for review.
4. **Map screen side to the stadium.** North = the 3252 safe-standing terrace, South = the scoreboard end.
   The mapping depends only on which sideline the main broadcast camera is on, a venue constant:
   camera on the **west** sideline (looking east) puts the 3252 on the **left** of the screen; camera on the
   **east** sideline puts it on the **right**. The script never assumes this. Rows carry their screen side but stay
   `Unverified` (`camera_side_uncalibrated`) until you check one contact sheet (the north goal is the one with the
   steep terrace behind it and the open north-east keyhole corner beside it) and run the re-map once. The benches sit
   on the west sideline, so `west` is the expected answer if the main camera is on the bench side, but confirm it
   from footage before using it.
5. **Write everything back.** `matches.csv` (columns above, plus the legacy `attacking_end_1h` / `direction_status`),
   `direction_labels.csv` (status `verified` with URL, timestamp and landmark; human labels are left alone),
   `out/verification_log.jsonl`, and `out/direction_summary.md` with the Sequence A (1H North / 2H South) vs
   Sequence B (1H South / 2H North) count per season.

A row is `Unverified` whenever any link in that chain is missing, and `verification_note` says which:
`no_video_found`, `no_official_video`, `restricted`, `rate_limited`, `network_blocked`, `download_error`,
`no_wide_shot`, `no_kickoff_frame`, `kit_not_found`, `ambiguous_frames:*`, `camera_side_uncalibrated`.

Run it (dependencies `yt-dlp`, `opencv-python-headless`, `pandas`, `numpy`, `imageio-ffmpeg` are pip-installed
automatically unless `--no-install`):

```bash
cd lafc-direction
python scripts/selftest_verify_directions.py                       # offline check of the pipeline, ~1 min
python scripts/verify_directions.py                                 # all 156 matches; 2 s polite delay between requests
#   -> open out/frames/<any date>/contact_sheet.jpg, decide which screen side holds the 3252 terrace
python scripts/verify_directions.py --remap-only --camera-side west  # or east; converts stored screen sides to North/South
python scripts/verify_directions.py --summary-only                   # reprint the per-season Sequence A / B table
```

Useful options: `--date 2024-04-27`, `--season 2023`, `--limit 10`, `--force` (redo verified rows), `--dry-run`
(search and validate only), `--cookies cookies.txt` (bot-check or age-gated videos), `--delay 5` (slower),
`--accept-long-videos` (full-match replays; the kickoff is then not in the first 90 s, so pair it with a
`video_overrides.csv` local clip cut at the kickoff). Manual review: put the URL or a local clip path for a match
in `data/video_overrides.csv` and re-run for that `--date`.

Known limits, deliberately not papered over: LAFC are identified by kit class, so a match in which LAFC wore a light
or grey kit must be listed in `kit_overrides.csv` or the side would be read for the opponent; a highlight package
that does not open on the kickoff / line-up wide shot yields `no_kickoff_frame` (fall back to a full-match replay
via overrides); the automated landmark check is the camera-side calibration, not per-frame terrace detection, so
the one-time calibration is the step that makes the whole column empirical.

Latest run in this environment (2026-09-29): 156 processed, 0 North, 0 South, 156 Unverified (`network_blocked`).

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
