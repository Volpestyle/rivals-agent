# scoreboard-fix: part C, rate-matched per-action thresholds on the four LOSO checkpoints (VUH-1353)

2026-09-24. This was run exactly as pre-registered in `idm-diag.md` ("The smallest pre-registrable change to test
next").
- **No retraining,** and nothing lands from this.
- **Mac:** inference only; 16 passes in 16 min, MPS, niced, code `1df31e7`.
- **PC:** the scoring, read-only.

## Method, as registered

1. **Threshold,** per fold and supported action: the probability quantile, over the fold's **own three train
   sessions'** known rows, at which the model fires at the train onset rate π_train (the top π_train share of rows
   fires). In `thresholds.py` every threshold is fixed before the held-out file is read.
2. **The abstention band is off.** Every known held-out row is answered: 1.0 if p ≥ threshold, else 0.0. So the
   positive count is every known onset, the fixed count.
3. **Scoring** uses the landed, reviewed `policy/idm_eval.py` (`b49aa26`). As a cross-check, the pre-fix module
   (`a84169c`, snapshot `idm_eval_head.py`) was run on the same predictions. The script asserts identical tp/fp/fn
   for every fold and action, and it passed.
4. **Chance-at-rate:** the same held-out rows fire at random at the model's held-out fire rate, with the mean F1 over
   **20 seeded draws**.
5. **Judge:** "signal" if model F1 − chance F1 ≥ **0.05** in **≥ 3 of 4 folds**, counting only folds where the action
   has **≥ 30 held-out onsets**. With fewer than 3 qualifying folds the verdict is "undecided".

## Verdicts

| Action | Verdict | Folds passing / qualifying |
|---|---|---|
| **jump** | **signal** | **4 / 4** |
| move_forward | no signal | 0 / 3 |
| move_left | no signal | 0 / 4 |
| move_back | no signal | 0 / 4 |
| move_right | no signal | 0 / 4 |
| web_swing | no signal | 1 / 3 |
| amazing_combo | no signal | 1 / 3 |
| spider_power | no signal | 0 / 3 |
| web_cluster | no signal | 0 / 4 |
| get_over_here | undecided | 0 / 2 |
| team_up | undecided | 0 / 2 |
| goh_targeting | undecided (supported in one fold only) | 0 / 0 |

## Per fold (the qualifying rows; the full table is in `thresholds-out.md`)

| Action | Held out | Onsets | π_train | Threshold | Fire rate | P / R | **F1** | Chance F1 (sd) | **ΔF1** | AUC |
|---|---|---|---|---|---|---|---|---|---|---|
| jump | 171533 | 88 | 0.0130 | 0.807 | 0.0097 | 0.156 / 0.159 | **0.157** | 0.042 (0.021) | **+0.116** | 0.844 |
| jump | 051828 | 361 | 0.0126 | 0.852 | 0.0093 | 0.133 / 0.086 | **0.104** | 0.052 (0.010) | **+0.053** | 0.733 |
| jump | 205528 | 487 | 0.0131 | 0.854 | 0.0134 | 0.265 / 0.292 | **0.278** | 0.063 (0.008) | **+0.215** | 0.845 |
| jump | 200129 | 1,250 | 0.0126 | 0.730 | 0.0111 | 0.124 / 0.106 | **0.114** | 0.059 (0.007) | **+0.055** | 0.729 |
| amazing_combo | 051828 | 60 | 0.0021 | 0.393 | 0.0017 | 0.048 / 0.033 | 0.039 | 0.009 | +0.030 | 0.797 |
| amazing_combo | 205528 | 82 | 0.0022 | 0.466 | 0.0029 | 0.070 / 0.098 | 0.082 | 0.014 | +0.067 | 0.828 |
| amazing_combo | 200129 | 212 | 0.0021 | 0.378 | 0.0015 | 0.021 / 0.014 | 0.017 | 0.009 | +0.008 | 0.781 |
| web_swing | 051828 | 83 | 0.0034 | 0.383 | 0.0039 | 0.071 / 0.084 | 0.077 | 0.019 | +0.058 | 0.631 |
| web_swing | 205528 | 135 | 0.0034 | 0.473 | 0.0043 | 0.035 / 0.044 | 0.039 | 0.022 | +0.017 | 0.626 |
| web_swing | 200129 | 330 | 0.0033 | 0.344 | 0.0021 | 0.015 / 0.009 | 0.011 | 0.012 | −0.000 | 0.633 |
| spider_power | 205528 | 156 | 0.0037 | 0.640 | 0.0028 | 0.071 / 0.051 | 0.060 | 0.012 | +0.047 | 0.622 |
| web_cluster | 205528 | 336 | 0.0076 | 0.603 | 0.0093 | 0.062 / 0.069 | 0.065 | 0.043 | +0.022 | 0.665 |
| move_left | 200129 | 735 | 0.0069 | 0.504 | 0.0047 | 0.031 / 0.019 | 0.024 | 0.030 | −0.006 | 0.531 |
| move_right | 051828 | 156 | 0.0057 | 0.365 | 0.0067 | 0.006 / 0.006 | 0.006 | 0.034 | −0.028 | 0.457 |

- **The movement keys** are at or below chance in every fold: ΔF1 from −0.028 to +0.032, AUC 0.46–0.58.
- **Get Over Here!, team_up and spider_power** never clear chance by 0.05, except spider_power on 205528 (+0.047,
  just short).

## Against the prediction registered in `idm-diag.md`

| Registered | Result |
|---|---|
| "F1 rises above chance-at-rate only where held-out AUC ≥ 0.7 (amazing_combo, jump, team_up)" | **Partly.** Jump rises in all 4 folds. amazing_combo (AUC 0.78–0.83 where it qualifies) rises in 1 of 3 only. team_up is undecided (2 qualifying folds, no gain). |
| "It stays ≤ 0.10 for every action" | **Wrong for jump.** Its F1 is 0.157, 0.104, **0.278** and 0.114, so the fixed-0.5 decision rule was hiding usable jump detections. For every other action it holds (≤ 0.082). |
| "The movement keys stay at chance" | **Holds.** |
| The implied reading: if the prediction holds, "the thresholds are not the lever: the input is" | **Split by action.** For jump, the threshold was a lever: F1 roughly doubles to quadruples over chance once the rule stops fighting the class prior. For everything else it isn't; the probabilities rank weakly (AUC 0.46–0.83) at base rates of 0.1–0.8 %, and no threshold turns that into detections. |

**My reading.**
- **Jump** carries visible evidence in the motion stack itself: the camera lifts within the ±8-interval window, and
  AUC is 0.73–0.85. Its failure at 0.5 was the decision rule.
- **The HUD-visible abilities** (combo, Get Over Here!, team_up, spider_power, web_cluster) have weak ranking and do
  not clear chance. This fits the earlier note that their HUD evidence lags the press by 0.1–1.9 s, while the head
  sees the HUD only at the interval's start and end.
- **The movement keys** carry no onset signal at all in these inputs.
- **The input change noted in `idm-diag.md` remains the lever for the non-jump actions.** It is HUD crops after the
  interval, which the stores hold up to +16 video frames. It is not proposed as a run here.
- **One caveat seen in the table:** the train-matched fire rate does not always transfer. For example, move_right on
  171533 fires at 0.026 against π_train 0.006. The held-out probability distribution shifts between sessions. That
  hurts precision and is part of what a threshold cannot fix.

## Files

**Scripts:**

| File | sha256 |
|---|---|
| Mac: `press_predict.py` | `f17c99bce151a781535955fbc95e00908527b2f98303065f5425c640cc52075a` |
| Mac: `press.zsh` | `ec9240849bf30070bec5d0462fbe93221bca515a1c469094ea326555bbee67a4` |
| PC: `thresholds.py` | `c88c08a3de38b8169724c339afe3416bd0bfd3ca7bb0eb17438839d927697e20` |
| PC: `idm_eval_head.py` (the pre-fix cross-check, `git show a84169c:policy/idm_eval.py`) | `bfb5e96ee70b046479d1d13318219799e35bf903b322164c605bba441303dc5a` |

**Outputs:**

| File | sha256 |
|---|---|
| `thresholds-out.md` (every fold and action) | `01ba21ff238f4adbb435d0f36082302501672d1be98de427dc704ef64daec6ee` |
| `thresholds-results.json` | `c6ba654ff93006576ab5f48dcf2cd96607ff3b7829a53d93eeb7a519e6378563` |

All are in `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\idm-diag\`.

**The 16 probability files** (`idm-diag\press\`, 100 MB; each checkpoint's sigmoid press probabilities per usable row).
All were hash-checked against the Mac.

| File | sha256 |
|---|---|
| `051828-on-051828.jsonl` | `2e9df1a147a80a51cb560ecf9a97283f9e3971db3cf352215d28583a5788cd4d` |
| `051828-on-171533.jsonl` | `d29e288c59581c201e7f155c9172a69919c4051f9c82e645ef8c8a3471a9822f` |
| `051828-on-200129.jsonl` | `b1d3c50368e62e15ac5be599e39bfdb9254cacfd334308e58ae641624e14af3b` |
| `051828-on-205528.jsonl` | `983962ca784442e5e54a1e8f22bbd2abea8b35d08fc74baf4adf35efc3483975` |
| `171533-on-051828.jsonl` | `b4d51fb50c9aeaf9e4f495dcf7a96fbec5380ab0c9b1aeaaf06f9d89fb4584e8` |
| `171533-on-171533.jsonl` | `aa34597439b12d6edbe4d2bce34cd2d145271fd3f31ad740b41a5402670b1f3b` |
| `171533-on-200129.jsonl` | `49963ee211d29edceb3f076f0379fc2d9a1be8e896e987de2a0e8fe85cb921eb` |
| `171533-on-205528.jsonl` | `40b56bb29c3fbb1c042824090a77b83a05e2829885988633f552789cc01cbaba` |
| `200129-on-051828.jsonl` | `aa7b2fe35075964a15f372c2c9c1ba891d7d40ebcb84e2e257223f73c8db020a` |
| `200129-on-171533.jsonl` | `ead6008f3c1538db213d27cd95897bf592d73d94d4fedbbf6f575667f1e47517` |
| `200129-on-200129.jsonl` | `21cd753b1810d44704c7839dae59a9d6d52e77938de1d80144c1f39151e75885` |
| `200129-on-205528.jsonl` | `eca5846d5b1306913708e12c8c7cd7746a47a2970c4eab49d87292a91d48a781` |
| `205528-on-051828.jsonl` | `a528f5d2afe7fc214dd5d1977cfe7dd4e15205252830c3bf620832901312125c` |
| `205528-on-171533.jsonl` | `14298fab49c8e6fdfdba1bbc0b3445de4595a2ad3382564b04bbe5832e372f00` |
| `205528-on-200129.jsonl` | `f0933616fd002297c04454a6d9a29ce85b76caf726278841cc2e9b6620eae5de` |
| `205528-on-205528.jsonl` | `9ae95e01822ac6495dfae6a7aa075bae51a8b535d1faae4e9e15964bd2a6b70d` |
