# Ready-pose revision proposal after alt-cam-20260928b

Standalone CPU prototype only. The reviewed runtime, driver, input path and v1
receipt have not been changed. Integration requires live-review's delta-only
pre-run review before landing or use. Arrival stays `reenter.py`, no hand-posing.

## What the retained evidence actually shows

`failure.json` records **deadline during capture**, not a final analyzed-frame
classification. The last `pose_quality_wait` audit (decision 707026.2123768)
has two accepted patches, with top-right NCC .949376 and bottom-left uniqueness
.008447. The next capture at 707026.2232136 crossed the recovery deadline before
analysis; that later image was saved as `refusal-current.png`. On replay it
passes the current v1: top-right NCC .950482 provides the third patch. Its
correlation is .945023, rather than the prior audit's .945177.

Thus the saved image is the exact terminal capture, but its attached audit
belongs to the preceding analyzed frame. This is a retention association bug,
not evidence that the guard analyzed and wrongly rejected a passing frame.
The preceding exact audit image is not in the 1 Hz journal. Frame 150 at
707025.5753913 reproduces the two-patch refusal, and the prototype accepts it.
Eight of the nine last retained guard frames pass the prototype; frame 148
still safely refuses inconsistent motion. Neither sparse samples nor these
controls establish that the full live recovery sequence would succeed.

The fading controller toast is outside the scenery band (native band x1320–2380,
y240–840; toast is near the bottom-right HUD). It does not directly enter these
patch metrics. Its presence remains the lead-recorded ready-inspection deviation.
Training bots and animated scenery do occur inside the scene band; pose proof
is not a guarantee that every piece of scene content is static.

## Proposed delta for findings 1–3

1. Add a centre patch column: x16/84/152 at band scale, keeping 96x60 patches,
   both rows, NCC >=.95 and uniqueness >=.02. Keep at least three agreeing
   patches across both rows and at least two columns. This fills the horizontal
   coverage gap and supplies another eligible patch when an outer patch becomes
   marginal. Do not reduce confidence, uniqueness or shift limits.
2. After spatial agreement, classify offsets beyond 1.5 band px as **changed**
   before considering phase confidence. Low phase confidence must not turn
   demonstrated patch motion into a recoverable quality failure. Insufficient
   or inconsistent patches still remain unprovable and never authorize input.
3. After all geometry bounds pass, align the current band by the measured small
   patch-median shift and require whole-band correlation >=.95 over the valid
   interior. Registration is used only for residual scene-content checking,
   never to hide actual displacement. This avoids rejecting permitted subpixel
   shifts while restoring a check across the patch gaps and rejected patches.
   No raw-correlation floor was lowered to force this case to pass.
4. Fix retention association: retain the last **analyzed** pair and its capture/
   decision stamps separately from any subsequent **unanalyzed terminal**
   capture. Label both explicitly. On capture-deadline refusal, never attach a
   prior audit to the later image. Keep array retention bounded and encode only
   after close; add a test where a failing frame is followed by a passing frame
   that arrives after the deadline. The deadline must still refuse.

No prime/segment/lease/token/deadline changes, no longer neutral wait, no GDI
change, and no optional FPS-buffer optimization in this revision.

## Prototype evidence and limits

`probe.json` pins the native PNGs and standalone `candidate.py`; it is not a
review receipt. The current terminal pair passes with four patches instead of
three and registered correlation .985865. The actual retained two-patch
failure at journal frame 150 passes with three patches and registered
correlation .983676 (`preceding-frames.json`). All 30 earlier ready frames pass;
translations beyond the original bound refuse. Centre-strip noise/flat fills
that passed v1 now refuse, at registered correlations .939497/.925691. Hero-only
animation outside the band still passes; the saved yaw-01b motion pair refuses.

Thresholds remain engineering checks with narrow native support, not calibrated
error bounds or a universal bot/content-change detector. The next integration
must retain the existing synthetic translation/ambiguity/deadline/guard suite,
add the exact terminal pair and preceding refusal frames, centre-content
controls, a low-phase/high-agreement motion test, and the retention-association
regression. Then send only the analyzer/test/retention delta and new pins to
live-review. No new sitting is justified solely by prototype success.
