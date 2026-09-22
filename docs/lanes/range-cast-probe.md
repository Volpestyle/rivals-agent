# VUH-1346: scripted Web-Cluster calibration probe

2026-09-22. Proposal-clock eligibility correction independently reviewed;
**lead adopts this scheduler delta for native measurement.** Startup remains
accepted/pushed `3a1165f`, with root reporting that it worked in B/C. RCP1 and
the startup/controller/actuator boundaries are unchanged. This lane sent no
native input and performed no native capture. Owned:
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

- Native entry first runs the existing `agent.startup.start_pose`: a separate,
  up-to-14-second **GUARDED CAMERA-ONLY STARTUP**, then the unchanged probe budget
  of at most eight seconds. Combined authorization is capped at 22 seconds from
  just before Live opens. Existing startup pulse/search/settle thresholds stay
  unchanged; no walking, attacks or new search logic is added.
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
- Probe phase: at most five seconds after setup and eight seconds total. Budget checks run
  before/after acquisition and before sends; existing lease protection applies
  when a callback blocks. Every scheduled slot remains in the report, including
  setup failures, refusals and slots never reached after a stop.
- No legacy offensive sequence, warmup, keepalive, scoreboard, menu navigation
  or repositioning routine. Healthy `no_new_start` retains independently scripted
  approach/aim and may complete its owned pulse. This is not learned movement or
  aim calibration; root must verify the visible same-platform setup beforehand.

The decision uses genuine `RangeSkill` and frozen `RangeSkillResources(webs,
observed_t=State.t)`. Proposal time must be inside the fixed slot. An original
fresh causal observation may precede the slot, with the request deadline equal
to `min(slot.deadline, State.t + PERIOD_S)`. `request_valid_until` records that
actual start authority in the slot report and decision trace; it is null for
non-proposals. The fixed `deadline` remains the slot end. Observation time remains acquisition
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

Both `default_perception()` and `_plaza_view()` preload before Live attaches.
The caller constructs exactly one Live and one LiveIO; `start_pose` receives that
same Live, the combined range/focus/deadline proof, existing idle/plaza readers,
and `attached_t` taken after LiveIO returns. The probe keeps that device and the
original LiveIO clock origin throughout. Camera pulses use the accepted helper's
Live.send path; LT pulses later use the unchanged guarded executor path.

The helper's right-stick prime and bounded camera search mitigate attachment
drift. Its five-second frame-only delay does not prove that the device switch
completed or the view became still. Its two plaza observations do not identify
Luna or certify the configured ROI. The unchanged probe must still earn its
three-observation target/ammo setup. Root must audit the resulting startup view
and native cast response; no new readiness or identity reader is implied.

Range and actual focus are checked during startup acquisitions/delays, before
camera sends, and by Live's proof. The same proof rejects after the combined
deadline. These are bounded authorizations and existing lease protection, not
a hard process-exit or physical-delivery guarantee during blocked capture,
proof, logging or cleanup. Startup step writing counts against the probe's
existing IO budget; slow evidence writes can shorten or consume it.

On startup refusal, the accepted helper closes Live. The caller writes the
original startup steps/kept frames via `_write_start_steps` and actual RunLog,
plus a refusal report containing all three unattempted slots. No Loop is
constructed and no schedule/policy is called. `StartRefused` produces CLI exit 1;
unexpected exceptions retain the same artifacts and are re-raised. A refused
startup does not invent an executor release event: no executor pulse existed.

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
  --out "C:\rivals-agent\data\l1\range-cast-probe-20260922-b" `
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
- `start-steps.jsonl` and `start-step-NN.png`: the existing helper's step records
  and kept native decision frames on acceptance or refusal. Step `t` remains
  seconds since helper entry; `stamp` remains acquisition START seconds after
  `attached_by_t`. `startup` metadata in config/report/meta records those clock
  definitions, accepted confirmation acquisition times in the original LiveIO
  clock, phase start/finish, helper limits, turns/timings or the refusal error.
  `steps_file: null` explicitly exposes a best-effort writer failure. Original
  State/resource times are never rebased after startup.
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

**54 passed, 1 skipped in 1.75 s**, plus the explicitly selected frozen-C JSON
test **1 passed in 0.10 s**. All previous 35 tests remain. The main harness constructs actual Live with an injected
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

For the prior caller, same range-review independently passed
26 tests and the original healthy/brief-loss/sustained-loss joined controls:
3/3, 1/1 and 1/1 proposals/acceptances. It accepted the complete scripted caller
while reusing the other unchanged proof. Lead adopts that software acceptance.
Root alone integrates, runs the probe, pairs video and accepts the visual audit.
Synthetic checks do not establish a game-visible cast or learned-live authority.

The nine new startup cases execute real `start_pose`, Live/LiveIO, Loop and RunLog
with a fake device/capture, declared synthetic readers and an injected fake image
writer. The helper and executor are not stubbed. The healthy control proves
reader/plaza preload before attach, one-device ownership, only camera/neutral
reports before startup acceptance, 3/3 subsequent proposals/acceptances, fresh
resource observations on the continuous clock, stored step artifacts and neutral
release. Refusal controls cover no plaza, focus loss during the prime, range loss,
idle, slow capture, unexpected plaza exceptions and focus absent before attach.
They prove zero policy calls and three retained unattempted slots. A slow startup
evidence-writer control consumes the remaining probe budget without any LT send.

### Native prerequisite inspected for this delta

Only attempt A's `probe-config.json`, `probe-report.json`, `frames.jsonl` and two
referenced JPGs were read under `data/l1/range-cast-probe-20260922-a/`. Both images
show KBM prompts and five visible webs. At 0.0888 seconds, `000000.jpg` shows Luna
on the right; at 2.0316 seconds, `000026.jpg` no longer shows her and the view has
shifted toward the doorway. This pair supports a view change, not a measured
angular drift rate. The available frames log has 21 serialized decision States
(IDs 1-21), all with `webs: null`. The report records zero proposals and `setup_timeout`,
retaining all three slots. No reader was changed and no revised native attempt
was run by this lane.

| Attempt A file | Inspected SHA-256 |
|---|---|
| probe-config.json | `95f0960e32ef4a78e610896fa1fcd7affce550e9c6c58459e748051b5781060b` |
| probe-report.json | `ca15a4c4a16bb7fd1275ad6108f48cd01cc683bb970db33021fcab6118a76154` |
| frames.jsonl | `29ac99d35ae6f8714675222b236df0dca28f9d04c59da0be084e585a30e9bd33` |
| 000000.jpg | `18ae2a0dfe4116125652ed49dff903c94d8e771c8a2cba6271169022136f44cb` |
| 000026.jpg | `ecce980140bad1083433ad0505fe05802a523ab29f94b2b8775a7466ea5a4ceb` |

No native hardware/input/capture, broader corpus reads, learned-policy loads,
installs, commits or Linear transitions were performed by the producer/reviewer.
Independent review accepted this startup delta. Root alone
integrates, runs the probe, pairs video and accepts the visual audit. Synthetic
checks do not establish a HUD switch, stopped drift or a game-visible cast.

### C proposal-clock correction

Before editing, actual `CastSchedule` reproduced C's first two `late_opportunity`
refusals from its saved States and slot `evaluated_t`, despite evaluation inside
the slot and observation ages 53.898 ms / 64.150 ms. The scheduler now checks the
actual proposal time against the fixed slot and the original observation expiry.
It never stamps either the State, intent anchor or ammo snapshot with that later
time. Stale observations refuse as `stale_observation`; future/invalid clocks
remain refused. Slots are terminal once proposed/refused, with no retry or requeue.

| Saved C slot | New request valid_until | Remaining at saved proposal | Offline controller, synthetically armed |
|---|---|---|---|
| 1 | 8.485428100009448 | 46.102 ms | accepted; fake LiveIO guarded send returned |
| 2 | 9.953198800003156 | 35.850 ms | accepted; fake LiveIO guarded send returned |
| 3 | 11.513327899994328 | 26.967 ms | insufficient_press_time; no LT |

Those are isolated counterfactual software checks of actual saved States, not
historical gameplay results. **All three original C slots remain failed; original
C has zero acceptances and zero LT sends.** Neither B nor C was modified. Only
C's config/report/frames JSON was read for this delta; no native images or video.

The ordinary synthetic suite adds early-before-slot, exact/after-slot expiry,
fresh-before-slot, stale/exact observation expiry, future/invalid clocks, unknown/
empty resources, both deadline minima and one-time slot consumption. A joined
real Loop/Controller/LiveIO/Live run uses 94 ms acquisitions with processing phase
crossing slot starts: 64 ms HUD work yields 3 proposals/3 accepts; 74 ms yields
3 proposals/0 accepts, all full-press refusals. Observation/resource clocks remain
original, and terminal release is checked. The separate recorded-JSON test uses
actual C States and fake LiveIO, with each Controller synthetically armed to
isolate the request boundary; it reads only these hash-pinned files:

| C file | Immutable SHA-256 |
|---|---|
| probe-config.json | `4b8db2ed2657c02272779d7de14e67383dd6c578ee9f31c68e8543cb704d6a31` |
| probe-report.json | `3249a82ef06725493f2e4021708f1a67f6313fdc9bbc6438549dafb438eb67f8` |
| frames.jsonl | `09003eb6df9a0342cdb2dca89836bda3a58b856d271d221280262d90dd4eee67` |

```powershell
uv run --no-sync python -m pytest tests/test_range_cast_probe.py::test_frozen_c_states_keep_original_clocks_through_controller_and_fake_liveio --corpus -q
```

That test is skipped by default; `--corpus` above selects only the authorized C
case. It verifies file hashes before and after. The same reviewer accepted this
scheduler delta; root owns landing and the next native attempt.

Frozen raw SHA-256:

| File | SHA-256 |
|---|---|
| scripts/range_cast_probe.py | `28873faf416881d9f8d41a601670829512add555dfe0e5f4c88dce43fa7d2767` |
| tests/test_range_cast_probe.py | `fdac894952e23b0fcb81341ec1de1bf452030322689a847cc12bdbdfefdf955a` |
