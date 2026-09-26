# Gate 2 readers: the one re-validation (seed 20260927)

Owner: scoreboard-fix. Reviewer: fit-review. The pre-registration is lane doc section `3fc13f3b` with amendments 3
(`9d8ad8f2`), 4 (`51a2733c`) and the addendum to amendment 3 (`94e1f61a`). The code is frozen at amendment 4 and was
re-hashed immediately before scoring:
- `perception/killfeed.py` `c5147271`;
- `perception/spectator_prompt.json` `5aeab850`;
- `perception/match_timer.py` `945b3634`;
- `perception/match_timer_glyphs.json` `1f5ce476`.

There was no tuning and there is no second attempt. Nothing is committed.

## Verdict

| Item | Judged? | Result | Bar | |
|---|---|---|---|---|
| **K1** kill-feed recall, live (arrivals after a shift) | judged | 7 of 39 = **0.18** | ≥ 0.90 | **FAIL** |
| **K2** kill-feed precision, live | judged | 7 of 9 = **0.78** | ≥ 0.95 | **FAIL** |
| **K3** kill-feed timing, live (matched entries) | judged | within 2 frames 1.00, within 1 frame 1.00 (n = 7) | ≥ 0.95 / ≥ 0.80 | pass |
| **T1** timer values | judged | 1 wrong in 750 (0.13 %); 1 unknown of 112 legible (0.9 %) | ≤ 0.5 % / ≤ 10 % | **PASS** |
| T2 timer changes, live | information only (69 < 100) | recall 0.942 (65 of 69), exact 0.938, all within ±1 frame, 0 false changes, 0 wrong-valued | — | — |
| T3' timer offsets, live | information only (69 < 100) | 9 of 10 segments matched, every matched offset error 0.0 ms; 1 segment unmatched (see below) | — | — |
| Replay half | — | no source | — | **undecided** |

**The kill-feed reader FAILS the re-validation. The timer reader passes T1, and its T2 and T3' are undecided by the
support floor.**

### Why the kill feed failed: the layout recognition, on a live competitive match

- **Six of the 22-48-05 windows were read as the spectator layout** (#0–#5), although they are live. Four of them
  hold the 30 judged arrivals after a shift that were missed; #6 was read as live.
  - 22-48-05 is the main account's **competitive** Convoy match.
  - Its live HUD shows a team-box clock where the replay viewer's team-B clock sits: team_b reads "04:00" on 115 of
    120 sampled frames of #1, while the "Press N to Show" prompt reads on 0 of 120.
  - `recognise_layout` takes a team-clock read **or** the prompt as evidence of the replay viewer, so it returned
    "spectator".
  - The reader then looked for the feed in the spectator slot rows (y 316–342) and found nothing.
- **This is the fail-closed rule failing:** a layout the development recordings never showed (a competitive live HUD)
  was recognised confidently as the wrong one, instead of returning unknown.
  - All development recordings were Quick Match (live) or replays. The competitive HUD was never in development.
  - The Quick Match development replay had no team-box clocks, which is why the prompt was added. The team-clock
    evidence was kept from the first version and is what misfired.
- **On the windows recognised correctly** (20-56-10 #0 and 21-13-21 #0, both live Quick Match):
  - 7 of 9 arrivals after a shift were detected, all within ±1 frame.
  - **The two misses, both in 21-13-21:**
    - 3094, the second of two arrivals 12 frames apart, where only the first shift was detected;
    - 4726, over a red damage screen.
- **The two false shift detections:**
  - 21-13-21 at 1206, the double arrival 3 frames apart, which the truth excludes;
  - 22-48-05 #2 at frame 40, in the misrecognised layout.
- **This breakdown is reported for the mechanism only,** not as a substitute verdict. The registered K1–K3 pool every
  live window.
- **Empty-feed arrivals** (reported, not judged): 9 of 25 detected. Most misses are in the misrecognised windows.

### Timer notes

- **T1's one "wrong":** 20-56-10 value frame 135. I labelled it illegible (a pop frame with a ghosted glyph), and the
  reader read "1.0". By the rule, any value on an "illegible" frame counts as wrong. It is still within the bar.
- **T2's misses:**
  - 20-56-10 #6 at 1049 (an SS.d change);
  - 22-48-05 #14 at 154 and 274, the last SS.d seconds before the round ends;
  - 22-48-05 #6 at 46, the window's first change.
- **T3':** the one unmatched segment is 22-48-05 #14, which has 3 truth anchors (3.2 → 0.0 s) and no reader anchors,
  because of those two misses.
- **Display jitter, as a measured property** (per-tick residual around each segment's median, T3' segments): truth
  and reader both p50 0 ms, p90 8.3 ms, max 100 ms. The 100 ms is the game's own SS.d handover step: the display shows
  6.0 for 12 frames.

## Support

| Half | Item | Truth count | Floor |
|---|---|---|---|
| Live | K1–K3 (arrivals after a shift) | 39 | 30 (met) |
| Live | T2 / T3' (second changes) | 69 | 100 (not met: information only) |
| Live | T1 (value frames) | 750 (112 legible) | none |
| Replay | all | no source | undecided |

**Why the timer is short:** 21-13-21 (God Quarry, overtime) and 22-48-05 (competitive Convoy) show no centre timer in
any drawn window, and the four original sources had almost no room left outside the first draw's ±60 s margin.

## Blind re-label agreement (reported, not judged)

Fit-review's labels are `blind/fit-review-labels.json` (`2b4868b4`); the adjudication is `truth/blind_adjudication.json`
(`0da1ad04`).
- **T1:** 49 of 50 identical. v42 (22-48-05 frame 106): mine 00:35, fit-review 00:36. Re-inspected at 3×, it is
  clearly 00:35, so mine stands.
- **The whole window (22-48-05 #6):** 0 arrivals from both of us.
- **Arrivals after a shift:** e01, e02, e07 and e08 identical. e05 and the Cenxtii arrival in e09 are 1 frame apart.
  - Fit-review's main e09 answer is the other arrival in the crop range (chickentendy71). That one is also 1 frame
    apart, and its shift frame as well; I took fit-review's frames after re-inspection.
- **Empty-feed arrivals (e00, e03, e04, e06):** my labels were the 0.2 s coarse cell, an upper bound.
  - **e00, e04, e06:** fit-review's frame-level first frames were 14, 21 and 19 frames earlier than mine. I adopted
    them after re-inspecting the frames.
  - **e03:** fit-review's crops begin at frame 4128, with the entry already present, so it labelled no exact onset
    (first = its first crop, marked unsure). The final value, 4126 (26 frames before my coarse 4152), comes from my own
    re-inspection of frames before its crop range. It is not fit-review's frame.
  - **The other 21 empty-feed arrivals** in the truth stay at coarse resolution; they are reported, not judged.
- **Truth v2** (`feed_truth.json` `856df87d`) went into scoring. It differs from v1 (`8842a476`) only in the seven
  adjudicated arrivals, which are listed in the adjudication file.

## Scorer limitations (from fit-review's review, `review-gate2-revalidation-20260926.md`)

1. **T3' segment matching** (`r2_score_timer.py`, the segment association): each truth segment is paired with the
   reader segment that shares the most displayed values.
   - There is no time or format correspondence constraint, no one-to-one consumption, and no separate account of extra
     reader segments.
   - The segmentation and offset formulas follow amendment 3, but this association is not a general implementation
     of "every segment".
   - It does not affect the present T3' figures, which are information only (69 < 100).
2. **Dropped clock rows:** timer anchors whose frame has no composition time in the logger's `frames.csv` are dropped
   silently rather than counted, although the registration asks for them to be reported. Neither limitation affects
   T1.

A future timing verdict needs both fixed.

## Deviations and disclosures

1. **The draw for the two new sources** ran `draw_sample_3.py` (`b12682c5`), a copy of `draw_sample_2.py` (`68cd14e2`).
   It changes only three things:
   - the source list;
   - the replay is dropped;
   - new sources are exempt from the first-draw exclusion.

   Seed 20260927, sizes, counts, the 60 s margin and the top-up rule are unchanged. The lead accepted it. The outputs
   are `sample-3.json` `852c78f3`, plus `sample-2.json` `d7e738e2` for the four original sources.
2. **A labelling aid:** in 22-48-05 #3 (its last two arrivals) and #4 (all its arrivals after a shift), candidate shift
   frames were located with a loose slot-drop detector (`jumpaid.py` `82750358`: slot NCC < 0.6, drop-one-slot NCC >
   0.6). Every frame was then read by eye. The lead accepted this as disclosed; the blind re-label is its check.
   - Fit-review's subsample happened to include one of those arrivals (e08), with the same first frame.
   - **Note:** in those windows the reader missed every arrival anyway, because of the layout. The aid's closeness to
     the reader's test did not flatter the score.
3. **Empty-feed arrivals** are labelled at 0.2 s resolution, except the four adjudicated ones.
4. **Two arrivals** in 22-48-05 #3 (4940, 5323) were found at frame level after my coarse pass missed them. They are in
   the truth.
5. **The game was started** while I was diagnosing, after all scoring decodes had finished. A last diagnostic decode was
   refused by the stop check; nothing in the scores depends on it.

## Reading, as registered

- **The kill-feed reader supplies no Gate 2 anchors.** This was the one re-validation (amendment 3), so a fix now needs
  new recordings and a new pre-registration.
- **The named failure:** layout recognition treats any team-box clock as the replay viewer. The competitive live HUD
  has one. A fix would need to recognise the competitive live HUD, or use the prompt alone for the viewer, and fail
  closed on anything else. It would have to be tuned and checked on development recordings that include a competitive
  match; none is registered for development now.
- **The timer reader:** T1 passes. T2 and T3' are information only (69 < 100), and both look clean. It still lacks a
  decided change-timing result for the live half, and the replay half is undecided.

## Hashes

| Item | sha256 |
|---|---|
| Truth (LF), `reval/truth-sha256.txt` | feed_truth v1 `8842a476` / v2 `856df87d`; timer_changes `74260cfa`; timer_values `033955fe`; timer_coarse `6d11a2d7` |
| Blind packet | manifest `8354d77d`, key `44b47205` |
| Fit-review's labels | `2b4868b4` |
| Adjudication | `0da1ad04` |
| Scorers | `r2_score_timer.py` `79eb59f2`, `r2_score_feed.py` `eda9a938` |
| Outputs | `score_timer.json` `66512807`, `score_feed.json` `8be58102` |
| Media (streamed) | 21-13-21 `7ec60040…`, 22-48-05 `cb9c7ad7…` |
| Registry at GO | `e8a1d060` |

**Memory:** peaks were 0.38 GB (extraction), 0.23 GB (timer scoring) and 1.08 GB (kill-feed scoring). There was at
most one decode of mine at a time; the decoder waits while two ffmpeg are running and refuses under 4 GB free.
