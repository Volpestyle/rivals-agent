"""AsyncJev against a transport whose requests are futures the test resolves by hand. No network."""
from collections import Counter
from concurrent.futures import Future

import pytest

from agent import brain, jev
from agent.brain import BURST_HOLD_S, Memory
from agent.intents import BURST, Combo, Engage, Idle, Search
from agent.jev import AsyncJev, TransportError, legal, name_of, story_loop
from agent.state import ANCHOR, ENEMY, PULL, SWING, UPPERCUT, Ability, Detection, State

FRAME = (2560, 1440)
READY = {SWING: Ability(True, 3), PULL: Ability(True), UPPERCUT: Ability(True, 2)}


def enemy(x=1280, tagged=None, h=300):  # h = bbox height px: 600 near, 300 mid on a 1440 px frame
    return Detection(ENEMY, (x - h / 4, 720 - h / 2, x + h / 4, 720 + h / 2), 0.9, tagged=tagged)


def st(t, **kw):
    kw.setdefault("frame", FRAME)
    kw.setdefault("hp", 100)
    kw.setdefault("max_hp", 100)
    kw.setdefault("abilities", dict(READY))
    kw.setdefault("webs", 3)
    kw.setdefault("on_target", True)
    return State(t=t, **kw)


def mid_unaimed(t, x=1280, **kw):
    """Scripted answer: Engage, with no hold. Offered to Jev: engage, search, idle, disengage."""
    return st(t, detections=[enemy(x, tagged=False)], on_target=False, **kw)


def near(t, tagged=False, **kw):
    """Scripted answer: Engage, with no hold. Jev may also be offered pull and burst."""
    return st(t, detections=[enemy(tagged=tagged, h=600)], **kw)


def reply(intent, target=None, anchor=None):
    def ans(choice):
        return {"type": "choice", "choice": choice, "probabilities": {choice: 1.0}, "confidence": 0.9}

    a = {"intent": ans(intent)}
    if target is not None:
        a["target"] = ans(str(target))
    if anchor is not None:
        a["anchor"] = ans(str(anchor))
    return {"answers": a, "usage": {"input_tokens": 500, "output_tokens": 50, "cost": 2e-5}}


class Air:
    """Transport double: submit() hands back a Future the test resolves whenever it likes."""

    def __init__(self):
        self.futures, self.bodies = [], []

    def submit(self, body):
        f = Future()
        self.futures.append(f)
        self.bodies.append(body)
        return f


def asked_then(scene, answer, *land_ticks):
    """Tick 0 sends a request about `scene`; `answer` lands (a response, or an exception to fail with);
    then the given States are ticked. Returns (jev, memory, air, intents)."""
    air, m = Air(), Memory()
    j = AsyncJev(air)
    first = j(scene, m)
    assert len(air.futures) == 1 and j.stats.trace == [(scene.t, "scripted")]
    if isinstance(answer, BaseException):
        air.futures[0].set_exception(answer)
    else:
        air.futures[0].set_result(answer)
    return j, m, air, [first] + [j(s, m) for s in land_ticks]


# --- the loop never waits, and one request is in flight ---------------------

def test_scripted_answers_while_one_request_is_in_flight():
    air, m = Air(), Memory()
    j = AsyncJev(air)
    for i in range(6):
        assert j(mid_unaimed(i / 10), m) == Engage(enemy(tagged=False))
    assert len(air.futures) == 1  # never a second while the first is in the air
    assert [src for _, src in j.stats.trace] == ["scripted"] * 6
    assert j.stats.jev_share == 0 and j.stats.calls == 1


def test_landed_answer_is_adopted_as_the_target_is_now_and_the_next_request_goes_out():
    air, m = Air(), Memory()
    j = AsyncJev(air)
    j(mid_unaimed(0.0), m)
    j(mid_unaimed(0.1), m)  # still in the air
    air.futures[0].set_result(reply("engage", target=0))  # lands between ticks 0.1 and 0.2
    moved = enemy(1330, tagged=False)  # drifted, but well inside MATCH_FRAC of the frame height
    assert j(mid_unaimed(0.2, x=1330), m) == Engage(moved)  # the current detection, not the one the question was about
    assert j.stats.trace == [(0.0, "scripted"), (0.1, "scripted"), (0.2, "jev")]
    assert j.stats.sources == Counter(scripted=2, jev=1) and j.stats.jev_share == pytest.approx(1 / 3)
    assert j.stats.age_ms == [pytest.approx(200)] and j.stats.drops == Counter() and j.stats.fallbacks == Counter()
    assert len(air.futures) == 2  # a new request the tick the last one landed


def test_adopted_hold_intents_keep_their_hold():
    """Near range: scripted engages with no hold, but Jev is offered the burst and may choose it."""
    j, m, air, intents = asked_then(near(0.0), reply("burst", target=0), near(0.1))
    assert intents[1] == Combo(BURST, enemy(tagged=False, h=600)) and j.stats.sources["jev"] == 1
    assert j.stats.chosen == Counter(burst=1)
    assert m.hold_until == pytest.approx(0.1 + BURST_HOLD_S)


def test_adopted_answer_without_a_target():
    j, m, air, intents = asked_then(mid_unaimed(0.0), reply("idle"), mid_unaimed(0.1))
    assert intents[1] == Idle() and j.stats.sources["jev"] == 1


# --- answers that are not adopted --------------------------------------------

DROPS = [
    ("stale", mid_unaimed(0.0), reply("engage", target=0), mid_unaimed(0.7)),  # 0.7 s old > MAX_AGE_S
    ("situation", mid_unaimed(0.0), reply("engage", target=0), near(0.2)),  # asked at range, lands in melee
    ("target_gone", mid_unaimed(0.0), reply("engage", target=0), mid_unaimed(0.2, x=200)),  # nothing near where it was
    ("illegal", near(0.0), reply("pull", target=0), near(0.2, tagged=True)),  # the tag appeared meanwhile
    ("illegal", near(0.0), reply("pull", target=0), near(0.2, abilities=dict(READY, **{PULL: Ability(False)}))),
    ("detector_down", mid_unaimed(0.0), reply("engage", target=0), st(0.55, detections=None)),
]


@pytest.mark.parametrize("reason,ask,answer,land", DROPS)
def test_a_landed_answer_that_is_no_longer_valid_is_dropped_and_counted(reason, ask, answer, land):
    j, m, air, intents = asked_then(ask, answer, land)
    assert j.stats.drops == Counter({reason: 1}) and j.stats.sources["jev"] == 0
    assert j.stats.trace[-1][1] == ("gate" if reason == "gated" else "scripted")
    assert intents[1] == brain.decide(land, Memory()) or reason == "gated"  # the scripted answer stood


def test_an_answer_that_lands_inside_a_hold_the_scripted_policy_started_is_gated():
    air, m = Air(), Memory()
    j = AsyncJev(air)
    j(mid_unaimed(0.0), m)  # asked while nothing held
    aimed = st(0.1, detections=[enemy(tagged=False)])  # now aimed at mid range: scripted starts a burst hold
    first = j(aimed, m)
    assert isinstance(first, Combo) and len(air.futures) == 1
    air.futures[0].set_result(reply("engage", target=0))
    assert j(st(0.2, detections=[enemy(tagged=False)]), m) is first  # the hold goes on
    assert j.stats.drops == Counter(gated=1) and j.stats.trace[-1] == (0.2, "gate")


def test_no_request_is_sent_on_a_tick_that_starts_a_hold_and_one_goes_out_when_it_ends():
    air, m = Air(), Memory()
    j = AsyncJev(air)
    aimed = lambda t: st(t, detections=[enemy(tagged=False)])
    assert isinstance(j(aimed(0.0), m), Combo)  # scripted burst, held 3 s
    for i in range(1, 30):
        j(aimed(i / 10), m)
    assert air.futures == []  # nothing in flight, nothing sent: the gate held the whole time
    j(mid_unaimed(BURST_HOLD_S + 0.1), m)
    assert len(air.futures) == 1


def test_max_age_is_the_bound_and_is_named():
    assert jev.MAX_AGE_S == 0.6
    j, m, air, intents = asked_then(mid_unaimed(0.0), reply("idle"), mid_unaimed(jev.MAX_AGE_S))
    assert j.stats.sources["jev"] == 1  # exactly at the bound is still fresh
    j, m, air, intents = asked_then(mid_unaimed(0.0), reply("idle"), mid_unaimed(jev.MAX_AGE_S + 0.05))
    assert j.stats.drops == Counter(stale=1)


# --- failures -----------------------------------------------------------------

FAILURES = [
    (TimeoutError("socket"), "timeout"),
    (TransportError("HTTP 502"), "http"),
    (ValueError("not json"), "parse"),
    (RuntimeError("anything else"), "http"),
    ({}, "parse"),
    (reply("banana"), "vocab"),
    (reply("burst", target=0), "vocab"),  # a real intent that was not offered (pull/burst need aim here)
]


@pytest.mark.parametrize("bad,reason", FAILURES)
def test_a_failed_or_unusable_answer_is_counted_and_scripted_decides(bad, reason):
    j, m, air, intents = asked_then(mid_unaimed(0.0), bad, mid_unaimed(0.1))
    assert j.stats.fallbacks == Counter({reason: 1}) and j.stats.drops == Counter()
    assert j.stats.trace[-1][1] == "scripted"
    assert len(air.futures) == 2  # and the slot is free again


def test_a_hung_request_holds_the_slot_while_scripted_keeps_answering():
    air, m = Air(), Memory()
    j = AsyncJev(air)
    for i in range(30):  # three seconds of ticks, the request never lands
        j(mid_unaimed(i / 10), m)
    assert len(air.futures) == 1 and j.stats.sources == Counter(scripted=30)
    air.futures[0].set_exception(TimeoutError("socket cap"))  # the transport's own cap ends it
    j(mid_unaimed(3.0), m)
    assert j.stats.fallbacks == Counter(timeout=1) and len(air.futures) == 2


def test_a_submit_that_raises_is_a_counted_fallback_and_the_tick_still_answers():
    class Broken:
        def submit(self, body):
            raise TimeoutError("previous call still in flight")

    j = AsyncJev(Broken())
    assert j(mid_unaimed(0.0), Memory()) == Engage(enemy(tagged=False))
    assert j.stats.fallbacks == Counter(http=1) and j.stats.calls == 0


# --- when a request is (not) sent ---------------------------------------------

def test_no_request_when_the_gate_decides_or_the_detector_is_down():
    air = Air()
    j = AsyncJev(air)
    assert isinstance(j(st(0.0, hp=20, detections=[enemy()]), Memory()), brain.Disengage)  # retreat
    assert j(st(0.0, detections=None), Memory()) == Idle()  # detector down, no target
    assert air.futures == [] and j.stats.trace == [(0.0, "gate"), (0.0, "scripted")]


def test_requests_carry_the_state_asked_about():
    air = Air()
    AsyncJev(air)(near(0.0), Memory())
    body, = air.bodies
    assert body["model"] == jev.MODEL and body["state"]["targets"][0]["range"] == "near"
    assert "pull" in body["questions"]["intent"]["criteria"]


def test_decide_jev_is_the_nonblocking_variant(monkeypatch):
    air = Air()
    monkeypatch.setattr(jev, "_default", AsyncJev(air))
    assert jev.decide_jev(mid_unaimed(0.0), Memory()) == Engage(enemy(tagged=False))
    assert isinstance(jev.default(), AsyncJev) and len(air.futures) == 1


# --- the whole story ----------------------------------------------------------

class Rotating:
    """Answers every request at once, choosing offered intents in turn (target and anchor 0)."""

    def __init__(self):
        self.n = 0

    def submit(self, body):
        names = list(body["questions"]["intent"]["criteria"])
        name = names[self.n % len(names)]
        self.n += 1
        f = Future()
        f.set_result(reply(name, target=0 if "target" in body["questions"] else None,
                           anchor=0 if "anchor" in body["questions"] else None))
        return f


def test_over_the_synthetic_story_every_adopted_answer_is_legal_and_every_tick_is_logged():
    j, m, adopted, n = AsyncJev(Rotating()), Memory(), 0, 400
    for s in story_loop(n, 10):
        intent = j(s, m)
        if j.stats.trace[-1][1] == "jev":
            adopted += 1
            det = getattr(intent, "target", None) or getattr(intent, "anchor", None)
            assert legal(name_of(intent), s, det), (s.t, intent)
    st_ = j.stats
    assert len(st_.trace) == n == sum(st_.sources.values())
    assert [t for t, _ in st_.trace] == sorted(t for t, _ in st_.trace)
    assert adopted == st_.sources["jev"] > 0 and st_.sources["scripted"] > 0 and st_.sources["gate"] > 0
    assert set(st_.drops) <= {"gated", "stale", "situation", "target_gone", "illegal", "detector_down"}
    assert not st_.fallbacks


def test_bench_async_reports_the_share():
    out = jev.bench_async(300, 0, transport=Rotating())
    assert out["ticks"] == 300 and sum(out["decided_by"].values()) == 300
    assert 0 < out["jev_share_of_ticks"] < 1 and out["jev_share_of_choices"] >= out["jev_share_of_ticks"]
    assert out["tick_wall_ms"]["max"] < 50  # it never waits
    assert sum(out["jev_chose"].values()) == out["decided_by"]["jev"]
    assert sum(out["jev_differs_from_scripted"].values()) <= out["decided_by"]["jev"]  # Rotating disagrees sometimes
