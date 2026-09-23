# VUH-1319 Galacta pilot input — 2026-09-22

Prepared against main `cdf3a7ab1011dc27a785fae2e02f31f93b002bb4`. Root owns
desktop collection and integration. This delivery supplies an **unexecuted**
schedule for the accepted offline scorer; it is not a launch authorization or
evidence that a Galacta setup works. No runtime/scorer/policy/HUD source changed.

The usable input is `data/benchmarks/galacta-pilot-20260922/schedule.json`.
Keep that predeclaration immutable; fill a separate `filled.json` in the same
directory with the same twenty entries/order. The scorer consumes its existing
`range-benchmark-v1` fields. Additional `predeclaration`, pair/order and
`collection` fields are operator notes, ignored by the scorer.

## Fixed schedule and starts

Each row below is an adjacent pair, a separate fresh loop/history per trial.
Both policies encounter near/mid in the same order. All twenty allocations stay
in the scheduled denominator, including unrun slots after an experiment stop;
no replacement retries. Five pairs per bin; ten trials per policy.

| Pair | Bin | Global trial order |
| --- | --- | --- |
| 01 | near | 01 learned, 02 scripted |
| 02 | mid | 03 scripted, 04 learned |
| 03 | near | 05 scripted, 06 learned |
| 04 | mid | 07 learned, 08 scripted |
| 05 | near | 09 learned, 10 scripted |
| 06 | mid | 11 scripted, 12 learned |
| 07 | near | 13 scripted, 14 learned |
| 08 | mid | 15 learned, 16 scripted |
| 09 | near | 17 learned, 18 scripted |
| 10 | mid | 19 scripted, 20 learned |

The actual `agent.brain.RANGES` height branch defines the bins. Measure
`h = (bbox_y2 - bbox_y1) / State.frame[1]` on the designated bot at readiness:
near is `h >= .325`; mid is `.065 < h < .325`. Exactly `.065` is far and cannot
count as mid. These are apparent outline sizes, **not metres**; leave
`Detection.distance` unknown. Preserve the processed frame dimensions and bbox,
native visual correspondence and any clipping/identity uncertainty. Height is
classified only at the observed start; movement afterward is allowed.

The shared condition allocation is `galacta-shared-01`: same Galacta area/view
reference, patch, bot-health configuration, bot-movement setting, PAD bindings,
hold-to-swing, normal cooldowns and full starting resources. Root's concurrent
setup supplies the exact location reference and observed setting values before
slot 1; all are currently null/unverified. The schedule does not claim a known
Galacta health value or movement setting. Freeze the actual shared configuration
once and use it for both policies; if setup cannot meet a planned bin, retain
that failure. Player movement/aim continue normally; there is no stationary
player or Idle prerequisite. Missing target-health evidence cannot be guessed
from a vanished bar or a successful `start_pose`.

The existing-scripted baseline is `agent.brain.decide` at the pinned revision,
with the existing Controller, 60 Hz configured reflex / 10 Hz decision cadence,
20-second loop cap, normal cooldowns and end scoreboard. Live warmup is already
off; the legacy 180-second keepalive cannot trigger in a fresh 20-second loop.
Its existing attack sequences remain part of that baseline. This is not an
always-start policy substituted into the learned mode.

The learned candidate continues the archived request checkpoint
`6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef`, confidence .7,
with the pinned current code and existing scripted target/aim/approach executor.
Only the fifth archive's report/meta were read to identify it. Root supplies
fresh reviewed Galacta runtime/deployment profiles and checkpoint path; the
consumed Luna binding is not reusable. This schedule does not itself certify a
runtime profile. Record any necessary code/config change explicitly before the
first trial; preserve this original schedule and every allocated slot.

## Fields to bind before and after each trial

`episode_id` is already unique and remains the scheduled identifier. `run_id`,
`epoch` and `target` have unique visibly unexecuted/unobserved placeholders;
bind them to the real run, reset epoch and **particular visible bot life**.
`spec.track=0` exists only because the accepted constructor requires an integer;
it is not an observed detection. `collection.observed_track=null` makes this
explicit. Replace it from evidence even if the actual observed ID happens to
be zero. Shared names such as GALACTA BOT and reissued tracker IDs alone do not
identify an incarnation.

Before an attempt, retain these actual facts; unknowns remain null:

| Field(s) | Required source / meaning |
| --- | --- |
| `spec.policy`; runtime receipt alongside `collection` | Frozen baseline revision/config or checkpoint + exact source/runtime/deployment/controller/reader/calibration hashes; root's existing provenance receipt, not inferred from a filename. |
| `spec.patch`, `patch_evidence` | Observed client/build reference. The kit default or archived Luna patch is not observation of this session. |
| `spec.cooldowns`, `settings_evidence`, `settings` | Observed normal cooldown regime; settings keys `bot_health`, `bot_movement`, `bindings`, `swing`. Keep the actual settings/profile hash as an additional settings key for exact joint matching, plus contemporaneous evidence. Do not put per-trial evidence filenames in the settings values being compared. |
| `collection.start_bbox`, `start_frame`, `start_visual_height_ratio`, `start_location_view_evidence` | Actual processed bbox/dimensions, derived ratio, corresponding native location/view and visible Galacta identity. These join fields are not validated automatically by the scorer. |
| Reset observation, when a reset occurs | `t`, `kind:"reset"`, `epoch` naming the new epoch, `evidence`. Record the actual reset boundary/procedure and later respawn; do not fabricate a reset to explain unknown counter history. |
| Same-epoch baseline board | `t`, `kind:"board"`, `epoch`, `evidence`, `kos` or null. Native open/readable scoreboard after the latest reset and before readiness, with no intervening attack/uncaptured KO. Preserve grab bounds below. |
| Readiness observation | `t`, `kind:"ready"`, `epoch`, `target`, `track`, `range_ok`, `identity`, `full_health`, `resources_ready`, `evidence`. All four booleans must be exactly true for a valid start; evidence must establish each. An actual failed readiness assessment may contain false/unknown values and stays a setup failure. An absent assessment stays absent. |
| `collection.native_recording`, `clock_join` | Existing original recording reference plus mapping/uncertainty from native PTS to the loop monotonic clock. Never use file index, rounded log time or inference-return time as acquisition time. |

The audited readiness timestamp starts the **20-second encounter**. Actual own
resources and visible full target health must be established then, not borrowed
from a setup frame after a reset or attack. The historical name/no-bar cue needs
the existing visual audit contract; no new automatic full-health reader exists.

After the trial, preserve all observations (including failures):

| Field(s) | Required source / meaning |
| --- | --- |
| Designated kill observation | `t`, `kind:"kill"`, `epoch`, `target`, `track`, `identity:true`, persistent `event_id`, `association`, `lo`, `hi`, `evidence`. Reviewed continuity ties this specific incarnation to affirmative KO/feed evidence; `[lo,hi]` bounds occurrence, `t` is display/observation time. Interval wholly inside `[ready,ready+20]`; a common bot name, disappearance or aggregate increment is insufficient. |
| After scoreboard | Same board fields and epoch as baseline, after the kill interval; exactly one corroborating KO increment is required. Extra respawn/other-bot kills cannot be pooled. Preserve missing/unreadable boards as missing/null. |
| Timeout coverage | If no completion is established: `kind:"coverage"`, `t`, `lo`, `hi`, `epoch`, `target`, `track`, `identity:true`, `association`, `evidence` documenting continuous audited no-completion coverage through `ready+20`. `max_time` alone is not a timeout observation. |
| Range / reset / stop | Actual `range` observations with `t,epoch,evidence,range_ok`; every reset boundary; `stop:{t,reason,evidence}` at its real time. Preserve loss, unknown, capture/operator interruption and runtime error evidence rather than calling them death or timeout. |
| `scope_audit` | `breach:true/false/null`, `evidence`; add auditor identity in `collection.scope_audit_author`. Null is unaudited, not zero breaches. |
| `run_dir`, `log_interval` | Explicit completed run directory relative to filled manifest and `[start,end]` in that run's clock, including applicable baseline/terminal board captures. No overlapping intervals for shared logs; trials in a common run must preserve resets and chronological observations. Never make separate run IDs solely to hide shared history. |
| Timing / release | Preserve originating decision/resource/step, send and neutral release records unchanged; put neutral references in `collection.neutral_release_evidence`. Record actual setup/reset/respawn intervals with clock/evidence, total `wall_seconds`, and measured `reset_seconds` / `respawn_seconds` arrays. Empty arrays mean unmeasured, not free resets. |

For automatic board adaptation from `meta.json`, keep all of
`file`, `parsed.open`, `parsed.kos`, `captured_t`,
`capture_interval:[grab_start,grab_return]`, and
`capture_clock:"grab_start_to_return_loop_seconds"`. The existing adapter emits
`Observation(t=captured_t, lo=grab_start, hi=grab_return, capture_clock=...)`.
The baseline interval must start after reset and end by readiness; an after-board
interval must start at or after the kill's upper bound. Legacy board `t` is
pre-hold and cannot be substituted. Grab bounds do not bound render age or a
game event; the audit retains that uncertainty. Explicit audited board times
can be supplied in `observations` when automatic metadata is absent. Never
backdate a kill from a board timestamp.

## Existing caller commands and concrete joins

Offline commands work now, require no model, capture or pad, and do not sync the
shared environment:

```powershell
uv run --offline --no-project python -m scripts.range_benchmark score data/benchmarks/galacta-pilot-20260922/schedule.json
uv run --offline --no-project python -m scripts.range_benchmark inspect-log <completed-run-directory>
uv run --offline --no-project python -m scripts.range_benchmark score data/benchmarks/galacta-pilot-20260922/filled.json
```

After root has native scoreboard images, the existing pixel reader can be called
in its **already provisioned perception environment**:

```powershell
uv run --offline --no-sync python -m scripts.range_benchmark read-pixels <baseline-native.png> <after-native.png>
```

The existing runtime entry accepts the following arguments. These are root-only
caller templates with pending actual paths/PID, **not a complete automated
benchmark collector**; none was executed here. Run only in root's provisioned
runtime after the collection joins below are established:

```powershell
uv run --offline --no-sync python -m agent.loop --live --brain range-skill --range-checkpoint <checkpoint-path> --range-sha256 6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef --range-identity <source-identity.json> --range-runtime <fresh-galacta-runtime.json> --range-deployment <fresh-galacta-deployment.json> --game-pid <actual-game-pid> --cooldowns normal --max-s 20 --reflex-hz 60 --decision-hz 10 --save-fps 10 --run galacta-pilot-20260922-01-learned
uv run --offline --no-sync python -m agent.loop --live --brain scripted --cooldowns normal --max-s 20 --reflex-hz 60 --decision-hz 10 --save-fps 10 --run galacta-pilot-20260922-02-scripted
```

Concrete caller gaps are limited and visible in current code:

1. `main` performs `start_pose`, then starts Loop without an audited episode-ready
   hook or pre-start scoreboard. `Loop.t0` is its first acquisition, not an
   externally verified target/resource timestamp. The smallest collection join
   is a real same-epoch native baseline plus readiness at the actual input-phase
   origin, on the same preserved clock, before offense. If that cannot be proved,
   a command with `--max-s 20` is not by itself a valid 20-second benchmark start.
   An existing root supervisor may supply the join; this delivery does not add
   one or retimestamp observations. Startup's Galacta acceptance is being checked
   by root, and cannot stand in for identity/full-health/resource proof.
2. Neither CLI pins a designated visual incarnation or stops automatically at an
   audited KO. Generic selection may change targets, and the fifth Luna run
   continued after respawn. Root's collection/audit must preserve association and
   stop/release the episode appropriately using its existing supervised boundary.
   `score` is offline and cannot enforce that stop. No new target or KO reader is
   supplied. Do not score multiple incarnations as one task.
3. End scoreboard acquisition exists (`_finish -> _scoreboard`) but the learned
   session guard still expires at pre-attach time +14+20 seconds. Acquisition can
   be refused at that boundary; a missing terminal board stays missing. The
   scorer's two-second display grace grants no input/deadline extension. Root
   retains any separate already-authorized observation collection.
4. `--game-pid` is checked/composed only for `--brain range-skill`; the scripted
   CLI uses the legacy `LiveIO()` proof path. Passing that flag to scripted mode
   does not create a foreground-PID proof. Root must resolve its existing guarded
   baseline collection path before treating these command templates as a matched
   guarded pilot. No safety-path change is proposed or made here.
5. `score` matches joint scenario/patch/cooldowns/settings counts, not native
   landmark/bin correctness or pair order. Preserve and audit the predeclared
   pair/order/bin evidence alongside the result. `meta.stop` adaptation uses the
   last log row, and unlocated errors fail closed; retain the exact stop/release
   record separately rather than changing log timestamps. Native PTS-to-loop
   alignment and full acquisition-to-input latency remain explicit audit joins.
   The CLI reports compute latency from `ms`/`ms_decide`; capture-to-input remains
   unknown unless separately measured. It does not consume the newer detailed
   stage clocks as end-to-end latency.

## Verified preview and handoff

`unexecuted-result.json` is stdout from the actual accepted CLI (exit 0), not a
synthetic success fixture. It retains **20 setup failures, zero attempted or
auditable executed encounters**, null start/end/reward/evidence, ten slots per
policy and five per bin. `comparable_schedule:true` only means the planned joint
context counts (including shared nulls) match. Both `comparison_ready` values,
both matched-baseline values and both gates are false. The preview's 0/10
fractions/Wilson intervals are arithmetic on an unexecuted allocation, not
measured performance or a claim that gameplay failed twenty times.

`verification.json` pins inspected sources and records the real CLI result plus
pure height-boundary checks. `verify.py` uses only stdlib and existing pure code;
it refuses to overwrite its frozen reports. All scope audits, timing exposure,
reset costs and human-reference comparison remain unestablished. The accepted
exploratory Luna KO is not one of these trials. No human reference was read or
invented.

Root's minimum next handoff is the observed Galacta setup/condition profile,
joined baseline/readiness/phase origin and guarded baseline caller decision,
then filled per-trial records preserving every allocation. The existing F review
applies to the changed evidence interface once an actual filled artifact is
ready; this unexecuted preparation requests no new broad audit. Outcome gate:
at least eight audited designated completions in the learned ten within 20s,
zero scope breaches, actual matched baseline evidence, complete failure/reset/
latency report and wide uncertainty. This is feasibility, not James parity.
