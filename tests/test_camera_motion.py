"""Checks for perception.camera_motion.

    uv run --group perception --group dev pytest tests/test_camera_motion.py

Synthetic where it can be: a textured image warped by the exact homography of a
known camera rotation (K R K^-1) is the one input whose true rotation is known,
so the estimator's geometry and sign conventions are checked against it, not
against the turn map, which is itself only a calibration.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

cv2 = pytest.importorskip("cv2")

from perception.camera_motion import (  # noqa: E402
    Estimator, camera_angles, commanded, focal_for, inverse_map, kabsch, map_rate, rays,
)
from agent.controller import Cal  # noqa: E402

W, H = 1280, 720


def texture(seed=1):
    """A busy, non-repeating scene: random blobs and lines."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), 90, np.uint8)
    for _ in range(900):
        c = tuple(int(v) for v in rng.integers(0, 255, 3))
        if rng.random() < 0.5:
            cv2.circle(img, (int(rng.integers(0, W)), int(rng.integers(0, H))),
                       int(rng.integers(3, 25)), c, -1)
        else:
            cv2.line(img, (int(rng.integers(0, W)), int(rng.integers(0, H))),
                     (int(rng.integers(0, W)), int(rng.integers(0, H))), c, 2)
    return img


def rotate_view(img, yaw_deg, pitch_deg):
    """The same scene seen after the camera turns right by yaw and up by pitch."""
    f = focal_for(W)
    k = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])
    y, p = np.radians(yaw_deg), np.radians(pitch_deg)
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    cam = ry @ rx                                  # new camera axes in the old frame
    hmg = k @ cam.T @ np.linalg.inv(k)             # old pixel -> new pixel
    return cv2.warpPerspective(img, hmg, (W, H))


def estimate(a, b):
    est = Estimator(W)
    est.step(a, 0.0)
    return est.step(b, 0.1)


@pytest.mark.parametrize("yaw,pitch", [(3.0, 0.0), (-3.0, 0.0), (0.0, 2.0), (0.0, -2.0),
                                       (15.0, 0.0), (-6.0, 3.0)])
def test_a_known_rotation_is_recovered_with_the_right_sign(yaw, pitch):
    """Right is positive yaw, up is positive pitch -- the pad's own conventions
    are checked separately against the log. 15 degrees is a 0.45-stick step at
    the proxies' ~9 Hz, so large steps are covered, not just small ones."""
    img = texture()
    s = estimate(img, rotate_view(img, yaw, pitch))
    assert s.yaw_deg is not None, s
    assert abs(s.yaw_deg - yaw) < 0.3, (s.yaw_deg, yaw)
    assert abs(s.pitch_deg - pitch) < 0.3, (s.pitch_deg, pitch)


def test_no_motion_reads_as_no_rotation():
    img = texture()
    s = estimate(img, img.copy())
    assert s.yaw_deg is not None and abs(s.yaw_deg) < 0.05 and abs(s.pitch_deg) < 0.05


def test_a_featureless_frame_abstains_rather_than_guessing():
    flat = np.full((H, W, 3), 70, np.uint8)
    s = estimate(flat, flat.copy())
    assert s.yaw_deg is None and s.yaw_rate is None


def test_the_masked_body_does_not_vote():
    """A body that stays centred while the world turns must not pull the
    estimate toward zero: the fit sees only the world."""
    img = texture()
    turned = rotate_view(img, 5.0, 0.0)
    body = (slice(int(0.35 * H), H), slice(int(0.4 * W), int(0.6 * W)))
    turned[body] = img[body]                      # the "player" did not move on screen
    s = estimate(img, turned)
    assert abs(s.yaw_deg - 5.0) < 0.3


def test_kabsch_recovers_an_exact_rotation():
    rng = np.random.default_rng(3)
    a = rays(rng.uniform([0, 0], [W, H], (50, 2)), (H, W), focal_for(W))
    ang = np.radians(10)
    r = np.array([[np.cos(ang), 0, np.sin(ang)], [0, 1, 0], [-np.sin(ang), 0, np.cos(ang)]])
    assert np.allclose(kabsch(a, a @ r.T), r, atol=1e-9)


def test_pitched_camera_yaw_is_not_underestimated():
    """Yaw about the world vertical, seen by a camera pitched 40 degrees, shows
    up partly as roll; world yaw must still come out whole."""
    y, p = np.radians(8), np.radians(40)
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    # World yaw is about the world's up axis, which the pitched camera sees tilted.
    up = rx.T @ np.array([0, 1.0, 0])
    k = np.array([[0, -up[2], up[1]], [up[2], 0, -up[0]], [-up[1], up[0], 0]])
    cam_turn = np.eye(3) + np.sin(y) * k + (1 - np.cos(y)) * k @ k
    yaw, pitch, roll = camera_angles(cam_turn.T)
    assert abs(yaw - 8) < 0.05 and abs(pitch) < 0.05 and abs(roll) > 1


def test_the_turn_map_round_trips():
    for stick in (0.05, 0.1, 0.3, 0.45, 0.8, -0.45):
        assert abs(inverse_map(map_rate(stick, Cal().yaw_map), Cal().yaw_map) - stick) < 1e-9
    assert inverse_map(900, Cal().yaw_map) == 1.0      # beyond the map saturates, never extrapolates


def test_commanded_integrates_ticks_across_the_interval():
    """0.45 for half the interval and 0 for the other half is half the turn."""
    pad = [(0.0, 0.45, 0, 0, 0, ()), (0.05, 0.0, 0, 0, 0, ()), (0.10, 0.0, 0, 0, 0, ())]
    c = commanded(pad, 0.0, 0.1, lag=0.0)
    assert abs(c["map_yaw_deg"] - 172.0 * 0.05) < 1e-6
    assert abs(c["rx"] - 0.225) < 1e-9 and c["rx_spread"] == 0.45
    late = commanded(pad, 0.05, 0.15, lag=0.05)          # the same window, seen one lag later
    assert abs(late["map_yaw_deg"] - c["map_yaw_deg"]) < 1e-6


def test_a_static_overlay_is_learned_and_cannot_outvote_the_world():
    """An overlay drawn on every frame agrees on 'no motion'; learned from the
    source's own frames, it is masked and the world's turn wins."""
    from perception.camera_motion import static_mask

    base = texture(5)
    frames = [rotate_view(base, 4.0 * k, 0.0) for k in range(8)]
    # A busy panel in the top-left border, identical on every frame.
    panel = texture(9)[:220, :360]
    for f in frames:
        f[:220, :360] = panel
    mask = static_mask(frames)
    assert mask[100, 150] == 0                        # the panel is overlay
    assert mask[H // 2, W // 2] == 255                # the centre never is
    est = Estimator(W, overlay=mask)
    est.step(frames[2], 0.0)
    s = est.step(frames[3], 0.1)
    assert abs(s.yaw_deg - 4.0) < 0.3, s


def test_a_held_trigger_is_an_attack_not_a_turn():
    """Melee (rt) and Web Cluster (lt) are logged apart from buttons; a combo must
    not be scored as an ordinary turn, because it holds the camera still."""
    from perception.camera_motion import Pad, commanded, stratum

    turning = Pad([(0.0, 0.45, 0, 0, 0, (), 0, 0), (1.0, 0.45, 0, 0, 0, (), 0, 0)])
    melee = Pad([(0.0, 0.45, 0, 0, 0, (), 0, 1.0), (1.0, 0.45, 0, 0, 0, (), 0, 1.0)])
    for pad, want in ((turning, "turn"), (melee, "attack")):
        assert stratum(commanded(pad, 0.4, 0.5, 0.0), pad, 0.4, 0.5, 0.0) == want
