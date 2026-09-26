"""From the policy's semantic actions and requested camera degrees to the existing guarded pad (§4). Offline, stdlib.

This module only computes pad states: it never opens a pad. The live path hands its output to `agent.controller.Live`
(`send_guarded`, whitelist, fresh-HUD proof, the 250 ms lease), which stays the only door to the pad. There is no
SendInput path: L0 closed injected mouse buttons and nobody works around it, and hardware or driver injectors are out
of scope (`docs/plan.md` scope boundary).

Camera: requested degrees per step -> deg/s -> stick deflection through the measured maps (`agent.controller.Cal`,
yaw 172 deg/s at 0.45, 415 at 1.0; pitch 99 at 1.0), feedforward, plus an optional correction on the accumulated
error between requested and measured rotation. Whether the correction is needed is decided by the measured tracking
error (`tracking_error`), reported before any pilot; nothing here assumes the maps are exact in play.
"""
from dataclasses import dataclass, field
import math

from agent.controller import NEUTRAL, Cal, stick_for

from . import vocab

STEP_S = 1 / 30

# Semantic action -> pad buttons / triggers that Live's whitelist allows. Movement goes to the left stick.
BUTTON = {"jump": "A", "web_swing": "LB", "get_over_here": "RB", "amazing_combo": "X"}
TRIGGER = {"spider_power": "rt", "web_cluster": "lt"}
MOVE = {"move_forward": (0., 1.), "move_back": (0., -1.), "move_left": (-1., 0.), "move_right": (1., 0.)}


def max_step_degrees(cal=None):
    """The largest rotation per step the pad can produce: (yaw, pitch) at full deflection."""
    cal = cal or Cal()
    return cal.yaw_map[-1][1] * STEP_S, cal.pitch_map[-1][1] * STEP_S


def saturate(yaw_deg, pitch_deg, cal=None):
    """What the pad can deliver of a requested rotation (sign kept)."""
    my, mp = max_step_degrees(cal)
    return math.copysign(min(abs(yaw_deg), my), yaw_deg), math.copysign(min(abs(pitch_deg), mp), pitch_deg)


def decode_step(held_p, press_p, release_p, prev_held, live_mask, threshold=.5):
    """The executed actions of one step, consistent with a hold model: (held, press, release) bit lists.

    Masked actions are never executed. A press is a rise of the hold, or a tap (press and release both predicted
    while not held before or after); a release is a fall of the hold, or the tap's release."""
    held, press, release = [], [], []
    for c in range(vocab.N):
        if not live_mask[c]:
            held.append(0), press.append(0), release.append(0)
            continue
        h = int(held_p[c] >= threshold)
        tap = not h and not prev_held[c] and press_p[c] >= threshold and release_p[c] >= threshold
        held.append(h)
        press.append(int((h and not prev_held[c]) or tap))
        release.append(int((prev_held[c] and not h) or tap))
    return held, press, release


def pad_state(held, press, yaw_deg, pitch_deg, *, cal=None, correction=(0., 0.)):
    """One step's pad dict for Live.send_guarded. A tap is held for the whole step (the pad needs >= 33 ms: Cal.press_s),
    so `press` without `held` still sets the control for this step. `correction` is deg/s added per axis."""
    cal = cal or Cal()
    active = [h or p for h, p in zip(held, press)]
    lx = sum(MOVE[n][0] for n in MOVE if active[vocab.INDEX[n]])
    ly = sum(MOVE[n][1] for n in MOVE if active[vocab.INDEX[n]])
    norm = math.hypot(lx, ly)
    if norm > 1:
        lx, ly = lx / norm, ly / norm
    out = dict(NEUTRAL)
    out["lx"], out["ly"] = lx, ly
    out["buttons"] = tuple(sorted(BUTTON[n] for n in BUTTON if active[vocab.INDEX[n]]))
    for n, t in TRIGGER.items():
        out[t] = 1. if active[vocab.INDEX[n]] else 0.
    yaw_rate = yaw_deg / STEP_S + correction[0]
    # policy pitch is positive downward and ry up-positive; None (an unknown pitch gain) sends no pitch
    pitch_up_rate = -((pitch_deg or 0.) / STEP_S) + correction[1]
    out["rx"] = stick_for(yaw_rate, cal.yaw_map, cal.yaw_deadzone)
    out["ry"] = stick_for(pitch_up_rate, cal.pitch_map, cal.pitch_deadzone)
    return out


def caveat(accel_on=True, kind="slow_turn_constant"):
    """The degree caveat every saturation, tracking and feasibility number carries (vocab.DEGREE_CAVEAT), until a
    multi-speed take confirms the gain is linear (kind "speed_curve")."""
    return vocab.DEGREE_CAVEAT if kind != "speed_curve" else None


def min_step_degrees(cal=None):
    """The smallest rotation per step with measured support, per axis: the first measured non-zero map point / 30.
    Requests below it are commanded through the interpolated low end (and, until measured, through the deadzone)."""
    cal = cal or Cal()
    first = lambda m: next(r for s, r in m if r > 0)
    return {"yaw": first(cal.yaw_map) * STEP_S, "pitch": first(cal.pitch_map) * STEP_S,
            "yaw_deadzone": cal.yaw_deadzone, "pitch_deadzone": cal.pitch_deadzone,
            "deadzone_measured": cal.yaw_deadzone is not None and cal.pitch_deadzone is not None,
            "caveat": caveat()}


# Requested-rate bands for the tracking-error report (deg/s), per axis (review L3): the unmeasured low end, then the
# measured map's segments, then saturation (K3). Pitch's first measured point is 43 deg/s at 0.5.
RATE_BANDS = {"yaw": (0., 9., 18.5, 61.5, 172., 415.), "pitch": (0., 9., 43., 99.)}


def _band(rate_abs, cap, bands):
    if rate_abs > cap:
        return "saturated"
    for lo, hi in zip(bands, bands[1:]):
        if rate_abs < hi or hi == bands[-1]:
            return f"{lo:g}-{hi:g}"
    return "saturated"


def replay_profiles(sessions):
    """Requested-rotation profiles for the pre-pilot tracking test: James's own camera steps, in degrees, from
    train-split recordings (train or dev use) only, so validation stays unread before the real fit (K3)."""
    from . import steps
    for s in sessions:
        steps.require(s.split == "train", f"{s.session_id}: replay profiles come from train or dev recordings only")
    out = []
    for s in sessions:
        for a, b in steps.runs(s, regimes=steps.REGIMES):
            out.append([(t["yaw"], t["pitch"]) for t in (steps.target(r, s.calibration) for r in s.rows[a:b])
                        if t["yaw"] is not None])
    return out


@dataclass
class Tracker:
    """Accumulated requested-minus-measured rotation, fed back as deg/s with gain `k` (0 = feedforward only)."""
    k: float = 0.
    limit_deg: float = 20.
    error: list = field(default_factory=lambda: [0., 0.])

    def update(self, requested, measured):
        for i in range(2):
            if measured[i] is None:          # no measurement this step: do not integrate a guess
                continue
            self.error[i] = max(-self.limit_deg, min(self.limit_deg, self.error[i] + requested[i] - measured[i]))
        # pitch is positive downward in both lists; the pad's ry is up-positive, pad_state flips it
        return self.k * self.error[0], -self.k * self.error[1]


def tracking_error(requested, measured, cal=None):
    """Per-axis error of executed against requested rotation over a run: [(yaw, pitch)] each, degrees per step.

    Reports MAE, bias, RMS, the share of steps whose request exceeds what the pad can deliver, and the MAE over
    unsaturated steps only. Steps with an unmeasured axis are skipped for that axis."""
    my, mp = max_step_degrees(cal)
    out = {}
    for i, (axis, cap) in enumerate((("yaw", my), ("pitch", mp))):
        pairs = [(r[i], m[i]) for r, m in zip(requested, measured) if m[i] is not None and r[i] is not None]
        if not pairs:
            out[axis] = None
            continue
        errs = [m - r for r, m in pairs]
        unsat = [abs(m - r) for r, m in pairs if abs(r) <= cap]
        bands = {}
        for r, m in pairs:
            b = bands.setdefault(_band(abs(r) / STEP_S, cap / STEP_S, RATE_BANDS[axis]), [0, 0., 0.])
            b[0], b[1], b[2] = b[0] + 1, b[1] + abs(m - r), b[2] + (m - r)
        out[axis] = {"steps": len(pairs), "mae": sum(map(abs, errs)) / len(errs), "bias": sum(errs) / len(errs),
                     "rms": math.sqrt(sum(e * e for e in errs) / len(errs)),
                     "saturated_share": sum(abs(r) > cap for r, _ in pairs) / len(pairs),
                     "unsaturated_mae": sum(unsat) / len(unsat) if unsat else None,
                     "by_requested_rate_deg_s": {k: {"steps": n, "mae": e / n, "bias": s / n}
                                                 for k, (n, e, s) in sorted(bands.items())}}
    out["caveat"] = caveat()
    return out


def human_feasibility(yaw_steps, pitch_steps, cal=None):
    """Share of human camera steps (degrees per step) the pad cannot reproduce at full deflection, and share of moving
    steps below the smallest measured rotation (the unmeasured low end, K3)."""
    my, mp = max_step_degrees(cal)
    low = min_step_degrees(cal)
    moving = lambda vs: [v for v in vs if v]
    share = lambda vs, f: sum(map(f, vs)) / max(1, len(vs))
    return {"yaw_over_cap": share(yaw_steps, lambda v: abs(v) > my),
            "pitch_over_cap": share(pitch_steps, lambda v: abs(v) > mp),
            "yaw_moving_below_min": share(moving(yaw_steps), lambda v: abs(v) < low["yaw"]),
            "pitch_moving_below_min": share(moving(pitch_steps), lambda v: abs(v) < low["pitch"]),
            "yaw_cap_deg": my, "pitch_cap_deg": mp, "min_step_deg": low, "caveat": caveat()}
