# First-door arrivals: offline handback for VUH-1299

PC HOLD remains binding. This handback uses local retained artifacts only; current PC processes, pads and screen are **not checked**. The third trial's historical text output reports `procs: 0`, `pads: 0` after its run, not the current PC state.

**Result: trials 1 and 2 support the sampled arrival criteria below, including one successful console-rim recovery in trial 2. Trial 3 is visually incomplete. This is an L4 evidence handback, not independent acceptance or authorization for another trial.** Lead: `w26:pH`. Issue: [VUH-1299](https://linear.app/vuhlp/issue/VUH-1299).

## Verified local state and evidence

Inspection date: 2026-09-21. Local main: `a724e7bf4492`; first-door merge `291b586` is in its history. The retained invocation logs do not certify the deployed file hashes, so the local revision is not represented as a verified PC deployment. The writer freeze at `21a390f547eb` is a constraint, not a fingerprint recomputed by this inspection.

| Trial | Retained video | Arrival folder | Native PNGs inspected | Invocation result from retained text |
|---|---|---|---|---|
| 1 | `data/video/firstdoor1.mp4`, 465,787,900 bytes | `data/reenter/arrive-20260921-183337/` | 8: steps 1, 2, 15–20 | `EXIT 0`; 20 rows; 18:33:33.58–18:34:12.41 (38.83 s) |
| 2 | `data/video/firstdoor2.mp4`, 427,616,261 bytes | `data/reenter/arrive-20260921-184506/` | 13: steps 1, 2, 5–9, 16–21 | `EXIT 0`; 21 rows; 18:45:02.11–18:45:45.56 (43.45 s) |
| 3 | `firstdoor3.mp4` unavailable locally | `arrive-20260921-185654` unavailable locally | None | `EXIT 0`; text says 23 rows; 18:56:50.73–18:57:34.17 (43.44 s) |

Both available videos probe as H.264, 2560×1440, 60 fps, 85 seconds. All 21 retained native PNGs are 2560×1440 and inspected visually; their existing appearance-match timestamps are used below. No video is decoded wholesale to memory and no new media is generated. The existing replay files remain unchanged:

- [Trial 1 replay](arrival-firstdoor-1-20260921-183337-replay.jsonl)
- [Trial 2 replay](arrival-firstdoor-2-20260921-184506-replay.jsonl)

Invocation text lives in `/tmp/claude-501/-Users-james-dev-rivals-agent/15260d99-db72-4fa9-8ec7-1e9cae473d4b/scratchpad/`: `reenter-firstdoor1.log`, `reenter-firstdoor2.log`, `firstdoor3.out`. The third file explicitly names the PC arrival folder and the final message `in the Practice Range as Spider-Man`. Filename-only searches of this checkout (including ignored paths), the takeover handoff directory and `/tmp` find that text, but no third-trial video, step log or frames. There is no reacquisition or retry.

## Per-trial arrival criteria

Criteria a–d follow [L4's arrival reporting](../../lanes/l4-controller.md) and [re-entry's measurement contract](../../lanes/reentry.md). PASS below means supported by the retained samples and action rows, subject to the stated limits; it is not the lead's acceptance decision. Pixel areas and heights below are the detector's 1280×720 coordinates; horizontal positions are fractions of width.

| Criterion | Trial 1 | Trial 2 | Trial 3 |
|---|---|---|---|
| First door | **Plaza door.** Step 1 logs a walk at `door_x=0.446`; native 24.47 s shows that door partly hidden by the central console, with stairs beyond. Native replay measures its blob at x 0.446, 3,611 px, **98 px tall**; the other door is larger (8,594 px, x 0.201). This sample exercises the short first-choice candidate. Step 2 keeps the plaza door at x 0.439. | **Plaza door.** Step 1 logs a walk at x 0.442; native 27.97 s has its blob at x 0.441, 4,361 px, 136 px tall, while the other door is larger (7,981 px, x 0.210). The short-height exception is **not demonstrated by this native sample**. | **UNKNOWN**; exit 0 does not identify the selected door. |
| a. Plaza pane covers the hero's column immediately before disappearance | **PASS.** Step 16 / 35.32 s: main pane blob spans x **0.317–0.467**, native hero column 0.416 (live log 0.417). Stairs, planter and Luna are beyond the opening. Step 17 / 36.12 s shows the hero outside beside the planter. | **PASS.** Step 17 / 40.05 s: pane blob x **0.263–0.434**, hero 0.416. Step 18 / 40.85 s shows him beyond the pane, beside the planter and stairs. | **INCOMPLETE**; no crossing frames. |
| b. OUT set, no step onto the door frame | **PASS on sampled crossing.** Step 17 explicitly logs `out: look around left`. Last three walks (14–16) have logged blob areas 36,750 / 36,533 / 20,862; next frame has none. Their live changes, reported on steps 15–17, are 22.46 / 25.82 / 22.08: advancing, no jamb stall. | **PASS on sampled crossing.** OUT is explicit at step 18. Last three walks (15–17): 38,225 / 39,347 / 21,306; next frame none. Live changes on steps 16–18: 20.98 / 25.42 / 21.99. Earlier console-rim stall is separate from the door crossing. | **INCOMPLETE**; no OUT/action rows available. |
| c. After OUT, no steer toward or walk at a door blob | **PASS, weakly exercised.** One left sweep at step 17, then standing confirmation. No qualifying door blob on that OUT frame; dark door housing remains at the right. No subsequent door-directed walk/turn in the log. | **PASS, weakly exercised.** Same pattern at step 18. No qualifying blob on the OUT frame. | **INCOMPLETE**. |
| d. Two live plaza confirmations, no door in view, a bot ahead | **PASS.** Live True at steps 18–19. Native 36.65 / 36.87 s show Luna Snow, name readable, at x about **0.52**, Hero Simulation console to her left, stairs right, no door visible. Step 20 / 37.60 s retains this end view. | **PASS.** Live True at steps 19–20. Native 41.42 / 41.62 s show Luna Snow, name readable, at x about **0.45**, console left, stairs right, no door visible. Step 21 / 42.38 s retains this end view. | **INCOMPLETE**; success text cannot substitute for two retained confirmations and a visual end pose. |

Native frame links: [trial 1 crossing](../../../data/reenter/arrive-20260921-183337/native/step16-native-v035.32.png), [trial 1 confirmation](../../../data/reenter/arrive-20260921-183337/native/step19-native-v036.87.png), [trial 2 crossing](../../../data/reenter/arrive-20260921-184506/native/step17-native-v040.05.png), [trial 2 confirmation](../../../data/reenter/arrive-20260921-184506/native/step20-native-v041.62.png).

**No-progress recovery:** trial 1 does not exercise it (`still=0` throughout; no sidestep). Trial 2 does: steps 5–7, native 30.80 / 31.62 / 32.43 s, show Spider-Man at the same raised central-console rim. Steps 6 and 7 report live changes **3.12** and **3.62**, `still=1` then `2`. Step 7 commands the first **0.40 s left sidestep**. At step 8 / 33.17 s the console is farther right and the route to the same plaza door is clear; step 9 / 33.97 s shows forward progress, live `moved=27.0`. Only one sidestep occurs. No fall is visible in these samples; this establishes one recovery, not general sidestep safety, the second-sidestep limit or terminal refusal. Trial 3 recovery is unknown.

Recovery links: [before sidestep](../../../data/reenter/arrive-20260921-184506/native/step07-native-v032.43.png), [after sidestep](../../../data/reenter/arrive-20260921-184506/native/step08-native-v033.17.png), [forward progress](../../../data/reenter/arrive-20260921-184506/native/step09-native-v033.97.png).

## Live values, replay values and limits

| Frames | LIVE step log | Native recording replay, rechecked | Saved 720p JPEG replay, rechecked |
|---|---|---|---|
| Trial 1 steps 18–19 | True / True | True / True | False / False |
| Trial 2 steps 19–20 | True / True | True / True | False / False |
| Other inspected arrival decision frames | False | False | False |
| RT rows: trial 1 step 20, trial 2 step 21 | null (not another live confirmation) | True | False |

Recheck uses only `plaza_view` and image readers on these retained files at local `a724e7bf4492`, in an isolated `uv run --no-project --with opencv-python --with numpy` process under `nice -n 10`. It agrees with all 21 existing replay rows. Native PNGs are compressed recording frames matched by appearance, **not** the tool's exact dxcam decision/proving frames. Existing match MADs are 1.38–1.95 for trial 1 and 1.36–2.32 for trial 2; the matching itself is not rerun here. The JPEG/native difference is not a live predicate failure. `plaza_view` detects a plausible enemy box; Luna identity above is visual evidence, not an identity guarantee from that predicate.

Logging precision matters:

- `door_blob_x` / `door_px` describe the largest blob under the ordinary 100 px height filter, **not necessarily the selected door**. Trial 1's short plaza candidate is absent from that default replay list while `door_x=0.446` correctly accompanies the walk. This is not a wrong-door selection.
- A turn row's `door_x` is prior/predicted state, not a certified selected blob. These rows do not establish identity tracking or recovery of a lost door from a new pose with two candidates.
- `gate` is constant policy text, not per-write proof evidence. `t` is logged after the action; the saved frame precedes it. First-to-last-row spans are **12.298 s** and **13.573 s**, omit the first action, and are not the full invocation wall times. `ARRIVE_S` budgets scheduled actions, not wall time.
- The logs report exit 0 for all three invocations. That does not prove a–d; in particular it does not prove OUT latched or that the selected door was the plaza door. Trial 3 stays incomplete.
- Both local trials only weakly exercise post-OUT behavior: neither supplies a qualifying door blob after OUT. No claim covers resisting a reappearing pane in these two runs. The third trial's branch coverage is unknown. Full-stream no-fall/input-safety audit and three distinct starting-cursor acceptance are not established by this bounded arrival inspection.

Only this Markdown file is authored. No PC access, capture, pad, deploy, corpus test, writer/kit/manifest change, label/training change, lane-doc edit, commit or Linear write occurs. Existing untracked replay files and other lanes' changes remain untouched. Independent review, acceptance, preservation/publication of retained evidence and integration belong to the lead; the missing third-trial visuals remain the concrete blocker to a complete three-arrival handback.

Reflection: the live/native/JPEG distinction and exit-code limits are already documented in the lane contract; no additional skill or rule change is warranted.
