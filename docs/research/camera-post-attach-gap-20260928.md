# Post-attach camera gap, 2026-09-28

Owner: evaluator. VUH-1384. Offline diagnosis and implementation candidate; no live authorization.

## What yaw-03 establishes

The 100 ms stop was real. The first prime report returned at `721432.7836695`; its proving frame began acquisition at `721432.7611445` and returned at `721432.764261`. The next `Live.fresh()` returned that same timestamp after its wait expired. The guard stopped at `721432.8922981`, at 131.1466 ms acquisition age. Neutral returned at `721432.8947214`: a 111.052 ms report-return interval. These are software timestamps, not hardware delivery times. No motion response or camera calibration was established.

OBS `C:/Users/volpe/Videos/2026-09-28 22-36-21.mkv` closed cleanly at 22:48:56 CDT. Its input metadata reports no dropped events or writer error. The four-second CPU decode surrounding yaw-03 contains 481 frames. Frames are matched to `RivalsInput/20260929T033621-926Z-191512-2/frames.csv` by PTS, including the independently read 21 ms MKV stream offset; each emitted raw frame's Adler checksum matches ffmpeg's timestamped showinfo entry. Local composition-clock mapping varies by less than one microsecond; this is not a capture-latency calibration.

The recorded scene also stops visibly updating. At 1280x720 gray, 58 consecutive transitions change at most 50 pixels by more than three luminance levels. The corresponding image spans **483.3 ms**, from 27.3 ms before the first report to 456.1 ms after it; clear image changes resume at +464.4 ms. Thresholds of 50, 100 and 500 pixels give the same interval; a stricter 10-pixel threshold gives 458.3 ms. The outside-window median is 5,098.5 changed pixels per frame; the stopped interval median is zero. Lossy HEVC reconstruction causes tiny residual differences, so exact hashes alone miss this freeze. The retained sample images show the same portal, hero pose and keyboard prompts during the interval, then animation resumes.

This supports a shared displayed/captured-image stall around attachment and the first report. It does **not** isolate the game renderer, Windows compositor, capture pipeline or device switch as the cause. In particular, OBS composition timestamps are not original game presentation timestamps. The timing is consistent with the proposed device-switch hitch; it is not proof of that mechanism. Sitting d's original failed clause remains unknown and is not retroactively relabeled.

The OBS log identifies the active scene as `Scene 2`, with `Display Capture` using **DXGI**. It and DXCAM therefore share the Desktop Duplication path; the second recording is corroboration of the image stall, not an independent measurement of the game renderer. No capture method or OBS setting was changed for this diagnosis.

Artifacts: `data/calibration/alt-cam-20260928e/post-attach-diagnosis/` contains the bounded decode script, ffmpeg invocation/log, per-frame checksums/timestamps/differences, selected images, `gap-summary.json` and `gap-findings.json`. The exact live refusal remains in `yaw-03/`. No live process or desktop input was used for this diagnosis.

## Repair submitted for exact-byte review

The independent design review rejected an unconditional neutral wait before priming: it would add at least 200 ms of fresh-pad drift even on healthy starts. The candidate instead preserves the immediate +0.45/300 ms prime. **Only a freshness or capture-unavailable refusal in that first prime permits one bounded neutral recovery and one response prime.** Its record explicitly says priming is unknown; a partial report is not evidence of priming.

- Fix the startup deadline at two seconds after the pad factory returns, capped by the original block deadline. It covers the first capture, first prime, any recovery and the response analysis. An independent monitor closes the pad at expiry even if the main capture call is blocked. Native calls and the actuator lock cannot be forcibly interrupted; this is a software deadline, not a proven hardware bound. Successful response analysis must check the deadline before disarming it.
- During recovery, require distinct acquisitions spanning at least 200 ms with no inter-acquisition gap or returned-frame age over 100 ms. Stale or missing evidence resets the streak. Ordinary `grab() -> None` polls between display refreshes do not reset a still-valid streak. The deadline never restarts. No non-neutral reports go out while waiting.
- Run the same +0.45/300 ms prime once more only if that streak passes. Its frames replace the interrupted prime's response samples; the two are never mixed. There is no third execution. Each send retains the 100 ms freshness requirement and lease bound. A second gap, actuator refusal, semantic failure, wrong/missing motion or exception ends the block.
- Once directional response is established, retain the existing five-second neutral settle, fixed-reference pose checks and operator inspection of a new ready-0 frame. A response is not proof of stationarity. No measurement is permitted by the original pre-attach image alone.
- The attach token and manifest explicitly disclose at most two prime executions, at most 0.6 s commanded prime time, and the conditional recovery. This is a changed input budget and needs a new live grant, not reuse of the yaw-02/03 allowance.

The two seconds bound software startup exposure, **not degrees of drift**: M1's old drift rate does not establish a current-account rate. The single response prime also turns the camera. This candidate addresses the observed one-time gap only if the stream resumes inside the bound; it cannot cure a recurring capture stall.

The camera driver's `Live` opts into explicit owned-target removal on close. Other callers retain their existing default. The installed `vgamepad` 0.1.0 has no public close method: its destructor removes and frees the target, but `watch_pad` creates a reference cycle that can defer it. The candidate therefore wraps the owned target's lifetime: remove at most once under the actuator lock, verify it is detached, leave subsequent writes inert, and free exactly once when the wrapper is collected. It never calls the base destructor manually. A removal error is explicit; an attached target is never freed. Process-exit removal is documented by the installed binding but has not been tested here.

Every failed initialization closes regardless of report count. Synchronous response-image encoding waits until response acceptance or confirmed removal; recovery-gap encoding waits until removal. A removal failure skips native failure-image encoding and the normal frame-writer drain, preserving the original stop and recording the cleanup error before exit. The independent watchdog and monitor remain active; neither neutral state nor a dropped Python reference is presented as physical detachment.

Production delta: `agent/controller.py` and `scripts/measure_camera_turns.py`. Offline tests: `tests/test_live_pad.py` and `tests/test_measure_camera_turns.py`. Runtime receipt is pending; the amended design review is `camera-post-attach-gap-review-20260928.md`, SHA256 `c2fc7995d10a877c471cce9cbd81c0c66851ed87ee5407e38f15ac1bd94dd642`.

## Offline checks and live stop condition

The offline checks replay an approximately 483 ms gap, require a fresh streak before the response prime, preserve the immediate fast path, reject a second gap and semantic stops, and exercise persistent missing/cached frames and a blocked capture. Tests also cover response analysis crossing the startup deadline, unchanged motion/settle/pose checks, cleanup preserving the original failure, and no encoding before the response/removal boundary. A fake ViGEm client exercises remove/free counts, the observer cycle, close/lease-watchdog races and inert post-removal writes. None constructs a native pad; native unplug remains unverified live.

Only after review and the lead's explicit live grant: one bounded initialization plus the existing approved measurement block. Stop on a second capture gap, absent prime response, persistent drift, wrong pose, or any existing refusal. No automatic repeats and no calibration claim unless the original motion evidence is produced.

Independent runtime review: pending. The candidate is uncommitted and must not run live until exact-byte review and the lead's separate grant.
