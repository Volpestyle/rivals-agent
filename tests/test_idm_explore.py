"""EXPLORATORY runner: synthetic inputs only, no recorded payloads or GPU work."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from policy import idm_targets as T
from policy.idm import explore as E, match_targets as M, temporal as P, temporal_store as S
from policy.range_bc import vocab
from scripts import job_status
from test_idm_model import header


@pytest.fixture(autouse=True)
def bounded_threads():
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(before)


def targets(sid="synthetic", split="train", n=110):
    h = header(sid, split)
    h["source"] = {"steps": {"sha256": "1" * 64}, "imported_demo": {"sha256": "2" * 64}}
    rows = []
    for i in range(n):
        press, held = [0] * vocab.N, [0] * vocab.N
        press[vocab.INDEX["amazing_combo"]] = int(i % 7 == 0)
        press[vocab.INDEX["jump"]] = int(i % 11 == 0)
        held[:] = press
        t0, t1 = round(i * 1e9 / 60), round((i + 1) * 1e9 / 60)
        f0 = {"frame_index": 2 * i, "pts": 2 * i, "composition_ns": t0}
        f1 = {"frame_index": 2 * i + 2, "pts": 2 * i + 2, "composition_ns": t1}
        rate, regime = T.gain_regime(0, 0, t1 - t0)
        row = {"i": i, "parent": i // 2, "half": i % 2, "run": "run", "segment": "segment",
               "suitability": "accepted", "regime": "normal", "gap_free": True, "t0_ns": t0, "t1_ns": t1,
               "frame0": f0, "frame1": f1, "press": press, "release": [0] * vocab.N,
               "held_start": [0] * vocab.N, "held_end": held, "held_known": [True] * vocab.N,
               "mouse_dx": 0, "mouse_dy": 0, "yaw_deg": 0.0, "pitch_deg": 0.0,
               "beyond_pad_envelope": False, "mouse_rate_cps": rate, "gain_regime": regime}
        rows.append(row)
    return T.Targets(h, rows)


def admission(t, **registry_overrides):
    sid = t.session_id
    row = {"session_id": sid, "split": "idm_train", "session_group": sid,
           "expected_media_sha256": t.header["media_sha256"], **registry_overrides}
    entry = {"source_kind": "live", "session_group": sid, "media_sha256": t.header["media_sha256"],
             "steps_sha256": "1" * 64, "imported_demo_sha256": "2" * 64,
             "identity_sha256": M.digest(M.identity(t.header)), "motor_statement_sha256": "3" * 64}
    return M.Admission({sid: entry}, {sid: row}, "4" * 64)


def test_idm_train_needs_admission_before_malformed_rows(tmp_path):
    t = targets(split="idm_train")
    path = tmp_path / "targets.jsonl"
    path.write_text(json.dumps(t.header) + "\nMUST NOT PARSE THIS\n")
    with pytest.raises(T.TargetError, match="admission required"):
        T.load(path, denylist={"sessions": []})
    with pytest.raises(T.TargetError, match="motor identity pending"):
        T.load(path, denylist={"sessions": []}, match_admission=admission(t, training_pending="motor"))
    with pytest.raises(T.TargetError, match="replay"):
        T.load(path, denylist={"sessions": []}, match_admission=admission(t, pair="live"))


def test_reviewed_idm_train_roundtrip_support_and_identity(tmp_path):
    t = targets(split="idm_train")
    path = tmp_path / "targets.jsonl"
    T.write(path, t.header, t.rows)
    read = T.load(path, denylist={"sessions": []}, match_admission=admission(t))
    supported, counts = T.supported_actions([read], min_positives=1)
    assert supported["amazing_combo"] and counts["amazing_combo"] > 0
    bad = deepcopy(t.header)
    bad["calibration"]["yaw_deg_per_count"] *= 2
    with pytest.raises(T.TargetError, match="identity differs"):
        admission(t).header(bad)


@pytest.mark.parametrize("split", ["gate2", "test", "reader_validation", "reader_development"])
def test_other_roles_stay_closed_before_rows(tmp_path, split):
    t = targets(split=split)
    path = tmp_path / "targets.jsonl"
    path.write_text(json.dumps(t.header) + "\ninvalid")
    with pytest.raises(T.TargetError):
        T.load(path, denylist={"sessions": []})


def test_contiguous_context_and_exact_lead_combo_window():
    t = targets()
    ticks = P.offsets()
    assert P.WINDOWS["amazing_combo"] == (-12, 36) and max(ticks) == 36
    pairs, counts = P.context_rows(t, ticks)
    assert counts["eligible"] == len(t.rows) - 30 - 36
    assert all([r["frame1"]["frame_index"] for r in context] ==
               [anchor["frame1"]["frame_index"] + 2 * k for k in ticks] for anchor, context in pairs)


@pytest.mark.parametrize("change", ["gap", "segment", "run", "time", "unusable"])
def test_context_cannot_cross_any_interior_boundary(change):
    t = targets(n=180)
    if change == "gap":
        t.rows[90]["gap_free"] = False
    elif change in ("segment", "run"):
        for r in t.rows[90:]:
            r[change] = "other"
    elif change == "time":
        t.rows[90]["t0_ns"] += 1
    else:
        t.rows[90]["suitability"] = "rejected"
    pairs, _ = P.context_rows(t, P.offsets())
    assert all(not (context[0]["i"] < 90 < context[-1]["i"]) for _, context in pairs)


def tiny():
    return P.Config(feature_dim=8, width=24, global_width=16, heads=4, blocks=1)


def inputs():
    torch.manual_seed(1)
    ticks = P.offsets()
    return (torch.randn(2, len(ticks), 8, requires_grad=True),
            torch.randn(2, len(ticks), 3, 16, 20),
            torch.tensor(ticks).float()[None].expand(2, -1) / 60, ticks)


def test_short_arm_cannot_see_future_and_frozen_features_get_no_gradients():
    model = P.PressHead(tiny()).eval()
    g, hud, time, ticks = inputs()
    altered_g, altered_hud = g.detach().clone(), hud.clone()
    changed = [i for i, t in enumerate(ticks) if t > 8]
    altered_g[:, changed] += 100
    altered_hud[:, changed] += 100
    s = model(g, hud, time, ticks, arm="S")
    assert torch.equal(s, model(altered_g, altered_hud, time, ticks, arm="S"))
    l = model(g, hud, time, ticks, arm="L")
    assert not torch.allclose(l, model(altered_g, altered_hud, time, ticks, arm="L"))
    l.sum().backward()
    assert g.grad is None
    assert any(p.grad is not None for p in model.hud.parameters())
    assert not any("camera" in name for name, _ in model.named_parameters())


def test_action_masks_cannot_leak_via_other_queries():
    model = P.PressHead(tiny()).eval()
    g, hud, time, ticks = inputs()
    before = model(g, hud, time, ticks, arm="L")
    g = g.detach().clone()
    g[:, ticks.index(36)] += 100
    after = model(g, hud, time, ticks, arm="L")
    assert torch.equal(before[:, 1], after[:, 1])  # jump ends at +30, Combo at +36
    assert not torch.allclose(before[:, 0], after[:, 0])


class SyntheticStore:
    def __init__(self, t):
        self.index = {r["frame1"]["frame_index"]: i for i, r in enumerate(t.rows)}

    def inputs(self, rows):
        values = torch.tensor([r["i"] / 100 for r in rows])[:, None].expand(-1, 8).clone()
        hud = torch.zeros(len(rows), 3, 16, 20)
        for i, r in enumerate(rows):
            hud[i] += r["press"][vocab.INDEX["amazing_combo"]]
        return values, hud


def test_tiny_matched_pair_fits_scores_and_keeps_same_anchors():
    t, h = targets(), targets("held")
    tr, he = (E.EdgeExamples([(x, SyntheticStore(x))]) for x in (t, h))
    seen = []
    for arm in ("S", "L"):
        model, result = E.edge_fit(tr, arm=arm, epochs=1, batch=16, config=tiny(), min_positives=1,
                                  progress=seen.append)
        score = E.probabilities(model, tr, arm=arm, device="cpu")
        thresholds, _ = E.calibrate(tr, score)
        hp = E.probabilities(model, he, arm=arm, device="cpu")
        metrics = E.score_edges(he, hp, thresholds, result["supported"])
        assert metrics["amazing_combo"]["decides"] is False  # tiny synthetic support, no real verdict
        assert math_isfinite(metrics["amazing_combo"]["delta_f1"])
    assert seen[-1]["n"] == seen[-1]["total"] == len(tr)


def math_isfinite(value):
    return bool(np.isfinite(value))


@pytest.mark.parametrize("fail", [False, True])
def test_status_lifecycle_and_failure(tmp_path, fail):
    def work(progress):
        progress({"n": 1, "total": 2})
        if fail:
            raise RuntimeError("synthetic failure")
        return 7
    if fail:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            E.with_status("synthetic", tmp_path / "report.json", work, root=tmp_path, host="pc")
    else:
        assert E.with_status("synthetic", tmp_path / "report.json", work, root=tmp_path, host="pc") == 7
    data = json.loads((tmp_path / "synthetic.status.json").read_text())
    job_status.validate(data)
    assert data["stage"] == ("failed" if fail else "done")
    assert data["owner"] == "idm-owner" and data["eta"] is None


def test_preflight_refuses_pending_or_frozen_before_opening_targets(tmp_path, monkeypatch):
    from agent import human_intake as hi

    monkeypatch.setattr(hi, "check_registry", lambda *a, **k: {})
    for sid, extra in [("pending", {"split": "idm_train", "training_pending": "motor"}),
                       ("20260923T171533-187Z-33696-5", {"split": "train"}),
                       ("sealed", {"split": "gate2"})]:
        registry = tmp_path / "registry.json"
        registry.write_text(json.dumps({"sessions": [{"session_id": sid, **extra}]}))
        manifest = {"format": E.FORMAT, "scope": "EXPLORATORY",
                    "sessions": [{"session_id": sid, "role": "train", "targets": "must-not-open"}]}
        with pytest.raises(ValueError):
            E.preflight(manifest, registry=registry, denylist={"sessions": []})


@pytest.mark.parametrize("role", ["train", "heldout"])
@pytest.mark.parametrize("edge", [False, True])
def test_explore_refuses_val_in_every_role_before_target_open(tmp_path, monkeypatch, role, edge):
    from agent import human_intake as hi
    from pathlib import Path

    monkeypatch.setattr(hi, "check_registry", lambda *a, **k: {})
    # The registered validation ID is just a name in this synthetic registry.
    # No real recording, target file or validation metadata is opened.
    sid = "20260925T212646-322Z-49728-6"
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"sessions": [{"session_id": sid, "split": "val"}]}))
    forbidden = tmp_path / "must-not-open.idm.jsonl"
    opened = []
    original = Path.open
    def spy(path, *args, **kwargs):
        if path == forbidden:
            opened.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", spy)
    manifest = {"format": E.FORMAT, "scope": "EXPLORATORY",
                "sessions": [{"session_id": sid, "role": role, "targets": str(forbidden)}]}
    with pytest.raises(ValueError, match="training source"):
        E.preflight(manifest, registry=registry, denylist={"sessions": []}, edge=edge)
    assert opened == []


def test_primary_support_is_counted_after_context_trimming():
    t = targets()
    for r in t.rows[30:]:
        r["press"][vocab.INDEX["amazing_combo"]] = 0
    examples = E.EdgeExamples([(t, SyntheticStore(t))])
    with pytest.raises(ValueError, match="insufficient post-context"):
        E.edge_fit(examples, arm="L", epochs=1, config=tiny(), min_positives=1)


def test_mixed_train_and_reviewed_match_can_refit_without_allowing_val(tmp_path):
    from test_idm_model import session, TINY, SUPPORTED
    from policy.idm import train as TR

    first, store1, _ = session(tmp_path, "range", n=6)
    second, store2, _ = session(tmp_path, "match", n=6)
    # Objects here are synthetic and already loaded; the file-level admission
    # boundary is exercised separately above, never disabled in a real runner.
    second.header["split"] = "idm_train"
    examples = TR.Examples([(first, store1), (second, store2)], TINY, SUPPORTED)
    seen = []
    _, history, _ = TR.fit(examples, TINY, TR.train_statistics(examples), epochs=1, progress=seen.append)
    assert len(history) == 1 and seen[-1]["n"] == len(examples)
    second.header["split"] = "val"
    with pytest.raises(TR.FitError, match="train/idm_train"):
        TR.fit(examples, TINY, TR.train_statistics(examples), epochs=1)


def test_source_family_overlap_refused_before_second_payload(tmp_path, monkeypatch):
    from agent import human_intake as hi

    monkeypatch.setattr(hi, "check_registry", lambda *a, **k: {})
    entries, sessions = [], []
    for sid, role in (("one", "train"), ("two", "heldout")):
        t = targets(sid, n=3)
        t.header["session_group"] = "same-family"
        path = tmp_path / (sid + ".jsonl")
        if role == "train":
            T.write(path, t.header, t.rows)
        else:
            path.write_text(json.dumps(t.header) + "\nMUST NOT PARSE")
        entries.append({"session_id": sid, "split": "train", "session_group": "same-family"})
        sessions.append({"session_id": sid, "role": role, "targets": str(path), "targets_sha256": T.sha256(path)})
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"sessions": entries}))
    with pytest.raises(ValueError, match="same live/replay family"):
        E.preflight({"format": E.FORMAT, "scope": "EXPLORATORY", "sessions": sessions},
                    registry=reg, denylist={"sessions": []})


def test_synthetic_preparation_roundtrip_and_stale_pts_refusal(tmp_path, monkeypatch):
    # Synthetic decoder only. No subprocess, video read, model asset or Mac call.
    monkeypatch.setattr(S.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(S.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(S.decode.cache, "probe_colour", lambda *a: {})
    monkeypatch.setattr(S.decode.cache, "check_colour", lambda *a: None)
    monkeypatch.setattr(S.decode.cache, "probe_size", lambda *a: [2560, 1440])
    video = tmp_path / "synthetic.mkv"
    video.write_bytes(b"synthetic source bytes, not a video")
    t = targets(n=80)
    t.header["media_sha256"] = T.sha256(video)
    demo = tmp_path / "demo.jsonl"
    demo.write_text(json.dumps({"media_sha256": t.header["media_sha256"], "session_id": t.session_id}) + "\n" +
                    json.dumps({"decoded": {"pts": list(range(200)), "timebase_num": 1, "timebase_den": 120}}) + "\n")
    t.header["source"]["imported_demo"]["sha256"] = T.sha256(demo)
    seen = []
    def decoder(path, keys, sink, *_):
        seen.extend(keys)
        for i, key in enumerate(keys):
            sink(i, np.full((252, 448, 3), key % 255, np.uint8), np.zeros((80, 200, 3), np.uint8))
        return keys, [1, 120]
    monkeypatch.setattr(S.decode, "_decode", decoder)
    class Backbone:
        asset_receipt = {"synthetic": True}
        def __call__(self, pixels):
            return torch.zeros(len(pixels), 6528)
    out = tmp_path / "store"
    S.prepare(t, "a" * 64, video=video, demo=demo, out=out, backbone=Backbone(), device="cpu")
    assert seen == sorted(set(seen))
    store = S.FeatureStore(out, t, "a" * 64, manifest_sha256=T.sha256(out / "features.json"))
    row = next(r for r in t.rows if r["frame1"]["frame_index"] in store.index)
    g, h = store.inputs([row])
    assert g.shape == (1, 6528) and h.shape == (1, 3, 80, 200)
    bad = deepcopy(row)
    bad["frame1"]["pts"] += 1
    with pytest.raises(ValueError, match="PTS differs"):
        store.inputs([bad])
    with pytest.raises(ValueError, match="identity/format"):
        S.FeatureStore(out, t, "b" * 64, manifest_sha256=T.sha256(out / "features.json"))
    with (out / "features.f32").open("ab") as f:
        f.write(b"bad")
    with pytest.raises(ValueError, match="length/hash"):
        S.FeatureStore(out, t, "a" * 64, manifest_sha256=T.sha256(out / "features.json"))


def test_run_cli_refuses_wrong_code_before_registry_access(tmp_path):
    manifest = tmp_path / "run.json"
    manifest.write_text(json.dumps({"code_closure": {}, "independent_review": "accepted"}))
    with pytest.raises(ValueError, match="reviewed exact code closure"):
        E.main(["preflight", "--manifest", str(manifest), "--manifest-sha256", T.sha256(manifest),
                "--registry", "must-not-open"])


def test_encoder_failure_reaps_only_its_own_decoder(monkeypatch):
    import io

    class Process:
        stdout = io.BytesIO(bytes(int(np.prod(S.decode._STACK))))
        stderr = io.BytesIO(b"")
        terminated = False
        waited = False
        def terminate(self):
            self.terminated = True
        def wait(self, **kwargs):
            self.waited = True
    proc = Process()
    monkeypatch.setattr(S.decode.subprocess, "Popen", lambda *a, **k: proc)
    def sink(*args):
        raise RuntimeError("synthetic encoder failure")
    with pytest.raises(RuntimeError, match="encoder failure"):
        S.decode._decode("synthetic", [0], sink, "ffmpeg", 2)
    assert proc.terminated and proc.waited and proc.stdout.closed and proc.stderr.closed
