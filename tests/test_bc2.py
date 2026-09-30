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


def make_session(root, sid, n=300, seed=0):
    rng = np.random.default_rng(seed)
    d = root / sid
    d.mkdir()
    np.save(d / "feats.npy", rng.standard_normal((n, 2, bc2_model.FEAT)).astype(np.float16))
    np.save(d / "gray_g.npy", rng.integers(0, 255, (n, 72, 128), dtype=np.uint8))
    np.save(d / "gray_c.npy", rng.integers(0, 255, (n, 64, 64), dtype=np.uint8))
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
    report = bc2_train.fit(tr, dv, dv, tmp_path / "out", config=bc2_model.Config(embed=16, motion=16, hidden=32),
                           epochs=1, batch_size=4, device="cpu", log=lambda *_: None)
    assert report["selected_epoch"] == 1
    pooled = report["selected"]["eval_pooled"]
    assert 0 <= pooled["press_macro_f1"] <= 1
    assert pooled["yaw"]["zero_mae"] > 0 and pooled["yaw"]["steps"] > 0
    assert set(report["selected"]["thresholds"]) == set(vocab.NAMES)
