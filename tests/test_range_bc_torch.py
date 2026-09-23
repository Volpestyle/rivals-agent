"""The end-to-end range fit's torch pieces: model, loss, deterministic trainer, both evaluation modes, checkpoints,
the fit CLI and the bench. Runs with `uv run --group execution pytest tests/test_range_bc_torch.py` (skipped without
torch)."""
from dataclasses import replace
import hashlib
import json

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import bench, cache, fixture, steps, train, vocab  # noqa: E402
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
    assert parameter_count(model) == 4_808_768, counts      # the lane doc's table
    acts, cams, state = model(*zeros(), torch.zeros(1, 2, steps.PREV_DIM))
    assert acts.shape == (1, 2, 3, vocab.N) and cams.shape == (1, 2, 2, vocab.CAMERA_CLASSES)
    assert state[0].shape == (1, 1, 512)


def test_twins():
    history = Policy(replace(Config(), frames=False))
    assert not hasattr(history, "global_enc") and parameter_count(history) == 2_555_240
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
    assert r["sealed_denylist"]["default"] is True
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
    # today the package is untracked, so a real fit is refused before anything is trained
    with pytest.raises(train.FitError, match="untracked|uncommitted"):
        train.main(base + ["--out", str(tmp_path / "e"), "--preregistration", str(pre), "--hud-parity", str(parity)])
    assert not (tmp_path / "e").exists()


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
