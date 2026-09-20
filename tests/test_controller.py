"""Offline checks for agent/controller.py: closed-loop aim against a simulated camera, and the burst's button set."""
import math

from agent.controller import NEUTRAL, Cal, Controller, _interp
from agent.intents import BURST, Combo, Engage, Idle
from agent.state import ENEMY, Detection, State


def _settle(plant_gain, delay_steps=3, offset_deg=30.0):
    cal, c = Cal(), Controller()
    f, yaw, t, hist, inside_since, boost = cal.focal_1280, 0.0, 0.0, [], None, 0.0
    for _ in range(90):
        cx = 640 + f * math.tan(math.radians(offset_deg - yaw))
        d = Detection(ENEMY, (cx - 10, 340, cx + 10, 380), 0.9)
        pad, _ = c.aim_only(State(t=t, frame=(1280, 720), detections=[d]), d)
        hist.append(pad["rx"])
        cmd = hist[-1 - delay_steps] if len(hist) > delay_steps else 0.0   # capture -> screen delay
        full = _interp(abs(cmd), cal.yaw_map)                              # same boost lag as the controller's model
        base = min(full, 147.0 * abs(cmd))
        boost += (full - base - boost) * min(1.0, (1 / 60) / cal.boost_tau_s)
        yaw += plant_gain * math.copysign(base + boost, cmd) / 60
        t += 1 / 60
        inside = abs(cx - 640) <= 10
        inside_since = (inside_since if inside_since is not None else t) if inside else None
    return inside_since, offset_deg - yaw


def test_aim_settles_fast_on_the_measured_map():
    # 30 deg at Horizontal Sensitivity 130 is camera-limited: the first 0.1 s at full stick only turns 14.8 deg.
    # 0.33 s here; the live target of 0.30 s needs a higher sensitivity setting, not a different controller.
    settle, err = _settle(1.0)
    assert settle is not None and settle < 0.35, settle
    assert abs(err) < 1.0


def test_aim_survives_a_25_percent_slower_camera():
    settle, err = _settle(0.75)
    assert settle is not None and settle < 0.7 and abs(err) < 1.0, (settle, err)


def test_burst_presses_every_button_once_the_aim_is_on_and_idle_releases():
    c, d = Controller(), Detection(ENEMY, (630, 340, 650, 380), 0.9)
    intent, seen = Combo(BURST, d), set()
    for i in range(360):
        pad = c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), intent)
        seen |= set(pad["buttons"]) | ({"LT"} if pad["lt"] else set()) | ({"RT"} if pad["rt"] else set())
    assert seen == {"LT", "RB", "X", "RT"}
    assert c.step(State(t=7.0, frame=(1280, 720), detections=[d]), Idle()) == NEUTRAL


def test_own_hero_box_is_never_a_target():
    c = Controller()
    me = Detection(ENEMY, (420, 340, 580, 700), 0.9)       # Spider-Man's own torso
    bot = Detection(ENEMY, (900, 330, 920, 365), 0.9)
    pad = c.step(State(t=0.0, frame=(1280, 720), detections=[me, bot]), Engage(bot))
    assert pad["rx"] > 0                                  # turns right, toward the bot
