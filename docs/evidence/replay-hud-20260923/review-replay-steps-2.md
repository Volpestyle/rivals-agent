# Re-check: replay-steps-2 (R1, R2, R3 on the rebuilt DayMR table)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The re-check is read-only.

## Bytes

**Checked, and equal to the hand-back:**

- table `0690fd72`
- `build.json` `932c55d6`
- `hud/events.json` `629490f1`
- `hud/manifest.json` `da6ace58`
- `perception/replay_hud.py` `40d4f968`
- `policy/range_bc/steps.py` `aa17bbcd`

**Moved since the hand-back:** at 20:50, after the table was built (20:40), `scripts/replay_steps.py` became
`f1b0f7bc` (the hand-back says `3d18dcde`) and `tests/test_replay_steps.py` became `ad534d9a` (was `ae007516`).

- At those bytes, `uv run --no-sync pytest tests/test_replay_steps.py` gives **17 passed, 5 failed**.
- All 5 are `ValueError: too many values to unpack` in the synthetic label-rule tests. The press-window tuple has
  gained a field, which looks like the window-level contract being written now.
- **I could not reproduce "22 passed"**, because the `3d18dcde`/`ae007516` bytes are no longer on disk.
- My checks below are on the table itself, which is what `3d18dcde` produced. The builder needs its own green run at
  whatever bytes land.

## Verdict: both findings are gone from the table

I ran my own checks from the raw reader rows (`rs2.py`, `rs3.py` in my scratchpad), not the builder's functions.

**R1, false 0s in a press window: gone.**

- **The two ult casts:** the 78 rows in 617.054-619.620 s and the 38 rows in 755.454-756.679 s are all **null**
  (they were 76 + 36 zeros).
- **No 0 lies before any cast's first evidence**, for any basis. Each window is `[t_lo − Lmax, t_hi − Lmin]` with the
  floored lags.
- **Every 0 lies wholly inside `press_coverage`:** 0 exceptions across 83,512 zeros.
- **Masks:** `press_known == (press is not None)` on every row, for all five casts.

**R2, rows inside withheld spans: gone.**

- **Deaths:** **0 rows** in 25 death regions. That counts 21 hp-0 clusters, rebuilt my way and widened over adjacent
  frames not read alive, plus my 4 pinned deaths. The first table had 306.
- **Other withheld frames:** 0 frames under any row are timeline, no-HUD or column-unknown.
- **Other POV:** 2,707 "viewer not following" frames sit under rows. All are in bar blips of 3 s or less; **none is
  in a follow run longer than 3 s**.
- The remaining 6,504 frames under rows are "reader abstained" (live play, HUD unread). They are allowed in spans
  only, and never as alive evidence for forgiveness.

**R3, coverage bridging: fixed.**

- The merged coverage stretches contain **0 withheld frames**, for every ability.
- The only press-coverage spans crossing a boundary are the two EXCLUDE end edges (1658.5 and 1864.9 s). That is
  the press-time shift of a stretch that starts at the edge, correct by construction.
- **No 0 lies within 2 s before any seek or EXCLUDE edge.**

**The split and the header.** `split: "replay"` and `viewer_fov_assumption: "viewer, unverified"`.

## One note (not blocking): countdown casts rest on James's cooldown-start lag

For team-up and GOH, the builder uses only the press→cooldown-start lag. For team-up that lag is 2-10 ms, measured
on James's 10 s team-up; **DayMR's is Symbiote Bond (15 s)**.

- **The disagreement:** on this footage, the first-evidence lag from the same measured table would put the press
  earlier. It gives [first_seen − 1.68, first_seen − 0.26] for team-up and [first_seen − 1.87, first_seen − 1.04]
  for GOH, where "the lag table" is `press-lags.json`, i.e. James's takes.
- **The affected zeros:** **54 team-up zeros and 2 GOH zeros** lie in that earlier view's window but outside the
  cooldown-start window the builder uses. Examples:
  - team-up rows from `pts` 513313, 0.2 s before an implied start of 513.526;
  - GOH rows 1284171 and 2028146.
- **Why it isn't a rule violation:** these zeros are inside the stated rule. But they depend on the countdown lag
  transferring to a different team-up and player, and on this footage the two lag views disagree by about 0.3-1.7 s.
- **Suggested fix:** for countdown casts, null the union of both views' windows (56 rows). Or state the assumption
  in `build.json` and the lane doc.

## The producer's finding, and the lead's contract

The producer reports that under R1 only **1 positive survives** (a team-up countdown cast). **This is correct:**

- James's lag spreads (0.15-1.6 s; ult floored to [0, 0.51] s) never fit inside a 33 ms step.
- The table as built is trusted negatives plus unknown windows. It holds no per-step positives.
- **The lead's decision is sound, and I have no objection:**
  - rows inside a press window become unknown;
  - `events.json` carries `[lo, hi]` per cast, for a window-level loss.

**For the window-level loss, two conditions:**

- The `[lo, hi]` per cast must be exactly the window the builder nulls, including the countdown-union choice above,
  so a cast is never both a window positive and a step 0.
- A window must only count where its steps are all in rows. A window cut by a run break or a death is partial.
  - **Flag partial windows** rather than training on them.
  - Two casts are already fully out of the spans: 2 AC and 1 ult were outside the rows in the first build.
