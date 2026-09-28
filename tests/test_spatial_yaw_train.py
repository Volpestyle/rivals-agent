"""CPU synthetic science-path checks: no admitted payloads or cloud calls."""
import copy
import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from cloud.modal_guard import stages as guarded_stages
from cloud.modal_guard.common import Refused
from policy.range_bc import fixture, steps, train, vocab
from policy.range_bc.explore_chunks import chunk_loss_terms
from policy.range_bc.explore_chunks_train import fit_chunks
from policy.range_bc.explore_encoder import EncoderPolicy
from policy.range_bc.model import Config
from policy.range_bc.spatial_yaw_cache import extract_session, frame_ids, sha
from policy.range_bc.spatial_yaw_data import SpatialArrays, SpatialBatches, export_labels, load_dataset
from policy.range_bc.spatial_yaw_eval import evaluate_model
from policy.range_bc.spatial_yaw_launch import stages
from policy.range_bc.spatial_yaw_report import markdown, summarize
from policy.range_bc.spatial_yaw_train import SpatialYawPolicy, tensor_digest


@pytest.fixture(autouse=True)
def cpu_only():
    torch.set_num_threads(2)


def source_array():
    header, rows = fixture.session("synthetic-yaw", runs=(8,), seed=4, unknown_mouse=0)
    session = steps.Session("synthetic", "a"*64, header, rows)
    frames = np.zeros((8, 2, 2, 3), dtype=np.uint8)
    return train.SessionArrays(session, (frames, frames, frames, list(range(8)), {}))


def test_fit_entry_matches_encoder_stride_before_loading_checkpoint(tmp_path, monkeypatch):
    from policy.range_bc import spatial_yaw_train as runner
    from policy.range_bc.explore_encoder import FeatureBatches

    # Metadata only: 4,704 train windows require 588 batches/epoch and
    # exactly 15,288 updates. The generic loader's stride 48 must fail here.
    arrays = [SimpleNamespace(runs=[(0, 96 + 64*4703)], press_windows=None)]
    dev = [SimpleNamespace(runs=[(0, 96 + 64*5)], press_windows=None)]
    expected = [FeatureBatches(x, stride=64).windows for x in (arrays, dev)]
    assert len(expected[0]) == 4704
    assert SpatialBatches(arrays).windows != expected[0]
    seen = []

    def batches(*args, **kwargs):
        value = SpatialBatches(*args, **kwargs)
        seen.append(value.windows)
        assert value.window == 96
        return value

    class CheckpointBoundary(Exception):
        pass

    def checkpoint(*args):
        assert seen == expected
        raise CheckpointBoundary

    monkeypatch.setattr(runner, "checked_spec", lambda *args: {
        "dataset_root": "unused", "dataset_sha256": "unused", "grid": 4,
        "base_checkpoint": "unused", "base_sha256": "unused", "seed": 1})
    monkeypatch.setattr(runner, "runtime", lambda: "cpu")
    monkeypatch.setattr(runner, "load_dataset", lambda *args: (arrays, dev, {}))
    monkeypatch.setattr(runner, "SpatialBatches", batches)
    monkeypatch.setattr(runner, "load_base", checkpoint)
    with pytest.raises(CheckpointBoundary):
        runner.fit(tmp_path, spec_path="unused", spec_sha256="unused")


def portable(tmp_path, grid):
    import hashlib
    arr = source_array()
    ids = frame_ids(arr)
    identity = {"session": arr.session.session_id, "steps_sha256": arr.session.sha256,
                "count": len(ids), "frame_ids_sha256": hashlib.sha256(ids.tobytes()).hexdigest()}
    def tower(pixel_values):
        return SimpleNamespace(last_hidden_state=torch.arange(256).float()[None, :, None]
                               .expand(len(pixel_values), -1, 1024) / 256)
    extract_session(arr, tower, tmp_path / arr.session.session_id, identity, lambda _: None, device="cpu")
    value = export_labels([arr], [], tmp_path)
    return arr, SpatialArrays(tmp_path, value["sessions"][0], grid), value


def test_portable_roundtrip_matches_masks_windows_mapping_and_corruption_refusal(tmp_path):
    original, packed, value = portable(tmp_path, 8)
    for key in ("act", "act_known", "camera", "camera_known", "valid", "prev", "regime", "row_frame"):
        assert torch.equal(getattr(original, key), getattr(packed, key))
    assert packed.session == original.session and packed.runs == original.runs
    g, _, _ = packed.frames(torch.tensor([7, 0, 7]))
    assert g.shape == (3, 81920) and torch.equal(g[0], g[2])
    assert export_labels([original], [], tmp_path) == value
    with (tmp_path / original.session.session_id / "labels.pt").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="hash differs"):
        SpatialArrays(tmp_path, value["sessions"][0], 8)


def test_allowlist_refuses_unknown_before_any_payload_open(tmp_path):
    value = {"format": "spatial-yaw-data-v1", "inputs_sha256": __import__(
        "policy.range_bc.spatial_yaw_cache", fromlist=["INPUTS"]).INPUTS,
        "sessions": [{"session": "unapproved", "role": "train"}]*10}
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="roster"):
        load_dataset(tmp_path, sha(path), 4)


@pytest.mark.parametrize("grid", (4, 8))
def test_real_tiny_fit_eval_reload_and_stage_reentry(tmp_path, grid):
    _, arr, _ = portable(tmp_path / "data", grid)
    batches = SpatialBatches([arr], window=4, stride=4, min_run=1, burn_in=0)
    stats = steps.train_statistics([arr.session])
    base = EncoderPolicy(Config(history=False, hud=False))
    before = tensor_digest(base)
    root = tmp_path / "fit"
    calls = []
    identity = {"attempt_id": "synthetic-yaw", "code_sha256": "a"*64,
                "inputs_sha256": "b"*64, "recipe_sha256": "c"*64,
                "output_volume_id": "vo-synthetic", "deadline_unix": 1000}
    def compute(dest):
        calls.append(1)
        model, _, status = fit_chunks(batches, base.config, stats, dest, dev=batches, seed=1, epochs=1,
            batch_size=1, warmup=0, device="cpu", model_factory=lambda *_: SpatialYawPolicy(base, grid))
        assert status == "complete" and tensor_digest(model.base) == before
        assert all(p.grad is None for p in model.base.parameters())
        assert model.yaw.out.weight.abs().sum() > 0
        result = evaluate_model(model, [arr], stats["live_mask"], [.5]*vocab.N, chunk=4)
        assert result["retention"]["exact_action_and_pitch_predictions"]
        assert result["retention"]["exact_pitch_logits"]
        payload = torch.load(dest / "epoch-1.pt", weights_only=True, map_location="cpu")
        model.load_state_dict(payload["model"], strict=True)
        assert result == evaluate_model(model, [arr], stats["live_mask"], [.5]*vocab.N, chunk=4)
        (dest / "evaluation.json").write_text(json.dumps(result))
        return 0
    args = (root, "fit", identity, ["epoch-1.pt", "evaluation.json"], compute)
    receipt = guarded_stages.run(*args, commit=lambda: None, reload=lambda: None, wall=lambda: 1)
    assert guarded_stages.run(*args, commit=lambda: None, reload=lambda: None, wall=lambda: 2) == receipt
    assert calls == [1]
    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises(Refused, match="partial"):
        guarded_stages.run(partial, *args[1:], commit=lambda: None, reload=lambda: None, wall=lambda: 3)
    assert calls == [1]


def test_paired_initialization_base_logits_loss_and_history_independence():
    base = EncoderPolicy(Config(history=False, hud=False))
    models = []
    for grid in (4, 8):
        torch.manual_seed(3)
        models.append(SpatialYawPolicy(base, grid))
    for (k, p), (j, q) in zip(models[0].yaw.named_parameters(), models[1].yaw.named_parameters()):
        assert k == j and torch.equal(p, q)
    global4 = torch.randn(1, 3, 16384)
    prev = torch.randn(1, 3, steps.PREV_DIM)
    with torch.no_grad():
        expected = base(global4, global4, None, prev)
    for model in models:
        packed = torch.cat((global4, torch.randn(1, 3, model.grid**2*1024)), -1)
        actions, camera, _ = model(packed, packed, None, prev)
        assert torch.equal(actions, expected[0]) and torch.equal(camera, expected[1])
        other = model(packed, packed, None, prev*99)
        assert torch.equal(actions, other[0]) and torch.equal(camera, other[1])
        target = {"act": torch.zeros_like(actions), "act_mask": torch.ones_like(actions, dtype=torch.bool),
                  "camera": torch.zeros(camera.shape[:-1], dtype=torch.long),
                  "camera_mask": torch.ones(camera.shape[:-1], dtype=torch.bool)}
        weights = torch.ones(2, vocab.N)
        chunk = model.forward_chunks(packed, packed, None, prev)
        a = train.total_loss(train.loss_terms(actions, camera, target, weights))
        b = train.total_loss(chunk_loss_terms(*chunk[:2], {"chunk_"+k: v.unsqueeze(2) for k,v in target.items()}, weights))
        assert torch.equal(a, b)


def results():
    rows = []
    for grid in (4, 8):
        for seed in (1, 2, 3):
            yaw = {k: {"n": 3, "mae_deg": 1 if grid == 4 else .9, "zero_motion_mae_deg": 2,
                       "false_turn_ge_point6_rate": .1} for k in ("all", "left", "right", "human_yaw_zero", "both_axes_zero")}
            rows.append({"spec": {"grid": grid, "seed": seed, "dataset_sha256": "a"*64, "base_sha256": str(seed)*64,
                                  "cutoff_sha256": "b"*64, "epochs": 26, "updates": 15288},
                         "base": {"unchanged": seed}, "fit": {"frozen_base_exact": True},
                         "retention": {"exact_action_and_pitch_predictions": True, "exact_pitch_logits": True},
                         "candidate": {"yaw": yaw, "metrics": {"macro_press_f1_tol": .3,
                                                    "camera": {"pitch": {"mae_deg": .6}}}}})
    return rows


def test_six_arm_report_filters_direction_still_retention_and_pairing():
    original = results()
    report = summarize(original)
    assert report["next"] == "propose fresh-seed confirm"
    assert "Left MAE" in markdown(report) and len(report["paired"]) == 3
    for subset, key, value in (("right", "mae_deg", 1.3), ("all", "mae_deg", 1),
                               ("human_yaw_zero", "false_turn_ge_point6_rate", .11),
                               ("both_axes_zero", "n", 0)):
        changed = copy.deepcopy(original)
        changed[-1]["candidate"]["yaw"][subset][key] = value
        assert summarize(changed)["next"] != "propose fresh-seed confirm"
    for mutate in (lambda r: r.pop(), lambda r: r[-1]["retention"].update(exact_pitch_logits=False),
                   lambda r: r[-1]["spec"].update(base_sha256="wrong")):
        changed = copy.deepcopy(original)
        mutate(changed)
        with pytest.raises(ValueError):
            summarize(changed)


def test_shared_stage_descriptor_matches_callback_artifacts():
    result = stages("/inputs/recipe.json", "a"*64)
    assert [s["name"] for s in result] == ["fit", "evaluation"]
    assert result[0]["artifacts"] == ["epoch-26.pt", "fit.json"]
    assert result[1]["function"] == "evaluate" and result[1]["artifacts"] == ["evaluation.json"]
    bridged = stages("/inputs/recipe.json", "a"*64, module="cloud.yaw_fit_entry", payload_manifest_sha256="b"*64)
    assert all(s["kwargs"]["payload_manifest_sha256"] == "b"*64 for s in bridged)


def test_bridge_verifies_source_before_dispatch_and_rejects_corruption(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    from pathlib import Path
    bridge = Path("docs/evidence/nitrogen-spatial-yaw-20260927/scientific-driver/yaw_fit_entry.py")
    cloud = tmp_path / "cloud"
    payload = cloud / "yaw_payload"
    payload.mkdir(parents=True)
    target = cloud / "yaw_fit_entry.py"
    target.write_bytes(bridge.read_bytes())
    source = payload / "worker.py"
    source.write_text("pinned synthetic worker")
    manifest = cloud / "yaw-payload-manifest.json"
    manifest.write_text(json.dumps({"files": {"worker.py": sha(source)}}))
    spec = importlib.util.spec_from_file_location("test_yaw_bridge", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    worker = SimpleNamespace(fit=lambda *a, **kw: calls.append((a, kw)) or 0)
    monkeypatch.setattr(module.importlib, "import_module", lambda name: worker)
    # Simulate the clean isolated source-mount process's package ownership.
    import sys
    monkeypatch.setitem(sys.modules, "policy", SimpleNamespace(__file__=str(payload / "policy/__init__.py")))
    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(__file__=str(payload / "agent/__init__.py")))
    monkeypatch.setattr(sys, "path", list(sys.path))
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert module.fit(tmp_path, payload_manifest_sha256=digest, spec_path="recipe", spec_sha256="a"*64) == 0
    assert len(calls) == 1
    source.write_text("changed")
    with pytest.raises(ValueError, match="payload bytes differ"):
        module.fit(tmp_path, payload_manifest_sha256=digest, spec_path="recipe", spec_sha256="a"*64)
    assert len(calls) == 1


def test_nll_ablation_and_both_cutoff_retention(tmp_path):
    _, arr, _ = portable(tmp_path, 8)
    model = SpatialYawPolicy(EncoderPolicy(Config(history=False, hud=False)), 8)
    stats = steps.train_statistics([arr.session])
    value = evaluate_model(model, [arr], stats["live_mask"], [.4]*vocab.N, chunk=4)
    # The zero-initialized residual makes the real/zero ablation exactly equal;
    # this also tests eligibility is counted independently from decode output.
    nll = value["spatial_token_ablation"]["yaw_nll"]
    assert nll["real"] == nll["zero_spatial"]
    assert nll["real"]["n"] == int((arr.valid & arr.camera_known[:, 0]).sum())
    for suffix in ("", "_fixed05"):
        assert value["base"+suffix]["metrics"]["actions"] == value["candidate"+suffix]["metrics"]["actions"]
        assert value["base"+suffix]["press_rates"] == value["candidate"+suffix]["press_rates"]
