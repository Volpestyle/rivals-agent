"""Offline checks for agent/controller.py: closed-loop aim against a simulated camera, and the burst's button set."""
import math
from dataclasses import replace

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


def test_he_never_walks_at_a_box_beyond_the_engagement_cap():
    """handoff30: a confirmed, crop-measured 36 px dummy ~45 m off (0.025 of the frame) drew 0.8 s of forward walk off the plaza's edge.
    At the cap (brain.RANGES.reach_h, 40 m on the height ruler) the walk stops; just inside it the walk stands. Not a ground check."""
    for h, walks in ((18, False), (23, False), (24, True), (70, True)):      # on 720: 23 px = 0.0319, 24 px = 0.0333
        d, c = Detection(ENEMY, (630, 360 - h / 2, 650, 360 + h / 2), 0.9), Controller()
        pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[d]), Engage(d)) for i in range(30)]
        assert any(p["ly"] == 1.0 for p in pads) is walks, h


def test_a_held_target_whose_own_measured_distance_passes_the_cap_is_not_walked_at():
    """Review of 5aef664: id 4 acquired at 39 m with a 54 px crop box; the next frame the SAME held id reports 41 m. The brain keeps Engage
    by its id (held targets are not re-acquired), and the walk read only the box height: ly 1.0 at a target known to be past the cap.
    The cap reads the measured box's own distance when it has one; with none, the height, as before."""
    from agent.brain import Memory, decide, in_reach
    m, c, frame = Memory(), Controller(), (2560, 1440)
    for i in range(3):
        s = State(t=i / 10, frame=frame, detections=[Detection(ENEMY, (1270, 693, 1290, 747), 0.9, distance=39.0, track=4)])
        intent = decide(s, m)
        pad = c.step(s, intent, intent_t=s.t)
    assert isinstance(intent, Engage) and pad["ly"] == 1.0
    d = Detection(ENEMY, (1270, 693, 1290, 747), 0.9, distance=41.0, track=4)
    s = State(t=0.3, frame=frame, detections=[d])
    intent = decide(s, m)
    assert not in_reach(d, s) and isinstance(intent, Engage)
    assert c.step(s, intent, intent_t=s.t)["ly"] == 0.0
    d = Detection(ENEMY, (1270, 700, 1290, 740), 0.9, distance=20.0, track=4)    # 40 px, under the height line, but measured at 20 m
    s = State(t=0.4, frame=frame, detections=[d])
    assert c.step(s, decide(s, m), intent_t=s.t)["ly"] == 1.0


def test_a_drifted_track_is_never_re_seeded_onto_another_object():
    """reach30 t 24.46: the held target (the bot, id 44, whole-frame only, far left) was unseen for 0.25 s; the controller re-seeded on the
    nearest crop box, the door's edge (id 51), counted it measured and confirmed, turned RIGHT and walked at it."""
    bot = Detection(ENEMY, (20, 300, 80, 420), 0.9, track=44)                 # left of the aim crop: the brain's measurement only
    door = Detection(ENEMY, (900, 250, 960, 450), 0.9, track=51)
    c = Controller()
    pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[door] if i > 12 else []), Engage(bot)) for i in range(60)]
    assert all(p["ly"] == 0.0 for p in pads) and all(p["rx"] <= 0.0 for p in pads)
    assert not c.track.confirmed


def test_a_box_of_another_size_is_not_the_target():
    """reach30 t 23.86-24.16: the whole-frame bot's track (183 px) took the 30-40 px distant boxes crossing its bearing as its measurement
    and aimed after them. Boxes more than the tracker's SIZE_RATIO apart are not the same object."""
    bot = Detection(ENEMY, (610, 314, 670, 406), 0.9, track=44)                # 92 px on 720 (reach30: 183 on 1440), at the crosshair
    speck = Detection(ENEMY, (632, 342, 648, 360), 0.9, track=45)              # 18 px (36 on 1440), right where she is predicted
    c = Controller()
    for i in range(20):
        c.step(State(t=i / 60, frame=(1280, 720), detections=[speck]), Engage(bot))
    assert not c.track.confirmed and not c._measured
    c.step(State(t=0.4, frame=(1280, 720), detections=[replace(bot, track=46)]), Engage(bot))   # her own size under another id: aimed at
    assert c.track.confirmed


def test_he_walks_only_at_the_held_targets_own_box():
    """A box measured for the target but carrying another tracker id is aimed at and may be pressed on, but is not walked at. Boxes with
    no ids (a finder run without the tracker) keep the old rule."""
    held = Detection(ENEMY, (610, 330, 670, 400), 0.9, track=7)
    for box, walks in ((held, True), (replace(held, track=8), False), (replace(held, track=None), True)):
        c = Controller()
        pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[box]), Engage(held)) for i in range(30)]
        assert any(p["ly"] == 1.0 for p in pads) is walks, box.track


def test_the_held_targets_own_id_is_its_measurement_wherever_the_bearing_put_it():
    """The tracker matches through the camera's turn (it models it); the controller's bearing gate does not. A box carrying the held id is
    the target even far off the predicted bearing."""
    held = Detection(ENEMY, (610, 330, 670, 400), 0.9, track=7)
    c = Controller()
    for i in range(10):
        c.step(State(t=i / 60, frame=(1280, 720), detections=[held]), Engage(held))
    moved = replace(held, bbox=(1110, 330, 1170, 400))                         # 500 px right in one step
    c.step(State(t=10 / 60, frame=(1280, 720), detections=[moved]), Engage(held))
    assert c._measured and c._measured_as == 7


def test_another_ids_box_never_arms_or_starts_an_attack_for_the_held_target():
    """Review of d5818cf: WebStrike(id 1, tagged) with only id 2 at the same bearing and size (tag unknown) pressed RB on steps 4-5. The
    tag is id 1's: whether RB pulls or zips at id 2 is unknown. Another id's box may be aimed at, but earns no arming, no press, no walk."""
    from agent.intents import WebStrike
    held, other = Detection(ENEMY, (580, 260, 700, 460), 0.9, track=1, tagged=True), Detection(ENEMY, (580, 260, 700, 460), 0.9, track=2)
    for intent in (WebStrike(held), Engage(held)):
        c = Controller()
        pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[other]), intent) for i in range(30)]
        assert not any(_pressed(p) or p["ly"] for p in pads) and c.stable == 0, type(intent).__name__
    c = Controller()                                                            # the held target's own box: the strike goes out
    pads = [c.step(State(t=i / 60, frame=(1280, 720), detections=[held]), WebStrike(held)) for i in range(30)]
    assert any("RB" in p["buttons"] for p in pads)


def _plaza30_71(c):
    """plaza30 t 28.286-28.403, recorded crop boxes (2560x1440; every one cut by the crop's right edge at x 1760): the tracker gave the
    point-blank Luna bot's outline fragments one id, 71; the nearest by bearing was the upper piece, 200 -> 114 -> 107 px."""
    F, E = (2560, 1440), lambda b, i=71: Detection(ENEMY, b, 0.9, track=i)
    rows = [(28.286, [E((1532, 240, 1760, 716)), E((1537, 757, 1727, 840), 73), E((1725, 865, 1760, 954), 74)]),
            (28.310, [E((1544, 519, 1760, 1018)), E((1546, 282, 1760, 488))]),
            (28.330, [E((1544, 557, 1760, 1033)), E((1552, 319, 1760, 519))]),
            (28.347, [E((1542, 590, 1760, 1060)), E((1722, 439, 1760, 553))]),
            (28.364, [E((1538, 623, 1760, 1122)), E((1726, 480, 1760, 587))]),
            (28.385, [E((1525, 528, 1760, 1159))]),                         # from here only the whole box: 631, then ~520 px
            (28.403, [E((1509, 563, 1760, 1200))])]
    rows += [(28.42 + k * 0.02, [E((1538, 582, 1760, 1102))]) for k in range(30)]
    held, out = rows[0][1][0], []
    for t, dets in rows:
        out.append((t, c.step(State(t=t, frame=F, detections=dets), Engage(held), intent_t=t), c._measured))
    return out


def test_the_held_ids_whole_box_is_taken_back_after_a_fragment_set_the_tracks_size():
    """plaza30 t 28.385-36.71: the track's size came from a 107 px fragment of id 71, and the id's own 631 px box was then refused as another
    size (5.9x, over CLOSE_RATIO) on every tick for 8.3 s: nothing measured, the frozen track inside AIM_DONE_DEG and then lost, the pad
    neutral while the brain held Engage(71) with the bot 316 px right of the crosshair. Once the track has gone unmeasured past the re-seed
    delay (0.25 s) it re-seeds onto the held id's own box whatever its size, aim-only; the next frame of the id at that size measures and
    confirms it. Arming restarts from zero."""
    c = Controller()
    out = _plaza30_71(c)
    assert [m for t, _, m in out if t <= 28.364] == [True] * 5
    after = [(t, p, m) for t, p, m in out if t > 28.364]
    turn = next(i for i, (t, p, _) in enumerate(after) if p["rx"] > 0.3 and t - 28.364 > 0.25)
    assert after[turn][0] - 28.364 <= 0.27 and not after[turn][2]          # re-seeded on the first tick past the delay: turned toward, aim-only
    assert all(m for _, _, m in after[turn + 1:]) and c.track.h > 400 and c.track.confirmed   # measured, at its own size, from the next
    assert not any(_pressed(p) for t, p, _ in out if t > 28.364)          # off-centre: turned toward, nothing pressed


def test_a_held_id_box_of_another_size_is_refused_while_the_track_is_fresh_and_other_boxes_never_re_seed():
    """plaza30 t 16.836: an 89 px crop box took the held id 37 for one frame, 300 px from the 585 px bot that carried it; the size check
    refused it. It still does while the track is fresh. After a blind gap past the re-seed delay the held id's box is aimed at only: one
    frame of it measures, arms and walks nothing. A box of another size with another id or no id is not taken at all."""
    F = (2560, 1440)
    held = Detection(ENEMY, (1180, 400, 1380, 985), 0.9, track=37)            # 585 px, on the crosshair
    c = Controller()
    for k in range(8):
        c.step(State(t=k / 50, frame=F, detections=[held]), Engage(held), intent_t=k / 50)
    t = 8 / 50
    stray = Detection(ENEMY, (1520, 700, 1560, 789), 0.9, track=37)           # 89 px, the held id, one frame
    pad = c.step(State(t=t, frame=F, detections=[stray]), Engage(held), intent_t=t)
    assert not c._measured and pad["ly"] == 0.0 and c.track.h == 585
    c = Controller()                                                           # review of ec7359a: the stray after a blind gap
    for t in (0.0, 0.02, 0.04):
        c.step(State(t=t, frame=F, detections=[held]), Engage(held), intent_t=t)
    for t in (0.1, 0.2, 0.3):
        c.step(State(t=t, frame=F, detections=[]), Engage(held), intent_t=t)
    pad = c.step(State(t=0.32, frame=F, detections=[stray]), Engage(held), intent_t=0.32)
    assert pad["rx"] > 0.3 and pad["ly"] == 0.0 and not c._measured and c.stable == 0 and not c.track.confirmed
    pads = [c.step(State(t=0.34 + k / 50, frame=F, detections=[]), Engage(held), intent_t=0.34 + k / 50) for k in range(20)]
    assert not any(p["ly"] or _pressed(p) for p in pads)                     # it never came back: nothing but the turn
    for box in (replace(stray, track=38), replace(stray, track=None)):
        c = Controller()
        for k in range(8):
            c.step(State(t=k / 50, frame=F, detections=[held]), Engage(held), intent_t=k / 50)
        pads = [c.step(State(t=(8 + k) / 50, frame=F, detections=[box]), Engage(held), intent_t=(8 + k) / 50) for k in range(40)]
        assert not c._measured and c.track.h == 585 and not any(p["ly"] or _pressed(p) for p in pads), box.track


def test_a_playing_burst_finishes_its_own_sequence_after_the_target_changes_and_nothing_new_is_armed():
    """plaza30 t 25.651: the LT went out with no crop box, under Engage(66), 0.7 s after the second KO. It is the burst's own last tap: armed
    at 22.668 on Combo(54) on the held id's own box (5 steps measured), sequence end fixed then at +3.032 s (25.700), the LT at +2.983 s.
    Only Idle and Disengage preempt a playing primitive. Nothing is armed on the coast: no play() while no box is measured, and no press
    once the sequence has ended."""
    F = (1280, 720)
    held = Detection(ENEMY, (630, 340, 650, 380), 0.9, track=54)
    c, t, armed = Controller(), 0.0, None
    while armed is None:
        c.step(State(t=t, frame=F, detections=[held]), Combo(BURST, held))
        armed = t if c.seq else None
        t += 1 / 60
    end = c.seq[-1][0]
    assert c.seq_name == "burst" and abs(end - armed - 3.032) < 1e-6
    while t < armed + 1.79:                                                  # LT, RB, X on the held box; the RT is playing (24.459)
        c.step(State(t=t, frame=F, detections=[held]), Combo(BURST, held))
        t += 1 / 60
    plays, play = [], c.play
    c.play = lambda name, when: (plays.append((name, when)), play(name, when))
    succ = Engage(Detection(ENEMY, (900, 300, 930, 380), 0.9, track=66))      # the brain moves on; its box never reaches the crop
    lts = []
    while t < end + 2.0:
        pad = c.step(State(t=t, frame=F, detections=[]), succ)
        if pad["lt"]:
            lts.append(t)
            assert c.seq_name == "burst"
        assert t < end or not _pressed(pad)
        t += 1 / 60
    assert plays == [] and lts and all(armed + 2.95 <= x < end for x in lts)
