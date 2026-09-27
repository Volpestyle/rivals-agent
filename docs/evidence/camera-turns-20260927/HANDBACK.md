# Camera turn driver: pre-run review request

Owner live-loop; reviewer binds-review; VUH-1384. No desktop, capture device,
pad, GPU or game was used to produce this packet. The two new code files are
uncommitted pending pre-run review. This packet adds a driver around the motion
guard and full-report observer already accepted in 5c3f74e.

`scripts/measure_camera_turns.py` defaults to prepare-only. Live mode requires
Windows, an explicit foreground game PID, a sitting and native recording
reference, and a `camera-turns-review-v1` receipt covering exactly `FILES`.
Verification compares receipt, import-time and current disk hashes before attach.
`source-hashes.json` lists the review inputs; it is not an approval receipt.

At most four distinct signed yaw deflections run in a <=180-second block; each
segment is <=20 seconds. Only rx is nonzero. Every renewal has fresh range/idle
proof and a <=100 ms lease bounded by the segment end. A separate monitor
closes the pad on focus loss, keyboard input or block expiry even if capture
blocks. Any capture/report/disk/proof exception releases and closes. No automatic
activity refresh, navigation, retry or calibration installation occurs.

Before each segment the driver saves a native ready image while neutral, then
waits for the lead to inspect it and acknowledge that segment's fresh token.
The lead writes `continue-N.json` containing `{"token":"<ready-N token>"}`
from another machine/process without moving game focus. This is an inspection
gate, not an instruction for James to switch to a terminal. Acknowledgements
expire with the block and never bypass the next fresh proof. Neutral attach
can rotate the camera on this client; inspect the post-attach pose, and do not
assume neutral reports or the first command prove device acknowledgement.

The driver stores timestamped scenery bands, native guard traces (bounded
background queue with retention counts), full outgoing reports including
neutrals, and the external native recording reference. `watch_pad` timestamps
are report-return times, not device acknowledgement. The existing no-motion,
direction and orthogonal-motion checks are mandatory. A motion refusal stops
before another segment. Image correlation proposes returns only: four returns
give three post-transient intervals; <=5% spread produces a candidate rate.
The native video must establish one full turn per interval, absence of bots,
level camera, motion and timestamp precision. Correlation can alias scenery;
the code never marks a map accepted. Slow deflections that cannot finish enough
turns in 20 seconds remain unknown. No-motion is not a measured zero.

Far-landmark focal analysis is offline via `--sweeps-json <json> --output <new>`.
It requires six annotated sweeps, three per direction, each with
`far_landmark`, `level_camera`, `rate_receipt_sha256`, `native_evidence`,
`signed_rate_deg_s`, `rate_uncertainty_deg_s`, `edge_enter_t`, `edge_exit_t`,
and `timing_uncertainty_s` (uncertainty of the edge-to-edge duration).
The combined timing/rate error must be <=0.5 degrees and repeated FOV estimates
within one degree. These are candidate values requiring landmark review, not
a default 640-pixel calibration. Finite video sampling may fail this precision
gate; never supply an invented uncertainty. A slower independently calibrated
human-mouse sweep, as described by the focal review, is then the lead-owned
alternative. A near-landmark control diagnoses parallax; it is not fed into the
far-landmark fit. Pitch remains the existing reviewed short-pulse procedure
only after focal acceptance, away from clamps; no 360-degree pitch inference.

Offline validation: 16 tests pass in the private live-loop CUDA environment,
without selecting CUDA. Tests cover a synthetic rotating-texture valid control,
static refusal, stopping before a second segment, release on capture error,
lease bounds, blocked-capture independent closure for key/focus/deadline,
prepare-only pad exclusion, invalid requests and focal uncertainty. Ruff passes.
Synthetic correctness does not establish native turn detection accuracy.

Example preparation (no input):

```powershell
uv run --no-project --python C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe python scripts/measure_camera_turns.py --deflections .45 -.45 --seconds 20 --scope-seconds 180 --output data/calibration/<sitting>/yaw-a-prepared
```

The lead alone schedules live use after receipt and deployment verification,
adding `--live --review-receipt <receipt> --game-pid <pid> --sitting <id>
--recording-ref <native-video>`, with a different new output directory. James
moves/attacks and restores the pose between blocks; camera turning does not
reset inactivity. No alt policy episode precedes accepted camera maps and
the controller/loop/record/bindings re-freeze.
