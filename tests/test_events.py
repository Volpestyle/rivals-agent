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

from perception.events import (  # noqa: E402
    BANNER_HOLD, Event, HUD_HOLD, banner_word, extract, extract_one, segment,
)
from perception.hud import MK, Hud, read as read_hud  # noqa: E402

# Local-only: the demo clips are never committed, so anything that reads one
# skips when it is absent rather than failing.
DAY_CLIP = ROOT / "data/demos/samples/daymr-2879354299-21600-60s.mp4"

SLOTS = ("teamup", "swing", "get_over_here", "uppercut")


def hud(hp=250, max_hp=250, webs=5, ready=True, charges=None, ult=True, bar=1.0, **over):
    """A Hud with every slot ready and no cooldown unless a keyword overrides one."""
    abilities = {s: (over.pop(f"{s}_ready", ready), over.pop(f"{s}_charges", charges))
                 for s in SLOTS}
    cooldowns = {s: over.pop(f"{s}_cd", None) for s in SLOTS}
    assert not over, f"unused overrides {over}"
    return Hud(hp=hp, max_hp=max_hp, bar_fill=bar, webs=webs, abilities=abilities,
               ult_ready=ult, ult_charge=1.0 if ult else 0.0, cooldowns=cooldowns)


def reads(*huds, start=0, hz=10.0):
    return [(start + i, round((start + i) / hz, 3), h) for i, h in enumerate(huds)]


def kinds(events):
    return [(e.kind, e.slot) for e in events]


# Most tests here are about what the readers see, not about which ability sits
# where, so they pass the mapping a source with our own slot order would give.
# Without one every slot is legitimately unknown -- see the mapping tests.
IDENTITY = {"teamup": "teamup", "swing": "swing",
            "get_over_here": "get_over_here", "uppercut": "uppercut"}


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
    assert events[0].i_from == 1 and events[0].i_to == 3


def test_unknown_does_not_confirm_a_candidate():
    """Two halves of a debounce separated by a None still confirm: the None is skipped."""
    seq = reads(hud(hp=250), hud(hp=200), hud(hp=None), hud(hp=200))
    assert kinds(extract_one(seq)) == [("hp_lost", None)]


# --- debounce -------------------------------------------------------------

def test_single_frame_flicker_is_ignored_even_though_hp_steps_are_raw():
    """hp confirms on one frame so that consecutive steps stay separate, so the
    guard against a misread is its shape: gone for one frame, then the exact
    same number back. A real hit does not undo itself."""
    seq = reads(hud(hp=250), hud(hp=250), hud(hp=13), hud(hp=250), hud(hp=250))
    assert extract_one(seq) == []


def test_two_frames_confirm_a_slow_channel():
    seq = reads(hud(hp=250), hud(hp=200), hud(hp=200))
    assert kinds(extract_one(seq)) == [("hp_lost", None)]


def test_a_dim_icon_is_a_lockout_not_a_cast():
    """The audit's first finding: the swing icon goes red during a wall climb
    with the charge count unchanged, and that used to read as a use. An icon
    dimming says only that the slot is unusable right now."""
    seq = reads(hud(), hud(swing_ready=False), hud(), hud())
    got = kinds(extract_one(seq, mapping=IDENTITY))
    assert got == [("slot_unavailable", "swing"), ("slot_available", "swing")]
    assert not any(k == "ability_cast" for k, _ in got)


def test_a_cooldown_number_appearing_is_a_cast():
    """What actually proves a cast: the slot's icon is replaced by a countdown."""
    seq = reads(hud(), hud(get_over_here_cd=8), hud(get_over_here_cd=8), hud(get_over_here_cd=7))
    casts = [e for e in extract_one(seq, mapping=IDENTITY) if e.kind == "ability_cast"]
    assert len(casts) == 1 and casts[0].slot == "get_over_here"
    assert casts[0].amount == 8          # the cooldown it started at


def test_a_countdown_ticking_down_is_not_more_casts():
    seq = reads(*[hud(get_over_here_cd=n) for n in (8, 8, 7, 6, 5)])
    assert [e.kind for e in extract_one(seq) if e.kind == "ability_cast"] == []


def test_debounce_is_overridable_per_channel():
    seq = reads(hud(), hud(swing_ready=False), hud(), hud())
    assert extract_one(seq, debounce={"ready": 2}) == []


def test_hp_emits_raw_steps_not_a_net():
    """The audit's fourth finding: 250 -> 195 -> 220 in three frames became a
    single net loss of 30, which is not a thing that happened. Both steps, or
    nothing."""
    seq = reads(hud(hp=250), hud(hp=195), hud(hp=220), hud(hp=220))
    got = [(e.kind, e.amount) for e in extract_one(seq)]
    assert ("hp_lost", 55) in got and ("hp_gained", 25) in got
    assert ("hp_lost", 30) not in got


# --- one event per kind ---------------------------------------------------

def test_every_event_kind():
    cases = {
        ("slot_unavailable", "swing"): (hud(), hud(swing_ready=False), hud(swing_ready=False)),
        ("ability_cast", "swing"): (hud(), hud(swing_cd=6), hud(swing_cd=6)),
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
        got = kinds(extract_one(reads(*huds), mapping=IDENTITY))
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
    assert (e.i_from, e.i_to) == (1, 2), (e.i_from, e.i_to)
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
    """A menu or BRB card is long; a HUD gap has to last to be believed."""
    rs = _tagged([hud()] * 4 + [Hud()] * 8 + [hud()] * 4, [True] * 16)
    segs = segment(rs)
    assert [s.ended_by for s in segs] == ["no_hud", "run_end"]
    assert [s.started_by for s in segs] == ["run_start", "hud_returned"]


def test_a_brief_hud_dropout_does_not_cut_a_segment():
    """Two frames where neither digits nor bar read is the reader struggling."""
    rs = _tagged([hud()] * 4 + [Hud(), Hud()] + [hud()] * 4, [True] * 10)
    assert len(segment(rs)) == 1


def test_death_ends_a_segment_and_respawn_starts_one():
    rs = _tagged([hud(hp=40)] * 3 + [hud(hp=0)] * 3 + [hud(hp=250)] * 3, [True] * 9)
    segs = segment(rs)
    assert segs[0].ended_by == "death" and segs[1].started_by == "respawn"


def test_unknown_hero_does_not_break_a_segment():
    """Not knowing who is playing is not evidence that it is not us."""
    rs = _tagged([hud()] * 8, [True, True, True, None, None, True, True, True])
    assert len(segment(rs)) == 1


def _cut_at(huds, cut_frames):
    """Reads for an edited source: full tuples with the cut flag last."""
    return [(i, round(i / 10, 3), h, True, None, False, i in cut_frames)
            for i, h in enumerate(huds)]


def test_an_editorial_cut_ends_a_segment():
    """An upload is spliced from several matches; no segment may span a splice."""
    rs = _cut_at([hud(hp=250)] * 5 + [hud(hp=180)] * 5, {5})
    segs = segment(rs)
    assert [s.ended_by for s in segs] == ["hard_cut", "run_end"]
    assert [s.started_by for s in segs] == ["run_start", "after_cut"]


def test_no_event_crosses_a_cut():
    """hp 250 before the splice and 180 after it is not 70 damage."""
    rs = _cut_at([hud(hp=250)] * 5 + [hud(hp=180)] * 5, {5})
    events, _ = extract(rs)
    assert [e.kind for e in events if e.kind.startswith("hp_")] == []


def test_a_source_with_no_cuts_segments_exactly_as_before():
    """The flag is absent on every continuous capture; nothing may change."""
    huds = [hud(hp=250)] * 4 + [hud(hp=0)] * 3 + [hud(hp=250)] * 4
    plain = _tagged(huds, [True] * 11)
    assert [(s.started_by, s.ended_by) for s in segment(plain)] == \
           [(s.started_by, s.ended_by) for s in segment(_cut_at(huds, set()))]


def test_a_source_nobody_checked_for_cuts_says_so_rather_than_claiming_none():
    """0 means the detection ran and found nothing; null means it never ran."""
    import json

    from perception.events import dump

    huds = [hud(hp=250)] * 3
    unchecked = _tagged(huds, [True] * 3)                      # no cut flag at all
    checked = _cut_at(huds, set())                             # ran, found none
    assert json.loads(dump([], [], unchecked).splitlines()[0])["cuts"] is None
    assert json.loads(dump([], [], checked).splitlines()[0])["cuts"] == 0


def test_cut_times_land_on_the_first_frame_of_the_new_scene():
    from perception.events import _cut_flags

    rows = [{"i": i, "t": i / 10} for i in range(10)]
    # A cut at 0.35 s: frame 3 (0.3) is still the old scene, frame 4 is the new.
    assert [n for n, f in enumerate(_cut_flags([0.35], rows)) if f] == [4]
    # Two cuts inside one sampling interval still only break once.
    assert sum(_cut_flags([0.31, 0.34], rows)) == 1


def test_observed_cooldowns_are_measured_not_assumed():
    """The patch fingerprint: what the HUD showed, per ability, per source."""
    from perception.events import Event, observed

    def cast(t, amount):
        return Event("ability_cast", int(t * 10), t, int(t * 10) + 1, t + 0.1,
                     slot="uppercut", amount=amount)

    evs = [cast(0.0, 6), cast(1.0, 6), cast(5.0, 6),
           Event("slot_available", 70, 7.0, 71, 7.1, slot="uppercut"),
           Event("charges_spent", 80, 8.0, 81, 8.1, slot="uppercut",
                 before=2, after=1)]
    got = observed(evs)["uppercut"]
    assert got["casts"] == 3
    assert got["countdown_mode"] == 6            # the game printed 6 every time
    assert got["countdown"] == {"6": 3}
    assert got["charges"] == 2
    # One availability, credited to the cast just before it (7.1 - 5.1), not to
    # the whole combo that led up to it.
    assert got["relock_s"] == 2.0 and got["relock_n"] == 1


def test_the_countdown_mode_survives_reads_that_caught_the_timer_late():
    """A cast read a tick late prints 7, not 8; the full value must still win."""
    from perception.events import Event, observed

    def cast(n, amount):
        return Event("ability_cast", n * 100, n * 10.0, n * 100 + 1, n * 10.0 + 0.1,
                     slot="get_over_here", amount=amount)

    evs = [cast(n, a) for n, a in enumerate([8, 8, 8, 8, 8, 7, 7, 6, 5, 2])]
    got = observed(evs)["get_over_here"]
    assert got["countdown_mode"] == 8
    assert got["countdown"]["8"] == 5 and got["countdown"]["2"] == 1


def test_a_cooldown_is_not_measured_across_a_segment_break():
    """The slot may have come back during footage nobody saw."""
    from perception.events import Event, observed

    evs = [Event("ability_cast", 0, 0.0, 1, 0.1, slot="swing", amount=6, segment=0),
           Event("ability_cast", 90, 9.0, 91, 9.1, slot="swing", amount=6, segment=1)]
    assert "recast_s" not in observed(evs)["swing"]


def test_an_unidentified_slot_reports_no_cooldowns():
    from perception.events import Event, observed

    evs = [Event("ability_cast", 0, 0.0, 1, 0.1, slot=None, slot_pos="teamup")]
    assert observed(evs) == {}


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


# --- killcam and the scoreboard overlay, from the DayMR clip --------------

def _clip_frame(path, seconds):
    """One frame of a local clip, or None when the clip is not on this machine."""
    import cv2

    if not path.exists():
        return None
    cap = cv2.VideoCapture(str(path))
    try:
        # By frame index, not milliseconds: seeking this clip by time lands
        # seconds away and the whole point here is a specific moment.
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(seconds * (cap.get(cv2.CAP_PROP_FPS) or 60)))
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def test_killcam_banner_is_read_off_the_clip():
    """+50 s of the DayMR clip is the killcam: PAST LIVES beside the countdown."""
    frame = _clip_frame(DAY_CLIP, 50.0)
    if frame is None:
        return
    assert banner_word(frame) == "killcam"


def test_the_killcam_shows_someone_elses_hud():
    """The danger the reason exists for: a *readable* HUD that is not ours."""
    frame = _clip_frame(DAY_CLIP, 50.2)
    if frame is None:
        return
    hud_there = read_hud(frame, MK)
    assert banner_word(frame) == "killcam"
    assert hud_there.hp == 275, hud_there.hp   # the killer's health, not ours


def test_scoreboard_overlay_leaves_the_hud_unreadable():
    """+43 s: the scoreboard covers the HUD, so hp and bar must be unknown."""
    frame = _clip_frame(DAY_CLIP, 43.0)
    if frame is None:
        return
    hud_there = read_hud(frame, MK)
    assert hud_there.hp is None and hud_there.bar_fill is None, hud_there


def test_killcam_ends_a_segment_with_its_own_reason():
    """It is not a hero swap and not spectating, and it gets its own name."""
    reads = ([(i, i / 10, hud(hp=250), True, None) for i in range(6)]
             + [(i, i / 10, hud(hp=275), True, "killcam") for i in range(6, 6 + BANNER_HOLD + 2)]
             + [(i, i / 10, hud(hp=250), True, None) for i in range(6 + BANNER_HOLD + 2, 20)])
    events, segs = extract(reads)
    assert [s.ended_by for s in segs] == ["killcam", "run_end"], [s.ended_by for s in segs]
    assert segs[1].started_by == "killcam_over"
    assert events == [], "the killer's 275 hp must not become our hp events"


def test_spectating_and_killcam_are_different_reasons():
    def run(word):
        reads = ([(i, i / 10, hud(), True, None) for i in range(6)]
                 + [(i, i / 10, hud(), True, word) for i in range(6, 6 + BANNER_HOLD + 2)]
                 + [(i, i / 10, hud(), True, None) for i in range(6 + BANNER_HOLD + 2, 20)])
        return segment(reads)[0].ended_by

    assert run("killcam") == "killcam"
    assert run("spectating") == "spectating"


def test_no_event_crosses_a_scoreboard_blackout():
    """An overlay long enough to break the segment also breaks the event chain."""
    blind = HUD_HOLD + 2
    reads = ([(i, i / 10, hud(hp=250), True, None) for i in range(6)]
             + [(i, i / 10, Hud(), True, None) for i in range(6, 6 + blind)]
             + [(i, i / 10, hud(hp=180), True, None) for i in range(6 + blind, 6 + blind + 6)])
    events, segs = extract(reads)
    assert len(segs) == 2
    assert not any(e.kind == "hp_lost" for e in events), \
        "250 before the overlay and 180 after is not a readable 70 damage"


def test_an_unmapped_slot_reports_no_ability_rather_than_a_guess():
    """A mapping that omits a position means its icon could not be identified."""
    seq = reads(hud(), hud(swing_cd=6), hud(swing_cd=6))
    named = extract_one(seq, mapping={"swing": "get_over_here"})
    assert [(e.kind, e.slot, e.slot_pos) for e in named] == \
        [("ability_cast", "get_over_here", "swing")]
    blank = extract_one(seq, mapping={})
    assert [(e.kind, e.slot, e.slot_pos) for e in blank] == \
        [("ability_cast", None, "swing")]


def test_no_mapping_at_all_is_unknown_not_the_layout_position():
    """`slot` is an ability, `slot_pos` a position, and without the icon
    mapping the ability is unknown. Copying the position across guesses, and
    guesses wrong on every source whose slot order differs from ours -- which
    is both Day sections and both guide windows."""
    seq = reads(hud(), hud(swing_cd=6), hud(swing_cd=6))
    got = extract_one(seq, mapping=None)
    assert [(e.kind, e.slot, e.slot_pos) for e in got] == \
        [("ability_cast", None, "swing")]


def test_the_ult_needs_no_icon_mapping():
    """There is one ult; knowing which ability it is needs no icon read."""
    seq = reads(hud(ult=True), hud(ult=False), hud(ult=False))
    assert ("ult_spent", "ult") in kinds(extract_one(seq, mapping=None))


def test_a_file_with_no_mapping_says_so_rather_than_showing_an_empty_one():
    """{} means the icons were read and none identified; null means nobody
    looked. A loader must be able to tell those apart."""
    import json

    from perception.events import dump

    seq = reads(hud(), hud(swing_cd=6), hud(swing_cd=6))
    meta = json.loads(dump(extract_one(seq, mapping=None), [], seq).splitlines()[0])
    assert meta["slot_mapping"] is None and meta["slot_mapping_from"] is None
    meta = json.loads(dump(extract_one(seq, mapping={}), [], seq, mapping={}).splitlines()[0])
    assert meta["slot_mapping"] == {} and meta["slot_mapping_from"]
