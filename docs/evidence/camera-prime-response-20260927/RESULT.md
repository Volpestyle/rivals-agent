# Prime response: saved-native false refusal reproduced and fixed

Camera-analysis, VUH-1384, 2026-09-27. Exploratory owner evidence; no independent
review, input operation, rate, angle, focal or calibration acceptance.

## Root cause

The exact saved pair from `data/calibration/alt-cam-20260927/yaw-01b/` has capture
timestamps 609857.514211 and 609857.603321: 89.110 ms apart, within the existing
40..100 ms response-pair gate. PNG hashes match the original frame receipts:

| Saved frame | SHA256 |
|---|---|
| initialization-motion-before.png | 007c703813f7fb5d924da3d70aacadf29cc39a8a99d49c353e47134719c0b3ac |
| initialization-motion-after.png | d90fe16f9e0077c1dd0d4c73dada21ebb3bf1dd3af5adb651338371722fd6bb9 |

Both native frames were visually inspected. Architecture clearly moves left;
the hero and device-switch overlay remain largely screen-fixed. The pair is not
pixel-identical. Capture age beyond the saved receipt cannot be independently
established from two PNGs; the caller must retain capture freshness checks.

The old 240x160 template, x520..760/y100..260 at 1280 scale, matches at dx=-170,
dy=0 with NCC **0.68931049**. Direction, minimum motion and maximum displacement
512 px do not fail. Confidence fails its 0.8 gate, before phase is evaluated.
The switching banner touches the ROI top, but excluding it by moving the top
to y105/y120/y130 yields NCC **0.6867/0.6735/0.6567**, still below 0.8.
Banner contamination is not a sufficient explanation or fix.

The supported diagnosis is that the large rigid translation template does not
retain enough photometric correspondence during this yaw/perspective change.
Smaller patches find coherent displacement with the original confidence floor.
This does not isolate perspective from every possible blur/parallax contribution.
There is no evidence requiring a longer prime or another input.

## Small estimator change and actual replay

`perception.camera_prime_response.analyze(before, after, direction=-1,
before_t=None, after_t=None)` takes pixels only (times are keyword-only).
It accepts native 2560x1440 BGR or 1280x720 BGR/grey uint8. Direction means
expected **image** displacement. Optional timestamps must jointly pass 40..100 ms;
when omitted, the caller keeps that existing timing guard.

A fixed grid of 48 nonoverlapping 32x32 upper-scene patches replaces one large
template. Its source and destination support excludes y<120, including the
observed switch banner, and y>=330, avoiding this pose's hero. Every usable
patch retains NCC >=0.8, plus a >=0.04 unique-peak margin, reverse match within
2 px, phase response >=0.2 and residual <=1.5 px per axis. Searches allow either
direction; they are never biased by the requested sign. At least six patches,
three columns, two rows, >=80% coherent displacement and >=80% expected-sign
motion are required. The 2 px minimum, 512 px maximum and dominant-axis checks
remain. Refusal never supplies accepted `dx`, `dy` or `confidence` fields.
`confidence` is minimum coherent-patch NCC, not a calibrated probability.

[Final replay](final-replay/result.json), source/module hashes included:

| Control | Result |
|---|---|
| Exact saved pair, direction -1 | Pass: 14/14 coherent patches; dx=-175.5, dy=0 at 1280 scale; minimum NCC 0.817921 |
| Same frame twice | Refuse identical/stale pixels |
| Exact pair, direction +1 | Refuse wrong direction |
| Reversed pair, original direction -1 | Refuse wrong direction |
| Reversed pair, direction +1 | Pass: 13/14 coherent patches; dx=171.5, dy=0; minimum NCC 0.809136 |
| Distinct frames with duplicate timestamp | Refuse invalid pair interval |

The [accepted-patch overlay](final-replay/accepted-patches.png) was inspected:
patches span three rows of stairs, rock, columns, rail and other scenery. The
matching set does not rely on the hero, banner or training bots. Pixel medians
differ slightly when the pair reverses because each source grid sees different
scene points. These medians must not be converted into angle or rate.

Attempt 01 is preserved: a sparser 48x48-patch version found only two valid
correspondences and refused. Attempt 02 introduced the final fixed 32x32 grid;
the final replay adds the large-template banner controls and overlay without
changing estimator bytes. No score/sign/motion thresholds were lowered.

## Verification and limits

24 owner tests passed in 2.10 s, using the durable private environment through
`uv run --no-project`, PCGuard, BelowNormal and CPU only. Tests importorskip
numpy/cv2 before importing the estimator. Valid geometric controls use
H=K R K^-1 perspective yaw in both signs; flat translations test pixel direction
only and are not presented as angular geometry. No-motion, brightness change,
unrelated texture, periodic texture, flat texture, local-only change, vertical
motion, wrong sign, subthreshold displacement, banner-only change, malformed
pixels and invalid timestamps/direction refuse.

A small valid synthetic yaw of 0.08 radians is an explicit false-refusal control:
its ROI flow fails the conservative translation-consensus gate. Sparse scenery,
large pitch, extreme perspective, blur, parallax or wider overlays can also
refuse. No universal moving-object exclusion is proven. Two images alone cannot
prove motion was caused by the pad or identify the camera's physical rotation.
The result is only coherent image-response evidence. Caller-owned fresh HUD,
prime/report intervals, release, neutral settle, banner clearance and operator
ready checks remain mandatory and unchanged.

No video was opened, hashed or decoded. No source logger, sealed source, GPU,
desktop, capture or actuator was accessed. Only the explicitly named native
pair and its small saved receipts were used as visual evidence. All owned
replay and test processes exited; no automatic work remains queued. Driver,
l4, input and existing evidence files were not edited. Integration belongs to
live-loop.
