# Comparing event predictions without inventing exact event times

Research reference, 2026-09-26. Synthetic only; no production evaluator, corpus,
checkpoint or admission rule changed. This adds an evaluation component to the
[research proposal](thesis-proposal.md), not evidence of improved gameplay.

The [frontier refinement](frontier-event-evaluation.md) preserves exact results
while forgetting expired evidence and unmatchable predictions. It adds a bound
in local overlap/density, 5,644 oracle checks and synthetic/project-shaped timing
measurements, including a nested-interval state-cap failure.

## A stronger result than overlapping metric ranges suggest

Suppose exactly three distinct events occurred. Their time intervals are [0,0],
[1,1] and [2,3]. Model A predicts events at {0,1,2}; B predicts {1,2}. Use exact
one-to-one matching, with no timing tolerance. The only possible truth sequences
are {0,1,2} and {0,1,3}.

| Possible truth | A F1 | B F1 | A minus B |
|---|---|---|---|
| {0,1,2} | 1 | 4/5 | 1/5 |
| {0,1,3} | 2/3 | 2/5 | 4/15 |

Individual score ranges overlap: A is in [2/3,1], B in [2/5,4/5]. Subtracting
their separate endpoints gives [-2/15,3/5], which cannot establish a ranking.
But the **sharp paired difference is [1/5,4/15]**: A wins under every admissible
truth. The apparent negative difference used different truths for A and B.

This is an identification interval over uncertain annotations, not a statistical
confidence interval or a guarantee about future episodes. Its validity requires
that the actual truth belongs to the stipulated admissible set.

## Exact temporal calculation

Let E contain m inclusive intervals, one per distinct true event. Let Y(E) be all
binary event sequences containing exactly m events that can be assigned
injectively to those intervals. A and B are fixed predicted event sequences.
For each truth sequence y, match predictions one-to-one within the same fixed
early/late tolerance around each true event. Define

    Delta_min = min_{y in Y(E)} [F1(A,y) - F1(B,y)]
    Delta_max = max_{y in Y(E)} [F1(A,y) - F1(B,y)].

Since m and the prediction counts are fixed,

    F1(A,y) - F1(B,y) = 2 TP(A,y)/(m+|A|) - 2 TP(B,y)/(m+|B|).

The [reference DP](paired_event_bounds.py) processes time bins and branches on
whether a truth event occurs. Its state combines an earliest-deadline evidence
matcher with two independent greedy prediction-matcher cursors. A truth event
earns a rational reward for each model's successful match. Each state retains
the lowest and highest cumulative reward among its prefixes.

Correctness follows from three facts. Earliest-deadline matching recognizes
whether a truth sequence can satisfy the distinct interval evidence (the
exchange argument is in [event-evidence.md](event-evidence.md)). Greedy matching
of sorted predicted times to sorted true times maximizes cardinality under a
fixed early/late window. Finally, prefixes reaching the same product state have
identical future possibilities and future reward increments, so keeping only
their minimum and maximum accumulated rewards loses neither extremum.

The implementation has at most 2^m (|A|+1)(|B|+1) states per time bin. Its simple
transition scans give a conservative time bound
O(T 2^m (|A|+1)(|B|+1)(m+|A|+|B|)), with two layers of states in memory.
This is a small-component reference, not a scalability claim. Evidence components
cannot be split independently if prediction matching can cross their boundaries.

## Verification

```powershell
uv run --no-sync python docs/research/executable-imitation/paired_event_bounds.py
```

The DP matches an independently implemented exhaustive oracle in **5,640 cases**:
all interval multisets of sizes one and two, all pairs of binary prediction sets,
horizons one through three, and tolerances (early,late) of (0,0), (1,0), (0,1).
The oracle enumerates feasible truth assignments and prediction matchings; it
does not call either greedy transition. Comparisons use exact rational numbers.
Additional checks cover the table above, an ambiguous ranking [-1,1], identical
predictions [0,0], and inconsistent evidence returning no feasible truth rather
than a fabricated metric. Undefined empty-truth/empty-prediction F1 is rejected.

## Required boundaries for Rivals

- Compare the same event type and clock. Cast-time intervals cannot directly
  score physical button presses or first-visible-evidence times.
- Exactly m events is a substantive assumption. A collection of positive cast
  windows is not proof that no other casts occurred. The repository's `complete`
  window flag does not establish a complete event transcript.
- Event identities must be distinct. Duplicate detections cannot become two
  required truth events. One-bin resolution must support the maximum event rate.
- Use predeclared timing tolerances. The current evaluator distinguishes
  teacher-forced and self-fed tolerances to avoid crediting delayed echoes.
- Interval containment errors invalidate the bound. A calibrated interval set
  needs separate coverage evidence; this script supplies none.
- Fixed-frame prediction rankings are not closed-loop policy rankings. Actions
  change subsequent observations and outcomes in the game.

The [missing-event extension](#missing-event-extension) below handles bounded
optional counts and known-negative bins. Unknown command/effect mappings still
require a further model layer, which is not implemented here. Tightening
intervals or counts solely to get a preferred ranking invalidates the result.

## Missing-event extension

[missing_event_bounds.py](missing_event_bounds.py) computes exact paired bounds
when every annotated interval requires a distinct event, but up to K additional
events may occur anywhere outside explicitly known-negative bins. Additional
events may occur inside annotated intervals too. A bound K at least T permits
all possible counts at the stipulated one-event-per-bin resolution; it makes
no completeness assumption. At least one positive interval is required by this
reference implementation.

```powershell
uv run --no-sync python docs/research/executable-imitation/missing_event_bounds.py
```

The algorithm runs separate passes for each possible total event count k. Within
a pass, F1 denominators are fixed at k+|A| and k+|B|. A used-event counter joins
the product state; a truth event need not satisfy an unmatched interval. Greedy
matching still determines whether the required intervals are covered. Taking
the envelope of the per-count bounds yields the sharp bound over all allowed
counts. This avoids incorrectly applying the annotated count m as the F1
denominator when missing events are possible.

The extended implementation agrees with exhaustive truth/assignment/matching
enumeration on **3,120 cases**: horizons one through three; all single intervals
plus a duplicate full-horizon interval pair; every prediction-set pair;
no negative bins versus the last bin known negative; and tolerances (0,0),
(1,0), (0,1). Every feasible total count is compared, not only the final envelope.

Two exact examples show why the extension matters:

| Evidence and predictions | Assumption | Sharp A minus B F1 |
|---|---|---|
| Event at 0; A={0}, B={0,1} | No missing events | [1/3,1/3] |
| Same | One additional event may exist | [-1/3,1/3] |
| Same | Bin 1 independently verified event-free | [1/3,1/3] |
| Original three-window example above | All possible extra events in its four-bin horizon | [4/21,4/15] |

In the first case, one missed event can reverse the ranking. In the last case,
the ranking survives every admissible missing-event placement. Missingness
therefore need not make all comparisons useless, but it must enter the evaluated
set. A verified negative can resolve a comparison that additional positive
timing precision would leave ambiguous.

These examples do not measure the missing-event rate of the HUD reader. Setting
a small K requires external evidence; it cannot be chosen because it narrows the
bounds favorably. Extra-event tolerance is a sensitivity analysis, not a learned
missingness probability. The code does not handle false annotated positives or
uncertain event identities. Retain those as separate failure modes.

Related primary work strengthens the baseline requirements:
[Schroeter et al., AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17145)
already combine soft temporal localization with counting-based sparsity for
misaligned point-event labels. [Bilen et al., ICASSP 2020](https://arxiv.org/abs/1910.08440)
propose robust sound-event evaluation and PSDS to reduce dependence on operating
points and annotation subjectivity. These are important comparisons; neither
abstract establishes an equivalent sharp paired bound over missing-event
placements. A full algorithm-level comparison remains necessary before claiming
that this temporal formulation is new.

## Prior art and the remaining contribution question

[Polo et al., NeurIPS 2024](https://arxiv.org/abs/2312.04601) already formulate
weak-supervision performance evaluation as partial identification, including F1
bounds using marginal constraints and convex optimization. Their general
bounded-function formulation also makes a difference of model scores a natural
comparison target. Neither partial identification nor paired comparison is a
novelty claim here. The candidate technical contribution is the structured
temporal identified set with one-to-one matching and an exact product-state
algorithm; novelty and superiority to existing formulations remain to be checked.

[Yang et al., NeurIPS 2019](https://papers.neurips.cc/paper/8317-imitation-learning-from-observations-by-minimizing-inverse-dynamics-disagreement.pdf)
already study the gap between observation and action imitation via inverse
dynamics disagreement. Their analysis assumes shared dynamics. This project
must separately account for source/target interfaces and cannot interpret
event-metric superiority as a bound on task reward without additional assumptions.

The useful next experiment is whether paired bounds settle more model comparisons
than separate metric bounds at the same annotation budget on reviewed development
evidence. If they do, annotation can focus on genuinely unresolved comparisons.
That selection rule also needs comparison against existing decision-focused
acquisition methods; it is not a new principle merely because it uses event times.

This is a tested method for one well-defined evaluation problem. It strengthens
the proposed research program, but neither doctoral originality nor a better
Spider-Man policy has been established by these synthetic tests.
