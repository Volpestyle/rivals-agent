# EXPLORATORY cold-onset / continuation diagnostic

Post-confirmation risk check requested by steering and approved by the lead. This does not change the frozen judge or the confirmation verdict. Six existing candidate/control checkpoints, their original CUDA TRAIN cutoffs, median camera decoder, the same MPS stack and completed features; no fitting, extraction or paid compute.

Previous 15 or 30 rows only. Cold: no semantic or unsupported human press and exactly zero yaw/pitch; all prior press/camera channels known and valid. Run-boundary/unknown-history rows excluded; continuation is the known-history complement. Existing held actions may persist in cold rows.

Press F1 uses original coordinates and +/-1 matcher, with truth and predictions restricted to the same stratum. Boundary-permitting recall additionally allows predictions outside the target stratum; this is sensitivity only and can credit a one-frame late echo. Six-action macro recall uses zero for actions with no positives. Camera moving/sign recall uses absolute target/prediction >=0.3 deg/step, matching the existing sign target threshold.

The split depends on James’s recorded history, not on model predictions. Recurrent visual memory is still present; even a cold row can contain an older action, held movement, animation or spent ammo. This stratification probes continuation dependence; it cannot demonstrate closed-loop control or remove observation feedback mismatch.

**Finding:** the measured press advantage occurs in continuations. At 0.5 s, only 731 frames and 5 EDGE_ACTIONS presses qualify as cold; every candidate and control seed misses all five under strict same-stratum matching. Candidate continuation F1 averages 0.302575 versus control 0.004067. At 1 s, only 502 frames qualify and there are **zero cold press targets**: the conservative macro score is zero, but cold press recall is statistically unmeasurable, not demonstrated failure on observed events. The dataset is overwhelmingly active, so these sparse cold events cannot establish that copying causes the aggregate gain. They provide no evidence of reliable independent press initiation.

The boundary-permitting 0.5 s recall is 0.20/0.40/0.40 for candidate seeds: these matches occur one frame after the cold human press and could be visual echoes. Cold camera errors also lose to zero on both axes. At 0.5 s there are only three nontrivial yaw and one pitch targets; at 1 s there are none. Expect weaker live initiation than the headline offline F1 establishes, and require a deliberate initiation-rich evaluation before claiming it.

## Press: paired-seed means

| Window | Stratum | Arm | Frames | True EDGE presses | Mean F1 | Mean macro recall | Mean micro recall | Mean matched presses |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 0.5s | cold | candidate | 731 | 5 | 0.000000 | 0.000000 | 0.000000 | 0.00 |
| 0.5s | cold | control | 731 | 5 | 0.000000 | 0.000000 | 0.000000 | 0.00 |
| 0.5s | continuation | candidate | 23795 | 1431 | 0.302575 | 0.280041 | 0.313534 | 448.67 |
| 0.5s | continuation | control | 23795 | 1431 | 0.004067 | 0.002078 | 0.003727 | 5.33 |
| 1.0s | cold | candidate | 502 | 0 | 0.000000 | 0.000000 | — | 0.00 |
| 1.0s | cold | control | 502 | 0 | 0.000000 | 0.000000 | — | 0.00 |
| 1.0s | continuation | candidate | 23994 | 1433 | 0.301960 | 0.279367 | 0.313096 | 448.67 |
| 1.0s | continuation | control | 23994 | 1433 | 0.004071 | 0.002080 | 0.003722 | 5.33 |

Frames and true presses are the same human population for every seed; they are not multiplied by three. Recall macro averages the six EDGE_ACTIONS and counts an action without positives as zero; the micro column and per-action counts in the raw JSON distinguish low support from missed events.

## Every seed and boundary sensitivity

| Run | Window | Stratum | F1 | Macro recall | Micro recall | Boundary-permitting micro recall |
|---|---|---|---:|---:|---:|---:|
| candidate-s1 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.200000 |
| candidate-s1 | 0.5s | continuation | 0.289137 | 0.264099 | 0.302586 | 0.302586 |
| candidate-s1 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| candidate-s1 | 1.0s | continuation | 0.288210 | 0.263070 | 0.301465 | 0.301465 |
| control-s1 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| control-s1 | 0.5s | continuation | 0.002884 | 0.001452 | 0.002795 | 0.002795 |
| control-s1 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| control-s1 | 1.0s | continuation | 0.002885 | 0.001452 | 0.002791 | 0.002791 |
| candidate-s2 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.400000 |
| candidate-s2 | 0.5s | continuation | 0.314181 | 0.290821 | 0.317959 | 0.317959 |
| candidate-s2 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| candidate-s2 | 1.0s | continuation | 0.313965 | 0.290560 | 0.318214 | 0.318214 |
| control-s2 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| control-s2 | 0.5s | continuation | 0.002600 | 0.001310 | 0.002795 | 0.002795 |
| control-s2 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| control-s2 | 1.0s | continuation | 0.002596 | 0.001308 | 0.002791 | 0.002791 |
| candidate-s3 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.400000 |
| candidate-s3 | 0.5s | continuation | 0.304407 | 0.285202 | 0.320056 | 0.320056 |
| candidate-s3 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| candidate-s3 | 1.0s | continuation | 0.303706 | 0.284471 | 0.319609 | 0.319609 |
| control-s3 | 0.5s | cold | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| control-s3 | 0.5s | continuation | 0.006717 | 0.003472 | 0.005590 | 0.005590 |
| control-s3 | 1.0s | cold | 0.000000 | 0.000000 | — | — |
| control-s3 | 1.0s | continuation | 0.006734 | 0.003481 | 0.005583 | 0.005583 |

Boundary-permitting recall can credit an output one frame after the cold human press, when its animation has already appeared. It is reported as sensitivity, not substituted for the strict cold score.

## Camera, separated by axis

Motion means at least 0.3 degrees in the current step, matching the existing sign-scoring target threshold. Motion recall asks whether the prediction reaches that magnitude; signed-motion recall also requires the correct sign. MAE includes all known rows in the stratum; moving MAE isolates nontrivial current movement. All are seed means.

| Window | Stratum | Arm | Axis | Motion targets | MAE | Zero MAE | Moving MAE | Moving zero MAE | Motion recall | Signed-motion recall |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.5s | cold | candidate | yaw | 3 | 0.176661 | 0.004072 | 1.273411 | 0.804796 | 0.444444 | 0.444444 |
| 0.5s | cold | candidate | pitch | 1 | 0.102618 | 0.003303 | 0.706872 | 1.620616 | 1.000000 | 1.000000 |
| 0.5s | cold | control | yaw | 3 | 0.131896 | 0.004072 | 1.258320 | 0.804796 | 0.111111 | 0.111111 |
| 0.5s | cold | control | pitch | 1 | 0.052073 | 0.003303 | 1.420616 | 1.620616 | 0.333333 | 0.333333 |
| 0.5s | continuation | candidate | yaw | 13891 | 1.822668 | 1.790320 | 2.709688 | 3.019402 | 0.635759 | 0.456531 |
| 0.5s | continuation | candidate | pitch | 11756 | 0.609935 | 0.736419 | 0.911149 | 1.413218 | 0.700578 | 0.636242 |
| 0.5s | continuation | control | yaw | 13891 | 1.932351 | 1.790320 | 3.095054 | 3.019402 | 0.232285 | 0.120246 |
| 0.5s | continuation | control | pitch | 11756 | 0.800758 | 0.736419 | 1.416311 | 1.413218 | 0.232732 | 0.131706 |
| 1.0s | cold | candidate | yaw | 0 | 0.110478 | 0.000329 | — | — | — | — |
| 1.0s | cold | candidate | pitch | 0 | 0.067196 | 0.000198 | — | — | — | — |
| 1.0s | cold | control | yaw | 0 | 0.061397 | 0.000329 | — | — | — | — |
| 1.0s | cold | control | pitch | 0 | 0.022155 | 0.000198 | — | — | — | — |
| 1.0s | continuation | candidate | yaw | 13882 | 1.810418 | 1.775280 | 2.711485 | 3.021040 | 0.635427 | 0.456082 |
| 1.0s | continuation | candidate | pitch | 11744 | 0.606020 | 0.729551 | 0.911084 | 1.413077 | 0.700528 | 0.636183 |
| 1.0s | continuation | control | yaw | 13882 | 1.918750 | 1.775280 | 3.096840 | 3.021040 | 0.232459 | 0.120348 |
| 1.0s | continuation | control | pitch | 11744 | 0.794382 | 0.729551 | 1.416156 | 1.413077 | 0.232998 | 0.131869 |

## Integrity and limitations

The diagnostic preserves original run coordinates and masks eligibility rather than compressing frames. Tests cover current/future-label exclusion, 15/30-frame windows, unknown history, gaps, tiny nonzero movement, unsupported presses and a late echo crossing the stratum boundary. Four synthetic tests passed on PC and Mac.

Aggregate reproduction differences (diagnostic rerun minus original confirmation TRAIN/median):

| Run | F1 difference | Camera MAE difference |
|---|---:|---:|
| candidate-s1 | +0.000000000000 | +0.000000000000 |
| control-s1 | +0.000000000000 | +0.000000000000 |
| candidate-s2 | +0.000000000000 | +0.000000000000 |
| control-s2 | +0.000000000000 | +0.000000000000 |
| candidate-s3 | +0.000000000000 | +0.000000000000 |
| control-s3 | +0.000000000000 | +0.000000000000 |

This is an exploratory post-result analysis with two requested history windows and potentially sparse cold events. No multiplicity-corrected inference, causal attribution or live-performance guarantee is claimed. The same caution applies to a future pixel ego-motion input: its apparent predictive value can depend on James’s past actions appearing in the observation stream, while live it would see the model’s own actions.

Raw data: [cold-onsets-results.json](cold-onsets-results.json). Metric source `a8be454`, A3 runner `91dd14a`; the confirmation decision under reviewed A3 judge `66830ce6` remains unchanged (historical `6f2187dd` is retained). See [confirmation-report.md](confirmation-report.md) for the unchanged confirmation decision.

Raw stage/terminal receipts: [cold-onsets-results.zip](cold-onsets-results.zip), SHA-256 `fdf5e6a08fa8aed78d0b38f3ee2408766e918cb1f3743d833cb9a8a1954f1557`. All six aggregate reproduction differences are exactly zero. Niced Mac run exited 0; cloud cost $0.
