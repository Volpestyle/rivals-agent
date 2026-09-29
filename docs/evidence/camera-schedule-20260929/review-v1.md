# Independent pre-run review v1: fixed camera calibration schedule, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, fresh session, outside the evaluator lane). Read-only; no desktop input, game,
pad, capture or GPU. Reviewed against `review-inputs.json` sha256
`9ddd05407007afd7601ae53f2763d0c39063e2dcc947b19632f37c6ad97ad4e3` at HEAD `30de887`. All 10 runtime `files` and all 10
`support_files` hashes match the working tree.

## Verdict: FIX

There is one blocking finding. The parent-death stop path has a real hole: if the supervisor dies while it holds a
shared `multiprocessing.Value` lock, the actuator blocks and keeps its last report indefinitely. It then has no lease
release, deadline, takeover or detach. The fix is small. Everything else the brief asks about holds. After the fix,
re-review only the delta: `scripts/calibrate_camera_schedule.py`, possibly `agent/camera_calibration.py` and the new
test.

## Findings, by severity

### F1 (blocking, high harm, low probability): a dead supervisor can freeze the deadman with input held

- The four shared timestamps use `ctx.Value("d", …)`, which defaults to `lock=True`
  (`scripts/calibrate_camera_schedule.py:156`). The four are `seen`, `heartbeat`, `worker_tick` and `origin`. `cancel`
  is `ctx.Event()` (`:157`). Its `is_set()` also acquires a shared Condition lock.
- The actuator's `safety()` reads `seen.value`, `heartbeat.value` and `cancel.is_set()` on every call (`:61-63`).
- `CameraPad._monitor` calls `self.safety()` first. The lease release comes only after it
  (`agent/camera_calibration.py:190` and `:195`). `send()` calls `safety()` while holding `self.lock` (`:140`).
- On Windows these are `SemLock` semaphores, which are not abandonment-aware. I measured this in the live venv
  (Python 3.11.9). After the holder process was terminated with the lock held, `acquire(timeout=2)` returned `False`.
- **Reproduction with the real `CameraPad`**, 3 of 3 runs. The supervisor stand-in writes `heartbeat.value` in a loop and
  is terminated inside the write. The actuator is `CameraPad(fake_pad, safety, end)`, and it has just sent the legal
  opener (LY 0.25, RT 1). Three seconds after the kill:
  - `pad.reports` still ends with the `opener` report;
  - there has been no `lease_release`;
  - `closed=False` and `reason=None`;
  - the monitor thread is alive, blocked in `safety()`.

  So the opener, or an RX +0.45 yaw, stays held with no 100 ms lease, no deadline and no takeover check. Control: a kill
  outside the lock gives `lease_release` at +0.1 s, then `supervisor_heartbeat`, then `cleanup` and detach, as designed.
  Script: see the appendix.
- Exposure: the parent has to die hard, by TerminateProcess, OOM or a crash, while the child survives, and the kill
  has to land inside a microsecond critical section. The supervisor enters that section about 5 times per ~10 ms loop.
  Ctrl+C and closing the console reach both processes, so they are not exposures. The probability is low, but the
  failure removes human takeover and release together, and the brief names parent death as a stop path that must hold.
- **Fix:**
  - Use `ctx.RawValue("d", v)` (or `lock=False`) for the four doubles. Each has one writer, and an aligned 8-byte
    load or store is atomic on x64.
  - Replace `cancel` with a lock-free flag, such as a `RawValue("b")` or a `RawValue("d")` cancel time, that the child
    only reads.
  - Add a regression test: a spawned holder process takes the shared lock, if any remains, and is terminated. Assert
    that `CameraPad` closes within the heartbeat bound.
  - Optionally, have the monitor apply the lease and deadline before calling external callbacks.

  The same hazard works in reverse: an actuator killed mid-read can hang the supervisor at `heartbeat.value = now`. That
  case sends no input, because the dead actuator's handle closes, but it loses `execution.json`. The same fix covers it.

### F2 (low, grant scope): the CLI admits more than the approved contract

`schedule()` accepts one to four distinct signed yaw values with |d| ≤ 1, each held 0.5–20 s
(`agent/camera_calibration.py:26-32`, `scripts/calibrate_camera_schedule.py:270-272`). The lead-approved contract is one
+0.45 block of 20 s. That wider range is still right-stick X only and is declared in `ready-attach.json` before
attachment, so it is not unsafe input. But this receipt pins code, not arguments. The live grant should name the exact
invocation: the defaults (`--deflections 0.45 --seconds 20`) and the scope. Alternatively, the tool could refuse
anything else until a wider schedule is approved.

### F3 (low): unpinned code runs in the pad-owning process

`desktop_checks` imports `agent.loop` for `foreground_pid_guard` (`scripts/calibrate_camera_schedule.py:46`). That import
runs module-level code from `agent/brain.py`, `demos.py`, `intents.py`, `jev.py`, `replay.py`, `state.py` and
`tracker.py` in the actuator (`agent/loop.py:35-45`). None of those files is in `FILES`, so editing them would not
invalidate the receipt. I found no import-time side effect today; `agent.loop` pulls in no numpy, cv2, torch or vgamepad.
Consider inlining the 10-line focus check, or pinning the transitive modules. `vgamepad` itself is environment-level and
unpinned, which is expected.

### F4 (low, false failure only): the end-of-schedule race in `execute`

At `agent/camera_calibration.py:215-219`, `clock()` can cross `end` between the `while` test and `now = clock()`, for
example after a sleep that returns a few microseconds early. Then `active` is `None` and
`min(... if start + r.start > now)` is empty, so it raises `ValueError`. That fails safe, because `finally` still
releases and detaches. But a completed schedule would then be recorded as an error and cost a rerun. Break out of the
loop when `now >= end`.

### F5 (low, tests and evidence)

The owner's suite checks `scope_reason` as a pure function. Its only supervisor-level test is the happy path with a
483 ms gap. No test covers these at supervisor level:
- a blackout over 1 s during the run;
- range loss during the run;
- takeover during the run;
- parent death or a stuck lock.

I wrote those first three as scratch tests with the owner's fakes: a thread-based actuator and a fake device. All pass:
- A 3 s gap starting at 6 s stops with `capture_blackout`; the last non-neutral report is before 7.1 s.
- Range loss at 7 s gives `range_or_idle`; the last non-neutral report is within 0.15 s.
- Takeover at 7 s gives `focus_or_human_takeover`, with the actuator `cancelled`, within 0.1 s.

In each case removal was confirmed, and the final report was neutral. Please add them to
`tests/test_camera_calibration_schedule.py`, together with the F1 regression test. Also, `owner-tests.txt` holds only
the pytest output, although the README says it records the "exact invocation".

## What I verified (no finding)

1. **Pad input.**
   - Every report is `reset()` (which zeroes buttons, both triggers and both sticks), then RX with RY 0, then LY and RT
     for the opener only, then `update()` (`agent/camera_calibration.py:124-133`).
   - Nothing calls `press_button`. The `watch_pad` wrapper records calls and sends nothing. So X and every other digital
     button are unreachable.
   - The opener must be the first non-neutral report. It must equal (0, 0.25, 1), last at most 0.2 s, and cannot restart
     or extend.
   - LY and RT are refused outside the opener. RX is finite with |RX| ≤ 1, and `execute` sends only the declared rows.
   - vgamepad's `VX360Gamepad.__init__` sends a default report, which is neutral.
   - RT is checked against `combat_controls("spider_power")` before attachment.
2. **Stops.**
   - Focus, takeover, range or idle, a blackout of 1 s or more, the deadline, cancel and a heartbeat older than 0.25 s
     all reach `close()`, which sends neutral and then does an at-most-once explicit remove, even when neutral fails.
   - The 100 ms lease monitor is independent of the scheduler.
   - Exceptions in `execute` and in the actuator reach `close()` through `finally`.
   - The supervisor's `finally` terminates only its owned child, before writing `execution.json` or `bands.npz`, and
     the actuator writes its result file only after all pad operations.
   - A stuck native call is caught by the `worker_tick` stall check, then handled by cancel, a 0.2 s wait and
     terminate. Removal after process exit is documented but not hardware-verified, as the README says.
   - I measured a spawn child's exit after its result write at 9 ms, so the 0.2 s join does not force-kill healthy runs.
   - Parent death is covered by the heartbeat, except for F1.
3. **Monitor.**
   - `seen` is set only after a positive `in_range` check with no idle warning. Its value is the capture thread's
     timestamp, taken before `grab()`, which is conservative.
   - The two-slot queue drops the newest frame and keeps the real timestamps. No proof time is substituted.
   - dxcam returns `None` for an unchanged desktop, so a stalled game produces no proof.
   - The actuator's `0 <= now - last_range < 1` check fails on missing or future times.
   - `perf_counter` is system-wide QPC across spawn processes. Measured: the child's value fell between the parent's
     before and after readings.
   - Attachment needs range proof less than 0.1 s old, the token, and a re-verified receipt. The actuator re-hashes the
     source before constructing the pad.
4. **Scope.** The 8 existing pinned files are byte-identical to HEAD after CRLF normalization. `agent/controller.py`
   shows as modified only because of line endings. `Live`, the 100 ms bound, the old driver and `agent/loop.py` have no
   change.
5. **Offline side.** `scripts/analyze_camera_schedule.py` imports only cv2, numpy and `perception.camera_*`. It does not
   import vgamepad, dxcam or the controller. It reads the run directory, the manifest's `recording_ref` and the ledger
   and exclusions named on the CLI, and spawns only ffprobe and ffmpeg on that recording. It sends no input, and it can
   reach sealed data only if an operator points it there.
6. **Tests.** `uv run --group perception pytest tests/test_camera_calibration_schedule.py` in a private
   `UV_PROJECT_ENVIRONMENT`: **41 passed in 10.21 s**. The scratch stop-path tests: 3 passed (F5).

## Appendix: F1 reproduction (scratch, fake pad, no device)

```python
import multiprocessing as mp, sys, time
sys.path.insert(0, r"C:\Users\volpe\repos\rivals-agent")
from agent.camera_calibration import CameraPad, scope_reason

class Fake:  # records updates; no native device
    def __init__(self): self.rx = 0.; self.log = []
    def reset(self): self.rx = 0.
    def right_joystick_float(self, x, y): self.rx = x
    def left_joystick_float(self, x, y): pass
    def right_trigger_float(self, v): pass
    def update(self): self.log.append((time.perf_counter(), self.rx))
    def detach(self): self.log.append((time.perf_counter(), "detached"))

def supervisor(heartbeat):
    lock = heartbeat.get_lock()
    while True:
        with lock:
            heartbeat.value = time.perf_counter()
            time.sleep(.005)  # widens the real microsecond window so the kill lands inside it
        time.sleep(.001)

if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    heartbeat = ctx.Value("d", time.perf_counter())
    sup = ctx.Process(target=supervisor, args=(heartbeat,)); sup.start(); time.sleep(1.)
    end = time.perf_counter() + 30
    def safety():
        now = time.perf_counter()
        return scope_reason(now, now - .01, heartbeat.value, end, False, True, False)
    fake = Fake(); pad = CameraPad(fake, safety, end)
    pad.send(0., "opener", time.perf_counter() + .2, ly=.25, rt=1.)
    time.sleep(.05); sup.terminate(); sup.join(); time.sleep(3.)
    print(pad.reports, pad.closed.is_set(), pad.reason, pad.monitor.is_alive())
    # observed: [... 'role': 'opener'] False None True  (no lease_release, no close)
```
