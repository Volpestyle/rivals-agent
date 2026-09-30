"""Exploration around a LivePolicy's own decode, for online RL (VUH-1321).

Each live action's hold/press/release gate is sampled instead of thresholded:

    fire = (logit(p) - logit(threshold)) / temperature + L > 0,   L ~ Logistic(0, 1)

so P(fire) = sigmoid((logit p - logit threshold) / temperature). The sampled 0/1 gates then go through the same
`executor.decode_step` the policy uses (rises, taps, the live mask), so exploration can only produce actions the
deterministic decode could produce: never a masked action, never a new control. temperature 0 is the deterministic
decode, bit for bit. The camera is left exactly as the policy decodes it.

Options (off unless option_rate_hz > 0). A BC policy that idles from a still start has hold probabilities far below
its thresholds (bc2-mix399-s0 on recorded range frames: every action fires on < 1% of steps at temperature 0.5), so
gate sampling alone barely explores. An option holds one live action (weights OPTION_WEIGHTS) for a random 0.2-0.8 s,
started at option_rate_hz on average and ORed into that action's hold gate. It goes through the same decode_step and
mask, so it too can only produce what the deterministic decode could: one more held live action, for a bounded time.

The wrapper owns no capture or pad IO. It writes one JSONL row per step (probabilities, thresholds, deterministic and
sampled decisions) for the update.
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


OPTION_WEIGHTS = {"spider_power": .22, "web_cluster": .14, "amazing_combo": .08, "get_over_here": .08, "jump": .12,
                  "web_swing": .06, "move_forward": .10, "move_left": .07, "move_right": .07, "move_back": .06}
OPTION_S = (.2, .8)


class ExploringPolicy:
    """Wraps a LivePolicy: same reset/step/close, same Step type, sampled action gates."""

    def __init__(self, base, *, temperature=0.0, seed=0, log_path=None, option_rate_hz=0.0):
        if not (isinstance(option_rate_hz, (int, float)) and math.isfinite(option_rate_hz) and 0 <= option_rate_hz <= 2):
            raise ValueError("option_rate_hz must be in [0, 2]")
        self.option_rate_hz = float(option_rate_hz)
        self.option, self.option_until, self.t_prev = None, -math.inf, None
        if not (isinstance(temperature, (int, float)) and math.isfinite(temperature) and 0 <= temperature <= 2):
            raise ValueError("temperature must be in [0, 2]")
        self.base, self.temperature, self.seed = base, float(temperature), seed
        self.rng = random.Random(seed)
        self.log = open(log_path, "w", encoding="utf-8", buffering=1) if log_path else None
        self.episode = 0
        # The live runner's warm-up calls step() before reset() (agent/learned_runner.py warm_finder): start from no holds.
        self.prev_exec = [0] * len(base.names)

    def __getattr__(self, name):                # anything else the runner reads comes from the base policy
        return getattr(self.base, name)

    def reset(self):
        self.base.reset()
        self.prev_exec = [0] * len(self.base.names)
        self.option, self.option_until, self.t_prev = None, -math.inf, None
        self.episode += 1
        if self.log:
            self.log.write(json.dumps({"event": "reset", "episode": self.episode,
                                       "temperature": self.temperature, "seed": self.seed,
                                       "option_rate_hz": self.option_rate_hz}) + "\n")

    def step(self, frame_bgr, t=None):
        from policy.range_bc import executor
        step = self.base.step(frame_bgr, t=t)
        option = self._option(t)
        if self.temperature <= 0 and option is None:
            self.prev_exec = [int(step.held[n]) for n in self.base.names]
            self._write(step, t, step.held, step.press, step.release)
            return step
        names, levels, mask = self.base.names, self.base.levels, self.base.mask
        gates = [[gate(p, levels[i], self.temperature, self.rng.random() or 1e-12) for p in step.probs[name]]
                 for i, name in enumerate(names)]
        if option is not None and option in names:
            gates[names.index(option)][0] = 1              # the option holds its action; decode_step applies the mask
        # One decode over all actions (it is independent per action), against the holds actually executed last step.
        held, press, release = executor.decode_step([g[0] for g in gates], [g[1] for g in gates],
                                                    [g[2] for g in gates], self.prev_exec, mask, threshold=.5)
        # The next step's rise/tap logic (and any model reading previous actions) must see what was executed.
        self.base.prev.update(held=list(held), press=list(press), release=list(release))
        self.prev_exec = list(held)
        named = lambda bits: {n: bool(b) for n, b in zip(names, bits)}
        explored = type(step)(**{**step.as_dict(), "held": named(held), "press": named(press),
                                 "release": named(release)})
        self._write(step, t, explored.held, explored.press, explored.release, option)
        return explored

    def _option(self, t):
        """The action an option is holding at capture time t; new options start as a Poisson process."""
        import time
        now = time.perf_counter() if t is None else t
        dt = 0. if self.t_prev is None else min(max(now - self.t_prev, 0.), .5)
        self.t_prev = now
        if self.option is not None and now >= self.option_until:
            self.option = None
        if self.option is None and self.option_rate_hz > 0 and self.rng.random() < 1 - math.exp(-self.option_rate_hz * dt):
            live = [n for n, m in zip(self.base.names, self.base.mask) if m and n in OPTION_WEIGHTS]
            if live:
                self.option = self.rng.choices(live, weights=[OPTION_WEIGHTS[n] for n in live])[0]
                self.option_until = now + self.rng.uniform(*OPTION_S)
        return self.option

    def _write(self, step, t, held, press, release, option=None):
        if not self.log:
            return
        live = [n for n, m in zip(self.base.names, self.base.mask) if m]
        self.log.write(json.dumps({
            "event": "step", "episode": self.episode, "index": step.index, "t": t,
            "probs": {n: step.probs[n] for n in live},
            "det": {"held": [n for n in live if step.held[n]], "press": [n for n in live if step.press[n]]},
            "exec": {"held": [n for n in live if held[n]], "press": [n for n in live if press[n]],
                     "release": [n for n in live if release[n]]},
            "option": option, "yaw_deg": step.yaw_deg, "pitch_deg": step.pitch_deg}) + "\n")

    def close(self):
        try:
            self.base.close()
        finally:
            if self.log:
                self.log.close()
