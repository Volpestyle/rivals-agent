# Discard stale frames before controller attachment

Sitting `alt-cam-20260928e/yaw-01` stopped on its first pre-attach proof: 600.2695 ms against the 100 ms freshness bound, while every semantic guard passed. No pad existed and no input was sent. V5 retained the exact frame and clause. A subsequent 60-frame read-only probe had a 38.301 ms worst combined capture/check time and did not reproduce the stall. Its source is unestablished; this change does not claim to fix that source.

The delta from `1af578c` is confined to `pre_attach_proof` and its tests. Before a pad exists, it may discard stale/no-frame acquisitions within a two-second window of acquisition starts. Every returned frame must still pass all existing guards and the unchanged 100 ms age bound. Range/idle/focus/keyboard/deadline failures and capture exceptions remain immediate stops. Persistent stale captures retain the last exact checked frame and clause. Discard events split capture from guard timing for diagnosis. The original block deadline remains binding; a blocking backend call cannot be preempted by this helper, and no pad exists during it.

All post-attachment behavior, attach-token inspection, pose comparison, prime, report leases, deadlines and measurement acceptance are unchanged. This is a readiness change; no stale image gains permission to drive input. It does not establish a yaw rate or qualify sitting e as calibration.

Owner validation: the measurement/ready-pose/prime suite passed 143 tests with 12 corpus skips. Tests reproduce the measured 600.2695 ms interval in acquisition and in checking, verify a different fresh frame is returned, and cover persistent stale captures and semantic failures. The existing post-attach refusal tests remain in the passing suite. Review and byte pins are adjacent when issued.

Live evidence remains in `data/calibration/alt-cam-20260928e/`, including `SITTING.md`, the exact refusal frame/metadata and the read-only timing probe. Native OBS reference: `C:/Users/volpe/Videos/2026-09-28 22-03-09.mkv`. No new live attempt is included in this packet.
