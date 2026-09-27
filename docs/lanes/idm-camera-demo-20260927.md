# Camera-only TRAIN demonstration — 2026-09-27

Owner: idm-owner · VUH-1353 · illustration, **not evaluation**

Delivered MP4: `data/idm/cloud-20260927/camera-demo/camera-train-range.mp4`, 12 seconds, H.264, 960×800, 30 fps, 360 frames, 9,062,537 bytes. SHA-256: `e8fc48cca7550babedbc174841179ff4bde557330843a43d5a4b3299a98d0ac2`. The PC copy matches the Mac render receipt. Lead posts it to Linear; this lane has not posted media.

Suggested caption:

> Camera-only IDM watching James in the practice range. Cyan shows logged mouse movement converted to degrees; amber shows the model's estimate, on the same arrow scale over the preceding 0.10 seconds. This is an admitted TRAIN example that the A4 weights saw, not a validation result. At about 3 seconds the pitch estimate disagrees; at about 9 seconds the uncertainty rule abstains. Buttons are omitted. Pitch truth uses equal-sensitivity calibration, and offline inference uses ±133 ms of context.

Source: `20260923T051828-422Z-33696-1`, original media SHA-256 `ad14e5bc0a1e0da23527a8f4a092e591ddf568ac925cfd0b2907e38dc94b9aaf`. Fixed source interval [120,132) seconds was chosen before inference. All 720 prediction rows are contiguous admitted TRAIN rows. Every displayed source PTS is checked equal to the corresponding prediction row; 360 display frames select alternate 60 Hz predictions. Seven prediction rows abstain on at least one axis. A 0.10-second display window containing an abstention displays unknown, never zero.

A4 checkpoint: `90aa4befa489e9a8385d9d40445be2d17efafb32395375aecedb0f488fb7da0a`, deployed pitch correction `A-6f8dba7b`; target SHA-256 `2e89adf3079a27c2f64fb2d142cfdd6c39bf1b2895398491e03dc82976bc6d8d`. Source video, targets, model and existing frame-store arrays were checked before inference. Prediction file `camera.json`: SHA-256 `ddbfb6ca9cb70cf8e1f9df4722d2d7884a09b76771e5f9393ec3748df1995ac6`. Provenance is in the adjacent `receipt.json`.

Verification: exact PTS equality, encoder exit 0, ffprobe duration/frame-count/format, local output hashes, and visual inspection at 0, 3, 6 and 9 seconds. Both arrow panels have the same 5 px/degree scale and explicitly label clipping beyond 14 degrees. The first five prediction rows have less than the full 0.10-second trailing support at the clip boundary. No smoothing or correction of predictions was applied.

CPU only, two threads, nice 10, $0. The first renderer failed while parsing a long FFmpeg selection expression after inference had completed. Its log and predictions remain under `/Users/james/dev/idm-data/camera-demo-20260927`. The corrected renderer selects a bounded timestamp interval and every fourth native frame, then asserts exact PTS equality; it reuses the hash-pinned predictions. Corrected render: 27.595 seconds, peak Python RSS 902,676,480 bytes. Script `data/idm/cloud-20260927/camera_demo_render2.py` SHA-256 `fc20b5d9af4fa8547c209a750bde2f580c488a8d35364a47be7a33f641769b5c`. Finished Mac directory: `/Users/james/dev/idm-data/camera-demo-20260927-render2`.

The lead's later Mac queue instruction arrived after this render completed. No further Mac compute was started; any additional render waits for explore-policy's explicit slot release.

The requested archive part is omitted under the lead's stated range-only fallback. Admission-codex confirmed that f641ef3 authorizes world-feature SSL only, not camera inference or footage posting. The four admitted sources are February 2026, not calendar 2025. No SPIDEY source was read for the demo. A separate bounded demo-use decision is needed for an archive example.
