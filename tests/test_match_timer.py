"""perception.match_timer: the HUD match-timer value reader (lane doc, "Gate 2 step 1"; landed as a value reader
only, after fit-review's review of the seed-20260927 re-validation: T1 passed, T2 / T3' and the replay half undecided).

    uv run --group perception pytest tests/test_match_timer.py     (skipped without cv2 / numpy)

Fixtures (tests/fixtures/match_timer/) are crops of DEVELOPMENT recordings only (20-06-20.mkv, 20-37-11.mkv and the
DayMR replay's round 1); no validation recording and never a Gate 2 pair. The rejected kill-feed reader and its tests are
kept as a failed experiment in docs/evidence/gate2-revalidation-20260926/code/.
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

from perception import match_timer as M  # noqa: E402

FX = ROOT / "tests" / "fixtures" / "match_timer"


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
