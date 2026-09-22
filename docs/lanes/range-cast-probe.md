# VUH-1346: scripted Web-Cluster calibration probe

2026-09-22. Independent same-reviewer acceptance and lead adoption are complete
for the scripted caller, including RCP1. Other boundaries retain their accepted
evidence. **No native run was performed by this lane.** Owned:
`scripts/range_cast_probe.py`, `tests/test_range_cast_probe.py`, this note.

This is explicitly SCRIPTED CALIBRATION, not a learned policy or deployment.
No checkpoint, fit artifact, deployment receipt or source/runtime binding is
loaded or manufactured. The earlier human fit remains separate.

## Composition and bounded schedule

The standalone entry composes the accepted `Loop`, `Controller`, `LiveIO`, `Live`
and actual `RunLog`. Root added `brain_name="range-cast-probe"` with declared
10 Hz cadence, guarded range-skill execution and no policy object. Root changed
the executor's provenance to `accepted_range_skill_request`; the actual producer
is `scripted_calibration_web_pulse`. The probe preserves those raw logs.
The existing learned CLI/loaders remain separate. No production file was edited
or stubbed by this lane.

Bounded constants, with no CLI overrides:

- Setup: at most two seconds; three consecutive decision observations of one
  tracked target in the configured normalized ROI, with known positive ammo.
- Bind that causal tracker ID once. Later target loss/coast/replacement latches
  refusal; never acquire a replacement or retry an opportunity.
  ProbeIO observes the actual Loop controller's detached public trace before
  each send, so a reflex refusal between 10 Hz decisions also latches. It pins
  the trace to the bound target ID and current acquisition observation timestamp.
- Exactly three scheduled opportunities: setup +1.0, +2.5 and +4.0 seconds.
  Each has a 100 ms window. A late opportunity or unknown/empty ammo consumes
  the slot without a start; controller alignment, stability, resources, press
  budget and actuator deadlines independently retain their accepted authority.
- At most five seconds after setup and eight seconds total. Budget checks run
  before/after acquisition and before sends; existing lease protection applies
  when a callback blocks. Every scheduled slot remains in the report, including
  setup failures, refusals and slots never reached after a stop.
- No legacy offensive sequence, warmup, keepalive, scoreboard, menu navigation
  or repositioning routine. Healthy `no_new_start` retains independently scripted
  approach/aim and may complete its owned pulse. This is not learned movement or
  aim calibration; root must verify the visible same-platform setup beforehand.

The decision uses genuine `RangeSkill` and frozen `RangeSkillResources(webs,
observed_t=State.t)`. A start's deadline is the scheduled slot deadline, not a
fresh timestamp invented after slow work. Observation time remains acquisition
START; execution time comes from the same LiveIO origin. Controller and guarded
actuator checks are unchanged. Decisions run synchronously for this small script;
slow HUD work can refuse a slot rather than move it later.

## Live entry and operator prerequisites

Only `--live` reaches native factories. `--dry` and import require no native
capture/device libraries. Live entry requires the root's actual game process PID,
a nonempty lead-observed normal-cooldown note, and a visible same-platform setup
note. It checks the configured PID against the foreground window before opening
capture/pad. Read-only foreground checks also guard acquisition/sends and compose
into Live's range proof after the pixel check. It never changes desktop focus.

`meta.json` records cooldowns normal **only from the explicit lead observation**;
the probe does not read the Practice Settings value. Unknown/missing notes are
not replaced with fabricated metadata. Patch remains `unverified`. The first
pulse may be ineffective after device attachment: retain that failure, with no
priming attack, retry or extra scheduled slot.

After independent approval, root supplies these variables from its existing
prepared runtime and contemporaneous observations. The command is run from the
repository in the owned desktop session; this lane did not execute it:

```powershell
& $probePython -m scripts.range_cast_probe --live `
  --out "C:\rivals-agent\data\l1\range-cast-probe-20260922-a" `
  --game-pid $probeGamePid `
  --target-roi 0.45 0.35 0.55 0.65 `
  --normal-cooldowns-note $probeCooldownNote `
  --setup-note $probeSetupNote
```

`$probePython` is the root's already provisioned native runtime interpreter;
no environment sync/install is part of the probe. `$probeGamePid` must be the
verified game PID, not a guessed process. The shown ROI is a normalized central
rectangle; root must configure it for the designated visible bot. Multiple
candidates in that rectangle fail setup. Output directories must be new.

The standalone synthetic exercise, with actual Loop/Controller/RunLog:

```powershell
uv run --no-sync python -m scripts.range_cast_probe --dry --out "$env:TEMP\range-cast-probe-dry-20260922-a"
```

## Evidence and synchronization handoff

Native entry reuses Live's dxcam acquisition and RunLog's native JPEG writer at
20 fps. It does not start/stop a separate video recorder or consume an active
recording. Root owns its existing native video recording infrastructure and
the visual cast/ammo audit.

Caller artifacts for that audit:

- `frames.jsonl`: acquisition-relative observation times, original decision
  State/ammo, target IDs, scripted decision traces, owned pulse deadlines and
  controller acceptance/cancellation, actual send attempt/return/failure records,
  and terminal `executor_release` rows with both release attempts if needed.
- Native `NNNNNN.jpg` samples referenced by those rows, plus actual `meta.json`
  from RunLog: runtime source/mode, stops, errors, latency and release events.
- `probe-config.json`: configured target ROI, fixed schedule, operator notes and
  `loop_perf_origin` and configured foreground process PID. Native entry also records a wall-clock nanosecond sample
  bracketed by two perf_counter samples, without changing observation timestamps.
- `probe-report.json`: all three scheduled slots; actual start proposals,
  controller acceptances, LT send attempts/returns/failures and not-sent requests
  counted separately; per-slot controller reasons and sends; terminal releases.
  `reflex_latch` records the first qualifying executor reason, observation time,
  execution time, latch time, bound target ID and original decision ID. Subsequent
  decision traces carry that same latch; original controller traces stay intact.
  A failed send can be preceded by acceptance: its original owned-pulse trace
  establishes that software acceptance even when the normal tick row was skipped.
  Repeated terminal references to that same send are deduplicated.

Root must retain the paired video path/hash, recorder command/launch timing,
video PTS/timebase and any independently established offset mapping for this
specific recording. The wall/perf bracket is only a clock anchor, not proof of
the recorder's render, buffering or mux latency. Matching multiple saved native
frames to video can support a separately audited alignment; do not borrow another
recording's offset. `video_clock_mapping` and `visual_casts` deliberately remain
null. JPEG sampling alone may miss a 33 ms pulse/cast.

One accepted request may cause multiple LT send calls while its single pulse is
held. Those calls are not multiple casts. Conversely, software acceptance,
returned send, pressed duration, scoreboard increments or outcome count do not
prove a game-visible Web-Cluster cast. Root audits native animation/projectile/
ammo evidence and bounds the response time only when synchronization supports it.
This probe does not certify a full deployment, target correctness or policy fit.

## Verification and review boundary

```powershell
uv run --no-sync python -m pytest tests/test_range_cast_probe.py -q
```

**26 passed in 1.33 s.** The main harness constructs actual Live with an injected
fake device/capture, actual LiveIO, actual Loop/Controller and actual RunLog.
Tests show three proposals/acceptances on the healthy synthetic schedule,
non-start movement, distinct late-proposal and late-controller refusal, unknown
ammo, target-switch refusal, range/focus/capture stop, complete scheduled
denominators, successful and failed terminal release during an owned pulse, and
acceptance followed by a failed guarded send. The failure test exposed duplicate
terminal references losing send ownership; the report now retains the original
pulse owner. A fresh subprocess proves --dry imports no cv2/dxcam/vgamepad.

RCP1 was reproduced before editing with `harness.__wrapped__(pytest.MonkeyPatch)`
and the real joined Live/LiveIO/Loop/Controller/RunLog. Only synthetic detections
were hidden using `dataclasses.replace(frame, detections=())`:

| Synthetic observation condition | Before: proposals / accepts | Repaired: proposals / accepts |
|---|---|---|
| Healthy | 3 / 3 | 3 / 3 |
| Hidden only `1.24 < t < 1.29` | 3 / 3 (defect) | 1 / 1 |
| Hidden `1.24 < t < 1.45` | 1 / 1 | 1 / 1 |

The brief interval produced real `target_coasting` traces at 1.25, 1.2667 and
1.2833 seconds. The repair retains the first at 1.25 seconds for bound target 1,
decision 13; both later slots are refused as `target_identity_lost`. All three
denominator entries remain. The same tracked ID returns, but never starts again.
A separate brief loss at 1.44–1.49 seconds verifies the latch during no-new-start.
The tests check original resource timestamps, persisted first-refusal attribution,
later neutral sends and successful terminal release.

The probe's explicit classification includes target/detector loss, coast,
ambiguity, unmeasured/invalid target and Controller's structural hard refusals.
It does not latch ordinary decision/pulse expiry, unknown/empty/stale ammo,
alignment, stability, distance, busy/spacing or insufficient press time. The
structural `decision_expired_or_invalid` reason means an invalid decision interval;
ordinary elapsed authorization is separately named `decision_expired` and retains
its existing behavior. Actual pure Controller traces verify ambiguity, unknown
detector, invalid frame/future resource faults, and non-latching ammo, alignment,
expiry and late-press controls. Old-observation, foreign-ID and external-cancel
traces cannot establish this bound target's current-step latch. The observer
records schedule refusal only; it never retimestamps resources, changes a
controller trace, issues a decision or modifies general Controller reacquisition.

No native hardware, game capture/input, corpus reads, learned-policy loads,
installs, commits or Linear transitions. Same range-review independently passed
26 tests and the original healthy/brief-loss/sustained-loss joined controls:
3/3, 1/1 and 1/1 proposals/acceptances. It accepted the complete scripted caller
while reusing the other unchanged proof. Lead adopts that software acceptance.
Root alone integrates, runs the probe, pairs video and accepts the visual audit.
Synthetic checks do not establish a game-visible cast or learned-live authority.

Frozen raw SHA-256:

| File | SHA-256 |
|---|---|
| scripts/range_cast_probe.py | `1c3ce3d6a1ba003075dc2042d81de14cdf9aee2fed976a7f0cb9db2bb141ead4` |
| tests/test_range_cast_probe.py | `dcb764cbc971b02c4378318ed1c0af5e3a8419ecfa6fd63e7f3aabd2728cfd32` |
