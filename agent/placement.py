"""Placement between range trials: home on the courtyard Galacta pair from finder boxes (docs/lanes/placement.md).

Pure and stdlib-only: no capture, pad or perception import. A driver (`scripts/place.py`) grabs native frames, runs
the loop's own readers (`agent.loop.default_perception`: `in_range`, the whole-frame finder `wide`), passes the boxes
here, and executes the returned action through `agent.controller.Live`. Nothing here sends input.

`classify` names one frame: PAIR (the two courtyard bots with the measured on-lane signature, on the lane's level, with
a pose), TWO (the pair with a consistent pose but not the signature), UNLEVELLED (a pair-like view while the camera
pitch is not at the reference: the answer is PITCH_RESET, never a move), NEAR_ONE (point blank to one bot), LOST, or
NOT_IN_RANGE.

The pose (review F1) is a feasible set: every position consistent with the two pixel-exact bearings, the known 5.17 m
spacing, ONE range from the mean box height with a bounded scale error, and a per-box height ratio within a measured
bound of its prediction. A frame no pose fits is rejected. The side of the lane is known only when every feasible pose
agrees; every move must be safe for every feasible pose, and no predicted end may lie beyond DROP_MARGIN_M on the drop
side (+x) unless it is closer to the axis than its start.

`plan`: PITCH_RESET, TURN, STRAFE, WALK (at most PULSE_S), READY or HAND_BACK. It moves only with a pose and never
jumps. Every call counts against MAX_STEPS (review F5). Near placement is refused until the lane's edge has been
measured (review F4).

IN-SAMPLE: every threshold below was set on the same labelled frames it is tested on (tests/fixtures/placement/).
A held-out check on the supervised-look frames and James's next sessions must pass before this gates live input.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

# --- Camera and bots -----------------------------------------------------------------------------------------------
REF_H = 1440                    # boxes are compared in 1440-row pixels whatever the frame size
CENTRE_X = 1280                 # screen centre in 2560-wide pixels
FOCAL_PX = 930.0                # 465 px at 1280 wide (agent.controller.Cal.focal_1280), scaled to 2560
H_TIMES_DISTANCE_M = 0.96       # h * metres to a bot: .0385 at the 25 m marks
PAIR_SPACING_M = 5.17           # bot to bot: median over 60 labelled pairs (p10-p90 4.67-5.57)

# --- Signature (IN-SAMPLE) -----------------------------------------------------------------------------------------
GALACTA_ASPECT = (0.70, 1.40)   # w/h of a Galacta box at far/mid (measured 0.80-1.12); a lane sliver is 0.23
PAIR_SEP_PER_H = (3.3, 4.7)     # (cx_right - cx_left) / mean box height: labelled on-lane pairs 3.38-4.64
PAIR_MAX_DY = 40                # |y1_left - y1_right| in 1440-row px (on-lane max 35)
PAIR_MAX_DH = 0.25              # |h_left - h_right| / max(h) (on-lane max 0.224)

# --- Level at the reference pitch (review F2, F3; PROVISIONAL, IN-SAMPLE) --------------------------------------------
# On one level and at a fixed pitch a box's bottom row is linear in its height: y2 = horizon + slope * h. Fitted on 32
# boxes of the low-pitch cluster of labelled pairs; the cluster's other 32 boxes, held out, stay within -25..+40 px.
# The high-pitch cluster sits 87-205 px off, the lower-plaza views of the pair and the review's x1.9 plaza pair about
# 200 px off. The reference pitch must be reproduced by PITCH_RESET, whose stick durations are UNMEASURED: the check
# only guarantees for a pitch error under ~150 px (~9 degrees).
LEVEL_Y2_AT_ZERO_H = 495.9
LEVEL_SLOPE = 1.073
LEVEL_RESIDUAL_PX = (-40.0, 50.0)

# --- Pose (review F1; IN-SAMPLE) -----------------------------------------------------------------------------------
# The pose is a FEASIBLE SET, not a point: every (x, y) consistent with the exact bearings, a range-scale error within
# +-RANGE_SCALE_ERR, and a per-box height ratio within +-RANGE_LOG_BOUND of its geometric prediction. Near the axis the
# subtended angle barely depends on x, so the angle alone cannot bound |x| (a 5% scale error reads as ~0.3*d of offset);
# the height ratio alone cannot survive a differential box bias. Together they bound it.
RANGE_LOG_BOUND = 0.21          # accept a frame when its best pose fits the height ratio this well (clean labelled <= 0.21)
BIAS_LOG_MAX = math.log(1.25 / 0.75)   # keep every pose within this for safety: the review's +-25% differential bias
RANGE_SCALE_ERR = 0.10          # at the reference pitch; UNMEASURED (labelled frames of mixed pitch show up to 0.23)
SCALE_STEPS = 7                 # grid over the scale error
MIN_PAIR_RANGE_M = 2.9          # closer than this the pair geometry is not used (the pair is 5.17 m wide)

# --- Lane (UNVERIFIED until the supervised look) ---------------------------------------------------------------------
DROP_MARGIN_M = 2.0             # no predicted end beyond this on the drop side (+x) unless it moves toward the axis ...
DROP_ZONE_Y_M = -10.0           # ... within this far of the bots: the unrailed stretch; farther out the right side is
                                # railed (pilot frames). UNVERIFIED: the look measures where the rail ends
LANE_X_M = 3.5                  # the central |x| accepted as "on the lane"; UNVERIFIED lane extent
LANE_Y_M = (-30.0, -1.0)
EDGE_X_M = None                 # the measured drop edge; None refuses near placement (review F4)
NEAR_EDGE_CLEARANCE_M = 1.5     # near stand ceiling: EDGE_X_M - this
NEAR_STRAFE_S = 0.15            # near approach strafe pulse, each with a fresh pose

# --- Point blank ---------------------------------------------------------------------------------------------------
NEAR_MIN_H = 0.25               # one box this tall is point blank (slot starts .33-.34; a KO end .45)
NEAR_ASPECT = (0.50, 1.40)      # a point-blank box seen from the side narrows to ~0.58
NEAR_CX = (640, 1920)           # its centre within the middle three quarters of the frame

FRAMES_PER_DECISION = 3
FRAMES_TO_AGREE = 2             # review F6: a pose must be seen on 2 of 3 frames

BINS = {                        # target band on the designated (right) bot's h = box height / frame height
    "far": (0.033, 0.047),      # the lane's 25 m end: .0385 measured
    "mid": (0.085, 0.110),      # slot 3 start .092; agent.brain.RANGES mid is .065-.325
    "near": (0.330, 0.370),     # slot 1 start .342; near is >= .325
}
LATERAL_OK_M = 2.0              # far/mid starts need the central |x| within this

# --- Motion ----------------------------------------------------------------------------------------------------------
WALK_M_PER_S = 3.75             # 25 m end -> mid in ~3.7 s and 15 m -> near in ~3.9 s of forward stick
STRAFE_M_PER_S = 3.75           # UNMEASURED: assumed equal to walking; the supervised look measures it
YAW_DEG_PER_S = 172.0           # right stick 0.45 (Cal.yaw_map); 0.35 s = 60 deg
PULSE_S = 0.4
MIN_PULSE_S = 0.05
SWEEP_DEG = 60.0
JITTER_DEG = (15.0, -30.0, 15.0)
HEADING_TOL_DEG = 6.0
MAX_PULSES = 40                 # moves per attempt
MAX_SECONDS = 90.0              # per attempt, from the caller's dt
MAX_STEPS = 150                 # every call, whatever dt says (review F5)
MAX_PITCH_RESETS = 3
MAX_BAD_MOVES = 2
MAX_LOST_AFTER_MOVE = 4
RATE_FACTOR = (0.5, 2.0)        # a move's true displacement vs the planned one; the review found 0.5-2x safe
TRACK_MARGIN_M = 0.3            # slack when pruning a frame's poses against the tracked x interval


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def w(self):
        return self.x2 - self.x1

    @property
    def h(self):
        return self.y2 - self.y1

    @property
    def cx(self):
        return (self.x1 + self.x2) / 2


@dataclass(frozen=True)
class Pose:
    """Metres in the pair's frame: bots at (-S/2, 0) and (+S/2, 0), the lane runs toward -y; heading 0 faces +y.

    `feasible` holds every (x, y, heading_deg) consistent with the frame (see RANGE_LOG_BOUND); `x`, `y`, `d` are its
    central member; `side` is +1 or -1 when every feasible x agrees (beyond 0.3 m), else None; `x_hi` = max |x|."""
    x: float
    y: float
    d: float
    side: int | None
    x_hi: float
    feasible: tuple

    def hypotheses(self):
        return [(1 if px >= 0 else -1, px, py, h) for px, py, h in self.feasible]

    @property
    def abs_x(self):
        return abs(self.x)

    @property
    def heading(self):
        return min(self.feasible, key=lambda f: math.hypot(f[0] - self.x, f[1] - self.y))[2]


@dataclass(frozen=True)
class View:
    kind: str                   # PAIR | TWO | UNLEVELLED | NEAR_ONE | LOST | NOT_IN_RANGE
    target: Box | None = None   # the designated (right) bot, in 1440-row, 2560-wide pixels
    other: Box | None = None
    h: float | None = None      # target height / frame height
    pose: Pose | None = None
    reason: str = ""

    @property
    def aim_x(self):
        if self.other is not None and self.target is not None:
            return (self.other.cx + self.target.cx) / 2
        return self.target.cx if self.target is not None else None


def _scaled(bbox, frame):
    s = REF_H / frame[1]
    x1, y1, x2, y2 = bbox
    return Box(x1 * s, y1 * s, x2 * s, y2 * s)


def _bearing(b):
    return math.atan((b.cx - CENTRE_X) / FOCAL_PX)


def _subtended(beta, d):
    px, py = d * math.sin(beta), -d * math.cos(beta)
    return math.atan2(PAIR_SPACING_M / 2 - px, -py) - math.atan2(-PAIR_SPACING_M / 2 - px, -py)


def _solve_beta(alpha, d):
    """Angle off the axis at which the pair subtends `alpha` from distance `d` to its midpoint; (beta, alpha/on-axis)."""
    a0 = _subtended(0.0, d)
    if alpha >= a0:
        return 0.0, alpha / a0
    lo, hi = 0.0, math.radians(89.0)
    for _ in range(24):                                        # 89 deg / 2**24: ~5e-6 deg
        m = (lo + hi) / 2
        if _subtended(m, d) > alpha:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2, alpha / a0


def _mean_h(beta, d):
    px, py = d * math.sin(beta), -d * math.cos(beta)
    half = PAIR_SPACING_M / 2
    return H_TIMES_DISTANCE_M * (1 / math.hypot(-half - px, py) + 1 / math.hypot(half - px, py)) / 2


def _fit_distance(alpha, hm):
    """(d, beta): the distance to the midpoint at which the pose subtending `alpha` predicts mean box height `hm`.
    The mean of the two boxes' heights is not the midpoint's range at close range, where the bots are wide apart."""
    lo, hi = PAIR_SPACING_M / 2 + 0.05, 200.0
    if _mean_h(_solve_beta(alpha, lo)[0], lo) < hm:
        return None
    for _ in range(28):                                        # 200 m / 2**28: sub-micrometre
        m = (lo + hi) / 2
        if _mean_h(_solve_beta(alpha, m)[0], m) > hm:
            lo = m
        else:
            hi = m
    d = (lo + hi) / 2
    beta, ratio = _solve_beta(alpha, d)
    return None if ratio > 1.02 else (d, beta)                 # the angle is wider than any pose at this range allows


def localise(left, right):
    """The pose from two boxes, or None when no pose fits the frame.

    Bearings are exact, the mean-height range has a scale error within +-RANGE_SCALE_ERR, and each candidate pose
    predicts the per-box height ratio. The frame is accepted only if its best pose fits within RANGE_LOG_BOUND (the
    clean labelled residual). The SAFETY set, from which the side and |x| bound come, keeps every pose within
    BIAS_LOG_MAX: a box may carry up to the review's +-25% differential bias, so a pose that fits only that loosely
    may still be the true one."""
    pa, pb = _bearing(left), _bearing(right)
    alpha = pb - pa
    hm = (left.h + right.h) / 2 / REF_H
    if alpha <= 0 or hm <= 0:
        return None
    if H_TIMES_DISTANCE_M / hm < MIN_PAIR_RANGE_M:
        return None
    half = PAIR_SPACING_M / 2
    l_meas = math.log(right.h / left.h)
    cands = []                                                 # (residual, x, y, heading, d)
    for i in range(SCALE_STEPS):
        e = -RANGE_SCALE_ERR + 2 * RANGE_SCALE_ERR * i / (SCALE_STEPS - 1)
        fit = _fit_distance(alpha, hm * (1 + e))
        if fit is None:
            continue
        d, beta = fit
        ax, y = d * math.sin(beta), -d * math.cos(beta)
        l_pred = math.log(math.hypot(-half - ax, y) / math.hypot(half - ax, y))
        for s in (1, -1) if ax > 1e-9 else (1,):
            px = s * ax
            heading = (math.degrees(math.atan2(-half - px, -y)) - math.degrees(pa) + 180) % 360 - 180
            cands.append((abs(l_meas - s * l_pred), px, y, heading, d))
    if not cands:
        return None
    best = min(cands)
    if best[0] > RANGE_LOG_BOUND:
        return None
    safety = [(c[1], c[2], c[3]) for c in cands if c[0] <= BIAS_LOG_MAX]
    xs = [f[0] for f in safety]
    side = 1 if min(xs) > 0.3 else -1 if max(xs) < -0.3 else None
    return Pose(best[1], best[2], best[4], side, max(abs(v) for v in xs), tuple(safety))


def on_lane(pose):
    """The central pose is on the lane (off-lane false pairs localise 15-20 m to the side)."""
    return abs(pose.x) <= LANE_X_M and LANE_Y_M[0] <= pose.y <= LANE_Y_M[1]


def level_residual(b):
    """Pixels between a box's bottom and the lane's level at the reference pitch."""
    return b.y2 - (LEVEL_Y2_AT_ZERO_H + LEVEL_SLOPE * b.h)


def _level_ok(b):
    return LEVEL_RESIDUAL_PX[0] <= level_residual(b) <= LEVEL_RESIDUAL_PX[1]


def pair_signature(left, right):
    """The measured on-lane pair shape; pitch-free."""
    hm = (left.h + right.h) / 2
    ratio = (right.cx - left.cx) / hm
    return (PAIR_SEP_PER_H[0] <= ratio <= PAIR_SEP_PER_H[1] and abs(left.y1 - right.y1) <= PAIR_MAX_DY
            and abs(left.h - right.h) / max(left.h, right.h) <= PAIR_MAX_DH)


def classify(frame, boxes, in_range=True, pitch_ref=False):
    """frame = (width, height); boxes = finder bboxes in its pixels; pitch_ref = the camera is at the reference pitch.

    The driver sets pitch_ref after its PITCH_RESET. Recorded frames of unknown pitch pass False and can never yield
    a pose, so they can never yield a move."""
    if not in_range:
        return View("NOT_IN_RANGE", reason="range HUD not proven")
    bs = [b for b in (_scaled(x, frame) for x in boxes) if b.h > 0 and b.w > 0]
    galacta = [b for b in bs if GALACTA_ASPECT[0] <= b.w / b.h <= GALACTA_ASPECT[1]]
    found = []
    for i, a in enumerate(galacta):
        for b in galacta[i + 1:]:
            left, right = (a, b) if a.cx <= b.cx else (b, a)
            pose = localise(left, right)
            if pose is None or not on_lane(pose):
                continue
            found.append((0 if pair_signature(left, right) else 1, left, right, pose))
    if found:
        best = min(f[0] for f in found)
        top = [f for f in found if f[0] == best]
        if len(top) > 1:
            return View("LOST", reason=f"{len(top)} candidate pairs")
        rank, left, right, pose = top[0]
        if not pitch_ref:
            return View("UNLEVELLED", target=right, other=left, h=right.h / REF_H, reason="pitch not at reference")
        if not (_level_ok(left) and _level_ok(right)):
            return View("LOST", target=right, other=left, reason="pair not on the lane's level")
        return View("PAIR" if rank == 0 else "TWO", target=right, other=left, h=right.h / REF_H, pose=pose)
    near = [b for b in bs if b.h / REF_H >= NEAR_MIN_H and NEAR_ASPECT[0] <= b.w / b.h <= NEAR_ASPECT[1]
            and NEAR_CX[0] <= b.cx <= NEAR_CX[1]]
    if len(near) == 1:
        return View("NEAR_ONE", target=near[0], h=near[0].h / REF_H)
    return View("LOST", reason="no pair and no single point-blank bot" if not near else "several point-blank boxes")


def _same_pose(a, b):
    return (abs(a.d - b.d) <= 0.15 * max(a.d, b.d) and abs(a.x_hi - b.x_hi) <= 1.5
            and (a.side is None or b.side is None or a.side == b.side))


def decide(views):
    """One decision from up to FRAMES_PER_DECISION fresh views (review F6).

    NOT_IN_RANGE on any frame wins. A pose counts only when FRAMES_TO_AGREE views of the same kind carry consistent
    poses (the latest is returned); then UNLEVELLED or NEAR_ONE seen on as many frames; else LOST."""
    views = list(views)[-FRAMES_PER_DECISION:]
    for v in views:
        if v.kind == "NOT_IN_RANGE":
            return v
    for kind in ("PAIR", "TWO"):
        posed = [v for v in views if v.kind == kind and v.pose is not None]
        for v in reversed(posed):
            if sum(_same_pose(v.pose, w.pose) for w in posed) >= FRAMES_TO_AGREE:
                return v
    for kind in ("UNLEVELLED", "NEAR_ONE"):
        hit = [v for v in views if v.kind == kind]
        if len(hit) >= FRAMES_TO_AGREE:
            return hit[-1]
    lost = [v for v in views if v.kind == "LOST"]
    return lost[-1] if lost else View("LOST", reason="no view agreed on enough frames")


# --- Planner ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Action:
    kind: str                   # PITCH_RESET | TURN | STRAFE | WALK | READY | HAND_BACK
    value: float = 0.0          # TURN: degrees (+ right); STRAFE: seconds (+ right); WALK: seconds (+ forward)
    reason: str = ""


@dataclass(frozen=True)
class PlanState:
    target_bin: str
    attempt: int = 1
    steps: int = 0
    elapsed: float = 0.0
    moves: int = 0
    pitched: bool = False
    pitch_resets: int = 0
    sweep_deg: float = 0.0
    jitter: int = 0
    bad_moves: int = 0
    lost_after_move: int = 0
    x_bounds: tuple | None = None       # tracked [lo, hi] of x, carried through our own moves
    at_near_stand: bool = False
    last: Action | None = None
    last_view: View | None = None
    log: tuple = field(default_factory=tuple)


def turn_seconds(degrees):
    """Right-stick 0.45 hold for a turn of `degrees` (sign gives the direction)."""
    return abs(degrees) / YAW_DEG_PER_S


def target_range(target_bin):
    """Metres from the designated bot at the middle of the bin."""
    lo, hi = BINS[target_bin]
    return H_TIMES_DISTANCE_M / ((lo + hi) / 2)


def _clip(s, limit=PULSE_S):
    s = max(-limit, min(limit, s))
    return math.copysign(max(abs(s), MIN_PULSE_S), s)


def _end(x, y, heading_deg, action):
    h = math.radians(heading_deg)
    if action.kind == "WALK":
        d = action.value * WALK_M_PER_S
        return x + d * math.sin(h), y + d * math.cos(h)
    d = action.value * STRAFE_M_PER_S
    return x + d * math.cos(h), y - d * math.sin(h)


def safe(pose, action, ceiling=DROP_MARGIN_M):
    """The move's predicted end is safe for every feasible pose: within the drop zone never beyond `ceiling` on the
    drop side (+x) unless closer to the axis than its start, and never off the lane's ends. The left side is walls and
    planters in every pilot frame, not a drop: UNVERIFIED, the supervised look checks it."""
    for _, x, y, heading in pose.hypotheses():
        ex, ey = _end(x, y, heading, action)
        if ex > ceiling and ex >= x - 0.05 and ey >= DROP_ZONE_Y_M:
            return False
        if not LANE_Y_M[0] <= ey <= LANE_Y_M[1]:
            return False
    return True


def _track(state, view):
    """Prune the frame's feasible poses to the x interval our own moves allow, and carry the interval on.

    A camera turn does not move x; a walk or strafe moves it by the planned displacement times RATE_FACTOR. A frame
    that contradicts the interval entirely is kept as it is and restarts the track (its own safety set still holds)."""
    pose = view.pose
    if pose is None:
        return state, view
    bounds = state.x_bounds
    last = state.last
    if bounds is not None and last is not None and last.kind in ("WALK", "STRAFE") and state.last_view is not None             and state.last_view.pose is not None:
        deltas = [(_end(x, y, h, replace(last, value=last.value * f))[0] - x)
                  for _, x, y, h in state.last_view.pose.hypotheses() for f in RATE_FACTOR]
        bounds = (bounds[0] + min(deltas + [0.0]), bounds[1] + max(deltas + [0.0]))
    feas = pose.feasible
    if bounds is not None:
        kept = tuple(f for f in feas if bounds[0] - TRACK_MARGIN_M <= f[0] <= bounds[1] + TRACK_MARGIN_M)
        feas = kept or feas
    xs = [f[0] for f in feas]
    side = 1 if min(xs) > 0.3 else -1 if max(xs) < -0.3 else None
    central = min(feas, key=lambda f: abs(f[0] - pose.x) + abs(f[1] - pose.y))
    pose = replace(pose, x=central[0], y=central[1], side=side, x_hi=max(abs(v) for v in xs), feasible=feas)
    return replace(state, x_bounds=(min(xs), max(xs))), replace(view, pose=pose)


def _retry_or_hand_back(state, reason):
    if state.attempt < 2:
        fresh = PlanState(state.target_bin, attempt=state.attempt + 1, steps=state.steps, pitched=True,
                          pitch_resets=1, log=state.log + (f"retry: {reason}",))
        return Action("PITCH_RESET", reason=f"retry after: {reason}"), fresh
    return Action("HAND_BACK", reason=reason), replace(state, log=state.log + (f"hand back: {reason}",))


def _emit(state, action, view, note):
    moved = action.kind in ("WALK", "STRAFE")
    return action, replace(state, moves=state.moves + moved, last=action, last_view=view, log=state.log + (note,))


def _search(state, view):
    located = state.last_view is not None and state.last_view.kind in ("PAIR", "TWO", "NEAR_ONE")
    if state.jitter < len(JITTER_DEG) and (located or state.jitter):
        act = Action("TURN", JITTER_DEG[state.jitter], "search: small camera jitter")
        return act, replace(state, jitter=state.jitter + 1, last=act, log=state.log + ("jitter",))
    if state.sweep_deg >= 360.0:
        return _retry_or_hand_back(state, "pair not found in a full camera turn")
    act = Action("TURN", SWEEP_DEG, "search: camera only")
    return act, replace(state, sweep_deg=state.sweep_deg + SWEEP_DEG, last=act, last_view=view,
                        log=state.log + ("sweep",))


def plan(state, view, dt=0.0):
    """One step: the decided view of fresh frames -> (action, new state). Every call counts against MAX_STEPS."""
    state = replace(state, steps=state.steps + 1, elapsed=state.elapsed + dt)
    if state.steps > MAX_STEPS:
        return Action("HAND_BACK", reason="step limit"), replace(state, log=state.log + ("hand back: step limit",))
    if view.kind == "NOT_IN_RANGE":
        return Action("HAND_BACK", reason="not in range"), state
    if state.target_bin == "near" and EDGE_X_M is None:
        return Action("HAND_BACK", reason="near placement needs the measured lane edge (review F4)"), state
    if not state.pitched or view.kind == "UNLEVELLED":
        if state.pitch_resets >= MAX_PITCH_RESETS:
            return _retry_or_hand_back(state, "pitch did not reach the reference level")
        act = Action("PITCH_RESET", reason="camera pitch to the reference before classifying")
        return act, replace(state, pitched=True, pitch_resets=state.pitch_resets + 1, last=act, last_view=view,
                            log=state.log + ("pitch reset",))
    if state.moves >= MAX_PULSES or state.elapsed >= MAX_SECONDS:
        return _retry_or_hand_back(state, "placement budget spent")

    state, view = _track(state, view)
    last = state.last
    if last is not None and last.kind in ("WALK", "STRAFE"):
        prev = state.last_view.pose if state.last_view is not None else None
        if view.pose is None:
            state = replace(state, lost_after_move=state.lost_after_move + 1)
            if state.lost_after_move > MAX_LOST_AFTER_MOVE:
                return _retry_or_hand_back(state, "moves kept losing the pair")
        elif prev is not None:
            ends = [_end(x, y, h, last) for _, x, y, h in prev.hypotheses()]
            miss = min(math.hypot(fx - ex, fy - ey) for ex, ey in ends for fx, fy, _ in view.pose.feasible)
            bad = miss > 1.5 * abs(last.value) * WALK_M_PER_S + 0.25 * view.pose.d
            state = replace(state, bad_moves=state.bad_moves + 1 if bad else 0)
            if state.bad_moves >= MAX_BAD_MOVES:
                return _retry_or_hand_back(state, "moves did not go where predicted")

    lo, hi = BINS[state.target_bin]
    if view.kind == "NEAR_ONE":
        if state.at_near_stand:
            err = math.degrees(math.atan((view.target.cx - CENTRE_X) / FOCAL_PX))
            if abs(err) > HEADING_TOL_DEG:
                return _emit(state, Action("TURN", err, "near: centre the designated bot"), view, "turn")
            if lo <= view.h <= hi:
                return _emit(state, Action("READY", reason=f"near: designated bot h {view.h:.3f}"), view, "ready")
            state = replace(state, at_near_stand=False)
        if state.sweep_deg >= 360.0:
            return _retry_or_hand_back(state, "point blank and the other bot not found in a full camera turn")
        act = Action("TURN", SWEEP_DEG, "point blank: camera only until both bots are in view")
        return act, replace(state, sweep_deg=state.sweep_deg + SWEEP_DEG, last=act, last_view=view,
                            log=state.log + ("near sweep",))
    if view.kind not in ("PAIR", "TWO") or view.pose is None:
        return _search(state, view)

    pose = view.pose
    state = replace(state, sweep_deg=0.0, jitter=0)
    err = math.degrees(math.atan((view.aim_x - CENTRE_X) / FOCAL_PX))
    if abs(err) > HEADING_TOL_DEG:                               # face the pair's midpoint: needs no side
        return _emit(state, Action("TURN", err, "face the pair"), view, f"turn {err:+.1f}")

    ceiling = DROP_MARGIN_M
    toward_pair = Action("WALK", _clip((pose.d - MIN_PAIR_RANGE_M - 0.5) / WALK_M_PER_S),
                         "side unresolved: walk toward the pair (inward for both mirror poses)")
    if state.target_bin == "near":
        ceiling = EDGE_X_M - NEAR_EDGE_CLEARANCE_M
        stand_x, want = min(PAIR_SPACING_M / 2, ceiling), target_range("near")
        if pose.side is None:
            if pose.d <= MIN_PAIR_RANGE_M + 0.6:
                return _retry_or_hand_back(state, "side of the lane unresolved at close range")
            act = toward_pair
        elif abs(stand_x - pose.x) > 0.3:
            ex = stand_x - pose.x
            h = pose.heading
            act = Action("STRAFE", _clip(ex * math.cos(math.radians(h)) / STRAFE_M_PER_S, NEAR_STRAFE_S),
                         f"near: strafe {ex:+.1f} m toward the stand")
        else:
            dist_b = math.hypot(PAIR_SPACING_M / 2 - pose.x, pose.y)
            if dist_b - want > 0.35 and pose.d > MIN_PAIR_RANGE_M + 0.3:
                act = Action("WALK", _clip((dist_b - want) / WALK_M_PER_S, NEAR_STRAFE_S), "near: walk to the stand")
            else:
                b = math.degrees(math.atan((view.target.cx - CENTRE_X) / FOCAL_PX))
                act = Action("TURN", b, "near: at the stand, turn onto the designated bot")
                return act, replace(state, at_near_stand=True, last=act, last_view=view, log=state.log + ("to bot",))
    elif abs(pose.x) > LATERAL_OK_M and (pose.side == 1 or (pose.side == -1 and pose.y < DROP_ZONE_Y_M)):
        h = pose.heading
        ex = -pose.x
        act = Action("STRAFE", _clip(ex * math.cos(math.radians(h)) / STRAFE_M_PER_S), f"strafe {ex:+.1f} m to the axis")
    elif lo <= view.h <= hi:
        if view.kind == "PAIR":
            return _emit(state, Action("READY", reason=f"PAIR h {view.h:.3f} in {state.target_bin}"), view, "ready")
        return _search(state, view)
    else:
        dist_b = H_TIMES_DISTANCE_M / view.h                      # the bin is on the designated bot's own box
        act = Action("WALK", _clip((dist_b - target_range(state.target_bin)) / WALK_M_PER_S),
                     f"walk {dist_b - target_range(state.target_bin):+.1f} m toward the bin")
    if act.kind == "WALK" and act.value < 0 and state.target_bin != "near":
        left_limit = -(LANE_X_M - 0.7)
        if pose.side == -1 and pose.x < left_limit:
            # Backing out along the ray from the left drifts further left: step back toward the axis (every feasible
            # pose is left of the axis, so the strafe cannot reach the drop side's margin; safe() checks it).
            act = Action("STRAFE", PULSE_S / 2, "backing out: step back toward the axis from the left")
        elif not safe(pose, act, ceiling) and pose.side != -1:
            # Backing out along the ray can widen x toward the drop (+x). Facing the pair, a LEFT strafe moves toward
            # -x for every feasible pose, until every pose lies left of the axis and backing out is safe.
            if pose.x - PULSE_S / 2 * STRAFE_M_PER_S < left_limit:
                return _retry_or_hand_back(state, "no room left of the axis to back out safely")
            act = Action("STRAFE", -PULSE_S / 2, "strafe left, away from the drop side, before backing out")
    if not safe(pose, act, ceiling):
        return _retry_or_hand_back(state, f"{act.kind.lower()} {act.value:+.2f} is not safe for every feasible pose")
    return _emit(state, act, view, f"{act.kind.lower()} {act.value:+.2f}")
