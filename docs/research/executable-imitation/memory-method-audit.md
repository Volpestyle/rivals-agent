# The next learning comparison: memory of effects, with explicit uncertainty

Research audit, 2026-09-26. This is a proposed comparison, not a new training arm,
an accepted learning-plan change, or a demonstrated gameplay improvement.

Update: the [existing attempt/effect contrast](attempt-effect-contrast.md) locates
two hash-verified training-source cases with an RMB rise and ammo consumption but
different hit outcomes. They are not matched histories or new admitted labels;
the subsequent memory-dependent decision contrast remains unverified.
The continuation check found further shots after both outcomes, with different
targets and current context. This specific pair cannot establish a memory benefit.

## Why this is the next question

The [interim fit diagnosis](../../lanes/end-to-end-fit-interim.md) documents a
teacher-forced advantage that did not survive self-fed execution: decoded presses
collapsed and camera predictions matched zero motion. That historical result
motivates studying what history represents. It does not prove the latest models
have the same failure, or establish that a particular memory architecture fixes it.

The timing archive has now answered its useful preliminary questions: the old
model loses robustly, a constant offset cannot rescue it, and the marginal labels
do not identify the sign of its linear timing information. More tiny timing
diagnostics will not establish a new learning method. The next substantive result
must concern decisions or execution under action-dependent observations.

## Closest research, and what it already covers

[BPP (2026)](https://arxiv.org/html/2602.15010v1) conditions a policy on selected
task-progress keyframes. It reports failures where action history does not reveal
whether an operation succeeded. Its experiments also show that better state
prediction on demonstrations need not improve rollout behavior. Keyframes are
detected with a VLM, with reported 3–5 second query latency and a training latency
mask. This is a close baseline for effect-based history, not evidence that its
implementation meets a fast game-control budget.

[KEMO (2026)](https://arxiv.org/html/2606.23589v1) already addresses the heavy
detector limitation: kinematic candidates plus visual verification feed compact
keyframe memory, gated fusion and transition-weighted learning. Consequently,
replacing BPP's VLM with cheap event detection is not sufficient novelty.

[BEACON (2026)](https://arxiv.org/html/2609.22730v1) supplies another close
comparison: an explicit Bayesian belief, including uncertainty, conditions a
diffusion policy. Its two simulated tasks use static hidden variables and
specified observation models. Generic belief-conditioned imitation is therefore
also established. Our dynamic cooldowns, failed inputs and unknown visual
emission process would need their own validated model; those are applicability
questions, not an automatic novelty claim.

[TRACE (2026)](https://arxiv.org/html/2606.14551v2) stores earlier evidence in
bounded memory and retrieves it using signatures of the executed state trajectory.
Its delayed-evidence setting concerns cues that disappear before a later choice.
That differs from evidence that arrives late about a past event. The methods
still overlap enough that a bounded causal memory module cannot be claimed as
original on its own.

Two alternatives are less direct fits. [Stable-BC](https://arxiv.org/html/2408.06246v1)
studies local error dynamics and stability using robot/environment state and
smooth dynamics. A recurrent policy's stability on frozen image sequences would
not establish stability of the game plus executor. [DML-IL, current v2](https://arxiv.org/html/2502.07656v2)
uses lagged history as an instrument under additive confounding and a specified
noise horizon. Appendix F explicitly discusses the difficulty of validating
instrument independence. Neither assumption is established for our discrete
controls, controller limits, or HUD missingness. These are not drop-in remedies.

## Concrete adaptation worth testing

Keep current visual input and executable action outputs. Compare three histories:
the existing recurrent history, deterministic effect keyframes, and an uncertain
effect-state representation. Each receives the same causal visual evidence,
executor state, training sessions and compute budget. Include a current-frame
baseline and equal-budget recent/uniform keyframe controls. Compare an ordinary
Bayesian filter as well as a learned estimator; a neural module must not take
credit for basic filtering.

The proposed input separates quantities that already have different contracts:

| Quantity | Source and meaning | What must not be inferred |
|---|---|---|
| Decoder state and delivered pad commands | Actual executor log, with current binding/calibration identity | A command is not a successful cast or hit. |
| Visual effect evidence | Retained frames, event type, occurrence interval, availability time, unknown status | Missing detection is not a negative outcome. |
| Persistent task state | Estimates or sets of possibilities conditioned on causal evidence | A cooldown transition alone does not identify a hit, target death, or tactical success. |

The existing [Event contract](../../../perception/events.py) already separates
`[t_from,t_to]` from `known_at` and documents prefix consistency. Reuse that
boundary: an event may enter memory only when it is available, even if its
estimated occurrence was earlier. Do not invent another timestamp convention.
Reader outputs and any probability model still need validation; the presence of
these fields does not establish accurate live detection or calibrated beliefs.

For an initial cooldown/resource study, uncertain memory can retain a set of
compatible states when observation probabilities are unavailable. Calling that
set a calibrated probability distribution would be unjustified. Unknown-state
coverage and its cost to decision quality are measured outcomes, not nuisances
to suppress. Preserve the executor's real state even when visual effects remain
uncertain; the [executor probe](executor-state-boundary.md) shows why physical
pad snapshots alone are not a sufficient replacement for decoder state.

## A discriminating experiment, rather than another architecture claim

First establish whether the existing admitted material contains failed and
successful attempts with comparable command histories and different visible
outcomes. Label what was attempted, what effect is established, when that evidence
became available, and whether a subsequent decision requires remembering it.
Inspect native frames before extracting at scale. Do not fabricate exact press
labels from casts, complete negatives from missing evidence, or event identities
from duplicate interval keys. This correspondence remains the immediate missing
empirical input; the archived timing exports do not provide it.

If that contrast exists, compare histories on the same verified pairs before
training a policy. An effect memory that cannot distinguish those outcomes has
no demonstrated advantage over action history. If the distinguishing evidence
is absent in pixels at the decision time, all methods must retain uncertainty;
later evidence cannot be leaked backward to manufacture success.

For policy evaluation, train on matched demonstrations and test recovery after
failed attempts, delayed detections, duplicate evidence and unreadable intervals.
Artificial corruption isolates causes; naturally occurring failures test whether
those causes describe the game. Frozen-frame self-feeding is only a diagnostic.
Distinguish corruption of a policy's recorded history from perturbing actions
and observing an expert's actual recovery: [DART](https://proceedings.mlr.press/v78/laskey17a.html)
uses the latter during demonstration collection. It supplies a recovery-data
comparison if that stage is scheduled, not a justification for treating unchanged
recorded images as the consequences of substituted actions. No such collection
or live perturbation is initiated by this proposal.
The decisive result requires action-dependent rollouts and the canonical
learning plan's outcome/reset prerequisites, with timeouts and refusals included.
Hold detector and executor fixed when comparing memory; then ablate the detector
separately. Report latency and completion, not just agreement with demonstrations.

A potentially doctoral contribution would be a demonstrated, broadly applicable
way to retain decision-relevant effect uncertainty under unknown interface and
observation dynamics, beating these memory and filtering baselines at a matched
interaction budget. A Rivals-specific event-memory implementation alone would
be an engineering application. No such original contribution or advantage has
yet been established. The present gain is a much stronger comparison set and a
specific failure contrast that can falsify the proposed approach cheaply.
