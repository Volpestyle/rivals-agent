# fit-countermeasures-2-prereg (VUH-1346): round 2 against the known-idle absorbing state. Pre-registered, not launched

**A plumbing-scope test on dev, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**

- **Brief:** `brief-hud-review-countermeasures-2.md` (`99c96599…`), step 2.
- **Code:** `fit-countermeasures-2-code.md` plus fit-review's round-2 F1 fix (`fit-countermeasures-2-code-2.md`).
- **Draft:** for the lead's OK, which comes after fit-review's verdict on the fix. No run starts before both.

## The question

Round 1 (`fit-countermeasures.md`, `ee5f43b5…`) found neither countermeasure removes the self-fed collapse. The lead
accepted why: neither trains the absorbing state, a **known** all-idle history while the human acts.

Round 2 asks whether training on that state directly removes the idle and latched self-fed states while keeping the
executed teacher-forced skill. There are two ways:
- **D:** corrupting the history to known-idle;
- **E:** feeding the model's own closed-loop history.

**Prev dropout 0.5 is set aside** (the lead's decision). It feeds "unknown", not known-idle.

## Arms

Each arm changes one thing against A: its history option. Everything else is round 1's.

| Arm | What | Trained? |
|---|---|---|
| **A**, baseline | `interim94-s012`'s `model_nohud`, seeds 0-2, re-read on the new metrics: round 1's `A-reread.json` (`8a13a3fd…`), re-evaluated again with this round's code and required byte-identical | no |
| **D**, known-idle corruption | `model_nohud`, `--idle-corruption 0.5 --idle-run 8 48`, prev dropout 0.2 | yes, seeds 0, 1, 2 |
| **E**, sequential self-conditioning | `model_nohud`, `--self-roll 0.5 --self-roll-steps 32 --self-roll-ramp 0.5`, prev dropout 0.2 | yes, seeds 0, 1, 2 |

**Two invocations in one queue, D first, then E.** The code refuses two history options in one run. Both use:
- `--arms model_nohud` (no twin: the question is the candidate's self-fed behaviour);
- `--seeds 0 1 2`, the interim recipe (13 epochs, wd 1e-4, stride 64, lag 0, batch 8, lr 3e-4, regimes normal, MPS,
  plumbing);
- train: the five interim sessions (80.53 counted min); dev 171533 + 205528;
- parity `e9efe999…`;
- the seven caches re-verified against `verify-7.json`.

**Code:** a `git archive` of the commit the lead lands after fit-review's verdict, with its own venv.

## Why these settings (fixed now)

**D: P 0.5, runs of 8-48 steps.**
- The absorbing state is a sustained known-idle history. Self-fed, it starts at step 1 and never ends.
- A run of 8-48 steps (0.27-1.6 s) is long enough that the human often starts or holds an action inside it: the model
  sees "known idle" while the target says "act", and can only answer from the frames.
- **Coverage:** runs start in the scored part of the window (steps 32-95) and are clipped at its end, so a hit sequence
  loses a mean of 21.0 of its 64 scored steps. P 0.5 corrupts about **16 %** of scored steps.
- **Why not more:** 84 % of steps keep the true history, so hold continuation stays learnable.

**E: P 0.5, K 32, ramp 0.5.**
- 32 steps (1.07 s) is long enough for a closed-loop rollout to fall into the model's own idle or latched state. Round
  1's diagnosis shows the collapse happens within the first steps of a rollout.
- It is short enough to keep the start's state teacher-grounded.
- **Placement:** starts are uniform in [32, 63], so all 32 fed-back steps are scored (fit-review F1).
- **Coverage:** at full rate, half the sequences take the rolled history, about **25 %** of scored steps.
- **The ramp** (to 0.5 over the first half of the steps) keeps the early, untrained rollouts from dominating.

## Figures and the echo rule

**Exactly as round 1** (`fit-countermeasures-prereg.md`, `078d5351…`):
- S1-S4 from `self_fed_checks`, with S4 on the observable rows;
- T, the executed teacher-forced macro press-F1 (late 0; a one-step echo scores nothing);
- F, the self-fed macro press-F1 (±1 step);
- executed-TF press counts are never skill evidence.

**Reported, not judged:**
- `held_change_f1`;
- dev total and argmin epoch;
- the train-loss curve against A's (the cost of each option);
- whether any self-fed camera beats persistence (0.418°) or ar2 (0.376°);
- wall time per seed (E's rollout cost).

## Pass rules (unchanged from round 1, fixed before any run)

| Check | Pass when |
|---|---|
| S1 | `hold_onset_recall` ≥ **0.05** |
| S2 | pooled `press_ratio` in **[0.5, 2.0]** and ≥ **6 of the 10** live actions' `press_ratio` in [0.5, 2.0] |
| S3 | `camera_mae` ≤ **0.95 × `zero_motion_camera_mae`** (≤ 1.163° on this dev) |
| S4 | `any_hold_share` in **[0.5, 1.3] × `human_any_hold_share`** (observable rows; [0.35, 0.91] on this dev); fails if either is `None` |

- **An arm passes S:** at least **2 of 3 seeds** pass all four checks.
- **K:** `mean T(arm) ≥ mean T(A) − (range T(A) + range T(arm))`. A: T 0.045 / 0.028 / 0.033, mean 0.0351, range 0.0167.

## Outcomes, and what each means for the real fit

| Outcome | Condition | The real fit pre-registers |
|---|---|---|
| **Sanity failure** | A passes S | nothing; the metrics are wrong; stop |
| **D works** | D passes S and K; E does not pass both | every required arm (`model`, `model_nohud`, `history_only`) with `--idle-corruption 0.5 --idle-run 8 48` |
| **E works** | E passes S and K; D does not pass both | every required arm with `--self-roll 0.5 --self-roll-steps 32 --self-roll-ramp 0.5` |
| **Both work** | D and E pass S and K | the higher mean F. Within the two arms' combined F ranges, **D**: cheaper, with no rollout and no feedback loop in training |
| **Live but less skilled** | an arm passes S but fails K | **not adopted directly.** The rate trades liveness for skill, so round 3 tests that arm alone at half the rate (D P 0.25, or E P 0.25), same rules. If both arms land here, both at half rate. If the lead prefers to adopt it anyway, that is a separate, stated decision |
| **Neither works** | neither passes S | no real fit. Report the per-seed failures. Candidates for round 3, the lead's choice: the options at full rate (P 1.0); combining D and E (a code change, since the code refuses it today); a normalised frames-only arm (B seed 0's saturation says it needs it) |

**How this matches the draft:** the real-fit draft (`fit-real-prereg-draft.md`) keys its arm table to round 1's
outcomes. A D or E outcome here replaces its "C only" row with the same shape: all three required arms, with the
winning option.

## Checks on the reports (the judge extends round 1's `judge_cm.py`; tested on synthetic inputs before any D/E figure is read)

**Per report (`cm2-d-s012`, `cm2-e-s012`):**
- scope plumbing;
- config: epochs 13, wd 1e-4, stride 64, lag 0, prev dropout 0.2, arms [model_nohud], the arm's own option exactly as
  above and the other two null;
- seeds [0, 1, 2];
- parity `e9efe999…`;
- the interim cohort and step tables;
- test not opened;
- three checkpoints equal to the Mac files;
- `code_closure` equal to the landed files.

**A:** re-evaluated with the same code; every stored block and gate byte-identical.

## Run

- **How:** one durable Mac queue, as round 1: niced, a status file, a `.log` and `.exit` per run, stops at the first
  failure; no PC poll.
- **Order:** verify the caches, re-read A, then D, then E.
- **Expected:**
  - D: about 3 × 55-60 min, as A;
  - E: the rollout adds about 32 sequential recurrent steps per batch, estimated 3 × 80-110 min (measured at epoch 0
    and reported);
  - evaluation: about 5 min each;
  - total: **about 7-9 h**.
- **Hand-back:** `fit-countermeasures-2.md`.

## Limitations, known now

- **Dev only:** two runs, old build, read many times.
- **One P per arm and three seeds.** A near-miss is reported as such; the rules are not re-tuned.
- **D's corruption is one run per sequence.** The self-fed state is idle from step 1, far longer than 48 steps.
- **E rolls 32 steps from a teacher-grounded state,** not from a run's start.
- **Neither D nor E is combined with the other,** by design (one change per arm).
