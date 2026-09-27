# Interim IDM refit result — EXPLORATORY

Owner: idm-owner, VUH-1353. Completed **2026-09-27 06:59:51 CDT**, exit 0. Three epochs, seed 0, MPS; 80.53 minutes from five range training sessions, with 171533/205528 held out. This is neither the expanded match cohort nor the seconds-context edge experiment.

**Finding:** camera recovery is useful against zero, but does not beat the previous-true-rotation baseline. Several action scores rank onsets well, but the fixed-threshold outputs overfire. No Gate 2 readiness or checkpoint promotion follows.

## Verified delivery

Collected report, checkpoint, run manifest, run log, console/resource log and exit receipt; all six raw SHA256 values match the Mac's manifest. The report has the intended run-manifest pin, MPS, seed 0, three epochs and no smoke limit. Checkpoint bytes match the report. No new inference, fit, decode or sealed-source access was performed during collection.

- [Report](../../data/idm/explore-20260927/refit-result/report.json): `bce156fcf7cd941a3ee77d16a7eac93e709e3f04d35c32a40ad90e773bdf6e2a`.
- [Checkpoint](../../data/idm/explore-20260927/refit-result/refit.pt): `1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541`.
- [All artifact hashes](../../data/idm/explore-20260927/refit-result/refit-final-hashes.json).
- Wall time **56m 59s**; training 54m 06s. Epoch losses 1.2860, 0.7241, 0.6034. Peak RSS 53.30 GiB; peak process footprint 3.78 GiB; zero process swaps. RSS includes mapped stores, not just active model memory.

The failed launcher attempt and corrected wrapper are recorded in [the launch note](idm-refit-launch-20260927.md). The wrapper-only delta remains subject to independent post-run review before result acceptance; no receipt for that delta is included in this packet. No commit or deployment was made.

## Camera on heldout range dev

49,080 eligible intervals: 9,244 on 171533 and 39,836 on 205528. Moving means absolute truth rotation >0.5 degrees per 60 Hz interval. Values below are degrees; each predictor is scored on its own answered rows, so these are not identical answered subsets. Pitch truth is still derived from equal sensitivity, not independently measured pitch calibration.

| Dev / axis | Model MAE | Model moving median error | Zero moving median | Persistence moving median | Model moving direction |
|---|---:|---:|---:|---:|---:|
| 171533 yaw | 0.1732 | 0.2461 | 1.2237 | 0.1984 | 99.60% |
| 171533 pitch | 0.1412 | 0.4448 | 0.8930 | 0.0992 | 94.05% |
| 205528 yaw | 0.3008 | 0.3436 | 1.4552 | 0.1984 | 98.62% |
| 205528 pitch | 0.2804 | 0.5011 | 0.9261 | 0.1323 | 89.96% |
| Pooled yaw | 0.2835 | 0.3315 | 1.4222 | 0.1984 | 98.53% |
| Pooled pitch | 0.2554 | 0.4928 | 0.8930 | 0.1323 | 90.16% |

Pooled all-interval MAE for model / zero / persistence is **0.2835 / 0.8691 / 0.2206 yaw**, **0.2554 / 0.3577 / 0.0919 pitch**. Model answered 48,959 yaw rows (99.75%) and 48,818 pitch rows (99.47%); zero answered all 49,080, persistence 49,077. Persistence uses the previous interval's **true human rotation** inside each continuous run: a useful diagnostic, unavailable on unlabelled video. Its advantage is not evidence that a deployable pixel-only alternative has beaten the IDM.

Pooled median absolute integrated error over 0.25s / 1s: model yaw **1.3269 / 4.2743**, zero **4.4980 / 24.7061**, persistence **0.4300 / 0.6284**; model pitch **1.5849 / 4.1372**, zero **2.4144 / 9.2276**, persistence **0.2315 / 0.2977**. Window counts differ with abstention and continuity; the report retains denominators.

Uncertainty is not automatically calibrated by carrying pitch-A: extrapolated yaw within-2-sigma coverage is **88.06% / 85.70%** on 171533/205528. No matched A4 rescore, geometric baseline or Pearson-r calculation was produced here. Do not compare the new MAE directly to an old headline measured on different rows or call this an A4 improvement.

## Press heads

Existing pooled/HUD head, fixed probability threshold 0.5, existing abstention band, one-to-one matching within +/-2 intervals. **No train-rate threshold calibration or chance-at-rate comparison was run.** AUC is computed on answered rows; it is not the chance-adjusted F1 judge used in the earlier edge experiments. Zero and persistence predict no presses and have F1 0 for every listed action.

| Action | Heldout onsets | Pooled F1 | Precision | Recall | AUC | F1: 171533 / 205528 |
|---|---:|---:|---:|---:|---:|---:|
| Amazing Combo | 96 | 0.3209 | 0.1976 | 0.8542 | 0.9571 | 0.3099 / 0.3213 |
| Jump | 575 | 0.2109 | 0.1196 | 0.8939 | 0.9505 | 0.2548 / 0.2054 |
| Web Cluster | 384 | 0.4164 | 0.2940 | 0.7135 | 0.8828 | 0.4670 / 0.4100 |
| Web Swing | 160 | 0.3041 | 0.1835 | 0.8875 | 0.9430 | 0.3108 / 0.3046 |
| Get Over Here | 42 | 0.1102 | 0.0592 | 0.7857 | 0.9120 | 0.1165 / 0.1127 |
| Team-up | 50 | 0.1119 | 0.0678 | 0.3200 | 0.7918 | 0.1935 / 0.1062 |
| Spider Power | 180 | 0.1186 | 0.0959 | 0.1556 | 0.7449 | 0.1333 / 0.1165 |
| Move forward | 248 | 0 | — | 0 | 0.5742 | 0 / 0 |
| Move back | 197 | 0 | — | 0 | 0.5894 | 0 / 0 |
| Move left | 326 | 0 | — | 0 | 0.5431 | 0 / 0 |
| Move right | 250 | 0 | — | 0 | 0.5407 | 0 / 0 |
| GOH targeting | 9 | 0 | — | 0 | 0.8868 | 0 / 0 |

Combo: **82 TP, 333 FP, 14 FN**; jump: **514 TP, 3,785 FP, 61 FN**. Predicted/true onset rates are 0.0085/0.0020 for Combo and 0.0876/0.0117 for jump. High recall and AUC do not make these outputs usable press labels. Movement has no emitted onsets at this threshold, with 6.89–51.17% abstention by action; this does not test held-state recovery.

Support is per session, not rescued by pooling: Combo has only **14** positives on 171533 (undecided there) and 82 on 205528; jump has 88/487. GOH targeting has only 9 pooled and is undecided. On 171533, GOH, team-up, Spider Power, Web Swing and move-forward also fall below 30 onsets. Melee, simple-swing and ultimate are training-unsupported and are not scored as learned actions.

## Gate 2 and next step

**Gate 2 remains unready.** This single-seed range refit supplies no live-match/replay transfer evidence, no independently validated evaluation alignment, no new camera calibration acceptance and no replicated/chance-adjusted press conclusion. Both Gate 2 pairs remain sealed. Keep A4/pitch A as the existing reference; this checkpoint is an exploratory candidate only.

Next concrete step for the expanded refit: obtain admission-owner's accepted **`rivals-idm-match-admission-v1`** receipt plus its pinned imported demos, reviewed steps and motor/identity evidence, then build targets/stores for the eligible live matches. That receipt is the known blocker; registration and video hashes are insufficient. The replay and motor-pending main-account file remain excluded by the reviewed target path. In parallel planning, the low-cost action diagnostic is a train-only rate-matched threshold/chance score on this fixed checkpoint before attributing action success; it was not launched here. The separate seconds-context Combo experiment still needs pinned DINO assets and its prepared stores.

Mac compute is released by this lane: the refit exited successfully and no successor was launched. The lead controls the next queue allocation.
