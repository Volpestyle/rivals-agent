"""No corpus: refuse partial/mismatched artifacts before evaluation-only recovery."""
import json
import hashlib
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import confirm_encoder_recovery as recovery
from policy.range_bc.train import FitError


def fixture(root, *, epoch=26, status="complete", seed=1, history=False, finite=True):
    recipe = {"seed": seed, "config": {"history": history}, "encoder_explore": {
        "prereg_sha256": recovery.A1, "assets": {"vision_sha256": recovery.VISION}}}
    value = {"epoch": epoch, "updates": 15288, "status": status, "recipe": recipe,
             "model": {"weight": torch.tensor([1. if finite else float("nan")])}}
    for name in ("epoch-26.pt", "latest.pt"):
        torch.save(value, root / name)
    (root / "status.json").write_text(json.dumps({"epoch": epoch, "updates": 15288, "status": status}))
    calibration = {"source": "TRAIN teacher-forced predictions only", "thresholds": [.7] * 15}
    (root / "evaluation.json").write_text(json.dumps({"recipe": recipe, "threshold_calibration": calibration}))
    return {"arm": "candidate", "seed": 1, "files": {
        p.name: recovery.sha(p) for p in root.iterdir()}}, calibration


def test_complete_stage_returns_exact_original_train_calibration(tmp_path):
    pin, calibration = fixture(tmp_path)
    assert recovery.authenticate(tmp_path, pin) == calibration


@pytest.mark.parametrize("change", [{"epoch": 25}, {"status": "running"}, {"seed": 2},
                                    {"history": True}, {"finite": False}])
def test_refuses_incomplete_or_wrong_identity_even_with_valid_file_hashes(tmp_path, change):
    pin, _ = fixture(tmp_path, **change)
    with pytest.raises(FitError):
        recovery.authenticate(tmp_path, pin)


def test_refuses_changed_checkpoint_before_loading(tmp_path):
    pin, _ = fixture(tmp_path)
    (tmp_path / "epoch-26.pt").write_bytes(b"changed")
    with pytest.raises(FitError, match="changed recovery artifact"):
        recovery.authenticate(tmp_path, pin)


def test_refuses_different_final_tensors_even_when_each_file_is_pinned(tmp_path):
    pin, _ = fixture(tmp_path)
    path = tmp_path / "latest.pt"
    payload = torch.load(path, weights_only=True)
    payload["model"]["weight"] += 1
    torch.save(payload, path)
    pin["files"]["latest.pt"] = recovery.sha(path)
    with pytest.raises(FitError, match="changed final tensor"):
        recovery.authenticate(tmp_path, pin)


def test_same_session_name_does_not_allow_changed_steps_or_pixels():
    arr = SimpleNamespace(session=SimpleNamespace(session_id="synthetic", sha256="steps"),
                          manifest={"global_sha256": "original pixels"})
    pin = {"synthetic": {"steps_sha256": "steps", "cache_manifest_sha256": hashlib.sha256(
        json.dumps(arr.manifest, sort_keys=True).encode()).hexdigest()}}
    recovery.authenticate_cohort([arr], pin)
    arr.manifest["global_sha256"] = "changed pixels"
    with pytest.raises(FitError, match="cohort bytes differ"):
        recovery.authenticate_cohort([arr], pin)
    arr.manifest["global_sha256"] = "original pixels"
    arr.session.sha256 = "changed labels"
    with pytest.raises(FitError, match="cohort bytes differ"):
        recovery.authenticate_cohort([arr], pin)


def test_completed_feature_stage_refuses_partial_or_changed_artifacts(tmp_path):
    root = tmp_path / "features"
    root.mkdir()
    summary = {}
    for sid in recovery.DEV_IDS:
        folder = root / sid
        folder.mkdir()
        for name in ("global.npy", "crop.npy"):
            (folder / name).write_bytes(b"synthetic array bytes")
        (folder / "features.json").write_text("{}")
        summary[sid] = {"manifest_sha256": recovery.sha(folder / "features.json")}
    (root / "features.json").write_text(json.dumps(summary))
    value = {"stage": "frozen-dev-features", "exit": 0, "root": str(root), "inputs_sha256": "inputs",
             "vision_sha256": recovery.VISION, "graph": recovery.GRAPH, "device": "mps",
             "files": {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": recovery.sha(p)}
                       for p in root.rglob("*") if p.is_file()}}
    path = tmp_path / "stage.json"
    path.write_text(json.dumps(value))
    assert recovery.completed_features(path, recovery.sha(path), "inputs") == root
    with pytest.raises(FitError, match="identity differs"):
        recovery.completed_features(path, recovery.sha(path), "other cohort")
    pixel = next(root.rglob("global.npy"))
    pixel.write_bytes(b"corrupted array bytes")
    with pytest.raises(FitError, match="feature artifact changed"):
        recovery.completed_features(path, recovery.sha(path), "inputs")
    del value["files"][pixel.relative_to(root).as_posix()]
    path.write_text(json.dumps(value))
    with pytest.raises(FitError, match="partial feature stage"):
        recovery.completed_features(path, recovery.sha(path), "inputs")
