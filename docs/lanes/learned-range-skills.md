# Learned range skill events — implementation handoff

2026-09-22. VUH-1346. Owner: learned-range; independent changed-boundary review:
range-review; integration/acceptance: root. Implementation is review-ready,
**synthetic plumbing only**, not admitted human training or deployment approval.
No real data/media were opened; no pad, capture, shared installation or commit.

The learned output is one Web-Cluster start request per 100 ms forecast horizon.
`no_new_start` permits independently scripted aim/approach and completion of an
already owned bounded pulse. It is not standing idle, tactical Search or an
instruction to stop moving. Selection, aim, movement, resource legality and pulse
delivery stay scripted. Low-HP Disengage is scripted retreat, not learned routing.

## Exact APIs for admission and root

`policy/range_skill_policy.py` exports:

```python
FORMAT = "rivals-range-skill-events-v1"
HEAD = "web_cluster_start"
OUTCOMES = ("no_new_start", "start")
SEMANTIC_REVISION = "web-cluster-onset-v1"
FEATURE_REVISION = "masked-state-grid-causal-v1"

SourceIdentity(patch, cooldown_regime, source_profile_sha256,
               perception_sha256, selector_sha256,
               semantic_revision=SEMANTIC_REVISION,
               feature_revision=FEATURE_REVISION)
SkillRuntimeIdentity(patch, cooldown_regime, runtime_settings_sha256,
                     calibration_sha256, controller_code_sha256,
                     perception_sha256, semantic_review_sha256,
                     input_domain="virtual_pad", selector_sha256="",
                     semantic_revision=SEMANTIC_REVISION,
                     feature_revision=FEATURE_REVISION)
SkillDeploymentBinding(checkpoint_sha256, source_identity_sha256,
                       runtime, review_sha256)
```

`selector_sha256` is required to be a valid hash despite the runtime dataclass's
empty constructor default. The same fixed selector implementation is pinned in
source and runtime. Source/runtime perception profiles may differ and need their
own review. `source_profile_sha256` names the **visual source profile**, including
explicit motor-setting unknowns. It does not assert known KBM motor settings and
cannot substitute for the runtime pad settings/calibration evidence.

`SkillDeploymentBinding.runtime` is a `SkillRuntimeIdentity`, not an unparsed
dictionary. Its source digest is `digest(dataclasses.asdict(source_identity))`.
The receipt binds exact checkpoint bytes and the independently expected runtime,
including controller code, calibration, perception, selector, semantic/feature
revisions and semantic review. Hashes name receipts; they cannot prove that a
human/independent review actually occurred. Root supplies accepted receipts.

```python
EventExample(
    session, group, split, continuous_id, media_sha256, review_sha256,
    evidence, source,
    segment_start_t, segment_end_t, grid_origin_t, grid_index,
    history, anchor_t,
    exposure_start_t, exposure_end_t, confirmation_t,
    label, label_known, reason, anchor_target_track, target_agreed,
    event_id=None, last_not_started_t=None, first_started_t=None,
    head=HEAD, semantic_revision=SEMANTIC_REVISION,
    origin="reviewed_human",
)
```

`history` is a tuple of the existing `Snapshot(state, target, available_t)` type;
`source` is a `SourceIdentity`. `split` accepts `train` or `val`; sealed/test and
scripted supervision are refused. Native media and reviews are receipt hashes,
with an evidence reference. Admission supplies these objects; there is no inferred
real-data adapter or corpus discovery. Preserve the selector output at each
historical snapshot; only the causal anchor target is matched to the reviewed
human event. Do not retrofit future human targets into earlier inputs.

## Coverage, actual clocks and labels

`Spec` fixes `steps=5`, `period_s=.1`, `tolerance_s=.025`. Hidden width and refusal
confidence are configurable. Grid origin and continuous segment boundaries come
from the admitted packet, not a search for bins that yield desirable labels.
Each segment retains every eligible coordinate, inclusively:

```text
first = ceil((segment_start_t - grid_origin_t) / .1) + 4
last  = floor((segment_end_t - grid_origin_t) / .1) - 1
anchor_t = grid_origin_t + grid_index * .1
forecast = (anchor_t, anchor_t + .1]
```

The implementation tolerates floating-point rounding at these boundaries.
It rejects duplicate/missing coordinates, inconsistent segment declarations,
overlapping segments and session/media/group leakage between splits. Each immutable
media hash is bound to one canonical session, group and split within the cohort;
renaming the session cannot double its support. Distinct media in the same group
remain valid. Counts follow cohort validation, never deduplication by guesswork.

**Uninspected coverage rows need no decoding or annotation.** Keep
`label_known=False`, `label=None`, an explicit `reason`, `history=()`,
`target_agreed=False`, `anchor_target_track=None`; the three exposure/confirmation
clocks may all be `None`. They contribute to coverage/mask counts and evidence
identity, never tensors, negatives or scores. Known rows require actual history,
full horizon exposure and reviewed causal target correspondence. One genuine
onset and one genuine nononset plus these cheap coverage rows suffice for a
train-only plumbing fit; independent validation is not a prerequisite for that fit.

`event_window(history, anchor_t, spec=Spec(), sampling="grid")` checks each actual
`State.t` within 25 ms **at or before** its scheduled tick; `available_t` must be
between acquisition and that tick. Actual clocks remain unchanged. The last
decoded CTS need not equal the annotation grid anchor. Duplicate, future or stale
frames fail; history and confirmation cannot cross the continuous boundary.

With `sampling="live"`, the final actual acquisition time is the anchor; earlier
actual observations can jitter either side of nominal positions within 25 ms,
with adjacent cadence also within 25 ms of 100 ms. All observations must be causal
at the anchor. The consumer receives already processed State objects; State has
no separate processing-availability field, so it records availability on that
State's clock. Root's actual acquisition-to-decision/input latency and deadline
guards remain necessary. This offline-grid/live-acquisition sampling difference
is an explicit v1 assumption to test on independent validation, not timestamp
retiming or a latency measurement.

A positive carries stable `event_id` and the observed bracket
`(last_not_started_t, first_started_t]`, wholly within one forecast interval.
`confirmation_t` includes the latest observation needed to confirm the label;
`purge_footprint()` extends through that confirmation. Known nononsets require
the same full-horizon exposure and target match. Moving, recovery and other
abilities are compatible with no new web start. `target_agreed=False`, switch
disagreement or a cross-bin bracket remains unknown. A retained unknown bracket
cannot overlap a known adjacent label; uncertain bins cannot become negatives.
One event cannot supervise multiple positives or change brackets under one ID.

## Train, evaluate, save and load

```python
policy = train(examples, spec=Spec(), epochs=20, batch_size=32,
               lr=.001, device="cpu", seed=0)
sha = save_checkpoint(path, policy, examples,
                      code_sha256=code_hash, training_config=config)
policy = load_checkpoint(path, expected_sha256=sha,
                         expected_identity=source,
                         expected_runtime=runtime,
                         deployment_binding=binding,
                         device="cpu", offline=False)
report = evaluate(policy, train_examples, validation,
                  complete_evaluation=False)
```

CPU/MPS only. Training uses every known row, inverse-class-frequency weighted
cross-entropy and no negative subsampling. The GRU, fixed masked State features,
numeric fitting and portable checkpoint helpers are reused from `range_policy`.
The legacy format, vocabulary and offline behavior remain unchanged.

Reports distinguish grid bins, unique events, masked reasons and ammo-positive
visible nononsets. Ammo-positive is a measured stratum, **not proof of every
physical start condition**. Unknown rows are neither inferred nor scored.
Validation must be independently grouped and match the exact training evidence.
Partial observed diagnostics are explicitly named; full evaluation additionally
requires `complete_evaluation=True` and known coverage for every declared bin.
Completeness applies to declared segments, not an uninspected whole recording.

Event metrics match proposed requests one-to-one to brackets inside their forecast bin.
Additional requests count as false positives, withheld starts as false negatives;
refusals and unknown coverage remain visible. Timing is request-to-bracket
distance, not an invented precise human onset. Baselines are never-start,
always-start, deterministic training-rate requests, recent confirmed event
(only confirmations already available at the current anchor, within one second)
and ammo-positive. Baselines are diagnostic predictions, never training labels.
The former metric key `accepted` is now `confidence_filtered`: thresholding an
offline probability is not consumer or executor acceptance. Reports explicitly
name `prediction_boundary="offline_model_proposals"`, record the threshold and
set `consumer_acceptance_measured=False` and `executor_acceptance_measured=False`
inside `confidence_filter`. `offline_assumptions` lists the boundary: known rows
provide reviewed causal selector outputs, but evaluation does not replay the
continuous gate, history faults, retreat, aim, resource legality, pulse ownership,
deadlines or delivery. Model and confidence-filtered TP counts are proposals only.
The training-rate estimate describes known rows and can be biased in a partial
packet; no generalization claim follows. Report actual live accepted pulses
separately from offline model proposals.

Checkpoint files are exclusively created, CPU portable, externally hash pinned
and loaded with `weights_only=True`. New loader rejects legacy formats,
class names and bindings. Train/save issue no deployment receipt. A synthetic
checkpoint only loads offline; reviewed-human metadata alone still cannot load
live without expected runtime plus matching new receipt. The former binary
checkpoint stays a legacy synthetic diagnostic; class 0 is never reinterpreted.
Root owns legacy live-mode revocation and CLI integration.

## Consumer boundary

```python
from agent.learned_range_skill import LearnedRangeSkillBrain
brain = LearnedRangeSkillBrain.from_checkpoint(
    path, expected_sha256=sha, expected_identity=source,
    expected_runtime=runtime, deployment_binding=binding,
    device="cpu", offline=False,
)
intent = brain(state, memory)
```

Use a fresh brain and Memory per episode. The reviewed `brain.gate` supplies fixed
target selection; only valid scripted Disengage can bypass model inference.
Legacy held Engage/Combo/Search intents are never returned. Missing detector,
lost/coasting/untracked target, malformed current state, incomplete/invalid
history, inference error or low confidence produces neutral `Idle`. Missing
detector, malformed observations, nonmonotonic clocks or cadence gaps reset
history; five valid causal observations are needed again. **Known-empty frames
and valid frames with no selected target remain history**, including first-sighting
acquisition and observed target loss/coast. Their actual selector output stays
`None`; the consumer still refuses an unsupported current target. A valid first
acquisition can infer immediately when the preceding observed gameplay completes
the five snapshots. Scripted retreat observations likewise remain causal history,
while the current retreat gate never infers an offensive request. Histories and
returned targets are copied. A currently observed target
switch remains represented in actual causal history; no future target features
are invented. Controller owns rejection/sequence clearing on switch.

The learned path emits:

```python
RangeSkill(target, request, decision_id, state.t + .1,
           RangeSkillResources(webs=state.webs, observed_t=state.t))
```

IDs increase on every consumer invocation, including refusals, within its
episode. `consumer.last` contains decision clock/ID, proposal, probabilities,
source/reason, target, validity and resource clocks; root captures it atomically
with the decision. Pass **original** `Decision.t` to `Controller.step(intent_t=...)`.
Never replace the resource observation time or ammo with reflex readings.
`consumer.source` uses `range_skill_model`, `range_skill_refusal`, or
`range_skill_gate`. Gate trace explicitly names scripted low-HP retreat.
Unknown/zero ammo can be proposed by the model but Controller must consume and
reject that start; the consumer never invents another offensive action.

Controller review remains separate: one start is terminally consumed on accept
or reject, full calibrated press must fit the deadline, no-new completes only
its owned pulse, refusal/loss expires/cancels, and no scripted attack fallback.
Movement/aim and true pulse delivery require root's integrated episode review.

## Verification and remaining limits

Bounded Windows CPU command using cached isolated dependencies:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_skill_policy.py tests/test_range_policy.py tests/test_range_skill_controller.py tests/test_range_skill_loop.py -q
```

Initial pre-review result: **196 passed**. Includes new event schema/window/cohort masks, two-row
fit/exact reload, legacy regressions, review-binding rejection, real pure
Controller movement/start/refusal release and root's synthetic loop tests.
No pad factory or real media is involved. MPS execution has not been tested in
this delta. This is neither a performance result nor independent review.

The next consumer is admission's reviewed event packet using the exact fields
above; the next gate is range-review's changed-code review and root integration.
Human train-only fitting remains blocked on that packet, not on stationary Idle
footage or an arbitrary sample count. Accepted live reliance additionally needs
independent semantic validation, explicit reviewed runtime binding and bounded
episode evidence. No fit, kill, learned aiming, routing or teammate-support
claim is established by these synthetic tests.

Initial review snapshot SHA-256 (superseded by the RSP delta below; preserved as evidence):

| File | SHA-256 |
| --- | --- |
| `policy/range_skill_policy.py` | `9938df94ee777d1e5bce6297271b491c79b4d43b62e592ac2634a5980d22aeac` |
| `agent/learned_range_skill.py` | `cfdb0bf51ab495cf7ab8748049d34d7d5a83719f23e33df2b565d4a6cd23b394` |
| `tests/test_range_skill_policy.py` | `82d6520136903977fbcb9e106b88afd4f51aaa056ebf71a5f324583035d0b3c9` |
| `policy/range_policy.py` (pure helpers only) | `c46e7d8a6523892107c8a878532505d020896e5b32e9df6179c049d6aa3410bb` |

## RSP1/RSP2 same-reviewer delta

Root independently confirmed both findings. Before repairing production code,
the two new regressions reproduced **2 failures** with synthetic data:

- RSP1: the same five-row packet under a second session alias passed `cohort`,
  reporting `bin_support=[2,2]`, `unique_events=2` instead of rejecting duplicated
  immutable media. The repair binds media to `(session, group, split)` before
  fit/reporting. Same-session overlapping segment aliases also reject; distinct
  media/sessions sharing a group remain legal.
- RSP2: actual `brain.gate` on observations at `0,.1,.2,.3,.4`, empty for the
  first three and the same visible target for the last two, selected targets
  `[None,None,None,None,target]`. Offline confidence filtering reported TP=1;
  consumer returned `Idle/warming_up`, calls=0, history=1. After the repair the
  same real-gate control returns `RangeSkill(start)`, calls=1, history=5 with
  **exactly those original selector outputs**, no retrospective target fill.

No EventExample fields, semantic/feature/format constants, packet contents,
native media, labels or accepted legacy helpers changed. Only the offline report
key `accepted` changed to the more accurate `confidence_filtered`, with explicit
proposal-boundary metadata. No controller/executor acceptance is inferred.

Current isolated delta command (deliberately excludes root's changing Controller
join; imports no Controller on this selection):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_skill_policy.py -k 'not model_request_crosses_real_pure_controller_boundary' -q
```

Result: **68 passed, 1 deselected**. Controls include warmed proposals, current
empty/coasting refusal with retained actual observations, first-acquisition
confidence refusal, detector/malformed/cadence hard resets, and scripted retreat
without inference. Existing portable fit/load, masks and receipt checks also pass.
The accepted legacy helper file remains byte-identical to its hash above.
This delta is frozen for the same independent reviewer; root owns the subsequent
Controller/Loop join, acceptance and landing. No live or real-data claim follows.

Frozen RSP delta SHA-256:

| File | SHA-256 |
| --- | --- |
| `policy/range_skill_policy.py` | `582e3f08cba512d65cb58fc60de5e4498a26ad8766eda4fb66dde8d731580ed1` |
| `agent/learned_range_skill.py` | `77e4b7f19d4796737356b71d058d7c33688570940083cc82edb21d7c3e5c89ba` |
| `tests/test_range_skill_policy.py` | `3422e8968f157a41304d0a8d0e04d159a281b4cb5cdc6c02f5a011b03efb3947` |
