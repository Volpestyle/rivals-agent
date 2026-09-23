"""read_tagged and hp against James's 2026-09-23 calibration take (VUH-1294).

The labels and fixtures are committed in docs/evidence/hud-calibration-20260923/;
the frames the labels name live under data/hud/calib-20260923/ (gitignored,
recipe in that README), so the scoring tests are corpus-marked. The rest pin the
tracer contract itself: "no tracer" needs this box's own plate in view.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from perception import hud

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs/evidence/hud-calibration-20260923"
FIXTURES = EVIDENCE / "fixtures"

# --- the contract, on a drawn frame ------------------------------------------

GREEN = (83, 199, 92)   # BGR of the enemy-colour plate, H~62 S~150 V~200
RED = (40, 40, 230)
NAME = "LUNA SNOW-Easy"


def _scene(tracer=True, bar_top=600, cx=1280, bar=True, colour=GREEN, frame=None):
    """A 2560 frame with one enemy plate at the offsets measured on the take:
    bar over name (name top 26 below the bar's, centred, bar's left end 110 left
    of centre), marker bottom 33 over the bar. `bar=False` is an enemy not yet
    hit, which the game draws with its name alone."""
    f = np.full((1440, 2560, 3), (120, 60, 60), np.uint8) if frame is None else frame
    if bar:
        cv2.rectangle(f, (cx - 110, bar_top), (cx + 110, bar_top + 18), colour, -1)
    (w, h), _ = cv2.getTextSize(NAME, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
    cv2.putText(f, NAME, (cx - w // 2, bar_top + 26 + h), cv2.FONT_HERSHEY_DUPLEX, 0.55, colour, 1)
    if tracer:
        base = np.array([[c == "#" for c in r] for r in hud.TRACER], np.uint8) * 255
        mark = cv2.resize(base, (36, 42), interpolation=cv2.INTER_NEAREST)
        y0 = bar_top - 33 - 42
        roi = f[y0:y0 + 42, cx - 18:cx + 18]
        roi[mark > 0] = 255
    return f


PLATE_BOX = (1180, 599, 1380, 900)    # the outline took in the plate: its top is the bar's
BODY_BOX = (1210, 700, 1350, 1000)    # a body under the plate
LEG = (1250, 1000, 1300, 1135)        # a fragment far below it


@pytest.fixture(params=[True, False], ids=["bar-required", "name-alone"])
def either_witness(request, monkeypatch):
    """Every safety property must hold whichever way PLATE_NEEDS_BAR is set."""
    monkeypatch.setattr(hud, "PLATE_NEEDS_BAR", request.param)
    return request.param


def test_a_box_holding_its_plate_reads_the_marker_just_above_it(either_witness):
    """The outline took in the plate, so the marker sits right on the box's top
    edge, below the band. This read False on 7 tagged whole or plate boxes."""
    assert hud.read_tagged(_scene(tracer=True), PLATE_BOX) is True
    assert hud.read_tagged(_scene(tracer=False), PLATE_BOX) is False
    assert hud.read_tagged(_scene(tracer=True), BODY_BOX) is True
    assert hud.read_tagged(_scene(tracer=False), BODY_BOX) is False


def test_a_fragment_with_no_plate_over_it_is_unknown_not_untagged(either_witness):
    """A leg: the band above it is empty, but its plate floats higher than a
    plate floats over a box that size. That was a confident False on 13
    tagged fragments; it is not evidence of anything."""
    assert hud.read_tagged(_scene(tracer=True), LEG) is None
    assert hud.read_tagged(_scene(tracer=False), LEG) is None


@pytest.mark.parametrize("colour", [RED, GREEN], ids=["red-bar", "green-bar"])
def test_a_bar_across_a_tagged_fragment_is_not_its_plate(colour, either_witness):
    """hud-review's constructed failure (F1): any flat run of either colour
    across a tagged fragment was taken as its plate and read False."""
    f = _scene(tracer=True)
    cv2.rectangle(f, (1200, 1000), (1340, 1014), colour, -1)
    assert hud.read_tagged(f, LEG) is not False


@pytest.mark.parametrize("name,box", [
    ("beam-0274_1881_0_0.png", (1881, 1165, 1926, 1222)),
    ("beam-0175_1991_-60_0.png", (1991, 1081, 2122, 1305)),
])
def test_a_real_beam_across_a_tagged_box_is_not_its_plate(name, box, either_witness):
    """hud-review's real-pixel case: the red beam of frame 0315 pasted across
    tagged boxes of the take (lossless crops of its PNGs, placed back at their
    offset in the frame). The first read False as a leg with the marker in
    plain view; the second, the beam over the bot's bar, read False once
    names alone were witnesses, before the letter test."""
    crop_at = {"beam-0274_1881_0_0.png": (1480, 880), "beam-0175_1991_-60_0.png": (1680, 700)}[name]
    crop = cv2.imread(str(FIXTURES / name))
    frame = np.zeros((1440, 2560, 3), np.uint8)
    x0, y0 = crop_at
    frame[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    assert hud.read_tagged(frame, box) is not False


def test_the_enemy_outline_is_not_taken_for_a_plate(either_witness):
    """The outline is drawn in the enemy colour too. A flat stretch of it
    (a hollow run, 0.15-0.21 ink on the take) must not stand in for a plate."""
    frame = np.full((1440, 2560, 3), (120, 60, 60), np.uint8)
    cv2.rectangle(frame, (1240, 740), (1320, 754), GREEN, 2)
    assert hud.read_tagged(frame, (1230, 700, 1330, 900)) is None


def test_a_plate_whose_marker_place_is_off_screen_proves_nothing(either_witness):
    """A plate at the very top: its marker would be drawn above the frame, so
    an empty window there is not "no tracer"."""
    frame = _scene(tracer=False, bar_top=60)
    assert hud.read_tagged(frame, (1180, 150, 1380, 450)) is None


def test_green_hud_text_in_a_dead_zone_is_not_a_plate(either_witness):
    """The fps readout and the kill feed are green text at the top right; with
    the marker's place on screen they would still be a witness, as they were
    for junk boxes on the take. Moved out of the zone, the same plate is one."""
    zone = _scene(tracer=False, bar_top=300, cx=2380)
    assert hud.read_tagged(zone, (2280, 299, 2480, 600)) is None
    assert hud.read_tagged(_scene(tracer=False, bar_top=300, cx=1280), (1180, 299, 1380, 600)) is False


def test_two_bots_plates_over_one_merged_box_read_unknown(either_witness):
    """One box over two bots, one marked and one not: which enemy is this?"""
    frame = _scene(tracer=True, cx=1180)
    frame[:, 1320:] = _scene(tracer=False, cx=1460)[:, 1320:]
    assert hud.read_tagged(frame, (1060, 599, 1580, 900)) is None


def test_the_plate_colour_is_the_finders():
    """The plate is read in the colour the caller's finder used: a red plate is
    no witness for the default green, and is for colour="red"."""
    f = _scene(tracer=False, colour=RED)
    assert hud.read_tagged(f, PLATE_BOX) is None
    assert hud.read_tagged(f, PLATE_BOX, colour="red") is False


def test_an_enemy_not_yet_hit_is_witnessed_by_its_name_alone(monkeypatch):
    """The game draws an enemy nobody has hit with its name and no bar. By
    default (the lead's call) that name is a witness; with the bar required
    it is not, and such an enemy is unknown."""
    f = _scene(tracer=False, bar=False)
    assert hud.read_tagged(f, (1180, 625, 1380, 900)) is False
    monkeypatch.setattr(hud, "PLATE_NEEDS_BAR", True)
    assert hud.read_tagged(f, (1180, 625, 1380, 900)) is None


def test_the_plate_path_costs_little():
    """Finding the plate and searching over it, the part read_tagged added:
    ~1 ms on the PC with the game running, against 1.4-6 ms for the band."""
    f = _scene(tracer=False)
    hud._own_plates(f, PLATE_BOX, hud.PLATE_COLOURS["green"])
    times = []
    for _ in range(40):
        t0 = time.perf_counter()
        for narrow, wide in hud._own_plates(f, PLATE_BOX, hud.PLATE_COLOURS["green"]):
            hud._tracer_peak(f, *wide, within=(narrow[0], narrow[2]))
        times.append((time.perf_counter() - t0) * 1000)
    assert statistics.median(times) <= 4.0, f"plate path median {statistics.median(times):.2f} ms"


def test_hp_228_at_1280_reads_unknown_not_220():
    """The digit veto's demonstrated failure: frame 0269's hp text taken down to
    1280 (lossless crop, placed back at HP_TEXT). Its 8 matched a 0 inside
    STRONG and hp read 220; a 0 with an 8 close behind now needs a 0's hole."""
    crop = cv2.imread(str(FIXTURES / "hp-228-at-1280.png"))
    frame = np.zeros((720, 1280, 3), np.uint8)
    x0, y0 = int(hud.HP_TEXT[0] * 1280), int(hud.HP_TEXT[1] * 720)
    frame[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    assert hud.read_hp(frame) == (None, 250)


# --- the calibration take ----------------------------------------------------

def _frames(doc):
    for entry in doc["frames"]:
        path = ROOT / entry["path"]
        if not path.exists():
            pytest.skip("calibration frames not on this machine (data/hud/calib-20260923)")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], entry["path"]
        yield entry, cv2.imread(str(path))


@pytest.mark.corpus
def test_read_tagged_on_the_calibration_take():
    """142 hand-labelled live boxes, far to close. Never a wrong answer; before
    the plate witness 20 tagged boxes read False (0 wrong True either way)."""
    doc = json.loads((EVIDENCE / "tag_truth.json").read_text())
    hits = unknown = 0
    wrong = []
    for entry, frame in _frames(doc):
        for box in entry["boxes"]:
            if box["tagged"] is None:
                continue
            got = hud.read_tagged(frame, box["bbox"])
            if got is None:
                unknown += 1
            elif got is box["tagged"]:
                hits += 1
            else:
                wrong.append(f"{entry['path']} {box['bbox']}: {got}")
    assert not wrong, wrong
    assert hits >= 72, f"{hits} hits, {unknown} unknown"   # measured 75 of 142 (36 True, 39 False)


@pytest.mark.corpus
def test_no_true_without_a_marker_and_no_false_beside_one():
    """All 339 live boxes of the take against a whole-frame marker scan made
    independently of any box: True only in frames with a marker somewhere,
    and False never on a box with a marker above it or near it."""
    doc = json.loads((EVIDENCE / "whole_take.json").read_text())
    bad = []
    for entry, frame in _frames(doc):
        marks = [(x + 18, y + 42) for x, y, score in entry["markers"] if score >= hud.TRACER_MATCH]
        for x1, y1, x2, y2 in entry["boxes"]:
            got = hud.read_tagged(frame, (x1, y1, x2, y2))
            if got is True and not marks:
                bad.append(f"{entry['path']} {[x1, y1, x2, y2]}: True, no marker in frame")
            near = any(x1 - 200 <= mx <= x2 + 200 and y1 - 700 <= my <= y2 + 200 for mx, my in marks)
            if got is False and near:
                bad.append(f"{entry['path']} {[x1, y1, x2, y2]}: False beside a marker")
    assert not bad, bad


@pytest.mark.corpus
@pytest.mark.parametrize("width", [2560, 1280])
def test_hp_on_the_calibration_take(width):
    """124 hand-read hp values from 0 to 373, 53 of them with a 1. Taken down
    to 1280 the 8 of 228 used to read as a 0."""
    doc = json.loads((EVIDENCE / "hp_truth.json").read_text())
    got_hp = got_max = 0
    wrong = []
    for entry, frame in _frames(doc):
        if width != frame.shape[1]:
            frame = cv2.resize(frame, (width, width * 9 // 16), interpolation=cv2.INTER_AREA)
        hp, max_hp = hud.read_hp(frame)
        for name, got, want in (("hp", hp, entry["hp"]), ("max_hp", max_hp, entry["max_hp"])):
            if got is not None and got != want:
                wrong.append(f"{entry['path']} {name}: {got}, truth {want}")
        got_hp += hp == entry["hp"]
        got_max += max_hp == entry["max_hp"]
    assert not wrong, wrong
    assert got_hp >= 113 and got_max >= 109, (got_hp, got_max)   # measured 117/113 at 2560, 115/111 at 1280
