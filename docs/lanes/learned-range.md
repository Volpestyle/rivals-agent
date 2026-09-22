# Executable learned range candidate — VUH-1346

Owner: learned-range. Lead owns integration, independent review, admission and
acceptance. Base `77d5032`; four new files only, uncommitted pending review.
No real/sealed data inspected or trained; no capture, pad creation or input.
VUH-1347 is the separate independent validation recording request.

## Decision and caller inventory

Lead accepted v1 **Idle / Engage only** on 2026-09-22. Claim: learned attack
delegation/timing. Aiming, approach, attacks/combos and target selection remain
scripted. No model-controlled range kills have been demonstrated.

| Existing boundary | Inspected behavior and consequence |
| --- | --- |
| `agent.loop.Decider._decide` | Constructs `State` from the processed frame, calls optional `see(frame,t)`, then `decide(state, Memory)`. New consumer uses State only; no `see` needed. |
| `brain.gate` | Owns fixed target selection, acquisition, coasting, retreat and active holds. Reused, with forced decisions reported separately. |
| `jev.legal` / `jev.adopt` | Reused legality and mode/intent bookkeeping. `idle` builds actual `Idle`; no fallback to scripted attacks. |
| `Controller.step` | `Engage(target)` aims, walks and chooses shots/melee/uppercut. `Idle` clears an active primitive. It does not learn button timing. |
| `Loop._tick` / `Live` | Range/focus/frame freshness, stale-decision release, pad allowlist and watchdog remain root-owned safety boundaries. |
| `policy.live` / `policy.train` | Historical MLX scripted-label head and fallback semantics cannot serve as human imitation or neutral refusal. Reuse the seam, not its training provenance. |
| `policy.execution` | Native KBM head remains offline. Reuse lazy PyTorch loading, canonical hashing, fingerprinting and validation utilities; do not reinterpret its output. |

Other existing options: `Search` executes a scripted sweep, `Disengage` executes
a scripted retreat, `Pull`/`WebStrike` require known tracer state, `Combo(BURST)`
executes a fixed sequence, and `SwingTo` needs an anchor. These are excluded
from the learned vocabulary. The unchanged gate can still force `Disengage`.
There is no learned no-target navigation; a trial must establish its starting
view/episode through root's harness. No claim of learned target/position choice.

## Interface handoff

```python
from policy.range_policy import (Identity, RuntimeIdentity, DeploymentBinding,
                                 Spec, train, evaluate, save_checkpoint)
from agent.learned_range import LearnedRangeBrain

# Admission supplies explicit in-memory Example records. There is no discovery,
# importer, placement writer or automatic KBM-to-intent labeling in this lane.
policy = train(train_examples, spec=Spec(), device="mps", epochs=20)
checksum = save_checkpoint(
    new_path, policy, train_examples, code_sha256=code_digest,
    training_config={"epochs": 20, "device": "mps", "seed": 0},
)
# Optional for a clearly labeled train-only diagnostic; mandatory for acceptance.
report = evaluate(policy, train_examples, independent_validation_examples)

brain = LearnedRangeBrain.from_checkpoint(
    new_path, expected_sha256=checksum,
    expected_identity=Identity(patch, cooldown_regime, settings_digest,
                               perception_digest),
    expected_runtime=runtime_profile,
    deployment_binding=reviewed_binding, device="cpu",
)
# Root's existing Loop(..., decide=brain) seam after independent review.
intent = brain(state, memory)
```

Construct a fresh consumer and `Memory` for each episode. Default cadence is
10 Hz: five observations at `t-.4, t-.3, t-.2, t-.1, t` (25 ms slot tolerance).
Root must match its decision cadence to the checkpoint's spec. Cadence gaps
clear history; repeated/backward states refuse. History holds copies of the
processed states. Missing detector clears history and yields `Idle` before the
gate can renew any intent. Warmup or invalid full history prevents offensive
gate holds/coasting as well as model decisions. Valid current-state retreat
may preempt history warmup, but cannot bypass detector failure, malformed state
or nonmonotonic timestamps. Fresh known-empty detections (`[]`, unlike `None`)
with a complete valid window preserve the gate's existing coasting grace.
Invalid predictions, low confidence or illegal Engage yield `Idle`. No
ranking-through-illegal-choice or scripted attack fallback. Gate decisions are
reported as
`range_gate`; predictions as `range_learned`; refusals as `range_refusal`.
`brain.last` supplies timestamp, source, reason, probabilities, typed action
and target track; `brain.stats` counts source. Root owns recording these details
beyond the existing per-decision source field. No shared files changed.

Default confidence threshold .7 is a declared heuristic, not calibrated
uncertainty or a performance gate. No wall-clock freshness claim is possible
from State alone: root must retain the loop and Live checks independently.
Checkpoint load pins a caller-supplied SHA-256, source identity, feature layout,
vocabulary, tensor shapes and finite weights. `weights_only=True` is used.
Synthetic origin requires `offline=True`. Source `Identity` is unchanged human
KBM provenance, never a declaration of the live pad configuration.

Live load additionally requires both `expected_runtime: RuntimeIdentity` and
`deployment_binding: DeploymentBinding`; missing either rejects. Offline
train-only candidates can load without either. If either is supplied even in
offline mode, both must validate. Exact field names:

```python
runtime_profile = RuntimeIdentity(
    patch=patch, cooldown_regime=cooldown_regime,
    runtime_settings_sha256=pad_settings_digest,
    calibration_sha256=pad_calibration_digest,
    controller_code_sha256=integrated_controller_code_digest,
    perception_sha256=runtime_perception_digest,
    semantic_review_sha256=source_to_pad_semantics_review_digest,
    input_domain="virtual_pad",
)
reviewed_binding = DeploymentBinding(
    checkpoint_sha256=checksum,
    source_identity_sha256=source_identity_digest,
    runtime=runtime_profile, review_sha256=deployment_review_digest,
)
```

The binding is an external review receipt issued after the independent
validation/semantic/controller gates by the acceptance owner, not a trainer
flag. This avoids a self-referential checkpoint hash. Its source digest is
`digest(asdict(source_identity))`; its model digest pins exact checkpoint bytes.
The separately measured expected runtime must equal the entire reviewed runtime
profile. Patch/cooldown must match the source. Runtime settings hash the
**domain-tagged virtual-pad settings manifest**; copying the KBM settings digest
rejects. Calibration/code/perception/semantic-review hashes are individually
required. Controller code identity covers the integrated selector/decision/
controller implementation. Root loads accepted JSON profiles explicitly and
constructs the dataclasses (including the nested runtime in the binding).

Hashes pin supplied evidence; they cannot certify that a review actually
happened. Root must supply the accepted receipt and independently measured
runtime, and retains trial authority and screen guards. `train`/`save_checkpoint`
create no receipt and require no deployment approval. Direct policy injection
and fabricated receipt fixtures are for offline tests only.

## Causal feature and supervision contract

The GRU consumes 26 columns: value/known pairs for HP fraction, web ammo, pull/
uppercut/swing readiness, crosshair, detector availability, fixed-target presence,
target x/y/height in frame fractions, measured distance/40 and tracer state.
Features use fixed physical scaling; there are no fitted feature statistics.
Class weights and majority baseline use training labels only. Raw frames remain
the source of State, but this first candidate does not encode raw scene pixels;
its limited spatial/context representation is an explicit quality ceiling.

`Snapshot(state, target, available_t)` must refer to the processed frame, with
every measurement and its evidence available by the anchor. Target must be in
that frame's detections. Unknown values retain known=0. No raw controls, future
events, labels, outcomes, split/group identifiers, review verdicts or future
eligibility enter the feature tensor. Admission must use the same causal
perception/selector pipeline, including history before the labeled anchor, and
record its digest. Retrospectively identified targets cannot be backfilled into
causal features. The API checks clocks/layout; it cannot prove a producer's
pixel provenance or inspection attestation.

Each `Example` names session, whole-session group, train/val split, continuous
segment, original media and review SHA-256, evidence reference, identity, history,
anchor, next 100 ms label interval, and optional causal previous-label and
comparable scripted baseline. Origin is `reviewed_human` or explicitly synthetic;
scripted origin and test/sealed examples reject. Unknown labels are `None` and
never become idle. Duplicate decisions, session/media split leakage and mixed
origin/patch/settings/perception are rejected. A fitting-set digest pins exact
examples, including review provenance, across training, save and evaluation.

Admission must supply the following inspected evidence before real consumption:

- **Engage:** native key/button evidence plus native video establishing an
  offensive action toward the fixed selected bot, with explicit approval that
  delegating to this controller is an acceptable coarse semantic projection.
  Button presence alone does not establish this. No mouse-to-stick conversion.
- **Idle:** known focused controls and inspected footage establishing genuine
  neutral waiting. Movement, swing, retreat, recovery, target ambiguity and
  unavailable controls are not automatically neutral negatives.
- **Unknown/negative controls:** inspect attack-looking failures, target mismatch,
  held-state uncertainty, focus/pause boundaries and mixed/unsupported actions
  together with valid positive and neutral examples. Mask unresolved semantics.
- **Timing/identity:** admission's reviewed original-media intervals, independent
  packet/PTS anchor and capture-alignment assumption/bound, binding/settings and
  patch evidence. One example's complete history/label horizon must stay inside
  one accepted continuous segment. Future evidence is label-only and retained
  through its actual latest endpoint in the admission purge boundary.

This lane does not create review attestations or an adapter by guessing these
facts. A handed-over admitted KBM dataset alone is insufficient if its offensive
versus neutral semantic projection and target correspondence remain unreviewed.
The label adapter remains a concrete admission/interface prerequisite.

Training does not require validation: an admitted single-session diagnostic
can fit and save. Both learned classes need positive training support; if no
reviewed neutral examples exist, report that exact missing contrast. Acceptance
and live reliance still need independent-session validation. `evaluate` reports
per-action confusion/recall, confidence coverage/refusals, unknown count,
per-group results, onset/continuation strata and majority/persistence/comparable
scripted baselines. Unsupported baseline rows stay absent, with explicit n.
No final-test unseal path exists here.

## Inspected synthetic evidence

2026-09-22, Windows CPU, PyTorch `2.14.0+cpu`, no shared environment install:

```powershell
uv run --no-sync pytest tests/test_range_policy.py -q
# 42 passed, 27 dependency skips
uv run --offline --no-project --with torch --with pytest python -m pytest tests/test_range_policy.py -q
# 69 passed; isolated cached uv runtime, 2.30 seconds
uv run --no-sync pytest tests/test_range_policy.py tests/test_brain.py tests/test_brain_replay.py tests/test_jev.py tests/test_jev_async.py tests/test_controller.py -q
# 184 passed, 27 dependency skips
```

Implementation SHA-256 after the independent-review fixes (pending re-review):

| File | SHA-256 |
| --- | --- |
| `policy/range_policy.py` | `890410cf789ec88cd605bbb7aa65dc176a16e228fcec5c974aa194d54fdf6adc` |
| `agent/learned_range.py` | `5c7e0d9a38224cd86ed34a8c1baf8e51d6e474b4b9fa6eb95e0f61bc70cc1cbc` |
| `tests/test_range_policy.py` | `afc78bb79726b97d0017f463f000ebe522280c4ad315c1b28e3c4342c049a5cf` |

The real synthetic fit uses eight train and four separate synthetic validation
examples, hidden size 8, 80 CPU epochs, one CPU thread, seed 0. It scores 4/4 vs
majority 2/4 on an intentionally trivial HP-coded fixture. Checkpoint reload
reproduces the complete report exactly and the loaded model yields `Engage`
through the real typed consumer. A neutral refusal cancels a running
`Controller` sequence and returns its actual neutral dictionary. This pure
controller test creates no pad. Malformed output/weights/shapes, changed hashes,
stale identity, future observations, split leakage, missing support, unknown
labels and synthetic deployment refusal are exercised. Synthetic fitting proves
software plumbing only; it supplies zero human-performance evidence.

The independent review found two P1 blockers in that initial candidate: the
gate could renew offensive execution despite detector loss or a history gap,
and source KBM settings were conflated with runtime pad compatibility. New
regressions reproduced five failing cases before the consumer repair. The
repaired cases return `Idle` and cancel an active real pure-controller melee
sequence without a model call. Controls preserve known-empty coasting and
valid-current-state retreat, including retreat during history warmup. The
complete history is checked even on gate returns, catching accumulated cadence
drift and future evidence. Runtime tests exercise missing/stale/mismatched
receipts, every runtime profile field, changed checkpoint bytes, copied KBM
settings, missing semantic review, and valid separate source/runtime identities.
Receipt metadata is fabricated test data only; no deployment approval exists.

Next prerequisites: independent read-only review arranged by lead; admission's
reviewed semantic candidate and adapter handoff; then a bounded Mac diagnostic
fit via `mac-remote`. Do not change the human-execution worktree or venv during
another active job. Root owns guarded loop integration and committing accepted
changes to main. No real run or Mac transfer has been performed by this lane.
