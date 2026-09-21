# L4 controller

Linear: VUH-1296. Evidence: `docs/evidence/l4/`. Raw measurements: `C:\rivals-agent\data\l4\` on the PC.

The game is in the Practice Range as Spider-Man where the third `cursor-cost` arrival ends: on the plaza beside the spawn
room door's planter, facing the Luna Snow bot, RT pressed once, idle, no pad connected
(`arrival-cost-3-20260921-155528-endpose.jpg`); the range's inactivity drop returns it to the lobby by itself. The PC holds
`agent/`, `scripts/` (with templates) and `perception/` from `git archive a7fff98`, all 42 tracked files verified by sha256,
nothing of this lane's scratch beside them. No gameplay run follows until the lead says so.

## Three supervised arrivals from spawn at a7fff98 (VUH-1299): `data/reenter/arrive-20260921-{153213,154347,155528}/`

Three full `scripts/reenter.py` invocations, each left to its own end: no strafe, no help, no other input, no 30 s run.
`capture.py preflight` passed (47 dxcam frames in 1 s); `--dry-run` read `practice_panel`, so invocation 1 starts from the
PRACTICE panel and 2 and 3 from the PLAY lobby after the game's own inactivity drop (lobby by 15:43:32 and 15:55:12, polled
with `--dry-run`). No refusal of any kind, no re-invocation. After each: 0 python left, 0 Xbox pads present.

**Every written press and its proof age** (the tool's own lines; limit 300 ms, acquisition start to check; no age refusal):

| Press | Invocation 1 | Invocation 2 | Invocation 3 |
|---|---|---|---|
| A, PRACTICE tab (lobby) | - (started on the panel) | **137 ms**: grab 77 (dxcam), classify 1, proof 59, checks 0 | **56 ms**: grab 4 (dxcam), classify 1, proof 51, checks 0 |
| A, PRACTICE RANGE tile (the press refused at 310-320 ms at 6f2e44e) | **68 ms**: grab 17 (dxcam), classify 1, proof 50, checks 0 | **152 ms**: grab 91 (dxcam), classify 1, proof 59, checks 0 | **120 ms**: grab 67 (dxcam), classify 1, proof 51, checks 0 |
| RB | 5 ms: grab 4, classify 1, proof 0, checks 0 | 17 ms: grab 16, classify 1 | 11 ms: grab 10, classify 1 |
| RB | 5 ms: grab 4, classify 1 | 13 ms: grab 12, classify 1 | 5 ms: grab 4, classify 1 |
| A, Spider-Man (tooltip match 0.94 / 1.00 / 0.92) | **76 ms**: grab 5, classify 1, proof 70, checks 0 | **92 ms**: grab 7, classify 1, proof 83, checks 0 | **88 ms**: grab 4, classify 1, proof 83, checks 0 |
| X | 5 ms: grab 4, classify 1 | 5 ms: grab 4, classify 1 | 4 ms: grab 3, classify 1 |
| RT (in the range) | 9 ms: grab 7, classify 2 | 14 ms: grab 12, classify 2 | 5 ms: grab 4, classify 2 |

On the PC the cursor proof is 50-59 ms and the tooltip proof 70-83 ms; the largest age is 152 ms, and what varies is the
grab (4-91 ms, all dxcam, no GDI grab on any press). Full tool output: `arrival-cost-N-...-reenter.log`.

**Native evidence.** A native 2560x1440 60 fps recording (`ddagrab` -> `h264_nvenc`, `-cq 19`, 85 s, started just before
each invocation): `data/video/cost{1,2,3}.mp4` on the Mac and in `C:\rivals-agent\data\video\` (497, 480, 496 MB;
gitignored). Native PNGs of the recording frame best matching each step's decision JPEG (mean abs difference 1.3-2.0 grey
levels at 320x180): `data/reenter/arrive-<time>/native/` (steps 15-20 for arrivals 1 and 2; steps 1-6 and 16-21 for arrival
3). They are frames of the recording, not the tool's proving frames. No sidestep fired, so there are no sidestep frames.

**LIVE `plaza_view` and replays, kept apart** (`arrival-cost-N-...-replay.jsonl`): LIVE is True on exactly the two
confirmation steps of each arrival (18-19, 18-19, 19-20) and False on every other action row. REPLAY on the native recording
frames: True on all six confirmations, False on the walk and OUT frames. REPLAY on the saved 720p JPEGs: False on all six.

| | Arrival 1 (15:32:09) | Arrival 2 (15:43:43) | Arrival 3 (15:55:24) |
|---|---|---|---|
| Exit code / last line | **0**, `in the Practice Range as Spider-Man` | **0**, same | **0**, same |
| Rows / arrival elapsed (first row's log to last) / invocation wall (`START` to `EXIT`) | 20 / **12.36 s** / 31.5 s (from the panel) | 20 / **12.34 s** / 43.5 s | 21 / **12.69 s** / 42.9 s |
| Door taken in frame 1 | the PLAZA door (0.443; the other door at 0.21 the larger blob) | the PLAZA door (0.444; the other door at 0.20 the larger) | **the OTHER door**: step 1 is a 0.17 s LEFT turn, the turn for a door at 0.20, then two walks at it (steps 2-3, selected pane 0.473, 0.472). The plaza door is in view at ~0.44, half hidden behind the central column, 3.5k px on the recording frame (REPLAY) and under the 3k floor on the saved JPEG; LIVE it was not selected |
| Kept door lost and re-chosen mid-walk | no (largest step-to-step move of the selected pane 0.10) | no (0.10) | **yes, once, at step 5**: after the 0.08 s right turn the other door's blob is gone (REPLAY: the only blob is the plaza door, 23.9k at 0.665, 0.26 from the predicted 0.402, past `DOOR_KEEP` 0.25), and the re-choice takes the plaza door, a 0.21 s right turn, then walks at it to the end. It was the ONLY blob: 'nearest his column' between TWO doors from a changed pose is still NOT EXERCISED |
| a. pane over his column on the step before the door vanishes, and it is the plaza door | **PASS**: native step 16, pane 0.26-0.47, hero 0.417; step 15, 0.32-0.51. Planter, stairs and plaza beyond it | **PASS**: native step 16, pane 0.27-0.47, hero 0.418; step 15, 0.25-0.50 | **PASS**: native step 17, pane 0.27-0.47, hero 0.418; step 16, 0.30-0.51. The plaza door |
| b. OUT set, no step onto the door frame | **PASS**: walks at 37.5k, 36.6k, 17.1k, then no door, `out: look around left` (step 17). No snag: every walk moved 23.8-35.3 | **PASS**: walks at 37.0k, 47.2k, 23.1k, OUT on step 17. No snag (moved 21.4, 28.9, 19.4) | **PASS**: walks at 36.7k, 37.6k, 14.8k, OUT on step 18. No snag (moved 22.1, 29.1, 36.8) |
| c. after OUT: no steer toward and no walk at any door blob | **PASS, weakly exercised**: one left turn on a frame with no lime blob | **PASS, weakly exercised**: the same | **PASS, weakly exercised**: the same |
| d. the end: plaza_view twice LIVE, no door in view, a bot ahead | **PASS**: LIVE True on steps 18, 19; no lime in view. On the plaza beside the door's planter, facing the Luna Snow bot (name bar readable) at x ~0.40, mid distance, the Hero Simulation console to her left, the stairs to the right; the hero drawn faded, the camera pushed up to him by the planter | **PASS**: LIVE True on steps 18, 19; same place, the bot at x ~0.43 | **PASS**: LIVE True on steps 19, 20; same place, the bot at x ~0.42 |
| e. no-progress | **NOT EXERCISED**: no stall, no sidestep | **NOT EXERCISED**: no stall, no sidestep | **NOT EXERCISED**: no stall, no sidestep |

**(e) Every completed walk, LIVE `moved` / `still`** (read on the row after the walk; `still` is 0 on every row of all three):
- Arrival 1, walks at steps 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16: moved 25.2, 27.1, 27.7, 25.2, 30.0, 44.3, 40.9, 34.5,
  33.6, 37.3, 23.8, 30.9, 35.3.
- Arrival 2, the same steps: 26.3, 27.2, 24.2, 25.7, 34.8, 40.9, 42.1, 36.0, 33.1, 35.0, 21.4, 28.9, 19.4.
- Arrival 3, walks at steps 2, 3, 6, 7, 8, 9, 11, 12, 13, 15, 16, 17: 25.9, 31.9, 30.5, 29.4, 41.2, 43.9, 32.1, 33.7, 35.3,
  22.1, 29.1, 36.8.
The smallest is 19.4 (arrival 2's last walk, through the door), against the 8.0 stall line. No stall was detected and none
happened by eye: no walk into the console's rim in any of the three (the step-5 brush of the second round does not show;
those walks moved 25-30). **No sidestep fired, so no false stall either.** The recovery is not exercised; none was provoked.

Seen in all three, not part of a-e: the first plaza confirmation is taken while the view is still moving. Between the two
confirmation frames (0.2 s apart on the recording) the Luna bot moves from x ~0.80 to x ~0.40-0.43 of the frame: the 0.3 s
left look-around has not finished turning when the 'second look, standing still' frame is judged. Both frames read True
LIVE in every arrival.

Evidence: `arrival-cost-{1,2,3}-20260921-<time>-sheet.jpg` (contact sheet per arrival: door blobs yellow, the row's
`door_x` cyan, hero column red, target ticks white), `...-steps.jsonl`, `...-reenter.log`, `...-replay.jsonl`,
`...-endpose.jpg` (desktop screenshot after each end, no input), `arrival-cost-{1,2,3}-native-frames.jpg` (native crossing,
OUT, the confirmations and the end pose; arrival 3's also has steps 1 and 5).

## No-input timing of the re-entry proof on the PRACTICE panel (VUH-1299): the age at the write is NOT MEASURABLE there with no pad

`scripts/reenter.py --dry-run --timing 50` on the screen the game is on (`practice_panel`), at 6f2e44e, nothing changed, no
pad created, nothing pressed, no navigation. After each run: 0 python left, 0 Xbox pads present. Logs:
`reenter-timing-practice-panel-{norec-1,norec-2,recorder}.log`.

**All 150 rounds stop before the age check: `refused=no proof for A: the cursor ring was not found`, `age_ms=nan`,
`tap_frame_ms`, `tap_gdi_ms`, `tap_classify_ms`, `tap_proof_ms` all 0.** With no pad connected the game draws no click cursor
on this panel (its hints are the keyboard's), so `Safe.press` refuses at its own proof and `Live.tap`, where the age is
compared with the 0.3 s limit, is never entered. The distribution of the proof's age at the write, and how many of 50 would
have been refused for age, cannot be had from this mode on this screen without a pad and a stick move, which this
measurement does not allow. The mode times one screen's path only, the screen it is on: it says nothing about the lobby's A.
It prints no settle stage.

What it does measure, per condition (`safe_ms` = `Safe.press`'s own frame, classify and one proof attempt, here a
`find_cursor` that finds no ring):

| Condition | `safe_ms` min / p50 / p95 / max (n = 50) | dxcam probe (2 s) | Game's FPS counter | PC CPU load samples |
|---|---|---|---|---|
| 1. no recorder, first run | 92 / 208 / 255 / 259 | 151 frames in 746 grabs; first after 47 ms; gap p50 8 ms, max 45 ms | not read | not sampled (a wrapper bug of this lane's lost the samples) |
| 1. no recorder, second run | 85 / 221 / 256 / 261 | 145 frames in 828 grabs; first after 28 ms; gap p50 7 ms, max 68 ms | 471 | 62, 56, 58 % |
| 2. native recorder running as for the arrivals (`ddagrab` -> `h264_nvenc`, 60 fps, `-cq 19`) | 171 / 219 / 259 / 260 | 129 frames in 884 grabs; first after 62 ms; gap p50 10 ms, max 68 ms | 414 | 49, 51, 55, 68 % |

Read plainly: the recorder does not move `safe_ms`'s p50, p95 or max (its min rises from ~90 to 171 ms); the panel is not a
static screen to dxcam (65-75 frames/s arrive); one frame + classify + one proof attempt costs up to 261 ms on the PC against
a 300 ms age limit, and a real press runs the proof twice (`Safe.press`, then `Live.tap` on its own frame). Whether `tap`'s
pass costs the same when the ring IS there is not measured here.

**Lobby A against tile A: not measurable with `--timing`** (one screen, and not past `Safe` here). Offline only, on the
Mac, not the PC, over stored frames (30 repeats each): `find_cursor` 45-47 ms whether or not a ring is present; `on_practice_tab`
45-48 ms; `on_practice_range_tile` 46-48 ms (its two checks, cursor on the tile and DOOM MATCH not highlighted, add 1-2 ms
to the cursor search); `classify` 0.1-0.3 ms. On the Mac the two proofs cost the same to within 2 ms and almost all of it
is the cursor search; the PC's `safe_ms` is about 4-5 times the Mac's proof time, with the game at 414-471 FPS taking
half the CPU.

## Third round of supervised arrivals at 6f2e44e (VUH-1299): stopped at a refusal before the range, no arrival ran

Deploy at 6f2e44e hash-verified (42 files), `capture.py preflight` passed (98 dxcam frames in 1 s), `--dry-run` read `lobby`.
Attempt 1, with the native recorder started just before it as in the second round:

| Invocation | What it logged | Exit / wall |
|---|---|---|
| 1 (14:47:30) | `screen lobby`, `A (cursor (1223,392) is on the PRACTICE tab; TRY COMPETITIVE is idle)`, `screen practice_panel`, `A (cursor is on the PRACTICE RANGE tile; DOOM MATCH is not)`, then `STOP: the proof is 0.31 s old (limit 0.3 s); A not sent` | 1 / 17.3 s |
| `--dry-run` after it | `screen: practice_panel`, a recognised screen, so the one pre-authorized re-invocation ran | - |
| 1b (14:49:07), the one re-invocation | `screen practice_panel`, `A (cursor is on the PRACTICE RANGE tile; DOOM MATCH is not)`, then `STOP: the proof is 0.32 s old (limit 0.3 s); A not sent` | 1 / 6.7 s |

No third invocation. **Attempts 2 and 3 did not run and a-e are NOT EXERCISED for the whole round**: the no-progress test and
the sidestep never ran live. The reasons to stop rather than go on: the same guard refused the same press twice, 10-20 ms
over its limit, which is not a one-off; and the game is on the PRACTICE panel, not the PLAY lobby the order starts from,
and leaving it is lobby navigation. The guard did its job: no A went out on a proof older than the limit, and nothing else
was sent. After each invocation: 0 python left, 0 Xbox pads present.

Facts for the re-entry owner (the cause is not established here):
- The refused press is the A on the PRACTICE RANGE tile; the lobby's A, one step earlier in the same invocation, passed.
- The same press passed 6 of 6 times in the first two rounds today (the second round with the same recorder running).
- `git diff 90aaeb0 6f2e44e` touches only the arrival (`_scene`, `STILL`, the sidestep); the menu proof path is unchanged.
- The panel is a static screen. With no input and no recorder running the PC read 61 % CPU load, the game taking 15.9
  CPU-seconds in 3 s, its own counter at 467-540 FPS on this menu.
- Recordings of both invocations (native, `ddagrab` -> `h264_nvenc`): `data/video/stuck1.mp4` (57 MB) and
  `data/video/stuck1b.mp4` (12 MB) on the Mac and in `C:\rivals-agent\data\video\`. Refusal frames:
  `arrival-stuck-1-refuse-20260921-144747.jpg`, `arrival-stuck-1b-refuse-20260921-144913.jpg` (originals in `data/reenter/`).

## Three supervised arrivals from spawn at 90aaeb0, second round (VUH-1299): `data/reenter/arrive-20260921-{133804,135001,140151}/`

Three full `scripts/reenter.py` invocations from the PLAY lobby, each left to its own end: no strafe, no help, no other
input, no 30 s run. `capture.py preflight` passed (145 dxcam frames in 1 s). Between arrivals the game went back to the lobby
by its own inactivity drop (polled with `--dry-run`, which holds no pad): lobby by 13:49:46 and by 14:01:37. Every menu step
passed first time in all three (tooltip match 0.92, 1.00, 1.00); no refusal before the range, no re-invocation. After each:
0 python left, 0 Xbox pads present.

**Native evidence.** A native 2560x1440 60 fps screen recording (`ffmpeg`, `ddagrab` straight into `h264_nvenc`, `-cq 19`,
85 s, started just before each invocation) covers every arrival whole: `data/video/door{1,2,3}.mp4` on the Mac and
`C:\rivals-agent\data\video\` on the PC (432, 432, 384 MB; gitignored). For the crossing and the final two plaza
confirmations the recording's frame that best matches each step's saved decision JPEG (mean abs difference 1.4-2.0 grey
levels at 320x180) is kept as a native PNG: `data/reenter/arrive-<time>/native/stepNN-native-v<video s>.png` (steps 13-18 for
arrivals 1 and 2; steps 4, 5, 6, 12, 20, 21 for arrival 3, which has no crossing). These are frames of the recording, within
one 60 fps frame of the decision frame by appearance; they are not the tool's own proving frames.

**Live predicate results and replays, kept apart.** LIVE is what `reenter.py` logged at the time. REPLAY is `plaza_view` run
afterwards on a stored image, nothing changed in it (`arrival-door-N-...-replay.jsonl`).

| Step | LIVE `plaza_view` | REPLAY on the native recording frame | REPLAY on the saved 720p JPEG |
|---|---|---|---|
| Arrival 1, steps 13, 14 (walks at the door), 15 (out) | False, False, False | False, False, False | False, False, False |
| Arrival 1, steps 16, 17 (the two confirmations) | **True, True** | True, True | **False, False** |
| Arrival 2, steps 13, 14, 15 | False, False, False | False, False, False | False, False, False |
| Arrival 2, steps 16, 17 | **True, True** | True, True | **False, False** |
| Arrival 3, steps 4, 5, 6, 12, 20 | False throughout | False | False |

The 720p JPEGs do not reproduce the live True; the native recording frames do, on all four confirmations.

Verdicts are by eye on the retained frames, not from the exit code or the row fields (`door_blob_x` / `door_px` are the
largest current blob, a turn's `door_x` the prior or predicted door, `gate` constant policy text, `t` the logging time after
the action). Arrival elapsed is first row's log to last row's log (it leaves out the first step); `ARRIVE_S` is scheduled
action time, not a wall-clock deadline. Invocation wall time is `START` to `EXIT` of the whole `reenter.py` process.

| | Arrival 1 (13:38:00) | Arrival 2 (13:49:57) | Arrival 3 (14:01:47) |
|---|---|---|---|
| Exit code / last line | **0**, `RT`, `in the Practice Range as Spider-Man` | **0**, same | **1**, `could not confirm the spawn room was left within 14 s` |
| Rows / arrival elapsed / invocation wall | 18 / **11.48 s** / 46.5 s | 18 / **11.42 s** / 41.9 s | 21 / **15.01 s** / 49.0 s |
| Door taken in frame 1 | the PLAZA door, nearest his column (0.442; the other door 0.17, the larger blob in frames 2-3) | the PLAZA door (0.442; the other door at 0.20 is the larger blob in frames 1-2: 8.4k against the plaza door's smaller one) | the PLAZA door (0.441; the other door at 0.20 the larger blob in frames 1-2) |
| Kept door lost and re-chosen mid-walk | no: no `no door` row before OUT, largest step-to-step move of the selected pane 0.09 | no: largest move 0.09 | no: the selected pane stays at 0.37-0.39 for 16 walks. 'Nearest his column' from a changed pose is NOT EXERCISED in any of the three |
| a. pane over his column on the step before the door vanishes, and it is the plaza door | **PASS**: step 14 (native), pane 0.34-0.50, hero 0.414; step 13, 0.37-0.51. The plaza door: the planter, the stairs and the Luna bot are beyond it | **PASS**: step 14 (native), pane 0.41-0.54, hero 0.417 (12 px inside the pane's left edge); step 13, 0.36-0.54 | **NOT EXERCISED**: he never reaches the door |
| b. OUT set, no step onto the door frame | **PASS**: walks at 23.8k and 16.6k, then no door, `out: look around left` (step 15). No jamb snag: the pane shrinks steadily 40k -> 37k -> 24k -> 17k over steps 11-14 | **PASS**: walks at 30.3k and 30.2k, then no door, OUT on step 15. No snag (88k -> 47k -> 37k -> 30k) | **NOT EXERCISED** |
| c. after OUT: no steer toward and no walk at any door blob | **PASS, weakly exercised**: one post-OUT step, a left turn, on a frame with no lime blob (native replay: no blobs on steps 15-18) | **PASS, weakly exercised**: the same, one left turn, no lime blob in view | **NOT EXERCISED** |
| d. the end: plaza_view twice, no door in view, a bot ahead | **PASS**: LIVE True on steps 16 and 17, no lime in view. He stands on the plaza beside the door's planter and faces the Luna Snow bot (name bar readable) at x ~0.54, mid distance, the Hero Simulation console to her left, the stairs to the right. RT pressed once | **PASS**: LIVE True on steps 16 and 17, no lime in view. Same place and heading: the Luna Snow bot ahead at x ~0.59, the console to her left. The hero is drawn faded (the camera is pushed up against him by the planter behind; `hero_x` reads 0.98, not his column) | **FAIL**: `plaza_view` False throughout. He ends INSIDE the spawn room, stuck against the central console's rim, facing the plaza door (23k px at 0.37) across it; no bot in view |

Arrival 3, what the frames show: steps 1-4 are the same as in arrivals 1 and 2 (three walks, a 0.08 s right turn). From
step 5 on every frame is the same view: 16 walk steps into the raised rim of the room's central console, the plaza door on
his column at 0.37-0.39 the whole time, its blob flickering between 11.8k and 26.3k px with the pane's own animation, no
advance (`arrival-door-3-native-stuck-at-console.jpg`). In arrivals 1 and 2 the same rim is brushed on steps 5-6 and he
slides off it (pane 24k -> 31k -> 38k and 21k -> 15k -> 27k -> 41k); in arrival 3 he does not (18k -> 16k -> 20k -> 26k ->
24k). At step 5 the selected pane sits at 0.381, 0.380 and 0.372 in the three: about 10 px of heading between sliding past
and sticking (`arrival-door-steps4-6-compared.jpg`). Nothing in the arrival notices a walk that does not move him.

Evidence: `arrival-door-{1,2,3}-20260921-<time>-sheet.jpg` (one contact sheet per arrival: door blobs yellow, the row's
`door_x` cyan, hero column red, target column ticks white), `...-steps.jsonl`, `...-replay.jsonl`, `...-endpose.jpg`
(desktop screenshot after each end, no input), `arrival-door-{1,2}-native-crossing-out-plaza-end.jpg` (native steps 14, 15,
the confirmation and the end pose), `arrival-door-3-native-stuck-at-console.jpg`, `arrival-door-steps4-6-compared.jpg`.

## Three supervised arrivals from spawn at 8c5f800 (VUH-1299): `data/reenter/arrive-20260921-{125409,130539,131747}/`

Three full `scripts/reenter.py` invocations from the PLAY lobby, each left to its own end: no strafe, no help, no other
input, no 30 s run. `capture.py preflight` passed (96 dxcam frames in 1 s). Between arrivals the game went back to the lobby
by its own inactivity drop (polled with `--dry-run`, which holds no pad): 12:54:50 -> lobby by 13:05:24; 13:06 -> lobby by
13:17:32. Every menu step passed first time in all three (tooltip match 0.87, 1.00, 0.94); no refusal before the range, no
re-invocation. After each: 0 python left, 0 Xbox pads present.

Verdicts are by eye on the retained frames, not from the exit code or the row fields. In the rows a turn's `door_x` is taken
before that frame's selection (None or the predicted prior-door position) and `door_blob_x` / `door_px` are the LARGEST
current blob, not necessarily the kept door; `gate` is constant policy text; `t` is the logging time after the action; most
frames are the decision frame before it. On the sheets every door-sized lime blob is boxed in yellow (recomputed from the
saved 720p JPEG, the largest thick), the row's `door_x` is the cyan line, the hero column the red line, and the white ticks
are the steering target 0.40 +- 0.08. Elapsed is first row's log to last row's log, which leaves out the first step
(one 0.16-0.5 s action); `ARRIVE_S` is a budget of scheduled action time, not a wall-clock deadline.

| | Arrival 1 (12:54:09) | Arrival 2 (13:05:39) | Arrival 3 (13:17:47) |
|---|---|---|---|
| Exit code / last line | **1**, `could not confirm the spawn room was left within 14 s` | **0**, `RT`, `in the Practice Range as Spider-Man` | **1**, same stop as arrival 1 |
| Rows / elapsed | 23 / **14.99 s** | 20 / **12.04 s** | 23 / **15.18 s** |
| Door taken first | the room's OTHER lime door (left of the plaza door): in frame 1 it is the bigger blob (8.2k px at 0.14-0.26, the plaza door 3.5k at 0.40-0.49), he turns left to it and keeps it | the plaza door: in frame 1 it is the bigger blob (6.0k at 0.41-0.49, on his column; the other door 5.8k) and he keeps it while the other door is the largest blob in frames 2-3 | the OTHER door, as arrival 1 (7.3k at 0.16-0.26 against 5.6k) |
| a. the crossing: pane over the hero's column on the step before the door vanishes | other door (step 10 -> none on 11): the logged blob is a 3.4k strip at 0.45, 40 px right of his column (0.418), under the JPEG recompute's size floor; the pane covered his column one step earlier (0.20-0.49). Through with no snag. **Plaza door: NOT EXERCISED** (never crossed) | **PASS**: step 16, pane blob 0.31-0.52, hero 0.416; step 15, 0.37-0.53 | other door (step 10): strip 0.42-0.50, its left edge on his column (0.417). **Plaza door (step 21): PASS, marginal**: blob 0.31-0.42, hero 0.416 at its right edge. Through both with no snag |
| b. OUT set, no step onto the door frame | **FAIL**: never set. The last walk before the door vanished was at a 3.4k px blob (19.1k the step before), under `OUT_PX` 20k. No jamb snag | **PASS**: last walk at 26.8k, next frame no door, `out: look around left`; no jamb snag (blob 44k -> 34k -> 27k over steps 14-16, steady advance) | **FAIL** on both crossings: last walks at 7.6k (other door) and 7.7k (plaza door; 19.9k the step before). No jamb snag |
| c. after OUT: no steer toward and no walk at any door blob | **NOT EXERCISED** (OUT never set). What the rule is for did happen: outside the other door he looked right, turned to the room seen back through that door (steps 12-13) and walked back in (14-15), then turned to the plaza door (16) and walked at it five times (17-21) | **PASS, weakly exercised**: one post-OUT step, a left turn, on a frame with no lime blob in it | **NOT EXERCISED**. Same walk back in through the other door (steps 12-15), then the plaza door (16-21), through it on step 21; then `no door: look around` turns him RIGHT (the pre-OUT branch), and the final frame has a 7.7k sliver of the pane at 0.37-0.42 on his column (0.391): the next step would have walked at it, had budget remained |
| d. the end: plaza_view twice, no door in view, a bot ahead | **FAIL**: `plaza_view` False throughout. He ends INSIDE the spawn room at the plaza door's right jamb, facing out through the pane (29k blob at 0.21-0.40), planter and stairs beyond it, no bot in view | **PASS**: `plaza_view` True on steps 18 and 19, no lime in view; he stands on the plaza beside the door's planter facing the Luna Snow bot (name bar readable) just right of his column at mid distance, the Hero Simulation console to her left, the stairs to the right. RT pressed once | **FAIL**: `plaza_view` False throughout. He ends OUTSIDE on the plaza side, at the door, facing its dark housing edge-on with the pane's sliver on his column; planter at the left edge, the room's pillars to the right of the housing; no bot in view |

What the three show together:
- Which door he takes is decided by frame 1: the two lime doors are within 0.3k-4.7k px of each other there, and he takes
  whichever is the larger blob. Keeping the chosen door works (arrival 2 keeps the plaza door through two frames where the
  other is larger; arrivals 1 and 3 keep the other door all the way through it).
- OUT was set on 1 of the 4 crossings seen. The pane's blob shrinks as he reaches it (the last walk is at 3k-8k px on three
  crossings, 27k on one; the step before that is 19.1k, 19.9k, 34k), so the 20k test on the last walk misses.
- With OUT not set, the old behaviour is unchanged: a look-around to the RIGHT finds the door just left, from outside, and he
  walks back at it. The 14 s budget then ends the arrival wherever he is.
- `plaza_view` needs the bot's box between 0.35 and 0.95 of the width; it says the green finder has a plausible box there
  with little lime round it, not that the box is a bot. In arrival 2 the box is the Luna Snow bot by eye.

Evidence: `arrival-out-{1,2,3}-20260921-<time>-sheet.jpg` (one contact sheet per arrival), `...-steps.jsonl`,
`...-endpose.jpg` (desktop screenshot after each end, no input), `arrival-out-2-crossing-out-plaza-end.jpg` (steps 16, 17,
19 and the end pose), `arrival-out-3-crossings-end.jpg` (steps 9-12 and 20-23 and the end pose).

## Supervised arrival measurement (VUH-1299): `data/reenter/arrive-20260921-122442/` on the PC and the Mac

One real `scripts/reenter.py` invocation at 8c73f21 with the arrival's step log, left to run to its own end: no strafe, no
correction, no other input, no 30 s run. `capture.py preflight` passed (61 dxcam frames in 1 s). The game had dropped to the
lobby by itself; `--dry-run` read `lobby`. Menus passed first time: PRACTICE tab, PRACTICE RANGE tile, `hero_select`, `RB`,
`RB`, `A (... SPIDER-MAN (match 1.00) beside the cursor at (856,39))`, `X`, `in_range`. Then
`STOP: could not confirm the spawn room was left within 14 s`, `24 arrival steps logged`, exit 1; 0 python left, 0 Xbox
pads present. Rows: `arrival-20260921-122442-steps.jsonl`. Sheets with the door blob's box (yellow, the blob nearest the
logged `door_blob_x`, recomputed from the saved 720p JPEG) and the hero column (red): `arrival-20260921-122442-sheet.jpg`
(all 24), `arrival-20260921-122442-steps12-24.jpg` (larger).

How to read the rows: `gate` is the same constant policy text on every row, the refused one included; it is not a measured
verdict and not the actuator's proving frame. `t` is the logging time AFTER the action. Frames 1-23 are the decision frame
BEFORE that row's action; frame 24 (the refusal) is the last frame looked at, after step 23's walk. No RT row exists: the
arrival never reached the RT. Nothing here says when a frame was acquired or that a proof completed. `plaza_view` is False
on all 23 action rows.

| Steps | t after the first row (s) | Action (from the row) | `door_x` / `door_px` / `hero_x` | By eye on the frame |
|---|---|---|---|---|
| 1-5 | 0.0-2.5 | walk, turn left 0.24 s, walk, turn right 0.27 s, walk | 0.44, 0.17, 0.54, 0.88, 0.47 / 4.8k-16.9k / 0.38-0.42 | inside the spawn room; two lime doors are in view in frames 4 and 5, and the blob changes between them (0.17 then 0.54 then 0.88 then 0.47) |
| 6-10 | 3.4-6.6 | five walks | 0.47-0.48 / 29k -> 63k / 0.416-0.418 | straight at the door from inside, the plaza and the Luna bot seen through the glass |
| 11-12 | 6.8-7.7 | turn right 0.08 s, walk | 0.59, 0.50 / 48k, 44k / 0.42, 0.39 | at the door, inside. The glass fills the view's left two thirds; the blob is only the saturated right part of the pane |
| 13-15 | 8.5-9.5 | walk, turn right 0.08 s, walk | 0.52, 0.59, 0.52 / 54k, 31k, 33k / 0.42, 0.42, 0.39 | **crossing the threshold.** The plaza is in the open to the left (Luna bot in clear view at x ~0.22, left of `plaza_view`'s 0.35-0.95 window); the blob is the strip of pane against the right jamb, over the planter |
| 16 | 10.0 | no door: look around, right 0.30 s | none / 0 / 0.42 | **outside.** The planter ahead, the door's dark housing to the right, no lime blob |
| 17 | 10.9 | **door ahead: walk** | 0.56 / 3.8k / 0.39 | outside, facing the door's dark housing; the blob is a 53 px wide lime sliver of the pane's edge. He walks at it |
| 18-19 | 11.4-11.9 | look around right, twice | none | the housing at point blank, then the housing's side with the room behind it |
| 20 | 12.3 | door off centre: turn right 0.24 s | 0.82 / 87k / 0.38 | **the door from OUTSIDE**: the pane with its green cross, the spawn room's pillars seen through it |
| 21-23 | 13.1-14.7 | three walks | 0.54, 0.50, 0.57 / 67k, 94k, 77k / 0.39, 0.42, 0.42 | walking back at the door from outside |
| 24 | 14.7 | refused | none / 0 / 0.42 | beside the housing, facing into the spawn room |

The lead's questions, from the rows and frames:
- **(a) He passes through the door.** The door stops being ahead on **step 16**: steps 13-15 are the crossing (the blob is
  the pane's strip at the right jamb while the plaza is open to the left), and step 16's decision frame has no door blob and
  shows the plaza-side planter.
- **(b) Yes, the walk-back is in the rows.** After one look-around (step 16) the blob is the pane's edge seen from outside
  and he walks at it (step 17); two more look-arounds bring the whole pane into view from outside (step 20, 87k px, the
  biggest blob of the run), he centres it and walks at it three times (steps 21-23, 1.5 s of forward stick).
- **(c) At the jamb** (step 21, outside): the pane's box is x 533-802 of 1280, centred at 0.54, and he stands at 0.39 in
  front of the dark frame to the pane's left: the expected picture (pane 0.49-0.58, hero ~0.40). Step 22: pane 0.50
  (box 374-796), hero 0.42, his column now inside the pane's box. Step 23: pane 0.57 (box 563-853), hero 0.42, just left of
  the box, with the room in open view to the pane's left.
- **(d) End pose** (frame 24 and `after-arrival-20260921-1228.jpg`, the same view 3 min later): he stands at ~0.41 beside
  the door's dark housing (x 0.56-0.88, blue triangles, cyan strips), which is immediately to his right; he faces into the
  spawn room along its inner ring, one of the room's tall glass pillars to the left and the room's other lime door small in
  the distance at x ~0.55; the plaza's planter shows behind the housing at the right edge. No lime blob, `plaza_view` null
  on the refusal row and False on every row before it. Whether his feet are inside the threshold cannot be read from the
  frame; there is no glass between the camera and the room.

Timing: the 14.0 s budget is a counter (0.75 per walk, turn + 0.15, 0.45 per look-around; 15 walks, 5 turns and 3
look-arounds add up to 14.26); from the first row's log to the last is 14.70 s. Log-to-log intervals are 0.80-0.82 s per
walk step, 0.51-0.52 s per look-around, 0.28-0.46 s per turn, so each step costs about 0.05-0.07 s more wall time than its
budget share. The five earlier arrivals have no step rows, so a
per-step comparison does not exist. Their end differs by eye: those ended outside at the door's plaza-side pillar
(`reach30` started there); this one ends at the doorway facing into the room, after three walks back at the pane.

## Supervised run `reach30` (VUH-1314): `data/l1/reach30/` on the PC and the Mac

30 s, scripted brain, `--cooldowns normal` (from play before the run: ammo 2 after three shots, Get Over Here showing 7,
`cooldowns-normal-verified-7.jpg`; the cooldowns script read the switch as already off and pressed nothing). `meta.json`
carries `patch: null` (the kit doc is not on the PC); patch not read from the screen, the kit doc's Season 10, Version
20260911 stands. This run is not certification of no falls or of reliable episodes; it shows what is written here and no more.

Entry, `scripts/reenter.py` (`capture.py preflight` passed first, 107 dxcam frames in 1 s; `--dry-run` read `lobby`):
hero select and the A proof **passed first time**: `screen hero_select`, `RB`, `RB`,
`A (the game's tooltip names SPIDER-MAN (match 0.92) beside the cursor at (851,42))`, `X`, `screen in_range`, then the known
arrival stop (exit 1, `could not confirm the spawn room was left within 14 s`) with him outside on the plaza side of the
door. No re-invocation was needed, no hand navigation. After the pad connected a throwaway forward / back move went out
before any turn. The run started facing the door's plaza-side pillar, a few metres from it, the bot behind him.

| | `reach30` | `handoff30` |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions; 0 python left, 0 Xbox pads present | same |
| Reflex | 55.8 Hz; tick p50 / p95 / max 9.0 / 13.1 / 17.9 ms; 2 of 1,676 ticks over budget | 56.1 Hz; 9.0 / 12.7 / 22.3; 8 of 1,683 |
| Aim finder | 6.0 / 8.8 / 13.7 ms | 5.9 / 8.6 / 15.5 |
| Decision | 10.1 Hz; 52 / 67 / 93 ms | 10.0 Hz; 55 / 69 / 83 |
| Scoreboard (parsed) | **0 KOs**, 0 deaths, 55 damage, accuracy 0 %, Web-Cluster accuracy 0 % | 0 KOs, 0 deaths, 250 damage |

**Engaged seconds by target kind, by eye on the drawn frames** (`reach30-sheet.jpg`: crop white, decision boxes cyan, crop
boxes yellow, the held target red). Criterion for the reach rule: a box AT OR UNDER THE HEIGHT CUTOFF (`reach_h` = 0.0325 of
frame height = 47 px at 1440p) versus a target with a MEASURED distance inside / outside the 40 m cap. Engaged total 14.0 s
(784 ticks).

| Kind | Engaged | Ids |
|---|---|---|
| Real bot in reach (the Luna Snow bot; picked at 123-199 px, above the cutoff; no measured distance) | 5.5 s | 11, 16, 44, 67, 68 |
| Box at or under the height cutoff | **0 s**: none picked. The smallest picked box is 90 px. 33 crop ids of 28-46 px appeared (the small distant boxes through the archway, door slivers) and none was picked | - |
| Measured out of the cap | **NOT EXERCISED**: none of the 140 decision detections carried a distance, so every reach decision in this run is the height criterion | - |
| Door from the plaza side (leaf, cross, edge glow, top glow) | 8.5 s | 1, 21, 22, 23, 30, 36, 51, 58 |
| Door from the spawn-room side | 0 s (the inside was not entered; seen only through the door) | - |
| Kill feed | 0 s (no box in that corner) | - |
| Other | 0 s | - |

Of the 5.5 s on the real bot, the held id was measured in the crop on 57 ticks (~1.0 s): id 16 on 17 ticks as a 30-36 px
sliver clipped by the crop's top edge (not walked at), id 68 on all 40 of its ticks at 137-144 px, where the one burst of
the run landed (t 32.56, 55 damage). The replay's generic labels call 12.69 s "luna": it counts the door's boxes as
Luna-sized; the by-eye table above is the accounting.

**Forward-walk episodes** (left stick forward under Engage; the two 0.3 s throwaway moves at t 3.2-3.8 are `Live`'s own):

| t (s) | Toward what (by eye) | Held id / crop box on those ticks | Height, distance | Should the rule have allowed it |
|---|---|---|---|---|
| 3.93-4.29 (0.36) | the plaza-side door leaf | 1 / id 1, then id 3 for the last 4 ticks | 249-463 px (clipped by the crop top), none | yes by the rule (above 47 px, no distance). Not a bot: a perception false positive |
| 14.95-14.97 (2 ticks) | the door's top glow, camera pitched up | 21 / 21 | 89-105 px, none | yes by the rule; door |
| 15.76-16.31 (0.55) | the door's green cross | 23 / 23 (25 for one tick) | 53-222 px, none | yes by the rule; door |
| 18.62-19.04 (0.42) | the door's edge, farther off | 30 / ids 31, 32, 29 on 8 of 13 ticks, 30 on 5 | 103-262 px, none | yes by height; on 8 ticks the measured box was not the held id |
| 19.46-19.67 (5 ticks) | the same door edge | 30 / id 31 only | **49, 50, 55 px**, then 242, 319; none | yes: 49 px is above the 47 px cutoff, by 2 px. The measured box was not the held id |
| 22.80-22.86 (2 ticks) | the door's edge beside its dark pillar | 36 / 36 | 194-294 px, none | yes by the rule; door |
| 24.46-24.79 (0.33) | the door's edge, **while the held target was the Luna bot 948 px left of the crosshair (id 44, whole-frame only)** | 44 / id 51 for 11 ticks, then the brain moved to 51 | 61-394 px, none | the height rule allowed it. The box walked at was not the held target: the controller's track, drifted off every box for 0.25 s, re-seeded on the nearest crop box of the same class (full right stick toward the door, away from the bot) and that re-seed counts as measured and confirmed. The association is by bearing; it does not read the tracker id |
| 28.49-28.66 (0.17) | the door's green cross | 58 / 58 and 57 | 89-219 px, none | yes by the rule; door |
| 32.27-32.47 (0.20) | **the Luna bot** | 67 then 68 / 68 | 109-144 px, none | yes: a real bot in reach, above the cutoff |

No forward walk happened toward a box at or under the cutoff, and none toward a small distant box.

**Whole-frame -> crop hand-offs (picked outside the crop).** Strips: `reach30-handoffs.jpg`.

| Pick | Id | What, where (native centre, height) | Reached the crop under | Elapsed / ending |
|---|---|---|---|---|
| t 7.65 | 11 | Luna bot, (2126,910), 199 px, right of and below the crop | **changed id**: the crop saw her as id 12 (165-168 px) from t 7.92; id 11 never appeared in the crop | held 0.84 s, steered on the pick tick, **released** to Search at t 8.49 with her in the crop as 12 |
| t 14.86 | 21 | door top glow, (527,866), 105 px | the same id, 21, after 0.09 s | the brain moved to 22 after 0.10 s |
| t 14.98 | 22 | green glow at the bottom-right corner, (2224,1156), 249 px | never | released after 0.44 s |
| t 18.57 | 30 | door edge, (765,362), 267 px | the same id, 30, after 0.23 s, on 7 of 75 ticks; ids 29, 31, 32, 34 on the others | held 1.30 s, released |
| t 23.75 | 44 | Luna bot, (384,1038), 183 px, left of the crop | **never**: steered 0.02 s after the pick (left, 0.43) for ~0.2 s, then no stick; at t 24.46 the controller re-seeded on the door edge (id 51) and turned right | the brain moved to 51 (the door) at t 24.72 |
| t 32.20 | 67 | Luna bot, (410,458), 185 px, left of the crop | **changed id**: 68 in the crop from t 32.27 (0.07 s) | the brain moved to 68 after 0.17 s; burst at t 32.56; run end at t 33.16 |

Three real-bot cases exercised: none reached the crop under the same id (two changed ids, one never reached it). The two
door cases that reached the crop kept their id. Replay `live_handoffs`: 7.87 held 11 / crop 13, 18.62 30/31, 22.93 36/41,
23.86 44/45, 32.27 67/68, all `kept: false`; replay `handoffs` has 16.03 23 -> [23] kept.

**Plaza, falls, end.** He did not leave the plaza and did not fall: the whole run is within a few metres of the plaza-side
door, and it ends on the plaza facing the Luna bot (`after-reach30.jpg`). One run, 30 s.

**Stalls over 0.5 s** (a target held, pad neutral): 4.46 / 0.60 (id 1, door), 9.05 / 0.64 and 10.02 / 1.45 (id 16: the Luna
bot in view ABOVE the crop with the camera pitched at the floor, centred in yaw, no pitch stick), 16.42 / 1.83 (id 23, door
cross, not in the crop), 24.91 / 0.74 (id 51, door), 28.78 / 0.78 (id 58, door). The replay's list (4.46 / 0.73,
9.05 / 0.66, 10.02 / 1.48, 16.43 / 0.84, 24.91 / 0.75, 28.78 / 0.81) agrees except that it ends the id 23 stall early. No
tick gap over 0.1 s.

**Search pitch, seen in this run** (`reach30-search-pitch.jpg`): every Search was 2.6-3.4 s long and ended in a door
engagement. Search's first 2 s undo the aim's pitch at half stick down, and its absolute re-level starts by running up into
the clamp at 2.0 s; each search was cut off inside that up phase (0.5-1.4 s of full up stick), so the come-down that zeroes
the pitch account never ran. The pitch account (`pitch_used`, reconstructed from the sent sticks) then read +0.3 to +1.4
stick-seconds for the rest of the run: at or over the 0.30 budget, so the aim's up pitch was refused from t 8.7 on, and each
following search pitched down for up to 1.5 s to undo stick-seconds that the game's pitch clamp had partly swallowed. The
camera looked at the floor at t ~5.4-7.0, 11.6-13.5, 20.1-22.1, 26.0-28.0, 30.2-31.8 and at the ceiling around t 14.4-15.4;
the id 16 stall is the Luna bot above the crop with the up pitch refused. The first floor look (t 5.4-7.0) comes before any up
phase, after 0.29 s of full up stick on the door and 0.32 s of half stick down, and is steeper than the pitch map gives for
those sticks: not explained by this run. Nothing was tuned.

Trace counts: 13 target ids, 71 ids issued by the replay tracker, held id visible 0.162 of held ticks.

## Supervised run `handoff30` (VUH-1314): `data/l1/handoff30/` on the PC and the Mac

30 s, scripted brain, `--cooldowns normal` (from play before the run: ammo 2 after three shots, Get Over Here showing 7,
`cooldowns-normal-verified-6.jpg`; the cooldowns script read the switch as already off and pressed nothing). Patch not read
from the screen; the kit doc's Season 10, version 20260911 stands.

Entry, `scripts/reenter.py` (`capture.py preflight` passed first, 47 dxcam frames in 1 s; `--dry-run` read `lobby`):
- The just-opened hero select was read first time: `screen hero_select`, then `RB`, `RB` with no "looking again" line and no
  refusal there. How long it looked is not in its output.
- It then **refused at the A**: `no proof for A: a tooltip is up and does not name SPIDER-MAN (match 0.73)`, exit 1
  (`reenter-refuse-tooltip-20260921-1037.jpg`). The tooltip beside the Spider-Man portrait read "Request to Team-Up with
  SPIDER-MAN / Remove from Strike Squad" (Peni Parker was the highlighted hero), not the tooltip the tool knows.
- Its `--dry-run` then read `hero_select`, `hero tab: duelists`, cursor found, so the one pre-authorized re-invocation ran:
  `A (the game's tooltip names SPIDER-MAN (match 0.92) beside the cursor at (888,36))`, `X`, `in_range`, then the known
  arrival stop (exit 1) with him outside on the plaza side of the door. No third attempt, no hand navigation.
- The start pose was not the one asked for: turns sent right after a pad connects were swallowed twice, so the run started
  facing the door's plaza side and the loop's own search brought the bot in from the edge of the view.

| | `handoff30` | `stall30` |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions; 0 python left, 0 Xbox pads present | same |
| Reflex | 56.1 Hz; tick p50 / p95 / max 9.0 / 12.7 / 22.3 ms; 8 of 1,683 ticks over budget | 55.6 Hz; 9.1 / 12.1 / 18.7; 6 of 1,667 |
| Aim finder | 5.9 / 8.6 / 15.5 ms | 6.1 / 8.5 / 14.9 |
| Decision | 10.0 Hz; 55 / 69 / 83 ms | 51 / 73 / 104 |
| Scoreboard (parsed) | **0 KOs**, 0 deaths, 250 damage, accuracy 50 %, Web-Cluster accuracy 20 % | 1 KO, 0 deaths, 445 damage |

**The acceptance question: whole-frame -> crop cases (a target known only to the whole-frame search when picked). Exercised
twice.** Strips with the crop, decision boxes (held target red) and crop boxes: `handoff30-wholeframe-target15.jpg`,
`handoff30-wholeframe-target71.jpg`.

| Pick | Id | Box (native) | From the crosshair | Steering | Reached the crop under | Elapsed / ending |
|---|---|---|---|---|---|---|
| t 5.38 s | 15 | (1988,617)-(2128,817), the Luna Snow bot right of the crop | 778 px | full stick on the pick tick (no gap) | **the SAME id, 15.** One tick at t 5.43 shows a 10 px sliver at the crop's right edge as id 17; from t 5.45 the body is id 15, at 11 px by t 5.76, when the burst starts | in the crop 0.07 s after the pick; held 2.31 s. After the web strike and uppercut at point blank (t 6.85 on) the crop's boxes become ids 27 / 28 and the brain moves to 28 at t 7.70: an id change at close range after hits, not at the hand-off. No release |
| t 9.59 s | 71 | (1379,92)-(1415,132), a 36x40 px box above the crop: one of a pair of small distant squares, not the Luna bot | 619 px | stick on the pick tick (no gap) | **the SAME id, 71**, from t 9.66 (0.07 s) to t 9.73; after that the boxes there are ids 72, 74, 75, 76 | held 1.45 s, **released** at t 11.04 to Search |

No-steer gap after a pick: none (0.00 s in both cases; 1.1 s in `stall30`).

`postfreeze30_replay.py --run data/l1/handoff30` (generic labels, no `LABELS` entry added): stalls over 0.5 s (start s /
length s) 4.66 / 0.63, 12.19 / 0.59, 14.29 / 1.28; engaged 3.38 s "luna" + 7.42 s "other"; held id visible 0.173; ids 111;
`handoffs` [[5.45, 15, [15], true]]; `live_handoffs` lists eight moments where the crop's id differed from the held id, all
`kept: false` (5.43 held 15 crop 17, the one-tick sliver; 5.92 15/22; 6.83 and 6.85 15/27; 8.70 28/45; 9.78 71/72;
11.56 78/79; 12.96 92/94).

By eye on the drawn frames (`handoff30-sheet.jpg`):
- Real bot: ids 15 and 28, ~4.2 s engaged, 250 damage, no KO. The last attack is at t 8.75.
- Door: **0 engaged seconds from either side.** The plaza-side door filled the view for the first second and was never
  targeted; the inside of the spawn room was not seen in this run. Kill feed: 0 (0 reflex boxes in that corner).
- Other: ids 5, 71, 78, 92, 101 (~6.6 s), all 33-40 px boxes: small distant squares across the range, usually in pairs.
- **He left the plaza at t ~14:** the controller walked forward for 0.8 s toward id 92, one of those distant squares, measured
  in the crop, and he went over the plaza's edge to the lower ring. The last 17.6 s are Search with nothing in view.
- Trace counts: 7 target ids, 98 ids issued, held id visible on 109 of 589 held ticks (19 %).

## Supervised run `stall30` (VUH-1314): `data/l1/stall30/` on the PC and the Mac

30 s, scripted brain, `--cooldowns normal` (from play before the run: ammo 2 after three shots, Get Over Here showing 7,
`cooldowns-normal-verified-5.jpg`; the cooldowns script read the switch as already off and pressed nothing). Patch not read
from the screen; the kit doc's Season 10, version 20260911 stands. Entry: `reenter.py` refused once on the first hero-select
frame ("hero tab None is not recognised", 2 s after the screen opened, `reenter-refuse-hero-tab-20260921-0941.jpg`); its
`--dry-run` read the settled screen as `hero tab: all`, and the one authorized re-invocation went RB, RB, A on the
Spider-Man tooltip (0.92), X, in range, then stopped on the arrival confirmation again (exit 1) with him outside on the
plaza side of the door.

| | `stall30` | `trackerlive30` |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions; 0 python left, 0 Xbox pads present | same |
| Reflex | 55.6 Hz; tick p50 / p95 / max 9.1 / 12.1 / 18.7 ms; 6 of 1,667 ticks over budget | 54.6 Hz; 9.8 / 12.6 / 18.0; 2 of 1,639 |
| Aim finder | 6.1 / 8.5 / 14.9 ms | 6.7 / 8.9 / 12.8 |
| Decision | 10.0 Hz; 51 / 73 / 104 ms | 52 / 76 / 92 |
| Scoreboard (parsed) | 1 KO, 0 deaths, 445 damage, accuracy 30 %, Web-Cluster accuracy 28 % | 2 KOs, 0 deaths, 760 damage |

**The acceptance question: targets known only to the whole-frame search when picked. Exercised twice.** Decision boxes, the
aim crop and the held target (red) are drawn on `stall30-wholeframe-target15.jpg` and `stall30-wholeframe-target71.jpg`.

| Pick | Id | Box (native) | From the crosshair | Re-aim | Did THAT id reach the aim crop | Elapsed / ending |
|---|---|---|---|---|---|---|
| t 4.98 s | 15 | (1882,594)-(1975,750), the Luna Snow bot right of the crop | 650 px | **No stick for the first 1.1 s** (rx = ry = 0 on twelve consecutive decisions, the box static at 650-656 px); the first stick command came at t 6.17 | **No.** The bot entered the crop at t 6.26 under a NEW id, 19, and was on the crosshair (8 px) by t 6.86; the held id 15 only coasted | released after 1.97 s (t 6.95); id 19 picked at t 7.13 and web-struck |
| t 16.35 s | 71 | (1965,775)-(2533,1094), the bot at the bottom right, 3-4 m | 992 px | Yes, from the first decision (rx +1.0) | **No.** The bot entered the crop at t 16.95 (0.6 s) under a NEW id, 73, and was at 18 px by t 17.58; the held id 71 only coasted | held 2.10 s, then the brain switched to 73 (t 18.48); no abort |

So the re-aim brings the bot into the crop (0.6 s when it steers at once), but the whole-frame id is never the id the crop
gives it, so "the same target reached the crop" is NO in both cases by id, and the brain spends 2 s on a coasting id before
it takes the new one. The first case also shows 1.1 s with no steering at all.

`docs/evidence/l4/postfreeze30_replay.py --run data/l1/stall30` (generic labels: no `LABELS` entry was added for this run):
ids 106, held-id visible 0.23, engaged 14.19 s "luna" + 2.93 s "other", stalls over 0.5 s (start s, length s):
3.95 / 2.14, 10.41 / 0.91, 15.02 / 0.52, 19.61 / 1.07, 24.06 / 1.08. The generic labels call any box 100 px or taller the
bot, which is wrong here; by eye on the drawn frames (`stall30-sheet.jpg`):

- **Real bot: ~10.3 s** (ids 15, 19, 30, 71, 73).
- **The green health door: 2.65 s, id 48 (t 12.68-15.33), seen from the PLAZA side, with the burst played at it (58 attack
  ticks).** Ids 45 and 46 just before it (0.8 s, boxes at the crop's left edge as he turned onto the door) are probably
  door too. The finder's hue rule drops the door seen from inside the spawn room; from outside it still makes a box.
- Kill feed: 0 (0 reflex boxes in that corner).
- Other: id 11, a 29x30 px box (1.25 s); id 98, the ceiling skylight seen from the lower ring (1.52 s).
- Trace counts: 10 target ids, 94 ids issued, held id visible on 209 of 917 held ticks (23 %). After the web strike at
  t ~18.7 he ended on the lower ring; the last attack is at t 19.2 and the last 8 s are Search with nothing in view.

## Supervised run `trackerlive30` (VUH-1314): `data/l1/trackerlive30/` on the PC and the Mac

30 s, scripted brain, `--cooldowns normal` (verified from play before the run: ammo 2 after three shots, Get Over Here
showing 7, `cooldowns-normal-verified-4.jpg`; `l4_practice_settings.py cooldowns-off` read the switch as already off and
pressed nothing). Patch not read from the screen; the kit doc's Season 10, version 20260911 stands. Entry was
`scripts/reenter.py`: every menu press passed its proof; the arrival again stopped with "could not confirm the spawn room
was left within 14 s" while he stood outside at the door frame. Contact sheet with every box drawn and the held target in
red: `trackerlive30-sheet.jpg`; metadata `trackerlive30-meta.json`.

| | `trackerlive30` | `postfreeze30` |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions; log clean, 0 python left, 0 Xbox pads present | same |
| Reflex | 54.6 Hz; tick p50 / p95 / max 9.8 / 12.6 / 18.0 ms; **2 of 1,639 ticks over budget** | 49.9 Hz; 11.4 / 17.9 / 25.7; 80 of 1,499 |
| Aim finder | 6.7 / 8.9 / 12.8 ms | 6.3 / 10.2 / 16.2 |
| Decision | 10.1 Hz; 52 / 76 / 92 ms | 40 / 58 / 94 |
| Scoreboard (parsed) | 2 KOs, 0 deaths, 760 damage, accuracy 72 %, Web-Cluster accuracy 16 % | 2 KOs, 0 deaths, 565 damage |

Target accounting from the per-tick trace (the owner's `postfreeze30_replay.py` has its run path and its by-eye labels
hard-coded for `postfreeze30`, so it does not score this run; these are trace counts plus what the drawn boxes show):

- **Door and kill feed: 0 engaged seconds.** The lime door was in view for the first ~1.3 s and produced no box; 0 of 1,156
  reflex boxes fall in the kill-feed corner. Every target box on the 24 sampled frames sits on the Luna Snow bot.
- First box in the crop at t 4.48 s, first engaging tick at 4.60 s (0.12 s later, inside the expected 0.1-0.5 s).
- Engaging ticks 1,463 of 1,639 (~26.8 s). The held id was visible on 482 of 1,462 held ticks (**33 %**, was 21 %), coasting
  on 801, neither on 179. `target_px` while visible p10 / p50 / p90 / max = 35 / 198 / 393 / 500 native px.
- **9 target ids for one bot in 27 s** (3, 9, 20, 21, 35, 46, 56, 63, 85), 63 ids issued in all (was 14 and 84). Three were
  never visible to the reflex crop: 46 (3.0 s: a 44x36 px box at the right edge, the downed bot), 63 (1.3 s, one 22x31 px
  box) and **85 (the last 4.9 s): the respawned bot, seen only by the whole-frame search at x 1756-2526, to the right of the
  960 px crop.** He stood still for those 4.9 s: the controller turns toward a target the crop has not confirmed for 1 s,
  then stops, and the brain kept engaging it. No attack was pressed in the last 7 s.
- Pieces of one body sharing an id: 32 ticks (was 7 ticks of an upper and a lower box carrying the same id by accident).
- Re-acquisitions after a coast: 15; ten after gaps under 0.3 s; the five longer ones (gap s / `target_px`): 0.90 / 267,
  0.76 / 206, 0.41 / 301, 0.89 / 54, 4.31 / 107.


## Post-freeze supervised run: `C:\rivals-agent\data\l1\postfreeze30\` (30 s, scripted brain, `--cooldowns normal`)

Before it: `capture.py preflight` passed (222 dxcam frames in 1 s); cooldowns verified from play through `Live`
(ammo 2 after three shots, Get Over Here showing 7, `cooldowns-normal-verified-3.jpg`), so the practice-settings script was
not needed. Contact sheet `postfreeze30-sheet.jpg`, metadata `postfreeze30-meta.json`.

| | `postfreeze30` | before the safety work (`loop30c`) |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive, 0 missed decisions | same |
| Clean close | log ends `EXIT 0`; 0 python / uv processes; 0 Xbox 360 devices present | |
| Reflex | 49.9 Hz; tick p50 / p95 / max 11.4 / 17.9 / 25.7 ms; **80 of 1,499 ticks over the 16.7 ms budget** | 57.6 Hz; 6.9 / 9.7 / 15.8; 0 over |
| Aim finder | 6.3 / 10.2 / 16.2 ms | 5.6 / 7.5 / 14.5 |
| Decision | 10.1 Hz; 39.5 / 57.7 / 93.8 ms | 26 / 40 / 60 |
| End scoreboard (parsed) | 2 KOs, 565 damage, 0 deaths, accuracy 69 %, Web-Cluster accuracy 25 % (a fresh range session, so these are the run's own) | |

Cost of the safety layer: about +4.5 ms per reflex tick at the median (aim finder +0.7 ms; the rest is the positive range
identity, a banner template match plus the bar tests, run by the loop's guard and again by `Live` at every commit, and the
tracker). 79 of the 80 over-budget ticks had no box in the crop, 74 of them under Engage: the expensive tick is the
no-detection one, not the fight. The obvious saving is proving the range once per frame and sharing the verdict, which
is a change to the reviewed boundary, so it needs the reviewer.

Id trace (`ids`, `coasting`, `target`, `target_px`; native px from the crosshair):

- The brain held a target id on 1,497 of 1,499 ticks, but that id was **visible on only 313 ticks (21 %)**, coasting on
  1,019 and neither on 165. While visible, `target_px` p10 / p50 / p90 / max = 27 / 161 / 409 / 520; 12 % of visible
  ticks within 30 px, 23 % within 60, 43 % within 120.
- **14 target ids in 30 s** (1, 2, 7, 3, 4, 17, 21, 29, 31, 48, 55, 57, 88, 110) and **84 distinct ids** issued on a plaza
  with one bot: identity does not persist. Ids 1-4 (t 3-12 s) were the spawn room's green health door and its cross, the
  known false positive: he stood facing it for the first ~9 s and fired a Web Cluster at it (sheet frames 19-77), until
  Search turned him to Luna Snow. Ids 55 (5 s) and 110 were never visible at all.
- **Re-acquisitions after a coast: 20.** Gap and `target_px` at re-acquisition: 0.07 s / 174; 8.44 / 231; 0.25 / 96;
  0.05 / 68; 0.06 / 104; 0.05 / 183; 1.73 / 520; 1.33 / 273; 0.02 / 23; 0.47 / 471; 0.77 / 373; 0.86 / 355; 5.79 / 422;
  0.07 / 464; 0.04 / 410; 0.32 / 223; 0.92 / 346; 0.02 / 186; 0.04 / 22; 0.02 / 199. After any gap over 0.3 s the target
  comes back 220-520 px off the crosshair.
- **Did an id move onto a different box: yes, within a tick.** On 7 ticks the same id sat on two boxes at once (id 31 at
  16.78 and 16.81 s, id 48 at 19.28 s, id 57 at 28.68 and 28.70 s, ...): at close range the outline splits into an upper and
  a lower box and both get the target's id, which shows up as same-id jumps of 150-280 px between consecutive ticks (21 of
  them). No case of a held id hopping to a different bot was seen; there was only one bot.

For the re-entry owner, `data\reenter\refuse-20260921-051559.jpg`: he is **outside** the spawn room, on the plaza side,
standing at the door frame's outer left edge and facing the frame edge-on, so the view is the dark jamb with the plaza
planter to its right and the room's curved wall and second door to its left; the plaza and the Luna Snow bot are behind
him. The walk did leave the room; the confirmation looks the wrong way. Turning 180 deg from that pose shows the plaza with
the bot ahead.

Cooldowns: "No Ability Cooldown" was still OFF after the re-entry (`practice-settings-still-off-after-reentry.jpg`); the
infinity on the HUD is the melee slot, Web Cluster is the 5 beside it. Verified from play through `Live`: ammo 2 after three
shots, Get Over Here showing 7 (`cooldowns-normal-verified-2.jpg`). `scripts/l4_practice_settings.py cooldowns-off` had its
first live run since the rewrite: START from a proven range frame, the pause row steered by its lit state, the
`pause.practice_settings` confirm, then on the page it walked the cursor looking for the long "(Always On)" help title,
which does not exist when the parent toggle is off, gave up with "never reached the No Ability Cooldown row" without
pressing anything on the page, and closed back to the range with B from proven screens. Fixed offline, not yet re-run live:
the script reads the switch first (`toggle_on` returns True / False / None, and None whenever the page is not at rest,
because a "... Deactivated" toast slides the rows up ~20 px) and returns success with no presses when it is already off;
an unreadable switch is a Stop. Fixture `tests/fixtures/menus/ps-open-nac-already-off.jpg` is that live frame.

**For the re-entry owner: the spawn room's green door catches him on its LEFT jamb.** Seen twice: by hand today (a
slightly-left approach walked into the wall left of the door; backing off 0.3 s and strafing right ~0.9 s before walking
forward cleared it) and in `data\reenter\refuse-20260920-223448.jpg` (pressed against the left jamb from inside, facing out
at an angle, where the door reads as a narrow tilted band, so its visual centre is not where the opening is). Approach from
the right of the door's centre, or strafe right ~0.9 s before the walk.

Route note: from the lower ring, the purple jump pad beside the plaza stairs launches him onto the main plaza in front of
the spawn room's green door, facing the Luna Snow bot.

## Tick-budget regression: profile (offline, no pad, 2026-09-21)

Harness `docs/evidence/l4/tick-profile-harness.py`, result `tick-profile-postfreeze30-replay.json`: the real `Loop`,
`default_perception`, `Tracker`, `Controller`, threaded `Decider`, `RunLog` and `Live` commit path, with a fake pad and a
replay capture serving `postfreeze30`'s 273 native frames at 60 Hz (a fresh array per grab), run on the PC with the game up
(on the lobby, ~480 fps, so GPU load is not the range's). It reproduces the run: 52.2 Hz, tick p50 / p95 / max
11.1 / 17.0 / 22.0 ms, 77 of 1,372 ticks over 16.7 ms (live: 49.9 Hz, 11.4 / 17.9 / 25.7, 80 of 1,499).

| Component (per tick) | p50 | p95 | max ms |
|---|---|---|---|
| aim finder (960 px crop) | 5.9 | 9.3 | 14.2 |
| range proof inside `Live._commit` | 2.3 | 4.5 | 35.1 |
| loop's early `in_range` guard | 2.0 | 2.7 | 6.9 |
| loop's `idle_warning` guard | 0.6 | 0.8 | 4.0 |
| `_log` (outside `tick_ms`; frame copy for the JPEG writer) | 0.1 | 4.1 | 25.9 |
| controller step / tracker update / `decider.offer` / `Live._apply` (fake pad) | 0.06 / 0.03 / 0.00 / 0.01 | | |
| capture: not comparable on replay. A delivered live dxcam grab measured 23.5 ms p50 on the lobby (GPU saturated at 480 fps); in the range the loop's period was 17-19 ms. The real pad write is not measured (no pad opened); before the safety work the whole tick, pad write included, was 6.9 ms | | | |

- The regression is the positive range predicate run twice: 2.0 + 2.3 = 4.3 ms of the +4.5 ms. The tracker costs 0.03 ms.
- Over-budget ticks: 76 of 77 had no box in the aim crop, and 76 of 77 overlapped the decision worker's whole-frame finder
  (which only runs when the crop is empty; it takes 31 ms p50 on the worker here against 14.6 ms alone). In 56 the largest
  excess was the aim finder (+5 ms mean: the two finders contend), in 21 one of the two predicates.
- Removing only `Live`'s duplicate evaluation would bring 61 of the 77 back under budget.
- **The predicate itself is the waste:** `record.banner_score` converts the whole 2560x1440 frame to grey (0.9 ms) and
  resizes it (1.2 ms) to look at a 184x29 px corner. Cropping the banner window first gives the same score (0.981 vs 0.981
  on a run frame) in 0.075 ms instead of 1.44 ms. With both predicates at ~0.3 ms all 77 over-budget ticks come back
  under budget, with no change to the reviewed authorization boundary. The shared verdict would then save ~0.3 ms a tick.

### `record.banner_score` crops before it converts (accepted by the input-safety reviewer, on main, deployed)

Measured on the PC on live frames, capture only (no pad created, no input, game on the PLAY lobby, 400 dxcam frames at
2560x1440, the two paths alternated per frame): `in_range` costs **0.19 / 0.27 / 0.40 ms** (median / p95 / max) crop-first
against 1.20 / 1.53 / 2.85 ms on the old whole-frame path; `banner_score` alone 0.28 / 0.43 / 0.67 against
1.30 / 1.60 / 3.41 ms. Scores are equal on 400 of 400 frames (max difference 0.0) and so is `in_range`. On the lobby it
reads not-in-range on every frame (banner score 0.075-0.083 against the 0.55 threshold), so these timings are the
early-exit path: the banner fails and the health-bar tests never run. In the range `in_range` also runs the bar tests
(~0.8 ms in the replay profile below); a live in-range timing needs the game in the range.


The shared range verdict was NOT built (after this fix it would save ~0.3 ms a tick for a change to the reviewed
authorization boundary). Only the predicate's internals change; `in_range`'s signature, thresholds, bar tests and every
caller are untouched.

- Crop-first is used only where it is exact: frames whose width and height are whole multiples of 1280x720 (the 2560x1440
  capture, 3840x2160). There INTER_AREA is a k x k box average, so cropping the window's input pixels first gives
  bit-identical output, and grey conversion is per pixel. Every other size takes the old whole-frame path unchanged: a
  first version that aligned crops for fractional scales was off by +-1 grey level at 2560x1600, so it was dropped.
- Equivalence, old (whole-frame reference) against new, on every recorded frame: **25,807 frames on the PC, 0 decision flips
  against `BANNER_MIN` 0.55, max |new - old| = 0.0, 0 non-zero differences** (`banner-equivalence-pc-25807-frames.json`,
  per source: 16,929 native 2560x1440 frames and 8,876 at 1280x720). Margins identical before and after: lowest positive
  0.6826, highest negative 0.2152. Fixtures, the 210-frame positive set and 74 evidence images on the Mac: 320 frames (29
  native), 0 flips, max difference 0.0 (`banner-equivalence-fixtures.json`). The PC's recordings hold only 89 negatives,
  all 720p; native-resolution negatives (lobby, hero select, practice panel) come from `tests/fixtures/reentry`.
- Permanent regression: `tests/test_banner_equivalence.py` keeps the old implementation as `reference_window` /
  `reference_score` and holds the new one to it on all 36 fixtures at 10 sizes (native, 1920x1080, 3840x2160, 1600x900,
  1366x768, 2560x1600, 1280x720, 1280x800, 1024x576, 640x360): same window pixels, same score, same decision. Also grey
  frames, odd shapes, a banner partly or wholly off the frame, and frames too small to hold the banner (score 0, `in_range`
  False, never raises; the old code raised `cv2.error` on a 1280-wide sliver). The existing 52-case suite passes unchanged.
- Mutations of the new geometry, all killed: crop origin x+1, origin y-1, wrong scale, wrong corner, axes swapped, no +-4 px
  slack, nearest instead of area, crop-first at non-multiple sizes, small-frame guard removed.
- Profile with the fix (`tick-profile-cropfirst-replay.json`, same harness and frames): 54.7 Hz (was 52.2), tick p50 / p95
  / max 9.0 / 15.7 / 18.9 ms (was 11.1 / 17.0 / 22.0), **28 of 1,439 ticks over budget (was 77 of 1,372)**. Early guard
  0.8 / 1.2 / 2.6 ms, proof in `Live` 0.9 / 4.7 / 18.2, aim finder 6.1 / 9.6 / 15.3, idle guard 0.6 / 0.9 / 4.5. What is
  left of the predicate (~0.8 ms) is the health-bar tests.
- The 28 that remain: 27 had no box in the crop and all 28 overlapped the decision worker's whole-frame finder; in 22 the
  largest excess was the aim finder (+5.9 ms mean). This replay uses no GPU in either finder, so it is CPU contention between
  the two OpenCV finders (and the GIL around their Python parts), not GPU load; the aim finder's median is the same whether
  or not the wide finder is running (6.3 vs 6.1 ms), only its tail moves. Worst tick 18.9 ms, so the cost is a tick ~2 ms
  late on 2 % of ticks: not worth a change to reviewed code now. If it ever matters: run the wide search on the 720p
  downscale, or cap OpenCV's threads on the worker.

## Capture fault: dxcam delivers no frames when no monitor is attached

Since 2026-09-20 23:08:24 Desktop Duplication returns nothing: `AcquireNextFrame` times out (`0x887A0027`
DXGI_ERROR_WAIT_TIMEOUT) even with a 1 s timeout, three times running, on a freshly created and on a recreated dxcam
camera, while GDI sees ~10 % of the screen's pixels change in 0.3 s. Cause: **no monitor is attached.** Every Monitor PnP
device reads `Present = False`; the ASUS VG27AQM1A (`DISPLAY\AUS2753\5&2E4F0D5A&0&UID4355`) has
`LastArrivalDate` 17:39:52 and `LastRemovalDate` 23:08:24. Windows keeps the 2560x1440@240 desktop on `\\.\DISPLAY1`
(`AttachedToDesktop` true, one adapter, one output, so no index change), the game keeps rendering (windowed/borderless,
GDI reads it), but with no sink DWM presents nothing to the output, so there is no frame to duplicate. Ruled out: TDR or
driver reset (no display, nvlddmkm, dxgkrnl or Kernel-Power events 22:30-00:10), an output or adapter change, a mode
change, exclusive fullscreen, leftover processes. 23:08 is ~15 min after the last keyboard/mouse-class input; the display
idle-off is 15 min (VIDEOIDLE 0x384) and virtual-pad input does not reset it, so the likeliest trigger is Windows turning
the display off and the monitor dropping DisplayPort hot-plug in its sleep; a monitor switched off at the panel looks
identical from here.

- **Detect:** `python scripts/capture.py preflight` (uncommitted): 1 s of dxcam grabs; 0 frames exits non-zero with the
  cause and the check to run (`Get-PnpDevice -Class Monitor | Where-Object Present`). `tests/test_capture_preflight.py`.
  Run it before any live tool; `open_capture()`'s silent fall to GDI hides this fault.
- **Recover without a person:** untested, needs the lead's go-ahead since it is desktop input: wake the display
  (a real mouse move, or `SendMessage(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)`), then confirm a Monitor device
  is Present and the preflight passes. The lead's injected mouse move did not bring the monitor back (no arrival after
  23:08), which points at the panel being off or in a deep sleep that needs its button.
- **Prevent:** display idle-off to never while agents run (`powercfg -change -monitor-timeout-ac 0`, reversible), or a
  DisplayPort/HDMI dummy plug so an output always has a sink. Not done; a power setting and hardware are James's call.
- **If it needs James:** press the monitor's power button (or wake it from its own standby) so it shows the desktop; leave
  it on, or fit a dummy plug.

## Input safety (VUH-1325): this lane's fixes, all offline, awaiting re-review

Nothing here has been run live or synced to the PC; the freeze stands until the co-lead re-runs its fault injections.
Principle: the lowest layer that touches a pad (`agent.controller.Live` in play, `scripts/l4_menu.Menu` in menus)
enforces freshness at commit, the lease, the whitelist and the confirm allow-list; a caller cannot weaken them.

| Rule | Where | How | Test |
|---|---|---|---|
| The range guard is positive identity | `scripts/record.in_range` (same name and signature) | The "PRACTICE RANGE" banner by template (`scripts/templates/range_banner.png`, correlation >= 0.55; range frames score 0.92-1.0) AND the HUD health bar bright with darker screen under it AND the bar's segment dividers | `tests/test_in_range.py` (52): range frames pass; lobby, hero select, practice panel, pause menu, Practice Settings, leave dialog and scoreboard fail, and still fail with the health strip painted white; flat, noisy, tiny and `None` frames fail. 210 of 210 frames sampled from `baseline1` / `baseline3` pass |
| Freshness is judged at commit | `Live._commit` + `Live._apply`, `Menu._commit` | A frame is stamped when its grab STARTS; all proof is computed; only then is its age checked (0.1 s in play, 0.35 s in menus) and the pad written. In `Live` the proving frame's timestamp is carried down to the actuator and checked again inside the pad lock, immediately before the write, so a wait for the lock cannot hide a stale proof. A slow grab or a slow guard cannot authorise a press. Menu frames come from GDI, which always returns the current screen, and must postdate the previous input | `test_live_pad.py`, `test_l4_menu.py`: a guard / check that takes 2 s, a grab that takes 0.5 s, a grab that returns nothing |
| A lease under every actuator path | `Live._watchdog` | A thread on the real clock (`time.monotonic`, not the patchable `time`) returns the pad to neutral 0.25 s after the last proven send. Only `_apply` takes the pad lock, for one report; capture and guards never run under it. No first frame within 2 s is an error, not a wait. `close()` is serialised with commits under the same lock: it writes neutral and from then on every non-neutral write is refused (release and close stay idempotent). `Live.hold()` re-proves every 50 ms for callers that need a longer hold | capture blocked mid-hold, a caller that stops calling, an all-`None` capture, a send after close, a close racing sends, a 0.2 s wait for the pad lock while the screen becomes the lobby |
| The whitelist is in the wrapper | `Live.send` | A, X, LB, RB and the known state keys only; anything else is refused with the pad neutral. The pad object is private | every other button and an unknown key |
| BACK has one door, with recognised transitions | `Live.scoreboard(hold_s)` | Range proven on a frame grabbed for the purpose (never a cached one) -> BACK down -> each new frame must be the scoreboard (`perception.scoreboard.is_scoreboard` is True) or, only during the first 0.8 s while it fades in, still carry the range banner -> release -> the range recognised again within 1.5 s. Any other frame, stale proof or missing frame releases at once and raises. Returns the last frame recognised as the scoreboard, or `None` | lobby / dialog / black during the hold, a cached range frame over a lobby, a board that never gives the range back, interrupt mid-hold |
| Screens are named, never supplied | `Menu` | `Menu(screens)` / `expect(screens)` take names from `SCREENS` (range, pause, practice_settings), each a positive template match; a callable or an unknown name is refused before a pad opens. The leave dialog is recognised (`on_leave_dialog`) but is not a screen input can be sent to | a permissive lambda on a lobby frame, the leave dialog |
| Confirms go through an allow-list at the actuator | `Menu.confirm`, token `A:<control>` | `CONFIRMABLE` = `pause.practice_settings` (pause screen AND that row lit) and `practice_settings.no_ability_cooldown` (page title AND the help panel naming that row), proven at the press. Plain `A` is not a token. LEAVE GAME, the dialog's CONFIRM, EXIT TO DESKTOP and RESTORE DEFAULTS are not confirmable; this lane ships no entry point for LEAVE GAME | wrong row, wrong page, a control whose screen is not the one on display, unlisted controls |
| No long holds in menus | `Menu` | `hold:` does not exist; START is a tap that needs a proven range frame whatever screen was named; a stick is held at most 0.6 s and every nudge is proven again; X, BACK, Y and the d-pad are refused; a lost cursor sends nothing | `hold:A,60`, long stick tokens, the refused vocabulary |
| Neutral on every exit | `Menu._hold`, `Live.hold` / `keepalive` / `scoreboard`, `l4_practice_settings.main` | try/finally reset + update; the practice-settings close presses B only from a positively matched page or pause menu and sends nothing from anything else | KeyboardInterrupt mid-press, closing from lobby / black / white |

The co-lead's second reproducer (`/tmp/rivals-controller-rereview-v2.py`, 10 cases) passes. Of the first one's seven
reproductions, all are blocked (stale X, stale START, A on the leave dialog, A under a permissive check on the lobby,
`hold:A,60`, BACK held through lobby frames, X held through a blocked capture).

What `in_range` returns: **True** only on the range's playing screen. **False** on the held-BACK scoreboard (the banner
stays but the HUD bar does not), the pause menu and its pages (banner dimmed and blurred), hero select, the lobby, a
desktop or any lost-focus window. Known limit, fails closed: the bar test wants over half the strip bright, so under
about 50 % hp it reads False and input stops.

**For rivals-brain (their files, not patched):** (a) `agent/loop.py` `LiveIO.scoreboard` presses BACK on
`self.live.pad`, which does not exist: call `self.live.scoreboard(hold_s)`, use the frame it returns (it can be `None`),
and let `RangeLost` end the run. (b) `tests/test_reenter.py` `spawn_frame()` paints `f[:600, :1200]`, which erases the
banner, so 11 re-entry tests see "unknown screen"; painting `f[130:600, :1200]` keeps it and they pass (checked on a
temporary copy). (c) The lease means anything driving `Live` must send at least every 0.25 s while it wants an input
held; the loop does (60 Hz).

`scripts/l4_trial.py` takes its scoreboard frames through `Live.scoreboard`; `scripts/l4_measure.py` holds sticks through
`Live.hold`. `scripts/l4_practice_settings.py` has two modes, `look` and `cooldowns-off`.

## Collection batch (scripted brain, cooldowns normal, same code and settings)

| Run | KOs | Damage | Reflex Hz | tick p50 / p95 ms | Note |
|---|---|---|---|---|---|
| `baseline1` | 21 | 5,590 | 55.1 | 7.0 / 10.0 | no recorder |
| `baseline2` | **0** | 0 | 57.0 | 7.0 / 10.9 | **stalled for the whole run**: camera pitched straight down beside a point-blank bot, brain on Engage throughout (17,090 ticks), aim crop saw no box, so no press, no move, no Search (and so no re-level) |
| `baseline3` | 20 | 5,000 | 53.4 | 7.3 / 11.0 | ended outside the arena |
| `baseline4` | **0** | 0 | 56.8 | 7.2 / 11.3 | Search for the whole run (16,997 ticks): he began it on the lower ring, where there are no bots |

All four stopped on `max_time` with no range gap, no error, 0 missed decisions, 2-5 ticks over budget; runs 2-4 had the
all-GPU recorder on (`C:\rivals-agent\data\video\baseline<n>.mp4`). Mean 10.3 KOs (sd 11.8), 2,648 damage (sd 3,067):
the spread is two working runs (20-21 KOs, 5,000-5,590) and two dead ones, not noise around a mean. `baseline5` and
`baseline6` were not run. On the Mac under `data/l1/<run>/`: `frames.jsonl`, `meta.json` (with `cooldowns`,
`scoreboard_before`, `proxy`, `screen_recording`), `proxy-720p.mp4` (one video frame per saved image, in order) and the
end scoreboard. Native frames and 60 fps recordings stay on the PC.

## Baseline (VUH-1300): `C:\rivals-agent\data\l1\baseline1\`

Five minutes, scripted brain, **real cooldowns** (`"cooldowns": "normal"` and `scoreboard_before` added to its
`meta.json` after the run), 2,760 native frames + `frames.jsonl` (16,522 rows), 1.6 GB. No video recorder running.

| | `baseline1` |
|---|---|
| **Score** | **21 KOs and 5,590 damage in 300 s** (board before: 2 KOs / 645; end board parsed by `perception/scoreboard.py` and checked by eye: 23 KOs, 6,235 damage, 0 deaths, accuracy 40 %, Web-Cluster accuracy 56 %) |
| Stop / guards | `max_time`; no range gap, no error, no stall, 1 keep-alive; never left the arena |
| Reflex | 55.1 Hz, tick p50 / p95 / max 7.0 / 10.0 / 17.8 ms, period p50 / p95 17.3 / 23.1 ms, 2 of 16,522 ticks over the 16.7 ms budget |
| Aim finder | 5.7 / 8.0 / 16.5 ms |
| Decision | 10.0 Hz, 28.6 / 46.7 / 104.8 ms, lag 29.6 / 47.6 / 105.8 ms, 0 missed |
| Intents (ticks) | engage 7,577, combo:burst 6,966, webstrike 917, search 860, pull 197, idle 5 |
| Best 10 s | t = 290-300 s (237 attack ticks), `baseline1-best-10s.jpg` |
| Worst 10 s | t = 10-20 s (0 attack ticks): after a KO he stands facing the downed bot's corner for ~7 s before Search starts, `baseline1-worst-10s.jpg`. Three more dead windows: 70-80, 180-190, 190-200 s |

Capture-to-input is not logged separately; the reflex tick (frame in hand to `pad.send`) is the 7 ms above. The confirming
run before it, `loop30c` (30 s, same place, cooldowns normal): 57.6 Hz, 0 over budget, 2 KOs.

**Screen recording cost** (ffmpeg 8, `h264_nvenc`, 60 fps, started just before the loop; the game's FPS counter read 238-240
in every case):

| Recorder | Reflex Hz | tick p50 / p95 ms | over budget | decision p50 ms |
|---|---|---|---|---|
| none (`loop30c`) | 57.6 | 6.9 / 9.7 | 0 | 26 |
| `ddagrab` -> `hwdownload` -> CPU scale to 1080p (`loop30v`) | 50.3 | 8.5 / 14.1 | 18 | 46 |
| `ddagrab` straight into NVENC at native 2560x1440 (`loop30g`) | 56.7 | 7.8 / 10.9 | 0 | 31 |

The CPU-scaled path costs the loop its rates; the all-GPU native path is close to free (`scale_d3d11` into NVENC failed
with "Invalid argument", so 1080p has to be a re-encode afterwards). `C:\rivals-agent\data\video\loop30g.mp4`: 55 s,
2560x1440, 60 fps, 215 MB; loop t = 0 is video second 4.0; 4 KOs in the 30 s; busiest fighting is video 9-29 s.

**Practice Settings, cooldowns.** "No Ability Cooldown" is now OFF (`practice-settings-cooldowns-off.jpg`); its sub-option
"(Always On)" disappears from the page when the parent is off (it was on, and its help text says it re-activates the
parent "each time you enter the Practice Range", so **re-check after every re-entry**). Verified from play
(`cooldowns-normal-verified.jpg`): Web Cluster ammo 2 after three shots, recharging; Get Over Here shows a 7 s cooldown
number. `scripts/l4_practice_settings.py cooldowns-off` does it on one pad: the page's cursor cannot be found reliably
(two sprites), so it steers by which pause-menu row is lit and by the help panel's title, steps right onto the switch,
and closes the menu before the pad goes away. With real cooldowns the burst still KOs Galacta bots (23 in 5.5 minutes).

**Earlier state, for the record.** The game was taken to the lobby on purpose through Pause > LEAVE GAME
(`left-game-lobby.jpg`, dialog `leave-game-dialog.jpg`: "Are you sure you want to leave the game?", CONFIRM (X) /
CANCEL (B); confirmed with the cursor and A, never X). During that visit a pad disconnected three times with the pause
menu or the dialog open and the game stayed put, so that did not reproduce as the cause of the earlier drop.

Movement rule since the fall: `Engage` walks forward only on a step where the aim sensor measured the target's box (not
on a coast, a hit flash, a lost track, or a target only the brain's whole-frame search saw); `Search` never moves. Tested
offline and held through `loop30c`, `baseline1`, `loop30v`, `loop30g`.

**Cooldown regime.** Practice Settings has "No Ability Cooldown" and "No Ability Cooldown (Always On)" ON by default, and
every range recording so far was made that way: `run1`, `trial1`, `tagrun`, `tagrun0`, `tagrun1`, `swatch-*`, `loop30a`,
`loop30b`, and everything under `data\l4\` (aim, primitive, scoreboard, tagged-native, tagrb trials). That is why Web
Cluster ammo never left 5, the ultimate relit in 3.5 s and no cooldown numbers appear. Runs made after the toggle was
turned off (`loop30c`, `baseline1`, `loop30v`, `loop30g`) carry `"cooldowns": "normal"` in their `meta.json` (added after the run; `agent/loop.py` does not write it);
runs without the field are cooldowns-off.

## Live loop (VUH-1300), first two runs

`python -m agent.loop --live --run <name> --max-s 30`, launched like `l4_trial.py`. `agent/` and `perception/` on the PC
match commit 140e31c by sha256 (19 files), plus this lane's working `agent/controller.py`.

| | `loop30a` (plaza, Luna Snow) | `loop30b` (open platform) |
|---|---|---|
| Stop / guards | `max_time`; no range gap, no error, 1 keep-alive | same |
| Reflex | 56.7 Hz, tick p50 / p95 / max 7.5 / 11.4 / 15.8 ms, period p50 / p95 16.9 / 22.1 ms, 0 over the 16.7 ms budget | 57.4 Hz, 6.7 / 10.2 / 14.3 ms, 0 over |
| Aim finder (960 px crop) | 6.0 / 9.5 / 14.2 ms | 5.4 / 8.6 / 13.1 ms |
| Decision | 10.0 Hz, 32 / 46 / 63 ms, lag 33 / 47 / 63 ms, 0 missed | 27 / 39 / 61 ms, 0 missed |
| Intents (ticks) | engage 354, search 1344, idle 4 | engage 503, search 1217, idle 4 |
| End scoreboard (parsed by `perception/scoreboard.py`) | 1 KO, 275 damage, accuracy 11 %, Web-Cluster accuracy 100 % | unchanged: 1 KO, 275 (no damage dealt) |

Rates hold with the game running. Capture-to-input total is not separately logged; the reflex tick (capture hand-off to
`pad.send`) is the 7 ms above, on top of dxcam's delivery.

What went wrong, and whose it is:

- **Controller (mine, fixed, tests added):** (1) the hit-flash coast refreshed `seen_t`, so "on target" stayed true with
  no box, the attack re-fired and renewed the coast for ever: run a marched forward 5 s at nothing after the KO. A press
  now needs a box measured on that very step. (2) `Search` levelled the camera from a model of our own stick, but the
  game pitches the camera itself (web strike, uppercut, falls): run a searched the floor for 23 s. `Search` now runs the
  pitch into its upper clamp and comes down a measured 1.8 s at half stick (= level), 2 s into a search and every 12 s;
  seen working in run b. (3) The brain engages targets that only the whole-frame search sees (outside the aim crop).
  Each Search / Engage flip (10 in the first 5 s of run b) re-seeded the track from the brain's target and walked 0.6 s
  with no reflex detection, off the platform edge. A target the aim crop has not measured is now turned toward and
  nothing else. Fix (3) is untested live.
- **For rivals-brain / L3, not patched:** in run b the brain's Engage targets came from whole-frame detections on an
  open platform with no bot in sight (ferns and cypresses are the only green there); the reflex crop saw a box on
  only a few ticks (e.g. native [1242,477,1308,538]). Worth checking the whole-frame finder on `data\l1\loop30b`.

## Sekkombo check: RB on a TAGGED target

Settled live on the Luna Snow bot, contact sheets `sekkombo-tagrb-trial0.jpg` (from ~10 m) and `-trial1.jpg` (from
~3.4 m): Web Cluster (tracer icon visible), then RB 0.7 s later. **Both times Spider-Man zips to the bot and kicks it
(a web strike); the bot is not pulled to him.** At 10 m he crosses the gap in ~0.5 s; at 3.4 m he still flips through
the strike and the bot is knocked back a few metres. The kit note stands; the "pull after tag" reading is not what the
default binding does. (The separate "Get Over Here Targeting" binding row is still untested.)

## Practice Settings (Pause > PRACTICE SETTINGS, `practice-settings.jpg`)

The whole page: **No Ability Cooldown** (on), **No Ability Cooldown (Always On)** (on), **Friendly Fire** (off), and a
Test Tools row **Controller Operation** [START] ("can record controller input and calibration status"). Y restores
defaults, B goes back. **There is no option for bot movement, bot attacks, respawn or placement.** Bot behaviour in the
range is set at the in-world kiosks (Hero Simulation by the spawn, the Galacta courtyard consoles), not here; those are
not explored. A red-glowing bot at the far end of the courtyard has not been tested for attacks. So far no range bot
has dealt damage.

## State

| Item | State |
|------|-------|
| Game settings | Done, table below |
| Native-resolution recordings for L2 / L3 | Three exist (table below). Bots, green nameplates and green enemy health bars at varied range: yes. Spider-Tracer tags: not confirmed on any frame. Damage taken: none, no bot met so far attacks |
| Scoring source | **Found: hold View/BACK in the range for a scoreboard** with KOs / deaths / assists and a per-hero row: Accuracy, **Damage**, Damage Blocked, Healing, Web-Cluster Accuracy, Spectacular Spin KOs (`scoreboard-back-native.jpg`). Damage read 210 before one ultimate and 845 after it |
| Ult charge as a damage proxy | Refuted for the range: the ultimate icon was lit again 3.5 s after casting (`ult-after-3s-killfeed.jpg`), so it does not meter damage there. A kill feed (top right) and a "DOUBLE!" banner do appear on KOs |
| Ranging | Delivered by L3 from outline height (`distance_m = 1872 / outline_box_height_px` at native); `brain.RANGES` carries the thresholds. A live sanity check at two known distances is still owed |
| `agent/controller.py` | `Live` (dxcam + range-HUD guard + one held pad + `keepalive()`), and the pure `Controller.step(state, intent) -> pad dict`. Reads `brain.RANGES.near_h`. Junk-box guard, hit-flash coast (`HIT_BLIND_S` 0.35 s after our own attack the track and its armed state are held), and a 1.5 s loss tolerance for a near box that runs off the frame. No player-region filter of its own (L3's finder has one) |
| `tests/test_controller.py` | 9 offline checks, passing |
| Enemy finder in the trials | L3's `find_enemies` on a 960 px native crop around the crosshair (`scale=2.0`), whole frame only when the crop is empty; boxes converted to 1280x720. Trial loop runs at ~70 Hz saving 720p frames |
| **Aim settle, live** | Standing Galacta bots, offset measured on screen, same bot held through the offset by the tracker. **8 of 10 under 300 ms from 31-44 deg: 191 / 220 / 226 / 233 / 235 / 241 / 264 / 271 ms.** All five left turns (35 deg) settled in 220-271 ms, so the left-turn occlusion fix works live. Two failures: one 31 deg trial lost the box mid-turn (683 ms), one 52 deg trial started with the bot at the frame edge and did not settle in 1 s (`aim-30deg-result.json`; earlier runs `aim-20deg-result.json`, `aim-24deg-result.json`) |
| **Primitive replays, live** | `web_cluster` 4 trials, `pull` 3, `burst` 3, all ran to completion; trial 0 of each inspected on a contact sheet: Web Cluster hits and the **Spider-Tracer icon appears over the bot's health bar** (`prim-web_cluster.jpg`); pull throws the web line and wraps the bot (`prim-pull.jpg`); burst tags, web-strikes across ~12 m, uppercuts, melees and **KOs the bot** with the kill feed showing (`prim-burst.jpg`). Trials 1+ not inspected. `melee_combo`, `uppercut`, `web_strike` not replayed on their own (they run inside burst). `swing` not run (no anchors) |
| Durations seen in burst trial 0 | Web strike: RB to arrival ~0.8 s from ~12 m (box height 84 -> 168 px between 0.97 and 1.18 s after the LT). The scripted burst is 3.0 s long; the Galacta bot was KO'd about 2 s in. Not yet measured per primitive |
| `agent/anchors.py` | Not written |
| Scoreboard fixtures | **Done.** `docs/evidence/l4/scoreboard/`: `board0..7.jpg` native, KOs 6 -> 13 and Damage 1375 -> 2680 (one burst between boards, a KO every round), values in `truth.json`; `killfeed-a.jpg`, `killfeed-b.jpg` native with the kill feed top right. Timing: the board starts fading in 270-520 ms after BACK goes down and is fully drawn ~200 ms later: hold >= 0.8 s. All in-between frames are on the PC in `data\l4\scoreboard\` (`board<r>-<ms>ms.jpg`, `fight<r>-NNN.jpg`) |
| Native tagged frames | **Done.** `C:\rivals-agent\data\l4\tagged-native\`, 4 trials on one Galacta bot at ~3 m, native q95, 10 fps: `t<i>-a-untagged-000..009` (no icon), `t<i>-b-after-web-cluster-000..028` (Web Cluster fired at frame 000; the Spider-Tracer icon, a white web glyph above the health bar, is on every inspected frame 003-027; 000-002 are the shot and hit flash). One distance only (`tagged-native-sheet.jpg`) |
| Not started | Practice Settings bot options (the drop happened on the way in), two-distance ranging check, pad-state-to-frame offset and the 30 fps native check, standalone melee / uppercut / web-strike replays, the two aim failures, `agent/anchors.py` |

Live finding: the bot nearest the crosshair is often drawn **behind Spider-Man's own body** (third person). A player-region
filter in the controller froze the aim on it for a whole run; it was removed.

## Game settings set (through the game's own menu)

| Setting | Where | Default | Now |
|---------|-------|---------|-----|
| Aim Sensitivity Curve Type | Controller > Combat > Advanced | Classic Curve | **Linear Curve** |
| Aim Assist Strength | same | 100 | **0** (`settings-aim-assist-0.jpg`) |
| Horizontal Sensitivity | Controller > Combat | 130 | **265** (`settings-hsens-265.jpg`); Vertical left at 75 |
| Hold to Swing | Controller > Combat > Spider-Man | off | **on** |
| Simple Swing (the kit's "Automatic Swing") | same | on | **off** |
| Enemy Color | **Accessibility > Custom Colors** | Default (red) | **Green** (`settings-enemy-color-green.jpg`) |

Enemy Color is a list of named swatches, no hue slider or hex entry: Default, Orange, Red, Pink, Pinkish-Purple,
(more), Blue-Green, Green, Yellow-Green, Yellow, Orange-Yellow. The Green swatch in the menu is `#53C75C`. **In
game it renders muted, about `#40AF58`** (OpenCV H 67, S ~160, V ~175; median of the outline and name-text pixels on
Luna Snow at native resolution), not `#00FF00`. It colours the enemy outline, name text, health bar and the
scoreboard's enemy panel. The spawn room's health door and the courtyard hedges are close enough in hue to matter.
The same page has Ally Color, HP Bar Color, Shield HP Bar Color, Warning Color and Color Blind Mode, all left alone.

Defaults read and left alone: Cursor Sensitivity 100, Vibration on (80), Trigger Deadzone off, Eye-Gaze Targeting
Min / Max Input Deadzone 5 / 5, Horizontal / Vertical Max Deadzone Sensitivity Boost 0 / 0, Max Deadzone Latency
Response Time 0, Max Deadzone Response Time 30, Aim Assist Type Classic, Window Size 50, Ease In projectile /
hitscan / melee 80 / 40 / 0, Disable Aim Assist at Max Deadzone off, Close-Range Aim Assist off, Targeting
Sensitivity While Aloft 100, Hold to Wall Crawl off, Hold to Run on Walls off, Direction of Wall Crawling "Advance
Vertically Upwards", Attack Range Hint on.

## Measurements (Linear curve, H / V sensitivity 265 / 75, aim assist 0)

- **Focal length 465 px at 1280 wide, horizontal FOV about 108 deg.** Pinned by timing a full 360 deg turn at 0.45
  stick (2.08 s, 173 deg/s, view match 0.985) and choosing the focal length at which still-frame pixel shifts give
  the same rate. Solving it from pixel shifts alone is ill-conditioned (gave 590-860); an earlier value of 760 was
  wrong, and every angle computed with it was about 1.5x too small.
- **Yaw rate vs stick** (deg/s): 0.1 -> 18, 0.2 -> 61, 0.3 -> 110, 0.45 -> 172, 0.6 -> 241, 0.8 -> 320, 1.0 -> 415.
  Immediate at every deflection (first 60 ms average within 6 % of the steady rate); left matches right. The
  "late outer-zone boost" reported earlier was an artefact of the wrong focal length.
- **Pitch rate**: 0.5 -> 43 deg/s, 1.0 -> 99 deg/s.
- **Press floor**: A held 8 ms registered 6/6 (so did every length to 120 ms). The controller presses for 33 ms.
- **Pad -> screen latency 17-20 ms** (A press to first changed frame, game at 240 fps). The trial loop runs at about
  50 Hz saving 1280-wide frames and about 27 Hz saving native frames.
- At the old Horizontal Sensitivity 130 the full-stick rate was roughly 240-300 deg/s; on the default Classic curve
  a full turn at full stick took 1.89 s.

## Recordings for L2 / L3 (PC, `C:\rivals-agent\data\l1\`)

All native 2560x1440 JPEG q90 at 10 fps, with `frames.jsonl` (one row per loop step: time, pad state, intent, the
boxes the adapter returned; rows with `file` are the saved frames). Enemy Color Green in all three.

| Run | Frames | What is in it |
|-----|--------|---------------|
| `tagrun0` | 609 | Plaza. Frames ~75-300: the Luna Snow bot from ~8 m to point blank, green name, green health bar after damage, melee. Then the camera ran up to the ceiling and he fell to the lower level; the rest is scenery |
| `tagrun1` | 354 | Walkway, one Galacta bot close; ends looking at the ceiling (the run stopped itself on a HUD-guard false alarm) |
| `tagrun` | 511 | Courtyard. Frames ~40-215: several Galacta bots at near / mid / far, one downed. Camera level throughout. Frames ~230-480 face a hedge |

hp stayed 250/250 in all of them: neither the Luna Snow bot nor these Galacta bots attack. The ultimate gives
500/500 for 2.4 s (`ult-cast.jpg`), which is the only hp change seen.

## Enemy Color swatch sweep (PC, `C:\rivals-agent\data\l1\swatch-<spot>-<name>\`)

Each set was recorded by setting the swatch through the game's menu and saving 50
native frames (JPEG q90, 10 fps) per swatch with the camera untouched between them, verifies the Enemy Color header
after each change, and leaves the game on Green. A full sweep takes about 2.5 minutes. Swatches: Green, Blue-Green,
Yellow-Green, Default.

| Spot | In view | Use |
|------|---------|-----|
| `courtyard2` | One standing Galacta bot (~12 m), hedges, cypresses, stairs. Camera identical across swatches. **Blue-Green is spoiled**: the keep-alive's Web Cluster knocked the bot down before that set | Bot vs background for Green, Yellow-Green, Default (`swatch-courtyard2-sheet.jpg`) |
| `courtyard` | A downed bot, hedges, stairs, a wall-crawl camera tilt | Background; downed-bot outline |
| `courtyard3`, `courtyard4` | Hedges, palms, cypresses only; camera identical within each set | False-positive rate per swatch (`swatch-courtyard4-sheet.jpg`) |

Not done: the spot with the spawn-room health door and the Luna Snow bot (the player is a level below the plaza and
the route back is not mapped). The keep-alive no longer attacks. Framing a view is unreliable: the `turn_s` argument
turned the camera the wrong way on two of four runs, cause not found (suspect: the pad-connect "Switching Devices"
disturbance), so check the first frame of a set before trusting it.

## What the aim loop is

Alpha-beta tracker on the target's bearing in commanded-camera coordinates: the frame in hand shows the camera angle
commanded one latency ago, so the error acted on is the tracked bearing minus the angle commanded since.
Feedforward is the inverse of the measured stick -> rate map; P (+ small I) does the rest. Detections mostly inside
the player's own screen region are ignored.

Live findings that shaped it:

- **Third-person occlusion.** A bot left of the crosshair passes behind Spider-Man's own body on screen as the
  camera turns onto it (`aim-left-turn-occlusion.jpg`); the loop coasts on the bearing for up to 0.5 s and does not
  re-seed onto suit boxes meanwhile. Untested live.
- **A close bot's nameplate sits overhead**, so chasing the box pitched the camera into the ceiling twice. Pitch is
  now limited to a stick-time budget (0.30 stick-seconds from where the controller started), and `Search` spends
  it back to level. A commanded-angle pitch clamp was tried first and drifted badly. Held level in `tagrun`.
- `Engage` taps X (Amazing Combo) when the box says "near". With junk boxes that happened on the first step of a
  run. In the range a tap is an ability; the HUD guard is what keeps it off the lobby.

## Open verifications from the kit

| # | Result |
|---|--------|
| 1 defaults | Read, listed above |
| 2 separate pull binding | Spider-Man's page has a "Get Over Here Targeting" binding row (RB / none) separate from "GET OVER HERE!" (RB). Untested. No "pull regardless of tracer" toggle seen |
| 3 press floor / auto-repeat | 8 ms registers. Hold auto-repeat not measured |
| 6 pad bindings | Pause = START. Change hero = hold X. **Scoreboard = hold View/BACK.** Bindings page (`settings-spiderman-bindings.jpg`) matches the kit: RT, LT, R3 melee, RB, LB, X, Y / B team-ups, L3+R3 ultimate, A jump, d-pad = Hero Profile / Customizable Wheel / Chrono Vision / Ping |
| 7 practice range | Web Cluster ammo never depletes (HUD stays at 5). The ultimate is available again within 3.5 s of casting. Luna Snow and Galacta bots do not attack; Galacta bots can be KO'd (3 by one ultimate) |
| 4, 5, 8 | Not reached |

## Game and tool facts

- The inactivity removal applies anywhere in the range, about 10 minutes after the last move or attack. Menu and
  camera-only input do not reset it. `Live.keepalive()` (walk, walk back, one RT) runs at the start of every
  measurement and trial.
- **The first input after a pad connects is swallowed** by the "Switching Devices..." switch, even 4 s after
  connecting. Send a throwaway move first.
- Tab presses (RB) in Settings drop when sent 0.6 s apart from a fresh pad: 3 of 7 landed. With 0.5 s extra between
  them, 4 of 4 landed.
- One `B` from anywhere in Settings returns to the range. The pause menu opens with the cursor on SETTINGS. Settings
  opens on MATCH; after a game restart the Controller sub-tab is back on GENERAL and the hero page on ALL HEROES.
- Settings sliders: A on an arrow steps 1; **holding A on an arrow auto-repeats** (130 -> 265 in 3 s); A on the track
  drags to the cursor. Changes on ALL HEROES show on Spider-Man's page. After CHANGE HERO the cursor sits on RESTORE
  DEFAULTS: do not press A there.
- `l4_menu.py goto:x,y` finds the cursor ring with a Hough circle (r 20-32 px at 1280x720) and steps it closed
  loop; it lands within ~9 px, and jiggles when the ring is lost over a widget. Open-loop cursor moves miss
  (560-1000 px/s).
- Hero re-pick does not respawn the player. Backing onto a purple chevron pad from the lower level throws him to
  the upper walkway by the Galacta courtyard. Walking backwards for seconds on the plaza walks off its edge.
- The HUD guard (`record.in_range`) gave one false "HUD lost" with the camera pointing straight up; it fails safe
  (input released, run stops).
- Dropped: optical flow for the turn map (repeating wall panels); solving focal length from pixel shifts; a boost-lag
  model in the controller; a commanded-angle pitch clamp; red-colour enemy finding on JPEGs (L1).
