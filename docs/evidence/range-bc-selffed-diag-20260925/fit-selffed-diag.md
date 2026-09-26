# fit-selffed-diag (VUH-1346): why self-fed rollouts are degenerate

Brief `brief-hud-review-selffed-diag.md` (`a14d11af…`). Inference only, no training.

**Checkpoints:** `interim94-s012`'s seed-0 `model_nohud` (`2d5183cb…`) and `history_only` (`c939ce0f…`).

**Dev:** 171533 + 205528, loaded exactly as `run_fit` does. That gives **two runs, 4,630 and 19,926 steps** (24,556
scored).

**The probe:** `selffed/diag.py`. It computes frame features once (MPS for no-HUD), then steps the recurrent part on
the CPU under six previous-action feeds.

**Reproduction check.** Its `tf` and `sf` modes reproduce the report exactly:

| Arm | Teacher-forced F1 / camera MAE | Self-fed F1 / camera MAE |
|---|---|---|
| no-HUD | 0.1783 / 0.5953° | 0 / 1.2246° |
| twin | 0.1431 / 0.5737° | 0 / 1.2246° |

## Finding

**A model property, not an evaluation bug.** The models learned to continue the previous action, not to start one.
Self-fed from an idle start, "nothing held, no camera motion" is an absorbing state:
- the model never raises a hold or a camera motion from it;
- the executor's decode never executes the presses it does predict.

**1. Teacher-forced competence is continuation.** Measured on the true labels, with the true previous action as input:

| | no-HUD | twin | Human |
|---|---|---|---|
| Hold continues (true previous held → `held_p ≥ .5`) | 93.4 % | 95.7 % | |
| Hold starts from idle (true onsets: previous not held, now held; n = 2,453) | **2.0 %** recalled, mean `held_p` 0.097 | **0.5 %**, mean 0.058 | hazard 1.1 % per idle step-action |
| Camera: previous yaw zero → predicts non-zero | 2.2 % | 1.8 % | 22 % of such steps start moving |
| Camera: previous yaw moving → predicts non-zero | 92.7 % | 94.0 % | |

- The hold figures look good (`held_balanced_accuracy` 0.96 on `move_forward`) only because the model copies the
  input. `held_change_f1` is 0.00-0.04 on all four movement actions.
- The camera is moving in 77 % of dev steps. The model tracks it by copying: it repeats the previous class exactly in
  40 % of those steps, and almost never starts it.

**2. Self-fed, the idle state is absorbing** (no-HUD; the twin is the same or lower):

| Steps into the run | 0 | 1-29 | 30-299 | 300-2,999 | 3,000+ |
|---|---|---|---|---|---|
| mean of max live `held_p` | 0.40 | 0.034 | 0.040 | 0.045 | 0.046 |
| peak live `held_p` | 0.40 | 0.21 | 0.26 | 0.33 | 0.48 |
| mean P(yaw = zero class) | 0.20 | 0.89 | 0.84 | 0.84 | 0.82 |
| steps with the median yaw class non-zero | 0 | 0 | 0 | 0 | 0 |

- **Step 0** is fed `prev_vector(None)` (known = 0). From step 1 on, it is fed a *known* all-idle action. `held_p`
  collapses by 10× at once and never recovers: **no hold crosses 0.5 in 24,556 steps**. The yaw median is the zero
  class from step 1 on, so the camera equals zero motion (1.2246°).
- **The answer to the brief's question:** the probabilities never rise. They do not sit just under the threshold, and
  do not decay slowly; the collapse is immediate. They are highest at step 0, before any history exists.

**3. The decode also discards what the model does predict.**
- Self-fed no-HUD still has `press_p ≥ .5` on 1,602 step-actions (peak 0.94).
- `executor.decode_step` executes a press only as a rise of `held` or as a tap (press and release both ≥ .5). A lone
  press probability is dropped, so **0 presses are executed**.
- The teacher-forced press-F1 counts exactly those lone press probabilities. So the pre-registered TF press-F1
  (0.178 no-HUD, the basis of the interim "Opens") **scores a signal the executor never acts on**. It is also
  over-predicted: jump has 3,516 predicted presses against 575 true.

## Probes that locate the cause (no-HUD / twin; F1 = macro press-F1 tol, camera MAE in degrees)

| Feed | What it tests | no-HUD F1 / camera | twin F1 / camera | Behaviour |
|---|---|---|---|---|
| `tf` | true history | 0.178 / 0.595 | 0.143 / 0.574 | reproduces the report |
| `sf` | the executor's own actions (live) | 0 / 1.225 | 0 / 1.225 | absorbing idle |
| `unknown` | history blanked every step (known = 0: the 20 % prev-dropout condition) | **0.079** / 1.238 | 0 / 1.230 | no-HUD acts from frames: hold-onset recall 5.6 %, yaw non-zero 30-42 %. The twin has no input left, so its output is constant |
| `presshold` | self-fed, `press_p ≥ .5` also opens a hold | 0.034 / 1.225 | 0 / 1.225 | holds start, then **latch**: some hold stays on in 99.6-100 % of steps after step 300. The camera stays zero |
| `sample` | self-fed, holds and camera classes sampled (seed 0) | 0.077 / 1.891 | 0.039 / 2.049 | leaves the idle state but over-presses up to 6× (2-3× on movement; spider_power 1,120 against 180 true). Camera worse than zero motion |
| `warm30` | true history for 30 steps, then self-fed | 0.002 / 1.229 | 0.001 / 1.382 | locks into whatever state step 30 held: one run idle forever, the other latched. The no-HUD camera decays to zero; the twin's latches non-zero |

**What the probes show:**
- **The cause is the fed-back history.** With the same weights and frames, blanking the history (`unknown`) gives the
  no-HUD arm non-zero F1 and onsets. Feeding it its own idle history gives zero.
- **The threshold alone is not the cause.** Opening holds on press (`presshold`) trades "never start" for "never stop":
  the same copy dynamics in the other direction.
- **Sampling alone is not a fix.** It gives activity with no timing: executed presses at up to 6× the human rate, and
  camera error above zero motion.
- **The self-fed path is not buggy.** It implements what the live executor would send. The rollout code reproduces the
  report to four decimal places, and the other feeds through the same path give non-trivial, feed-dependent outputs.

**Checked in the code.**
- `predict_self` feeds `prev_vector(sent)`: executed bits, known = 1, and the saturated camera class.
- That is the live executor's contract, and in training `prev` is the human's recorded step.
- The only training exposure to anything else is `prev_dropout = .2`, which zeros the whole vector including the known
  bit. The model therefore never sees "known idle while it should act", nor its own errors.

This is the classic imitation-learning copycat, or causal-confusion, failure. The previous action predicts the next
one far better than the frames do (the hold continues 93-96 % of the time; the onset hazard is 1.1 %). So the history
pathway dominates, and nothing in training penalises failing to start.

## Pre-registerable changes for the real fit

1. **Train against the history shortcut, and read it self-fed.** Two arms beside the candidate, same recipe:
   - **frames-only** (`history=False`; `--frames-only` already exists in `train.py`). It has no feedback path, so
     self-fed equals teacher-forced by construction.
     - Tests whether the frames alone carry initiation.
     - Lower bound from this checkpoint: the `unknown` probe, F1 0.079 and hold-onset recall 5.6 %.
   - **self-conditioned history** (scheduled sampling). During training, replace the previous-action input with the
     model's own decoded previous action. The rate ramps from 0 to a pre-declared p (for example 0.25 → 0.5 over the
     schedule). Also raise `prev_dropout` to about 0.5.
     - Tests whether exposure to its own actions removes the absorbing idle and latched states while keeping the
       history's value.
     - Needs a `train.py` change and a changed-boundary review.

   **Judged on self-fed dev figures, pre-declared:**
   - hold-onset recall > 0 (target ≥ the `unknown` probe's 5.6 %);
   - executed presses per live action within 0.5-2× the human count;
   - camera MAE below zero motion (1.2246°);
   - no latched state (share of steps with any hold on, within ±50 % of the human share).

2. **Make the headline metric an executed one.** Pre-register a teacher-forced press-F1 computed on
   `executor.decode_step` applied to the teacher-forced probabilities, replacing (or reported beside) the probability
   F1. It tests the same decisions the pad would send.
   - Report `held_change_f1` beside `held_balanced_accuracy`, so copying cannot read as competence.
   - The interim "Opens" should be re-read on it before it informs the real fit's design.
   - Decode variants (press-opens-hold, sampling, per-action thresholds) belong after change 1, with thresholds fixed
     from train statistics, never from dev. On this checkpoint none fixes the collapse on its own.

## Limitations

- **One checkpoint per arm** (seed 0, 80.5-minute group). The report's self-fed block shows the same zero for all seeds
  in both groups and in plumbing. The per-step profile is only measured here.
- **Two dev runs.** The position bins before step 300 are two runs' first steps. The `warm30` "0.5" rows are one run
  idle and one latched, not a population.
- **The onset, profile and probe metrics are mine, defined in `diag.py`, not pre-registered.** The probes are
  diagnostics, not candidate policies. `sample` uses one seed.
- **Step on CPU, features on MPS.** The `tf` and `sf` figures equal the report's to four places, so the device
  difference does not matter here.
- **The recommendations are untested.** Change 1 needs training and code review. The `unknown` probe is only indicative for frames-only: this model saw blank history in 20 % of
  training steps, and a model trained without history at all could do better or worse.

## Artifacts

| File | sha256 |
|---|---|
| `selffed/diag.py` | `f8c7bd9a77d5224c72fe74126dad7a04719cb87e2b69de6259245435dd941789` |
| `selffed/diag-model_nohud.json` | `465bfe87b16c680d217be13440e3c4ef6fc0e8ec29b2a20fa9d4fbabfd76211c` |
| `selffed/diag-history_only.json` | `b262f736bde4867acb66453d6461c531939be600e2a6819b93afed9ebb40ed2a` |

- The same bytes are on the Mac in `/Users/james/dev/range-bc-data/selffed-diag/`.
- It was run as `cd code-5d2ec29 && PYTHONPATH=. nice -n 10 .venv/bin/python …/diag.py --arm <arm> --out … --device mps|cpu`,
  about 30 s per arm.
- Nothing in `runs/` or `idm-data` was touched. No checkout edits, commits, Linear or game input.
