"""Synthetic contract and bounded CPU checks. No corpus, capture or input devices."""
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from agent.brain import Memory
from agent import brain as scripted_brain
from agent.human_demos import DemoError
from agent.intents import Combo, Disengage, Engage, Idle, RangeSkill
from agent.learned_range_skill import LearnedRangeSkillBrain
from agent.state import Detection, State
from policy import range_policy as legacy
from policy.range_skill_policy import (FEATURE_REVISION, FORMAT, HEAD, OUTCOMES, SEMANTIC_REVISION,
    EventExample, SkillDeploymentBinding, SkillRuntimeIdentity, SourceIdentity, Snapshot, Spec,
    cohort, coverage_report, digest, evaluate, event_metrics, event_window, evidence_digest,
    load_checkpoint, save_checkpoint, train, same_event_domain, RangeSkillPolicy,
    REQUEST_FORMAT, REQUEST_HEAD, REQUEST_SEMANTIC_REVISION, RequestExample)

SOURCE = SourceIdentity("synthetic-patch", "normal", "a" * 64, "b" * 64, "c" * 64)
RUNTIME = SkillRuntimeIdentity("synthetic-patch", "normal", "1" * 64, "2" * 64, "3" * 64,
                               "4" * 64, "5" * 64, selector_sha256="c" * 64)
TARGET = Detection("enemy", (440, 200, 560, 390), .9, distance=10, track=1)
SPEC = Spec(hidden=4)


def state(t, *, detections=(TARGET,), webs=3, hp=240):
    return State(t, (1000, 600), hp=hp, max_hp=250, webs=webs, on_target=True,
                 detections=list(detections) if detections is not None else None)


def example(index=4, label="start", *, split="train"):
    anchor = index * .1
    history = tuple(Snapshot(state((index - 4 + i) * .1 - .01), TARGET, (index - 4 + i) * .1 - .008)
                    for i in range(5)) if label is not None else ()
    return EventExample(session=split, group=split, split=split, continuous_id="continuous-1",
        media_sha256=("d" if split == "train" else "e") * 64, review_sha256="f" * 64,
        evidence="synthetic fixture only", source=SOURCE, segment_start_t=-.025, segment_end_t=.9,
        grid_origin_t=0., grid_index=index, history=history, anchor_t=anchor,
        exposure_start_t=anchor if label else None, exposure_end_t=anchor + .1 if label else None,
        confirmation_t=anchor + .11 if label else None, label=label, label_known=label is not None,
        reason="synthetic_observed" if label else "uninspected", anchor_target_track=1 if label else None,
        target_agreed=label is not None, event_id="cast-1" if label == "start" else None,
        last_not_started_t=anchor + .02 if label == "start" else None,
        first_started_t=anchor + .05 if label == "start" else None, origin="synthetic")


def packet(split="train"):
    return [example(4, "start", split=split), example(5, "no_new_start", split=split),
            *(example(i, None, split=split) for i in range(6, 9))]


def evaluation_fixture():
    """Fixed synthetic scorer, not a trained model or human supervision."""
    rows = packet()
    validation_source = replace(SOURCE, source_profile_sha256="7" * 64)
    validation = [replace(e, source=validation_source) for e in packet("val")]
    calls = []

    def probabilities(history, anchor_t):
        event_window(history, anchor_t, SPEC)
        calls.append(anchor_t)
        return (.01, .99) if anchor_t < .45 else (.99, .01)

    policy = SimpleNamespace(spec=SPEC, identity=SOURCE, origin="synthetic", support=(1, 1),
                             data_sha256=evidence_digest(rows), probabilities=probabilities)
    return policy, rows, validation, calls


def test_evaluation_preserves_distinct_independent_source_profiles():
    policy, rows, validation, calls = evaluation_fixture()
    before = evidence_digest(validation)
    cohort(rows)
    cohort(validation)
    report = evaluate(policy, rows, validation)
    assert len(calls) == 2
    assert report["metrics"]["confidence_filtered"]["true_positive"] == 1
    assert report["metrics"]["confidence_filtered"]["false_positive"] == 0
    assert report["training_source"] == asdict(SOURCE)
    assert report["validation_sources"] == [asdict(validation[0].source)]
    assert report["training_source"]["source_profile_sha256"] != report["validation_sources"][0]["source_profile_sha256"]
    assert report["domain_compatibility"] == "structural_only_not_review_admission_or_live_approval"
    assert evidence_digest(validation) == before


@pytest.mark.parametrize("field,value", [
    ("patch", "other-patch"), ("cooldown_regime", "off"),
    ("perception_sha256", "8" * 64), ("selector_sha256", "8" * 64),
    ("semantic_revision", "other-semantics"), ("feature_revision", "other-features"),
])
def test_evaluation_rejects_each_domain_difference_before_inference(field, value):
    policy, rows, validation, calls = evaluation_fixture()
    different = replace(validation[0].source, **{field: value})
    assert not same_event_domain(SOURCE, different)
    with pytest.raises(DemoError):
        evaluate(policy, rows, [replace(e, source=different) for e in validation])
    assert not calls


@pytest.mark.parametrize("mismatch", ["validation_origin", "policy_origin", "policy_identity", "evidence", "support"])
def test_evaluation_rejects_provenance_or_support_mismatch_before_inference(mismatch):
    policy, rows, validation, calls = evaluation_fixture()
    if mismatch == "validation_origin":
        validation = [replace(e, origin="reviewed_human") for e in validation]
    elif mismatch == "policy_origin":
        policy.origin = "reviewed_human"
    elif mismatch == "policy_identity":
        policy.identity = validation[0].source  # compatible domain is insufficient for training provenance
    elif mismatch == "evidence":
        policy.data_sha256 = "8" * 64
    else:
        policy.support = (2, 2)
    with pytest.raises(DemoError):
        evaluate(policy, rows, validation)
    assert not calls


@pytest.mark.parametrize("key,value", [("group", "train"), ("session", "train"), ("media_sha256", "d" * 64)])
def test_evaluation_rejects_joint_split_leakage_before_inference(key, value):
    policy, rows, validation, calls = evaluation_fixture()
    # Same-profile control isolates the unchanged placement rule.
    validation = [replace(e, source=SOURCE, **{key: value}) for e in validation]
    with pytest.raises(DemoError, match="split leakage"):
        evaluate(policy, rows, validation)
    assert not calls


def test_evaluation_rejects_same_source_session_alias_before_inference():
    policy, rows, validation, calls = evaluation_fixture()
    alias = [replace(e, session="val-alias") for e in validation]
    with pytest.raises(DemoError, match="split leakage"):
        evaluate(policy, rows, [*validation, *alias])
    assert not calls


@pytest.mark.parametrize("kind", ["media", "session"])
def test_evaluation_requires_full_profile_consistency_within_media_and_session(kind):
    policy, rows, validation, calls = evaluation_fixture()
    different = replace(validation[1].source, source_profile_sha256="6" * 64)
    validation[1] = replace(validation[1], source=different,
                            media_sha256="8" * 64 if kind == "session" else validation[1].media_sha256)
    with pytest.raises(DemoError, match=f"inconsistent source identity within {kind}"):
        evaluate(policy, rows, validation)
    assert not calls


@pytest.mark.parametrize("failure", ["missing_grid", "duplicate_grid", "event_id", "bracket", "purge", "uncertain_overlap"])
def test_evaluation_reuses_coverage_event_and_purge_rules_before_inference(failure):
    policy, rows, validation, calls = evaluation_fixture()
    if failure == "missing_grid":
        validation.pop()
    elif failure == "duplicate_grid":
        validation.append(validation[-1])
    elif failure == "event_id":
        validation[1] = replace(example(5, "start", split="val"), source=validation[0].source)
    elif failure == "bracket":
        validation[0] = replace(validation[0], first_started_t=.501)
    elif failure == "purge":
        validation[0] = replace(validation[0], confirmation_t=.901)
    else:
        validation[0] = replace(validation[0], label=None, label_known=False, reason="cross_bin",
                                last_not_started_t=.48, first_started_t=.52, confirmation_t=.53)
    with pytest.raises(DemoError):
        evaluate(policy, rows, validation)
    assert not calls


def test_evaluation_retains_multiple_independent_validation_profiles():
    policy, rows, validation, calls = evaluation_fixture()
    third_source = replace(SOURCE, source_profile_sha256="6" * 64)
    third = [replace(e, session="val-third", group="third", media_sha256="8" * 64, source=third_source)
             for e in validation]
    report = evaluate(policy, rows, [*validation, *third])
    assert len(calls) == 4
    assert {s["source_profile_sha256"] for s in report["validation_sources"]} == {"6" * 64, "7" * 64}
    assert report["training_source"] == asdict(SOURCE)


def test_public_cohort_train_and_save_still_require_exact_source_identity(tmp_path):
    policy, rows, validation, calls = evaluation_fixture()
    distinct_train = [replace(e, split="train") for e in validation]
    assert same_event_domain(SOURCE, distinct_train[0].source)
    with pytest.raises(DemoError, match="mixed source identity"):
        cohort([*rows, *distinct_train])
    # Fails before the numeric fitter; this test performs no training.
    with pytest.raises(DemoError, match="mixed source identity"):
        train([*rows, *distinct_train], epochs=1)
    with pytest.raises(DemoError, match="checkpoint training provenance mismatch"):
        save_checkpoint(tmp_path / "refused.pt", policy, distinct_train,
                        code_sha256="9" * 64, training_config={})
    assert not (tmp_path / "refused.pt").exists() and not calls


def test_load_and_deployment_still_require_exact_source_profile(tmp_path):
    pytest.importorskip("torch")
    rows = packet()
    # Fresh random weights only: no training job or optimization.
    policy = RangeSkillPolicy(legacy.make_model(SPEC), SPEC, SOURCE, (1, 1), "synthetic",
                              evidence_digest(rows), coverage_report(rows))
    path = tmp_path / "synthetic-untrained.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={"untrained_test": True})
    different = replace(SOURCE, source_profile_sha256="7" * 64)
    assert same_event_domain(SOURCE, different)
    with pytest.raises(DemoError, match="source identity mismatch"):
        load_checkpoint(path, expected_sha256=sha, expected_identity=different, offline=True)
    receipt = SkillDeploymentBinding(sha, digest(asdict(SOURCE)), RUNTIME, "8" * 64)
    with pytest.raises(DemoError, match="deployment source binding mismatch"):
        receipt.validate(checkpoint_sha256=sha, source_identity=different, expected_runtime=RUNTIME)


def test_grid_uses_actual_cts_and_preserves_resource_clock():
    e = example()
    assert e.history[-1].state.t == pytest.approx(.39)
    assert len(e.validate()) == 5
    assert e.history[-1].state.t != e.anchor_t
    assert e.history[-1].available_t == pytest.approx(.392)
    assert e.purge_footprint() == pytest.approx((-.01, .51))
    with pytest.raises(DemoError):
        legacy.window(e.history, e.anchor_t, SPEC)


@pytest.mark.parametrize("mutation", [
    lambda e: replace(e, history=()),
    lambda e: replace(e, label="idle"),
    lambda e: replace(e, label="engage"),
    lambda e: replace(e, label_known=False),
    lambda e: replace(e, target_agreed=False),
    lambda e: replace(e, anchor_target_track=99),
    lambda e: replace(e, grid_index=5),
    lambda e: replace(e, exposure_start_t=e.anchor_t + .001),
    lambda e: replace(e, exposure_end_t=e.anchor_t + .099),
    lambda e: replace(e, confirmation_t=e.anchor_t + .099),
    lambda e: replace(e, confirmation_t=1.),
    lambda e: replace(e, first_started_t=e.anchor_t + .101),
    lambda e: replace(e, last_not_started_t=e.anchor_t - .001),
    lambda e: replace(e, event_id=None),
    lambda e: replace(e, head="engage"),
    lambda e: replace(e, semantic_revision="legacy"),
    lambda e: replace(e, origin="scripted"),
    lambda e: replace(e, split="test"),
    lambda e: replace(e, source=legacy.Identity("patch", "normal", "a" * 64, "b" * 64)),
    lambda e: replace(e, history=(*e.history[:-1], replace(e.history[-1], available_t=e.anchor_t + .001))),
    lambda e: replace(e, history=(*e.history[:-1], Snapshot(state(e.anchor_t + .001), TARGET, e.anchor_t + .001))),
    lambda e: replace(e, history=(*e.history[:-1], Snapshot(state(e.anchor_t - .026), TARGET, e.anchor_t - .026))),
    lambda e: replace(e, history=(e.history[0], e.history[0], *e.history[2:])),
    lambda e: replace(e, history=(replace(e.history[0], available_t=.001), *e.history[1:])),
])
def test_known_rows_reject_invalid_evidence(mutation):
    with pytest.raises(DemoError):
        mutation(example()).validate()


def test_unknown_coverage_does_not_need_fabricated_features_or_exposure():
    rows = packet()
    assert cohort(rows) == (SOURCE, "synthetic")
    assert rows[-1].validate() is None
    report = coverage_report(rows)
    assert report["bin_support"] == [1, 1]
    assert report["unique_events"] == 1
    assert report["masked_reasons"] == {"uninspected": 3}
    assert report["ammo_positive_visible_nononsets"] == 1
    assert not report["complete_label_coverage"]
    with pytest.raises(DemoError, match="missing grid coverage"):
        cohort(rows[:-1])
    with pytest.raises(DemoError, match="duplicate grid"):
        cohort([*rows, rows[-1]])
    with pytest.raises(DemoError):
        replace(rows[-1], reason="").validate()


def test_cross_bin_event_masks_all_intersected_rows():
    rows = packet()
    rows[0] = replace(rows[0], label_known=False, label=None, reason="cross_bin",
                      last_not_started_t=.48, first_started_t=.52, confirmation_t=.53)
    with pytest.raises(DemoError, match="overlaps a known"):
        cohort(rows)
    rows[1] = replace(rows[1], label_known=False, label=None, reason="cross_bin")
    cohort(rows)


def test_event_id_not_reused_and_no_partition_leakage():
    rows = packet()
    rows[1] = example(5)
    with pytest.raises(DemoError, match="event ID reused"):
        cohort(rows)
    with pytest.raises(DemoError, match="leakage"):
        cohort([*packet(), *(replace(e, session="train") for e in packet("val"))])
    with pytest.raises(DemoError, match="leakage"):
        cohort([*packet(), *(replace(e, media_sha256="d" * 64) for e in packet("val"))])


def test_same_media_cannot_double_support_under_session_alias():
    rows = packet()
    alias = [replace(e, session="session-alias") for e in rows]
    with pytest.raises(DemoError, match="media"):
        cohort([*rows, *alias])
    with pytest.raises(DemoError, match="media"):
        train([*rows, *alias], epochs=1)


def test_same_group_distinct_media_sessions_remain_valid():
    rows = packet()
    other = [replace(e, session="distinct-session", media_sha256="8" * 64) for e in rows]
    cohort([*rows, *other])
    report = coverage_report([*rows, *other])
    assert report["bin_support"] == [2, 2] and report["unique_events"] == 2


def test_same_media_segment_alias_cannot_duplicate_exposure():
    rows = packet()
    alias = [replace(e, continuous_id="segment-alias", event_id="event-alias" if e.event_id else None)
             for e in rows]
    with pytest.raises(DemoError, match="overlapping continuous"):
        cohort([*rows, *alias])


def first_acquisition_history():
    memory = Memory()
    snapshots = []
    for i in range(5):
        current = state(i * .1, detections=() if i < 3 else (TARGET,))
        _, target = scripted_brain.gate(current, memory)
        snapshots.append(Snapshot(current, target, current.t))
    return tuple(snapshots)


def test_first_acquisition_real_gate_matches_offline_proposal():
    history = first_acquisition_history()
    assert [s.target for s in history] == [None, None, None, None, TARGET]
    rows, validation = packet(), packet("val")
    validation[0] = replace(validation[0], history=history)
    diagnostic = SimpleNamespace(spec=SPEC, identity=SOURCE, origin="synthetic", support=(1, 1),
                                 data_sha256=evidence_digest(rows), probabilities=lambda *args: (.01, .99))
    report = evaluate(diagnostic, rows, validation)
    offline = report["metrics"]["confidence_filtered"]
    assert offline["true_positive"] == 1
    assert "accepted" not in report["metrics"]
    assert report["prediction_boundary"] == "offline_model_proposals"
    assert report["confidence_filter"] == {"threshold": SPEC.confidence,
                                            "consumer_acceptance_measured": False,
                                            "executor_acceptance_measured": False}
    assert report["offline_assumptions"]
    policy = FixedPolicy()
    consumer, memory = LearnedRangeSkillBrain(policy), Memory()
    for snapshot in history:
        intent = consumer(snapshot.state, memory)
    assert isinstance(intent, RangeSkill)
    assert intent.web_cluster_request == "start" and policy.calls == 1
    assert tuple(consumer.history) == history


@pytest.mark.parametrize("failure", ["missing_detector", "malformed", "cadence_gap"])
def test_first_acquisition_does_not_bypass_hard_history_reset(failure):
    snapshots = first_acquisition_history()
    policy = FixedPolicy()
    consumer, memory = LearnedRangeSkillBrain(policy), Memory()
    for i, snapshot in enumerate(snapshots):
        current = replace(snapshot.state)
        if i == 1 and failure == "missing_detector":
            current.detections = None
        if i == 1 and failure == "malformed":
            current.webs = -1
        if i >= 2 and failure == "cadence_gap":
            current.t += .1
        intent = consumer(current, memory)
    assert isinstance(intent, Idle) and consumer.reason == "warming_up"
    assert policy.calls == 0 and len(consumer.history) == 3


def test_first_acquisition_still_applies_confidence_refusal():
    policy = FixedPolicy((.5, .5))
    consumer, memory = LearnedRangeSkillBrain(policy), Memory()
    for snapshot in first_acquisition_history():
        intent = consumer(snapshot.state, memory)
    assert isinstance(intent, Idle) and consumer.reason == "low_confidence"
    assert policy.calls == 1 and len(consumer.history) == 5


@pytest.mark.parametrize("coasting", [(), (TARGET.track,)])
def test_warmed_current_target_loss_refuses_but_keeps_observed_gameplay(coasting):
    consumer, memory, _ = warmed()
    calls = consumer.policy.calls
    current = state(.6, detections=())
    current.coasting = coasting
    assert isinstance(consumer(current, memory), Idle)
    assert consumer.reason == "target_unobserved" and consumer.policy.calls == calls
    assert len(consumer.history) == 5
    assert consumer.history[-1].state.detections == [] and consumer.history[-1].target is None


def test_retreat_observations_remain_causal_but_current_retreat_never_infers():
    consumer, memory, _ = warmed()
    calls = consumer.policy.calls
    assert isinstance(consumer(state(.6, hp=20), memory), Disengage)
    assert consumer.policy.calls == calls and len(consumer.history) == 5
    assert consumer.history[-1].state.hp == 20
    assert isinstance(consumer(state(.7, hp=240), memory), RangeSkill)
    assert consumer.policy.calls == calls + 1


def test_latest_confirmation_is_in_purge_footprint():
    e = replace(example(), confirmation_t=.85)
    e.validate()
    assert e.purge_footprint()[1] == .85
    with pytest.raises(DemoError):
        replace(e, segment_end_t=.8).validate()


def test_live_sampling_uses_actual_anchor_and_bounded_jitter():
    clocks = (.0, .105, .2, .31, .4)
    history = tuple(Snapshot(state(t), TARGET, t) for t in clocks)
    event_window(history, .4, sampling="live")
    with pytest.raises(DemoError, match="future grid"):
        event_window(history, .4)
    with pytest.raises(DemoError, match="cadence"):
        event_window(tuple(Snapshot(state(t), TARGET, t) for t in (.0, .076, .224, .3, .4)), .4, sampling="live")
    with pytest.raises(DemoError):
        Spec(steps=4).validate()


class FixedPolicy:
    spec = SPEC

    def __init__(self, probabilities=(.01, .99)):
        self.values, self.calls = probabilities, 0

    def probabilities(self, history, anchor_t, *, sampling):
        assert sampling == "live"
        event_window(history, anchor_t, self.spec, sampling=sampling)
        self.calls += 1
        return self.values


def warmed(values=(.01, .99)):
    policy = FixedPolicy(values)
    consumer, memory = LearnedRangeSkillBrain(policy), Memory()
    for i in range(6):  # reviewed selector acquires after two sightings
        intent = consumer(state(i * .1), memory)
    return consumer, memory, intent


def test_consumer_start_and_no_new_use_resource_observation_and_unique_ids():
    consumer, memory, intent = warmed()
    assert isinstance(intent, RangeSkill)
    assert intent.web_cluster_request == "start"
    assert intent.resources.webs == 3 and intent.resources.observed_t == .5
    assert intent.valid_until == pytest.approx(.6)
    consumer.policy.values = (.99, .01)
    current = state(.6, webs=None)
    next_intent = consumer(current, memory)
    current.webs = 5
    assert next_intent.web_cluster_request == "no_new_start"
    assert next_intent.decision_id > intent.decision_id
    assert next_intent.resources.webs is None and next_intent.resources.observed_t == .6
    assert consumer.last["resources"] == {"webs": None, "observed_t": .6}
    assert consumer.history[-1].state.webs is None


@pytest.mark.parametrize("legacy_intent", [Engage(TARGET), Combo("burst", TARGET)])
@pytest.mark.parametrize("failure", ["detector", "gap", "coast", "empty", "backwards", "malformed"])
def test_faults_cannot_refresh_old_attack(legacy_intent, failure):
    consumer, memory, _ = warmed()
    memory.intent, memory.hold_until = legacy_intent, 9.
    before = consumer.policy.calls
    current = state(.6)
    if failure == "detector":
        current.detections = None
    elif failure == "gap":
        current.t = .8
    elif failure == "coast":
        current.detections, current.coasting = [], (TARGET.track,)
    elif failure == "empty":
        current.detections = []
    elif failure == "backwards":
        current.t = .5
    elif failure == "malformed":
        current.webs = -1
    assert isinstance(consumer(current, memory), Idle)
    assert consumer.policy.calls == before
    assert isinstance(memory.intent, Idle)


def test_valid_legacy_hold_is_never_adopted_but_model_can_make_fresh_request():
    consumer, memory, _ = warmed()
    memory.intent, memory.hold_until = Combo("burst", TARGET), 9.
    intent = consumer(state(.6), memory)
    assert type(intent) is RangeSkill
    assert consumer.source == "range_skill_model"
    assert memory.hold_until == -float("inf")


def test_low_hp_retreat_is_scripted_and_detector_failure_preempts_it():
    consumer, memory, _ = warmed()
    assert isinstance(consumer(state(.6, hp=20), memory), Disengage)
    assert consumer.source == "range_skill_gate"
    assert consumer.reason == "scripted_low_hp_retreat"
    assert isinstance(consumer(state(.7, hp=20, detections=None), memory), Idle)


@pytest.mark.parametrize("values", [(.5, .5), (float("nan"), .9), (.1, .1), (1.,), (.1, 2.)])
def test_uncertain_or_invalid_predictions_refuse(values):
    consumer, _, intent = warmed(values)
    assert isinstance(intent, Idle)
    assert consumer.source == "range_skill_refusal"


def test_inference_error_refuses_without_fallback():
    consumer, memory, _ = warmed()
    def broken(*args, **kwargs):
        raise RuntimeError("synthetic failure")
    consumer.policy.probabilities = broken
    assert isinstance(consumer(state(.6), memory), Idle)
    assert consumer.reason == "inference_failed"


def test_model_request_crosses_real_pure_controller_boundary_and_refusal_releases():
    from agent.controller import Controller, NEUTRAL
    consumer, memory, intent = warmed((.99, .01))
    controller = Controller()
    # Reflex runs between decisions, preserving the original decision timestamp.
    for t in (.5, .52, .54, .56, .58):
        out = controller.step(state(t, webs=None), intent, intent_t=.5)
        assert not out["lt"] and not out["rt"] and not out["buttons"]
    assert out["ly"] == 1  # no-new is moving play, not global Idle
    consumer.policy.values = (.01, .99)
    attack = consumer(state(.6), memory)
    out = controller.step(state(.6, webs=None), attack, intent_t=.6)
    assert controller.range_skill_trace["accepted"] and out["lt"] == 1
    # A future reflex reading cannot refill the decision's ammo or preserve a faulted pulse.
    refused = consumer(state(.61, detections=None), memory)
    assert isinstance(refused, Idle)
    assert controller.step(state(.61, webs=5), refused, intent_t=.61) == NEUTRAL
    assert controller.range_skill_trace["pulse_outcome"] == "truncated"


def test_detector_gap_recovery_requires_new_five_snapshot_history():
    consumer, memory, _ = warmed()
    calls = consumer.policy.calls
    assert isinstance(consumer(state(.6, detections=None), memory), Idle)
    for t in (.7, .8, .9, 1.):
        assert isinstance(consumer(state(t), memory), Idle)
    assert consumer.policy.calls == calls
    assert isinstance(consumer(state(1.1), memory), RangeSkill)


def test_copied_histories_and_malformed_coasting_refuse():
    consumer, memory, _ = warmed()
    current = state(.6)
    consumer(current, memory)
    current.detections.clear()
    assert consumer.history[-1].state.detections == [TARGET]
    bad = state(.7)
    bad.coasting = None
    assert isinstance(consumer(bad, memory), Idle)
    assert consumer.reason == "malformed_target_state"


def test_timing_metrics_count_one_event_and_extra_start_as_false_positive():
    rows = packet()
    metrics = event_metrics(rows, ["start", "start", None, None, None])
    assert (metrics["true_positive"], metrics["false_positive"], metrics["false_negative"]) == (1, 1, 0)
    assert metrics["mean_request_to_bracket_s"] == pytest.approx(.02)
    assert metrics["masked_bins"] == 3
    assert event_metrics(rows, [None] * 5)["false_negative"] == 1


@pytest.fixture
def fitted():
    torch = pytest.importorskip("torch")
    torch.set_num_threads(1)
    rows = packet()
    return train(rows, spec=SPEC, epochs=2, batch_size=2), rows


def test_two_observed_rows_fit_reload_and_masked_rows_never_score(fitted, tmp_path):
    policy, rows = fitted
    assert policy.support == (1, 1)
    path = tmp_path / "events.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={"epochs": 2})
    loaded = load_checkpoint(path, expected_sha256=sha, expected_identity=SOURCE, offline=True)
    assert loaded.probabilities(rows[0].history, rows[0].anchor_t) == policy.probabilities(rows[0].history, rows[0].anchor_t)
    with pytest.raises(FileExistsError):
        save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={})
    report = evaluate(loaded, rows, packet("val"))
    assert report["scope"] == "partial_observed_diagnostic"
    assert report["probabilities"][2:] == [None] * 3
    assert report["metrics"]["always_start"]["false_positive"] == 1
    with pytest.raises(DemoError, match="complete observed coverage"):
        evaluate(loaded, rows, packet("val"), complete_evaluation=True)
    with pytest.raises(DemoError, match="synthetic checkpoint"):
        load_checkpoint(path, expected_sha256=sha, expected_identity=SOURCE)


def test_checkpoint_pins_new_semantics_and_separate_reviewed_runtime(fitted, tmp_path):
    policy, rows = fitted
    torch = pytest.importorskip("torch")
    path = tmp_path / "synthetic.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={})
    payload = torch.load(path, weights_only=True)
    # Synthetic metadata fixture for exercising the loader gate; not human evidence or approval.
    payload["origin"] = "reviewed_human"
    reviewed = tmp_path / "pretend-review-loader-test.pt"
    torch.save(payload, reviewed)
    sha = legacy.fingerprint(reviewed)
    receipt = SkillDeploymentBinding(sha, digest(asdict(SOURCE)), RUNTIME, "8" * 64)
    with pytest.raises(DemoError, match="live load requires"):
        load_checkpoint(reviewed, expected_sha256=sha, expected_identity=SOURCE)
    loaded = load_checkpoint(reviewed, expected_sha256=sha, expected_identity=SOURCE,
                             expected_runtime=RUNTIME, deployment_binding=receipt)
    assert loaded.identity == SOURCE
    for runtime in (replace(RUNTIME, calibration_sha256="7" * 64),
                    replace(RUNTIME, selector_sha256="7" * 64),
                    replace(RUNTIME, semantic_revision="legacy")):
        with pytest.raises(DemoError):
            load_checkpoint(reviewed, expected_sha256=sha, expected_identity=SOURCE,
                            expected_runtime=runtime, deployment_binding=receipt)
    copied = replace(RUNTIME, runtime_settings_sha256=SOURCE.source_profile_sha256)
    with pytest.raises(DemoError, match="not runtime motor"):
        replace(receipt, runtime=copied).validate(checkpoint_sha256=sha, source_identity=SOURCE, expected_runtime=copied)
    with pytest.raises(DemoError):
        replace(receipt, checkpoint_sha256="7" * 64).validate(checkpoint_sha256=sha, source_identity=SOURCE, expected_runtime=RUNTIME)
    old_receipt = legacy.DeploymentBinding(sha, digest(asdict(SOURCE)), RUNTIME, "8" * 64)
    with pytest.raises(DemoError):
        load_checkpoint(reviewed, expected_sha256=sha, expected_identity=SOURCE,
                        expected_runtime=RUNTIME, deployment_binding=old_receipt)
    payload["format"] = legacy.FORMAT
    old = tmp_path / "wrong-format.pt"
    torch.save(payload, old)
    with pytest.raises(DemoError, match="incompatible event"):
        load_checkpoint(old, expected_sha256=legacy.fingerprint(old), expected_identity=SOURCE, offline=True)


def test_fit_requires_both_semantic_outcomes_without_an_idle_class():
    rows = packet()
    rows[0] = replace(rows[0], label_known=False, label=None, reason="unreviewed")
    with pytest.raises(DemoError, match="every output"):
        train(rows, epochs=1)
    assert OUTCOMES == ("no_new_start", "start") and HEAD == "web_cluster_start"
    assert FORMAT != legacy.FORMAT
    assert SOURCE.semantic_revision == SEMANTIC_REVISION and SOURCE.feature_revision == FEATURE_REVISION


REQUEST_SOURCE = replace(SOURCE, semantic_revision=REQUEST_SEMANTIC_REVISION)
REQUEST_RUNTIME = replace(RUNTIME, semantic_revision=REQUEST_SEMANTIC_REVISION)


def request_example(index=4, label="start", *, split="train"):
    old = example(index, label, split=split)
    # Fixture construction only: no real visual row or label is converted.
    common = {name: getattr(old, name) for name in old.__dataclass_fields__
              if name not in ("event_id", "last_not_started_t", "first_started_t", "head", "semantic_revision")}
    common["source"] = REQUEST_SOURCE
    positive = label == "start"
    return RequestExample(**common, request_id="request-1" if positive else None,
        request_t=old.anchor_t + .05 if positive else None,
        raw_input_sha256=("1" if split == "train" else "2") * 64,
        raw_device=7 if positive else None, request_seq=12 if positive else None,
        prior_up_seq=10 if positive else None, prior_up_t=old.anchor_t - .01 if positive else None,
        raw_continuity_start_t=old.anchor_t - .02, raw_continuity_end_t=old.anchor_t + .1,
        raw_continuity_known=label is not None,
        request_status="fresh_rise" if positive else "no_fresh_rise" if label else "unknown",
        raw_evidence="synthetic received RMB interval, displayed source-local web binding",
        cast_id="cast-1" if positive else None,
        cast_last_not_started_t=old.anchor_t + .07 if positive else None,
        cast_first_started_t=old.anchor_t + .09 if positive else None,
        association_agreed=positive, association_evidence="synthetic same-target cast association" if positive else "")


def request_packet(split="train"):
    return [request_example(4, "start", split=split), request_example(5, "no_new_start", split=split),
            *(request_example(i, None, split=split) for i in range(6, 9))]


def test_request_point_is_separate_from_visual_bracket_and_old_constructor():
    row = request_example()
    assert len(row.validate(SPEC)) == 5
    assert row.event_id == row.request_id and row.event_end_t == row.request_t
    assert "event_id" not in asdict(row) and "last_not_started_t" not in asdict(row)
    with pytest.raises(TypeError):
        replace(row, last_not_started_t=.44)
    with pytest.raises(DemoError, match="head/semantics"):
        replace(example(), source=REQUEST_SOURCE, head=REQUEST_HEAD,
                semantic_revision=REQUEST_SEMANTIC_REVISION).validate()
    with pytest.raises(DemoError, match="head/semantics"):
        replace(row, source=SOURCE).validate()


@pytest.mark.parametrize("time", [.4, .399, .500001])
def test_request_point_must_be_strictly_after_anchor_and_within_horizon(time):
    row = replace(request_example(), request_t=time, cast_first_started_t=.58, confirmation_t=.59)
    with pytest.raises(DemoError, match="next bin"):
        row.validate()


def test_request_at_right_boundary_and_later_cast_are_valid():
    row = replace(request_example(), request_t=.5, cast_last_not_started_t=.57,
                  cast_first_started_t=.59, confirmation_t=.684998151)
    row.validate()
    assert row.purge_footprint()[1] == .684998151  # latest used overlap release, not a feature
    rows = request_packet()
    rows[0] = row
    cohort(rows)  # later visual cast overlaps next known non-request; it is not a second request
    metrics = event_metrics(rows, ["start", "no_new_start", None, None, None])
    assert metrics["true_positive"] == 1
    assert metrics["mean_request_lead_s"] == pytest.approx(.1)
    assert "mean_request_to_bracket_s" not in metrics


@pytest.mark.parametrize("clock", ["state", "available"])
def test_request_features_cannot_contain_future_or_post_request_observations(clock):
    row = request_example()
    final = row.history[-1]
    # Ordinary future snapshot and the old grid validator's sub-nanosecond epsilon.
    for request_t, feature_t in ((.45, .46), (.4000000001, .4000000002)):
        final_state = replace(final.state, t=feature_t) if clock == "state" else final.state
        final_snapshot = Snapshot(final_state, final.target, feature_t)
        with pytest.raises(DemoError):
            replace(row, request_t=request_t, history=(*row.history[:-1], final_snapshot)).validate()


def test_received_held_continuation_and_release_can_be_known_nonrequest():
    row = replace(request_example(5, "no_new_start"),
                  raw_evidence="Synthetic full RMB interval: held at anchor, release .56; no fresh rise; other bindings unknown")
    assert len(row.validate()) == 5
    assert row.request_id is None and row.request_t is None
    assert coverage_report([row])["bin_support"] == [1, 0]
    # 'held' alone is an incomplete annotation, not a negative by default.
    assert replace(request_example(5, None), request_status="held").validate() is None
    with pytest.raises(DemoError, match="no_fresh_rise"):
        replace(row, request_status="held").validate()


@pytest.mark.parametrize("status", ["held", "repeated_down", "unknown", "association_conflict"])
def test_uncertain_request_status_is_masked_not_credited(status):
    row = replace(request_example(), request_status=status, label=None, label_known=False,
                  reason="synthetic ambiguity", association_agreed=False)
    assert row.validate() is None
    assert coverage_report([row])["unique_events"] == 0
    assert event_metrics([row], ["start"])["scored_bins"] == 0
    with pytest.raises(DemoError):
        replace(row, label="start", label_known=True).validate()


@pytest.mark.parametrize("changes", [
    {"raw_input_sha256": None}, {"raw_evidence": ""}, {"raw_continuity_known": False},
    {"raw_continuity_start_t": .401}, {"raw_continuity_end_t": .499}, {"raw_continuity_end_t": .7},
    {"request_t": None}, {"raw_device": None}, {"request_seq": True},
    {"prior_up_seq": None, "prior_up_t": None}, {"prior_up_seq": 12}, {"prior_up_t": .451},
    {"raw_continuity_start_t": .395}, {"association_agreed": False}, {"association_evidence": ""},
    {"cast_id": None}, {"cast_last_not_started_t": .43, "cast_first_started_t": .44},
    {"confirmation_t": .48}, {"target_agreed": False},
])
def test_known_request_requires_raw_continuity_rise_and_cast_evidence(changes):
    with pytest.raises(DemoError):
        replace(request_example(), **changes).validate()


@pytest.mark.parametrize("changes", [
    {"raw_input_sha256": None}, {"raw_continuity_known": False}, {"raw_evidence": ""},
    {"raw_continuity_start_t": .501}, {"raw_continuity_end_t": .599}, {"raw_continuity_end_t": .7},
    {"request_status": "repeated_down"}, {"target_agreed": False},
])
def test_known_nonrequest_needs_full_interval_and_target_evidence(changes):
    with pytest.raises(DemoError):
        replace(request_example(5, "no_new_start"), **changes).validate()


def test_request_coverage_and_uncertain_point_overlap_cannot_create_negatives():
    rows = request_packet()
    with pytest.raises(DemoError, match="missing grid"):
        cohort(rows[:-1])
    rows[2] = replace(request_example(6, None), request_id="ambiguous-2", request_t=.55,
                      raw_device=7, request_seq=20, request_status="association_conflict")
    with pytest.raises(DemoError, match="overlaps a known"):
        cohort(rows)


@pytest.mark.parametrize("failure", ["media_alias", "raw_alias", "request_id", "cast", "raw_source"])
def test_request_canonical_media_and_one_event_credit(failure):
    rows = request_packet()
    if failure == "media_alias":
        rows += [replace(e, session="alias") for e in rows]
    elif failure == "raw_alias":
        rows += [replace(e, session="other", media_sha256="8" * 64,
                         request_id="request-alias" if e.request_id else None) for e in rows]
    elif failure in ("request_id", "cast"):
        rows[1] = replace(request_example(5), request_seq=22, prior_up_seq=20,
                          request_id="request-2" if failure == "cast" else "request-1")
    else:
        rows[1] = replace(rows[1], raw_input_sha256="8" * 64)
    with pytest.raises(DemoError):
        cohort(rows)


def test_distinct_media_same_group_is_valid_with_distinct_requests():
    rows = request_packet()
    other = [replace(e, session="other", media_sha256="8" * 64, raw_input_sha256="9" * 64) for e in rows]
    cohort(rows + other)
    assert coverage_report(rows + other)["unique_events"] == 2
    assert coverage_report(rows + other)["bin_support"] == [2, 2]


def test_request_metrics_use_point_not_delayed_cast_and_one_to_one_credit():
    rows = request_packet()
    rows[0] = replace(rows[0], cast_last_not_started_t=.57, cast_first_started_t=.59, confirmation_t=.7)
    cohort(rows)
    metrics = event_metrics(rows, ["start", "start", None, None, None])
    assert (metrics["true_positive"], metrics["false_positive"], metrics["false_negative"]) == (1, 1, 0)
    assert metrics["mean_request_lead_s"] == pytest.approx(.05)
    late = event_metrics(rows, ["no_new_start", "start", None, None, None])
    assert (late["true_positive"], late["false_positive"], late["false_negative"]) == (0, 1, 1)


@pytest.fixture
def request_fitted():
    torch = pytest.importorskip("torch")
    torch.set_num_threads(1)
    rows = request_packet()
    return train(rows, spec=SPEC, epochs=2, batch_size=2), rows


def test_request_train_portable_load_eval_and_actual_consumer(request_fitted, tmp_path):
    policy, rows = request_fitted
    assert (policy.format, policy.head, policy.semantic_revision) == (REQUEST_FORMAT, REQUEST_HEAD, REQUEST_SEMANTIC_REVISION)
    assert policy.support == (1, 1)
    path = tmp_path / "requests.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={"epochs": 2})
    loaded = load_checkpoint(path, expected_sha256=sha, expected_identity=REQUEST_SOURCE, offline=True)
    assert loaded.probabilities(rows[0].history, .4) == policy.probabilities(rows[0].history, .4)
    validation = [replace(e, source=replace(REQUEST_SOURCE, source_profile_sha256="7" * 64)) for e in request_packet("val")]
    report = evaluate(loaded, rows, validation)
    assert (report["format"], report["head"], report["semantic_revision"]) == (REQUEST_FORMAT, REQUEST_HEAD, REQUEST_SEMANTIC_REVISION)
    assert report["training_source"]["source_profile_sha256"] != report["validation_sources"][0]["source_profile_sha256"]
    assert report["probabilities"][2:] == [None] * 3
    assert not report["confidence_filter"]["consumer_acceptance_measured"]
    consumer = LearnedRangeSkillBrain.from_checkpoint(path, expected_sha256=sha, expected_identity=REQUEST_SOURCE, offline=True)
    memory = Memory()
    for t in (0., .1, .2, .3, .4, .5):
        intent = consumer(state(t), memory)
    assert consumer.policy.identity == REQUEST_SOURCE and consumer.policy.head == REQUEST_HEAD
    assert consumer.last["probabilities"] is not None  # actual gate + actual unmodified model, no executor
    assert type(intent) in (Idle, RangeSkill)  # tiny fit is not a confidence/performance claim
    with pytest.raises(DemoError, match="synthetic checkpoint"):
        load_checkpoint(path, expected_sha256=sha, expected_identity=REQUEST_SOURCE)


def test_cross_semantic_cohort_training_and_evaluation_refuse_before_inference():
    with pytest.raises(DemoError, match="mixed source"):
        cohort(packet() + request_packet("val"))
    with pytest.raises(DemoError, match="mixed source"):
        train(packet() + request_packet("val"), epochs=1)
    policy, rows, _, calls = evaluation_fixture()
    with pytest.raises(DemoError, match="mixed source"):
        evaluate(policy, rows, request_packet("val"))
    assert not calls


def test_cross_semantic_checkpoints_and_deployment_never_coerce_classes(request_fitted, fitted, tmp_path):
    for policy, rows, expected, wrong in ((*request_fitted, REQUEST_SOURCE, SOURCE), (*fitted, SOURCE, REQUEST_SOURCE)):
        path = tmp_path / (policy.format + ".pt")
        sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={})
        with pytest.raises(DemoError, match="incompatible event checkpoint"):
            load_checkpoint(path, expected_sha256=sha, expected_identity=wrong, offline=True)
        with pytest.raises(DemoError):
            save_checkpoint(tmp_path / "wrong.pt", policy, packet() if expected == REQUEST_SOURCE else request_packet(),
                            code_sha256="9" * 64, training_config={})
        runtime = RUNTIME if expected == REQUEST_SOURCE else REQUEST_RUNTIME
        binding = SkillDeploymentBinding(sha, digest(asdict(expected)), runtime, "8" * 64)
        with pytest.raises(DemoError, match="semantic/feature mismatch"):
            load_checkpoint(path, expected_sha256=sha, expected_identity=expected, offline=True,
                            expected_runtime=runtime, deployment_binding=binding)
    policy, rows = request_fitted
    path = tmp_path / "request-bound.pt"
    sha = save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={})
    binding = SkillDeploymentBinding(sha, digest(asdict(REQUEST_SOURCE)), REQUEST_RUNTIME, "8" * 64)
    assert load_checkpoint(path, expected_sha256=sha, expected_identity=REQUEST_SOURCE, offline=True,
                           expected_runtime=REQUEST_RUNTIME, deployment_binding=binding).identity == REQUEST_SOURCE


@pytest.mark.parametrize("field,value", [("format", FORMAT), ("head", HEAD), ("semantic_revision", SEMANTIC_REVISION)])
def test_request_loader_rejects_mixed_portable_headers(request_fitted, tmp_path, field, value):
    policy, rows = request_fitted
    torch = pytest.importorskip("torch")
    path = tmp_path / "original.pt"
    save_checkpoint(path, policy, rows, code_sha256="9" * 64, training_config={})
    payload = torch.load(path, weights_only=True)
    payload[field] = value
    wrong = tmp_path / "mixed.pt"
    torch.save(payload, wrong)
    with pytest.raises(DemoError, match="incompatible event"):
        load_checkpoint(wrong, expected_sha256=legacy.fingerprint(wrong), expected_identity=REQUEST_SOURCE, offline=True)


def test_received_state_prehistory_extends_only_evidence_purge_not_gameplay():
    # Synthetic clock control using the lead-supplied dependency boundary. No
    # source artifact/adapter read, real label, or admitted evidence is implied.
    row = replace(request_example(141), segment_start_t=11., segment_end_t=22.25,
                  raw_continuity_start_t=.421919351, prior_up_t=10.415016051,
                  request_t=14.197983651, cast_last_not_started_t=14.29,
                  cast_first_started_t=14.31, confirmation_t=14.384998151)
    original_history = row.history
    row.validate()
    assert row.purge_footprint() == (.421919351, 14.384998151)
    assert row.history == original_history
    assert all(11. <= s.state.t <= row.anchor_t for s in row.history)
    assert row.exposure_start_t >= 11. and row.exposure_end_t <= 22.25
    negative = replace(request_example(137, "no_new_start"), segment_start_t=11., segment_end_t=22.25,
                       raw_continuity_start_t=.421919351,
                       raw_evidence="Synthetic focus and held-state carry-in before gameplay, no fresh rise in bin")
    negative.validate()
    assert negative.purge_footprint()[0] == .421919351
    for changes in ({"raw_continuity_start_t": 14.11}, {"raw_continuity_end_t": 14.19},
                    {"raw_continuity_end_t": 14.4}, {"raw_continuity_start_t": float("nan")},
                    {"raw_continuity_end_t": float("inf")}, {"raw_continuity_start_t": 15.},
                    {"raw_continuity_start_t": 10.42}):
        with pytest.raises(DemoError):
            replace(row, **changes).validate()
    # Carry-in evidence does not authorize historical gameplay feature padding.
    bad_history = (replace(row.history[0], state=replace(row.history[0].state, t=10.9)), *row.history[1:])
    with pytest.raises(DemoError):
        replace(row, history=bad_history).validate()


def test_empty_request_metric_stratum_retains_explicit_request_semantics():
    metrics = event_metrics([], [], semantic_revision=REQUEST_SEMANTIC_REVISION)
    assert metrics["mean_request_lead_s"] is None
    assert "mean_request_to_bracket_s" not in metrics
    with pytest.raises(DemoError, match="mixed metric semantics"):
        event_metrics(packet(), [None] * 5, semantic_revision=REQUEST_SEMANTIC_REVISION)


def request_evaluation_fixture():
    policy, _, _, calls = evaluation_fixture()  # fixed scorer, no fit or model construction
    rows, validation = request_packet(), request_packet("val")
    policy.identity, policy.data_sha256 = REQUEST_SOURCE, evidence_digest(rows)
    return policy, rows, validation, calls


@pytest.mark.parametrize("coverage", ["nonrequest", "masked_only", "positive"])
def test_raw_ledger_alias_rejects_before_inference_for_every_label_mask(coverage):
    policy, rows, validation, calls = request_evaluation_fixture()
    if coverage == "nonrequest":
        validation[0] = request_example(4, None, split="val")
        assert (validation[1].raw_continuity_start_t, validation[1].raw_continuity_end_t) == (.48, .6)
    elif coverage == "masked_only":
        validation = [request_example(i, None, split="val") for i in range(4, 9)]
    validation = [replace(e, raw_input_sha256="1" * 64) for e in validation]
    try:
        evaluate(policy, rows, validation)
    except DemoError:
        assert not calls
    else:
        pytest.fail(f"shared raw ledger accepted across placement: coverage={coverage}, scorer anchors={calls}")


@pytest.mark.parametrize("coverage", ["nonrequest", "masked_only", "positive"])
def test_independent_raw_ledger_preserves_each_coverage_control(coverage):
    policy, rows, validation, calls = request_evaluation_fixture()
    if coverage == "nonrequest":
        validation[0] = request_example(4, None, split="val")
    elif coverage == "masked_only":
        validation = [request_example(i, None, split="val") for i in range(4, 9)]
    assert all(e.raw_input_sha256 == "2" * 64 for e in validation)
    report = evaluate(policy, rows, validation)
    assert calls == ({"nonrequest": [.5], "masked_only": [], "positive": [.4, .5]}[coverage])
    assert report["coverage"]["grid_rows"] == 5


def test_masked_only_supplied_ledger_cannot_alias_session_even_without_split_change():
    rows = request_packet()
    other = [replace(request_example(i, None), session="alias", media_sha256="8" * 64,
                     raw_input_sha256="1" * 64 if i == 8 else None) for i in range(4, 9)]
    assert all(e.label is None and e.request_id is None for e in other)
    with pytest.raises(DemoError, match="leakage"):
        cohort(rows + other)


def test_raw_ledger_can_support_distinct_media_in_same_canonical_session_group():
    rows = request_packet()
    other = [replace(request_example(i, "no_new_start" if i == 15 else None),
                     media_sha256="8" * 64, continuous_id="continuous-2",
                     segment_start_t=.975, segment_end_t=1.9) for i in range(14, 19)]
    assert all(e.raw_input_sha256 == "1" * 64 and e.session == "train" and e.group == "train" for e in other)
    cohort(rows + other)
    assert coverage_report(rows + other)["bin_support"] == [2, 1]
