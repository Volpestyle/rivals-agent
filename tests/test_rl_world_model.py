import json

import pytest

from rl.world_model import data as D

N = D.N_ACT


def header(**kw):
    h = {"format": "rivals-range-steps-v1", "session_id": "s", "split": "train", "actions": list(D.ACTIONS),
         "calibration": {"yaw_deg_per_count": 0.05, "pitch_deg_per_count": 0.05}}
    h.update(kw)
    return h


def row(i, run="r0", held=None, press=None, dx=0, dy=0, known=True, suit="accepted"):
    return {"i": i, "run": run, "suitability": suit, "gap_free": True,
            "held_end": held or [0] * N, "held_known": [True] * N, "press": press or [0] * N,
            "mouse_dx": dx, "mouse_dy": dy, "relative_known": known}


def test_step_actions_aggregate_three_rows():
    held = [0] * N
    held[4] = 1                     # jump held in one of three rows
    press = [0] * N
    press[10] = 1                   # spider_power pressed once
    rows = [row(0, dx=100), row(1, held=held, press=press, dx=100), row(2, dx=100, dy=-40), row(3)]
    acts = D.step_actions(header(), rows)
    a = acts[0]
    assert len(a) == D.ACTION_DIM
    assert a[4] == pytest.approx(1 / 3)
    assert a[N + 10] == 1.0
    assert a[-2] == pytest.approx(300 * 0.05 / D.DEG_SCALE)
    assert a[-1] == pytest.approx(-40 * 0.05 / D.DEG_SCALE)
    assert acts[2] is None and acts[3] is None


def test_action_order_follows_names_not_positions():
    names = list(reversed(D.ACTIONS))
    held = [0] * N
    held[names.index("web_swing")] = 1
    a = D.step_actions(header(actions=names), [row(0, held=held)], stride=1)[0]
    assert a[D.ACTIONS.index("web_swing")] == 1.0
    assert sum(a[:N]) == 1.0


def test_unknown_mouse_is_zero_not_guessed():
    a = D.step_actions(header(), [row(0, dx=500, known=False)], stride=1)[0]
    assert a[-2] == 0.0


def test_valid_starts_respect_runs_gaps_and_suitability():
    rows = [row(i) for i in range(6)] + [row(6, suit="rejected")] + [row(i) for i in range(7, 10)]
    rows += [row(10, run="r1"), row(11, run="r1"), row(13, run="r1")]   # step index gap at 13
    assert D.valid_starts(rows, 3) == [0, 1, 2, 3, 7]
    assert D.valid_starts(rows, 2) == [0, 1, 2, 3, 4, 7, 8, 10]


def test_sealed_sessions_refused(tmp_path):
    deny = tmp_path / "deny.json"
    deny.write_text(json.dumps({"sessions": [{"session_id": "sealedA"}]}))
    D.check_not_sealed(["ok1"], deny)
    with pytest.raises(ValueError):
        D.check_not_sealed(["ok1", "sealedA"], deny)


def test_training_smoke_on_synthetic_data(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("cv2")
    pytest.importorskip("PIL")
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg missing")
    from rl.world_model import train as T
    res = T.main(["--synthetic", "--out", str(tmp_path), "--steps", "4", "--batch", "4", "--chs", "8,16,16,16",
                  "--eval-n", "4", "--horizon", "3", "--video-horizon", "3", "--video-clips", "2"])
    assert set(res) >= {"copy_last", "model_mean", "mean_zero_actions", "mean_shuffled_actions", "model_sample"}
    assert len(res["model_mean"]["mse"]) == 3
    assert (tmp_path / "real_vs_imagined.mp4").stat().st_size > 0
    assert (tmp_path / "model.pt").exists()


def replay_row(i, run="v:0-1", held=None, known=True, press=None, yaw=1.0, conf=0.9):
    held = held if held is not None else [0] * N
    return {"i": i, "run": run, "suitability": "accepted", "held_end": held, "held_known": [known] * N,
            "press": press if press is not None else [0] * N, "press_known": [True] * N,
            "yaw_deg": yaw, "pitch_deg": 0.0, "camera_conf": conf}


def test_expert_kept_rows_and_trusted_channels_only():
    from rl.world_model import expert_prep as E
    rows = [replay_row(i) for i in range(7)] + [replay_row(8), replay_row(9), replay_row(10)]   # gap at 7->8
    assert E.kept_rows(rows) == [0, 3, 7]
    order = {name: j for j, name in enumerate(D.ACTIONS)}
    held = [1] * N
    v = E.step_action([replay_row(0, held=held), replay_row(1, held=held), replay_row(2, held=held, conf=0.1)], order)
    vals, known = v[:D.ACTION_DIM], v[D.ACTION_DIM:]
    assert known[D.ACTIONS.index("move_forward")] == 1 and vals[D.ACTIONS.index("move_forward")] == 1
    assert known[D.ACTIONS.index("move_back")] == 0 and vals[D.ACTIONS.index("move_back")] == 0     # noise channel
    assert known[N + D.ACTIONS.index("jump")] == 1 and known[N + D.ACTIONS.index("get_over_here")] == 0
    assert known[-1] == 0 and vals[-2] == 0          # low camera confidence in one row -> camera unknown
    nulls = [replay_row(0), replay_row(1), dict(replay_row(2), yaw_deg=None)]
    assert E.step_action(nulls, order)[-1] == 0


def test_own_known_mask():
    rows = [row(0), dict(row(1), relative_known=False), row(2), row(3)]
    k = D.step_known(header(), rows)
    assert k[0][-1] == 0 and k[2][-1] == 1 and k[0][N] == 1


def test_segment_starts():
    pytest.importorskip("numpy")
    pytest.importorskip("torch")
    from rl.world_model.v2 import segment_starts
    assert segment_starts([0, 0, 0, 1, 1, 1, 1], 3) == [0, 3, 4]
    assert segment_starts([0, 0], 3) == []


def test_v3_smoke_with_expert_shard(tmp_path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("torch")
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("PIL")
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg missing")
    from rl.world_model import v2
    shard = tmp_path / "expert" / "expert-x-s0"
    shard.mkdir(parents=True)
    offs, blob = [0], b""
    for m in range(40):
        img = np.full((144, 256, 3), m * 5, np.uint8)
        jpg = cv2.imencode(".jpg", img)[1].tobytes()
        blob += jpg
        offs.append(len(blob))
    (shard / "frames.bin").write_bytes(blob)
    np.save(shard / "offsets.npy", np.asarray(offs, np.int64))
    np.save(shard / "actions.npy", np.zeros((40, 2 * D.ACTION_DIM), np.float32))
    np.save(shard / "segs.npy", np.asarray([0] * 20 + [1] * 20, np.int32))
    (shard / "meta.json").write_text(json.dumps({"shard": "expert-x-s0", "player": "reqmr", "kept": 40}))
    res = v2.main(["--synthetic", "--out", str(tmp_path / "out"), "--steps", "3", "--batch", "4", "--ctx", "4",
                   "--roll-max", "2", "--roll-start", "0", "--roll-p", "1", "--chs", "8,16,16,16,16", "--horizon", "3",
                   "--eval-n", "2", "--video-clips", "1", "--sample-steps", "2", "--expert-root", str(tmp_path / "expert"),
                   "--expert-share", "0.5"])
    assert "native/mean|all" in res
    log = [json.loads(line) for line in (tmp_path / "out" / "log.jsonl").read_text().splitlines()]
    data = next(r for r in log if r["event"] == "data")
    assert data["expert"]["shards"] == 1 and data["expert"]["sources"] == ["james", "reqmr"]
