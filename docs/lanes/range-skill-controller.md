# VUH-1346: independent movement and one requested Web-Cluster pulse

2026-09-22. RSC1/RSC2/RSC3 repair frozen for the same independent range-review and root
integration before live reliance. Synthetic/offline evidence only. Owns
`agent/intents.py`, pure-controller and explicitly authorized guarded Live changes in `agent/controller.py`,
`tests/test_range_skill_controller.py`, and this note. HUD/scorer, policy,
consumer, loop and corpus are unchanged by this lane. Legacy Live.send and the
watchdog polling mechanism retain their behavior; guarded sends cap its lease.

## Caller contract

```python
@dataclass(frozen=True)
class RangeSkillResources:
    webs: int | None
    observed_t: float

@dataclass(frozen=True)
class RangeSkill:
    target: Detection
    web_cluster_request: Literal["start", "no_new_start"]
    decision_id: int
    valid_until: float
    resources: RangeSkillResources

pad = controller.step(reflex_state, intent, intent_t=decision_anchor,
                      execution_t=current_loop_time)
trace = controller.range_skill_trace  # detached dict snapshot, not a method
# On source_end, exception, shutdown, or another external release:
neutral = controller.cancel_range_skill(current_loop_time, reason="source_end")
```

Root must construct the immutable resource snapshot from the decision's original
HUD observation and preserve that observation time. Reflex `State.webs` is
deliberately ignored: the existing loop builds a detection-only reflex State.
`intent_t`, `observed_t`, `valid_until`, reflex `State.t` and `execution_t` share
loop seconds. `execution_t=None` defaults to State.t for existing pure/replay
callers. Explicit execution time must be finite, at least State.t, and may not
go backward across calls. State.t remains the observation clock used by
`_follow`, `_aim`, camera history and arming. It is never overwritten.

An offensive request requires `intent_t <= State.t <= execution_t < valid_until`
and positive decision validity of at most 100 ms, independently of the loop's
one-second gate. Missing/nonfinite/future anchors and non-increasing observation
time still fault neutral. **Expiry alone cancels offensive authorization but
does not discard valid current target measurements, arming or guarded movement.**
This prevents expired asynchronous decisions from repeatedly resetting arming.
The expired request is still consumed and cannot fire later or gain a new deadline.

IDs are nonnegative integers strictly increasing per fresh episode Controller,
including no-new decisions. A repeat must have the same entire intent and
anchor. Every new ID is consumed on first receipt, even when rejected. Lower IDs
and changed payloads under an old ID fault neutral; no target switch, no-new,
refusal, mode exit or subsequent alignment can resurrect a rejected start.

Root's consumer owns valid causal history, learned proposal provenance, mask,
target selection, model revision and deployment binding. This four-field-plus-
resources intent cannot certify those facts. Invalid history/prediction must
produce `Idle` (or independently authorized safety behavior), never a scripted
offensive gate fallback. Root must pin the intended mode and join that decision
trace to this controller trace and actual send result. This lane adds no producer.

## Executor behavior

Range mode has its own pulse state and returns before legacy offensive selection.
Entry discards all old sequences and resets arming. A foreign legacy sequence
inserted while in range mode faults neutral. Exit cancels the owned pulse;
explicit existing modes otherwise retain their existing behavior.

Each healthy step reuses `_follow` and `_aim`, requiring exactly one current,
plausible measurement of the held tracker ID. Missing/untracked/ambiguous target,
coast, detector failure or fault cancels the pulse and returns neutral. A target
switch cancels the old pulse and requires fresh arming. Guarded forward approach
requires the normal reach/near limits plus ARM_FRAMES consecutive measurements.
This is scripted movement and aim, without ground/ledge sensing, traversal,
post-kill relocation, search fallback or any learned movement claim.

Only a fresh `start` may schedule the existing `primitive("web_cluster")`:
alignment, stability, reach, known ammo, shot spacing and full-press time must all
pass. No other primitive can be selected. Busy, unaligned, unstable, unreachable,
unsupported ammo, spacing and late-start rejections are terminal for that ID;
healthy guarded movement still updates. They are never buffered until legal.

The resource snapshot must have a finite original timestamp no later than
`intent_t`. Malformed/future resource clocks fault neutral even for no-new.
For starting, the observation may be at most 100 ms old at execution time and
ammo must be an integer 1–5 (not bool/float). Unknown, empty, stale or unsupported
ammo rejects a start. Healthy no-new with unknown/stale ammo may still move and
finish an already accepted owned pulse; resource uncertainty cannot create one.

A late start is rejected unless `execution_t + cal.press_s <= valid_until`.
The accepted pulse retains its original deadline; a fresh no-new decision cannot
extend it. At default calibration its stages are LT=1 for 33 ms then LT=0 for
30 ms, advanced against execution time on subsequent reflex steps. Shot spacing
also uses execution time. Normal no-new preserves that pulse. Expiry/fault/loss
cancels it on the controller call; fault/loss still clears tracking and arming.
Independent Live/watchdog release remains essential between controller calls;
this pure function is not an autonomous wall-clock release timer.

`cancel_range_skill(execution_t, reason)` returns a neutral request, clears the
owned pulse/track/arming and records original pulse ownership without inventing a
decision or observation. It preserves consumed IDs. The detached trace has
`event="cancel"`, `decision_id/proposal/resources=None`, the last observation time
and explicit cancellation execution time. Repeated cancellation does not invent
a second release edge. Invalid cancellation clocks still cancel, marking the
clock invalid and never claiming a completed press. Root must separately perform
and log actual release attempt/result/time in its _release/_finish integration.

## Guarded actuator deadline

```python
live.send_guarded(pad, not_after=absolute_perf_deadline,
                  release_at=absolute_perf_release)
```

This is a full pad snapshot over NEUTRAL, with the existing button whitelist.
Both deadlines must be finite numbers (not bool), with not_after <= release_at.
The method returns None on success; malformed deadlines/whitelist violations
release and raise Forbidden; expired deadlines or missing/stale proof release
and raise RangeLost. Deadlines are exclusive for nonneutral commits. Neutral
always releases, including when valid finite deadlines have already elapsed.

`_commit` checks deadlines after fresh-frame proof; `_apply` checks them again
inside the device lock immediately before nonneutral write. The remaining
`release_at - perf_counter()` interval caps the existing real-monotonic lease,
sampled before device write, without extending the deadline on renewal. The
watchdog still polls every 20 ms. Legacy send retains its LEASE_S behavior.
This closes delayed proof/lock commits and bounds the held request at existing
watchdog resolution; it is **not a hard physical device-delivery guarantee**.

Root's LiveIO translates loop-relative deadlines by adding t0. For a new LT edge,
root supplies not_after=min(request.valid_until-cal.press_s,pulse.press_until)
and release_at=min(pulse.press_until,pulse.valid_until); ongoing LT uses
not_after=release_at. Root owns the final pre-send guard and joins the physical
send/release outcomes. No Loop edits or policy reads were made for this repair.

## Trace and actual pure example

`range_skill_trace` returns a deep copy for the latest step. Outside range mode it
is None, except the first exit step records cancellation. Fields are:

- `t` (observation-time compatibility alias), `observation_t`, `execution_t`,
  `execution_clock_valid`, `event` (`step` or `cancel`)
- `decision_id`, `target_id`, `proposal`, `valid_until`, `resources`
- `accepted` (true only on the first accepted request), `reason`, `cancel_reason`
- `pulse_decision_id`, `pulse_target_id`, `pulse_press_until`, `pulse_valid_until`,
  `pulse_phase` (`press`, `release`, `none`)
- `lt_down`, `press_edge`, `release_edge`, `ended_pulse_decision_id`, `pulse_outcome`
- `movement_source`, `offense_source`, `pad` (the returned pad request)

An ended pulse reports `completed` only for normal sequence exhaustion,
`truncated` for cancellation before its press end (or invalid clock), and
`cancelled_after_press` for cancellation at/after that end. These describe pure
controller requests, **not delivered input or a visually executed cast**. Root
must keep proposal/acceptance, sent press/release and observed game event separate.
Malformed numeric trace values become null, preserving strict JSON logging.

Actual real-Controller synthetic trace (centered target, five stable measurements,
snapshot ammo 5; no reflex ammo supplied):

| t | decision | reason | forward | LT | owning pulse | phase | edge/outcome |
|---|---|---|---|---|---|---|---|
| .08 | 4 | no_new_start | 1 | 0 | none | none | none |
| .10 | 10 | accepted | 1 | 1 | 10 | press | press |
| .12 | 11 | no_new_start | 1 | 1 | 10 | press | none |
| .14 | 11 | duplicate_no_new_start | 1 | 0 | 10 | release | release |
| .18 | 12 | no_new_start | 1 | 0 | 10 | none | completed |
| .20 | 13 | shot_spacing | 1 | 0 | none | none | none |

## Verification and frozen source

```powershell
uv run --no-sync python -m pytest tests/test_range_skill_controller.py tests/test_controller.py tests/test_live_pad.py -q
```

**137 passed in 2.42 s.** Before repairs, three new pure RSC reproductions failed:
expiry left stable=0 instead of five, execution_t was unsupported, and external
cancellation was absent. Three guarded-actuator reproductions also failed before
that API existed. Root independently reproduced the actual threaded/work-delay/
source-end Loop failures; its real threaded integration regression is root-owned.
This lane did not run or edit it.

The repaired tests prove observation/arming preservation across expiry; missing
target/hard-fault controls; immutable old ID/deadline; execution-time ammo/press
budget and phase progression without retimestamping; malformed/backward execution
clocks; original-pulse cancellation and repeated/no-pulse controls; delayed fake
proof and fake lock refusal plus valid controls; capped lease/renewal and the
actual watchdog loop with a fake clock; invalid deadlines, whitelist and legacy
send compatibility. No real pad factory was used.

Earlier focused tests also exercise movement+nonstart, near-target
non-fallback, one start/repeated ID, healthy no-new completion, malformed/stale
requests, alignment expiry, busy/spacing/ammo consumption, original resource
clock, full-press deadline, release/truncation, real Engage/melee/burst transitions,
all legacy sequence kinds, foreign sequence faults, target switch/coast/loss,
unknown detector, Idle history refusal, unreachable/sliver boxes, nonmonotonic
clock, detached/strict-JSON traces and accepted-start provenance for every LT edge.
The existing pure controller and fake-pad safety suites also pass. Diff whitespace check passes.
No native frames, corpus, shared installs, real pad factories, live input/capture,
commits or Linear transitions were used.

SHA-256 at freeze (raw working-tree bytes):

| Path | SHA-256 |
|---|---|
| agent/intents.py | `a28cc40c42a44b2e352d9a48b8bc8d06d78b1792a568effde16bde8f66b3a653` |
| agent/controller.py | `edf606a77e600709545ef9f1ec7c15cc2796279c7305634e599780f55f59ab8c` |
| tests/test_range_skill_controller.py | `093ff86a775817bb787578d7ff1e933107b99ae4e8292bb0b5365ece530a4a19` |

Remaining boundary: independent code review, root's producer/loop resource/event
clock assertions and integration, then separately authorized evidence. Pure
tests establish executor semantics, not fluid gameplay, cast success, learned
movement or policy quality.
