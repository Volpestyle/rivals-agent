# Mac match-expanded IDM: less still-row noise, worse moving-row accuracy

EXPLORATORY / idm-owner / VUH-1353 / 2026-09-28. **Complete**, all fit/press/evaluate exits 0. The fresh three-epoch fit used eight TRAIN ranges plus current -4a1/-5a1/-6/-7/-8/-10: 200.976 counted minutes, 722,074 complete contexts, 135,390 updates. Whole -11/-12 families were excluded from fit and calibration. Their 37,980 unread rows were frozen before launch by 59d2404/17b0f96, unchanged from 5a04fa8.

The new model improves still-row and overall camera MAE against full03 on both transfer sources, but **moving MAE worsens on both axes in both sources**. One-second pitch error also worsens slightly in both. This is a trade-off, not a demonstrated replacement for full03. Press precision remains insufficient for automatic labels. No Gate 2, replay-transfer or larger-corpus-labeling claim.

## Held-out transfer: per-source common-row slices first

All models inferred on the same Mac MPS stack. `New Mac` is 1ddf84b5, `Full03` is f681da9f (immediate baseline), `Older prior` is 1b9bcc6a. `Zero motion` predicts 0 degrees and is distinct from zeroing the press model's pixels. Per-interval MAE is degrees; moving means |logged truth| >= 0.5 deg, still means below 0.5 deg (not necessarily exactly stationary). One-second error is absolute error of the sum over 60 contiguous intervals, not mean per-frame error. Pitch truth remains derived from the accepted calibration.

The table uses the per-axis intersection answered by all three models; zero uses those same rows/windows. No re-selection or tuning followed predictions.

| Source | Axis | Model | Still MAE | Moving MAE | All MAE | 1s sum error |
|---|---|---|---:|---:|---:|---:|
| -11 | yaw | New Mac | 0.1522 | 0.6231 | 0.3591 | 9.6685 |
| -11 | yaw | Full03 | 0.1808 | 0.6024 | 0.3661 | 9.7215 |
| -11 | yaw | Older prior | 0.1732 | 0.7465 | 0.4252 | 10.9504 |
| -11 | yaw | Zero motion | 0.1350 | 2.0962 | 0.9969 | 38.6307 |
| -11 | pitch | New Mac | 0.1597 | 0.7993 | 0.3027 | 7.8499 |
| -11 | pitch | Full03 | 0.1854 | 0.7673 | 0.3154 | 7.7837 |
| -11 | pitch | Older prior | 0.1972 | 0.9013 | 0.3545 | 9.3560 |
| -11 | pitch | Zero motion | 0.1362 | 1.1768 | 0.3688 | 10.2277 |
| -12 | yaw | New Mac | 0.1486 | 0.6429 | 0.3473 | 10.0126 |
| -12 | yaw | Full03 | 0.1752 | 0.6252 | 0.3561 | 9.9590 |
| -12 | yaw | Older prior | 0.1729 | 0.7747 | 0.4148 | 12.1168 |
| -12 | yaw | Zero motion | 0.1148 | 2.1448 | 0.9309 | 36.5733 |
| -12 | pitch | New Mac | 0.1482 | 0.7779 | 0.2754 | 7.4016 |
| -12 | pitch | Full03 | 0.1638 | 0.7429 | 0.2808 | 7.3059 |
| -12 | pitch | Older prior | 0.1649 | 0.8304 | 0.2993 | 7.7594 |
| -12 | pitch | Zero motion | 0.1099 | 1.1300 | 0.3160 | 9.1273 |

| Source | Axis | Selected | Common answered | Still / moving | Common 1s windows |
|---|---|---:|---:|---:|---:|
| -11 | yaw | 15,960 | 15,655 | 8,775 / 6,880 | 192 |
| -11 | pitch | 15,960 | 15,710 | 12,199 / 3,511 | 196 |
| -12 | yaw | 22,020 | 21,738 | 12,999 / 8,739 | 292 |
| -12 | pitch | 22,020 | 21,505 | 17,162 / 4,343 | 267 |

Against full03, still-yaw MAE falls 15.8% in -11 and 15.2% in -12; still-pitch falls 13.9% and 9.5%. Moving-yaw MAE rises 3.4% and 2.8%; moving-pitch rises 4.2% and 4.7%. One-second pitch error rises 0.9% and 1.3%; one-second yaw is nearly unchanged (-0.5%/+0.5%). Still-pitch error remains worse than zero in both sources (0.1597 vs 0.1362; 0.1482 vs 0.1099).

Both new **and full03** beat zero on overall and one-second pitch on these unread windows. Therefore the contrast with the earlier 9,000-row diagnostic cannot be credited solely to this refit: those were different windows, and the current full03 control also benefits from their different motion composition. The whole sessions are out of all three fits, but previously read blocks informed the question; this is an exploratory transfer check, not an untouched sealed confirm set.

Own answered coverage (different subsets, not the common-row comparison):

| Source | Axis | New answered | Full03 answered | Older prior answered | Zero answered |
|---|---|---:|---:|---:|---:|
| -11 | yaw | 15,860 | 15,873 | 15,743 | 15,960 |
| -11 | pitch | 15,876 | 15,830 | 15,860 | 15,960 |
| -12 | yaw | 21,939 | 21,911 | 21,822 | 22,020 |
| -12 | pitch | 21,885 | 21,688 | 21,811 | 22,020 |

Own-coverage pitch MAE for new/full03 is 0.3070/0.3202 in -11 and 0.2788/0.2833 in -12. The apparent one-second change can reverse with different answered windows: use the common-window table for matched claims. Full own/common statistics and counts are retained in `transfer-report.json`.

Only after those per-source slices, pooled common-row interval MAE:

| Axis | New | Full03 | Older prior | Zero motion |
|---|---:|---:|---:|---:|
| yaw | 0.3523 | 0.3603 | 0.4191 | 0.9585 |
| pitch | 0.2869 | 0.2954 | 0.3226 | 0.3383 |

Pooled new/full03 still error is 0.1500/0.1774 yaw and 0.1530/0.1728 pitch. Moving error is 0.6342/0.6151 yaw and 0.7875/0.7538 pitch. One-second error is 9.8761/9.8648 yaw and 7.5914/7.5082 pitch. Pooling weights the two sources differently (15,960 vs 22,020 selected rows); it does not replace per-source evidence.

## Frozen range dev and press control

Same 49,080 context-complete development rows, with camera intersection computed anew for all three models:

| Range source | Axis | New MAE | Full03 MAE | Older prior MAE | New / full03 moving MAE | New / full03 1s error |
|---|---|---:|---:|---:|---:|---:|
| 171533 | yaw | 0.1615 | 0.1543 | 0.1689 | 0.4070 / 0.3721 | 4.5946 / 3.8231 |
| 171533 | pitch | 0.1385 | 0.1356 | 0.1405 | 0.5036 / 0.4594 | 4.0052 / 3.5633 |
| 205528 | yaw | 0.2664 | 0.2575 | 0.2978 | 0.4855 / 0.4627 | 7.2494 / 6.4973 |
| 205528 | pitch | 0.2574 | 0.2553 | 0.2769 | 0.5587 / 0.5182 | 6.9132 / 6.8086 |

Range-dev overall camera MAE, moving error and one-second error worsen versus full03 in both sources/both axes, while still-row errors improve. The new fit changed both training composition and backend relative to CUDA-trained full03; even with the same initialization recipe/seed and same MPS inference here, a single run is not a clean causal estimate of extra-match benefit. These recomputed pooled/common camera metrics must not be substituted for the differently pooled historical report without their coverage definition.

Press TRAIN-rate calibration used only the 14 authorized TRAIN sources. Thresholds were fixed before dev inference: Amazing Combo 0.9247166514, Jump 0.9428152442, Web Cluster 0.9717117548. New and full03 score exactly the same ordered 49,080 dev rows, one-to-one +/-2 intervals and 20 deterministic Bernoulli chance draws at each session's predicted rate. All three heads answer every known row here; these un-abstained diagnostics are distinct from runtime confidence-filtered label coverage. New press evaluation is MPS; historical full03 press evaluation is CUDA.

| Action | New precision / recall | Full03 precision / recall | New / full03 F1 | New TP / FP / FN | New chance F1 |
|---|---:|---:|---:|---:|---:|
| amazing_combo | 52.58% / 53.12% | 49.11% / 57.29% | 0.5285 / 0.5288 | 51 / 46 / 45 | 0.0091 |
| jump | 39.50% / 49.04% | 42.05% / 49.22% | 0.4375 / 0.4535 | 282 / 432 / 293 | 0.0633 |
| web_cluster | 45.45% / 44.27% | 49.20% / 48.18% | 0.4485 / 0.4868 | 170 / 204 / 214 | 0.0378 |

Amazing Combo exchanges recall for precision with essentially unchanged F1; Jump and Web Cluster decline. About 47% / 61% / 55% of predicted presses respectively are false positives. Amazing Combo remains non-deciding under the existing support rule because 171533 has 14 positives. No match-button evaluation or label authorization follows from this range-dev result.

At fixed 0.5, precision remains low:

| Action | New precision / recall | Full03 precision / recall |
|---|---:|---:|
| amazing_combo | 16.63% / 84.38% | 25.39% / 84.38% |
| jump | 15.45% / 90.09% | 14.05% / 91.30% |
| web_cluster | 24.77% / 76.56% | 25.11% / 77.34% |

Zeroing both motion and HUD tensors produces zero predicted onsets for every action under both threshold methods; precision is undefined, recall/F1 are 0. Real visuals carry useful signal, but this alone does not make button labels reliable.

## Execution, integrity and cost

Launch 18:06:02 UTC; final evaluate status done 20:59:19 UTC, about **2 h 53 m** elapsed, within the six-hour planning envelope. Fit wall 8145.23 s, press 1819.08 s, camera 433.46 s. Actual trainer 129.849 min; all 3 completed epoch states are retained and independently validated. No interruption/resume or retry occurred in this run; exact interrupted/uninterrupted MPS equivalence remains the pre-launch synthetic test.

Peak process RSS: fit 88.63 GiB, press 89.36 GiB, camera 10.67 GiB, including mapped stores. Peak memory footprint from native time: fit 5.64 GiB, press 5.56 GiB, camera 5.84 GiB. Per-process time reports 0 swaps; system swap was already present and declined at epoch checks, with no new swap-outs between those snapshots. RSS is not private footprint. All phases exited 0; final process inventory is empty.

**Additional cloud compute: $0.** Existing lane allocation/paid accounting is unchanged. Retained cloud input and output volumes remain untouched per lead instruction; no deletion, paid launch, new recording, decode or admission occurred.

Final checkpoint SHA256: `1ddf84b5486973ef65387d65d9304daf507d58deb0ab026117c618739bab8efb`. Complete training checkpoints: epoch 1 `21123360`, epoch 2 `1fc6ae2f`, epoch 3 `769d5d00` (full pins in the separate epoch packets and collection receipt). Final model tensors/config/provenance exactly match complete epoch 3. Neither held-out family appears in fit provenance or TRAIN threshold sources.

All 32 collected files passed native and PC size/hash checks. Saved predictions reproduce every own/common per-source/pooled camera metric; saved TRAIN probabilities reproduce the thresholds using checkpoint-pinned positive counts; saved dev arrays reproduce press metrics/chance draws. Exact ordered dev IDs match full03, and transfer IDs/selection metadata exactly match the pre-prediction complement. The verifier reads pinned target metadata and saved outputs only, no images or new predictions. Numeric recomputation tolerance 1e-12; actual maximum is in `verification.json`.

Archive SHA256: `07c33b766943fc6f543ad6c421b9d146426e567bb3367d9654d2f92b26e20b88`. Payloads, probability arrays, predictions and checkpoints remain in `data/idm/match-refit-mac-20260928/collected/` and native `/Users/james/dev/idm-data/match-refit-mac-20260928/result/`. Git retains reports, receipts and exact artifact pins. Source 59d2404 with cache-only amendment 17b0f96; manifest 73d486da. Earlier pre-launch missing-module/cache refusals are disclosed in those packets; neither started a fit.

## Remaining acceptance and next owner action

This experiment is complete. Reliable press labels, still/moving camera trade-offs, replay/live transfer and sealed Gate 2 acceptance remain unresolved. Recommend retaining full03 as the comparison baseline and treating the new checkpoint as a still-versus-moving trade-off rather than promoting it automatically. Lead decides the next bounded experiment or transfer/Gate 2 step; IDM owns its proposal and implementation after authorization. No further fit or pilot is started. These 37,980 rows are now read; do not choose thresholds or another model on them and call the same readout fresh validation.

Mac slot explicitly released to herdr-lead after collection/hash checks and metric verification. Result/current limitations/next action handed to the lead for VUH-1353 update/readback; direct workspace Linear writes remain unavailable to this lane. No result is claimed published until the lead confirms readback.
