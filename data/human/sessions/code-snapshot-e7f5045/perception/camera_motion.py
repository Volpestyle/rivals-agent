"""Camera rotation between consecutive frames, from the pixels alone.

    uv run --group perception python -m perception.camera_motion proxy data/l1/baseline4 out.jsonl
    uv run --group perception python -m perception.camera_motion video clip.mp4 out.jsonl --hz 60

A feasibility probe for inverse dynamics: can the camera command an expert gave
be recovered from their footage? Three different quantities, kept apart in every
output and never renamed into one another:

  observed   image motion -- matched feature displacement, pixels
  estimated  camera rotation fitted to that motion -- yaw/pitch, degrees
  inferred   the stick command that rotation implies through the turn map

The pad log proves what was *commanded*. The turn map (agent.controller.Cal,
measured by the controller lane) is a calibration model of what a command does,
not independent truth about what the camera actually did: a camera pitched into
its limit ignores a pitch command the map says moves it.

Method: ORB features outside the HUD, the player's own body and any known
enemy box; ratio-tested matches; then a rotation-only fit. Each pixel is
back-projected to a ray with the known focal length and the rotation that maps
one frame's rays onto the next is solved in closed form (Kabsch) inside RANSAC
with two-point samples. No small-angle approximation, so an 18 degree step at
10 Hz is fitted as exactly as a 3 degree one at 60 fps. The camera cannot roll,
so any roll in the fitted rotation is world yaw seen from a pitched camera, and
world yaw is recovered as the length of the yaw-roll component.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.controller import Cal, _interp  # noqa: E402

CAL = Cal()

# Regions that do not move with the world, as frame fractions (x0, y0, x1, y1).
# The HUD bands, and the third-person body, which stays put while the world
# turns behind it -- matching on him would read every turn as no turn.
HUD_MASK = ((0.0, 0.0, 1.0, 0.12),       # objective text, score bar, kill feed
            (0.0, 0.78, 1.0, 1.0))       # hp, ammo, ability row, portrait
BODY_MASK = ((0.36, 0.30, 0.64, 1.0),)   # Spider-Man and the crosshair

MIN_INLIERS = 20        # fewer than this and the fit abstains
MIN_INLIER_FRAC = 0.35
RANSAC_ITERS = 300
INLIER_PX = 3.0         # reprojection tolerance, at the frame's own width


@dataclass
class Step:
    """One frame pair. Rates are None when the fit abstained."""

    t0: float
    t1: float
    matches: int
    inliers: int
    flow_px: float | None       # OBSERVED: median inlier displacement, pixels
    yaw_deg: float | None       # ESTIMATED: world yaw over the interval, right positive
    pitch_deg: float | None     # ESTIMATED: pitch over the interval, up positive
    roll_deg: float | None      # fitted roll; ~0 unless pitched, see world_yaw
    world_diff: float | None = None      # DIAGNOSTIC only: mean grey change in the centre strips
    border_frac: float | None = None     # share of inliers outside STATIC_CENTRE
    centre_matches: int | None = None    # ratio-tested matches in the centre strips (see pair_abstain)
    centre_flow: float | None = None     # their median displacement, px (diagnostic)
    centre_rot_deg: float | None = None  # rotation fitted to the centre matches alone (zero-flow pairs only)
    centre_inliers: int | None = None    # centre matches that rotation explains (see pair_abstain)
    centre_consistency: float | None = None  # their share of the centre matches (DIAGNOSTIC only)
    centre_yaw_deg: float | None = None  # that centre-only rotation as yaw / pitch (diagnostic, or the
    centre_pitch_deg: float | None = None  # reported rotation when source == "centre")
    world_rot_deg: float | None = None   # rotation fitted to the centre fit's OUTLIERS (see pair_decision)
    world_inliers: int | None = None     # outliers it explains, when they span both side strips
    world_yaw_deg: float | None = None
    world_pitch_deg: float | None = None
    frame_diff: float | None = None      # mean grey change over the whole frame (diagnostic)
    block_diff: float | None = None      # largest 16x16-block mean grey change (repeated-frame check)
    source: str = "main"                 # "centre": the rotation came from a centre-only fit (see pair_decision)
    abstain: str | None = None           # why a fitted pair's rotation was withheld

    @property
    def yaw_rate(self):
        return None if self.yaw_deg is None else self.yaw_deg / (self.t1 - self.t0)

    @property
    def pitch_rate(self):
        return None if self.pitch_deg is None else self.pitch_deg / (self.t1 - self.t0)


def focal_for(width):
    """The calibrated focal length scaled to this frame width (fixed FOV)."""
    return CAL.focal_1280 * width / 1280.0


STATIC_STD = 6.0                          # grey levels; below this a pixel never changed
STATIC_CENTRE = (0.2, 0.25, 0.8, 0.75)    # never treated as overlay, see static_mask


def static_mask(frames):
    """uint8 mask, 0 on this source's static overlays, learned from its own frames.

    A pixel whose value barely changes across frames spread over a whole run is
    drawn on top of the world, not part of it: the range's menu panel, an FPS
    counter, a streamer's webcam frame, chat, a logo. Unmasked, those features
    agree perfectly on "no motion" and out-vote a blurred or sparse world during
    a fast turn -- which is exactly how the first version read the 0.45-stick
    Search spin as standing still. Learned per source because every VOD draws
    different overlays. Only the borders are eligible: a camera that holds
    still for a whole run would otherwise mask its own world.
    """
    import cv2

    grey = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if f.ndim == 3 else f
                     for f in frames]).astype(np.float32)
    h, w = grey.shape[1:]
    static = (grey.std(axis=0) < STATIC_STD).astype(np.uint8)
    x0, y0, x1, y1 = STATIC_CENTRE
    static[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 0
    static = cv2.dilate(static, np.ones((15, 15), np.uint8))
    return np.where(static > 0, 0, 255).astype(np.uint8)


def window_overlay(frames, n=12):
    """static_mask() learned from n frames spread over one window's own frames.

    For callers that stream a window rather than seek a file: decode a sparse
    sample of the window first, learn its overlays, then stream it in full.
    """
    frames = list(frames)
    if not frames:
        return None
    pick = np.linspace(0, len(frames) - 1, min(n, len(frames))).astype(int)
    return static_mask([frames[i] for i in pick])


# The in-client replay viewer (VUH-1328) draws a spectator UI over the world that
# the HUD bands above do not cover. Measured on the DayMR replay's keyframe k0414
# (843 s). Unmasked, these feature-rich, perfectly still regions won every fit on
# eight 3 s windows: inlier flow 0 on 99-100 % of pairs, read as no rotation.
REPLAY_UI_MASK = ((0.0, 0.0, 1.0, 0.21),       # both team rosters: portraits, names, ult %
                  (0.78, 0.19, 1.0, 0.25),     # client FPS readout and the kill-feed row
                  (0.89, 0.58, 1.0, 0.70))     # "Current Player" ping and packet-loss box

# A window whose fits mostly found nothing moving, and whose world could not
# confirm it, is not evidence of a still camera: a static overlay out-voting the
# world reads the same. Such a window is reported invalid and its rotations
# withheld, never reported as zero. Only zeros the centre test (pair_abstain)
# could NOT confirm are counted, so a camera that really held still -- confirmed
# by its own centre matches -- keeps its window. run_video applies this over fixed
# WINDOW_S sub-windows, so one bad stretch cannot null a whole recording's turns.
ZERO_FLOW_PX = 0.05       # median displacement at or under this: nothing moved
MAX_ZERO_FLOW = 0.5       # fraction of fitted pairs; above it the window is invalid
WINDOW_S = 3.0


def _unconfirmed_zero(s):
    return s.flow_px is not None and s.flow_px <= ZERO_FLOW_PX and s.abstain is not None


def window_verdict(steps):
    """{"valid", "zero_flow_frac", "unconfirmed_zero_frac", "fitted", "pairs", "reason"} for one window."""
    fitted = [s for s in steps if s.flow_px is not None]
    if not fitted:
        return {"valid": False, "zero_flow_frac": None, "unconfirmed_zero_frac": None, "fitted": 0,
                "pairs": len(steps), "reason": "no fitted pairs"}
    zero = sum(s.flow_px <= ZERO_FLOW_PX for s in fitted) / len(fitted)
    frac = sum(_unconfirmed_zero(s) for s in fitted) / len(fitted)
    valid = frac <= MAX_ZERO_FLOW
    return {"valid": valid, "zero_flow_frac": round(zero, 3), "unconfirmed_zero_frac": round(frac, 3),
            "fitted": len(fitted), "pairs": len(steps),
            "reason": None if valid else "most pairs are zero flow the world's own matches did not confirm"}


def checked(steps):
    """(steps, verdict) for one window; an invalid window's rotations come back as None, not 0."""
    verdict = window_verdict(steps)
    if verdict["valid"]:
        return steps, verdict
    return [replace(s, yaw_deg=None, pitch_deg=None, roll_deg=None,
                    abstain=s.abstain or "window invalid") for s in steps], verdict


def checked_windows(steps, window_s=WINDOW_S):
    """`checked` over consecutive fixed sub-windows of window_s seconds (by t0).

    Returns (steps, verdicts), verdicts as [{"t0", **verdict}, ...].
    """
    if not steps:
        return steps, []
    start = steps[0].t0
    groups = {}
    for s in steps:
        groups.setdefault(int((s.t0 - start) // window_s), []).append(s)
    out, verdicts = [], []
    for k in sorted(groups):
        part, verdict = checked(groups[k])
        out += part
        verdicts.append({"t0": round(start + k * window_s, 3), **verdict})
    return out, verdicts


# The window rule only catches total failure. An overlay out-votes the world
# during a fast turn -- a blurred or sparse world -- so it strikes the fast pairs,
# the ones that matter, inside windows that pass. So every zero-flow pair must be
# confirmed by the world itself: the ratio-tested matches in the centre strips
# (STATIC_CENTRE, never overlay, minus the body's columns) must be numerous enough,
# and a rotation fitted to them alone must be small and must explain at least
# MIN_CENTRE_MATCHES of them.
# A still camera with a bot, an effect or a limb moving in the centre keeps its
# zero: most centre matches are the still world. So does ORB keypoint jitter: on
# real range footage centre matches of a still camera move 0.2-1.7 px (the
# keypoint grid; 1 px is ~0.12 deg at 465 px focal), which a bar in pixels
# (0.05 px) wrongly read as motion. An overlay-won pair has no centre matches (a
# world too soft to match), or centre matches that rotate by more than
# CENTRE_STILL_DEG, or too few that any one rotation explains (parallax from a
# moving camera), and is withheld. The explained SHARE is a diagnostic only: in
# combat, effects and bots in the centre lower it while the static majority still
# fits zero, and requiring 80 % withheld most combat zeros (lead decision (i)).
# The mean pixel change (`world_diff`) is a diagnostic only: it rises for any
# motion in the centre, not just camera rotation, and it withheld true stills on
# range footage (review C1).
# A zero whose inliers are nearly all in the border strips is withheld first.
# Border shares measured: this file's synthetic texture() scenes 0.57-0.58, real
# range pairs 0.16-0.98; the border rule never fired on ~700 real range pairs.
#
# Two refinements from the review re-check (review-camera-motion-2.md):
# - When the centre fit is strongly supported and rotated, the main fit's zero is
#   the error and the centre rotation is the better estimate: it is REPORTED,
#   flagged source="centre", rather than withheld (B3). Against logged mouse
#   counts on James's live windows it is directional but imprecise: median error
#   about 0.5 deg on 1.1-1.3 deg moves, n = 24, including the outlier-refit
#   rotations below.
# - The border rule also fires on a still camera looking at a plain floor, where
#   almost every feature sits at the edges. When it would fire, the centre decides
#   if it has a few matches that did not move beyond keypoint jitter (B2; the
#   baseline1 2510 cluster).
MIN_CENTRE_MATCHES = 20
CENTRE_STILL_DEG = 0.25       # centre-only rotation under this is keypoint jitter, not motion
CENTRE_STRONG_INLIERS = 50    # a centre fit this well supported ...
CENTRE_STRONG_SHARE = 0.80    # ... and this consistent is reported when it rotates
PAIR_BORDER_FRAC = 0.95
BORDER_OVERRIDE_MATCHES = 10  # with the border rule firing, this many centre matches ...
BORDER_OVERRIDE_PX = 1.0      # ... whose median moved no more than jitter keep the zero
# Lead decision (a), from live turns with logged mouse counts: on a live turn the
# centre's zero consensus can come from content fixed to the screen or to the
# character (limbs outside the body columns, attached effects) while the world
# rotates, and the explained share cannot tell that from range combat (a still
# world with moving effects). The centre fit's OUTLIERS separate them: if they
# form one consistent rotation of at least CENTRE_STILL_DEG, supported on BOTH
# side strips, the world turned and the zero is contradicted (reported from that
# fit when it is strong, as B3, else withheld). Combat effects and bots move
# incoherently, or on one side only, and do not.
# Known residual: on 051828's live windows, 7 of 319 pairs with >= 60 mouse counts
# (13 of 722 at >= 20) still report a zero. Their outliers form no single rotation
# on both sides -- most likely world parallax while the character moves and turns,
# which a rotation-only refit cannot model. So a main-source zero is not proof of
# a still camera during movement plus turning. See docs/lanes/inverse-dynamics.md,
# "lead decision (a), measured".
WORLD_MIN_INLIERS = 20
WORLD_MIN_PER_SIDE = 5
WORLD_STRONG_INLIERS = 50
# OBS repeats an image at a new timestamp when the game hands it no new frame; the
# re-encoded repeat differs by ~0.07 grey levels on average. Such a pair shows
# nothing about the camera, so it is withheld, never reported as zero. The MEAN
# cannot find it -- a 40 px mark moving 12 px averages ~0.1 too -- but WHERE the
# change sits can: re-encoding noise is low in every block (<= 4.5 even for a busy
# texture re-encoded at another quality), any real change is large somewhere
# (a 12 px dot appearing: 17). So the largest 16x16-block mean decides.
REPEAT_BLOCK = 8.0


def pair_decision(step):
    """("main" | "centre" | "world" | None, reason) for one fitted pair.

    "main" keeps the main fit (a moving fit, or a confirmed zero); "centre"
    reports the centre-only rotation instead of the main fit's zero; "world"
    reports the rotation of the centre fit's outliers; None withholds, with the
    reason. A repeated frame is withheld whatever the fits say.
    """
    if step.block_diff is not None and step.block_diff <= REPEAT_BLOCK:
        return None, "repeated frame"
    if step.flow_px is None or step.flow_px > ZERO_FLOW_PX:
        return "main", None
    if step.world_rot_deg is not None:
        if step.world_inliers >= WORLD_STRONG_INLIERS:
            return "world", None
        return None, "zero flow contradicted by a world rotation among the centre outliers"
    if (step.centre_inliers is not None and step.centre_inliers >= CENTRE_STRONG_INLIERS
            and step.centre_consistency >= CENTRE_STRONG_SHARE and step.centre_rot_deg >= CENTRE_STILL_DEG):
        return "centre", None
    if step.border_frac is not None and step.border_frac >= PAIR_BORDER_FRAC:
        if ((step.centre_matches or 0) >= BORDER_OVERRIDE_MATCHES and step.centre_flow is not None
                and step.centre_flow <= BORDER_OVERRIDE_PX):
            return "main", None
        return None, "zero flow on border features only"
    if step.centre_matches is None or step.centre_matches < MIN_CENTRE_MATCHES:
        return None, "zero flow unconfirmed: too few centre matches"
    if (step.centre_rot_deg is None or step.centre_rot_deg >= CENTRE_STILL_DEG
            or step.centre_inliers is None or step.centre_inliers < MIN_CENTRE_MATCHES):
        return None, "zero flow contradicted by the centre's own matches"
    return "main", None


def pair_abstain(step):
    """Why a fitted pair's rotation must be withheld, or None (kept, or reported from the centre)."""
    return pair_decision(step)[1]


def centre_strips(pts, shape):
    """Mask of points inside STATIC_CENTRE and outside the body's columns."""
    h, w = shape[:2]
    x0, y0, x1, y1 = STATIC_CENTRE
    bx0, _, bx1, _ = BODY_MASK[0]
    x, y = pts[:, 0] / w, pts[:, 1] / h
    return (x >= x0) & (x < x1) & (y >= y0) & (y < y1) & ~((x >= bx0) & (x < bx1))


def _centre_world(grey):
    """The centre region (never overlay), body excluded, subsampled by 4."""
    h, w = grey.shape
    x0, y0, x1, y1 = STATIC_CENTRE
    c = grey[int(y0 * h):int(y1 * h):4, int(x0 * w):int(x1 * w):4].astype(np.int16)
    bx0, _, bx1, _ = BODY_MASK[0]
    keep = np.ones(c.shape[1], bool)
    keep[max(0, int((bx0 - x0) * w) // 4):int((bx1 - x0) * w) // 4] = False
    return c[:, keep]


def mask_for(shape, extra=(), dets=(), det_scale=1.0, base=None):
    """uint8 mask, 255 where features may be taken."""
    import cv2

    h, w = shape[:2]
    m = base.copy() if base is not None else np.full((h, w), 255, np.uint8)
    for x0, y0, x1, y1 in (*HUD_MASK, *BODY_MASK, *extra):
        cv2.rectangle(m, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), 0, -1)
    for x0, y0, x1, y1 in dets:           # moving enemies, in some other pixel scale
        pad = 0.15 * (x1 - x0)
        cv2.rectangle(m, (int((x0 - pad) * det_scale), int((y0 - pad) * det_scale)),
                      (int((x1 + pad) * det_scale), int((y1 + pad) * det_scale)), 0, -1)
    return m


def rays(pts, shape, focal):
    """Pixels to unit rays, OpenCV camera axes (x right, y down, z forward)."""
    h, w = shape[:2]
    v = np.column_stack([(pts[:, 0] - w / 2) / focal, (pts[:, 1] - h / 2) / focal,
                         np.ones(len(pts))])
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def kabsch(a, b):
    """Rotation R minimising |R a_i - b_i| over unit rays."""
    u, _, vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    return vt.T @ np.diag([1.0, 1.0, d]) @ u.T


def rotvec(r):
    """Axis-angle vector (radians) of a rotation matrix."""
    angle = np.arccos(np.clip((np.trace(r) - 1) / 2, -1.0, 1.0))
    if angle < 1e-9:
        return np.zeros(3)
    axis = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / (2 * np.sin(angle))
    return axis * angle


def fit_rotation(p0, p1, shape, focal, rng=None):
    """(R, inlier mask) mapping frame-0 rays onto frame-1 rays, or (None, None)."""
    if len(p0) < MIN_INLIERS:
        return None, None
    rng = rng or np.random.default_rng(0)
    a, b = rays(p0, shape, focal), rays(p1, shape, focal)
    tol = INLIER_PX / focal                 # angular tolerance, radians
    best = None
    for _ in range(RANSAC_ITERS):
        i = rng.choice(len(a), 2, replace=False)
        if np.linalg.norm(np.cross(a[i[0]], a[i[1]])) < 1e-3:
            continue                          # degenerate pair
        r = kabsch(a[i], b[i])
        inl = np.linalg.norm(a @ r.T - b, axis=1) < tol
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < MIN_INLIERS:
        return None, None
    r = kabsch(a[best], b[best])
    inl = np.linalg.norm(a @ r.T - b, axis=1) < tol
    return kabsch(a[inl], b[inl]), inl


def camera_angles(r):
    """(yaw, pitch, roll) in degrees for the camera's own turn, from R.

    R maps a world ray's direction in the old camera to the new one, so the
    camera itself turned by the inverse. Yaw right and pitch up are positive.
    The game camera has no roll: a fitted roll is world yaw seen from a pitched
    camera, so world yaw is the signed length of the yaw-and-roll component.
    """
    w = -np.degrees(rotvec(r))               # the camera's rotation, camera axes
    # With y down and z forward, a positive turn about +y swings z toward +x (a
    # right turn) and a positive turn about +x swings z toward -y (looking up).
    pitch = w[0]
    yaw_cam, roll = w[1], w[2]
    yaw = np.sign(yaw_cam) * np.hypot(yaw_cam, roll) if abs(yaw_cam) > 1e-9 else 0.0
    return float(yaw), float(pitch), float(roll)


# --- focal length from the footage itself (IDM measurement M2) -----------------
# Whether the replay viewer renders at the same field of view as live play. The
# calibrated focal (Cal.focal_1280) was pinned by timing a 360 degree turn,
# because solving it from pixel shifts alone was ill-conditioned (590-860). So
# this fit is only trusted on the replay after it recovers that known focal on
# James's own live footage (`replay_focal`), and it always reports how sharp its
# minimum is: a wide basin means the footage cannot tell focal lengths apart.
# On real footage it has not yet been conditioned: the 2026-09-23 live gate
# refused at 515 px with a 427-637 px basin. The viewer-FOV re-record is M2's test.
FOCAL_GRID = np.arange(300.0, 900.1, 2.5)   # px at 1280 wide
FOCAL_COARSE = (350.0, 465.0, 600.0, 800.0)  # where each pair's outliers are decided
FOCAL_TOL = 0.05          # the live fit must land this close to the calibrated focal
FOCAL_BASIN = 0.05        # and every focal within 5 % of its minimum residual this close to it
FOCAL_RISE = 0.05         # a focal is "in the basin" while its residual is within 5 % of the minimum
MIN_FOCAL_PAIRS = 20


def _reprojection_rms(p0, p1, shape, focal):
    """RMS pixel error of the best pure rotation mapping p0 onto p1 at this focal."""
    a, b = rays(p0, shape, focal), rays(p1, shape, focal)
    q = a @ kabsch(a, b).T
    h, w = shape[:2]
    px = np.column_stack([focal * q[:, 0] / q[:, 2] + w / 2, focal * q[:, 1] / q[:, 2] + h / 2])
    return float(np.sqrt(((px - p1) ** 2).sum(axis=1).mean()))


def focal_fit(pairs, shape, grid=FOCAL_GRID):
    """The focal length under which a set of frame pairs are best explained as pure rotations.

    `pairs` are (p0, p1) matched pixel arrays in frames of `shape`, and `grid`
    is in pixels at that width. Each pair's outliers (moving players, parallax)
    are decided once, by the widest RANSAC consensus over FOCAL_COARSE, so every
    focal is scored on the same points. Returns focal, basin (lowest and highest
    grid focal within FOCAL_RISE of the minimum), basin_frac (its width over the
    focal) and the number of pairs used.
    """
    used = []
    for p0, p1 in pairs:
        best = None
        for f in FOCAL_COARSE:
            _, inl = fit_rotation(p0, p1, shape, f * shape[1] / 1280.0)
            if inl is not None and (best is None or inl.sum() > best.sum()):
                best = inl
        if best is not None and best.sum() >= MIN_INLIERS:
            used.append((p0[best], p1[best]))
    if not used:
        return {"focal": None, "basin": None, "basin_frac": None, "pairs": 0}
    scale = shape[1] / 1280.0
    res = np.array([sum(_reprojection_rms(a, b, shape, f * scale) for a, b in used) for f in grid])
    i = int(res.argmin())
    inside = grid[res <= res[i] * (1 + FOCAL_RISE)]
    return {"focal": float(grid[i]), "basin": (float(inside.min()), float(inside.max())),
            "basin_frac": round(float(inside.max() - inside.min()) / float(grid[i]), 3), "pairs": len(used)}


def replay_focal(live_pairs, replay_pairs, shape, known=None):
    """M2 with its gate: fit the replay only if the same fit recovers the known focal live.

    Refused (replay None) when the live fit is under MIN_FOCAL_PAIRS, misses the
    calibrated focal by more than FOCAL_TOL, or has a basin wider than FOCAL_BASIN.
    The replay fit reports its own basin; a wide one is an unknown FOV, not a value.
    """
    known = known or CAL.focal_1280
    live = focal_fit(live_pairs, shape)
    reason = None
    if live["pairs"] < MIN_FOCAL_PAIRS:
        reason = f"only {live['pairs']} usable live pairs"
    elif abs(live["focal"] - known) / known > FOCAL_TOL:
        reason = f"live fit {live['focal']:.1f} px misses the calibrated {known:.1f} px"
    elif live["basin_frac"] > FOCAL_BASIN:
        reason = f"live basin {live['basin']} is too wide to tell focal lengths apart"
    gate = {"known": known, "live": live, "passed": reason is None, "reason": reason}
    if reason:
        return {"gate": gate, "replay": None}
    rep = focal_fit(replay_pairs, shape)
    rep["conditioned"] = (rep["pairs"] >= MIN_FOCAL_PAIRS and rep["basin_frac"] is not None
                          and rep["basin_frac"] <= FOCAL_BASIN)
    return {"gate": gate, "replay": rep}


class Estimator:
    """Frame-to-frame rotation over a stream of frames."""

    def __init__(self, width, extra_mask=(), nfeatures=1500, overlay=None):
        import cv2

        self.cv2 = cv2
        self.orb = cv2.ORB_create(nfeatures=nfeatures, fastThreshold=10)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        self.extra = extra_mask
        self.overlay = overlay                  # static_mask() for this source, if learned
        self.focal = focal_for(width)
        self.prev = None
        self.prev_world = None
        self.prev_g = None
        self.last_matches = None                # (p0, p1) ratio-tested matches of the last pair, for focal_fit
        self.rng = np.random.default_rng(0)

    def features(self, frame, dets=(), det_scale=1.0):
        g = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        base = self.overlay if self.overlay is not None and self.overlay.shape == g.shape else None
        m = mask_for(g.shape, self.extra, dets, det_scale, base)
        kp, des = self.orb.detectAndCompute(g, m)
        pts = np.float32([k.pt for k in kp]) if kp else np.zeros((0, 2), np.float32)
        return g.shape, pts, des

    def step(self, frame, t, dets=(), det_scale=1.0):
        """Feed the next frame; returns the Step from the previous one, or None.

        A fitted pair that `pair_decision` rejects comes back with its rotation
        withheld and the reason in `abstain`, never as a zero rotation; one whose
        zero the centre fit strongly contradicts reports the centre rotation,
        with `source` = "centre".
        """
        g = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        world = _centre_world(g)
        cur = (t, *self.features(g, dets, det_scale))
        prev, self.prev = self.prev, cur
        prev_world, self.prev_world = self.prev_world, world
        prev_g, self.prev_g = self.prev_g, g.astype(np.int16)
        if prev is None:
            return None
        s = self.compare(prev, cur)
        s.world_diff = float(np.abs(world - prev_world).mean())
        d = np.abs(g.astype(np.int16) - prev_g).astype(np.float32)
        s.frame_diff = float(d.mean())
        s.block_diff = float(self.cv2.resize(d, (max(1, d.shape[1] // 16), max(1, d.shape[0] // 16)),
                                             interpolation=self.cv2.INTER_AREA).max())
        use, why = pair_decision(s)
        if use == "centre":
            return replace(s, yaw_deg=s.centre_yaw_deg, pitch_deg=s.centre_pitch_deg, roll_deg=None, source="centre")
        if use == "world":
            return replace(s, yaw_deg=s.world_yaw_deg, pitch_deg=s.world_pitch_deg, roll_deg=None, source="centre")
        return replace(s, yaw_deg=None, pitch_deg=None, roll_deg=None, abstain=why) if why else s

    def compare(self, a, b):
        self.last_matches = None            # never the previous pair's (review C4)
        (t0, shape, p0, d0), (t1, _, p1, d1) = a, b
        none = Step(t0, t1, 0, 0, None, None, None, None)
        if d0 is None or d1 is None or len(p0) < 2 or len(p1) < 2:
            return none
        pairs = self.matcher.knnMatch(d0, d1, k=2)
        # Lowe's ratio test. It is the defence against repeating wall panels: a
        # feature on a periodic texture has a second match nearly as good as its
        # first, and is dropped rather than voting for a one-panel-off shift.
        good = [m for m, *rest in (p for p in pairs if p)
                if not rest or m.distance < 0.75 * rest[0].distance]
        if len(good) < MIN_INLIERS:
            return Step(t0, t1, len(good), 0, None, None, None, None)
        q0 = p0[[m.queryIdx for m in good]]
        q1 = p1[[m.trainIdx for m in good]]
        self.last_matches = (q0, q1)
        r, inl = fit_rotation(q0, q1, shape, self.focal, self.rng)
        if r is None or inl.mean() < MIN_INLIER_FRAC:
            return Step(t0, t1, len(good), 0 if inl is None else int(inl.sum()),
                        None, None, None, None)
        yaw, pitch, roll = camera_angles(r)
        flow = float(np.median(np.linalg.norm(q1[inl] - q0[inl], axis=1)))
        h, w = shape[:2]
        x0, y0, x1, y1 = STATIC_CENTRE
        pts = q1[inl]
        inside = ((pts[:, 0] >= x0 * w) & (pts[:, 0] < x1 * w) & (pts[:, 1] >= y0 * h) & (pts[:, 1] < y1 * h))
        centre = centre_strips(q0, shape) & centre_strips(q1, shape)
        centre_flow = (float(np.median(np.linalg.norm(q1[centre] - q0[centre], axis=1)))
                       if centre.any() else None)
        centre_rot = centre_inl = centre_cons = centre_yaw = centre_pitch = None
        world_rot = world_inl = world_yaw = world_pitch = None
        if flow <= ZERO_FLOW_PX and centre.sum() >= MIN_CENTRE_MATCHES:
            # Its own generator, so the main fit's random sequence is untouched.
            rc, ic = fit_rotation(q0[centre], q1[centre], shape, self.focal, np.random.default_rng(1))
            if rc is not None:
                centre_rot = float(np.degrees(np.linalg.norm(rotvec(rc))))
                centre_inl = int(ic.sum())
                centre_cons = float(ic.mean())
                centre_yaw, centre_pitch, _ = camera_angles(rc)
                world = self._world_rotation(q0[centre][~ic], q1[centre][~ic], shape)
                if world is not None:
                    world_rot, world_inl, world_yaw, world_pitch = world
        return Step(t0, t1, len(good), int(inl.sum()), flow, yaw, pitch, roll,
                    border_frac=round(float(1 - inside.mean()), 3),
                    centre_matches=int(centre.sum()), centre_flow=centre_flow,
                    centre_rot_deg=centre_rot, centre_inliers=centre_inl, centre_consistency=centre_cons,
                    centre_yaw_deg=centre_yaw, centre_pitch_deg=centre_pitch,
                    world_rot_deg=world_rot, world_inliers=world_inl,
                    world_yaw_deg=world_yaw, world_pitch_deg=world_pitch)

    def _world_rotation(self, a, b, shape):
        """(deg, inliers, yaw, pitch) when the centre fit's outliers form one rotation of
        at least CENTRE_STILL_DEG with WORLD_MIN_INLIERS inliers, WORLD_MIN_PER_SIDE on
        each side strip; else None. Its own generator, like the centre fit."""
        if len(a) < WORLD_MIN_INLIERS:
            return None
        r, inl = fit_rotation(a, b, shape, self.focal, np.random.default_rng(2))
        if r is None or inl.sum() < WORLD_MIN_INLIERS:
            return None
        deg = float(np.degrees(np.linalg.norm(rotvec(r))))
        mid = shape[1] / 2
        if deg < CENTRE_STILL_DEG or min((a[inl, 0] < mid).sum(), (a[inl, 0] >= mid).sum()) < WORLD_MIN_PER_SIDE:
            return None
        yaw, pitch, _ = camera_angles(r)
        return deg, int(inl.sum()), yaw, pitch


# --- the command side --------------------------------------------------------

def map_rate(stick, table):
    """Calibrated turn rate (deg/s, signed) for a stick deflection."""
    return float(np.sign(stick) * _interp(abs(stick), table))


def inverse_map(rate, table):
    """The stick deflection the calibration says gives this rate (signed)."""
    mag = abs(rate)
    for (s0, r0), (s1, r1) in zip(table, table[1:]):
        if mag <= r1:
            return float(np.sign(rate) * (s0 + (s1 - s0) * (mag - r0) / (r1 - r0)))
    return float(np.sign(rate) * table[-1][0])      # saturated: the most a stick can say


class Pad(list):
    """A run's ticks, (t, rx, ry, lx, ly, buttons[, lt, rt]), time index built once.

    The triggers are logged apart from `buttons`: rt is melee, lt Web Cluster.
    Missing them once filed whole melee combos under ordinary turns.
    """

    def __init__(self, ticks):
        super().__init__(ticks)
        self.t = np.array([p[0] for p in self])
        self.pressed = np.array([bool(p[5]) for p in self])
        self.attack = np.array([len(p) > 7 and bool(p[6] or p[7]) for p in self])


def load_pad(frames_jsonl):
    """Pad for every tick of a run log."""
    out = []
    for line in Path(frames_jsonl).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            p = r["pad"]
            out.append((float(r["t"]), float(p["rx"]), float(p["ry"]), float(p["lx"]),
                        float(p["ly"]), tuple(p.get("buttons") or ()),
                        float(p.get("lt") or 0), float(p.get("rt") or 0)))
    return Pad(out)


def commanded(pad, t0, t1, lag):
    """What the pad commanded over [t0 - lag, t1 - lag]: time-weighted.

    Returns mean rx, mean ry, the map-predicted yaw and pitch (degrees over the
    interval, integrated tick by tick), the spread of rx, and whether anything
    else was going on (movement, a button) that can move the camera by itself.
    """
    a, b = t0 - lag, t1 - lag
    pad = pad if isinstance(pad, Pad) else Pad(pad)
    # Ticks hold their value until the next one.
    idx = max(0, int(np.searchsorted(pad.t, a, "right")) - 1)
    yaw = pitch = srx = sry = 0.0
    rxs, moving, pressed = [], False, False
    cur = a
    while cur < b and idx < len(pad):
        nxt = min(b, pad[idx + 1][0] if idx + 1 < len(pad) else b)
        dt = max(0.0, nxt - cur)
        _, rx, ry, lx, ly, btn = pad[idx][:6]
        yaw += map_rate(rx, CAL.yaw_map) * dt
        pitch += map_rate(ry, CAL.pitch_map) * dt
        srx += rx * dt
        sry += ry * dt
        rxs.append(rx)
        moving |= bool(lx or ly)
        pressed |= bool(btn)
        cur, idx = nxt, idx + 1
    span = max(b - a, 1e-9)
    return {"rx": srx / span, "ry": sry / span, "map_yaw_deg": yaw, "map_pitch_deg": pitch,
            "rx_spread": float(np.ptp(rxs)) if rxs else 0.0, "moving": moving, "pressed": pressed}


# --- drivers -----------------------------------------------------------------

def _sample(video, n=60, width=None, start=None, duration=None):
    """n frames spread evenly over a video (or a window of it), for static_mask."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    first = int((start or 0) * fps)
    last = min(total, first + int(duration * fps)) if duration else total
    out = []
    for k in np.linspace(first, max(first, last - 1), n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(k))
        ok, f = cap.read()
        if ok:
            if width and f.shape[1] != width:
                f = cv2.resize(f, (width, round(f.shape[0] * width / f.shape[1])),
                               interpolation=cv2.INTER_AREA)
            out.append(f)
    cap.release()
    return out


def run_proxy(run_dir, out=None, progress=500):
    """Every consecutive proxy pair of a logged run, with the log alongside.

    A run's proxy-720p.mp4 holds one video frame per saved image, in order, so
    video frame k is the log row whose `file` is image k -- the alignment is by
    construction, and each frame's time is its log time.
    """
    import cv2

    run_dir = Path(run_dir)
    rows = [json.loads(l) for l in (run_dir / "frames.jsonl").read_text().splitlines() if l.strip()]
    saved = [r for r in rows if r.get("file")]
    overlay = static_mask(_sample(run_dir / "proxy-720p.mp4"))
    cap = cv2.VideoCapture(str(run_dir / "proxy-720p.mp4"))
    est, steps = None, []
    for k, row in enumerate(saved):
        ok, frame = cap.read()
        if not ok:
            break
        if est is None:
            est = Estimator(frame.shape[1], overlay=overlay)
        # Enemy boxes in the log are native pixels; the proxy is 1280 wide.
        s = est.step(frame, float(row["t"]), row.get("dets") or (), frame.shape[1] / 2560.0)
        if s is not None:
            steps.append(s)
        if progress and k % progress == 0:
            print(f"  {run_dir.name} {k}/{len(saved)}", file=sys.stderr)
    cap.release()
    if out:
        write(steps, out, {"run": run_dir.name, "source": "proxy-720p.mp4",
                           "focal": est.focal if est else None})
    return steps


def run_video(video, out=None, hz=None, start=None, duration=None, extra_mask=(),
              t_offset=0.0, width=1280, progress=1000, spectator_mask=False):
    """Every consecutive pair of a video, at its native rate or every Nth frame.

    Frames are downscaled to `width` first, which the focal length follows.
    `t_offset` is subtracted from video time, to put a recording on its log's clock.
    `spectator_mask` adds the replay viewer's spectator-UI rects (REPLAY_UI_MASK).
    Apply it identically to replay and live footage whenever the two are compared,
    so both domains lose the same pixels. Each pair's zero is confirmed or
    withheld by `pair_abstain`, and the verdict (`checked_windows`) runs over fixed
    WINDOW_S sub-windows: a sub-window that is mostly unconfirmed zeros has its
    rotations withheld, and the meta line lists every sub-window's verdict.
    """
    import cv2

    if spectator_mask:
        extra_mask = (*REPLAY_UI_MASK, *extra_mask)
    overlay = static_mask(_sample(video, width=width, start=start, duration=duration))
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    if start:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    step_n = max(1, round(fps / hz)) if hz else 1
    est, steps, n = None, [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if duration and start is not None and t > start + duration:
            break
        if n % step_n == 0:
            if frame.shape[1] != width:
                frame = cv2.resize(frame, (width, round(frame.shape[0] * width / frame.shape[1])),
                                   interpolation=cv2.INTER_AREA)
            if est is None:
                est = Estimator(width, extra_mask, overlay=overlay)
            s = est.step(frame, t - t_offset)
            if s is not None:
                steps.append(s)
        n += 1
        if progress and n % progress == 0:
            print(f"  {Path(video).name} {n} frames", file=sys.stderr)
    cap.release()
    steps, verdicts = checked_windows(steps)
    if out:
        write(steps, out, {"video": str(video), "hz": hz or fps, "start": start,
                           "duration": duration, "width": width, "spectator_mask": spectator_mask,
                           "focal": est.focal if est else None, "t_offset": t_offset,
                           "window_s": WINDOW_S, "verdicts": verdicts})
    return steps


# --- evaluation against the pad log ------------------------------------------

BANDS = (("zero", 0.0, 0.03), ("low", 0.03, 0.2), ("mid", 0.2, 0.5), ("high", 0.5, 1.01))
ABILITY_WINDOW = 0.5      # seconds after a press in which the camera may move by itself


def stratum(c, pad, t0, t1, lag):
    """What else could be moving the camera over this interval.

    ability  a button was pressed in the half second before: pull and web
             strike drag the player, and the camera with him
    attack   a trigger was held in that window: melee (rt) or Web Cluster (lt).
             A melee combo holds the camera nearly still against the stick
    moving   the left stick was deflected: translation and parallax
    mixed    the right stick changed within the interval
    turn     a steady right-stick command and nothing else
    still    no command at all
    """
    lo, hi = np.searchsorted(pad.t, [t0 - lag - ABILITY_WINDOW, t1 - lag], "left")
    if pad.pressed[lo:hi + 1].any():
        return "ability"
    if pad.attack[lo:hi + 1].any():
        return "attack"
    if c["moving"]:
        return "moving"
    if c["rx_spread"] > 0.05:
        return "mixed"
    return "turn" if abs(c["rx"]) >= 0.03 or abs(c["ry"]) >= 0.03 else "still"


def pair(steps, pad, lag):
    """One row per interval: observed, estimated, map-predicted, inferred, commanded.

    Abstained intervals are kept (estimate None) so coverage can be counted.
    """
    pad = pad if isinstance(pad, Pad) else Pad(pad)
    rows = []
    for s in steps:
        dt = s.t1 - s.t0
        if dt <= 0:
            continue
        c = commanded(pad, s.t0, s.t1, lag)
        est = s.yaw_rate
        rows.append({
            "t0": s.t0, "dt": dt, "stratum": stratum(c, pad, s.t0, s.t1, lag),
            "observed_px_s": None if s.flow_px is None else s.flow_px / dt,
            "est_yaw": est, "est_pitch": s.pitch_rate,
            "map_yaw": c["map_yaw_deg"] / dt, "map_pitch": c["map_pitch_deg"] / dt,
            "inferred_rx": None if est is None else inverse_map(est, CAL.yaw_map),
            "cmd_rx": c["rx"], "cmd_ry": c["ry"],
        })
    return rows


def fit_lag(rows_by_lag, grid):
    """The lag minimising median |estimated - map-predicted| yaw rate on clean turns.

    Only 'turn' and 'still' intervals vote: an ability or movement moves the
    camera without a stick command, which is not what latency is about.
    """
    best, best_err = None, np.inf
    for lag in grid:
        errs = [abs(r["est_yaw"] - r["map_yaw"]) for r in rows_by_lag(lag)
                if r["est_yaw"] is not None and r["stratum"] in ("turn", "still")]
        err = float(np.median(errs)) if errs else np.inf
        if err < best_err:
            best, best_err = lag, err
    return best, best_err


def _block_ci(rows, stat, block_s=10.0, n=400, seed=0):
    """95% interval of stat(rows) by resampling contiguous time blocks, so that
    correlated neighbouring frames are not counted as independent evidence."""
    if not rows:
        return None
    t0 = rows[0]["t0"]
    blocks = {}
    for r in rows:
        blocks.setdefault(int((r["t0"] - t0) // block_s), []).append(r)
    keys = list(blocks)
    if len(keys) < 3:
        return None
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = [r for k in rng.choice(keys, len(keys)) for r in blocks[k]]
        v = stat(pick)
        if v is not None and np.isfinite(v):
            vals.append(v)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if vals else None


def _mae(pairs):
    return float(np.mean([abs(a - b) for a, b in pairs])) if pairs else None


def summarise(rows):
    """The tables: coverage, rotation agreement, command reconstruction, baselines.

    Rotation level compares the ESTIMATE with the MAP'S PREDICTION from the
    commanded stick -- agreement between two models, not accuracy against truth.
    Command level compares the INFERRED stick with the COMMANDED one, which is
    truth about what was commanded. Neutral predicts zero in both.
    """
    fitted = [r for r in rows if r["est_yaw"] is not None]
    rot = [(r["est_yaw"], r["map_yaw"]) for r in fitted]
    cmd = [(r["inferred_rx"], r["cmd_rx"]) for r in fitted]
    turning = [r for r in fitted if abs(r["cmd_rx"]) >= 0.03]
    direction = [np.sign(r["inferred_rx"]) == np.sign(r["cmd_rx"]) for r in turning]
    out = {
        "n": len(rows), "coverage": round(len(fitted) / len(rows), 3) if rows else None,
        "observed_px_s_median": (float(np.median([r["observed_px_s"] for r in fitted]))
                                 if fitted else None),
        # rotation: estimated vs calibrated-map prediction (deg/s)
        "rot_mae": _mae(rot), "rot_mae_neutral": _mae([(0.0, m) for _, m in rot]),
        "rot_r": (float(np.corrcoef(*zip(*rot))[0, 1])
                  if len(rot) > 2 and np.std([a for a, _ in rot]) > 0
                  and np.std([b for _, b in rot]) > 0 else None),
        # command: inferred stick vs commanded stick (stick units)
        "cmd_mae": _mae(cmd), "cmd_mae_neutral": _mae([(0.0, c) for _, c in cmd]),
        "direction_acc": float(np.mean(direction)) if direction else None,
        "direction_n": len(direction),
    }
    out["cmd_mae_ci"] = _block_ci(fitted, lambda rs: _mae([(r["inferred_rx"], r["cmd_rx"]) for r in rs]))
    out["rot_mae_ci"] = _block_ci(fitted, lambda rs: _mae([(r["est_yaw"], r["map_yaw"]) for r in rs]))
    return out


def band_of(rx):
    a = abs(rx)
    return next(name for name, lo, hi in BANDS if lo <= a < hi)


def _thumbs(video, size=(160, 90)):
    """Every frame of a video as a small grey thumbnail, with its time."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    times, thumbs = [], []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        times.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
        thumbs.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), size,
                                 interpolation=cv2.INTER_AREA).astype(np.float32))
    cap.release()
    return np.array(times), np.stack(thumbs)


def align_clock(video, frames, samples=25):
    """Offset (video seconds minus log seconds) that puts a recording on its log.

    Decided by image identity, never by motion: each sampled saved frame is found
    in the recording by nearest thumbnail, and the offsets are compared. Using
    motion would fold the very latency being measured into the alignment.
    `frames` is [(log_t, image)]. Returns (median offset, spread of the
    agreeing samples, how many agreed).
    """
    import cv2

    times, thumbs = _thumbs(video)
    flat = thumbs.reshape(len(thumbs), -1)
    offsets = []
    for t, img in frames[:: max(1, len(frames) // samples)]:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        q = cv2.resize(g, thumbs.shape[1:][::-1], interpolation=cv2.INTER_AREA).astype(np.float32)
        err = ((flat - q.ravel()) ** 2).mean(axis=1)
        best = int(np.argmin(err))
        # A frame that matches several places equally (a static view) says nothing.
        runner = np.partition(err, 30)[30] if len(err) > 31 else np.inf
        if err[best] < 0.5 * runner:
            offsets.append(times[best] - t)
    if not offsets:
        return None, None, 0
    offsets = np.array(offsets)
    med = float(np.median(offsets))
    agree = offsets[np.abs(offsets - med) < 0.05]
    return med, float(np.ptp(agree)) if len(agree) else None, int(len(agree))


def write(steps, out, meta):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        fh.write(json.dumps({"type": "meta", **meta}) + "\n")
        for s in steps:
            fh.write(json.dumps(asdict(s)) + "\n")


def read(path):
    lines = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    return lines[0], [Step(**{k: v for k, v in l.items()}) for l in lines[1:]]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("proxy")
    a.add_argument("run_dir")
    a.add_argument("out")
    b = sub.add_parser("video")
    b.add_argument("video")
    b.add_argument("out")
    b.add_argument("--hz", type=float)
    b.add_argument("--start", type=float)
    b.add_argument("--duration", type=float)
    b.add_argument("--t-offset", type=float, default=0.0)
    b.add_argument("--width", type=int, default=1280)
    b.add_argument("--mask", action="append", default=[],
                   help="extra masked box as x0,y0,x1,y1 frame fractions (overlays)")
    b.add_argument("--spectator-mask", action="store_true",
                   help="mask the replay viewer's spectator-UI rects; use on replay and live alike")
    args = p.parse_args(argv)
    if args.cmd == "proxy":
        steps = run_proxy(args.run_dir, args.out)
    else:
        extra = tuple(tuple(float(v) for v in m.split(",")) for m in args.mask)
        steps = run_video(args.video, args.out, args.hz, args.start, args.duration, extra,
                          args.t_offset, args.width, spectator_mask=args.spectator_mask)
    ok = [s for s in steps if s.yaw_deg is not None]
    withheld = [s for s in steps if s.abstain]
    # "coverage" is rotations reported over all pairs; withheld pairs (fitted, then
    # refused by pair_abstain or a window verdict) are counted apart from failed fits.
    print(json.dumps({"pairs": len(steps), "reported": len(ok), "withheld": len(withheld),
                      "coverage": round(len(ok) / max(1, len(steps)), 3)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
