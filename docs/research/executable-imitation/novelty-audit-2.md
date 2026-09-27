# Second novelty audit: the architecture is not yet a research contribution

2026-09-26. Research-only follow-up to [the proposal](README.md). No game input,
training, corpus access, tracking writes or changes to production code.

**Decision:** downgrade the proposed two-part architecture from a putative novel
method to an engineering hypothesis. Stronger prior art covers most of the
conceptual claims. An exact counterexample also shows that freezing a predictor
does not identify physical action effects. This is evidence against prematurely
implementing the proposed architecture, not evidence against improving the agent.

## Closest additional prior art

Primary sources inspected on the research date:

| Work | Relevant result | What it rules out or requires |
|---|---|---|
| [Learning Belief Representations for Imitation Learning in POMDPs](https://arxiv.org/abs/1906.09510), UAI 2019 | Learns a belief module with an imitation objective and dynamics/action-sequence regularizers. | A learned belief in front of an imitation policy is established. Its joint training also makes a frozen-versus-joint ablation necessary. |
| [Learning Causal State Representations of Partially Observable Environments](https://arxiv.org/abs/1906.10437), inspected v2 (2021) | Compresses observation/action histories through predictive causal states, with a connection to bisimulation. | A sufficient action-history summary and prediction-based representation cannot be claimed as new on their own. |
| [Delayed Reinforcement Learning by Imitation](https://proceedings.mlr.press/v162/liotet22a.html), ICML 2022 | DIDA adapts undelayed demonstrations to delayed environments using dataset aggregation, with theoretical and empirical analysis. | Delay adaptation through imitation predates this project. Expert query/data-aggregation access must be accounted for when choosing comparisons. |
| [Deconfounding Imitation Learning with Variational Inference](https://arxiv.org/html/2211.02667v2), TMLR 2024 | Distinguishes conditioning on one's past actions from using physical transitions to infer hidden context. Its practical method learns inference from exploration data. | This is the closest conceptual overlap. Separate physical inference plus a latent-conditioned imitation policy is not a defensible standalone novelty claim. |
| [Signal Temporal Logic Neural Predictive Control](https://arxiv.org/abs/2309.05131), 2023 | Learns controllers for temporal specifications using predicted trajectories and a backup policy. | Temporal feasibility and fallback control are established. Estimating an unknown deadline is a different statistical problem, not solved by introducing temporal logic. |
| [HALO: Memory Retrieval in Visuomotor Policies for Long-Horizon Robot Control](https://arxiv.org/abs/2606.25136v1), RSS 2026 project | Uses video question-answer supervision and sparse retrieval to address spurious historical correlations and accumulating context errors. | Selective memory addressing copycat-like problems has current visual-control competitors. VLM-supervised long-horizon retrieval is not automatically appropriate for subsecond camera control. |
| [Learning When to Stop: Selective Imitation Learning Under Arbitrary Dynamics Shift](https://arxiv.org/abs/2605.09183), 2026 preprint | Studies stopping rules under dynamics shift with source labeled expert demonstrations and target unlabeled expert trajectories. | Refusal under transfer uncertainty is not new. Its data assumptions differ from having only old mouse demonstrations and a few pad calibrations. Stopped regret is not task completion. |
| [Scalable Causal Imitation Learning](https://arxiv.org/html/2607.17003), 2026 | Uses causal adjustment with off-policy imitation objectives; its window reduction assumes bounded, time-homogeneous confounding and a causal graph. | A small history window cannot simply be called causally sufficient in Rivals. Unknown camera effects and resources must be checked against those assumptions. |

The deconfounding paper explicitly separates insufficient state/action support
from hidden-context confounding, and its limitations retain the former. That
distinction matters here: an absorbing idle state does not by itself prove a
hidden confounder. It may result from action persistence, imbalance, exposure
bias and the decoder. These mechanisms call for different experiments.

## A falsification of the frozen-predictor argument

[identification_probe.py](identification_probe.py) constructs a fully observed,
noise-free scalar system:

```text
y = b*x + g*u
true b = 1/2, true g = 3/2
expert demonstrations always use u = x
```

Every demonstrated transition then satisfies `y=2*x`. Every model with `b+g=2`
fits perfectly. The minimum-norm interpolant is `(b,g)=(1,1)`, not the true model.
Freezing it or blocking policy gradients cannot reveal the missing information.
On commands `u=-x`, that model predicts zero while the true endpoint is `-x`.

There are 20 observed x values, from -1 to 1 in increments of 0.1 excluding zero.
The script uses exact rational arithmetic and evaluates 41 members of the
infinite perfectly fitting model family. Its output is:

| Quantity | Result |
|---|---|
| Demonstration prediction MSE of the minimum-norm model | 0 |
| Determinant of the demonstration feature Gram matrix | 0: not identifiable |
| Prediction MSE on reversed commands | 77/200 = 0.385 |
| True endpoint MSE when this model controls toward zero | 77/200 = 0.385 |
| After adding the transition `(x,u,y)=(1,0,1/2)` | Gram determinant 77/10; unique recovered model `(1/2,3/2)` |
| Prediction and control MSE after that calibration | 0 |

Reproduction, executed successfully on the PC using CPU and standard library:

```powershell
uv run --no-sync python docs/research/executable-imitation/identification_probe.py
```

For a linear predictor with design rows `(x_i,u_i)`, the two coefficients are
identifiable exactly when

```text
det(X'X) = sum(x_i^2)*sum(u_i^2) - sum(x_i*u_i)^2 > 0.
```

This is ordinary regression identifiability. The probe demonstrates a failure
of an architectural argument, not a new identification theorem. It does not
establish that James's real demonstrations are rank deficient, or that one
calibration row suffices in noisy, partially observed Rivals. The toy has no
hidden confounder; its problem is missing action variation at a given state.

## Implications for the actual project

The previous proposal must not skip three separable evidence requirements:

1. **Behavioral feedback:** establish which current fit arm can initiate and
   release actions when fed its own decoded outputs. Current code already
   contains frames-only, corruption and self-conditioning variants. Historical
   interim failure is a reason to inspect those results, not to repeat the work.
2. **Physical prediction:** validate a dynamics predictor where commands differ
   from the demonstrated persistence pattern. A held-out recording of the same
   behavior can still leave this unanswered. Contrast ordinary turns with
   reversals, neutral transitions and supported ability-related camera changes.
   Command receipts prove what was requested; pixels are needed for effects.
3. **Cross-device validity:** identify the target pad's current response and its
   uncertainty separately from the mouse source. Source-domain fit cannot prove
   target-domain response. The source code explicitly marks the old map stale.

No action-history corruption in a fixed human video produces the missing
counterfactual physical transition. It can regularize a policy, but should not
be used as a dynamics training target for the corrupted command. Neither the
current repository nor its authors are accused of doing that; this is a constraint
on the new proposed experiment.

For the first physical-prediction audit, aggregate by whole accepted session and
command regime, not independent frames. Report coverage, prediction residuals,
uncertainty calibration, and failures to distinguish effect from camera motion
caused by an ability. Audit a small native-frame sample before expansion. Any
new game-input measurement requires the existing controller owner and review;
this note authorizes none and changes no collection schedule.

## Revised research direction and kill criterion

A narrower question remains worth investigating: **how can a pixels-only
imitator decide which target-controller measurements are necessary to preserve
expert task outcomes, when commands, visual effects and event evidence have
different clocks?**

This is a possible problem formulation, not a new method claim. General active
system identification, task-informed exploration, delay compensation and causal
imitation are all existing fields. To earn novelty, an eventual result must
identify a specific unanswered estimation/control question and outperform
strong calibration-plus-control baselines. Adding all those words to an
architecture is insufficient.

The repository has a useful concrete complication for further research: replay
ability evidence supplies overlapping event-time intervals, not exact press
times. Its accepted noisy-OR objective intentionally lets one predicted press
satisfy two overlapping windows (`end-to-end-fit.md`, W1). That is a documented
relaxation, not a bug. A possible next investigation is whether conserving
distinct event evidence while propagating timing uncertainty improves causal
policy learning and action-effect identification. CTC, weak action segmentation,
interval-censored point processes and event matching must be checked before
claiming novelty there too. The initial search already finds
[occurrence-count localization](https://proceedings.mlr.press/v97/schroeter19a/schroeter19a.pdf)
and [mark-censored event inference](https://proceedings.mlr.press/v216/boyd23a.html),
so merely preserving counts or modeling missing events will not qualify.
The specific uncertainty to resolve is whether the evidence-generation process
is action-dependent and whether a training objective can handle that without
inventing exact press times or treating unobserved failed presses as negatives.
No replay gates or data admissions change.

**Current conclusion:** the first architecture does not yet meet the user's
doctoral-level originality requirement. This audit changes the next action:
do not spend a training run implementing it on novelty grounds. Preserve its
useful engineering tests, investigate the information lost in timing/label
construction, and search for a claim that survives the closest prior art.
