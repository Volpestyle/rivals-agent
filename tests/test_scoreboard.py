"""Checks for perception.scoreboard.

    uv run --group perception --group dev pytest tests/test_scoreboard.py

The detector is checked on both scoreboards that exist: the practice range's
(pad HUD, committed under docs/evidence/l4/) and a live match's on a
mouse-and-keyboard stream. The VOD clip is local-only, so the tests that touch
it skip when it is not on the machine.

The reader is checked only on the range scoreboard, which is all it claims.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.scoreboard import (  # noqa: E402
    FIELDS, MIN_WIDTH, is_scoreboard, read_scoreboard, rule_score,
)

RANGE_NATIVE = ROOT / "docs/evidence/l4/scoreboard-back-native.jpg"
RANGE_720 = ROOT / "docs/evidence/l4/scoreboard-back-720.jpg"
EXTRA_RANGE = ROOT / "docs/evidence/l4/scoreboard"      # L4 adds more here
DAY_CLIP = ROOT / "data/demos/samples/daymr-2879354299-21600-60s.mp4"
# The four moments the DayMR player has the scoreboard open, found frame by
# frame: he checks it roughly every fifteen seconds.
DAY_SCOREBOARD_S = (13.1, 28.7, 42.1, 59.5)
DAY_PLAY_S = (5.0, 20.0, 35.0, 44.5)

# Read off docs/evidence/l4/scoreboard-back-native.jpg by eye.
RANGE_TRUTH = {
    "kos": 3, "deaths": 0, "assists": 1,
    "accuracy": 0, "damage": 845, "damage_blocked": 0, "healing": 0,
    "web_cluster_accuracy": 50, "spin_kos": 3,
}


def _clip_frame(seconds):
    if not DAY_CLIP.exists():
        return None
    cap = cv2.VideoCapture(str(DAY_CLIP))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(seconds * (cap.get(cv2.CAP_PROP_FPS) or 60)))
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


# --- is_scoreboard --------------------------------------------------------

def test_range_scoreboard_is_detected_at_both_sizes():
    for path in (RANGE_NATIVE, RANGE_720):
        frame = cv2.imread(str(path))
        assert frame is not None, path
        assert is_scoreboard(frame) is True, (path.name, rule_score(frame))


def test_match_scoreboard_is_detected_on_a_stream():
    """A different HUD, a different resolution, the same rule under the headers."""
    seen = 0
    for seconds in DAY_SCOREBOARD_S:
        frame = _clip_frame(seconds)
        if frame is None:
            continue
        seen += 1
        assert is_scoreboard(frame) is True, (seconds, rule_score(frame))
    if DAY_CLIP.exists():
        assert seen == len(DAY_SCOREBOARD_S)


def test_ordinary_play_is_not_a_scoreboard():
    for seconds in DAY_PLAY_S:
        frame = _clip_frame(seconds)
        if frame is None:
            continue
        assert is_scoreboard(frame) is False, (seconds, rule_score(frame))
    for path in sorted(glob.glob(str(ROOT / "data/run1/*.jpg")))[::700]:
        frame = cv2.imread(path)
        if frame is not None:
            assert is_scoreboard(frame) is False, (path, rule_score(frame))


def test_the_margin_is_wide():
    """Guards the threshold: scoreboards score ~0.97 and play well under 0.5."""
    frame = cv2.imread(str(RANGE_NATIVE))
    assert rule_score(frame) > 0.9
    play = [cv2.imread(p) for p in sorted(glob.glob(str(ROOT / "data/run1/*.jpg")))[::900]]
    scores = [rule_score(f) for f in play if f is not None]
    if scores:
        assert max(scores) < 0.5, scores


# --- read_scoreboard ------------------------------------------------------

def test_range_scoreboard_reads_every_value():
    frame = cv2.imread(str(RANGE_NATIVE))
    got = read_scoreboard(frame)
    assert got["open"] is True
    for field, want in RANGE_TRUTH.items():
        assert got[field] == want, f"{field}: read {got[field]!r}, truth {want!r}"


def test_a_frame_too_small_reads_nothing_rather_than_guessing():
    """The 720p copy of the same scoreboard: detectable, not readable."""
    frame = cv2.imread(str(RANGE_720))
    got = read_scoreboard(frame)
    assert got["open"] is True
    assert got["too_small"] == frame.shape[1]
    assert all(got[f] is None for f in FIELDS), got
    assert frame.shape[1] < MIN_WIDTH


def test_a_frame_without_a_scoreboard_reads_nothing():
    frame = cv2.imread(sorted(glob.glob(str(ROOT / "data/run1/*.jpg")))[0])
    if frame is None:
        return
    got = read_scoreboard(frame)
    assert got["open"] is False
    assert all(got[f] is None for f in FIELDS)


def test_result_is_a_plain_dict_the_loop_can_store():
    import json

    got = read_scoreboard(cv2.imread(str(RANGE_NATIVE)))
    assert isinstance(got, dict)
    json.dumps(got)          # must survive being written straight to a run record
    assert set(FIELDS) <= set(got)


TRUTH = EXTRA_RANGE / "truth.json"
# truth.json spells three fields its own way; this is the only place that knows.
TRUTH_KEYS = {"accuracy_pct": "accuracy", "web_cluster_accuracy_pct": "web_cluster_accuracy",
              "spectacular_spin_kos": "spin_kos"}


def _boards():
    import json

    if not TRUTH.exists():
        return []
    boards = json.loads(TRUTH.read_text())["boards"]
    return [(EXTRA_RANGE / name, {TRUTH_KEYS.get(k, k): v for k, v in values.items()})
            for name, values in boards.items()]


def test_every_l4_board_reads_every_field():
    """The eight native boards L4 read by eye: every value, no guesses."""
    boards = _boards()
    for path, truth in boards:
        frame = cv2.imread(str(path))
        assert frame is not None, path
        got = read_scoreboard(frame)
        assert got["open"] is True, path.name
        for field, want in truth.items():
            assert got[field] == want, f"{path.name} {field}: read {got[field]!r}, truth {want!r}"


def test_boards_read_with_their_own_values_held_out():
    """Leave-one-out: learn the digits from every other board, read this one.
    The templates come from these same boards, so this is the honest number."""
    from perception import scoreboard as sb

    frames = [(RANGE_NATIVE, RANGE_TRUTH)] + _boards()
    if len(frames) < 3:
        return
    full = dict(sb.GLYPHS)
    try:
        for held, (path, truth) in enumerate(frames):
            namespace = {}
            exec(sb.learn([f for j, f in enumerate(frames) if j != held]), {}, namespace)
            sb.GLYPHS.clear()
            sb.GLYPHS.update(namespace["GLYPHS"])
            sb._CACHE.clear()
            got = read_scoreboard(cv2.imread(str(path)))
            for field, want in truth.items():
                assert got[field] in (want, None), f"{path.name} {field}: WRONG {got[field]!r}"
                assert got[field] == want, f"{path.name} {field}: unread with it held out"
    finally:
        sb.GLYPHS.clear()
        sb.GLYPHS.update(full)
        sb._CACHE.clear()


def test_thousands_are_read_whole():
    """"1,375": the comma is too small to segment and used to split the number,
    so damage read as 1. Every board past 999 must read in full."""
    for path, truth in _boards():
        if truth["damage"] >= 1000:
            got = read_scoreboard(cv2.imread(str(path)))
            assert got["damage"] == truth["damage"], (path.name, got["damage"])


# --- kill feed ------------------------------------------------------------

def test_killfeed_frames_are_detected():
    from perception.scoreboard import is_killfeed

    for name in ("killfeed-a.jpg", "killfeed-b.jpg"):
        frame = cv2.imread(str(EXTRA_RANGE / name))
        if frame is None:
            continue
        assert is_killfeed(frame) is True, name


def test_no_killfeed_on_play_or_on_a_board():
    """Pale sky is colourless too; it is the crisp banner edge that tells them apart."""
    from perception.scoreboard import is_killfeed

    for path in sorted(glob.glob(str(ROOT / "data/run1/*.jpg")))[::120]:
        frame = cv2.imread(path)
        if frame is not None:
            assert is_killfeed(frame) is False, path
    for path, _ in _boards():
        assert is_killfeed(cv2.imread(str(path))) is False, path.name


def test_a_killfeed_line_appearing_is_a_ko_event():
    from perception.events import extract_one
    from perception.hud import Hud

    blank = Hud(hp=250, max_hp=250, bar_fill=1.0, webs=5, abilities={}, ult_ready=True)
    reads = [(i, i / 10, blank, feed) for i, feed in
             enumerate([False, False, False, True, True, True, True, False, False])]
    kos = [e for e in extract_one(reads) if e.kind == "ko_feed"]
    assert len(kos) == 1, kos
    assert kos[0].i_to == 4           # confirmed on its second frame
    assert kos[0].i_from == 2         # last frame without the line
