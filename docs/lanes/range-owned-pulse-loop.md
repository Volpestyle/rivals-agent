# Owned pulse caller join — VUH-1346

The lead adopted `request-start-owned-pulse-v1` as a new runtime execution
interpretation. The source label forecasts a received request point in 100 ms;
it does not specify completion of a 33 ms press within that interval. Historical
runs and bindings retain their old interpretation. No labels, model, threshold,
sampling tolerance or prediction horizon changed. This is not a claim of
unchanged 100 ms held-input authority, physical press imitation or better play.

Controller acceptance at A fixes nominal end E=A+press_s. The original request
deadline D remains unchanged in the trace. The caller caps E by the learned
phase end and absolute native session deadline, producing H. The first LT send
must commit strictly before min(D,H,original resource observation+100 ms).
Continuation of the same owned pulse uses H, without another ammo observation
or request lifetime. Delays consume the fixed press budget; a send return never
moves A or E. Healthy current observations remain necessary; fault, refusal,
target loss/change and explicit cancellation retain their immediate releases.

`LiveIO.send_guarded(..., scope_not_after=None)` translates the optional hard
scope from loop seconds into the same absolute perf_counter domain as its two
existing deadlines. `Loop(..., scope_not_after=None)` receives the existing
main caller's absolute session limit relative to the original LiveIO origin.
The range-skill phase limit is first acquisition plus max_s. Every range-skill
combat send, including movement, carries the smaller hard limit into the
actuator lock. Hard scope failure is RangeLost, never recoverable InputExpired.
A normal phase end detected before tick work returns max_time; expiry during
processing/send releases and stops. Startup and scoreboard retain their
separately accepted session/focus proofs; the combat phase lease is not renewed
by them. Scripted probe relative scheduling is unchanged, while its shared
RangeSkill controller now has the new pulse semantics. Old calibration records
are not rewritten or automatically made new deployment receipts.

A send returning after H is recorded as returned, with a detached returned_pad,
followed immediately by Controller cancellation and explicit release. Its
origin row is `executor_returned_then_released`, with no delivered top-level
pad. The original decision, State, resources, accepting step and timing remain
attached; release occurs before diagnostic writes. The same origin is mirrored
in meta, not counted as a second send. Failed release or failed release recording
prevents recovery. Overall scope expiry also stops after a returned send. These
records describe API returns and software authorization, not physical duration.

Root's nine caller regressions first failed against the old caller. The final
23 checks include real Controller/LiveIO/Live with fake devices, late fresh
start and same-owner continuation after D, phase/session caps at nonzero
origins, original ammo age, proof/lock scope precedence, delayed actual write
returns and on-disk RunLog/summary attribution for successful/failed releases.
Existing failed-send fixtures now inject specifically on LT because movement
uses guarded sends too. Tests that expected insufficient full-press time now
expect the deliberately changed fresh-start behavior; actual expired requests
remain refused. The historical C corpus test's expectations were updated for
the new software interpretation but that opt-in corpus case was not run.

Verification on frozen candidate bytes:

```powershell
uv run --offline --no-project --with pytest python -B -m pytest tests/test_range_owned_pulse_loop.py tests/test_range_pulse_lifetime.py tests/test_range_skill_controller.py tests/test_range_skill_loop.py tests/test_range_request_expiry.py tests/test_range_cast_probe.py tests/test_loop.py tests/test_live_pad.py -q -p no:cacheprovider --tb=short --show-capture=no
# 407 passed, 9 skipped (8 Torch joins, 1 opt-in C corpus case)
uv run --offline --no-project --with torch --with pytest python -B -m pytest tests/test_range_skill_loop.py -q -p no:cacheprovider --tb=short --show-capture=no -k 'actual_event_checkpoint_main_consumer_controller_and_recording or actual_new_live_loader_refuses_before_perception_or_pad'
# 8 passed, 101 deselected
```

The eight real synthetic saved-checkpoint joins cover both visual/request heads,
actual loader/consumer/Controller/Loop/RunLog and pre-hardware refusals. No human
checkpoint, native capture/input or corpus was opened. Producer Controller/Live
evidence is in [range-request-pulse-lifetime.md](range-request-pulse-lifetime.md).
Independent changed-boundary review and lead acceptance remain pending for
this joined candidate. A later live experiment needs genuine updated semantic,
controller/perception and scope artifacts; old bindings cannot certify it.
