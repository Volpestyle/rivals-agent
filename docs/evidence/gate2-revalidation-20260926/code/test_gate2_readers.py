"""perception.match_timer and perception.killfeed: Gate 2's timer and kill-feed readers (lane doc, "Gate 2 step 1").

    uv run --group perception pytest tests/test_gate2_readers.py     (skipped without cv2 / numpy)

Fixtures (tests/fixtures/gate2_readers/) are crops of DEVELOPMENT recordings only (20-06-20.mkv, 20-37-11.mkv and the
DayMR replay's round 1); no validation recording and never the Gate 2 pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception import killfeed as KF, match_timer as M  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "gate2_readers"


def img(name):
    return cv2.imread(str(FX / name))


@pytest.mark.parametrize("name, channel, expected", [
    ("centre_white_mmss.png", M.CENTRE, ("00:24", "mmss", "white")),
    ("centre_yellow_mmss.png", M.CENTRE, ("00:03", "mmss", "yellow")),
    ("centre_decimal.png", M.CENTRE, ("19.1", "decimal", "yellow")),
    ("centre_pop.png", M.CENTRE, ("18.9", "decimal_pop", "yellow")),     # the SS.d pop, read by undoing its scale
    ("team_a.png", M.TEAM_A, ("04:00", "mmss", "white")),
    ("team_b.png", M.TEAM_B, ("03:50", "mmss", "white")),
])
def test_the_timer_reads_each_format_on_its_channel(name, channel, expected):
    r = M.read_box(img(name), channel)
    assert r is not None and (r.text, r.fmt, r.color) == expected


@pytest.mark.parametrize("name", [
    "centre_lilac.png",      # 03:43 on a pale lilac sky: once misread as 03:48; it abstains now, never a guess
    "centre_blurred.png",    # the dimmed, blurred timer of a death screen
    "centre_none.png",       # no timer drawn
])
def test_the_timer_abstains_rather_than_guessing(name):
    assert M.read_box(img(name), M.CENTRE) is None


def test_a_non_native_frame_is_refused():
    with pytest.raises(ValueError, match="2560x1440"):
        M.read_frame(np.zeros((720, 1280, 3), np.uint8))
    reads = M.read_frame(np.zeros((1440, 2560, 3), np.uint8))
    assert set(reads) == {"centre", "team_a", "team_b"} and all(v is None for v in reads.values())


def test_the_glyph_file_holds_every_character_of_every_set():
    raw = json.loads((ROOT / "perception" / "match_timer_glyphs.json").read_text(encoding="utf-8"))
    assert set(raw["sets"]) == {"mmss", "decimal", "team"}
    assert set(raw["sets"]["mmss"]) == set(raw["sets"]["team"]) == set("0123456789:")
    assert set(raw["sets"]["decimal"]) == set("0123456789.")


def R(text):
    fmt = "decimal" if "." in text else "mmss"
    secs = float(text) if fmt == "decimal" else float(int(text[:2]) * 60 + int(text[3:]))
    return M.Read(text, secs, fmt, "white", 0.9)


def test_second_changes_take_the_first_frame_of_a_new_second_between_two_read_frames():
    seq = [R("00:12")] * 5 + [R("00:11")] * 40 + [R("00:10")] * 40
    assert M.second_changes(seq) == [(5, 12, 11), (45, 11, 10)]
    gap = [R("00:12")] * 5 + [None] + [R("00:11")] * 40               # the frame before the change is unread
    assert M.second_changes(gap) == []


def test_second_changes_skip_jumps_reverts_and_late_frames_after_a_revert():
    jump = [R("02:22")] * 10 + [R("04:52")] * 40                        # a checkpoint's time extension: not an anchor
    assert M.second_changes(jump) == []
    revert = [R("18.0")] * 10 + [R("17.9")] * 3 + [R("18.0")] * 6 + [R("17.9")] * 40     # the pop redraws 18.0
    assert M.second_changes(revert) == []
    decimal = [R("12.1")] * 12 + [R("12.0")] * 12 + [R("11.9")] * 40   # SS.d: the whole second changes at 11.9
    assert M.second_changes(decimal) == [(24, 12, 11)]


@pytest.mark.parametrize("name, entry", [
    ("kf_live_light.png", True), ("kf_live_dark.png", True), ("kf_spec_entry.png", True),
    ("kf_live_empty.png", False), ("kf_spec_empty.png", False),
])
def test_entry_likeness_on_real_top_slots(name, entry):
    assert KF.entry_like(img(name)) is entry


def test_the_viewer_prompt_marks_replay_frames_only():
    assert KF.viewer_prompt(img("prompt_viewer.png"), cropped=True) is True      # the Quick Match development replay
    assert KF.viewer_prompt(img("prompt_live.png"), cropped=True) is False       # a live development frame


def test_two_arrivals_sixteen_frames_apart_are_two_entries():
    light, dark = img("kf_live_light.png"), img("kf_live_dark.png")
    events = {40: [(0, light, 1.0)], 100: [(1, light, 1.0)]}
    for j, a in enumerate(np.linspace(0.1, 1.0, 10)):
        events[103 + j] = [(1, light, 1.0), (0, dark, float(a))]
    events[116] = [(1, dark, 1.0)]                                      # the second shift, 16 frames later (the oldest
    for j, a in enumerate(np.linspace(0.1, 1.0, 10)):                   # entry leaves the two visible slots)
        events[119 + j] = [(1, dark, 1.0), (0, light, float(a))]
    found = KF.entries(_live_sequence(events, n=300), "live", cropped=True)
    assert [e.k for e in found if e.via == "shift"] == [100 + KF.SHIFT_LAG["live"], 116 + KF.SHIFT_LAG["live"]]


def test_the_layout_is_recognised_or_unknown():
    assert KF.recognise_layout([True] * 40 + [False] * 10) == "spectator"
    assert KF.recognise_layout([False] * 100) == "live"
    assert KF.recognise_layout([True] * 10 + [False] * 90) is None           # neither clearly: fail closed
    assert KF.recognise_layout([]) is None
    assert KF.entries([np.zeros((130, 540, 3), np.uint8)] * 10, None, cropped=True) is None


def _live_sequence(events, n=260, seed=0):
    """Region crops (live layout) over a static textured background, with entry bands pasted per `events`:
    {frame: [(slot, band image, alpha)]} held until the next event."""
    rng = np.random.default_rng(seed)
    bg = rng.integers(40, 120, (130, 540, 3)).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (0, 0), 3)
    lay = KF.LAYOUTS["live"]
    r0 = lay["band"][0] - lay["region"][1]
    c0 = lay["cols"][0] - lay["region"][0]
    frames, state = [], []
    for k in range(n):
        state = events.get(k, state)
        f = bg.copy()
        for slot, band, alpha in state:
            y = r0 + 50 * slot
            h, w = band.shape[:2]
            f[y:y + h, c0:c0 + w] = (alpha * band + (1 - alpha) * f[y:y + h, c0:c0 + w]).astype(np.uint8)
        frames.append(f)
    return frames


def test_an_arrival_after_a_shift_is_timed_from_the_shift():
    light, dark = img("kf_live_light.png"), img("kf_live_dark.png")
    events = {40: [(0, light, 1.0)], 100: [(1, light, 1.0)]}          # the old entry drops a slot at frame 100
    for j, a in enumerate(np.linspace(0.1, 1.0, 10)):                  # the new one fades in from frame 104
        events[104 + j] = [(1, light, 1.0), (0, dark, float(a))]
    found = KF.entries(_live_sequence(events), "live", cropped=True)
    shift = [e for e in found if e.via == "shift"]
    assert [e.k for e in shift] == [100 + KF.SHIFT_LAG["live"]]


def test_an_arrival_into_an_empty_feed_is_never_a_shift_anchor():
    light = img("kf_live_light.png")
    events = {k: [(0, light, float(a))] for k, a in zip(range(80, 92), np.linspace(0.08, 1.0, 12))}
    found = KF.entries(_live_sequence(events), "live", cropped=True)
    assert len(found) == 1 and found[0].via in ("ramp", "untimed")
    assert found[0].k is None or abs(found[0].k - 80) <= 3
