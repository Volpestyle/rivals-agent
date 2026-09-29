# Outside research check-in, 2026-09-28 00:15 CDT

Focused delta from [23:15](evaluator-checkin-20260927-2315.md), using the hourly
schedule James requested. The substantive experiment is progressing; no new
model-quality result or change of research direction is warranted yet.

Read-only logs for full02 app `ap-euLgri5kwbkjuNBUaB7Nng` show 337,600 of
1,961,526 training row visits at 00:16:24 CDT: **17.21% of training**, not of
the entire pipeline. Between 00:04:51 and 00:16:24, throughput is about 7.07
batch-16 updates/s, consistent with the 6.78/s conservative sizing probe.
The first epoch has not completed in this sample. Evaluation and calibration
are still ahead, so this is progress evidence, not evidence of accuracy.
The job board lists the same active Modal app; the completion watcher has a
fresh 00:16:03 heartbeat and reports RUNNING, no exit and no result yet.
Its $14.82 allocation estimate includes previous lane bounds and storage;
it is not this run's invoice. The authorized full-run cap remains $26.29.

The separate steering pane retired at James's request. Its
[handoff](../steering/handoff-20260927.md), landed at 0afbc63, retains the
IDM-first, camera-first qualification and pretrained-policy comparison
directions. It also accepts the prior correction: poor generalization does
not uniquely diagnose too few hours, and the archive needs transfer/source
qualification before labeling. Updated only this evaluator's routing brief
to avoid messaging the retired pane. Operations retains dispatch and spend
authority. The handoff's old 45-minute reference is historical; the live
Windows task and current brief are hourly.

No newer VUH-1346 or VUH-1353 result comments arrived. Operations reports a
project update and cleanup of superseded issues; it explicitly distinguishes
the milestone percentage rise caused by cancellations from research progress.
The new VUH-1384 comment records both failed camera/FPS attempts and the
accepted repairs, with focal, signed maps and actual game FPS cost still
unmeasured. No new live sitting is claimed.

The next scientific decision still depends on the completed expanded IDM's
camera error and press precision/recall/coverage, followed by the existing
transfer protocol. Continued training at the measured rate is expected work,
not a stall. No status-only message, extra research assignment, compute,
review or schedule was created in this check.
