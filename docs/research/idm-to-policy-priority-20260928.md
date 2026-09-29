# Next step after the mixed IDM refit

2026-09-28, 16:19 CDT. Outside evaluator; requested by herdr-lead. Advisory only.

**Pause new IDM refits, retain full03, and choose (c): size one full NitroGen policy
adaptation on existing native labels. Continue full03 source qualification toward
(b); defer (a).** This pauses model tinkering, not the data engine. Existing owners
and advancement gates remain in place; this note authorizes no execution.

The [new result](../evidence/idm-match-refit-mac-result-20260928/report.md)
trades roughly 15% lower still-yaw error for 3% higher moving-yaw error, with
range-dev regressions. Both models already beat zero on pitch in these windows;
the refit did not uniquely unlock that. “Still” includes small real motion, so
this is not yet evidence for a binary stationary/moving head. Different training
composition and backend also prevent attributing the trade-off solely to added
matches. Preserve the new checkpoint, but do not promote it.

The more consequential uncertainty is whether a **causal policy learns useful
turning from trusted demonstrations**. The confirmed custom head still loses to
zero on yaw (1.7717 versus 1.7352). Accurate inverse reconstruction, using future
frames, does not establish which turn a policy should choose from current/past
pixels. Neither failure establishes that more data is useless.

1. **Make the next policy decision about the full pretrained actor.** Our
   [existing assessment](nitrogen/policy-adaptation-vs-heads-20260928.md) documents
   that only NitroGen's vision weights have been tested here. Its released action
   policy is a different transfer hypothesis, supported as a research direction
   by the [official implementation](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/README.md),
   not evidence of Rivals competence. Remove “IDM labels qualified” as a prerequisite
   **for sizing a native-label arm**. Existing logged demonstrations supply the
   supervision; preserve their trusted labels.

   Reuse the memo and retained weights for one bounded feasibility decision:
   exact action/mask/cadence round trips; whole-sampler latency and memory; and
   trainable scope, throughput and integration cost. Use the actual 25-dimensional,
   18-step checkpoint with 16 sampling iterations, not the old memo's defaults.
   Unknown actions stay masked. Calibration remains necessary for valid stick
   targets, but need not block inspecting the model or sizing its computation.
   Stop before extensive integration if the measured runtime or cost is impractical.

   If feasible, recommend one bounded native-label adaptation against the current
   custom-head baseline and zero motion on the same permitted development sessions.
   Fix the endpoint before fitting. Useful evidence is yaw improvement with moving
   and left/right slices, limited false turns on zero-input intervals, and retained
   pitch/button behavior. Do not claim action pretraining caused a win without a
   matched initialization control.

2. **Finish the prepared camera/FPS sitting as the next physical attempt.** The
   [current sitting plan](../lanes/live-loop-sitting-20260927.md) is ready after its
   repairs, but accepted yaw maps for the current alt settings and completed FPS
   A/B/A remain outstanding.
   This resolves actuator/runtime uncertainty, not policy learning. Full-turn yaw
   does not establish short-pulse response, focal length or pitch calibration.
   Reuse the accepted plan; no repeat request for James's completed recordings.
   Later live evidence must include target centering/reacquisition and actual
   combat outcomes against the existing scripted comparison, not merely movement.

3. **Advance the data engine with frozen full03, not another refit.** Complete the
   existing Gate 2/source qualification for a bounded new-footage shard, yaw first;
   include other heads only if separately qualified. Accuracy, uncertainty and
   usable coverage count; plausible overlays alone do not. Once qualified, compare
   native-only training with native plus that shard using the same policy,
   evaluation and declared training budget. This tests actual corpus expansion.
   Reopen IDM architecture work if a specific source/coverage requirement fails,
   or downstream evidence implicates pseudo-label error. Live policy success is
   not a new prerequisite for IDM qualification.

Lead is the decision consumer; explore-policy, live-loop and idm-owner retain
their respective work. No new lane or parallel roadmap is needed.
