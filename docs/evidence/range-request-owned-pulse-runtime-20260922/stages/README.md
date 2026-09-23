# Owned-pulse run: recorded stages and control support

The finalized run reached `max_time` with **406 normal ticks, 95 retained decisions, ten unique accepted owners, 20 returned LT calls and zero failed sends**. All ten owners have one initial LT return and one continuation return. These are executor observations, not cast/hit/KO counts; F owns native outcomes.

The interpretation is explicitly `request-start-owned-pulse-v1`: original start deadline D, immutable Controller acceptance A and nominal end E=A+33 ms. The old 67 ms full-press gate is **not applied**. Analysis reads only the two finalized run JSON files, thread/launch JSON and the previous completed-run report. No model, human data, media, Controller/Loop imports or live input was used. `receipts.json` pins all five inputs and their unchanged before/after hashes.

## Actual support and cadence

| Recorded category | Previous completed run | Owned-pulse run |
|---|---:|---:|
| Normal / failed-send rows | 400 / 2 | 406 / 0 |
| Unique decisions | 90 | 95 |
| Model-event proposals | 53 | 72 |
| Start / no-new proposals | 35 / 18 | 48 / 24 |
| Warmup / target-unobserved / low-confidence | 35 / 2 / 0 | 20 / 1 / 2 |
| Invalid history | 0 | 0 |
| Offered / late slots | 90 / 10 | 95 / 5 |
| Accepted owners / returned LT calls | 3 / 2 | 10 / 20 |

There are 74 logged probability vectors: 72 model events plus two confidence refusals. All 95 State/trace acquisition timestamps and first-consumption timing objects match their metadata exactly. All were published and consumed. Seventeen first executor timestamps are missing and remain null; stage accounting does not invent them. Each acquisition-to-consumption sum matches exactly (maximum accounting error zero).

The 48 start proposals first encountered **ten acceptances, 22 shot-spacing refusals, 11 unsupported/empty-ammo refusals and five unstable-target refusals**. Thirty-six had positive, fresh original ammo at first execution. Twelve proposed start with an observed zero snapshot; one encountered the earlier unstable-target guard, the other eleven the ammo guard. These original reasons are retained.

All **24 no-new proposals** had positive/fresh original ammo (ten with five webs, fourteen with four); 23 reached `no_new_start`, one reached `target_coasting`, and none emitted LT at first consumption. Thus the log contains actual non-start controls with available ammo, alongside starts at the same ammo counts. This is observed head/consumer/executor support, not human ground truth, policy accuracy or independent validation. No new labels are assigned.

Late slots 1, 24, 53, 75 and 85 had residuals 25.078, 36.984, 28.437, 25.311 and 32.549 ms. The five actual adjacent gaps were 178.090–210.966 ms. Clock-only history accounting gives four warmups after each gap, plus the initial target-unobserved position: 21 clock-warmup positions and 74 usable windows. No worker queue miss occurred; no slots or snapshots were filled/retimed.

## Start authorization and owned continuations

All pulse traces preserve owner A/E/D exactly; E-A is 33 ms and every A precedes D. Original resource timestamps equal the owner's decision State timestamp. Every first send uses the recorded minimum of D, original ammo expiry, E and phase/session scope; continuations use only the capped fixed E. All 20 recorded calls returned before their applicable send limit. Entry/return bracket a software call; no actuator check or physical onset timestamp is fabricated.

| Owner | Original webs | A minus anchor (ms) | E minus D (ms) | First-send applicable slack at return (ms) |
|---|---:|---:|---:|---:|
| 11 | 5 | 58.248 | -8.752 | 31.288 |
| 37 | 5 | 77.211 | 10.211 | 21.042 |
| 41 | 4 | 70.597 | 3.597 | 27.637 |
| 45 | 4 | 61.202 | -5.798 | 31.271 |
| 49 | 3 | 75.242 | 8.242 | 22.990 |
| 57 | 2 | 77.558 | 10.558 | 20.915 |
| 61 | 2 | 65.506 | -1.494 | 31.290 |
| 65 | 2 | 72.124 | 5.124 | 26.192 |
| 69 | 1 | 66.792 | -0.208 | 31.380 |
| 78 | 1 | 81.408 | 14.408 | 17.054 |

Six nominal ends lie beyond D. **Two continuations actually entered after D:**

| Owner | Entry after D | Return after D | Remaining E budget at return |
|---|---:|---:|---:|
| 57 | 3.165 ms | 5.715 ms | 4.843 ms |
| 78 | 7.177 ms | 9.549 ms | 4.859 ms |

Both were the original owner's continuation (`press_edge=False`, `accepted=False`, reason `decision_expired`). Their original ammo ages at entry were 103.165/107.177 ms; that does not authorize a new start, and neither was a new start. A/E/D were not renewed. This is direct recorded support for the adopted continuation semantics, not transferred predictions or a hypothetical replay.

Each owner has one LT release edge and one later `completed` outcome in Controller bookkeeping. The first recorded non-LT send returns 9.621–20.164 ms after nominal E; the watchdog may already have neutralized the device. Therefore these rows cannot establish actual held duration, exact release time or delivered pulse completion. The final `max_time` release also returned, with no pulse owner remaining and no recorded errors.

## Stage comparison

Milliseconds, median / nearest-rank p95 across all retained decisions; no sums of percentiles.

| Stage | Previous completed run | Owned-pulse run |
|---|---:|---:|
| Acquisition to offer | 22.703 / 28.869 | 22.527 / 28.585 |
| Offer to worker | 1.289 / 1.467 | 1.308 / 1.467 |
| Detection/tracking/tag | 11.504 / 14.285 | 11.798 / 14.755 |
| HUD/coasting | 22.941 / 26.825 | 20.012 / 24.949 |
| Entire brain/consumer | 0.861 / 1.963 | 0.910 / 2.243 |
| Publication to consumption | 13.226 / 25.184 | 13.965 / 28.598 |
| Acquisition to publication | 58.377 / 69.125 | 54.683 / 61.926 |
| **Acquisition to consumption** | **71.261 / 88.403** | **69.475 / 84.287** |

Full per-stage and per-decision numbers are in `report.json`, including assembly/publication overhead. On model-event decisions alone, the full consumer median is 0.973 ms (previously 1.025 ms), not isolated Torch. Both thread receipts record unchanged 24 intra-op / 24 inter-op. Different scenes, HUD filtering, proposal mix and execution interpretation prevent a pure causal speedup claim. The largest remaining median interval is **acquisition-to-offer, 22.527 ms**, an unsplit capture/guard/reflex interval; HUD/coasting remains the largest worker stage at 20.012 ms. No further benchmark or repair is assigned here.

The 10-second phase began at loop time 6.512356300. `max_time` was observed at phase age **10.003527700 s**; metadata rounds to 10.004. Last processed acquisition was at age 9.983223100 s, last send returned at 9.999008700 s, and terminal release returned at 10.021966200 s. Phase end 16.512356300 was earlier than the absolute session cutoff 23.648247800 and was the effective send/lease cap. Cleanup timing is not evidence of authority extension or exact physical release.

`analyze.py` is stdlib-only and exclusively creates `report.json`/`receipts.json`; it refuses overwrite. Reproduce with an existing interpreter in a clean copy at the same repository-relative path with the pinned inputs. The earlier completed-run report and all original artifacts remain unchanged.
