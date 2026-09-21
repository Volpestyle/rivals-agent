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
from dataclasses import replace  # noqa: E402
import pytest  # noqa: E402

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

# Known mechanics are an input the caller supplies; tests that mean the current
# patch say so.
from perception.events import KITS as _KITS, KIT_REFERENCE as _KIT_REF  # noqa: E402

KIT = _KITS[_KIT_REF]


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
    assert got == [("icon_dimmed", "swing"), ("icon_lit", "swing")]
    assert not any(k == "ability_cast" for k, _ in got)


def test_a_cooldown_number_appearing_is_a_cast():
    """What actually proves a cast: the slot's icon is replaced by a countdown
    whose start -- expiry less the full length -- lies inside the segment. A
    read of 8 says 7 to 8 s remain, so the segment must be open a second first."""
    seq = reads(*[hud()] * 12, hud(get_over_here_cd=8), hud(get_over_here_cd=8), hud(get_over_here_cd=7))
    casts = [e for e in extract_one(seq, mapping=IDENTITY, timers={"get_over_here": 8})
             if e.kind == "ability_cast"]
    assert len(casts) == 1 and casts[0].slot == "get_over_here"
    assert casts[0].amount == 8          # the cooldown it started at


def test_a_countdown_ticking_down_is_not_more_casts():
    """One cast, placed inside the segment, however many values it ticks through."""
    seq = reads(*[hud()] * 12, *[hud(get_over_here_cd=n) for n in (8, 8, 7, 7, 6, 6, 5, 5)])
    got = extract_one(seq, mapping=IDENTITY, timers={"get_over_here": 8})
    assert [e.kind for e in got if e.kind.startswith("ability_")] == ["ability_cast"]


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

def _refilling(charge=0.4):
    """The ult meter part-charged: what proves a spend, and a return."""
    return replace(hud(ult=False), ult_charge=charge)


def test_every_event_kind():
    cases = {
        ("icon_dimmed", "swing"): (hud(), hud(swing_ready=False), hud(swing_ready=False)),
        ("ability_cast", "swing"): (*[hud()] * 12, hud(swing_cd=6), hud(swing_cd=6)),
        ("charges_spent", "swing"): (hud(swing_charges=3), hud(swing_charges=2), hud(swing_charges=2)),
        ("charges_regained", "swing"): (hud(swing_charges=2), hud(swing_charges=3), hud(swing_charges=3)),
        ("web_cluster_fired", None): (hud(webs=5), hud(webs=4), hud(webs=4)),
        ("web_cluster_reloaded", None): (hud(webs=2), hud(webs=5), hud(webs=5)),
        ("hp_lost", None): (hud(hp=250), hud(hp=200), hud(hp=200)),
        ("hp_gained", None): (hud(hp=200), hud(hp=250), hud(hp=250)),
        ("ult_spent", "ult"): (hud(ult=True), hud(ult=False), _refilling()),
        ("ult_ready", "ult"): (_refilling(), hud(ult=True), hud(ult=True)),
    }
    for want, huds in cases.items():
        got = kinds(extract_one(reads(*huds), mapping=IDENTITY, timers={"swing": 6}))
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
           Event("cooldown_ended", 70, 7.0, 71, 7.1, slot="uppercut"),
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
    assert [(e.slot, e.slot_pos) for e in named] == [("get_over_here", "swing")]
    blank = extract_one(seq, mapping={})
    assert [(e.slot, e.slot_pos) for e in blank] == [(None, "swing")]


def test_no_mapping_at_all_is_unknown_not_the_layout_position():
    """`slot` is an ability, `slot_pos` a position, and without the icon
    mapping the ability is unknown. Copying the position across guesses, and
    guesses wrong on every source whose slot order differs from ours -- which
    is both Day sections and both guide windows."""
    seq = reads(hud(), hud(swing_cd=6), hud(swing_cd=6))
    got = extract_one(seq, mapping=None)
    assert [(e.slot, e.slot_pos) for e in got] == [(None, "swing")]


def test_the_ult_needs_no_icon_mapping():
    """There is one ult; knowing which ability it is needs no icon read."""
    seq = reads(hud(ult=True), hud(ult=False), _refilling())
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


# --- the writer: recipes, staleness, regeneration --------------------------

def test_pts_times_are_read_off_showinfo():
    from perception.events import _pts_times

    log = ("[Parsed_showinfo_1 @ 0x1] n:   0 pts:  61440 pts_time:1200.02 duration:1\n"
           "[Parsed_showinfo_1 @ 0x1] n:   1 pts:  61442 pts_time:1200.0533 duration:1\n")
    assert _pts_times(log) == [1200.02, 1200.0533]


def _write(path, meta):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "meta", **meta}) + "\n")


def test_check_lists_old_formats_and_files_nobody_can_rebuild(tmp_path):
    from perception.events import FORMAT_VERSION, check

    recipe = {"video": "v.mp4", "hz": 10.0, "start": None, "duration": None, "layout": "mk"}
    from perception.events import writer_version

    full = {"recipe": recipe, "cut_times": [], "observed": {}, "slot_mapping": {},
            "writer": writer_version(), "container_start_s": 0.0, "stream_start_s": 0.0,
            "timer_lengths": {}, "kit": None}
    _write(tmp_path / "good.jsonl", {"format": FORMAT_VERSION, **full})
    _write(tmp_path / "sub" / "old.jsonl", {"format": FORMAT_VERSION - 1, **full})
    _write(tmp_path / "orphan.jsonl", {"format": FORMAT_VERSION, **full, "recipe": None})
    # Same format number, written before cut_times existed: found by the key it lacks.
    _write(tmp_path / "older.jsonl", {"format": FORMAT_VERSION, **{k: v for k, v in full.items()
                                                                   if k != "cut_times"}})
    stale = {p.name: why for p, why in check(tmp_path)}
    _write(tmp_path / "other.jsonl", {"format": FORMAT_VERSION, **full, "writer": "000000000000"})
    assert set(stale) | {"other.jsonl"} == {p.name for p, _ in check(tmp_path)}
    assert set(stale) == {"old.jsonl", "orphan.jsonl", "older.jsonl"}
    assert "format" in stale["old.jsonl"] and "recipe" in stale["orphan.jsonl"]
    assert "cut_times" in stale["older.jsonl"]


def test_regenerate_reports_a_file_it_cannot_rebuild_rather_than_skipping_it(tmp_path):
    from perception.events import regenerate

    _write(tmp_path / "orphan.jsonl", {"format": 1, "recipe": None})
    assert regenerate(tmp_path)["no_recipe"] == [str(tmp_path / "orphan.jsonl")]


def test_from_video_samples_an_exact_window_and_records_how(tmp_path):
    """End to end on a synthetic 60 fps video: the window, the grid, the origin
    in source seconds, times from zero, and a recipe that says all of it."""
    import json
    import shutil
    import subprocess

    import pytest

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    from perception.events import FORMAT_VERSION, check, from_video

    video = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=60",
                    "-t", "3", "-pix_fmt", "yuv420p", str(video), "-y"], check=True)
    out = tmp_path / "events" / "src.jsonl"
    got = from_video(video, out, hz=10, start=1.0, duration=1.0, layout="mk",
                     workdir=tmp_path / "work")
    meta = json.loads(out.read_text().splitlines()[0])
    assert got["frames"] == 10                       # 1 s at 10 Hz, exactly
    assert abs(meta["pts_origin_s"] - 1.0) < 0.02    # source time of the first frame
    assert meta["recipe"] == {"video": str(video), "hz": 10, "start": 1.0,
                              "duration": 1.0, "layout": "mk"}
    assert meta["format"] == FORMAT_VERSION and meta["cuts"] is not None
    assert check(tmp_path / "events") == []
    assert not any((tmp_path / "work").iterdir())    # no frames left behind


def test_the_demonstration_directory_holds_one_format_throughout():
    """The loader refuses anything but the current format; this names the files
    that would be refused. Local data only -- skips where it is absent."""
    import pytest

    from perception.events import EVENTS_DIR, check

    root = ROOT / EVENTS_DIR
    if not root.exists():
        pytest.skip("no local demonstration events")
    stale = check(root)
    assert not stale, "run `python -m perception.events regenerate`:\n" + \
        "\n".join(f"  {p}: {why}" for p, why in stale)


# --- another hero passing as ours --------------------------------------------

STRANGE_VOD = ROOT / "data/demos/vods/daymr-2879354299-21660-900s.mp4"


def _vod_frame(path, seconds):
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def test_doctor_strange_is_not_spider_man():
    """The box annotator's find: a minute of DayMR on Doctor Strange (650 hp)
    read as own-Spider-Man, because Strange scores inside Spider-Man's band on
    the one-class portrait match. Local VOD only; skips without it."""
    import pytest

    from perception.events import playing_spiderman

    if not STRANGE_VOD.exists():
        pytest.skip("retained section not on this machine")
    # Source time, all Strange. One of them reads unknown (his portrait mid-animation),
    # which the segmenter carries across; what must never happen is True.
    verdicts = [playing_spiderman(_vod_frame(STRANGE_VOD, s)) for s in (822, 835, 850, 865, 878)]
    assert True not in verdicts, verdicts
    assert verdicts.count(False) >= 4, verdicts
    for seconds in (800.0, 802.0):                         # Spider-Man, just before
        assert playing_spiderman(_vod_frame(STRANGE_VOD, seconds)) is not False, seconds


def test_the_strange_stretch_is_no_longer_a_play_segment():
    """End to end on the retained section: no segment may cover 822-878 s."""
    import json

    import pytest

    path = ROOT / "data/demos/events/sections/daymr-2879354299-21660-900s.jsonl"
    if not path.exists():
        pytest.skip("retained section events not on this machine")
    lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    origin = lines[0]["pts_origin_s"] or 0.0
    covering = [s for s in lines if s.get("type") == "segment"
                and s["start_t"] + origin < 870 and s["end_t"] + origin > 830]
    assert not covering, covering


# --- format 5: cuts inside gaps, cut times, per-segment regime ---------------

def _reads7(huds, aside=None, cuts=()):
    aside = aside or {}
    return [(i, round(i / 10, 3), h, True, aside.get(i), False, i in cuts)
            for i, h in enumerate(huds)]


def test_a_cut_inside_a_scoreboard_gap_is_not_a_bridgeable_tap():
    """The loader bridges short scoreboard gaps. A cut hidden in one would fuse
    two unrelated shots, so the cut outranks the scoreboard on both sides."""
    huds = [hud(hp=250)] * 5 + [hud(hp=None)] * 4 + [hud(hp=180)] * 5
    board = {i: "scoreboard" for i in range(5, 9)}
    plain = segment(_reads7(huds, board))
    assert [(s.started_by, s.ended_by) for s in plain] == \
        [("run_start", "scoreboard"), ("scoreboard_closed", "run_end")]
    cut = segment(_reads7(huds, board, cuts={7}))       # mid-gap
    assert [(s.started_by, s.ended_by) for s in cut] == \
        [("run_start", "hard_cut"), ("after_cut", "run_end")]


def test_every_cut_time_is_in_the_meta_line():
    import json

    from perception.events import dump

    huds = [hud(hp=250)] * 12
    meta = json.loads(dump([], [], _reads7(huds, cuts={3, 9})).splitlines()[0])
    assert meta["cut_times"] == [0.3, 0.9] and meta["cuts"] == 2
    unchecked = json.loads(dump([], [], _tagged(huds, [True] * 12)).splitlines()[0])
    assert unchecked["cut_times"] is None and unchecked["cuts"] is None


def test_a_segment_is_normal_only_where_a_countdown_proved_it():
    """The HUD can prove cooldowns are on; it cannot prove they are off."""
    rs = _reads7([hud()] * 12 + [hud(get_over_here_cd=8)] * 10 + [hud(get_over_here_cd=7)] * 10 +
                 [hud(hp=0)] * 3 + [hud()] * 4)
    _, segs = extract(rs, mapping=IDENTITY, kit=KIT)
    assert [s.cooldowns for s in segs] == ["normal", "unknown"]



def test_the_three_clocks_are_recorded_apart(tmp_path):
    """A container that starts before its video stream (audio first, as on the
    DayMR section): the meta line must say both, and t + pts_origin_s -
    container_start_s must land on the seek time of the frame."""
    import json
    import shutil
    import subprocess

    import pytest

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    from perception.events import from_video

    video = tmp_path / "late-video.mp4"
    # 2 s of audio from 0, video starting 0.5 s later.
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=60",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
                    "-filter_complex", "[0:v]setpts=PTS+0.5/TB[v]", "-map", "[v]", "-map", "1:a",
                    "-pix_fmt", "yuv420p", "-shortest", str(video), "-y"], check=True)
    out = tmp_path / "e.jsonl"
    from_video(video, out, hz=10, layout="mk", workdir=tmp_path / "w")
    meta = json.loads(out.read_text().splitlines()[0])
    assert meta["stream_start_s"] > meta["container_start_s"], meta
    assert abs(meta["pts_origin_s"] - meta["stream_start_s"]) < 0.02, meta
    seek_of_first = meta["pts_origin_s"] - meta["container_start_s"]
    assert abs(seek_of_first - (meta["stream_start_s"] - meta["container_start_s"])) < 0.02


# --- countdown timers: a continuing cooldown is not a new cast ---------------
# Regressions from the gap-resumption measurement (docs/lanes/l2-hud.md). The
# fixture holds one slot's frozen per-frame reads around each ability_cast that
# was checked by eye: 17 duplicates, 6 real casts, 1 that cannot be told.

import json as _json

GAP_FIXTURE = ROOT / "tests/fixtures/gap_casts.json"


def _gap_cases(expect):
    return [c for c in _json.loads(GAP_FIXTURE.read_text())["cases"] if c["expect"] == expect]


def _run_case(case):
    """extract_one over the case's reads, the slot mapped to itself."""
    slot = case["slot"]
    rs = [(i, t, Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={slot: (ready, charges)},
                     cooldowns={slot: cd}))
          for i, t, cd, ready, charges in case["frames"]]
    # Durations are inputs: the reference kit for the charged slots (a recorded
    # `full` there is the old calibration's), the case's own for the rest --
    # team-up 15 is Symbiote Bond, the icon both train sources show.
    from perception.events import KITS, KIT_REFERENCE, durations

    if slot in ("swing", "uppercut"):
        full, lock = durations(KITS[KIT_REFERENCE], {slot: slot})[slot]
    else:
        full, lock = case["full"], None
    from perception.events import charge_maxima

    return extract_one(rs, mapping={slot: slot}, timers={slot: full} if full else None,
                       locks={slot: lock} if lock else None,
                       maxes=charge_maxima(KITS[KIT_REFERENCE], {slot: slot}))


def _near_event(events, kind, case, tol=0.35):
    return [e for e in events if e.kind == kind and abs(e.t_to - case["t_event"]) <= tol]


@pytest.mark.parametrize("case", _gap_cases("duplicate"), ids=lambda c: f"{c['source'][:5]}-{c['slot']}-{c['t_event']}")
def test_a_countdown_read_again_after_a_gap_is_not_a_new_cast(case):
    """Every one of these was a continuing countdown the old channel counted twice."""
    assert not _near_event(_run_case(case), "ability_cast", case)


@pytest.mark.parametrize("case", _gap_cases("cast"), ids=lambda c: f"{c['source'][:5]}-{c['slot']}-{c['t_event']}")
def test_a_real_cast_is_still_a_cast(case):
    """The controls and the charged second uses, verified on the frames: still
    casts, with finite bounds the evidence justifies, known soon after. An
    empty, unknown-only or deferred output fails here."""
    import math

    (cast,) = _near_event(_run_case(case), "ability_cast", case, tol=1.2)
    assert all(math.isfinite(x) for x in (cast.t_from, cast.t_to, cast.known_at)), cast
    assert cast.t_from <= cast.t_to <= cast.known_at, cast
    assert cast.t_to - cast.t_from <= 2.5, cast        # measured: 1.1-2.3 s
    assert cast.known_at - cast.t_to <= 1.5, cast      # measured: 0.1-1.1 s


def test_a_case_that_cannot_be_told_stays_unknown():
    """Req uppercut 52.0: its "previous countdown 7" is chat; with two charges a
    continuing timer cannot rule out a real second use. Neither cast nor silence."""
    (case,) = _gap_cases("uncertain")
    events = _run_case(case)
    assert not _near_event(events, "ability_cast", case)
    assert _near_event(events, "ability_uncertain", case, tol=1.2)


def _slot_reads(values, slot="swing", charges=None, ready=None, t0=0.0):
    charges = charges or [None] * len(values)
    ready = ready or [None] * len(values)
    return [(k, round(t0 + k / 10, 3),
             Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={slot: (r, c)}, cooldowns={slot: v}))
            for k, (v, c, r) in enumerate(zip(values, charges, ready))]


def test_a_second_use_during_a_recharge_is_still_a_charge_spent():
    """A charged slot's timer keeps running through a second use; the use is
    proved by the charge count, and the timer must not erase it."""
    vals = [5] * 10 + [4] * 10 + [None] * 3 + [3] * 7 + [2] * 10
    chg = [1] * 20 + [None] * 3 + [0] * 17
    events = extract_one(_slot_reads(vals, charges=chg), mapping={"swing": "swing"})
    assert [e.kind for e in events if e.kind == "charges_spent"] == ["charges_spent"]
    assert not [e for e in events if e.kind == "ability_cast"]


def test_a_recharge_completing_is_not_a_cast_and_the_next_use_is():
    """Day swing 48-52 s, as the frames show it: a use empties the slot and a
    countdown appears; the recharge completes -- the number goes, the badge
    comes back -- which is not a cast; a second use empties it again and the
    next recharge's countdown appears part-way through, which is. Each is known
    on its confirming read; the badge read before each places it."""
    vals = [None] * 5 + [2] * 10 + [1] * 8 + [None] * 12 + [5] * 10
    chg = [1] * 5 + [0] * 18 + [1] * 12 + [0] * 10
    events = extract_one(_slot_reads(vals, charges=chg, ready=[True] * 45), mapping={"swing": "swing"})
    casts = [e for e in events if e.kind == "ability_cast"]
    assert [e.t_to for e in casts] == [0.5, 3.5], casts          # no later than the first read
    assert [e.known_at for e in casts] == [0.6, 3.6], casts      # known on the confirming one
    assert [e.kind for e in events if e.kind == "charges_regained"] == ["charges_regained"]


def test_a_missing_read_never_ends_a_cooldown():
    """Unread frames mid-countdown are the reader, not the cooldown ending."""
    vals = [8] * 10 + [7] * 5 + [None] * 6 + [6] * 10 + [5] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 41),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    assert [e for e in events if e.kind == "ability_cast"] == []


def test_a_restart_at_full_value_after_the_cooldown_is_a_cast():
    """The kit's evidence for a new one-charge cast: the countdown runs out and
    starts again at its full value."""
    vals = [2] * 10 + [1] * 10 + [None] * 10 + [8] * 10 + [7] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 50),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    casts = [e for e in events if e.kind == "ability_cast"]
    assert len(casts) == 1 and casts[0].amount == 8
    assert abs(casts[0].known_at - 3.1) < 0.05, "known on the confirming read, not the first"
    assert casts[0].t_to <= 3.0
    assert 1.9 <= casts[0].t_from <= 2.1, "after the last timer's end; two reads of 8 bound it from below"


def test_a_timer_the_kit_cannot_produce_is_uncertain_not_a_cast():
    """A one-charge countdown cannot restart before the running one ends."""
    vals = [8] * 10 + [7] * 10 + [8] * 10 + [7] * 10     # jumps back up with 6 s still to run
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 40),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    kinds = [e.kind for e in events if e.kind.startswith("ability_")]
    assert "ability_uncertain" in kinds and kinds.count("ability_cast") == 0


def test_full_lengths_are_measured_from_ticking_timers():
    """Get Over Here's 8 matches the kit; a number that sits still never counts."""
    from perception.events import timer_lengths

    ticking = _slot_reads([8] * 10 + [7] * 10 + [6] * 10, slot="get_over_here")
    still = _slot_reads([12] * 60, slot="get_over_here", t0=100.0)
    assert timer_lengths(ticking + still) == {"get_over_here": 8}


# --- segmentation fixes ------------------------------------------------------

def _aside_reads(asides, playing=None, huds=None):
    playing = playing or [True] * len(asides)
    huds = huds or [hud(hp=250)] * len(asides)
    return [(i, round(i / 10, 3), h, p, a, False, False)
            for i, (a, p, h) in enumerate(zip(asides, playing, huds))]


def test_a_two_frame_scoreboard_tap_ends_the_segment():
    """Req 657.7: the board fully up for two frames of a three-frame tap."""
    segs = segment(_aside_reads([None] * 8 + ["scoreboard"] * 2 + [None] * 8))
    assert [(s.started_by, s.ended_by) for s in segs] == \
        [("run_start", "scoreboard"), ("scoreboard_closed", "run_end")]


def test_one_false_killcam_frame_still_does_not_cut():
    """Day 330.0: one frame reads "killcam" over ordinary play. It must not cut."""
    assert len(segment(_aside_reads([None] * 8 + ["killcam"] + [None] * 8))) == 1


def test_a_respawn_black_cuts_at_once():
    """Day 85.2: one to two frames of black between a teammate's HUD and ours --
    far shorter than the HUD vote, so it used to be absorbed."""
    blank = Hud()
    segs = segment(_aside_reads([None] * 8 + ["black"] * 2 + [None] * 8,
                                huds=[hud(hp=325)] * 8 + [blank] * 2 + [hud(hp=250)] * 8))
    assert [s.ended_by for s in segs][0] == "no_hud" and len(segs) == 2


def test_is_black_on_a_black_game_area_only():
    import numpy as np

    from perception.events import is_black

    frame = np.full((1080, 1920, 3), 60, np.uint8)
    assert not is_black(frame)
    frame[216:810, 384:1536] = 2          # the game area black, overlays around it intact
    assert is_black(frame)


# --- hp cause: a change in hp alone is not damage or healing ------------------

def _hp_window(name):
    fx = _json.loads((ROOT / "tests/fixtures/hp_cause.json").read_text())
    return [(i, t, Hud(hp=hp, max_hp=mx, bar_fill=bar, bar_damage=dmg))
            for i, t, hp, mx, bar, dmg in fx["windows"][name]]


def test_a_decaying_shield_with_max_hp_unread_is_not_damage():
    """Day 62-71 s: hp 400 -> 304 in 6 and 12 hp ticks, a bonus pool decaying,
    max hp unreadable nearly throughout. The old stream called it ten hits."""
    events = extract_one(_hp_window("decay"))
    lost = [e for e in events if e.kind == "hp_lost"]
    assert lost and all(e.cause == "unknown" for e in lost), [(e.t_to, e.cause) for e in lost]


def test_an_ultimate_bonus_with_max_hp_unread_is_not_healing():
    """Day 342.2 s: hp 124 -> 379, the ultimate's +250 bonus health."""
    events = extract_one(_hp_window("ultimate"))
    big = [e for e in events if e.kind == "hp_gained" and e.amount and e.amount >= 200]
    assert big and all(e.cause == "unknown" for e in big)
    assert not [e for e in events if e.kind == "hp_gained" and e.cause == "heal" and e.amount >= 200]


def test_damage_is_damage_only_with_max_hp_read_unchanged():
    seq = reads(hud(hp=250, max_hp=250), hud(hp=200, max_hp=250), hud(hp=200, max_hp=250))
    (e,) = [e for e in extract_one(seq) if e.kind == "hp_lost"]
    assert e.cause == "damage"
    seq = reads(hud(hp=250, max_hp=None), hud(hp=200, max_hp=None), hud(hp=200, max_hp=None))
    (e,) = [e for e in extract_one(seq) if e.kind == "hp_lost"]
    assert e.cause == "unknown"


def test_max_hp_changed_is_still_the_evidence_channel():
    seq = reads(hud(hp=250, max_hp=250), hud(hp=250, max_hp=300), hud(hp=250, max_hp=300))
    assert ("max_hp_changed", None) in kinds(extract_one(seq))


# --- icons are display state -------------------------------------------------

def test_prohibition_marks_are_display_events_that_certify_nothing():
    """Day 13-27 s: the swing icon dims (13.9-18.8 s), then red prohibition marks. They are
    reported as what the icon showed, never as a cast or as availability."""
    fx = _json.loads((ROOT / "tests/fixtures/icon_display.json").read_text())
    rs = [(i, t, Hud(hp=250, max_hp=250, bar_fill=1.0,
                     abilities={s: (v[0], v[1]) for s, v in slots.items()},
                     cooldowns={s: v[2] for s, v in slots.items()}))
          for i, t, slots in fx["frames"]]
    events = extract_one(rs, mapping=IDENTITY)
    icon = [e for e in events if e.kind in ("icon_dimmed", "icon_lit")]
    assert icon, "the fixture should show the marks"
    assert not [e for e in events if e.kind in ("slot_available", "slot_unavailable")]
    countdowns = {s for _, _, slots in fx["frames"] for s, v in slots.items() if v[2] is not None}
    certified = [e for e in events if e.kind in ("ability_cast", "cooldown_ended")]
    assert all(e.slot in countdowns for e in certified)      # only where a countdown was read


def test_a_cooldown_watched_running_out_is_recorded():
    vals = [3] * 10 + [2] * 10 + [1] * 10 + [None] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 40),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    (end,) = [e for e in events if e.kind == "cooldown_ended"]
    assert 2.9 <= end.t_to <= 3.3


def test_an_icon_lighting_up_is_not_a_return():
    seq = reads(hud(get_over_here_ready=False), hud(), hud(), hud())
    events = extract_one(seq, mapping=IDENTITY)
    assert ("icon_lit", "get_over_here") in kinds(events)
    assert not [e for e in events if e.kind == "cooldown_ended"]


# --- portrait negatives: the spectated teammates ----------------------------

def _portrait_frame(name):
    import cv2
    import numpy as np

    from perception.events import PORTRAIT

    crop = cv2.imread(str(ROOT / f"tests/fixtures/portrait-{name}.png"))
    frame = np.zeros((1080, 1920, 3), np.uint8)
    x0, y0 = int(PORTRAIT[0] * 1920), int(PORTRAIT[1] * 1080)
    frame[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    return frame


def test_a_spectated_teammate_is_not_spider_man():
    """Day 81 and 84.5 s: DayMR spectating two teammates. Both passed the
    one-class portrait match and were kept as own play in several stretches."""
    from perception.events import playing_spiderman

    assert playing_spiderman(_portrait_frame("teammate-bearded")) is False
    assert playing_spiderman(_portrait_frame("teammate-white-haired")) is False
    assert playing_spiderman(_portrait_frame("spiderman")) is True


# --- native frames that cannot be crops (local data only) -------------------

import os as _os

NATIVE = Path(_os.environ.get("RIVALS_DATA", ROOT / "data")) / "experiments/b0/frames"


def _native(src, t):
    import cv2

    path = NATIVE / src / f"{round(t * 10) + 1:06d}.jpg"
    if not path.exists():
        pytest.skip("native frames not on this machine")
    return cv2.imread(str(path))


def test_native_respawn_black_is_black_and_play_is_not():
    from perception.events import is_black

    assert is_black(_native("daymr-2879354299-21660-900s", 85.2))
    assert not is_black(_native("daymr-2879354299-21660-900s", 85.5))
    assert not is_black(_native("daymr-2879354299-21660-900s", 330.0))


def test_native_scoreboard_tap_is_read_on_its_open_frames():
    from perception.scoreboard import is_scoreboard

    assert is_scoreboard(_native("reqmr-2873352801-1980-900s", 657.7)) is True
    assert is_scoreboard(_native("reqmr-2873352801-1980-900s", 657.8)) is True
    assert is_scoreboard(_native("reqmr-2873352801-1980-900s", 658.0)) is False


def test_native_false_killcam_is_one_frame():
    """Day 330.0: the reader's one false 'killcam' over ordinary play. It stays
    one frame, which the banner vote absorbs (see the synthetic test above)."""
    from perception.events import banner_word

    words = [banner_word(_native("daymr-2879354299-21660-900s", t)) for t in (329.9, 330.0, 330.1)]
    assert words.count("killcam") <= 1


def test_native_countdowns_the_old_reader_missed():
    """Visible countdowns the classifier refused (6 against 8) or dropped as too
    wide (11), now read; and none read as a different number."""
    from perception import hud

    cases = [("daymr-2879354299-21660-900s", "get_over_here", 244.3, 6),
             ("daymr-2879354299-21660-900s", "get_over_here", 648.3, 6),
             ("reqmr-2873352801-1980-900s", "get_over_here", 86.8, 6),
             ("reqmr-2873352801-1980-900s", "get_over_here", 369.2, 6),
             ("reqmr-2873352801-1980-900s", "teamup", 600.3, 11),
             ("reqmr-2873352801-1980-900s", "teamup", 141.9, 10)]
    for src, slot, t, want in cases:
        assert hud.read_cooldown(_native(src, t), slot, hud.LAYOUTS["mk"]) == want, (src, t)
    # A 9 whose tail half-closes on a busy background must not become an 8.
    assert hud.read_cooldown(_native("daymr-2879354299-21660-900s", 337.7), "teamup",
                             hud.LAYOUTS["mk"]) in (None, 9)


def test_a_one_frame_misread_mid_countdown_is_nothing():
    """Day 339.0: a running 6 read as 8 for one frame. One read is not a timer:
    no cast, and no uncertainty either -- the countdown simply continues."""
    vals = [7] * 10 + [6] * 5 + [8] + [6] * 5 + [5] * 10 + [4] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 41),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    assert not [e for e in events if e.kind in ("ability_cast", "ability_uncertain")]


def test_an_uppercut_between_cast_lock_is_a_use_only_with_evidence_placing_it():
    """Every uppercut use shows the short between-cast lock ("1" on this patch).
    A "1" after frames with no number could equally be the last second of a
    recharge that began before the segment: uncertain. A charge badge read
    beforehand places the use after it, less the lock itself."""
    vals = [None] * 15 + [1] * 8 + [None] * 10
    events = extract_one(_slot_reads(vals, slot="uppercut", ready=[True] * 33), mapping={"uppercut": "uppercut"})
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_uncertain"]
    events = extract_one(_slot_reads(vals, slot="uppercut", charges=[1] * 33, ready=[True] * 33),
                         mapping={"uppercut": "uppercut"}, timers={"uppercut": 6}, locks={"uppercut": 1})
    (cast,) = [e for e in events if e.kind.startswith("ability_")]
    assert cast.kind == "ability_cast" and cast.t_from <= 0.4 and cast.t_to == 1.5 and cast.known_at == 1.6


def test_an_unread_frame_is_no_evidence_either_way_for_a_charged_use():
    """On the stream HUD most frames of a charged slot are unreadable (chat).
    Such a frame neither places a use (the countdown may have been running
    unread) nor makes one doubtful; a charge badge read does place it, and an
    out-of-kit read beside it makes it uncertain."""
    vals = [None] * 10 + [4] * 10 + [3] * 10
    ready = [None] * 10 + [True] * 20
    kit = {"mapping": {"swing": "swing"}, "timers": {"swing": 6}}
    events = extract_one(_slot_reads(vals, slot="swing", ready=ready), **kit)
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_uncertain"]
    badge = [1] * 10 + [0] * 20
    events = extract_one(_slot_reads(vals, slot="swing", charges=badge, ready=ready), **kit)
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_cast"]
    vals[5] = 9                                               # a number swing cannot show
    events = extract_one(_slot_reads(vals, slot="swing", charges=badge, ready=ready), **kit)
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_uncertain"]


def test_a_countdown_that_may_predate_the_segment_is_uncertain_even_after_a_lit_slot():
    """A one-charge countdown first read at full just after the segment opens
    may have started a moment before it. The frame before showing the slot lit
    with no number does not settle it: that is also a running cooldown whose
    digits went unread."""
    vals = [None] * 3 + [8] * 10 + [7] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here", ready=[True] * 23),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_uncertain"]


# --- review contract probes (writer-fix review of b6ae015) ------------------
# Copied from the independent review. Each is a contract, not a tuning: they
# failed on b6ae015 and hold for the evidence model above.

def _probe_rows(values, slot="get_over_here", ready=True, start=0, playing=True):
    result = []
    for n, v in enumerate(values):
        lit = ready[n] if isinstance(ready, list) else ready
        i = start + n
        result.append((i, round(i / 10, 3), Hud(hp=250, max_hp=250, bar_fill=1.0,
                       abilities={slot: (lit, None)}, cooldowns={slot: v}), playing))
    return result


def _probe_events(rs, slot="get_over_here", full=8):
    return extract_one(rs, mapping={slot: slot}, timers={slot: full})


def _casts(es):
    return [e for e in es if e.kind == "ability_cast"]


def test_probe_lit_missing_number_does_not_prove_in_segment_cast():
    # Segment opens mid-countdown, first glyph unreadable, then reads 5.
    assert _casts(_probe_events(_probe_rows([None, 5, 5]))) == []


def test_probe_unread_charge_slot_does_not_prove_in_segment_cast():
    rs = _probe_rows([None] * 10 + [4] * 2, slot="swing", ready=[None] * 10 + [True] * 2)
    assert _casts(_probe_events(rs, slot="swing", full=6)) == []


def test_probe_number_dropout_does_not_narrow_event_interval():
    # A use at 1.0 expires at 9.0, but the first readable digit is 4 at 5.0.
    (event,) = _casts(_probe_events(_probe_rows([None] * 50 + [4] * 2)))
    assert event.t_from <= 1.0, event


def test_probe_confirmation_cannot_be_visible_in_an_earlier_prefix():
    # First 8 at 2.0; confirming 7 at 3.0. At 2.0 no confirmed event exists.
    # Restated on known_at: the review's copy selected by t_to, which was the
    # known-by time then and is now the occurrence bound (the use was no later
    # than 2.0, and that is known only at 3.0).
    rs = _probe_rows([None] * 20 + [8] + [None] * 9 + [7], ready=None)
    short = [e for e in _probe_events(rs[:21]) if e.known_at <= 2.0]
    long = [e for e in _probe_events(rs) if e.known_at <= 2.0]
    assert short == long, long


def test_probe_expiry_alone_is_not_observed_ready():
    rs = _probe_rows([8, 8] + [None] * 85, ready=True)
    es = _probe_events(rs)
    ended = [e for e in es if e.kind == "cooldown_ended"]
    observed_ready = bool(ended) and not any(
        e.kind in ("ability_cast", "ability_uncertain") and e.t_to > ended[-1].t_to for e in es)
    assert not observed_ready, ended


def test_probe_non_play_timers_do_not_reclassify_own_play():
    from perception.events import timer_lengths

    own = _probe_rows([None] * 20 + [8] * 10 + [7] * 10 + [6] * 10 + [5] * 10, ready=None)
    other = []
    for start in (300, 600, 900):
        other += _probe_rows([12] * 10 + [11] * 10 + [10] * 10, ready=None, start=start, playing=False)
    # The review's copy relied on extract()'s old default kit; mechanics are now
    # supplied, as for every known-kit test.
    short, _ = extract(own, mapping={"get_over_here": "get_over_here"}, kit=KIT)
    long, _ = extract(own + other, mapping={"get_over_here": "get_over_here"}, kit=KIT)
    a = [(e.kind, e.t_from, e.t_to) for e in short if e.kind == "ability_cast"]
    b = [(e.kind, e.t_from, e.t_to) for e in long if e.kind == "ability_cast" and e.t_to <= own[-1][1]]
    assert a
    assert a == b, (timer_lengths(own), timer_lengths(own + other))


def test_probe_one_max_hp_read_does_not_prove_both_sides_unchanged():
    # A full 400 bonus pool decays to 394; after it max hp is unreadable.
    rs = [(0, 0.0, Hud(hp=400, max_hp=400, bar_fill=1.0)),
          (1, 0.1, Hud(hp=394, max_hp=None, bar_fill=1.0)),
          (2, 0.2, Hud(hp=394, max_hp=None, bar_fill=1.0))]
    (event,) = [e for e in extract_one(rs) if e.kind == "hp_lost"]
    assert event.cause == "unknown", event


def test_probe_ult_prohibition_is_not_a_spend():
    rs = [(i, i / 10, Hud(hp=250, max_hp=250, bar_fill=1.0, ult_ready=v, ult_charge=q))
          for i, (v, q) in enumerate([(True, 1.0), (False, 0.0), (False, 0.0), (True, 1.0)])]
    assert [e for e in extract_one(rs) if e.kind == "ult_spent"] == []


def test_a_timer_last_read_far_from_zero_records_no_end():
    """An expiry by the clock alone is not recorded when the countdown was last
    read with seconds to run: the slot after it is unknown, and an end event
    there would read as the slot coming back."""
    rs = _probe_rows([None] * 20 + [8] * 2 + [None] * 85, ready=True)
    es = _probe_events(rs)
    assert _casts(es) and not [e for e in es if e.kind == "cooldown_ended"]


def test_an_ult_icon_coming_back_full_is_not_a_return():
    """The other half of the prohibition mark: the icon lights again at full with
    no refill seen, which is display, not the ult becoming ready."""
    rs = [(i, i / 10, Hud(hp=250, max_hp=250, bar_fill=1.0, ult_ready=v, ult_charge=q))
          for i, (v, q) in enumerate([(True, 1.0), (False, 0.0), (False, 0.0), (True, 1.0)])]
    assert [(e.kind, e.slot) for e in extract_one(rs)] == [("icon_dimmed", "ult"), ("icon_lit", "ult")]


# --- second review batch (native-frame review of b6ae015) --------------------

def test_the_previous_timer_is_the_one_still_running_not_the_latest_made():
    """Day team-up 101.6-145.6 s, the frozen reads: a countdown runs 14 -> 6;
    chat read as "1" twice at 103.0 / 103.3 forms a timer of its own; at 109.9
    two misread 8s (the slot shows 6). Against the chat timer the 8s passed the
    kit check and became a cast while the cooldown was running."""
    fx = _json.loads((ROOT / "tests/fixtures/teamup_prev.json").read_text())
    rs = [(i, t, Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={"teamup": (r, c)}, cooldowns={"teamup": cd}))
          for i, t, cd, r, c in fx["frames"]]
    events = extract_one(rs, mapping={"teamup": "teamup"}, timers={"teamup": 15})
    assert not [e for e in events if e.kind == "ability_cast" and 101.6 <= e.t_to <= 115.5]
    # Nor an uncertain stretch: the 8s were read while the 6 provably ran, so
    # they are a misread of it, and censoring 8 s of known cooldown helps nobody.
    assert not [e for e in events if e.kind.startswith("ability_") and 101.6 <= e.known_at <= 115.5]


def test_a_single_read_is_uncertain_once_its_expiry_passes():
    """Req uppercut 89.7 / 98.5: one "1", every neighbour unreadable. A real
    between-cast lock and a misread cannot be told apart; the stream says so,
    from the moment the read could have been confirmed and was not."""
    vals = [None] * 20 + [1] + [None] * 20
    events = extract_one(_slot_reads(vals, slot="uppercut"), mapping={"uppercut": "uppercut"})
    (e,) = [e for e in events if e.kind.startswith("ability_")]
    assert e.kind == "ability_uncertain" and e.known_at >= 3.15 and e.t_to == 2.0
    early = extract_one(_slot_reads(vals[:30], slot="uppercut"), mapping={"uppercut": "uppercut"})
    assert [x for x in early if x.known_at <= 3.0] == [x for x in events if x.known_at <= 3.0]


def test_a_single_misread_inside_a_running_cooldown_is_nothing():
    vals = [None] * 12 + [8] * 10 + [3] + [7] * 10 + [6] * 10 + [5] * 10 + [4] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here"), mapping={"get_over_here": "get_over_here"},
                         timers={"get_over_here": 8})
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_cast"]
    # A charged slot: a countdown on screen means no charge to use.
    vals = [None] * 12 + [5] * 10 + [2] + [4] * 10 + [3] * 10 + [2] * 10 + [1] * 10
    events = extract_one(_slot_reads(vals, charges=[1] * 12 + [0] * 51), mapping={"swing": "swing"},
                         timers={"swing": 6})
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_cast"]


def test_a_countdown_longer_than_the_kit_raises_the_alarm_and_stops_casts():
    """Measured lengths are an alarm, never a calibration: a charged slot's
    countdown ticking above the kit's recharge contradicts the kit, and from
    then on the slot writes only uncertainty. Before it, casts stand: the
    alarm is causal, so a prefix still yields what the whole did."""
    ok = [None] * 12 + [5] * 10 + [4] * 10 + [None] * 30
    long = [9] * 10 + [8] * 10 + [7] * 10 + [None] * 30 + [5] * 10 + [4] * 10
    rs = [(*r, True) for r in _slot_reads(ok + long, charges=[1] * 12 + [0] * 20 + [1] * 30 + [0] * 90)]
    alarm = {}
    events, _ = extract(rs, mapping={"swing": "swing"}, alarm=alarm, kit=KIT)
    assert alarm["swing"]["read"] == 9 and alarm["swing"]["kit"] == 6.0, alarm
    kinds_ = [(e.kind, e.t_to) for e in events if e.kind.startswith("ability_")]
    assert kinds_[0][0] == "ability_cast" and all(k == "ability_uncertain" for k, _ in kinds_[1:]), kinds_
    # Day swing 152.5: one misread "8" inside a 6-5 recharge is not a longer timer.
    one = [None] * 2 + [8] + [None] * 9 + [6] * 10 + [5] * 10 + [4] * 10
    alarm = {}
    extract([(*r, True) for r in _slot_reads(one)], mapping={"swing": "swing"}, alarm=alarm, kit=KIT)
    assert alarm == {}
    # Three lone reads that happen to tick, 9, 8, 7 a second apart: none confirmed.
    alarm = {}
    sparse = [None] * 12 + [9] + [None] * 9 + [8] + [None] * 9 + [7] + [None] * 20
    extract([(*r, True) for r in _slot_reads(sparse)], mapping={"swing": "swing"}, alarm=alarm, kit=KIT)
    assert alarm == {}
    # Chat parked over the slot for three seconds: one value, never ticking.
    alarm = {}
    extract([(*r, True) for r in _slot_reads([None] * 12 + [9] * 30 + [None] * 10)],
            mapping={"swing": "swing"}, alarm=alarm, kit=KIT)
    assert alarm == {}
    # Day uppercut 155.0: "8 8 7 7" inside half a second is a misread pair, not a timer.
    pair = [None] * 12 + [8, 8, 7, 7] + [None] * 30
    alarm = {}
    extract([(*r, True) for r in _slot_reads(pair, slot="uppercut")], mapping={"uppercut": "uppercut"}, alarm=alarm,
            kit=KIT)
    assert alarm == {}


def test_black_level_boundaries():
    """Measured over all 17,986 frames of both train sections: firings at most
    7.56, ordinary dark gameplay from 11.49 (Req 46.5 s, the underground map)."""
    import numpy as np

    from perception.events import is_black

    for level, black in ((7, True), (11, False), (22, False)):
        frame = np.full((1080, 1920, 3), 60, np.uint8)
        frame[216:810, 384:1536] = level
        assert is_black(frame) is black, level


def test_native_dark_gameplay_is_not_black():
    from perception.events import is_black

    assert not is_black(_native("reqmr-2873352801-1980-900s", 46.5))


def test_hp_cause_needs_max_hp_unchanged_not_merely_read():
    """Max hp read on both sides but moved by a different amount than hp (the
    ultimate's bonus coming off): not damage, and not a shield tick either."""
    seq = reads(hud(hp=400, max_hp=500), hud(hp=150, max_hp=300), hud(hp=150, max_hp=300))
    (e,) = [e for e in extract_one(seq) if e.kind == "hp_lost"]
    assert e.cause == "unknown"


def test_a_cast_interval_starts_no_earlier_than_its_timer_allows():
    """The lower bound is expiry - full length, not the segment start."""
    (e,) = _casts(_probe_events(_probe_rows([None] * 50 + [8] * 2)))
    assert e.t_from == 4.1 and e.t_to == 5.0 and e.known_at == 5.1, e   # two 8s: start in (4.1, 5.0]


def test_a_weak_own_hero_match_is_visible_on_the_segment():
    rs = [(i, i / 10, hud(), True, None, False, False, score)
          for i, score in enumerate([0.41] * 5 + [0.37] * 3 + [0.41] * 5)]
    _, segs = extract(rs, mapping=IDENTITY)
    assert [s.hero_weak_frames for s in segs] == [3]
    _, segs = extract([r[:7] for r in rs], mapping=IDENTITY)
    assert [s.hero_weak_frames for s in segs] == [None]


def test_a_timer_expiring_before_the_running_one_is_nothing():
    """A one-charge slot cannot start a second timer while one runs: read while
    the first provably runs, it is a misread of that one, and emits nothing."""
    vals = [None] * 40 + [8] * 10 + [5] * 2 + [7] * 10
    events = extract_one(_slot_reads(vals, slot="get_over_here"), mapping={"get_over_here": "get_over_here"},
                         timers={"get_over_here": 8})
    assert [e.kind for e in events if e.kind.startswith("ability_")] == ["ability_cast"]


def test_without_a_length_a_first_timer_cannot_be_placed():
    seq = reads(*[hud()] * 12, *[hud(get_over_here_cd=n) for n in (8, 8, 7, 7)])
    got = extract_one(seq, mapping=IDENTITY)
    assert [e.kind for e in got if e.kind.startswith("ability_")] == ["ability_uncertain"]


def test_a_segment_whose_timer_outruns_the_source_length_gets_no_length():
    """Team-up is Symbiote Bond (15 s) on the train sources and Parker Power-Up
    (10 s) with another partner. A 15 s timer in a source measured at 10 must
    not be placed with 10: that segment's first timer is then unplaceable."""
    ten = [None] * 12 + [10] * 10 + [9] * 10 + [8] * 10 + [None] * 100
    rs = [(i, round(i / 10, 3), Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={"teamup": (True, None)},
                                    cooldowns={"teamup": v}), True) for i, v in enumerate(ten * 3)]
    fifteen = [None] * 12 + [15] * 10 + [14] * 10 + [13] * 10
    start = len(rs) + 30
    rs += [(start + i, round((start + i) / 10, 3), Hud(hp=0), True) for i in range(3)]      # a death between
    rs += [(start + 3 + i, round((start + 3 + i) / 10, 3), Hud(hp=250, max_hp=250, bar_fill=1.0,
            abilities={"teamup": (True, None)}, cooldowns={"teamup": v}), True) for i, v in enumerate(fifteen)]
    events, segs = extract(rs, mapping={"teamup": "teamup"})
    last = [e.kind for e in events if e.segment == len(segs) - 1 and e.kind.startswith("ability_")]
    assert last == ["ability_uncertain"], last


# --- round two review (eb69a63): durations are inputs; known_at is causal ------
# The five probes, verbatim. They select by t_to as the review wrote them; the
# prefix property below states the contract on known_at, for every event.

def _r2_rows(values, slot='get_over_here', charges=None):
    return [(i, round(i / 10, 3), Hud(hp=250, max_hp=250, bar_fill=1.,
        abilities={slot: (None, charges[i] if charges else None)},
        cooldowns={slot: v}), True) for i, v in enumerate(values)]


def _r2_timer_events(rs, full=8):
    return extract_one(rs, mapping={'get_over_here': 'get_over_here'},
                       timers={'get_over_here': full})


def _r2_at(es, t):
    return [e for e in es if e.t_to <= t and e.kind in
            ('ability_cast', 'ability_uncertain', 'cooldown_ended')]


def test_r2_late_first_read_does_not_establish_full_cooldown():
    # Physical history: 8 s cast at -1, expiry 7; digits hidden until t=2.
    # Same visible sequence also fits a 5 s cast at 2. No observed restart.
    rs = _r2_rows([None] * 20 + [5] * 10 + [4] * 10 + [3] * 10)
    es, _ = extract(rs, mapping={'get_over_here': 'get_over_here'})
    assert not [e for e in es if e.kind == 'ability_cast'], es


def test_r2_future_confirmation_does_not_erase_past_uncertainty():
    vals = [None] * 42
    vals[10] = 4   # not yet a confirmed timer
    vals[20] = 1   # isolated, its expiry passes by 3.2
    vals[40] = 1   # confirms the first timer only at 4.0
    short = _r2_at(_r2_timer_events(_r2_rows(vals[:33])), 3.2)
    long = _r2_at(_r2_timer_events(_r2_rows(vals)), 3.2)
    assert short == long, (short, long)


def test_r2_future_timer_read_does_not_move_an_already_known_expiry():
    vals = [None] * 35
    vals[20] = 1
    vals[21] = 1
    vals[33] = 1
    short = _r2_at(_r2_timer_events(_r2_rows(vals[:33])), 3.2)
    long = _r2_at(_r2_timer_events(_r2_rows(vals)), 3.2)
    assert short == long, (short, long)


def test_r2_old_two_second_uppercut_lock_does_not_move_cast_later():
    # Old-patch uppercut at 2.2, lock expires 4.2. One charge remains;
    # hidden countdown plus badge 1 at 3.8, then 1 at 3.9 and 4.0.
    vals = [None] * 41
    vals[39] = vals[40] = 1
    rs = _r2_rows(vals, slot='uppercut', charges=[2] * 22 + [1] * 19)
    es = extract_one(rs, mapping={'uppercut': 'uppercut'})
    casts = [e for e in es if e.kind == 'ability_cast']
    assert casts, es
    assert casts[0].t_from <= 2.2, casts


def test_r2_later_own_play_does_not_reclassify_earlier_event():
    first = [None] * 20 + [8] * 10 + [7] * 10 + [6] * 10 + [None] * 120
    later = ([None] * 20 + [6] * 10 + [5] * 10 + [4] * 10 + [None] * 120) * 3
    short, _ = extract(_r2_rows(first), mapping={'get_over_here': 'get_over_here'})
    long, _ = extract(_r2_rows(first + later), mapping={'get_over_here': 'get_over_here'})
    assert _r2_at(short, len(first) / 10) == _r2_at(long, len(first) / 10)


def test_the_old_patch_kit_places_the_old_lock():
    """The same reads under the previous patch's kit (a 2 s lock): the badge
    bound allows the use at 2.2. Under the current kit the lock is 1 s and the
    bound is later -- which is why the kit is keyed by the recorded patch."""
    from perception.events import KITS, durations

    vals = [None] * 41
    vals[39] = vals[40] = 1
    rs = _r2_rows(vals, slot='uppercut', charges=[2] * 22 + [1] * 19)
    full, lock = durations(KITS["Season 10, Version 20260903"], {"uppercut": "uppercut"})["uppercut"]
    (cast,) = [e for e in extract_one(rs, mapping={'uppercut': 'uppercut'}, timers={'uppercut': full},
                                      locks={'uppercut': lock}) if e.kind == 'ability_cast']
    assert cast.t_from <= 2.2, cast


def test_no_kit_means_every_timer_event_is_uncertain():
    rs = _r2_rows([None] * 20 + [8] * 10 + [7] * 10 + [6] * 10)
    es, _ = extract(rs, mapping={'get_over_here': 'get_over_here'}, kit=None)
    assert [e.kind for e in es if e.kind.startswith("ability_")] == ["ability_uncertain"]


def test_team_up_has_no_length_without_its_variant():
    """Symbiote Bond is 15 s, Parker Power-Up 10 s: the slot's length depends on
    which it holds, which is not identified per segment."""
    from perception.events import KITS, KIT_REFERENCE, durations

    assert durations(KITS[KIT_REFERENCE], {"teamup": "teamup"})["teamup"] == (None, None)


# --- the prefix invariant -----------------------------------------------------

def _prefix_invariant(run, rs, min_casts=0):
    """For every prefix, the events with known_i inside it equal the whole's --
    `run` fixes the kit, so the prefix and the whole get identical inputs --
    and the whole is not vacuous: at least `min_casts` casts, all known inside
    the reads rather than deferred past their end."""
    full = run(rs)
    assert all(e.known_i is not None and e.known_at is not None for e in full)
    known = [e for e in full if e.kind == "ability_cast" and e.known_i <= rs[-1][0]]
    assert len(known) >= min_casts, (len(known), min_casts)
    for n in range(1, len(rs) + 1):
        last = rs[n - 1][0]
        short = sorted(repr(e) for e in run(rs[:n]) if e.known_i <= last)
        whole = sorted(repr(e) for e in full if e.known_i <= last)
        assert short == whole, (n, last, set(short) ^ set(whole))


def _gap_reads(case):
    slot = case["slot"]
    return [(i, t, Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={slot: (ready, charges)},
                       cooldowns={slot: cd})) for i, t, cd, ready, charges in case["frames"]]


@pytest.mark.parametrize("case", _json.loads(GAP_FIXTURE.read_text())["cases"],
                         ids=lambda c: f"{c['source'][:5]}-{c['slot']}-{c['t_event']}")
def test_prefix_invariant_on_native_reads(case):
    rs = _gap_reads(case)
    _prefix_invariant(lambda x: _run_case({**case, "frames": [
        (r[0], r[1], r[2].cooldowns[case["slot"]], *r[2].abilities[case["slot"]]) for r in x]}), rs,
        min_casts=1 if case["expect"] == "cast" else 0)


def test_prefix_invariant_on_the_team_up_fixture_and_hp_windows():
    fx = _json.loads((ROOT / "tests/fixtures/teamup_prev.json").read_text())
    rs = [(i, t, Hud(hp=250, max_hp=250, bar_fill=1.0, abilities={"teamup": (r, c)}, cooldowns={"teamup": cd}))
          for i, t, cd, r, c in fx["frames"]]
    _prefix_invariant(lambda x: extract_one(x, mapping={"teamup": "teamup"}, timers={"teamup": 15}), rs,
                      min_casts=1)
    for name in ("decay", "ultimate"):
        _prefix_invariant(extract_one, _hp_window(name))


def test_prefix_invariant_on_the_review_probe_sequences():
    vals = [None] * 42
    vals[10], vals[20], vals[40] = 4, 1, 1
    _prefix_invariant(_r2_timer_events, _r2_rows(vals))
    vals = [None] * 35
    vals[20] = vals[21] = vals[33] = 1
    _prefix_invariant(_r2_timer_events, _r2_rows(vals))
    vals = [None] * 41
    vals[39] = vals[40] = 1
    _prefix_invariant(lambda x: extract_one(x, mapping={'uppercut': 'uppercut'}),
                      _r2_rows(vals, slot='uppercut', charges=[2] * 22 + [1] * 19))
    first = [None] * 20 + [8] * 10 + [7] * 10 + [6] * 10 + [None] * 40
    later = [None] * 20 + [6] * 10 + [5] * 10 + [4] * 10 + [None] * 30
    _prefix_invariant(lambda x: extract(x, mapping={'get_over_here': 'get_over_here'}, kit=KIT)[0],
                      _r2_rows(first + later), min_casts=1)


def test_prefix_invariant_across_segment_breaks():
    """extract() over a run with a death, a scoreboard tap, a one-frame portrait
    blip, hp steps, a shield tick and the ult: segment membership settles
    within SEG_LAG, and every event's known_i carries it."""
    huds, asides, playing = [], [], []

    def add(h, n, aside=None, play=True):
        huds.extend([h] * n)
        asides.extend([aside] * n)
        playing.extend([play] * n)
    add(hud(), 15)
    for v in (8, 8, 7, 7, 6, 6):
        add(hud(get_over_here_cd=v), 1)
    add(hud(hp=200), 3)
    add(hud(hp=200), 1, play=False)                       # a one-frame blip: absorbed
    add(hud(hp=200, ult=False), 2)
    add(replace(hud(hp=200, ult=False), ult_charge=0.5), 3)
    add(hud(hp=0), 3)                                     # death
    add(hud(hp=250, max_hp=300), 20)
    add(hud(hp=240, max_hp=290), 4)                       # a shield tick
    add(hud(hp=240, max_hp=290), 2, aside="scoreboard")   # a tap
    add(hud(hp=240, max_hp=290, swing_cd=5, swing_charges=0), 4)
    add(hud(hp=240, max_hp=290), 20)
    rs = [(i, round(i / 10, 3), h, p, a, False, False) for i, (h, a, p) in enumerate(zip(huds, asides, playing))]
    _prefix_invariant(lambda x: extract(x, mapping=IDENTITY, kit=KIT)[0], rs, min_casts=1)



def test_a_timer_that_ran_out_does_not_swallow_the_next_one():
    """Once a timer's expiry has passed it is closed: a countdown read just
    after, though within the rounding band of the old expiry, is a new one."""
    vals = [None] * 20 + [1, 1] + [None] * 10 + [1, 1] + [None] * 20
    events = extract_one(_slot_reads(vals, slot="uppercut", charges=[1] * 54), mapping={"uppercut": "uppercut"},
                         timers={"uppercut": 6}, locks={"uppercut": 1})
    assert len([e for e in events if e.kind.startswith("ability_")]) == 2


def test_prefix_invariant_where_segmentation_and_hp_look_ahead():
    """The places a later frame can still change an earlier one: a portrait
    blip on the very frame hp changes; a blip followed by two seconds of
    unknown portrait; a one-frame hp spike; a shield tick whose max hp lands a
    frame late; the ult going dark with its refill seen later."""
    huds, playing = [], []

    def add(h, n, play=True):
        huds.extend([h] * n)
        playing.extend([play] * n)
    add(hud(), 15)
    add(hud(hp=200, swing_ready=False), 1, play=False)    # blip on the change; the icon settles at once
    add(hud(hp=200), 15)
    add(hud(hp=200), 1, play=False)                       # blip, then unknown
    add(hud(hp=200), 5, play=None)
    add(hud(hp=200, uppercut_ready=False), 5, play=None)  # an icon change inside the unknown run
    add(hud(hp=200), 10, play=None)
    add(hud(hp=200), 15)
    add(hud(hp=40), 1)                                    # a spike
    add(hud(hp=200), 10)
    add(hud(hp=300, max_hp=300), 10)
    add(hud(hp=298, max_hp=300), 1)                       # max hp a frame late
    add(hud(hp=298, max_hp=298), 10)
    add(hud(hp=298, max_hp=298, ult=False), 8)
    add(replace(hud(hp=298, max_hp=298, ult=False), ult_charge=0.5), 5)
    add(hud(hp=298, max_hp=298), 20)
    rs = [(i, round(i / 10, 3), h, p, None, False, False) for i, (h, p) in enumerate(zip(huds, playing))]
    _prefix_invariant(lambda x: extract(x, mapping=IDENTITY, kit=KIT)[0], rs)
    _prefix_invariant(lambda x: extract_one([r[:3] for r in x], mapping=IDENTITY), rs)


def test_native_mk_charge_badges_read_across_the_uppercut_decrements():
    """Day uppercut: the badge steps 2 -> 1 a frame or two before the "1" lock.
    The "2" is a light disc with a dark digit, the "1" a light digit on a dark
    centre whose ring is too faint to find; the M&K reader read neither."""
    from perception import hud

    mk = hud.LAYOUTS["mk"]
    src = "daymr-2879354299-21660-900s"
    for two, one in ((46.6, 46.7), (240.9, 241.0), (320.9, 321.0), (612.9, 613.0),
                     (721.4, 721.8), (748.9, 749.0), (759.0, 759.1)):
        assert hud.read_charges(_native(src, two), mk.slot_cx["uppercut"], mk) == 2, two
        assert hud.read_charges(_native(src, one), mk.slot_cx["uppercut"], mk) == 1, one
    # Chat over the badge ("for some 1v1s") is not a charge count.
    assert hud.read_charges(_native("reqmr-2873352801-1980-900s", 165.0), mk.slot_cx["uppercut"], mk) is None



def test_a_restart_is_a_cast_only_where_its_start_fits_the_last_expiry():
    """Compatibility of intervals, not a tolerance: "3" read at 2.0 and 2.1 puts
    the previous expiry in (4.1, 5.0]; a restart first read 8, 8 at T starts in
    (T - 0.9, T]. They must meet, up to TIMER_EPS of frame timing."""
    def run(k):
        vals = [None] * 20 + [3, 3] + [None] * (k - 22) + [8, 8] + [None] * 30
        es = extract_one(_slot_reads(vals, slot="get_over_here"),
                         mapping={"get_over_here": "get_over_here"}, timers={"get_over_here": 8})
        return [e.kind for e in es if e.kind.startswith("ability_")]
    assert run(50) == ["ability_cast"]       # T 5.0: start (4.1, 5.0] meets the expiry
    assert run(40) == ["ability_cast"]       # T 4.0: 0.1 s short, one frame of timing
    assert run(30) == []                     # T 3.0: a second early, while the 3 provably runs


def _native_reads(src):
    """A train section's per-frame reads, from B0's sidecars (local only)."""
    root = Path(_os.environ.get("RIVALS_DATA", ROOT / "data"))
    vis = root / f"experiments/b0/visibility/{src}.json"
    meta = root / f"demos/events/sections/{src}.jsonl"
    if not vis.exists() or not meta.exists():
        pytest.skip("B0 sidecars not on this machine")
    mapping = _json.loads(meta.read_text().splitlines()[0])["slot_mapping"]
    rows = []
    for f in _json.loads(vis.read_text())["frames"]:
        h = dict(f.get("hud") or {})
        h["abilities"] = {k: tuple(v) for k, v in (h.get("abilities") or {}).items()}
        rows.append((f["i"], f["t"], Hud(**h), f["playing"], f["aside"], f["killfeed"], f["cut"]))
    return rows, mapping


@pytest.mark.parametrize("src", ["daymr-2879354299-21660-900s", "reqmr-2873352801-1980-900s"])
def test_prefix_invariant_on_every_real_segment(src):
    """Every prefix of every own-play segment of both train sections, and the
    whole source cut at tenths: the events known inside a prefix are the
    whole's, field for field, with the reference kit on both sides."""
    from perception.events import KITS, KIT_REFERENCE, ceilings, charge_maxima, durations

    rows, mapping = _native_reads(src)
    spans = durations(KITS[KIT_REFERENCE], mapping)
    kw = dict(mapping=mapping, timers={p: f for p, (f, _) in spans.items() if f},
              locks={p: l for p, (_, l) in spans.items() if l}, tops=ceilings(KITS[KIT_REFERENCE], mapping),
              maxes=charge_maxima(KITS[KIT_REFERENCE], mapping))
    by_i = {r[0]: (r[0], r[1], r[2], r[5]) for r in rows}
    casts = 0
    for seg in segment(rows):
        inside = [by_i[i] for i in range(seg.start_i, seg.end_i + 1) if i in by_i]
        full = extract_one(inside, **kw)
        casts += sum(1 for e in full if e.kind == "ability_cast")
        for n in range(2, len(inside) + 1):
            last = inside[n - 1][0]
            assert sorted(map(repr, (e for e in extract_one(inside[:n], **kw) if e.known_i <= last))) == \
                sorted(map(repr, (e for e in full if e.known_i <= last))), (src, seg.start_t, n)
    assert casts >= 50, casts                      # not vacuous: the sections' casts are there
    whole, _ = extract(rows, mapping=mapping, kit=KIT)
    for k in range(1, 10):
        cut = rows[: len(rows) * k // 10]
        last = cut[-1][0]
        part, _ = extract(cut, mapping=mapping, kit=KIT)
        assert sorted(map(repr, (e for e in part if e.known_i <= last))) == \
            sorted(map(repr, (e for e in whole if e.known_i <= last))), (src, k)



def test_a_team_up_read_above_every_variant_is_not_a_countdown():
    """With the variant unknown the length is, but not the ceiling: no team-up
    counts down from more than its longest variant, 15 s."""
    rs = [(*r, True) for r in _slot_reads([None] * 12 + [20] * 2 + [None] * 30, slot="teamup")]
    events, _ = extract(rs, mapping={"teamup": "teamup"}, kit=KIT)
    assert not [e for e in events if e.kind.startswith("ability_")]



# --- round three review (a63a510): the three probes and their positive controls, verbatim --

def _r3_rows(vals, slot='get_over_here', charges=None):
    return [(i, round(i/10,3), Hud(hp=250,max_hp=250,bar_fill=1.,
        abilities={slot:(None, None if charges is None else charges[i])},
        cooldowns={slot:v}), True) for i,v in enumerate(vals)]


def _r3_goh(rs):
    return extract_one(rs,mapping={'get_over_here':'get_over_here'},timers={'get_over_here':8})


def test_r3_restated_confirmation_probe_preserves_intent_and_is_nonvacuous():
    rs=_r3_rows([None]*20+[8]+[None]*9+[7])
    short=_r3_goh(rs[:21]); full=_r3_goh(rs)
    assert [e for e in short if e.known_at<=2] == [e for e in full if e.known_at<=2]
    casts=[e for e in full if e.kind=='ability_cast']
    assert len(casts) == 1
    assert casts[0].t_to <= 2.
    assert casts[0].known_at == 3.


def test_r3_omitted_kit_is_not_a_claim_of_current_patch():
    rs=_r3_rows([None]*20+[8]*10+[7]*10+[6]*10)
    es,_=extract(rs,mapping={'get_over_here':'get_over_here'})
    assert not [e for e in es if e.kind=='ability_cast'], repr(es)


def test_r3_unknown_charged_kit_and_no_badge_cannot_infer_cast_from_second_timer():
    vals=[None]*110
    vals[20]=vals[21]=2
    vals[80]=vals[81]=2
    es,_=extract(_r3_rows(vals,slot='swing'),mapping={'swing':'swing'},kit=None)
    assert not [e for e in es if e.kind=='ability_cast'], repr(es)


def test_r3_known_kit_rejects_impossible_badge_counts():
    # Kit declares uppercut max2, so a noisy 7->1 is not six spent charges.
    rs=_r3_rows([None]*40,slot='uppercut',charges=[7]*20+[1]*20)
    es,_=extract(rs,mapping={'uppercut':'uppercut'},kit=_KITS[_KIT_REF])
    assert not [e for e in es if e.kind=='charges_spent'], repr(es)


def test_r3_independent_charge_drop_survives_unknown_kit():
    vals=[None]*40
    es,_=extract(_r3_rows(vals,slot='uppercut',charges=[2]*20+[1]*20),
                 mapping={'uppercut':'uppercut'},kit=None)
    assert [e for e in es if e.kind=='charges_spent'], repr(es)


def test_r3_known_kit_survives_confirmation_and_segmentation_lag():
    rs=_r3_rows([None]*20+[8]*10+[7]*10+[6]*10)
    es,_=extract(rs,mapping={'get_over_here':'get_over_here'},kit=_KITS[_KIT_REF])
    casts=[e for e in es if e.kind=='ability_cast']
    assert len(casts) == 1, repr(es)
    assert casts[0].known_at <= rs[-1][1]
    for n in range(1,len(rs)+1):
        prefix,_=extract(rs[:n],mapping={'get_over_here':'get_over_here'},kit=_KITS[_KIT_REF])
        assert [e for e in prefix if e.known_at<=rs[n-1][1]] == [e for e in es if e.known_at<=rs[n-1][1]]


def test_an_impossible_badge_count_places_no_cast_either():
    """The same validated counts feed cast placement. Swing (max 3, lock
    unknown): a read of 7 then 1 is not a decrement, so it cannot place the
    use behind a countdown; the recharge alone cannot either (it may predate
    the segment). A real 3 -> 1 drop does place it."""
    vals = [None] * 39 + [2, 2] + [None] * 10
    def casts(before):
        rs = _r3_rows(vals, slot='swing', charges=[before] * 22 + [1] * 29)
        es, _ = extract(rs, mapping={'swing': 'swing'}, kit=_KITS[_KIT_REF])
        return [e for e in es if e.kind == 'ability_cast'], rs
    bad, rs = casts(7)
    assert not bad, bad
    assert rs[0][2].abilities['swing'][1] == 7       # the raw read is kept, not clamped
    good, _ = casts(3)
    assert len(good) == 1 and good[0].t_from <= 2.2, good
