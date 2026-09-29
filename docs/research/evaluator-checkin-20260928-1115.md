# Full03 advances the IDM; choose the next source before the next fit

2026-09-28, 11:15 CDT check-in. Outside research advice for herdr-lead and
idm-owner / VUH-1353. This note recommends a sequence; it authorizes no compute,
new lane, split change, or corpus labeling.

Full03 is useful progress for the data engine. All three epochs and seven stages
completed, with recoverable epoch checkpoints and the final artifacts collected.
The [owner's result](../evidence/idm-expanded-full03-result-20260928/report.md),
commit `c10717f`, is the result record. The reported cost is about $21.9 from the
lead's metered delta, not an invoice. No new execution or raw-data inspection was
needed for this assessment.

## What the result supports

On the two existing range-development sessions:

| Measure | Previous IDM | Full03 |
|---|---:|---:|
| Yaw MAE, degrees per target interval | 0.2835 | 0.2488 |
| Derived pitch MAE | 0.2554 | 0.2359 |
| TRAIN-rate Combo precision / recall | 42.19% / 56.25% | 49.11% / 57.29% |
| TRAIN-rate Jump precision / recall | 35.74% / 41.39% | 42.05% / 49.22% |
| TRAIN-rate Web precision / recall | 42.67% / 43.23% | 49.20% / 48.18% |

Both sessions improve in camera mean error. Camera answered subsets differ, and
the old/new training backend also changed; this is descriptive improvement,
not an isolated causal estimate for adding match data. Press rows are identical.
The fixed-0.5 Web result regresses, so the improvement depends on the specified
threshold method. Rate matching is not probability calibration. Button labels
should remain unknown where reliability is unestablished: roughly half the
predicted presses here are false positives.

A useful extra clue comes from the already-saved camera diagnostics. Accumulated
one-second error matters when many plausible interval labels are imitated:

| Absolute one-second sum error, degrees | Previous IDM | Full03 |
|---|---:|---:|
| Yaw median / mean / p90 | 4.2743 / 8.4244 / 20.7997 | 3.4096 / 6.6742 / 16.2373 |
| Derived pitch median / mean / p90 | 4.1372 / 7.5128 / 18.9101 | 4.1739 / 6.5239 / 15.2744 |

Yaw improves across these summaries. Pitch mean and tail improve, while its
median is essentially flat. Still-row interval MAE worsens on both axes. These
are each model's eligible windows, not a matched-window comparison (yaw counts
772/795; pitch 715/707). They argue for keeping axis, moving/still, coverage and
accumulated-error summaries in the existing diagnostic, not declaring a new
acceptance threshold. They do not measure live controller drift.

Sources: [previous saved camera report](../evidence/idm-expanded-full03-launch-20260928/baseline-camera.json)
and [full03 saved camera report](../evidence/idm-expanded-full03-result-20260928/artifacts/camera/camera.json).

## The next investment

The lead is right that persistence using the previous **true** camera input is
unavailable on unlogged footage. Losing to that oracle does not by itself reject
the IDM. However, beating zero establishes useful signal, not sufficient label
quality or a solution to policy turning.

The proposed range turning pilot needs its source stated. If it replaces labels
on footage where James's admitted input logs already supply camera targets, it
adds no demonstration coverage. A teacher might denoise those targets or make a
simpler imitation task, but that is a separate hypothesis requiring the native
labels as the control. It is not automatically the data-expansion experiment or
the fix for the prior causal policy's yaw failures. If the pilot instead adds
previously unlogged footage, identify that source and its applicable transfer
qualification. The established [VPT route](https://arxiv.org/abs/2206.11795)
uses an IDM to expand supervision to additional unlogged demonstrations.

My priority would be the **existing range-to-match development diagnostic**
before choosing another full refit or this policy pilot:

- **Question:** does frozen full03 supply useful camera labels on admitted match
  material outside its fit, and what failure would another match expansion fix?
- **Cheapest useful comparison:** when the already-owned later-match stores are
  ready, score bounded eligible development windows with logged truth, frozen
  full03, the prior checkpoint and zero; retain the existing axis, motion,
  accumulated-error and coverage summaries. Size the read through idm-owner;
  this note does not launch it or claim it is free.
- **Decision:** if the gap is small and supported across sources, prioritize the
  remaining camera-first Gate 2 prerequisites and transfer read. If the gap is
  material, use its slices to choose the next refit's composition or label fix.
  If a result is ambiguous, stop at the bounded diagnostic and name the missing
  fact rather than automatically buy another full fit.
- **Consumer and scope:** idm-owner already owns this diagnostic and the later
  match preparation; herdr-lead chooses the next funded action. Later matches
  marked TRAIN remain TRAIN. Not being in this fit makes an exploratory
  diagnostic possible, not a new confirm holdout. Preserve the sealed Gate 2
  pairs and freeze contract. Do not select checkpoints on those pairs.

Continue the useful store preparation. Adding later matches could materially
improve the current approximately 92% range / 8% match training mix. But let the
newly available checkpoint tell us where labels fail before defaulting to the
next large run. A bounded policy pilot remains reasonable with a distinct
hypothesis and native-label baseline; it need not wait for autonomous gameplay
to justify its existence. No new review ceremony is needed for this decision.
