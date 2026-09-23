# Fragment contract repair: before and after (VUH-1314)

The repair lets range mode measure one bot that the finder drew in pieces. The witness it adds is the tracker's own association. It
is not a grouping by id. The controller unites only a matched box and its `_body_of` pieces, re-checked geometrically. The union must
stay inside the box where the body last stood as one box, padded as a piece is. It refuses any box group that `_bodies` joined as
stacked. It never walks forward on a united body. The rule, the boundary and the residuals are in
[docs/lanes/tracker.md, "The body witness (range mode)"](../../lanes/tracker.md). The failure it answers is
[range-support-followup-20260922](../range-support-followup-20260922/README.md).

Reproduce from the repository root. The command writes only `summary.json` here:

```
uv run --offline --no-project python -B docs/evidence/range-fragment-repair-20260922/run.py
```

- `run.py` exports HEAD `83c6739`'s `agent/` with `git archive` into a temporary directory. It runs both trees and pins the inputs:
  the slot-4 log's raw sha256, and LF-normalized sha256 of the code and scripts.
- `replay.py` replays every recorded reflex tick of `data/l1/galacta-pilot-20260922-04-learned/frames.jsonl`
  (sha256 `1eadcb5e…9e071a6`, the same pin as the original diagnostic) through one `Tracker` and one `Controller`.
- `scenarios.py` runs the review's conflict cases through a real Tracker, State and Controller.

No model, perception, Loop, Live or pad is imported. No game input was sent.

## Replay fidelity

| Check | Result |
|---|---|
| HEAD replay against the recording (1068 range steps) | 0 reason mismatches, pads identical (max \|Δ\| 0.0), ids identical on every row |
| Working tree with no witness passed, against HEAD | 0 reason changes, 0 pad changes |
| Working tree's fresh `Tracker.observe` over the id-stripped boxes | reproduces every recorded id |
| The camera that `observe` places boxes in | the recording's: a second controller steps the legacy inputs and reproduces every recorded pad (0 differ). The replayed controller's own aim, which the recorded pixels never saw, does not move the tracker |

## The 12 refused decisions (first consumption)

| Decision | Row | HEAD | Repair | Target's association |
|---|---|---|---|---|
| 53 | 290 | target_missing_or_ambiguous | no_new_start | matched box + 3 pieces |
| 54 | 295 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |
| 55 | 301 | target_missing_or_ambiguous | no_new_start | matched box + 3 pieces |
| 56 | 306 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |
| 57 | 312 | target_missing_or_ambiguous | no_new_start | matched box + 3 pieces |
| 58 | 317 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |
| 155 | 855 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |
| 156 | 859 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |
| 157 | 865 | target_missing_or_ambiguous | **target_missing_or_ambiguous** | two-box `_bodies` group + 3 pieces |
| 158 | 870 | target_missing_or_ambiguous | **target_missing_or_ambiguous** | two-box `_bodies` group + 3 pieces |
| 159 | 876 | target_missing_or_ambiguous | **target_missing_or_ambiguous** | two-box `_bodies` group + 3 pieces |
| 160 | 881 | target_missing_or_ambiguous | no_new_start | matched box + 4 pieces |

**9 of 12 are repaired.** Decisions 157-159 stay refused by design. The finder drew Galacta's left side as two boxes stacked one over
the other, (1131, 603, 1215, 813) above (1042, 852, 1231, 1034) at row 865. The tracker's split rule joins them, and a smaller bot
standing on a near bot's head would look the same. They are the first native examples for a later rule that tells the two apart.

## All 64 refused ticks

| After the repair | Ticks | Target's association |
|---|---|---|
| no_new_start | 9 | matched box + 1-4 single-box pieces (48 ticks in all) |
| duplicate_no_new_start | 16 | |
| decision_expired | 23 | |
| target_missing_or_ambiguous (unchanged) | 16 | two-box `_bodies` group + 3 pieces (rows 864-882) |

`ly` is 0 on all 64 ticks: approach is withheld on every united body. The 48 measured unions are 379-470 px wide. Against the
target's last one-box width they are at most 0.99, so every one sits inside the `whole` cap. The per-tick table is `former_refusal_ticks.table` in
`summary.json`.

Across the whole run:
- No reason changes outside those 64 ticks.
- Starts accepted: 0 before, 0 after.
- LT-down ticks: 0 before, 0 after.
- Forward (`ly`) ticks: 76 before, 76 after, and `ly`, `lt`, `lx`, `rt` and the buttons are identical tick for tick.
- 484 ticks change aim only (`rx`/`ry`): once the controller stops refusing, it keeps aiming at the body.

The first, unreviewed repair differed: it walked forward on 48 of these ticks, because the fragment unions (416-503 px) read shorter
than the whole box (525-536 px) and fell under `near_h` (468 px).

## Review scenarios (a `start` request after arming on the target)

| Scenario | HEAD | Repair |
|---|---|---|
| S0 one whole body (control) | accepted, LT 1, ly 1 | accepted, LT 1, ly 1 (single member: the raw rule) |
| S1 native d53 reflex fragments | target_missing_or_ambiguous | **accepted, LT 1, ly 0**, union (1140, 610, 1521, 1091), 4 members |
| S1b native d53 decision fragments | target_missing_or_ambiguous | accepted, LT 1, ly 0, same union, 5 members |
| S2 smaller bot inside a near bot | target_missing_or_ambiguous | unaligned_target, ly 0; union = the near bot's own box |
| S3 smaller bot stacked on the target's head | target_missing_or_ambiguous | target_missing_or_ambiguous |
| S4 lane hole: two 250x200 boxes 10 px apart | target_missing_or_ambiguous | target_missing_or_ambiguous |
| S5 far small body alone (control) | outside_reach | outside_reach |
| S5b / S5c two stacked beyond-reach boxes | target_missing_or_ambiguous | target_missing_or_ambiguous |
| S6 target gone, another bot in the crop | target_missing_or_ambiguous | target_missing_or_ambiguous |
| T3a a smaller bot steps out of a near target, 240 px/s, `start` every tick | no start while it is present | no start; union at most 309 px wide (target 250); refused from its 17th tick |
| T3b the same, across the crosshair, target left of it | no start | no start; same bound |

## D1: a piece is not followed out of the body (delta review)

The first repair tested new pieces against the track's box, which already contained every piece taken before. A second bot absorbed
once could therefore be followed out of the target a few pixels per update, keeping the target's id (review T3). Before, meaning the
reviewed tree `vuh1314-owner-final.patch` run through this same `scenarios.py`:

| | Before | After |
|---|---|---|
| T3a starts accepted while the second bot is present | 2 (ticks 19, 40); union up to 481 px wide | 0; union at most 309 px; refused from tick 17 |
| T3b starts accepted while the second bot is present | 2 (ticks 22, 43), both with the crosshair on the second bot | 0; union at most 309 px; refused from tick 17 |
| S1 / S1b / S2 | accepted, ly 0 / accepted, ly 0 / unaligned_target, ly 0 | identical |
| Slot-4 former refusals measured | 48 | 48, the same reasons and pads tick for tick |

The fix is the review's first option: the controller caps the union at the held id's last single-box measurement plus `PIECE_PAD`
× its size, within `HIST_S`. The tracker supplies that box as `TrackedBody.whole`, turned into the current camera as it turns its
own boxes, so the controller keeps no history of its own.

The second option was tried first and regressed three of the 48 ticks: it made that box the `reference` itself. The d56 first
consumption (row 306) and rows 858 and 860 were each matched on a 113-114 px fragment against a 513-525 px whole box. That broke
the `CLOSE_RATIO` size bound, which is kept as a refusal, never a fault.

## Suites

- `uv run pytest`: 1260 passed, 61 skipped.
- `uv run --group perception pytest`: 2058 passed, 125 skipped, 5 failed, followed by `uv sync`. The 5 failures predate this change
  and are unrelated to it. They need gitignored data this checkout lacks, fail the same on a clean HEAD, and touch no changed code:
  - `test_hud.py::test_hud_accuracy`: 145 of 145 labelled HUD frames are not on disk.
  - `test_replay_states.py::test_walk_makes_loadable_states`, `::test_finder_is_a_plain_function` and
    `::test_missing_frame_is_skipped_not_faked`: `data/run1/frames.jsonl` is missing.
  - `test_scoreboard.py::test_a_frame_without_a_scoreboard_reads_nothing`: there are no `data/run1/*.jpg`.

## Limits

- Reflex rows log integer-rounded boxes and no class, confidence, plate or distance. The replay rebuilds each box as ENEMY with
  confidence 0.9 and distance None: the outline finder's constant and its absent distance. The controller tests confidence only
  against 0.4.
- Each intent is rebuilt from its logged decision: the first same-id hostile, as `brain._pick_target`, with the logged request, times
  and resources. Ticks with no range trace step Idle at their observation time.
- The fidelity check above bounds all of these: HEAD's replay reproduces every recorded reason and pad exactly.
- The replay is open loop. The repaired controller's pads are its decisions on the recorded frames. Its own aim differs from the
  recording once it stops refusing, and it never moved the camera those frames were taken under.
- This is one recording, one bot, one pose. It shows the contract gap closed on the demonstrated failure. It says nothing about the
  pilot's zero learned start proposals, and it is no live acceptance.
