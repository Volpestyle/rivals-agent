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
    load_checkpoint, save_checkpoint, train)

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
