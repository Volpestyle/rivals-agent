# First archived-data result: timing uncertainty cannot rescue the old B0 model

2026-09-26. James authorized using existing development artifacts provided the
research does not impede current work. This is an exploratory, read-only
reanalysis of the completed format-5 H2 B0 experiment, not a current Round 3
evaluation or a change to any production acceptance gate.

## Finding

The fitting-median baseline has lower mean absolute timing error than the learned
model for **every assignment of true event times inside the stored timing
intervals**, on both historical development folds:

| Historical fold | Common-support WEB rows | Bound on mean true error: model minus median |
|---|---:|---:|
| Day fit, Req development | 524 | +0.076075 to +0.281482 seconds |
| Req fit, Day development | 410 | +0.024427 to +0.189768 seconds |

Positive means the model is worse. This is conditional on the stored intervals
containing the target event time. It is not a confidence interval, an estimate
over new sessions, or a gameplay result. Overlapping forecast windows remain
overlapping; these are not 934 independent events.

The universal claim applies only to the common-support rows: 524 of 670 and
410 of 532 positive WEB forecast windows, respectively. It does not cover the
146 and 122 excluded positive windows. A neighboring read-only review reproduced
both folds and reported that exclusions arise from decision/horizon crossings
and ambiguous first events; its additional clipped-interval sensitivity results
have not been independently reproduced here. Label-side exclusion does not by
itself establish representativeness beyond the retained rows.

The original experiment already reported `no_improvement`: WEB occurrence F1
improved, while distance-outside-interval timing error worsened. The new result
strengthens only the timing interpretation. Even favorable exact locations
within the retained intervals cannot reverse the aggregate timing ranking.
The accepted historical conclusion remains unchanged.

## What was computed

For each existing common-support timing row, take model delay a, fitting-only
median delay b and stored interval [l,h]. Define d(y)=|a-y|-|b-y|. This function
is monotone between its constant tails, so its extrema over [l,h] occur at the
endpoints. Average the lower endpoints and the upper endpoints across the same
rows as the original evaluation. Calculations use exact fractions of the stored
binary floating-point values; reported decimals are rounded presentations.

Each row's possible truth is allowed to vary independently. Some rows may refer
to the same underlying event, so this is a relaxation of any jointly consistent
event assignment. That can widen the bounds; it cannot invalidate the positive
lower bound for a consistent assignment contained in the product set. We make
no claim that these endpoints are sharp under shared-event constraints.

This paired absolute-error calculation is a small analytic baseline, not the
new event-F1 DP and not an algorithmic novelty claim. It was selected because
the available archive contains overlapping conditional timing forecasts, which
cannot be passed unchanged to a distinct-event sequence evaluator.

## Provenance and verification

Source: `/Users/james/dev/rivals-agent/data/experiments/b0-multilabel-format5-h2/`.
Its README identifies the accepted two-source development corpus and explicit
source selection, with no sealed payloads. Both folds' `predictions.npz`,
`windows.json` and `report.json` were copied to the local scratchpad.
Every copied payload's SHA-256 matches the archive's `SHA256SUMS`; copied README
SHA-256 also matches. No model checkpoints, raw media or feature arrays were copied.

The [analysis script](timing_bounds_pilot.py) uses only the Python standard library.
It reads the named numeric NPY members, rejects unsupported formats, verifies
source hashes and checks shapes, positive timing support and interval limits.
It reproduces the original common-support counts and both reported interval
errors within 1e-6 seconds before reporting new bounds. The [result JSON](historical-timing-pilot.json)
records exact rational bounds, script/source hashes and row-level ranking counts
as aggregates. The complete two-fold calculation took approximately 0.07 seconds
of local wall time. No model was loaded or executed.

```powershell
uv run --no-sync python docs/research/executable-imitation/timing_bounds_pilot.py --root scratchpad/research-executable-imitation/b0-metadata --fold day-to-req
uv run --no-sync python docs/research/executable-imitation/timing_bounds_pilot.py --root scratchpad/research-executable-imitation/b0-metadata --fold req-to-day
```

## Keeping current work unaffected

Before analysis, the existing job-board snapshot at 2026-09-27 00:12:52 UTC
reported Mac GPU 54%, a memory-pressure warning and 62.5/63.5 GB swap usage.
This ruled out adding research inference or training on that machine. Transfers
used named finalized files, capped at 4,096 Kbit/s, totaling under 5 MB including
metadata. Computation ran locally on CPU. Timed-out read-only SSH clients were
terminated by their own bounded subprocess calls; no existing job was stopped.
Production code, active experiments, source labels and evaluation gates were
not modified. The resource snapshot establishes why load was kept small; it is
not a measurement that every transfer had literally zero system impact.

## Consequence for the research

There is now a concrete real-data example of a useful comparison surviving
uncertain timing labels. It supports investigating paired uncertainty-aware
evaluation, but does not validate the event-F1 method, reduce measured annotation
cost, establish publication novelty, or improve the current agent. The next
event-level experiment still needs compatible timestamped predictions and
reviewed distinct event evidence; the archive access problem is resolved, while
the representation mismatch remains explicit.
