Neither works. **No real fit under the pre-registration.**

VUH-1346, countermeasures round 2; independent judging, 2026-09-26. D (known-idle corruption) and E (sequential self-conditioning) both pass K, but each has **0/3 seeds passing S1-S4 together**. A also has 0/3, so there is no sanity failure. This is a dev plumbing test, not policy acceptance or a live-pilot candidate.

The rules were not changed. The pre-registered next choices belong to the lead: full-rate P=1.0, combining D and E (requires a code change), or a normalised frames-only arm. The half-rate branch applies to an arm passing S and failing K; neither arm is in that branch.

**Inputs and report checks**

Pre-registration LF SHA-256: `4d4576db90f65bb62f7fb4fb7a462a99d13b3d7c9898a8277a615e3d39608a17`. The four judge/test files matched the lead's pins before tests or result retrieval and were rechecked unchanged afterward. `test_judge_cm2.py`: 11 PASS checks, ALL PASS; `test_judge_cm.py`: 14 PASS checks, ALL PASS. Both exit 0. The original pinned judge exited 0 with `check_failures: []`; its exact output is `reading.json`.

| Judge/test file | SHA-256 |
|---|---|
| judge_cm.py | 6f77e938e689f64c74a2a21ddf4f7ec5d22ac232e8099e94f62a74a7f1692e1f |
| judge_cm2.py | d3a99f0ae8e1c89490cb0aacf30963f70b81b4df80b5e852f49759c059700f06 |
| test_judge_cm.py | a5f09d3d0dce5b5235c1d5a41a35ed33ab14626afb07a4f6f7090b7566df7740 |
| test_judge_cm2.py | fa54b216d1736e752de0ae672a82fc1a66874e7bf3537b1a47fe6b077f8b9b74 |

| Report check | D | E |
|---|---|---|
| Scope | PASS: plumbing | PASS: plumbing |
| Shared recipe | PASS: epochs 13, wd 0.0001, stride 64, lag 0, prev dropout 0.2 | PASS: same |
| Arm and seeds | PASS: model_nohud only; 0, 1, 2 | PASS: model_nohud only; 0, 1, 2 |
| History option | PASS: idle_corruption p=0.5, run=[8,48]; self_roll/self_condition null | PASS: self_roll p=0.5, steps=32, ramp=0.5; idle_corruption/self_condition null |
| Other config | PASS: train_fraction=1, max_steps=null, g1_press_source=teacher_forced | PASS: same |
| Batch / lr / regime / device | PASS: 8 / 0.0003 / normal / MPS | PASS: same |
| Parity | PASS: e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801 | PASS: same |
| Cohort and steps | PASS: exact 5 interim train + 171533/205528 dev, all 7 step hashes | PASS: same |
| Test not opened | PASS: explicit false | PASS: explicit false |
| Checkpoint set and identity | PASS: seeds 0-2, all 3 hashes equal Mac shasum | PASS: seeds 0-2, all 3 hashes equal Mac shasum |
| Code closure | PASS: judge pins and all 20 closure entries equal git 3670d0e | PASS: same 20 entries |
| Queue exit | PASS: 0 | PASS: 0 |

A: all five stored-block/gate equality flags are true. The newly copied `A-reread.json` is also byte-identical to the previously pinned round-1 local copy (`8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9`). The seven-cache receipt is `d23b8b9e…`, matching the queue's pinned interim receipt. Cache verification was a separate queue prerequisite, with a byte-comparison guard before A, D and E; the reports' own `cache_hashes_verified` field is false, so it is not the evidence for that prerequisite. Queue status is `DONE 2026-09-26T17:10:27`.

**S1-S4, exactly as registered**

S1: hold-onset recall >=0.05. S2: pooled press ratio in [0.5,2.0] AND at least 6/10 live-action ratios in that band. S3: camera MAE <=1.1634128700769406 degrees (0.95 times zero-motion 1.2246451263967797). S4: observable any-hold share in [0.34964978009447795,0.9090894282456427], from human share 0.6992995601889559. All seeds have 24,556 observable rows and zero excluded rows. Displayed figures are rounded; the judge used full precision.

| Arm | Seed | S1 onset recall | S2 pooled; in-band actions | S3 camera deg | S4 any-hold share | All S |
|---|---|---|---|---|---|---|
| A | 0 | 0.000000 FAIL | 0.000000; 0/10 FAIL | 1.224645 FAIL | 0.000000 FAIL | FAIL |
| A | 1 | 0.000000 FAIL | 0.000407; 0/10 FAIL | 1.224647 FAIL | 0.001955 FAIL | FAIL |
| A | 2 | 0.003261 FAIL | 0.000814; 0/10 FAIL | 1.229017 FAIL | 0.053062 FAIL | FAIL |
| D | 0 | 0.111292 PASS | 0.034581; 0/10 FAIL | 1.245415 FAIL | 0.957811 FAIL | FAIL |
| D | 1 | 0.068080 PASS | 0.013426; 0/10 FAIL | 1.355352 FAIL | 0.617649 PASS | FAIL |
| D | 2 | 0.108031 PASS | 0.048413; 0/10 FAIL | 1.351690 FAIL | 0.840080 PASS | FAIL |
| E | 0 | 0.048104 FAIL | 0.303092; 2/10 FAIL | 1.296499 FAIL | 0.262624 FAIL | FAIL |
| E | 1 | 0.021606 FAIL | 0.422295; 2/10 FAIL | 1.328293 FAIL | 0.230697 FAIL | FAIL |
| E | 2 | 0.053812 PASS | 0.270545; 2/10 FAIL | 1.371259 FAIL | 0.354862 PASS | FAIL |

D passes onset recall for all seeds, but its pooled press ratios remain 0.0134-0.0484 and no live action is in band; all cameras fail. Seed 0 also holds too much. E produces more presses, but all pooled ratios remain below 0.5, only 2/10 actions are in band, and every camera fails. E seed 0's S1 **near-miss**, 0.0481043620057073 versus 0.05 (short by 0.0018956379942927), stays a failure; it also fails the other three checks. E seed 2 passes S1 and S4, but fails S2 and S3. These are partial improvements, not an arm-level pass.

**S and skill retention K**

T is executed teacher-forced macro press-F1, late=0; F is self-fed macro press-F1, +/-1 step. Executed-TF press counts are not used as skill evidence. K uses mean T(arm) >= mean T(A) - [range T(A) + range T(arm)].

| Arm | S | T seeds 0/1/2 | Mean T | Range T | K bar | K | Mean F | Range F |
|---|---|---|---|---|---|---|---|---|
| A | 0/3; FAIL | 0.044745, 0.028001, 0.032582 | 0.035109 | 0.016743 | baseline | baseline | 0.000000 | 0.000000 |
| D | 0/3; FAIL | 0.034225, 0.022206, 0.027941 | 0.028124 | 0.012020 | 0.006346 | PASS | 0.006408 | 0.006640 |
| E | 0/3; FAIL | 0.043666, 0.041046, 0.044338 | 0.043017 | 0.003292 | 0.015074 | PASS | 0.071924 | 0.036882 |

The exact K bars are D=0.006346027475135921 and E=0.015073777561288765. Both pass. The Both-work F tie-break never applies because neither passes S.

**Reported, not judged**

Epochs below use the judge's 1-based numbering (stored `epoch` values are 0-based). Dev total is shown at the final epoch and at its argmin; no checkpoint selection or threshold is changed. Fit seconds are reported per-seed training wall times; separate evaluation and queue overhead are not silently included.

| Arm | Seed | Final dev total | Argmin epoch | Min dev total | Final train loss | Fit seconds | Fit min | Self-fed camera deg | TF camera deg |
|---|---|---|---|---|---|---|---|---|---|
| A | 0 | 1.314375 | 13 | 1.314375 | 1.338020 | 3131.009 | 52.18 | 1.224645 | 0.595326 |
| A | 1 | 1.315224 | 13 | 1.315224 | 1.357209 | 3066.914 | 51.12 | 1.224647 | 0.585843 |
| A | 2 | 1.310065 | 12 | 1.309587 | 1.332540 | 3136.515 | 52.28 | 1.229017 | 0.583246 |
| D | 0 | 1.413932 | 12 | 1.412403 | 1.567471 | 2903.368 | 48.39 | 1.245415 | 0.658843 |
| D | 1 | 1.415353 | 13 | 1.415353 | 1.572237 | 3092.429 | 51.54 | 1.355352 | 0.642862 |
| D | 2 | 1.368271 | 13 | 1.368271 | 1.508149 | 3810.723 | 63.51 | 1.351690 | 0.621838 |
| E | 0 | 1.473030 | 12 | 1.471156 | 1.674296 | 5265.194 | 87.75 | 1.296499 | 0.647755 |
| E | 1 | 1.492671 | 13 | 1.492671 | 1.728540 | 3865.419 | 64.42 | 1.328293 | 0.653352 |
| E | 2 | 1.460794 | 11 | 1.460543 | 1.667197 | 3636.711 | 60.61 | 1.371259 | 0.640105 |

No self-fed camera in A, D or E beats persistence **0.418 degrees** or ar2 **0.376 degrees**; none even passes S3. Teacher-forced camera is shown for context only. E's per-seed runtime varies, so this single sequential queue does not isolate an architectural speed ratio.

Train-loss curves against A, seeds 0/1/2 in each cell (all 13 epochs; descriptive training cost only):

| Epoch (1-based) | A train loss, seeds 0/1/2 | D train loss, seeds 0/1/2 | E train loss, seeds 0/1/2 |
|---|---|---|---|
| 1 | 2.785889, 2.823297, 2.801593 | 2.786111, 2.823452, 2.801275 | 2.786014, 2.823410, 2.801598 |
| 2 | 2.461111, 2.448313, 2.439370 | 2.465162, 2.460639, 2.445711 | 2.463080, 2.465385, 2.447777 |
| 3 | 2.209572, 2.167556, 2.163122 | 2.396144, 2.317112, 2.306041 | 2.300900, 2.335112, 2.266332 |
| 4 | 1.896792, 1.854528, 1.875032 | 2.180731, 2.098459, 2.075869 | 2.073324, 2.110572, 2.043878 |
| 5 | 1.688610, 1.666823, 1.688896 | 1.982910, 1.902485, 1.898290 | 1.942723, 1.952782, 1.922577 |
| 6 | 1.569927, 1.559468, 1.563680 | 1.829586, 1.792702, 1.765837 | 1.875890, 1.875960, 1.854671 |
| 7 | 1.492962, 1.492636, 1.489133 | 1.740281, 1.714547, 1.677626 | 1.834689, 1.856318, 1.816116 |
| 8 | 1.439345, 1.447131, 1.436922 | 1.681604, 1.666499, 1.622012 | 1.790072, 1.825720, 1.778512 |
| 9 | 1.403044, 1.411765, 1.396869 | 1.637695, 1.627535, 1.571816 | 1.737617, 1.772227, 1.734149 |
| 10 | 1.374034, 1.386903, 1.369317 | 1.603165, 1.599253, 1.545209 | 1.715405, 1.755443, 1.708367 |
| 11 | 1.355348, 1.370454, 1.350696 | 1.586758, 1.584990, 1.525388 | 1.690466, 1.737865, 1.684104 |
| 12 | 1.344070, 1.360805, 1.338830 | 1.571384, 1.572740, 1.517923 | 1.671770, 1.722622, 1.675986 |
| 13 | 1.338020, 1.357209, 1.332540 | 1.567471, 1.572237, 1.508149 | 1.674296, 1.728540, 1.667197 |

`held_change_f1` is a per-action figure, not a preregistered scalar pass rule. The following tables retain all 15 reported actions, with seeds 0/1/2 in each cell. No new macro average is used for judging. Unsupported/non-live actions are included as reported; S2 above uses only the 10 live actions.

held_change_f1: **self_fed**

| Action | A seeds 0/1/2 | D seeds 0/1/2 | E seeds 0/1/2 |
|---|---|---|---|
| amazing_combo | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.034188 | 0.017391, 0.000000, 0.017544 |
| get_over_here | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| goh_targeting | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| jump | 0.000000, 0.000000, 0.000000 | 0.012719, 0.003407, 0.006504 | 0.066265, 0.016026, 0.071605 |
| melee | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| move_back | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| move_forward | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.010850, 0.000000, 0.010657 |
| move_left | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| move_right | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| simple_swing | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| spider_power | 0.000000, 0.000000, 0.000000 | 0.005155, 0.000000, 0.000000 | 0.008772, 0.017241, 0.008000 |
| team_up | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| ultimate | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| web_cluster | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.007692 | 0.035941, 0.009926, 0.039648 |
| web_swing | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.005236 | 0.029126, 0.000000, 0.014634 |

held_change_f1: **executed_teacher_forced**

| Action | A seeds 0/1/2 | D seeds 0/1/2 | E seeds 0/1/2 |
|---|---|---|---|
| amazing_combo | 0.145946, 0.145078, 0.144330 | 0.152174, 0.170213, 0.137566 | 0.154696, 0.188482, 0.155440 |
| get_over_here | 0.102041, 0.038462, 0.020833 | 0.000000, 0.022727, 0.000000 | 0.044444, 0.022727, 0.044444 |
| goh_targeting | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| jump | 0.061644, 0.044194, 0.060449 | 0.063194, 0.043103, 0.062500 | 0.090290, 0.068936, 0.094148 |
| melee | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| move_back | 0.020202, 0.012626, 0.010101 | 0.032419, 0.017588, 0.025000 | 0.028640, 0.012225, 0.029340 |
| move_forward | 0.007851, 0.003972, 0.005900 | 0.009681, 0.005831, 0.005831 | 0.023235, 0.017127, 0.005775 |
| move_left | 0.026034, 0.013783, 0.021407 | 0.032061, 0.020833, 0.013825 | 0.025148, 0.030479, 0.035608 |
| move_right | 0.010040, 0.022133, 0.018000 | 0.020040, 0.024000, 0.009960 | 0.029354, 0.027397, 0.020952 |
| simple_swing | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| spider_power | 0.005495, 0.002717, 0.013587 | 0.018519, 0.000000, 0.023866 | 0.023041, 0.020050, 0.020179 |
| team_up | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| ultimate | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 | 0.000000, 0.000000, 0.000000 |
| web_cluster | 0.118890, 0.110226, 0.098013 | 0.077437, 0.059920, 0.111543 | 0.117955, 0.090667, 0.131406 |
| web_swing | 0.079872, 0.029032, 0.051447 | 0.070000, 0.087542, 0.064309 | 0.078176, 0.090909, 0.075342 |

held_change_f1: **teacher_forced**

| Action | A seeds 0/1/2 | D seeds 0/1/2 | E seeds 0/1/2 |
|---|---|---|---|
| amazing_combo | 0.284238, 0.286472, 0.284916 | 0.289216, 0.293987, 0.254237 | 0.297362, 0.340230, 0.289617 |
| get_over_here | 0.392344, 0.348718, 0.346154 | 0.378378, 0.376147, 0.374429 | 0.387097, 0.376147, 0.377880 |
| goh_targeting | 0.272727, 0.272727, 0.272727 | 0.272727, 0.272727, 0.272727 | 0.272727, 0.272727, 0.272727 |
| jump | 0.183206, 0.146801, 0.192090 | 0.156116, 0.124533, 0.161514 | 0.252719, 0.181089, 0.240741 |
| melee | 0.035294, 0.035503, 0.035398 | 0.035398, 0.035398, 0.035398 | 0.035398, 0.035398, 0.035398 |
| move_back | 0.030710, 0.015842, 0.019011 | 0.043924, 0.026846, 0.026490 | 0.066025, 0.037094, 0.042042 |
| move_forward | 0.000000, 0.000000, 0.013699 | 0.002350, 0.000000, 0.006309 | 0.013483, 0.014065, 0.008876 |
| move_left | 0.034853, 0.008197, 0.029650 | 0.029279, 0.025057, 0.022872 | 0.040816, 0.041943, 0.059024 |
| move_right | 0.009756, 0.023217, 0.016000 | 0.011396, 0.022315, 0.011429 | 0.040161, 0.044893, 0.033816 |
| simple_swing | 0.086093, 0.086093, 0.086093 | 0.086093, 0.086093, 0.086093 | 0.086093, 0.086093, 0.086093 |
| spider_power | 0.016077, 0.000000, 0.009901 | 0.025594, 0.014641, 0.016736 | 0.025316, 0.012903, 0.025042 |
| team_up | 0.346290, 0.342657, 0.350877 | 0.348432, 0.348432, 0.348432 | 0.348432, 0.348432, 0.348432 |
| ultimate | 0.347826, 0.347826, 0.347826 | 0.347826, 0.347826, 0.347826 | 0.347826, 0.347826, 0.347826 |
| web_cluster | 0.263069, 0.234759, 0.250429 | 0.176370, 0.128852, 0.214411 | 0.254767, 0.210247, 0.269291 |
| web_swing | 0.118380, 0.098418, 0.100503 | 0.117483, 0.107345, 0.096386 | 0.128767, 0.141026, 0.167320 |

**Evidence and transfer**

The new results folder contains the three reports, A reread, D/E .log/.exit, queue.status, queue.nohup, queue.zsh, A-reread.log, verify-cm2.json/.err, the six-line `mac-sha256-cm2.txt`, test logs and `reading.json`. The remote is `james`, Darwin arm64. Transfer used `ssh -n -T -o BatchMode=yes mac` and verified each copied small file against remote `shasum -a 256` before writing it locally. Only checkpoint digest text was copied, never .pt or .f32 data.

Transport limitation: SSH returned all required small files and six checkpoint digests, then stalled during supplemental queries for the old remote baseline/cache receipts. The 120-second timeout killed only this review's local SSH transport. Those supplemental remote queries are not claimed as completed; baseline identity was checked against the existing pinned local round-1 copy, and cache receipt identity against the pre-existing pin. No training, media reads, Mac writes/deletions or commits occurred. Local Python checks ran sequentially under the 2 GiB Windows Job limit. Judges were never edited.

This is repeatedly inspected old-build dev data, only three seeds and one rate per arm. No result here authorizes a real fit or deployment.

| Primary artifact | SHA-256 |
|---|---|
| runs/cm2-d-s012/report.json | 6695baa4efa105e0cd52d34e1fad2ffafbc47349faaa8196be0c4cb51cb03117 |
| runs/cm2-e-s012/report.json | 06feb07450319cacab07f8d780261a37299034fc86ae28baba034f94094c7000 |
| runs/interim94-s012/report.json | e8d955c0faa59937456ed91485d731781850e316a1892a9544d24c93f47938d5 |
| countermeasures2/A-reread.json | 8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9 |
| mac-sha256-cm2.txt | 637249e9b01fa44b17da1cd3c766de94b5ae13a613f25ff663f82b6b5c6694d1 |
| reading.json | 43e2a73eef8f0afe36dc2dabf2d40bd3263f99dbc92cb114a752474931df0db0 |

