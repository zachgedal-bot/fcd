# Athlemix Plus: implementation spec

Six screens in `premium/index.html` (toggle Free / Plus at the top, or
`?tier=plus`). Everything below is what the app needs to make them real.
Pricing and copy are proposals; the gating rules and the contact rules are not.

## 1. The hooks, and what the free tier must show

| Screen | Free tier shows | Plus reveals | Why people pay |
|---|---|---|---|
| Profile | views, coach views, saves (counts) | film completion, search appearances, pool rank | the counts prove the data exists |
| Who viewed you | number of coaches, division, role, region, "repeat visit", blurred program | program name, 90-day history, message CTA | the single biggest converter on LinkedIn; same mechanic |
| Your rank | rough band ("Top ~?%"), factor bars without notes | exact percentile, D1-filter position, the notes, the moves and their point gains | tells a 2028 whether they are wasting time on D1 mail |
| Coach reach | sent / opened / replied counts, thread list | reply-rate benchmark, what answered messages had in common, warm paths, intro requests | turns cold outreach into a measured process |
| Program page | record, seniors leaving, commit count, camps | need at your position, commit timing, which clubs the program is watching | due diligence before spending on a camp |
| Paywall | bottom sheet from any lock | | |

Rule for every lock: show the shape of the data (count, category, blurred
name), never fabricate the specifics. A blurred row must be a real row.

## 2. Data model (additions to the existing app)

```
ProfileView      id, viewer_user_id, viewed_user_id, viewer_role (coach|player|parent|club), viewer_program_id?, ts, source (search|reel|share|link)
Save             coach_user_id, program_id, player_user_id, ts            -- "program saves"
SearchAppearance player_user_id, search_id, ts, filters_json              -- written by the search service per result page
FilmView         reel_id, viewer_user_id?, watched_seconds, length_seconds, ts
Outreach         thread_id, from_user_id, to_user_id, program_id, sent_ts, opened_ts?, replied_ts?, has_reel_link, has_schedule
Program          id, name, division, conference, region
RosterEntry      program_id, player_name, position, class_year, source, ts   -- scraped or coach-maintained
Commit           program_id, player_user_id?, player_name, position, class_year, announced_ts
PoolRank         player_user_id, pool_key (class:position:region), percentile, factors_json, computed_ts   -- nightly job
Subscription     user_id, plan (plus|scout), status, started_ts, renews_ts, guardian_user_id?
```

Coach identity is only ever revealed when `viewer_role = coach` AND the coach
account is verified (school email or admin approval). Views by other players
and parents are counted but never named, at any tier.

## 3. The rank

Nightly job per pool (class year × primary position × region; fall back to
national when a pool has fewer than 50 players):

```
score = 0.30 film + 0.25 academics + 0.20 exposure + 0.15 verified_stats + 0.10 activity
film           = f(reel count, completion rate, recency)              capped at 3 reels
academics      = f(GPA, test score present, transcript verified)
exposure       = f(coach views 30d, saves, search appearances)        log-scaled
verified_stats = 1 if a club or HS coach verified the season line, else 0.4 with self-reported, 0 with none
activity       = f(days since last post, profile completeness)
percentile     = rank of score within pool
```

"Moves that change it" is computed by re-scoring the player with one input
changed (test score added, stats verified, reel posted) and reporting the
percentile delta. Never show a move whose delta is under 1 point.

Publish the weights in the help centre. Players will ask, and hidden weights
read as arbitrary.

## 4. Gating

- Server-side. Every premium field is stripped from API responses for
  non-subscribers; the client never receives a real value it then blurs.
  The blurred rows are rendered from the free payload (role, division, region).
- `GET /me/insights` returns `{tier, coach_views_30d, viewers:[{role,div,region,when,repeat, program?}], rank:{band, percentile?, factors:[{k,v,note?}], moves?}, outreach:{sent,opened,replied, benchmark?, warm?}}` with the optional fields present only on Plus.
- Paywall opens from any lock; deep link `athlemix://plus?from=<screen>` so conversion is attributable per screen.
- Under-18 accounts: a subscription must be started from a linked guardian
  account (Apple/Google family purchase or guardian card). Store `guardian_user_id`.

## 5. Recruiting-contact rules the product must enforce

NCAA Division I and II women's soccer: no recruiting communication from
college coaches to a prospect before **June 15 after sophomore year** (DI) /
June 15 after sophomore year (DII), and no off-campus contact before August 1
before junior year. Division III and NAIA are looser. Consequences:

- "Message" from a coach to a 2028 player before that date must be blocked
  server-side with a clear reason, not just hidden. Player-initiated messages
  and camp registrations are allowed; the coach's reply is what the rules govern.
- "Who viewed you" is fine at any age: a view is not a contact.
- "Warm paths / ask intro" routes through the club coach, which is permitted.
- Log every coach→player message with class year and date so compliance
  questions can be answered later.

Check the current NCAA recruiting calendar for soccer before shipping; dates
move.

## 6. Events to track (the metrics that run the business)

```
view_profile_insights  {tier, coach_views_30d}
lock_impression        {screen, lock}
lock_tap               {screen, lock}
paywall_view           {from}
trial_start            {plan, from, guardian:bool}
trial_convert          {plan}
churn                  {plan, days_active, last_screen}
viewer_reveal_message  {program_id}      -- Plus user messaged a program that viewed them
rank_move_completed    {move}            -- player did the thing the rank screen suggested
```

Targets to watch: lock_tap / lock_impression by screen (expect "who viewed"
highest), trial_start / paywall_view, trial_convert, and whether Plus users
message repeat viewers more (that is the story the upsell copy makes; verify
it before the copy stays).

## 7. Pricing proposal

Athlemix Plus $14.99/month or $99/year, 7-day trial, for players and parents.
Athlemix Scout $49/month or $399/year for coaches and clubs. Mid-range for the
category (NCSA and SportsRecruits sell packages in the hundreds to thousands;
Hudl Highlights and similar are $10–20/month). Test $9.99 against $14.99 by
region before locking it.

## 8. Dropping the screens into the app

`premium/index.html`, `premium.css` and `mock.json` are static. To prototype
inside Athlemix, serve the folder and link it; to implement, take one screen at
a time in this order, each behind the same feature flag: who-viewed → rank →
paywall → coach reach → program page → profile tiles. The first three are
enough to start charging.
