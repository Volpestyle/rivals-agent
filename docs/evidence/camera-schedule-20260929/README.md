# Fixed calibration schedule: owner handoff, 2026-09-29

**Produced offline; frozen for fresh independent live-input review. Not landed, run live, or accepted as calibration.** Repair owner: evaluator (`w2:p2N`). Consumer and live-grant owner: herdr-lead. Issue: [VUH-1384](https://linear.app/vuhlp/issue/VUH-1384/agent-pad-follows-jamess-custom-controller-settings-on-the-alt-binds).

This implements the lead-approved split in [the design note](../../research/camera-calibration-open-loop-20260928.md), including the later instruction that replaces its manual idle refresh with one fixed move-and-attack opener. There is no safety objection to that opener within the approved practice-range, focus, takeover and duration bounds. Its effect on idle and fresh-pad drift is **unverified**: a report can be swallowed during device switching. The semantic monitor remains authoritative if the idle warning appears.

## Changed boundary

Only four new files are proposed: `agent/camera_calibration.py`, `scripts/calibrate_camera_schedule.py`, `scripts/analyze_camera_schedule.py`, and `tests/test_camera_calibration_schedule.py`. The parked startup-retry source is retained under `data/calibration/alt-cam-20260928e/parked-startup-retry/`, alongside its existing evidence packet. Its own patch was reversed after verifying those bytes. The existing `Live`, 100 ms feedback limit, old calibration driver and their tests have no semantic diff.

The default schedule, measured from the actuator's actual start, is:

| Interval | Input | Offline use |
|---|---|---|
| 0–0.2 s | LY +0.25 and RT 1; every other channel zero | Excluded; attempted idle refresh |
| 0.2–0.5 s | RX +0.45 only, one prime | Response grading only |
| 0.5–5.5 s | Neutral | Pose grading near its end |
| 5.5–25.5 s | RX +0.45 only | Yaw candidate, excluding startup/transients |
| End or any stop | Neutral, then explicit owned-target removal | Cleanup evidence |

The CLI admits 1–4 distinct signed yaw values with absolute magnitude at most 1, 0.5–20 seconds per segment, a 0.5-second neutral gap between segments, and an outer deadline at most 180 seconds. The opener and prime cannot repeat or extend. No pitch, digital buttons, left X or left trigger are exposed. The whole schedule is declared before attachment; delays never append missed time.

The supervisor captures, checks range/idle, and retains evidence. A separate owned process constructs the pad, executes the fixed schedule, checks focus and **all keyboard/mouse buttons**, and owns a 100 ms renewable input lease plus an independent release thread. Supervisor/actuator heartbeat loss, human takeover, lost focus, failed range/idle semantics, the deadline, or **one second without a positive captured range frame** ends execution. Pre-attach approval uses one inspection token and a fresh range observation. No pose, texture, prime-response or post-attach 100 ms quality decision can refuse the schedule. Actual acquisition times are retained; no proof time is substituted.

Cleanup attempts neutral, then explicit owned-target remove (at most once) and free (exactly once after confirmed removal), including failed initialization. If the child is stuck, the parent cancels, waits 0.2 seconds, then terminates only its owned child and waits up to one second. Native calls holding the pad lock remain a real limitation: process-exit removal is documented by ViGEm, **not hardware-verified here**. The tool records a forced exit or unconfirmed removal as failure, never a successful calibration. Result publication is an atomic file after pad operations end; evidence encoding and drains cannot postpone parent-initiated cleanup.

## Offline measurement

The analyzer reuses existing pose, prime-response and signed-yaw analysis. Frozen/flat imagery, capture gaps and explicitly annotated invalid intervals split usable spans at their original timestamps. Opener/prime are never yaw measurements. A neutral interruption ends the continuous report interval used by the current grader; later portions are not silently joined. Toast, Spider-Sense, aim-assist and scene geometry still require native inspection and explicit exclusions. Rates remain candidates until native full-turn/geometry review. No output automatically changes a controller map.

Optional OBS reading matches decoded PTS and checksums to the closed recording's RivalsInput composition ledger. The native recording remains retained; the decoder uses 1280×720 grayscale working images. OBS and DXCAM share DXGI, so agreement is not independent proof of presentation or device-delivery time. A recording path's existence does not establish that OBS is recording; the live operator supplies that fact.

## Verification and next action

- **153 tests passed in 19.67 s**, including the unchanged Live/old-driver suites, fake-device detach failures, mouse takeover, lease/deadline behavior, and a full fake supervisor/actuator execution across a 483 ms capture gap with unusable image texture. These are offline checks, not physical-pad or native-process fault injection. Exact invocation/output: `owner-tests.txt`.
- Scoped Ruff passed: `owner-ruff.txt`.
- The new OBS reader verified **480 frames across 3.9916665 seconds**, with 78 images in the requested response/pose windows, from the closed `2026-09-28 22-36-21.mkv`. No live capture or device was used. Script, timestamp ledger, decode log and result: `data/calibration/alt-cam-20260928e/open-loop-offline-check/`; pins in `review-inputs.json`. This checks the reader, not a yaw rate.

Herdr-lead launches the fresh reviewer against `review-inputs.json`. Its `files` field is the live runtime boundary; `support_files` records offline code/tests/evidence without making future quality-only edits invalidate the live receipt. The independent reviewer supplies a JSON receipt with `format: camera-schedule-review-v1`, `verdict: LAND`, and an exact copy of the approved runtime `files` mapping. The owner does not author that approval. Review, landing and a separate bounded live grant precede execution.

Prepare-only command (constructs no pad or capture):

```powershell
uv run --no-project --python C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe python scripts/calibrate_camera_schedule.py --output <new-preparation-directory>
```

After the independent receipt, landing and live grant, the desktop invocation additionally needs `--live --review-receipt <receipt.json> --game-pid <pid> --sitting <sitting> --recording-ref <new-running-OBS-path>`. It creates `ready-attach.png` and `ready-attach.json`; the granted operator inspects them and writes the same token to `continue-attach.json`. No launch or token approval has occurred for this candidate.

Once the pad is detached and the native recording is closed:

```powershell
uv run --no-project --python C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe python scripts/analyze_camera_schedule.py --run <run-directory> --output <new-analysis-directory> --obs-frames-csv <matching-RivalsInput/frames.csv>
```

An optional `--exclude-json` takes absolute monotonic `{start, end, reason}` intervals established by inspection. The first deliverable remains a supported signed yaw estimate from a real bounded attempt, not another completed script.
