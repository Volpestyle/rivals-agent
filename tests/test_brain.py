"""State machine transitions and unknown-field handling. Plain asserts; run with `uv run pytest`."""
import json
from dataclasses import replace

import pytest

from agent.brain import BURST_HOLD_S, FIGHT, LOST_S, RETREAT_MAX_S, STRIKE_HOLD_S, Memory, decide
from agent.intents import BURST, MACROS, Combo, Disengage, Engage, Idle, Pull, Search, SwingTo, WebStrike
from agent.state import ANCHOR, ENEMY, PULL, SWING, TARGET, UPPERCUT, Ability, Detection, State

FRAME = (2560, 1440)  # the test geometry below is authored at this size
READY = {SWING: Ability(True, 3), PULL: Ability(True), UPPERCUT: Ability(True, 2)}


def enemy(h=300, x=1280, k=1.0, **kw):  # h = bbox height px: 600 near, 300 mid, 90 far on a 1440 px frame; k rescales to a smaller frame
    box = (x - h / 4, 720 - h / 2, x + h / 4, 720 + h / 2)
    return Detection(kw.pop("cls", ENEMY), tuple(k * v for v in box), kw.pop("conf", 0.9), **kw)


ANCH = Detection(ANCHOR, (1800, 200, 1900, 300), 0.8)


def st(t, **kw):
    kw.setdefault("frame", FRAME)
    kw.setdefault("hp", 100)
    kw.setdefault("max_hp", 100)
    kw.setdefault("abilities", dict(READY))
    kw.setdefault("webs", 3)
    kw.setdefault("on_target", True)
    return State(t=t, **kw)


def test_nothing_in_view_searches():
    assert decide(st(0, detections=[]), Memory()) == Search()


def test_low_confidence_detection_is_ignored():
    assert decide(st(0, detections=[enemy(conf=0.2)]), Memory()) == Search()


def test_detector_down_idles_instead_of_searching():
    assert decide(st(0, detections=None), Memory()) == Idle()


def test_hostile_classes_both_count():
    assert isinstance(decide(st(0, detections=[enemy(cls=TARGET)]), Memory()), Combo)


# --- range ------------------------------------------------------------------

def test_range_by_bbox_height():
    assert decide(st(0, detections=[enemy(600)]), Memory()) == Engage(enemy(600))  # near
    assert decide(st(0, detections=[enemy(300)]), Memory()) == Combo(BURST, enemy(300))  # mid
    assert decide(st(0, detections=[enemy(90), ANCH]), Memory()) == SwingTo(ANCH)  # far


def test_range_thresholds_come_from_one_table(monkeypatch):
    from agent import brain
    from agent.brain import RANGES, Ranges, range_of

    # L3's ground-truth ranging: distance_m = 1.30 / (box height / frame height); the table is that at 4 m and 20 m
    assert (RANGES.near_m, RANGES.far_m, RANGES.near_h, RANGES.far_h) == (4.0, 20.0, 0.325, 0.065)
    assert RANGES.near_h * RANGES.near_m == pytest.approx(1.30) == RANGES.far_h * RANGES.far_m
    s = st(0)
    other = Ranges(near_h=0.12, far_h=0.05)  # a table with different height columns
    assert [range_of(enemy(h), s) for h in (60, 130, 200)] == ["far", "mid", "mid"]  # 0.325 of 1440 px is 468 px
    assert [range_of(enemy(h), s, other) for h in (60, 130, 200)] == ["far", "mid", "near"]
    assert range_of(enemy(90, distance=3.0), s, Ranges(near_m=2.5)) == "mid"  # the metre columns too
    # decisions read the table at call time, so setting it needs no change at any call site
    box = enemy(200)
    assert isinstance(decide(st(0, detections=[box]), Memory()), Combo)  # mid range under the default table
    monkeypatch.setattr(brain, "RANGES", other)
    assert decide(st(0, detections=[box]), Memory()) == Engage(box)  # near under the other one


def test_range_and_aim_follow_the_frame_the_boxes_are_in():
    half = (1280, 720)  # what L1 records and perception processes
    for h, expected in ((600, Engage), (300, Combo)):  # near, mid
        full = decide(st(0, detections=[enemy(h)]), Memory())
        scaled = decide(st(0, frame=half, detections=[enemy(h, k=0.5)]), Memory())
        assert type(full) is type(scaled) is expected
    # with the crosshair reader down, "aimed" means the bbox holds the centre of the frame it is in
    centred = enemy(300, k=0.5)
    assert isinstance(decide(st(0, frame=half, detections=[centred], on_target=None), Memory()), Combo)
    # the mistake a default frame allowed: half-size boxes read against a full-size frame look far smaller
    near_half = enemy(600, k=0.5)
    assert isinstance(decide(st(0, frame=half, detections=[near_half]), Memory()), Engage)
    assert not isinstance(decide(st(0, frame=FRAME, detections=[near_half]), Memory()), Engage)


def test_range_prefers_distance_estimate_over_bbox():
    tiny_but_close = enemy(90, distance=3.0)  # bbox alone says far, so it would swing
    assert decide(st(0, detections=[tiny_but_close, ANCH]), Memory()) == Engage(tiny_but_close)
    huge_but_far = enemy(600, distance=40.0)
    assert decide(st(0, detections=[huge_but_far, ANCH]), Memory()) == SwingTo(ANCH)
    mid_by_distance = enemy(90, distance=12.0)
    assert decide(st(0, detections=[mid_by_distance]), Memory()) == Combo(BURST, mid_by_distance)


def test_range_cutoffs_follow_the_kit():
    def kind(metres):
        d = enemy(300, distance=metres, tagged=True)
        return type(decide(st(0, detections=[d, ANCH]), Memory())).__name__

    # uppercut / kick reach 4 m; pull and burst reach 20 m
    assert [kind(m) for m in (4.0, 4.1, 20.0, 20.1)] == ["Engage", "WebStrike", "WebStrike", "SwingTo"]


def test_near_range_engages_whatever_the_tag():
    for tag in (True, False, None):  # melee_combo and uppercut consume a tag themselves
        near = enemy(600, tagged=tag)
        assert decide(st(0, detections=[near]), Memory()) == Engage(near)


def test_far_swing_needs_anchor_and_charge():
    far = enemy(90)
    assert decide(st(0, detections=[far]), Memory()) == Engage(far)  # no anchor
    spent = dict(READY, **{SWING: Ability(False, 0)})
    assert decide(st(0, detections=[far, ANCH], abilities=spent), Memory()) == Engage(far)


def test_picks_hostile_nearest_crosshair_and_sticks_to_it():
    m = Memory()
    a, b = enemy(300, x=1200), enemy(300, x=2000)
    assert decide(st(0, detections=[a, b], on_target=False), m).target == a
    b_closer = enemy(300, x=1320)  # 'a' drifted away, b now nearer the crosshair, but we track a
    a_moved = enemy(300, x=1150)
    assert decide(st(0.1, detections=[a_moved, b_closer], on_target=False), m).target == a_moved


# --- Spider-Tracer: Get Over Here! pulls untagged, zips to tagged -----------

def test_tagged_mid_target_is_web_struck_never_pulled():
    tagged = enemy(300, tagged=True)
    # a burst would be possible, but the tag is already on: go to them
    assert decide(st(0, detections=[tagged]), Memory()) == WebStrike(tagged)
    assert decide(st(0, detections=[tagged], webs=0, abilities={PULL: READY[PULL]}), Memory()) == WebStrike(tagged)
    # the web strike auto-locks, so it does not wait for the crosshair
    assert decide(st(0, detections=[tagged], on_target=False), Memory()) == WebStrike(tagged)


def test_untagged_mid_target_is_pulled_only_when_a_burst_is_not_possible():
    untagged = enemy(300, tagged=False)
    assert decide(st(0, detections=[untagged]), Memory()) == Combo(BURST, untagged)
    assert decide(st(0, detections=[untagged], webs=0), Memory()) == Pull(untagged)  # out of Web Cluster
    assert decide(st(0, detections=[untagged], webs=None), Memory()) == Pull(untagged)  # ammo unreadable
    assert decide(st(0, detections=[untagged], abilities={PULL: READY[PULL]}), Memory()) == Pull(untagged)


def test_pull_needs_aim():
    untagged = enemy(300, tagged=False)
    assert decide(st(0, detections=[untagged], webs=0, on_target=False), Memory()) == Engage(untagged)
    assert decide(st(0, detections=[untagged], on_target=False), Memory()) == Engage(untagged)  # burst too


def test_unknown_tag_never_presses_get_over_here_blind():
    unknown = enemy(300)  # tagged=None
    assert decide(st(0, detections=[unknown]), Memory()) == Combo(BURST, unknown)  # burst tags first
    assert decide(st(0, detections=[unknown], webs=0), Memory()) == Engage(unknown)
    assert decide(st(0, detections=[unknown], abilities={PULL: READY[PULL]}), Memory()) == Engage(unknown)


def test_get_over_here_on_cooldown_or_unread_is_not_used():
    cooling = dict(READY, **{PULL: Ability(False)})
    unread = {UPPERCUT: READY[UPPERCUT]}  # no pull slot at all
    for tag in (True, False, None):
        d = enemy(300, tagged=tag)
        assert decide(st(0, detections=[d], abilities=cooling), Memory()) == Engage(d)
        assert decide(st(0, detections=[d], abilities=unread), Memory()) == Engage(d)


def test_combo_names_are_kit_macros():
    assert isinstance(decide(st(0, detections=[enemy(300)]), Memory()), Combo)
    assert decide(st(0, detections=[enemy(300)]), Memory()).name in MACROS


# --- unknown fields ---------------------------------------------------------

def test_unknown_ability_is_never_spent():
    mid, far = enemy(300, tagged=False), enemy(90)
    assert decide(st(0, detections=[mid], abilities={}), Memory()) == Engage(mid)
    assert decide(st(0, detections=[far, ANCH], abilities={}), Memory()) == Engage(far)
    unreadable = {PULL: READY[PULL], UPPERCUT: Ability(None, None)}
    assert decide(st(0, detections=[mid], abilities=unreadable), Memory()) == Pull(mid)  # no burst without uppercut


def test_unreadable_icon_falls_back_to_charge_count():
    mid = enemy(300, tagged=False)
    have = {PULL: READY[PULL], UPPERCUT: Ability(None, 1)}
    none = {PULL: READY[PULL], UPPERCUT: Ability(None, 0)}
    assert decide(st(0, detections=[mid], abilities=have), Memory()) == Combo(BURST, mid)
    assert decide(st(0, detections=[mid], abilities=none), Memory()) == Pull(mid)


def test_unknown_hp_never_retreats():
    m = Memory()
    for i in range(80):  # 8 s of unreadable hp with an enemy in view
        assert not isinstance(decide(st(i / 10, hp=None, max_hp=None, detections=[enemy(300)]), m), Disengage)


def test_unknown_on_target_falls_back_to_geometry():
    centred = enemy(300)  # bbox covers the frame centre
    assert decide(st(0, detections=[centred], on_target=None), Memory()) == Combo(BURST, centred)
    off = enemy(300, x=300)
    assert decide(st(0, detections=[off], on_target=None), Memory()) == Engage(off)


def test_unknown_detections_ride_out_a_short_dropout_then_idle():
    m = Memory()
    first = decide(st(0, detections=[enemy(300)], on_target=False), m)
    assert decide(st(LOST_S - 0.1, detections=None), m) is first
    assert decide(st(LOST_S + 0.5, detections=None), m) == Idle()


def test_short_flicker_keeps_intent_but_long_loss_searches():
    m = Memory()
    first = decide(st(0, detections=[enemy(300)], on_target=False), m)
    assert decide(st(0.3, detections=[]), m) is first
    assert decide(st(0.8, detections=[]), m) == Search()


def test_a_target_lost_right_after_our_own_hit_is_not_the_target_leaving():
    # L3: a bot flashes white when hit and its outline vanishes for a few frames (L4 holds its track 0.35 s).
    # The brain's flicker window (LOST_S) outlasts that, so the fight is neither dropped nor turned into a search.
    m = Memory()
    near = enemy(600)
    assert decide(st(0, detections=[near]), m) == Engage(near)
    for i in range(1, 5):  # four blind frames at 10 Hz
        assert decide(st(i / 10, detections=[]), m) == Engage(near)
        assert m.mode == FIGHT
    assert decide(st(0.5, detections=[enemy(600, x=1300)]), m) == Engage(enemy(600, x=1300))  # back on the same target
    assert m.mode == FIGHT
    assert LOST_S > 0.35  # the window, not the tests above, is what must outlast the flash
    assert decide(st(0.5 + LOST_S + 0.2, detections=[]), m) == Search()  # a real loss still ends the fight


# --- retreat ----------------------------------------------------------------

def test_retreat_has_hysteresis_and_rearms():
    m = Memory()
    near = enemy(600)
    assert decide(st(0, detections=[near]), m) == Engage(near)
    assert decide(st(0.1, hp=25, detections=[near]), m) == Disengage()
    assert decide(st(1.0, hp=40, detections=[near]), m) == Disengage()  # between thresholds: stay out
    assert not isinstance(decide(st(2.0, hp=70, detections=[near]), m), Disengage)
    assert decide(st(2.1, hp=20, detections=[near]), m) == Disengage()  # re-armed by recovery


def test_retreat_timeout_does_not_flap_back_in():
    m = Memory()
    assert decide(st(0, hp=25, detections=[enemy(300)]), m) == Disengage()
    assert not isinstance(decide(st(RETREAT_MAX_S, hp=25, detections=[enemy(300)]), m), Disengage)
    assert not isinstance(decide(st(RETREAT_MAX_S + 0.1, hp=25, detections=[enemy(300)]), m), Disengage)


def test_retreat_survives_unreadable_hp_until_timeout():
    m = Memory()
    assert decide(st(0, hp=25, detections=[enemy(300)]), m) == Disengage()
    assert decide(st(3, hp=None, max_hp=None, detections=[enemy(300)]), m) == Disengage()
    assert not isinstance(decide(st(RETREAT_MAX_S + 0.1, hp=None, max_hp=None, detections=[enemy(300)]), m), Disengage)


# --- holds ------------------------------------------------------------------

def test_burst_is_not_reconsidered_until_its_hold_expires():
    m = Memory()
    first = decide(st(0, detections=[enemy(300)]), m)
    assert first == Combo(BURST, enemy(300))
    moved = enemy(300, x=1400)
    assert decide(st(0.5, detections=[moved]), m) is first
    assert decide(st(BURST_HOLD_S - 0.1, detections=[moved]), m) is first
    assert decide(st(BURST_HOLD_S + 0.1, detections=[moved]), m).target == moved


def test_web_strike_hold_ends_and_the_next_tick_sees_the_new_range():
    m = Memory()
    first = decide(st(0, detections=[enemy(300, tagged=True)]), m)
    assert isinstance(first, WebStrike)
    landed = enemy(600, tagged=True)  # the strike closed the gap
    assert decide(st(STRIKE_HOLD_S - 0.1, detections=[landed]), m) is first
    assert decide(st(STRIKE_HOLD_S + 0.1, detections=[landed]), m) == Engage(landed)


def test_retreat_preempts_a_playing_combo():
    m = Memory()
    assert isinstance(decide(st(0, detections=[enemy(300)]), m), Combo)
    assert decide(st(0.3, hp=20, detections=[enemy(300)]), m) == Disengage()


# --- search -----------------------------------------------------------------

def test_search_swings_to_an_anchor_only_after_a_while():
    m = Memory()
    assert decide(st(0, detections=[ANCH]), m) == Search()
    assert decide(st(2.9, detections=[ANCH]), m) == Search()
    assert decide(st(3.0, detections=[ANCH]), m) == SwingTo(ANCH)
    assert decide(st(3.5, detections=[ANCH]), m) == SwingTo(ANCH)  # holding
    assert decide(st(4.3, detections=[ANCH]), m) == Search()  # search clock restarted


# --- State JSON -------------------------------------------------------------

def test_state_roundtrips_through_json_including_unknowns():
    s = State(t=1.5, frame=(1280, 720), hp=None, abilities={PULL: Ability(None, 2)},
              detections=[enemy(300, distance=8.0, tagged=True), enemy(300, tagged=None)], on_target=None)
    assert State.from_dict(json.loads(json.dumps(s.to_dict()))) == s


def test_bare_state_loads_as_all_unknown_and_empty_detections_stay_empty():
    s = State.from_dict({"t": 3.0, "frame": [1280, 720]})
    assert (s.frame, s.hp, s.max_hp, s.webs, s.detections, s.on_target, s.abilities) == ((1280, 720), None, None, None, None, None, {})
    assert State.from_dict({"t": 3.0, "frame": [1280, 720], "detections": []}).detections == []


def test_frame_is_required():
    with pytest.raises(TypeError):
        State(t=0.0)
    with pytest.raises(KeyError):
        State.from_dict({"t": 3.0})  # a recording without its frame size cannot be interpreted
    with pytest.raises(ValueError):
        State.from_dict({"t": 3.0, "frame": [1280]})
    with pytest.raises(TypeError):
        State.from_dict({"t": 3.0, "frame": None})


def test_detection_recorded_before_the_tag_field_loads_as_unknown_tag():
    old = {"t": 1.0, "frame": [1280, 720], "detections": [{"cls": "enemy", "bbox": [0, 0, 10, 20], "conf": 0.9}]}
    assert State.from_dict(old).detections[0].tagged is None


def test_a_bot_beyond_the_engagement_cap_is_never_picked():
    """handoff30: five of seven targets were the range's robot dummies far down the shooting lane, 33-40 px (~45 m) on the height ruler,
    past the 40 m engagement cap (chosen from the kit: Web Cluster falls to 50% at 40 m), and walking at one took him off the plaza. They
    are searched past."""
    m, dummy = Memory(), enemy(h=36, x=1300)
    assert [decide(st(t, detections=[replace(dummy, track=5)]), m) for t in (0.0, 0.1, 0.2)] == [Search()] * 3
    m, bot = Memory(), enemy(h=60, x=1300, track=6)                          # the smallest bot engaged on the recorded runs
    assert isinstance([decide(st(t, detections=[bot]), m) for t in (0.0, 0.1)][-1], Engage)
    m = Memory()                                                             # with both in view, the far one nearer the crosshair
    got = [decide(st(t, detections=[replace(dummy, track=5, bbox=(1270, 700, 1288, 736)), replace(bot, bbox=(1800, 600, 1830, 660))]), m)
           for t in (0.0, 0.1)][-1]
    assert got.target.track == 6


def test_the_engagement_cap_reads_distance_when_it_has_one():
    from agent.brain import in_reach
    s = st(0)
    assert in_reach(enemy(h=20, distance=39.0), s) and not in_reach(enemy(h=600, distance=41.0), s)
    assert in_reach(enemy(h=47), s) and not in_reach(enemy(h=46), s)       # 47 / 1440 = 0.0326 > reach_h 0.0325


def test_a_new_id_of_the_held_targets_size_succeeds_it_while_it_coasts():
    """reach30 11 -> 12: the tracker gave the bot a new id across a fast turn; the brain held the coasting 11 for 0.8 s while she stood in
    view as 12, then searched. For a target last seen outside the aim crop, a NEW id (absent when it was last seen) of its size, present
    at two decisions, takes its place."""
    m = Memory()
    for t in (0.0, 0.1):
        decide(st(t, detections=[enemy(h=200, x=1900, track=11), enemy(h=190, x=200, track=3)]), m)
    assert m.target.track == 11                                               # x 1900: outside the crop (800-1760 at 1440p)
    her = enemy(h=173, x=1700, track=12)
    wall = enemy(h=190, x=200, track=3)                                        # present beside 11, and nearer its size: never its successor
    decide(st(0.2, detections=[her, wall], coasting=(11,)), m)                 # first sighting: not yet
    assert m.target.track == 11
    decide(st(0.3, detections=[her, wall], coasting=(11,)), m)
    assert m.target.track == 12
    m = Memory()
    for t in (0.0, 0.1):
        decide(st(t, detections=[enemy(h=200, x=1900, track=11)]), m)
    for t in (0.2, 0.3):
        decide(st(t, detections=[enemy(h=90, x=1700, track=12)], coasting=(11,)), m)   # another size: not her
    assert m.target.track == 11
    m = Memory()
    for t in (0.0, 0.1):
        decide(st(t, detections=[enemy(h=200, x=1400, track=11)]), m)         # inside the crop: the coasting trade stands
    for t in (0.2, 0.3):
        decide(st(t, detections=[enemy(h=190, x=1450, track=12)], coasting=(11,)), m)
    assert m.target.track == 11
