"""Synthetic only: no corpus, checkpoints, network or rented compute."""
import copy
import hashlib
import json
import sys

import pytest

from policy.range_bc import confirm_encoder_judge as j
from policy.range_bc import metrics, vocab


def evaluation(arm, seed, f=None, mae=None):
    candidate = arm == "candidate"
    recipe = {"tag": "CONFIRM", "seed": seed, "horizon": 1, "epochs": 26, "batch": 8,
              "lr": .0003, "weight_decay": .0001, "warmup": 500, "device": "cuda",
              "prev_dropout": .2, "lag": 0, "cohort": "full", "windows": 4697,
              "total_steps": 15288, "run_identity": j.INPUT_SHA + "0" * 64,
              "config": {**copy.deepcopy(j.CONFIG), "history": not candidate},
              "pos_weight": [[20.] * vocab.N] * 2,
              "encoder_explore": {"arm": "nitrogen", "prereg_sha256": "a" * 64,
                                  "history_input": "disabled" if candidate else "enabled",
                                  "assets": {"vision_sha256": j.VISION_SHA},
                                  "extraction": {k: {"frames": v} for k, v in j.FRAMES.items()}}}
    decode = {"F": (.3 if candidate else .2) if f is None else f,
              "S3_camera_mae": (1.1 if candidate else 1.3) if mae is None else mae,
              "S1_S2_S4": {"steps": 24556, "true_presses": 2458, "press_ratio": .92},
              "chance_floor": {"draws": 256, "seed": 20260927, "human_live_presses": 2458,
                               "human_edge_presses": 1437, "macro_f1_mean": .08,
                               "valid_steps": 24556, "window": {"early": 1, "late": 1},
                               "actions": list(vocab.EDGE_ACTIONS)}}
    return {"tag": "CONFIRM", "recipe": recipe, "epoch": 26, "skipped_decodes": [],
            "threshold_calibration": {"source": "TRAIN teacher-forced predictions only"},
            "decode": {k: copy.deepcopy(decode) for k in j.CONDITIONS},
            "references": {"frozen_dev": {"zero_motion": {
                "camera_mae_mean": j.ZERO, "camera": {"yaw": {"steps": 24556}}}}}}


def rows():
    return [(arm, seed, evaluation(arm, seed)) for arm in ("candidate", "control") for seed in j.SEEDS]


def test_joint_decision_and_fixed_cutoff_cannot_select_winner():
    data = rows()
    data[0][2]["decode"][j.SECONDARY]["F"] = 0
    out = j.judge(data)
    assert out["decision"] == "CONFIRMED"
    assert out["means"]["candidate"]["press_f1"] == pytest.approx(.3)
    assert out["human_live_press_events_per_frame"] == 2458 / 24556


@pytest.mark.parametrize("field,value,pass_field", [
    ("F", .2, "press_primary_pass"),  # one tie despite winning mean
    ("F", .1, "press_primary_pass"),  # one losing seed despite winning mean
    ("S3_camera_mae", j.ZERO, "camera_primary_pass"),
    ("S3_camera_mae", 1.4, "camera_primary_pass"),
])
def test_every_seed_must_win_and_zero_is_primary(field, value, pass_field):
    data = rows()
    data[0][2]["decode"][j.PRIMARY][field] = value
    out = j.judge(data)
    assert out["decision"] == "NOT_CONFIRMED" and not out[pass_field]


def test_improvement_below_incumbent_is_not_confirmation():
    data = rows()
    for arm, _, ev in data:
        ev["decode"][j.PRIMARY]["F"] = .1 if arm == "candidate" else .05
    assert not j.judge(data)["press_primary_pass"]


@pytest.mark.parametrize("case", ["missing", "duplicate", "seed0", "history", "config", "vision",
                                 "cohort", "stop", "skips", "nan", "denominator", "calibration",
                                 "chance", "prereg", "loss"])
def test_invalid_receipts_refuse_a_verdict(case):
    data = rows()
    ev = data[0][2]
    if case == "missing":
        data.pop()
    elif case == "duplicate":
        data.append(data[0])
    elif case == "seed0":
        data[0] = ("candidate", 0, ev)
    elif case == "history":
        ev["recipe"]["config"]["history"] = True
    elif case == "config":
        for _, _, e in data:
            e["recipe"]["config"]["hidden"] = 256
    elif case == "vision":
        ev["recipe"]["encoder_explore"]["assets"]["vision_sha256"] = "0" * 64
    elif case == "cohort":
        ev["recipe"]["encoder_explore"]["extraction"].pop(next(iter(j.FRAMES)))
    elif case == "stop":
        ev["stop_reason"] = "STOP"
    elif case == "skips":
        ev["skipped_decodes"] = ["fixed_0.5/mode"]
    elif case == "nan":
        ev["decode"][j.PRIMARY]["F"] = float("nan")
    elif case == "denominator":
        ev["decode"][j.PRIMARY]["S1_S2_S4"]["true_presses"] = 2457
    elif case == "calibration":
        ev["threshold_calibration"]["source"] = "DEV"
    elif case == "chance":
        ev["decode"][j.PRIMARY]["chance_floor"]["draws"] = 1
    elif case == "prereg":
        ev["recipe"]["encoder_explore"]["prereg_sha256"] = "b" * 64
    elif case == "loss":
        ev["recipe"]["pos_weight"] = [[1.] * vocab.N] * 2
    with pytest.raises(ValueError):
        j.judge(data)


def pair(human=False, pred=False, known=True, valid=True):
    return ({"valid": valid, "target": {"known": [known] * vocab.N,
                                        "press_known": [known] * vocab.N,
                                        "press": [int(human)] * vocab.N}},
            {"press": [float(pred)] * vocab.N})


def test_random_floor_exact_counts_masking_run_boundaries_and_determinism():
    runs = [[pair(True, True), pair(True, True, known=False), pair(True, True, valid=False)],
            [pair(True, False), pair(False, True)],
            [({"valid": False, "target": None}, {"press": [1.] * vocab.N})]]
    out = j.random_press_floor(runs, [True] * vocab.N, draws=8)
    assert out == j.random_press_floor(runs, [True] * vocab.N, draws=8)
    assert out["matched_predicted_counts"] == {n: [1, 1, 0] for n in vocab.EDGE_ACTIONS}
    assert out["human_live_presses"] == 2 * vocab.N
    assert out["human_edge_presses"] == 2 * len(vocab.EDGE_ACTIONS)
    assert out["human_any_press_frames"] == 2 and out["human_any_press_observable_frames"] == 3
    assert out["macro_f1_mean"] == 1.  # either location is within +/-1 in second run
    split = [[pair(True, False)], [pair(False, True)]]
    assert j.random_press_floor(split, [True] * vocab.N, draws=8)["macro_f1_mean"] == 0.


def test_random_floor_uniform_sampling_and_one_to_one():
    # Every position predicts, so sampling cannot alter the score: 1 TP, 2 FP.
    runs = [[pair(False, True), pair(True, True), pair(False, True)]]
    out = j.random_press_floor(runs, [True] * vocab.N, draws=8)
    assert out["macro_f1_mean"] == metrics.f1(1, 2, 0) == .5
    with pytest.raises(ValueError):
        j.random_press_floor([], [True] * vocab.N)


def test_cli_authenticates_sources_prereg_and_terminal_collection(tmp_path, monkeypatch):
    prereg = tmp_path / "prereg.md"
    prereg.write_text("synthetic prereg\n")
    spec = {"judge_sha256": j.source_sha(j.__file__),
            "dependency_sha256": {m.__name__: j.source_sha(m.__file__) for m in (metrics, vocab)},
            "preregistration": str(prereg), "prereg_sha256": j.source_sha(prereg), "runs": []}
    for arm, seed, ev in rows():
        ev["recipe"]["encoder_explore"]["prereg_sha256"] = spec["prereg_sha256"]
        ep, fp = tmp_path / f"{arm}-{seed}.json", tmp_path / f"{arm}-{seed}-final.json"
        ep.write_text(json.dumps(ev))
        sha = hashlib.sha256(ep.read_bytes()).hexdigest()
        fp.write_text(json.dumps({"exit": 0, "teardown": {"terminal": True},
                                  "collection": {"evaluation.json": {"sha256": sha}}}))
        spec["runs"].append({"arm": arm, "seed": seed, "evaluation": str(ep), "evaluation_sha256": sha,
                             "final": str(fp), "final_sha256": hashlib.sha256(fp.read_bytes()).hexdigest()})
    manifest, out = tmp_path / "runs.json", tmp_path / "judgement.json"
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(sys, "argv", ["judge", "--runs", str(manifest), "--out", str(out)])
    j.main()
    assert json.loads(out.read_text())["decision"] == "CONFIRMED"
    with pytest.raises(FileExistsError):
        j.main()
    prereg.write_text("changed\n")
    with pytest.raises(ValueError, match="prereg pin"):
        j.main()
