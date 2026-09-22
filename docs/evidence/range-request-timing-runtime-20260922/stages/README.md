# Actual request-run stage cost, 2026-09-22

The next latency investigation should isolate the existing HUD reader's cost. In this run, the HUD/coasting stage took **27.91 ms median**, compared with **0.95 ms for the entire brain/consumer call on model-event decisions**. Acquisition-to-offer and publication-to-consumption also consume substantial time. These clocks locate elapsed costs; they do not identify a particular HUD subreader or establish CPU contention. Root owns that narrower reader profiling. No model, thread, deadline, tolerance or production change is proposed here.

Inputs are the finalized `range-request-timing-20260922-1` JSON and the two preflight JSON files. `receipts.json` records their identical before/after hashes and the inspected Loop source hash. The analysis imports only the standard library, reads no checkpoint/media/human rows, performs no inference, and does not execute Loop. It does not transfer predictions or durations from the earlier run.

## Retention and scheduling

The 4.751-second run retained 196 normal ticks and all 45 decision records, including failed-send decision 45. Every first decision row's timing object exactly matches its metadata timing object and actual State timestamp. All 45 were published and consumed; the report retains explicit missing/unconsumed fields (empty here). Twelve decisions lack a first executor timing; their consumption-to-execution values remain null.

There were 29 `model_event`, two `low_confidence`, 13 `warming_up`, one `target_unobserved`, and **zero `invalid_history`** outcomes. Model-event proposals were 11 starts and 18 no-new-starts. Low-confidence outcomes are separate from these proposal counts.

Of 48 phase slots, 45 were offered. Slots 13, 16 and 30 were correctly skipped: the first eligible acquisitions were respectively 25.5753, 25.5206 and 30.2654 ms after phase. These produced actual adjacent gaps of 200.0925, 207.1645 and 185.6498 ms before decisions 14, 16 and 29. Clock-only five-observation accounting reproduces all recorded warmups and usable model windows: three initial warmups, then two, four and four after those gaps. The initial target-unobserved observation accounts for the other initial clock-warmup position. There was no worker-queue miss. Missing slots still cost history rebuilding; no timestamps or slots were repaired.

## Actual elapsed stages

All-decision distributions, in milliseconds; p95 is nearest-rank. Percentiles are not additive. The script checks each individual decision's stage sum against acquisition-to-consumption (maximum accounting error zero).

| Stage | Median | p95 | Maximum |
|---|---:|---:|---:|
| Acquisition to offer | 22.647 | 29.678 | 30.886 |
| Offer to worker | 1.241 | 1.378 | 1.450 |
| Detection/tracking/tag stage | 4.358 | 13.030 | 13.511 |
| Coasting snapshot + HUD | 27.908 | 33.376 | 42.577 |
| State assembly | 0.0048 | 0.0074 | 0.0273 |
| Entire brain/consumer call | 0.902 | 1.849 | 3.223 |
| Brain completion to publication | 0.0225 | 0.0273 | 0.0347 |
| Publication to first consumption | 14.173 | 24.542 | 30.695 |
| **Acquisition to consumption** | **72.696** | **84.809** | **95.572** |

Acquisition-to-publication median was 59.681 ms. Acquisition-to-offer includes capture/guard/reflex processing, not just queue dispatch. Detection/tag includes wide detection/tracking when used plus the tag loop, not an isolated tag read. Publication-to-consumption includes reflex/scheduling wait. For the 29 model-event decisions alone, the brain/consumer median/p95/max were 0.952/2.842/3.223 ms. That stage includes consumer gates, history/features and model work; it is not isolated Torch timing. Preflight recorded 24 intra-op and 24 inter-op threads both before and after main, unchanged. These measurements give no reason to prioritize thread tuning.

## One failed send, with exact margins

The fixed 100 ms authorization horizon and 33 ms press leave at most 67 ms from acquisition to press start, before accounting for send proof. The first ten start requests all had negative full-press slack at their first execution: seven reported `insufficient_press_time`; three reported `unstable_target` (also late, but do not relabel their actual refusal). Decision 45 was the first accepted start.

For decision 45, acquisition-to-consumption was 65.8075 ms: pre-offer 19.0077, queue 1.2604, detection/tag 12.2489, HUD/coasting 30.9901, assembly 0.0052, consumer 0.8554, publication 0.0219, and consumption wait 1.4179 ms. Detection/tag plus HUD alone cost 43.2390 ms. This particular failure had little remaining publication wait to remove.

| Decision 45 boundary | Loop time (s) / margin |
|---|---:|
| Actual acquisition | 11.256737500 |
| Authorization expiry | 11.356737500 |
| Controller acceptance | 11.322548600 |
| Full-press slack at acceptance | 1.188900 ms |
| Send entry | 11.322863600 |
| Latest full-press start (`not_after`) | 11.323737500 |
| Full-press slack at send entry | 0.873900 ms |
| Failed return | 11.324030400 |
| Send-call elapsed | 1.166800 ms |
| Failed return beyond full-press deadline | 0.292900 ms |

The recorded error is `guarded input deadline expired after proof; input released`. Acceptance-to-send entry used 0.3150 ms. The failed-send row and both cancellation/release rows reference the **same attempted send**. There were zero returned LT calls and both releases returned; controller acceptance does not establish delivery or a cast. The deadline guard stopped correctly. The timestamps do not isolate the exact instant within the send call at which proof completed.

## Next bounded step and reproduction

Root's reader profiling should identify which work makes the actual HUD/coasting stage roughly 28 ms, then propose the smallest semantics-preserving reduction. Detection/tag is the next worker cost to inspect if needed. Pre-offer processing and reflex consumption cadence remain separate contributors; improving only GRU dispatch cannot recover the observed margins. No expiry extension or relaxed history tolerance is supported. A reduction must be measured at actual guarded-send acceptance, not inferred to guarantee success from summed median savings.

`analyze.py` creates `report.json` and `receipts.json` exclusively and refuses to overwrite them. Reproduce in a clean copy at the same repository-relative path, with the four pinned inputs and inspected source available, using an existing Python interpreter. The report contains per-decision stage costs, actual schedule entries, all start margins, missing markers and the retained single failed-send evidence. This is one short runtime diagnosis, not a throughput benchmark or quality/generalization result.
