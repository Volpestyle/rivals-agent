# Pitch pulse extension: independent review packet

Owner: evaluator, w2:p2N. Reviewer: live-review, w2:p3E. Result issue: VUH-1384; lead w2:p1J owns the sitting grant and Linear publication. Offline implementation only; not landed or authorized for live input until the reviewer supplies LAND and the lead grants exact sitting arguments.

## Delta from camera schedule v2

`--axis yaw` remains the default. Its opener, RX +0.45 prime, five-second settle, yaw values, durations, neutral gaps, outer deadline and all stop paths retain their behavior. Reports gain an explicit `ry` field (zero for yaw); manifests gain `axis`. Runtime change is limited to `agent/camera_calibration.py` and `scripts/calibrate_camera_schedule.py`.

`--axis pitch` selects RY for the measurement segments. It requires explicit `--seconds` from 0.1 through 0.5; the yaw default of 20 seconds is refused. One to four distinct signed deflections with magnitude at most one are declared before attachment. The walk/RT opener and yaw prime are unchanged; the measurement has RX, LY, RT and digital buttons zero. Simultaneous RX/RY is refused, and RY is refused outside `pitch-*` roles. Half-second neutral gaps remain. There is no pitch feedback, clamp detection, automatic re-level, repeat or retry. Opposite signs can be declared as separate pulses; they are not assumed to cancel perfectly.

RY now participates in the existing renewable lease, recorded reports, neutral reset and cleanup. The supervisor recognizes either axis when locating the first measurement segment. Shared timestamp cells, focus/human/range/idle checks, blackout threshold, heartbeat, deadline, process-death handling and owned-target detach have no changes. Generic Live, the old driver and controller code are untouched. F3's transitive intents/state/tracker imports remain the already accepted limitation.

The short pitch cap limits commanded time; it does not prove the camera avoids its pitch clamp or establish degrees. Native recording and offline analysis must exclude clamp/settling/occluded spans. The new native turn-count analyzer is offline, outside runtime pins, and yaw-only; it is not a pitch calibration claim.

## Review and receipt

`review-inputs.json` pins the nine runtime files in `files`, plus owner tests, the complete delta and v2 before snapshots in `support_files`. The prior accepted receipt is `docs/evidence/camera-schedule-20260929-v2/review-v2-receipt.json`. Reuse its evidence for unchanged safety behavior; review RY propagation and every newly reachable boundary.

Write `review-v1.md` and `review-v1-receipt.json` here. The runtime verifier requires JSON `format: camera-schedule-review-v1`, `verdict: LAND`, and an exact copy of this packet's `files` mapping. Include reviewer identity, `review_inputs_sha256`, review document hash and conditions. The owner never writes the approval receipt.

Owner tests cover invalid pitch durations/axis/mixed reports, native-free preparation, pitch lease expiry, each monitor stop, supervisor blackout/range/takeover during pitch, and a real spawned supervisor's hard death during pitch using fake devices. They verify software behavior, not new hardware pitch behavior. Owner output is in `owner-tests.txt` and `owner-ruff.txt`.
