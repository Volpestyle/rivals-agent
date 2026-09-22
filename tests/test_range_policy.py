"""Synthetic contract/CPU checks only. No real corpus, frame capture or pad."""
from dataclasses import asdict, replace
import math

import pytest

from agent.brain import Memory
from agent.human_demos import DemoError
from agent.intents import Disengage, Engage, Idle
from agent.learned_range import LearnedRangeBrain
from agent.state import Ability, Detection, State
from policy.range_policy import (ACTIONS, FEATURES, DeploymentBinding, Example, Identity,
                                 RuntimeIdentity, Snapshot, Spec, cohort, digest, evaluate, feature_row, fingerprint,
                                 load_checkpoint, save_checkpoint, train, window)

IDENTITY = Identity("test-patch", "normal", "a" * 64, "b" * 64)
TARGET = Detection("enemy", (440, 180, 560, 370), .9, distance=10, tagged=False)
SPEC = Spec(hidden=8)
RUNTIME = RuntimeIdentity("test-patch", "normal", "1" * 64, "2" * 64,
                          "3" * 64, "4" * 64, "5" * 64)


def state(t, *, hp=240, detections=(TARGET,)):
    return State(t=t, frame=(1000, 600), hp=hp, max_hp=250,
                 webs=5, abilities={"pull": Ability(False), "uppercut": Ability(True)},
                 detections=list(detections) if detections is not None else None, on_target=True)


def example(i=0, label="engage", split="train", group=None):
    group = group or split
    anchor = i + .4
    history = tuple(Snapshot(state(i + k / 10, hp=240 if label == "engage" else 120),
                             TARGET, i + k / 10) for k in range(5))
    return Example(session=group, group=group, split=split, continuous_id="segment1",
                   media_sha256=("c" if split == "train" else "d") * 64,
                   review_sha256="e" * 64, evidence="synthetic fixture only",
                   identity=IDENTITY, history=history, anchor_t=anchor, label_end_t=anchor + .1,
                   label=label, previous_label=None, previous_known_t=None, scripted_label=None,
                   origin="synthetic")


class FixedPolicy:
    spec = SPEC

    def __init__(self, values=(.01, .99)):
        self.values, self.calls = values, 0

    def probabilities(self, history, anchor_t):
        window(history, anchor_t, self.spec)
        self.calls += 1
        return self.values


def warmed(values=(.01, .99)):
    policy = FixedPolicy(values)
    consumer, memory = LearnedRangeBrain(policy), Memory()
    for i in range(5):
        intent = consumer(state(i / 10), memory)
    return consumer, memory, intent


def test_unknown_is_distinct_from_false_and_zero():
    unknown = feature_row(Snapshot(State(0., (100, 100)), None, 0.))
    known = feature_row(Snapshot(State(0., (100, 100), hp=0, max_hp=250, webs=0,
                                      detections=[], on_target=False), None, 0.))
    for name in ("hp_fraction", "webs", "on_target", "target"):
        column = FEATURES.index(name)
        assert unknown[column:column + 2] == (0., 0.)
        assert known[column:column + 2] == (0., 1.)


@pytest.mark.parametrize("mutation", [
    lambda e: replace(e, history=e.history[:-1]),
    lambda e: replace(e, history=(*e.history[:-1], replace(e.history[-1], available_t=e.anchor_t + .01))),
    lambda e: replace(e, history=(*e.history[:-1], Snapshot(state(e.anchor_t + .01), TARGET, e.anchor_t + .01))),
    lambda e: replace(e, history=(e.history[0], e.history[0], *e.history[2:])),
    lambda e: replace(e, previous_label="engage", previous_known_t=e.anchor_t + .01),
    lambda e: replace(e, label_end_t=e.anchor_t),
    lambda e: replace(e, split="test"),
    lambda e: replace(e, origin="scripted"),
    lambda e: replace(e, label="pull"),
])
def test_rejects_future_stale_sealed_and_wrong_supervision(mutation):
    with pytest.raises(DemoError):
        mutation(example()).validate(SPEC)


def test_future_label_and_baselines_cannot_change_features():
    e = example()
    other = replace(e, label="idle", previous_label="idle", previous_known_t=e.anchor_t,
                    scripted_label="engage", evidence="changed FUTURE evidence")
    assert e.validate(SPEC) == other.validate(SPEC)


@pytest.mark.parametrize("field,value", [("hp", math.nan), ("frame", (0, 600)),
                                        ("webs", -1), ("on_target", 1)])
def test_malformed_state_refuses_before_gate(field, value):
    consumer, memory, _ = warmed()
    bad = replace(state(.5), **{field: value})
    assert isinstance(consumer(bad, memory), Idle)
    assert consumer.reason == "malformed_state"


@pytest.mark.parametrize("change", [
    {"group": "train"}, {"session": "train"}, {"media_sha256": "c" * 64},
    {"identity": replace(IDENTITY, patch="other")}, {"origin": "reviewed_human"},
])
def test_cohort_rejects_leakage_and_mixed_provenance(change):
    with pytest.raises(DemoError):
        cohort([example(), replace(example(split="val"), **change)], SPEC)


def test_unknown_labels_remain_unknown_and_duplicates_refuse():
    e = example(label=None)
    assert e.label is None
    e.validate(SPEC)
    with pytest.raises(DemoError, match="duplicate"):
        cohort([e, e], SPEC)


def test_real_idle_and_engage_use_existing_typed_boundary():
    consumer, memory, intent = warmed()
    assert isinstance(intent, Engage) and intent.target == TARGET
    assert consumer.source == "range_learned"
    consumer.policy.values = (.99, .01)
    assert isinstance(consumer(state(.5), memory), Idle)
    assert consumer.source == "range_learned" and consumer.reason == "idle"


@pytest.mark.parametrize("values,reason", [((.5, .5), "uncertain"),
                                           ((math.nan, .99), "malformed_prediction"),
                                           ((.7, .7), "malformed_prediction"),
                                           ((1.,), "malformed_prediction"),
                                           ((-.1, 1.1), "malformed_prediction")])
def test_bad_predictions_never_invoke_scripted_attack(values, reason):
    consumer, _, intent = warmed(values)
    assert isinstance(intent, Idle)
    assert consumer.reason == reason and consumer.source == "range_refusal"


def test_retreat_gate_is_retained_and_identified():
    consumer, memory, _ = warmed()
    count = consumer.policy.calls
    assert isinstance(consumer(state(.5, hp=20), memory), Disengage)
    assert consumer.source == "range_gate"
    assert consumer.policy.calls == count


@pytest.mark.parametrize("t,detections,reason", [
    (.5, None, "unknown_detector"), (.7, None, "unknown_detector"),
    (.7, (), "warming_up"), (.7, (TARGET,), "warming_up"),
])
def test_gate_cannot_renew_attack_without_current_detector_and_history(t, detections, reason):
    from agent.controller import Controller, NEUTRAL
    consumer, memory, attack = warmed()
    controller = Controller()
    controller.step(state(.4), attack)
    controller.play("melee_combo", .4)
    count = consumer.policy.calls
    intent = consumer(state(t, detections=detections), memory)
    assert isinstance(intent, Idle)
    assert consumer.source == "range_refusal" and consumer.reason == reason
    assert consumer.policy.calls == count
    assert controller.step(state(t, detections=detections), intent) == NEUTRAL
    assert not controller.seq


def test_valid_known_empty_coasting_keeps_gate_but_unknown_cannot():
    consumer, memory, attack = warmed()
    count = consumer.policy.calls
    assert consumer(state(.5, detections=()), memory) is attack
    assert consumer.source == "range_gate" and consumer.policy.calls == count
    assert isinstance(consumer(state(.6, detections=None), memory), Idle)
    assert consumer.reason == "unknown_detector"
    assert isinstance(consumer(state(.7), memory), Idle)
    assert consumer.reason == "warming_up"


def test_gate_checks_entire_history_not_just_last_interval():
    consumer, memory, _ = warmed()
    consumer.history[1] = replace(consumer.history[1], available_t=2.)
    assert isinstance(consumer(state(.5, detections=()), memory), Idle)
    assert consumer.reason == "invalid_history"


@pytest.mark.parametrize("t", [.5, .7])
def test_retreat_can_preempt_history_warmup_with_valid_current_detector(t):
    from agent.controller import Controller
    consumer, memory, _ = warmed()
    intent = consumer(state(t, hp=20), memory)
    assert isinstance(intent, Disengage) and consumer.source == "range_gate"
    output = Controller().step(state(t, hp=20), intent)
    assert output["rt"] == output["lt"] == 0 and not output["buttons"]


def test_retreat_does_not_bypass_missing_detector():
    consumer, memory, _ = warmed()
    assert isinstance(consumer(state(.5, hp=20, detections=None), memory), Idle)
    assert consumer.reason == "unknown_detector"


def test_valid_coasting_keeps_existing_offensive_sequence_only_with_valid_history():
    from agent.controller import Controller
    consumer, memory, attack = warmed()
    controller = Controller()
    controller.step(state(.4), attack)
    controller.play("melee_combo", .4)
    intent = consumer(state(.5, detections=()), memory)
    assert intent is attack and consumer.source == "range_gate"
    assert controller.step(state(.5, detections=()), intent)["rt"] == 1.


def test_individually_small_cadence_drift_cannot_bypass_full_window_check():
    consumer, memory, _ = warmed()
    consumer.policy.values = (.99, .01)
    assert isinstance(consumer(state(.52, detections=()), memory), Engage)
    assert isinstance(consumer(state(.64, detections=()), memory), Idle)
    assert consumer.reason == "invalid_history"


def test_stale_gap_repeated_state_and_missing_target():
    consumer, memory, _ = warmed()
    assert isinstance(consumer(state(.4), memory), Idle)
    assert consumer.reason == "nonmonotonic_state"
    assert isinstance(consumer(state(2.), memory), Idle)
    assert consumer.reason == "warming_up"
    for i in range(1, 8):
        intent = consumer(state(2 + i / 10, detections=()), memory)
    assert isinstance(intent, Idle) and consumer.reason == "illegal"


def test_refusal_cancels_existing_pure_controller_sequence():
    from agent.controller import Controller, NEUTRAL
    controller = Controller()
    consumer, memory, attack = warmed()
    controller.step(state(.4), attack)
    controller.play("web_cluster", .4)
    assert controller.seq
    consumer.policy.values = (.5, .5)
    neutral = consumer(state(.5), memory)
    assert isinstance(neutral, Idle)
    assert controller.step(state(.5), neutral) == NEUTRAL
    assert controller.seq == []


def test_history_copies_the_processed_state():
    consumer = LearnedRangeBrain(FixedPolicy())
    s = state(0.)
    consumer(s, Memory())
    s.hp = 0
    assert consumer.history[0].state.hp == 240


@pytest.fixture(scope="module")
def fitted():
    torch = pytest.importorskip("torch")
    threads = torch.get_num_threads()
    torch.set_num_threads(1)
    examples = [example(i, ACTIONS[i % 2]) for i in range(8)]
    policy = train(examples, spec=SPEC, epochs=80, batch_size=8, lr=.03)
    yield policy, examples
    torch.set_num_threads(threads)


def test_real_torch_fit_reload_and_typed_consumer(fitted, tmp_path):
    policy, examples = fitted
    val = [example(i, ACTIONS[i % 2], split="val") for i in range(4)]
    before = evaluate(policy, examples, val)
    assert before["model"]["accuracy"] == 1.
    assert before["majority"]["accuracy"] == .5
    assert before["persistence"]["n"] == 0 and before["scripted_comparable"]["n"] == 0
    path = tmp_path / "model.pt"
    checksum = save_checkpoint(path, policy, examples, code_sha256="f" * 64,
                               training_config={"epochs": 80, "seed": 0, "device": "cpu"})
    loaded = load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY, offline=True)
    assert evaluate(loaded, examples, val) == before
    consumer = LearnedRangeBrain(loaded)
    memory = Memory()
    for snapshot in val[1].history:
        result = consumer(snapshot.state, memory)
    assert isinstance(result, Engage) and consumer.source == "range_learned"
    with pytest.raises(DemoError, match="offline only"):
        load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY)
    with pytest.raises(DemoError, match="identity"):
        load_checkpoint(path, expected_sha256=checksum, expected_identity=replace(IDENTITY, patch="new"), offline=True)
    with pytest.raises(DemoError, match="digest"):
        load_checkpoint(path, expected_sha256="0" * 64, expected_identity=IDENTITY, offline=True)
    with pytest.raises(FileExistsError):
        save_checkpoint(path, policy, examples, code_sha256="f" * 64, training_config={})


@pytest.mark.parametrize("corruption", ["format", "features", "actions", "nan", "shape", "support"])
def test_malformed_checkpoints_fail_before_consumer(fitted, tmp_path, corruption):
    import torch
    policy, examples = fitted
    path = tmp_path / "model.pt"
    save_checkpoint(path, policy, examples, code_sha256="f" * 64, training_config={})
    blob = torch.load(path, weights_only=True)
    if corruption in ("format", "features", "actions"):
        blob[corruption] = "keyboard_mouse"
    elif corruption == "nan":
        blob["weights"]["head.bias"][0] = math.nan
    elif corruption == "shape":
        blob["weights"]["head.bias"] = torch.ones(3)
    else:
        blob["support"] = [1, 0]
    torch.save(blob, path)
    with pytest.raises((DemoError, RuntimeError)):
        load_checkpoint(path, expected_sha256=fingerprint(path), expected_identity=IDENTITY, offline=True)


def test_train_val_baselines_unknowns_and_evidence_pin(fitted):
    policy, examples = fitted
    with pytest.raises(DemoError, match="train only"):
        train([example(split="val")], spec=SPEC)
    with pytest.raises(DemoError, match="both actions"):
        train([example(label="engage")], spec=SPEC)
    val = [replace(example(i, label, "val"), previous_label="idle", previous_known_t=0.,
                   scripted_label="engage") for i, label in enumerate(("idle", "engage", None))]
    report = evaluate(policy, examples, val)
    assert report["unknown_labels"] == 1
    assert report["model"]["support"] == [1, 1]
    assert report["persistence"]["accuracy"] == .5
    assert report["scripted_comparable"]["accuracy"] == .5
    changed = [replace(e, evidence="another training set") for e in examples]
    with pytest.raises(DemoError, match="evidence mismatch"):
        evaluate(policy, changed, val)


@pytest.fixture
def receipt_fixture(fitted, tmp_path):
    """Fabricated receipt metadata for loader tests; no human data or approval."""
    import torch
    policy, examples = fitted
    path = tmp_path / "receipt-test.pt"
    save_checkpoint(path, policy, examples, code_sha256="f" * 64, training_config={})
    payload = torch.load(path, weights_only=True)
    # Exercise the human-origin loader branch with synthetic bytes only.
    payload["origin"] = "reviewed_human"
    torch.save(payload, path)
    checksum = fingerprint(path)
    binding = DeploymentBinding(checksum, digest(asdict(IDENTITY)), RUNTIME, "6" * 64)
    return path, checksum, binding


@pytest.mark.parametrize("supply_runtime,supply_binding", [(False, False), (True, False), (False, True)])
def test_live_requires_separate_runtime_and_reviewed_checkpoint_binding(receipt_fixture,
                                                                      supply_runtime, supply_binding):
    path, checksum, binding = receipt_fixture
    with pytest.raises(DemoError, match="live load requires"):
        LearnedRangeBrain.from_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY,
                                          expected_runtime=RUNTIME if supply_runtime else None,
                                          deployment_binding=binding if supply_binding else None)


def test_valid_runtime_binding_preserves_distinct_source_provenance(receipt_fixture):
    path, checksum, binding = receipt_fixture
    loaded = LearnedRangeBrain.from_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY,
                                              expected_runtime=RUNTIME, deployment_binding=binding)
    assert loaded.policy.identity == IDENTITY
    assert loaded.policy.identity.settings_sha256 != RUNTIME.runtime_settings_sha256
    # A diagnostic candidate still loads offline without any deployment receipt.
    offline = load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY, offline=True)
    assert offline.identity == loaded.policy.identity


@pytest.mark.parametrize("field", ["runtime_settings_sha256", "calibration_sha256", "controller_code_sha256",
                                   "perception_sha256", "semantic_review_sha256", "patch", "cooldown_regime"])
def test_changed_runtime_profile_rejects_before_consumer(receipt_fixture, field):
    path, checksum, binding = receipt_fixture
    replacement = "7" * 64 if field.endswith("sha256") else "new-patch" if field == "patch" else "off"
    with pytest.raises(DemoError, match="runtime profile mismatch"):
        load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY,
                        expected_runtime=replace(RUNTIME, **{field: replacement}), deployment_binding=binding)


@pytest.mark.parametrize("field,message", [("checkpoint_sha256", "checkpoint binding"),
                                           ("source_identity_sha256", "source binding"),
                                           ("review_sha256", "binding hashes")])
def test_invalid_review_binding_rejects(receipt_fixture, field, message):
    path, checksum, binding = receipt_fixture
    value = "" if field == "review_sha256" else "0" * 64
    with pytest.raises(DemoError, match=message):
        load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY,
                        expected_runtime=RUNTIME, deployment_binding=replace(binding, **{field: value}))


@pytest.mark.parametrize("profile,message", [
    (replace(RUNTIME, runtime_settings_sha256=IDENTITY.settings_sha256), "KBM settings"),
    (replace(RUNTIME, input_domain="keyboard_mouse"), "virtual_pad domain"),
    (replace(RUNTIME, semantic_review_sha256=""), "semantic review hashes"),
    (replace(RUNTIME, patch="another"), "kit mismatch"),
])
def test_even_matching_binding_requires_real_pad_profile_fields(receipt_fixture, profile, message):
    path, checksum, binding = receipt_fixture
    with pytest.raises(DemoError, match=message):
        load_checkpoint(path, expected_sha256=checksum, expected_identity=IDENTITY,
                        expected_runtime=profile, deployment_binding=replace(binding, runtime=profile))


def test_binding_cannot_follow_changed_checkpoint_bytes(receipt_fixture):
    import torch
    path, checksum, binding = receipt_fixture
    payload = torch.load(path, weights_only=True)
    payload["weights"]["head.bias"][0] += .01
    torch.save(payload, path)
    assert fingerprint(path) != checksum
    with pytest.raises(DemoError, match="checkpoint binding mismatch"):
        load_checkpoint(path, expected_sha256=fingerprint(path), expected_identity=IDENTITY,
                        expected_runtime=RUNTIME, deployment_binding=binding)
