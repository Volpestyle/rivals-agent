# a3: pre-attach approval and M1 startup for both modes

Owner live-loop; VUH-1384; pre-run input review requested from binds-review.
Exact eleven dependency pins: source-hashes-a3.json. Only driver/tests changed
from a2. Old receipts are stale. No live input, desktop capture, video decode,
GPU or sealed-source access was used for these checks.

The stopped yaw-01 sitting is retained under
`data/calibration/alt-cam-20260927/yaw-01`. A 39-second post-attach token wait
allowed fresh-pad drift to invalidate the ready pose. Full-turn mode now uses
the same M1 startup as pulses; there is no human wait with an unprimed pad.

## Input order and guards

1. Capture-only ready-attach and operator token BEFORE Live. Fresh range/idle,
   focus/key and <=100ms capture proof; <=180s deadline includes the gate.
   Compare current scenery with saved ready-attach; refuse changed/ambiguous pose.
2. Verify receipt again, construct Live with settle_s=0, install report watcher
   and independent focus/key/deadline monitor. First guarded non-neutral report
   is START_TURN_RX=.45 for START_TURN_S=.3 from agent/startup.py. No PNG encoding,
   sleep, operator gate or search before prime. collect_segment retains every
   fresh frame; renewals <=40ms, leases <=100ms capped to prime end, finally neutral.
3. Require observed response with unchanged l4.checked_shift(direction=-1).
   Pair uses guard-retained native frames and their capture timestamps, both
   in the latter **150-300ms after first send**, separated by **40-100ms**. Full
   ~50-degree displacement may exceed the motion check envelope, so this pair
   tests response only. Record pair times, gap and mid_motion_response_only.
   No suitable pair, no motion, wrong sign or unreliable fit ends the block,
   without retry, extra pulse or automatic alternate estimator.
4. Five full seconds neutral AFTER response verification, with fresh guards.
   Last half-second requires stable scenery. Save post-init frame; NEW ready-0
   and separate token. Operator checks banner cleared, range, level, bot-free
   pose after roughly 50 degrees right. Five seconds is not a banner detector.
5. Every measurement token gate compares fresh scenery with its saved ready
   frame, including after token arrival. Changed or ambiguous views refuse.
   Bad pose ends the block; no automatic leveling/search or new input type.

Pose gate requires finite phase score >=.5, correlation >=.95, maximum 1.5 band
pixels per axis (~3px at1280). It is conservative: low texture or animation can
refuse. It does not establish a calibrated angle, and no thresholds were tuned
on the failed native pair. Short-pulse measurement axes, durations, focal gate,
lease/freshness checks and no-retry policy are unchanged.

Manifest, initialization start/end events, initialization.json, full reports
and result/failure references label initialization_excluded. Native before,
response-pair and after stills plus full-rate bands are separate from segment
measurements. Failure before detail creation still has exclusion events.

## Owner verification

- **40 passed in 4.49s**, CUDA hidden, private durable env, PCGuard, BelowNormal,
  two CPU/OpenCV threads. Peak observed process RSS122,048,512B.
- Ruff on driver/tests and scoped git whitespace check pass.
- Fixed native regression (no video decode): ready-0 duplicate accepted,
  phase1/correlation~1; actual guard39 drift refused (correlation .1331 and
  unreliable/large phase shift). Exact source PNG hashes and audits retained.
- Checks: a3-checks-run1/pytest.txt and a3-checks-run1/checks.json.
  Reproducer: a3-owner-checks.py. It reads exactly the two existing yaw-01 PNGs,
  no video or corpus. Job status marked done; process exited.
- Synthetic checks cover both-mode ordering, 39s pre-attach delay without pad,
  rejected tokens/changed poses, late-prime response-only pairing, early-only
  capture refusal, missing motion/no retry, five-second neutral, initialization
  exclusion on failure, lease deadlines and independent blocked-capture stops.

Operator sheet still HOLD until pre-run receipt accepts these exact bytes.
Lead will use reenter.py, keep-alive BEFORE first block, close its pad, restore
pose, then approve attach and NEW ready-0 separately. No worker input/capture.
Durable Python: C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe.
Lead owns console-session DXCAM/vgamepad qualification. Focal, camera map, game
FPS cost and live-policy acceptance remain unmeasured.
