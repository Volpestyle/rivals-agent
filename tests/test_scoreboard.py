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


def test_extra_range_frames_when_l4_delivers_them():
    """Widens automatically: every frame L4 drops in must read or say it cannot."""
    for path in sorted(glob.glob(str(EXTRA_RANGE / "*.jpg"))):
        frame = cv2.imread(path)
        if frame is None:
            continue
        assert is_scoreboard(frame) is True, path
        got = read_scoreboard(frame)
        for field in FIELDS:
            assert got[field] is None or isinstance(got[field], int), (path, field)
