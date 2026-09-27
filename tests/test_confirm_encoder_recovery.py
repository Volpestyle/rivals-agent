"""No corpus: refuse partial/mismatched artifacts before evaluation-only recovery."""
import json

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
