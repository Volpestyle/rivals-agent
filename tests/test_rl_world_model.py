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
