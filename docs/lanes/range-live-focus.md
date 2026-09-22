# VUH-1346: learned live caller focus and runtime bound

2026-09-22. Frozen for independent range-review; not yet accepted for native use.
Root owns runtime-profile hashes, binding approval and the next native attempt.
Checkpoint quality validation remains separate and pending. This lane performed
no native capture/input, model-quality work, media reads, installs or commits.

## Reproduced caller defect

Before changing production code, a synthetic fake-device harness executed actual
`agent.loop.main`, startup, LiveIO, Live, the threaded Decider, Controller and
RunLog. Only checkpoint loading was replaced by a declared synthetic EventBrain;
pixel readers, capture/device and the image writer used injected fake dependencies.
With foreground false throughout, the original caller still attached one device,
sent five camera reports, ran 60 learned-mode ticks/10 decisions and exited 0.
The actual default Live proof saw range pixels but had no foreground constraint.

## Caller/API change

`--live --brain range-skill` now requires `--game-pid` in `1..4294967295`.
The existing range-policy `--max-s` default of 20 and validation `(0, 20]` remain
unchanged for live and dry callers. The one diagnostic uses explicit `--max-s 10`;
it does not reduce the caller's general trial duration. Existing checkpoint, identity,
runtime/deployment binding and cadence validation completes before the focus
factory, perception or hardware. Missing/invalid PID and an initially unfocused
configured process cannot reach perception, capture or attachment.

`agent.loop.foreground_pid_guard(pid)` is the sole implementation of the read-only
Win32 PID check. `scripts.range_cast_probe` imports/re-exports that same function;
its accepted schedule/startup behavior is unchanged. It never changes focus or
navigates. Dry mode and legacy live callers retain their existing paths; the
existing legacy `--brain range --live` rejection also remains.

After perception, plaza and scoreboard readers preload, the caller checks focus
again before opening capture. It starts an absolute `perf_counter` deadline just
before Live opens: `START_DEADLINE_S + max_s`. Explicit `--max-s 10` gives 24 seconds;
explicit or default 20 gives 34 seconds. One Live instance
receives three independently composed proofs: range, recognized scoreboard, and
the opening session banner. Each checks focus/deadline before and after its pixel
reader. False uses Live's existing refusal/release behavior. Supplying the custom
range guard does not silently replace board/session readers with always-false
defaults. `_scoreboard_readers()` loads the same readers and predicates as default
Live: `is_scoreboard(frame) is True` and `banner_score(frame) >= BANNER_MIN`.

The accepted startup helper receives the composed range proof, including during
frame-only delays. Actual Live initialization also checks that proof before its
pad factory: focus lost during its acquisition/proof cannot attach a device.
After attachment, startup refusal still closes Live and preserves startup steps.
During the learned phase and scoreboard, failed scope proof uses the existing
release/stop paths. It is logged as the existing range-proof refusal, rather than
inventing a pixel diagnosis of the focus/deadline failure.

No Controller, Live method, policy, reader algorithm or observation/resource clock
was changed. The combined deadline is a proof boundary, not a hard physical-write
or process-exit guarantee: focus can change after proof; lock/device delays remain
under existing freshness, guarded LT deadlines and watchdog resolution. Startup
and cleanup may finish later if capture or another callback blocks. No old input
is reauthorized and no timestamp is rebased to restart the combined budget.

`meta.json.start.live_scope` records configured PID, read-only focus method,
original LiveIO perf origin, absolute deadline, deadline in the original loop
clock, startup/phase limits and their combined budget. Existing State/resource
timestamps and executor send/release events remain intact.

After independent approval and root's separate runtime binding review, the caller
shape is:

```powershell
& $reviewedPython -m agent.loop --live --brain range-skill `
  --game-pid $verifiedGamePid --max-s 10 --cooldowns normal `
  --range-checkpoint $checkpoint --range-sha256 $checkpointSha256 `
  --range-identity $sourceIdentity --range-runtime $observedRuntime `
  --range-deployment $reviewedBinding --no-scoreboard --run $newRunName
```

The variables above are root-supplied reviewed artifacts, not defaults or approval
receipts created by this lane. The scoreboard remains functional if explicitly
used within the same focus/deadline proof; this example omits it for the bounded
exploratory run.

## Verification

```powershell
uv run --no-sync python -m pytest tests/test_range_skill_loop.py tests/test_range_cast_probe.py tests/test_loop.py tests/test_startup.py -q -rs
```

The earlier broader boundary run passed 215 tests with 10 skips. After lead's
timing-scope correction, only the affected timing and caller-boundary selection
was rerun on the final bytes:

```powershell
uv run --no-sync python -m pytest tests/test_range_skill_loop.py -k 'live_cli or scope_proof or foreground_guard' -q
```

28 passed, 34 deselected in 8.03 seconds. These cases cover valid actual joined main/LiveIO/Live
with no-new movement and guarded starts; explicit 10=>24 and explicit/default
20=>34-second metadata, with rejection above 20; bad/missing
PID; already-unfocused; preload, initialization, post-attach and post-start loss;
absolute expiry after startup; successful real scoreboard opening/banner/board
proofs and focus refusal while holding BACK; loader rejection before focus/hardware;
legacy pose-only behavior; exact expiry after a slow reader; and the shared Win32
PID-result comparison using fake API functions. Prior probe focus/dry, loop and
startup controls remain included. Model-dependent skipped checks do not establish
quality or binding acceptance; the caller harness explicitly stubs only that
loader boundary. No corpus test was enabled.

Changed paths: `agent/loop.py`, `scripts/range_cast_probe.py`,
`tests/test_range_skill_loop.py`, and this note. `tests/test_range_cast_probe.py`
is unchanged and reused as an injected fake-device fixture and regression suite.

Frozen SHA-256 (note's own hash is handed back separately):

| File | SHA-256 |
|---|---|
| agent/loop.py | `d9486813a723b1d0813576a35d7d4e6bce3928a817b623a533a226be878239de` |
| scripts/range_cast_probe.py | `6792eb459b1a887c9d615e97cc53540c36e9750ffae44f3c39cbfeb6bb7c9a7b` |
| tests/test_range_skill_loop.py | `4bedd3189580ea3c541b575a85c4d96735dbfb1bde066e136a5062084d994cc6` |
