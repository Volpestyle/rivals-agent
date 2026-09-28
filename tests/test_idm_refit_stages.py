"""Shared-guard stage recovery and scientific handoff, synthetic pixels only."""
import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from cloud.modal_guard import stages
from cloud.modal_guard.common import Refused
from policy.idm import refit_stages as R
from policy.range_bc import vocab
from test_idm_explore import targets


@pytest.fixture
def rig(tmp_path, monkeypatch):
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    loaded = [({"role": role, "targets_sha256": "a" * 64}, targets(sid=sid, n=80))
              for role, sid in (("train", "synthetic-train"), ("heldout", "synthetic-dev"))]
    support = dict.fromkeys(vocab.NAMES, True)

    class Model:
        config = SimpleNamespace(differences=16, height=1, width=1)
        def eval(self):
            return self
        def __call__(self, motion, hud):
            score = motion.mean((1, 2, 3)) * 4 - 2
            return score[:, None].expand(-1, vocab.N), None
    model = Model()
    model.support = support

    class Examples:
        def __init__(self, sets, config, supported):
            self.items = [(target, None, row, None) for target, _ in sets for row in target.rows]
            self.press = torch.tensor([r["press"] for _, _, r, _ in self.items], dtype=torch.float32)
            self.press_mask = torch.tensor([r["held_known"] for _, _, r, _ in self.items])
        def __len__(self):
            return len(self.items)
        def inputs(self, idx):
            return (torch.ones(len(idx), 16, 1, 1), torch.ones(len(idx), 6, 80, 200))

    fit_calls = []
    def fit(inputs, *, out, **kwargs):
        fit_calls.append(kwargs)
        (out / "refit.pt").write_bytes(b"synthetic completed checkpoint")
        return {"checkpoint_sha256": R.T.sha256(out / "refit.pt"),
                "history": [{"epoch": i, "train_loss": .2} for i in range(3)]}
    monkeypatch.setattr(R.E, "refit", fit)
    monkeypatch.setattr(R.E, "require_decode_platform", lambda _: "synthetic")
    monkeypatch.setattr(R, "sessions", lambda data, role: (
        [(target, None) for item, target in data if item["role"] == role], {}))
    monkeypatch.setattr(R.TR, "Examples", Examples)
    monkeypatch.setattr(R.TR, "load_checkpoint", lambda *a, **k: (model, {
        "meta": {"targets": {t.session_id: {"sha256": item["targets_sha256"]} for item, t in loaded}},
        "model": {"weight": torch.zeros(1)}}))
    monkeypatch.setattr(R.TR, "gate1", lambda *a, **k: {"synthetic": True})
    identity = {"attempt_id": "synthetic-attempt", "code_sha256": "1"*64,
                "inputs_sha256": "2"*64, "recipe_sha256": "3"*64,
                "output_volume_id": "vo-synthetic"}

    def run(phase):
        return stages.run(tmp_path / phase, phase, identity, R.ARTIFACTS[phase],
            lambda path: R.compute(path, phase, loaded, device="cpu", manifest_sha256="4"*64,
                                   progress=lambda _: None), commit=lambda: None, reload=lambda: None)
    yield SimpleNamespace(run=run, root=tmp_path, calls=fit_calls, loaded=loaded, identity=identity, model=model)
    torch.set_num_threads(before)


def test_complete_fit_reentry_skips_fit_then_finishes_report(rig):
    first = rig.run("fit")
    assert rig.run("fit") == first
    assert len(rig.calls) == 1 and rig.calls[0]["evaluate"] is False
    for phase in list(R.ARTIFACTS)[1:]:
        rig.run(phase)
    report = json.loads((rig.root / "report/report.json").read_text())
    assert set(report["controls"]) == {"real", "zero_visuals"}
    assert report["heldout_rows"] == 80
    assert report["calibration"]["sessions"] == ["synthetic-train"]
    real = np.load(rig.root / "real/probabilities.npy")
    zero = np.load(rig.root / "zero/probabilities.npy")
    assert (real > zero).all()
    assert (rig.root / "real/row-ids.json").read_bytes() == (rig.root / "zero/row-ids.json").read_bytes()
    rig.run("report")
    assert len(rig.calls) == 1


def test_partial_fit_never_retrains(rig):
    (rig.root / "fit").mkdir()
    (rig.root / "fit/refit.pt").write_bytes(b"partial")
    with pytest.raises(Refused, match="partial"):
        rig.run("fit")
    assert rig.calls == []


def test_changed_completed_checkpoint_refused(rig):
    rig.run("fit")
    (rig.root / "fit/refit.pt").write_bytes(b"changed")
    with pytest.raises(Refused, match="hash mismatch"):
        rig.run("camera")
    assert len(rig.calls) == 1


def test_zero_stage_does_not_open_stores(rig, monkeypatch):
    for phase in ("fit", "calibration", "real"):
        rig.run(phase)
    monkeypatch.setattr(R, "sessions", lambda *a: pytest.fail("zero pass read pixels"))
    rig.run("zero")


def test_real_requires_completed_train_calibration(rig):
    rig.run("fit")
    with pytest.raises(Refused, match="partial"):
        rig.run("real")


@pytest.mark.parametrize("rows", [
    [["synthetic-dev", 0]], [["synthetic-train", 0], ["synthetic-train", 0]],
    [["synthetic-train", 9999]],
])
def test_saved_labels_refuse_role_overlap_duplicate_or_missing_rows(rig, rows):
    with pytest.raises(ValueError):
        R.selected(rig.loaded, rows, "train", rig.model.support)


def test_report_refuses_changed_score_payload(rig):
    for phase in ("fit", "camera", "calibration", "real", "zero"):
        rig.run(phase)
    np.save(rig.root / "zero/probabilities.npy", np.zeros((80, 3), dtype=np.float32))
    with pytest.raises(Refused, match="hash mismatch"):
        rig.run("report")


def resign(rig, phase, filename):
    """Simulate a producer that completed and hashed semantically wrong output."""
    path = rig.root / phase / filename
    marker = rig.root / phase / "completed.json"
    receipt = json.loads(marker.read_text())
    receipt["artifacts"][filename] = {"bytes": path.stat().st_size, "sha256": R.T.sha256(path)}
    marker.write_text(json.dumps(receipt))


def test_report_refuses_completed_but_reordered_zero_rows(rig):
    for phase in ("fit", "camera", "calibration", "real", "zero"):
        rig.run(phase)
    path = rig.root / "zero/row-ids.json"
    path.write_text(json.dumps(list(reversed(json.loads(path.read_text())))))
    resign(rig, "zero", "row-ids.json")
    with pytest.raises(ValueError, match="row order mismatch"):
        rig.run("report")


def test_incomplete_epoch_history_refuses_even_when_hashed(rig):
    rig.run("fit")
    path = rig.root / "fit/fit.json"
    report = json.loads(path.read_text())
    report["history"].pop()
    path.write_text(json.dumps(report))
    resign(rig, "fit", "fit.json")
    with pytest.raises(ValueError, match="incomplete fit history"):
        rig.run("camera")


def test_actual_tiny_fit_saves_reloadable_checkpoint_without_evaluation(tmp_path, monkeypatch):
    from test_idm_model import session, TINY
    loaded = []
    for role in ("train", "heldout"):
        target, store, path = session(tmp_path, "tiny-"+role, n=36)
        manifest_path = store.directory / "frames.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["decode"] = {"platform": "synthetic"}
        manifest_path.write_text(json.dumps(manifest))
        loaded.append(({"role": role, "store": str(store.directory), "targets_sha256": R.T.sha256(path),
                        "frames_sha256": R.T.sha256(manifest_path)}, target))
    monkeypatch.setattr(R.E, "CameraConfig", lambda: TINY)
    monkeypatch.setattr(R.T, "check_cohort", lambda *a: {"synthetic": True})
    monkeypatch.setattr(R.T, "load_patch_equivalence", lambda: {})
    monkeypatch.setattr(R.TR, "gate1", lambda *a, **k: pytest.fail("fit must complete before camera evaluation"))
    out = tmp_path / "fit"
    out.mkdir()
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        report = R.E.refit(loaded, out=out, seed=0, epochs=1, device="cpu", progress=lambda _: None,
                           evaluate=False)
    finally:
        torch.set_num_threads(before)
    _, payload = R.TR.load_checkpoint(out / "refit.pt")
    assert report["checkpoint_sha256"] == R.T.sha256(out / "refit.pt")
    assert report["gate1_diagnostic"] is None
    assert len(report["history"]) == 1 and payload["meta"]["seed"] == 0
