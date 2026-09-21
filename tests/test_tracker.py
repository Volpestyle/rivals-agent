"""agent/tracker.py (VUH-1314): one id per enemy, through the four ways the green finder loses a bot, and the brain and Jev following it.

Stdlib only. Boxes are native 2560x1440 pixels, frames arrive every 1/60 s unless a test says otherwise. The recorded-frame checks are in
tests/test_tracker_frames.py.
"""
import math

import pytest

from agent import brain
from agent.brain import Memory, decide
from agent.intents import Engage, Search
from agent.jev import reassociate
from agent.state import ENEMY, Ability, Detection, State
from agent.tracker import CLOSE_AGE_S, MAX_AGE_S, NEW_AGE_S, SMALL_AGE_S, Tracker

FRAME = (2560, 1440)
HZ = 60


def box(cx, cy, h, w=None):
    w = w if w is not None else h / 2.4
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def det(cx, cy, h, **kw):
    return Detection(kw.pop("cls", ENEMY), box(cx, cy, h, kw.pop("w", None)), kw.pop("conf", 0.9), **kw)


def run(tracker, frames, hz=HZ, t0=0.0):
    """frames: list of detection lists, one per tick. Returns [(ids, coasting)] per tick."""
    out = []
    for i, dets in enumerate(frames):
        got = tracker.update(dets, t0 + i / hz, FRAME)
        out.append(([d.track for d in got], tracker.coasting))
    return out


def walk(n, x0=1200.0, vx=40.0, y=720.0, h=300.0):
    """A bot drifting right at vx px per second, n ticks."""
    return [[det(x0 + vx * i / HZ, y, h)] for i in range(n)]


def main_id(tracked):
    ids = {i for ids, _ in tracked for i in ids}
    assert len(ids) == 1, ids
    return ids.pop()


# --- the basics --------------------------------------------------------------------------------------------------------
def test_a_bot_keeps_one_id_while_it_moves_and_the_camera_turns():
    tr = Tracker()
    frames = [[det(600 + 55 * i, 700, 300 + 0.5 * i)] for i in range(90)]      # 55 px a frame across the view: a camera turning at ~300 deg/s
    assert main_id(run(tr, frames)) == 1


def test_every_detection_gets_an_id_and_ids_are_never_reused():
    tr = Tracker()
    first = run(tr, [[det(500, 500, 200)]] * 5)
    run(tr, [[]] * 120)                                                        # long enough for every track to be dropped
    assert tr.tracks == [] and tr.coasting == ()
    again = run(tr, [[det(500, 500, 200)]] * 5, t0=5.0)
    assert main_id(first) == 1 and main_id(again) == 2


def test_two_bots_get_two_ids_and_boxes_of_other_classes_never_match():
    tr = Tracker()
    got = tr.update([det(500, 700, 300), det(1800, 700, 300)], 0.0, FRAME)
    assert [d.track for d in got] == [1, 2]
    other = tr.update([det(500, 700, 300, cls="anchor")], 0.1, FRAME)
    assert other[0].track == 3


def test_the_input_boxes_are_returned_unchanged_apart_from_the_id():
    tr = Tracker()
    d = det(500, 700, 300, distance=7.0, tagged=True, conf=0.61)
    out, = tr.update([d], 0.0, FRAME)
    assert out.track == 1 and (out.bbox, out.conf, out.distance, out.tagged, out.cls) == (d.bbox, d.conf, d.distance, d.tagged, d.cls)


# --- the four ways the finder loses a bot -------------------------------------------------------------------------------
def gap(frames, start, n):
    """The same detections with `n` ticks starting at `start` emptied: the finder lost the bot there."""
    return [[] if start <= i < start + n else dets for i, dets in enumerate(frames)]


def test_hit_flash_the_outline_vanishes_for_a_few_frames_and_the_id_comes_back():
    frames = gap(walk(90), 30, 21)                                             # ~0.35 s, l4's HIT_BLIND_S
    tracked = run(Tracker(), frames)
    assert main_id(tracked) == 1
    assert all(c == (1,) for _, c in tracked[31:51]) and tracked[30][1] == (1,)     # the brain is told: held, not gone
    assert tracked[51][1] == () and tracked[52][0] == [1]                       # and the flag clears when it is seen again


def test_small_and_far_a_flickering_box_at_the_size_floor_keeps_its_id_through_long_gaps():
    frames = [[det(1500, 500, 60)] if i % 66 < 3 else [] for i in range(300)]     # 3 ticks in view, then ~1.05 s of nothing, over and over
    tracked = run(Tracker(), frames)
    assert main_id(tracked) == 1
    # ...and a gap longer than the memory is a different bot: ids are held for a bounded time only
    long_gap = gap([[det(1500, 500, 60)]] * 200, 10, int((SMALL_AGE_S + 0.3) * HZ))
    assert len({i for ids, _ in run(Tracker(), long_gap) for i in ids}) == 2


def test_point_blank_the_outline_runs_off_the_frame_and_the_id_survives_the_wild_box():
    approach = [[det(1280 + 3 * i, 720, 300 + 10 * i)] for i in range(40)]      # closing fast, h to ~0.75 of the frame
    off = [[]] * int(1.4 * HZ)                                                 # the outline fails the fill test: nothing for 1.4 s
    back = [[det(1500, 800, 180)]] * 6                                         # then a small piece of it, cut by the edge, near where it left
    tracked = run(Tracker(), approach + off + back)
    assert main_id(tracked) == 1
    gone = run(Tracker(), approach + [[]] * int((CLOSE_AGE_S + 0.4) * HZ) + back)
    assert len({i for ids, _ in gone for i in ids}) == 2                       # held 1.5 s at most
    far = run(Tracker(), approach + off + [[det(2350, 800, 180)]] * 6)         # a box ~950 px from where it left is not it, however big it was
    assert len({i for ids, _ in far for i in ids}) == 2


def test_occluded_behind_the_hero_the_bot_returns_where_its_velocity_says():
    walk_in = [[det(1000 + 300 * i / HZ * 3, 900, 350)] for i in range(40)]    # moving right at 900 px/s toward the hero's body...
    hidden = [[]] * int(0.5 * HZ)                                              # ...behind it for 0.5 s
    x_out = 1000 + 300 * 3 * (40 + 30) / HZ
    out = [[det(x_out + 900 * i / HZ, 900, 350)] for i in range(20)]           # and out the other side, where the motion puts it
    tracked = run(Tracker(), walk_in + hidden + out)
    assert main_id(tracked) == 1


def test_a_junk_box_that_flickers_is_dropped_fast_and_never_reported_as_held():
    tr = Tracker()
    tracked = run(tr, [[det(700, 300, 80)]] + [[]] * 40)                        # one frame: a lit panel, a lamp
    assert all(c == () for _, c in tracked)                                    # never "coasting": nobody should wait for it
    assert tr.tracks == [] and int(NEW_AGE_S * HZ) < 40


def test_the_finders_split_body_is_one_id_and_a_close_bot_is_not_a_second_one():
    tr = Tracker()
    run(tr, walk(20, h=500))
    upper, lower = det(1300, 600, 240, w=200), det(1290, 950, 340, w=190)       # one body drawn as two boxes with a small gap (recorded frame 19)
    got = tr.update([upper, lower], 20 / HZ, FRAME)
    assert [d.track for d in got] == [1, 1]
    whole = tr.update([det(1300, 800, 680, w=280)], 21 / HZ, FRAME)              # and the next frame's single box is still that bot
    assert whole[0].track == 1


def test_two_bots_in_a_line_overlapping_on_screen_keep_two_ids():
    """One dummy behind another: centres 30 px apart, the nearer one taller, overlapping over the whole height. Not one body in pieces."""
    frames = [[det(1000, 700, 300), det(1030, 700, 420)] for _ in range(10)]
    ids = run(Tracker(), frames)
    assert all(len(set(i)) == 2 for i, _ in ids) and ids[0][0] == ids[-1][0]
    stacked = [[det(1300, 600, 240, w=200), det(1290, 950, 340, w=190)] for _ in range(3)]    # the finder's real split: stacked, a small gap
    assert all(len(set(i)) == 1 for i, _ in run(Tracker(), stacked))
    flat = [[det(1300, 600, 100, w=300), det(1300, 710, 100, w=300)] for _ in range(3)]      # stacked, but together wider than tall: not a body
    assert all(len(set(i)) == 2 for i, _ in run(Tracker(), flat))
    touching = [[det(1000, 600, 240, w=200), det(1180, 850, 240, w=200)] for _ in range(3)]   # stacked, body-shaped together, sides overlap 20 px
    assert all(len(set(i)) == 2 for i, _ in run(Tracker(), touching))


def test_a_close_bot_drawn_in_changing_pieces_keeps_one_id():
    """postfreeze30: at close range the finder returns one bot as 2-5 pieces that change every frame, and the aim crop's edges cut it.
    A piece that would start a new id, lying inside the body matched in the same update, is that body."""
    tr = Tracker()
    run(tr, [[det(1280, 760, 600, w=250)]] * 5)                                     # the bot, whole, confirmed
    pieces = [[det(1280, 620, 300, w=240), det(1300, 930, 250, w=120)],             # upper and lower body
              [det(1275, 700, 420, w=250), det(1250, 1000, 120, w=60), det(1320, 480, 90, w=80)],   # three pieces, one cut by the crop edge
              [det(1285, 770, 610, w=255)]]                                         # and whole again
    ids = [[d.track for d in tr.update(p, (5 + k) / HZ, FRAME)] for k, p in enumerate(pieces)]
    assert ids == [[1, 1], [1, 1, 1], [1]]


def test_a_piece_needs_its_body_seen_in_the_same_update():
    tr = Tracker()
    run(tr, [[det(1280, 760, 600, w=250)]] * 5)
    got = tr.update([det(1300, 930, 250, w=120)], 5 / HZ, FRAME)                    # only a piece-sized box where the body is merely predicted
    assert got[0].track == 1                                                        # (matched by the gate as before: close box, ratio 2.4)
    tr2 = Tracker()
    run(tr2, [[det(1000, 700, 400)]] * 5)
    lamp = tr2.update([det(1000, 700, 60)], 5 / HZ, FRAME)                          # a lamp at a merely predicted body: a new id
    assert lamp[0].track == 2


def test_what_is_not_a_piece_of_the_body_gets_its_own_id():
    tr = Tracker()
    run(tr, [[det(1280, 760, 600, w=250)]] * 5)
    beside = tr.update([det(1280, 760, 600, w=250), det(1460, 760, 300, w=125)], 5 / HZ, FRAME)   # a second bot, mostly outside the body
    assert [d.track for d in beside] == [1, 2]
    tr = Tracker()
    run(tr, [[det(1280, 760, 600, w=250)]] * 5)
    front = tr.update([det(1280, 760, 600, w=250), det(1300, 780, 800, w=330)], 5 / HZ, FRAME)    # a nearer, taller bot passing in front
    assert [d.track for d in front] == [1, 2]
    young = Tracker()
    run(young, [[det(1280, 760, 600, w=250)]] * 2)                                  # seen twice: not yet a confirmed body
    got = young.update([det(1275, 700, 420, w=250), det(1320, 480, 90, w=80)], 2 / HZ, FRAME)   # torso, and a head piece (not stacked)
    assert len({d.track for d in got}) == 2                                         # it takes no pieces


def test_none_is_no_detections():
    tr = Tracker()
    run(tr, [[det(1000, 700, 300)]] * 5)
    assert tr.update(None, 5 / HZ, FRAME) == [] and tr.coasting == (1,)


# --- identity: who is who -------------------------------------------------------------------------------------------------
def test_two_bots_crossing_paths_keep_their_own_ids():
    a = [[det(1000 + 300 * i / HZ, 700, 300), det(1800 - 300 * i / HZ, 720, 300)] for i in range(120)]     # A rightwards, B leftwards, crossing at 60
    tracked = run(Tracker(), a)
    left_id, right_id = tracked[0][0]
    assert tracked[-1][0] == [left_id, right_id]                                # A is still A, B is still B, after passing through each other


@pytest.mark.parametrize("h, dx", [(300, 450), (468, 702), (600, 900), (965, 1447)])
def test_the_target_lost_for_a_moment_is_not_swapped_for_a_bot_that_is_nearer(h, dx):
    """The reviewer's steal table: A is the target; it washes out in a hit flash and B, never tracked, comes into view 1.5 box sizes from
    where A was (the old gate's edge). GATE 1.3, just above the recorded bot's own largest jump (1.12), keeps A's id off B there; a thief
    nearer than 1.3 sizes still takes it (the residual risk in docs/lanes/tracker.md)."""
    a_only = [[det(1000, 700, h)] for _ in range(20)]                           # A (target), alone
    flash = [[det(1000 + dx, 700, h)] for _ in range(15)]                       # A washes out; B, never tracked before, is in view
    back = [[det(1002, 700, h), det(1000 + dx, 700, h)] for _ in range(5)]
    tracked = run(Tracker(), a_only + flash + back)
    a_id, b_id = tracked[0][0][0], tracked[20][0][0]
    assert a_id != b_id and all(ids == [b_id] for ids, _ in tracked[20:35]) and all(a_id in c for _, c in tracked[20:35])
    assert tracked[-1][0] == [a_id, b_id]


def test_a_much_smaller_box_at_the_same_place_is_not_the_bot():
    tr = Tracker()
    run(tr, [[det(1000, 700, 400)]] * 5)
    lamp = tr.update([det(1000, 700, 60)], 5 / HZ, FRAME)
    assert lamp[0].track == 2


def test_updates_out_of_order_do_not_rewind_or_crash():
    """The reflex thread and the decision worker share one tracker; the worker's frame can be a little older than the newest."""
    tr = Tracker()
    run(tr, walk(30))
    newer = tr.update([det(1200 + 40 * 30 / HZ, 720, 300)], 30 / HZ, FRAME)
    older = tr.update([det(1200 + 40 * 27 / HZ, 720, 300)], 27 / HZ, FRAME)
    again = tr.update([det(1200 + 40 * 31 / HZ, 720, 300)], 31 / HZ, FRAME)
    assert newer[0].track == older[0].track == again[0].track == 1


def test_the_tracker_is_deterministic():
    frames = gap(walk(90), 30, 21)
    assert run(Tracker(), frames) == run(Tracker(), frames)


def test_a_track_seen_long_ago_at_a_similar_place_is_a_new_bot():
    tr = Tracker()
    run(tr, walk(20))
    out = tr.update([det(1200, 720, 300)], 20 / HZ + CLOSE_AGE_S + 0.5, FRAME)      # h 0.21 of the frame: a close box, held 1.5 s
    assert out[0].track == 2


# --- State, the brain and Jev follow the id -------------------------------------------------------------------------------------
def test_state_round_trips_track_ids_and_the_coasting_list_and_old_lines_still_load():
    st = State(t=1.0, frame=FRAME, detections=[det(500, 500, 200, track=7, plate=True), det(900, 500, 200, plate=None)], coasting=(3, 5))
    back = State.from_dict(st.to_dict())
    assert back == st and back.detections[0].track == 7 and back.coasting == (3, 5)
    assert [d.plate for d in back.detections] == [True, None]                        # unknown stays None, never False
    old = {"t": 1.0, "frame": [2560, 1440], "detections": [{"cls": "enemy", "bbox": [1, 2, 3, 4], "conf": 0.9}]}
    loaded = State.from_dict(old)
    assert loaded.detections[0].track is None and loaded.coasting == ()


def st(t, dets, coasting=(), **kw):
    kw.setdefault("hp", 100)
    kw.setdefault("max_hp", 100)
    kw.setdefault("abilities", {})
    return State(t=t, frame=FRAME, detections=dets, coasting=coasting, **kw)


def test_the_brain_stays_on_its_target_by_id_even_when_another_bot_is_nearer_the_crosshair():
    m = Memory()
    a, b = det(1000, 720, 600, track=1), det(1290, 720, 600, track=2)            # B is right on the crosshair, A is where the brain engaged
    decide(st(-0.1, [a]), m)                                                    # seen at the previous decision: acquisition needs two in a row
    assert decide(st(0.0, [a]), m) == Engage(a)
    got = decide(st(0.1, [a, b]), m)
    assert got == Engage(a) and m.target.track == 1                             # not "nearest the crosshair": that is B


def test_a_target_the_tracker_still_holds_is_not_swapped_and_its_intent_stands_past_the_flicker_window():
    m = Memory()
    a, b = det(1000, 720, 600, track=1), det(1050, 720, 600, track=2)
    decide(st(-0.1, [a]), m)                                                    # seen at the previous decision: acquisition needs two in a row
    assert decide(st(0.0, [a]), m) == Engage(a)
    for k in range(1, 12):                                                      # A vanishes for 1.1 s; B is right where A was
        assert decide(st(k * 0.1, [b], coasting=(1,)), m) == Engage(a), k       # LOST_S alone (0.5 s) would have given up at k=6
        assert m.target.track == 1
    assert decide(st(1.3, [b], coasting=()), m) == Engage(b)                    # the tracker let go: now B is the target
    assert m.target.track == 2


def test_the_brains_id_path_never_returns_an_anchor_or_a_low_confidence_box():
    """The id is not a licence: a box carrying the target's id that is not a hostile, or is below MIN_CONF, is not the target."""
    from agent.state import ANCHOR
    a = det(1000, 720, 600, track=1)
    for impostor in (det(1000, 720, 600, track=1, cls=ANCHOR), det(1000, 720, 600, track=1, conf=brain.MIN_CONF / 2)):
        m = Memory()
        m.target, m.target_t = a, 0.0
        assert brain._pick_target(st(0.1, [impostor]), m) is None, impostor


def test_jevs_id_path_matches_the_class_as_well_as_the_id():
    from agent.state import ANCHOR
    a = det(1000, 720, 600, track=1)
    swing = det(1000, 720, 600, track=1, cls=ANCHOR)
    assert reassociate(st(0.1, [swing]), a) is None                              # same id, another class: not the target
    assert reassociate(st(0.1, [swing, a]), a) == a


def test_without_ids_the_old_behaviour_is_unchanged():
    m = Memory()
    a, b = det(1000, 720, 600), det(1050, 720, 600)
    decide(st(-0.1, [a]), m)                                                    # seen at the previous decision: acquisition needs two in a row
    assert decide(st(0.0, [a]), m) == Engage(a)
    assert decide(st(0.1, [b]), m) == Engage(b)                                  # nearest where it was: the old rule
    assert decide(st(0.2, []), m) == Engage(b) and decide(st(1.0, []), m) == Search()


def test_jev_follows_a_target_by_id_and_keeps_one_the_tracker_holds():
    a = det(1000, 720, 600, track=1)
    nearer_but_other = det(1005, 720, 600, track=2)
    moved = det(1600, 720, 600, track=1)
    assert reassociate(st(0.0, [nearer_but_other, moved]), a) == moved           # same id, far away: it is still A
    assert reassociate(st(0.0, [nearer_but_other], coasting=(1,)), a) == a       # held unseen: keep the answer standing
    assert reassociate(st(0.0, [nearer_but_other]), a) is None or reassociate(st(0.0, [nearer_but_other]), a).track == 2
    assert reassociate(st(0.0, [det(1010, 720, 600)]), det(1000, 720, 600)) is not None      # no ids: the old nearest rule


def test_the_mode_bookkeeping_is_unaffected_by_ids():
    m = Memory()
    near = det(1280, 720, 900, track=4)
    decide(st(-0.1, [near]), m)
    decide(st(0.0, [near]), m)
    assert m.mode == brain.FIGHT


def test_a_killed_target_is_released_once_the_tracker_lets_go_and_the_trace_stops_naming_it():
    """postfreeze30: the brain stopped engaging a killed bot 0.94 s after its last sighting, but kept naming it as the target, so the
    trace showed the dead bot held for five seconds. Held while its id coasts; released after, target cleared; a new bot is picked as usual."""
    m = Memory()
    a = det(1280, 720, 600, track=1)
    decide(st(-0.1, [a]), m)                                                    # seen at the previous decision: acquisition needs two in a row
    assert decide(st(0.0, [a]), m) == Engage(a)
    assert decide(st(0.8, [], coasting=(1,)), m) == Engage(a) and m.target.track == 1      # the tracker still holds it: kept
    released = decide(st(1.6, [], coasting=()), m)                                         # let go, and past LOST_S
    assert not isinstance(released, Engage) and m.target is None
    b = det(900, 720, 500, track=2)
    decide(st(1.9, [b]), m)                                                          # a new bot: seen at two decisions in a row
    assert decide(st(2.0, [b]), m) == Engage(b) and m.target.track == 2


def test_a_brief_flicker_within_lost_s_keeps_the_target():
    m = Memory()
    a = det(1280, 720, 600, track=1)
    decide(st(-0.1, [a]), m)
    decide(st(0.0, [a]), m)
    decide(st(brain.LOST_S / 2, [], coasting=()), m)
    assert m.target is not None and m.target.track == 1


def test_a_box_seen_at_a_single_decision_is_never_engaged():
    """postfreeze30: the door's last false boxes are slivers in one frame each, and one sighting started a combo held ~3 s."""
    m = Memory()
    sliver = det(1270, 780, 128, w=21, track=5)
    assert not isinstance(decide(st(0.0, [sliver]), m), Engage) and m.target is None
    assert not isinstance(decide(st(0.1, []), m), Engage) and m.target is None
    other = det(1400, 700, 130, w=22, track=6)                                  # another one-frame sliver, elsewhere: still nothing
    assert not isinstance(decide(st(0.2, [other]), m), Engage) and m.target is None


def test_a_held_target_survives_a_single_missing_decision_and_is_taken_back_by_its_id_at_once():
    m = Memory()
    a = det(1280, 720, 600, track=1)
    decide(st(-0.1, [a]), m)
    assert decide(st(0.0, [a]), m) == Engage(a)
    assert decide(st(0.1, [], coasting=()), m) == Engage(a)                      # one decision without it (not even coasting): kept, LOST_S
    back = det(1300, 720, 600, track=1)                                          # back, a little moved: its own id, no two-in-a-row needed
    assert decide(st(0.2, [back]), m) == Engage(back) and m.target is back


def _chain(reverse):
    tr = Tracker()
    run(tr, [[det(1000, 700, 600, w=250)]] * 5)
    pieces = [det(x, 700, 80, w=140) for x in (1155, 1240, 1325, 1410, 1495)]      # only the first lies inside the body
    got = tr.update([det(1000, 700, 600, w=250)] + (pieces[::-1] if reverse else pieces), 5 / HZ, FRAME)
    by_x = {round((d.bbox[0] + d.bbox[2]) / 2): d.track for d in got[1:]}
    return got[0].track, by_x, tr


def test_an_absorbed_piece_is_never_a_witness_so_the_body_does_not_chain_outward():
    """Input-path review: absorbed groups were witnesses for the next, growing the footprint box by box, and the result depended on the
    order (HEAD [1,1,1,1,1,1] forward, [1,2,3,4,5,1] reversed). Only bodies matched on their own are witnesses."""
    body, fwd, tr = _chain(False)
    _, rev, _ = _chain(True)
    assert fwd[1155] == body and all(fwd[x] != body for x in (1240, 1325, 1410, 1495))
    assert {x: t == body for x, t in fwd.items()} == {x: t == body for x, t in rev.items()}        # the same partition either way
    assert len({fwd[x] for x in (1240, 1325, 1410, 1495)}) == 4                                     # each outside box its own id
    held = next(t for t in tr.tracks if t.id == body)
    assert held.box[2] <= 1155 + 70 + 1                                              # the body's box reaches no further than its piece
