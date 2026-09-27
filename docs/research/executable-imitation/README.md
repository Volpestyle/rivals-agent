# Research candidate: imitation with execution-aware memory and expiring goals

## State at pause (2026-09-26)

Paused under the [steering charter](../../steering/charter-20260926.md): this
event-timing track has not demonstrated a contribution to the live gameplay loop.

- **Established:** exact paired event-F1 reference and frontier solvers pass
  exhaustive checks; archived B0 timing bounds favor the median baseline on
  both retained development folds. Two history-only seeds reproduce their
  archived metrics on 24,556 development steps. Under controlled two-step
  command-label coarsening, paired bounds resolve 7/27 comparisons versus 6/27
  for separate bounds; all 108 comparisons across four widths contain the
  known-label difference. These are offline diagnostics, not gameplay results.
- **Open:** publication novelty, natural cast-effect evaluation, annotation-cost
  savings and current-policy improvement. The 35 development HUD ammo decreases
  remain unvalidated candidates. The original recording's full hash matches;
  no endpoint decoding or new label admission was performed. Do not resume that
  inspection automatically when the unrelated video job finishes.
- **Artifacts:** research scripts and result notes live in this directory,
  including `frontier_event_bounds.py`, `history_command_export.py` and
  `command_coarsening_pilot.py`. Local copied archives, checkpoints, development
  tables and prediction exports were moved outside the shared checkout to
  `C:/Users/volpe/AppData/Local/Temp/codex-rivals-research-20260926-01a0e006/research-executable-imitation/`
  (subdirectories `b0-metadata/` and `history-export/`). All 16 files retained
  their SHA-256 hashes; the empty repo-root `scratchpad/` was removed. Historical
  commands naming that scratch path need the new location. No research jobs
  remain running; no commits were made for this handoff.

Start with the [consolidated research proposal](thesis-proposal.md) for the
current question, prior-art boundaries, experimental comparisons and rejection
criteria. The original architectural candidate below is retained for its audit.
The [current memory-method audit](memory-method-audit.md) adds BPP, KEMO, BEACON
and TRACE as close comparisons and specifies the failed-versus-successful effect
contrast needed before proposing another policy architecture.
The [command/effect result](command-effect-inference.md) adds exact inference
checks and a proved special case where ambiguous controls do not prevent
successful effect imitation.
The [executor boundary probe](executor-state-boundary.md) demonstrates in the
current pure mapping that decoded taps, pad edges and decoder memory are
different quantities; it identifies a concrete baseline for the proposal.
The [paired event evaluator](paired-event-evaluation.md) computes exact bounds
on model differences under shared timestamp uncertainty, checked against 5,640
exhaustive cases. It can establish rankings despite overlapping separate ranges.
The [frontier implementation](frontier-event-evaluation.md) makes that comparison
practical on long low-overlap sequences, while exposing a nested-interval limit.
The [full-method evaluation audit](evaluation-novelty-audit.md) narrows the
candidate contribution and identifies the missing development prediction export
needed to test its practical value.
The [command-coarsening pilot](command-coarsening-pilot.md) now supplies two
verified archived prediction streams: paired bounds resolve one additional
action/session ranking under controlled coarsening. Natural effect-label
uncertainty and current-policy benefit remain untested.
The [first real-data pilot](historical-timing-pilot.md) uses verified archived
development outputs: timing uncertainty cannot reverse the old B0 model's loss
to its median baseline in either fold. It required no model inference or training.
The [offset diagnostic](timing-shift-diagnostic.md) strengthens that result:
even an oracle-selected constant timing correction cannot rescue either fold,
with exact global optimization and 1,026 independent small-problem checks.
The [signal diagnostic](timing-signal-diagnostic.md) prevents overinterpreting
that failure: marginal timing intervals do not identify even the sign of linear
timing association, and repeated first-interval keys require event-level care.

Research date: 2026-09-26. Author: research agent. Repository inspected at
`12569448e9e9d97e8477cf964e6ecee4deda7cf6` with unrelated untracked work present.
**Updated by the [second novelty audit](novelty-audit-2.md):** close prior art
covers the proposed belief/policy separation, and a new exact counterexample
shows that freezing a predictor does not identify action effects. Treat the
architecture below as an engineering hypothesis, not an established novel method.
The [event-evidence investigation](event-evidence.md) adds a tested exact
interval-event objective and identifies why stronger cast counts cannot yet
be treated as stronger physical press labels.
This is a research proposal and novelty audit, not a change to the learning plan,
an accepted policy, or a claim of publication-ready novelty. The direct workspace
Linear connector was unavailable. Existing consumers are the VUH-1346 fit and
VUH-1322 execution work; their current tracker status was not verified.

The most promising question is: **can an imitator retain action history needed
to predict its own delayed physical effects, while rejecting history that merely
predicts what the demonstrator usually does next, and choose only goals still
reachable before their opportunity expires?**

This connects two real project boundaries: an observed imitation-history failure
and the keyboard/mouse-to-pad transfer. Neither a larger backbone nor a generic
world model resolves those boundaries by itself. A defensible research result
would isolate this distinction, derive conditions under which it matters, and
demonstrate improved outcomes over strong existing methods at equal data and
interaction budgets. That result has **not** been established here.

## What the repository actually supports

| Finding | Evidence | Consequence |
|---|---|---|
| An interim no-HUD model made no decoded presses over 24,556 self-fed steps; blanking its history yielded press-F1 0.079 | [Interim diagnosis](../../lanes/end-to-end-fit-interim.md), [original diagnostic](../../evidence/range-bc-selffed-diag-20260925/fit-selffed-diag.md) | Investigate history dependence before buying a larger model. These are historical interim checkpoints, not proof that every current candidate fails. |
| Teacher-forced press probabilities can look better while the actual hold/tap decoder emits nothing | Same diagnosis; `policy/range_bc/executor.py::decode_step` | Score decoded actions, onsets, releases and persistent idle/hold states. A probability-head F1 is insufficient. |
| Frames and previous action embeddings enter one LSTM | `policy/range_bc/model.py::Policy.step` | There is no explicit separation between behavioral persistence and estimation of pending physical effects. |
| Current training code already has frames-only, one-step self-conditioning, idle corruption and sequential self-conditioning machinery | `policy/range_bc/model.py::Config.history`; `train.py::self_conditioned_forward`, `IDLE_CORRUPTION_RULE`, `SELF_ROLL_RULE` | Do not propose these as new work or novelty. Check the owning lane's current comparisons before adding arms. Presence in code does not establish efficacy. |
| Offline self-fed evaluation feeds back decoded actions while retaining recorded human frames | `policy/range_bc/train.py::predict_self` and module contract | It diagnoses feedback collapse; it does not simulate what those actions would have made the game show. It cannot measure counterfactual gameplay success. |
| Per-step camera clipping and optional accumulated-error correction already exist | `executor.py::saturate`, `Tracker`, `pad_state` | Compare against these; do not rediscover saturation handling as a contribution. |
| The executor explicitly calls historical 415 deg/s yaw and 99 deg/s pitch maps stale for the current alt settings | `executor.py` module contract | No current rate limit, saturation prevalence or tracking guarantee can be inferred from those numbers. Recalibration belongs to the controller owner. |
| The learning plan separates observed motion, inferred angle and commanded input, and prohibits sealed-source development | [Learning plan](../../learning-plan.md), [recording log](../../recording-log.md) | Pixels are evidence, not privileged state. Unknowns and whole-session splits remain binding. |

No raw recording, sealed file, checkpoint, or game process was opened in this
research pass. Existing evidence reports were read. Runtime, training and admission
code were not modified.

## Prior art that rules out easy novelty claims

Sources below are author papers, proceedings, or official research publications.
The comparison is scoped to the inspected material, not an exhaustive claim that
no related method exists. Search date is above; publication dates differ.

| Primary source | What is already established | Implication here |
|---|---|---|
| [Causal Confusion in Imitation Learning](https://arxiv.org/abs/1905.11979), 2019 | Observationally predictive features can yield poor policies when the learner changes the state distribution. | The existence of the shortcut is not new. Mask interventions need a causal interpretation. |
| [Fighting Copycat Agents](https://arxiv.org/abs/2010.14876), 2020 | Adversarial representation learning removes excess previous-action information while preserving useful prediction. | An anti-history bottleneck alone is prior art. It must be compared against selective use of execution history. |
| [Keyframe-Focused Visual Imitation Learning](https://proceedings.mlr.press/v139/wen21d.html), 2021 | Upweights expert action changes to address copycat behavior. | Transition weighting is a simple required comparator, not a thesis contribution. The repository's older tactical weighting failure does not settle this different execution task. |
| [Residual Action Prediction](https://arxiv.org/abs/2207.09705), 2022 | A memory stream learns through residual prediction, then combines historical features with the current observation. | Splitting memory and policy into two streams is already known. A new method must identify what execution-specific information the split preserves. |
| [Action-Constrained Imitation Learning / DTWIL](https://arxiv.org/html/2508.14379v1), ICML 2025 | Uses MPC and dynamic time warping to construct feasible surrogate demonstrations for a learner with a smaller action space; learns dynamics with online experience. | Retiming mouse demonstrations for a slower pad is not novel. Count target-domain interactions fairly; offline-only comparisons to DTWIL are not equivalent. |
| [Real-Time Execution of Action Chunking Flow Policies](https://arxiv.org/html/2506.07339v2), NeurIPS 2025 | Generates chunks asynchronously while preserving actions already committed during inference. | Committed-prefix handling is prior art. RTC is designed for flow/diffusion policies, not a direct replacement for this stepwise LSTM. |
| [Imitation Learning with Temporal Logic Constraints](https://proceedings.neurips.cc/paper_files/paper/2025/file/e9fa0f2895e827b15f43b1fdd15a2a04-Paper-Conference.pdf), NeurIPS 2025 | Uses demonstrations to help satisfy infinite-horizon LTL objectives via accepting-state guidance. | Temporal task structure is not new. Its inspected objective differs from estimating uncertain physical expiry from pixels; this is a distinction, not proof of novelty. |
| [When Does Predictive Inverse Dynamics Outperform Behavior Cloning?](https://arxiv.org/html/2601.21718), 2026, inspected v3 | Explains a bias/variance advantage of future-state conditioning and limitations from the approximate predictor's distribution shift. Its analysis explicitly uses a support assumption. | Future-goal prediction plus an inverse model is already a strong baseline. A mouse-reachable future is not automatically in the pad's reachable support. |
| [Streaming augmentations for game imitation](https://www.microsoft.com/en-us/research/publication/augmentations-streamed-video-games/), CoG 2026 | Evaluates temporally correlated visual corruption augmentation with PIDMs in modern games. | Compression and stale-image robustness have directly relevant precedent. Test only corruptions actually present in the local capture/deployment path. |

The broad proposals “predict future frames,” “remove copycat behavior,” “retime
demonstrations,” and “account for latency” all fail the novelty test individually.
The surviving **candidate**, not verified literature gap, is their intersection:
learning a sufficient execution belief from pixels and command receipts while
transferring opportunities across different actuator dynamics under uncertain
deadlines. Still needed: a closer search of delayed-POMDP belief learning,
signal-temporal-logic MPC, cross-embodiment reachability and selective imitation.

## Three analytical checks, and what they do not prove

The companion [probe.py](probe.py) uses only the standard library. It neither
imports the agent nor loads a corpus. Run from the repository root:

```powershell
uv run --no-sync python docs/research/executable-imitation/probe.py
```

Executed 2026-09-26, exit code 0:

| Check | Result |
|---|---|
| Finite scalar reachability: exhaustive controls versus closed form | 2,625 parameter cases, zero mismatches |
| Spatial DTW for paths `[0,2,4]` and `[0,0,2,2,4]` | 0, although arrival is step 2 versus step 4 and the deadline is step 2 |
| Same stale observation, different committed command; best common next action | Minimum expected squared endpoint error 1; conditioning on the command gives 0 |
| Visible goal 4, three steps; expert actions `[0,0,4]`, learner cap 2 | Per-step clipping ends at 2; elementary goal control `[2,2,0]` ends at 4 |

**1. Reachability lower bound.** In a one-dimensional integrator, let the
unavoidable command prefix end at position `x_q`, followed by `n` free steps with
`|u| <= c`. The minimum final distance to a stationary goal `g` is

```text
e_min = max(0, |g - x_q| - n*c).
```

Proof: total free displacement has magnitude at most `n*c` by the triangle
inequality. Moving toward the goal at the limit, with a smaller final command if
needed, attains that bound. The probe checks the integer-control version on an
integer grid, where every intermediate integer displacement is attainable.
Continuous camera motion with acceleration, unknown target motion, occlusion,
angle wrap and game-induced motion does not automatically satisfy this model.
This is elementary reachability, **not a new theorem**.

**2. Spatial matching can lose time-sensitive success.** A spatial-only DTW
distance can be zero for an expert and a slower learner while an external deadline
is missed. Including appropriate clocks or task state in the alignment can fix
the counterexample; it does not disprove DTWIL generally. Freezing a cooldown or
target's motion while stretching only the learner's trajectory would be a false
game model. The physical clock must keep running.

**3. Removing all command memory can discard necessary information.** Let the
last observed position be 0, the goal 0, an unavoidable pending command be
`q in {-1,+1}` with equal probability, and one free action `u in [-1,+1]` follow
it. A policy that discards `q` has expected squared error
`((1+u)^2 + (-1+u)^2)/2 = 1+u^2 >= 1`; using `u=-q` achieves 0.
The observation is identical in both cases. This establishes the relevance of
pending execution memory under these assumptions. It does not show that any
existing anti-copycat paper discards all such information.

All three checks can be solved by ordinary model-based control with exact state.
They motivate the learned, partially observed problem; they provide **no evidence
that a new learning algorithm beats a strong baseline**.

## Candidate method and the falsifiable claim

Working hypothesis: at fixed demonstrations and target-domain interaction budget,
separating history's physical effects from its behavioral correlations improves
both recovery from idle and timely execution under changed latency/rate limits,
relative to the strongest ordinary BC and model-based adaptation baselines.

Proposed factorization:

```text
causal visual history --> current-state estimate -------------------+
time-stamped executed/pending commands --> dynamics prediction -----+--> belief at action-effect time
                                                                    |
expert-trained visual goal proposer --> candidate goal + time window |
                                      |                             |
                                      +--> feasibility/expiry check-+
                                                   |
                                      goal-conditioned pad policy
                                                   |
                                        existing guarded executor
```

The state estimate keeps visual temporal memory for resources, momentum and
occlusion. Command history enters through an independently trained dynamics
predictor and explicit pending-command state. The first ablation prevents the
imitation loss from modifying that predictor. The actor receives predicted
physical effects and uncertainty, not an unrestricted embedding of recent
demonstrator actions. This restriction may still leak shortcuts; it is an
experimental hypothesis, not a causal guarantee.

Desired goals can be visible target alignment or a visible destination. Start
with those modest quantities before learning a general video generator. Goal
selection must be causal at inference; actual future frames can supply offline
training targets but are never runtime inputs. Expert button order is weak
evidence about intended subgoals, not ground truth for intention.

The deadline must come from an observable cue, independently verified mechanics,
or an explicitly uncertain predictor. An expert's press time is **not** evidence
that the opportunity expires then. No hard-coded tracer lifetime is assumed by
this research note. An unknown expiry stays unknown and cannot certify a timed
action. Failure to certify the current goal should trigger a supported alternate
goal or further observation, not be rewarded as success or universal inactivity.

For uncertainty, construct a belief set over the state at action-effect time and
a set of plausible dynamics. A robust feasible action sequence must succeed for
the whole declared set, including observation age and execution delay. If the
sets have separately validated failure probabilities, a union bound can bound
their joint failure; a model ensemble alone supplies no such coverage guarantee.
This conservative rule can reject useful actions. Report false refusals and
completion per allocated trial alongside erroneous acceptances.

Training cannot replace human history with arbitrary idle actions while treating
the unchanged next video frame as a physical transition from those actions.
Such corruption may be a useful robustness regularizer, as current code permits,
but it is not an intervention dataset or DAgger. Dynamics fitting requires actual
logged command/observation pairs and measured timing. Agent-reached states need
appropriate correction labels when the desired action changes.

## Shortest experiment that can reject this direction

**First, reuse the current fit owner's anti-copycat comparisons.** Current code
already implements several proposed remedies. Resolve their current results,
without retuning on sealed data. Assess executed onset/release behavior,
camera initiation/reversal and idle/hold durations. This research pass did not
launch training or assert those newer arms have failed.

**Second, test identifiability on a small authorized development sample.** Before
large extraction, inspect 30 contiguous examples across at least three training
sessions: ten ordinary turns, ten rapid turns near ability use, ten interruptions
or recoveries. This is a proposed audit size, not a statistical power claim. Have
the existing admission owner establish permitted intervals. Preserve ambiguous
examples and native-frame evidence. Record frame availability time, commanded
actions, visible effects, action legality and whether any deadline is actually
observable. Do not invent off-policy feasible labels by clipping mouse counts.
If deadlines or action-effect state cannot be measured at useful coverage, narrow
the experiment to visible alignment and report that limitation.

**Third, a controlled pixel-based benchmark.** Build or adapt a small environment
with identical imagery but independently varied command delay, camera speed cap,
goal expiry and action persistence. Ground-truth state is for scoring and a
clearly marked oracle comparator only. Keep expert data fixed across arms. Hold
out combinations of dynamics, not random adjacent frames. Compare:

| Arm | Purpose |
|---|---|
| Current BC, frames-only, and best existing self-conditioning arm | Establish whether simple fixes already solve it |
| Keyframe weighting and residual-action method | Cover direct anti-copycat prior art |
| PIDM with matched visual encoder | Isolate benefit of predicting a goal |
| Goal tracking with calibrated delay/rate limits and ordinary MPC | Strong engineering baseline; likely solves the toy checks |
| DTWIL-style trajectory alignment, and a deadline-aware MPC extension | Test whether constrained retiming plus explicit time already suffices |
| Candidate, minus command-effect memory; minus deadlines; without predictor gradient restriction | Attribute any gain to the stated mechanism |

Flow-policy RTC is an additional comparison only if a flow/chunk policy is
actually introduced; do not force an incompatible wrapper onto the LSTM.
Match encoder capacity, compute and real environment interactions, including
dynamics calibration. Run several seeds and report interval estimates by
independent episode/session. Final sample size should follow pilot variance and
a declared useful effect size, not a claim that ten trials can certify a paper.

**Fourth, guarded Rivals transfer only after the existing gates.** Require current
pad calibration, reviewed live code, fresh range HUD, identity-pinned deployment,
usable episode/reset flow and an accepted policy candidate. All controls remain
on the PC; training follows the Mac ownership contract. Reuse the existing
scheduled-trial and matched-scripted protocol, retain setup failures and unknown
outcomes. A range result tests mechanics, not tactical performance against humans.
AI-only custom claims require the separate environment guard and learning-plan
milestone F. This research proposal changes none of those permissions.

Reject the research claim if ordinary calibrated MPC matches it, existing
self-conditioning removes the relevant failure across tested delays, no
command-memory-specific effect survives ablation, inferred goal windows are
unreliable, or a gain depends on excluding abstentions/failed setups. If the
candidate only improves fixed-video self-fed metrics, it remains a diagnostic
result. A useful engineering improvement can survive even when the novelty claim
does not.

## What would justify doctoral-level significance

Three connected contributions are plausible: a precise identifiability result
for useful versus shortcut action memory under delayed pixels; a learnable
execution-belief method with a calibrated feasibility/coverage tradeoff; and
cross-dynamics experiments demonstrating a repeatable advantage over the strong
baselines above. Generalization beyond one hero/client configuration is needed
for a broad claim. The elementary proofs and synthetic checks here do not meet
that standard alone.

Delivered in this pass: a repository-grounded failure analysis, nine primary
research connections, explicit exclusions of already-published ideas, a tested
counterexample script, and an experiment that can falsify the candidate. The
novelty claim and empirical advantage remain open. The next research action is
to test the proposed information separation against delayed-POMDP and
deadline-aware MPC literature before writing a new training architecture.
