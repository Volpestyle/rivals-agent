# fit-countermeasures-prereg (VUH-1346): do the countermeasures remove the copycat collapse? Pre-registered, not launched

**Amendment 1 (fit-review F1, 2026-09-25):** S4's shares are now defined on the rows where the human's any-hold label is observable, and S4 fails when a share is `None`. On this dev no row is excluded, so every number below is unchanged. The approved version is `fit-countermeasures-prereg-v1.md` (`de00d589…`).

**A plumbing-scope test on dev, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**
Brief `brief-hud-review-countermeasures.md` (`80aa1f23…`), step 4. Draft for the lead's OK, which comes together with
fit-review's verdict on `fit-countermeasures-code.md`. No run starts before both.

## The question

Does training against the history shortcut (arm C) or removing the history (arm B):
- remove the absorbing idle and latched self-fed states that `fit-selffed-diag.md` found,
- while keeping the executed teacher-forced skill?

The reading picks the arms and headline metrics the real fit pre-registers.

## Arms

| Arm | What | Trained? |
|---|---|---|
| **A**, baseline | `interim94-s012`'s `model_nohud`, seeds 0-2, re-read on the new metrics | no: its six stored checkpoints are re-evaluated with the reviewed code, as `repro_metrics.py` does |
| **B**, frames-only | `frames_only_nohud`: `history=False, hud=False`, the no-HUD candidate without the history input | yes, seeds 0, 1, 2 |
| **C**, self-conditioned | `model_nohud` with self-conditioned history, **p = 0.5, ramp = 0.5** (the rate rises linearly to 0.5 over the first half of the steps, then holds), prev dropout 0.2 | yes, seeds 0, 1, 2 |

**One invocation trains B and C.** The self-conditioning option is a no-op for a model without a history input: the
reviewed test shows a `history=False` model trains byte-identically with it on and off. So both come from one report
`runs/cm-s012`:

```
uv run --offline --locked --group execution python -m policy.range_bc.train --scope plumbing --device mps \
  --cache-root $K --batch 8 --lr 0.0003 --regimes normal \
  --train $S/<051828> $S/<200129> $S/<232304> $S/<021320> $S/<025230> --dev $S/<171533> $S/<205528> \
  --arms model_nohud --frames-only-nohud --self-condition 0.5 --self-condition-ramp 0.5 --prev-dropout 0.2 \
  --seeds 0 1 2 --epochs 13 --weight-decay 0.0001 --stride 64 --lag 0 \
  --hud-parity $I/hud-parity-1-p2.json --out $R/cm-s012
```

**Recipe:** the interim recipe, unchanged except for the self-conditioning:
- 13 epochs, wd 1e-4, stride 64, lag 0, batch 8, lr 3e-4, regimes normal, MPS, plumbing scope;
- train: the five sessions (80.53 counted min); dev: 171533 + 205528;
- the seven caches of `verify-7.json`.

**Code:** the reviewed code, as a `git archive` of the commit the lead lands (or `cf25505` plus the reviewed files,
hashes recorded) with its own venv, like `code-cm`.

**Why these choices:**
- **p = 0.5:** a model that sees its own action at half the steps must learn to act from frames when its fed history
  is wrong.
- **Prev dropout stays 0.2:** C changes one thing against A, so a pass is attributable. Raising the dropout (the
  diagnosis's other suggestion) is the follow-up if C fails.
- **No twin:** the question is the candidate's self-fed behaviour, not the HUD.

## Figures (all on dev, from each report's new blocks)

Per arm and seed:

| Figure | Source |
|---|---|
| **S1** self-fed hold-onset recall, pooled over live actions | `self_fed_checks.hold_onset_recall` |
| **S2** executed against human presses per live action | `self_fed_checks.actions[*].press_ratio` (all 10 live actions have ≥ 42 true presses on dev) and the pooled `press_ratio` |
| **S3** self-fed camera MAE against zero motion | `self_fed_checks.camera_mae` against `zero_motion_camera_mae` (1.2246° on this dev) |
| **S4** self-fed share of steps with any live hold on, against the human's, on the rows where the human's any-hold label is observable (a live hold known held, or every live hold known released; fit-review F1) | `any_hold_share` against `human_any_hold_share` (0.699 on this dev; all 24,556 valid rows are observable, `any_hold_excluded_steps` 0) |
| **T** executed teacher-forced macro press-F1 | `executed_teacher_forced.macro_press_f1_tol` |
| **F** self-fed macro press-F1 (tolerance ±1 step) | `self_fed.<arm>.<seed>.all.macro_press_f1_tol` |

Also reported, not judged: executed-TF and self-fed `held_change_f1` per action, executed-TF camera MAE, and the
existing teacher-forced figures.

## How the one-step executed echo is read (fixed now)

**What it is.** Under teacher forcing, the decode's hold follows the true previous hold. So a model that copies the
history executes the human's presses exactly one step late. On `interim94-s012` no-HUD seed 0, move_right is 250
executed against 250 true, and jump 593 against 575.

**The rule:**
1. **T keeps the teacher window, late 0.** A press executed after the true press, with the true action already in the
   input, is an echo and scores nothing (F2). T is therefore the skill a policy shows by pressing **at or one step
   before** the human. It is the only teacher-forced skill figure used in the reading.
2. **Executed-TF press counts and rates are not skill evidence.** A ratio near 1 is expected from echo alone; they are
   reported, never judged.
3. **Self-fed figures use the self-fed window (±1 step).** There is no true history in the input, so a one-step-late
   press is not an echo there. F and S2 read it as timing error within tolerance.
4. **Like-for-like.** B has no history, so it cannot echo. Its T and A's and C's T are all late-0 figures on the same
   dev, so comparing them is fair.

## Pass rules (fixed now, before any run)

**A seed passes self-fed (S)** when all four hold:

| Check | Pass when | Catches |
|---|---|---|
| S1 | `hold_onset_recall` ≥ **0.05** | idle (A: 0-0.003) |
| S2 | pooled `press_ratio` in **[0.5, 2.0]** and at least **6 of the 10** live actions have `press_ratio` in [0.5, 2.0] | idle (A: ≤ 0.001), latched, over-pressing (the sampling probe: up to 6×) |
| S3 | `camera_mae` ≤ **0.95 × `zero_motion_camera_mae`** (≤ 1.163° on this dev) | a still camera (A: 1.2246-1.2290) |
| S4 | `any_hold_share` in **[0.5, 1.3] × `human_any_hold_share`** ([0.35, 0.91] on this dev); fails if either share is `None` (no observable rows) | idle (0) and latched (1.0, twin seed 2) |

- **An arm passes S** when at least **2 of its 3 seeds** pass.
- **An arm keeps executed skill (K)** when `mean T(arm) ≥ mean T(A) − (range T(A) + range T(arm))`, over its three
  seeds. Not being worse than the copycat baseline by more than the seed spread is the bar here; beating it is not
  required.

**Where the numbers come from:**
- 0.05 is about the diagnosis's history-blanked probe (5.6 %) rounded down;
- [0.5, 2] and the any-hold band are the diagnosis's proposal, fixed to the human figures above;
- 0.95 avoids a pass by rounding noise on a near-still camera.

## Outcomes, and what each means for the real fit

| Outcome | Condition | The real fit pre-registers |
|---|---|---|
| **Sanity failure** | A passes S | Nothing. The metrics are wrong; stop and report |
| **C works** | C passes S and K; B does not pass both | the candidate arm(s) with self-conditioned history (p 0.5, ramp 0.5), headline = S (as the gate) plus T and F |
| **B works** | B passes S and K; C does not pass both | frames-only no-HUD as the candidate (no history input), same headline |
| **Both work** | B and C pass S and K | the arm with the higher mean F. Within the two arms' combined F ranges, **B**: no feedback path, so no absorbing state is possible |
| **Neither works** | neither passes S and K | no real-fit arms from this test. Report which checks failed per seed. Candidates for the next test, in order: prev dropout 0.5 with C, sequential self-conditioning, a stochastic decode with train-fixed thresholds. The lead decides |

**Also reported and not acted on:**
- whether any arm's self-fed camera beats persistence (0.418°) or ar2 (0.376°);
- each arm's argmin epoch;
- C's train-loss curve against A's (the cost of self-conditioning).

**Known before this pre-registration**, and so not evidence for any rule:
- A's figures on the new metrics (`countermeasures/repro-metrics-interim94-s012.json`, computed during the code
  proofs): T 0.045 / 0.028 / 0.033; S fails every check on every seed.
- The thresholds were set from the diagnosis and the human dev figures, not from any B or C output; none exists.

## Checks on the report (a judge script, written after the review and tested before the run)

- scope plumbing;
- config: epochs 13, wd 1e-4, stride 64, lag 0, `prev_dropout` 0.2, `self_condition` `{p 0.5, ramp 0.5, rule}`,
  arms [model_nohud, frames_only_nohud];
- seeds [0, 1, 2];
- parity `e9efe999…`;
- the interim cohort and step-table hashes;
- `test_opened` false;
- each checkpoint's Mac sha256 equals the report;
- `code_closure` hashes equal the reviewed files.

A is re-evaluated with the same code, and its stored blocks are shown byte-identical first, as in proof (a).

## Run

- **Where and how:** on the Mac after the lead's OK, one durable queue: `nohup nice -n 10 zsh -l …`, a status file,
  and a `.log` and `.exit`.
- **Start:** only when nothing else of ours runs there.
- **Monitoring:** no background poll on the PC; the lead wakes me.
- **Expected about 5.5-6 h:**
  - C: 3 × about 55 min (the self-conditioning adds one recurrent pass per step);
  - B: 3 × about 52 min (the same encoders as no-HUD);
  - evaluation about 5 min;
  - A's re-evaluation about 5 min.
- **Hand-back:** `fit-countermeasures.md`, with the table per arm and seed, the rules' result, the outcome, hashes and
  limitations.

## Limitations, known now

- **Dev only:** two runs, old build, plumbing scope. It is the same dev as the interim and diagnosis, now read
  several times, though never used to fit.
- **C is the one-step approximation** (`fit-countermeasures-code.md`, open point 1). A C failure does not rule out
  sequential self-conditioning.
- **Three seeds and one p.** A near-miss is reported as such; the rules are not re-tuned after the fact.
- **S3 is a weak camera bar:** 0.95 × zero motion is still far worse than ar2.
