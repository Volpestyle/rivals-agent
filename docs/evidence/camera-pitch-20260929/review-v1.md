# Independent pre-run review v1: minimal RY (pitch) extension, VUH-1384, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the evaluator lane; also the reviewer of camera schedule
v1 and v2). Read-only; no desktop input, game, pad, capture, GPU, paid compute or sealed data.

Reviewed against `review-inputs.json` sha256 `d3f0a89637526e1d856b74df38655ffff59e9f4da945fbe616ff4fc2aff27773`,
base commit `8331c45` (v2 landed).

- All 9 runtime `files` and all 8 `support_files` hashes match the working tree.
- The seven unchanged runtime files carry the same hashes as the v2 LAND receipt
  ([review-v2-receipt.json](../camera-schedule-20260929-v2/review-v2-receipt.json)), and each equals HEAD after
  line-ending normalization.
- The `before/` snapshots equal HEAD.
- I diffed HEAD against the working tree myself rather than relying on `delta.diff`. The only runtime changes are in
  `agent/camera_calibration.py` and `scripts/calibrate_camera_schedule.py`, and every hunk is the RY and `axis` plumbing
  described below.

The v2 evidence for unchanged safety behavior is reused: focus, all-key and mouse takeover, range and idle, heartbeat,
the 1 s blackout, raw shared cells, the deadline, owned detach, and the order of termination before evidence writes.
The F3 residual stays disclosed: the pinned `agent/controller.py` still imports the unpinned `agent.intents`,
`agent.state` and `agent.tracker` into the pad process. I re-checked the module graph and it has not grown.

## Verdict: LAND

Nothing blocks. RY can reach the pad only as a declared `pitch-*` segment, one axis at a time, with the stated
magnitude and duration bounds. It takes part in every release path. No gameplay, old-driver or generic `Live` code
changed.

## Checks, in order of harm

1. **RY reaches only declared pitch reports.**
   - `_report` is the only writer. It runs `reset()`, then `right_joystick_float(rx, ry)`, then LY and RT for the
     opener only, then `update()` (`agent/camera_calibration.py:131-140`).
   - `send` refuses RY outside a role that starts with `pitch-`, and refuses RX and RY together, before it takes the
     lock or sends anything (`:143-146`).
   - The opener must be exactly (RX 0, RY 0, LY 0.25, RT 1) (`:159`).
   - The first non-neutral report of any axis must be the opener (`:169-172`).
   - `schedule` builds `pitch-i` rows with RX 0 and RY equal to the declared value, and yaw rows with RY 0 (`:43-44`).
   - `execute` passes only `row.ry` (`:232`).
   - Adversarial probe, with a fake pad and the real `CameraPad`. Each of these was refused and sent no report:
     - RY before the opener;
     - RY on the opener, on `yaw-0`, on `prime` or on `neutral`;
     - a role named `pitch` without an index;
     - RX and RY together;
     - RY of 1.01, infinity or `True`;
     - RY together with LY.

     No report in the probe carried RY.
2. **Magnitude and duration bounds.**
   - Pitch deflections: one to four distinct, finite, signed values with 0 < |RY| ≤ 1.
   - Pitch `--seconds` must lie in 0.1–0.5. The yaw default of 20 s is refused for pitch, so pitch needs an explicit
     value.
   - Yaw bounds are unchanged at 0.5–20 s.
   - The 0.5 s neutral gaps, the single 0.2 s opener, the 0.3 s RX 0.45 prime, the 5 s settle and the ≤ 180 s outer
     scope are all unchanged.
   - Late wakeups can only shorten or skip a pulse, never extend it: the lease is at most `min(now + 0.1, end)`, and the
     expired-update path sends neutral.
3. **Neutral clears both axes.**
   - `reset()` zeroes the whole report.
   - Every neutral, `expired_update_skipped`, `lease_release` and `cleanup` report calls `_report(0., …)` with `ry=0`.
   - Owner tests assert the final fake row is (RX 0, RY 0, buttons 0, LY 0, RT 0) after the lease, each monitor stop,
     each supervisor stop and a hard-killed supervisor.
4. **RY takes part in every release.**
   - The lease is armed when `rx or ry or ly or rt` (`:175`). The monitor, the deadline, exceptions in `execute`, and
     the heartbeat on parent death are unchanged and axis-agnostic.
   - Independent reproduction: a spawned supervisor using the production `shared_state` was hard-killed mid-write
     while a `pitch-0` pulse at RY −1.0 was held. **5 of 5 runs** went `lease_release`, `supervisor_heartbeat`, then
     `cleanup`, closing 0.251–0.264 s after the kill, with a final fake RY of 0.
5. **Unchanged guards and scope.**
   - `scope_reason`, `human_input`, `desktop_checks`, `shared_state`, `terminate_owned`, the supervisor's range, idle
     and blackout loop, and `owned_target` or detach have no diff.
   - The supervisor change is one line: `settle_end` recognizes `pitch-` (`scripts/calibrate_camera_schedule.py:191`).
     That value only chooses which retained frames are labelled for evidence; nothing controls input with it.
   - The CLI adds `--axis {yaw,pitch}`, and the manifest records it. `ready-attach.json` already lists the whole
     schedule through `asdict`, now including `ry`, so the operator's one approval covers the declared RY values.
   - `agent/controller.py`, `startup.py`, `live_range_bc.py`, `pad_bindings.py`, `agent/loop.py`, `scripts/record.py`,
     `capture.py` and `l4_measure.py` are unchanged.
   - Nothing in the runtime imports the new untracked `agent/camera_map.py` or the offline analyzer.

## Findings (none blocking)

- **N1 (low, test coverage).** The shared `FakePad.right_joystick_float` used to assert `ry == 0` on every report, which
  implicitly guarded yaw mode. The delta removed that assertion (`tests/test_camera_calibration_schedule.py:28-29`),
  and no yaw test now asserts that RY stays zero. The code guarantees it, since RY is refused outside `pitch-*` roles,
  but please restore the invariant cheaply. For example, have the fake assert `ry == 0` unless the role is pitch, or
  add `all(r["ry"] == 0 for r in reports)` to the yaw supervised tests. This does not affect the runtime receipt.
- **N2 (condition, not a defect).** The code admits up to four RY values up to full deflection, each for 0.1–0.5 s.
  This receipt covers code only. A live grant must name the exact `--axis`, `--deflections`, `--seconds`,
  `--scope-seconds` and sitting. The short cap bounds commanded time. It does not prevent the pitch clamp, and it
  establishes neither degrees nor the sign convention: vgamepad treats positive Y as stick-up, and the game's invert
  setting has not been checked here. Those are offline quality questions, and they authorize no action.

## Tests run

- Owner command, with the cache disabled so nothing was written to the repo: `uv run --no-project --python
  C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe python -m pytest -p no:cacheprovider
  tests/test_camera_calibration_schedule.py tests/test_camera_schedule_analysis.py -q`, giving **78 passed in 49.63 s**.
- Independent scratch probes, with fake pads and no device: the RY boundary probe above, and parent death during RY
  (5 of 5 released).

## Limits (unchanged)

- Everything uses fake devices and synthetic frames.
- Physical ViGEm removal after the process exits, a blocked native call holding the pad lock, the real game's pitch
  response and clamp, and the idle-refresh effect of the opener are not verified on hardware.
- The raw-cell safety argument is specific to x64, as in v2.
