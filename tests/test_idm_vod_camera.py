"""policy.idm.vod.camera_answer must stay identical to policy.idm.train._camera (the labeller's copy)."""
import random

import pytest

torch = pytest.importorskip("torch")

from policy.idm import train, vod  # noqa: E402


def test_constants_match():
    assert vod.CAMERA_ABSTAIN_STD == train.CAMERA_ABSTAIN_STD
    assert vod.PITCH_STD_CALIBRATION == train.PITCH_STD_CALIBRATION
    assert tuple(vod.PITCH_STD_EDGES) == tuple(train.PITCH_STD_EDGES)
    assert tuple(vod.PITCH_STD_K) == tuple(train.PITCH_STD_K)


def test_answers_match():
    rng = random.Random(0)
    cal = {"yaw_deg_per_count": 0.0330738, "pitch_deg_per_count": 0.0330738}
    for _ in range(500):
        mu_y, mu_p = rng.uniform(-20, 20), rng.uniform(-8, 8)
        logvar = [rng.uniform(-9, 3), rng.uniform(-9, 3)]
        r = {"t0_ns": 0, "t1_ns": rng.choice([16_666_667, 16_000_000, 17_500_000])}
        assert vod.camera_answer(mu_y, mu_p, logvar, r, cal) == train._camera(mu_y, mu_p, logvar, r, cal)
