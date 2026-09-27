"""Causal, portable range-option candidate. No corpus discovery or input devices.

The only learned choice is neutral versus delegation to the existing Engage
controller. Supervision is an independently reviewed semantic projection of
human play, NOT a conversion of KBM controls or scripted-brain labels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

from agent.state import State, Detection
from .execution import canonical, fingerprint, require, torch_module

FORMAT = "rivals-range-options-v1"
ACTIONS = ("idle", "engage")
FIELDS = ("hp_fraction", "webs", "pull_ready", "uppercut_ready", "swing_ready",
          "on_target", "detector", "target", "target_x", "target_y",
          "target_height", "target_distance", "target_tagged")
FEATURES = tuple(part for field in FIELDS for part in (field, field + "_known"))


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class Identity:
    """Source human recording/perception provenance, never pad configuration."""
    patch: str
    cooldown_regime: str
    settings_sha256: str
    perception_sha256: str

    def validate(self):
        require(bool(self.patch.strip()) and self.patch.lower() != "unknown", "known patch required")
        require(self.cooldown_regime in ("normal", "off"), "unknown cooldown regime")
        require(sha256(self.settings_sha256) and sha256(self.perception_sha256), "identity hashes required")


@dataclass(frozen=True)
class RuntimeIdentity:
    """Independently measured pad profile plus the reviewed semantic mapping.

    runtime_settings_sha256 hashes a domain-tagged virtual-pad settings manifest,
    not the human KBM settings. controller_code_sha256 covers the integrated
    decision/target-selector/controller implementation, not just model weights.
    """
    patch: str
    cooldown_regime: str
    runtime_settings_sha256: str
    calibration_sha256: str
    controller_code_sha256: str
    perception_sha256: str
    semantic_review_sha256: str
    input_domain: str = "virtual_pad"

    def validate(self):
        require(isinstance(self.patch, str) and bool(self.patch.strip()) and self.patch.lower() != "unknown",
                "known runtime patch required")
        require(self.cooldown_regime in ("normal", "off"), "unknown runtime cooldown regime")
        require(self.input_domain == "virtual_pad", "runtime must use the accepted virtual_pad domain")
        require(all(sha256(value) for value in (self.runtime_settings_sha256, self.calibration_sha256,
                    self.controller_code_sha256, self.perception_sha256, self.semantic_review_sha256)),
                "runtime settings/calibration/code/perception/semantic review hashes required")


@dataclass(frozen=True)
class DeploymentBinding:
    """External reviewed receipt binds immutable checkpoint bytes to one runtime.

    Issued by the review/acceptance owner after the source-to-pad semantic review
    and validation gates, never by train/save. Hashes pin evidence, not proof
    that an inspection actually happened; the caller must supply the accepted
    receipt and independently measured expected runtime, not fabricate either.
    """
    checkpoint_sha256: str
    source_identity_sha256: str
    runtime: RuntimeIdentity
    review_sha256: str

    def validate(self, *, checkpoint_sha256, source_identity, expected_runtime):
        require(type(expected_runtime) is RuntimeIdentity and type(self.runtime) is RuntimeIdentity,
                "explicit RuntimeIdentity required")
        expected_runtime.validate()
        self.runtime.validate()
        require(all(sha256(value) for value in
                    (self.checkpoint_sha256, self.source_identity_sha256, self.review_sha256)),
                "reviewed deployment binding hashes required")
        require(self.checkpoint_sha256 == checkpoint_sha256, "deployment checkpoint binding mismatch")
        require(self.source_identity_sha256 == digest(asdict(source_identity)), "deployment source binding mismatch")
        require(self.runtime == expected_runtime, "deployment runtime profile mismatch")
        require((self.runtime.patch, self.runtime.cooldown_regime) ==
                (source_identity.patch, source_identity.cooldown_regime), "source/runtime kit mismatch")
        require(self.runtime.runtime_settings_sha256 != source_identity.settings_sha256,
                "source KBM settings are not runtime pad evidence")


@dataclass(frozen=True)
class Spec:
    steps: int = 5
    period_s: float = .1
    tolerance_s: float = .025
    hidden: int = 32
    confidence: float = .7

    def validate(self):
        require(type(self.steps) is int and 2 <= self.steps <= 32, "invalid history steps")
        require(finite(self.period_s) and .05 <= self.period_s <= .2, "invalid decision period")
        require(finite(self.tolerance_s) and 0 <= self.tolerance_s < self.period_s / 2, "invalid time tolerance")
        require(type(self.hidden) is int and 1 <= self.hidden <= 256, "invalid hidden width")
        require(finite(self.confidence) and .5 < self.confidence <= 1, "invalid confidence threshold")


@dataclass(frozen=True)
class Snapshot:
    state: State
    target: Detection | None
    available_t: float  # when the pixel-derived measurement became available


def feature_row(snapshot):
    """Same masked, fixed physical scaling offline and live; no fitted features."""
    state, target = snapshot.state, snapshot.target
    require(finite(state.t) and finite(snapshot.available_t) and snapshot.available_t >= state.t,
            "invalid observation clock")
    require(len(state.frame) == 2 and all(type(v) is int and v > 0 for v in state.frame), "invalid frame")
    require(target is None or target in (state.detections or ()), "target must be observed in this frame")
    for det in state.detections or ():
        require(len(det.bbox) == 4 and all(finite(v) for v in det.bbox), "invalid bbox")
        x1, y1, x2, y2 = det.bbox
        require(0 <= x1 < x2 <= state.frame[0] and 0 <= y1 < y2 <= state.frame[1], "bbox outside frame")
        require(finite(det.conf) and 0 <= det.conf <= 1, "invalid detection confidence")
        require(det.distance is None or (finite(det.distance) and det.distance > 0), "invalid distance")
        require(det.tagged is None or type(det.tagged) is bool, "invalid tag")
    require(state.hp is None or (finite(state.hp) and state.hp >= 0), "invalid hp")
    require(state.max_hp is None or (finite(state.max_hp) and state.max_hp > 0), "invalid max hp")
    require(state.webs is None or (type(state.webs) is int and 0 <= state.webs <= 5), "invalid webs")
    require(state.on_target is None or type(state.on_target) is bool, "invalid crosshair")
    values = [state.hp / state.max_hp if state.hp is not None and state.max_hp is not None else None,
              state.webs / 5 if state.webs is not None else None]
    for name in ("pull", "uppercut", "swing"):
        ability = state.abilities.get(name)
        ready = ability.ready if ability else None
        require(ready is None or type(ready) is bool, "invalid ability readiness")
        values.append(ready)
    values.extend((state.on_target, state.detections is not None,
                   target is not None if state.detections is not None else None))
    values.extend((target.center[0] / state.frame[0], target.center[1] / state.frame[1],
                   target.height / state.frame[1],
                   target.distance / 40 if target.distance is not None else None, target.tagged)
                  if target is not None else (None,) * 5)
    return tuple(x for value in values for x in ((float(value), 1.) if value is not None else (0., 0.)))


def window(history, anchor_t, spec):
    spec.validate()
    require(finite(anchor_t) and len(history) == spec.steps, "incomplete history")
    rows = []
    for i, snapshot in enumerate(history):
        expected = anchor_t - (spec.steps - i - 1) * spec.period_s
        require(snapshot.state.t <= anchor_t and snapshot.available_t <= anchor_t, "future observation")
        require(abs(snapshot.state.t - expected) <= spec.tolerance_s + 1e-9, "stale or irregular history")
        rows.append(feature_row(snapshot))
    require(abs(history[-1].state.t - anchor_t) < 1e-9, "anchor must be the processed frame")
    return rows


@dataclass(frozen=True)
class Example:
    """Already admitted semantic evidence, provided in memory by admission's adapter.

    label=None is unknown, never idle. The receipt names native input/video
    evidence and a reviewed target match. It is not an automatic admission gate.
    One continuous_id cannot cross a focus/pause/gap or suitability boundary.
    """
    session: str
    group: str
    split: str
    continuous_id: str
    media_sha256: str
    review_sha256: str
    evidence: str
    identity: Identity
    history: tuple[Snapshot, ...]
    anchor_t: float
    label_end_t: float
    label: str | None
    previous_label: str | None
    previous_known_t: float | None
    scripted_label: str | None
    origin: str = "reviewed_human"

    def validate(self, spec):
        require(self.split in ("train", "val"), "sealed/test examples refused")
        require(self.origin in ("reviewed_human", "synthetic"), "scripted labels are not human supervision")
        require(all(isinstance(v, str) and v.strip() for v in
                    (self.session, self.group, self.continuous_id, self.evidence)), "evidence identity required")
        require(sha256(self.media_sha256) and sha256(self.review_sha256), "source/review hashes required")
        self.identity.validate()
        require(self.label in (*ACTIONS, None) and self.previous_label in (*ACTIONS, None)
                and self.scripted_label in (*ACTIONS, None), "unknown action vocabulary")
        require(finite(self.label_end_t) and abs(self.label_end_t - self.anchor_t - spec.period_s) < 1e-8,
                "label must cover the next decision interval")
        if self.previous_label is not None:
            require(finite(self.previous_known_t) and self.previous_known_t <= self.anchor_t,
                    "future persistence baseline")
        rows = window(self.history, self.anchor_t, spec)
        if self.label == "engage":
            require(self.history[-1].target is not None, "engage needs a reviewed visible target match")
        return rows


def cohort(examples, spec):
    require(bool(examples), "no examples")
    identity, origin = examples[0].identity, examples[0].origin
    seen, groups, sessions, media = set(), {}, {}, {}
    for example in examples:
        example.validate(spec)
        require(example.identity == identity and example.origin == origin, "mixed identity or supervision origin")
        key = example.session, example.anchor_t
        require(key not in seen, "duplicate decision")
        seen.add(key)
        for mapping, item, placement in ((groups, example.group, example.split),
                                         (sessions, example.session, (example.group, example.split)),
                                         (media, example.media_sha256, (example.group, example.split))):
            require(item not in mapping or mapping[item] == placement, "session/media split leakage")
            mapping[item] = placement
    return identity, origin


def make_model(spec, *, feature_count=len(FEATURES), output_count=len(ACTIONS)):
    spec.validate()
    torch = torch_module()

    class RangeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.temporal = torch.nn.GRU(feature_count, spec.hidden, batch_first=True)
            self.head = torch.nn.Linear(spec.hidden, output_count)

        def forward(self, x):
            _, hidden = self.temporal(x)
            return self.head(hidden[-1])

    return RangeModel()


def fit_classifier(rows, labels, spec, *, output_count, epochs, batch_size, lr, device, seed):
    """Shared numeric fit only; callers own vocabulary, evidence and masks."""
    require(type(epochs) is int and 1 <= epochs <= 10000 and type(batch_size) is int and batch_size > 0
            and finite(lr) and lr > 0, "invalid fit configuration")
    require(rows and len(rows) == len(labels), "empty or mismatched fit tensors")
    support = [labels.count(i) for i in range(output_count)]
    require(all(support) and sum(support) == len(labels), "every output needs training support")
    torch = torch_module()
    torch.manual_seed(seed)
    model = make_model(spec, feature_count=len(rows[0][0]), output_count=output_count).to(device)
    x = torch.tensor(rows, dtype=torch.float32, device=device)
    y = torch.tensor(labels, dtype=torch.long, device=device)
    weights = torch.tensor([len(labels) / (output_count * n) for n in support], dtype=torch.float32, device=device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    for _ in range(epochs):
        model.train()
        order = torch.randperm(len(labels)).tolist()
        for start in range(0, len(order), batch_size):
            index = order[start:start + batch_size]
            optimizer.zero_grad()
            loss = torch.nn.functional.cross_entropy(model(x[index]), y[index], weight=weights)
            require(bool(torch.isfinite(loss)), "nonfinite training loss")
            loss.backward()
            optimizer.step()
    return model


def save_portable(path, payload):
    """Exclusive artifact creation; caller supplies its versioned metadata."""
    with Path(path).open("xb") as stream:
        torch_module().save(payload, stream)
    return fingerprint(path)


def load_portable(path, expected_sha256):
    require(sha256(expected_sha256) and fingerprint(path) == expected_sha256, "checkpoint digest mismatch")
    return torch_module().load(path, map_location="cpu", weights_only=True)


class RangePolicy:
    def __init__(self, model, spec, identity, support, origin, data_sha256, device="cpu"):
        spec.validate()
        identity.validate()
        require(len(support) == len(ACTIONS) and all(type(n) is int and n > 0 for n in support),
                "both actions need training support")
        require(origin in ("synthetic", "reviewed_human") and sha256(data_sha256), "invalid training provenance")
        self.model, self.spec, self.identity = model.eval(), spec, identity
        self.support, self.origin, self.device = tuple(support), origin, device
        self.data_sha256 = data_sha256

    def probabilities(self, history, anchor_t):
        torch = torch_module()
        block = torch.tensor([window(history, anchor_t, self.spec)], dtype=torch.float32, device=self.device)
        with torch.no_grad():
            probs = self.model(block).softmax(-1)[0].cpu().tolist()
        require(len(probs) == len(ACTIONS) and all(finite(p) and 0 <= p <= 1 for p in probs), "invalid model output")
        return tuple(probs)


def train(examples, *, spec=Spec(), epochs=20, batch_size=32, lr=.001, device="cpu", seed=0):
    """Explicit in-memory candidate; train partition only, no media or registry IO."""
    identity, origin = cohort(examples, spec)
    require(all(e.split == "train" for e in examples), "training requires train only")
    require(type(epochs) is int and 1 <= epochs <= 10000 and type(batch_size) is int and batch_size > 0
            and finite(lr) and lr > 0, "invalid fit configuration")
    known = [e for e in examples if e.label is not None]
    support = [sum(e.label == action for e in known) for action in ACTIONS]
    require(all(support), "both actions need training support")
    model = fit_classifier([e.validate(spec) for e in known], [ACTIONS.index(e.label) for e in known],
                           spec, output_count=len(ACTIONS), epochs=epochs, batch_size=batch_size,
                           lr=lr, device=device, seed=seed)
    return RangePolicy(model, spec, identity, support, origin, evidence_digest(examples), device)


def score(truth, predicted):
    pairs = [(t, p) for t, p in zip(truth, predicted) if t is not None and p is not None]
    confusion = [[sum(t == a and p == b for t, p in pairs) for b in ACTIONS] for a in ACTIONS]
    support = [sum(row) for row in confusion]
    recall = [confusion[i][i] / n if n else None for i, n in enumerate(support)]
    return {"n": len(pairs), "support": support, "confusion": confusion, "recall": recall,
            "accuracy": sum(t == p for t, p in pairs) / len(pairs) if pairs else None,
            "balanced_accuracy": sum(recall) / len(recall) if all(n is not None for n in recall) else None}


def evaluate(policy, train_examples, validation):
    """Reject split leakage before inference; missing baseline labels stay missing."""
    identity, origin = cohort([*train_examples, *validation], policy.spec)
    require(identity == policy.identity and origin == policy.origin, "evaluation identity mismatch")
    require(train_examples and validation and all(e.split == "train" for e in train_examples)
            and all(e.split == "val" for e in validation), "independent train/val required")
    support = [sum(e.label == a for e in train_examples) for a in ACTIONS]
    require(tuple(support) == policy.support, "training support mismatch")
    require(evidence_digest(train_examples) == policy.data_sha256, "training evidence mismatch")
    majority = ACTIONS[max(range(len(ACTIONS)), key=lambda i: support[i])]
    truth = [e.label for e in validation]
    probabilities = [policy.probabilities(e.history, e.anchor_t) for e in validation]
    prediction = [ACTIONS[max(range(len(ACTIONS)), key=lambda i: p[i])] for p in probabilities]
    accepted = [name if max(p) >= policy.spec.confidence else None for name, p in zip(prediction, probabilities)]
    return {"model": score(truth, prediction), "accepted": score(truth, accepted),
            "majority": score(truth, [majority] * len(truth)),
            "persistence": score(truth, [e.previous_label for e in validation]),
            "scripted_comparable": score(truth, [e.scripted_label for e in validation]),
            "unknown_labels": sum(t is None for t in truth),
            "refusals": sum(a is None for a in accepted), "probabilities": probabilities,
            "onset": score([e.label for e in validation if e.previous_label == "idle"],
                           [p for e, p in zip(validation, prediction) if e.previous_label == "idle"]),
            "continuation": score([e.label for e in validation if e.previous_label == "engage"],
                                  [p for e, p in zip(validation, prediction) if e.previous_label == "engage"]),
            "by_group": {group: score([e.label for e in validation if e.group == group],
                                      [p for e, p in zip(validation, prediction) if e.group == group])
                         for group in sorted({e.group for e in validation})}}


def evidence_digest(examples):
    return digest([asdict(e) for e in examples])


def save_checkpoint(path, policy, examples, *, code_sha256, training_config):
    identity, origin = cohort(examples, policy.spec)
    require(identity == policy.identity and origin == policy.origin and all(e.split == "train" for e in examples),
            "checkpoint training provenance mismatch")
    require(sha256(code_sha256), "code hash required")
    require(evidence_digest(examples) == policy.data_sha256, "training evidence mismatch")
    canonical(training_config)
    payload = {"format": FORMAT, "actions": list(ACTIONS), "features": list(FEATURES),
               "spec": asdict(policy.spec), "identity": asdict(identity), "origin": origin,
               "support": list(policy.support), "data_sha256": evidence_digest(examples),
               "code_sha256": code_sha256, "training_config": training_config,
               "reviews": sorted({e.review_sha256 for e in examples}),
               "groups": sorted({e.group for e in examples}),
               "weights": {k: v.detach().cpu() for k, v in policy.model.state_dict().items()}}
    return save_portable(path, payload)


def load_checkpoint(path, *, expected_sha256, expected_identity, expected_runtime=None,
                    deployment_binding=None, device="cpu", offline=False):
    """Pin the reviewed artifact externally; weights_only prevents pickle execution.

    Non-offline loading requires an external reviewed deployment binding and
    independently pinned runtime profile. Train/save never grant live approval.
    """
    expected_identity.validate()
    torch = torch_module()
    payload = load_portable(path, expected_sha256)
    require(isinstance(payload, dict) and payload.get("format") == FORMAT, "incompatible range checkpoint")
    require(payload.get("actions") == list(ACTIONS) and payload.get("features") == list(FEATURES),
            "incompatible vocabulary/features")
    identity, spec = Identity(**payload["identity"]), Spec(**payload["spec"])
    spec.validate()
    require(identity == expected_identity, "stale patch/settings/perception identity")
    require(payload.get("origin") in (("synthetic", "reviewed_human") if offline else ("reviewed_human",)),
            "synthetic checkpoint is offline only")
    if not offline or expected_runtime is not None or deployment_binding is not None:
        require(type(deployment_binding) is DeploymentBinding and type(expected_runtime) is RuntimeIdentity,
                "live load requires expected_runtime and reviewed deployment_binding")
        deployment_binding.validate(checkpoint_sha256=expected_sha256, source_identity=identity,
                                    expected_runtime=expected_runtime)
    require(sha256(payload.get("code_sha256")) and sha256(payload.get("data_sha256"))
            and payload.get("reviews") and all(sha256(r) for r in payload["reviews"])
            and payload.get("groups"), "missing model provenance")
    model = make_model(spec)
    model.load_state_dict(payload["weights"], strict=True)
    require(all(bool(torch.isfinite(v).all()) for v in model.state_dict().values()), "nonfinite model weights")
    model.to(device)
    return RangePolicy(model, spec, identity, payload["support"], payload["origin"], payload["data_sha256"], device)
