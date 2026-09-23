"""The tracker's current body witness in range mode (VUH-1314): what it unites, what it refuses. No game, no pad, no data/."""
from dataclasses import replace

import pytest

from agent import loop as runtime
from agent.controller import ARM_FRAMES, Controller, near_h
from agent.intents import Idle, RangeSkill, RangeSkillResources
from agent.state import Detection, ENEMY, TARGET, State
from agent.tracker import PIECE_PAD, TrackedBody, TrackingObservation, Tracker
from tests.test_loop import BOT, FakePad, Frames, readers, timeline
from tests.test_range_skill_loop import EventBrain

F720, F1440 = (1280, 720), (2560, 1440)
INVALID, MISSING = "invalid_tracking_observation", "target_missing_or_ambiguous"


def E(box, **fields):                           # the reflex finder's box: ENEMY, conf .9, no distance
    return Detection(ENEMY, tuple(float(v) for v in box), .9, **fields)


# Galacta slot 4 (galacta-pilot-20260922-04-learned, docs/evidence/range-support-followup-20260922): the whole box of
# decision 52's ticks, then the reflex fragments of decisions 53 and 54 (rows 290 and 295). The tracker gives each set one id.
WHOLE = E((1047, 564, 1521, 1090))
D53 = [E((1376, 650, 1509, 858)), E((1140, 610, 1223, 817)), E((1154, 892, 1234, 1091)), E((1451, 931, 1521, 969))]
D54 = [E((1140, 608, 1223, 813)), E((1377, 624, 1492, 764)), E((1161, 888, 1236, 1032)), E((1451, 788, 1511, 856)),
       E((1451, 927, 1521, 966))]


def paired(frame, whole, pieces, proposal="start", observation=True, others=()):
    """Arm on `whole` (the target, id 1) plus `others`, then one tick on `pieces` + `others`, the way the loop pairs them."""
    tracker, c = Tracker(), Controller()
    for i in range(ARM_FRAMES):
        t = i * .02
        raw = tracker.update([whole, *others], t, frame)
        c.step(State(t, frame, detections=raw), RangeSkill(raw[0], "no_new_start", i, t + .1, RangeSkillResources(5, t)), intent_t=t)
    t, kw = ARM_FRAMES * .02, {}
    if observation:
        snap = tracker.observe([*pieces, *others], t, frame)
        raw, kw["tracking_observation"] = list(snap.raw), snap
    else:
        snap, raw = None, tracker.update([*pieces, *others], t, frame)
    intent = RangeSkill(replace(whole, track=1), proposal, 100, t + .1, RangeSkillResources(5, t))
    pad = c.step(State(t, frame, detections=raw, coasting=tuple(tracker.coasting)), intent, intent_t=t, **kw)
    return c, raw, pad, snap


def target_body(snap, track=1):
    return next(b for b in snap.bodies if b.track == track)


# -- the demonstrated failure, repaired ---------------------------------------------------------------------------------
@pytest.mark.parametrize("proposal,reason", [("start", "accepted"), ("no_new_start", "no_new_start")])
def test_native_d53_fragments_are_one_measured_body_without_changing_raw(proposal, reason):
    head, _, refused, _ = paired(F1440, WHOLE, D53, proposal, observation=False)
    assert head.range_skill_trace["reason"] == MISSING and refused["lt"] == refused["ly"] == 0 and head.stable == 0
    c, raw, pad, snap = paired(F1440, WHOLE, D53, proposal)
    assert [d.bbox for d in raw] == [d.bbox for d in D53] and {d.track for d in raw} == {1}   # the decision path keeps the fragments
    body = target_body(snap)
    assert body.how == "matched" and len(body.own) == 1 and len(body.pieces) == 3 and body.reference is not None
    trace = c.range_skill_trace
    assert trace["reason"] == reason and c.stable > ARM_FRAMES
    assert trace["body_observation"]["member_count"] == 4
    assert trace["body_observation"]["bbox"] == (1140, 610, 1521, 1091)
    assert trace["body_observation"]["plate_count"] == 0 and trace["body_observation"]["approach_withheld"] is True
    assert pad["lt"] == (1.0 if proposal == "start" else 0.0) and pad["ly"] == 0.0


def test_fragment_ticks_withhold_approach_that_their_short_union_would_command():
    """Their union measures the body short (d54: 424 px against the 526 px whole box, under near_h), so it would walk at a bot
    already in near range. Fragments aim and arm; they never walk. Whole-box ticks before them are the raw rule's, pad for pad."""
    def run(observation):
        tracker, c, out = Tracker(), Controller(), []
        ticks = [WHOLE] * 8 + [D53, D54, D53, D54] + [WHOLE] * 2
        for i, dets in enumerate(ticks):
            t = i * .02
            dets = dets if isinstance(dets, list) else [dets]
            if observation:
                snap = tracker.observe(dets, t, F1440)
                raw, kw = list(snap.raw), {"tracking_observation": snap}
            else:
                raw, kw = tracker.update(dets, t, F1440), {}
            pad = c.step(State(t, F1440, detections=raw, coasting=tuple(tracker.coasting)),
                         RangeSkill(raw[0], "no_new_start", i, t + .1, RangeSkillResources(5, t)), intent_t=t, **kw)
            out.append((pad, c.range_skill_trace["reason"], c.range_skill_trace["body_observation"], c.track and c.track.h))
        return out
    head, now = run(False), run(True)
    assert [p for p, *_ in now[:8]] == [p for p, *_ in head[:8]]                       # whole-box neighbours: unchanged
    assert all(b["member_count"] == 1 and not b["approach_withheld"] for _, _, b, _ in now[:8] + now[12:])
    assert [r for _, r, _, _ in head[8:12]] == [MISSING] * 4
    for pad, reason, body, h in now[8:12]:
        assert reason == "no_new_start" and body["approach_withheld"] and body["member_count"] in (4, 5) and pad["ly"] == 0
    assert now[9][3] / F1440[1] < near_h()                                                # not near by the union: the rule holds it


# -- genuine identity conflicts stay refused ---------------------------------------------------------------------------
@pytest.mark.parametrize("frame,whole,pieces", [
    (F720, E((600, 380, 680, 580)), [E((600, 380, 680, 580)), E((610, 270, 660, 375))]),       # S3: a smaller bot stacked on its head,
    (F1440, E((1100, 300, 1350, 500)), [E((1100, 300, 1350, 500)), E((1100, 510, 1350, 710))]),  # S4: tracker.md's 250x200 pair
    (F720, E((630, 350, 640, 370)), [E((630, 350, 640, 370)), E((631, 372, 639, 388))]),       # S5b: two beyond-reach boxes
    (F720, E((630, 350, 640, 370)), [E((630, 350, 640, 370)), E((631, 332, 639, 348))]),       # S5c: ... the other way up
    (F720, E((600, 260, 680, 460)), [E((600, 260, 680, 350)), E((600, 355, 680, 460))]),       # a clean split-in-two looks the same
], ids=["S3-stacked-bot", "S4-lane-hole", "S5b-reach", "S5c-reach", "split-in-two"])
def test_boxes_joined_as_stacked_are_never_united(frame, whole, pieces):
    head, _, _, _ = paired(frame, whole, pieces, observation=False)
    c, _, pad, snap = paired(frame, whole, pieces)
    assert len(target_body(snap).own) == 2                                               # one `_bodies` group, not pieces
    assert c.range_skill_trace["reason"] == head.range_skill_trace["reason"] == MISSING
    assert pad["lt"] == pad["ly"] == 0 and c.stable == 0 and c.range_skill_trace["body_observation"] is None


def test_smaller_bot_inside_a_near_bot_is_a_piece_that_does_not_move_the_union():
    """The residual in docs/lanes/tracker.md: geometry cannot tell it from a piece. On the update it is taken it adds no area, so the
    measurement is the near bot's. That does not last by itself: the track's box keeps it, the next update's pieces are tested against
    that box, and the union could follow it out of the body (the next test); the `whole` cap stops that."""
    c, _, pad, snap = paired(F1440, E((1000, 400, 1250, 1000)), [E((1000, 400, 1250, 1000)), E((1030, 450, 1155, 750))])
    assert len(target_body(snap).pieces) == 1
    assert c.range_skill_trace["body_observation"]["bbox"] == (1000, 400, 1250, 1000) and pad["ly"] == 0


@pytest.mark.parametrize("target,intruder", [
    ((1150, 420, 1400, 1020), (1300, 650, 1395, 950)),                  # T3a: a smaller bot steps out of a near target, 240 px/s
    ((950, 420, 1200, 1020), (1100, 650, 1195, 950)),                   # T3b: ...across the crosshair, the target left of it
], ids=["T3a", "T3b"])
def test_a_second_bot_absorbed_once_is_not_followed_out_of_the_target(target, intruder):
    """Review T3: the tracker keeps both under the target's id as the second walks out, a piece at a time. The union may not leave the
    target's own box, padded as a piece is, and no start is accepted while the crosshair is on the second bot and not the target."""
    def run(observation):
        tracker, c, out = Tracker(), Controller(), []
        for i in range(66):
            t, k = i / 60, max(0, i - 6)
            walker = (intruder[0] + 4 * k, intruder[1], intruder[2] + 4 * k, intruder[3])
            boxes = [target] if i < 6 else [target, walker]
            if observation:
                snap = tracker.observe([E(b) for b in boxes], t, F1440)
                raw, kw = list(snap.raw), {"tracking_observation": snap}
            else:
                raw, kw = tracker.update([E(b) for b in boxes], t, F1440), {}
            pad = c.step(State(t, F1440, detections=raw, coasting=tuple(tracker.coasting)),
                         RangeSkill(E(target, track=1), "start", i, t + .1, RangeSkillResources(5, t)), intent_t=t, **kw)
            out.append((walker, [d.track for d in raw], c.range_skill_trace, pad))
        return out

    cap = PIECE_PAD * max(target[2] - target[0], target[3] - target[1])

    def inside(b):
        return target[0] - cap <= b[0] and target[1] - cap <= b[1] and b[2] <= target[2] + cap and b[3] <= target[3] + cap

    def on(b):
        return b[0] <= 1280 <= b[2] and b[1] <= 720 <= b[3]
    head, now = run(False), run(True)
    assert all(ids == [1, 1] for _, ids, _, _ in now[6:])                                 # the tracker never lets go of it
    assert not any(trace["accepted"] for _, _, trace, _ in head[6:])                   # HEAD: two boxes, one id, refused
    for walker, _, trace, pad in now[6:]:
        body = trace["body_observation"]
        assert body is None or inside(body["bbox"])
        if not inside(walker):
            assert trace["reason"] == MISSING and pad["lt"] == pad["ly"] == 0
        assert not (trace["accepted"] and on(walker) and not on(target))
    assert any(not inside(w) for w, *_ in now)                                            # it does walk out,
    assert any(t["body_observation"] and t["body_observation"]["member_count"] == 2 for _, _, t, _ in now)   # after being a piece


@pytest.mark.parametrize("distances,reason", [((13., None, None, None), MISSING), ((13., 20., 13., 13.), MISSING),
                                              ((13., 13., 13., 13.), "no_new_start")])
def test_members_that_disagree_about_distance_are_not_one_measurement(distances, reason):
    pieces = [replace(d, distance=k) for d, k in zip(D53, distances)]
    c, _, pad, _ = paired(F1440, replace(WHOLE, distance=13.), pieces, "no_new_start")
    assert c.range_skill_trace["reason"] == reason


def test_a_well_formed_witness_without_the_target_reports_it_missing():
    tracker, c = Tracker(), Controller()
    for i in range(ARM_FRAMES):
        raw = tracker.update([BOT], i * .02, F1440)
        c.step(State(i * .02, F1440, detections=raw), RangeSkill(raw[0], "no_new_start", i, i * .02 + .1,
                                                                RangeSkillResources(5, i * .02)), intent_t=i * .02)
    snap = tracker.observe([E((100, 100, 140, 200))], 3.0, F1440)                       # the target expired: not held, not coasting
    c.step(State(3.0, F1440, detections=list(snap.raw), coasting=snap.coasting),
           RangeSkill(replace(BOT, track=1), "start", 100, 3.1, RangeSkillResources(5, 3.0)), intent_t=3.0, tracking_observation=snap)
    assert 1 not in snap.coasting and c.range_skill_trace["reason"] == MISSING


def test_an_unrelated_box_cannot_veto_the_target():
    """Only the target's members are held to the target checks; another id's box needs only a type and its place in the partition."""
    flat = E((200, 820, 260, 820))                                                       # zero height: outline.py's rounding edge
    loud = replace(E((300, 700, 360, 820)), conf=1.2)
    c, _, _, snap = paired(F1440, WHOLE, D53, "no_new_start", others=(flat, loud))
    assert len(snap.bodies) == 3 and c.range_skill_trace["reason"] == "no_new_start"
    target, a, b = replace(WHOLE, track=1), E((200, 700, 260, 820), track=2), E((205, 760, 255, 800), track=2)
    for reference, expected in (((5., 5., 5., 5.), target), (None, INVALID)):           # nor another body's degenerate reference
        other = TrackedBody(2, ENEMY, "matched", (1,), ((2,),), reference, None, (200., 700., 260., 820.))
        mine = TrackedBody(1, ENEMY, "matched", (0,), (), None, None, target.bbox)
        witness = TrackingObservation(1.0, F1440, (target, a, b), (), (mine, other))
        got = Controller._range_body_measurement(State(1.0, F1440, detections=[target, a, b]), target, witness)
        assert (got[0] if isinstance(got, tuple) else got) == expected


# -- a witness that is not this State's, or not the tracker's association ------------------------------------------------
def _body(target=True, **changes):
    return lambda state, snap: (state, replace(snap, bodies=tuple(replace(b, **changes) if (b.track == 1) == target else b
                                                                  for b in snap.bodies)))


def _raw(i, **changes):
    def mutate(state, snap):
        raw = list(snap.raw)
        raw[i] = replace(raw[i], **changes)
        return replace(state, detections=list(raw)), replace(snap, raw=tuple(raw))
    return mutate


def _pieces(edit):
    return lambda state, snap: (state, replace(snap, bodies=tuple(replace(b, pieces=edit(b.pieces)) if b.track == 1 else b
                                                                  for b in snap.bodies)))


@pytest.mark.parametrize("mutate", [
    lambda state, snap: (state, replace(snap, t=snap.t - .02)),                              # an older update's witness
    lambda state, snap: (state, replace(snap, frame=F720)),
    lambda state, snap: (replace(state, coasting=(7,)), snap),
    lambda state, snap: (replace(state, detections=list(snap.raw[:-1])), snap),              # not this State's boxes
    _body(bbox=(1100, 610, 1521, 1091)),                                         # a union it does not have
    _pieces(lambda p: p[:-1]),                                                               # a member left out
    _pieces(lambda p: p + p[:1]),                                                            # a member counted twice
    _raw(1, cls=TARGET),                                                                     # a mixed-class body
    _body(how="entering"),                                                        # pieces on a body not matched itself
    _body(reference=None),                                                        # pieces tested against nothing
    _body(False, reference=(0., 0., 10., 10.)),                                                    # a reference with no pieces
    _body(False, whole=(0., 0., 10., 10.)),                                                        # a whole box with no pieces
    _body(whole=(float('nan'), 564., 1521., 1090.)),                                               # a whole box not finite
    _body(whole=(1047., 564., 1521.)),                                                             # a whole box not a box
    lambda state, snap: (state, replace(snap, bodies=snap.bodies[:-1])),                     # a box in no body
], ids=["stale-t", "frame", "coasting", "raw-not-state", "forged-bbox", "member-dropped", "member-twice", "cross-class",
        "pieces-unmatched", "no-reference", "stray-reference", "stray-whole", "nan-whole", "short-whole",
        "not-a-partition"])
def test_a_malformed_witness_refuses_as_a_contract_fault(mutate):
    tracker, c = Tracker(), Controller()
    others = (E((200, 700, 260, 820)),)
    for i in range(ARM_FRAMES):
        raw = tracker.update([WHOLE, *others], i * .02, F1440)
        c.step(State(i * .02, F1440, detections=raw), RangeSkill(raw[0], "no_new_start", i, i * .02 + .1,
                                                                RangeSkillResources(5, i * .02)), intent_t=i * .02)
    t = ARM_FRAMES * .02
    snap = tracker.observe([*D53, *others], t, F1440)
    state, snap = mutate(State(t, F1440, detections=list(snap.raw), coasting=snap.coasting), snap)
    pad = c.step(state, RangeSkill(replace(WHOLE, track=1), "start", 100, t + .1, RangeSkillResources(5, t)), intent_t=t,
                 tracking_observation=snap)
    assert c.range_skill_trace["reason"] == INVALID and pad["lt"] == pad["ly"] == 0 and c.stable == 0
    assert c.range_skill_trace["body_observation"] is None


A, B = E((20, 100, 60, 200), track=1), E((1200, 500, 1260, 700), track=1)    # S7: one id on boxes 1180 px apart


SPAN = (20., 100., 1260., 700.)
FAR = (E((100, 300, 160, 450), track=1), E((1000, 300, 1060, 450), track=1))


@pytest.mark.parametrize("raw,own,pieces,reference,whole,reason", [
    ((A, B), (0,), ((1,),), A.bbox, A.bbox, INVALID),       # claimed as a piece: not inside its body the way _body_of requires
    ((A, B), (0,), ((1,),), SPAN, SPAN, MISSING),           # ...with a reference forged round both: no gate could have matched it
    ((A, B), (0, 1), (), None, None, MISSING),              # grouped by id as one box group: never united
    (FAR, (0,), ((1,),), FAR[1].bbox, (100., 300., 1060., 450.), INVALID),     # the piece's own box as reference, 900 px from
                                                                               # `own`: only the centre bound refuses it
    ((A, replace(A, bbox=(25., 110., 55., 190.))), (0,), ((1,),), A.bbox, None, MISSING),   # a real piece, no recent one-box box
], ids=["claimed-piece", "forged-reference", "grouped-by-id", "centre-bound", "no-whole"])
def test_a_hand_built_witness_cannot_unite_distant_boxes(raw, own, pieces, reference, whole, reason):
    members = [raw[i] for i in own + sum(pieces, ())]
    bbox = tuple(f(d.bbox[k] for d in members) for k, f in enumerate((min, min, max, max)))
    body = TrackedBody(1, ENEMY, "matched", own, pieces, reference, whole, bbox)
    got = Controller._range_body_measurement(State(1.0, F720, detections=list(raw)), raw[0],
                                             TrackingObservation(1.0, F720, raw, (), (body,)))
    assert got == reason


# -- equivalence, detachment and the refusal trace ---------------------------------------------------------------------
@pytest.mark.parametrize("frame,whole", [(F720, E((600, 260, 680, 460))), (F1440, WHOLE)])
@pytest.mark.parametrize("proposal", ["start", "no_new_start"])
def test_a_single_box_body_is_the_raw_rule_exactly(frame, whole, proposal):
    head, _, before, _ = paired(frame, whole, [whole], proposal, observation=False)
    now, _, after, _ = paired(frame, whole, [whole], proposal)
    assert after == before and now.range_skill_trace["reason"] == head.range_skill_trace["reason"]
    assert head.range_skill_trace["body_observation"]["source"] == "raw_single"
    assert now.range_skill_trace["body_observation"]["source"] == "tracker_current_body"
    assert now.range_skill_trace["body_observation"]["member_count"] == 1


def test_a_later_update_leaves_a_taken_snapshot_unchanged_and_observe_returns_update_output():
    a, b = Tracker(), Tracker()
    for i in range(6):
        a.update([WHOLE], i * .02, F1440)
        b.update([WHOLE], i * .02, F1440)
    snap, out = a.observe(D53, .12, F1440), b.update(D53, .12, F1440)
    assert list(snap.raw) == out and snap.coasting == b.coasting
    before = (snap.raw, snap.coasting, snap.bodies)
    a.update([], .14, F1440)
    a.update([E((100, 100, 140, 200))], .16, F1440)
    assert (snap.raw, snap.coasting, snap.bodies) == before


def test_a_refusal_after_measurement_carries_no_body():
    """invalid_press_calibration refuses after the body was measured; the refused trace must not carry it."""
    c2 = Controller()
    c2.cal = replace(c2.cal, press_s=0.0)
    tracker = Tracker()
    for i in range(ARM_FRAMES + 1):
        t = i * .02
        snap = tracker.observe([E((600, 260, 680, 460))], t, F720)
        request = "start" if i == ARM_FRAMES else "no_new_start"
        c2.step(State(t, F720, detections=list(snap.raw)), RangeSkill(snap.raw[0], request, i, t + .1, RangeSkillResources(5, t)),
                intent_t=t, tracking_observation=snap)
    assert c2.range_skill_trace["reason"] == "invalid_press_calibration"
    assert c2.range_skill_trace["body_observation"] is None


# -- the loop hands the witness over in range mode only ------------------------------------------------------------------
class Spy(Controller):
    def step(self, state, intent, intent_t=None, execution_t=None, **kw):
        self.seen = getattr(self, "seen", []) + [kw.get("tracking_observation")]
        return super().step(state, intent, intent_t, execution_t, **kw)


class Rows:
    def __init__(self):
        self.rows = []

    def write(self, row, frame=None):
        self.rows.append(row)

    def close(self, *args):
        pass


class IdsOnly:
    """A tracker with ids and no `observe`: range mode keeps the raw single-box rule."""
    coasting = ()

    def update(self, dets, t, frame=None, cam=None, clip=None):
        return [replace(d, track=1) for d in dets]


def _range_run(tracker=None):
    spy, log = Spy(), Rows()
    runtime.Loop(Frames(timeline(.65, dets=[BOT])), FakePad(), readers(), EventBrain(), controller=spy, tracker=tracker,
                 brain_name="range-skill", max_s=1, scoreboard=False, log=log).run()
    steps = [r for r in log.rows if r.get("range_skill_trace", {}).get("event") == "step"]
    return spy, log.rows, steps


def test_range_mode_passes_the_witness_and_logs_the_body_and_the_coasting_it_used():
    spy, rows, steps = _range_run()
    assert spy.seen and all(type(s) is TrackingObservation for s in spy.seen)
    measured = [r["range_skill_trace"]["body_observation"] for r in steps if r["range_skill_trace"]["body_observation"]]
    assert measured and all(b["source"] == "tracker_current_body" and b["member_count"] == 1 for b in measured)
    assert all(r["coasting"] == [] for r in steps)                                      # origin's reflex coasting, a list
    states = [r["state"] for r in rows if "state" in r]
    assert states and all([tuple(d["bbox"]) for d in s["detections"]] == [BOT.bbox] for s in states)


@pytest.mark.parametrize("tracker", [IdsOnly(), runtime.NoTracker()], ids=["ids-no-observe", "no-tracker"])
def test_range_mode_without_observe_keeps_the_raw_rule(tracker):
    spy, _, steps = _range_run(tracker)
    assert spy.seen and all(s is None for s in spy.seen)
    bodies = [r["range_skill_trace"]["body_observation"] for r in steps if r["range_skill_trace"]["body_observation"]]
    if isinstance(tracker, IdsOnly):
        assert bodies and all(b["source"] == "raw_single" for b in bodies)
    else:
        assert not bodies                                                                # no id at all: invalid_target, as before


def test_legacy_mode_never_passes_a_witness():
    spy = Spy()
    runtime.Loop(Frames(timeline(.3, dets=[BOT])), FakePad(), readers(), lambda state, memory: Idle(), controller=spy,
                 warmup=False).run()
    assert spy.seen and all(s is None for s in spy.seen)
