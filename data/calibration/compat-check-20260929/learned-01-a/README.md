# Learned-01 A: runner diagnosis (2026-09-30)

The live attempt stopped at 12.932 s with `stale_or_nonmonotonic_frame`.
It made 126 decisions, discarded 121 after inference, sent five pad snapshots,
and closed the pad and policy worker cleanly. Sources: [result.json](result.json)
and [frames.jsonl](frames.jsonl). No additional game input or OBS decode was used
for this diagnosis.

| Live trace component | p50 | p95 |
| --- | ---: | ---: |
| Inference | 95.21 ms | 131.64 ms |
| Capture timestamp to inference start (`queue_wait_s`) | 33.41 ms | 61.86 ms |
| Decision age | 135.79 ms | 192.33 ms |
| Completion to controller pickup | 1.36 ms | 17.49 ms |

`queue_wait_s` includes acquisition, HUD readers, frame copying and pending-job
residence. The existing trace cannot separate those costs. The runner now adds
`capture_s`, `readers_s`, `offer_copy_s` and `queue_resident_s` so the next live
run can identify which part consumes the budget. Capture timestamps still
identify the exact policy frame; neither an updated HUD proof nor a later
observation refreshes its input expiry.

A 50-run CPU check on this run's native 2560x1440 `stop.png`, with two OpenCV
threads, measured native copy p50/p95 2.11/3.03 ms and 1280 resize plus copy
1.15/1.45 ms. This saves about 1 ms on the producer. The current policy enlarges
the smaller input again and runs the same two encoder views, so this does not
establish a model-speed benefit and may lose crop detail. Native policy input
remains unchanged. The policy owner handles model/preprocessing latency.
Working measurement: `D:/rivals-offline/learned-runner-20260930/runner-live-a-analysis/copy-timing.json`.

The old stop combined invalid/future age and repeated/regressed timestamps in
one OR expression, without recording its values. **The exact historical branch
cannot be established from the retained artifacts.** `Live.fresh()` explicitly
returns its previous frame after a capture timeout, which repeats its timestamp.
Treating this expected transient reuse as a fatal nonmonotonic clock is a runner
contract bug; it does not prove that reuse caused this particular stop.

The corrected runner releases input and records an `observation_discard` for
transient repeated/stale frames, then reacquires before inference or input.
The 100 ms input freshness bound stays unchanged. Existing 250 ms no-frame
grace bounds a persistent capture stall. Clock regression, future/invalid stamps
and persistent stalls stop under distinct named clauses. Refusal rows record
current/previous stamps, age and reader/acquisition costs; the final native
stop PNG remains mandatory evidence through the existing run cleanup.

The launcher now records `<attempt>.gpu-preflight.json` and warns about other
Python/TensorRT GPU clients without creating a resource gate. A read-only
post-run snapshot at 18:59 UTC found IDM PIDs 241336 and 158128 at **2939.5 MiB
dedicated usage each** using Windows GPU process-memory counters. NVML reported
`[N/A]`, which is unknown, not zero. This is a post-run measurement, not a
reconstruction of the live VRAM allocation. Pausing a process does not release
its model allocations; shared allocations may cause pressure, but the retained
live trace alone does not prove VRAM paging caused its latency. No other
processes were paused or closed by this worker.
Working snapshot: `D:/rivals-offline/learned-runner-20260930/runner-live-a-analysis/gpu-snapshot.json`.

Offline regression checks cover transient reuse/recovery, stale readers,
clock regression, invalid/future stamps, capture stall, camera-pulse release,
timing separation and Windows GPU-probe telemetry failures. They do not establish
the next sitting's latency with the game running. The next live run supplies
that measurement.
