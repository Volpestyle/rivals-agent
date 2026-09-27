# Exact paired event comparison can forget expired history

Research implementation and scaling check, 2026-09-26. No production evaluator,
training, admission, source labels, or live input changed. This improves the
[paired event reference](paired-event-evaluation.md), under the same exact-count,
distinct-event and fixed-clock assumptions. It does not make those assumptions
true for an arbitrary replay export.

## Result

The [frontier implementation](frontier_event_bounds.py) retains only unresolved
evidence and prediction positions that can affect a future match. All **5,644**
independent exhaustive comparisons pass, including asymmetric tolerance,
cross-boundary matching, nested intervals, empty truth and impossible evidence.

One local standard-library run gave these descriptive timings:

| Problem | Frontier time | Peak states |
|---|---:|---:|
| 100 synthetic events, nonoverlapping intervals | 0.71 ms | 2 |
| Same 100-event input, original reference | 18.28 ms | not instrumented |
| 1,000 synthetic events, nonoverlapping intervals | 6.53 ms | 2 |
| 300 synthetic events, maximum overlap 4 | 12.53 ms | 12 |
| 300 synthetic events, maximum overlap 16 | 55.75 ms | 48 |
| 16 nested synthetic intervals | stopped at state cap | exceeded 20,000 |

These are single-run wall times, not a controlled hardware performance study.
The speed difference includes exact integer rewards in place of repeated
Fraction arithmetic as well as the state reduction; no isolated attribution is
claimed. The nested example is a material limitation, not a completed bound.
The research cap raises an error and returns no interval rather than silently
approximating or pruning a possible truth.

## Why the state reduction is exact

At time t, an evidence interval that has expired must already be matched on
every viable path. An interval whose release is in the future has not yet been
matched. Only currently available, unmatched intervals distinguish future
possibilities. Store their IDs ordered by deadline, release and identity; on an
event, match the first. This is the same earliest-deadline transition as the
reference. New intervals are inserted only at their release time.

For each prediction sequence, a prediction earlier than t minus the early
tolerance cannot match this or any later truth. Advance the cursor past it even
when no event occurs. Doing so changes no past match and earns no reward.
Predictions beyond t plus the late tolerance cannot have been consumed by an
earlier truth. Cursor differences therefore occur only inside a local tolerance
window. The cursors remain connected across evidence intervals: the algorithm
does not split components where a prediction could bridge their boundary.

Prefixes with the same pending intervals and normalized cursors have identical
future choices and rewards. Keeping only minimum/maximum accumulated rewards
thus preserves both exact extrema. With m fixed events, use integer weights
2(m+|B|) and -2(m+|A|), then divide by (m+|A|)(m+|B|) at the end. This is exactly
the paired F1 difference; no floating-point approximation enters the search.

Let w be the maximum number of active evidence intervals, and k_A,k_B the
maximum counts of predictions in a tolerance window. At a fixed time layer the
state count is at most

    2^w (k_A+1)(k_B+1).

The implementation's tuple sorting costs O(w log(w+1)) per state; global cursor
floors use binary searches per time bin. Under unit-cost integer arithmetic a
conservative bound is O(m log(m+1) + T log(|A|+|B|+2) +
T 2^w (k_A+1)(k_B+1) (w+1) log(w+2)). Two state layers are retained. Exact
arithmetic and IDs carry their usual bit-length costs. This explains why a long
low-density sequence can be cheap while a short nested example is expensive.

## Project-shaped timing check, without invented event labels

The same hash-verified development exports used in the timing pilot provide
95 and 78 unique first-interval keys. Only their geometry is used here. Decimal
endpoints are rounded outward to a 100 ms grid, and artificial prediction sets
are placed at unique lower versus upper endpoints with one-bin early/late
tolerance. These are **not model predictions**, and no policy scores are reported.

The constructed problems have 6,828 and 8,013 bins, maximum grid overlap one,
and complete in 7.49 and 9.61 ms with peak three states. The
[report](frontier-event-benchmark.json) records source and script hashes.
The exercise shows tractable computation on this timestamp geometry. It does
not prove event identity, completeness, timing coverage or benchmark eligibility.
The accepted replay lane's reported overlap groups are a different source and
representation; the synthetic overlap tests must not be called measurements of
that corpus.

## Prior art and research value

Forgetting completed jobs and parameterizing by overlapping windows is established
in scheduling. [Single-machine scheduling with release times, deadlines, setup
times, and rejection](https://doi.org/10.1016/j.ejor.2020.09.042) explicitly uses
overlap width for exact dynamic programming. [Scheduling unit dependent tasks
with time windows](https://doi.org/10.1016/j.dam.2020.11.024) similarly parameterizes
by interval-graph pathwidth. This search does not establish novelty for the
paired-F1 specialization, and the general frontier technique is not an invention.

The useful result is narrower: exact shared-truth comparison need not enumerate
whole-session event assignments when local ambiguity is small. It removes one
computational concern from the research proposal. An empirical comparison against
alternative evaluators, verified event evidence, and a demonstrated benefit to
policy selection or annotation cost are still required. This is not improved
gameplay and is not yet a publishable contribution.

```powershell
uv run --no-sync python docs/research/executable-imitation/frontier_event_bounds.py --verify
uv run --no-sync python docs/research/executable-imitation/frontier_event_bounds.py --root scratchpad/research-executable-imitation/b0-metadata --output scratchpad/research-executable-imitation/frontier-reproduction.json
```
