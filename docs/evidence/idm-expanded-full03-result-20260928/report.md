# Expanded IDM full03: completed, improved range-dev diagnostics

EXPLORATORY, idm-owner / VUH-1353, 2026-09-28. The unchanged three-epoch fit completed on the eight TRAIN ranges plus current -4a1/-5a1/-6: 181.89 admitted minutes, 653,842 training examples, 122,598 optimizer steps. All seven stages and three complete epoch checkpoints were independently collected from output volume `vo-dpykVEKfIL22lf5pWsMeQA`, hash-verified on the Mac, transferred, and verified again on the PC. No retry or new inference was launched for this report.

Camera error and TRAIN-calibrated press diagnostics improved on the existing range-dev cohort. Press precision remains inadequate for reliable automatic labels, and camera MAE remains worse than logged-motion persistence. This is not Gate 2, match/replay transfer validation, or permission to label the larger corpus.

## Camera comparison

Pinned baseline `bce156fcf7cd941a3ee77d16a7eac93e709e3f04d35c32a40ad90e773bdf6e2a`, checkpoint `1b9bcc6a`. Both reports cover the same two development sources and 49,080 eligible rows. Values below are degrees per target interval.

| Axis | Baseline MAE | Full03 MAE | Baseline answered | Full03 answered | Zero motion MAE | Persistence MAE |
|---|---:|---:|---:|---:|---:|---:|
| Yaw | 0.2835 | 0.2488 | 48,959 / 49,080 | 49,018 / 49,080 | 0.8691 | 0.2206 |
| Derived pitch | 0.2554 | 0.2359 | 48,818 / 49,080 | 48,740 / 49,080 | 0.3577 | 0.0919 |

Reported MAE falls 12.2% for yaw and 7.6% for pitch. **The answered subsets differ**, so this is not a matched-intersection error estimate. Coverage is 99.874% yaw and 99.307% pitch. Zero motion covers all rows; persistence covers 49,077. The camera baseline fit/evaluation was MPS and full03 is CUDA. Additional training data and backend changed together; no causal attribution to added matches alone is justified. Pitch truth remains derived from the accepted calibration.

Both development sources improve in mean error: 171533 yaw/pitch 0.1732/0.1412 → 0.1569/0.1360; 205528 0.3008/0.2804 → 0.2615/0.2573. Moving-row errors improve (yaw 0.5683 → 0.4653, pitch 0.6338 → 0.5187), while still-row errors worsen (yaw 0.1155 → 0.1211, pitch 0.1362 → 0.1466). The zero camera control predicts no motion; it is distinct from the press zero-visual ablation.

## Press comparison on identical ordered rows

Baseline report `dd09f3b33b2a27c458fca580bec8da7753b38584d73950aa35a4fe14efed6a98`. The baseline saved row list and both new real/zero lists are exactly equal after JSON parsing: 9,244 rows from 171533 and 39,836 from 205528. Their byte hashes differ only because serialization differs. All press conditions answer 49,080 / 49,080 rows, with no probability abstention band. Scoring remains one-to-one ±2 intervals with 20 deterministic Bernoulli chance draws at each session's predicted rate.

TRAIN-rate quantiles are fitted on TRAIN only and frozen before dev inference. The method is unchanged; TRAIN composition and thresholds changed. Both press evaluations use CUDA, although the baseline weights were trained on MPS.

| Action | Baseline precision / recall | Full03 precision / recall | Baseline F1 | Full03 F1 | Full03 TP / FP / FN |
|---|---:|---:|---:|---:|---:|
| Amazing Combo | 42.19% / 56.25% | 49.11% / 57.29% | 0.4821 | 0.5288 | 55 / 57 / 41 |
| Jump | 35.74% / 41.39% | 42.05% / 49.22% | 0.3836 | 0.4535 | 283 / 390 / 292 |
| Web Cluster | 42.67% / 43.23% | 49.20% / 48.18% | 0.4295 | 0.4868 | 185 / 191 / 199 |

All three calibrated precision/recall pairs improve, but roughly half the predicted presses are false positives. New chance-mean F1 is 0.0104 / 0.0616 / 0.0377 respectively. Amazing Combo remains non-deciding under the existing per-session support rule: 171533 has only 14 positive onsets. New thresholds are 0.924330 / 0.942976 / 0.958613. Predicted-row shares are 0.228% / 1.371% / 0.766%; these are distinct from the 100% answered-row coverage.

At fixed 0.5, the original precision problem persists:

| Action | Baseline precision / recall | Full03 precision / recall | Baseline F1 → full03 F1 |
|---|---:|---:|---:|
| Amazing Combo | 15.96% / 86.46% | 25.39% / 84.38% | 0.2695 → 0.3904 |
| Jump | 8.22% / 94.26% | 14.05% / 91.30% | 0.1512 → 0.2435 |
| Web Cluster | 27.24% / 73.70% | 25.11% / 77.34% | 0.3978 → 0.3791 |

Zeroing both motion and HUD inputs yields constant probabilities and **zero predicted onsets** for all three actions under both threshold methods, for both baseline and full03. Precision is undefined, recall/F1 are zero. Real visuals therefore carry useful signal on this dev cohort; this is not sufficient evidence of match or replay transfer.

## Checkpoints, execution and verification

Final inference checkpoint SHA256: `f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde` (1,710,123 bytes). Three complete training-state checkpoints are retained:

| Epoch | Steps | Checkpoint SHA256 |
|---|---:|---|
| 1 | 40,866 | b34aaef574d2d68afe17f19e33596c97dda79141e0f1b87b61fd6adfcc5a5e87 |
| 2 | 81,732 | 851e401a626085710b066021d464ed8ef71d2f248dcc5522eaa30192bd3873bb |
| 3 | 122,598 | f86c3bbaa3bbc258f3cf1a84c61a013fd6d64ae5725866ec1b6ec21f09e206bc |

CPU inspection confirmed finite model tensors, optimizer state, epoch/cursor/step metadata, and exact tensor equality between epoch 3 and the final inference checkpoint. Epoch checkpoints contain the RNG/data-order recovery state. No real interruption/resume occurred in this successful fit; the uninterrupted/resumed equivalence claim remains the earlier offline synthetic test, not a new live recovery demonstration.

Fit time was 21,430.924 seconds (5.95 hours). Epoch cumulative times were 7,103.229 / 14,300.380 / 21,427.744 seconds. App `ap-S6lLYCw0bpGcPfFhcMyLgy`, call `fc-01M3KG8EMEDPHPJMGVTGN5KZV1`, started 07:56:46.807 UTC and stopped at **15:30:57 UTC**, roughly 7 h 34 min elapsed, within the 36,310-second native timeout. Terminal snapshots show stopped, tasks 0, containers empty. Two teardown queries reported already-stopped errors; they do not invalidate the completed call or subsequent zero-container proof. No claim of zero host stop calls is made for this full run.

The collector authenticated the exact volume and scientific identities without requiring a host terminal result. It accepted 10 completion receipts and verified all 15 referenced artifacts. Every transferred file passed the retained 32-file hash inventory. Probability arrays are finite float32 with the expected shapes; ordered dev rows match, roles are disjoint, and pooled precision/recall recompute from counts. `summarize-full03.py` reproduces these local checks and `comparison.json`; no raw footage or sealed data is read. The full metadata report is `artifacts/report/report.json` (SHA256 `9ea9ce74c946a857e17a03d7019c4b7411fac243a77a2dc0afcf2aff1ee7e030`).

## Accounting, retention and next action

**≈ $21.9, lead's metered-delta read, not an invoice.** Lead ledger `210a67b`: at 10:34 CDT month metered $101.89, billed $70.40; since the prior $78.33 check, ephemeral apps increased $22.27, including the shakedown's lagged remainder. Volumes increased $1.29 across retained input and old outputs; that is not attributed wholly to full03. Prior lane allocation estimate including $1.65 storage was $19.676993; adding full03 gives approximately **$41.58 against the $50 lane allocation**, mixing historical bounds and a new estimate rather than claiming an exact cumulative bill.

The lead's latest correction supersedes input cleanup: **retain** `vo-PnBxKAp9G4Y8nNwfBOgrdU` / `rivals-idm-expanded-20260928-01-inputs` until the next refit's inputs are staged or James decides otherwise. Keep full03 output volume `vo-dpykVEKfIL22lf5pWsMeQA`. No deletion or relaunch was performed.

All collected payloads, arrays, row IDs and checkpoints remain under `data/idm/cloud-20260927/full03-result-collected/` on the PC and `/Users/james/dev/idm-data/expanded-refit-d4f05e0/full03-result-collected/` on the Mac. The archive SHA256 is `785d5ddc7d68366c800eeba6b06c62262d51b021cfa9a1e3576cbba1d4239095`. Git retains metadata and pins; large payloads remain in those verified stores and the output volume.

Remaining acceptance: transfer/Gate 2 evidence and sufficiently reliable press labels remain unproven. Next owner action (idm-owner): prepare the separately authorized expansion with -7/-8/-10/-11/-12 after current-authority and native-store checks, reusing retained inputs; report its scope and cost before any paid launch. The lead owns VUH-1353 reconciliation/readback and spending reconciliation. No current result authorizes larger-corpus labeling.
