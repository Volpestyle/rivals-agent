"""policy.bc2: phase correlation recovers a known shift; a tiny synthetic fit and evaluation run end to end."""
import json

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from policy.bc2 import model as bc2_model, train as bc2_train  # noqa: E402
from policy.range_bc import vocab  # noqa: E402


def test_phase_corr_recovers_shift():
    g = torch.Generator().manual_seed(0)
    base = torch.rand(1, 80, 160, generator=g) * 255
    base = torch.nn.functional.avg_pool2d(base[None], 3, 1, 1)[0]
    prev, cur = base[:, 8:72, 8:136], torch.roll(base, shifts=(2, -5), dims=(1, 2))[:, 8:72, 8:136]
    dx, dy, peak = bc2_model.phase_corr(prev, cur)[0].tolist()
    assert round(dx) == -5 and round(dy) == 2 and peak > .1


def test_green_profile_finds_bar_bearing():
    view = torch.zeros(1, 144, 256, 3, dtype=torch.uint8)
    view[0, 40:42, 180:200] = torch.tensor([64, 175, 88], dtype=torch.uint8)      # an in-game green bar, right
    out = bc2_model.green_profile(view)[0]
    assert out[-3].expm1() > 30 and 0.4 < float(out[-2]) < 0.6 and 0.3 < float(out[-1]) < 0.6


def make_session(root, sid, n=300, seed=0):
    rng = np.random.default_rng(seed)
    d = root / sid
    d.mkdir()
    np.save(d / "feats.npy", rng.standard_normal((n, 2, bc2_model.FEAT)).astype(np.float16))
    np.save(d / "gray_g.npy", rng.integers(0, 255, (n, 72, 128), dtype=np.uint8))
    np.save(d / "gray_c.npy", rng.integers(0, 255, (n, 64, 64), dtype=np.uint8))
    np.save(d / "gray_g1.npy", rng.integers(0, 255, (n, 144, 256), dtype=np.uint8))
    np.save(d / "green.npy", rng.standard_normal((n, bc2_model.GREEN_DIM)).astype(np.float16))
    act = np.zeros((n, 3, vocab.N), np.uint8)
    act[::10, 1, vocab.INDEX["jump"]] = 1
    act[::10, 2, vocab.INDEX["jump"]] = 1
    act[:, 0, vocab.INDEX["move_forward"]] = (np.arange(n) // 20) % 2
    yaw = rng.normal(0, 2, n).astype(np.float32)
    run_start = np.zeros(n, bool)
    run_start[[0, n // 2]] = True
    np.savez(d / "targets.npz", row=np.arange(n), frame=np.arange(n), run_start=run_start, valid=np.ones(n, bool),
             act=act, act_known=np.ones((n, 3, vocab.N), bool), yaw=yaw, pitch=yaw / 3,
             cam_class=np.stack([[vocab.camera_class(float(y)), vocab.camera_class(float(y) / 3)] for y in yaw]),
             cam_known=np.ones((n, 2), bool))
    (d / "meta.json").write_text(json.dumps({"session": sid}))
    return d


def test_tiny_fit_and_evaluate(tmp_path):
    feats = tmp_path / "features"
    feats.mkdir()
    tr = [make_session(feats, "a", seed=1), make_session(feats, "b", seed=2)]
    dv = [make_session(feats, "c", seed=3)]
    config = bc2_model.Config(embed=16, motion=16, hidden=32, use_green=True, use_dt=True, chunk=4, hires=True)
    report = bc2_train.fit(tr, dv, dv, tmp_path / "out", config=config,
                           epochs=2, batch_size=4, device="cpu", log=lambda *_: None, onset_weight=3., motion_dropout=.5, static_aug=.5, oversample={"a": .6},
                           expert_dirs=[make_session(feats, "x", seed=4)], expert_epochs=1, expert_share=.5)
    assert report["selected_epoch"] in (1, 2) and report["expert"]["steps"] == 300
    pooled = report["selected"]["eval_pooled"]
    assert 0 <= pooled["press_macro_f1"] <= 1
    assert pooled["yaw"]["zero_mae"] > 0 and pooled["yaw"]["steps"] > 0
    assert set(report["selected"]["thresholds"]) == set(vocab.NAMES)


def relabel_case(tmp_path, *, change=None):
    from copy import deepcopy
    from policy.range_bc import fixture, steps
    h, rows = fixture.replay_session("expert-123", runs=(8,))
    sh = dict(h, session_id="expert-123-s0", session_group="expert-123-s0", source_video_group="expert-123")
    old = fixture.write(tmp_path / "old.jsonl", sh, rows)
    nh, new = deepcopy(h), deepcopy(rows[1:])
    nh["calibration"]["source"] = "new-idm"
    nh["idm"] = {"checkpoint": "c.pt+d.pt"}
    # Changed nominal clock, dropped first and interior rows, unchanged physical frame identities.
    new = [r for r in new if r["i"] != 4]
    for i, r in enumerate(new):
        r["i"] = i
        r["anchor_ns"] += 100
        r["yaw_deg"] = 2.
    if change:
        change(nh, new)
    labels = fixture.write(tmp_path / "new.jsonl", nh, new)
    d = make_session(tmp_path, "expert-123-s0", n=8)
    (d / "meta.json").write_text(json.dumps({"session": sh["session_id"], "steps_sha256": steps.sha256(old)}))
    return old, labels, d


def test_relabel_keeps_exact_feature_rows_and_resets_across_missing_rows(tmp_path):
    from policy.bc2.expert import relabel
    old, labels, d = relabel_case(tmp_path)
    expected = {name: np.load(d / (name + ".npy"))[[1, 2, 3, 5, 6, 7]]
                for name in ("feats", "gray_g", "gray_c", "green")}
    assert relabel(old, labels, d) == (6, 2)
    s = bc2_train.Session(d, "cpu")
    assert s.t["feature_row"].tolist() == [1, 2, 3, 5, 6, 7]
    assert s.runs == [(0, 3), (3, 6)]
    assert s.prev.tolist() == [0, 0, 1, 3, 3, 4]
    for name, values in expected.items():
        np.testing.assert_array_equal(getattr(s, name).numpy(), values)
    assert s.t["yaw"].tolist() == [2.] * 6
    assert s.meta["relabel"]["idm"]["checkpoint"] == "c.pt+d.pt"


@pytest.mark.parametrize("change,message", [
    (lambda h, r: h.update(media_sha256="f" * 64), "different source"),
    (lambda h, r: r.append(dict(r[0], i=len(r))), "duplicate source-frame"),
    (lambda h, r: [x["frame"].update(pts=x["frame"]["pts"] + 1) for x in r], "no eligible exact"),
])
def test_relabel_refuses_wrong_source_duplicates_and_no_overlap_without_writing(tmp_path, change, message):
    from policy.bc2.expert import relabel
    old, labels, d = relabel_case(tmp_path, change=change)
    before = (d / "targets.npz").read_bytes(), (d / "meta.json").read_bytes()
    with pytest.raises(ValueError, match=message):
        relabel(old, labels, d)
    assert before == ((d / "targets.npz").read_bytes(), (d / "meta.json").read_bytes())


def test_session_refuses_shortened_targets_without_feature_mapping(tmp_path):
    d = make_session(tmp_path, "short", n=8)
    with np.load(d / "targets.npz") as z:
        targets = {k: z[k][1:] for k in z.files}
    np.savez(d / "targets.npz", **targets)
    with pytest.raises(ValueError, match="explicit feature_row required"):
        bc2_train.Session(d, "cpu")


def test_fit_refuses_expert_rows_that_form_no_trainable_windows(tmp_path):
    own = make_session(tmp_path, "own", n=64)
    expert = make_session(tmp_path, "short-expert", n=8)
    with pytest.raises(ValueError, match="no trainable runs"):
        bc2_train.fit([own], [own], [], tmp_path / "out", config=bc2_model.Config(), device="cpu",
                      expert_dirs=[expert])


def test_explicit_expert_cohort_ignores_arrivals_and_refuses_mixed_or_incomplete_shards(tmp_path):
    from policy.bc2.cohort import expert_dirs
    a, b = [make_session(tmp_path, name, n=8) for name in ("expert-123-s0", "expert-456-s0")]
    for d in (a, b):
        (d / "meta.json").write_text(json.dumps({"session": d.name, "calibration": {"source": "v2-a"}}))
    assert expert_dirs(tmp_path, [a.name]) == [a]
    with pytest.raises(ValueError, match="differs from requested"):
        expert_dirs(tmp_path, [a.name], "v2-cd")
    with pytest.raises(ValueError, match="duplicate"):
        expert_dirs(tmp_path, [a.name, a.name])
    (b / "meta.json").write_text(json.dumps({"session": b.name, "calibration": {"source": "v2-cd"}}))
    with pytest.raises(ValueError, match="mixes label sources"):
        expert_dirs(tmp_path, [a.name, b.name])
    (a / "gray_c.npy").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        expert_dirs(tmp_path, [a.name])


def test_split_features(tmp_path):
    from policy.bc2 import local_eval
    d = make_session(tmp_path, "x", n=100, seed=5)
    cut, n = local_eval.split(d, .8)
    assert (cut, n) == (80, 100)
    fit, hold = bc2_train.Session(tmp_path / "x-fit", "cpu"), bc2_train.Session(tmp_path / "x-hold", "cpu")
    assert fit.n == 80 and hold.n == 20 and bool(hold.t["run_start"][0])
    assert np.array_equal(np.load(tmp_path / "x-hold" / "gray_c.npy"), np.load(d / "gray_c.npy")[80:])


def test_streamed_session_batches_match_resident(tmp_path):
    d = make_session(tmp_path, "s", n=300)
    with np.load(d / "targets.npz") as z:      # drop rows 40-59: explicit feature_row mapping, a run break
        keep = np.r_[0:40, 60:300]
        t = {k: z[k][keep] for k in z.files}
    t["feature_row"] = keep
    t["run_start"][40] = True
    np.savez(d / "targets.npz", **t)
    res, st = bc2_train.Session(d, "cpu"), bc2_train.Session(d, "cpu", stream=True)
    assert isinstance(st.feats, np.memmap)
    items = [(0, 0, 128, True, 1), (1, 30, 100, False, 2), (0, 150, 64, False, 3)]
    torch.manual_seed(5)
    a = bc2_train.batch([res, res], items, "cpu", chunk=3, static_aug=.5, motion_dropout=.5)
    torch.manual_seed(5)
    b = bc2_train.batch([st, st], items, "cpu", chunk=3, static_aug=.5, motion_dropout=.5)
    assert a.keys() == b.keys()
    for k in a:
        assert torch.equal(a[k], b[k]), k
    with pytest.raises(ValueError, match="training-only"):
        st.inputs(torch.zeros(1, 4, dtype=torch.long))


def test_equal_expert_windows_give_equal_steps_and_weights_apply(tmp_path):
    feats = tmp_path / "features"
    feats.mkdir()
    own, dev = make_session(feats, "a", seed=1), make_session(feats, "c", seed=3)
    small = [make_session(feats, "x", seed=4)]
    big = small + [make_session(feats, f"y{i}", n=600, seed=5 + i) for i in range(3)]
    with np.load(big[1] / "targets.npz") as z:
        t = {k: z[k] for k in z.files}
    t["press_soft"] = np.full((600, vocab.N), np.nan, np.float32)
    t["press_soft"][::7, vocab.INDEX["jump"]] = .3
    np.savez(big[1] / "targets.npz", **t)
    config = bc2_model.Config(embed=16, motion=16, hidden=32, use_dt=True)
    runs = {}
    for name, experts, stream in (("A", small, False), ("B", big, True)):
        runs[name] = bc2_train.fit([own], [dev], [dev], tmp_path / name, config=config, epochs=2, batch_size=4,
                                   device="cpu", log=lambda *_: None, expert_dirs=experts, expert_windows=4,
                                   stream_expert=stream, press_unknown=("spider_power",),
                                   soft_targets=("press_soft",),
                                   cam_weight={"weight": 5., "source": "test", "rows": {"a": [[10, 60], [200, 230]]}})
    assert runs["A"]["steps"] == runs["B"]["steps"]
    assert [h["train_loss"] > 0 for h in runs["A"]["history"]] == [True, True]
    assert [h["epoch"] for h in runs["A"]["history"]] == [h["epoch"] for h in runs["B"]["history"]]
    assert runs["B"]["expert"]["streamed"] and runs["B"]["expert"]["soft_rows"]["press_soft"] == 86
    assert runs["A"]["cam_weight"]["row_share"]["a"] == pytest.approx(80 / 300, abs=1e-4)
    with pytest.raises(ValueError, match="fewer than"):
        bc2_train.fit([own], [dev], [], tmp_path / "C", config=config, epochs=1, batch_size=4, device="cpu",
                      log=lambda *_: None, expert_dirs=small, expert_windows=10 ** 6)


def test_window_rows_maps_composition_times_to_row_ranges(tmp_path):
    from policy.bc2 import data
    p = tmp_path / "s.steps.jsonl"
    rows = [{"i": k, "frame": {"composition_ns": 1000 + 100 * k}} for k in range(20)]
    p.write_text("\n".join(json.dumps(r) for r in [{"format": "x"}] + rows) + "\n")
    # rows 2-4 (1200-1400), 10 (exactly 2000), 18-19 (window past the end)
    assert data.window_rows(p, [[1150, 1450], [2000, 2050], [2750, 9999]]) == [[2, 5], [10, 11], [18, 20]]


def test_relabel_carries_soft_targets_into_training_batches(tmp_path):
    from policy.bc2.expert import relabel
    jump, swing = vocab.INDEX["jump"], vocab.INDEX["web_swing"]

    def soft(h, rows):
        for r in rows:
            r["press_p"] = [None] * vocab.N
            r["press_p"][jump] = .25
            r["held_p"] = {"web_swing": .75}
    old, labels, d = relabel_case(tmp_path, change=soft)
    relabel(old, labels, d)
    with np.load(d / "targets.npz") as z:
        assert z["press_soft"].shape == (6, vocab.N) and np.isnan(z["press_soft"][:, swing]).all()
        assert (z["press_soft"][:, jump] == .25).all() and (z["held_soft"][:, swing] == .75).all()
    s = bc2_train.Session(d, "cpu")
    assert s.soft("press_soft", 1) == 6 and s.soft("held_soft", 0) == 6
    b = bc2_train.batch([s], [(0, 0, 3, True, 1)], "cpu")
    assert torch.allclose(b["act"][0, :, 1, jump], torch.full((3,), .25))
    assert torch.allclose(b["act"][0, :, 0, swing], torch.full((3,), .75))
    # a relabel to labels without soft fields leaves none behind
    (tmp_path / "plain").mkdir()
    old2, labels2, d2 = relabel_case(tmp_path / "plain")
    relabel(old2, labels2, d2)
    with np.load(d2 / "targets.npz") as z:
        assert "press_soft" not in z.files


def test_fullscale_plan_extracts_only_uncovered_frames_in_whole_pieces(tmp_path):
    from policy.bc2 import fullscale
    from policy.bc2.expert import load_labels
    from policy.range_bc import fixture
    h, rows = fixture.replay_session("expert-9", runs=(40, 30, 20))
    for d in ("v2cd", "have"):
        (tmp_path / d).mkdir()
    table = fixture.write(tmp_path / "v2cd" / "expert-9.steps.jsonl", h, rows)
    have = rows[10:20] + rows[70:90]          # an existing shard holds run 0's middle and all of run 2
    sh = dict(h, session_id="expert-9-s0", session_group="expert-9-s0", source_video_group="expert-9")
    fixture.write(tmp_path / "have" / "expert-9-s0.steps.jsonl", sh, [dict(r, i=k) for k, r in enumerate(have)])
    written = fullscale.plan([table], fullscale.covered([tmp_path / "have"]), tmp_path / "out", rows_per_shard=1000)
    assert list(written.values()) == [60]                     # 90 rows - 30 covered
    s = load_labels(next(iter(written)))                       # header and row checks pass
    assert s.session_id == "expert-9-c0" and s.header["source_video_group"] == "expert-9"
    runs = [r["run"] for r in s.rows]
    run0, run1 = rows[0]["run"], rows[40]["run"]
    assert runs[:10] == [run0 + "~0"] * 10 and runs[10:30] == [run0 + "~1"] * 20 and runs[30:] == [run1] * 30
    from policy.range_bc import steps
    assert [b - a for a, b in steps.runs(s)] == [10, 20, 30]  # no window bridges the covered gap


def test_overlaid_cohort_accepts_new_shards_and_mixed_base_sources(tmp_path):
    from policy.bc2.cohort import expert_dirs
    a, c = [make_session(tmp_path, name, n=8) for name in ("expert-1-s0", "expert-2-c0")]
    (a / "meta.json").write_text(json.dumps({"session": "expert-1-s0", "calibration": {"source": "idm v2-a"}}))
    (c / "meta.json").write_text(json.dumps({"session": "expert-2-c0", "calibration": {"source": "idm v2-cd"}}))
    with pytest.raises(ValueError, match="mixes label sources"):
        expert_dirs(tmp_path, ["expert-1-s0", "expert-2-c0"])
    assert [d.name for d in expert_dirs(tmp_path, ["expert-1-s0", "expert-2-c0"], overlaid=True)] == \
        ["expert-1-s0", "expert-2-c0"]
