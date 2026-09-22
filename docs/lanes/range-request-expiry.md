# Request expiry is cancellation, not range loss

Root-owned candidate against `5a4120e`, not yet accepted or deployed. Independent
review is required for `agent/controller.py`, `agent/loop.py`,
`tests/test_range_request_expiry.py` and this note. HUD performance is a separate
frozen lane; no model, training evidence, timing constant or binding changed.

## Observed failure and contract

Both original native runs stopped after a guarded request ran out of full-press
time during proof, despite valid range evidence. The second run retained decision
45, with 0.874 ms left at call entry and a failed return 0.293 ms past its send
deadline. Those historical failures stay unchanged. Red joined controls reproduced
the same episode stop after the first or a continued pulse report: four failures
(two type controls, two joined continuations) and seven valid stop controls.

An expired request remains terminally consumed. It receives no renewed deadline,
retry, substituted action or completed-cast claim. In learned `range-skill` mode,
successful neutral cancellation permits observation to continue and a later
independently guarded decision to act. Scripted calibration retains stop behavior.
Missing/stale range or focus proof, an expired session proof, a closed device,
other transport errors, or failed neutral release still end play.

## Mechanism

`InputExpired` subclasses `RangeLost` to preserve conservative legacy/probe callers.
Only the actual actuator can produce it after a valid proof, exclusive request
deadline failure and a returned neutral write. The old early expiry branch is
removed: `_apply` now adjudicates closed device, stale proof and request expiry
in that order under its existing actuator lock. A closed/stale device therefore
cannot be misclassified as recoverable expiry. The deadline and watchdog lease
are unchanged; the current refusal message names the actuator. Old logs retain
their original "after proof" message.

The learned Loop cancels the original Controller pulse, preserving consumed IDs,
and requires the explicit release call to return before continuing. Both failed
release attempts remain visible; a failure cannot become a successful cancellation.
Pre-send expiry now also checks this returned-release result. The failed-send row
and metadata mirror retain the original State, resources, decision, pulse owner,
stage clocks and proposed pad, with no delivered pad. Release precedes writing.
A failure to persist the originating row propagates and stops; no inferred row or
probability fills a gap. The mirror is the same event, not another failed send.

The current expired reflex has no movement fallback. Subsequent decisions and
observations follow existing target, history, resource, expiry and range guards.
Normal no-new-start cannot replay the cancelled pulse. A continuation that expires
after an earlier returned press is recorded as truncated, not completed delivery.

## Verification

```text
uv run --offline --no-project --with pytest python -B -m pytest tests/test_range_request_expiry.py -q -p no:cacheprovider
```

14 passed. Two actual Live/LiveIO/Loop/Controller/RunLog fake-device runs expire
the initial or a continuation report, preserve one failure and its original owner,
then permit a different fresh request. Proof/lock expiry types, missing proof,
stale proof, closed actuator, failed neutral writes/releases, pre-send expiry,
writer failure and scripted-probe stop controls pass. Named focus/session tests
supply false composed-proof results; they do not execute Win32 or newly validate
the unchanged foreground/session composition.

Before the final three added cases, the integrated stdlib suite passed 369 tests
with nine existing Torch/corpus skips:

```text
uv run --offline --no-project --with pytest python -B -m pytest tests/test_range_request_expiry.py tests/test_range_skill_controller.py tests/test_live_pad.py tests/test_controller.py tests/test_range_skill_loop.py tests/test_loop.py tests/test_range_cast_probe.py -q -p no:cacheprovider
```

The eight actual synthetic visual/request checkpoint main/consumer/Controller/log
joins and live-loader refusal cases also passed in the existing cached CPU runtime:

```text
uv run --offline --no-project --with torch --with pytest python -B -m pytest tests/test_range_skill_loop.py -q -p no:cacheprovider -k "actual_event_checkpoint_main_consumer_controller_and_recording or actual_new_live_loader_refuses_before_perception_or_pad"
```

No actual model, corpus, native capture/input, training data, shared installation or
runtime binding was used. Synthetic checkpoint fixtures do not establish policy
quality. This change cannot promise a faster decision or successful cast; it keeps
an expected expired request from falsely terminating an otherwise valid episode.

## Independent cancellation-record finding and repair

The independent reviewer found that failure of only the release-row writer was
swallowed: release succeeded and its metadata mirror survived, but later requests
could still fire. Root reproduced both initial/continued-pulse cases against the
reviewer's actual executable test (two failures, six valid controls).

The release helper now returns failure when that record cannot be written,
preventing recovery while preserving `release_returned=True` for the actual
transport and the original failure evidence. Both release attempts and persistence
errors remain distinct; no failed write is described as a failed physical release.
Two lasting regressions cover the exact case. Existing range-loss stop reporting
remains, with the actual persistence error in `errors`. No deadline or input change.
Final delta selection: 41 passed / 93 deselected across the 17 owned cases, the
reviewer's eight executable controls and relevant existing failed-send/release
tests. It covers release-only, origin-only and all diagnostic writer failures.
