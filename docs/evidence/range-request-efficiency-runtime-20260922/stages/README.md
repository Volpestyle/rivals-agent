# Third-run recorded stage comparison

The run reached `max_time` after cancelling two expired requests. **HUD/coasting remains the largest median stage: 22.94 ms**, followed closely by acquisition-to-offer at 22.70 ms. These are the remaining measured latency priorities for root's decision; this result assigns no further profiling or repair. The full consumer/model-event call took 1.03 ms median. Nothing here supports a model/thread/deadline change.

This compares finalized `range-request-efficiency-20260922-1` JSON with the frozen 45-decision report in `range-request-stage-cost-20260922`. It is elapsed-clock accounting, with no inference, training, native imports or media inspection. Different frames, scenes, durations and proposal mixes prevent attributing the observed differences solely to the HUD optimization. Native outcomes remain with the independent audit.

## Episode and retained clocks

The exact count is **400 normal rows + two failed-send rows = 402 metadata ticks**, not 402 normal rows. All 90 decisions were retained, published and consumed. Their actual State/trace acquisition times, metadata timing objects and first-consumption reflex acquisitions match exactly. Each decision's stage sum equals its acquisition-to-consumption duration (maximum accounting error zero). Thirty decisions lack a first executor clock; those values remain null, not zero. Missing publication/unconsumed lists are explicitly empty.

The requested phase was 10 seconds. Its actual origin was loop time 6.544668100. The last processed observation was at phase age **9.985679300 s**; its non-LT send returned at age **10.009863100 s**. The next acquisition hit the pre-processing `max_time` check at age **10.010020300 s**, hence metadata `seconds=10.01`. Terminal neutral release returned at age **10.015546600 s**. Thus `max_time` describes the acquisition check, not an exactly 10.000-second wall-clock release. No extra decision or processed tick is invented for that terminal acquisition.

## Stage distributions

Milliseconds; each cell is median / nearest-rank p95. Columns contain all retained decisions, 45 previously and 90 now. Percentiles are not summed.

| Stage | Prior run | Third run |
|---|---:|---:|
| Acquisition to offer | 22.647 / 29.678 | 22.703 / 28.869 |
| Offer to worker | 1.241 / 1.378 | 1.289 / 1.467 |
| Detection/tracking/tag | 4.358 / 13.030 | 11.504 / 14.285 |
| HUD + coasting snapshot | 27.908 / 33.376 | 22.941 / 26.825 |
| State assembly | 0.0048 / 0.0074 | 0.0054 / 0.0076 |
| Entire brain/consumer | 0.902 / 1.849 | 0.861 / 1.963 |
| Brain completion to publication | 0.0225 / 0.0273 | 0.0216 / 0.0265 |
| Publication to consumption | 14.173 / 24.542 | 13.226 / 25.184 |
| Acquisition to publication | 59.681 / 66.207 | 58.377 / 69.125 |
| **Acquisition to consumption** | **72.696 / 84.809** | **71.261 / 88.403** |

Observed HUD median fell 4.968 ms while detection/tag median rose 7.146 ms. Overall median fell 1.435 ms and p95 rose 3.595 ms. These are separate distribution comparisons, not additive explanations. The acquisition-to-consumption maximum was 100.894 ms on a refusal decision; model-event maximum was 92.648 ms. For model-event decisions alone, full consumer median/p95 were 0.952/2.842 ms previously and 1.025/3.245 ms now. Both thread receipts record unchanged 24 intra-op / 24 inter-op counts.

The same stage definitions apply: pre-offer includes capture/guard/reflex work; detection/tag includes wide detection/tracking when needed and the tag loop; HUD includes the coasting snapshot; consumer includes gates/history/features/model; publication wait includes reflex scheduling. These clocks do not isolate individual reader functions or CPU contention.

## Cadence and requests

There were 53 model events (35 start, 18 no-new), 35 warmups, two target-unobserved refusals and **zero invalid-history refusals**. The prior run had 29 model events, 13 warmups, one target-unobserved and two low-confidence refusals.

Of 100 slots, 90 were offered and ten correctly skipped for late acquisition, versus 45/48 previously. Late slots were 2, 11, 12, 24, 28, 42, 51, 66, 77 and 90; residuals ranged 25.0546–30.2793 ms. Nine resulting gaps ranged 191.5887–298.1163 ms. Clock-only five-observation accounting matches 37 warmup positions (35 reported warmups plus two target refusals) and 53 usable positions. No worker-queue misses occurred. Full per-gap counts remain in `report.json`; missing slots were not filled or retimed.

The 35 start proposals first encountered 19 insufficient-press-time refusals, nine unstable-target refusals, four shot-spacing refusals and three acceptances. Actual refusal reasons are preserved, without relabelling other failures as timing failures.

## Pulse ownership and recovery

Margins below use the unchanged 100 ms horizon and 33 ms full press. Negative return slack means the recorded failed return was beyond the latest start deadline; it does not identify the exact internal proof-completion instant.

| Run / request | Acquisition → consumption ms | Acceptance full-press slack ms | Send-entry slack ms | Send-return slack ms | Outcome |
|---|---:|---:|---:|---:|---|
| Prior / 45 | 65.8075 | 1.1889 | 0.8739 | -0.2929 | Failed; episode stopped |
| Third / 10 | 55.7642 | 11.2333 | 10.9446 | 9.4484 | Initial LT returned |
| Third / 54 | 65.7935 | 1.2037 | 0.8651 | -0.3420 | Expired; cancelled |
| Third / 66 | 66.3596 | 0.6374 | 0.2988 | -0.9243 | Expired; cancelled |

The two returned LT calls both belong to **one pulse, owner 10**: initial press plus its continuation (`press_edge=False`, no second acceptance). Owners 54 and 66 each have one failed initial send and zero returned LT calls. Their send calls took 1.2071 and 1.2231 ms, exceeding their entry margins. Each has one returned neutral cancellation before the originating failure row; its metadata mirror is the same event. RunLog additionally attached a filename/index to failure 54 after mirroring; all other event fields match exactly. No referenced image was opened.

After owner 54's cancellation, 36 later decisions were retained, beginning with 55; only the distinct owner 66 was later accepted. After owner 66, 24 later decisions were retained, beginning with 67. Neither expired ID was reaccepted or produced a later LT send. Both cancellations and the final release returned. This demonstrates continuation after cancellation in the recorded caller, not retry, extended authorization or guaranteed native delivery. No native cast/hit conclusion is drawn from these writes.

## Reproduction and receipts

`analyze.py` uses only the standard library and exact authorized JSON inputs. It checks supplied run hashes, preserves all inputs with matching before/after hashes, and creates `report.json`/`receipts.json` exclusively. Run with an existing interpreter in a clean copy at the same repository-relative path; existing outputs deliberately prevent overwrite. Receipts pin the five input files, inspected Loop source and analyzer. Previous reports and all production sources remain unchanged.
