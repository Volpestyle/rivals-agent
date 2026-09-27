# TRAIN focal attempt — VUH-1384 — 2026-09-27

Owner: camera-analysis. Integration/provenance owner: live-loop.

**Actual result: refused; no focal or defensible bounds.** Three pinned native
stills at rows 7, 1807 and 3606 yielded zero shared LK tracks. Visual inspection
shows changing camera position, airborne/close combat, pitch and near geometry.
The intervening raw counts exceed the slow-gain speed support. These frames
cannot replace a stationary far-landmark sweep.

[Result and retained evidence](../evidence/focal-train-20260927/RESULT.md)
contains source hashes, actual counts, observations, the empty track attempt,
startup failure, reusable fitter's limits, and test evidence (15 passed).

Scope stayed within the named admitted TRAIN source and the four assigned new
paths. Existing `steps.load` denylist checks precede access. No native decode,
GPU, desktop, cloud, input, dataset writes or Linear writes. All work is offline
exploration under the owner-test rule; no independent review was requested.
Game presence prevented new decode, and no extraction is running or queued.

The source settings hash and lead-verified 1.89/1.89, 800 DPI provenance are
retained. Account identity remains unknown and alt focal transfer unverified.
One input-only slow-yaw shortlist (833:860) is uninspected; no-button state is
not stationarity. The fitter remains a diagnostic until independent far tracks,
windows/signs and latency/gain support agree. Live-loop was told not to wait or
remove the focal step from the sitting based on this attempt.
