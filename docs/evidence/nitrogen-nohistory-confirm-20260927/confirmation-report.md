# NitroGen no-history confirmation — six seeds/arms, Mac A2b recovery

**CONFIRMED** under the reviewed A3 judge `66830ce6`. Press primary: **True**. Camera primary: **True**. Both must pass; the rule was not changed after results.

Candidate: NitroGen, no previous-action input. Control: matched NitroGen with history, training history dropout 0.2. Seeds 1, 2 and 3 per arm; seed 0 is excluded. Each original fit completed 26 epochs / 15,288 updates on L40S. All six were evaluated on one MPS stack, using unchanged final checkpoints and original CUDA TRAIN-calibrated cutoffs. The frozen-dev set is an admitted TRAIN holdout, not an untouched sealed test.

The camera gain is still pitch-driven: mean yaw MAE **1.771697** is **2.10% worse than zero** (1.735184), while pitch **0.594485** is **16.75% better than zero** (0.714106). Passing the registered aggregate camera gate is not evidence that the model turns toward targets horizontally. The history-enabled control nearly stops pressing during self-fed decoding.

## Primary results

TRAIN-calibrated press cutoff and median camera decoder. Camera error is mean absolute error in degrees per step, averaged across yaw and pitch; “median” names the decoder, not a median error statistic. Each seed must favor the candidate; the mean press F1 must also beat incumbent H1 0.101745815, and each candidate camera MAE plus its mean must beat zero motion and the matched control.

| Arm | Seed | Press F1 | Predicted/human press rate | Camera MAE | Yaw MAE | Pitch MAE |
|---|---:|---:|---:|---:|---:|---:|
| candidate | 1 | 0.288988 | 0.9443x | 1.184344 | 1.772979 | 0.595710 |
| candidate | 2 | 0.314255 | 0.9260x | 1.187238 | 1.780877 | 0.593599 |
| candidate | 3 | 0.304449 | 0.9264x | 1.177691 | 1.761234 | 0.594147 |
| **candidate mean** | | **0.302564** | 0.9322x | **1.183091** | **1.771697** | **0.594485** |
| control | 1 | 0.002876 | 0.0024x | 1.283690 | 1.790295 | 0.777085 |
| control | 2 | 0.002588 | 0.0028x | 1.302038 | 1.835857 | 0.768219 |
| control | 3 | 0.006717 | 0.0073x | 1.396054 | 2.003702 | 0.788405 |
| **control mean** | | **0.004060** | 0.0042x | **1.327261** | **1.876618** | **0.777903** |

Paired differences are candidate minus control: positive favors candidate for F1; negative favors it for MAE.

| Seed | Press F1 difference | Camera MAE difference | Yaw difference | Pitch difference |
|---|---:|---:|---:|---:|
| 1 | +0.286112 | -0.099346 | -0.017316 | -0.181375 |
| 2 | +0.311668 | -0.114800 | -0.054980 | -0.174620 |
| 3 | +0.297732 | -0.218363 | -0.242468 | -0.194259 |

| Camera reference | Mean MAE | Yaw MAE | Pitch MAE | Input privilege |
|---|---:|---:|---:|---|
| zero_motion | 1.224645 | 1.735184 | 0.714106 | No motion input; primary baseline |
| persistence | 0.418271 | 0.596854 | 0.239687 | Uses true human action history, unavailable to no-history candidate |
| ar2_refit_selected_train | 0.379687 | 0.546940 | 0.212434 | Uses true human action history, unavailable to no-history candidate |

## Press base rate, secondary metrics and chance floor

Human live-action press events: **2458 / 24556 = 0.10009774 events/frame**. Six EDGE_ACTIONS events: 1437 / 24556 = 0.05851930. Binary any-live-press rate on observable frames: **2333 / 24556 = 0.09500733**. Events/frame and fraction of frames with any press are distinct.

Rate-matched random presser: 256 preregistered draws, preserving per-action/per-run predicted press counts and eligible coordinates, with the same ±1-frame matcher and six-action macro F1. The p05–p95 range is the Monte Carlo distribution, not a confidence interval for the learned model.

| Run | Cutoff | F1 | Predicted events/frame | Rate ratio | Random F1 mean | Random p05–p95 |
|---|---|---:|---:|---:|---:|---|
| candidate-s1 | fixed_0.5 | 0.329519 | 0.13332790 | 1.3320x | 0.032026 | 0.025458–0.038839 |
| candidate-s1 | train_chosen | 0.288988 | 0.09451865 | 0.9443x | 0.027338 | 0.020053–0.034626 |
| control-s1 | fixed_0.5 | 0.059325 | 0.00887767 | 0.0887x | 0.007444 | 0.004356–0.011794 |
| control-s1 | train_chosen | 0.002876 | 0.00024434 | 0.0024x | 0.000196 | 0.000000–0.000861 |
| candidate-s2 | fixed_0.5 | 0.356561 | 0.13202476 | 1.3190x | 0.032091 | 0.025632–0.039166 |
| candidate-s2 | train_chosen | 0.314255 | 0.09268611 | 0.9260x | 0.027393 | 0.019918–0.035745 |
| control-s2 | fixed_0.5 | 0.053870 | 0.00830754 | 0.0830x | 0.006690 | 0.003134–0.011147 |
| control-s2 | train_chosen | 0.002588 | 0.00028506 | 0.0028x | 0.000243 | 0.000000–0.001149 |
| candidate-s3 | fixed_0.5 | 0.358547 | 0.13064017 | 1.3051x | 0.032433 | 0.025999–0.039085 |
| candidate-s3 | train_chosen | 0.304449 | 0.09272683 | 0.9264x | 0.027929 | 0.021398–0.035781 |
| control-s3 | fixed_0.5 | 0.067260 | 0.00928490 | 0.0928x | 0.007828 | 0.003903–0.012144 |
| control-s3 | train_chosen | 0.006717 | 0.00073302 | 0.0073x | 0.000538 | 0.000000–0.001832 |

## Real versus zero visual-feature NLL

Teacher action history is held fixed where the architecture uses it. Zero-feature inference is an out-of-distribution sensitivity check, not a separately trained history-only control. Lower NLL is better. Press NLL pools all known action coordinates; positive-only NLL pools positive press labels. Moving-sign NLL conditions on nonzero target motion.

| Run | Features | Yaw NLL | Pitch NLL | Moving yaw sign NLL | Moving pitch sign NLL | Press NLL | Positive press NLL |
|---|---|---:|---:|---:|---:|---:|---:|
| candidate-s1 | visual | 2.906047 | 2.520958 | 0.688351 | 0.524156 | 0.092017 | 1.808041 |
| candidate-s1 | zero_features | 5.003218 | 3.725662 | 1.628887 | 0.747940 | 0.132622 | 2.061434 |
| control-s1 | visual | 1.493883 | 1.340188 | 0.160486 | 0.148444 | 0.080563 | 1.549569 |
| control-s1 | zero_features | 1.526192 | 1.380970 | 0.163948 | 0.155631 | 0.126272 | 2.072684 |
| candidate-s2 | visual | 2.926834 | 2.527703 | 0.688093 | 0.521132 | 0.093915 | 1.769074 |
| candidate-s2 | zero_features | 3.952325 | 3.034550 | 1.315592 | 0.714201 | 0.189550 | 1.793047 |
| control-s2 | visual | 1.493333 | 1.337847 | 0.161558 | 0.148757 | 0.080494 | 1.597215 |
| control-s2 | zero_features | 1.562430 | 1.408710 | 0.163470 | 0.155923 | 0.123301 | 2.355542 |
| candidate-s3 | visual | 2.933599 | 2.564943 | 0.677640 | 0.526873 | 0.093827 | 1.701375 |
| candidate-s3 | zero_features | 3.973740 | 3.579304 | 0.833152 | 0.765241 | 0.187978 | 1.837440 |
| control-s3 | visual | 1.491266 | 1.335061 | 0.159244 | 0.148364 | 0.080094 | 1.531973 |
| control-s3 | zero_features | 1.532853 | 1.389468 | 0.162913 | 0.155803 | 0.102984 | 1.989398 |

## All 36 self-fed decode results

No decodes were skipped. No persistence stop fired. With history disabled, teacher-forced and self-fed input histories are identical by construction; closing that gap is not counted as a result.

| Run | Cutoff / camera decoder | Press F1 | Camera MAE | Yaw MAE | Pitch MAE |
|---|---|---:|---:|---:|---:|
| candidate-s1 | fixed_0.5/median | 0.329519 | 1.184344 | 1.772979 | 0.595710 |
| candidate-s1 | fixed_0.5/mode | 0.329519 | 1.349932 | 2.054616 | 0.645247 |
| candidate-s1 | fixed_0.5/expectation | 0.329519 | 1.251322 | 1.877736 | 0.624909 |
| candidate-s1 | train_chosen/median | 0.288988 | 1.184344 | 1.772979 | 0.595710 |
| candidate-s1 | train_chosen/mode | 0.288988 | 1.349932 | 2.054616 | 0.645247 |
| candidate-s1 | train_chosen/expectation | 0.288988 | 1.251322 | 1.877736 | 0.624909 |
| control-s1 | fixed_0.5/median | 0.059325 | 1.398809 | 1.990479 | 0.807139 |
| control-s1 | fixed_0.5/mode | 0.082232 | 1.854950 | 2.742538 | 0.967363 |
| control-s1 | fixed_0.5/expectation | 0.096747 | 1.875666 | 2.691324 | 1.060008 |
| control-s1 | train_chosen/median | 0.002876 | 1.283690 | 1.790295 | 0.777085 |
| control-s1 | train_chosen/mode | 0.000000 | 1.349311 | 1.918391 | 0.780231 |
| control-s1 | train_chosen/expectation | 0.018970 | 1.938898 | 2.704991 | 1.172805 |
| candidate-s2 | fixed_0.5/median | 0.356561 | 1.187238 | 1.780877 | 0.593599 |
| candidate-s2 | fixed_0.5/mode | 0.356561 | 1.361976 | 2.080322 | 0.643630 |
| candidate-s2 | fixed_0.5/expectation | 0.356561 | 1.251748 | 1.878984 | 0.624512 |
| candidate-s2 | train_chosen/median | 0.314255 | 1.187238 | 1.780877 | 0.593599 |
| candidate-s2 | train_chosen/mode | 0.314255 | 1.361976 | 2.080322 | 0.643630 |
| candidate-s2 | train_chosen/expectation | 0.314255 | 1.251748 | 1.878984 | 0.624512 |
| control-s2 | fixed_0.5/median | 0.053870 | 1.369348 | 1.954181 | 0.784516 |
| control-s2 | fixed_0.5/mode | 0.080174 | 1.967492 | 3.023092 | 0.911893 |
| control-s2 | fixed_0.5/expectation | 0.098868 | 1.892462 | 2.708128 | 1.076795 |
| control-s2 | train_chosen/median | 0.002588 | 1.302038 | 1.835857 | 0.768219 |
| control-s2 | train_chosen/mode | 0.000577 | 1.224620 | 1.735145 | 0.714096 |
| control-s2 | train_chosen/expectation | 0.006514 | 1.929281 | 2.647783 | 1.210779 |
| candidate-s3 | fixed_0.5/median | 0.358547 | 1.177691 | 1.761234 | 0.594147 |
| candidate-s3 | fixed_0.5/mode | 0.358547 | 1.350823 | 2.054031 | 0.647614 |
| candidate-s3 | fixed_0.5/expectation | 0.358547 | 1.237264 | 1.848625 | 0.625903 |
| candidate-s3 | train_chosen/median | 0.304449 | 1.177691 | 1.761234 | 0.594147 |
| candidate-s3 | train_chosen/mode | 0.304449 | 1.350823 | 2.054031 | 0.647614 |
| candidate-s3 | train_chosen/expectation | 0.304449 | 1.237264 | 1.848625 | 0.625903 |
| control-s3 | fixed_0.5/median | 0.067260 | 1.387923 | 1.957433 | 0.818412 |
| control-s3 | fixed_0.5/mode | 0.064544 | 1.442233 | 2.060733 | 0.823732 |
| control-s3 | fixed_0.5/expectation | 0.100930 | 1.903596 | 2.730318 | 1.076874 |
| control-s3 | train_chosen/median | 0.006717 | 1.396054 | 2.003702 | 0.788405 |
| control-s3 | train_chosen/mode | 0.005128 | 1.587674 | 2.244889 | 0.930459 |
| control-s3 | train_chosen/expectation | 0.008021 | 1.923000 | 2.809145 | 1.036854 |

## Integrity, recovery and cost

Before publishing, the judgement source_manifest was independently compared to the preregistered pins: A3 judge `66830ce6eb302f4b9052b99f0f6ee31836121dd524e7eb1ddabd5a32915ef6c8`, metrics `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5`, vocab `9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e` and A1 `7950bd9f…`. All matched, and source_manifest includes A3 `fca0af0dbe486e055c945923e715c105cced467072014641d751fc85f6ec0d3d`. Independent A3 review receipt SHA `cd1e95264a431f575b9b85257affee397bb0d6395e7201c221800fea4c6fc159` is retained in [a3-review-receipt.zip](a3-review-receipt.zip). The historical judge 6f2187dd remains byte-intact. A3 corrects only its malformed 65-character input-manifest pin in a new copy; actual manifest bytes match the 64-character checkpoint identities and upload receipt. The correction and new judge hash were preregistered before any numerical metric was inspected, and independently cleared before judging. No metric or decision logic changed.

The original Modal failures and exit-1 finals are retained. Recovered epoch-26 bytes matched two independent volume reads, loaded with weights_only=True, matched complete latest-state tensors and epoch/update receipts, and were pinned before recovery. No pre-failure checkpoint digest existed, so integrity is not claimed against an unavailable earlier digest. New success receipts explicitly cover evaluation-only recovery and terminal Mac process exit, not successful original Modal apps.

First Mac A2 completed features but failed before inference on Path serialization. Fix/reuse receipt committed `88b231d`; feature-stage SHA `d051df52812522d8973fec3b1e9a2dac5f1a37371cfdfd9798d553b53f66b23e`. A2b streamed every feature-file hash before reuse; no refit, re-extraction or threshold re-selection. All six complete evaluations and process exit 0 were required before opening any result. Mac MPS: torch 2.14.0, transformers 4.57.1, safetensors 0.6.2; bf16 vision, float32 pooling, float16 feature cache, float32 heads. The launcher ran at nice 10 with two CPU threads. The seed-0 explore numbers used CUDA; cross-round numeric comparisons therefore include a device-stack difference.

Conservative original confirmation compute allocation: **$13.878193**, against the $20 cap. Mac recovery: **$0**. Cumulative explore-lane allocation: **approximately $49.026837**, including earlier $35.148644; this is an allocation estimate, not an invoice and excludes other lanes/storage. The lead owns James’s $150 weekend ledger. All six original Modal apps were independently verified terminal with zero tasks/containers.

Evidence: [judgement.json](judgement.json), [report-data.json](report-data.json), [mac-a3-results.zip](mac-a3-results.zip) (SHA-256 `c8fada8aadb2d9ed377cb3ef4a7521021a53f36fa0f64c1f89c48a69beb04baf`; per-file raw hashes inside), [modal-incident.md](modal-incident.md), [preregistration-a2.md](preregistration-a2.md), [preregistration-a3.md](preregistration-a3.md), [mac-a2b-recovery.md](mac-a2b-recovery.md).

This result concerns three paired seeds on one frozen development cohort. It does not establish autonomous playability, target acquisition, robustness on new sessions, or authorization to drive the live game. No sealed data was read.

The lead-requested post-result cold-onset diagnostic and 30 s offline replay follow as separate exploratory addenda; neither changes this verdict.
