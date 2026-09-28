# Frozen range-to-match camera diagnostic

EXPLORATORY, idm-owner / [VUH-1353](https://linear.app/vuhlp/issue/VUH-1353), 2026-09-28. **Full03 improves moving-camera MAE and one-second accumulated error over the prior model in every source on both axes. Yaw transfer is encouraging; derived pitch remains weak, with still-row noise and overall pitch MAE worse than zero motion in three of five sources.** This is a bounded diagnostic, not a Gate 2 pass or permission to label the larger corpus.

## Per-source common-row results first

Each source contributes the same frozen first/last 15-second blocks, 1,800 rows. Every triple below is **full03 / prior / zero motion** on identical per-axis answered rows. MAE is degrees per 60 Hz interval. Moving means absolute logged truth >=0.5 degrees; “still” means below that threshold, not necessarily exactly zero. Zero is a no-motion baseline, not a zero-visual neural ablation.

### Yaw

| Match | Common rows / 1,800 | Moving rows | Moving MAE: full03 / prior / zero | Still rows | Still MAE: full03 / prior / zero | All common-row MAE: full03 / prior / zero |
|---|---:|---:|---|---:|---|---|
| -7 | 1730 | 926 | 0.8441 / 1.0110 / 2.5948 | 804 | 0.3370 / 0.3042 / 0.1395 | 0.6084 / 0.6825 / 1.4537 |
| -8 | 1775 | 610 | 0.6698 / 0.9519 / 1.9359 | 1165 | 0.1561 / 0.1608 / 0.1260 | 0.3327 / 0.4327 / 0.7480 |
| -10 | 1785 | 535 | 0.6775 / 0.7819 / 2.4644 | 1250 | 0.1369 / 0.1188 / 0.0607 | 0.2989 / 0.3175 / 0.7812 |
| -11 | 1788 | 461 | 0.4488 / 0.5404 / 1.5929 | 1327 | 0.1409 / 0.1545 / 0.1457 | 0.2203 / 0.2540 / 0.5188 |
| -12 | 1784 | 749 | 0.7088 / 0.8014 / 1.7802 | 1035 | 0.3369 / 0.2936 / 0.1363 | 0.4931 / 0.5068 / 0.8265 |

### Derived pitch

| Match | Common rows / 1,800 | Moving rows | Moving MAE: full03 / prior / zero | Still rows | Still MAE: full03 / prior / zero | All common-row MAE: full03 / prior / zero |
|---|---:|---:|---|---:|---|---|
| -7 | 1747 | 695 | 0.9849 / 1.0373 / 1.2987 | 1052 | 0.2601 / 0.2411 / 0.1421 | 0.5485 / 0.5579 / 0.6023 |
| -8 | 1768 | 238 | 0.5864 / 0.7194 / 1.0018 | 1530 | 0.1933 / 0.1756 / 0.1219 | 0.2462 / 0.2488 / 0.2403 |
| -10 | 1788 | 367 | 0.9451 / 1.0333 / 1.2855 | 1421 | 0.1631 / 0.1556 / 0.0767 | 0.3236 / 0.3358 / 0.3248 |
| -11 | 1773 | 281 | 0.6502 / 0.7017 / 0.8693 | 1492 | 0.1929 / 0.1970 / 0.1406 | 0.2654 / 0.2770 / 0.2561 |
| -12 | 1775 | 238 | 0.8043 / 0.8737 / 0.9967 | 1537 | 0.2139 / 0.2161 / 0.1289 | 0.2931 / 0.3042 / 0.2452 |

Full03 reduces moving-row MAE versus prior in all ten source/axis comparisons. Still yaw worsens in -7, -10 and -12; still pitch worsens in -7, -8 and -10. Full03 pitch is worse than zero on overall common rows in -8, -11 and -12. On -10 it barely beats zero per interval and loses to zero over one second. These are descriptive comparisons, without a significance or generalization claim.

### One-second accumulated error on common valid windows

These are means of `abs(sum(predicted degrees) - sum(logged degrees))` over existing non-overlapping 60-interval windows. A missing answer excludes the entire window identically for all three predictors. This is accumulated input error, not a reconstructed visual camera trajectory.

| Match | Yaw windows | Yaw error: full03 / prior / zero | Pitch windows | Pitch error: full03 / prior / zero |
|---|---:|---|---:|---|
| -7 | 18 | 11.2687 / 12.8701 / 51.9369 | 18 | 18.5027 / 19.2994 / 22.7272 |
| -8 | 23 | 5.8873 / 8.6908 / 23.1344 | 22 | 6.5583 / 7.2530 / 8.2369 |
| -10 | 25 | 5.4853 / 7.3125 / 27.8098 | 25 | 8.8387 / 9.0561 / 8.5277 |
| -11 | 25 | 4.8151 / 6.4880 / 24.0275 | 24 | 10.8845 / 11.5685 / 11.9410 |
| -12 | 24 | 14.5919 / 19.4190 / 44.8646 | 24 | 13.2438 / 13.7087 / 10.5230 |

Full03 improves one-second error over prior in all five sources on both axes. Against zero, pitch is worse in -10 and -12. The full JSON also retains 15-interval windows, medians and p90; an improved mean does not imply every tail improves.

### Coverage and motion imbalance

| Match | Full03 yaw / prior yaw answered | Full03 pitch / prior pitch answered | Selected moving yaw / pitch rows (before abstention) |
|---|---|---|---|
| -7 | 1769 / 1749 | 1767 / 1776 | 972 / 723 |
| -8 | 1791 / 1779 | 1771 / 1788 | 625 / 253 |
| -10 | 1799 / 1785 | 1791 / 1795 | 540 / 374 |
| -11 | 1798 / 1790 | 1778 / 1788 | 467 / 292 |
| -12 | 1793 / 1785 | 1783 / 1791 | 761 / 239 |

All counts above have denominator 1,800; zero answers all 1,800 before common masking. Selected motion proportions differ by source and block: -7 yaw is 54% moving versus 40.9% of its whole usable session; -10 first/last blocks contain 57/483 moving yaw rows. See the [evaluator’s metadata check](../../research/evaluator-checkin-20260928-1215.md). We did not reselect, rebalance or tune thresholds after that observation. Adjacent frames are correlated; 9,000 rows are not 9,000 independent trials.

## Pooled summaries, conditional on the fixed composition

| Axis | Common rows / 9,000 | Full03 MAE | Prior MAE | Zero MAE | Moving full03 / prior / zero | Still full03 / prior / zero |
|---|---:|---:|---:|---:|---|---|
| yaw_deg | 8862 | 0.3893 | 0.4371 | 0.8620 | 0.6981 / 0.8487 / 2.1243 | 0.2078 / 0.1951 / 0.1199 |
| pitch_deg | 8851 | 0.3347 | 0.3441 | 0.3330 | 0.8494 / 0.9216 / 1.1513 | 0.2016 / 0.1948 / 0.1213 |

Common-row yaw MAE falls 10.9% versus prior (0.4371 to 0.3893 degrees); pitch falls 2.7% (0.3441 to 0.3347), but zero pitch is 0.3330. Common one-second mean errors are yaw 8.2258 / 10.8054 / 33.3881 degrees over 115 windows and pitch 11.3042 / 11.8585 / 11.8817 over 113 windows. Still-row noise offsets much of the moving-pitch improvement. Raw range-dev versus match MAE is not a controlled transfer comparison because motion and scene difficulty differ.

### Existing gain and speed strata

All entries use common rows and remain full03 / prior / zero. These strata follow logged mouse speed; pitch is still derived from the logged calibration.

| Axis | Gain/speed stratum | Rows | MAE: full03 / prior / zero |
|---|---|---:|---|
| yaw_deg | calibrated | 5748 | 0.2129 / 0.2053 / 0.1527 |
| yaw_deg | extrapolated | 3114 | 0.7150 / 0.8650 / 2.1712 |
| yaw_deg | <=1x | 4836 | 0.1980 / 0.1850 / 0.0919 |
| yaw_deg | 1-4x | 2692 | 0.3746 / 0.4596 / 0.8357 |
| yaw_deg | >4x | 1334 | 1.1126 / 1.3054 / 3.7072 |
| pitch_deg | calibrated | 5720 | 0.1719 / 0.1704 / 0.1092 |
| pitch_deg | extrapolated | 3131 | 0.6323 / 0.6615 / 0.7417 |
| pitch_deg | <=1x | 4818 | 0.1501 / 0.1433 / 0.0704 |
| pitch_deg | 1-4x | 2657 | 0.3827 / 0.4293 / 0.4576 |
| pitch_deg | >4x | 1376 | 0.8887 / 0.8827 / 1.0119 |

The full03 improvement is concentrated in moving/extrapolated yaw; calibrated and <=1x yaw are worse than prior. Pitch >4x MAE is slightly worse than prior. This does not support a uniform improvement claim.

## Provenance, verification and resources

- Frozen model hashes: full03 `f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde`; prior `1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541`. Both inferred with PyTorch 2.14.0 on the same Mac MPS stack, two CPU threads, niced. Full03 was CUDA-trained; prior was MPS-trained. Device matching at inference does not erase fit-backend differences.
- Five later sources -7/-8/-10/-11/-12 retain `idm_train` roles. Current authority12 accepted receipts validated; checkpoint provenance excludes all five from both fits. No sealed, test, DayMR, replay or archive source was read. No fit, button evaluation, new labels or role mutation.
- The [preparation packet](../idm-range-to-match-preparation-20260928/report.md) fixed exact IDs before inference. Scientific implementation is `d9986c3`; the deployed a2 source snapshot preserves those bytes. Manifest `8c6e6c61f51465bfcacf3ad93cc1be478163497e32ea611d94c8b1a154d2edbf` binds checkpoints, targets, admission references, store manifests and unchanged selections.
- All 30 relocation file pairs (six per source) match source/destination hashes. Five native Darwin arm64 stores contain 112,076 frames, 18,032,580,096 frame+HUD bytes. Existing decoder checks source, target and exact PTS; each payload was rehashed. Fifteen grayscale gameplay samples and fifteen corresponding color HUD crops were inspected intact before inference. Sample inspection is a stored-pixel control, not new admission or proof of timing accuracy.
- All collected hashes match Mac bytes. On the PC, predictions were checked finite-or-unknown, exact 9,000 row identities and unchanged selection; all own/common camera metrics were recomputed exactly, with separate arithmetic checks of per-source overall/still/moving means. `verification.json` records the checks. The prior 30 synthetic diagnostic/evaluator tests remain valid; unchanged code was not retested just for collection.
- Decoder attempts before a2 failed before FFmpeg/media decode (missing Torch import then CRLF wrapper), disclosed in preparation; failed paths remain preserved. The successful serial stores and diagnostic all exited 0. Terminal receipt confirms owned processes absent. The Mac heavy slot was explicitly released to herdr-lead after collection.
- **$0 additional paid compute.** No Modal launch or cloud mutation. Prior lane estimate remains approximately $41.58 of $50, combining historical bounds/storage allocation with lead’s approximate full03 metered delta; it is not an invoice. Existing full03 input and output volumes remain retained under the lead’s latest instruction.

## Result, remaining acceptance and next action

Produced: a completed, hash-verified exploratory transfer diagnostic with per-source and common-row controls. It supports useful yaw transfer on these admitted live-match windows and identifies still-row/pitch error as a concrete weakness. It does not validate buttons, replay transfer, patch/settings transfer, Gate 2, or broad corpus labeling.

Next, idm-owner sends this reading to the lead before proposing the next expanded refit’s scope/cost. Recommend targeting the demonstrated stationary/pitch failure before treating more training data as the solution; no threshold or training change was made here. Any follow-up remains a lead decision, and successful later TRAIN diagnosis cannot replace sealed Gate 2 contracts. No new compute is queued. The lead owns VUH-1353 current-result/remaining/next-action reconciliation and readback.

Native run: `/Users/james/dev/idm-data/range-to-match-20260928-a2/`. Canonical report SHA256 `8d9a460a9dc4cb701d785ca19e140c8a378836469500af4aefe6ed831cd30a32`; predictions `72cf61a0df2d015bf520b3fff91f76d37f86a40b69b5cbb46f34d83e4dc5f86c`; collected archive `9bf16d5145ff519e4407b3c33dfb75ea54545cf7684eb466a491602e9c72def0`.
