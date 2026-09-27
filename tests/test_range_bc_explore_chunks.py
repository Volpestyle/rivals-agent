"""EXPLORATORY synthetic checks; never opens demonstration payloads."""

from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import steps, train, vocab
from policy.range_bc.explore_chunks import ChunkBatches, ChunkPolicy, chunk_loss_terms
from policy.range_bc.model import Config, Policy


def small_config():
    return Config(frames=False, hud=False, embed=4, hidden=8, history_embed=4)


def test_h1_matches_control_outputs_losses_and_gradients():
    torch.manual_seed(7)
    control = Policy(small_config())
    torch.manual_seed(7)
    chunk = ChunkPolicy(small_config(), 1)
    assert control.state_dict().keys() == chunk.state_dict().keys()
    prev = torch.randn(2, 5, steps.PREV_DIM)
    a, c, _ = control(None, None, None, prev)
    ca, cc, _ = chunk.forward_chunks(None, None, None, prev)
    assert torch.equal(a, ca[:, :, 0])
    assert torch.equal(c, cc[:, :, 0])
    batch = {"act": torch.randint(2, a.shape).float(), "act_mask": torch.rand(a.shape) > .2,
             "camera": torch.randint(vocab.CAMERA_CLASSES, c.shape[:-1]),
             "camera_mask": torch.rand(c.shape[:-1]) > .2}
    weights = torch.ones(2, vocab.N)
    baseline = train.total_loss(train.loss_terms(a, c, batch, weights))
    loss = train.total_loss(chunk_loss_terms(ca, cc, {f"chunk_{k}": v.unsqueeze(2)
                                                   for k, v in batch.items()}, weights))
    assert torch.equal(baseline, loss)
    baseline.backward()
    loss.backward()
    for p, q in zip(control.parameters(), chunk.parameters()):
        assert torch.equal(p.grad, q.grad)


@pytest.mark.parametrize("horizon", [4, 8])
def test_all_heads_learn_but_only_step_one_executes(horizon):
    policy = ChunkPolicy(small_config(), horizon)
    prev = torch.randn(1, 4, steps.PREV_DIM)
    a, c, _ = policy.forward_chunks(None, None, None, prev)
    first = policy(None, None, None, prev)
    assert torch.equal(a[:, :, 0], first[0])
    assert torch.equal(c[:, :, 0], first[1])
    batch = {"chunk_act": torch.zeros_like(a), "chunk_act_mask": torch.ones_like(a, dtype=torch.bool),
             "chunk_camera": torch.zeros(c.shape[:-1], dtype=torch.long),
             "chunk_camera_mask": torch.ones(c.shape[:-1], dtype=torch.bool)}
    train.total_loss(chunk_loss_terms(a, c, batch, torch.ones(2, vocab.N))).backward()
    for head in [policy.actions, policy.camera, *policy.future_actions, *policy.future_camera]:
        assert head.weight.grad.abs().sum() > 0
    with torch.no_grad():
        for head in [*policy.future_actions, *policy.future_camera]:
            head.weight.fill_(999)
            head.bias.fill_(-999)
    after = policy(None, None, None, prev)
    assert torch.equal(first[0], after[0])
    assert torch.equal(first[1], after[1])


def synthetic_array():
    n = 15
    arr = SimpleNamespace(
        runs=[(0, 10), (10, 15)], press_windows=None,
        global_frames=torch.zeros(n, 1, 1, 3), crop_frames=torch.zeros(n, 1, 1, 3),
        hud_frames=torch.zeros(n, 1, 1, 3), prev=torch.zeros(n, steps.PREV_DIM),
        act=torch.arange(n).float()[:, None, None].expand(n, 3, vocab.N).clone(),
        act_known=torch.ones(n, 3, vocab.N, dtype=torch.bool),
        camera=torch.arange(n)[:, None].expand(n, 2).clone(),
        camera_known=torch.ones(n, 2, dtype=torch.bool), valid=torch.ones(n, dtype=torch.bool),
        regime=torch.zeros(n))
    arr.act_known[7, 1, 0] = False
    arr.camera_known[7, 1] = False
    arr.valid[8] = False
    return arr


def test_chunk_targets_mask_unknowns_burn_in_padding_and_run_edges():
    arr = synthetic_array()
    batches = ChunkBatches([arr], horizon=4, window=6, stride=4, min_run=1, burn_in=2, frames=False)
    # Choose a middle window, with future labels extending beyond its end.
    batches.windows = [(0, 4, 6, 0), (0, 10, 5, 10)]
    b = batches.batch([0, 1])
    for key in ("act", "act_mask", "camera", "camera_mask"):
        assert torch.equal(b[key], b[f"chunk_{key}"][:, :, 0])
    assert not b["chunk_act_mask"][0, :2].any()  # source burn-in
    assert b["chunk_act"][0, 2, 1, 0, 0] == 7
    assert not b["chunk_act_mask"][0, 2, 1, 1, 0]  # unknown future press
    assert b["chunk_act_mask"][0, 2, 1, 0, 0]  # known hold remains usable
    assert not b["chunk_camera_mask"][0, 2, 1, 1]
    assert not b["chunk_act_mask"][0, 2, 2].any()  # invalid future row 8
    assert not b["chunk_act_mask"][0, 4].any()  # invalid source row 8
    assert not b["chunk_act_mask"][0, 5, 1:].any()  # run boundary at row 10
    assert not b["chunk_act_mask"][1, 5].any()  # padded source
    batches.windows = [(0, 0, 6, 0)]
    b = batches.batch([0])
    assert b["chunk_act"][0, 5, 1, 0, 0] == 6  # outside window, within run
    assert b["chunk_act_mask"][0, 5, 1].all()


def test_masked_future_targets_have_zero_gradient():
    arr = synthetic_array()
    batches = ChunkBatches([arr], horizon=4, window=6, stride=4, min_run=1, burn_in=2, frames=False)
    b = batches.batch([0])
    a = torch.randn(b["chunk_act"].shape, requires_grad=True)
    c = torch.randn(*b["chunk_camera"].shape, vocab.CAMERA_CLASSES, requires_grad=True)
    train.total_loss(chunk_loss_terms(a, c, b, torch.ones(2, vocab.N))).backward()
    assert (a.grad[~b["chunk_act_mask"]] == 0).all()
    assert (c.grad[~b["chunk_camera_mask"]] == 0).all()


def test_interrupt_resume_preserves_optimizer_and_augmentation_rng(tmp_path):
    from policy.range_bc.explore_chunks_train import fit_chunks

    arr = synthetic_array()
    arr.session = SimpleNamespace(split="train")
    # Binary labels for the actual synthetic fit (the indexing test uses row IDs).
    arr.act = (arr.act.remainder(2) == 0).float()
    batches = ChunkBatches([arr], horizon=4, window=6, stride=4, min_run=1, burn_in=2, frames=False)
    stats = {"press": [2] * vocab.N, "release": [2] * vocab.N, "known": [10] * vocab.N}
    kwargs = dict(seed=3, epochs=2, batch_size=1, warmup=2, device="cpu")
    full, _, status = fit_chunks(batches, small_config(), stats, tmp_path / "full", **kwargs)
    assert status == "complete"
    _, _, status = fit_chunks(batches, small_config(), stats, tmp_path / "resume", stop_after_steps=1, **kwargs)
    assert status == "yielded"
    resumed, _, status = fit_chunks(batches, small_config(), stats, tmp_path / "resume", resume=True, **kwargs)
    assert status == "complete"
    for key, value in full.state_dict().items():
        assert torch.equal(value, resumed.state_dict()[key]), key


@pytest.mark.parametrize("cohort", ["full", "interim"])
def test_manifest_rejects_held_or_dev_in_train_before_any_payload(tmp_path, cohort):
    import json
    from policy.range_bc.explore_chunks_train import DEV_IDS, INTERIM_IDS, TRAIN_IDS, load_manifest

    roster = TRAIN_IDS | DEV_IDS
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"sessions": [{"session_id": s, "split": "train"} for s in roster]}))
    tally = tmp_path / "tally.json"
    tally.write_text(json.dumps({"rows": [{"session": s, "split": "train", "status": "admitted",
                                          "trainable_min": 1} for s in roster]}))
    selected = TRAIN_IDS if cohort == "full" else INTERIM_IDS
    manifest = {"train": [{"steps": f"/nonexistent/{s}.jsonl", "cache": "unused"} for s in sorted(selected)],
                "dev": [{"steps": f"/nonexistent/{s}.jsonl", "cache": "unused"} for s in sorted(DEV_IDS)]}
    path = tmp_path / "manifest.json"
    for replacement in ("20260922T032454-642Z-24328-1", sorted(DEV_IDS)[0], "20260925T212646-322Z-49728-6"):
        manifest["train"][0]["steps"] = f"/nonexistent/{replacement}.jsonl"
        path.write_text(json.dumps(manifest))
        with pytest.raises(train.FitError, match="authorized full-cohort roster"):
            load_manifest(path, registry, tally, cohort=cohort)


def test_threshold_adapter_reuses_exact_hold_rise_and_tap_rule():
    from policy.range_bc import executor
    from policy.range_bc.explore_chunks_eval import ThresholdPolicy

    model = ChunkPolicy(small_config(), 4)
    cutoffs = [.25, .5, .75] * (vocab.N // 3)
    cutoffs += [.5] * (vocab.N - len(cutoffs))
    adapter = ThresholdPolicy(model, cutoffs)
    prev = torch.randn(1, 4, steps.PREV_DIM)
    raw, cam, _ = model(None, None, None, prev)
    adjusted, same_cam, _ = adapter(None, None, None, prev)
    assert torch.equal(cam, same_cam)
    before = [0] * vocab.N
    for t in range(4):
        p = raw[0, t].sigmoid().tolist()
        q = adjusted[0, t].sigmoid().tolist()
        expected = [[0] * vocab.N for _ in range(3)]
        for c in range(vocab.N):
            result = executor.decode_step(*p, before, [True] * vocab.N, threshold=cutoffs[c])
            for channel in range(3):
                expected[channel][c] = result[channel][c]
        actual = executor.decode_step(*q, before, [True] * vocab.N)
        assert actual == tuple(expected)
        before = actual[0]


def test_threshold_adapter_matches_python_comparison_at_float32_boundaries():
    from policy.range_bc.explore_chunks_eval import THRESHOLDS, ThresholdPolicy

    model = ChunkPolicy(small_config(), 1)
    for threshold in THRESHOLDS:
        adapter = ThresholdPolicy(model, [threshold] * vocab.N)
        logits = torch.logit(torch.full((1, 1, 3, vocab.N), threshold))
        for toward in (torch.full_like(logits, -torch.inf), torch.full_like(logits, torch.inf)):
            near = torch.nextafter(logits, toward)
            for values in (logits, near):
                expected = [float(p) >= threshold for p in values.sigmoid().flatten().tolist()]
                actual = (adapter.decisions(values).sigmoid() >= .5).flatten().tolist()
                assert actual == expected


def test_resume_rejects_same_size_changed_targets_and_window_schedule(tmp_path):
    from policy.range_bc.explore_chunks_train import fit_chunks

    arr = synthetic_array()
    arr.session = SimpleNamespace(split="train")
    arr.act = arr.act.remainder(2)
    batches = ChunkBatches([arr], horizon=1, window=6, stride=4, min_run=1, burn_in=2, frames=False)
    stats = {"press": [2] * vocab.N, "release": [2] * vocab.N, "known": [10] * vocab.N}
    kwargs = dict(epochs=2, batch_size=1, device="cpu")
    fit_chunks(batches, small_config(), stats, tmp_path, stop_after_steps=1, **kwargs)
    arr.act[0, 0, 0] = 1 - arr.act[0, 0, 0]
    with pytest.raises(train.FitError, match="resume recipe differs"):
        fit_chunks(batches, small_config(), stats, tmp_path, resume=True, **kwargs)
    arr.act[0, 0, 0] = 1 - arr.act[0, 0, 0]
    batches.burn_in = 3
    with pytest.raises(train.FitError, match="resume recipe differs"):
        fit_chunks(batches, small_config(), stats, tmp_path, resume=True, **kwargs)


def test_threshold_calibration_masks_unknowns_and_resets_runs():
    from policy.range_bc.explore_chunks_eval import choose_thresholds

    def example(prob, press, *, known=True, valid=True):
        target = {"known": [known] * vocab.N, "press_known": [known] * vocab.N,
                  "press": [press] * vocab.N}
        pred = {"held": [prob] * vocab.N, "press": [0.] * vocab.N, "release": [0.] * vocab.N}
        return {"valid": valid, "target": target}, pred

    run = [example(.4, 1), example(.1, 0), example(.4, 1)]
    result = choose_thresholds([run, [example(.4, 1)]], [True] * vocab.N)
    assert result["thresholds"] == [.4] * vocab.N
    assert result["true_presses"] == [3] * vocab.N
    assert [v["calibrated"]["presses"] for v in result["actions"].values()] == [3] * vocab.N
    unknown = choose_thresholds([[example(.4, 1, known=False)]], [True] * vocab.N)
    assert unknown["known_steps"] == [0] * vocab.N
    assert unknown["thresholds"] == [.5] * vocab.N


def test_exact_threshold_search_matches_exhaustive_executor_boundaries():
    import numpy as np
    from policy.range_bc.explore_thresholds import choose, vector_counts

    rng = np.random.default_rng(9184)
    for n in (1, 7, 100):
        for _ in range(12):
            p = rng.choice([0., .1, .25, .5, .75, .9, 1.], size=(n, 3)).astype(np.float64)
            previous = np.r_[-1., p[:-1, 0]]
            previous[::7] = -1.
            known = rng.integers(0, 2, n).astype(bool)
            target = int(rng.integers(0, n + 1))
            threshold, count, _ = choose(p, previous, known, target)
            assert vector_counts(p, previous, known, known, threshold)["presses"] == count
            edges = np.unique(np.r_[0., 1., p.ravel()])
            candidates = np.unique(np.r_[edges, np.nextafter(edges[edges < 1], np.inf), .5])
            expected = min((abs(vector_counts(p, previous, known, known, t)["presses"] - target),
                            abs(t - .5), t) for t in candidates)
            assert (abs(count - target), abs(threshold - .5), threshold) == expected
    # A live zero-positive action is calibrated by the same rule, not forced to .5.
    threshold, count, _ = choose(np.array([[.8, 0., 0.]]), np.array([-1.]), np.array([True]), 0)
    assert threshold == np.nextafter(.8, np.inf) and count == 0


def camera_arrays():
    import numpy as np
    from policy.range_bc import fixture

    header, rows = fixture.session("explore-synthetic", runs=(12, 10), seed=4)
    session = steps.Session("synthetic", "synthetic", header, rows)
    frames = tuple(np.zeros((len(rows), 2, 2, 3), dtype=np.uint8) for _ in range(3))
    return train.SessionArrays(session, (*frames, list(range(len(rows))), {}))


def test_camera_decoders_preserve_continuous_expectation_and_pad_feedback():
    from policy.range_bc.explore_camera import decode_camera, sent_prediction
    from policy.range_bc import executor

    probs = [0.] * vocab.CAMERA_CLASSES
    probs[0], probs[vocab.ZERO_CLASS], probs[-1] = .4, .15, .45
    assert decode_camera(probs, "median") == 0
    assert decode_camera(probs, "mode") == 40
    assert decode_camera(probs, "expectation") == pytest.approx(2.)
    prediction, feedback = sent_prediction([[0.] * vocab.N] * 3, [probs, probs], [0] * vocab.N,
                                           [True] * vocab.N, [.5] * vocab.N, "mode", False)
    assert prediction["yaw"] == executor.max_step_degrees()[0]
    assert prediction["pitch"] is None and feedback["cp"] is None
    assert feedback["cy"] == vocab.camera_class(prediction["yaw"])


def test_multi_decoder_default_reproduces_legacy_predictions_and_independent_states():
    from policy.range_bc.explore_camera import predict_suite

    torch.manual_seed(5)
    model = ChunkPolicy(small_config(), 1)
    arr = camera_arrays()
    live = [True] * vocab.N
    names = {("fixed", "median"): [.5] * vocab.N, ("lower", "expectation"): [.2] * vocab.N}
    suite = predict_suite(model, [arr], live, names, device="cpu", chunk=7)
    teacher = train.executed_runs(train.predict_teacher(model, [arr], device="cpu", chunk=7), live)
    legacy = train.predict_self(model, [arr], live, device="cpu", chunk=7)
    assert suite[("fixed", "median")]["teacher"] == teacher
    for actual_run, legacy_run in zip(suite[("fixed", "median")]["self"], legacy):
        for (record, prediction), (old_record, old_prediction) in zip(actual_run, legacy_run):
            assert record == old_record
            assert prediction == {k: old_prediction[k] for k in prediction}
    solo = predict_suite(model, [arr], live, {("lower", "expectation"): [.2] * vocab.N}, device="cpu", chunk=7)
    for actual_run, solo_run in zip(suite[("lower", "expectation")]["self"], solo[("lower", "expectation")]["self"]):
        for (_, pred), (_, one) in zip(actual_run, solo_run):
            for key in ("held", "press", "release"):
                assert pred[key] == one[key]
            for key in ("yaw", "pitch"):
                assert pred[key] == pytest.approx(one[key], abs=1e-5)


def test_conditioning_nll_masks_unknown_axes_and_measures_feature_ablation():
    from policy.range_bc.explore_camera import conditioning_nll

    torch.manual_seed(4)
    model = ChunkPolicy(small_config(), 1)
    model.features = lambda g, c, h, b, t, like: torch.ones(b, t, model.config.frame_features)
    arr = camera_arrays()
    arr.camera_known[:, 1] = False
    report = conditioning_nll(model, [arr], device="cpu", chunk=7)
    visual, zero = report["axes"]["visual"], report["axes"]["zero_features"]
    assert visual["pitch"]["n"] == 0 and visual["pitch"]["nll"] is None
    assert visual["yaw"]["n"] == int(arr.valid.sum())
    assert visual["yaw"]["nll"] != zero["yaw"]["nll"]
    assert "out of distribution" in report["limitation"]
    for mode in ("visual", "zero_features"):
        for c, name in enumerate(vocab.NAMES):
            mask = arr.act_known[:, 1, c] & arr.valid
            assert report["press"][mode][name]["n"] == int(mask.sum())
            assert report["press"][mode][name]["positive_n"] == int((mask & (arr.act[:, 1, c] > .5)).sum())


def test_encoder_shared_initialization_and_feature_gradient():
    from policy.range_bc.explore_encoder import EncoderPolicy, WIDTH

    config = Config(hud=False, embed=4, hidden=8, history_embed=4)
    torch.manual_seed(0)
    original = ChunkPolicy(config, 1)
    torch.manual_seed(0)
    model = EncoderPolicy(config, 1)
    for key, value in original.state_dict().items():
        if not key.startswith(("global_enc.", "crop_enc.")):
            assert torch.equal(value, model.state_dict()[key])
    g, c = torch.randn(1, 5, WIDTH), torch.randn(1, 5, WIDTH)
    prev = torch.randn(1, 5, steps.PREV_DIM)
    a, cam, _ = model(g, c, None, prev)
    (a.square().mean() + cam.square().mean()).backward()
    assert model.global_enc[0].weight.grad.abs().sum() > 0
    assert model.crop_enc[0].weight.grad.abs().sum() > 0
    assert model.core.weight_ih_l0.grad.abs().sum() > 0


def test_encoder_batches_keep_labels_masks_dropout_and_feature_rows():
    from policy.range_bc.explore_encoder import FeatureBatches, WIDTH

    arr = synthetic_array()
    arr.prev = torch.randn_like(arr.prev)
    arr.frames = lambda rows: (rows[:, None].expand(-1, WIDTH).half(),
                               (rows[:, None] + 100).expand(-1, WIDTH).half(), torch.zeros(len(rows), 1))
    opts = dict(window=8, stride=4, min_run=4, burn_in=2)
    reference = ChunkBatches([arr], horizon=1, frames=False, **opts)
    actual = FeatureBatches([arr], **opts)
    assert reference.windows == actual.windows
    ids = list(range(len(actual.windows)))
    b = reference.batch(ids, torch.Generator().manual_seed(7))
    got = actual.batch(ids, torch.Generator().manual_seed(7))
    for key in ("prev", "act", "act_mask", "camera", "camera_mask", "chunk_act_mask", "chunk_camera_mask"):
        assert torch.equal(b[key], got[key])
    for i, (_, start, n, _) in enumerate(actual.windows):
        assert torch.equal(got["global"][i, :n, 0], torch.arange(start, start + n).half())
        assert torch.equal(got["crop"][i, :n, 0], torch.arange(start + 100, start + n + 100).half())
        assert not got["global"][i, n:].any()


def test_encoder_pool_preserves_row_major_spatial_cells():
    from policy.range_bc.explore_encoder import pool_tokens

    pixels = torch.arange(256).reshape(1, 256, 1).expand(-1, -1, 1024).float()
    pooled = pool_tokens(pixels).reshape(1, 16, 1024)
    expected = torch.tensor([[(r * 4 + y) * 16 + c * 4 + x for y in range(4) for x in range(4)]
                             for r in range(4) for c in range(4)]).float().mean(1)
    assert torch.equal(pooled[0, :, 0], expected)


def test_encoder_history_disabled_ignores_feedback_in_fit_and_recurrent_decode():
    from policy.range_bc.explore_encoder import EncoderPolicy, WIDTH

    config = Config(hud=False, history=False, embed=4, hidden=8, history_embed=4)
    torch.manual_seed(12)
    model = EncoderPolicy(config, 1)
    g, c = torch.randn(1, 5, WIDTH), torch.randn(1, 5, WIDTH)
    prev = torch.randn(1, 5, steps.PREV_DIM)
    feats = model.features(g, c, None, 1, 5, prev)
    for operation in (model.step, model.chunk_step):
        a, cam, state = operation(feats, prev)
        zero_a, zero_cam, zero_state = operation(feats, torch.zeros_like(prev))
        assert torch.equal(a, zero_a) and torch.equal(cam, zero_cam)
        assert all(torch.equal(x, y) for x, y in zip(state, zero_state))
    # Recurrent rollout retains visual memory but is invariant to arbitrary feedback.
    states = [None, None]
    for t in range(5):
        left = model.step(feats[:, t:t + 1], prev[:, t:t + 1], states[0])
        right = model.step(feats[:, t:t + 1], prev[:, t:t + 1] * -100, states[1])
        assert torch.equal(left[0], right[0]) and torch.equal(left[1], right[1])
        states = [left[2], right[2]]
    (a.square().mean() + cam.square().mean()).backward()
    assert model.global_enc[0].weight.grad.abs().sum() > 0
    assert model.crop_enc[0].weight.grad.abs().sum() > 0
    assert model.hist[0].weight.grad.count_nonzero() == 0


@pytest.mark.parametrize("enabled,mae,expected_count", [(True, .3, 1), (True, .418, 2), (False, .3, 2)])
@pytest.mark.parametrize("recovered", [False, True])
def test_decode_persistence_stop_saves_first_result_and_stops_summary(
        tmp_path, monkeypatch, enabled, mae, expected_count, recovered):
    import json
    from pathlib import Path
    from policy.range_bc import explore_chunks_eval as ev
    from policy.range_bc.explore_chunks_train import FORMAT

    config = small_config()
    model = ChunkPolicy(config, 1)
    checkpoint = tmp_path / "model.pt"
    torch.save({"format": FORMAT, "recipe": {"config": config.as_dict(), "horizon": 1, "cohort": "full"},
                "model": model.state_dict(), "epoch": 26, "seconds": 1.}, checkpoint)
    monkeypatch.setattr(steps, "train_statistics", lambda _: {"live_mask": [True] * vocab.N})
    monkeypatch.setattr(train, "predict_teacher", lambda *a, **kw: [])
    if recovered:
        def forbid_train_inference(*a, **kw):
            raise AssertionError("recovery must reuse original TRAIN cutoffs")
        monkeypatch.setattr(train, "predict_teacher", forbid_train_inference)
    monkeypatch.setattr(ev, "choose_thresholds", lambda *a: {"thresholds": [.5] * vocab.N})
    monkeypatch.setattr(ev, "recompute_references", lambda *a: {
        "frozen_dev": {"persistence": {"camera_mae_mean": .418}}})
    monkeypatch.setattr(ev, "conditioning_nll", lambda *a, **kw: {})
    monkeypatch.setattr(ev, "predict_suite", lambda *a, **kw: {
        ("fixed_0.5", d): {"teacher": [], "self": [], "teacher_camera": []}
        for d in ("median", "mode")})
    monkeypatch.setattr(ev.metrics, "evaluate", lambda *a, **kw: {
        "camera_mae_mean": mae, "macro_press_f1_tol": .2})
    monkeypatch.setattr(ev.metrics, "selffed_checks", lambda *a: {})
    # Recovery supplies pathlib objects; the persisted receipt must remain JSON.
    args = SimpleNamespace(out=tmp_path / "evaluation.json", checkpoint=checkpoint,
                           manifest="unused", registry="unused", tally="unused")
    messages = []
    result = ev.evaluate(args, messages.append, device="cpu", stop_on_persistence=enabled,
                         array_loader=lambda *a, **kw: ([], []), recovered_calibration=(
                             {"source": "TRAIN teacher-forced predictions only", "thresholds": [.7] * vocab.N}
                             if recovered else None))
    persisted = json.loads(Path(args.out).read_text())
    assert persisted == result and len(result["decode"]) == expected_count
    assert persisted["checkpoint"] == str(checkpoint)
    if recovered:
        assert result["threshold_calibration"]["thresholds"] == [.7] * vocab.N
    if expected_count == 1:
        assert list(result["decode"]) == ["fixed_0.5/median"]
        assert messages[-1] == result["stop_reason"]
        assert result["skipped_decodes"] == ["fixed_0.5/mode"]
    else:
        assert "stop_reason" not in result
        assert result["skipped_decodes"] == []


@pytest.mark.parametrize("seed,history", [(1, "disabled"), (2, "enabled"), (3, "disabled")])
def test_confirmation_entrypoint_propagates_seed_history_and_prereg(tmp_path, monkeypatch, seed, history):
    from policy.range_bc import explore_encoder as encoder
    from scripts import job_status

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda: "NVIDIA L40S")
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    monkeypatch.setattr(job_status, "write", lambda *a, **kw: None)
    monkeypatch.setattr(encoder, "load_manifest", lambda *a, **kw: ([], []))
    monkeypatch.setattr(encoder, "download_tower", lambda *a: (None, {}))
    monkeypatch.setattr(encoder, "extract", lambda *a: {})
    monkeypatch.setattr(encoder, "FeatureBatches", lambda *a, **kw: None)
    monkeypatch.setattr(steps, "train_statistics", lambda *a: {})
    monkeypatch.setattr(steps, "sha256", lambda *a: "b" * 64)
    called = {}

    def fit(batches, config, *a, **kw):
        called.update(kw)
        assert config.history == (history == "enabled")
        return None, None, "complete"

    def evaluate(*a, **kw):
        assert kw["chance_floor"] and kw["stop_on_persistence"]
        return {}

    monkeypatch.setattr(encoder, "fit_chunks", fit)
    monkeypatch.setattr(encoder, "evaluate", evaluate)
    args = ["--arm", "nitrogen", "--manifest", "unused", "--registry", "unused", "--tally", "unused",
            "--out", str(tmp_path), "--stop-file", "unused", "--log", "unused", "--history", history,
            "--seed", str(seed), "--job-name", "synthetic", "--confirm-prereg-sha256", "a" * 64,
            "--stop-on-persistence"]
    assert encoder.main(args) == 0
    assert called["seed"] == seed and called["experiment_tag"] == "CONFIRM"
    assert called["recipe_extra"]["prereg_sha256"] == "a" * 64
