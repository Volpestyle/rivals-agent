"""Confirmation preparation is local only; the reviewed spend functions are reused."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1] / "docs/evidence/nitrogen-nohistory-confirm-20260927/launch"


def module(name, root=ROOT):
    spec = importlib.util.spec_from_file_location(name, root / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_six_disjoint_authenticated_configs_and_funded_guard(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    prepare = module("prepare_confirm")
    archive, prereg = tmp_path / "code.tar", tmp_path / "prereg.md"
    archive.write_bytes(b"synthetic archive")
    prereg.write_bytes(b"synthetic prereg\n")
    root = tmp_path / "campaign"
    receipt = prepare.prepare(root, prereg, archive, "synthetic")
    assert not receipt["launched"] and len(receipt["runs"]) == 6
    names, volumes, reserved = set(), set(), 0.
    for dirname in receipt["runs"]:
        dest = Path(dirname)
        budget = module("encoder_budget", dest)
        names.add(budget.APP_NAME)
        volumes.add(budget.OUTPUT_VOLUME)
        value = budget.reservation(wall=10000, mono=5000)
        assert value["lifetime_seconds"] == 3594 and value["function_timeout_seconds"] == 3174
        assert not budget.expired(value, wall=10000, mono=5000)
        assert budget.expired(value, wall=value["stop_at_unix"], mono=5000)
        assert budget.expired(value, wall=10000, mono=value["stop_monotonic"])
        reserved += value["reserved_usd"]
        # The worker validates history, paired seed, unique names, and the prereg pin.
        worker = module("encoder_worker", dest)
        config_path = dest / "run-config.json"
        sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
        config = worker.load_run_config(config_path, sha, "nitrogen")
        assert config["prereg_sha256"] == receipt["prereg_sha256"]
        pins = json.loads((dest / "runner-manifest.json").read_text())
        assert pins["image"]["id"] == "im-FNjy4v5u4XYF29SBGvT0KD"
        assert all(hashlib.sha256((dest / n).read_bytes()).hexdigest() == s for n, s in pins["files"].items())
        with pytest.raises(AssertionError):
            worker.load_run_config(config_path, "0" * 64, "nitrogen")
    assert len(names) == len(volumes) == 6 and reserved == pytest.approx(19.97950176)
    with pytest.raises(FileExistsError):
        prepare.prepare(root, prereg, archive, "synthetic")


def test_guard_functions_are_the_reviewed_ast():
    tree = ast.parse((ROOT / "encoder_budget.py").read_text())
    nodes = [ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, ast.FunctionDef)]
    # Computed from the completed, reviewed no-history guard before copying it.
    assert hashlib.sha256("\n".join(nodes).encode()).hexdigest() == "e79032c7b5ffa9226e667d867937d5f582960c1d5081d4b98d352d6b90985d6c"
