"""A top-down simulated courtyard lane for agent/placement.py: tests and `scripts/place.py --replay` use it.

Metres in the pair frame: bots at x = +-PAIR_SPACING_M/2, y = 0; the lane runs toward -y. The left side x < -5 is a
wall. The right side x > +4.5 is railed for y < -8 and an unrailed DROP for y >= -8, the stretch beside the bots where
both falls of galacta-pilot-20260923 happened. The extents are the design's estimate, not a map (UNVERIFIED).

The camera has a pitch offset in pixels (0 = the reference; PITCH_RESET returns it to `pitch_after_reset`). Lane boxes
sit on the planner's level line. After a fall Spider-Man is on the lower plaza: the pair stays visible at any heading,
from below, its boxes ~214 px under the lane's level (the real lower-plaza frame and the review's x1.9 pair).
`height_bias=(left, right)` multiplies each bot's box height about its bottom: the differential bias of review F1.
"""
import math
import random

from . import placement as P

HALF_FOV_DEG = 54.0             # ~108 deg horizontal field of view
BOX_ASPECT = 0.95               # Galacta w/h at far/mid (measured 0.80-1.12)
PLAZA_LEVEL_PX = 214.0          # the lower-plaza view's level residual (real frame 215; x1.9 plaza pair 214)


def render(x, y, heading_deg, *, fallen=False, pitch_px=0.0, height_bias=(1.0, 1.0), drop=lambda: False):
    """Finder-like boxes (2560x1440 pixels) of the two bots seen from a pose. `drop()` true drops that box (flicker)."""
    out = []
    for bx, bias in zip((-P.PAIR_SPACING_M / 2, P.PAIR_SPACING_M / 2), height_bias):
        dx, dy = bx - x, -y
        r = math.hypot(dx, dy)
        phi = (math.degrees(math.atan2(dx, dy)) - heading_deg + 180) % 360 - 180
        if abs(phi) >= HALF_FOV_DEG or drop():
            continue
        hpx = P.H_TIMES_DISTANCE_M / r * P.REF_H
        cx = P.CENTRE_X + P.FOCAL_PX * math.tan(math.radians(phi))
        w = BOX_ASPECT * hpx
        y2 = P.LEVEL_Y2_AT_ZERO_H + P.LEVEL_SLOPE * hpx + pitch_px + (PLAZA_LEVEL_PX if fallen else 0.0)
        out.append([cx - w / 2, y2 - hpx * bias, cx + w / 2, y2])
    return out


class Lane:
    WALL_X, DROP_X, RAIL_Y = -5.0, 4.5, -8.0

    def __init__(self, x, y, heading_deg, flicker=0.0, seed=1, speed=1.0, height_bias=(1.0, 1.0),
                 pitch_px=0.0, pitch_after_reset=0.0):
        self.x, self.y, self.heading = x, y, heading_deg
        self.fallen = False
        self.rng = random.Random(seed)
        self.flicker, self.speed, self.height_bias = flicker, speed, height_bias
        self.pitch_px, self.pitch_after_reset = pitch_px, pitch_after_reset
        self.pitch_ref = False
        self.moves = []

    def _move(self, dx, dy):
        n = 20
        for _ in range(n):
            nx, ny = max(self.x + dx / n, self.WALL_X), min(self.y + dy / n, -0.8)
            if nx > self.DROP_X:
                if ny < self.RAIL_Y:
                    nx = self.DROP_X
                else:
                    self.fallen = True
                    self.x, self.y = nx, ny
                    return
            self.x, self.y = nx, ny

    def walk(self, seconds):
        self.moves.append(("walk", seconds))
        if not self.fallen:
            d, h = seconds * P.WALK_M_PER_S * self.speed, math.radians(self.heading)
            self._move(d * math.sin(h), d * math.cos(h))

    def strafe(self, seconds):
        self.moves.append(("strafe", seconds))
        if not self.fallen:
            d, h = seconds * P.STRAFE_M_PER_S * self.speed, math.radians(self.heading)
            self._move(d * math.cos(h), -d * math.sin(h))

    def jump(self):
        """A forward jump: ~3 m along the heading, over whatever edge is there."""
        self.moves.append(("jump", 1))
        h = math.radians(self.heading)
        self._move(3.0 * math.sin(h), 3.0 * math.cos(h))

    def turn(self, degrees):
        self.heading = (self.heading + degrees + 180) % 360 - 180

    def pitch_reset(self):
        self.pitch_px, self.pitch_ref = self.pitch_after_reset, True

    def boxes(self):
        return render(self.x, self.y, self.heading, fallen=self.fallen, pitch_px=self.pitch_px,
                      height_bias=self.height_bias, drop=lambda: self.rng.random() < self.flicker)

    def view(self):
        if not self.flicker:                                   # deterministic frames: classify once, decide on copies
            v = P.classify((2560, 1440), self.boxes(), True, self.pitch_ref)
            return P.decide([v] * P.FRAMES_PER_DECISION)
        return P.decide([P.classify((2560, 1440), self.boxes(), True, self.pitch_ref)
                         for _ in range(P.FRAMES_PER_DECISION)])

    def act(self, action):
        if action.kind == "PITCH_RESET":
            self.pitch_reset()
        elif action.kind == "TURN":
            self.turn(action.value)
        elif action.kind == "WALK":
            self.walk(action.value)
        elif action.kind == "STRAFE":
            self.strafe(action.value)


def run(lane, target_bin, steps=400, dt=0.6):
    """Closed loop on the simulated lane: [(action, view)] up to READY or HAND_BACK, and the final planner state."""
    state, actions = P.PlanState(target_bin), []
    for _ in range(steps):
        view = lane.view()
        act, state = P.plan(state, view, dt=dt)
        actions.append((act, view))
        if act.kind in ("READY", "HAND_BACK"):
            break
        lane.act(act)
    return actions, state
