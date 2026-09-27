# Next camera bet: learned yaw from visible bot tracks

2026-09-27, explore-policy. **Proposal only; $0 spent, no new fit or game input.**
The NitroGen confirmation remains unchanged and running. This is one proposed next
experiment after its result, not authorization for a third explore arm.

## Why yaw, and why this input

Seed-0 no-history NitroGen median camera MAE was 1.185917° versus zero's 1.224645°,
but the improvement came from pitch: 0.589019° versus 0.714106°. **Yaw was worse:
1.782815° versus zero's 1.735184°.** The joint average does not establish useful
horizontal turning, let alone autonomous target acquisition. Confirm reports will
retain both axes and all paired differences; the judge is frozen.

The existing [target-bearing probe](target-bearing/result.md) is a warning against a
cheap nearest-bot rule. In 1,454 found-target TRAIN samples, nearest-bot bearing had
only about r=.13 and 59% next-turn sign agreement. The bot nearest the crosshair was
not always the one James fought. Green-only detection missed almost everything on
the main-account red-enemy session. These are limitations of that feature and probe,
not a ceiling on all target-conditioned policies.

The [camera-label analysis](camera-targets/analysis.md) also shows that zero is the
unconditional yaw median even though only about 19% of labels are exactly zero.
A weakly conditioned head can therefore minimize absolute error by barely turning.
Changing horizons or a decoder alone has already been explored; it would not supply
the missing direction/target information. Native bot boxes are also reduced to
roughly 4/11/26 pixels at p10/p50/p90 in the global policy view, followed by spatial
pooling. Precise horizontal geometry is a plausible missing cue, not a measured fact.

## First experiment to propose

**A learned, yaw-only head that receives all causally tracked visible bots, with the
existing human yaw commands as supervision.** Keep the selected frozen NitroGen
backbone and visual recurrent representation. Feed a small masked set of bot tokens
to a learned attention/readout head: normalized horizontal/vertical position, size,
causal image velocity, confidence, track age and explicit visible/unknown flags.
No single bot is declared the target by a nearest/largest rule. The head learns
which, if any, visible bot matters from the same demonstrations and visual context.
It still emits the ordinary yaw action; geometry never directly drives the pad.
Past **pixels**, not past human or predicted action commands, provide track motion.

Freeze the existing press, movement and pitch paths for this initial experiment.
Train only the yaw readout/geometry fusion, retaining the current yaw labels, units,
31-bin objective and median decode. Compare with the same-size yaw readout trained
with bot tokens masked, on identical windows/seeds/schedule. That isolates the value
of object geometry while protecting the confirmed press result. Use a preselected
checkpoint, such as candidate seed 1 if confirmation succeeds; do not choose the
checkpoint with the best observed camera result. A new paid budget would be a
separate lead decision after confirmation.

This is learned policy conditioning, not scripted aiming. In particular, do not
replace human yaw labels with `atan(nearest_bot_offset/focal)`: that would silently
label the wrong intended targets, depends on unaccepted FOV assumptions, and can
turn a detector into an aim controller without evidence. Normalized pixel geometry
does not need a new degrees-per-pixel calibration. Missing detections are unknown,
not a centred bot or proof that no bot exists. Offscreen searching remains a real
limitation; a target-visible gain alone cannot satisfy “playable.”

## Cheap prerequisite and evidence that would justify it

Before extraction or a fit, inspect a small, fixed native TRAIN sequence sample,
covering both enemy colors, left/right off-centre bots, several bots, close fragments,
occlusion and no visible bot. Use the existing pixel perception/tracking code where
it works. Check timestamps and that tracks use no future frame. Measure false bots,
missed visible bots and identity switches; do not equate current nearest-bot identity
with human intent. The existing probe's 20 inspected single frames do not establish
track identity or main-account recall. If the causal tracks are unreliable, fix that
observed prerequisite before spending a fit. No new recordings or sealed data are
needed for this bounded audit. It is proposed $0 Mac work, queued with the lead.

The proposed model test must improve **yaw MAE against zero and the matched masked-token
control**, plus yaw sign/onset accuracy on actual turns. Report left/right separately,
false turning during human-still intervals, target-visible versus missing/ambiguous
strata, and press retention. Compare real tokens to session-preserving shuffled tokens
as a diagnostic: more motion alone is not success. All-frame yaw remains necessary,
so target-visible gains cannot hide worse searching. Do not treat offline predicted
bearing reduction as an observed closed-loop result. Only a later authorized,
bounded practice-range sitting can show that it moves, turns toward bots and fights
autonomously. No live controller change or scripted-aim fallback is proposed here.

## $0 Mac side-by-side after confirmation

Use one fixed segment from frozen-dev session `20260923T171533-187Z-33696-5`:
the first continuous eligible 30-second interval after a 32-step warm-up. If no such
interval exists, report that and select the longest eligible interval by the same
rule, rather than searching for a favorable model result. Fix exact frame/row IDs
and timestamps before running inference. Reuse the existing native video or a
clearly labelled admitted frame cache; no new capture, sealed source or game input.

One synchronized video, three panels: **James recorded**, **old H1 epoch 26**, and
**NitroGen candidate seed 1 epoch 26** if the confirmation permits advancing it.
Every panel shows the same recorded frames; overlays show timestamp, semantic press
events, holds and yaw/pitch command traces. Main comparison uses TRAIN-calibrated
cutoffs for both models; retain fixed-.5 counts/F1 in the companion JSON for the old
incumbent reference. Reuse a stored TRAIN cutoff receipt if available; otherwise
compute it once from authorized TRAIN only on the Mac, never tune on this clip.
Both models run with their registered self-fed inputs and reset/warm-up rules.

Caption it **offline replay of James's frames — predicted controls, not model gameplay**.
The models' actions do not change those recorded observations. Show every frame in
the selected interval, including misses and long idle/incorrect turns; no cherry-picked
montage. Pin checkpoints, frame interval, configs, cutoff receipts and row-wise outputs.
The video explains button timing and the yaw bottleneck; it does not prove playability.
Inference and encoding run on the $0 Mac queue after the lead's slot, not on the PC GPU.
