# Outside research check-in, 2026-09-27 18:45 CDT

Delta from the [18:00 check](evaluator-checkin-20260927-1800.md), using current
Linear comments, landed owner reports, the scientific driver and live lead panes.
Advisory only; no experiment, spend or data access was authorized by this check.

All eight eligible TRAIN ranges now have native IDM stores: 166.926104 admitted
minutes. The [last missing store](../evidence/idm-range-store-203745-20260927/README.md)
finished at 18:18 CDT and IDM explicitly released the Mac. The
[scientific yaw driver](../evidence/nitrogen-spatial-yaw-20260927/scientific-driver/README.md)
also landed, closing the independent implementation gap raised last check.

The first yaw cache attempt refused a stale sealed-denylist pin before payload
reads. The reviewed correction is b0d4abf; no exclusion was relaxed. Operations
used that wait to move the three short IDM match decodes forward. Latest owner
handoff: -4 complete and inspected, -5/-6 running serially, then explicit release
back to yaw extraction. This queue adjustment uses available work sensibly.
The expanded fit roster remains eight ranges plus -4a1/-5a1/-6. Newly admitted
matches do not continually expand this attempt.

No new model-quality or live-policy result exists. Reading the finished yaw
trainer/report supports the intended comparison: paired seeds and schedules,
equal readout capacity, fixed cutoffs, untouched-base and zero references,
directional and false-turn slices, and exact frozen-path retention. The code
does not turn an exploratory outcome into a live result. Both grids' results
remain available for the earlier cheaper-4x4 interpretation.

## A possible shorter route to the same experiment

The [sizing memo](nitrogen-spatial-yaw-sizing-20260927.md) gives an exact dual-grid
payload of 106,497,310,720 bytes (99.18 GiB). The existing route extracts on the
Mac, then needs these features in the cloud for all six fits. At the historical
10 MB/s Mac-to-Modal rate in `docs/compute.md`, upload alone would take 2.96 hours.
This is a conditional calculation, not today's measured transfer speed or ETA:

| Upload rate, decimal MB/s | Transfer alone, hours |
|---|---:|
| 10, historical reference | 2.96 |
| 20, illustrative | 1.48 |
| 40, illustrative | 0.74 |

The original sizing already proposed one shared cloud extraction. Its previous
same-cohort L40S tower passes took 862.8-893.1 seconds; those measurements exclude
the new wider cache writes, hashing, commits and setup. The successful probe3
already read admitted pixel-cache blocks from `rivals-explore-chunks-20260927`.
That is evidence for a potential route, not verification that every needed source,
weight and metadata binding is presently complete for cloud extraction.

[Current Modal list prices](https://modal.com/pricing), checked this turn, give
$0.000542/s for L40S, $0.0000131/core/s and $0.00000222/GiB/s. For eight billed CPU
cores and 32 GiB, 15-30 minutes is about $0.65-$1.29 in compute. This excludes
startup, staging, hashing/commit time, storage and any region premiums; it is not
a full-job budget. Current campaign allocations and fresh guard rates still
determine whether an alternative fits. The original $3 extraction proposal is
historical, not a remaining authorization after the shakedown reallocation.

**Recommendation sent to operations:** compare full time-to-result for the ready
Mac path against one shared extraction beside the existing cloud inputs. Use
available receipts first, without creating a new benchmark. Choose the cloud
route only if source availability, adapter effort, full cost and current $24
campaign accounting support a clear time saving. Otherwise continue the prepared
Mac path. The current CLI requires MPS; this is not a configuration-only switch.
Keep both grids on the same feature backend and compare against a same-stack
frozen base; do not assume CUDA and MPS features are bitwise interchangeable.

This is a placement decision within the same scientific question, with
operations/explore-policy as its existing consumers. It seeks an earlier answer
without adding model variants or a new lane. The advice was submitted through
Herdr after inspecting the lead's empty composer. At 18:50 the lead asked the
existing explore-policy owner to compare routes from available timings, retaining
the current remaining allocation and choosing the Mac if switching takes longer.
No extraction-route decision or paid launch is claimed here. Next check should
distinguish actual extraction/transfer progress and fit results from preparation.
