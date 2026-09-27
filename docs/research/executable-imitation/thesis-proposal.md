# Research proposal: learning executable behavior from incomplete effects

Research synthesis, 2026-09-26. Prospective contribution, not an accepted
learning-plan change or demonstrated improvement. No game input, corpus access,
training, label admission or checkpoint modification was performed for this note.

The [memory-method audit](memory-method-audit.md) adds close 2026 work on effect
keyframes, cheap event memory, belief-conditioned imitation and bounded causal
memory. These narrow the architectural novelty claim further and define a
specific failed-versus-successful attempt comparison for the next empirical step.

The subsequent [command/effect probe](command-effect-inference.md) sharpens the
proposal: in a cooldown model, press-only and repeat-on-hold controls are
unidentifiable from cast-only data with unrestricted unknown policies, yet a
common pulse controller realizes every feasible cast sequence. Calibration
must therefore target a demonstrated decision difference; hidden-command
ambiguity alone does not justify it. The reference inference implementation
passes 2,624 independent exact comparisons under supplied mechanics.

A [pure executor probe](executor-state-boundary.md) adds a repository-specific
boundary: adjacent semantic taps produce the same pad snapshots as a continuous
hold, but leave different decoder state. Evaluate semantic events, timed pad
transitions and visual effects separately; none substitutes for the others.
RACE (linked in that note) further narrows novelty around feasible effect targets.

The [paired event evaluator](paired-event-evaluation.md) supplies an exact
synthetic comparison tool: optimize the score difference over a shared set of
admissible event times. Its 5,640 oracle comparisons pass. Use only where event
identity and completeness are established; the current positive-only replay
windows do not automatically meet that requirement.
Its subsequent missing-event extension allows optional events and known-negative
bins, with 3,120 additional exhaustive checks. It can report which comparisons
survive incomplete evidence without pretending that unobserved events are absent.

## The question worth pursuing

Can a learner transfer expert behavior between control interfaces when video
reveals only some action effects, without inventing command labels, and use a
small target calibration budget to resolve only ambiguities that affect success?

The concrete case is keyboard/mouse demonstrations and replay footage feeding a
pad-executed Spider-Man policy. A cast, a press and a held control are different
variables. Evidence can be late or unreadable; a failed press may produce no
cast; several casts might share a held input if that mechanism is established.
The research target is successful behavior under these ambiguities, not recovery
of one supposedly correct command transcript from every video.

This is a potentially substantial research program. The search has **not**
established an original algorithm or a publishable result. Its strongest current
asset is a precise experimental problem and falsified simplifying assumptions.

## A formal target that prevents misleading wins

Let M(E) be the set of command/effect/observation models consistent with admitted
evidence E and stated assumptions. A model includes source control semantics,
target response dynamics, observation delay and missingness. This is a conceptual
identified set, not a set we currently know how to estimate reliably from pixels.

For a target policy pi and bounded task loss L_m(pi), define worst-case regret

    R(pi, E) = sup_{m in M(E)} [L_m(pi) - inf_{pi' in Pi} L_m(pi')].

Pi must contain only causal, feasible policies using the allowed visual and
execution history, with the same information and executor constraints for every
comparison. An oracle with hidden game state is not an admissible comparator.
The model-specific optimum is an analysis quantity, not something measurable
directly in the live game. Controlled synthetic environments can supply it.

The objective is to reduce task regret per unit of target interaction, while
preserving coverage of plausible models. Shrinking M by discarding the truth
does not count as an improvement. Reporting only uncertainty reduction, an
event-surrogate score or a likelihood gain cannot establish this objective.

In a deterministic finite special case, let S_m be the actions that succeed
under model m. Calibration may stop when the intersection of S_m over remaining
models is nonempty. This does **not** require unique system identification.
It is already decision-region determination, not a new theorem or algorithm.
Pairwise compatibility is insufficient: {a,b}, {b,c}, {a,c} intersect pairwise
but have empty joint intersection. Existing hypergraph methods address this
structure. A learned, misspecified model class cannot inherit a finite-model
guarantee simply by using the same stopping condition.

## What the literature already owns

| Proposed ingredient | Existing foundation | Consequence |
|---|---|---|
| Separate useful physical memory from imitation shortcuts | [Causal confusion](https://arxiv.org/abs/1905.11979), [deconfounding imitation](https://arxiv.org/html/2211.02667v2) | A separate history encoder is not sufficient novelty. |
| Infer latent commands through an observation model | [PLUNDER](https://www.joydeepb.com/Publications/ral2024_plunder.pdf) | Marginalizing hidden actions is an established construction. |
| Learn event locations from weak counts | [Occurrence-count learning](https://proceedings.mlr.press/v97/schroeter19a.html) | Stronger window matching needs count-based comparisons. |
| Model missing events | [IMTPP](https://proceedings.mlr.press/v130/gupta21a.html) | Missingness alone is not a new research problem. |
| Act under partially identified dynamics | [Partially identified causal imitation](https://proceedings.neurips.cc/paper_files/paper/2024/hash/9f7f2f57d8eaf44b2f09020f64ff6d96-Abstract-Conference.html) | A model set or robust loss is not sufficient novelty. |
| Gather information until a decision is possible | [Decision-region determination](https://proceedings.mlr.press/v33/javdani14.pdf) | Do not relabel decision-focused calibration as an invention. |
| Identify dynamics for control | [Active control-oriented identification](https://arxiv.org/abs/2404.09030) | Compare against control-oriented acquisition, not only entropy. |
| Execute demonstrations under different action limits | [Action-constrained imitation](https://arxiv.org/html/2508.14379v1) | Feasibility-aware trajectory matching is a required comparison. |

The possible contribution lies in showing which ambiguities remain when both
the emission process and cross-interface action mapping are uncertain, and
resolving them at lower interaction cost with verified task benefit. Combining
the rows above is a hypothesis, not evidence of novelty. A competing method
that already covers this setting would narrow or eliminate that claim.

## Three linked studies, with rejection criteria

### 1. Establish what the evidence identifies

Use a controlled benchmark with known commands, hold/repeat semantics, delays,
failed commands and observation masks. Vary these factors independently before
combining them. Include both random missingness and action/state-dependent
missingness. Preserve exact source events separately from their visible reports.

Compare independent positive windows, count-only learning, interval compatibility,
and a latent command/effect observation model. Supply each baseline equivalent
information; an ordered transcript baseline requires a justified order, and an
oracle transcript belongs in a separate upper-bound condition.

Measure event-count error, localization coverage, false events and calibration
of the retained hypotheses. Measure physical command reconstruction only in
conditions where those commands are identifiable. The useful theoretical result
would characterize an identifiable decision quantity under explicit assumptions,
or an impossibility boundary; the basic ambiguity examples here are not novel.

Reject the stronger objective if its gains vanish under duplicate detections,
held-repeat controls or naturally missing evidence. Do not infer naturally
missing evidence performance from artificially masked clips alone.

### 2. Test whether calibration changes decisions efficiently

Hold the policy family and initial evidence fixed. Compare no calibration,
random admissible probes, predictive-uncertainty acquisition, control-oriented
identification, and decision-region acquisition. Equalize total interaction
time, including resets, failed attempts and observation waiting time. A shared
calibration dataset tests inference quality; each acquisition policy needs its
own interaction run to test experiment selection.

Report task regret versus interaction budget in the controlled benchmark,
model-set coverage, abstention, and sensitivity to deliberately omitted model
mechanisms. Report success and completion separately: always declining to act
can reduce observed error without producing a useful policy.

Reject a new acquisition method if an existing decision-region method with the
same model class matches it. Reject claimed robustness if the truth is excluded
and confidence increases anyway. Full identification is an informative baseline,
not a requirement for successful control.

### 3. Demonstrate executable benefit in the permitted range

Only after the repository's data ownership and independent review requirements
are satisfied, use owner-selected admitted development material and bounded
practice-range evaluations. No sealed material is required for an initial test.
Current pad hold/repeat behavior and camera response must be measured under the
actual configuration; historical stale maps are not substitutes.

Keep data, encoder, capacity, training compute, executor and reset distribution
matched. Existing frames-only, idle-corruption and self-roll options are real
baselines. Include a simple calibrated executor and ordinary feasible-goal
control so a neural architecture does not take credit for basic control fixes.

The primary outcome must be declared from the canonical learning plan before
running experiments. Also report decoded onsets/releases, persistent idle or
hold failures, completed episodes and interaction cost. Fixed recorded frames
with self-fed actions are a useful diagnostic, not closed-loop gameplay.
Use session-level splits and uncertainty intervals that respect episode/session
dependence; individual adjacent frames are not independent samples.

Reject the research claim if only head-level F1 or the training surrogate
improves, or if equal-budget simple baselines remove the live advantage.

## The shortest useful next experiment

Before building a joint world model, ask the existing data owner for a small
admitted paired development sample with independently reviewed event identities.
Stratify it by isolated casts, overlapping windows, failed inputs, held controls
and unreadable effects. Establish whether stronger distinct-event constraints
are semantically valid. Then compare relaxed windows, count-only supervision
and the exact interval objective with identical inputs and weighting.

This initial experiment tests an evidence question; it does not require a new
policy, a large extraction, new recording sessions or an active live agent.
If the ambiguity is primarily duplicate evidence or unmeasured repeat semantics,
fix the evidence model before testing a new loss. Training/admission code still
requires independent review before use.

## What is already delivered

- [Architecture and initial literature audit](README.md), with novelty claims
  downgraded when close prior work was found.
- [Identification audit](novelty-audit-2.md) and an exact synthetic example
  showing why a frozen predictor does not identify unsupported action effects.
- [Event-evidence analysis](event-evidence.md) and an interval-matching reference
  checked against an independent exhaustive oracle on 1,210 interval families.

These are research artifacts and synthetic correctness evidence. They do not
show improved gameplay. The doctoral standard would require an original result
that survives the comparisons above, generalizes beyond one hero/configuration,
and has reproducible evidence. That standard remains unmet by the current work.
