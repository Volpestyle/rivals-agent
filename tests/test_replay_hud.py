"""perception.replay_hud: column order, abstention, per-frame rows and cast events.

Needs opencv and numpy (`uv run --group perception pytest tests/test_replay_hud.py`). The event logic is tested on
synthetic rows. The layout, order and abstention tests use the DayMR replay keyframes and James's review frames where
they are on this machine (data/ is not committed); absent, those tests skip with the reason.
"""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from perception import hud
from perception import replay_hud as rh
from perception.replay_hud import Row

ROOT = Path(__file__).resolve().parent.parent
REPLAY = ROOT / "data" / "demos" / "replays" / "daymr-20260923-004325"
HUMAN = ROOT / "data" / "human" / "sessions"
has_replay = pytest.mark.skipif(not (REPLAY / "classify.json").is_file(), reason="DayMR replay keyframes absent")
has_human = pytest.mark.skipif(not list(HUMAN.glob("*/review-frames/*.jpg")), reason="James's review frames absent")


def key(name):
    return cv2.imread(str(REPLAY / "frames" / "key" / f"{name}.jpg"))


def cd(t, n, ability="get_over_here"):
    return Row(t, ability, "cooldown", n, 1.0)


def st(t, state, ability="get_over_here"):
    return Row(t, ability, state, None, 1.0 if state != "unknown" else 0.0)


def count(t, n, ability="web_cluster.ammo"):
    return Row(t, ability, "count", n, 1.0)


# --- column order ---------------------------------------------------------------------------------------------------

def _fake_hud(monkeypatch, icons, badged):
    """identify_order on synthetic columns: `icons` per column, a badge read in each column of `badged`."""
    monkeypatch.setattr(rh.hud, "read_hp", lambda f: (250, 250))
    monkeypatch.setattr(rh.hud, "read_bar_fill", lambda f: 1.0)
    monkeypatch.setattr(rh.hud, "identify_slot", lambda f, cx: icons[rh.COLUMNS.index(cx)])
    monkeypatch.setattr(rh.hud, "read_charges", lambda f, cx, layout: 1 if rh.COLUMNS.index(cx) in badged else None)


FRAMES20 = [np.zeros((10, 10, 3), np.uint8)] * 20


def test_disagreeing_icons_and_badges_abstain(monkeypatch):
    _fake_hud(monkeypatch, [None, "swing", "uppercut", "get_over_here"], {1, 3})
    got = rh.identify_order(FRAMES20)
    assert got["order"] is None and "disagree" in got["why"]


@pytest.mark.parametrize("icons, badged, why", [
    (["swing", "swing", "get_over_here", "uppercut"], {1, 3}, "column 1"),     # another ability in column 1
    ([None, "swing", "get_over_here", "uppercut"], {0, 1, 3}, "column 1"),     # a badge on the team-up
    ([None, "get_over_here", "swing", "uppercut"], {1, 3}, "column 2"),        # the swing not in column 2
    ([None, "swing", "get_over_here", "uppercut"], {3}, "column 2"),           # no swing charges
])
def test_every_column_is_verified(monkeypatch, icons, badged, why):
    """Review item 4: columns 1 and 2 are checked, not only 3 and 4."""
    _fake_hud(monkeypatch, icons, badged)
    got = rh.identify_order(FRAMES20)
    assert got["order"] is None and why in got["why"]


def test_identify_order_filters_by_the_followed_player_itself(monkeypatch):
    """Review item 5: the follow filter lives in the module. Frames of another POV do not vote."""
    _fake_hud(monkeypatch, [None, "swing", "get_over_here", "uppercut"], {1, 3})
    monkeypatch.setattr(rh, "timeline_up", lambda f: False)
    slots = iter(["A1"] * 20 + ["B5"] * 20)
    monkeypatch.setattr(rh, "followed_slot", lambda f: next(slots))
    got = rh.identify_order(FRAMES20 * 2, source="replay", follow="B5")
    assert got["order"] == rh.DAYMR_ORDER and got["frames"] == 20


def test_layout_for_maps_each_ability_to_its_column():
    james = rh.layout_for(rh.JAMES_ORDER)
    assert james.slot_cx["uppercut"] == hud.MK.slot_cx["get_over_here"]
    assert james.slot_cx["get_over_here"] == hud.MK.slot_cx["uppercut"]
    assert rh.layout_for(rh.DAYMR_ORDER).slot_cx == hud.MK.slot_cx
    assert james.hp_text == hud.MK.hp_text and james.webs == hud.MK.webs          # geometry is MK's, unchanged
    with pytest.raises(ValueError):
        rh.layout_for(("swing", "teamup", "uppercut", "get_over_here"))


def test_identify_order_abstains_without_evidence():
    blank = np.zeros((1440, 2560, 3), np.uint8)
    got = rh.identify_order([blank] * 20)
    assert got["order"] is None and got["frames"] == 0


@has_replay
def test_identify_order_on_the_replay_is_daymrs():
    rows = [r for r in json.loads((REPLAY / "classify.json").read_text()) if r["pov"] == "B5"][::10]
    got = rh.identify_order((cv2.imread(str(REPLAY / r["file"])) for r in rows), source="replay", follow="B5")
    assert got["order"] == rh.DAYMR_ORDER and got["icons"][1:] == ["swing", "get_over_here", "uppercut"]
    assert got["badges"][0] == 0 and got["badges"][2] == 0 and got["badges"][3] >= rh.ORDER_MIN_BADGES


@has_human
def test_identify_order_on_james_is_his():
    paths = sorted(HUMAN.glob("*/review-frames/*.jpg"))[::3]
    frames = (cv2.resize(cv2.imread(str(p)), (2560, 1440), interpolation=cv2.INTER_CUBIC) for p in paths)
    got = rh.identify_order(frames)
    assert got["order"] == rh.JAMES_ORDER and got["icons"][1:] == ["swing", "uppercut", "get_over_here"]
    assert got["badges"][0] == 0 and got["badges"][3] == 0


# --- abstention -----------------------------------------------------------------------------------------------------

@has_replay
@pytest.mark.parametrize("frame, up", [("k0515", True), ("k0235", True), ("k0796", True), ("k0420", False),
                                       ("k0359", False)])
def test_the_replay_timeline_is_detected(frame, up):
    assert rh.timeline_up(key(frame)) is up


@has_replay
def test_timeline_frames_abstain_instead_of_reading_the_timeline():
    """Intake §3: every timeline frame gave confidently wrong ability and ult reads."""
    rows = rh.read_frame(key("k0515"), 0.0, rh.DAYMR_ORDER, source="replay")
    assert {r.state for r in rows} == {"unknown"} and rows[0].reason == "replay timeline up"


@has_replay
def test_the_dead_camera_abstains():
    rows = rh.read_frame(key("k0359"), 0.0, rh.DAYMR_ORDER, source="replay", follow="B5")
    assert {r.state for r in rows} == {"unknown"} and "dead" in rows[0].reason


@has_replay
def test_following_another_player_abstains():
    rows = [r for r in json.loads((REPLAY / "classify.json").read_text())
            if r["pov"] == "A1" and r["ui"]["timeline_speed"] < 0.2]
    f = key(Path(rows[len(rows) // 2]["file"]).stem)
    assert rh.followed_slot(f) == "A1"
    out = rh.read_frame(f, 0.0, rh.DAYMR_ORDER, source="replay", follow="B5")
    assert {r.state for r in out} == {"unknown"} and "not following B5" in out[0].reason


def test_an_unknown_column_order_abstains():
    rows = rh.read_frame(np.zeros((1440, 2560, 3), np.uint8), 1.0, None)
    assert rows and {r.state for r in rows} == {"unknown"} and all(r.confidence == 0.0 for r in rows)


@has_replay
def test_a_clean_frame_reads_every_field():
    rows = {r.ability: r for r in rh.read_frame(key("k0420"), 5.0, rh.DAYMR_ORDER, source="replay", follow="B5")}
    assert set(rows) == {"teamup", "swing", "get_over_here", "uppercut", "swing.charges", "uppercut.charges",
                         "web_cluster.ammo", "ult", "hp"}
    assert all(r.t == 5.0 for r in rows.values())
    assert all(r.confidence > 0 for r in rows.values() if r.state != "unknown")


# --- cast events: cooldowns -----------------------------------------------------------------------------------------

def test_a_countdown_places_the_cooldown_start():
    """051828's Get Over Here!: F at 41.512, numerals 8 then 7 ... stepping at 43.43 + k; start = 42.43."""
    rows = [st(43.0, "ready"), cd(43.384, 8), cd(43.443, 7), cd(44.434, 6), cd(45.443, 5), cd(50.426, 1),
            st(50.434, "ready")]
    events, coverage, flags = rh.cast_events(rows)
    (e,) = events
    assert e.basis == "countdown" and 42.40 <= e.t_lo < e.t_hi <= 42.47 and not flags
    assert e.precision <= 0.03


def test_not_ready_without_a_numeral_is_not_a_cast():
    """The HUD greys other abilities while one animates (0.2-0.8 s around each Amazing Combo on 051828)."""
    rows = [st(1.0, "ready"), st(1.1, "not_ready"), st(1.6, "not_ready"), st(1.9, "ready")]
    events, _, _ = rh.cast_events(rows)
    assert events == []


def test_a_flicker_inside_a_countdown_does_not_split_the_cast():
    rows = [st(46.8, "ready", "teamup"), cd(47.251, 10, "teamup"), cd(47.9, 10, "teamup"),
            st(47.943, "ready", "teamup"), st(47.951, "ready", "teamup"), st(47.959, "ready", "teamup"),
            cd(47.968, 9, "teamup"), cd(48.9, 9, "teamup"), cd(48.943, 8, "teamup")]
    events, _, flags = rh.cast_events(rows, cooldowns={"teamup": 10.0}, min_run=1)
    assert len(events) == 1 and events[0].basis == "countdown" and not flags
    assert events[0].t_lo <= 46.935 <= events[0].t_hi                      # the C press


def test_a_restarted_countdown_is_a_second_cast():
    rows = [cd(10.0, 8), cd(11.0, 7), st(18.5, "ready"), cd(20.0, 8), cd(21.0, 7)]
    events, _, _ = rh.cast_events(rows)
    assert len(events) == 2 and events[1].t_lo > 18.0


def test_without_a_duration_the_transition_bounds_the_cast():
    rows = [st(1.0, "ready", "teamup"), cd(3.0, 12, "teamup"), cd(5.0, 10, "teamup")]
    (e,), _, _ = rh.cast_events(rows)
    assert (e.t_lo, e.t_hi, e.basis) == (1.0, 3.0, "transition")


def test_inconsistent_numerals_are_flagged_not_trusted():
    rows = [st(1.0, "ready"), cd(1.5, 8), cd(2.5, 8), cd(2.6, 3)]          # 3 right after 8: not one cooldown
    events, _, flags = rh.cast_events(rows)
    assert sorted(e.basis for e in events) == ["countdown", "flagged"] and "misread" in flags[0]["why"]
    rows = [st(1.0, "ready"), cd(1.5, 8)]
    events, _, flags = rh.cast_events(rows, cooldowns={"get_over_here": 0.5})   # a numeral above the duration
    assert flags and events[0].basis == "flagged"


# --- cast events: counts, ult, unknowns -----------------------------------------------------------------------------

def test_an_ammo_drop_is_a_cast_count_and_a_bound():
    rows = [count(0.0, 5), count(2.0, 3), count(4.0, 3)]
    (e,), _, _ = rh.cast_events(rows)
    assert (e.ability, e.count, e.t_lo, e.t_hi) == ("web_cluster", 2, 0.0, 2.0)


def test_unknown_reads_never_become_no_cast():
    rows = [count(0.0, 5), Row(1.0, "web_cluster.ammo", "unknown", None, 0.0, "ammo unread"), count(6.0, 5)]
    events, coverage, _ = rh.cast_events(rows)
    assert events == [] and coverage["web_cluster.ammo"] == []              # 6 s apart: casts could hide
    rows = [count(0.0, 5), count(0.5, 5)]
    _, coverage, _ = rh.cast_events(rows)
    assert coverage["web_cluster.ammo"] == [(0.0, 0.5)]                    # close enough: no event means no cast


def test_count_coverage_only_at_the_maximum():
    """Review item 1: below the maximum a regen is in flight, and a cast plus a regen cancel between reads."""
    rows = [count(0.0, 4), count(0.5, 4), count(1.0, 5), count(1.5, 5)]
    _, coverage, _ = rh.cast_events(rows)
    assert coverage["web_cluster.ammo"] == [(1.0, 1.5)]
    rows = [count(0.0, 2, "uppercut.charges"), count(0.4, 2, "uppercut.charges"), count(0.8, 1, "uppercut.charges"),
            count(1.2, 1, "uppercut.charges")]
    events, coverage, _ = rh.cast_events(rows)
    assert coverage["uppercut.charges"] == [(0.0, 0.4)] and len(events) == 1


def test_press_time_coverage_merges_cuts_at_events_then_shrinks():
    """Review round 2, P1: adjacent read pairs are merged, cut at every event, then shrunk once."""
    pairs = [(10 + k / 120, 10 + (k + 1) / 120) for k in range(1200)]          # 10 s of dense reads
    ev = [rh.Event("get_over_here", 14.0, 14.02, 1, "countdown", 15.0)]
    out = rh.press_coverage({"get_over_here": pairs}, ev, {"get_over_here": (0.6, 1.0, 5)})
    assert out["get_over_here"] == [pytest.approx((10 - 0.6, 14.0 - 1.0)), pytest.approx((15.0 - 0.6, 20 - 1.0))]


def test_a_straddling_pair_with_a_one_sample_lag_never_covers_the_cast():
    """Review round 2, P1(b): the ult's n = 1 lag (zero spread) let a ready -> charging pair claim 'no press' across
    its own cast. Cut at the event and floored, no coverage reaches the cast's press window."""
    pairs = [(617.054, 619.620), (619.620, 640.0)]                              # the first pair straddles the cast
    ev = [rh.Event("ult", 617.054, 619.620, 1, "transition", 619.620)]
    cov = rh.press_coverage({"ult": pairs}, ev, {"ult": (0.0085, 0.0085, 1)})["ult"]
    lo, hi = rh.floored_lag(0.0085, 0.0085, 1)
    assert lo == 0.0 and hi >= 0.0085 + rh.LAG_FEW_HALF_WIDTH_S                  # floored, clamped at 0
    press_window = (617.054 - hi, 619.620 - lo)
    assert all(b <= press_window[0] or a >= press_window[1] for a, b in cov)


def test_press_coverage_is_empty_without_a_measured_lag():
    cov = {"teamup": [(0.0, 5.0)], "web_cluster.ammo": [(0.0, 5.0)]}
    out = rh.press_coverage(cov, [], {"teamup": None})
    assert out == {"teamup": [], "web_cluster": []}
    assert all(v == [] for v in rh.press_coverage(cov, []).values())          # the module default: unmeasured


def test_a_replay_source_needs_a_follow():
    with pytest.raises(ValueError, match="roster slot"):
        rh.identify_order([], source="replay")


def test_min_run_drops_frame_flicker():
    rows = [count(t / 120, 3) for t in range(10)] + [count(10 / 120, 2)] + [count(t / 120, 3) for t in range(11, 20)]
    assert rh.cast_events(rows, min_run=1)[0]                               # a 1-frame misread is a "cast" ...
    assert rh.cast_events(rows, min_run=3)[0] == []                         # ... unless flicker is filtered


def test_ult_ready_to_charging_is_a_cast():
    rows = [Row(0.0, "ult", "ready", None, 1.0), Row(2.0, "ult", "charging", None, 1.0)]
    (e,), _, _ = rh.cast_events(rows)
    assert (e.ability, e.t_lo, e.t_hi) == ("ult", 0.0, 2.0)


def test_the_hud_limits_are_stated():
    text = " ".join(rh.NOT_FROM_HUD)
    for word in ("aim", "swing hold", "movement", "melee", "did not cast"):
        assert word in text


def test_a_numeral_spike_is_a_misread_not_a_new_cast():
    """The DayMR replay at 120 fps: '3' for 7 frames between 13s split one team-up cooldown into two casts."""
    rows = [st(513.5, "ready", "teamup")]
    rows += [cd(515.538 + k / 120, 13, "teamup") for k in range(70)]
    rows += [cd(516.179 + k / 120, 3, "teamup") for k in range(7)]
    rows += [cd(516.254 + k / 120, 13, "teamup") for k in range(30)]
    rows += [cd(516.538 + k / 120, 12, "teamup") for k in range(60)]
    events, _, flags = rh.cast_events(rows, cooldowns={"teamup": 15.0}, min_run=3)
    assert len(events) == 1 and events[0].basis == "countdown" and 513.4 <= events[0].t_lo < events[0].t_hi < 513.6
    assert any(f["why"] == "misread countdown numerals dropped" and f["frames"] == 7 for f in flags)


def test_two_countdowns_closer_than_the_cooldown_are_one_cast():
    rows = [cd(10.0, 8), cd(11.0, 7), cd(12.2, 8), cd(13.2, 7)]          # a restart 2 s in: impossible for 8 s
    events, _, flags = rh.cast_events(rows)
    assert len(events) == 1 and any("merged" in f["why"] for f in flags)


# --- coverage walls (review of the step table, R3) and the hp row (R2) -----------------------------------------------

def test_coverage_never_crosses_a_withheld_frame():
    rows = [count(0.0, 5), count(0.1, 5), Row(0.15, "ult", "unknown", None, 0.0, "dead (hp 0)"), count(0.2, 5)]
    _, coverage, _ = rh.cast_events(rows)
    assert coverage["web_cluster.ammo"] == [(0.0, 0.1)]                   # 0.1 -> 0.2 crosses the dead frame


def test_coverage_never_crosses_a_break_and_honours_the_gap_cap():
    rows = [count(t / 10, 5) for t in range(10)] + [Row(t / 10, "ult", "charging", None, 1.0) for t in range(10)]
    _, coverage, _ = rh.cast_events(rows, breaks=[(0.45, 0.45)])           # a seek at 0.45 s
    assert (0.4, 0.5) not in coverage["web_cluster.ammo"] and (0.3, 0.4) in coverage["web_cluster.ammo"]
    _, coverage, _ = rh.cast_events(rows, max_gap_s=0.05)                  # reads 0.1 s apart: none close enough
    assert coverage["web_cluster.ammo"] == [] and coverage["ult"] == []


def test_a_field_abstention_is_not_a_wall_but_hp_unread_is_not_alive():
    rows = [count(0.0, 5), Row(0.05, "web_cluster.ammo", "unknown", None, 0.0, "ammo unread"), count(0.1, 5)]
    _, coverage, _ = rh.cast_events(rows)
    assert coverage["web_cluster.ammo"] == [(0.0, 0.1)]                   # one field unread: the frame was on screen
    assert not rh.withheld(Row(0.0, "hp", "unknown", None, 0.0, "hp unread"))
    assert rh.withheld(Row(0.0, "hp", "unknown", None, 0.0, "dead (hp 0)"))


@has_replay
def test_the_hp_row_is_read_on_a_clean_frame():
    rows = {r.ability: r for r in rh.read_frame(key("k0420"), 5.0, rh.DAYMR_ORDER, source="replay", follow="B5")}
    assert rows["hp"].state == "count" and rows["hp"].numeral > 0


def test_the_lag_floor_never_goes_below_zero_and_keeps_a_measured_range():
    assert rh.floored_lag(0.0963, 1.1019, 35, 0.1044) == (0.0963, 1.1019)          # n >= 3: the measured range
    lo, hi = rh.floored_lag(0.0018, 0.0098, 6, 0.0045)
    assert lo >= 0.0 and hi - lo == pytest.approx(rh.LAG_MIN_WIDTH_S) or lo == 0.0  # widened to two frames, clamped
    assert rh.floored_lag(0.0085, 0.0085, 1) == (0.0, pytest.approx(0.5085))        # n = 1: +-0.5 s, clamped at 0
