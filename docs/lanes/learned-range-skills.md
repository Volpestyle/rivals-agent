# Learned range skill events — implementation handoff

Current request-timing delta: see **Versioned received-request head** below.
The visual-onset API and accepted historical results retain their original meaning.

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
Evaluation alone permits independent source-profile hashes when
`same_event_domain(a, b)` matches patch, cooldown regime, perception hash,
selector hash, semantic revision and feature revision. Original supervision
origins must agree. Complete source identity still stays consistent within each
immutable media and session; joint split/coverage/event validation is shared
with the exact public `cohort()` path. Training source identity, evidence digest
and support must match the policy exactly. No source profile is copied or erased.
Reports retain full `training_source` and `validation_sources` dictionaries and
state `domain_compatibility="structural_only_not_review_admission_or_live_approval"`.
This comparison supplies no new review, admission, compatibility receipt or live
approval. Public `cohort`, training, saving, loading and deployment bindings keep
their exact source-identity contract.
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

## Evaluation-only independent-profile correction

Root accepted/landed the preceding RSP and joined implementation at `8f78ae9`;
the real six-label diagnostic fit/report work is separate and remains accepted.
This correction neither reopens that result nor blocks active native calibration.
It changes only this doc, `policy/range_skill_policy.py` and its owned test file.

The red regression used two fully valid synthetic packets with distinct
session/group/media identities and a difference only in `source_profile_sha256`.
Both passed public `cohort()` independently; actual `evaluate()` failed with
`mixed source identity or supervision origin` before inference. Root's read-only
diagnosis established that real profile hashes identify source-specific provenance,
not a shared event domain. Reusing the training recording's hash would falsify it.

The correction extracts the existing rules into **one** `_validate_cohort`
implementation. Public `cohort()` remains exact; only evaluation requests domain
comparison. Media/session full-profile consistency, canonical placements, full
grids, event identity/brackets, continuous boundaries and confirmation/purge
checks still apply jointly across training and validation rows. The exact
training cohort, policy identity/origin, evidence digest and bin support are
checked before any prediction. No separate divergent validator was introduced.

The green regression calls actual `evaluate()`: two predictions, TP=1, FP=0,
with both original profile hashes retained and validation evidence digest
unchanged. This is a fixed synthetic scorer, not a trained model or performance
claim. A further control retains multiple distinct validation profiles.

Negative controls reject **before inference** for each of the six domain fields,
supervision-origin mismatch, incorrect policy training identity/origin/evidence
or support, shared group/media/session across splits, a same-source session alias,
inconsistent full profile within media or session, missing/duplicate coordinates,
reused event ID, invalid onset bracket, crossed purge boundary and uncertain-event
overlap. Public cohort/train and save still reject mismatched source identities.
Actual save/load of freshly initialized synthetic weights and deployment receipt
validation prove that a domain-compatible but different source hash still fails
the exact checkpoint/deployment boundary. No optimization or training ran.

Verification, cached isolated dependencies, no Controller/Loop/probe import or
real artifact access:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_skill_policy.py -k 'not model_request_crosses_real_pure_controller_boundary and not two_observed_rows_fit_reload and not checkpoint_pins_new_semantics' -q
```

**93 passed, 3 deselected.** The deselections are the Controller join and two
previously accepted tests that perform a numerical fit. The numeric fitter,
weights behavior, consumer, schema/constants, old checkpoints and six-label
artifacts are unchanged. `policy/range_policy.py` remains `c46e7d8a...3410bb`;
the consumer remains `77e4b7f1...5c89ba`. No real-data reads, labels, training,
input/capture, shared installs, commits or Linear edits were performed.

Lead accepts the independently reviewed evaluation-only delta for landing.
The same reviewer passed 93 tests with the three documented exclusions and
verified complete evaluation across two original validation profiles, retaining
both identities and unchanged evidence. Conflicting profiles even in unknown
coverage rows reject before inference. Native/runtime modules were not imported;
unchanged numerical and controller evidence was reused. New human validation
keeps its own truthful provenance and existing review/admission authority.

Frozen evaluation-only delta SHA-256:

| File | SHA-256 |
| --- | --- |
| `policy/range_skill_policy.py` | `3fb99790514eec159789ce5f8b155239a8ab6da359f825720b89a50def931f8d` |
| `tests/test_range_skill_policy.py` | `17480913cb27c43852ce2621b3b4cdc41a7861c34af1c6effe272066a9ab355f` |

## Versioned received-request head

2026-09-22, VUH-1346. Review-ready synthetic implementation; independent
range-review and root acceptance remain pending. The accepted timing interpretation
at `dddf760` is documented in
[`range-request-timing-20260922`](../evidence/range-request-timing-20260922/README.md)
and its [independent review](../evidence/range-request-timing-20260922/independent-review.md).
Both historical positive anchors followed received RMB. Their visible-onset labels,
checkpoints and artifacts remain unchanged; they are not relabeled request models.

The separately discriminated API in `policy/range_skill_policy.py` is:

```python
REQUEST_FORMAT = "rivals-range-skill-requests-v1"
REQUEST_HEAD = "web_cluster_request"
REQUEST_SEMANTIC_REVISION = "web-cluster-request-v1"

RequestExample(
    session, group, split, continuous_id, media_sha256, review_sha256,
    evidence, source,
    segment_start_t, segment_end_t, grid_origin_t, grid_index,
    history, anchor_t,
    exposure_start_t, exposure_end_t, confirmation_t,
    label, label_known, reason, anchor_target_track, target_agreed,
    request_id=None, request_t=None,
    raw_input_sha256=None, raw_device=None, request_seq=None,
    prior_up_seq=None, prior_up_t=None,
    raw_continuity_start_t=None, raw_continuity_end_t=None,
    raw_continuity_known=False, request_status="unknown", raw_evidence="",
    cast_id=None, cast_last_not_started_t=None, cast_first_started_t=None,
    association_agreed=False, association_evidence="",
    head=REQUEST_HEAD, semantic_revision=REQUEST_SEMANTIC_REVISION,
    origin="reviewed_human",
)
```

The required common fields and their masks have the same types as `EventExample`.
`raw_device`, `request_seq` and `prior_up_seq` are nonnegative native integer
identities; request/prior times and continuity endpoints use the original source
clock. Request IDs are stable within immutable media. No visual `event_id`,
`last_not_started_t` or `first_started_t` constructor aliases exist for this type.
Internal event properties permit reuse of the existing cohort/metrics machinery.

Admission supplies the source-local displayed RMB web binding, received-state
continuity including focus/carry-in dependencies, and target/cast association in
the existing reviewed evidence. `raw_input_sha256` pins the raw stream;
`raw_evidence` references its reviewed device/sequence/state interpretation.
`association_evidence` and the cast ID/bracket identify the separately observed
response. The existing `review_sha256`/`evidence` and training evidence digest bind
these fields together. Hashes and nonempty references do not establish review by
themselves. This module has no raw reader, human-label adapter or admission power.

| Known outcome | Required evidence and meaning |
| --- | --- |
| `start` | `request_status="fresh_rise"`; exact received RMB `request_t` in `(anchor_t, anchor_t+.1]`; request ID/device/sequence and preceding received-up sequence/time; reviewed same-target association to a separately observed cast. Every actual feature's `State.t` and `available_t` strictly precedes the point. No fabricated request onset bracket. |
| `no_new_start` | `request_status="no_fresh_rise"`; complete received-state interval establishes no fresh RMB rise under the source-local displayed binding. A fully observed held continuation and release is valid. It does not assert no alternate binding fired, no visual emission, no movement, or agent Idle. Request/prior/cast point fields remain `None`; held evidence belongs in `raw_evidence`. |
| Masked | `label=None`, `label_known=False`, explicit reason. Status `held` alone, `repeated_down`, `unknown` or `association_conflict` does not create a known negative/positive. Unknown rows may retain actual evidence or omit histories entirely. No negative subsampling or retrospective target substitution. |

Both known outcomes require full horizon exposure, reviewed causal anchor-target
agreement and raw continuity spanning the entire forecast interval. In symbols,
`raw_continuity_start_t <= anchor_t` and
`anchor_t+.1 <= raw_continuity_end_t <= confirmation_t`. A positive additionally
requires continuity reaching its preceding received-up state, an ordered sequence,
and agreed cast confirmation after the received request. This expresses received
native input timing; it makes no physical-press, game-consumption or delivery claim.

The observed cast bracket may fall **after** the request horizon. It affects
association and purge, never feature construction or point-bin assignment.
`confirmation_t` includes the latest evidence actually used, including overlap
release when supplied. `RequestExample.purge_footprint()` includes the earlier of
actual gameplay history and `raw_continuity_start_t`, and the latest horizon,
exposure, request, confirmation and raw continuity end. Focus/held-state carry-in
may predate `segment_start_t`; it is evidence dependence, not pre-game gameplay.
All five feature snapshots and label exposure remain inside the gameplay segment.
Synthetic supplied-clock controls validate dependency start `0.421919351` with
gameplay `11..22.25` and confirmation `14.384998151`, without padding or retiming.
This is a bookkeeping test, not a read or admission of the corresponding source.

The same `_ExampleBase` and single cohort validator retain fixed 10 Hz/five actual
causal snapshots, original clocks, full grid masks, source identity, canonical
session/media/group/split placement, segment separation and support rules.
Request credit is additionally pinned to `(raw_input_sha256, raw_device,
request_seq)`: changing its ID or media cannot gain another event credit. Within
media, one raw input source is retained and one observed cast cannot supervise
multiple requests. Distinct media in the same group remain supported. Uncertain
points prevent known labels in their overlapping request bin; later cast evidence
does not turn later no-request intervals into positive request bins.

`train`, `save_checkpoint`, `load_checkpoint`, `evaluate`, `RangeSkillPolicy`, and
`LearnedRangeSkillBrain.from_checkpoint` keep their existing names/arguments.
Use `SourceIdentity(..., semantic_revision=REQUEST_SEMANTIC_REVISION)` explicitly;
runtime identities must explicitly name the same revision if supplied. Defaults
remain historical visual semantics. The checkpoint header, source identity,
runtime binding and expected identity must agree on the exact head/revision;
mixed cohorts and cross-semantic loads/deployment bindings reject. No class index
coercion occurs. Save remains unapproved; no runtime or deployment binding was
issued. Consumer code is unchanged and can use the shared typed `RangeSkill`
output through its actual loader; selection, aim, movement and execution remain
scripted and subject to existing gates.

The accepted evaluation-only profile compatibility rule also applies to the new
head: validation retains its own truthful source hash while the six structural
domain fields and original supervision origin must agree. Public cohort,
training, save, load and deployment retain exact source identity checks. Reports
now include format/head/revision. New event metrics match the received point
one-to-one and report `mean_request_lead_s` (request point minus prediction anchor),
not visual latency. `event_metrics(..., semantic_revision=...)` preserves this
key in empty strata. Historical visual metrics retain their original bracket key
and numeric behavior. Baselines remain never/always/rate/recent-confirmed/ammo;
recent-confirmed cannot use a late association before its confirmation clock.
Offline confidence filtering still measures neither consumer nor executor
acceptance. Partial diagnostic coverage is not complete evaluation or live approval.

Verification (cached isolated CPU dependencies, no Controller/Loop/native import):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_skill_policy.py -k 'not model_request_crosses_real_pure_controller_boundary' -q
```

**150 passed, 1 deselected.** The exclusion is the existing Controller join.
New checks exercise the actual two-row synthetic fit/save/load/evaluate and
consumer, point boundaries, strict pre-request features, held/release negatives,
late cast/release purge, pre-game raw carry-in, missing/future/invalid continuity,
masked uncertainty, canonical request credit, and mixed-format/source/runtime
refusal. All prior visual, RSP and evaluation-compatibility controls pass. This
does not establish human performance; no human artifacts/media/raw inputs were
read, no real fit ran, and no input, shared installation, commit or Linear write
occurred. Root owns independent review, integration and any further reliance.

### RT1: canonical raw-ledger placement correction

The first request-head freeze remains unaccepted pending the same independent
range-review. Root reproduced a missed evidence boundary: request-event dedup
ran only when an event ID existed. A validation negative or masked row could
therefore reuse the training raw ledger under different media/session/group
identities without triggering it.

The exact synthetic red regression used `train=request_packet()` and
`validation=request_packet("val")`, replaced validation index 4 with
`request_example(4, None, split="val")`, then set every validation
`raw_input_sha256` to the training ledger (`"1" * 64`). Actual `evaluate()`
accepted and invoked the fixed scorer at **0.5** on the known negative with raw
continuity **[0.48, 0.6]**. All-masked validation reuse also passed, as did a
same-split session alias with the ledger supplied only by its last masked row.
The focused red run yielded **3 failed, 5 passed**; independent-ledger,
positive-alias refusal and legitimate same-session reuse controls already passed.

The correction adds every supplied request `raw_input_sha256` to the existing
placement loop as `(raw_input, hash) -> (session, group, split)`, independently
of label mask or event ID. This also connects raw evidence to the existing
full-source-identity consistency within canonical sessions. No new provenance
framework or label inference was added. Existing per-media raw-source consistency
and per-event dedup remain in place. A canonical session/group may still use its
ledger across distinct media and nonoverlapping gameplay segments; independent
validation retains its distinct ledger (`"2" * 64`). Unspecified raw hashes in
unknown coverage rows remain unspecified, never fabricated.

Green focused result: **8 passed**, including all three previous failures, the
positive alias, independent positive/negative/masked controls, and legitimate
same-session multi-media use. Aliases reject before inference; the independent
negative still calls the scorer at **0.5** with all five grid rows retained.

Broader synthetic regression, with every numerical-fit test and the Controller
join excluded for this repair:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_skill_policy.py -k 'not model_request_crosses_real_pure_controller_boundary and not two_observed_rows_fit_reload and not checkpoint_pins_new_semantics and not request_train_portable and not cross_semantic_checkpoints and not request_loader_rejects_mixed and not fit_requires_both' -q
```

**150 passed, 9 deselected.** Earlier numerical/checkpoint evidence is reused;
no optimization/training ran for RT1. Only this document, the policy module and
its owned test file changed in this repair. Root's `tests/test_range_skill_loop.py`
was neither edited nor run. No Controller/Loop/native import, corpus access,
input, shared installation, commit or Linear write. This correction is frozen
for the same reviewer; root owns acceptance and the admission-module handoff.
