"""Exploration around a LivePolicy's own decode, for online RL (VUH-1321).

Action gates. Each live action's hold/press/release gate is sampled instead of thresholded:

    fire = (logit(p) - logit(threshold)) / temperature + L > 0,   L ~ Logistic(0, 1)

so P(fire) = sigmoid((logit p - logit threshold) / temperature). The sampled 0/1 gates then go through the same
`executor.decode_step` the policy uses (rises, taps, the live mask), so exploration can only produce actions the
deterministic decode could produce: never a masked action, never a new control. temperature 0 is the deterministic
decode, bit for bit.

Options (off unless option_rate_hz > 0). A BC policy that idles from a still start has hold probabilities far below
its thresholds (bc2-mix399-s0 on recorded range frames: every action fires on < 1% of steps at temperature 0.5), so
gate sampling alone barely explores. An option holds one live action (weights OPTION_WEIGHTS) for a random 0.2-0.8 s,
started at option_rate_hz on average and ORed into that action's hold gate. It goes through the same decode_step and
mask, so it too can only produce what the deterministic decode could: one more held live action, for a bounded time.

Camera (off unless cam_temperature > 0 or turn_rate_hz > 0). Without it the RL arm's camera is the BC decode and RL
cannot discover aiming (first live sitting: mean |yaw| 0.05-0.22 deg per step).
  - cam_temperature: yaw and pitch classes are sampled from the policy's own camera distribution sharpened or flattened
    by the temperature (p ** (1/T)), instead of its mean/median decode.
  - Turn options: at turn_rate_hz, when an enemy-colour outline is visible (policy.bc2.model.green_profile on the
    144x256 global view: the nearest marked column's bearing, the HUD and hero regions masked), yaw toward it at a random
    0.6-2.5 deg per step for up to 0.15-0.5 s, ending early once it is centred or lost. Pitch stays the policy's.
Every camera request stays a finite number of degrees within the policy's own class range (|deg| <= vocab.CLAMP_DEG);
the runner's CameraPulses turns it into measured stick knots with their caps, exactly as for the BC decode.

The wrapper owns no capture or pad IO. It writes one JSONL row per step (probabilities, deterministic and executed
actions and camera, options) for the update.
"""
from __future__ import annotations

import json
import math
import random


def _logit(p, eps=1e-6):
    p = min(1 - eps, max(eps, p))
    return math.log(p / (1 - p))


def gate(p, threshold, temperature, u):
    """One sampled gate. u is uniform (0, 1); temperature 0 is p >= threshold."""
    if temperature <= 0:
        return int(p >= threshold)
    noise = math.log(u / (1 - u))              # standard logistic
    return int((_logit(p) - _logit(threshold)) / temperature + noise > 0)


def sample_class(probs, temperature, u):
    """A camera class from probs ** (1 / temperature), renormalised; u is uniform [0, 1)."""
    w = [max(p, 0.) ** (1. / temperature) for p in probs]
    total = sum(w)
    if not total > 0:
        return max(range(len(probs)), key=lambda k: probs[k])
    acc = 0.
    for k, x in enumerate(w):
        acc += x / total
        if u < acc:
            return k
    return len(w) - 1


def green_bearing(frame_bgr):
    """(visible, bearing in [-1, 1] of half-width) of the nearest enemy-colour column in the global view."""
    import cv2
    import torch
    from policy.bc2.model import green_profile
    small = cv2.resize(frame_bgr, (256, 144), interpolation=cv2.INTER_AREA)[..., ::-1].copy()
    g = green_profile(torch.from_numpy(small)[None])[0]
    mass = math.expm1(float(g[-3]))
    return mass > 0, float(g[-1])


OPTION_WEIGHTS = {"spider_power": .22, "web_cluster": .14, "amazing_combo": .08, "get_over_here": .08, "jump": .12,
                  "web_swing": .06, "move_forward": .10, "move_left": .07, "move_right": .07, "move_back": .06}
OPTION_S = (.2, .8)
TURN_S = (.15, .5)
TURN_DEG = (.6, 2.5)             # per 1/30 s step: well inside vocab.REPS; the runner's measured knots cap the stick
CENTRED = .03                    # of half-width


def _rate(x, name):
    if not (isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x <= 2):
        raise ValueError(f"{name} must be in [0, 2]")
    return float(x)


class ExploringPolicy:
    """Wraps a LivePolicy: same reset/step/close, same Step type, sampled action gates and camera."""

    def __init__(self, base, *, temperature=0.0, seed=0, log_path=None, option_rate_hz=0.0, cam_temperature=0.0,
                 turn_rate_hz=0.0, bearing=green_bearing):
        self.temperature = _rate(temperature, "temperature")
        self.option_rate_hz = _rate(option_rate_hz, "option_rate_hz")
        self.cam_temperature = _rate(cam_temperature, "cam_temperature")
        self.turn_rate_hz = _rate(turn_rate_hz, "turn_rate_hz")
        self.base, self.seed, self.bearing = base, seed, bearing
        self.rng = random.Random(seed)
        self.log = open(log_path, "w", encoding="utf-8", buffering=1) if log_path else None
        self.episode = 0
        # The live runner's warm-up calls step() before reset() (agent/learned_runner.py warm_finder): start from no holds.
        self.prev_exec = [0] * len(base.names)
        self.option, self.option_until, self.t_prev = None, -math.inf, None
        self.turn = None                        # (speed deg/step, until)
        self._cams = None
        if self.cam_temperature > 0 and hasattr(base, "_bc2_predict"):
            original = base._bc2_predict

            def capture(frame, t=None):         # keep the policy's camera distribution for sampling
                probs, cams = original(frame, t)
                self._cams = cams
                return probs, cams
            base._bc2_predict = capture

    def __getattr__(self, name):                # anything else the runner reads comes from the base policy
        return getattr(self.base, name)

    def reset(self):
        self.base.reset()
        self.prev_exec = [0] * len(self.base.names)
        self.option, self.option_until, self.t_prev = None, -math.inf, None
        self.turn, self._cams = None, None
        self.episode += 1
        if self.log:
            self.log.write(json.dumps({"event": "reset", "episode": self.episode, "temperature": self.temperature,
                                       "seed": self.seed, "option_rate_hz": self.option_rate_hz,
                                       "cam_temperature": self.cam_temperature,
                                       "turn_rate_hz": self.turn_rate_hz}) + "\n")

    def step(self, frame_bgr, t=None):
        from policy.range_bc import executor, vocab
        self._cams = None
        step = self.base.step(frame_bgr, t=t)
        now, dt = self._clock(t)
        option = self._option(now, dt)
        turn = self._turn(frame_bgr, now, dt)
        explore_actions = self.temperature > 0 or option is not None
        explore_camera = (self.cam_temperature > 0 and self._cams is not None) or turn is not None
        if not explore_actions and not explore_camera:
            self.prev_exec = [int(step.held[n]) for n in self.base.names]
            self._write(step, t, step.held, step.press, step.release, None, step.yaw_deg, step.pitch_deg, None)
            return step
        names = self.base.names
        held, press, release = ([int(step.held[n]) for n in names], [int(step.press[n]) for n in names],
                                [int(step.release[n]) for n in names])
        if explore_actions:
            levels, mask = self.base.levels, self.base.mask
            gates = [[gate(p, levels[i], self.temperature, self.rng.random() or 1e-12) for p in step.probs[name]]
                     for i, name in enumerate(names)]
            if option is not None and option in names:
                gates[names.index(option)][0] = 1          # the option holds its action; decode_step applies the mask
            # One decode over all actions (independent per action), against the holds actually executed last step.
            held, press, release = executor.decode_step([g[0] for g in gates], [g[1] for g in gates],
                                                        [g[2] for g in gates], self.prev_exec, mask, threshold=.5)
            # The next step's rise/tap logic (and any model reading previous actions) must see what was executed.
            self.base.prev.update(held=list(held), press=list(press), release=list(release))
        self.prev_exec = list(held)
        yaw, pitch = step.yaw_deg, step.pitch_deg
        if self.cam_temperature > 0 and self._cams is not None:
            c = vocab.CAMERA_CLASSES
            # LivePolicy's bc2 path returns [2, C] (one row per axis); a flat [2C] list is split the same way
            # LivePolicy.step does.
            yaw_p, pitch_p = self._cams if len(self._cams) == 2 else (self._cams[:c], self._cams[c:2 * c])
            cy = sample_class(yaw_p, self.cam_temperature, self.rng.random())
            cp = sample_class(pitch_p, self.cam_temperature, self.rng.random())
            yaw, pitch = vocab.class_degrees(cy), vocab.class_degrees(cp)
        if turn is not None:
            yaw = turn
        if not (math.isfinite(float(yaw)) and math.isfinite(float(pitch))):
            yaw, pitch = step.yaw_deg, step.pitch_deg          # never clamp a NaN into a full-range request
        yaw = max(-vocab.CLAMP_DEG, min(vocab.CLAMP_DEG, float(yaw)))
        pitch = max(-vocab.CLAMP_DEG, min(vocab.CLAMP_DEG, float(pitch)))
        named = lambda bits: {n: bool(b) for n, b in zip(names, bits)}
        explored = type(step)(**{**step.as_dict(), "held": named(held), "press": named(press),
                                 "release": named(release), "yaw_deg": yaw, "pitch_deg": pitch,
                                 "yaw_deg_s": yaw / (1 / 30), "pitch_deg_s": pitch / (1 / 30)})
        self._write(step, t, explored.held, explored.press, explored.release, option, yaw, pitch, turn)
        return explored

    def _clock(self, t):
        import time
        now = time.perf_counter() if t is None else t
        dt = 0. if self.t_prev is None else min(max(now - self.t_prev, 0.), .5)
        self.t_prev = now
        return now, dt

    def _started(self, rate, dt):
        return rate > 0 and self.rng.random() < 1 - math.exp(-rate * dt)

    def _option(self, now, dt):
        """The action an option is holding at capture time `now`; new options start as a Poisson process."""
        if self.option is not None and now >= self.option_until:
            self.option = None
        if self.option is None and self._started(self.option_rate_hz, dt):
            live = [n for n, m in zip(self.base.names, self.base.mask) if m and n in OPTION_WEIGHTS]
            if live:
                self.option = self.rng.choices(live, weights=[OPTION_WEIGHTS[n] for n in live])[0]
                self.option_until = now + self.rng.uniform(*OPTION_S)
        return self.option

    def _turn(self, frame, now, dt):
        """Degrees of yaw this step from a turn option toward the nearest enemy outline, or None."""
        if self.turn is not None and now >= self.turn[1]:
            self.turn = None
        if self.turn is None and not self._started(self.turn_rate_hz, dt):
            return None
        visible, bearing = self.bearing(frame)
        if not visible or abs(bearing) < CENTRED:
            self.turn = None                     # nothing to turn to, or already on it
            return None
        if self.turn is None:
            self.turn = (self.rng.uniform(*TURN_DEG), now + self.rng.uniform(*TURN_S))
        return math.copysign(self.turn[0], bearing)

    def _write(self, step, t, held, press, release, option, yaw, pitch, turn):
        if not self.log:
            return
        live = [n for n, m in zip(self.base.names, self.base.mask) if m]
        self.log.write(json.dumps({
            "event": "step", "episode": self.episode, "index": step.index, "t": t,
            "probs": {n: step.probs[n] for n in live},
            "det": {"held": [n for n in live if step.held[n]], "press": [n for n in live if step.press[n]],
                    "yaw_deg": step.yaw_deg, "pitch_deg": step.pitch_deg},
            "exec": {"held": [n for n in live if held[n]], "press": [n for n in live if press[n]],
                     "release": [n for n in live if release[n]], "yaw_deg": yaw, "pitch_deg": pitch},
            "option": option, "turn_deg": turn}) + "\n")

    def close(self):
        try:
            self.base.close()
        finally:
            if self.log:
                self.log.close()
