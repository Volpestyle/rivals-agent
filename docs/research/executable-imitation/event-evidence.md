# Preserving event evidence without inventing controls

2026-09-26. Research-only analysis. This note does not supersede the accepted
replay contract, admit a source, or implement a training loss. It follows the
[second novelty audit](novelty-audit-2.md).

## Concrete opportunity and constraint

The accepted replay objective scores each complete cast window independently
using noisy-OR. Its [W1 decision](../../lanes/end-to-end-fit.md) explicitly allows
one predicted press to satisfy overlapping windows. That is a deliberate weak
constraint. The historical table reports 119 of 262 complete Web Cluster windows
in overlap groups and four Web Cluster records with count two. These are figures
from the existing report, not a new inspection or prevalence estimate.

Preserving distinct event identities could retain supervision currently dropped
by that relaxation. **But a distinct cast is not automatically a distinct down
edge.** The [kit](../../spiderman-kit.md) still marks LT hold auto-fire unknown,
and the [controller note](../../lanes/l4-controller.md) says hold auto-repeat was
not measured. That is a target-pad uncertainty; it neither establishes nor
refutes the mouse source's behavior. The [HUD audit](../../lanes/replay-hud.md)
supports press-to-cast association on specific inspected mouse intervals, while
also documenting inputs with no cast and variable evidence delay. Generalizing
that association to every source/control mode needs evidence.

Consequently, the tested construction below is first an **event objective**.
Using it on press logits requires separately verified one-to-one semantics,
distinct evidence identities and interval validity. It cannot be switched on
across replay data merely because the mathematics works.

## Exact compatibility mass for small overlap components

Let `Y_t in {0,1}` indicate a point event in time bin t, with probabilities `p_t`
under a fixed-input independent-Bernoulli surrogate. Let each evidence identity
j require a distinct event somewhere in inclusive interval `[l_j,r_j]`.
Define `C(E)` as binary event paths with an injective matching from all evidence
identities to their compatible event times. Additional events are allowed.

```text
Z(p,E) = sum over y in C(E) of product_t p_t^y_t (1-p_t)^(1-y_t)
loss   = -log Z(p,E)
```

This is the probability mass of compatible event paths under the surrogate.
It is not automatically the likelihood of the observed evidence: an informative
observation/censoring mechanism can weight compatible paths differently. Nor is
it the probability of a real closed-loop rollout. Holding the input video fixed
while changing actions does not generate a counterfactual environment.

Naively summing over evidence-to-event assignments is incorrect: a path with
several valid assignments would be counted several times. Instead, process
event times in order and greedily assign each realized event to the currently
eligible, unmatched interval with earliest deadline. Ties use a fixed identity
order. Each binary path then induces exactly one state sequence.

**Why the matching is complete.** If some complete assignment uses the current
slot for a later-deadline interval i and a later slot for earliest-deadline
eligible interval j, swap those assignments. Both release times are satisfied:
i was already eligible now, and j is eligible now by construction. The later
slot was at or before j's deadline, which is no later than i's. If the current
slot was unused, move j's assigned slot to it. Repeating this exchange produces
the greedy matching whenever a complete matching exists.

Track the unmatched identities as a bitmask, branch on event/no event, merge
equal masks by summing probability, and discard a branch when an unmatched
interval expires. The implementation has worst-case cost `O(T*m*2^m)` and
memory `O(2^m)`. This is only suitable for small components as written. A useful
engineering improvement could exploit the maximum number of simultaneously
active intervals; that optimization is not implemented or claimed here.

Multiplicity is represented by distinct evidence tokens with the same interval
**only when the count is reliable**. Duplicate reports of one event are not
independent tokens. Arbitrarily overlapping windows are supported; no event
order is inferred from the order in which evidence becomes visible. Unit-bin
capacity is an explicit assumption. If two true events can occur in one bin,
use finer bins or a count-valued event model instead.

The positive evidence alone admits overproduction: making every bin an event
can satisfy all feasible constraints. Verified negative evidence, paired event
labels and output-rate diagnostics are still needed. Do not impose an invented
exact event count to suppress it. A negative cast label is not a negative input
label if an input could have failed to cast.

## Executed verification

[event_mass_probe.py](event_mass_probe.py) contains the dynamic program and a
separate exhaustive oracle. The oracle enumerates binary paths and all injective
assignments, accepting each path only once.

```powershell
uv run --no-sync python docs/research/executable-imitation/event_mass_probe.py
```

Executed successfully, exit 0. All interval multisets with up to three identities
over sequences of one through five bins were tested with nontrivial rational
probabilities, including identical/nested intervals and impossible assignments:

| Check | Result |
|---|---|
| Interval families compared against exhaustive oracle | 1,210, zero mismatches |
| Reversing evidence input order | Same mass for every checked family |
| Multiple assignments of one binary path | Counted once |
| Extra unobserved events | Permitted |
| Enough total events but none in one required interval | Correctly rejected |

For probabilities `[0.001,0.99,0.001]` and windows `[0,1]`, `[1,2]`:

| Objective | Mass/product | Negative log |
|---|---|---|
| Product of individual noisy-OR terms | 0.9801198001 | 0.02008047 |
| Distinct-event compatibility mass | 0.00197902 | 6.22515351 |

The first row is the unweighted mathematical counterpart of summing separate
window losses, not a recomputation of a production batch with its positive
weights and normalization. The product is not generally the joint probability
of all overlapping requirements. This example demonstrates different supervision,
not an empirical improvement or a calibrated 98% versus 0.2% confidence estimate.

## A necessary action-identification check

The probe also constructs a synthetic repeat-capable control held over bins
`[0,1,2]`. It has one down edge at 0 and produces cast effects at 0 and 2. An
edge-triggered mechanism could instead produce those same cast times from two
separate taps. Seeing the casts alone cannot choose between these mechanisms.
This remains true with perfect effect timestamps; wider intervals only add
ambiguity. The synthetic mechanism does **not** assert how Rivals actually works.

If the two mechanisms are observationally indistinguishable and equally likely,
no estimator based only on their common effect record can identify the correct
one with probability above 1/2. This is elementary indistinguishability, not a
new theorem. It shows why stronger count constraints on physical press labels
need calibration or paired inputs. A small set of successful tap examples does
not alone rule out hold-generated repeats elsewhere.

There is also a basic censoring ambiguity. In one regime let `p` be the chance
of a cast and `q` the chance its evidence is observed. With no false positives,
the observed frequency is `r=p*q`. Values `(p,q)=(0.2,1)` and `(0.8,0.25)` both
give `r=0.2`. Observed positives alone cannot determine the cast rate. Real
state-dependent censoring is more complex, not less. Paired controls plus
audited visual effects can estimate different parts of the observation process;
controls alone still do not prove that a cast occurred.

## Closest prior art and originality boundary

| Primary source | What it already does | Remaining distinction to investigate |
|---|---|---|
| [Occurrence Count Learning](https://proceedings.mlr.press/v97/schroeter19a.html), ICML 2019 | Learns point-event localization from occurrence counts. | Count supervision itself is not new; this project's evidence is a set of per-event time intervals and not a complete count of all attempted inputs. |
| [Extended CTC](https://arxiv.org/abs/1607.08584), 2016 | Marginalizes temporal action alignments using dynamic programming and visual similarity. | A complete ordered action transcript differs from incomplete effect evidence with allowed unobserved inputs. Marginalizing alignments is not new. |
| [Inference for mark-censored temporal point processes](https://proceedings.mlr.press/v216/boyd23a.html), UAI 2023 | Infers queries involving censored event types; the inspected paper states an MCAR assumption for its missing-mark setting. | The effect observation mechanism here may depend on action/state; that must be measured, not assumed. |
| [Learning Temporal Point Processes with Intermittent Observations](https://proceedings.mlr.press/v130/gupta21a.html), AISTATS 2021 | Models observed and missing events as coupled point processes, including history-dependent missingness. | Informative missing-event modeling also predates this proposal. Its presence alone cannot justify novelty. |
| [PLUNDER](https://www.joydeepb.com/Publications/ral2024_plunder.pdf), RA-L 2024 | Programmatic imitation from unlabeled/noisy demonstrations uses latent action inference and an observation model. | An observation model plus latent controls is established. Our proposal must be compared on control semantics, timing and required prior knowledge. |
| [Imitating Latent Policies from Observation](https://proceedings.mlr.press/v97/edwards19a.html), ICML 2019 | Learns latent policies from observations and grounds them using limited interaction. | Grounding latent effects into executable controls is not new. |
| [Grounded Latent-Action World Models](https://arxiv.org/abs/2606.21672), 2026 preprint | Grounds latent actions across heterogeneous demonstrations with labeled target-domain data. | Cross-device latent actions are a strong modern comparator; the specific evidence assumptions matter. |
| [Causal Imitation through Partial Identification](https://proceedings.neurips.cc/paper_files/paper/2024/hash/9f7f2f57d8eaf44b2f09020f64ff6d96-Abstract-Conference.html), NeurIPS 2024 | Studies imitation when confounded dynamics/rewards are not uniquely identified. | A partial-identification framing is also established. Do not claim that retaining ambiguity alone is a new principle. |

The matching construction is a useful exact reference implementation; this note
makes no claim that it is a new algorithm. It should be assessed as a stronger
event-supervision baseline before any larger learned emission model is attempted.

## A bounded development experiment

Use only admitted paired development material selected by the existing owner;
no sealed test or Gate 2 material. First hand-check a small native-frame sample
covering isolated events, overlaps, missed visual evidence, failed inputs and
long holds. Determine which event identities/counts and time intervals are
defensible. Keep source device/mode and patch explicit. Unknown mechanisms stay
unknown. Do not infer source hold semantics from the target pad.

On those paired windows, compare the current relaxed objective, exact point
event supervision where genuinely available, count-only learning, the tested
interval compatibility objective, and an observation-model extension. A
synthetically masked paired sample provides an oracle-controlled experiment;
it must be separate from naturally unreadable footage so success on artificial
missingness does not claim real-world robustness.

Judge event count, temporal coverage and false events first. Judge press/hold
recovery only where the command-to-effect mapping is established. Then compare
causal policy behavior with identical data, model capacity, compute, session
splits and executor. Whole-component loss placement must avoid duplicating
evidence across training windows; the existing once-per-epoch ownership rule
does not automatically transfer when a component spans several windows.

Stop if the apparently distinct evidence is duplicate detection, if one held
input explains multiple casts, if exact compatibility improves only its own
surrogate score, or if improvements disappear against count-only/CTC-style
baselines. Any change to training labels or admission requires the repository's
independent review; this synthetic script is not relied on for either.

This is a concrete optimization lead with an executable reference and explicit
semantic prerequisites. It is not yet a validated policy improvement or a
standalone doctoral contribution.
