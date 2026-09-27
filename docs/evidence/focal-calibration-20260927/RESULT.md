# Calibration focal: cannot establish

2026-09-27, camera-analysis, VUH-1384. Lead released the PC at 15:24 CDT.
Actual source observation and adjacent tracking completed. No accepted focal,
candidate focal, or defensible focal interval. Lead was notified immediately
and selected yaw + FPS only for the sitting. This is exploratory owner evidence,
not an independent review or calibration acceptance.

Only alt CALIBRATION `20260926T162648-153Z-116800-4` was decoded. Its original
media SHA256 matched `764f3fbce3cdb1eee8fbbcfe16f06e132c302b38cd7d5f06e3349fc9aeb72923`.
The other two authorized takes received static preparation only. No sealed
source, later recording, GPU, desktop or game input was accessed.

## Actual observation and failure

Four fixed native poses were decoded and inspected first; see
[inspection](INSPECTION-alt-left.md) and
[native receipt](alt_left-inspect-20260927T202700/native-evidence.json).
Then the predeclared first window, logger seconds [6.0, 6.8), supplied 96 native
frames at 120 Hz. All selected PTS and the 1/1000 muxer timebase matched the
logger packet mapping. Seven native PNGs total were retained across both runs.

The adjacent forward/backward LK tracker retained 52 complete tracks. The model
fit x = 640 + f tan(theta_track - gain * cumulative_counts), including 20
delay/smoothing combinations, and checked a level-yaw vertical invariant.
All 20 models refused. The best diagnostic was f=625 px at 1280 width, with
horizontal RMS 3.6373 px and vertical RMS 3.8402 px; both exceed the 1.5 px
limits. See [unaltered fit](alt_left-window-20260927T202800/fit.json),
[tracks and raw-count timing](alt_left-window-20260927T202800/tracks.npz), and
[native receipt](alt_left-window-20260927T202800/native-evidence.json).

The best profile 615..630 px is an optimization diagnostic, not a confidence
interval. The inherited helper's `conditional_bounds_px` applies historical
0.02% gain widening and is **not** this source's uncertainty. Both candidate
fields are null. No use of 625, 640, 465 or the profile as a replacement focal
is supported by this result.

Inspection of the retained first/middle/last window images shows foreground
columns and barriers, distant tower geometry, animated bots, foliage, labels,
and the third-person hero. Correspondences have not been individually certified
as stationary far landmarks. Grounded hero posture does not prove a stationary
camera center: orbit/parallax and non-level view remain possible. Residuals do
not identify which nuisance caused failure. No post-hoc point selection was
used to rescue the number; no additional windows were decoded.

## Remaining uncertainty

Capture latency is uncalibrated. The finite delay/smoothing grid does not bound
the game's transfer function or acceleration. Source near-360 count corrections
used focal465, so their gain agreement is partly focal-dependent; the nominal
0.0330738 deg/count and alt source 0.08% tolerance cannot independently certify
focal. Pitch/roll and translation were refusal checks, not fitted corrections.
Still and pitch controls and independent windows/signs were proposed but not
decoded after this refusal. Main/alt transfer is unverified; only this source's
alt identity is explicit. The rightward source account remains unknown.

## Owner checks and process closure

Seven synthetic owner tests passed in 0.11 s under PCGuard/BelowNormal using
`uv run --no-project --python C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe`.
Tests cover fixed-source authority, account separation, metadata-only access,
composition-clock selection, native PTS mapping, and no-overwrite evidence.
They do not establish source geometry. Existing fitter validity controls remain
in `tests/test_fit_focal_train.py`; they were not rerun for unchanged code.

Both decode runs exited successfully, sequentially using one lane FFmpeg
process with at most two threads. Peak parent RSS was 77,799,424 bytes for
inspection and 424,734,720 bytes for the window. Native decoder exit codes are
in the receipts; both [completion](alt_left-window-20260927T202800/completion.json)
records confirm decoder closure. Python fit and owner test processes exited.
Job status is done. All owned decoder/fit/test processes are stopped; no further
decode or math is queued. An unrelated FFmpeg PID 74904 remained untouched.

After the recorded run, the script gained a 90-second timer that also kills its
own blocked decoder and an explicit flag that inherited conditional bounds are
not source uncertainty. No decode was rerun for those changes. Source JSONs
retain the original static proposal flags; selection/completion receipts record
what actually ran. Frozen run bytes and previous evidence are preserved.
