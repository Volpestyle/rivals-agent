# Current sitting: lead-operated yaw and CUDA FPS cost

Owner live-loop; desktop/booking/Linear owner herdr-lead; input reviewer binds-review.
VUH-1384, updated 2026-09-27. This is a plan, not evidence of a completed sitting.

James authorized the lead to open the game, navigate to Practice Range and do
pad move-and-attack activity refreshes between measurement blocks. **James does
not need to be at the desk for these operations.** Live-loop and workers send
no game input and open no capture. The older 55/40-minute human reservation is
superseded by this operator arrangement, not by an accepted camera map.

Exact ordered commands, screenshot checks and atomic token locations:
[live-loop-operator-20260927.md](live-loop-operator-20260927.md), landed ad47f57.
The lead runs one block at a time, inspects its result and confirms closure
before any separate keep-alive. No concurrent worker process is needed.

## Current decision and timing

**Recommend yaw full turns + actuator-free FPS only for the current attempt.**
Allow roughly **23 minutes, capped at 30**: setup/pose/recording 0-4; four yaw
blocks 4-16; FPS A/B/A plus setup 16-19; retain evidence and close 19-23. Never
extend a block past 180 seconds. Retain the prior minute-33 absolute stop if
operations slip; it is not permission to fill the time with retries. The lead
owns the actual sequence and stop decision.

Short-pulse commands are ready and independently reviewed, but **all require
an accepted focal receipt**. Do not run them while focal is unknown. If focal
is established later, the lead can schedule their roughly six-minute block,
without the old six-minute mouse-sweep block only if the offline evidence
actually replaces it. The current refusal does not establish that replacement.
No live learned-versus-scripted trials are scheduled for this fallback.

## Offline focal attempt and remaining work

At $0, CPU-only, the worker attempted shared tracks on three existing native
TRAIN stills (rows 7, 1807, 3606 from session 20260923T051828-422Z-33696-1).
**Zero tracks survived. Focal and bounds are null.** The views are about 60 s
apart and show upper-platform near rails, airborne combat, then ground-level
close combat. They do not establish stationary far-landmark rotation. Evidence:
`docs/evidence/focal-train-20260927/existing-20260927T190413/result.json`.

This is a bounded refusal on these saved stills, not a claim that all existing
recordings are unusable. The named TRAIN table contains a promising no-button
slow-yaw window at rows 833:860 (27 frames, about 28.68 s, +368 counts, maximum
1,140 counts/s). Its adjacent native frames were not retained. No video decode
or hash job started before Marvel opened, and none will run alongside the game.
A later bounded extraction/fit while the game is stopped may still avoid any
new human recording. No-button input alone does not prove stationary scenery.

The source's sensitivity 1.89/1.89 and 800 DPI are pinned by its own settings and
review records. Main-versus-alt account identity is not explicit there; transfer
to the current alt view is unverified. Mouse smoothing and acceleration were
ON; gain .0330738 deg/count is supported for the recorded slow turn, with speed
dependence unresolved. Counts remove the need to estimate commanded turn rate,
but moving-frame alignment still needs latency/smoothing uncertainty. Do not
substitute pad sensitivity 247/124 or assume 640 px focal.

## Ready implementation and operator checks

- Camera driver/pulse initialization: landed 6f3a7f7, 29 tests, pre-run a2 LAND.
  Receipt `docs/evidence/camera-turns-20260927/camera-turns-review-v1-a2.json`
  (5c9da6f0); v1/a1 receipts are stale. Full-turn analysis has 47 owner tests,
  landed d1c49a4. Native video must still establish full turns and validity.
- Full-turn groups are (+.45,-.45,+.1,-.1), (+.2,-.2,+.3,-.3), (+.6,-.6), then
  (+.8,-.8,+1,-1). Keep >=.8 last or alone. Each segment has its own fresh native
  ready frame and token; refusal ends the block, without automatic retry.
- Every future pulse block starts with separately token-gated +.45 yaw /120 ms
  initialization. Directional motion must be observed or it stops. Re-check
  the bot-free pose on NEW ready-0 after its roughly 19-degree turn, then issue
  a separate token. Exclude initialization frames/reports/video from calibration.
  Pitch signs alternate +.5,-.5,+1,-1, away from clamps; no return pulse exists.
- Steam Input DISABLED, Spider-Man in Practice Range, actual saved H/V247/124,
  normal cooldowns, visible FPS counter and native OBS recording. Record other
  settings; do not change aim assist ad hoc. Range/HUD/idle/focus/key/capture
  failure or deadline ends the block. Lead refreshes activity only between
  closed blocks and re-establishes pose. Camera turns do not reset inactivity.
- FPS runner landed 22b53fc with 27 tests and actual fallback preparation passed.
  It has no actuator and consumes no execution maps. Use newly observed sitting
  settings, exact checkpoint, compact-bgr, two CPU threads, explicit CUDA and
  capture flags. GPU inference approval is 4f81722. All other analysis stops for
  the A/B/A comparison. Live-fps has finished and is idle.

## Fallback result and FPS contract

Approved fallback interim94-s012 model_nohud seed0 SHA256:
`2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`.
Its fixed 120-second /3,600 native TRAIN-frame replay produced zero supported
presses/holds/releases and zero RAW median yaw/pitch on every step: 100% neutral.
Human: 437 supported presses (3.642/s), 28.42% action neutral, 9.92% action-plus-
camera neutral; mean absolute yaw/pitch 2.027/0.864 deg per step, with pitch
explicitly derived from equal sensitivity. These were self-fed raw classes,
not camera-disabled forced zeros. Replay code/evidence landed f8892cf:
`docs/evidence/live-loop-fallback-train-20260927/RESULT.md`.

The historical frozen-dev self-fed failure stands. Use this model only as the
FPS inference workload, with outputs discarded. A0 does not exist; phase1-02
stopped and phase103 refused before AppCreate; round3 is parked. No adapter or
new candidate is authorized. Lead must explicitly select any replacement.

FPS A1/B/A2 is 120 seconds: each phase 10 s warmup +30 s measured. Keep model
resident, view/resolution/settings/OBS/FPS cap and capture workload fixed. A
has capture/guards/evidence only; B adds single-flight CUDA inference; final A
turns inference off. Capture target30Hz, retained native counter samples1Hz;
report actual rates, prediction ages, memory and evidence drops. No keep-alive
runs during this sequence. Perform it before the sequence instead.

After closure, manually annotate retained visible FPS values (unreadable blank)
and run the annotate command. Report per-phase count/sample rate/median/p10,
A1/A2 drift, cap saturation and paired loss relative to mean(A1,A2). Sparse
counter samples are not frame-time or 1%-low measurements. FPS cost and its
acceptability remain unmeasured until the desktop attempt and annotation.

Any future policy input still requires an eligible selected checkpoint,
accepted execution maps, reviewed input code and re-freeze of controller,
loop, record, pad_bindings and changed live dependencies. No missing rate or
deadzone is guessed, and the current symmetric Cal cannot hide asymmetry.

## VUH-1384 current-result text for the lead

Inference/CLI accepted and landed (7ca7e16, d034ff1). Camera initialization/input
landed 6f3a7f7 with a2 pre-run receipt 5c9da6f0 and 29 tests; offline analysis has 47
tests. Actuator-free FPS runner 22b53fc has 27 tests. Fallback native TRAIN replay
f8892cf was 100% neutral across 3,600 frames including raw camera, versus 437
supported human presses; learned/scripted pairs are deferred. Operator sheet
ad47f57 supports lead-operated yaw and FPS, without worker input or James at
the desk. Offline focal attempt on retained native stills refused (zero shared
tracks); focal/pulses remain unresolved, with a consecutive-frame TRAIN window
identified for later CPU extraction. No A0 checkpoint exists. Camera acceptance,
live policy outcomes, game FPS cost and acceptance remain unmeasured. Lead owns
publication and the sitting record; this text does not claim a Linear write.
