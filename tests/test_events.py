"""Checks for perception.events on synthetic read sequences.

    uv run --group perception --group dev pytest tests/test_events.py

Synthetic on purpose: every rule here is about how a *sequence* of reads becomes
events, and a handmade sequence can say "this frame was unknown, that one
flickered" precisely, which no recording can.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.events import Event, extract, extract_one, segment  # noqa: E402
from perception.hud import Hud  # noqa: E402

SLOTS = ("teamup", "swing", "pull", "uppercut")


def hud(hp=250, max_hp=250, webs=5, ready=True, charges=None, ult=True, bar=1.0, **over):
    """A Hud with every slot ready unless a keyword overrides one."""
    abilities = {s: (over.pop(f"{s}_ready", ready), over.pop(f"{s}_charges", charges))
                 for s in SLOTS}
    assert not over, f"unused overrides {over}"
    return Hud(hp=hp, max_hp=max_hp, bar_fill=bar, webs=webs,
               abilities=abilities, ult_ready=ult, ult_charge=1.0 if ult else 0.0)


def reads(*huds, start=0, hz=10.0):
    return [(start + i, round((start + i) / hz, 3), h) for i, h in enumerate(huds)]


def kinds(events):
    return [(e.kind, e.slot) for e in events]


# --- the None rule --------------------------------------------------------

def test_unknown_emits_nothing_and_breaks_nothing():
    """A None read is not a value: no event, and the run before it continues."""
    seq = reads(hud(hp=250), hud(hp=None), hud(hp=None), hud(hp=250))
    assert extract_one(seq) == []


def test_unknown_between_two_values_does_not_hide_the_change():
    seq = reads(hud(hp=250), hud(hp=250), hud(hp=None), hud(hp=200), hud(hp=200))
    events = extract_one(seq)
    assert kinds(events) == [("hp_lost", None)]
    assert events[0].amount == 50
    # the interval brackets the unknown frame rather than claiming an instant
    assert events[0].i_from == 1 and events[0].i_to == 4


def test_unknown_does_not_confirm_a_candidate():
    """Two halves of a debounce separated by a None still confirm: the None is skipped."""
    seq = reads(hud(hp=250), hud(hp=200), hud(hp=None), hud(hp=200))
    assert kinds(extract_one(seq)) == [("hp_lost", None)]


# --- debounce -------------------------------------------------------------

def test_single_frame_flicker_on_a_slow_channel_is_ignored():
    seq = reads(hud(hp=250), hud(hp=250), hud(hp=13), hud(hp=250), hud(hp=250))
    assert extract_one(seq) == []


def test_two_frames_confirm_a_slow_channel():
    seq = reads(hud(hp=250), hud(hp=200), hud(hp=200))
    assert kinds(extract_one(seq)) == [("hp_lost", None)]


def test_ready_confirms_on_one_frame_because_a_real_use_lasts_one():
    """The Web-Swing icon is red for a single frame at 10 fps when it is used."""
    seq = reads(hud(), hud(swing_ready=False), hud(), hud())
    assert kinds(extract_one(seq)) == [("ability_used", "swing"), ("ability_ready", "swing")]


def test_debounce_is_overridable_per_channel():
    seq = reads(hud(), hud(swing_ready=False), hud(), hud())
    assert extract_one(seq, debounce={"ready": 2}) == []


# --- one event per kind ---------------------------------------------------

def test_every_event_kind():
    cases = {
        ("ability_used", "swing"): (hud(), hud(swing_ready=False), hud(swing_ready=False)),
        ("charges_spent", "swing"): (hud(swing_charges=3), hud(swing_charges=2), hud(swing_charges=2)),
        ("charges_regained", "swing"): (hud(swing_charges=2), hud(swing_charges=3), hud(swing_charges=3)),
        ("web_cluster_fired", None): (hud(webs=5), hud(webs=4), hud(webs=4)),
        ("web_cluster_reloaded", None): (hud(webs=2), hud(webs=5), hud(webs=5)),
        ("hp_lost", None): (hud(hp=250), hud(hp=200), hud(hp=200)),
        ("hp_gained", None): (hud(hp=200), hud(hp=250), hud(hp=250)),
        ("ult_spent", "ult"): (hud(ult=True), hud(ult=False), hud(ult=False)),
        ("ult_ready", "ult"): (hud(ult=False), hud(ult=True), hud(ult=True)),
    }
    for want, huds in cases.items():
        got = kinds(extract_one(reads(*huds)))
        assert want in got, f"{want} not in {got}"


def test_death_and_respawn():
    seq = reads(hud(hp=40), hud(hp=0), hud(hp=0))
    assert ("death", None) in kinds(extract_one(seq))
    seq = reads(hud(hp=0), hud(hp=250), hud(hp=250))
    assert ("respawn", None) in kinds(extract_one(seq))


def test_shield_decay_is_not_damage():
    """hp and max hp falling together is the team-up shield, not a hit."""
    seq = reads(hud(hp=300, max_hp=300), hud(hp=298, max_hp=298), hud(hp=298, max_hp=298))
    got = kinds(extract_one(seq))
    assert ("shield_decayed", None) in got
    assert ("hp_lost", None) not in got and ("max_hp_changed", None) not in got


def test_real_damage_under_a_shield_is_still_damage():
    """hp drops while max hp holds: that is a hit, and must survive the merge."""
    seq = reads(hud(hp=300, max_hp=300), hud(hp=260, max_hp=300), hud(hp=260, max_hp=300))
    assert ("hp_lost", None) in kinds(extract_one(seq))


# --- events are intervals -------------------------------------------------

def test_events_carry_an_interval_not_an_instant():
    seq = reads(hud(hp=250), hud(hp=250), hud(hp=200), hud(hp=200))
    e = extract_one(seq)[0]
    assert (e.i_from, e.i_to) == (1, 3), (e.i_from, e.i_to)
    assert e.t_from < e.t_to
    assert not hasattr(e, "t"), "no field may claim a single press time"
    assert set(Event.__dataclass_fields__) >= {"i_from", "t_from", "i_to", "t_to"}


# --- segmentation ---------------------------------------------------------

def _tagged(huds, playing):
    return [(i, round(i / 10, 3), h, p) for i, (h, p) in enumerate(zip(huds, playing))]


def test_spectating_ends_a_segment_and_no_event_crosses_it():
    """The spectated hero's health must not become our hp events."""
    ours = [hud(hp=250)] * 4
    theirs = [hud(hp=665)] * 4          # longer than PORTRAIT_HOLD, so it is believed
    back = [hud(hp=250)] * 4
    rs = _tagged(ours + theirs + back, [True] * 4 + [False] * 4 + [True] * 4)
    events, segs = extract(rs)
    assert [s.ended_by for s in segs] == ["not_our_hero", "run_end"]
    assert [s.started_by for s in segs] == ["run_start", "hero_returned"]
    assert events == [], "the 250 -> 665 -> 250 jump must not become hp events"


def test_missing_hud_ends_a_segment():
    rs = _tagged([hud(), Hud(), Hud(), hud()], [True, None, None, True])
    segs = segment(rs)
    assert [s.ended_by for s in segs] == ["no_hud", "run_end"]
    assert [s.started_by for s in segs] == ["run_start", "hud_returned"]


def test_death_ends_a_segment_and_respawn_starts_one():
    rs = _tagged([hud(hp=40), hud(hp=0), hud(hp=250)], [True, True, True])
    segs = segment(rs)
    assert segs[0].ended_by == "death" and segs[1].started_by == "respawn"


def test_unknown_hero_does_not_break_a_segment():
    """Not knowing who is playing is not evidence that it is not us."""
    rs = _tagged([hud(), hud(), hud()], [True, None, True])
    assert len(segment(rs)) == 1


def test_events_are_labelled_with_their_segment():
    rs = _tagged([hud(hp=250)] * 3 + [hud(hp=665)] * 3 + [hud(hp=250), hud(hp=200), hud(hp=200)],
                 [True] * 3 + [False] * 3 + [True] * 3)
    events, segs = extract(rs)
    assert len(segs) == 2
    assert all(e.segment == 1 for e in events), [(e.kind, e.segment) for e in events]


def test_a_brief_portrait_wobble_does_not_cut_a_segment():
    """One or two marginal frames are noise, not a hero swap."""
    rs = _tagged([hud()] * 6, [True, True, False, False, True, True])
    assert len(segment(rs)) == 1
