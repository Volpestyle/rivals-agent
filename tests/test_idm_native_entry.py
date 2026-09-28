"""No media, network, CUDA or resource provisioning in native bridge checks."""
import json
from types import SimpleNamespace

import pytest

from policy.idm import native_entry as N


def packet(tmp_path):
    payload = tmp_path / "idm_payload"
    (payload / "policy").mkdir(parents=True)
    source = payload / "policy/worker.py"
    source.write_text("# synthetic source\n")
    manifest = {"format": "idm-native-payload-v1", "files": {"policy/worker.py": N.digest(source)}}
    path = tmp_path / "idm-payload-manifest.json"
    path.write_text(json.dumps(manifest))
    return payload, path, N.digest(path)


def test_payload_and_generated_bytecode(tmp_path):
    payload, _, pin = packet(tmp_path)
    (payload / "policy/__pycache__").mkdir()
    (payload / "policy/__pycache__/worker.pyc").write_bytes(b"compiled")
    assert N.verify_payload(tmp_path, pin)[0] == payload


@pytest.mark.parametrize("change", ["manifest", "source", "extra", "missing"])
def test_changed_closure_refuses(tmp_path, change):
    payload, manifest, pin = packet(tmp_path)
    if change == "manifest":
        manifest.write_text("{}")
    elif change == "source":
        (payload / "policy/worker.py").write_text("changed")
    elif change == "extra":
        (payload / "policy/extra.py").write_text("extra")
    else:
        (payload / "policy/worker.py").unlink()
    with pytest.raises(ValueError, match="differ"):
        N.verify_payload(tmp_path, pin)


def test_payload_escape_refuses(tmp_path):
    _, path, _ = packet(tmp_path)
    doc = json.loads(path.read_text())
    doc["files"] = {"../outside.py": "a" * 64}
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        N.verify_payload(tmp_path, N.digest(path))


def test_imported_foreign_package_refuses(tmp_path):
    with pytest.raises(ValueError, match="already imported"):
        N.activate(tmp_path)


def test_input_namespace_refuses_without_read(monkeypatch):
    monkeypatch.setattr(N, "digest", lambda _: pytest.fail("must refuse before reading"))
    for path in ("relative.json", "/outputs/manifest.json", "/inputs/../outside.json"):
        with pytest.raises(ValueError, match="outside"):
            N.input_ref({"path": path, "sha256": "a" * 64})


@pytest.mark.parametrize("phase", ["probe", "fit", "zero"])
def test_dispatch_only_selected_callback(tmp_path, monkeypatch, phase):
    calls = []
    worker = SimpleNamespace(ARTIFACTS={"fit": [], "zero": []},
        probe=lambda root, **kw: calls.append(("probe", root, kw)) or 0,
        stage=lambda root, **kw: calls.append(("stage", root, kw)) or 0)
    manifest = {"inputs": {"path": "/inputs/manifest.json", "sha256": "a" * 64},
                "registry": {"path": "/inputs/registry.json", "sha256": "b" * 64}}
    monkeypatch.setattr(N, "verify_payload", lambda *_: (tmp_path, manifest))
    monkeypatch.setattr(N, "activate", lambda _: None)
    monkeypatch.setattr(N.importlib, "import_module", lambda name: worker)
    monkeypatch.setattr(N, "input_ref", lambda ref: ref["path"])
    assert N.run(tmp_path / phase, payload_manifest_sha256="c" * 64, phase=phase,
                 input_volume_id="vo-input", output_volume_id="vo-output") == 0
    assert len(calls) == 1 and calls[0][0] == ("probe" if phase == "probe" else "stage")
    assert calls[0][2]["manifest_sha256"] == "a" * 64
    if phase != "probe":
        assert calls[0][2]["phase"] == phase


def test_guarded_fit_redelivery_still_uses_completed_stage(tmp_path):
    from cloud.modal_guard import stages
    calls = []
    identity = dict(attempt_id="idm-native-test", code_sha256="a" * 64,
                    inputs_sha256="b" * 64, recipe_sha256="c" * 64,
                    output_volume_id="vo-test")
    def compute(root):
        calls.append(root)
        (root / "fit.json").write_text("{}")
        return 0
    for _ in range(2):
        stages.run(tmp_path / "fit", "fit", identity, ["fit.json"], compute,
                   commit=lambda: None, reload=lambda: None)
    assert len(calls) == 1
