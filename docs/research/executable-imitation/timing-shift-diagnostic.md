# A constant timing correction cannot rescue the archived model

2026-09-26. Research-only follow-up to the [historical timing pilot](historical-timing-pilot.md).
Uses the same finalized, hash-verified development exports. No new transfer,
model inference, training, gameplay, source-label edit or production change.

## Result

The historical timing model remains worse than the fitting-median baseline even
after optimizing a separate constant offset for each development fold, clipping
predictions into the two-second horizon, and choosing the most favorable true
timestamp inside each row's recorded interval.

| Fold | Rows | Best optimistic offset | Minimum possible mean error excess over median |
|---|---:|---:|---:|
| Day fit / Req development | 524 | -0.193646 s | **+0.055159 s** |
| Req fit / Day development | 410 | -0.145532 s | **+0.015893 s** |

These positive minima rule out **every constant additive correction in this
clipped prediction family**, conditional on interval coverage and the archived
common-support rows. They are not sampling confidence intervals. The offset is
selected with development outcomes, deliberately giving the correction an oracle
advantage; it is not a correction fitted for deployment or a new held-out result.

Original predictions have standard deviations 0.553323 and 0.470571 seconds.
They are not collapsed constants. In the first fold 154 predictions precede
their intervals and 278 follow them; in the second, 146 precede and 193 follow.
The failure cannot be repaired by a uniform earlier/later shift of these exported
delays. This does not exclude a nonlinear recalibration, shrinkage, better
representation, or state-dependent correction. Nor does it identify which of
those is appropriate, diagnose current Round 3 models, or measure live latency.

## Exact calculation

For prediction a_i, baseline b, horizon H and interval [l_i,h_i], set

    z_i(delta) = clip(a_i + delta, 0, H)
    d_i(delta,y) = |z_i(delta)-y| - |b-y|.

The reported value is

    min_delta (1/n) sum_i min_{y in [l_i,h_i]} d_i(delta,y).

For fixed delta, the inner function is monotone in y, so its extrema occur at
the interval endpoints. As a function of z, its lower and upper envelopes are
piecewise linear; breakpoints lie at l_i, h_i and clip(b,l_i,h_i). Clipping adds
0 and H. Thus it suffices to evaluate offsets formed by subtracting a_i from
these five values for every row. Between consecutive breakpoints the aggregate
is linear; outside the outermost breakpoints every output is clipped constant.
This finite search is global, not a grid approximation or a local optimizer.

All source numbers are converted from their exact binary-float values to a
shared integer time lattice. The search uses integer arithmetic and reports
exact rational means. The script additionally minimizes the upper paired-error
envelope and the original interval-distance loss as separate diagnostics; these
objectives generally select different offsets. Only the lower-envelope minimum
is needed for the all-offset impossibility statement above.

As in the first pilot, row truths can vary independently. Shared-event
constraints could shrink the feasible set and raise this minimum, but cannot
reverse its positive sign. Overlapping rows are not independent event samples.

## Verification and reproduction

[Script](timing_shift_diagnostic.py), [machine-readable result](timing-shift-diagnostic.json).
The script verifies the three source hashes in each fold and reuses the first
pilot's reproduction of original counts and interval metrics before analysis.
It records its own hash and the source hashes. Both folds took approximately
0.95 seconds of local CPU wall time; no remote jobs were started.

The independent small-problem check enumerates one- and two-row problems,
point/interval labels, baseline positions, predictions, clipping plateaus and
half-step offsets/truths. All **1,026** comparisons match for lower-envelope,
upper-envelope and interval-loss minima. The piecewise-linear argument establishes
the continuous search; finite tests alone do not prove it for arbitrary inputs.

```powershell
uv run --no-sync python docs/research/executable-imitation/timing_shift_diagnostic.py --verify
uv run --no-sync python docs/research/executable-imitation/timing_shift_diagnostic.py --root scratchpad/research-executable-imitation/b0-metadata --output scratchpad/research-executable-imitation/timing-shift-reproduction.json
```

## Research consequence and prior-art limit

This eliminates a cheap correction hypothesis before spending training or live
interaction budget. It is a diagnostic specialization of elementary
piecewise-linear optimization, not a claimed novel learning algorithm. A future
training comparison should distinguish timing calibration from useful
state-conditioned information, with fitting-only calibration and fresh evaluation.
The archived folds have already informed this diagnosis and cannot serve as
untouched confirmation of a method designed from it.

Replacing interval-distance loss with a probabilistic censored-event objective
also has close prior art. [Yanagisawa (ICML 2023)](https://proceedings.mlr.press/v202/yanagisawa23a.html)
studies proper scoring rules for survival analysis. The authors'
[cenreg repository](https://github.com/CyberAgentAILab/cenreg) explicitly supplies
interval-censored scoring and calibration and cites Yanagisawa and Akiyama's
ICML 2026 paper on that subject. Its README distinguishes independence or
non-informative assumptions from dependent censoring handled using an assumed
copula. The 2026 full PDF was blocked by OpenReview's browser verification during
this search, so a theorem-level comparison remains outstanding. These sources
already prevent treating a generic censored timing loss as a new contribution.
Whether their assumptions fit visibility-dependent HUD evidence remains a real
question; no such applicability has been established here.
