# TRAIN-only pitch deadband: negative calibration result

EXPLORATORY, idm-owner / [VUH-1353](https://linear.app/vuhlp/issue/VUH-1353), 2026-09-28. **No nonzero threshold qualified. Identity (`tau=0`) was retained and the experiment stopped at TRAIN calibration, exactly as accepted.** Neither range-dev nor unread-match inference ran. Full03 weights, yaw and abstention are unchanged; no correction is promoted.

## Why it stopped

The eight TRAIN ranges contributed 3,600 metadata-selected rows each (28,800 total). Scores below weight sources equally, not by length or answered-row count. MAEs are pitch degrees per 60 Hz interval; one-second metrics are absolute accumulated input error. All candidate arithmetic uses the same frozen full03 predictions.

| Threshold | Macro still MAE | Still reduction | Macro moving MAE | Macro overall MAE | Worst source moving increase | Worst source one-second increase | First failed guard |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.000 | 0.163007 | 0.00% | 0.441524 | 0.241366 | 0.00% | 0.00% | identity control |
| 0.025 | 0.161672 | 0.82% | 0.441517 | 0.240396 | 0.01% | 0.31% | still reduction below five percent |
| 0.050 | 0.160710 | 1.41% | 0.441554 | 0.239718 | 0.04% | 0.50% | still reduction below five percent |
| 0.075 | 0.159950 | 1.88% | 0.441663 | 0.239209 | 0.09% | 0.66% | still reduction below five percent |
| 0.100 | 0.159025 | 2.44% | 0.441949 | 0.238631 | 0.17% | 1.71% | still reduction below five percent |
| 0.150 | 0.157611 | 3.31% | 0.443537 | 0.238070 | 0.61% | 1.63% | still reduction below five percent |
| 0.200 | 0.156902 | 3.74% | 0.446600 | 0.238481 | 1.72% | 3.68% | one-second guard: 051828 |
| 0.300 | 0.160259 | 1.69% | 0.457880 | 0.244169 | 4.43% | 10.80% | moving guard: 051828 |
| 0.400 | 0.163858 | -0.52% | 0.477898 | 0.252257 | 9.67% | 29.04% | moving guard: 051828 |
| 0.500 | 0.165783 | -1.70% | 0.517623 | 0.264544 | 20.64% | 41.73% | moving guard: 051828 |

Thresholds 0.025-0.15 degrees do not achieve the fixed 5% macro still-MAE reduction. The largest observed reduction is only about 3.75%, at 0.20 degrees; that threshold also violates the 2% per-source one-second guard (051828). Thresholds 0.30-0.50 violate moving-error guards, and their overall MAE exceeds identity. All eight sources have the required moving and complete-window support, so this is a negative result rather than an insufficient-support result. The complete per-source scores and exact first-failure reasons are retained in `result/calibration.json`.

This does not establish that every magnitude correction is useless. It rejects the ten accepted candidates under the frozen criteria. Small candidates modestly improve aggregate error, but lowering the 5% requirement after seeing them would be a different experiment. No threshold grid, weighting, guard, model or source selection was changed after the readout.

## Isolation and verification

- Lead accepted proposal `a065c99`. The complete calibration, dev and unread-match manifests and tested implementation were committed in `5a04fa8` **before inference**. Manifest SHA256: `81304ead59639e05a46b05f6508a9caf2916226dca3c90415e723915cea3571d`; module SHA256: `dd2bced2dfce9a58a3b7eb40dbc40243cb218ccdaf05321466a8357164413e4c`. Forty synthetic tests passed.
- The only inference was frozen full03 on the eight TRAIN ranges. The range-dev 49,080 rows and unread match 98,880 rows were frozen from metadata but never predicted. The old 9,000 match rows did not choose the threshold. Their exclusion, context overlap, one-second embargo and store-inspection-frame exclusions remain recorded in the committed manifest. No sealed, test, archive or DayMR source was accessed.
- All candidate outputs preserve yaw, other prediction fields and unknown masks. Verification rechecked this for every candidate and row. Original model uncertainties are retained for provenance, not recalibrated for deadband-transformed predictions. `verification.json` records per-source suppression counts; raw TRAIN predictions retain original values for every potentially suppressed row.
- Owner recomputation on the PC used only the pinned TRAIN tables and archived predictions: exact 28,800 row identities, all ten candidates, all counts, choice/guard outcomes and separate row-MAE arithmetic passed. Python/platform summation differed by at most `1.7763568394002505e-15` in means; verification uses a stated `1e-12` absolute tolerance, not a false bit-identical claim. No new inference was performed during verification.
- The full03 network fitted these ranges already; calibration scores are in-training and cannot establish transfer. The rejected method was not tested on the unread match set. That set remains available for a subsequent separately accepted method frozen using TRAIN/range data only.

## Runtime, artifacts and handback

The niced Mac MPS run exited 0 after **92.83 seconds wall time**, with two CPU threads, peak memory footprint 2,886,273,304 bytes and zero swaps. This is successful completion of a negative experiment, not successful calibration. Terminal collection verified the owned process absent and no dev/match result artifacts. The Mac heavy slot was explicitly released to herdr-lead. **$0 paid compute**, no refit, no upload/deletion/cloud mutation. Existing cloud inputs/outputs remain retained.

Canonical Mac folder: `/Users/james/dev/idm-data/pitch-deadband-20260928/`; PC collection: `data/idm/pitch-deadband-20260928/collected/`. Raw TRAIN predictions (20,910,487 bytes) remain in both locations rather than Git; SHA256 `ec28c66dc628eb18e76dc16a828c9400bb1f3c188c2f68afb161c967d0adafb1`. Collected archive SHA256 `cdc15c5ded103f098ab25c1ad7e6fc23166199eb6dd4fe13012205e7bb4f439e`; calibration SHA256 `332e91a5fbf430f07b699969bd71b0ac385b346fadfe98b1a5f9e1149cf5a610`; decision SHA256 `451e92132db350e5cbb73be2057dfaf82d5a24b3f01566866519fc523eb7ccd4`.

Current result: accepted bounded experiment completed; no pitch correction selected. Remaining acceptance: the still/pitch failure from the earlier match diagnostic, reliable buttons, replay/settings/patch transfer and Gate 2 remain unresolved. No new labeling or checkpoint promotion is authorized.

Next: lead decides the next method or expanded refit after this result. IDM retains ownership of the proposal and implementation. The previously proposed eight-range/eight-match, three-epoch Mac refit (~212.809 minutes, $0, provisional six-hour slot) remains **unlaunched and unapproved for execution**; the lead prefers that route if a refit is chosen. Do not treat extra data as an established fix for this negative correction result. No compute is queued and no tuning continues. Lead owns VUH-1353 current-result/remaining/next-action reconciliation and readback.
