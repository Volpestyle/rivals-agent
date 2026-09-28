"""Consumer seam tests; no real admission metadata, stores, cloud or GPU."""
import json
from pathlib import Path

import pytest

pytest.importorskip("torch")
pytest.importorskip("numpy")

from policy.idm import resumable_run as R


def test_local_store_mapping_keeps_relative_paths_and_roles(tmp_path):
    source, local = tmp_path / "inputs", tmp_path / "local"
    for root in (source, local):
        (root / "stores" / "session").mkdir(parents=True)
    item = {"store": str(source / "stores/session"), "role": "heldout", "frames_sha256": "a"*64}
    target = object()
    mapped = R.relocate([(item, target)], local, source)
    assert mapped == [({**item, "store": str(local / "stores/session")}, target)]
    assert item["store"] == str(source / "stores/session")
    with pytest.raises(ValueError, match="local disk"):
        R.relocate([(item, target)], source, source)
    with pytest.raises(ValueError, match="outside admitted"):
        R.relocate([({**item, "store": str(local)}, target)], local, source)


@pytest.mark.parametrize("phase", ["fit", "camera", "zero"])
def test_commit_and_resume_reach_compute_with_nonfatal_status(tmp_path, monkeypatch, phase):
    root = tmp_path / phase
    root.mkdir()
    identity = {"inputs_sha256": "a"*64, "recipe_sha256": "b"*64, "code_sha256": "c"*64}
    (root / "started.json").write_text(json.dumps({"identity": identity}))
    loaded = [(object(), object())]
    monkeypatch.setattr(R.cloud_run, "load_inputs", lambda **kw: (None, loaded, None, None))
    monkeypatch.setattr(R.R.D, "require_disjoint_roles", lambda _: None)
    monkeypatch.setattr(R.R.E, "require_decode_platform", lambda _: None)
    monkeypatch.setattr(R, "relocate", lambda value, path: value)
    def status_failure(*a, **k):
        raise OSError("dashboard unavailable")
    monkeypatch.setattr(R.R, "write", status_failure)
    calls = []
    commit = lambda: None
    state = {"receipt": "epoch.complete.json", "sha256": "d"*64} if phase == "fit" else None
    def compute(path, stage, inputs, **kwargs):
        assert path == root and stage == phase and inputs is loaded
        assert kwargs["commit"] is commit and kwargs["resume_state"] is state
        kwargs["progress"]({"n": 1, "total": 2})
        calls.append(kwargs)
        return 0
    monkeypatch.setattr(R.R, "compute", compute)
    assert R.run(root, phase=phase, manifest="unused", manifest_sha256="a"*64, registry="unused",
                 input_volume_id="vo-input", output_volume_id="vo-output", scientific_identity=identity,
                 commit=commit, resume_state=state, local_data_root="/tmp/local") == 0
    assert len(calls) == 1


def test_scientific_mismatch_refuses_before_input_access(tmp_path, monkeypatch):
    root = tmp_path / "fit"
    root.mkdir()
    (root / "started.json").write_text(json.dumps({"identity": {}}))
    monkeypatch.setattr(R.cloud_run, "load_inputs", lambda **_: pytest.fail("must refuse before input read"))
    with pytest.raises(ValueError, match="scientific"):
        R.run(root, phase="fit", manifest="unused", manifest_sha256="a"*64, registry="unused",
              input_volume_id="vo-input", output_volume_id="vo-output", scientific_identity={})


@pytest.mark.parametrize("route", ["local", "stage"])
def test_legacy_callback_status_failure_is_warn_only(tmp_path, monkeypatch, route):
    from policy.idm import local_run, refit_stages
    root = tmp_path / ("local" if route == "local" else "fit")
    root.mkdir()
    (root / "started.json").write_text(json.dumps({"identity": {
        "inputs_sha256": "a"*64, "attempt_id": "synthetic"}}))
    monkeypatch.setattr(R.cloud_run, "load_inputs", lambda **kw: (None, [], None, None))
    monkeypatch.setattr(refit_stages.D, "require_disjoint_roles", lambda _: None)
    monkeypatch.setattr(refit_stages.E, "require_decode_platform", lambda _: None)
    def broken(*a, **kw):
        raise OSError("status failure")
    monkeypatch.setattr(refit_stages, "write", broken)
    def prepare(value, **kw):
        kw["progress"]({"phase": "copy"})
        return value, {"verified": True}
    monkeypatch.setattr(local_run.local_store, "prepare", prepare)
    def compute(*a, **kw):
        kw["progress"]({"n": 1, "total": 2})
        return 0
    monkeypatch.setattr(refit_stages, "compute", compute)
    kwargs = dict(manifest="unused", manifest_sha256="a"*64, registry="unused",
                  input_volume_id="vo-input", output_volume_id="vo-output")
    if route == "local":
        assert local_run.run(root, phase="local", **kwargs) == 0
    else:
        assert refit_stages.stage(root, phase="fit", **kwargs) == 0
