"""policy/idm: the IDM model, its masked loss, the deterministic trainer, checkpoints and their provenance, the pixel
binding, the predictor's abstentions and stated std, Gate 1 wiring and the report. Synthetic fixtures only.

    uv run --group execution pytest tests/test_idm_model.py     (skipped without torch)

The fixture: a textured world that shifts horizontally by each interval's yaw (PX_PER_DEG pixels per degree), and a
HUD crop that lights up at an interval whose `jump` was pressed -- so the camera and edge heads have a signal.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policy import idm_targets as T  # noqa: E402
from policy.idm import frames as FR, model as M, train as TR  # noqa: E402
from policy.range_bc import vocab  # noqa: E402

TINY = M.Config(window=2, height=24, width=40, channels=(4, 8), embed=16, hud_channels=(4,), hud_embed=8, hidden=16,
                test_scale=True)
N, DT = vocab.N, 16_666_667
JUMP, FWD = vocab.INDEX["jump"], vocab.INDEX["move_forward"]
PX_PER_DEG = 2.0
GAIN = 0.0330738


def header(sid, split="train"):
    return {"format": T.FORMAT, "session_id": sid, "media_sha256": hashlib.sha256(sid.encode()).hexdigest(),
            "session_group": sid, "split": split, "parent_step_ns": 33_333_333, "frame_period_ns": 8_333_333,
            "actions": list(vocab.NAMES), "bindings": {}, "swing_mode": {}, "accel_on": True, "patch": "p",
            "settings_hash": "h", "pad_envelope": dict(T.PAD_ENVELOPE), "source": {},
            "calibration": {"kind": "slow_turn_constant", "yaw_deg_per_count": GAIN, "pitch_deg_per_count": GAIN,
                            "pitch": {"kind": "derived_equal_sensitivity"}}}


def session(tmp_path, sid, *, n=60, split="train", seed=0, hide=(), config=TINY, jump_p=0.25):
    """Targets (valid for the reader) and a frame store for n intervals. `hide`: intervals whose end frame is left
    out of the store. The fixture's pts equals the frame index."""
    rng = np.random.default_rng(seed)
    world = rng.integers(0, 256, (config.height, config.width + 360), dtype=np.uint8)
    counts = rng.choice([-60, -30, 0, 30, 60], size=n)                  # dx per interval
    jumps = rng.random(n) < jump_p
    rows, frames, hud = [], {}, {}
    offset = 0.0
    frame_px = {}
    for k in range(-config.window - 1, n + config.window + 1):             # the world's position at each end frame
        if 0 <= k < n:
            offset += counts[k] * GAIN * PX_PER_DEG
        frame_px[2 * k + 2] = offset
    for f, px in frame_px.items():
        if (f - 2) // 2 in hide:
            continue
        start = 180 + int(round(px))
        frames[f] = np.ascontiguousarray(world[:, start:start + config.width])
        crop = np.zeros(FR.HUD_SHAPE, np.uint8)
        k = (f - 2) // 2
        if 0 <= k < n and jumps[k]:
            crop[:, :, 0] = 255
        hud[f] = crop
    for k in range(n):
        dx = int(counts[k])
        yaw, pitch, beyond = T.degrees(dx, 0, header(sid)["calibration"], DT)
        rate, regime = T.gain_regime(dx, 0, DT)
        press = [0] * N
        release = [0] * N
        if jumps[k]:
            press[JUMP] = release[JUMP] = 1
        rows.append({"i": k, "parent": k // 2, "half": k % 2, "run": "r0", "segment": "s", "suitability": "accepted",
                     "regime": "normal", "gap_free": True, "t0_ns": k * DT, "t1_ns": (k + 1) * DT,
                     "frame0": {"frame_index": 2 * k, "pts": 2 * k, "composition_ns": k * DT},
                     "frame1": {"frame_index": 2 * k + 2, "pts": 2 * k + 2, "composition_ns": (k + 1) * DT},
                     "mouse_dx": dx, "mouse_dy": 0, "yaw_deg": yaw, "pitch_deg": pitch, "beyond_pad_envelope": beyond,
                     "mouse_rate_cps": None if rate is None else round(rate, 3), "gain_regime": regime,
                     "held_start": [0] * N, "held_end": [0] * N, "held_known": [True] * N, "press": press,
                     "release": release})
    path = tmp_path / f"{sid}.idm.jsonl"
    T.write(path, header(sid, split), rows)
    store_dir = tmp_path / "frames" / sid
    FR.write_store(store_dir, session_id=sid, media_sha256=header(sid)["media_sha256"], frames=frames, hud=hud,
                   pts={f: f for f in frames})
    return T.load(path), FR.FrameStore(store_dir, verify=True), path


SUPPORTED = {a: a in ("jump", "move_forward") for a in vocab.NAMES}


def prov(model, t, path, store, seed=0):
    return TR.provenance(seed=seed, supported=model.support, train_press_counts={"jump": 1},
                         targets={t.session_id: TR.target_entry(t, T.sha256(path))},
                         frame_stores={t.session_id: TR.store_entry(store)})


def fitted(model):
    """An untrained model given the fixture's support set, as fit() or a checkpoint would."""
    model.support = TR.support_set(SUPPORTED)
    return model


def examples(tmp_path, sid="a", **kw):
    t, store, _ = session(tmp_path, sid, **kw)
    return TR.Examples([(t, store)], TINY, SUPPORTED), t, store


def test_the_motion_input_is_at_least_448_wide_outside_test_fixtures():
    with pytest.raises(ValueError, match="448"):
        M.Config(width=320)
    model = M.IDM(M.Config())
    press, cam = model(torch.zeros(1, 16, 252, 448), torch.zeros(1, 6, 80, 200))
    assert press.shape == (1, N) and cam.shape == (1, 4)
    assert M.Config().differences == 16                                  # +-8 intervals (F3)


def test_examples_carry_masks_and_skip_rows_without_frames(tmp_path):
    ex, t, _ = examples(tmp_path, hide=(10,))
    lost = 2 * TINY.window + 1                                           # every row whose window holds that frame
    assert len(ex) == len(t.rows) - lost and ex.missing == lost
    assert not ex.press_mask[:, vocab.INDEX["ultimate"]].any()           # unsupported: never a label
    assert ex.press_mask[:, JUMP].all() and ex.camera_mask.all()
    motion, hud = ex.inputs([0, 1])
    assert motion.shape == (2, 2 * TINY.window, TINY.height, TINY.width) and hud.shape == (2, 6, 80, 200)


def test_masked_entries_carry_no_loss_and_no_gradient(tmp_path):
    ex, _, _ = examples(tmp_path)
    stats = TR.train_statistics(ex)
    model = M.IDM(TINY)
    idx = list(range(8))
    motion, hud = ex.inputs(idx)
    logits, cam = model(motion, hud)
    press, mask = ex.press[idx].clone(), ex.press_mask[idx].clone()
    cmask = ex.camera_mask[idx].clone()
    cmask[:, 1] = False
    base = TR.loss_terms(logits, cam, press, mask, ex.camera[idx], cmask, ex.camera_sigma[idx], stats["pos_weight"])
    ult = vocab.INDEX["ultimate"]
    press[:, ult] = 1 - press[:, ult]                                    # flip a masked label
    camera = ex.camera[idx].clone()
    camera[:, 1] += 50.0                                                 # and a masked camera axis
    other = TR.loss_terms(logits, cam, press, mask, camera, cmask, ex.camera_sigma[idx], stats["pos_weight"])
    assert torch.equal(base["total"], other["total"])
    logits.retain_grad()
    other["total"].backward()
    assert torch.all(logits.grad[:, ult] == 0)


def test_a_non_finite_masked_camera_target_leaves_the_gradients_finite(tmp_path):
    """torch.where's backward is 0 x the masked branch's gradient, and 0 x NaN is NaN: masked slots are sanitised
    before the NLL, so the gradients are finite and equal to a clean batch's."""
    ex, _, _ = examples(tmp_path)
    stats = TR.train_statistics(ex)
    idx = list(range(6))
    grads = []
    for poison in (False, True):
        torch.manual_seed(0)
        model = M.IDM(TINY)
        logits, cam = model(*ex.inputs(idx))
        camera, sigma, mask = ex.camera[idx].clone(), ex.camera_sigma[idx].clone(), ex.camera_mask[idx].clone()
        mask[0, :] = False
        mask[1, 1] = False
        if poison:
            camera[0, 0], camera[1, 1], sigma[0, 1] = float("nan"), float("inf"), float("nan")
        loss = TR.loss_terms(logits, cam, ex.press[idx], ex.press_mask[idx], camera, mask, sigma, stats["pos_weight"])
        assert torch.isfinite(loss["total"])
        loss["total"].backward()
        grads.append([p.grad.clone() for p in model.parameters()])
    assert all(torch.isfinite(g).all() for g in grads[1])
    assert all(torch.equal(a, b) for a, b in zip(*grads))


def test_extrapolated_targets_weigh_less_in_the_camera_loss(tmp_path):
    """The NLL's variance adds the target's sigma: the same miss costs less on an extrapolated (wider) target."""
    mu = torch.zeros(1, 4)
    y = torch.tensor([[2.0, 0.0]])
    mask = torch.tensor([[True, False]])
    none = torch.zeros(1, N, dtype=torch.bool)
    tight = TR.loss_terms(torch.zeros(1, N), mu, torch.zeros(1, N), none, y, mask, torch.tensor([[0.02, 0.0]]),
                          torch.ones(N))["camera"]
    wide = TR.loss_terms(torch.zeros(1, N), mu, torch.zeros(1, N), none, y, mask, torch.tensor([[0.5, 0.0]]),
                         torch.ones(N))["camera"]
    assert wide < tight


def test_beta_nll_is_off_by_default_and_rescales_only_the_gradient_weight(tmp_path):
    """The yaw falsification test's treatment: None is today's Gaussian NLL exactly; beta = 0.5 weights each element's
    NLL by stop-gradient(var ** beta), so d/d mu = var ** (beta - 1) (mu - y) and no gradient flows through the weight."""
    y, mask, sigma = torch.tensor([[3.0, -1.0]]), torch.tensor([[True, True]]), torch.tensor([[0.2, 0.1]])
    none = torch.zeros(1, N, dtype=torch.bool)

    def grads(**kw):
        out = torch.tensor([[0.5, 0.25, 1.2, -0.4]], requires_grad=True)
        loss = TR.loss_terms(torch.zeros(1, N), out, torch.zeros(1, N), none, y, mask, sigma, torch.ones(N), **kw)
        loss["camera"].backward()
        return loss["camera"].detach(), out.grad.clone()

    (l0, g0), (l1, g1) = grads(), grads(camera_beta=None)
    assert torch.equal(l0, l1) and torch.equal(g0, g1)                   # the default is today's loss, bit for bit
    _, gb = grads(camera_beta=0.5)
    var = torch.tensor([[1.2, -0.4]]).exp() + sigma ** 2
    mu = torch.tensor([[0.5, 0.25]])
    assert torch.allclose(gb[:, :2], var ** (0.5 - 1) * (mu - y) / 2, rtol=1e-5)       # the mean (mean over 2 elements)
    assert torch.allclose(gb[:, 2:], var ** 0.5 * g0[:, 2:], rtol=1e-5)               # log-variance: weighted only
    ex, _, _ = examples(tmp_path)
    with pytest.raises(TR.FitError, match="camera_beta"):
        TR.fit(ex, TINY, TR.train_statistics(ex), epochs=1, camera_beta=1.5)


def test_training_is_byte_reproducible_on_cpu_and_learns(tmp_path):
    t, store, path = session(tmp_path, "a")
    ex = TR.Examples([(t, store)], TINY, SUPPORTED)
    stats = TR.train_statistics(ex)
    shas, hist = [], None
    for _ in range(2):
        model, hist, _ = TR.fit(ex, TINY, stats, seed=3, epochs=6, batch_size=8, lr=3e-3)
        shas.append(hashlib.sha256(TR.checkpoint_bytes(model, prov(model, t, path, store, 3))).hexdigest())
    assert shas[0] == shas[1]
    assert hist[-1]["train_loss"] < hist[0]["train_loss"]
    other, _, _ = TR.fit(ex, TINY, stats, seed=4, epochs=1, batch_size=8)
    assert hashlib.sha256(TR.checkpoint_bytes(other, prov(other, t, path, store, 3))).hexdigest() != shas[0]


def test_training_refuses_a_val_file(tmp_path):
    ex, _, _ = examples(tmp_path, split="val")
    with pytest.raises(TR.FitError, match="only train"):
        TR.fit(ex, TINY, TR.train_statistics(ex), epochs=1)


def test_the_predictor_abstains_as_pre_registered(tmp_path):
    ex, t, store = examples(tmp_path, hide=(5,))
    model = fitted(M.IDM(TINY))
    preds = TR.predict(model, t, store)
    assert set(preds) == {r["i"] for r in t.rows}
    assert all(preds[i] == TR._abstain_all() for i in range(3, 8))      # their windows lack frame 12
    for p in preds.values():
        assert p["press"]["ultimate"] is None                            # unsupported: structurally unknown
        for a in ("jump", "move_forward"):
            v = p["press"][a]
            assert v is None or not (TR.ABSTAIN_BAND[0] < v < TR.ABSTAIN_BAND[1])
    with torch.no_grad():                                                # a very uncertain camera abstains
        model.camera[-1].bias[2:] = 5.0
    preds = TR.predict(model, t, store)
    assert all(p["yaw_deg"] is None for p in preds.values())


def test_the_reported_camera_std_includes_the_label_sigma_of_the_predicted_regime(tmp_path):
    t, store, _ = session(tmp_path, "a")
    model = fitted(M.IDM(TINY))

    def answer(yaw):
        with torch.no_grad():                                            # a model sure of itself: variance e^-12
            model.camera[-1].weight.zero_()
            model.camera[-1].bias.copy_(torch.tensor([yaw, 0.0, -12.0, -12.0]))
        return next(v for v in TR.predict(model, t, store).values() if v["gain_regime"] is not None)

    p = answer(10.0)
    assert p["gain_regime"] == "extrapolated"                            # 10 deg in 1/60 s is ~18,000 counts/s
    total = lambda label: (label ** 2 + np.exp(-12.0)) ** 0.5            # sqrt(label sigma^2 + model variance)
    assert p["yaw_std_deg"] == pytest.approx(total(0.5 * GAIN + 0.2 * 10.0), rel=1e-6)
    assert p["yaw_deg"] == pytest.approx(10.0)                           # 2.0 deg is inside the extrapolated bound
    p = answer(0.2)
    assert p["gain_regime"] == "calibrated" and p["yaw_std_deg"] == pytest.approx(total(0.5 * GAIN), rel=1e-6)
    p = answer(20.0)
    assert p["yaw_std_deg"] > TR.CAMERA_ABSTAIN_STD["extrapolated"] and p["yaw_deg"] is None


def test_gate1_scores_the_model_beside_both_baselines_and_the_checkpoint_carries_its_provenance(tmp_path):
    t, store, tpath = session(tmp_path, "train")
    ex = TR.Examples([(t, store)], TINY, SUPPORTED)
    model, _, _ = TR.fit(ex, TINY, TR.train_statistics(ex), seed=0, epochs=2, batch_size=8)
    assert model.support == TR.support_set(SUPPORTED)
    held, hstore, _ = session(tmp_path, "held", split="val", seed=9)
    result = TR.gate1(model, [(held, hstore)])
    assert set(result) == {"model", "zero", "persistence", "model_std_coverage", "pitch_truth"}
    cam = result["model"]["sessions"]["held"]["camera"]["yaw_deg"]
    assert "abs_error_deg_by_gain_regime" in cam and set(result["model"]["pooled"]["edges"]) == {"jump", "move_forward"}
    cov = result["model_std_coverage"]["held"]["yaw"]
    assert set(cov) == {"calibrated", "extrapolated"} and cov["extrapolated"]["evaluable"] > 0
    assert set(cov["calibrated"]) == {"evaluable", "answered", "abstention_rate", "within_1std", "within_2std"}
    assert result["pitch_truth"] == {"held": "derived_equal_sensitivity"}

    path = tmp_path / "m.pt"
    meta = prov(model, t, tpath, store)
    sha = TR.save_checkpoint(path, model, meta)
    loaded, payload = TR.load_checkpoint(path)
    assert payload["config"] == TINY.as_dict() and hashlib.sha256(path.read_bytes()).hexdigest() == sha
    m = payload["meta"]
    assert m["supported"] == TR.support_set(SUPPORTED) and loaded.support == m["supported"]
    assert m["train_press_counts"] == {"jump": 1} and m["seed"] == 0
    assert m["targets"]["train"]["sha256"] == T.sha256(tpath)
    assert m["targets"]["train"]["calibration"] == t.header["calibration"]
    assert m["targets"]["train"]["media_sha256"] == t.header["media_sha256"]
    assert m["frame_stores"]["train"]["frames_sha256"] == store.manifest["frames_sha256"]
    assert "policy/idm/train.py" in m["code_closure"] and "policy/idm_targets.py" in m["code_closure"]
    with pytest.raises(FileExistsError):
        TR.save_checkpoint(path, model, meta)


def test_the_support_set_comes_from_the_checkpoint(tmp_path):
    t, store, path = session(tmp_path, "a")
    model = fitted(M.IDM(TINY))
    with pytest.raises(TR.FitError, match="lacks"):
        TR.checkpoint_bytes(model, {"seed": 0})
    wider = {**SUPPORTED, "ultimate": True}
    with pytest.raises(TR.FitError, match="differs from the one the model was trained with"):
        TR.checkpoint_bytes(model, {**prov(model, t, path, store), "supported": TR.support_set(wider)})
    with pytest.raises(TR.FitError, match="differs from the checkpoint"):
        TR.predict(model, t, store, wider)                               # a caller cannot widen the support set
    assert TR.predict(model, t, store, SUPPORTED)                        # the same set is accepted
    with pytest.raises(TR.FitError, match="no support set"):
        TR.predict(M.IDM(TINY), t, store)


def test_a_real_fit_refuses_uncommitted_code_before_reading_anything(monkeypatch):
    def refuse(files):
        assert "policy/idm/train.py" in files
        raise TR.FitError("uncommitted")
    monkeypatch.setattr(TR, "require_committed", refuse)
    monkeypatch.setattr(T, "load", lambda *a, **k: pytest.fail("a target file was read"))
    with pytest.raises(TR.FitError, match="uncommitted"):
        TR.main(["fit", "--train", "x", "--heldout", "y", "--frames-root", "z", "--out", "o"])


def test_pixels_are_bound_to_the_targets_media_and_pts(tmp_path):
    t, _, _ = session(tmp_path, "a")
    other = tmp_path / "other"
    frames = {f: np.zeros((TINY.height, TINY.width), np.uint8) for f in range(0, 130, 2)}
    hud = {f: np.zeros(FR.HUD_SHAPE, np.uint8) for f in frames}
    FR.write_store(other / "media", session_id="a", media_sha256="0" * 64, frames=frames, hud=hud,
                   pts={f: f for f in frames})
    with pytest.raises(TR.FitError, match="other media"):
        TR.Examples([(t, FR.FrameStore(other / "media"))], TINY, SUPPORTED)
    FR.write_store(other / "pts", session_id="a", media_sha256=t.header["media_sha256"], frames=frames, hud=hud,
                   pts={f: f + (1 if f == 40 else 0) for f in frames})
    with pytest.raises(TR.FitError, match="frame 40 has pts 41"):
        TR.Examples([(t, FR.FrameStore(other / "pts"))], TINY, SUPPORTED)
    slow = T.Targets({**t.header, "frame_period_ns": 16_666_667}, t.rows)
    with pytest.raises(TR.FitError, match="120 fps"):
        TR.Examples([(slow, FR.FrameStore(tmp_path / "frames" / "a"))], TINY, SUPPORTED)


def test_a_frame_store_of_a_sealed_session_is_refused(tmp_path):
    session(tmp_path, "z")
    media = FR.FrameStore(tmp_path / "frames" / "z").manifest["media_sha256"]
    for row in ({"session_id": "z", "media_sha256": "f" * 64}, {"session_id": "other", "media_sha256": media}):
        with pytest.raises(FR.StoreError, match="sealed"):
            FR.FrameStore(tmp_path / "frames" / "z", denylist={"sessions": [row]})


def test_the_report_is_written_once_with_every_field(tmp_path):
    fields = {k: None for k in TR.REPORT_REQUIRED}
    fields["test_opened"] = False
    path = TR.write_report(tmp_path / "r.json", **fields)
    assert json.loads(path.read_text())["format"] == TR.REPORT_FORMAT
    with pytest.raises(FileExistsError):
        TR.write_report(path, **fields)
    with pytest.raises(TR.FitError, match="lacks"):
        TR.write_report(tmp_path / "x.json", scope="s")
    with pytest.raises(TR.FitError, match="never opens the test"):
        TR.write_report(tmp_path / "y.json", **{**fields, "test_opened": True})


def test_a_frame_store_refuses_a_tampered_array(tmp_path):
    session(tmp_path, "z")
    arr = tmp_path / "frames" / "z" / "frames.u8"
    data = bytearray(arr.read_bytes())
    data[0] ^= 1
    arr.write_bytes(bytes(data))
    with pytest.raises(FR.StoreError, match="differ"):
        FR.FrameStore(tmp_path / "frames" / "z", verify=True)


FRESH_FIT = """
import json, sys
sys.path.insert(0, sys.argv[1])
assert "agent.human_intake" not in sys.modules and "policy.idm_targets" not in sys.modules
from policy.idm import train as TR
checked = []
TR.require_committed = lambda files: checked.append(list(files))
rc = TR.main(sys.argv[3:])
json.dump({"rc": rc, "checked": checked}, open(sys.argv[2], "w"))
"""


def test_run_fit_end_to_end_commits_the_closure_it_checks_and_writes_a_report(tmp_path):
    """Review C1, import-order-proof: run_fit runs in a FRESH interpreter, where nothing but policy.idm.train has been
    imported, so a module imported lazily after the first closure would change the closure and fail the run. Every
    module the run imports is in the closure require_committed sees before anything is read, the closure is unchanged
    after the fit, and the run writes its checkpoint and report (full-scale config, smoke)."""
    import subprocess
    full = M.Config()
    train_t, train_store, train_path = session(tmp_path, "tr", n=80, config=full, jump_p=0.7)
    _, _, held_path = session(tmp_path, "he", n=40, split="val", seed=5, config=full, jump_p=0.7)
    out, result = tmp_path / "run", tmp_path / "result.json"
    eq, eq_sha = equivalence(tmp_path, builds=["p"])                    # the fixture headers' build
    proc = subprocess.run([sys.executable, "-c", FRESH_FIT, str(ROOT), str(result), "fit", "--train", str(train_path),
                           "--heldout", str(held_path), "--frames-root", str(tmp_path / "frames"), "--out", str(out),
                           "--epochs", "1", "--scope", "smoke", "--max-examples", "16",
                           "--patch-equivalence", str(eq), "--patch-equivalence-sha256", eq_sha],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    ran = json.loads(result.read_text(encoding="utf-8"))
    checked = ran["checked"]
    assert ran["rc"] == 0 and len(checked) == 1
    assert {"agent/human_intake.py", "agent/human_demos.py", "policy/idm_targets.py", "policy/idm/train.py",
            "policy/idm/frames.py"} <= set(checked[0])
    assert not any(f.startswith("tests/") for f in checked[0])          # a real run's closure, not pytest's
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert list(report["code_closure"]) == checked[0]                   # the closure checked is the one recorded
    assert report["train_statistics"]["examples"] == 16 and report["supported"]["jump"]
    assert report["frame_stores"]["tr"]["manifest_sha256"] == T.sha256(tmp_path / "frames" / "tr" / "frames.json")
    assert report["targets"]["tr"]["sha256"] == T.sha256(train_path) and report["scope"] == "smoke"
    _, payload = TR.load_checkpoint(out / "idm-seed0.pt")
    assert payload["meta"]["code_closure"] == report["code_closure"]
    assert hashlib.sha256((out / "idm-seed0.pt").read_bytes()).hexdigest() == report["checkpoint_sha256"]
    assert train_t.session_id == "tr" and train_store.manifest["width"] == 448
    cohort = report["cohort"]                                          # the kit version and the real builds
    assert cohort["builds"] == {"tr": "p", "he": "p"} and cohort["kit_version"] == "K"
    assert cohort["patch_equivalence"]["sha256"] == eq_sha and payload["meta"]["cohort"] == cohort


def equivalence(tmp_path, builds):
    """A patch-equivalence file naming `builds` under one kit version "K"; returns (path, LF sha256)."""
    text = json.dumps({"format": T.PATCH_EQUIVALENCE_FORMAT, "kit_versions": {"K": {
        "builds": builds, "evidence": ["test"], "decided_by": "lead", "decided_on": "2026-09-24"}}}) + "\n"
    path = tmp_path / f"equivalence-{'-'.join(builds)}.json"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path, hashlib.sha256(text.encode()).hexdigest()


def test_a_fit_refuses_a_build_the_equivalence_file_does_not_name_before_opening_a_store(tmp_path, monkeypatch):
    monkeypatch.setattr(TR, "require_committed", lambda files: None)
    _, _, train_path = session(tmp_path, "tr")
    _, _, held_path = session(tmp_path, "he", split="val", seed=5)
    monkeypatch.setattr(TR, "FrameStore", lambda *a, **k: pytest.fail("a store was opened"))
    eq, eq_sha = equivalence(tmp_path, builds=["another-build"])
    with pytest.raises(T.TargetError, match="adding a build to a kit version is a lead decision"):
        TR.main(["fit", "--train", str(train_path), "--heldout", str(held_path), "--frames-root",
                 str(tmp_path / "frames"), "--out", str(tmp_path / "o"),
                 "--patch-equivalence", str(eq), "--patch-equivalence-sha256", eq_sha])
    monkeypatch.setattr(T, "PATCH_EQUIVALENCE_SHA256", None)            # an unpinned file: no fit
    with pytest.raises(T.TargetError, match="must be pinned"):
        TR.main(["fit", "--train", str(train_path), "--heldout", str(held_path), "--frames-root",
                 str(tmp_path / "frames"), "--out", str(tmp_path / "o"), "--patch-equivalence", str(eq)])


def test_the_limit_is_for_smoke_runs_and_a_narrow_store_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(TR, "require_committed", lambda files: None)
    t, store, path = session(tmp_path, "a")
    with pytest.raises(TR.FitError, match="the model reads 448x252"):
        TR.Examples([(t, store)], M.Config(), SUPPORTED)                # a 40-wide store under the full model
    with pytest.raises(TR.FitError, match="smoke only"):
        TR.main(["fit", "--train", str(path), "--heldout", str(path), "--frames-root", str(tmp_path / "frames"),
                 "--out", str(tmp_path / "o"), "--max-examples", "4"])


def test_beta_nll_on_yaw_only_keeps_the_gaussian_nll_on_pitch(tmp_path):
    """The yaw-only test (lane doc 2026-09-25): axes "both" is the landed beta-NLL bit for bit; "yaw" gives yaw the
    beta-NLL gradient and pitch exactly the plain NLL's."""
    y, mask, sigma = torch.tensor([[3.0, -1.0]]), torch.tensor([[True, True]]), torch.tensor([[0.2, 0.1]])
    none = torch.zeros(1, N, dtype=torch.bool)

    def grads(**kw):
        out = torch.tensor([[0.5, 0.25, 1.2, -0.4]], requires_grad=True)
        loss = TR.loss_terms(torch.zeros(1, N), out, torch.zeros(1, N), none, y, mask, sigma, torch.ones(N), **kw)
        loss["camera"].backward()
        return loss["camera"].detach(), out.grad.clone()

    lb, gb = grads(camera_beta=0.5)
    lboth, gboth = grads(camera_beta=0.5, camera_beta_axes="both")
    assert torch.equal(lb, lboth) and torch.equal(gb, gboth)                # "both" is the landed behaviour
    _, gplain = grads()
    _, gyaw = grads(camera_beta=0.5, camera_beta_axes="yaw")
    assert torch.equal(gyaw[:, [0, 2]], gb[:, [0, 2]])                      # yaw mean and log-variance: beta-NLL
    assert torch.equal(gyaw[:, [1, 3]], gplain[:, [1, 3]])                  # pitch: the plain Gaussian NLL
    ex, _, _ = examples(tmp_path)
    with pytest.raises(TR.FitError, match="camera_beta_axes"):
        TR.fit(ex, TINY, TR.train_statistics(ex), epochs=1, camera_beta=0.5, camera_beta_axes="pitch")
