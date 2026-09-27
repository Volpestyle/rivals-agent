"""Inference parity on synthetic pixels only; never capture or input."""
import shutil
import time

import numpy as np
import pytest

from agent.live_range_bc import CachePreprocessor, Predictor
from policy.range_bc.live_inference import PersistentCachePreprocessor, InProcessCachePreprocessor, DevicePredictor


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires ffmpeg")
def test_persistent_graph_is_byte_exact_across_changing_frames():
    reference = CachePreprocessor()
    persistent = PersistentCachePreprocessor()
    try:
        rng = np.random.default_rng(7)
        for _ in range(4):
            frame = rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8)
            assert all(np.array_equal(a, b) for a, b in zip(reference(frame), persistent(frame)))
        with pytest.raises(ValueError, match="geometry"):
            persistent(np.zeros((720, 1280, 3), dtype=np.uint8))
    finally:
        persistent.close()
    assert persistent.process.poll() is not None
    with pytest.raises(RuntimeError, match="closed"):
        persistent(frame)


def test_cpu_predictor_matches_existing_recurrent_outputs():
    torch = pytest.importorskip("torch")
    from policy.range_bc.model import Policy, Config
    torch.set_num_threads(2)
    torch.manual_seed(7)
    model = Policy(Config(hud=False)).eval()
    rgb = [np.full(shape, 70, dtype=np.uint8) for shape in ((144, 256, 3), (128, 128, 3), (80, 200, 3))]
    a = Predictor(model, lambda frame: rgb, cooldowns="normal")
    b = DevicePredictor(model, lambda frame: rgb, cooldowns="normal")
    for _ in range(3):
        expected, actual = a(None, None), b(None, None)
        for x, y in zip(expected, actual):
            np.testing.assert_array_equal(x, y)
        for x, y in zip(a.state, b.state):
            torch.testing.assert_close(x, y, rtol=0, atol=0)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires ffmpeg")
@pytest.mark.parametrize("compact_bgr", [False, True])
def test_inprocess_graph_is_byte_exact_on_noise_and_real_tracked_fixture(compact_bgr):
    pytest.importorskip("av")
    import cv2
    from scripts.profile_range_bc_live import FIXTURES
    reference, fast = CachePreprocessor(), InProcessCachePreprocessor(compact_bgr=compact_bgr)
    try:
        rng = np.random.default_rng(20)
        frames = [rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8) for _ in range(3)]
        frames.extend(cv2.resize(cv2.imread(str(p)), (2560, 1440)) for p in FIXTURES)
        for frame in frames:
            for actual, expected in zip(fast(frame), reference(frame)):
                np.testing.assert_array_equal(actual, expected)
    finally:
        fast.close()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires ffmpeg")
def test_persistent_timeout_kills_child_and_refuses_reuse(monkeypatch):
    fast = PersistentCachePreprocessor(timeout=1.)
    fast.timeout = .001
    monkeypatch.setattr(fast, "_exchange", lambda raw: time.sleep(.02))
    frame = np.zeros((256, 256, 3), np.uint8)
    with pytest.raises(TimeoutError, match="instance closed"):
        fast(frame)
    assert fast.closed and fast.process.poll() is not None
    with pytest.raises(RuntimeError, match="closed"):
        fast(frame)


def test_exploratory_loader_hash_and_horizon_refuse_before_model_construction(tmp_path):
    torch = pytest.importorskip("torch")
    from agent.live_range_bc import sha256
    from policy.range_bc.explore_chunks_train import FORMAT
    from policy.range_bc.live_inference import load_explore_checkpoint
    path = tmp_path / "checkpoint.pt"
    torch.save({"format": FORMAT, "tag": "EXPLORATORY", "recipe": {"horizon": 4}}, path)
    with pytest.raises(ValueError, match="hash mismatch"):
        load_explore_checkpoint(path, "0" * 64)
    with pytest.raises(ValueError, match="only H1"):
        load_explore_checkpoint(path, sha256(path))


def test_batched_dino_preserves_two_views_and_recurrence():
    torch = pytest.importorskip("torch")
    from policy.range_bc import cm3
    class Backbone(torch.nn.Module):
        def forward(self, pixels):
            return pixels.mean((1, 2, 3))[:, None].expand(-1, cm3.FEATURE_DIM).contiguous()
    model = cm3.Policy(cm3.Config(arm="H")).eval()
    rgb = [np.full(shape, value, np.uint8) for shape, value in zip(
        ((144, 256, 3), (128, 128, 3), (80, 200, 3)), (20, 180, 0))]
    old = Predictor(model, lambda frame: rgb, cooldowns="normal", backbone=Backbone())
    new = DevicePredictor(model, lambda frame: rgb, cooldowns="normal", backbone=Backbone())
    for _ in range(2):
        for expected, actual in zip(old(None, None), new(None, None)):
            np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-6)
