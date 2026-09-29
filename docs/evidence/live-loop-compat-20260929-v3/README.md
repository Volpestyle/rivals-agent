# Compatibility v3: first-observation diagnosis and bounded warm-up

Owner live-loop, VUH-1319; lead w2:p1J routes the delta to live-review.
Offline result produced; code uncommitted and NOT accepted for LAND or RUN.
v1/v2 packets and the run-01 artifacts remain immutable.

## Exact run-01 clause

The first `CompatibilityCheck.observe()` reached the OR condition after
`percept.wide()` and `tracker.update()`. Its first operand,
`self.check_time() - stamp > LIMITS.frame_age_s`, was true. It raised
`stale_perception_or_scope` before the observe event or acquisition selection.
Initial capture freshness, initial scope proof, frame size and detection-box
validation had passed. A target-finder exception would have propagated instead.

This is established by code and result.json, not inferred from target placement:
the result has zero pulses/events and safety.stop_reason is null. In this CLI,
every false LiveSafety.proof either latches a scope reason (focus, takeover,
deadline, idle or range), or raises a pixel error. A scope failure at this check
therefore cannot explain the null safety reason. The age operand short-circuited
the second proof. The exact age and the particular slow component are unknowable
from this run: it retained neither the first frame nor component timing.
156 capture frames/s is throughput, not a bound on end-to-end first-frame age.

## Native timing on this PC

`measure_observe.py` calls the exact frozen v2 observe path, then the v3 path,
on retained 2560x1440 BGR pixels, 50 runs each. It includes frame copy, the
native idle/range pixel readers, native full-width finder, tracker and target
identity match. The timer starts before the fake next(); its stamp precedes
the copy, like capture-start stamping. PNG decode, imports and actual dxcam
acquisition are outside the timer. No live capture, safety scope or pad is
constructed. The guard uses the same pixel readers but replaces OS focus/
takeover checks with a constant offline authority; these timings cannot
establish a live total latency with game/OBS contention.

| Environment / retained frame | Path | p50 ms | p95 ms | max ms |
| --- | --- | ---: | ---: | ---: |
| durable live Python / yaw-01 ready-attach | v2 | 18.70 | 25.79 | 33.63 |
| durable live Python / yaw-01 ready-attach | v3 | 19.34 | 25.70 | 28.52 |
| durable live Python / OBS launch-near frame | v2 | 21.67 | 26.63 | 31.73 |
| durable live Python / OBS launch-near frame | v3 | 20.56 | 25.72 | 26.06 |
| repo environment / yaw-01 (initial process) | initial v3 | 25.79 | 28.81 | 80.93 |

Raw samples and hashes are in timing-*.json. All observations passed. The initial
80.93 ms first call included a 52.91 ms finder, vs 20.54 ms median finder.
Steady processing is not structurally above the 100 ms budget; no detector
resolution/crop change is warranted by these measurements. We preserve 100 ms.

Three additional fresh durable-live-Python processes each, on the OBS frame,
measured first observations of **41.51/32.72/33.86 ms cold**, and
**24.74/30.21/30.51 ms after synthetic warm-up**. Each process also ran 50
observations; raw first/p50/p95 records are fresh-*.json. Warm-up itself took
56.59-59.62 ms outside the scope. This small offline sample supports reduced
first-call overhead, not a proven explanation or guaranteed cure under game load.

## Small runtime delta

Only agent/camera_compat.py and tests/test_camera_compat.py change.

- Split the post-perception OR into `stale_after_perception` and
  `scope_lost_after_perception`, preserving the ordering and short circuit.
- Keep the last actual frame returned, its stamp, reader stage, capture age,
  initial scope/finder/tracker duration, detection count and post-perception age.
- Every caught stop emits a stop event with named clause and stage, after pad
  release, and saves that frame as stop.png. Retention failure is explicit and
  cannot replace the original stop. A stop before a frame exists records why
  it is unavailable. Exceptions retain diagnostics and still propagate. CLI
  attach/construct failures name their exception/scope and missing observation.
- Prime CPU pixel readers and finder/tracker with three synthetic black
  2560x1440 frames after preload, before scope creation and hardware attach.
  Synthetic pixels never authorize input. The existing focus/takeover preflight
  runs again afterwards. Warm-up receipts appear in result.json.

Input bounds, native actuator, response watchdog, admission hashes, calibration
pins, controller map and hero-region protection are unchanged. No input was sent.

## Bounded OBS inspection and next placement concern

Lead released decode only after game and OBS closed. ffmpeg decoded seconds
108-120 at 1 fps with two decode/output threads and BelowNormal priority,
to D:/rivals-offline/live-loop-compat-20260929-v3/frame-01.png through frame-12.png.
stderr is empty. Peak decoder working set was not recorded; no claim of a
measured memory peak is made. No decoder is left running by this worker.

run-01 result creation is 17:47:37 CDT, approximately 116 seconds after the
recording filename time. frame-09.png represents that neighborhood (1 fps
selection, not the actual dxcam first observation). It shows the range HUD,
two green bots and no idle warning. It cannot recover processing-time age.
The original video and all decoded-frame bytes are hash-pinned in review-inputs.json.

**Independent next concern:** on frame-09 the native finder emits only the
right bot: bbox (1521,659,1621,761), center (1571,710). The visible left bot
is in the measured hero exclusion zone, and appears smaller than its native
120 px height exemption. This can make left acquisition time out on retry;
it did not cause run-01. Do not remove the required hero-region protection
as a compatibility fix. Lead must select placement outside that zone or route
the true-positive exclusion to the perception owner for native-frame review.

## v3 sitting procedure delta (lead only)

Keep the existing profile, settings attestation, hash/capture preflights,
human/OBS/focus setup and bounded hidden launch in the immutable
data/calibration/compat-check-20260929/README.md, with these placement and
pre-launch additions. Preserve run-01; a lead-authorized next attempt needs
new output/log/placement names. This packet does not grant a retry.

The **LEFT target** must be outside PLAYER_ZONE: its screen position must have
**x < 0.27 * frame width**, i.e. x < 691.2 and more than **588.8 (~590) px left
of centre at 2560**, **or y < 0.39 * height**, i.e. y < 561.6 at 1440.
It must also lie more than 48 native px left of the crosshair. The right target
must remain more than 48 native px right of it, as before. Prefer a left target
above the zone: a target starting far left at ordinary height can enter the
exclusion zone while yaw converges, so initial placement alone does not establish
that it will stay detectable throughout the check. Do not disable the guard.

Immediately before the hidden compatibility launch, while the game is focused,
the lead runs this read-only screenshot check inside the desktop session using
the same durable live Python. Run it hidden or through the existing desktop
helper, without stealing game focus. Set these variables to the current PID and
new attempt's placement directory; do not reuse run-01 or an old screenshot.

```powershell
& $compatUv run --no-project --python $compatPython python docs/evidence/live-loop-compat-20260929-v3/placement_preflight.py --live-screenshot --game-pid $compatGamePid --out $compatPlacementOut
if ($LASTEXITCODE -ne 0) { throw 'Finder placement preflight refused; do not launch' }
```

The script opens only dxcam capture, saves the exact native screenshot and its
finder receipt, and refuses unless it reports an eligible left AND right enemy,
range HUD and no idle warning. It opens no pad and sends no input. The lead
visually checks that those boxes correspond to the intended Galacta bots, then
launches immediately without human repositioning; movement invalidates the
placement check. The live CLI still requires its own fresh proofs before input.
`--frame` is for offline regression only and never satisfies pre-launch authority.
On the OBS launch-near frame it correctly returned exit 1, left=[], right=[one
box], range=true, idle=false; receipt/screenshot live on D: and are hash-pinned.

## Verification and handoff

140 compatibility + live-safety tests passed with fake IO; tests.txt has the
command result. Ruff passes for the two runtime/test files and timing scripts.
New tests distinguish post-age/scope stops, retain the exact failed frame only
after release, retain reader exceptions and report disk errors without masking
the stop. Existing CLI tests verify warm-up precedes scope/attach. A synthetic
reader test verifies warm-up calls only the intended pixel readers. Placement
tests cover missing left/right, a left target inside the excluded region, and
the approved far-left/above-region placements.
Unchanged v2 acceptance and legacy evidence are reused; no live convergence claim.

The freeze manifest pins runtime/dependencies, preimages, delta and measurements.
Lead requests delta-only independent review of changed diagnostics/warm-up.
Current Linear issue is https://linear.app/vuhlp/issue/VUH-1319 (destination
not fetched here: no direct workspace Linear tool exposed). Pending reconciliation
owner: lead. Record run-01 age refusal, produced v3 packet, unresolved first-live
timing and left-placement issue, and next action: live-review then lead decides
whether placement and a bounded retry are ready. No acceptance transition yet.
