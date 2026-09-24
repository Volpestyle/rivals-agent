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


def _animated_copy(img):
    """The same view with something small animating (a still camera is never an exact repeat)."""
    moved = img.copy()
    cv2.circle(moved, (int(0.28 * W), int(0.5 * H)), 30, (255, 40, 200), -1)
    return moved


def test_no_motion_reads_as_no_rotation():
    img = texture()
    s = estimate(img, _animated_copy(img))
    assert s.yaw_deg is not None and abs(s.yaw_deg) < 0.05 and abs(s.pitch_deg) < 0.05


def test_a_repeated_frame_is_withheld_not_zero():
    """Lead decision (a): OBS repeats an image when the game gives it no new frame; the pair
    shows nothing about the camera, so it is withheld whatever the fits say."""
    img = texture()
    s = estimate(img, img.copy())
    assert s.block_diff == 0.0 and s.yaw_deg is None and s.abstain == "repeated frame", s


def test_a_re_encoded_repeat_is_a_repeat_and_a_small_animation_is_not():
    """The mean cannot tell them apart (both ~0.1 grey levels over the frame); the largest
    block change can: re-encoding noise stays low everywhere, a moving mark does not."""
    img = texture()
    enc = lambda x, q: cv2.imdecode(cv2.imencode(".jpg", x, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)
    s = estimate(enc(img, 90), enc(img, 92))
    assert s.block_diff <= 8.0 and s.abstain == "repeated frame", s
    a, b = img.copy(), img.copy()
    cv2.circle(a, (300, 360), 40, (255, 40, 200), -1)
    cv2.circle(b, (312, 360), 40, (255, 40, 200), -1)
    s = estimate(enc(a, 90), enc(b, 90))
    assert s.frame_diff < 0.2 and s.block_diff > 8.0 and s.abstain != "repeated frame", s


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


# --- the replay viewer, the zero-flow rules and the focal fit (VUH-1353) ------
# The spectator-UI cases below reproduce the MECHANISM of the M1 replay failure --
# ORB's feature budget going to sharp, still UI text over a soft world -- by
# construction: the world is blurred and its contrast halved (`_soft`). They do not
# show that the replay's world is soft; the masked M1 rerun on the replay does.

def _paste_replay_ui(frame, ui):
    """The replay viewer's spectator UI, drawn identically on every frame."""
    for x0, y0, x1, y1 in (((0.0, 0.12, 1.0, 0.21)), (0.78, 0.19, 1.0, 0.25), (0.89, 0.58, 1.0, 0.70)):
        ys, xs = slice(int(y0 * H), int(y1 * H)), slice(int(x0 * W), int(x1 * W))
        frame[ys, xs] = ui[ys, xs]
    return frame


def _soft(img):
    """A blurred, low-contrast world, built so that sharp UI text out-votes it."""
    w = cv2.GaussianBlur(img, (0, 0), 3).astype(np.float32)
    return np.clip(90 + (w - 90) * 0.5, 0, 255).astype(np.uint8)


def _overlay_won_pair():
    ui = texture(11)
    return (_paste_replay_ui(_soft(texture()), ui),
            _paste_replay_ui(_soft(rotate_view(texture(), 4.0, 0.0)), ui))


def test_the_replay_ui_regions_are_masked_and_the_turn_is_recovered():
    """Mechanism check: rosters, FPS/kill-feed row and the Current Player box sit
    outside the pad HUD bands; with the replay mask no feature is taken there and
    the soft world's 4 degree turn is recovered."""
    from perception.camera_motion import REPLAY_UI_MASK, mask_for

    m = mask_for((H, W), REPLAY_UI_MASK)
    for x, y in ((0.5, 0.18), (0.9, 0.22), (0.95, 0.64)):
        assert m[int(y * H), int(x * W)] == 0, (x, y)
    a, b = _overlay_won_pair()
    est = Estimator(W, REPLAY_UI_MASK)
    est.step(a, 0.0)
    s = est.step(b, 0.1)
    assert s.yaw_deg is not None and abs(s.yaw_deg - 4.0) < 0.3, s


def test_an_overlay_won_zero_is_withheld_by_the_border_rule_on_images():
    """Mechanism check, unmasked: the UI wins the fit (zero flow) with its inliers in
    the border strips, so the border rule withholds it -- unknown, not 0."""
    a, b = _overlay_won_pair()
    s = estimate(a, b)
    assert s.flow_px is not None and s.flow_px <= 0.05, s          # the overlay did win the fit
    assert s.border_frac >= 0.95, s
    assert s.yaw_deg is None and s.abstain == "zero flow on border features only", s


def test_without_the_border_rule_the_centre_test_still_withholds_it(monkeypatch):
    """The centre test alone catches the same pair: the soft world yields no centre matches."""
    from perception import camera_motion as cm

    monkeypatch.setattr(cm, "PAIR_BORDER_FRAC", 1.01)
    a, b = _overlay_won_pair()
    s = estimate(a, b)
    assert s.yaw_deg is None and s.abstain == "zero flow unconfirmed: too few centre matches", s


@pytest.mark.parametrize("diameter", [100, 160])
def test_a_still_camera_with_something_moving_in_the_centre_keeps_its_zero(diameter):
    """Review C1/C3: a real still pair is never an exact copy -- an effect, a bot or
    a limb changes. The centre's own matches are the still world and confirm the
    zero, even where the mean pixel change (world_diff, a diagnostic) exceeds 4."""
    img = texture()
    moved = img.copy()
    cv2.circle(moved, (int(0.28 * W), int(0.5 * H)), diameter // 2, (255, 40, 200), -1)
    s = estimate(img, moved)
    assert s.abstain is None and s.yaw_deg is not None and abs(s.yaw_deg) < 0.05, s
    assert s.centre_inliers >= 20 and s.centre_rot_deg < 0.25, s
    assert 0.5 < s.border_frac < 0.95, s          # the border rule's restraint on an ordinary scene
    if diameter == 160:
        assert s.world_diff > 4.0, s               # the old world-change rule would have withheld it


def test_a_sharp_turn_keeps_its_rotation_and_centre_flow():
    s = estimate(texture(), rotate_view(texture(), 4.0, 0.0))
    assert s.abstain is None and abs(s.yaw_deg - 4.0) < 0.3 and s.centre_flow > 1.0, s


def test_the_pair_rule_branches():
    from perception.camera_motion import Step, pair_abstain

    def step(flow, bf, n, rot, inl):
        return Step(0.0, 0.01, 200, 150, flow, 0.0, 0.0, 0.0, border_frac=bf, centre_matches=n,
                    centre_rot_deg=rot, centre_inliers=inl, centre_consistency=None if inl is None else inl / n)

    contradicted = "zero flow contradicted by the centre's own matches"
    assert pair_abstain(step(0.0, 0.99, 300, 0.0, 300)) == "zero flow on border features only"
    assert pair_abstain(step(0.0, 0.6, 19, 0.0, 19)) == "zero flow unconfirmed: too few centre matches"
    assert pair_abstain(step(0.0, 0.6, 50, 0.30, 48)) == contradicted            # the centre rotated
    assert pair_abstain(step(0.0, 0.6, 50, 0.10, 19)) == contradicted            # too few explained by any rotation
    assert pair_abstain(step(0.0, 0.6, 50, None, None)) == contradicted          # no fit at all
    assert pair_abstain(step(0.0, 0.6, 50, 0.12, 45)) is None                    # keypoint jitter: kept
    assert pair_abstain(step(0.0, 0.6, 200, 0.05, 60)) is None                   # combat: a 30 % share still keeps it
    assert pair_abstain(step(2.5, 0.99, 0, None, None)) is None                  # a moving fit is never withheld here


@pytest.mark.parametrize("shift_px,kept", [(1, True), (2, True), (5, False)])
def test_centre_jitter_is_kept_and_centre_motion_is_not_a_zero(shift_px, kept):
    """Lead decision (c): the border world is identical (the fit reads zero flow) while
    the centre strips move by shift_px. 1-2 px is ORB keypoint jitter on real range
    footage (1 px is ~0.12 deg at 465 px) and keeps the zero; 5 px (~0.46 deg) is
    real motion the zero cannot claim."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    moved = img.copy()
    x0, y0, x1, y1 = STATIC_CENTRE
    ys, xs = slice(int(y0 * H), int(y1 * H)), slice(int(x0 * W), int(x1 * W))
    moved[ys, xs] = np.roll(img[ys, xs], shift_px, axis=1)
    s = estimate(img, moved)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.centre_inliers >= 20, s
    if kept:
        assert s.abstain is None and s.source == "main" and s.centre_rot_deg < 0.25, s
    else:
        # Real motion the zero cannot claim. The centre fit is strong here, so (review B3)
        # its rotation is reported, flagged, instead of the zero.
        assert s.source == "centre" and s.centre_rot_deg >= 0.25 and abs(s.yaw_deg) >= 0.25, s


# The review's two real range pairs (l2 proxies' baseline1, saved native frames,
# downscaled to 1280): a true still camera with one glowing effect, and a jump the
# camera translates with. Local-only; pinned by hash.
BASELINE1 = [ROOT / "data/l1/baseline1", Path("C:/rivals-agent/data/l1/baseline1")]
REVIEW_PAIRS = {
    1398: (("001398.jpg", "e68a9a66bb468d299e4de1bbca0a1265d5845306a615e72729e86d9312c8e715"),
           ("001399.jpg", "a749c969ca23a050e22e243f2da584a14a8d16ee1337f3edf5691d5b4c392da8"), None),
    97: (("000097.jpg", "29f0d56fc871699dc7e9611f6e329a9fd19a414d7756a64fe28cdbe2de2d57d6"),
         ("000098.jpg", "48dac4b9ba8832cd02ecaf62170c62d254ae313843aba636198ba6c7c98e1fb7"),
         "zero flow contradicted by the centre's own matches"),
}


@pytest.mark.corpus
@pytest.mark.parametrize("k", sorted(REVIEW_PAIRS))
def test_the_reviewed_range_pairs(k):
    import hashlib

    run = next((d for d in BASELINE1 if d.exists()), None)
    if run is None:
        pytest.skip("the l2 range proxies' baseline1 frames are local to the PC")
    (fa, ha), (fb, hb), want = REVIEW_PAIRS[k]
    frames = []
    for name, digest in ((fa, ha), (fb, hb)):
        assert hashlib.sha256((run / name).read_bytes()).hexdigest() == digest, name
        frames.append(cv2.resize(cv2.imread(str(run / name)), (W, H), interpolation=cv2.INTER_AREA))
    s = estimate(*frames)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.abstain == want, s
    if want is None:
        assert s.yaw_deg is not None and abs(s.yaw_deg) < 0.05
        assert s.centre_rot_deg < 0.25 and s.centre_inliers >= 20, s


def test_the_window_overlay_is_learned_from_the_window_itself():
    from perception.camera_motion import window_overlay

    ui = texture(11)
    frames = [_paste_replay_ui(rotate_view(texture(5), 3.0 * k, 0.0), ui) for k in range(30)]
    mask = window_overlay(frames, n=12)
    assert mask[int(0.16 * H), int(0.1 * W)] == 0      # the roster band is overlay
    assert mask[H // 2, W // 2] == 255


def _steps(kinds, dt=0.1):
    """Steps from a string: 'z' unconfirmed zero (withheld), 's' confirmed still, 't' a turn, '.' no fit."""
    from perception.camera_motion import Step

    out = []
    for i, k in enumerate(kinds):
        t0 = i * dt
        if k == ".":
            out.append(Step(t0, t0 + dt, 10, 0, None, None, None, None))
        elif k == "z":
            out.append(Step(t0, t0 + dt, 100, 80, 0.0, None, None, None, abstain="zero flow unconfirmed: too few centre matches"))
        elif k == "s":
            out.append(Step(t0, t0 + dt, 100, 80, 0.0, 0.0, 0.0, 0.0, centre_matches=200, centre_flow=0.0))
        else:
            out.append(Step(t0, t0 + dt, 100, 80, 3.0, 0.5, 0.0, 0.0, centre_matches=200, centre_flow=3.0))
    return out


def test_a_window_of_unconfirmed_zeros_is_invalid_not_no_rotation():
    """Over half the fitted pairs are zeros the world did not confirm: every rotation withheld."""
    from perception.camera_motion import checked

    steps, verdict = checked(_steps("zzzzzztttt"))
    assert verdict["valid"] is False and verdict["unconfirmed_zero_frac"] == 0.6
    assert all(s.yaw_deg is None for s in steps)


def test_a_confirmed_still_window_keeps_its_zeros_and_turns():
    """Review C2: zeros the centre confirmed are not counted against the window."""
    from perception.camera_motion import checked

    raw = _steps("sssssssstt.")
    steps, verdict = checked(raw)
    assert verdict["valid"] is True and verdict["zero_flow_frac"] == 0.8 and verdict["unconfirmed_zero_frac"] == 0.0
    assert steps == raw


def test_one_bad_stretch_does_not_null_the_other_sub_windows():
    """Review C2: the verdict runs over fixed 3 s sub-windows, so an invalid stretch
    withholds only itself."""
    from perception.camera_motion import checked_windows

    raw = _steps("z" * 30 + "sssssssstt" * 6)          # 3 s of unconfirmed zeros, then 6 s of stills and turns
    steps, verdicts = checked_windows(raw, window_s=3.0)
    assert [v["valid"] for v in verdicts] == [False, True, True]
    assert all(s.yaw_deg is None for s in steps[:30])
    assert [s.yaw_deg for s in steps[30:]] == [s.yaw_deg for s in raw[30:]]


def test_a_mostly_still_recording_keeps_its_turns_through_run_video(tmp_path):
    """Review C2 end to end: a 6 s clip, still with a moving patch for most of it and
    turning for a moment, keeps its turns and its confirmed zeros through run_video."""
    from perception.camera_motion import run_video

    base = texture()
    video = tmp_path / "still.avi"
    wr = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (W, H))
    yaw = 0.0
    for i in range(60):
        if 40 <= i < 46:
            yaw += 3.0                                  # 0.6 s of turning
        f = rotate_view(base, yaw, 0.0)
        # something animating every frame, so no pair is a repeated frame
        cv2.circle(f, (int(0.22 * W) + 12 * (i % 10), int(0.5 * H)), 40, (255, 40, 200), -1)
        wr.write(f)
    wr.release()
    steps = run_video(video, out=tmp_path / "out.jsonl", progress=0)
    turns = [s for s in steps if s.yaw_deg is not None and abs(s.yaw_deg) > 1.0]
    stills = [s for s in steps if s.yaw_deg is not None and abs(s.yaw_deg) < 0.05]
    assert len(turns) >= 5, [(round(s.t0, 1), s.yaw_deg, s.abstain) for s in steps]
    assert len(stills) >= 40, [(round(s.t0, 1), s.yaw_deg, s.abstain) for s in steps]
    meta = (tmp_path / "out.jsonl").read_text().splitlines()[0]
    assert '"verdicts"' in meta and '"valid": false' not in meta


# The focal tests below are CODE checks on ideal correspondences (whole-frame points,
# +/-6 degree rotations, 0.3 px noise). They are not evidence that M2 is conditioned
# on footage: shift-only fits gave 590-860 px, and the live gate refused at 515 px
# with a 427-637 px basin (VUH-1353 M1 rerun).

def _rotation_pairs(focal, n_pairs=30, max_deg=6.0, noise=0.3, outliers=0.15, seed=0):
    """Exact pure-rotation correspondences seen through `focal`, with pixel noise and outliers."""
    from perception.camera_motion import rays

    rng = np.random.default_rng(seed)
    pairs = []
    for _ in range(n_pairs):
        yaw, pitch = np.radians(rng.uniform(-max_deg, max_deg, 2))
        ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
        rx = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
        p0 = rng.uniform([40, 40], [W - 40, H - 40], (150, 2))
        q = rays(p0, (H, W), focal) @ (ry @ rx).T
        p1 = np.column_stack([focal * q[:, 0] / q[:, 2] + W / 2, focal * q[:, 1] / q[:, 2] + H / 2])
        p1 += rng.normal(0, noise, p1.shape)
        bad = rng.random(len(p1)) < outliers
        p1[bad] = rng.uniform([0, 0], [W, H], (int(bad.sum()), 2))
        pairs.append((p0, p1))
    return pairs


@pytest.mark.parametrize("focal", [465.0, 600.0])
def test_code_check_the_focal_fit_recovers_the_focal_the_pairs_were_made_with(focal):
    from perception.camera_motion import focal_fit

    got = focal_fit(_rotation_pairs(focal), (H, W))
    assert abs(got["focal"] - focal) / focal < 0.02, got
    assert got["basin_frac"] <= 0.05, got


def test_code_check_the_replay_focal_is_fitted_only_after_the_live_fit_recovers_465():
    from perception.camera_motion import replay_focal

    ok = replay_focal(_rotation_pairs(465.0), _rotation_pairs(600.0, seed=1), (H, W), known=465.0)
    assert ok["gate"]["passed"] is True
    assert abs(ok["replay"]["focal"] - 600.0) < 12 and ok["replay"]["conditioned"]

    wrong = replay_focal(_rotation_pairs(520.0), _rotation_pairs(600.0, seed=1), (H, W), known=465.0)
    assert wrong["gate"]["passed"] is False and wrong["replay"] is None
    assert "misses" in wrong["gate"]["reason"]


def test_code_check_turns_too_small_to_tell_focal_lengths_apart_are_refused():
    from perception.camera_motion import replay_focal

    tiny = _rotation_pairs(465.0, max_deg=0.05, noise=0.5)
    got = replay_focal(tiny, tiny, (H, W), known=465.0)
    assert got["gate"]["passed"] is False and got["replay"] is None


def test_last_matches_are_never_the_previous_pairs():
    """Review C4: a pair that returns early must not leave the previous pair's matches."""
    est = Estimator(W)
    img = texture()
    est.step(img, 0.0)
    est.step(rotate_view(img, 2.0, 0.0), 0.1)
    assert est.last_matches is not None
    flat = np.full((H, W, 3), 70, np.uint8)
    est.step(flat, 0.2)
    assert est.last_matches is None


@pytest.mark.parametrize("side", ["left", "right"])
def test_a_still_camera_with_moving_combat_content_keeps_its_zero(side):
    """Lead decisions (i) and (a): in combat an effect or a bot moves in one side strip and
    lowers the share of centre matches the zero explains (~0.6 here, under the 80 % option
    (c) required), while the static majority fits zero. The moving outliers do not form a
    world rotation on both sides, so the zero is kept."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    moved = img.copy()
    x0, y0, x1, y1 = STATIC_CENTRE
    ys = slice(int(y0 * H), int(y1 * H))
    xs = slice(int(x0 * W), int(0.36 * W)) if side == "left" else slice(int(0.64 * W), int(x1 * W))
    moved[ys, xs] = np.roll(img[ys, xs], 15, axis=1)
    s = estimate(img, moved)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.centre_consistency < 0.8 and s.centre_inliers >= 20 and s.centre_rot_deg < 0.25, s
    assert s.world_rot_deg is None, s
    assert s.abstain is None and s.source == "main" and abs(s.yaw_deg) < 0.05, s


def test_screen_fixed_content_cannot_hold_a_zero_while_the_world_turns():
    """Lead decision (a), the live-turn failure: content fixed to the screen fills part of
    the centre (zero consensus) while the rest of the world turns 1.5 degrees on both
    sides. The outliers form that world rotation, which is reported (source "centre")."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    turned = rotate_view(img, 1.5, 0.0)
    x0, y0, x1, y1 = STATIC_CENTRE
    keep = np.ones((H, W), bool)
    keep[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = False     # border: fixed, as an overlay
    keep[int(0.40 * H):int(0.62 * H), int(x0 * W):int(x1 * W)] = True  # a centre band fixed to the screen
    turned[keep] = img[keep]
    s = estimate(img, turned)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.world_rot_deg is not None and abs(s.world_rot_deg - 1.5) < 0.2, s
    assert s.source == "centre" and s.yaw_deg is not None and abs(s.yaw_deg) > 1.0, s


def test_limitation_a_rigid_object_across_both_strips_reads_as_the_world():
    """Known limitation of (a): one coherent object spanning both side strips moves like
    a world rotation and contradicts the zero. Pinned so a change is noticed."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    moved = img.copy()
    x0, y0, x1, y1 = STATIC_CENTRE
    ys = slice(int(y0 * H), int((y0 + 0.45 * (y1 - y0)) * H))
    xs = slice(int(x0 * W), int(x1 * W))
    moved[ys, xs] = np.roll(img[ys, xs], 15, axis=1)
    s = estimate(img, moved)
    assert s.world_rot_deg is not None and s.source == "centre", s


# --- review re-check (review-camera-motion-2.md): B3 centre-sourced rotation, B2 border override

def _border_still_centre_turned(yaw):
    """A world whose border strips stay put (as an overlay would) while the centre turns by `yaw`."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    turned = rotate_view(img, yaw, 0.0)
    x0, y0, x1, y1 = STATIC_CENTRE
    border = np.ones((H, W), bool)
    border[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = False
    turned[border] = img[border]
    return img, turned


@pytest.mark.parametrize("yaw", [0.8, 2.0])
def test_a_strong_centre_fit_reports_its_rotation_instead_of_the_zero(yaw):
    """B3: the main fit reads zero (the still border wins), the centre fit is strongly
    supported and rotated: its rotation is reported, flagged source="centre"."""
    a, b = _border_still_centre_turned(yaw)
    s = estimate(a, b)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.source == "centre" and s.abstain is None, s
    assert s.centre_inliers >= 50 and s.centre_consistency >= 0.8, s
    assert abs(s.yaw_deg - yaw) < 0.1, s


def _plain_floor(shift_px=0, spots=((0.25, 0.4), (0.3, 0.6), (0.7, 0.4))):
    """Texture only in the border strips, a plain centre with a few small textured patches."""
    from perception.camera_motion import STATIC_CENTRE

    img = texture()
    x0, y0, x1, y1 = STATIC_CENTRE
    frame = img.copy()
    frame[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = 90
    patch = texture(31)
    out = []
    for dx in (0, shift_px):
        f = frame.copy()
        for cx, cy in spots:
            px, py = int(cx * W), int(cy * H)
            f[py - 18:py + 18, px - 18 + dx:px + 18 + dx] = patch[py - 18:py + 18, px - 18:px + 18]
        out.append(f)
    return out


def test_the_border_rule_yields_to_a_still_centre():
    """B2: a still camera over a plain floor has almost all its inliers in the border
    strips. A few centre matches that did not move beyond jitter keep the zero."""
    a, b = _plain_floor(0)
    cv2.circle(b, (int(0.5 * W), int(0.9 * H)), 60, (255, 40, 200), -1)   # an animating HUD-band mark: not a repeat
    s = estimate(a, b)
    assert s.border_frac >= 0.95 and s.centre_matches >= 10 and s.centre_flow <= 1.0, s
    assert s.abstain is None and s.yaw_deg is not None and abs(s.yaw_deg) < 0.05, s


def test_the_border_rule_still_fires_when_the_centre_moved():
    """Too few centre matches for B3 to report, and they moved: the border rule withholds."""
    s = estimate(*_plain_floor(6))
    assert s.border_frac >= 0.95 and s.centre_flow > 1.0 and (s.centre_inliers or 0) < 50, s
    assert s.abstain == "zero flow on border features only", s


# Review re-check audit pairs from the l2 range proxies' baseline1 (saved frames at
# 1280 wide), hash-pinned. 721, 1329 and 2396: the camera visibly moved while the main
# fit read zero; the centre fit is strong, so its rotation is reported. 2510: audited
# still (difference black but for the character and the bot's name plate), yet its
# only centre matches are on that moving content and the floor gives none -- B2
# cannot confirm it. Pinned as a strict expected failure: the known false withhold.
AUDIT_PAIRS = {
    721: ("000721.jpg", "128e819072ae260abac7296a4eca9f36eaa93647aac268ef964fc49c0f4e3577",
          "000722.jpg", "ff4b5e495b15037e7c0b7add3913765064b9eeec72d2f8230d1124d21026b6bf"),
    1329: ("001329.jpg", "f744d97d8ad9dcd2b4277816896d557bde63a6660c4892299c3e4c764aa39e06",
           "001330.jpg", "b009a0aa8545d7e85ad68d4458862ff24efbb706d58c5e5319ef70e2da9a111d"),
    2396: ("002396.jpg", "d4075655bb2b34c73a295a3296c7a34c23eb0ef6b04a409258c561361eaabc1e",
           "002397.jpg", "7f3576feae0dbf014bbc3face58ec4c68f4978ef4f9d85e9691b5e6d1a9adccb"),
    2510: ("002510.jpg", "fbf1ed8e245d4579cf54b7eeabee5ae43c0336ae7b84e09d390edaca76d9dcfb",
           "002511.jpg", "80443ade39cbf8182ee691fe18bada96106d76b84404931d83275ef1cd755c3e"),
}


def _audit_pair(k):
    import hashlib

    run = next((d for d in BASELINE1 if d.exists()), None)
    if run is None:
        pytest.skip("the l2 range proxies' baseline1 frames are local to the PC")
    fa, ha, fb, hb = AUDIT_PAIRS[k]
    frames = []
    for name, digest in ((fa, ha), (fb, hb)):
        assert hashlib.sha256((run / name).read_bytes()).hexdigest() == digest, name
        frames.append(cv2.resize(cv2.imread(str(run / name)), (W, H), interpolation=cv2.INTER_AREA))
    return estimate(*frames)


@pytest.mark.corpus
@pytest.mark.parametrize("k", [721, 1329, 2396])
def test_audited_moving_pairs_report_the_centre_rotation(k):
    s = _audit_pair(k)
    assert s.flow_px is not None and s.flow_px <= 0.05, s
    assert s.source == "centre" and s.yaw_deg is not None and s.centre_rot_deg >= 0.25, s


@pytest.mark.corpus
@pytest.mark.xfail(strict=True, reason="audited still camera; its only centre matches are moving content, "
                                       "so B2 cannot confirm the zero (known false withhold)")
def test_audited_still_low_texture_pair_2510_keeps_its_zero():
    s = _audit_pair(2510)
    assert s.abstain is None and s.yaw_deg is not None and abs(s.yaw_deg) < 0.05, s
