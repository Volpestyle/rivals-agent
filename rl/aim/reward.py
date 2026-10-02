"""Dense aim reward from pixels: potential-based shaping on the crosshair-to-target offset (VUH-1321).

Potential. Phi(s) = -min(d, 1), d = distance from the screen centre (the crosshair) to the centre of the guarded
target vector's NEAREST box (policy.bc2.target_features, 1280x720 pixels), in units of the half screen width (640 px):
0 with a box centred on the crosshair, -1 at the left/right screen edge or beyond. "Nearest" is a function of the frame
alone, so when two persistent bots swap as nearest they are equally far at the swap and Phi does not jump.

Shaping. F_k = gamma_k * Phi(s_k) - Phi(s_{k-1}) between consecutive retained frames, gamma_k = 1 by default, so
F summed over any unbroken run of known frames is exactly Phi(last) - Phi(first): oscillating the camera over a
target nets zero, and holding still earns nothing.

None, never zero. F_k is None (no shaping term, and the chain re-anchors at s_k) when:
  - unknown:  the target vector is unknown at s_k (door abstention, no green detection: known = 0);
  - gap:      s_{k-1} was unknown, or the frames are more than MAX_GAP_S apart; reacquiring a target after a finder
              flicker, a door view or a dropped frame is never paid;
  - switch:   the nearest box moved more than JUMP half-widths or changed height by more than H_RATIO between the two
              frames. That is a box appearing or disappearing (a bot entering view, a KO'd bot vanishing, a fragment
              or a flicker), not camera motion; paying it would reward the finder, not the aim.
The cost of cutting is bounded and measured: every cut drops one Phi difference, never more than 1 in size.

Use. F is a separate reward component (rl.online.data `reward_aim`, with `aim_known`), not part of the sparse
`reward`. Summed into a discounted Monte-Carlo return, potential shaping telescopes to -Phi(s_k) plus a distant end
term: a pure state term that a constant AWR baseline does not cancel, so it would weight steps by how far off target
they START, which says nothing about the action. rl.online.update therefore consumes it as a short-horizon
advantage, `window(F, t, AIM_HORIZON_S)` = Phi(k + horizon) - Phi(k): did the camera bring the target closer over the
next half second. Results and limits: rl/out/aim/aim_reward_20261002.md, docs/lanes/rl.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

HALF_W = 640.          # 1280x720 pixels per unit of d
JUMP = .25             # half-widths the nearest box may move between two retained frames before it is a switch
H_RATIO = 1.6          # box height ratio between two retained frames beyond which it is a switch
MAX_GAP_S = .5         # s between retained frames beyond which the chain re-anchors
AIM_HORIZON_S = .5     # s: the update's advantage window
WEIGHT = .3            # starting weight per unit Phi (a full edge-to-centre acquisition = .3 of a hit)


def nearest(vec):
    """(x, y, h) of the nearest box in half-width units (x right, y down) and 720p height share, or None if unknown."""
    if vec is None or len(vec) < 5 or not vec[0] or not vec[1]:
        return None
    return float(vec[2]) * 1280 / HALF_W, float(vec[3]) * 720 / HALF_W, float(vec[4])


def potential(vec):
    """Phi in [-1, 0], or None when the target is unknown."""
    p = nearest(vec)
    return None if p is None else -min(math.hypot(p[0], p[1]), 1.)


@dataclass
class AimStep:
    t: float
    phi: float | None
    shaping: float | None       # weighted F_k; None = no term
    reason: str                 # ok | first | unknown | gap | switch
    prev_t: float | None = None  # the interval's start: the decision that caused F_k acted from here


@dataclass
class AimShaper:
    weight: float = 1.
    gamma: float = 1.
    jump: float = JUMP
    h_ratio: float = H_RATIO
    max_gap_s: float = MAX_GAP_S
    steps: list = field(default_factory=list)
    _prev: tuple | None = None   # (t, phi, (x, y, h)) of the previous frame, None if it was unknown

    def update(self, t, vec):
        p = nearest(vec)
        prev, phi = self._prev, potential(vec)
        if p is None:
            step = AimStep(t, None, None, "unknown", prev and prev[0])
            self._prev = None
        else:
            if prev is None:
                reason = "first" if not self.steps else "gap"
            elif t - prev[0] > self.max_gap_s:
                reason = "gap"
            else:
                (x0, y0, h0), (x1, y1, h1) = prev[2], p
                hr = max(h1, 1e-6) / max(h0, 1e-6)
                reason = "switch" if math.hypot(x1 - x0, y1 - y0) > self.jump or max(hr, 1 / hr) > self.h_ratio \
                    else "ok"
            f = self.weight * (self.gamma * phi - prev[1]) if reason == "ok" else None
            step = AimStep(t, phi, f, reason, prev and prev[0])
            self._prev = (t, phi, p)
        self.steps.append(step)
        return step


def shaping_series(vecs, times, **kwargs):
    """AimSteps for a whole sequence of target vectors (offline analysis)."""
    s = AimShaper(**kwargs)
    return [s.update(t, v) for v, t in zip(vecs, times)]


def window(values, t, horizon_s=AIM_HORIZON_S):
    """Per row k: the sum of values[j] for t[k] <= t[j] < t[k] + horizon_s (rows already credited to decisions).
    With per-decision F this is the aim change over the next horizon: Phi(k + horizon) - Phi(k) on an unbroken run."""
    import numpy as np
    v = np.nan_to_num(np.asarray(values, float))
    t = np.asarray(t, float)
    c = np.concatenate([[0.], np.cumsum(v)])
    hi = np.searchsorted(t, t + horizon_s, side="left")
    return c[hi] - c[np.arange(len(t))]
