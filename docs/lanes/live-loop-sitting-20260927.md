# Camera and FPS sitting: startup repair accepted

Owner live-loop; desktop/booking/Linear owner herdr-lead; input reviewer binds-review.
VUH-1384, 2026-09-27. This is the next-attempt plan, not acceptance evidence.

The first sitting stopped after yaw-01. Fresh-pad drift moved the ready view
while its token waited 39 seconds, then the segment refused. The environment's
Temp launcher was missing, so FPS A/B/A never ran. Camera map, focal, game FPS
cost and acceptance remain unknown. Raw evidence is
`data/calibration/alt-cam-20260927/yaw-01`; partial OBS video is
`C:/Users/volpe/Videos/2026-09-27 14-27-37.mkv`.

Lead released the PC at 15:24 CDT. Camera checks completed and a3 landed 91b6d9b.
Calibration focal analysis completed with an explicit refusal; its decoder and
fit exited. **Next sitting is yaw + FPS only**, after admission -5 assembly.
No pulse or new mouse-sweep block is included. Workers stop before the sitting.

## Before the next sitting

- Both camera modes have a3 pre-run LAND, receipt
  `docs/evidence/camera-turns-20260927/camera-turns-review-v1-a3.json` (47a7960a),
  reviewer handback f5298fae. Owner/reviewer each passed 40 CPU tests. Fixed native
  yaw-01 drift refuses; duplicate control passes. Old a2 is stale. Startup is
  capture-only token before Live; zero settle; M1 +.45 rx /300 ms; observed
  response from a late-prime 40-100ms pair; five seconds neutral; NEW ready-0
  inspection/token. Initialization is excluded with times. Changed or unprovable
  ready poses refuse. No retry, automatic leveling or search.
- Durable Python is `C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe`.
  Static env receipt 38bf7953: 36 pins, package checks/inference imports passed;
  DXCAM enumeration failed in service session 0. Lead will probe DXCAM/vgamepad
  through C:\desk in console session 1 after James closes the game. No new-env
  CUDA forward, FPS preparation or desktop qualification is claimed. Camera
  CPU tests passed using the repaired env.
- Focal is unknown after the actual alt CALIBRATION attempt: four native pose
  inspections, then 96 adjacent frames at 6.0-6.8s and 52 common tracks. All 20
  delay/smoothing models refuse. Horizontal/vertical RMS 3.637/3.840px exceed 1.5px
  gates; diagnostic 625px and profile 615-630 are NOT an accepted value or bounds.
  Old 465 gain coupling is unresolved; no main-account transfer. Raw evidence:
  `docs/evidence/focal-calibration-20260927/alt_left-window-20260927T202800/fit.json`.
  Focal packet landed 0dafeb0 with seven owner tests; full result is
  `docs/evidence/focal-calibration-20260927/RESULT.md`. Decoder/fit/test processes
  exited, CPU only, 425 MB peak parent RSS; no further work queued.

## Operator sequence and time

James authorized the lead to use reenter.py for setup, navigate and refresh
activity. James need not be at the desk. No worker drives input or capture.
Exact commands and atomic tokens are in
[live-loop-operator-20260927.md](live-loop-operator-20260927.md); it names the accepted a3 receipt and durable interpreter.

Allow about **23 minutes, capped at 30**, for yaw plus FPS. Hard stop remains
minute 33 if camera work is incomplete. Do not keep the range idle awaiting
implementation or a focal fit. The focal-dependent six-minute pulse block and
old six-minute mouse-sweep block are omitted from this attempt.

1. Setup Spider-Man in alt Practice Range, Steam Input disabled, H/V247/124,
   observed actual curve/assist/cooldown settings, FPS overlay and native OBS.
   **Move-and-attack keep-alive before the first block**, close that pad, then
   restore the open, level, bot-free view. Setup alone did not prevent idle drop.
2. Run yaw groups (+.45,-.45,+.1,-.1), (+.2,-.2,+.3,-.3), (+.6,-.6), and finally
   (+.8,-.8,+1,-1), at most 180 seconds per command. Refresh activity only after
   closure between blocks. No focal is needed. Every block has ready-attach
   approval without a pad, M1 prime, five-second neutral delay, then a separate
   ready-0 token. Recheck level, bots and banner after the roughly 50-degree turn.
   Native video must count full turns; an NPZ return is only a candidate.
3. Skip all short-pulse groups: focal was not established. Their commands remain
   in the sheet for a later accepted focal, not this sitting.
4. After camera closure and another activity refresh, run the actuator-free FPS
   A/B/A for 120 seconds with fixed view/settings/OBS/cap. Stop all worker math,
   tests, decode and inference during the comparison. No keep-alive inside it.
5. Retain failures and unexecuted rows. Annotate visible FPS evidence after
   closure, report A drift/cap saturation and paired loss. Lead writes the sitting
   record and acceptance. No worker process is required concurrently.

## Fallback and acceptance limits

The interim94-s012 fallback hash is
`2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`.
Its fixed 3,600-native-TRAIN-frame replay emitted zero supported actions and raw
median camera every step (100% neutral), versus 437 supported human presses,
28.42% action-neutral and 9.92% action-plus-camera-neutral. Evidence:
`docs/evidence/live-loop-fallback-train-20260927/RESULT.md` (f8892cf).
Historical frozen-dev self-fed failure stands. Use it only as FPS workload with
outputs discarded; there are no learned-versus-scripted pairs. A0 does not exist;
round3 is parked. Lead must explicitly select any replacement.

FPS runner 22b53fc has 27 owner tests and no actuator. A1/B/A2 each has 10 seconds
warmup plus 30 measured. Capture/guards/evidence remain active in A; B adds
single-flight CUDA inference. Report actual capture and 1Hz counter sample rates,
prediction ages, memory, dropped evidence, median/p10 FPS, A drift/cap saturation
and paired loss. Sparse counter readings are not frame-time/1%-low measures.
GPU inference approval 4f81722 does not make an unexecuted FPS result measured.
Any policy input still requires eligible checkpoint, accepted maps, reviewed
input and re-freeze of controller/loop/record/pad_bindings and dependencies.

## VUH-1384 current-result text for the lead

The camera/FPS sitting stopped after yaw-01: fresh-pad drift invalidated its
ready view, motion refused, and FPS could not start because the Temp Python
launcher was missing. No camera map or game FPS cost was measured. Startup
repair has a3 pre-run LAND (47a7960a), with 40 owner/reviewer CPU tests and an
actual yaw-01 drift rejection: pre-attach token, M1 300ms prime, five-second
neutral, fresh ready-0. Durable env receipt
38bf7953 provides C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe;
console-session desktop probe remains lead-owned. The alt CALIBRATION focal
attempt refused: 96 frames /52 tracks, all 20 models fail residual gates; no focal
or bounds. Decoder/fit stopped. Next sitting is yaw+FPS only after admission
assembly; no pulses. Fallback
replay f8892cf was 100% neutral across 3,600 frames; learned/scripted trials remain
deferred. Lead owns publication and sitting scheduling; no Linear write claimed.
