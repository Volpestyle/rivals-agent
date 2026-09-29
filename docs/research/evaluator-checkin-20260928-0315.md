# Outside research check-in, 2026-09-28 03:15 CDT

Inspected through 03:19 CDT. Delta from the [01:15 check](evaluator-checkin-20260928-0115.md)
and the [guard audit](modal-guard-reliability-audit-20260928.md): recovery work has
delivered, and full03 has launched. **Let the unchanged IDM experiment finish.**
There is no new accuracy result and no evidence warranting another architecture
bet or an interruption of this run.

The [accepted v2 shakedown](../evidence/modal-guard-v200-shakedown-20260928/report.md)
(`b370275`) demonstrates detached calls surviving the deliberate death of both
host observers, reattachment to their original call IDs, native timeout and
eventual zero containers without host stop calls. A committed synthetic CUDA
checkpoint survived the timeout, and its restored next stochastic output matched.
The [IDM recovery implementation](../evidence/idm-epoch-resume-20260928/report.md)
(`05a61b4`) separately reports exact interrupted/uninterrupted CPU training-state
parity, torn-publication recovery, warn-only telemetry and independent artifact
collection. These address the named failure boundaries; they do not constitute
a new model-quality result or full IDM CUDA parity test. Reuse this accepted
evidence rather than commissioning another general reliability review.

[Full03 launch](../evidence/idm-expanded-full03-launch-20260928/report.md)
(`debe338`) was at **02:56:46 CDT**, app `ap-S6lLYCw0bpGcPfFhcMyLgy`.
The owner's local watcher refreshed at 03:18:02; it records one active container,
no terminal state and no verified epoch yet. This is a fresh execution observation,
not a measurement of training throughput or convergence. The Mac's host log
contains the detached app/call IDs, without step counters. Do not turn the
ten-hour timeout envelope into a training-progress denominator. The watcher
will deliver the first verified epoch and the eventual terminal result.

The scientific recipe remains seed 0, three epochs, eight TRAIN ranges plus
matches -4a1/-5a1/-6: **181.89 admitted minutes**. The existing corpus receipts
attribute 166.93 minutes to range and about 14.96 to matches: approximately
**92% range / 8% match by duration**, before context trimming. Both frozen dev
sources are ranges. Consequently, a matched range-dev improvement would support
the expanded recipe on that domain; it would not by itself establish match or
replay transfer, nor isolate a causal data-volume effect from the old MPS/new
CUDA difference. This is an interpretation limit, not a reason to modify the
running cohort or open sealed footage.

The useful next decision remains the existing camera-error and press
precision/recall/coverage report with real/zero controls, followed by the
established range-to-match diagnostic and camera-first Gate 2 sequence. If camera
qualifies while buttons lag, preserve the planned partial-label route with
unsupported buttons unknown. Additional admitted matches can inform a later
refit, but the present result should first identify what still limits usable
labels. The closed custom yaw-head line and retired Round 3 need no new work
while this result is pending. No new live calibration or gameplay evidence was
found in the inspected delta.

One small prevention correction belongs to the lead: `docs/compute.md` still
says every paid run needs a **running-spend stop**, immediately above the newer
no-custom-budget rule. Its dated older cap paragraphs also read partly like
standing requirements. Remove or clearly mark the superseded requirements so a
future worker does not reintroduce the mechanism that killed these runs. This
is a documentation cleanup, not another launch gate or a change to full03.

The lead's latest manual bill check remains 02:51: $78.33 metered, roughly
$104.62 projected with full03; neither is a current settled invoice. No new
provider query, paid action, training, sealed-data access, schedule or dispatch
was performed. Read boundary: Rivals Agent project issue delta since 06:15 UTC;
VUH-1353's latest comment updated 08:06:46 UTC; retained launch/recovery receipts,
current watcher metadata, steering handoff, recording ledger and live lane note.
The existing lead is the consumer of the interpretation and documentation advice.
