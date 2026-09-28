import hashlib
import json
from pathlib import Path

import pytest

from policy.range_bc import spatial_yaw_local as local
from policy.range_bc import spatial_yaw_train as runner


def test_cache_complete_reuses_verified_bytes_and_refuses_corruption(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    raw = b'{"sessions": []}'
    (source / "dataset.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    calls = []

    def copy(src, dst, pin):
        calls.append((src, pin))
        Path(dst).mkdir()
        (Path(dst) / "dataset.json").write_bytes(raw)
        return {"files": {"dataset.json": {"bytes": len(raw), "sha256": digest}},
                "bytes": len(raw), "seconds": 0, "source_and_destination_verified": True}

    monkeypatch.setattr(local, "copy_dataset", copy)
    dst = local.prepare_cache(source, digest, "b" * 64, parent=tmp_path)
    assert local.prepare_cache(source, digest, "b" * 64, parent=tmp_path) == dst
    assert len(calls) == 1
    (dst / "dataset.json").write_bytes(b'x' * len(raw))
    with pytest.raises(ValueError, match="bytes differ"):
        local.prepare_cache(source, digest, "b" * 64, parent=tmp_path)
    assert len(calls) == 1


def test_partial_and_wrong_identity_refused(tmp_path):
    root = tmp_path / ("yaw-fit-cache-" + "b" * 64)
    root.mkdir()
    with pytest.raises(ValueError, match="partial"):
        local.prepare_cache(tmp_path, "a" * 64, "b" * 64, parent=tmp_path)
    (root / "copy-complete.json").write_text(json.dumps({"identity": {}}))
    with pytest.raises(ValueError, match="identity"):
        local.prepare_cache(tmp_path, "a" * 64, "b" * 64, parent=tmp_path)


def test_both_stage_call_sites_use_local_cache_and_legacy_preserved(monkeypatch):
    import ast
    import inspect

    calls = []
    monkeypatch.setattr(local, "prepare_cache", lambda *a: calls.append(a) or "/local/verified")
    spec = {"dataset_root": "/inputs/cache", "dataset_sha256": "a" * 64, "grid": 8}
    assert runner.dataset_path(spec, "b" * 64) == "/inputs/cache"
    spec["cache_mode"] = "verified-local"
    assert runner.dataset_path(spec, "b" * 64) == "/local/verified"
    assert calls == [("/inputs/cache", "a" * 64, "b" * 64)]
    for function in (runner.fit, runner.evaluate):
        node = ast.parse(inspect.getsource(function))
        loaders = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == "load_dataset"]
        assert len(loaders) == 1
        assert isinstance(loaders[0].args[0], ast.Call)
        assert loaders[0].args[0].func.id == "dataset_path"
    spec["grid"] = 4
    with pytest.raises(Exception, match="cache mode"):
        runner.dataset_path(spec, "b" * 64)
