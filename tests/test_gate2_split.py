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
