"""Synthetic checks for the next-launch copies; never imports Modal or opens data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1] / "docs/evidence/explore-encoder-20260927/launch-fixes"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("history", ["enabled", "disabled"])
def test_config_mode_is_authenticated(tmp_path, monkeypatch, history):
    stub = ModuleType("explore_mounts")
    stub.check_mounts = stub.logical_path = None
    monkeypatch.setitem(sys.modules, "explore_mounts", stub)
    worker = module("encoder_worker")
    p = tmp_path / "run-config.json"
    config = {"arm": "nitrogen", "history": history}
    p.write_text(json.dumps(config))
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert worker.load_run_config(p, sha, "nitrogen") == config
    with pytest.raises(AssertionError):
        worker.load_run_config(p, sha, "siglip")
    p.write_text(json.dumps({**config, "history": "invalid"}))
    with pytest.raises(AssertionError):
        worker.load_run_config(p, sha, "nitrogen")
    with pytest.raises(AssertionError):
        worker.load_run_config(p, hashlib.sha256(p.read_bytes()).hexdigest(), "nitrogen")


def test_manifest_pins_config_files_and_immutable_image(tmp_path):
    prepare = module("prepare_manifest")
    for name in prepare.FILES:
        (tmp_path / name).write_text("fixture")
    config = {"arm": "nitrogen", "history": "enabled"}
    (tmp_path / "run-config.json").write_text(json.dumps(config))
    result = prepare.manifest(tmp_path, commit="fixture", brief_cap=12, arm_cap=6)
    assert result["run_config"] == config
    assert result["image"]["id"] == "im-FNjy4v5u4XYF29SBGvT0KD"
    assert result["image"]["packages"]["transformers"] == "4.57.1"
    assert all(result["files"][n] == hashlib.sha256((tmp_path / n).read_bytes()).hexdigest()
               for n in prepare.FILES)
    with pytest.raises(ValueError):
        prepare.manifest(tmp_path, commit="fixture", brief_cap=5, arm_cap=6)
