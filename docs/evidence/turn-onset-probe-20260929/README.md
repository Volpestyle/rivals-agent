# Causal turn-onset probe — 2026-09-29

**EXPLORATORY verdict: NO ADVANCE for this new classifier.** Causal visual input contains useful direction/onset information relative to constant controls and shuffled images, but the changed objective does not improve on the existing no-history checkpoint. Its onset recall is only 20.1%, its probabilities generalize poorly, and 37.4% of quiet/still windows receive a false onset. This is not evidence that visual turn intent is unlearnable.

One eight-epoch visual fit and one matched nonvisual fit completed; no sweep, second fit, paid function, new admission, sealed access or live input occurred. The lead owns the next decision on VUH-1346. Inspect intent ambiguity or target-conditioned supervision before authorizing another fit, as the [experiment spec](../../research/policy-next-bet-turn-onsets-20260929.md) directs.

## Support, before scores

Counts were written before any development score was computed. They are overlapping prediction opportunities, not independent turn events. A cluster is a consecutive sequence of positive onset windows.

| Cohort/session | Eligible windows | Onset windows | Onset clusters | Quiet/still windows |
|---|---:|---:|---:|---:|
| Eight TRAIN sessions | 300,071 | 20,555 | 5,178 | 13,726 |
| Frozen dev 171533 | 4,617 | 552 | 116 | 767 |
| Frozen dev 205528 | 19,913 | 1,442 | 357 | 1,455 |
| **Dev pooled** | **24,530** | **1,994** | **473** | **2,222** |

Dev has 19,612 moving-yaw targets: 9,447 left and 10,165 right; onset targets split 1,068 left / 926 right. “Moving” refers to native human yaw labels, not annotated enemy movement. Two reused sessions cannot establish robustness on new sessions. Full session identities, TRAIN support and per-session calibration are in [report.json](report.json).

## Target and fixed comparison

At anchor time *t*, sum signed native mouse yaw over seven complete 33,333,333 ns bins: **0.233333331 s**, the full-bin approximation below 0.25 s. No fractional counts or future pixels are invented. The preceding seven bins define quiet when their **absolute travel**, not signed sum, is at most the threshold. Onset means quiet history followed by a nonzero future direction. Unknown labels, gaps, discontinuous timestamps, cuts and run boundaries are excluded.

The single noise/turn threshold is **0.4630332°**, the TRAIN 10th percentile of nonzero absolute integrated yaw, fixed before dev scores. It is a heuristic deadband, not a measured sensor-noise estimate. Left/right use strict excursions beyond ±threshold; equality is no meaningful turn.

The new model consumes eight causal frames of the existing frozen NitroGen vision features **through the seed-1 checkpoint's frozen global/crop projections** (512 dimensions). A 64-unit GRU predicts direction (three classes) and onset (binary), using unweighted CE+BCE. Both fits use seed 29, AdamW 3e-4, weight decay 1e-4, batch 512, eight epochs, final epoch only. The matched nonvisual arm has the same model, initialization, schedule and objective, with every visual input zero. Neither receives true action history, session identity or timestamps as features.

The checkpoint comparator was declared before scores: hold its current 31-class yaw distribution constant for seven bins and aggregate the resulting degrees into left/none/right. Its onset probability is motion probability gated by its own preceding seven median predictions being quiet. It never sums predictions from future images or uses human quiet labels as input. Seed 1 was selected in advance; seeds were not searched.

Each arm's onset cutoff maximizes TRAIN F1 over 101 fixed cutoffs, ties favoring the larger cutoff: visual 0.21, checkpoint 0.03, nonvisual/prior 0.06. Thus the constant controls predict onset everywhere at their selected cutoffs; their 100% still false-start rate is a consequence of that rule. No dev cutoff selection occurred. The prior uses TRAIN empirical class/onset rates. Shuffling permutes complete visual contexts within each dev session, retaining the visual cutoff; it is an inference sensitivity check, not a causal policy baseline.

## Results

| Arm | Onset precision | Recall | F1 | Moving direction accuracy | False starts / still |
|---|---:|---:|---:|---:|---:|
| **Visual probe** | **15.88%** | **20.06%** | **0.17727** | **61.97%** | **37.44%** |
| Matched nonvisual | 8.13% | 100% | 0.15035 | 48.17% | 100% |
| TRAIN prior | 8.13% | 100% | 0.15035 | 51.83% | 100% |
| Held no-history checkpoint | 14.18% | 44.23% | 0.21476 | 63.62% | 67.60% |
| Shuffled visual sensitivity | 9.05% | 11.43% | 0.10104 | 49.84% | 10.71% |

The visual probe has 400 true positives, 2,119 false positives and 1,594 false negatives; 832 false positives fall in the 2,222 quiet/still windows. Shuffling loses onset and direction discrimination, but also reduces still false starts from 832 to 238 at the same total prediction count (2,519). Real visual context therefore concentrates predictions in quiet periods without reliably separating their actual onsets from continued stillness. Do not conceal this with the aggregate F1 gain over the prior.

| Arm | Onset Brier ↓ | Onset ECE, 10 bins ↓ | Moving direction NLL ↓ | Three-class NLL ↓ |
|---|---:|---:|---:|---:|
| Visual | 0.07737 | 0.05209 | 0.87457 | 1.19023 |
| Nonvisual | 0.07495 | 0.01636 | 0.69327 | 1.06469 |
| TRAIN prior | 0.07484 | 0.01279 | 0.69261 | 1.06438 |
| Checkpoint | 0.12434 | 0.13494 | 0.70308 | 1.06962 |
| Shuffled | 0.08416 | 0.07615 | 1.18965 | 1.63251 |

The direction accuracy gain over the prior does not imply better probabilities: visual direction NLL, three-class NLL and onset Brier all trail the prior. TRAIN visual loss fell from 1.14782 to 0.78237 while the nonvisual loss settled at 1.26090; no epoch was selected using dev.

| Session | Arm | Onset P / R | Onset F1 | Direction | Still false starts |
|---|---|---:|---:|---:|---:|
| 171533 | Visual | 17.76% / 31.52% | 0.22715 | 59.69% | 40.81% |
| 171533 | Nonvisual | 11.96% / 100% | 0.21358 | 47.70% | 100% |
| 171533 | Prior | 11.96% / 100% | 0.21358 | 52.30% | 100% |
| 171533 | Checkpoint | 16.58% / 60.33% | 0.26005 | 64.04% | 76.92% |
| 171533 | Shuffled | 12.04% / 21.38% | 0.15405 | 48.42% | 17.86% |
| 205528 | Visual | 14.68% / 15.67% | 0.15163 | 62.41% | 35.67% |
| 205528 | Nonvisual | 7.24% / 100% | 0.13505 | 48.26% | 100% |
| 205528 | Prior | 7.24% / 100% | 0.13505 | 51.74% | 100% |
| 205528 | Checkpoint | 13.04% / 38.07% | 0.19423 | 63.54% | 62.68% |
| 205528 | Shuffled | 7.15% / 7.63% | 0.07380 | 50.12% | 6.94% |

## Original yaw metric retained

The [original confirmation](../nitrogen-nohistory-confirm-20260927/confirmation-report.md) remains **1.771697°/step yaw MAE** across three candidate seeds versus zero **1.735184°/step**; seed 1 was 1.772979. This probe does not replace that metric with a sparse-event score.

On all 24,556 eligible dev rows, the current seed-1 **raw median** inference gives 1.774194°/step versus zero 1.735184. Per session: 171533 gives 1.289445 versus 1.208037 (4,630 rows); 205528 gives 1.886830 versus 1.857672 (19,926 rows). This recomputation uses CUDA-created features with MPS heads and raw median degrees; the historical confirmation used MPS-created features and the executed decoder. It is not claimed to reproduce its exact value. The new classifier has no continuous per-step yaw output, so it has no directly comparable yaw MAE.

## Provenance and verification

- Probe/test code commit: **`ca1444c4ecea7abe5145719f3d127035942eb017`**. Probe SHA-256: `2d7ffe374524fd17edc7ff8af6387b89e3f0f81ca7a07ff72313d93946a45c97`.
- Fixed admitted dataset: `71e344f4f17d9e537c87c154b30f6aae12c14cc601b59d668299ac799715660e`; checkpoint: `9f3dfd1a9a2edb1c280f0a2a86a18cb34cfe2a7ce172931823ababca41eebf24`. The current denylist was loaded before the unchanged fixed-roster loader; payload hashes, roles and exported TRAIN statistics passed.
- Download only, profile `rivals`, workspace `volpestyle`, existing volume `rivals-yaw-extract-20260927-02-outputs`: 21,302,066,016 feature bytes, plus label/receipt files, with 214,217,478,144 disk bytes free before transfer. All selected artifacts matched their prior hashes. **Paid compute $0**; no Modal function or AWS call.
- Mac MPS, nice 15, two CPU threads, Python 3.11.15, torch 2.14.0, NumPy 2.4.6. Runtime came from a Git archive, separate venv, archive SHA `a79206c97ea8e5799615669901247c9ce098b1e8834d6fa4e1e184ffe2d0c223`. Terminal exit 0, 86.0 s including loading; process absence checked afterward. Mac slot released; no follow-up queued.
- A first download wrapper failed on an old checkout import before any download. Its corrected wrapper used an existing pinned code snapshot. The first experiment launch, Python 3.12, failed **before fitting** because four exported drift sums differed by about 1e-15. Python 3.11 matched the source export exactly; no loader check or payload was weakened. This Python summation compatibility matters when reusing these exact-statistic exports. Both failures are retained.
- Eleven synthetic tests passed on Windows and Mac, including causal context, future-image refusal, current-prediction-only extrapolation, cuts, unknown labels, quiet cancellation, metrics and backpropagation. Ruff passed; a real MPS gradient was verified. These checks establish implementation behavior, not gameplay quality.
- [results.zip](results.zip), SHA `3b9a3ca52daffb35a1ae6d46a3a8b774ddb0294f188960bb4b78c782969356bd`, contains raw predictions, support, fixed contract, logs, success/failure receipts and a per-file hash manifest. Trained weights remain under `/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929/attempt2/result/`; their hashes and exact package inventory are in the archive's `collection.json`. Nothing here authorizes live use or a confirm claim.
