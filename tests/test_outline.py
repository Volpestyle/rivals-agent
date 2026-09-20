"""Checks for the classical enemy finder.

Run with `uv run --group perception pytest`; a bare `uv run pytest` skips this file
(see tests/conftest.py). Synthetic frames only — no recorded data needed.
"""
import numpy as np

from agent.state import ENEMY
from perception.outline import GREEN, detect, find_bars, find_enemies, find_green

RED, GREEN_BGR = (0, 0, 255), (83, 199, 92)  # BGR; the game's own Enemy Color swatch


def _frame(h=720, w=1280):
    return np.zeros((h, w, 3), np.uint8)


def test_nameplate_found_and_body_placed_below_it():
    f = _frame()
    f[287:297, 449:554] = RED
    bars = find_bars(f)
    assert len(bars) == 1 and bars[0][:2] == (449, 287)
    dets = detect(f, mode="red")
    assert len(dets) == 1 and dets[0].cls == ENEMY
    assert dets[0].bbox[1] > 297, "body box must hang below the bar"


def test_tall_red_blob_is_not_a_nameplate():
    """The player's torso: red, large, but the wrong shape."""
    f = _frame()
    f[323:454, 453:560] = RED
    assert find_bars(f) == []


def test_player_belt_is_not_a_nameplate():
    """Spider-Man's belt is genuinely a wide thin bright-red bar.

    Shape and colour cannot separate it from a nameplate; what separates it is the
    torso directly above. This is the defect from the offline integration run
    (docs/evidence/l2/l6-outline-false-positives.png).
    """
    f = _frame()
    f[300:390, 430:530] = (0, 0, 200)   # torso above
    f[392:400, 430:500] = RED           # belt
    assert find_bars(f) == [], "belt must be rejected by the suit-above guard"


def test_nameplate_survives_when_nothing_is_above_it():
    """The guard must not fire on a real nameplate that happens to sit over scenery."""
    f = _frame()
    f[200:260, 440:520] = (120, 90, 70)  # dull masonry above, not suit-coloured
    f[287:297, 449:554] = RED
    assert len(find_bars(f)) == 1


def test_scale_must_be_given_for_a_native_crop():
    """A 960 px square cut from a 1440p capture has 2.0x marks, not 1.33x."""
    crop = _frame(960, 960)
    crop[400:420, 100:310] = RED         # a nameplate at native resolution
    assert find_bars(crop, scale=2.0), "with the true scale it is a nameplate"
    assert detect(crop, scale=2.0, mode="red")[0].bbox[0] > 0


def test_green_outline_box_is_the_silhouette():
    """A thin closed contour: the bounding box is the body, with no geometry guessing."""
    f = _frame()
    f[300:420, 600:660] = GREEN_BGR
    f[304:416, 604:656] = 0              # hollow it out, leaving a ~4 px ring
    dets = find_enemies(f)
    assert len(dets) == 1 and dets[0].cls == ENEMY
    # within a couple of px: closing the mask to rejoin the contour's arcs moves the
    # component bounds slightly, so the box is never exactly the drawn rectangle
    assert all(abs(a - b) <= 2 for a, b in zip(dets[0].bbox, (600.0, 300.0, 660.0, 420.0))), dets[0].bbox


def test_filled_green_region_is_rejected():
    """The range has a bright green door with a green cross; a solid patch is scenery."""
    f = _frame()
    f[300:420, 600:700] = GREEN_BGR          # filled, not a contour
    assert [b for b in find_green(f) if b[4] == "outline"] == []


def test_auto_mode_falls_back_to_the_red_path():
    """Footage recorded before the accessibility setting still has to work."""
    f = _frame()
    f[287:297, 449:554] = RED
    assert len(detect(f, mode="auto")) == 1


def test_outline_and_its_nameplate_are_one_enemy():
    """A bot carries both marks; it must not come back as two detections."""
    f = _frame()
    f[120:130, 600:700] = GREEN_BGR          # nameplate above
    f[180:320, 600:700] = GREEN_BGR
    f[186:314, 606:694] = 0              # hollow body outline below it
    assert len(find_enemies(f)) == 1


def test_lone_nameplate_still_counts():
    """An enemy behind cover shows only its bar; the brain still wants it."""
    f = _frame()
    f[120:130, 600:700] = GREEN_BGR
    assert len(find_enemies(f)) == 1


def test_close_enemy_in_the_player_band_survives():
    """A bot at point blank stands exactly where the player is drawn."""
    f = _frame()
    f[300:560, 560:700] = GREEN_BGR
    f[306:554, 566:694] = 0
    assert len(find_enemies(f)) == 1


def test_small_junk_in_the_player_band_is_dropped():
    f = _frame()
    f[500:530, 560:600] = GREEN_BGR
    f[504:526, 564:596] = 0
    assert find_enemies(f) == []


def test_band_is_a_parameter():
    """A swatch change must be one constant, not an edit through the file."""
    f = _frame()
    f[300:420, 600:660] = (200, 80, 80)      # a blue-ish mark, outside GREEN
    f[304:416, 604:656] = 0
    assert find_enemies(f) == []
    blue = GREEN._replace(hue_lo=100, hue_hi=125)
    assert len(find_enemies(f, band=blue)) == 1
