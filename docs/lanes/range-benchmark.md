# VUH-1319: deterministic range encounter benchmark

Owner: range benchmark lane. Base inspected: `77d50324881bc723a827d0f7202063f7b96e8e94`.
Owned files: `agent/episodes.py`, `scripts/range_benchmark.py`,
`tests/test_episodes.py`, this note. Original R1-R4, scoreboard timestamp controls
and the R1b/R3b/R2b delta were independently accepted and landed on main at
`f841527`. This is offline software; real gameplay evidence remains open.
No live input, capture attachment, desktop focus, pad
creation, corpus access, human-admission edits or commits were performed.

## Decision and delivery boundary

Lead accepted the pure interface and the first visible feasibility gate on
2026-09-22: **ten scheduled trials, at least eight audited designated-bot
completions within 20 seconds, zero scope breaches**. All ten remain in the
primary success-per-scheduled-trial denominator. Setup failures, interruptions
and unknowns are non-successes there. Also report success per attempted episode,
success per valid episode, every failure, reset cost and uncertainty. Baseline
bins and settings must match. This is feasibility, not pro-level parity.

The module prepares offline scoring for a real run. It neither supplies a learned
policy nor runs gameplay. The current logs cannot establish the gate alone.
The scorer is independently accepted and integrated at `f841527`; root owns
runtime scoring integration and actual evaluation evidence. Desktop ownership stays with the lead.

VUH-1325's body is stale: comments accept the eight findings at `a7f3445`, the
supervised safety run at `3a378ea`, and crop-first proof at `6c9a940`. Target
correctness and longer-run reliability remain open. VUH-1314 explicitly separates
held-ID consistency from visual correctness; its door/fragment failures are
material to this benchmark. Nothing here reinstates the old freeze or grants
new operational permission.

## What the pixels and existing logs actually support

Small authorized sample, all committed own-account evidence under
`docs/evidence/l4/`; no demonstration corpus was opened:

| Artifact | Inspection / existing reader result | Limit |
| --- | --- | --- |
| `scoreboard-back-native.jpg` (2560x1440) | Visually 3 KOs, 0 deaths, 1 assist, 845 damage; `read_scoreboard` agrees | Aggregate, no target association |
| `scoreboard-back-720.jpg` (1280x720) | Existing reader recognizes overlay, returns unknown counters (`too_small=1280`) | Do not substitute downscaled debug images for native digits |
| `scoreboard/killfeed-a.jpg` (2560x1440) | Feed names GALACTA BOT; several bots share that name; existing `is_killfeed=True` | Presence bit supplies neither event identity nor victim identity |
| `plaza30-start-confirm-2-native.jpg` (2560x1440) | Luna Snow visibly named without health bar; own HP 250/250, webs 5; feed false | Supports inspecting the proposed full-health cue, not a validated automatic full-health reader |
| `plaza30-practice-settings-page.jpg` (1280x720) | No Ability Cooldown switch visibly off | Historical settings evidence, not proof of the next session or patch |

`perception.scoreboard.read_scoreboard` and `is_killfeed` are the applicable
existing pixel outcome readers. `perception.evalread` contains older sample-bound
claims that the range has no scoreboard/feed; its HP and ult signals must not be
promoted into damage or elimination labels. No reader was changed or invented.

`agent.loop.RunLog` retains native saved frames and reflex rows containing `t`,
`ids`, `dets`, `target`, `coasting`, `ms`, and occasional decision `state` and
`ms_decide`. `meta.json` holds stop, range gaps, errors, parsed boards and timing
summaries. These supply useful descriptive observations, but neither a verified
full-health target start nor a target-linked kill occurrence. `State.frame` is
the processed coordinate space, which may differ from the saved native frame.

`plaza30-meta.json`: 2 aggregate KOs / 550 damage, normal cooldowns, no recorded
patch. That is not two scored designated-target episodes. Tick compute p95
12.86 ms, decision compute p95 99.53 ms and decision lag p95 121.88 ms are existing
run-level summaries, not capture-to-input latency. The scorer labels these
quantities separately and leaves unmeasured capture-to-input latency unknown.
Current loop `patch` can default from the kit; a nonempty metadata patch is not
observed build evidence.

## Pure caller contract

```python
from agent.episodes import EpisodeSpec, Observation, Stop, score_episode, score_batch
result = score_episode(spec, observations, stop=stop)
# Chronological (spec, observations, stop) tuples for repeated encounters:
results = score_batch(trials)
```

`score_batch` retains known observations separately for each run, including resets
after a completed trial and resets on failed trials. `score_episode` accepts that
context as `prior_observations`; its readiness always comes from the current
trial, never from history. Repeated citations of the same reset are idempotent;
conflicting epochs at one reset timestamp fail setup. A later trial cannot erase
a known boundary by omitting it from its own observation list.

All timestamps use the same monotonic recording clock, not time since process
launch, inference return time or image index. No wall clock is read by scoring.
Every observation has `t`, `kind`, `epoch`, and a nonempty `evidence` reference.
Evidence strings are audit references, not self-verifying proofs; the reviewer
must inspect those artifacts. Only an authorized pixel reader or human review
may assert the audited fields. Input schemas are frozen dataclasses and serialize
through `dataclasses.asdict`; `EpisodeResult.to_dict()` includes validity.

`EpisodeSpec` requires `episode_id`, `run_id`, frozen `policy` revision,
`scenario`, reset/counter `epoch`, designated visual-incarnation `target`, and
`track`. Context fields are `patch`, `patch_evidence`, `cooldowns='normal'`,
`settings_evidence`, `settings` with `bot_health`, `bot_movement`, `bindings`,
`swing`. Unknown context fails setup; it is never copied from expected defaults.
The target token distinguishes two same-name bots and a later respawn of one bot.
`display_grace_s` defaults to two seconds (maximum five): observation-only time
for delayed evidence, never permission to continue attacks beyond 20 seconds.

| Kind | Required meaning / fields |
| --- | --- |
| `ready` | Designated target and track, `range_ok`, `identity`, `full_health`, `resources_ready` all exactly true, with native evidence. First ready observation starts the clock. Unknown/false fails setup. A name must be readable on the associated visible bot; absence of a health bar alone cannot set full_health. |
| `board` | `kos` from an open, readable native scoreboard or null. `board_observation(t, epoch, evidence, parsed)` requires explicit audited time, or preserved grab bounds via `capture_interval` and `capture_clock`. Automatic meta adaptation requires all three root metadata fields: `captured_t`, `capture_interval`, `capture_clock`. Legacy pre-hold `t` or grab return alone is refused. Keep the pre-start baseline and post-event board in the same uninterrupted epoch. No attacks or uncaptured kills between baseline and readiness. |
| `kill` | Target, track, `identity=True`, persistent `event_id`, reviewed `association` reference tying that bot's visual continuity to the feed, occurrence bounds `lo..hi`, display `t`. A track ID or common victim name alone cannot populate association. |
| `coverage` | Audited no-designated-completion interval `lo..hi`, target, track, `identity=True`, association and recording reference. This is a reviewed recording interval, not zero detections or feed absent on one frame. Adjacent intervals can cover a timeout. |
| `range` | `range_ok=True/False/None` for a fresh observed range result; false is lost_range, null is interruption. A pre-ready failure remains active until an explicit true recovery. Recovery exactly at readiness clears an earlier loss: gaps are [loss, recovery). Tied contradictory range observations remain conservative regardless of row order. A ready assertion cannot clear a gap. Log gap intervals are merged before emitting loss/recovery observations. A scoreboard frame is a board observation, not a negative gameplay range observation. |
| `reset` | Ends attribution and names the new epoch. A previously observed epoch cannot be reused; pre-ready resets invalidate earlier baselines. A fresh post-reset board and readiness in the new epoch are required. Reset is an observed procedure, never a policy action. |

`Stop(t, reason, evidence)` preserves the runtime stop separately from a learning
terminal. Normal deadline/max-time stops cannot by themselves award a timeout.
Capture, guard, operator and other stops interrupt. The scorer never interprets
range loss as death. The first audited no-completion coverage through the 20 s
deadline supports timeout, including a controller stuck after a valid start.

Completion requires the associated kill, wholly within [ready, deadline], and
exactly one corroborating KO increment. A larger jump is conservatively unknown.
Repeated display reads produce no new credit; event and counter credits persist
across `score_batch`, keyed by run and epoch. Counter decreases invalidate
corroboration. Concurrent/overlapping encounters in one run and duplicate episode
IDs are rejected. Do not begin another target/reset before delayed attribution
finishes. An interval straddling the deadline is unknown, not backdated.

Reward v0, only for valid completed/timeout episodes: +1 completion or -0.25
timeout, minus 0.20 * elapsed/20 once. Completion uses the conservative upper
occurrence bound; both bounds are retained. Success at the deadline takes
precedence over timeout. Unknown/interrupted/setup rewards are null, not zero.
An unknown outcome's end/elapsed time stops at actual observed evidence or a
recorded stop; the 20-second horizon is not invented as an observation. The
restricted-completion comparison metric still intentionally assigns unsuccessful
attempts the deadline, as its definition requires.
Damage is always null in this reward: shield decay, healing and ult changes do
not produce damage shaping.

### Exact runtime handoff (outside this lane's owned paths)

1. Loop/supervisor owner freezes a run/episode identifier, policy+executor+reader
   revisions, scenario bin, target incarnation/track and reset epoch. Save native
   readiness evidence and actual resources. Existing start-pose acceptance proves
   arrival geometry, not full target health, resource readiness or visual identity.
2. Supervisor records observed build/patch and normal cooldown settings, bindings,
   swing mode, bot health/movement. Confirm exercised cooldown timing against the
   patch; do not label the kit default as an observed patch.
3. Preserve an initial native scoreboard reading, associated feed evidence and
   terminal native scoreboard reading. Existing `_scoreboard` acquires a board
   through reviewed guarded input, but its `t` is the passed loop time before
   the hold, not necessarily image-acquisition time. Add actual board capture
   metadata before automatic adaptation. Root reports the timestamp implementation
   independently accepted: `captured_t` is grab return,
   `capture_interval=[grab_start, grab_return]`, and
   `capture_clock='grab_start_to_return_loop_seconds'`, frozen when the board is
   chosen. The scorer preserves the interval in `Observation.lo/hi` and its clock;
   baseline intervals must end by ready and start after reset, while post-kill
   intervals must start at/after the audited kill upper bound. An overlapping
   grab cannot establish order. These are acquisition bounds, not render or
   game-event times: auditors must account for any earlier rendered frame in
   native evidence. Kill occurrence bounds never come from board `captured_t`.
   Legacy rows remain descriptive; explicit native-recording audit observations
   can still be supplied. This scorer must not
   press BACK or alter that path itself.
4. Add a separate audit adapter for visual target identity, full health and
   target-to-feed association, with occurrence intervals and stable event IDs.
   These readers do not currently exist. For the ten-trial pilot, explicit
   native-video human audit can supply the observations without pretending an
   automatic reader has been built. A missing observation stays unknown.
5. Stop encounter input at the true ready+20 s deadline or observed completion;
   release through existing reviewed input boundary. Observe a bounded delayed
   display interval before reset. Log interruptions with their own timestamps.
   Scoring is post-run; it is not a guard or a controller stop mechanism.
6. Keep continuous native recording through target acquisition, attack, terminal,
   reset and subsequent readiness. Record setup/reset/respawn durations and
   evidence, total wall exposure including rejected starts, acquisition-to-input
   latency, inference latency, real policy-choice count and fallback share.
   Existing tick `ms` is computation cost, not end-to-end latency. Root owns any
   capture changes; this lane did not consume a running capture.

## Offline CLI and manifest

```powershell
uv run --no-sync python -m scripts.range_benchmark inspect-log <completed-run-directory>
uv run --no-sync python -m scripts.range_benchmark score <benchmark.json>
# In an existing perception environment:
uv run --no-sync python -m scripts.range_benchmark read-pixels <native-frame.png>
```

CLI is module-invoked, stdout JSON only. `inspect-log` is explicitly descriptive;
it cannot manufacture episodes. `read-pixels` imports only the existing readers,
returns their observed values and null target/full-health claims. `score` reads
only named manifests/log directories; it never discovers corpora recursively.
Only completed immutable, authorized recordings should be named.

Manifest shape (fill evidence after acquisition; never remove failed slots):

```json
{
  "schema": "range-benchmark-v1",
  "scripted_baseline": "scripted:<frozen revision plus configuration>",
  "scenarios": {
    "plaza-front-mid": "declared view/landmarks, distance band, own resources",
    "plaza-offset-mid": "different declared view/offset, same resource regime"
  },
  "human_reference": null,
  "wall_seconds": null,
  "reset_seconds": [],
  "respawn_seconds": [],
  "trials": [
    {
      "spec": {"episode_id": "trial-01", "run_id": "run-01", "policy": "scripted:<frozen revision plus configuration>", "scenario": "plaza-front-mid", "epoch": "reset-01", "target": "bot-left-life-01", "track": 7},
      "observations": [],
      "stop": null,
      "scope_audit": {"breach": null, "evidence": null}
    }
  ]
}
```

This deliberately incomplete example scores setup failure until real context and
readiness are supplied. Fill ten predeclared slots per pilot policy, not one.
Each observation is the corresponding `Observation` dataclass dict. Optional
`run_dir` plus `log_interval: [start, end]` supplies existing timing rows, parsed
boards with finite `captured_t` plus valid grab interval/clock, gaps and runtime stops; overlapping log intervals
are rejected. Boards carrying only legacy `t` are retained in descriptive log
inspection but never converted into scoring observations. A grab-return point
without interval is also refused. Explicit audited board
observations can be supplied alongside `run_dir` until acquisition timestamps
exist. Active gaps retain state through readiness; closed gaps emit recovery.
Unlocated runtime errors fail
closed rather than being dropped from the scheduled denominator.

`scope_audit.breach` is true/false/null plus an evidence reference. All ten need
audits for a passing feasibility gate; any breach marks experiment stop required
and prevents every policy gate from passing. Scoring does not operate the stop.
Global summary counts collection workload; policy/scenario summaries are the
comparison. The baseline is identified explicitly, never inferred from log names.

`comparable_schedule` compares planned **joint counts** of scenario, patch,
cooldowns and settings. It does not prove execution. `execution_evidence` reports
auditable executed slots and started encounters by scenario for every policy.
Each slot needs readiness evidence and a scope audit; a started encounter also
needs actual encounter evidence or a recorded stop strictly after readiness,
within the scored encounter boundary. A same-time range confirmation cannot
prove execution; neither can frames after an immediate recorded stop. Audited failed readiness remains
a setup failure in the scheduled denominator, but does not count as a started
encounter. Readiness alone is not execution evidence. Every declared scenario
must have a started encounter with positive observed duration. The
`matched_baseline_comparison` value additionally requires executed/auditable
coverage for all scheduled baseline and candidate slots. That value gates the
candidate; ten empty baseline slots cannot pass it. Timeouts and other evidenced
failures remain in the comparison, not filtered out to make it look better.

## Bounded pilot, baseline and James reference

Predeclare ten candidate slots over at least two visible, safely reproducible
start bins; proposed initial mix is five front-facing and five angular-offset
starts at declared distance bands. Lead confirms concrete bins before collection.
Freeze scripted baseline code/configuration and candidate checkpoint, perception,
executor, action-selection mode and settings. Schedule ten baseline slots with
the same bins/settings, interleaving where practical. Rejected starts occupy
their scheduled slots; no hidden retries or replacement of difficult valid starts.

Use the learning-plan's ten-episode/30-minute collection feasibility ceiling
including setup/reset per scheduled pilot block; stop and report the incomplete
block if it cannot fit. The CLI caps evaluation at 20 scheduled slots per policy,
matching the subsequent bounded evaluation contract; it does not enforce a live
wall-time limit. Lead's runner must enforce the pilot cap. This lane grants no
live-run authorization.

James reference is an explicitly authorized immutable human range recording or
newly authorized matched execution, scored under the same target/health/patch/
cooldown/start contract. Declare `human_reference` provenance and use
`policy='human:<reference id>'` slots to report like-for-like metrics. No suitable
reference has been admitted or opened here. A reference name without comparable
audited trials reports `not_established`. No human-admission files were edited.
Twenty-second single-encounter results do not establish next-bot acquisition,
long continuous reliability, learned target choice, tactical quality or parity
with James. Those remain explicit later measurements.

Report completion fraction, complete failure table, successful occurrence bounds,
restricted completion time (unsuccessful attempted encounters count as 20 s),
reset/respawn distributions, valid episodes/hour over full observed wall time,
and latency sample denominators. Wilson 95% intervals are descriptive and wide:
8/10 is approximately 49% to 94%; repeated trials may be correlated. Missing
reset/latency measurements remain null with n=0.

## Verification

Synthetic scoring tests exercise readiness unknowns, wrong target/common feed,
counter-only increments, repeated-event/counter credit, counter decreases/reset,
deadline precedence/straddling, delayed display, continuous timeout coverage,
runtime interruption, full denominators, accepted gate, mismatched baseline,
CLI log adaptation and deterministic serialization. They do not prove gameplay.
Four committed-image cases separately verify the existing pixel reader results
above; they assert no target/full-health labels are fabricated.

Shared venv remains stdlib-only. Read-only fixture checks and adjacent-loop tests
use uv's separate cached no-project environment; no dependency sync/install was
performed into this checkout's `.venv`.

Current pure delta verification, 2026-09-22:

- `uv run --no-sync pytest tests/test_episodes.py tests/test_loop.py -q`:
  **154 passed, 4 skipped**. The four existing pixel tests remain skipped; no
  pixel review, corpus access, environment install or live test was repeated.
- The initial R1b/R2b/R3b reproduction subset failed **3 tests**, with **5 controls
  passing**, before changes. The full result above includes original R1-R4,
  accepted timestamp controls and the new cross-trial/same-time cases.

Earlier verification (before this pure delta):

- `uv run --no-sync pytest tests/test_episodes.py -q`: **70 passed, 4 skipped**
  (the four pixel cases need the perception environment).
- `uv run --offline --no-project --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_episodes.py tests/test_loop.py tests/test_loop_frames.py -q`:
  **145 passed, 5 skipped** (five corpus-dependent cases remain skipped).
- CLI `read-pixels` reproduced the four table entries in the isolated environment;
  CLI help and `plaza30-meta.json` descriptive inspection also ran.
- An initial attempt explicitly selecting `test_loop_frames.py` in the stdlib-only
  venv failed collection on its OpenCV import. It was rerun successfully in the
  isolated perception environment above; the shared venv was not changed.

### Independent review fixes, 2026-09-22

Before changes, the new regression subset reproduced eight failures (R1, open
and spanning pre-ready R2 gaps, R3, both R4 cases, and two legacy timestamp
cases); six valid controls passed. Fixes are limited to these four owned files.

- **R1:** pre-ready reset history validates epoch freshness and bounds baseline
  selection. `board9/reset9.5(spawn1)/ready10/kill15/board16` is now
  `setup_failure:reset_reused_epoch`, no reward. Reset at 8 naming `spawn2`,
  followed by fresh `spawn2` baseline/readiness, still completes for +0.95.
- **R2:** range failures are persistent state. The adapter merges overlapping
  gap intervals and emits recovery only at their end; the scorer checks state
  at readiness. `[8,null]` and `[8,11]` crossing ready10 are lost_range;
  `[8,9]` permits the valid completion; `[12,null]` remains lost_range. A closed
  overlapping gap cannot clear an open one.
- **R3:** planned matching is separate from executed/auditable comparison.
  Empty or readiness-only baseline slots block the candidate gate. Ten audited
  baseline timeouts are a valid comparison. An audited failed readiness is
  retained, while per-bin actual-start support is still required.
- **R4:** joint-context `Counter` replaces sets, preserving 4-standing/1-moving
  versus 1-standing/4-moving differences. Matching 4/1 controls pass. A merely
  declared but unused bin, or a bin containing only setup failures, cannot pass.
- **Scoreboard timing:** only finite `captured_t` with root's grab interval/clock
  is automatically adapted and filtered against observation bounds. Missing
  `captured_t` or interval yields no board credit; a late value cannot borrow old
  `t`. Ready/kill/reset-straddling acquisition intervals cannot prove order.
  Adapter and pure-scorer regressions cover interval preservation and overlap;
  valid nonoverlapping acquisition and explicit audited-observation controls pass.
  Render age is not measured by grab timing and remains an explicit audit
  requirement in the JSON report. No legacy log files were modified.

### Rereview delta: run history, observed execution and readiness boundaries

- **R1b:** `score_batch` carries per-run observation history into later scoring;
  credits and known resets now share run lifetime. The exact old-`spawn1` repro
  gives one completion followed by setup failure, no second reward/credit.
  Fresh `spawn2` baseline29/readiness30/kill35/board36 succeeds. Controls cover
  repeated reset citations, separate runs, resets on setup-failed trials and
  conflicting same-time reset epochs. Earlier readiness cannot replace current
  readiness, and all observation history must precede the next ready boundary.
- **R3b:** matching counts actual post-ready evidence/stops, independently from
  planned schedule and computed outcomes. `ready10 + rangeTrue10` produces zero
  auditable executed baseline slots and zero per-bin started support. Unknown
  end time now stops at the last observed timestamp; it is 10 with ready-only
  evidence, not 30. Recorded immediate interruptions remain audited slots but
  supply no started support; actual later stops or frames can support a started
  encounter. Audited timeouts, setup failures and all scheduled denominators
  remain intact. Post-stop frames cannot rehabilitate a zero-duration encounter.
- **R2b:** latest range state at readiness includes observations at that exact
  timestamp. Recovery 9.999 or 10 after loss8 permits ready10; recovery10.001
  does not. Loss and recovery tied at readiness, or tied before it, are
  conservative regardless of input ordering. The ready assertion itself still
  cannot clear a range failure.

Scoreboard adaptation and pixel readers were not changed in this delta. The
accepted acquisition-interval behavior remains covered by existing pure tests.

Remaining blockers: root-owned runtime scoring integration and actual audited
ready/target/terminal observations for a live pilot. Root owns
issue blocker tagging; this lane did not add another Linear comment.

Accepted offline software boundary: independent review and main integration at
`f841527`; root owns the runtime/audit adapter handoff. No live pilot, reset/respawn measurement, current patch proof,
human reference comparison or learned-policy performance is claimed.
