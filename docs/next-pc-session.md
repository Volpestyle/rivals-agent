# James's next PC session (prepared 2026-09-23)

One page, in order. Times are approximate, from the first recording's start (T+0).

**Before T+0:**
- The game is in the Practice Range as Spider-Man, with the September 23 settings.
- OBS is running with the Rivals Input Logger reading "enabled and waiting".
- Only one agent drives the PC.

Recordings:
- **A:** step 1 only.
- **B:** step 2, the validation take, as its own recording.
- **C:** steps 3–5.

**Kill switch for any step that sends input:**
- **Alt-Tab, or click any other window.** The game reads the pad only while it has focus, and `scripts/place.py`
  re-proves focus and the range HUD before every 50 ms write, so the pad goes neutral and the run stops.
- **Ctrl-C** in the agent's terminal closes the pad.
- **Stop on any translation** (walking, strafing). Nothing here presses a button; only the right stick moves.

| # | Time | What James does | What the agent sends | Kill switch | What it unblocks |
|---|---|---|---|---|---|
| 1 | T+0 – T+1 | **Multi-speed calibration** (recording A; `recording-protocol.md`, "multi-speed calibration take"). Three full 360° yaw turns (slow, medium, fast flick-like), each ending where it started. Then the same three speeds as pitch sweeps, from the horizon down and back. About 40 s. | Nothing | Stop recording | Camera degree labels above ~30 °/s: 92 % of human yaw motion is now marked "extrapolated" |
| 2 | T+1 – T+16 | **Validation take** (recording B). **Say "validation take" in chat before starting.** 10–15 min, played exactly like training: the same mix, cooldowns on, tab in and out once, no pause. Don't rewatch it. This is the sitting's first real play, as the protocol requires (`recording-protocol.md`, "Validation and test takes"). | Nothing | Stop recording | The `val` split, registered before inspection and reported beside train, never added to it. Fit results need at least two takes per split before they count |
| 3 | T+16 – T+17 | **Settings screens, only if anything changed** since September 23 (recording C): a 5 s look at each changed Controls page. Before step 5, check the pad settings too, and show them if touched: **Linear curve, H/V 265/75, aim assist 0** (`lanes/l4-controller.md:1278-1298`). | Nothing | Stop recording | The session's motor identity pinned from pixels. Step 5's numbers hold only at those pad settings |
| 4 | T+17 – T+22 | **Five-minute lane look** (`lanes/placement.md` §6 and §8 row A). From the 25 m end facing the pair:<br>- both lane edges;<br>- 1 s strafes right and left;<br>- the drop and its respawn;<br>- the three failure states, each with a slow camera circle, not moving;<br>- the plaza approach;<br>- 2 s stops along both edges. | Nothing | Stop recording | `EDGE_X_M` and the drop edge (F4), the strafe rate, the bias bound, plaza negatives: the placement lane's live gates |
| 5 | T+22 – T+30 | **Agent measurements.** Every step here needs a measurement declaration: PID and range-entry record, `james_present_recording: true`, a window of at most 1 h, and the lead's authorization naming each mode (`place.py` docstring; `placement.md` §8). A re-entry voids it. For 5b the declaration also carries `"pad_settings": {"curve": "Linear", "horizontal": 265, "vertical": 75, "aim_assist": 0}`. James parks, lets go, and watches.<br>**5a pitch reset** (~3 min): at the 25 m end, facing the pair.<br>**5b low-end map** (~2 min): on the spawn plaza, away from drops, facing textured scenery, no bot near the crosshair. | **5a:** `place.py --measure-pitch --declaration …`. The M1 prime (right stick ±0.45 for 0.3 s each way), then 29 resets (stick y fully down 2 s, then +0.5 for 0.2–1.6 s), a full-up look, and 3 repeats.<br>**5b:** `place.py --lowmap --declaration …`. The same prime. Then, twice each: right stick x at 0.02, 0.04–0.10 held 1.0 s right then 1.0 s left; right stick y at 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5 held 0.5 s up then 0.5 s down. A settled frame (0.35 s) before and after every hold. | Alt-Tab / click away; Ctrl-C. Stop if the camera does anything but tilt (5a), or turn slowly and come back (5b) | **5a:** `PITCH_DOWN_S` / `PITCH_UP_S` for PITCH_RESET (F3). That enables the reset check at the three failure spots (`placement.md` §8 row C) in a later window, once the values are in code through review.<br>**5b:** `data/placement/lowmap-<stamp>.json`: each axis's deadzone and low-end map in Cal's fields, measured from frames by `perception/camera_motion.py`. It says `ok` only if every hold was fitted, moved with the stick's sign, the map is monotone, and the top rates match Cal's within 25 % (else the pad settings differ). This clears fit review K3 (blocking before any pilot) |

**Then** normal recording (`recording-protocol.md`), roughly two hours on to one hour off.

**Before the session:** a reviewer checks `--lowmap` (the lead has scheduled it). Without that review, skip 5b; the
rest of the session is unaffected.

**Afterwards:**
- James drops the three video paths in chat: "calibration" (A), "validation take" (B), and "placement look,
  placement measurement" (C).
- Intake tags spans: step 1 "calibration". Steps 4 and 5 are tagged "placement look" and "placement measurement" and
  are rejected for whole-session training.
- Step 5's values reach code only through a reviewed change. Later, the live declaration and `agent.controller.Cal`
  must repeat them.
