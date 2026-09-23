# Two reset-window checks: no qualifying anchor

**Close this bounded support search.** Neither n154 nor n211 establishes a
clearly target-agreed causal anchor, so no additional cast-association decode
span is proposed.

| Bin | Actual final CTS / file PTS | Actual reset selection | Native anchor assessment |
|---|---|---|---|
|n154|15.399999384 /15.421|None|Named Luna is visible; final selection is absent. Earlier targets cannot be carried forward.|
|n211|21.099999156 /21.121|Local track2, bbox[1019,301,1107,336], taggedFalse, plateFalse|Box covers health-bar/nameplate pixels, not an identifiable bot body. Recipient agreement unknown.|

n211 differs from saved continuous replay (None), but reset selection alone is
not proof of a valid target. The distant visible Galacta body elsewhere in the
same image is not substituted into the selected box. Neither result establishes
a new positive or negative label.

## Every earlier selector output retained

### n154

| History tick | Actual CTS | Selected target |
|---|---|---|
|15.0|14.999999400|None|
|15.1|15.099999396|local track1, bbox[1444.0, 754.0, 1679.0, 855.0]|
|15.2|15.199999392|local track1, bbox[1519.0, 637.0, 1760.0, 811.0]|
|15.3|15.299999388|local track1, bbox[1477.0, 599.0, 1719.0, 755.0]|
|15.4|15.399999384|None|

### n211

| History tick | Actual CTS | Selected target |
|---|---|---|
|20.7|20.699999172|None|
|20.8|20.799999168|local track1, bbox[800.0, 255.0, 1137.0, 451.0]|
|20.9|20.899999164|None|
|21.0|20.999999160|local track2, bbox[913.0, 353.0, 1033.0, 405.0]|
|21.1|21.099999156|local track2, bbox[1019.0, 301.0, 1107.0, 336.0]|

`measurements.json` preserves all ten native frame references and hashes,
actual CTS/availability, full States/detections/coasting, gate outputs and every
selected box. Fresh Tracker/Memory was created separately per five-frame
window. The unchanged source-owned mapped MK HUD layout was used with current
accepted code. Current HUD includes the landed mask/countdown optimizations;
actual module bytes are pinned in the measurement, not misrepresented as the
older source-profile hash. Code pins were checked before and after processing.

The check ran CPU OpenCV with four threads in the existing offline cached
environment, using only default perception, tracker and brain.gate. No learned
model or policy was called, no controller/Loop instantiated, and no input was
sent. Exactly ten saved images were processed; both final native anchor images
were visually inspected at original resolution. No new video was decoded.
No old feature row, label, source profile, receipt or audit file was changed.
The reset/continuous distinction and window-local IDs remain explicit.

`check.py` reproduces only these two windows from repository root. The scoped
hash manifest pins the helper, measurements and inspected findings. This is a
target diagnostic, not an admission receipt. Root owns any next scope decision.
