# fit-countermeasures (VUH-1346): neither countermeasure removes the self-fed collapse

**A plumbing-scope test on dev, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**

- **Pre-registration:** `fit-countermeasures-prereg.md` (`078d5351…`, amendment 1).
- **Launch:** `fit-countermeasures-launch.md` (`2b58bd94…`).
- **Code:** a `git archive` of `807d35f`.
- **Run:** queue 22:37:56 → **DONE 05:46:51 CDT**, 2026-09-26; `cm-s012` exit 0.
- **Reading:** `countermeasures/reading-cm.json` (`50378f03…`), by `countermeasures/judge_cm.py` (`6f77e938…`), exit 0,
  no check failures.

## Outcome: **Neither works**

**No seed of any arm passes a single self-fed check** (S1, S2, S3 or S4). No arm passes S, so K and the both/tie rule
never decide anything.

**A does not pass S,** so the metrics are not the problem. The sanity row is clear.

**For the real fit:** by the pre-registered table (the countermeasures pre-registration and `fit-real-prereg-draft.md`
row "Neither"), **no real fit is launched on these arms**. The pre-registered next candidates, in order:
1. C with prev dropout 0.5, your standing first choice;
2. sequential self-conditioning;
3. a stochastic decode with train-fixed thresholds.

**You decide.** The corpus (180.57 train min, `b8f48ed`) is ready and waits on that choice. My reading of what the data
suggests for it is at the end, marked as inference.

## Per arm: T, F and K

| Arm | T (executed TF macro press-F1), seeds 0/1/2 | T mean (range) | F (self-fed macro press-F1), seeds 0/1/2 | F mean | Passes S | K (T mean ≥ bar) |
|---|---|---|---|---|---|---|
| **A** interim no-HUD, re-read | 0.045 / 0.028 / 0.033 | 0.0351 (0.0167) | 0 / 0 / 0 | 0 | no (0 of 3 seeds) | (baseline) |
| **B** `frames_only_nohud` | 0.000 / 0.047 / 0.043 | 0.0300 (0.0470) | 0 / 0.066 / 0.090 | 0.052 | no (0 of 3) | yes (bar −0.029) |
| **C** self-conditioned no-HUD | 0.051 / 0.048 / 0.057 | **0.0519** (0.0094) | 0.003 / 0.001 / 0.005 | 0.003 | no (0 of 3) | yes (bar +0.009) |

## Per seed: the self-fed checks (all fail)

Dev: 24,556 valid rows, all observable; human any-hold share 0.699; camera bar 0.95 × 1.2246° = 1.163°.

| Arm/seed | S1 onset recall (≥ 0.05) | S2 press ratio, actions in band (0.5-2; ≥ 6/10) | S3 camera (≤ 1.163°) | S4 any-hold (0.35-0.91) |
|---|---|---|---|---|
| A 0 / 1 / 2 | 0 / 0 / 0.003 | 0.000, 0 / 0.000, 0 / 0.001, 0 | 1.225 / 1.225 / 1.229 | 0.000 / 0.002 / 0.053 |
| B 0 | 0 | 0.000, 0 | 1.225 | 0.000 |
| B 1 | 0.021 | **1.184**, 2 | 1.214 | 0.190 |
| B 2 | 0.023 | **0.941**, 2 | 1.209 | 0.187 |
| C 0 / 1 / 2 | 0.0004 / 0 / 0.002 | 0.004, 0 / 0.002, 0 / 0.008, 0 | 1.243 / 1.225 / 1.236 | 0.011 / 0.006 / 0.014 |

**B's two live seeds pass the pooled press ratio but not the per-action band.** Their presses are almost all taps.
B seed 2, executed against true presses:

| Action | Executed / true |
|---|---|
| jump | 751 / 575 |
| spider_power | 487 / 180 |
| web_cluster | 862 / 384 |
| web_swing | 170 / 160 |
| move_forward | 43 / 248 |
| other movement | 0 |
| amazing_combo, get_over_here | 0 |

## Context (reported, not judged)

| Arm | Dev total, epoch 13, seeds 0/1/2 | Argmin epoch | TF camera MAE | Train loss, last |
|---|---|---|---|---|
| A | 1.314 / 1.315 / 1.310 | 13 / 13 / 12 (interim) | 0.595 / 0.586 / 0.583 | 1.338 / 1.357 / 1.333 |
| B | **2.387** / 2.205 / 2.156 | 9 / 13 / 13 | 1.225 / 1.214 / 1.209 | 2.457 / 2.173 / 2.175 |
| C | 1.441 / 1.434 / 1.425 | 13 / 12 / 13 | 0.681 / 0.678 / 0.661 | 1.580 / 1.581 / 1.565 |

- **B seed 0 never trained.** Its dev total stayed at 2.385-2.404 for all 13 epochs, the untrained level, and its
  train loss went flat at 2.46 after epoch 0.
  - Seeds 1 and 2 only began to fall at epochs 2-3 and ended at 2.16-2.21, far above A's 1.31, still falling.
  - Without the history input, this recipe (13 epochs, lr 3e-4, 500-step warmup) underfits badly, and one seed sat
    on the prior.
  - Per the rules this is just a failing seed. B's seeds 1 and 2 fail every check anyway.
- **Self-conditioning cost teacher-forced fit:**
  - dev total 1.43-1.44 against A's 1.31;
  - TF camera 0.66-0.68° against 0.58-0.60°;
  - but executed T rose from 0.035 to 0.052.
- **No arm's self-fed camera beats persistence (0.418°) or ar2 (0.376°).** All are at or above zero motion.

## What the data suggests for the next test (inference, not part of the pre-registered reading)

**1. One-step self-conditioning barely changes the model's history input.**
- The "own" previous action is decoded from a pass fed with the **true** history. Teacher-forced, the model's decode
  echoes the human one step late (executed presses equal the human count, `fit-countermeasures-code.md`).
- So C's replacement is mostly the human's action one step earlier: a lagged copy of the truth, not the model's own
  idle state. It never trains on "known idle while the human acts", the absorbing state the diagnosis found.
- C self-fed is as collapsed as A (onset ≤ 0.24 %, any-hold ≤ 1.4 %).
- **This explains the null result.** It is an inference from the echo measurement, not separately measured.

**2. Prev dropout 0.5 (the standing first candidate) blanks history to "unknown"** (known bit 0). That is not the
self-fed input either: self-fed feeds a *known* all-idle vector.
- The diagnosis's history-blanked probe (F1 0.079) shows the unknown condition is less absorbing.
- The live collapse is in the known-idle state, which dropout also never trains.
- **A targeted alternative:** corrupt the history to known-idle (or to the model's sequential rollout) at a declared
  rate. That is sequential self-conditioning, the second candidate, or a new "known-idle corruption" option.

**3. Frames alone carry tap timing but not holds or camera.**
- B's live seeds pressed jump, spider_power, web_cluster and web_swing at close to the right counts, and started almost
  no movement.
- A frames-only candidate would need more training than this recipe, and still lacks the hold state.

**4. My suggested order** for your decision: sequential self-conditioning or known-idle corruption ahead of dropout 0.5.
The data above says dropout 0.5 targets the wrong state. The pre-registered order lists dropout 0.5 first; the choice
is yours.

## Hashes (Mac `shasum -a 256` = local `sha256sum` for every copied file)

| File | sha256 |
|---|---|
| `runs/cm-s012/report.json` | `82adfc7ea730bd1fe6e074a061e163f116848e2d927cc6013b3c0898bc4d6528` |
| `runs/cm-s012.log` | `e3b03473a426006c08ad7dc939d4261807ab992984b400eefde5922d597233a6` |
| `runs/cm-s012.exit` (0) | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `A-reread.json` (arm A) | `8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9` |
| `verify-cm.json` (the seven caches, byte-identical to `verify-7.json`) | `d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7` |
| `queue.zsh` | `0093fc05f88c0664b482876282eb8a2a01bf86b1dca60df76debd15287cf5a65` |

**Checkpoints:** Mac sha256, each equal to its report entry (checked by the judge). They stay on the Mac.

| Checkpoint | sha256 |
|---|---|
| `frames_only_nohud-seed0.pt` | `2ec481ec012390f666630c226930135c6df82fd700c3470bfcb7f47cb8b43b36` |
| `frames_only_nohud-seed1.pt` | `0c0e5fcb708d8994f51e91923a6325822dfcb900523eccfd9cd5369124452d74` |
| `frames_only_nohud-seed2.pt` | `33d753be5f0f751432d1ac2805641d3310a671fd7b84cd26ca5a2f7f18aa2fe1` |
| `model_nohud-seed0.pt` (C) | `b7ac6edb8d4b5b0a320a4f2868dae3472ba7c513f537da94acb7203aafee809c` |
| `model_nohud-seed1.pt` (C) | `1c85b6996c47cc5eb0940a1699960d103320c7a4abd4e718eb2a6083ad032378` |
| `model_nohud-seed2.pt` (C) | `e61fa007dd14cf9b3980a0a6c793f98f726a7a5ea41f303fc2cf6e6ee7f0ae59` |

**The judge's report checks all pass:**
- scope plumbing;
- config: 13 epochs, wd 1e-4, stride 64, lag 0, prev dropout 0.2, self-conditioning p 0.5 / ramp 0.5, arms
  [model_nohud, frames_only_nohud], train fraction 1, no max steps;
- seeds [0, 1, 2];
- parity `e9efe999…`;
- the interim cohort and step tables;
- test not opened;
- six checkpoints equal to the Mac files;
- `code_closure` of `train.py` and `metrics.py` equal to the reviewed `dbfd8b1d…` / `ff8ec178…`;
- A's re-read byte-identical on every stored block.

**Judge tested before any B/C figure was read:** `countermeasures/test_judge_cm.py` (`a5f09d3d…`), 14 synthetic cases
built from A's data, all pass. They cover:
- each outcome row (neither, B, K loss, both with the F rule and the tie, one-seed C, A passing);
- every S boundary;
- config and code-closure mismatch detection.

## Proposed evidence folder (`docs/evidence/range-bc-countermeasures-20260926/`)

- **Documents:** `fit-countermeasures-prereg.md` (`078d5351…`) and `-v1.md` (`de00d589…`),
  `fit-countermeasures-code.md` and `-code-2.md`, `fit-countermeasures-launch.md`, this file.
- **Scripts:** `countermeasures/queue.zsh`, `repro_metrics.py`, `judge_cm.py`, `test_judge_cm.py`.
- **Outputs:** `verify-cm.json`, `A-reread.json`, `reading-cm.json`, `mac-sha256-cm.txt`, `runs/cm-s012/report.json`,
  `runs/cm-s012.log`, `.exit`.
- **Checkpoints stay on the Mac,** pinned by the hashes above.

## Limitations

- **Dev only:** two runs, old build, plumbing scope.
- **Three seeds, one p.** The result is not near any bar: no seed passes any check.
- **B seed 0 never trained.** Even without it, B fails every check.
- **C is the one-step approximation.** Its null result speaks to that implementation, not to sequential
  self-conditioning (see inference 1).
- **Contention:** an Xcode build and simulator, and my G1 test runs, shared the Mac. That affected wall time only.
