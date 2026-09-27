"""The gate2 split (the IDM's replay-of-self pairs, lead 2026-09-26): every fit reader refuses it, as it refuses test."""
import json

import pytest

from policy import idm_targets as T
from policy.range_bc import fixture, steps
from tests import test_idm_targets as idm_tests


def test_the_range_bc_reader_refuses_a_gate2_table_before_any_row(tmp_path):
    path = tmp_path / "gate2.jsonl"
    path.write_text(json.dumps(fixture.header_for("pair-x", split="gate2")) + "\nthis is not json\n", encoding="utf-8")
    for allow_test in (False, True):   # stricter than test: not even allow_test opens it
        with pytest.raises(steps.StepError, match="unknown split 'gate2'"):
            steps.load(path, allow_test=allow_test)
    with pytest.raises(steps.StepError):
        steps.load_cohort([path], splits=("train", "val"))


def test_the_idm_reader_refuses_a_gate2_table_before_any_row(tmp_path):
    h = T.header_from(idm_tests.header(), steps_path=__file__, demo_path=__file__, demo_sha256="1" * 64)
    h["split"] = "gate2"
    path = tmp_path / "g.idm.jsonl"
    path.write_text(json.dumps(h) + "\nnot json\n", encoding="utf-8")
    with pytest.raises(T.TargetError, match="split 'gate2'"):
        T.load(path)


def test_idm_train_is_a_registry_split_that_range_bc_refuses(tmp_path):
    """Logged matches train the IDM (lead decision 2026-09-26): idm_train is unsealed in the registry and trainable,
    and the range policy never loads it (HUMAN_SPLITS does not name it)."""
    from agent import human_demos as hd
    from agent import human_intake as hi
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps(dict(schema_version=1, sessions=[
        dict(session_id="m1", session_group="m1", split="idm_train", video_path="m1.mkv")])))
    assert [p.split for p in hd.read_splits(reg)] == ["idm_train"]
    assert "idm_train" not in hd.SEALED_SPLITS and "idm_train" not in steps.HUMAN_SPLITS
    path = tmp_path / "m1.jsonl"
    path.write_text(json.dumps(fixture.header_for("m1", split="idm_train")) + "\nthis is not json\n", encoding="utf-8")
    with pytest.raises(steps.StepError, match="unknown split 'idm_train'"):
        steps.load(path)
    assert hi.assign_split({}, "m1", 10.0, kind="match") == "idm_train"
    assert hi.assign_split({}, "r1", 10.0) in ("train", "val", "test")
    assert hi.assign_split({"m1": ("idm_train", 10.0)}, "m1", 10.0) == "idm_train"


def test_idm_and_gate2_groups_never_move_a_range_allocation():
    """Review F1 (admission-review's reproduction, 2026-09-26): only train/val/test minutes size the 70/15/15 targets."""
    from agent import human_intake as hi
    groups = {"g1": ("train", 10.0), "sealed": ("test", 2.1)}
    assert hi.assign_split(groups, "new_range", 3) == "val"
    for extra in ({"match": ("idm_train", 20.0)}, {"pair": ("gate2", 40.0)},
                  {"match": ("idm_train", 500.0), "pair": ("gate2", 0.5)}):
        assert hi.assign_split({**groups, **extra}, "new_range", 3) == "val"
