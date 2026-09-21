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


def test_search_relevels_the_camera_and_engage_does_not_walk_blind():
    from agent.intents import Search
    c, ry = Controller(), []
    for i in range(60 * 6):
        ry.append(c.step(State(t=i / 60, frame=(1280, 720), detections=[]), Search())["ry"])
    assert max(ry) == 1.0 and min(ry) == -0.5 and ry[-1] == 0.0          # up into the clamp, measured way down, then still
    c, d = Controller(), Detection(ENEMY, (610, 330, 670, 400), 0.9)
    pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[d] if i < 10 else []), Engage(d)) for i in range(120)]
    assert pads[5]["ly"] == 1.0 and all(p["ly"] == 0.0 for p in pads[10:])


def test_a_target_only_the_brain_saw_is_turned_toward_but_never_walked_at():
    from agent.intents import Search
    c, far_left = Controller(), Detection(ENEMY, (60, 330, 110, 400), 0.9)     # outside the aim crop: reflex dets stay empty
    pads = []
    for i in range(180):                                                        # the brain flips Search / Engage, as it did live
        intent = Search() if (i // 12) % 4 == 3 else Engage(far_left)
        pads.append(c.step(State(t=i / 60, frame=(1280, 720), detections=[]), intent))
    assert all(p["ly"] == 0.0 for p in pads) and not any(_pressed(p) for p in pads)
    assert pads[1]["rx"] < 0                                                    # but it does turn toward it


def test_forward_movement_only_on_steps_with_a_measured_box():
    from agent.intents import Search
    d, c = Detection(ENEMY, (610, 330, 670, 400), 0.9), Controller()
    for i in range(240):
        seen = (i // 7) % 2 == 0                                                # the box flickers, as live detectors do
        pad = c.step(State(t=i / 60, frame=(1280, 720), detections=[d] if seen else []), Engage(d))
        assert pad["ly"] == (1.0 if seen else 0.0), i
    c = Controller()
    assert all(c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), Search())[k] == 0.0
               for i in range(120) for k in ("lx", "ly"))


def test_a_whole_frame_target_is_re_aimed_from_every_new_measurement_until_the_crop_confirms_it():
    """trackerlive30: seeded once from the brain's whole-frame target, the turn stopped where the controller's own model said it had
    arrived, the bot stayed 630 px right, and the 1 s unconfirmed limit then stopped turning: 4.9 s standing still. Each new measurement
    (a new decision) now re-aims the track at the camera angle of the frame it was measured in, so the turn goes on while the bot is off."""
    c, F, dt = Controller(), (2560, 1440), 1 / 60
    right = lambda: Detection(ENEMY, (1756.0, 355.0, 2058.0, 916.0), 0.9)     # the respawned bot, 630 px right of the crosshair
    t, rx, intent = 0.0, [], Engage(right())
    for k in range(120):                                                       # 2 s; the bot never comes in (a recorded frame)
        if k % 6 == 0:
            intent = Engage(right())                                            # a new decision: a new measurement, still 630 px right
            it = t
        rx.append(c.step(State(t=t, frame=F, detections=[]), intent, intent_t=it)["rx"])
        t += dt
    assert all(v > 0 for v in rx[-60:])                                         # still turning toward it a second and more in
    old, t = Controller(), 0.0
    first = Engage(right())
    olds = []
    for k in range(120):                                                       # the same, with the brain's target never re-measured
        olds.append(old.step(State(t=t, frame=F, detections=[]), first, intent_t=0.0)["rx"])
        t += dt
    assert sum(1 for v in olds[-60:] if abs(v) > 0.02) == 0                     # the old behaviour: stopped


def test_a_target_the_crop_confirmed_is_not_moved_by_the_brains_measurements():
    c, F = Controller(), (2560, 1440)
    box = Detection(ENEMY, (1230.0, 520.0, 1330.0, 920.0), 0.9)                # on the crosshair, in the crop
    for k in range(10):
        c.step(State(t=k / 60, frame=F, detections=[box]), Engage(box), intent_t=k / 60)
    yaw = c.track.yaw
    far = Detection(ENEMY, (2000.0, 520.0, 2100.0, 920.0), 0.9)                # a stale whole-frame box elsewhere
    c.step(State(t=10 / 60, frame=F, detections=[box]), Engage(far), intent_t=0.0)
    assert c.track.confirmed and abs(c.track.yaw - yaw) < 1.0


def test_the_brains_target_is_placed_at_the_camera_angle_of_the_frame_it_was_measured_in():
    """The decision runs 40-60 ms behind the reflex step; at a 172 deg/s search turn that is 7-10 degrees of camera. The bearing uses the
    camera the measured frame showed, not the current one."""
    from agent.intents import Search
    c, F = Controller(), (2560, 1440)
    t = 0.0
    for k in range(18):                                                         # 0.3 s of search: the camera is turning right (it pauses 0.3-0.5 s)
        c.step(State(t=t, frame=F, detections=[]), Search())
        t += 1 / 60
    measured_t = t - 0.1                                                        # the decision's frame, 100 ms back
    box = Detection(ENEMY, (1230.0, 520.0, 1330.0, 920.0), 0.9)                # dead ahead in THAT frame
    c.step(State(t=t, frame=F, detections=[]), Engage(box), intent_t=measured_t)
    then = c._cam_at(measured_t - c.cal.latency_s)[0]
    now = c._cam_at(t - c.cal.latency_s)[0]
    assert abs(now - then) > 5.0                                                # the camera really moved in between
    assert abs(c.track.yaw - then) < 0.5                                        # and the target sits where it was, not where we look now


def test_when_the_brain_switches_target_the_controller_aims_at_the_new_one_at_once():
    """stall30: the controller kept the previous target's confirmed track, never re-aimed at the new whole-frame target (that path is for
    unconfirmed tracks), and counted the stale track as lost: 1.1 s with no stick while the brain engaged a bot 650 px to the right."""
    c, F = Controller(), (2560, 1440)
    old = Detection(ENEMY, (1230.0, 520.0, 1330.0, 920.0), 0.9, track=3)          # the last target, confirmed in the crop
    for k in range(10):
        c.step(State(t=k / 60, frame=F, detections=[old]), Engage(old), intent_t=k / 60)
    t = 70 / 60                                                                  # a second later it is gone; the brain picks another
    new = Detection(ENEMY, (1882.0, 594.0, 1978.0, 750.0), 0.9, track=15)        # 650 px right, only in the whole-frame search
    pad = c.step(State(t=t, frame=F, detections=[]), Engage(new), intent_t=t - 0.05)
    assert pad["rx"] > 0.3 and not c.track.confirmed


def test_he_never_walks_at_a_box_beyond_the_kits_reach():
    """handoff30: a confirmed, crop-measured 36 px dummy ~45 m off (0.025 of the frame) drew 0.8 s of forward walk off the plaza's edge.
    At the reach line (brain.RANGES.reach_h, 40 m) the walk stops; just inside it the walk stands."""
    for h, walks in ((18, False), (23, False), (24, True), (70, True)):      # on 720: 23 px = 0.0319, 24 px = 0.0333
        d, c = Detection(ENEMY, (630, 360 - h / 2, 650, 360 + h / 2), 0.9), Controller()
        pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), Engage(d)) for i in range(30)]
        assert any(p["ly"] == 1.0 for p in pads) is walks, h
