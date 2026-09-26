"""The end-to-end range fit's torch pieces: model, loss, deterministic trainer, both evaluation modes, checkpoints,
the fit CLI and the bench. Runs with `uv run --group execution pytest tests/test_range_bc_torch.py` (skipped without
torch)."""
import dataclasses
from dataclasses import replace
import hashlib
import json
import math
import sys

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import baselines, bench, cache, fixture, steps, train, vocab  # noqa: E402
from policy.range_bc.model import Config, Policy, parameter_count  # noqa: E402

TINY = Config(channels=(4, 4, 4), reduce=2, embed=8, hud_embed=4, history_embed=8, hidden=16)


def fake_cache(directory, session, seed=0):
    """A cache in the builder's format: deterministic noise plus a signal (the global frame's top rows are bright
    exactly when spider_power is pressed in the row's own step)."""
    directory.mkdir(parents=True)
    gen = torch.Generator().manual_seed(seed)
    n = len(session.rows)
    arrays = {k: torch.randint(0, 64, (n, *shape), generator=gen, dtype=torch.uint8)
              for k, shape in (("global", cache.GLOBAL), ("crop", cache.CROP), ("hud", cache.HUD))}
    lmb = vocab.INDEX["spider_power"]
    for k, r in enumerate(session.rows):
        if r["press"][lmb]:
            arrays["global"][k, :8] = 255
    manifest = {"format": cache.FORMAT, "session_id": session.session_id, "steps_sha256": session.sha256,
                "frames": n, "row_frame": list(range(n)), "ffmpeg": "synthetic"}
    for k, a in arrays.items():
        (directory / f"{k}.u8").write_bytes(a.numpy().tobytes())
        manifest[f"{k}_sha256"] = steps.sha256(directory / f"{k}.u8")
    (directory / "cache.json").write_text(json.dumps(manifest))


def cohort(tmp_path, split="train", name="t", runs=(150, 120), seed=0):
    header, rows = fixture.session(name, split=split, runs=runs, seed=seed)
    path = fixture.write(tmp_path / f"{name}.jsonl", header, rows)
    session = steps.load(path)
    fake_cache(tmp_path / "caches" / name, session, seed)
    return path, session


def arrays(tmp_path, split="train", name="t", seed=0, lag=0):
    _, session = cohort(tmp_path, split, name, seed=seed)
    frames = cache.open_cache(tmp_path / "caches" / name, session, verify_hashes=True)
    return train.SessionArrays(session, frames, lag=lag)


@pytest.fixture
def no_live_io_modules(monkeypatch):
    """The verifier's no_live_io check (policy/range_bc/verify.py) fails when vgamepad, dxcam or agent.loop is in
    sys.modules, which is right for a verifier process. In a whole-repo run earlier test files (tests/test_loop.py)
    import agent.loop first, so the verifier tests hide those entries for their own duration; monkeypatch restores
    them afterwards. The names are the guard's."""
    for name in ("vgamepad", "dxcam", "agent.loop"):
        monkeypatch.delitem(sys.modules, name, raising=False)


def zeros(t=2):
    return (torch.zeros(1, t, 3, 144, 256, dtype=torch.uint8), torch.zeros(1, t, 3, 128, 128, dtype=torch.uint8),
            torch.zeros(1, t, 3, 80, 200, dtype=torch.uint8))


def rand(t, seed=0):
    g = torch.Generator().manual_seed(seed)
    return tuple(torch.randint(0, 255, (1, t, 3, *hw), generator=g, dtype=torch.uint8)
                 for hw in ((144, 256), (128, 128), (80, 200)))


def test_default_model_matches_the_design():
    model = Policy()
    counts = {n: parameter_count(c) for n, c in model.named_children()}
    assert parameter_count(model) == 4_810_499, counts      # the lane doc's table
    acts, cams, state = model(*zeros(), torch.zeros(1, 2, steps.PREV_DIM))
    assert acts.shape == (1, 2, 3, vocab.N) and cams.shape == (1, 2, 2, vocab.CAMERA_CLASSES)
    assert state[0].shape == (1, 1, 512)


def test_twins():
    history = Policy(replace(Config(), frames=False))
    assert not hasattr(history, "global_enc") and parameter_count(history) == 2_556_971
    torch.manual_seed(0)
    frames_only = Policy(replace(TINY, history=False)).eval()
    a = frames_only(*rand(3), torch.zeros(1, 3, steps.PREV_DIM))[0]
    b = frames_only(*rand(3), torch.ones(1, 3, steps.PREV_DIM))[0]
    assert torch.equal(a, b)
    torch.manual_seed(0)
    blind = Policy(replace(TINY, frames=False)).eval()
    assert torch.equal(blind(*rand(3, 1), torch.ones(1, 3, steps.PREV_DIM))[0],
                       blind(*rand(3, 2), torch.ones(1, 3, steps.PREV_DIM))[0])


def test_the_policy_is_causal_and_stepping_equals_one_pass():
    torch.manual_seed(0)
    model = Policy(TINY).eval()
    g, c, h = rand(6)
    p = torch.rand(1, 6, steps.PREV_DIM)
    acts, cams, _ = model(g, c, h, p)
    g2, c2, h2, p2 = g.clone(), c.clone(), h.clone(), p.clone()
    g2[:, 4:], c2[:, 4:], h2[:, 4:], p2[:, 4:] = 0, 0, 0, 0
    acts2, cams2, _ = model(g2, c2, h2, p2)
    assert torch.equal(acts[:, :4], acts2[:, :4]) and torch.equal(cams[:, :4], cams2[:, :4])
    assert not torch.equal(acts[:, 4:], acts2[:, 4:])
    k1, _, s = model(g[:, :3], c[:, :3], h[:, :3], p[:, :3])
    k2, _, _ = model(g[:, 3:], c[:, 3:], h[:, 3:], p[:, 3:], s)
    assert torch.allclose(torch.cat([k1, k2], 1), acts, atol=1e-6)


def test_session_arrays_and_batches(tmp_path):
    arr = arrays(tmp_path)
    b = train.Batches([arr])
    # run 150 is tiled at 0 and 48 plus an end-aligned 54; run 120 at 150 plus an end-aligned 174
    assert b.windows == [(0, 0, 96, 0), (0, 48, 96, 0), (0, 54, 96, 0), (0, 150, 96, 150), (0, 174, 96, 150)]
    batch = b.batch([0, 1], torch.Generator().manual_seed(0), prev_dropout=0.)
    assert batch["global"].shape == (2, 96, 3, 144, 256) and batch["hud"].shape == (2, 96, 3, 80, 200)
    assert batch["act_mask"][0, 0].any() and not batch["act_mask"][1, :steps.BURN_IN].any()
    assert batch["act_mask"][1, steps.BURN_IN:].any()
    assert torch.equal(batch["prev"][0], arr.prev[torch.arange(0, 96)])
    assert batch["prev"][0, 0].sum() == 0 and batch["prev"][0, 1, -1] == 1     # run start: no previous action
    fwd = vocab.INDEX["move_forward"]
    unknown = [150, 151, 152]                                                 # the fixture's unknown hold after run1
    assert not arr.act_known[unknown, :, fwd].any() and arr.act_known[unknown, :, vocab.INDEX["jump"]].all()
    blind = train.Batches([arr], frames=False).batch([0, 1], torch.Generator().manual_seed(0))
    assert blind["global"].shape == (2, 96, 3, 1, 1) and blind["aug"] is None


def test_drq_shift_moves_the_global_stream_only(tmp_path):
    x = torch.arange(2 * 1 * 3 * 16 * 16, dtype=torch.float).reshape(2, 1, 3, 16, 16)
    shifted = train.drq_shift(x, torch.tensor([[0, 0], [2, -3]]))
    assert torch.equal(shifted[0], x[0])
    assert torch.equal(shifted[1, 0, :, 0:10, 3:16], x[1, 0, :, 2:12, 0:13])
    arr = arrays(tmp_path)
    b = train.Batches([arr]).batch([0], torch.Generator().manual_seed(5))
    d = train.to_device(b, "cpu")
    raw = b["crop"].float() * b["aug"]["scale"].view(-1, 1, 1, 1, 1) + b["aug"]["offset"].view(-1, 1, 1, 1, 1)
    assert torch.allclose(d["crop"], raw.clamp(0, 255))                     # the crop is jittered, never shifted


def test_masked_steps_carry_no_gradient(tmp_path):
    arr = arrays(tmp_path)
    b = train.Batches([arr]).batch([1])
    acts = torch.zeros(1, 96, 3, vocab.N, requires_grad=True)
    cams = torch.zeros(1, 96, 2, vocab.CAMERA_CLASSES, requires_grad=True)
    train.total_loss(train.loss_terms(acts, cams, b, torch.ones(2, vocab.N))).backward()
    assert acts.grad[0, :steps.BURN_IN].abs().sum() == 0 and cams.grad[0, :steps.BURN_IN].abs().sum() == 0
    assert acts.grad[0, steps.BURN_IN:].abs().sum() > 0


def test_training_is_byte_reproducible_on_cpu_and_logs_dev_loss(tmp_path):
    arr = arrays(tmp_path)
    dev = arrays(tmp_path, name="d", seed=5)
    stats = steps.train_statistics([arr.session])
    batches, dev_batches = train.Batches([arr]), train.Batches([dev])
    shas = []
    for _ in range(2):
        model, hist, _ = train.fit(batches, TINY, stats, seed=3, epochs=4, batch_size=2, lr=3e-3, warmup=5,
                                   dev=dev_batches)
        shas.append(hashlib.sha256(train.checkpoint_bytes(model, {"seed": 3})).hexdigest())
    assert shas[0] == shas[1]
    assert len(hist) == 4 and set(hist[0]["dev"]) == {"held", "press", "release", "camera", "total"}
    assert hist[-1]["train_loss"] < hist[0]["train_loss"]
    other, _, _ = train.fit(batches, TINY, stats, seed=4, epochs=1, batch_size=2, warmup=5)
    assert hashlib.sha256(train.checkpoint_bytes(other, {"seed": 3})).hexdigest() != shas[0]
    _, hist, _ = train.fit(batches, TINY, stats, seed=3, max_steps=7, batch_size=2, warmup=5)
    assert hist[-1]["steps"] == 7 and len(hist) == 3                       # 5 windows / 2 = 3 steps per epoch


def test_fit_refuses_validation_sessions(tmp_path):
    arr = arrays(tmp_path, split="val", name="v")
    with pytest.raises(train.FitError, match="only train"):
        train.fit(train.Batches([arr]), TINY, {}, epochs=1)


def test_teacher_forced_prediction(tmp_path):
    arr = arrays(tmp_path, split="val", name="v", lag=1)
    torch.manual_seed(0)
    model = Policy(TINY)
    runs = train.predict_teacher(model, [arr], chunk=40)
    assert [len(r) for r in runs] == [b - a for a, b in arr.runs]
    rec, pred = runs[0][0]
    assert rec["target"] == steps.target(arr.session.rows[1], arr.session.calibration)     # lag 1
    assert len(pred["press"]) == vocab.N and pred["yaw"] in (0.,) + vocab.REPS + tuple(-r for r in vocab.REPS)
    b = train.predict_teacher(model, [arr], chunk=7)
    for (_, x), (_, y) in zip(runs[0], b[0]):
        assert x["yaw"] == y["yaw"] and max(abs(u - v) for u, v in zip(x["press"], y["press"])) < 1e-5


def test_self_fed_prediction_feeds_back_what_was_sent(tmp_path):
    arr = arrays(tmp_path, split="val", name="v")
    torch.manual_seed(0)
    model = Policy(TINY)
    live = list(vocab.live_mask([1000] * vocab.N))
    runs = train.predict_self(model, [arr], live, chunk=40)
    assert [len(r) for r in runs] == [b - a for a, b in arr.runs]
    my, mp = train.executor.max_step_degrees()
    for _, p in runs[0]:
        assert set(p["held"]) <= {0., 1.} and p["held"][vocab.INDEX["ultimate"]] == 0.
        assert abs(p["yaw"]) <= my + 1e-9 and abs(p["pitch"]) <= mp + 1e-9
    again = train.predict_self(model, [arr], live, chunk=13)
    # chunking does not change the fed-back decisions; the diagnostic margin may differ by float noise (Mac CPU conv
    # kernels vary with batch shape)
    strip = lambda rs: [{k: v for k, v in p.items() if k != "margin"} for _, p in rs[0]]
    assert strip(again) == strip(runs)
    assert all(abs(a["margin"] - b["margin"]) < 1e-4 for (_, a), (_, b) in zip(again[0], runs[0]))


def test_checkpoint_round_trip_and_domain_refusal(tmp_path):
    torch.manual_seed(0)
    model = Policy(TINY)
    sha = train.save_checkpoint(tmp_path / "m.pt", model, {"seed": 0})
    assert sha == steps.sha256(tmp_path / "m.pt")
    loaded, payload = train.load_checkpoint(tmp_path / "m.pt")
    assert payload["domain"] == "semantic_pad" and loaded.config == TINY
    assert all(torch.equal(a, b) for a, b in zip(model.state_dict().values(), loaded.state_dict().values()))
    with pytest.raises(train.FitError, match="executor"):
        train.load_checkpoint(tmp_path / "m.pt", domain="keyboard_mouse")
    with pytest.raises(FileExistsError):
        train.save_checkpoint(tmp_path / "m.pt", model, {})


@pytest.mark.parametrize("flag", ["--train", "--dev", "--val"])
def test_the_fit_cli_refuses_a_replay_split_table(tmp_path, flag):
    """Replay rows are never train (lead decision 2026-09-23): --train, --dev and --val refuse a replay-split table
    before any fitting, whatever else is supplied."""
    header, rows = fixture.replay_session("rp", runs=(150,))
    replay = fixture.write(tmp_path / "rp.jsonl", header, rows)
    fake_cache(tmp_path / "caches" / "rp", steps.load(replay))
    train_path, _ = cohort(tmp_path, "train", "t", seed=0)
    args = {"--train": [str(train_path)], "--dev": [], "--val": []}
    args[flag] = args[flag] + [str(replay)] if flag != "--train" else [str(replay)]
    argv = [x for k, v in args.items() if v for x in (k, *v)]
    with pytest.raises(steps.StepError, match="replay-split recording is never train, val or test"):
        train.main(argv + ["--cache-root", str(tmp_path / "caches"), "--out", str(tmp_path / "o"), "--scope",
                           "smoke", "--epochs", "1", "--batch", "4", "--model-config", json.dumps(TINY.as_dict())])


def test_the_fit_cli_end_to_end(tmp_path):
    train_path, _ = cohort(tmp_path, "train", "t", seed=0)
    dev_path, _ = cohort(tmp_path, "train", "d", seed=2)
    val_path, _ = cohort(tmp_path, "val", "v", seed=1)
    tiny = json.dumps(TINY.as_dict())
    common = ["--train", str(train_path), "--cache-root", str(tmp_path / "caches"), "--epochs", "1", "--batch", "4",
              "--model-config", tiny]
    with pytest.raises(train.FitError, match="dev only"):
        train.main(common + ["--out", str(tmp_path / "p"), "--scope", "plumbing", "--val", str(val_path)])
    train.main(common + ["--out", str(tmp_path / "out"), "--scope", "smoke", "--dev", str(dev_path),
                         "--val", str(val_path)])
    r = json.loads((tmp_path / "out" / "report.json").read_text())
    assert r["scope"] == "smoke" and not r["test_opened"]
    assert r["sealed_denylist"]["session_ids"] == ["20260923T053616-779Z-33696-2"]     # always loaded, pinned
    arms = ("model", "model_nohud", "history_only")
    assert set(r["checkpoints"]) == {f"{arm}-seed{s}.pt" for arm in arms for s in (0, 1, 2)}
    assert set(r["gates"]) == {"dev", "val"} and set(r["gates"]["val"]) == {"model", "model_nohud"}
    assert all(v["complete"] for v in r["gates"]["val"].values())
    assert r["candidate"] == "model_nohud" and r["hud_parity"] is None          # no passing P2': the no-HUD arm
    assert "windows" not in r["metrics"]["val"] and "press_windows" not in r["windows"]   # human: no window term
    assert r["sealed_denylist"]["default"] is True
    assert r["patch_equivalence"] == {"path": steps.PATCH_EQUIVALENCE, "sha256_pin": steps.PATCH_EQUIVALENCE_SHA256,
                                      "default": True, "kit_version": "Season 10, Version 20260911",
                                      "builds": [fixture.PATCH]}
    tf = r["metrics"]["val"]["teacher_forced"]
    assert set(tf) == set(arms) | {"persistence", "zero_motion", "prior", "echo", "ar2"}
    assert tf["echo"]["all"]["window"] == {"early": 1, "late": 0, "self_fed": False}
    sf = r["metrics"]["val"]["self_fed"]
    assert set(sf) == set(arms) and sf["model"]["0"]["all"]["window"] == {"early": 1, "late": 1, "self_fed": True}
    assert len(r["budget"]) == 9 + 2 and all(len(h) == 1 and "dev" in h[0] for h in r["epochs_log"].values())
    assert [c["role"] for c in r["cohort"]] == ["train", "dev", "val"] and r["train_minutes"]["total"] > 0
    closure = r["code_closure"]
    for f in ("policy/range_bc/train.py", "policy/range_bc/verify.py", "agent/controller.py", "agent/human_intake.py"):
        assert f in closure
    assert not r["cache_hashes_verified"]
    for name, sha in r["checkpoints"].items():
        assert steps.sha256(tmp_path / "out" / name) == sha


def test_train_dev_and_val_must_map_to_one_kit_version(tmp_path):
    """Patch-equivalence amendment: each split is its own cohort, so the fit compares kit versions across them."""
    new = "1.1.3892207/build25501035"
    train_path, _ = cohort(tmp_path, "train", "t", seed=0)                          # the admitted build
    header, rows = fixture.session("v", split="val", runs=(150, 120), seed=1)
    header["patch"] = new
    val_path = fixture.write(tmp_path / "v.jsonl", header, rows)
    fake_cache(tmp_path / "caches" / "v", steps.load(val_path), 1)
    common = ["--train", str(train_path), "--val", str(val_path), "--cache-root", str(tmp_path / "caches"),
              "--scope", "smoke", "--epochs", "1", "--batch", "4", "--seeds", "0", "--arms", "model_nohud",
              "--model-config", json.dumps(TINY.as_dict())]
    two = tmp_path / "two-kits.json"                                                # the new build under another kit
    two.write_text(json.dumps({"format": steps.PATCH_EQUIVALENCE_FORMAT, "kit_versions": {
        "K-old": {"builds": [fixture.PATCH], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"},
        "K-new": {"builds": [new], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"}}}),
        encoding="utf-8")
    with pytest.raises(train.FitError, match=r"more than one kit version: 'K-new' \(builds \['1\.1\.3892207/build25501035'\]\); "
                                             r"'K-old'"):
        train.main(common + ["--out", str(tmp_path / "x"), "--patch-equivalence", str(two),
                             "--patch-equivalence-sha256", steps.sha256(two)])
    assert not (tmp_path / "x" / "report.json").exists()                           # refused before anything trained
    train.main(common + ["--out", str(tmp_path / "ok")])                            # the pinned file: one kit version
    r = json.loads((tmp_path / "ok" / "report.json").read_text())
    assert r["patch_equivalence"]["kit_version"] == "Season 10, Version 20260911"
    assert r["patch_equivalence"]["builds"] == sorted([fixture.PATCH, new])
    assert sorted(c["patch"] for c in r["cohort"]) == sorted([fixture.PATCH, new])  # headers keep the real builds


def test_scope_fit_refuses_what_the_review_asked(tmp_path):
    train_path, _ = cohort(tmp_path, "train", "t", seed=0)
    dev_path, _ = cohort(tmp_path, "train", "d", seed=2)
    val_path, _ = cohort(tmp_path, "val", "v", seed=1)
    parity = tmp_path / "parity.json"
    parity.write_text(json.dumps(PARITY_FAIL))
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps({"epochs": 1, "weight_decay": 1e-4, "stride": 48, "source": "test",
                               "hud_parity_sha256": hashlib.sha256(parity.read_bytes()).hexdigest()}))
    bad_pre = tmp_path / "bad-pre.json"
    bad_pre.write_text(json.dumps({"epochs": 1, "weight_decay": 1e-4, "stride": 48, "hud_parity_sha256": "0" * 64}))
    junk = tmp_path / "junk.json"
    junk.write_text(json.dumps({"pass": True}))
    base = ["--train", str(train_path), "--dev", str(dev_path), "--val", str(val_path), "--cache-root",
            str(tmp_path / "caches"), "--scope", "fit", "--epochs", "1", "--batch", "4"]
    with pytest.raises(train.FitError, match="smoke runs only"):
        train.main(base + ["--out", str(tmp_path / "a"), "--model-config", "{}"])
    with pytest.raises(train.FitError, match="plumbing tools"):
        train.main(base + ["--out", str(tmp_path / "a2"), "--arms", "model_nohud", "history_only"])
    with pytest.raises(train.FitError, match="plumbing tools"):
        train.main(base + ["--out", str(tmp_path / "a3"), "--train-fraction", "0.5"])
    with pytest.raises(train.FitError, match="preregistration"):
        train.main(base + ["--out", str(tmp_path / "b")])
    with pytest.raises(train.FitError, match="differs from the pre-registration"):
        train.main(base + ["--out", str(tmp_path / "c"), "--preregistration", str(pre), "--weight-decay", "0.01"])
    with pytest.raises(train.FitError, match="hud-parity"):
        train.main(base + ["--out", str(tmp_path / "d"), "--preregistration", str(pre)])
    with pytest.raises(train.FitError, match="not a hudparity result"):
        train.main(base + ["--out", str(tmp_path / "d2"), "--preregistration", str(pre), "--hud-parity", str(junk)])
    with pytest.raises(train.FitError, match="hud_parity_sha256"):
        train.main(base + ["--out", str(tmp_path / "d3"), "--preregistration", str(bad_pre), "--hud-parity",
                           str(parity)])
    other = tmp_path / "other-deny.json"
    other.write_bytes((train.ROOT / steps.DENYLIST).read_bytes())
    with pytest.raises(train.FitError, match="default denylist"):
        train.main(base + ["--out", str(tmp_path / "d4"), "--preregistration", str(pre), "--hud-parity", str(parity),
                           "--sealed-denylist", str(other)])
    other_eq = tmp_path / "other-equivalence.json"                 # the same bytes elsewhere: not the pinned default
    other_eq.write_bytes((train.ROOT / steps.PATCH_EQUIVALENCE).read_bytes())
    with pytest.raises(train.FitError, match="pinned default patch-equivalence"):
        train.main(base + ["--out", str(tmp_path / "d5"), "--preregistration", str(pre), "--hud-parity", str(parity),
                           "--patch-equivalence", str(other_eq)])
    # today the package is untracked, so a real fit is refused before anything is trained
    with pytest.raises(train.FitError, match="untracked|uncommitted"):
        train.main(base + ["--out", str(tmp_path / "e"), "--preregistration", str(pre), "--hud-parity", str(parity)])
    assert not (tmp_path / "e").exists()


def test_a_plumbing_run_trains_the_named_arms_on_a_nested_prefix(tmp_path):
    train_path, session = cohort(tmp_path, "train", "t", seed=0)
    dev_path, _ = cohort(tmp_path, "train", "d", seed=2)
    common = ["--train", str(train_path), "--dev", str(dev_path), "--cache-root", str(tmp_path / "caches"),
              "--scope", "plumbing", "--max-steps", "3", "--batch", "4", "--seeds", "0",
              "--model-config", json.dumps(TINY.as_dict())]
    with pytest.raises(train.FitError, match="at least one model arm"):
        train.main(common + ["--out", str(tmp_path / "x"), "--arms", "history_only"])
    train.main(common + ["--out", str(tmp_path / "half"), "--arms", "model", "history_only", "--train-fraction", ".5"])
    train.main(common + ["--out", str(tmp_path / "all"), "--arms", "model", "history_only"])
    half, full = (json.loads((tmp_path / n / "report.json").read_text()) for n in ("half", "all"))
    assert set(half["checkpoints"]) == {"model-seed0.pt", "history_only-seed0.pt"}
    assert half["config"]["arms"] == ["model", "history_only"] and half["config"]["train_fraction"] == .5
    # the pre-registered candidate (no-HUD) was not trained: the CPU reference falls back to the trained model arm
    assert half["candidate"] == "model_nohud" and half["candidate_checkpoint"] == "model-seed0.pt"
    assert half["candidate_reason"]["reference_arm"] == "model"
    assert set(half["gates"]["dev"]) == {"model"}
    # the same file and sha256, fewer counted minutes; the dev set is untouched
    assert [c["steps_sha256"] for c in half["cohort"]] == [c["steps_sha256"] for c in full["cohort"]]
    assert 0 < half["train_minutes"]["total"] < full["train_minutes"]["total"]
    assert half["windows"]["count"] < full["windows"]["count"]
    assert half["metrics"]["dev"]["teacher_forced"]["persistence"] == full["metrics"]["dev"]["teacher_forced"][
        "persistence"]


def test_every_pre_registered_plumbing_run_parses_under_the_fit_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "range_bc_plumbing", train.ROOT / "docs/evidence/fit-readiness-20260923/range_bc_plumbing.py")
    plumbing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plumbing)
    pre, _ = plumbing.load_prereg()
    runs = plumbing.run_list(pre, 1234)
    assert len(runs) == 9
    for name, args in runs:
        a = train.parser().parse_args(["--train", "t.jsonl", "--dev", "d.jsonl", "--cache-root", "c", "--out", "o",
                                       "--scope", "plumbing", "--device", "mps"] + args)
        assert a.batch == pre["fixed"]["batch"] and a.lr == pre["fixed"]["lr"] and a.val == []
        assert a.stride == 48 and 0 in a.seeds and any(arm in train.MODEL_ARMS for arm in a.arms)
        assert (a.max_steps == 1234) == name.startswith("plumb-p5-")


def test_bench_is_reproducible_on_cpu():
    a = bench.run(device="cpu", batch=1, window=4, n_steps=3, warmup=1, config=TINY)
    b = bench.run(device="cpu", batch=1, window=4, n_steps=3, warmup=1, config=TINY)
    assert a["error"] is None and a["checkpoint_sha256"] == b["checkpoint_sha256"]
    assert a["frames_per_second"] > 0


def test_self_fed_prediction_never_reads_the_true_previous_action(tmp_path):
    """Review K10 / F3: randomising the recorded previous action changes teacher-forced output and leaves self-fed
    output exactly as it was."""
    arr = arrays(tmp_path, split="val", name="v")
    torch.manual_seed(0)
    model = Policy(TINY)
    live = list(vocab.live_mask([1000] * vocab.N))
    tf1, sf1 = train.predict_teacher(model, [arr]), train.predict_self(model, [arr], live)
    arr.prev = torch.rand_like(arr.prev)
    tf2, sf2 = train.predict_teacher(model, [arr]), train.predict_self(model, [arr], live)
    assert [p for _, p in sf1[0]] == [p for _, p in sf2[0]]
    assert [p for _, p in tf1[0]] != [p for _, p in tf2[0]]


# ---- the CPU reload reference and verifier ----------------------------------------------------------------------------

def _fit(tmp_path, extra=(), pitch_gain=fixture.CALIBRATION["pitch_deg_per_count"]):
    paths = {}
    for split, name, seed in (("train", "t", 0), ("train", "d", 2), ("val", "v", 1)):
        header, rows = fixture.session(name, split=split, runs=(150, 120), seed=seed, pitch_gain=pitch_gain)
        paths[name] = fixture.write(tmp_path / f"{name}.jsonl", header, rows)
        fake_cache(tmp_path / "caches" / name, steps.load(paths[name]), seed)
    out = tmp_path / "out"
    train.main(["--train", str(paths["t"]), "--dev", str(paths["d"]), "--val", str(paths["v"]),
                "--cache-root", str(tmp_path / "caches"), "--out", str(out), "--scope", "smoke", "--epochs", "1",
                "--batch", "4", "--seeds", "0", "--model-config", json.dumps(TINY.as_dict()), *extra])
    return out, paths


@pytest.mark.usefixtures("no_live_io_modules")
def test_the_cpu_reference_verifies_and_every_tamper_fails(tmp_path):
    from policy.range_bc import verify
    import shutil
    deny = steps.load_denylist()
    out, paths = _fit(tmp_path)
    r = json.loads((out / "report.json").read_text())
    assert set(r["cpu_reference"]) == {"dev", "val"} and r["cpu_reference"]["val"]["device_vs_cpu"]["tf_decisions_equal"]
    rs = hashlib.sha256((out / "report.json").read_bytes()).hexdigest()
    ok, rep = verify.verify(out, "val", [paths["v"]], tmp_path / "caches", denylist=deny, report_sha256=rs)
    assert ok, rep["failed"]
    # thread count differs from the reference run (4 pinned here): summation order, not a defect
    assert rep["max_probability_delta"] <= 1e-6 and rep["checks"]["sf_decisions"]["ok"]
    ok, rep = verify.verify(out, "dev", [paths["d"]], tmp_path / "caches", denylist=deny, report_sha256=rs)
    assert ok, rep["failed"]

    def tampered(fn):
        copy = tmp_path / f"copy-{len(list(tmp_path.glob('copy-*')))}"
        shutil.copytree(out, copy)
        fn(copy)
        return verify.verify(copy, "val", [paths["v"]], tmp_path / "caches", denylist=deny, report_sha256=rs)

    def flip(path, at=100):
        b = bytearray(path.read_bytes())
        b[at] ^= 1
        path.write_bytes(bytes(b))
    ok, rep = tampered(lambda c: flip(c / r["candidate_checkpoint"], 5000))       # the candidate: model_nohud
    assert not ok and "checkpoint_sha256" in rep["failed"]
    ok, rep = tampered(lambda c: flip(c / "model-seed0.pt", 5000))                  # not the candidate: not verified
    assert ok
    ok, rep = tampered(lambda c: flip(c / "val-cpu-probs.f32"))
    assert not ok and "probs_sha256" in rep["failed"]
    ok, rep = verify.verify(out, "val", [paths["v"]], tmp_path / "caches", denylist=deny, report_sha256="0" * 64)
    assert not ok and rep["failed"] == ["report_sha256"]
    (tmp_path / "other").mkdir()
    header, rows = fixture.session("v", split="val", runs=(150, 120), seed=9)
    other = fixture.write(tmp_path / "other" / "v.jsonl", header, rows)
    with pytest.raises(cache.CacheError, match="different step table"):
        verify.verify(out, "val", [other], tmp_path / "caches", denylist=deny, report_sha256=rs)


@pytest.mark.usefixtures("no_live_io_modules")
def test_the_verifier_cli_writes_its_report_once(tmp_path):
    from policy.range_bc import verify
    out, paths = _fit(tmp_path)
    args = ["--run", str(out), "--set", "val", "--steps", str(paths["v"]), "--cache-root", str(tmp_path / "caches"),
            "--out", str(tmp_path / "windows-report.json"),
            "--report-sha256", hashlib.sha256((out / "report.json").read_bytes()).hexdigest()]
    assert verify.main(args) == 0
    rep = json.loads((tmp_path / "windows-report.json").read_text())
    assert rep["ok"] and rep["checks"]["no_live_io"]["ok"] and rep["checks"]["code_closure"]["ok"]
    with pytest.raises(FileExistsError):
        verify.main(args)


PARITY_FAIL = {"rule": "p2", "thresholds": {}, "P1": {"pass": True}, "P3": {"pass": True}, "sources": {},
               "pass": False}


def test_the_candidate_rule_needs_p2prime_and_the_validation_margin():
    ok = {"rule": "p2prime", "pass": True}
    v = lambda h, n: {"val": {"model": {"headline_self_fed_macro_press_f1": h},
                              "model_nohud": {"headline_self_fed_macro_press_f1": n}}}
    assert train.choose_candidate(None, v(.9, .1))[0] == "model_nohud"
    assert train.choose_candidate({"rule": "p2", "pass": True}, v(.9, .1))[0] == "model_nohud"   # run 1's rule
    assert train.choose_candidate({"rule": "p2prime", "pass": False}, v(.9, .1))[0] == "model_nohud"
    assert train.choose_candidate(ok, v(.54, .5))[0] == "model_nohud"                             # below +0.05
    assert train.choose_candidate(ok, v(.56, .5))[0] == "model"
    assert train.choose_candidate(ok, {})[0] == "model_nohud"                                     # no validation


@pytest.mark.usefixtures("no_live_io_modules")
def test_a_failed_parity_makes_the_no_hud_arm_the_candidate_with_stride_and_unknown_pitch(tmp_path):
    from policy.range_bc import verify
    parity = tmp_path / "parity.json"
    parity.write_text(json.dumps(PARITY_FAIL))
    out, paths = _fit(tmp_path, ["--stride", "64", "--hud-parity", str(parity)], pitch_gain=None)
    r = json.loads((out / "report.json").read_text())
    assert r["candidate"] == "model_nohud" and r["candidate_checkpoint"] == "model_nohud-seed0.pt"
    assert r["hud_parity"]["pass"] is False and r["config"]["stride"] == 64
    assert r["train_statistics"]["pitch_gain_known"] is False
    for arm in ("model", "model_nohud"):
        v = r["gates"]["val"][arm]
        assert v["pitch_gain_known"] is False and v["pilot_worthy"] is False
    assert r["metrics"]["val"]["self_fed"]["model_nohud"]["0"]["all"]["camera_axes"] == ["yaw"]
    model, _ = train.load_checkpoint(out / "model_nohud-seed0.pt")
    assert not hasattr(model, "hud_enc")
    ok, rep = verify.verify(out, "val", [paths["v"]], tmp_path / "caches", denylist=steps.load_denylist(),
                            report_sha256=hashlib.sha256((out / "report.json").read_bytes()).hexdigest())
    assert ok, rep["failed"]


# ---- replay source: an unknown channel never reaches the loss ----------------------------------------------------------

def test_a_replay_row_with_unknown_movement_never_contributes_to_the_movement_loss(tmp_path):
    header, rows = fixture.replay_session("rp", runs=(150,), seed=3)
    path = fixture.write(tmp_path / "rp.jsonl", header, rows)
    session = steps.load(path)
    fake_cache(tmp_path / "caches" / "rp", session)
    arr = train.SessionArrays(session, cache.open_cache(tmp_path / "caches" / "rp", session))
    b = train.Batches([arr]).batch([0])                                          # the run's first window: no burn-in
    move = [vocab.INDEX[n] for n in fixture.REPLAY_MOVE]
    unknown = [k for k in range(96) if rows[k]["held_known"][move[0]] is False]
    known = [k for k in range(96) if rows[k]["held_known"][move[0]] and rows[k]["gap_free"]]
    assert unknown and known
    assert not b["act_mask"][0, unknown][:, :, move].any()                      # every channel of every direction
    # gradient: exactly zero on unknown movement, non-zero where movement is known
    acts = torch.zeros(1, 96, 3, vocab.N, requires_grad=True)
    cams = torch.zeros(1, 96, 2, vocab.CAMERA_CLASSES, requires_grad=True)
    train.total_loss(train.loss_terms(acts, cams, b, torch.ones(2, vocab.N))).backward()
    g = acts.grad[0][:, :, move]
    assert g[unknown].abs().sum() == 0 and g[known].abs().sum() > 0
    # and the loss does not move when the (masked) values behind an unknown label change
    flipped = dict(b)
    act = b["act"].clone()
    act[0, torch.tensor(unknown)[:, None], :, torch.tensor(move)[None, :]] = 1.
    flipped["act"] = act
    base = train.total_loss(train.loss_terms(acts.detach(), cams.detach(), b, torch.ones(2, vocab.N)))
    after = train.total_loss(train.loss_terms(acts.detach(), cams.detach(), flipped, torch.ones(2, vocab.N)))
    assert torch.equal(base, after)


# ---- replay press windows (the window-level loss; lane doc "Replay window-level loss") -------------------------------

def replay_window_arrays(tmp_path, name="rw", lag=0):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = fixture.write_replay_windows(tmp_path, name)
    session = steps.load(path)
    fake_cache(tmp_path / "caches" / name, session)
    return train.SessionArrays(session, cache.open_cache(tmp_path / "caches" / name, session), lag=lag,
                               press_windows=steps.load_windows(session))


def test_the_window_term_is_zero_at_its_optimum_and_matches_the_closed_form():
    z = torch.full((12,), -3.)
    z[5] = 40.                                                                  # one press certain
    assert float(train.window_nll(z)) < 1e-6
    z = torch.linspace(-4, 1, 12, dtype=torch.float64)
    total = float(torch.nn.functional.softplus(z).sum())
    assert abs(float(train.window_nll(z)) - -math.log(1 - math.exp(-total))) < 1e-6
    assert float(train.window_nll(torch.full((3,), -60.))) == pytest.approx(-math.log(1e-12), rel=1e-4)   # capped


def test_the_window_term_has_gradient_only_inside_its_window_and_only_for_its_action():
    t, wc = 96, vocab.INDEX["web_cluster"]
    batch = {"act": torch.zeros(1, t, 3, vocab.N), "act_mask": torch.zeros(1, t, 3, vocab.N, dtype=torch.bool),
             "camera": torch.full((1, t, 2), vocab.ZERO_CLASS, dtype=torch.long),
             "camera_mask": torch.zeros(1, t, 2, dtype=torch.bool),
             "win_index": torch.tensor([[0, wc, 20, 36]])}
    acts = torch.full((1, t, 3, vocab.N), -1., requires_grad=True)
    cams = torch.zeros(1, t, 2, vocab.CAMERA_CLASSES, requires_grad=True)
    terms = train.loss_terms(acts, cams, batch, torch.ones(2, vocab.N))
    train.total_loss(terms).backward()
    g = acts.grad[0]
    assert (g[20:36, 1, wc] != 0).all()                                         # every step of the window
    assert g[:20].abs().sum() == 0 and g[36:].abs().sum() == 0                  # nothing outside it
    other = torch.ones(vocab.N, dtype=torch.bool)
    other[wc] = False
    assert g[:, :, other].abs().sum() == 0 and g[:, (0, 2)].abs().sum() == 0    # no other action, hold or release
    # one window over no known entries: the press term is that window's NLL, weighted by its action's pos_weight
    pw = torch.ones(2, vocab.N)
    pw[0, wc] = 3.
    expected = 3. * train.window_nll(acts.detach()[0, 20:36, 1, wc])
    assert torch.allclose(train.loss_terms(acts.detach(), cams.detach(), batch, pw)["press"], expected)


def test_each_window_is_scored_once_per_epoch_and_window_only_sequences_carry_no_step_loss(tmp_path):
    arr = replay_window_arrays(tmp_path)
    b64 = train.Batches([arr], stride=64, frames=False)
    assert b64.window_report["window_only_sequences"] == 1 == len(b64.window_only)
    assert b64.window_report["by_action"]["get_over_here"] == {
        "complete": 2, "counted": 2, "scored_base": 1, "scored_own": 1, "unplaced": 0, "overlap_pairs": 0,
        "largest_group": 1}
    batch = b64.batch(list(range(len(b64.windows))))
    seen = sorted((c, t0 + b64.windows[i][1], t1 - 1 + b64.windows[i][1]) for i, c, t0, t1 in
                  batch["win_index"].tolist())
    assert seen == sorted(arr.press_windows.counted)                             # every counted window, once
    (own,) = b64.window_only
    assert not batch["act_mask"][own].any() and not batch["camera_mask"][own].any()
    assert batch["act_mask"][[i for i in range(len(b64.windows)) if i != own]].any()
    b48 = train.Batches([arr], stride=48, frames=False)
    assert not b48.window_only and len(b48.batch(list(range(len(b48.windows))))["win_index"]) == 6
    # with lag 1 the window's positions move one step earlier, still one scoring each
    lagged = replay_window_arrays(tmp_path / "lag", lag=1)
    bl = train.Batches([lagged], stride=64, frames=False)
    rows = sorted((t0 + bl.windows[i][1], c) for i, c, t0, _ in
                  bl.batch(list(range(len(bl.windows))))["win_index"].tolist())
    assert rows[0] == (9, vocab.INDEX["web_cluster"]) and len(rows) == 6


def test_human_batches_and_the_human_loss_are_untouched(tmp_path):
    arr = arrays(tmp_path)
    assert arr.press_windows is None
    b = train.Batches([arr])
    assert not b.has_windows and b.window_report is None and not b.window_only
    batch = b.batch([0, 1])
    assert set(batch) == {"global", "crop", "hud", "prev", "act", "act_mask", "camera", "camera_mask", "regime", "aug"}
    acts = torch.randn(2, 96, 3, vocab.N)
    cams = torch.randn(2, 96, 2, vocab.CAMERA_CLASSES)
    pw = torch.full((2, vocab.N), 4.)
    mask = batch["act_mask"].float()
    bce = torch.nn.functional.binary_cross_entropy_with_logits(acts[:, :, 1], batch["act"][:, :, 1], reduction="none",
                                                               pos_weight=pw[0])
    press = (bce * mask[:, :, 1]).sum() / mask[:, :, 1].sum().clamp_min(1)     # today's expression, verbatim
    assert torch.equal(train.loss_terms(acts, cams, batch, pw)["press"], press)


def test_replay_evaluation_reports_window_recall_and_the_cli_still_refuses_replay(tmp_path):
    arr = replay_window_arrays(tmp_path)
    torch.manual_seed(0)
    model = Policy(replace(TINY, hud=False)).eval()
    relabelled = dataclasses.replace(arr.session, header={**arr.session.header, "split": "train"})
    placed, _ = steps.place_windows(arr.session, arr.press_windows.counted)
    stats = steps.train_statistics([relabelled], windows={arr.session.session_id: placed})
    ar2 = baselines.fit_ar2([relabelled])
    evaluation, _ = train.evaluate_set({("model_nohud", 0): model}, [arr], stats, ar2, device="cpu")
    block = evaluation["windows"]["model_nohud"][0]
    assert set(block) == {"tf", "sf"}
    assert block["tf"]["by_action"]["web_cluster"]["windows"] == 3                # complete cast windows, any length
    assert block["tf"]["by_action"]["amazing_combo"]["windows"] == 2              # the 70-row one is evaluated
    # review N4: each block carries the set's window counts, by kind and by how training would score them
    counts = {"web_cluster": {"windows": 4, "complete": 3, "partial_or_flagged": 1, "too_long": 0, "scored_base": 3,
                              "scored_window_only": 0, "unplaced": 0},
              "get_over_here": {"windows": 3, "complete": 2, "partial_or_flagged": 1, "too_long": 0, "scored_base": 2,
                                "scored_window_only": 0, "unplaced": 0},
              "amazing_combo": {"windows": 2, "complete": 2, "partial_or_flagged": 0, "too_long": 1, "scored_base": 1,
                                "scored_window_only": 0, "unplaced": 0}}
    assert block["tf"]["counts"] == block["sf"]["counts"] == counts            # the default stride, 48
    at64 = train.window_counts([arr], stride=64)
    assert at64["get_over_here"]["scored_base"] == 1 and at64["get_over_here"]["scored_window_only"] == 1
    for a in at64.values():
        assert a["windows"] == a["complete"] + a["partial_or_flagged"]
        assert a["complete"] == a["too_long"] + a["scored_base"] + a["scored_window_only"] + a["unplaced"]
    with pytest.raises(steps.StepError, match="replay"):                        # no CLI path loads a replay table
        train.main(["--train", str(arr.session.path), "--cache-root", str(tmp_path / "caches"), "--out",
                    str(tmp_path / "o"), "--scope", "smoke", "--epochs", "1", "--model-config",
                    json.dumps(TINY.as_dict())])


# ---- countermeasures: executed metrics and self-conditioned history (fit-selffed-diag.md) -----------------------------

def _decode_like_predict_self(acts, cams, prev, live, pitch_known):
    """The reference for own_previous: predict_self's per-step decoding, written with the executor and steps helpers."""
    out = prev.clone()
    for i in range(prev.shape[0]):
        prev_held = [int(v >= .5) and live[c] for c, v in enumerate(prev[i, 0, :vocab.N].tolist())]
        for t in range(prev.shape[1] - 1):
            p = torch.sigmoid(acts[i, t])
            m = torch.softmax(cams[i, t], -1)
            held, press, release = train.executor.decode_step(p[0].tolist(), p[1].tolist(), p[2].tolist(),
                                                              prev_held, live)
            yaw, pitch = train.executor.saturate(vocab.class_degrees(vocab.median_class(m[0].tolist())),
                                                 vocab.class_degrees(vocab.median_class(m[1].tolist())))
            sent = {"held": held, "press": press, "release": release, "known": [True] * vocab.N,
                    "cy": vocab.camera_class(yaw), "cp": vocab.camera_class(pitch) if pitch_known[i] else None}
            out[i, t + 1] = torch.tensor(steps.prev_vector(sent))
            prev_held = held
    return out


def test_own_previous_decodes_exactly_as_predict_self_sends():
    g = torch.Generator().manual_seed(0)
    b, t = 4, 40
    acts = torch.randn(b, t, 3, vocab.N, generator=g) * 2
    cams = torch.randn(b, t, 2, vocab.CAMERA_CLASSES, generator=g) * 3
    prev = (torch.rand(b, t, steps.PREV_DIM, generator=g) < .3).float()
    live = list(vocab.live_mask([1000] * vocab.N))
    pk = [True, False, True, False]
    got = train.own_previous(acts, cams, prev, live, pk)
    assert torch.equal(got, _decode_like_predict_self(acts, cams, prev, live, pk))
    assert torch.equal(got[:, 0], prev[:, 0])                            # step 0 keeps its input


# fit-review F2's retained float32 logits. On the reviewer's x86 CPU their float32 cumulative softmax mass through
# class 14 is exactly 0.5 while the Python sum is 0.4999999988358468, so vocab.median_class picks 15 and a float32
# cumsum 14. Softmax rounding is platform-dependent (the Mac's arm64 gives 0.50000006), so these rows are kept as a
# parity regression on both sides of 0.5, and the platform-independent boundary is built below from exact float32 sums.
MEDIAN_BOUNDARY = [-3.776796340942383, -1.7289953231811523, -4.881049156188965, -4.255186080932617, -5.356229782104492,
                   -2.7890396118164062, -4.216971397399902, -1.5013617277145386, -4.61875057220459, -1.9501867294311523,
                   -2.8966712951660156, -1.6201971769332886, -4.859790802001953, -3.8455939292907715,
                   -3.2241733074188232, -4.893590450286865, -2.5582942962646484, -1.9174140691757202,
                   -4.318824768066406, -2.1624302864074707, -4.95439338684082, -2.4538626670837402,
                   -2.5275580883026123, -3.510953426361084, -3.5381813049316406, -3.2958667278289795,
                   -3.912397623062134, -2.1852030754089355, -3.802489995956421, -1.576985478401184, -4.653883934020996]


def _float32_half_boundary():
    """float32 probabilities whose first two sum to just under 0.5 exactly (as Python floats) but to 0.5 when added
    in float32: vocab.median_class must not stop at class 1."""
    a, b = torch.tensor(.3), torch.tensor(.2)
    while not (float(a) + float(b) < .5 <= float(a + b)):
        b = torch.nextafter(b, torch.tensor(0.))
    rest = (1 - float(a) - float(b)) / (vocab.CAMERA_CLASSES - 2)
    return torch.tensor([float(a), float(b)] + [rest] * (vocab.CAMERA_CLASSES - 2))


def test_the_median_class_matches_the_reference_where_float32_reaches_one_half_early():
    probs = _float32_half_boundary()
    assert float(probs.cumsum(-1)[1]) >= .5 > sum(probs[:2].tolist())         # the trap a float32 cumsum falls into
    want = vocab.median_class(probs.tolist())
    assert want == 2
    assert train._median_classes(probs[None]).tolist() == [want]
    above = probs.clone()
    above[1] = torch.nextafter(above[1], torch.tensor(1.))
    while sum(above[:2].tolist()) < .5:
        above[1] = torch.nextafter(above[1], torch.tensor(1.))
    assert train._median_classes(above[None]).tolist() == [vocab.median_class(above.tolist())] == [1]


def test_own_previous_matches_the_reference_on_the_reviews_boundary_logits():
    below = torch.tensor(MEDIAN_BOUNDARY)
    above = below.clone()
    above[14] += 1e-3                                                    # the other side: the mass passes 0.5 at 14
    live = list(vocab.live_mask([1000] * vocab.N))
    for row in (below, above):
        cams = row.expand(1, 3, 2, vocab.CAMERA_CLASSES).clone()
        acts = torch.zeros(1, 3, 3, vocab.N)
        prev = torch.zeros(1, 3, steps.PREV_DIM)
        assert torch.equal(train.own_previous(acts, cams, prev, live, [True]),
                           _decode_like_predict_self(acts, cams, prev, live, [True]))
    assert vocab.median_class(torch.softmax(above, -1).tolist()) == 14


def test_self_condition_is_off_by_default_acts_only_through_the_history_and_is_reproducible(tmp_path):
    arr = arrays(tmp_path)
    stats = steps.train_statistics([arr.session])
    batches = train.Batches([arr])
    sha = lambda m: hashlib.sha256(train.checkpoint_bytes(m, {"seed": 3})).hexdigest()
    kw = {"seed": 3, "epochs": 3, "batch_size": 2, "lr": 3e-3, "warmup": 5}
    default = sha(train.fit(batches, TINY, stats, **kw)[0])
    assert sha(train.fit(batches, TINY, stats, self_condition=0., **kw)[0]) == default
    on = [sha(train.fit(batches, TINY, stats, self_condition=.5, self_condition_ramp=.5, **kw)[0]) for _ in range(2)]
    assert on[0] == on[1] != default
    blind = replace(TINY, history=False)                                 # no history input: nothing to replace
    assert sha(train.fit(batches, blind, stats, self_condition=.5, **kw)[0]) == sha(train.fit(batches, blind, stats, **kw)[0])
    assert sha(train.fit(batches, TINY, stats, prev_dropout=.5, **kw)[0]) != default
    with pytest.raises(train.FitError, match="self_condition"):
        train.fit(batches, TINY, stats, self_condition=1.5, **kw)
    with pytest.raises(train.FitError, match="prev_dropout"):
        train.fit(batches, TINY, stats, prev_dropout=1., **kw)


def test_executed_runs_are_the_executors_decisions(tmp_path):
    arr = arrays(tmp_path, split="val", name="v")
    torch.manual_seed(0)
    model = Policy(TINY)
    live = list(vocab.live_mask([1000] * vocab.N))
    tf = train.predict_teacher(model, [arr])
    ex = train.executed_runs(tf, live)
    my, mp = train.executor.max_step_degrees()
    prev_held = [0] * vocab.N
    for (r1, p), (r2, e) in zip(tf[0], ex[0]):
        assert r1 is r2
        held, press, release = train.executor.decode_step(p["held"], p["press"], p["release"], prev_held, live)
        assert (e["held"], e["press"], e["release"]) == tuple([float(v) for v in x] for x in (held, press, release))
        assert abs(e["yaw"]) <= my + 1e-9 and (e["pitch"] is None or abs(e["pitch"]) <= mp + 1e-9)
        prev_held = held


BASELINE_NAMES = ("persistence", "zero_motion", "prior", "echo", "ar2")


def test_the_fit_cli_reports_the_new_metrics_and_records_the_training_options(tmp_path):
    out, _ = _fit(tmp_path)
    r = json.loads((out / "report.json").read_text())
    assert r["config"]["prev_dropout"] == .2 and r["config"]["self_condition"] is None
    payload = torch.load(out / "model_nohud-seed0.pt", weights_only=True)
    assert set(payload["meta"]) == {"arm", "seed", "lag", "regimes"}     # default checkpoints: meta as before
    for split in ("dev", "val"):
        m = r["metrics"][split]
        assert set(m["executed_teacher_forced"]) == set(m["teacher_forced"]) - set(BASELINE_NAMES)
        assert m["executed_teacher_forced"]["model_nohud"]["0"]["window"] == train.metrics.EXECUTED_TEACHER
        c = m["self_fed_checks"]["model_nohud"]["0"]
        assert {"hold_onset_recall", "press_ratio", "any_hold_share", "human_any_hold_share", "camera_mae",
                "zero_motion_camera_mae", "held_change_f1"} <= set(c)
        assert c["zero_motion_camera_mae"] == m["teacher_forced"]["zero_motion"]["all"]["camera_mae_mean"]
        assert c["camera_mae"] == m["self_fed"]["model_nohud"]["0"]["all"]["camera_mae_mean"]
    (tmp_path / "on").mkdir(), (tmp_path / "bad").mkdir()
    on, _ = _fit(tmp_path / "on", ["--self-condition", ".5", "--self-condition-ramp", ".25", "--prev-dropout", ".3",
                                   "--frames-only-nohud"])
    r = json.loads((on / "report.json").read_text())
    assert r["config"]["prev_dropout"] == .3
    assert r["config"]["self_condition"] == {"p": .5, "ramp": .25, "rule": train.SELF_CONDITION_RULE}
    assert "frames_only_nohud" in r["config"]["arms"] and "frames_only_nohud-seed0.pt" in r["checkpoints"]
    assert set(r["metrics"]["dev"]["self_fed_checks"]) >= {"model_nohud", "frames_only_nohud"}
    payload = torch.load(on / "model_nohud-seed0.pt", weights_only=True)
    assert payload["meta"]["self_condition"] == {"p": .5, "ramp": .25} and payload["meta"]["prev_dropout"] == .3
    blind = torch.load(on / "frames_only_nohud-seed0.pt", weights_only=True)["config"]
    assert blind["history"] is False and blind["hud"] is False
    with pytest.raises(train.FitError, match="self-condition"):
        _fit(tmp_path / "bad", ["--self-condition", "2"])
