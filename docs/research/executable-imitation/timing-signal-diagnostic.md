# Poor timing error does not establish absence of timing signal

Research diagnostic, 2026-09-26. Same archived development exports as the
[timing pilot](historical-timing-pilot.md); no training, inference, transfers or
current-experiment changes. This follows the [constant-offset exclusion](timing-shift-diagnostic.md).

## Finding

Under independently varying row truths inside their recorded intervals, the sign
of the covariance between predicted and true delays is **not identified**:

| Fold | Covariance range (seconds squared) | Corresponding least-squares slope range |
|---|---:|---:|
| Day fit / Req development | -0.076887 to +0.093175 | -0.251127 to +0.304327 |
| Req fit / Day development | -0.052775 to +0.080332 | -0.238329 to +0.362775 |

Thus these marginal timing intervals alone do not tell us whether to preserve or
reverse the direction of the model's centered predictions. This is not evidence
that no useful signal exists, nor that a negative association is jointly feasible
under all shared-event constraints. The independent-row identified set is a
relaxation, and its ambiguous sign is an inconclusive result, unlike the previous
strictly positive error lower bounds, which survive further constraints.

## Calculation and interpretation

Let x_i=a_i-mean(a), V=mean(x_i squared), and C=mean(x_i*y_i). Since mean(x)=0,
C is the empirical covariance regardless of the unknown mean of y. Its extrema
over the product of intervals are

    C_lower = mean(min(x_i*l_i, x_i*h_i))
    C_upper = mean(max(x_i*l_i, x_i*h_i)).

For a constant baseline b and an **unclipped** centered linear correction
p_i=b+alpha*x_i, the change in squared error is exactly

    mean((p_i-y_i)^2 - (b-y_i)^2) = alpha^2*V - 2*alpha*C.

The hindsight-optimal slope is C/V. This yields the table's slope ranges without
fitting labels to interval midpoints. Because each covariance range contains
zero, the worst-case squared-error comparison in this restricted correction
family chooses alpha=0. That conservative choice is a property of the evidence
set and correction family; it does not prove that the baseline is universally
optimal, that the model contains no nonlinear information, or that clipping
would preserve the formula. Squared error is a diagnostic here, not a replacement
for the archived absolute-error acceptance metric.

Calibration and discrimination are already distinct concepts in forecast
evaluation; see [Gneiting and Resin, Regression Diagnostics meets Forecast Evaluation](https://arxiv.org/abs/2108.03210).
The covariance calculation above is elementary interval optimization, not a
novel algorithm or a substitute for that literature's calibration analysis.

## A concrete export boundary

All 934 scored rows' exported relative bounds match the **first retained absolute
interval** minus the forecast anchor within one microsecond. The first intervals
have only 95 and 78 distinct `(session, segment, lo, hi)` keys in the two folds.
Moreover, 86 and 103 scored rows respectively contain multiple retained intervals.
Those observations explain why these exports must not be blindly converted to
934 independent cast timestamps. The key counts are not verified event counts.

A separate exploratory calculation tying identical first-interval keys to one
absolute timestamp also left both covariance signs possible. It did not resolve
event identity and is not used in the reported certificate. The next event-level
study needs reviewed target identity and its relation to repeated forecast rows;
access to more rows of this same representation alone does not supply that fact.

This diagnostic changes the next action: do not prescribe an offset, reverse the
head, or discard its temporal features from these results. Establish event-level
target correspondence and evaluate fitting-only recalibration on fresh material
before claiming a learning improvement. These historical development folds have
already informed the research and cannot be called untouched confirmation data.

## Verification

[Script](timing_signal_diagnostic.py) and [result](timing-signal-diagnostic.json).
Exact rational arithmetic preserves the stored binary-float values. The script
reverifies payload hashes and original timing metrics, records source/script
hashes, and checks target correspondence. Both folds took about 0.125 seconds of
local CPU wall time. No production evaluator or learned model was imported.

An independent endpoint enumeration covers 819 one-, two- and three-row problems,
including constant predictions, point labels and intervals. It checks covariance
extrema and the squared-error identity directly at four slopes. All pass.

```powershell
uv run --no-sync python docs/research/executable-imitation/timing_signal_diagnostic.py --verify
uv run --no-sync python docs/research/executable-imitation/timing_signal_diagnostic.py --root scratchpad/research-executable-imitation/b0-metadata --output scratchpad/research-executable-imitation/timing-signal-reproduction.json
```
