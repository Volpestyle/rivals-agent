"""Synthetic round-3 contract tests; no corpus, assets, network, accelerator or dev scores."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import cache, cm3, cm3_features as features, cm3_train as training, steps, train, vocab  # noqa: E402
from policy.range_bc import cm3_proof as proof, fixture  # noqa: E402


@pytest.fixture(autouse=True)
def bounded_threads():
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(before)


def manifest_by_name(model):
    return {row["name"]: row for row in cm3.tensor_manifest(model)["tensors"]}


@pytest.mark.parametrize("seed", (0, 1, 2))
def test_paired_initialization_reordering_dummy_and_ambient_rng(seed):
    manifests = {}
    state = torch.random.get_rng_state().clone()
    for arm in cm3.ARMS:
        model = cm3.Policy(cm3.Config(arm, seed))
        manifests[arm] = manifest_by_name(model)
    assert torch.equal(state, torch.random.get_rng_state())
    for arm in reversed(cm3.ARMS):
        cm3.initialized(seed, "dummy/branch", lambda: torch.nn.Linear(27, 19))
        assert manifest_by_name(cm3.Policy(cm3.Config(arm, seed))) == manifests[arm]
    for arm in ("W",):
        for name, value in manifests["H"].items():
            assert value == manifests[arm][name]
    for name, value in manifests["I"].items():
        if name.startswith(("core.", "actions.", "camera.")):
            assert value == manifests["H"][name]
    # Mutation control: an ambient construction stream shifts when a branch is inserted.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        first = torch.nn.Linear(576, 512).weight.clone()
        torch.manual_seed(seed)
        torch.nn.Linear(27, 19)
        shifted = torch.nn.Linear(576, 512).weight
        assert not torch.equal(first, shifted)


def test_seed_formula_tags_and_unregistered_parameters():
    raw = hashlib.sha256(b"range-bc-cm3-v1|seed=0|tag=init/core").digest()
    assert cm3.stream_seed(0, "init/core") == int.from_bytes(raw[:8], "little") & ((1 << 63) - 1)
    assert cm3.HEAD_TAGS == {"actions": "init/head/actions", "camera": "init/head/camera"}
    model = cm3.Policy()
    model.extra = torch.nn.Linear(1, 1)
    with pytest.raises(ValueError, match="unregistered"):
        cm3.tensor_manifest(model)


@pytest.mark.parametrize("arm", ("H", "I"))
def test_absent_history_invariant_without_bias_or_parameters(arm):
    model = cm3.Policy(cm3.Config(arm)).eval()
    assert not hasattr(model, "hist")
    feats = torch.randn(2, 3, 512)
    a = model.step(feats, torch.zeros(2, 3, steps.PREV_DIM))
    b = model.step(feats, torch.full((2, 3, steps.PREV_DIM), float("nan")))
    for x, y in zip(a[:2] + a[2], b[:2] + b[2]):
        assert torch.equal(x, y)


def test_weak_history_cpu_dropout_includes_known_and_evaluation_no_draw():
    prev = torch.ones(4, 96, steps.PREV_DIM)
    seed = cm3.stream_seed(0, "train/history-dropout")
    g1, g2 = (torch.Generator().manual_seed(seed) for _ in range(2))
    a = cm3.history_dropout(prev, g1, training=True)
    assert torch.equal(a, cm3.history_dropout(prev, g2, training=True))
    assert bool((a == a[..., :1]).all()) and 0 < int(a.sum()) < prev.numel()
    state = g1.get_state().clone()
    assert cm3.history_dropout(prev, g1, training=False) is prev
    assert torch.equal(state, g1.get_state())
    model = cm3.Policy(cm3.Config("W"))
    assert model.hist[-1].eps == 1e-5 and not model.hist[-1].elementwise_affine


def test_normalization_stress_and_trainable_impala():
    h = cm3.Policy().eval()
    raw = torch.randn(2, 3, cm3.FEATURE_DIM) * 1e6
    encoded = h.features(raw, raw, None, 2, 3, raw)
    assert bool(torch.isfinite(encoded).all())
    assert torch.allclose(encoded[..., :256].mean(-1), torch.zeros(2, 3), atol=1e-6)
    assert torch.allclose(encoded[..., :256].square().mean(-1), torch.ones(2, 3), atol=1e-5)
    i = cm3.Policy(cm3.Config("I"))
    g, c = torch.zeros(1, 1, 3, 144, 256), torch.zeros(1, 1, 3, 128, 128)
    i(g, c, None, torch.zeros(1, 1, steps.PREV_DIM))[0].sum().backward()
    assert all(p.requires_grad and p.grad is not None for p in i.global_enc.parameters())
    assert i.core.input_size == 576


def loss_batch():
    gen = torch.Generator().manual_seed(91)
    batch = {"act": torch.randint(0, 2, (2, 3, 3, vocab.N), generator=gen).float(),
             "act_mask": torch.rand(2, 3, 3, vocab.N, generator=gen) > .3,
             "camera": torch.randint(0, vocab.CAMERA_CLASSES, (2, 3, 2), generator=gen),
             "camera_mask": torch.rand(2, 3, 2, generator=gen) > .2}
    logits = (torch.randn(2, 3, 3, vocab.N, generator=gen),
              torch.randn(2, 3, 2, vocab.CAMERA_CLASSES, generator=gen))
    return batch, logits, torch.full((2, vocab.N), 3.)


def test_weighted_loss_original_denominators_and_unit_exactness():
    batch, logits, pw = loss_batch()
    old = train.loss_terms(*logits, batch, pw)
    unit = training.loss_terms(*logits, {**batch, "step_weight": torch.ones(2, 3)}, pw)
    idle = training.loss_terms(*logits, {**batch, "step_weight": torch.full((2, 3), .1)}, pw)
    for h in old:
        assert torch.equal(old[h], unit[h])
        assert torch.allclose(idle[h], old[h] * .1, atol=1e-7, rtol=1e-6)
        assert not torch.allclose(idle[h], old[h])  # catches reweighted denominator mutation
    weight = torch.tensor([[.1, 1, .1], [1, 1, .1]])
    mixed = training.loss_terms(*logits, {**batch, "step_weight": weight}, pw)
    # Hand accumulate every known scalar with its original denominator and BCE positive weight.
    for hi, head in enumerate(training.HEADS):
        numerator, denominator = 0., 0
        for b in range(2):
            for t in range(3):
                mask = batch["camera_mask"][b, t] if hi == 3 else batch["act_mask"][b, t, hi]
                for c in range(len(mask)):
                    if not mask[c]:
                        continue
                    denominator += 1
                    if hi == 3:
                        x = logits[1][b, t, c]
                        value = float(torch.logsumexp(x, 0) - x[batch["camera"][b, t, c]])
                    else:
                        x, y = float(logits[0][b, t, hi, c]), float(batch["act"][b, t, hi, c])
                        import math
                        value = (3 if hi and y else 1) * math.log1p(math.exp(-x if y else x))
                    numerator += float(weight[b, t]) * value
        assert float(mixed[head]) == pytest.approx(numerator / max(1, denominator), rel=2e-6)


def audit_batches():
    n = 160
    arr = SimpleNamespace(session=SimpleNamespace(session_id="synthetic", split="train"),
                          valid=torch.ones(n, dtype=torch.bool), act_known=torch.ones(n, 3, vocab.N, dtype=torch.bool),
                          camera_known=torch.ones(n, 2, dtype=torch.bool))
    return SimpleNamespace(arrays=[arr], windows=[(0, 0, 96, 0), (0, 64, 96, 0)], burn_in=32, has_windows=False)


def test_effective_gate_masked_idle_overlap_and_one_element():
    batches = audit_batches()
    weights = torch.ones(160)
    zero = training.effective_weight_audit(batches, [weights])
    assert zero["weighting_has_scored_effect"] is False
    weights[70] = .1    # scored once in first window, burn-in masks second occurrence
    active = training.effective_weight_audit(batches, [weights])
    assert active["totals"]["held"]["C"] == vocab.N
    assert active["totals"]["camera"]["C"] == 2
    weights[:] = 1
    weights[120] = .1
    batches.arrays[0].act_known[120] = False
    batches.arrays[0].camera_known[120] = False
    masked = training.effective_weight_audit(batches, [weights])
    assert masked["weighting_has_scored_effect"] is False   # Raw idle count alone gives the wrong disposition.
    batches.arrays[0].camera_known[120, 0] = True
    single = training.effective_weight_audit(batches, [weights])
    assert single["weighting_has_scored_effect"] is True and single["totals"]["camera"]["C"] == 1
    assert single["totals"]["camera"]["E_tenths"] == 10 * single["totals"]["camera"]["U"] - 9
    batches.windows.append(batches.windows[1])
    assert training.effective_weight_audit(batches, [weights])["totals"]["camera"]["C"] == 2


def test_window_order_all_arms_all_epochs_unchanged():
    batches = audit_batches()
    import random
    for seed in (0, 1, 2):
        for epoch in range(13):
            order, receipt = cm3.window_order(batches, seed, epoch)
            expected = list(range(len(batches.windows)))
            random.Random(seed * 1000003 + epoch).shuffle(expected)
            assert order == expected
            for _ in cm3.ARMS:
                cm3.history_dropout(torch.ones(1, 3, steps.PREV_DIM), torch.Generator().manual_seed(89), training=True)
                assert cm3.window_order(batches, seed, epoch)[1] == receipt


def test_preprocess_geometry_rgb_padding_and_pooling():
    global_rgb = torch.zeros(1, 144, 256, 3, dtype=torch.uint8)
    global_rgb[..., 0] = 255
    out = features.preprocess(global_rgb, "global")
    assert out.shape == (1, 3, 224, 224) and out.dtype == torch.float32
    assert torch.allclose(out[:, :, :49], torch.zeros(1, 3, 49, 224), atol=3e-7)
    assert torch.allclose(out[:, :, 175:], torch.zeros(1, 3, 49, 224), atol=3e-7)
    assert float(out[0, 0, 80, 80]) == pytest.approx((1 - .485) / .229)
    assert float(out[0, 2, 80, 80]) == pytest.approx(-.406 / .225)
    with pytest.raises(ValueError):
        features.preprocess(global_rgb.permute(0, 3, 1, 2), "global")
    with pytest.raises(ValueError):
        features.preprocess(global_rgb.float(), "global")
    tokens = torch.arange(257).float().view(1, 257, 1).expand(1, 257, 384)
    result = features.pool_tokens(tokens).reshape(1, 17, 384)
    assert result[0, 0, 0] == 0
    for row in range(4):
        for col in range(4):
            expected = sum(1 + (row * 4 + i) * 16 + col * 4 + j for i in range(4) for j in range(4)) / 16
            assert float(result[0, 1 + row * 4 + col, 0]) == expected


def test_frozen_train_survives_outer_train_without_assets():
    # Exercise the actual wrapper's mode/gradient guard with a stand-in backbone; no downloads.
    frozen = features.FrozenDino.__new__(features.FrozenDino)
    torch.nn.Module.__init__(frozen)
    frozen.backbone = torch.nn.Sequential(torch.nn.Linear(4, 4), torch.nn.Dropout(.5))
    frozen.backbone.requires_grad_(False)
    outer = torch.nn.Sequential(frozen)
    before = {k: v.clone() for k, v in frozen.state_dict().items()}
    outer.train()
    assert not frozen.training and not frozen.backbone.training
    assert all(not p.requires_grad for p in frozen.parameters())
    assert all(torch.equal(v, frozen.state_dict()[k]) for k, v in before.items())


def test_feature_cache_rehash_and_metadata_mutations(tmp_path):
    identity = {"role": "train", "frame_refs": [["synthetic", 1, 1, [1, 30]]], "row_frame": [0]}
    assets, backend = {"weights_sha256": features.WEIGHTS_SHA256}, {"device": "cpu"}
    raw = torch.zeros(1, cm3.FEATURE_DIM).numpy().astype("<f4").tobytes()
    m = {"format": features.FORMAT, "source": identity, "source_identity_sha256": cm3.digest(identity),
         "selected_frames": [0], "dtype": "<f4", "shape": [1, cm3.FEATURE_DIM], "graph": features.GRAPH,
         "assets": assets, "backend": backend, "outputs": {k: hashlib.sha256(raw).hexdigest() for k in ("global", "crop")}}
    for name in ("global", "crop"):
        (tmp_path / f"{name}.f32").write_bytes(raw)
    path = tmp_path / "manifest.json"
    def opened(obj):
        path.write_text(json.dumps(obj), encoding="utf-8")
        return features.open_features(tmp_path, manifest_sha256=steps.sha256(path), identity=identity,
                                      assets=assets, backend=backend)
    valid = opened(m)
    assert valid[0].dtype.str == "<f4" and not valid[0].flags.writeable
    del valid
    for key, bad in (("dtype", "<f2"), ("shape", [1, 384]), ("selected_frames", [0, 0]),
                     ("graph", {"source": "BGR"}), ("assets", {}), ("backend", {"device": "mps"})):
        mutant = {**m, key: bad}
        with pytest.raises(ValueError):
            opened(mutant)
    changed = deepcopy(m)
    changed["source"]["frame_refs"][0][2] += 1
    with pytest.raises(ValueError):
        opened(changed)
    (tmp_path / "global.f32").write_bytes(b"\x01" + raw[1:])
    with pytest.raises(ValueError, match="corrupt"):
        opened(m)


def test_source_role_and_bad_weights_refuse_before_output(tmp_path):
    session = SimpleNamespace(split="test")
    with pytest.raises(ValueError, match="role"):
        features.source_identity(session, tmp_path / "nonexistent", manifest_sha256="a" * 64, role="test")
    (tmp_path / "model.safetensors").write_bytes(b"bad")
    with pytest.raises(ValueError, match="weight size"):
        features.verify_assets(tmp_path, config_sha256="a" * 64)
    assert not (tmp_path / "output").exists()


def feature_arrays(tmp_path, *, split="train", arm="H", n=160):
    header, rows = fixture.session("synthetic", split="train", runs=(n,))
    path = fixture.write(tmp_path / (split + ".jsonl"), header, rows)
    session = steps.load(path)
    # Original Batches uses dimensions; cached-feature path never indexes these stand-ins.
    rgb = torch.zeros(n, 1, 1, 3, dtype=torch.uint8).numpy()
    original = train.SessionArrays(session, (rgb, rgb, rgb, list(range(n)), {}))
    scene = torch.randn(n, cm3.FEATURE_DIM, generator=torch.Generator().manual_seed(2)).numpy()
    identity = {"session_id": session.session_id, "steps_sha256": session.sha256,
                "role": split, "row_frame": list(range(n))}
    return training.FeatureArrays(original, (scene, scene, list(range(n)), {"source": identity}))


def test_cached_batches_masks_rows_unit_weights_and_eval_guard(tmp_path):
    arr = feature_arrays(tmp_path)
    weights = torch.full((160,), .1)
    h = training.Batches([arr], arm="H", weights=[weights])
    reference = train.Batches([arr], frames=False, stride=64)
    bh, old = h.batch([0, 1]), reference.batch([0, 1])
    assert h.windows == reference.windows
    for key in ("act", "act_mask", "camera", "camera_mask", "prev", "regime"):
        assert torch.equal(bh[key], old[key])
    assert torch.equal(bh["global"][0], torch.from_numpy(arr.scene_global[:96]))
    assert bool((bh["step_weight"] == .1).all())
    w = training.Batches([arr], arm="W", weights=[weights])
    with pytest.raises(ValueError, match="generator"):
        w.batch([0])
    with pytest.raises(ValueError, match="augmentations"):
        h.batch([0], jitter=.1)
    dev = feature_arrays(tmp_path, split="dev")
    with pytest.raises(ValueError, match="sidecar"):
        training.Batches([dev], arm="H", training=False, weights=[weights])
    evaluation = training.Batches([dev], arm="H", training=False)
    assert "step_weight" not in evaluation.batch([0])


def test_self_fed_future_true_labels_do_not_enter_cached_path(tmp_path):
    arr = feature_arrays(tmp_path, n=8)
    model = cm3.Policy(cm3.Config("W")).eval()
    first = train.predict_self(model, [arr], [True] * vocab.N, chunk=4)
    arr.prev[:] = 1000
    # The reported target records change, but the model's self-fed predictions must not.
    for row in arr.session.rows[2:]:
        row["held_end"] = [1 - v for v in row["held_end"]]
    second = train.predict_self(model, [arr], [True] * vocab.N, chunk=4)
    assert [[p for _, p in run] for run in first] == [[p for _, p in run] for run in second]


def test_fixed_unique_frame_sample_repeats_and_role_refuses():
    arrays = []
    for name, sha in zip(proof.TRAIN_SESSIONS, proof.TRAIN_TABLE_HASHES):
        arrays.append(SimpleNamespace(session=SimpleNamespace(session_id=name, sha256=sha, split="train"),
                                      lag=0, regimes=("normal",), runs=[(0, 80)],
                                      row_frame=torch.arange(40).repeat_interleave(2)))
    a = proof.sample_frames(arrays)
    assert a == proof.sample_frames(arrays)
    assert [len(x["frame_ids"]) for x in a["sessions"]] == [26, 26, 26, 25, 25]
    assert all(len(set(x["frame_ids"])) == len(x["frame_ids"]) for x in a["sessions"])
    arrays[0].session.split = "dev"
    with pytest.raises(ValueError, match="role"):
        proof.sample_frames(arrays)


def test_cpu_numerics_decision_boundaries_and_repeat_receipt():
    model = cm3.Policy().eval()
    g = torch.zeros(1, 2, cm3.FEATURE_DIM)
    prev = torch.zeros(1, 2, steps.PREV_DIM)
    assert proof.policy_comparison(model, g, g, prev, device="cpu", live_mask=[True] * vocab.N,
                                   pitch_known=[True])["executed_identical"]
    acts = torch.zeros(1, 2, 3, vocab.N)  # sigmoid exactly .5 => held, by the unchanged executor
    cams = torch.zeros(1, 2, 2, vocab.CAMERA_CLASSES)
    sent = proof.decisions(acts, cams, [True] * vocab.N, [True])
    assert bool((sent[..., :vocab.N] == 1).all()) and bool((sent[..., -1] == 1).all())
    for value in (.5, float(torch.nextafter(torch.tensor(.5), torch.tensor(0))),
                  float(torch.nextafter(torch.tensor(.5), torch.tensor(1)))):
        p = torch.zeros(1, 2, vocab.CAMERA_CLASSES)
        p[..., 2], p[..., 19] = value, 1 - value
        assert train._median_classes(p)[0, 0].item() == vocab.median_class(p[0, 0].tolist())
    receipt = {"losses": [1., 2.], "seconds": 9., "seconds_per_update": .3}
    assert proof.verify_smoke_repeat(model, receipt, model, {**receipt, "seconds": 19.})["identical"]
    with pytest.raises(ValueError, match="blocks"):
        proof.verify_smoke_repeat(model, receipt, model, {**receipt, "losses": [2., 1.]})
    with pytest.raises(ValueError, match="tolerance"):
        proof.compare_float(torch.zeros(2), torch.ones(2))
    diagnostics = proof.normalization_diagnostics(model, g + 1e6, g - 1e6, prev)
    assert all(isinstance(x, float) for x in diagnostics["pre_range"])


def test_source_identity_mutations_before_open_and_conflicting_pts(tmp_path, monkeypatch):
    header, rows = fixture.session("source", runs=(2,))
    session = steps.load(fixture.write(tmp_path / "table.jsonl", header, rows))
    monkeypatch.setattr(features, "TRAIN_TABLES", {session.session_id: session.sha256})
    directory = tmp_path / "cache"
    directory.mkdir()
    frames, pts, row_frame = cache.plan(session)
    manifest = {"format": cache.FORMAT, "session_id": session.session_id, "steps_sha256": session.sha256,
                "frames": 2, "row_frame": row_frame, "graph": cache.GRAPH, "videos": []}
    for name, shape in (("global", cache.GLOBAL), ("crop", cache.CROP), ("hud", cache.HUD)):
        path = directory / f"{name}.u8"
        path.write_bytes(bytes(2 * shape[0] * shape[1] * shape[2]))
        manifest[name + "_sha256"] = steps.sha256(path)
        manifest[name + "_shape"] = list(shape)
    path = directory / "cache.json"
    def load(obj):
        path.write_text(json.dumps(obj), encoding="utf-8")
        return features.source_identity(session, directory, manifest_sha256=steps.sha256(path), role="train")
    opened, identity = load(manifest)
    assert identity["frame_refs"][0][2] == pts[0][0]
    del opened
    for key, value in (("graph", "BGR"), ("row_frame", list(reversed(row_frame))), ("session_id", "different"),
                       ("steps_sha256", "a" * 64), ("global_shape", [144, 256, 4]), ("global_sha256", "b" * 64)):
        with pytest.raises(ValueError):
            load({**manifest, key: value})
    session.rows[1]["frame"]["frame_index"] = session.rows[0]["frame"]["frame_index"]
    with pytest.raises(ValueError, match="two different pts"):
        load(manifest)


def test_legacy_frozen_source_tiny_training_checkpoint_and_decisions(tmp_path):
    """Execute the pinned old trainer beside current legacy code, on the same CPU fixture."""
    import subprocess
    import types
    from pathlib import Path
    from policy.range_bc.model import Config as LegacyConfig
    root = Path(__file__).resolve().parents[1]
    frozen = {}
    for name in ("model", "train"):
        source = subprocess.check_output(["git", "show", f"9d61d59:policy/range_bc/{name}.py"], cwd=root).decode()
        # A line-ending checkout convention does not change executable Python.
        assert source == (root / "policy" / "range_bc" / f"{name}.py").read_text(encoding="utf-8")
        frozen[name] = source
    original = types.ModuleType("policy.range_bc._frozen_train")
    original.__package__ = "policy.range_bc"
    original.__file__ = str(root / "policy" / "range_bc" / "train.py")
    exec(compile(frozen["train"], original.__file__, "exec"), original.__dict__)
    arr = feature_arrays(tmp_path, n=50).original
    batches = train.Batches([arr])
    config = LegacyConfig(channels=(1,), reduce=1, embed=2, hud_embed=2, history_embed=2, hidden=4,
                          global_hw=(1, 1), crop_hw=(1, 1), hud_hw=(1, 1))
    stats = steps.train_statistics([arr.session])
    old_model, old_log, _ = original.fit(batches, config, stats, seed=0, max_steps=2, batch_size=1)
    new_model, new_log, _ = train.fit(batches, config, stats, seed=0, max_steps=2, batch_size=1)
    assert train.checkpoint_bytes(old_model, {"synthetic": True}) == train.checkpoint_bytes(new_model, {"synthetic": True})
    assert [{k: v for k, v in e.items() if k != "seconds"} for e in old_log] == [
        {k: v for k, v in e.items() if k != "seconds"} for e in new_log]
    assert original.predict_teacher(old_model, [arr]) == train.predict_teacher(new_model, [arr])
    assert original.predict_self(old_model, [arr], stats["live_mask"]) == train.predict_self(new_model, [arr], stats["live_mask"])


def test_synthetic_evaluation_timing_has_no_scores():
    model = cm3.Policy(cm3.Config("W"))
    receipt = proof.time_evaluation(model, [2, 3], device="cpu", path="W", window_count=1)
    assert receipt["dev_scores"] is False and receipt["teacher_seconds"] > 0 and receipt["self_seconds"] > 0


def test_actual_transformers_shape_on_synthetic_pixels(monkeypatch):
    transformers = pytest.importorskip("transformers")
    config = transformers.Dinov2Config(hidden_size=384, num_hidden_layers=12, num_attention_heads=6,
                                       patch_size=14, image_size=518, num_channels=3)
    # Random synthetic model, emphatically not a pretrained-weight receipt.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(0)
        backbone = transformers.Dinov2Model(config).eval().requires_grad_(False)
    pixels = features.preprocess(torch.zeros(1, 128, 128, 3, dtype=torch.uint8), "crop")
    with torch.no_grad():
        result = features.pool_tokens(backbone(pixel_values=pixels).last_hidden_state)
    assert result.shape == (1, cm3.FEATURE_DIM) and result.dtype == torch.float32
    assert all(p.grad is None for p in backbone.parameters())


def test_stream_feature_cache_and_checkpoint_roundtrip(tmp_path):
    asset = {"weights_sha256": features.WEIGHTS_SHA256}
    class SyntheticBackbone(torch.nn.Module):
        asset_receipt = asset

        def forward(self, pixels):
            assert len(pixels) <= 8
            return pixels.mean((1, 2, 3))[:, None].expand(-1, cm3.FEATURE_DIM).contiguous()

    n = 9  # Exercises two bounded extraction batches for each view.
    identity = {"role": "train", "frame_refs": [["synthetic", i, i, [1, 30]] for i in range(n)],
                "row_frame": list(range(n))}
    g = torch.zeros(n, *cache.GLOBAL, dtype=torch.uint8).numpy()
    c = torch.zeros(n, *cache.CROP, dtype=torch.uint8).numpy()
    arrays = (g, c, None, list(range(n)), {"row_frame": list(range(n))})
    backend = {"device": "cpu", "purpose": "synthetic unit test"}
    out = tmp_path / "features"
    manifest = features.write_cache(out, SyntheticBackbone(), arrays, identity, asset_receipt=asset,
                                    backend_receipt=backend, selected_frames=list(range(n)))
    opened = features.open_features(out, manifest_sha256=steps.sha256(out / "manifest.json"),
                                    identity=identity, assets=asset, backend=backend)
    assert opened[0].shape == (n, cm3.FEATURE_DIM) and opened[-1] == manifest
    for bad_ids in ([0, 0], [1, 0], [n]):
        with pytest.raises(ValueError, match="order"):
            features.write_cache(tmp_path / "refused", SyntheticBackbone(), arrays, identity,
                                 asset_receipt=asset, backend_receipt=backend, selected_frames=bad_ids)
        assert not (tmp_path / "refused").exists()
    bad_arrays = (g.astype("float32"), c, *arrays[2:])
    with pytest.raises(ValueError, match="dtype"):
        features.write_cache(tmp_path / "refused", SyntheticBackbone(), bad_arrays, identity,
                             asset_receipt=asset, backend_receipt=backend, selected_frames=[0])
    assert not (tmp_path / "refused").exists()
    model = cm3.Policy(cm3.Config("W", 2))
    path = tmp_path / "synthetic-smoke.pt"
    path.write_bytes(training.checkpoint_bytes(model))
    loaded, payload = training.load_checkpoint(path)
    assert payload["purpose"] == "smoke"
    assert cm3.tensor_manifest(loaded) == cm3.tensor_manifest(model)
