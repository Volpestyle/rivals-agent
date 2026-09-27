# Calibration focal preparation — static only

VUH-1384, camera-analysis, 2026-09-27. **No new focal result or bounds.**
James is playing/recording. This packet is metadata/code preparation only:
no video open, stat/hash pass, image inspection, decoding, tests, numerical fit,
GPU, game input, automatic probe, or queued job. Existing evidence was read-only.
Lead's explicit game-closed release is required before the next phase.

## Authorized recordings and provenance

Only these three calibration entries are authorized; none is a split source.

| Session suffix | Recording | Account evidence | Existing yaw evidence |
|---|---|---|---|
| 162648-153Z-116800-4 | 2026-09-26 11-26-48.mkv | `calibration.json`: campaign (alt); recording log explicitly alt | Three left turns. Mean speeds 1,148 / 2,111 / 4,051 counts/s; gains differ from .0330738 by +.001 / -.006 / +.039%, within the recorded .08% gate. |
| 030045-211Z-7804-3 | 2026-09-24 22-00-45.mkv | No explicit account in the calibration or inspected registry entry; keep unassigned | Four right turns, means 1,806 / 3,841 / 6,207 / 12,088 counts/s. Counts/revolution 10,879.96–10,892.23 in the existing report. |
| 060921-977Z-60612-1 | 2026-09-26 01-09-21.mkv | `calibration.json`: main, settings folder 1859995554; dated James statement | Three right turns. Mean gain +.064%; slow +.159% fails the script's .08% gate but the lead accepted it under the .25% slow-class tolerance. |

Expected video identities below are copied from the calibration records,
**not rehashed or verified against video during this task**:

- Alt left: `764f3fbce3cdb1eee8fbbcfe16f06e132c302b38cd7d5f06e3349fc9aeb72923`.
- Rightward, account unassigned: `ff6b1fa017cb251c599603a7d10f6ddb03ef832c15c71af6270b8c4ff07c0aca`.
- Main right: `becf4c8ca197d0803ad5129c135881c49f9243ddfd3f24ad8c96159b5438264b`.

030045 explicitly cites the dated unchanged-settings statement: sensitivity
1.89/1.89, DPI 800, acceleration factor 1.00 and smoothing enabled. Main's record
states sensitivity 1.89 and DPI 800. Alt-left's calibration JSON states account
but does not contain its own numeric settings declaration; its equal measured
count gain is useful evidence, not proof that every projection setting matches.
Logger metadata for all three has null DPI/sensitivity and uncalibrated capture
latency. Main and alt focal estimates must remain separate. 030045 cannot serve
as the alt's opposite-sign check until account provenance is established.

## A dependency that the new fit must preserve

Both 09-26 `turncal.json` files explicitly report **focal 465**. 030045's
`estimate-meta.json` and `calibration.json:estimator_scale` do too. Their near-360
endpoint excess angles depend on that assumed focal. They corroborate count
gain across speeds/signs, but they are not independent focal ground truth.
The .02% historical closure bound cannot simply be attached to every derived
speed-class gain: recorded uncertainties reach .08%, and main slow uses .25%.

Later analysis should propagate gain/focal coupling or use observed scene
closure with raw counts, and retain the old focal-dependent endpoint correction
as a sensitivity check. Do not merely multiply 465 by the earlier ~3% estimator
discrepancy and call the result a calibrated focal. That discrepancy also
contains motion-model and correspondence error.

## Fixed proposed native windows

Every time below is **logger-relative composition time**, in seconds. It is
not directly an MKV seek position. Match `frames.csv` composition timestamps to
decoded PTS/timebase and verified native ordinals before using pixels; B-frame
callback order is not display order and a callback packet may not be muxed.

| Source | Initial still/pose inspection times | Proposed adjacent track windows | Still control |
|---|---|---|---|
| Alt left, first source | 4.018, 6.400, 10.000, 14.177 | [6.0,6.8), [9.5,10.3), [16.0,16.4), [22.0,22.2) | 13.972, 14.383 |
| Rightward, account unassigned | 2.298, 6.100, 7.700, 9.598 | [5.8,6.4), [7.4,8.0), [11.0,11.4), [14.7,14.9) | 9.598, 9.998 |
| Main right, separate result | 1.940, 3.500, 6.100, 9.263 | [3.2,3.8), [5.8,6.4), [10.8,11.2), [15.0,15.25) | 9.045, 9.482 |

These are fixed proposals from the existing stroke/rest metadata, selected
before any new pixels. They are not already inspected or accepted windows.
After release, start with the alt's four pose frames, inspect native geometry,
then only its first 0.8-second adjacent window. Expand only if correspondence,
stationarity and model checks survive. All frames in a window remain at native
120 Hz before analysis scaling; do not reintroduce a fixed-40-ms phase alias.

The rightward slow turn has a mouse1 press at logger 4.520 s and 8.3 degrees of
endpoint pitch in its old fit. Proposed slow windows avoid the press, but its
animation and camera pose still need inspection. Alt's pitch-sweep control at
27.918/28.319 s failed the old motion gate; retain it separately as a negative
control, not a yaw-calibration sample. Pitch-limit/orbit sweeps cannot establish
the same yaw-only model.

## Prepared and missing

`scripts/fit_focal_calibration.py` currently provides the fixed allowlist,
account-separated proposals, small-metadata loading, and composition-time packet
selection. It intentionally has **no video, decode or fitting entry point**.
`tests/test_fit_focal_calibration.py` contains five synthetic preparation checks;
**none has been run**, nor has the script been executed. No pass claim is made.
The durable environment for the released phase is
`C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe`.

Missing before a focal candidate: explicit lead release; owner test execution;
source-file and raw-log identity verification; source-specific native PTS checks;
small native pose inspection; stationary distant tracks across independent
windows; pitch/roll/parallax and still controls; latency/smoothing/gain sensitivity
with defensible bounds; appropriate same-account opposite-sign evidence. The
prior TRAIN fitter is reusable read-only as a baseline, but its fixed delay grid
and single-window profile are not already a sufficient uncertainty model.

Any later decode must use PCGuard, BelowNormal priority, no GPU, at most two
FFmpeg threads, the global two-decode limit and <=3 GB process memory, plus
job-status evidence. A merely quiet process list does not replace the explicit
lead release. No process has been queued to detect that condition automatically.
