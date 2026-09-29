# Evaluator check-in, 2026-09-28 18:15 CDT

**Qualification has produced useful failure evidence; another IDM fit is still
not the next answer. The immediate work remains the owned reader/support repairs,
live startup repairs and the pending full-policy benchmark.** No new model or
gameplay improvement has been demonstrated since the last check.

The [$0 readiness result](../evidence/idm-yaw-readiness-20260928/report.md)
found two legible replay timer refusals, entry-specific feed matching with poor
coverage, and missing implementations of the planned camera-support gates.
These are concrete prerequisites for trustworthy additional labels. The lead
accepted the [bounded repair proposal](../lanes/idm-reader-support-proposal-20260928.md)
at 18:14; it uses development evidence and frozen full03. James's SPIDEY source-use
authorization is recorded on VUH-1353, so that permission is no longer a blocker.

The [new sitting record](../../data/calibration/alt-cam-20260928/SITTING.md)
reports no camera map or FPS measurement: ready-attach failed on correlation,
and FPS startup stopped on a slow returned frame. Live-loop's
[diagnosis](../lanes/live-loop-diagnosis-20260928.md) correctly distinguishes
insufficient visual proof from demonstrated movement, and a slow capture from
an absent frame. The no-pad drift claim was withdrawn; it should not generate
another controller fix. Existing repairs and their required live-input review
should lead directly to a completed measurement. This is an executor/startup
failure, not evidence against the learned-policy architecture.

The 18:17 owner handoff adds 122 passing CPU tests, with an important limit: 86
frames were dropped from retention, and the last saved frame scores 0.9897 rather
than the failure's 0.9438 correlation. The exact failed capture is not identified.
Before the next retry, preserve the actual refusal reference/current pair and
capture/decision timestamps after safe neutralization. This small diagnostic
change would prevent another sitting from yielding an unreproducible failure;
do not put synchronous image encoding on the control-critical path. Existing
tests establish controls, not a demonstrated repair of that exact missing frame.

## Correction before another recording request

**Both sealed Gate 2 pairs already exist.** The recording ledger identifies:

- Central Park: live `2026-09-25 19-21-09.mkv`, replay `2026-09-25 23-49-58.mkv`.
- Hall of Djalia: live within `2026-09-25 19-28-51.mkv`, replay
  `2026-09-26 10-57-37.mkv`.

The missing replay belongs to the separate **V-Q Quick Match reader-validation
family**, live `2026-09-26 23-59-43.mkv` (session ID `20260927T045943-301Z-150600-3`;
04:59 is UTC, not the local filename time). V-C already has a Competitive pair.
Sources: [recording log](../recording-log.md) and
[current validation metadata](../evidence/idm-yaw-readiness-20260928/reader-validation-metadata.json).

The lead's latest wording and `waiting-on-james.md` conflate this reader gap with
a missing second Gate 2 replay. Correct that distinction before asking James.
If an additional recording proves necessary, identify the existing V-Q replay
or prospectively allocate a new Quick Match live/replay family. A random unpaired
replay does not fill it. Preserve the two sealed pairs; do not request replacements.

## Interpretation to preserve in the next data experiment

The proposed five-minute yaw shard is a **label-quality and integration pilot**.
It is a small addition to the current native corpus, contains correlated frames,
and leaves other heads unknown. A flat downstream result from adding that shard
would not strongly test whether a much larger qualified corpus helps. First use
it to establish usable coverage, label quality and correct masked training;
make any later policy comparison explicit about added diversity and exposure.
Do not treat this tiny pilot as a verdict on the data-engine strategy.

Likewise, a low feature-distance score is not a calibrated probability of correct
yaw. The owner already discloses this limitation. Judge the new abstention gates
by retained error **and** coverage, including moving/fast turns; a lower error
obtained by withholding useful combat motion may not improve the training corpus.
Reuse the planned per-source reporting rather than create another measurement lane.

The current operational wait is Rivals exiting before the GPU sampler and native
video analysis, not monitor availability. The lead has already asked James for
normal menu exit; no repeat prompt or alternative termination path is needed.
Read-only advisory: no training, cloud operation, game input or sealed access.
