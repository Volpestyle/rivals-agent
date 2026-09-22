"""Versioned per-ability event learning, with no media IO or admission adapter.

Unknown grid rows are coverage, never invented negatives. Source visual evidence
and reviewed pad deployment remain separate authorities. Torch is loaded lazily.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import math

from .execution import canonical, require, torch_module
from .range_policy import (FEATURES, Snapshot, Spec as LegacySpec, RuntimeIdentity,
                           digest, finite, sha256, feature_row, fit_classifier,
                           make_model, save_portable, load_portable)

FORMAT = "rivals-range-skill-events-v1"
HEAD = "web_cluster_start"
OUTCOMES = ("no_new_start", "start")
SEMANTIC_REVISION = "web-cluster-onset-v1"
FEATURE_REVISION = "masked-state-grid-causal-v1"
SAMPLING = "full_grid_masked"


@dataclass(frozen=True)
class Spec(LegacySpec):
    def validate(self):
        super().validate()
        require(self.steps == 5 and self.period_s == .1 and self.tolerance_s == .025,
                "event v1 freezes five snapshots at 10 Hz with 25 ms tolerance")


@dataclass(frozen=True)
class SourceIdentity:
    """Visual source profile may explicitly contain UNKNOWN motor settings."""
    patch: str
    cooldown_regime: str
    source_profile_sha256: str
    perception_sha256: str
    selector_sha256: str
    semantic_revision: str = SEMANTIC_REVISION
    feature_revision: str = FEATURE_REVISION

    def validate(self):
        require(isinstance(self.patch, str) and self.patch.strip() and self.patch.lower() != "unknown",
                "known source patch required")
        require(self.cooldown_regime in ("normal", "off"), "known source resource regime required")
        require(all(sha256(v) for v in (self.source_profile_sha256, self.perception_sha256,
                                       self.selector_sha256)), "visual source/profile hashes required")
        require(self.semantic_revision == SEMANTIC_REVISION and self.feature_revision == FEATURE_REVISION,
                "incompatible source event semantics/features")


@dataclass(frozen=True)
class SkillRuntimeIdentity(RuntimeIdentity):
    selector_sha256: str = ""
    semantic_revision: str = SEMANTIC_REVISION
    feature_revision: str = FEATURE_REVISION

    def validate(self):
        super().validate()
        require(sha256(self.selector_sha256), "runtime selector hash required")
        require(self.semantic_revision == SEMANTIC_REVISION and self.feature_revision == FEATURE_REVISION,
                "incompatible runtime event semantics/features")


@dataclass(frozen=True)
class SkillDeploymentBinding:
    """External acceptance receipt; train/save cannot issue deployment approval."""
    checkpoint_sha256: str
    source_identity_sha256: str
    runtime: SkillRuntimeIdentity
    review_sha256: str

    def validate(self, *, checkpoint_sha256, source_identity, expected_runtime):
        require(type(source_identity) is SourceIdentity and type(expected_runtime) is SkillRuntimeIdentity
                and type(self.runtime) is SkillRuntimeIdentity, "explicit event source/runtime identities required")
        source_identity.validate()
        expected_runtime.validate()
        self.runtime.validate()
        require(all(sha256(v) for v in (self.checkpoint_sha256, self.source_identity_sha256, self.review_sha256)),
                "deployment receipt hashes required")
        require(self.checkpoint_sha256 == checkpoint_sha256, "deployment checkpoint binding mismatch")
        require(self.source_identity_sha256 == digest(asdict(source_identity)), "deployment source binding mismatch")
        require(self.runtime == expected_runtime, "deployment runtime profile mismatch")
        require((self.runtime.patch, self.runtime.cooldown_regime, self.runtime.selector_sha256) ==
                (source_identity.patch, source_identity.cooldown_regime, source_identity.selector_sha256),
                "source/runtime kit or fixed selector mismatch")
        require(self.runtime.runtime_settings_sha256 != source_identity.source_profile_sha256,
                "visual source profile is not runtime motor settings evidence")


def event_window(history, anchor_t, spec=Spec(), *, sampling="grid"):
    """Grid: causal at each scheduled tick. Live: actual acquisition anchors.

    No clocks are rewritten. Live intermediate samples can jitter either side of
    their nominal positions, but every measurement must be available by anchor.
    """
    spec.validate()
    require(sampling in ("grid", "live"), "unknown sampling contract")
    require(finite(anchor_t) and len(history) == spec.steps, "incomplete history")
    rows, previous = [], None
    for i, snapshot in enumerate(history):
        rows.append(feature_row(snapshot))
        t, available = snapshot.state.t, snapshot.available_t
        tick = anchor_t - (spec.steps - 1 - i) * spec.period_s
        require(t <= anchor_t and available <= anchor_t + 1e-9, "future observation")
        require(abs(t - tick) <= spec.tolerance_s + 1e-9, "stale or irregular history")
        if sampling == "grid":
            require(t <= tick + 1e-9 and available <= tick + 1e-9, "future grid observation")
        if previous is not None:
            require(t > previous, "repeated or backwards snapshot")
            if sampling == "live":
                require(abs(t - previous - spec.period_s) <= spec.tolerance_s + 1e-9,
                        "irregular live cadence")
        previous = t
    if sampling == "live":
        require(abs(history[-1].state.t - anchor_t) < 1e-9, "live anchor must be acquired frame")
    return rows


@dataclass(frozen=True)
class EventExample:
    """Admission supplies reviewed evidence; this class never infers a human label.

    One row per eligible grid tick in each declared continuous segment. An
    uninspected row has label_known=False, label=None, reason and history=().
    Its optional exposure/confirmation fields may remain None. Actual observed
    clocks, including a final decoded CTS earlier than anchor, stay untouched.
    """
    session: str
    group: str
    split: str
    continuous_id: str
    media_sha256: str
    review_sha256: str
    evidence: str
    source: SourceIdentity
    segment_start_t: float
    segment_end_t: float
    grid_origin_t: float
    grid_index: int
    history: tuple[Snapshot, ...]
    anchor_t: float
    exposure_start_t: float | None
    exposure_end_t: float | None
    confirmation_t: float | None
    label: str | None
    label_known: bool
    reason: str
    anchor_target_track: int | None
    target_agreed: bool
    event_id: str | None = None
    last_not_started_t: float | None = None
    first_started_t: float | None = None
    head: str = HEAD
    semantic_revision: str = SEMANTIC_REVISION
    origin: str = "reviewed_human"

    def grid_bounds(self, spec=Spec()):
        first = math.ceil((self.segment_start_t - self.grid_origin_t) / spec.period_s - 1e-8) + spec.steps - 1
        last = math.floor((self.segment_end_t - self.grid_origin_t) / spec.period_s + 1e-8) - 1
        return first, last

    def purge_footprint(self, spec=Spec()):
        start = min((s.state.t for s in self.history), default=self.anchor_t - (spec.steps - 1) * spec.period_s)
        end = max(self.anchor_t + spec.period_s, self.exposure_end_t or self.anchor_t,
                  self.confirmation_t or self.anchor_t, self.first_started_t or self.anchor_t)
        return start, end

    def validate(self, spec=Spec()):
        spec.validate()
        require(type(self.source) is SourceIdentity, "event SourceIdentity required")
        self.source.validate()
        require(self.split in ("train", "val"), "sealed/test rows refused")
        require(self.origin in ("reviewed_human", "synthetic"), "scripted labels are not human supervision")
        require(all(isinstance(v, str) and v.strip() for v in
                    (self.session, self.group, self.continuous_id, self.evidence, self.reason)),
                "coverage/evidence identity and reason required")
        require(sha256(self.media_sha256) and sha256(self.review_sha256), "media/review hashes required")
        require(self.head == HEAD and self.semantic_revision == SEMANTIC_REVISION, "incompatible event head/semantics")
        require(all(finite(v) for v in (self.segment_start_t, self.segment_end_t, self.grid_origin_t, self.anchor_t))
                and self.segment_end_t > self.segment_start_t, "invalid segment clocks")
        require(type(self.grid_index) is int and abs(self.anchor_t - self.grid_origin_t - self.grid_index * spec.period_s) < 1e-8,
                "anchor is not the declared grid coordinate")
        first, last = self.grid_bounds(spec)
        require(first <= self.grid_index <= last, "grid history/horizon outside segment")
        require(type(self.label_known) is bool and type(self.target_agreed) is bool, "explicit boolean masks required")
        require(self.label in OUTCOMES if self.label_known else self.label is None, "label/mask mismatch")
        require(self.anchor_target_track is None or type(self.anchor_target_track) is int,
                "invalid anchor track identity")
        clocks = (self.exposure_start_t, self.exposure_end_t, self.confirmation_t)
        require(all(v is None or finite(v) for v in clocks), "invalid exposure clocks")
        if any(v is not None for v in clocks):
            require(all(v is not None for v in clocks), "partial exposure clocks")
            require(self.segment_start_t <= self.exposure_start_t <= self.exposure_end_t <= self.confirmation_t <= self.segment_end_t,
                    "exposure/confirmation outside continuous segment")
        bracket = (self.event_id, self.last_not_started_t, self.first_started_t)
        if any(v is not None for v in bracket):
            require(isinstance(self.event_id, str) and self.event_id.strip()
                    and finite(self.last_not_started_t) and finite(self.first_started_t)
                    and self.segment_start_t <= self.last_not_started_t < self.first_started_t <= self.segment_end_t,
                    "event identity and positive onset bracket required")
            require(self.confirmation_t is not None and self.confirmation_t >= self.first_started_t,
                    "latest event confirmation required")
        rows = event_window(self.history, self.anchor_t, spec) if self.history else None
        if self.history:
            require(self.history[0].state.t >= self.segment_start_t, "actual history crosses segment boundary")
        if not self.label_known:
            return None
        require(rows is not None, "known row needs actual causal history")
        require(self.exposure_start_t is not None and self.exposure_start_t <= self.anchor_t + 1e-9
                and self.exposure_end_t >= self.anchor_t + spec.period_s - 1e-9,
                "known label needs full next-bin exposure")
        target = self.history[-1].target
        require(self.target_agreed and target is not None and type(target.track) is int
                and target.track == self.anchor_target_track
                and target.track not in self.history[-1].state.coasting,
                "known row needs reviewed causal anchor target correspondence")
        require(all(s.state.detections is not None for s in self.history), "known row has detector failure")
        if self.label == "start":
            require(self.event_id is not None and self.last_not_started_t >= self.anchor_t - 1e-9
                    and self.first_started_t <= self.anchor_t + spec.period_s + 1e-9,
                    "positive bracket must fit wholly in one forecast bin")
        else:
            require(self.event_id is None, "nononset cannot own an onset event")
        return rows


def cohort(examples, spec=Spec()):
    """Exact source identity for public cohort, training and checkpoint callers."""
    return _validate_cohort(examples, spec, evaluation=False)


def same_event_domain(a, b):
    """Structural evaluation compatibility only; never review or live approval."""
    fields = ("patch", "cooldown_regime", "perception_sha256", "selector_sha256",
              "semantic_revision", "feature_revision")
    return (type(a) is SourceIdentity and type(b) is SourceIdentity
            and all(getattr(a, name) == getattr(b, name) for name in fields))


def _validate_cohort(examples, spec, *, evaluation):
    """One placement/coverage/event validator; only evaluate permits distinct profiles."""
    require(bool(examples), "no coverage rows")
    source, origin = examples[0].source, examples[0].origin
    segments, placements, events, profiles = defaultdict(list), {}, {}, {}
    for e in examples:
        e.validate(spec)
        compatible = same_event_domain(e.source, source) if evaluation else e.source == source
        require(compatible and e.origin == origin, "mixed source identity or supervision origin")
        for kind, key in (("media", e.media_sha256), ("session", e.session)):
            require(profiles.setdefault((kind, key), e.source) == e.source,
                    f"inconsistent source identity within {kind}")
        for kind, key, placement in (("group", e.group, e.split), ("session", e.session, (e.group, e.split)),
                                      ("media", e.media_sha256, (e.session, e.group, e.split))):
            old = placements.setdefault((kind, key), placement)
            require(old == placement, "session/media/group split leakage")
        segments[(e.session, e.continuous_id)].append(e)
        if e.event_id is not None:
            identity = (e.continuous_id, e.last_not_started_t, e.first_started_t)
            key = (e.session, e.event_id)
            require(events.setdefault(key, identity) == identity, "event ID reused with different bracket")
    for rows in segments.values():
        first = rows[0]
        contract = (first.segment_start_t, first.segment_end_t, first.grid_origin_t, first.media_sha256)
        require(all((e.segment_start_t, e.segment_end_t, e.grid_origin_t, e.media_sha256) == contract for e in rows),
                "inconsistent continuous segment/grid")
        lo, hi = first.grid_bounds(spec)
        indices = [e.grid_index for e in rows]
        require(len(set(indices)) == len(indices), "duplicate grid row")
        require(set(indices) == set(range(lo, hi + 1)), "missing grid coverage; retain explicit unknown rows")
        positive_ids = [e.event_id for e in rows if e.label_known and e.label == "start"]
        require(len(positive_ids) == len(set(positive_ids)), "one event cannot supervise multiple positive bins")
        for e in rows:
            if e.event_id is None:
                continue
            for other in rows:
                overlaps = (other.anchor_t < e.first_started_t - 1e-9
                            and other.anchor_t + spec.period_s > e.last_not_started_t + 1e-9)
                if overlaps and other.label_known:
                    require(e.label_known and other.event_id == e.event_id and other.label == "start",
                            "uncertain/cross-bin event overlaps a known label")
    # Overlapping segments cannot hide confirmation leakage or duplicate exposure.
    by_session = defaultdict(list)
    for (session, _), rows in segments.items():
        by_session[session].append((rows[0].segment_start_t, rows[0].segment_end_t))
    for spans in by_session.values():
        ordered = sorted(spans)
        require(all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:])), "overlapping continuous segments")
    return source, origin


def evidence_digest(examples):
    return digest([asdict(e) for e in sorted(examples, key=lambda e: (e.session, e.continuous_id, e.grid_index))])


def coverage_report(examples):
    """Summarize a validated cohort; public fit/evaluation validate before counting."""
    known = [e for e in examples if e.label_known]
    return {"grid_rows": len(examples), "known_rows": len(known), "masked_rows": len(examples) - len(known),
            "masked_reasons": dict(Counter(e.reason for e in examples if not e.label_known)),
            "bin_support": [sum(e.label == name for e in known) for name in OUTCOMES],
            "unique_events": len({(e.session, e.event_id) for e in known if e.label == "start"}),
            "ammo_positive_visible_nononsets": sum(e.label == "no_new_start" and e.history[-1].state.webs is not None
                                                     and e.history[-1].state.webs > 0 for e in known),
            "complete_label_coverage": len(known) == len(examples), "sampling": SAMPLING}


class RangeSkillPolicy:
    def __init__(self, model, spec, identity, support, origin, data_sha256, training_report, device="cpu"):
        spec.validate()
        require(type(identity) is SourceIdentity, "event source identity required")
        identity.validate()
        require(len(support) == len(OUTCOMES) and all(type(n) is int and n > 0 for n in support),
                "onset and nononset training support required")
        require(origin in ("reviewed_human", "synthetic") and sha256(data_sha256), "invalid training provenance")
        require(training_report.get("bin_support") == list(support)
                and training_report.get("unique_events") == support[1]
                and training_report.get("sampling") == SAMPLING, "inconsistent training report")
        self.model, self.spec, self.identity = model.eval(), spec, identity
        self.support, self.origin, self.data_sha256 = tuple(support), origin, data_sha256
        self.training_report, self.device = training_report, device

    def probabilities(self, history, anchor_t, *, sampling="grid"):
        torch = torch_module()
        block = torch.tensor([event_window(history, anchor_t, self.spec, sampling=sampling)],
                             dtype=torch.float32, device=self.device)
        with torch.no_grad():
            result = self.model(block).softmax(-1)[0].cpu().tolist()
        require(len(result) == len(OUTCOMES) and all(finite(p) and 0 <= p <= 1 for p in result)
                and abs(sum(result) - 1) < 1e-5, "invalid event probabilities")
        return tuple(result)


def train(examples, *, spec=Spec(), epochs=20, batch_size=32, lr=.001, device="cpu", seed=0):
    source, origin = cohort(examples, spec)
    require(all(e.split == "train" for e in examples), "fit accepts train partition only")
    require(device in ("cpu", "mps"), "event v1 supports CPU/MPS only")
    known = [e for e in examples if e.label_known]
    report = coverage_report(examples)
    model = fit_classifier([e.validate(spec) for e in known], [OUTCOMES.index(e.label) for e in known], spec,
                           output_count=len(OUTCOMES), epochs=epochs, batch_size=batch_size, lr=lr, device=device, seed=seed)
    return RangeSkillPolicy(model, spec, source, report["bin_support"], origin, evidence_digest(examples), report, device)


def event_metrics(examples, predictions, spec=Spec()):
    """One request at the anchor predicts a start in its next 100 ms bin.

    One-to-one bracket matching, scoped to the same session/segment. Unknown
    bins are unscored. Timing is distance from request to bracket, not an
    invented precise human onset. Repeated requests count as false positives.
    """
    require(len(examples) == len(predictions), "prediction count mismatch")
    known = [(e, p) for e, p in zip(examples, predictions) if e.label_known]
    require(all(p in (*OUTCOMES, None) for _, p in known), "invalid prediction")
    truth = {(e.session, e.continuous_id, e.event_id): e for e, _ in known if e.label == "start"}
    matched, timing, fp = set(), [], 0
    for e, p in sorted(known, key=lambda pair: (pair[0].session, pair[0].continuous_id, pair[0].anchor_t)):
        if p != "start":
            continue
        eligible = [(key, target) for key, target in truth.items() if key not in matched
                    and key[:2] == (e.session, e.continuous_id)
                    and target.last_not_started_t >= e.anchor_t - 1e-9
                    and target.first_started_t <= e.anchor_t + spec.period_s + 1e-9]
        if eligible:
            key, target = min(eligible, key=lambda item: item[1].first_started_t)
            matched.add(key)
            timing.append(max(0., target.last_not_started_t - e.anchor_t))
        else:
            fp += 1
    tp, fn = len(matched), len(truth) - len(matched)
    scored = [(e, p) for e, p in known if p is not None]
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "mean_request_to_bracket_s": sum(timing) / len(timing) if timing else None,
            "confusion": [[sum(e.label == a and p == b for e, p in scored) for b in OUTCOMES] for a in OUTCOMES],
            "refusals": sum(p is None for _, p in known), "scored_bins": len(scored),
            "masked_bins": len(examples) - len(known)}


def evaluate(policy, train_examples, validation, *, complete_evaluation=False):
    require(train_examples and validation and all(e.split == "train" for e in train_examples)
            and all(e.split == "val" for e in validation), "independent train/val required")
    source, origin = cohort(train_examples, policy.spec)
    require(source == policy.identity and origin == policy.origin, "evaluation identity mismatch")
    _validate_cohort([*train_examples, *validation], policy.spec, evaluation=True)
    require(evidence_digest(train_examples) == policy.data_sha256, "training evidence mismatch")
    require(tuple(coverage_report(train_examples)["bin_support"]) == tuple(policy.support), "training support mismatch")
    coverage = coverage_report(validation)
    require(type(complete_evaluation) is bool, "explicit evaluation coverage declaration required")
    require(not complete_evaluation or coverage["complete_label_coverage"], "full evaluation requires complete observed coverage")
    probabilities = [policy.probabilities(e.history, e.anchor_t) if e.label_known else None for e in validation]
    prediction = [OUTCOMES[max(range(len(OUTCOMES)), key=p.__getitem__)] if p else None for p in probabilities]
    confidence_filtered = [name if p and max(p) >= policy.spec.confidence else None
                           for name, p in zip(prediction, probabilities)]
    train_rate = policy.support[1] / sum(policy.support)
    # Deterministic expected request schedule with the training event rate, not labels from evaluation.
    rate_prediction = ["start" if math.floor((e.grid_index + 1) * train_rate) > math.floor(e.grid_index * train_rate)
                       else "no_new_start" for e in validation]
    recent = []
    for e in validation:
        prior = [p for p in validation if p.session == e.session and p.continuous_id == e.continuous_id
                 and p.label_known and p.label == "start" and p.confirmation_t <= e.anchor_t
                 and e.anchor_t - p.first_started_t <= 1.]
        recent.append("start" if prior else "no_new_start")
    resource = [None if not e.history or e.history[-1].state.webs is None else
                ("start" if e.history[-1].state.webs > 0 else "no_new_start") for e in validation]
    candidates = {"model": prediction, "confidence_filtered": confidence_filtered,
                  "never_start": ["no_new_start"] * len(validation),
                  "always_start": ["start"] * len(validation), "training_rate": rate_prediction,
                  "recent_confirmed_event": recent, "ammo_positive": resource}
    return {"scope": "complete_independent_evaluation" if complete_evaluation else "partial_observed_diagnostic",
            "training_source": asdict(source),
            "validation_sources": [asdict(identity) for identity in
                                   sorted({e.source for e in validation}, key=lambda identity: digest(asdict(identity)))],
            "domain_compatibility": "structural_only_not_review_admission_or_live_approval",
            "prediction_boundary": "offline_model_proposals",
            "confidence_filter": {"threshold": policy.spec.confidence, "consumer_acceptance_measured": False,
                                  "executor_acceptance_measured": False},
            "offline_assumptions": [
                "Each known row supplies reviewed causal selector outputs; no continuous live gate replay is performed.",
                "Grid observations precede their scheduled ticks; live sampling uses actual acquisition anchors.",
                "Confidence filtering does not simulate runtime history resets, retreat, current-target gates, or controller acceptance.",
                "Aim, resources, pulse ownership, expiry, execution and delivery require separate live/controller traces."],
            "coverage": coverage, "training_rate": train_rate, "probabilities": probabilities,
            "metrics": {name: event_metrics(validation, values, policy.spec) for name, values in candidates.items()},
            "ammo_positive_visible_nononsets": {
                name: event_metrics([e for e in validation if e.label_known and e.label == "no_new_start"
                                     and e.history[-1].state.webs is not None and e.history[-1].state.webs > 0],
                                    [p for e, p in zip(validation, values) if e.label_known and e.label == "no_new_start"
                                     and e.history[-1].state.webs is not None and e.history[-1].state.webs > 0], policy.spec)
                for name, values in candidates.items()}}


def save_checkpoint(path, policy, examples, *, code_sha256, training_config):
    source, origin = cohort(examples, policy.spec)
    require(source == policy.identity and origin == policy.origin and all(e.split == "train" for e in examples)
            and evidence_digest(examples) == policy.data_sha256, "checkpoint training provenance mismatch")
    require(sha256(code_sha256), "code hash required")
    canonical(training_config)
    return save_portable(path, {"format": FORMAT, "head": HEAD, "outcomes": list(OUTCOMES),
        "features": list(FEATURES), "spec": asdict(policy.spec), "source": asdict(source),
        "semantic_revision": SEMANTIC_REVISION, "feature_revision": FEATURE_REVISION,
        "origin": origin, "support": list(policy.support), "data_sha256": policy.data_sha256,
        "training_report": policy.training_report, "code_sha256": code_sha256, "training_config": training_config,
        "reviews": sorted({e.review_sha256 for e in examples}), "groups": sorted({e.group for e in examples}),
        "weights": {k: v.detach().cpu() for k, v in policy.model.state_dict().items()}})


def load_checkpoint(path, *, expected_sha256, expected_identity, expected_runtime=None,
                    deployment_binding=None, device="cpu", offline=False):
    require(type(expected_identity) is SourceIdentity, "explicit event SourceIdentity required")
    expected_identity.validate()
    require(device in ("cpu", "mps"), "event v1 supports CPU/MPS only")
    payload = load_portable(path, expected_sha256)
    require(isinstance(payload, dict) and payload.get("format") == FORMAT and payload.get("head") == HEAD,
            "incompatible event checkpoint")
    require(payload.get("outcomes") == list(OUTCOMES) and payload.get("features") == list(FEATURES)
            and payload.get("semantic_revision") == SEMANTIC_REVISION and payload.get("feature_revision") == FEATURE_REVISION,
            "incompatible event vocabulary/features/revision")
    identity, spec = SourceIdentity(**payload["source"]), Spec(**payload["spec"])
    spec.validate()
    require(identity == expected_identity, "source identity mismatch")
    require(payload.get("origin") in (("synthetic", "reviewed_human") if offline else ("reviewed_human",)),
            "synthetic checkpoint is offline only")
    if not offline or expected_runtime is not None or deployment_binding is not None:
        require(type(expected_runtime) is SkillRuntimeIdentity and type(deployment_binding) is SkillDeploymentBinding,
                "live load requires event runtime and reviewed deployment binding")
        deployment_binding.validate(checkpoint_sha256=expected_sha256, source_identity=identity, expected_runtime=expected_runtime)
    require(sha256(payload.get("data_sha256")) and sha256(payload.get("code_sha256")) and payload.get("reviews")
            and all(sha256(v) for v in payload["reviews"]) and payload.get("groups"), "missing event model provenance")
    model = make_model(spec, output_count=len(OUTCOMES))
    model.load_state_dict(payload["weights"], strict=True)
    torch = torch_module()
    require(all(bool(torch.isfinite(v).all()) for v in model.state_dict().values()), "nonfinite model weights")
    return RangeSkillPolicy(model.to(device), spec, identity, payload["support"], payload["origin"],
                            payload["data_sha256"], payload["training_report"], device)
