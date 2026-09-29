# Next offline policy bet: causal turn initiation

2026-09-29, evaluator advice for herdr-lead / VUH-1346. Recommendation only: no fit, provider call, raw dataset inspection, compute reservation or new lane was started.

**My next offline bet is a small native-label turn-initiation probe at a short action timescale, using the existing frozen visual representation.** Test whether causal images predict the onset and direction of a turn over the next approximately quarter-second. This is a changed supervision hypothesis, not another encoder, sampler optimization or larger regression sweep. Keep the end-to-end policy goal; a successful probe would justify changing its yaw objective, not replacing the product with scripts.

## Why this is the next uncertainty

The [confirmed no-history policy](../evidence/nitrogen-nohistory-confirm-20260927/confirmation-report.md) has yaw MAE 1.771697 versus zero's 1.735184, despite useful button/pitch results. Aggregate yaw MAE alone cannot tell whether it sees impending turns, mostly reacts after them, or misses direction while predicting movement. The code already uses **31 camera classes** and tests median/mode/expectation decoders (`policy/range_bc/model.py`, `explore_camera.py`). Merely proposing discretization or swapping the decoder would repeat existing work.

The [full NitroGen actor](../evidence/nitrogen-vl-cache-20260928/REPORT.md) remains parked after exact-output caching still measured p95 344.696 ms against the 150 ms stop. This is an integration/runtime negative, not proof that pretrained action policies cannot transfer. IDM remains parked with full03 preserved; the [reader/support result](../evidence/idm-reader-support-20260928/report.md) did not establish source qualification. Neither pause obliges a new custom architecture bet.

The new [native yaw measurement](../evidence/camera-native-turn-20260929/README.md) resolves one executor rate at one deflection. It does not improve policy labels or demonstrate learned target selection. Finish the current-profile calibration and a brief changed-control compatibility check, but do not revive the superseded standalone scripted-ten-encounter campaign as a research gate; the [21:07 amendment](policy-next-bet-scripted-baseline-20260928.md) already withdrew it.

## Bounded proposed experiment

1. Reuse the admitted native-label TRAIN/frozen-dev placement and existing feature caches. No IDM labels, new source admission, sealed payloads or full-actor integration. Before fitting, inspect existing onset/decoder reports to avoid rerunning an already answered slice.
2. Define one target from cumulative signed native yaw in the next 0.25 seconds at original timestamps: left / no meaningful turn / right, plus whether this starts after a quiet pre-window. Choose the quiet/noise threshold on TRAIN and fix it before development results. Mask unknown labels and windows crossing cuts. Inputs stop at the prediction time; future pixels are never inputs. Quarter-second labels do not authorize quarter-second open-loop game control.
3. Fit one small temporal classifier on the frozen representation. Compare a matched nonvisual baseline trained with the same objective, a TRAIN class-prior baseline, and the existing no-history checkpoint's current prediction held constant across the target interval (declare that extrapolation before reading scores). Do not sum predictions made from future recorded images: that would give the comparator future evidence. Include a real-versus-shuffled-image inference diagnostic, labelled as a sensitivity test. True human action-history persistence may be reported as a privileged oracle only; it is not an available no-history policy baseline.
4. Report onset precision/recall, left/right discrimination on moving targets, false turn starts during still periods, probability calibration and per-session results. Preserve the original all-frame yaw metric beside these diagnostics. Do not turn a sparse-event score into a claim of better gameplay, and do not tune thresholds to make the reused dev set look better.
5. Budget one local probe with no paid compute, to be sized/authorized by the lead and run on the Mac queue. Stop after that comparison. Advance only if causal visual input adds useful turn-onset/direction information over the matched nonvisual and prior baselines without hiding a false-turn increase. If it does not, inspect intent ambiguity or target-conditioned supervision before another fit; do not launch an architecture sweep.

The new axis is **future integrated turn initiation**, whereas earlier H=4/H=8 action-chunk experiments predicted per-step full-action sequences. That distinction is a hypothesis to test, not a reason to assume the probe wins. Onset support may be insufficient; report its counts before interpreting any score.

## Research context and next consumer

[Behavior Transformers](https://arxiv.org/abs/2206.11251) motivates treating multimodal demonstration actions as distributions, and [ACT](https://arxiv.org/abs/2304.13705) motivates reasoning over action sequences. Neither paper establishes that this Rivals dataset contains visually predictable yaw intent, and neither warrants a wholesale rewrite here. The proposed experiment borrows the temporal/multimodal question while reusing the current model and data boundary.

Consumer: herdr-lead decides whether to dispatch one bounded VUH-1346 probe. A positive result can inform an end-to-end yaw-head objective with buttons/pitch retained, then the existing baseline-compared learned evaluation. A negative result is still useful if it rules out short-timescale visual turn initiation under the current representation. IDM qualification can resume on its own named evidence; it does not wait for scripted kills or this probe.
