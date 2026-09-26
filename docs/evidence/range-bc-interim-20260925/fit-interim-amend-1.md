# fit-interim-amend-1 (VUH-1346, VUH-1359): multi-seed invocations after the seed-1 refusal

**Interim scaling-curve point, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**
Amends `fit-interim-prereg.md` (`8094bdd1…`). The shape is the lead's decision (brief `brief-hud-review-interim-relaunch.md`,
`f74e38ac…`); this file records the failure, checks the amendment is feasible, and fixes the relaunch. Not launched:
waiting for the lead's OK.

## What failed (facts, read on the Mac 15:59 CDT)

| Item | State |
|---|---|
| Queue 1 | `interim94/queue.zsh` (`a79e06b9…`), pid 31539, started 14:45:17. `queue.status` = `FAILED interim94-seed1`; no queue or `range_bc` process left |
| `interim94-seed0` | exit 0 at 15:51. `report.json` `a18e1f8e…`, `model_nohud-seed0.pt` `2d5183cb…`, `history_only-seed0.pt` `c939ce0f…`, log `0bbe86eb…`. The two checkpoint hashes equal the report's `checkpoints` entries. judge checks on it: none fail |
| `interim94-seed1` | exit 1 before training (log `6d3cc138…`, exit `4355a46b…`): `train.py` line 646, `require(0 in a.seeds, "seed 0 is the pre-declared candidate and must be trained")` → `FitError` |
| Cause | The pre-registration's "one invocation per seed, as the p5 runs were" was wrong on the facts. `run_fit` requires seed 0 in every invocation; the plumbing p5 runs were multi-seed (`plumb-p5-scale-1.00` has `seeds [0, 1]`, per-seed checkpoints). Nothing else failed |
| Contention | The IDM lane's MPS passes ran beside seed 0 from 15:27 (epoch 11 took +57 % wall time: 283 s and 376 s against about 240 s). Time only, not results. `idm-data/runs/resume-confirm.exit` now exists and no IDM process is running |

Local copies in `interim94/runs/` (hashes equal the Mac's): the seed-0 report, the seed-0 and seed-1 logs and exits.

## The amendment

1. **`interim94-seed0` stays exactly as it is** on the Mac: report, checkpoints, log, exit. The failed seed-1 log and exit
   too. Neither is modified or moved.
2. **Two invocations, `--seeds 0 1 2`, everything else as pre-registered** (train, dev, arms, recipe, parity file
   `e9efe999…`, code `code-5d2ec29`, caches of `verify-7.json`):
   - 94-minute group: train = the five sessions (80.53 counted min), out `runs/interim94-s012`;
   - control: train = 051828 + 200129 (33.59 min), out `runs/interim94-control47-s012`.
   - Order: 94-minute first, then control. So there are **two reports holding twelve checkpoints** (per arm and seed).
3. **The reading uses the per-seed figures of the two multi-seed reports** for all three seeds. `interim94-seed0` is
   the determinism check (below).
4. **Readings, rules (Closes / Reverses / Opens / Not resolved), dev, train sets and recipe: unchanged.**

## Feasibility, verified

**Per-seed figures.** The landed `docs/evidence/range-bc-plumbing-20260924/runs/plumb-p5-scale-1.00/report.json`
(`7d07ae9e…`, seeds [0, 1]) carries every figure the reading needs per arm and per seed; none is only aggregated:

| Figure | Where, per seed |
|---|---|
| dev total per epoch (so epoch 13, argmin epoch and minimum) and per head | `epochs_log["<arm>-seed<k>.pt"][i]["dev"]` |
| teacher-forced macro press-F1 and camera MAE | `metrics.dev.teacher_forced[<arm>]["<k>"].all.{macro_press_f1_tol, camera_mae_mean}` |
| checkpoint sha256 | `checkpoints["<arm>-seed<k>.pt"]` |
| ar2 and persistence baselines | `metrics.dev.teacher_forced.{ar2, persistence}.all`: model-independent, one per report |

The per-seed-invocation fallback (`--seeds 0 k`) is not needed.

**Seed independence in `train.py`** (read at `5d2ec29`; `policy/range_bc` is unchanged from there to `61b5b57`):
- the loop is arms outer, seeds inner: no-HUD seeds 0, 1, 2, then twin seeds 0, 1, 2;
- every `fit()` call re-seeds `random` and `torch` (`seed_everything`, deterministic algorithms), builds a fresh model
  and optimiser, and draws augmentation from its own `torch.Generator().manual_seed(seed)` and window order from
  `random.Random(seed * 1000003 + epoch)`;
- evaluation (`evaluate_set`) has no randomness and scores each model separately; the CPU reference is from
  `model_nohud` seed 0 in both runs;
- the checkpoint bytes are the model and fixed metadata (arm, seed, lag, regimes), with no time.

So seed 0 of `interim94-s012` should reproduce `interim94-seed0` exactly. **Unverified:** MPS kernels are not
guaranteed bitwise-deterministic across processes even under `use_deterministic_algorithms`. If they are not, the check
reports it as a finding with the differences; the reading still uses `interim94-s012`'s figures, and seed 0's spread
against `interim94-seed0` is stated, not averaged.

## The determinism check

`interim94-seed0` against `interim94-s012`'s seed 0, exactly:
- both seed-0 checkpoints' sha256 equal (`model_nohud-seed0.pt`, `history_only-seed0.pt`); at collection the Mac's
  `shasum` of each file also equals its report entry;
- the seed-0 epoch logs (dev and train loss per epoch, wall time excluded), teacher-forced, self-fed and sanity blocks,
  and the five baselines equal.

## Scripts

**`interim94/queue2.zsh`, sha256 `460ebb4870e154e35a9e5588e26105b2c3c52c1115080fd2712385dcfc55a687`**, the same bytes on the Mac
(`/Users/james/dev/range-bc-data/interim94/queue2.zsh`), `zsh -n` clean. Against `queue.zsh` it changes only:
- `--seeds $seed` becomes `--seeds 0 1 2`;
- two runs (`interim94-s012`, `interim94-control47-s012`) instead of six;
- its own status file `interim94/queue2.status`; one `.log` and `.exit` per run in `runs/`; stops at the first failure.

Neither out directory exists yet (`train.py` also refuses an existing one).

**`interim94/judge.py`, sha256 `bfab9d36425c278bc26390e5bf3061fce0a57d5103187a8e69dcd796981f8477`** (the original is kept as
`interim94/judge-v1.py`, `628c432e…`):
- reads `interim94-s012` and `interim94-control47-s012`, checks `seeds == [0, 1, 2]` and the rest of the unchanged
  checks, and also that every arm and seed has an epoch log and a teacher-forced block;
- extracts the reading's figures per arm per seed; the gaps, rules and recipe-health note are unchanged;
- adds the determinism check against `interim94-seed0` (which is also checked, with `seeds == [0]`);
- `--report <file> --group … --seeds …` checks one report and prints its per-seed figures.

**Re-tested** (`interim94/test_judge.py`, `c6523c64…`; all pass):

| Case | Result |
|---|---|
| p5 report, seeds [0, 1] | the figures equal an independent read of the raw report for both arms and seeds; no-HUD 1.6719, twin 1.6314, ar2 0.376°, persistence 0.418° as the plumbing record. Checks fail by design (epochs 20, stride 48, max_steps 1580, no parity, cohort) |
| p5 report, seeds [0, 1, 2] | 11 failures, including the seeds and the missing seed 2, reported instead of a crash (the first draft raised `KeyError`; fixed) |
| `interim94-seed0`, seeds [0] | figures equal the independent read; **no check fails** |
| constructed 3-seed report from `interim94-seed0` (wall time changed) | determinism equal; reading computed |
| the same with one checkpoint hash, one tf value (+1e-12) and one epoch dev total (+1e-12) changed | exactly those three differences reported, exit 1 |
| p5 against `interim94-seed0` | determinism differs, exit 1 |

**Noted, not a failure:** `interim94-seed0`'s ar2 camera MAE is 0.37623°, not the plumbing 0.37620°. ar2 is fitted on
train, which is now five sessions, so it moves slightly; it rounds to the pre-registered 0.376°. Persistence is
0.41827°, identical.

## Launch (after the lead's OK)

- Precondition met now: `idm-data/runs/resume-confirm.exit` exists, no IDM or `range_bc` process (15:59).
- From Git Bash, plain ssh with `ServerAliveInterval=15`: `nohup nice -n 10 zsh -l …/interim94/queue2.zsh`, then
  verify from `queue2.status` and the process, not from the launcher. Hand-back: `fit-interim-launch-2.md`.

**Expected wall time,** from `interim94-seed0`'s uncontended epochs (about 240 s per no-HUD epoch at 2,266 windows,
66 s per twin, 95 s evaluation for two models):

| Run | Estimate |
|---|---|
| `interim94-s012`: 3 × 52 min no-HUD + 3 min twin + about 5 min evaluation | about 2.75 h |
| `interim94-control47-s012` (about 945 windows) | about 1.2 h |
| Queue, if launched about 16:20 CDT | DONE about 20:15 CDT; more if the Mac is shared |

## Evidence for `docs/evidence/range-bc-interim-20260925/` (additions to the state file's list)

`fit-interim-amend-1.md`, `queue2.zsh`, both launch records (`fit-interim-launch.md`, `fit-interim-launch-2.md`), the
failed `interim94-seed1.log` and `.exit`, `interim94-seed0`'s report (the determinism reference), the adapted
`judge.py`. The six-report list becomes three reports: `interim94-s012`, `interim94-control47-s012`, `interim94-seed0`.
