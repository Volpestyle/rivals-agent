"""Offline checks for agent/controller.py: closed-loop aim against a simulated camera, and the burst's button set."""
import math

from agent.controller import NEUTRAL, Cal, Controller, _interp
from agent.intents import BURST, Combo, Engage, Idle
from agent.state import ENEMY, Detection, State


def _settle(plant_gain, delay_steps=3, offset_deg=30.0):
    cal, c = Cal(), Controller()
    f, yaw, t, hist, inside_since = cal.focal_1280, 0.0, 0.0, [], None
    for _ in range(90):
        cx = 640 + f * math.tan(math.radians(offset_deg - yaw))
        d = Detection(ENEMY, (cx - 10, 340, cx + 10, 380), 0.9)
        pad, _ = c.aim_only(State(t=t, frame=(1280, 720), detections=[d]), d)
        hist.append(pad["rx"])
        cmd = hist[-1 - delay_steps] if len(hist) > delay_steps else 0.0   # capture -> screen delay
        yaw += plant_gain * math.copysign(_interp(abs(cmd), cal.yaw_map), cmd) / 60
        t += 1 / 60
        inside = abs(cx - 640) <= 10
        inside_since = (inside_since if inside_since is not None else t) if inside else None
    return inside_since, offset_deg - yaw


def test_aim_settles_under_300ms_on_the_measured_map():
    settle, err = _settle(1.0)
    assert settle is not None and settle < 0.30, settle
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


def test_a_bot_drawn_behind_the_hero_is_still_aimed_at():
    # live finding: the bot nearest the crosshair stood behind Spider-Man's own body and a player-region filter froze the aim
    c, bot = Controller(), Detection(ENEMY, (440, 332, 596, 437), 0.9)
    pad = c.step(State(t=0.0, frame=(1280, 720), detections=[bot]), Engage(bot))
    assert pad["rx"] < 0                                  # turns left, onto it


def _pressed(pad):
    return set(pad["buttons"]) | ({"LT"} if pad["lt"] else set()) | ({"RT"} if pad["rt"] else set())


def test_nothing_is_pressed_on_the_first_steps_even_dead_on_target():
    c, d = Controller(), Detection(ENEMY, (630, 300, 650, 420), 0.9)   # tall enough to read as "near": Engage wants X
    pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), Engage(d)) for i in range(12)]
    assert all(not _pressed(p) for p in pads[:4]), [_pressed(p) for p in pads[:4]]
    assert any(_pressed(p) for p in pads[4:])


def test_boxes_that_do_not_persist_never_earn_a_press():
    import random
    rng, c = random.Random(0), Controller()
    for i in range(240):   # a different junk box every step, plus frames with none, as the hedges gave
        x, y = rng.uniform(100, 1180), rng.uniform(80, 560)
        dets = [] if i % 3 == 0 else [Detection(ENEMY, (x, y, x + 60, y + 130), 0.9)]
        target = dets[0] if dets else Detection(ENEMY, (630, 300, 650, 420), 0.9)
        for intent in (Engage(target), Combo(BURST, target)):
            assert not _pressed(c.step(State(t=i / 60, frame=(1280, 720), detections=dets), intent))


def test_a_sliver_or_a_frame_sized_box_is_not_a_target():
    for box in ((630, 358, 650, 362), (0, 0, 1280, 700)):
        c, d = Controller(), Detection(ENEMY, box, 0.9)
        assert all(not _pressed(c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), Engage(d))) for i in range(30))


def _run(c, frames, intent_for):
    out = []
    for i, dets in frames:
        target = dets[0] if dets else intent_for
        out.append(c.step(State(t=i / 60, frame=(1280, 720), detections=dets), Engage(target)))
    return out


def test_tracker_coasts_through_the_hit_flash_and_stays_armed():
    d = Detection(ENEMY, (610, 330, 670, 400), 0.9)                 # mid range: Engage fires Web Clusters
    c = Controller()
    seen = _run(c, [(i, [d]) for i in range(30)], d)
    assert any(p["lt"] for p in seen)                                # we attacked
    last_attack = max(i for i, p in enumerate(seen) if p["lt"])
    bearing = c.track.yaw
    blind = _run(c, [(i, []) for i in range(last_attack + 1, last_attack + 13)], d)   # 0.2 s with no outline
    assert c.track is not None and abs(c.track.yaw - bearing) < 0.5 and c.stable >= 5
    back = _run(c, [(i, [d]) for i in range(last_attack + 13, last_attack + 40)], d)
    assert any(p["lt"] for p in back[:22])                           # fires again without re-arming from zero


def test_a_blackout_with_no_attack_behind_it_disarms():
    d = Detection(ENEMY, (610, 330, 670, 400), 0.9)
    c = Controller()
    c.next_shot_t = 1e9                                              # never attacks
    _run(c, [(i, [d]) for i in range(30)], d)
    _run(c, [(i, []) for i in range(30, 42)], d)
    assert c.stable == 0
