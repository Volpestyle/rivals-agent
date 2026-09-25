# admission-owner final 16: BLOCKED. The importer refuses 025230 (and will refuse 232304) over one recorder timestamp; the other asks done

## BLOCKED: 025230's assembly stopped at its import

`assemble_session.py 20260925T025230-605Z-7804-2`, run with the independent record `33f0c38d…` and snapshot
`code-snapshot-2ad0992`:
- **Written before the stop:** the recording-log and registry copies, `settings.json` and `review.json`.
- **Then:** `hd.import_session` refused with **"composition times go backwards in presentation order"**
  (`agent/human_demos.py:290`, `match_frames`).
- **Nothing was frozen and nothing downstream was written.**
- **The four partial files were moved aside, not kept,** so the folder is back to its pre-assembly state. The copies are
  in my scratchpad, `arrivals-0924/failed-assembly-025230/`:
  - `settings.json` `1c695eb7…`
  - `review.json` `9fba18cd…`
  - `recording-log.57d1f3d.md` `574ed0e2…`
  - `registry.f36e9e3b5650.json` `f36e9e3b…`

**The cause: one packet's logged composition time repeats its neighbour's.** From 025230's `frames.csv`, by packet
index:

| Packet | pts | dts | Composition (s) | × 120 |
|---|---|---|---|---|
| 117 | 116 | 115 | 0.9667 | 116 |
| **118** | **120** | 116 | **0.9833** | **118** |
| 119 | 118 | 117 | 0.9833 | 118 |
| 120 | 119 | 118 | 0.9917 | 119 |
| 121 | 123 | 119 | 1.0250 | 123 |

- **What happened.** Packet 118 is the reordered P-frame (pts 120), and its composition time should be about 1.000 s.
  It logged 0.9833 s, the same as packet 119: slot 118 is doubled and slot 120 missing.
- **The effect.** In presentation order, composition steps back once (pts 119 → 0.9917 s, pts 120 → 0.9833 s).
- **Where it is.** 0.99 s, before focus (0.999 s) and outside every segment.
- **What I got wrong earlier.** In `arrivals-0924.md` and final-14 I called this a one-frame "capture gap"; it is a
  duplicated timestamp.
- **The pts-based recorder check passes** (26,997 frames matched), because it never looks at composition times.

**Where else it occurs** (one scan of every session's `frames.csv` in presentation order):

| Session | Reversals |
|---|---|
| **232304** | **1, at 323.108 s**: the "16.7 ms capture gap" the proposer cut as `seg-004` (rejected), between the two accepted segments |
| 025230 | 1, at 0.992 s |
| 051828, 171533, 200129, 205528 | 0 |
| 021320 | 0 |
| 030045, 204707 (calibration) | 0 |

So **232304's assembly will stop at the same check**, whatever edge rule it goes in with.

**Options** (the importer isn't my file; this is your call and the importer owner's):
- **A (my recommendation):**
  - `match_frames` tolerates an isolated duplicated composition time *only outside the review's accepted segments*.
  - That frame's composition becomes unknown, and it is dropped from the frame references and listed in the audit.
  - It refuses if the frame touches an accepted segment, or if there is more than one per N.
  - This fits both takes: 025230's is before focus, 232304's is inside a rejected `capture_gap` segment.
- **B:** derive the missing composition time from pts. That is a guess, which the house rule forbids, so I don't
  recommend it.
- **C:** leave both takes held until the importer owner decides.

**Nothing is assembled; the tally is unchanged.** 025230's evidence, verdicts and motor records are untouched, and the
assembly re-runs as soon as the import is unblocked.

## The other asks

**Calibration.** The slow class's uncertainty is recorded as **about ±0.8° excess, ±0.25 % gain**, in the lane doc's new
2026-09-25 entry, citing review-calibration-0924.md. The frozen record is unchanged.

**Caps Lock.** Agreed: the 56 are auto-repeat downs, and the physical presses are 2. That makes 025230's Simple Swings
the fewest of the recent takes, not the most.
- My "56 Caps Lock presses" in `arrivals-0924.md` and final-14 was wrong in kind.
- The key-down tables there (Shift 843, …) are raw downs too.
- Recorded in the lane doc.

**Wheel secondaries.** The profile binds **Simple Swing to CAPS + MouseScrollUp** and **Jump to SPACE +
MouseScrollDown** (mapping 5). Both are visible on the 2026-09-23 settings-look frames (f097596, f099596); I missed
both in my transcription then. The step tables carry wheel ticks only as the `wheel_v` sum, never as an action.

| Session | Wheel-up (accepted) | Accepted step rows with wheel-up | Wheel-down (accepted) | `simple_swing` presses now | … if MouseScrollUp were bound |
|---|---|---|---|---|---|
| 051828 | 10 (10) | 8 | 0 | 0 | 8 |
| 171533 | 0 | 0 | 0 | 0 | 0 |
| 200129 | 54 (43) | 28 | 0 | 3 | 31 |
| 205528 | 13 (13) | 12 | 1 (1) | 13 | 25; `jump` 487 → 488 |
| 025230 | 2 (2) | not assembled | 0 | 2 | 4 |
| 232304 | 6 (6, owner) | not assembled | 0 | — | +up to 6 |
| 021320 | 80 | in intake; all bursts in its first 4 s | 8 | — | — |
| 030045 | 0 | — | 0 | — | — |

**What the ticks look like.**
- **Every sampled burst** is 1–4 ticks within 70 ms. It comes about 0.05–0.1 s after a right click (Web Cluster), which
  itself follows melee (Mouse 5).
- **The frames** after four bursts (051828 at 331.07 s, 200129 at 1109.02 s, 205528 at 502.07 s and 603.91 s; sheet in my
  scratchpad `arrivals-0924/wheel-frames/`) show melee on Galacta bots and **no web-line swing**.
- **The reviewer's frames** show the same for 025230's 2 ticks and for **232304's 6 ticks: no Simple Swing on the frames.**
- **They look incidental.** Binding them would put 8–28 `simple_swing` positives per session on melee frames.
- No binding change without your go.

**232304 is next.** I'm coding the frame-level edge rule now and will re-emit its segments; `intake-edge-rule.md` follows.
Its assembly is blocked as above.

**021320:** in its frame-level verify step (decode from 11:12).

## Bytes

| File | Bytes | sha256 |
|---|---|---|
| `docs/lanes/human-admission.md` (two sections appended today) | 87,038 (LF 86,763) | LF `3aa055c70ec0cce13b9023534f5a0a82660511300b6ac51bb7bf2f2db2f75c81` |
| scratchpad `arrivals-0924/wheel-count.json` | | `5b8eceb036c50b64a08f81938657947def9f5087f6abc407e3fce8635f18144d` |
| scratchpad `arrivals-0924/wheel_count.py` | | `01e6512d9988115f66a548136d2daf426b7ca911da21e3c32615e24f8eb17f9d` |
| scratchpad `arrivals-0924/wheel-frames/wheel-sheet.jpg` | | `25a7d6eb29a43740d3e9d35fd337414e47be0c058311b8259e0ce378203a48ad` |

No commits, no Linear, nothing on the Mac.
