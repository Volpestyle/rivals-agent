"""Observed option status (VUH-1315): an option ends on evidence, and a timeout is only its named upper bound. Stdlib only.

One test per acceptance point of the issue (docs/lanes/l5-brain.md, "Observed option status"): the status the brain reads and the
evidence that decided it; a KO or a lost target ends the option at once; the hold constants are upper bounds; the recorded burst ends at
its KO; range-skill mode is untouched (the slot-4 replay against the base commit is corpus-marked).
"""
import io
import json
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from agent import brain, jev
from agent.brain import (ARRIVAL, BURST_MAX_S, COMPLETED, FAILED, INTERRUPTED, KO_FEED, LOST_S, OPTIONS, OUTSIDE_S, RELEASED,
                         RETREAT_HP, RUNNING, STRIKE_MAX_S, SUPERSEDED, SWING_MAX_S, TRACK_LOST, UPPER_BOUND, Memory, commit, decide)
from agent.controller import Controller
from agent.intents import BURST, Combo, Disengage, Engage, Pull, Search, SwingTo, WebStrike
from agent.learned_range_skill import LearnedRangeSkillBrain
from agent.loop import FakePad, Loop
from agent.state import ANCHOR, ENEMY, PULL, SWING, UPPERCUT, Ability, Detection, State
from tests.test_loop import BOT, F, Frames, readers, sends, timeline

ROOT = Path(__file__).resolve().parents[1]
BASE = "0f71336"      # main when this branch left it: the range-skill replay must match it exactly
FRAME = (2560, 1440)
READY = {SWING: Ability(True, 3), PULL: Ability(True), UPPERCUT: Ability(True, 2)}
ANCH = Detection(ANCHOR, (1800, 200, 1900, 300), 0.8)


def bot(h=300, x=1280, track=1, **kw):          # h px of a 1440 px frame: 300 mid, 600 near, 90 far
    return Detection(ENEMY, (x - h / 4, 720 - h / 2, x + h / 4, 720 + h / 2), 0.9, track=track, **kw)


def st(t, dets=(), feed=None, **kw):
    for k, v in (("hp", 100), ("max_hp", 100), ("abilities", dict(READY)), ("webs", 3), ("on_target", True)):
        kw.setdefault(k, v)
    kw.setdefault("frame", FRAME)
    return State(t=t, detections=list(dets), kill_feed=feed, **kw)


def chosen(m, t, dets, feed=False, **kw):
    """The intent chosen at `t` on `dets`, their ids seen on the decision before (acquisition takes two in a row)."""
    decide(st(round(t - 0.1, 6), dets, feed=feed, **kw), m)
    return decide(st(t, dets, feed=feed, **kw), m)


def burst(m, t=0.0, feed=False, **kw):
    c = chosen(m, t, [bot(**kw)], feed)
    assert c == Combo(BURST, bot(**kw)) and m.option.status == RUNNING and m.option.start_t == t
    return c


def ended(m):
    return m.option.status, m.option.evidence.observation, m.option.evidence.t


# --- 1. the status the brain reads, and the evidence that decided it -----------------------------------------------------------------

def test_a_running_option_names_the_completion_observations_it_could_not_read():
    m = Memory()
    c = burst(m)
    assert decide(st(0.1, [bot()], feed=None), m) is c
    assert (m.option.status, m.option.evidence, m.option.waiting_on) == (RUNNING, None, (KO_FEED,))
    assert decide(st(0.2, [bot()], feed=False), m) is c
    assert m.option.waiting_on == ()
    assert m.option.bound_t == pytest.approx(BURST_MAX_S) and m.option.intent is c


@pytest.mark.parametrize("case", ["ko", "arrival", "lost", "released", "retreat", "bound_read", "bound_unread", "swing_bound",
                                  "superseded"])
def test_every_ending_names_its_observation_and_the_state_time(case):
    m = Memory()
    if case == "ko":
        burst(m)
        decide(st(0.1, [bot()], feed=True), m)
        decide(st(0.2, [], feed=True, coasting=(1,)), m)
        assert ended(m) == (COMPLETED, KO_FEED, 0.2)
        assert m.option.evidence.detail == "kill feed False at 0.000, True at 0.100, 0.200; which bot is not read"
    elif case == "arrival":
        assert isinstance(chosen(m, 0.0, [bot(tagged=True)]), WebStrike)
        assert decide(st(0.3, [bot(600, tagged=True)]), m) == Engage(bot(600, tagged=True))
        assert ended(m) == (COMPLETED, ARRIVAL, 0.3)
    elif case == "lost":
        burst(m)
        decide(st(0.6, [], coasting=()), m)
        assert ended(m) == (INTERRUPTED, TRACK_LOST, 0.6)
    elif case == "released":
        burst(m, x=1907)                                           # outside the aim crop: released after OUTSIDE_S
        decide(st(OUTSIDE_S + 0.1, [bot(x=1907)]), m)
        assert ended(m) == (INTERRUPTED, RELEASED, OUTSIDE_S + 0.1)
    elif case == "retreat":
        burst(m)
        assert decide(st(0.3, [bot()], hp=20), m) == Disengage()
        assert ended(m) == (INTERRUPTED, RETREAT_HP, 0.3)
    elif case == "bound_read":
        burst(m)
        decide(st(BURST_MAX_S, [bot()], feed=False, webs=0), m)
        assert ended(m) == (FAILED, UPPER_BOUND, BURST_MAX_S)      # the feed was read: no KO within the bound
    elif case == "bound_unread":
        burst(m)
        decide(st(BURST_MAX_S, [bot()], feed=None, webs=0), m)
        assert ended(m) == (INTERRUPTED, UPPER_BOUND, BURST_MAX_S)  # an unread feed is not a failure
        assert "ko_feed not read" in m.option.evidence.detail
    elif case == "swing_bound":
        assert chosen(m, 0.0, [bot(90), ANCH]) == SwingTo(ANCH)
        decide(st(SWING_MAX_S, [bot(90), ANCH], abilities={}), m)
        assert ended(m) == (INTERRUPTED, UPPER_BOUND, SWING_MAX_S)  # nothing observes a swing's completion
    elif case == "superseded":
        c = burst(m)
        commit(m, Engage(bot()), 0.4)
        assert ended(m) == (INTERRUPTED, SUPERSEDED, 0.4) and m.option.intent is c


def test_the_status_serialises_for_the_run_log():
    m = Memory()
    burst(m)
    decide(st(0.1, [bot()], feed=True), m)
    decide(st(0.2, [], feed=True, coasting=(1,)), m)
    assert json.loads(json.dumps(m.option.to_dict())) == {
        "kind": "Combo", "target": 1, "start_t": 0.0, "bound_t": BURST_MAX_S, "status": COMPLETED, "waiting_on": [],
        "evidence": {"observation": KO_FEED, "t": 0.2, "detail": "kill feed False at 0.000, True at 0.100, 0.200; which bot is not read"}}


# --- 2. a KO or a lost target ends the option at once; a timeout is only the named bound ----------------------------------------------

def test_a_ko_ends_the_burst_at_once_and_stops_its_primitive():
    m = Memory()
    c = burst(m)
    assert decide(st(0.1, [bot()], feed=True), m) is c and m.stop is None       # one True read is not yet a KO
    got = decide(st(0.2, [], feed=True, coasting=(1,)), m)                      # the bot is down; the tracker still holds its id
    assert got == Search() and m.stop is c                                      # not re-issued through the flicker grace
    assert decide(st(0.3, [], feed=True, coasting=(1,)), m) == Search() and m.stop is None   # the stop is said once


@pytest.mark.parametrize("feeds, ko_at", [
    ((False, True, True), 2),
    ((False, True, None, True), 3),         # None neither counts nor resets
    ((False, True, False, True), None),     # a False read resets the count
    ((True, True, True), None),             # a line already up when first read is no onset
    ((None, None, True, True), None),
    ((False, True, True, True, True), 2),   # one onset is one KO
])
def test_a_ko_is_two_true_reads_after_a_false(feeds, ko_at):
    m, kos = Memory(), []
    for i, feed in enumerate(feeds):
        ev = brain._ko(st(i / 10, feed=feed), m)
        if ev is not None:
            kos.append(i)
            assert ev.observation == KO_FEED and ev.t == i / 10
    assert kos == ([] if ko_at is None else [ko_at])


def test_a_ko_stops_the_latest_attacks_primitive_even_after_its_option_was_interrupted():
    """plaza30: both bursts lost their option to an id change at point blank before the KO, while their primitives played on."""
    m = Memory()
    c = burst(m)
    decide(st(0.6, [bot(track=2)], feed=False, webs=0), m)                      # id 1 lost: interrupted, the primitive plays on
    assert ended(m) == (INTERRUPTED, TRACK_LOST, 0.6) and m.stop is None
    assert decide(st(0.7, [bot(track=2)], feed=True, webs=0), m) == Engage(bot(track=2))   # the same bot by eye, a new id
    decide(st(0.8, [bot(track=2)], feed=True, webs=0), m)
    assert m.stop is c and ended(m) == (INTERRUPTED, TRACK_LOST, 0.6)            # the KO stops it; the status stands as decided


def test_a_ko_stops_no_swing():
    m = Memory()
    assert chosen(m, 0.0, [bot(90), ANCH]) == SwingTo(ANCH)
    decide(st(0.1, [bot(90), ANCH], feed=True), m)
    decide(st(0.2, [bot(90), ANCH], feed=True), m)
    assert m.option.status == RUNNING and m.stop is None


def test_a_lost_target_ends_the_option_at_once():
    m = Memory()
    c = burst(m)
    assert decide(st(0.3, [], coasting=(1,)), m) is c        # briefly missing: the tracker holds its id
    assert decide(st(0.4, [], coasting=()), m) is c          # dropped, last seen within LOST_S: the unconfirmed or untracked grace
    got = decide(st(LOST_S + 0.1, [], coasting=()), m)       # the first State on which it is neither: ended there
    assert not isinstance(got, Combo) and ended(m) == (INTERRUPTED, TRACK_LOST, LOST_S + 0.1)
    assert m.stop is None                                    # track loss alone never stops a primitive (an id change at point blank)


def test_without_ending_evidence_an_option_runs_exactly_to_its_named_bound():
    m = Memory()
    c = burst(m)
    for t in (0.5, 1.5, BURST_MAX_S - 0.01):
        assert decide(st(t, [bot()], feed=False), m) is c
    assert decide(st(BURST_MAX_S, [bot()], feed=False, webs=0), m) == Engage(bot()) and m.option.status == FAILED


def test_a_pull_completes_when_its_target_is_pulled_into_near_range():
    m = Memory()
    p = chosen(m, 0.0, [bot(tagged=False)], webs=0)            # no ammo: no burst, so RB pulls the untagged bot
    assert p == Pull(bot(tagged=False))
    assert decide(st(0.2, [bot(tagged=False)], webs=0), m) is p
    assert decide(st(0.4, [bot(600, tagged=False)], webs=0), m) == Engage(bot(600, tagged=False))
    assert ended(m) == (COMPLETED, ARRIVAL, 0.4) and m.stop is p


# --- 3. the hold constants are gone; each option has its named upper bound --------------------------------------------------------

def test_the_hold_constants_are_gone_and_each_upper_bound_is_named():
    for old in ("BURST_HOLD_S", "PULL_HOLD_S", "STRIKE_HOLD_S", "SWING_HOLD_S"):
        assert not hasattr(brain, old)
    assert not hasattr(jev, "HOLD_S") and not hasattr(Memory(), "hold_until")
    assert {k.__name__: v.max_s for k, v in OPTIONS.items()} == {"Combo": 3.0, "WebStrike": 0.8, "Pull": 0.8, "SwingTo": 1.2}
    assert {k.__name__: v.completes_on for k, v in OPTIONS.items()} == {
        "Combo": (KO_FEED,), "WebStrike": (KO_FEED, ARRIVAL), "Pull": (KO_FEED, ARRIVAL), "SwingTo": ()}
    assert STRIKE_MAX_S == 0.8


# --- 4. the recorded burst ends at its KO, not at 3.0 s ------------------------------------------------------------------------------

# Burst trial 0 (C:\rivals-agent\data\l4\burst, docs/lanes/l4-controller.md): each saved 720p frame's time, the bot's box height (px) or
# None once it is gone, and perception.scoreboard.is_killfeed on that frame, as read for docs/evidence/option-status-20260923/.
TRIAL0 = [(0.455, 70, False), (0.537, 74, False), (0.619, 75, False), (0.696, 260, False), (0.771, 74, False), (0.839, 76, False),
          (0.906, 74, False), (0.980, 75, False), (1.095, 80, False), (1.171, 81, False), (1.240, 81, False), (1.309, 69, False),
          (1.391, 183, False), (1.464, 142, False), (1.544, 61, False), (1.628, 150, False), (1.708, 108, False), (1.787, 238, False),
          (1.861, 114, False), (1.935, 198, False), (2.034, None, None), (2.111, None, True), (2.195, None, True), (2.275, None, True)]


def test_the_recorded_burst_trial_ends_at_its_ko_not_at_its_bound():
    m, frame = Memory(), (1280, 720)
    box = lambda h: Detection(ENEMY, (640 - h / 4, 360 - h / 2, 640 + h / 4, 360 + h / 2), 0.9, track=1)   # noqa: E731
    decide(st(0.38, [box(71)], feed=False, frame=frame), m)
    c = commit(m, Combo(BURST, box(70)), 0.455)                 # the trial's first LT: the pad script, not the brain, started it
    for t, h, feed in TRIAL0[1:]:
        got = decide(st(t, [] if h is None else [box(h)], feed=feed, frame=frame, coasting=() if h else (1,)), m)
        if t < 2.195:
            assert got is c and m.option.status == RUNNING, t
        if t == 2.195:
            assert got is not c and m.stop is c
    assert ended(m) == (COMPLETED, KO_FEED, 2.195)
    assert m.option.bound_t == pytest.approx(0.455 + BURST_MAX_S)   # the hold would have run to 3.455 s


# --- the controller: a stop cuts only the primitive played for that intent -----------------------------------------------------------

def playing_burst(c):
    ctrl = Controller()
    ctrl.play(BURST, 0.0)
    ctrl.played, ctrl.intent_key = c, ("Combo", BURST)
    return ctrl


def test_a_stop_cuts_only_the_primitive_played_for_that_intent():
    c = Combo(BURST, BOT)
    s = State(t=2.0, frame=FRAME, detections=[])
    assert playing_burst(c).step(s, Search())["rt"] == 1.0                     # the burst's melee is being held at 2.0 s
    ctrl = playing_burst(c)
    out = ctrl.step(s, Search(), stop=c)
    assert out["rt"] == 0.0 and out["lt"] == 0.0 and out["buttons"] == () and ctrl.seq == []
    assert ctrl.step(replace(s, t=2.1), Search(), stop=c)["rt"] == 0.0            # said again: nothing to cut, nothing replayed
    assert playing_burst(c).step(s, Search(), stop=Combo(BURST, BOT))["rt"] == 1.0   # an equal intent is not that intent
    other = Controller()
    other.play("web_cluster", 1.99)
    other.played, other.intent_key = c, ("Engage", None)
    assert other.step(s, Search(), stop=c)["lt"] == 1.0                          # Engage's own shot is not the burst


# --- the loop: legacy reads the feed and stops the burst; range-skill mode reads nothing new --------------------------------------------

class MemoryLog:
    def __init__(self):
        self.rows = []

    def write(self, row, frame=None):
        self.rows.append(row)

    def close(self, *args):
        pass


def legacy_run(ko):
    """The scripted brain bursts the bot; at 1.0 s it is gone, and with `ko` the kill feed shows from then."""
    frames = timeline(3.5, dets=lambda t: [BOT] if t < 1.0 else [])
    for f, t in frames:
        f.feed = ko and t >= 1.0
    log, pad = MemoryLog(), FakePad()
    loop = Loop(Frames(frames), pad, replace(readers(abilities=dict(READY)), killfeed=lambda f: f.feed), brain.decide,
                warmup=False, scoreboard=False, log=log)
    loop.run()
    presses = [r["t"] for r in log.rows if "pad" in r and (r["pad"]["lt"] or r["pad"]["rt"] or r["pad"]["buttons"])]
    return log.rows, presses


def test_the_legacy_loop_reads_the_feed_logs_the_status_and_stops_the_burst_at_the_ko():
    rows, presses = legacy_run(ko=True)
    decisions = [r for r in rows if "state" in r]
    assert [r["state"]["kill_feed"] for r in decisions][:3] == [False, False, False]
    done = next(r for r in decisions if r.get("option", {}).get("status") == COMPLETED)
    assert done["option"]["evidence"]["observation"] == KO_FEED and done["option"]["stop"] is True
    assert done["state"]["t"] == pytest.approx(1.1, abs=0.02)            # the second True read
    assert presses and max(presses) < done["t"] + 1e-9                    # nothing pressed after the stop
    _, before = legacy_run(ko=False)
    assert before[:len(presses)] == presses and max(before) > 2.5         # without a KO the burst's melee and last shot play on


def test_range_skill_mode_reads_no_kill_feed_and_passes_no_stop():
    from tests.test_range_skill_loop import EventBrain

    def refuse(frame):
        raise AssertionError("range-skill mode read the kill feed")

    kwargs, pads = [], {}

    class Spy(Controller):
        def step(self, *a, **kw):
            kwargs.append(kw)
            return super().step(*a, **kw)

    for name, feed in (("absent", None), ("reader", refuse)):
        log, pad = MemoryLog(), FakePad()
        Loop(Frames(timeline(.65, dets=[BOT])), pad, replace(readers(), killfeed=feed), EventBrain(), brain_name="range-skill", max_s=1,
             keepalive_s=.01, scoreboard=False, log=log, controller=Spy()).run()
        pads[name] = sends(pad)
        assert all(r["state"]["kill_feed"] is None for r in log.rows if "state" in r)
        assert not any("option" in r for r in log.rows)
    assert kwargs and not any("stop" in kw for kw in kwargs)
    assert pads["absent"] == pads["reader"]


def test_the_range_skill_brain_decides_the_same_whatever_the_kill_feed_reads():
    from tests.test_range_skill_policy import FixedPolicy, state

    def run(feeds):
        consumer, memory, out = LearnedRangeSkillBrain(FixedPolicy()), Memory(), []
        for i, feed in enumerate(feeds):
            s = state(i * .1)
            s.kill_feed = feed
            out.append((consumer(s, memory), consumer.last, memory.option, memory.stop, memory.target, memory.mode))
        return out

    unread = run([None] * 12)
    assert run([False, False, True, True, False, True, True, True, None, False, True, True]) == unread
    assert any(type(x[0]).__name__ == "RangeSkill" for x in unread) and all(x[2] is None and x[3] is None for x in unread)


@pytest.mark.corpus
def test_the_slot4_range_replay_is_identical_to_the_base_commit(tmp_path):
    """Reasons, pads, ids and every other replayed field of Galacta slot 4's recorded range-skill ticks, in both of
    docs/evidence/range-fragment-repair-20260922's modes, and its review scenarios: the base commit's agent/ against this tree's."""
    if not (ROOT / "data/l1/galacta-pilot-20260922-04-learned/frames.jsonl").exists():
        pytest.skip("the slot-4 log is not under data/")
    here = ROOT / "docs/evidence/range-fragment-repair-20260922"
    zipped = subprocess.run(["git", "archive", "--format=zip", BASE, "agent"], cwd=ROOT, check=True, capture_output=True).stdout
    zipfile.ZipFile(io.BytesIO(zipped)).extractall(tmp_path / "base")
    got = {}
    for name, code in (("base", tmp_path / "base"), ("tree", ROOT)):
        for mode in ("legacy", "observe"):
            out = tmp_path / f"{name}-{mode}.json"
            subprocess.run([sys.executable, "-B", str(here / "replay.py"), str(code), mode, str(out)], cwd=ROOT, check=True)
            got[name, mode] = json.loads(out.read_text())["rows"]
        out = tmp_path / f"{name}-scenarios.json"
        subprocess.run([sys.executable, "-B", str(here / "scenarios.py"), str(code), str(out)], cwd=ROOT, check=True)
        got[name, "scenarios"] = json.loads(out.read_text())
    steps = [r for r in got["base", "legacy"] if r["recorded_reason"] is not None]
    assert len(steps) == 1068 and all(r["reason"] == r["recorded_reason"] and r["pad"] == r["recorded_pad"] for r in steps)
    for mode in ("legacy", "observe", "scenarios"):
        assert got["tree", mode] == got["base", mode], mode
