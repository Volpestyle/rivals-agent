# Native turn-count verdict, 2026-09-29

Owner: evaluator; VUH-1384. Offline review of the completed `alt-cam-20260929/yaw-01` run. **The approximately 2.34-second return is one full turn. Reject the 4.69-second / 77 degrees per second half-turn interpretation.**

The native recording shows the unique portal and stair building, circular tower, open pavilion and rock outcrop passing in that order before the portal returns. There is one portal passage per cycle, not two matching half-worlds. Eight consecutive portal crossings delimit seven full turns: **153.893 degrees/second at RX +0.45, bounds 151.397–156.473**, and a mean period of **2.339286 seconds**. The elapsed-time bracket is 16.104999–16.644999 seconds. These are endpoint sampling/annotation bounds, not a statistical confidence interval. This establishes this magnitude/direction only, not a focal calibration or the whole controller map.

## Retained evidence

All decode output remains on D: in `D:/rivals-agent-evidence/camera-native-turn-20260929/`:

- `native-0001.png` through `native-0160.png`: original 2560x1440 frames at every fifteenth decoded frame (8 samples/second), over native PTS 174.438 through 194.313 seconds. No spatial resizing of these evidence frames.
- `native-index.json` and `decode.log`: frame-to-PTS correspondence; `contact-1.jpg`, `contact-2.jpg` show the full sequence at 0.5-second spacing; `crossing-pairs.jpg` shows the eight portal passages with a screen-center guide. Contact sheets are previews; native PNGs are authoritative.
- `native-turn-counts-v2.json`: eight annotated crossing brackets, consecutive turn indices, source/manifest hashes and native-frame hashes. The portal interior animates; the bounds include an extra sample around its apparent center, plus 10 ms per endpoint for PTS/ledger matching. No interpolated sub-frame precision is claimed. The full interval was inspected using the 0.5-second contact sheets, crossing-pair previews and one full-resolution portal frame; all 160 extracted native frames are retained. V2 corrects V1's overstated wording that all 160 were visually inspected; the count, timestamps and source/frame pins are unchanged.
- `decode.py`, `decode-command.json`, `source.json`: reproducible decode and source hash. BelowNormal CPU process, two ffmpeg threads; observed ffmpeg peak working set 145,137,664 bytes. The driver streams the 1.35 GB source hash in 1 MiB chunks. No game, pad, GPU or paid job was used.

Source: `C:/Users/volpe/Videos/2026-09-29 00-45-47.mkv`, 1,349,517,588 bytes, SHA256 `eafb247e1a1d025c0aad795384a5c188078b13d52f0e8924409b0de534c0306a`. Closed RivalsInput ledger: `20260929T054547-313Z-191512-3`; native PTS includes stream offset 0.021 seconds. Frames map to the ledger's original composition times, not fabricated arrival times.

## Why the previous analyzer refused

The old geometric estimator requires every adjacent registered pair to move at least half a pixel in the expected direction, pass correlation thresholds, and fit a provisional cylindrical/focal model. A single failed pair rejects the entire span before return detection. In OBS, 17 pairs across two spans had essentially zero shift and correlation near 1 (repeated presentation despite small codec changes); the remaining 2,320 pairs passed. Repeated samples are not evidence that the whole 20-second turn failed.

DXCAM separately has 25 capture-gap discards. Its first three eligible spans are only 1.64, 1.92 and 2.01 seconds, shorter than one complete return. Their failed pairs also include correct-sign horizontal motion with correlation around 0.72–0.80 under the provisional rectification. Neither relaxing a live safety check nor silently joining these spans would solve the measurement problem.

The repaired `scripts/analyze_camera_schedule.py` preserves those diagnostic refusals and provides `--native-turn-counts` as an explicit native-count measurement route. It authenticates the recording and run manifest, validates consecutive full-turn indices, expected sign, endpoint bounds within the steady commanded segment, pinned native-frame references, exclusion overlap and period consistency. Frame references are retained without opening them; the full-turn interpretation is the owner's visual annotation, not an automatically verified semantic fact. Counting complete turns between original timestamp brackets needs no focal guess and does not integrate across missing DXCAM pairs.

`analysis-v2/analysis.json` on D: holds the produced rate, analyzer code hashes, corrected annotation and unchanged DXCAM refusal details; `run-analysis-v2.py` reproduces it at BelowNormal priority into a new output directory. Earlier `analysis/` and `analysis-final/` results are preserved. `artifact-index-a2.json` pins the final external files; the first index is retained. Owner validation before the pitch change: 62 tests passed in 31.07 seconds (48 existing calibration tests plus 14 native-count tests), Ruff passed. The final offline addition explicitly leaves pitch unknown until a focal/registration measurement exists; its 15 tests passed in 0.20 seconds. Later pitch tests are recorded in their own packet. No automatic image-only calibration claim is made: without native annotations the strict geometric estimator may still refuse; that uncertainty stays explicit.

## Focal remains a separate prerequisite

`focal-probe.py` / `focal-probe.json` are a small diagnostic using SIFT correspondences and unconstrained homographies between native frames. Estimates vary from invalid through about 490–635 pixels to one 1,151-pixel outlier (at 1280 width). They do not establish a focal value: third-person parallax, near surfaces and sparse correspondences confound this fit. Do not install a guessed focal or use those numbers to convert pitch/low-yaw pixels to degrees. The next sitting plan includes a brief far-landmark, logged-mouse-count angular-scale capture to close this prerequisite.
