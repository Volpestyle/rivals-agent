# Independent delta re-review v2: fixed camera calibration schedule, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, the v1 reviewer, outside the evaluator lane). Read-only; no desktop input,
game, pad, capture or GPU. Scope: the v2 delta and the unresolved v1 findings. Evidence from v1 for unchanged inputs is
reused ([review-v1.md](../camera-schedule-20260929/review-v1.md)).

Reviewed against `review-inputs.json` sha256 `fd659471689deb0c7a5ddabdd8e50bfac61418f783ea271b6c3e980fe4135c30` at HEAD
`30de887`. All 9 runtime `files` and all 11 `support_files` hashes match the working tree. The seven runtime files that
did not change carry the same hashes as in v1. I did not rely on `delta.diff`. I diffed `before/` against the working
tree myself, after line-ending normalization. The only runtime changes are the F1, F3 and F4 edits listed below.

## Verdict: LAND

F1 is fixed, and I reproduced the fix independently. F4 and F5 are fixed. F3 is mostly fixed: a small unpinned
residual remains, and it does not block. F2 is closed by the lead's decision to pin the arguments in the live grant.
The delta adds no path that can send or hold input.

## Findings

### F1 (was blocking): fixed

- **The fix.** `shared_state()` (`scripts/calibrate_camera_schedule.py:64-71`) now allocates the four doubles as
  `ctx.RawValue("d")` and cancellation as `ctx.RawValue("b")`.
  - The actuator's `safety()` reads only those cells, plus local Win32 calls (`:81-87`).
  - `terminate_owned` sets `cancel.value = 1` (`:156`).
  - Nothing else shared remains in the file: no `Value`, `Event`, `Lock`, `Queue`, `Manager` or `Pipe`. That leaves no
    interprocess lock on either side's path to a stop.
  - Each cell has one writer. An aligned 8-byte load or store is atomic on this Windows x64 target. The README states
    that this is not a portable guarantee, which is accurate.
  - `safety()` now samples the cells before its local `now`. So a heartbeat published concurrently cannot look like a
    future timestamp and trip the `0 <=` check. That is a correct refinement, and it can't relax any bound.
- **Independent reproduction.** I re-ran my v1 test against the production `shared_state`. A spawned supervisor writes
  `seen` and `heartbeat` in a tight loop with no sleep and is hard-terminated mid-write, with the opener armed and then
  with yaw armed.
  - **10 of 10 runs released and closed:** 5 opener and 5 `yaw-0`.
  - Each run went `lease_release`, then `supervisor_heartbeat`, then `cleanup` and detach, within 0.249–0.264 s of the
    kill.
  - Under v1 the same test held input indefinitely, 3 of 3 times.
- **Owner regression test** (`tests/test_camera_calibration_schedule.py:184-255`). It uses real spawned processes and a
  hard kill, the production allocator, and the real `CameraPad`, parametrized for opener and yaw.
  - It proves that the old lock stays abandoned, and that release and exactly one detach still happen.
  - It fails if a synchronized cell is reintroduced.
  - It checks that the surviving side can still read and write the cells.
  - The test's own `safety` lambda mirrors the production one rather than calling it. That is acceptable, because the
    defect lived in the allocator, which the test does use.

### F2 (was low): closed by the lead's decision

Per the lead, the live grant pins `--deflections 0.45 --seconds 20` and the outer scope. The code still accepts the
wider CLI range, and this receipt pins code, not arguments. The live grant is therefore the control, and it must name
the exact invocation.

### F3 (was low): mostly fixed; residual accepted

- `desktop_checks` now contains the focus check directly (`scripts/calibrate_camera_schedule.py:44-61`). It is
  byte-for-byte the same logic as `agent.loop.foreground_pid_guard`: the same Win32 `restype`/`argtypes`, the same
  positive-DWORD check, and still read-only.
- `agent/loop.py` has left the pin set and is no longer imported.
- I imported the actuator's module graph in the live venv: the spawn main module, `agent.pad_bindings` and
  `agent.startup`. The project modules it loads are `agent.camera_calibration`, `agent.controller`,
  `agent.pad_bindings` and `agent.startup`, which are all pinned. It also loads `agent.intents`, `agent.state` and
  `agent.tracker`, which are **not** pinned; they come in through module-level imports in the pinned
  `agent/controller.py:295-297`.
- Those three are dataclass and tracker definitions with no pad access, and v1 loaded them too. It is non-blocking.
  Pin them in a later freeze if one happens anyway.

### F4 (was low): fixed

`execute` now takes a second clock sample and breaks when `now >= end` (`agent/camera_calibration.py:217-219`). The
`finally` block still runs `pad.close()`, which sends neutral and then detaches. The last lease is already bounded by
`end`. There is no late send and no extension. The deterministic crossing test (`tests/...:174-181`) fails on any send
and asserts exactly one close.

### F5 (was low): fixed

- My three supervisor-level stop tests are adopted, with the fake context updated to `RawValue`
  (`tests/...:439-520`).
- The parent-death regression covers the lock hazard.
- The `terminate_owned` test now asserts that cancel is set before the first join.
- `owner-tests.txt` now records the command and the exit code.

## New paths that could hold input: none found

- `desktop_checks` returns the same two callables as before: focus, and takeover over every key and mouse button.
- `shared_state` only allocates memory.
- The reordering in `safety()` changes when values are read, not the thresholds.
- The early `break` in `execute` leads only to `close()`.
- `CameraPad`'s input boundary is untouched: `_report`, `send`, the opener rules, the lease and `close`. So is the
  supervisor's order of terminating before writing evidence. Only the `cancel` call changed.

The v1 verification of the input set, the stop paths, the 1 s monitor and the offline analyzer still applies unchanged.
`agent/controller.py`, `startup.py`, `live_range_bc.py`, `pad_bindings.py`, `scripts/capture.py`, `record.py` and
`l4_measure.py` have the same hashes as in v1. The generic `Live` path and `agent/loop.py` are still byte-identical to
HEAD, apart from line endings in `controller.py`.

## Tests run

- `uv run --group perception pytest tests/test_camera_calibration_schedule.py` in a private `UV_PROJECT_ENVIRONMENT`:
  **48 passed in 31.05 s**.
- The independent F1 reproduction against `shared_state`: 10 of 10 released, as above. It is a scratch script, not in
  the repo, with a fake pad and no device.

## Limits that remain (unchanged from v1 and the README)

- Every test uses fake devices and synthetic frames. Physical ViGEm removal after the process exits, a native call
  that blocks while holding the pad lock, and the idle refresh itself are not verified on hardware.
- The single-writer raw-cell argument is specific to x64. Moving to another platform would need a re-review.
- This receipt covers code only. The live grant must fix the arguments (F2) and the sitting.
