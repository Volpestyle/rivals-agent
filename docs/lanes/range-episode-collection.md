# VUH-1319 opt-in episode collection

Frozen software delta for F's changed-boundary review. Root owns integration,
native Galacta scouting, runtime bindings and evidence admission. This lane
changed only `agent/loop.py` and added `tests/test_episode_collection.py` plus
this note. The accepted Galacta schedule and handoff bytes remain unchanged.

## API and behavior

`agent.loop.main` adds `--collect-episode`, allowed only with `--live` and
`--brain scripted|range-skill`, normal cooldowns, a duration in `(0,20]`, and the
existing end scoreboard enabled. Periodic scoreboards are excluded in this mode.
The collection default is 20 seconds. Existing non-collection defaults stay as
before. `--stop-on-feed` is an additional optional collection-only flag.

The injected pure interface is:

```python
Loop(source, pad, percept, decide, log=RunLog(...),
     brain_name="scripted", max_s=20, collect_episode=True,
     candidate_feed=None, scope_not_after=absolute_deadline_in_loop_seconds)
```

`candidate_feed` is an optional frame -> True/False/None callable. Main preloads
the existing `perception.scoreboard.is_killfeed` when requested. A direct injected
collector needs a RunLog-compatible required image saver; the scripted pad must
support existing `send_guarded`. `RunLog.save(..., required=True)` fails when the
writer reports false or no file exists. Existing calls without `required` retain
their old behavior. Tests inject writers/devices; no native factory is invoked.

The sequence on one Live/LiveIO instance is:

1. Existing camera-only `start_pose` and its existing proof/evidence handling.
2. Loop checks the acquired range frame and takes `scoreboard-baseline` via the
   existing guarded scoreboard sequence, before any decision/history offer or
   controller phase input. Native PNG, parsed counters, actual capture interval
   and clock are retained. A missing board, unknown/invalid KO count, missing
   acquisition interval, guard refusal or failed required save prevents offense.
3. Request a new source acquisition **after** the baseline has returned and been
   saved. Its original timestamp must follow the board's grab return and be at
   or after the new acquisition request. Reject stale/future frames, lost range,
   idle warning or expired scope. Save `episode-first-phase.png` and the exact
   acquisition timestamp. Saving consumes time; it cannot renew the frame or
   restart the fallback execution clock. Excessive save delay aborts the phase.
4. Set the phase origin to that acquisition, then offer it to the existing fresh
   decider/controller. No baseline/startup frames enter policy history or phase
   slots. State/resource clocks and LiveIO's absolute origin are unchanged. The
   phase ends at origin + max_s or the earlier original session deadline.
5. Release through the existing boundary. A normal end attempts the existing
   guarded terminal scoreboard; refusal/missing evidence remains visible.

Collection disables warmup/keepalive for both policies. It changes neither
scripted combat choices nor learned request semantics, confidence, tolerance,
controller/pulse behavior or action vocabulary. Existing default legacy routes
remain unchanged. In collection, a range/focus gap is terminal for both policies;
there is no recovery into the same episode after that refusal.

Both collection policies require a positive configured `--game-pid`. The existing
read-only foreground check runs before readers/capture/pad and again after
preload. The same range, board and opening-session proofs compose foreground
and the **original absolute pre-attach deadline**, `t_open + 14 + max_s`.
Scripted collection sends use existing guarded LiveIO/Live delivery capped by
phase/session end, including the actuator's deadline recheck. Startup, baseline
collection and saving all consume that same budget. The baseline can therefore
leave less than 20 seconds for the phase if setup approaches its maximum; no
deadline is extended to repair that. Explicit 10 -> 24 seconds and default
20 -> 34 seconds are covered. Watchdog resolution still bounds physical release;
this is not a hard physical delivery-time guarantee.

A collection refused before phase start returns CLI exit 1 with retained Loop
metadata; unexpected exceptions still propagate after cleanup. Once a phase has
started, callers must inspect `stop` and the evidence; exit 0 does not assert a
valid episode, success or safe-delivery audit.

## Optional candidate-feed stop

With `--stop-on-feed`, the saved first-phase frame must return **False** from the
existing reader. True or unknown refuses before any decision. Afterward a True
on a processed reflex acquisition releases immediately, before image encoding
or log writing, records `episode-candidate-feed.png` with the actual acquisition
time, stops with `candidate_feed`, then attempts the existing guarded terminal
scoreboard. No further decision or offensive send uses that candidate frame.
Image/log errors cannot precede the release attempt; errors remain errors.

This is presence detection only. It does not recognize the designated Galacta
incarnation, killer, event identity, occurrence time or full target health.
Unknown intermediate readings do not become absence. No new reader or threshold
was added. Candidate time is an acquisition time, **not** a kill occurrence
timestamp, and candidate_feed is not automatically an episode-complete terminal.

## Exact evidence interface

`meta.json` gains `episode_collection` only for this opt-in path:

```text
status: baseline_pending | refused | phase_started
clock: loop_seconds
readiness_accepted: null
designated_completion: null
baseline: copied successful-return board record, if available
reacquire_requested_t: actual request time in existing loop clock, if reached
first_phase: {t, file, size, feed_present} | null
candidate_feed: {t, file, feed_present:true, designated_completion:null} | null
reason: refusal stop reason, when no phase started
```

All board attempts also remain in `scoreboards`. Successful captures preserve
legacy pre-hold `t`, plus `captured_t`, `capture_interval:[grab_start,grab_return]`
and `capture_clock:"grab_start_to_return_loop_seconds"`. Parsing/acquisition
metadata is appended before a required save, so a save failure leaves `file:null`
and the original error rather than an invented image. A failed acquisition has
the existing `skipped` reason. The terminal board can still be refused by the
original scope deadline. It is not made mandatory by extending authority.

Both collection policies retain actual release attempts/results/times in
`executor_events` and `frames.jsonl`; scripted events have no range-skill owner
trace. Existing learned decision/step/resource/send-failure joins are preserved.
Native image acquisition clocks remain the source's grab-start clock, and board
intervals remain grab bounds. Neither establishes rendering age or video PTS
alignment. Native video audit must account for those uncertainties.

The saved first-phase frame is **audit-ready evidence, not accepted readiness**.
Root still binds the scheduled run/reset epoch and designated incarnation, audits
near/mid bbox geometry, full health, resources, observed patch/settings, scope
and target-associated outcome. The collector performs no reset and cannot assert
that the epoch stayed unchanged. Existing scorer observations must be filled from
actual reviewed evidence, not created from `phase_started` or a feed bit.
In particular, the current scorer treats an unadjudicated `candidate_feed` stop
as an interruption. Preserve that runtime stop; root's later reviewed outcome
sidecar must establish the actual event/normal episode terminal where supported.
There is no new scorer adapter or automatic admission in this delta.

## Root caller templates after review/integration

Within root's existing provisioned runtime, add the collection flags to the
already reviewed model/binding invocation; the scoped Galacta profiles remain
root's responsibility. These commands were **not executed here**:

```powershell
uv run --offline --no-sync python -m agent.loop --live --brain range-skill --collect-episode --stop-on-feed --game-pid <actual-pid> --cooldowns normal --max-s 20 --range-checkpoint <checkpoint-path> --range-sha256 <pinned-sha256> --range-identity <source.json> --range-runtime <fresh-runtime.json> --range-deployment <fresh-binding.json> --run <scheduled-learned-run-name>
uv run --offline --no-sync python -m agent.loop --live --brain scripted --collect-episode --stop-on-feed --game-pid <actual-pid> --cooldowns normal --max-s 20 --run <scheduled-scripted-run-name>
```

Omit `--stop-on-feed` to collect through the bounded phase end. A missing baseline
always aborts either variant. Neither command claims a validated Galacta start
or replaces the predeclared schedule's retained failures.

## Verification and frozen pins

Before implementation, the three initial real-Loop tests failed because the
collection API was absent. The completed **59 focused checks pass**, covering
both policies, real Controller and RunLog, and the actual main/start_pose/LiveIO/
Live path with fake capture/device and a loader-only policy stub. Controls cover
baseline-before-offense, immutable observation/resource/phase clocks, empty and
unreadable boards, missing interval, stale/missing first frame, writer failure
and delay, no-feed precondition, candidate release-before-save, original exception
propagation, focus at preload/initialization/start/phase, actuator delay, expired
session, terminal-board refusal, normal completion and unchanged 14+max_s budget.

The broader pure regression selection passed **276 tests, one skipped, nine
deselected** before the final collection-only clock/status/late-send controls;
the final 59-check run includes those controls. Six existing joined CLI/default/
legacy-pose controls were rerun after the final source edit and passed. Model
training/loading cases and the saved-clock input test were explicitly deselected;
the corpus test stayed skipped. No model, human data or native media was opened.

```powershell
uv run --offline --no-project --with pytest python -m pytest tests/test_episode_collection.py -q
uv run --offline --no-project --with pytest python -m pytest tests/test_episode_collection.py tests/test_loop.py tests/test_range_skill_loop.py tests/test_range_cast_probe.py -k 'not actual_event_checkpoint_main and not actual_new_live_loader and not recorded_first_phase' -q
uv run --offline --no-project --with pytest python -m pytest tests/test_range_skill_loop.py -k 'live_cli_valid_actual_joined_stack or live_cli_legacy_pose_only or live_cli_explicit_diagnostic_and_existing_default' -q
```

Frozen SHA-256:

- `agent/loop.py`: `2365b4fb75cb0c012fa6713f061eb14623e0f3b35bf5497f322eb908e8dbda0e`
- `tests/test_episode_collection.py`: `ea7a7b88b3ab4756c335bd319a782e5c85a0f77785b24ba107fd0b0556b445e7`
- Unchanged schedule: `a69edd5ad6af7e00dc7c32a5e81045743a91c49d6043aff6752f655b710d0d1d`
- Unchanged Galacta handoff: `f51b8743c8504d7ebf5538aed8cf99e4d96bbd4231ea946c952f71eae5cafdde`

No native input/capture, shared installation, commit, Linear mutation or live
deployment occurred. These tests establish software behavior only. F reviews
this frozen delta; root integrates and owns the actual Galacta audit and binding.
