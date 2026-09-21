"""Checks for the classical enemy finder.

Run with `uv run --group perception pytest`; a bare `uv run pytest` skips this file
(see tests/conftest.py). Synthetic frames only — no recorded data needed.
"""
import numpy as np
import pytest

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


def test_health_bar_floating_above_the_body_is_not_a_second_enemy():
    """The bar clears the silhouette entirely, so an overlap test misses it."""
    f = _frame()
    f[250:262, 600:700] = GREEN_BGR      # health bar, well above and not touching
    f[320:460, 610:690] = GREEN_BGR
    f[326:454, 616:684] = 0              # body outline
    assert len(find_enemies(f)) == 1


def test_a_bar_far_above_a_body_is_still_its_own_enemy():
    """An enemy on a balcony above another must not be swallowed."""
    f = _frame()
    f[60:72, 600:700] = GREEN_BGR        # far above: a different enemy's mark
    f[320:460, 610:690] = GREEN_BGR
    f[326:454, 616:684] = 0
    assert len(find_enemies(f)) == 2


def test_a_band_can_wrap_hue_zero():
    """Red wraps 0, so hue_lo > hue_hi has to mean 'outside the gap', not 'empty'."""
    from perception.outline import RED
    f = _frame()
    f[300:420, 600:660] = (40, 40, 220)   # BGR red, hue ~0
    f[304:416, 604:656] = 0
    assert len(find_enemies(f, band=RED)) == 1
    assert find_enemies(f) == []          # and the green band must not see it


# --- the kill feed, and whether a box's name bar was seen (VUH-1314, postfreeze30) ------------------------------------------------------
def _body(f, y1, y2, x1, x2):
    f[y1:y2, x1:x2] = GREEN_BGR
    f[y1 + 6:y2 - 6, x1 + 6:x2 - 6] = 0


def test_the_kill_feed_name_is_never_an_enemy_but_a_real_bar_at_the_top_right_is():
    """The kill feed's victim name is one enemy-green text line at a fixed place (720p: y 30-37, x ~1160-1215). Dropped only when the
    mark lies wholly in that band: a real bot's bar at the top-right is taller or touches the top edge, and stays."""
    f = _frame()
    f[30:37, 1160:1210] = GREEN_BGR                  # the kill feed's "LUNA SNOW"
    assert find_enemies(f) == []
    g = _frame()
    g[24:52, 1140:1275] = GREEN_BGR                  # a real name-and-health bar, taller than the kill feed's line (tagrun0 000070)
    assert len(find_enemies(g)) == 1
    h = _frame()
    h[0:10, 1075:1155] = GREEN_BGR                   # a bar cut by the top edge (tagrun1 000342)
    assert len(find_enemies(h)) == 1


def test_a_body_records_whether_its_name_bar_was_seen():
    f = _frame()                                     # right of the player zone, whose small marks are dropped as the hero's own
    f[250:262, 900:1000] = GREEN_BGR                 # its bar
    _body(f, 320, 460, 910, 990)
    assert [d.plate for d in find_enemies(f)] == [True]
    g = _frame()
    _body(g, 320, 460, 910, 990)                     # no bar anywhere: seen to have none
    assert [d.plate for d in find_enemies(g)] == [False]
    h = _frame()
    _body(h, 60, 200, 910, 990)                      # where its bar would float is above the image: not seen, not "none"
    assert [d.plate for d in find_enemies(h)] == [None]


def test_a_bar_with_no_body_is_no_evidence_of_a_bar():
    """A lone bar is what green scenery fakes (the spawn room door's flat glass edges): the projected box says nothing either way."""
    f = _frame()
    f[120:130, 900:1000] = GREEN_BGR
    d, = find_enemies(f)
    assert d.plate is None


def test_native_kill_feed_frames_lose_only_the_kill_feed():
    import cv2
    from pathlib import Path
    kill = Path("data/l1/postfreeze30/000150.jpg")
    real = [Path("data/l1/tagrun0/000206.jpg"), Path("data/l1/tagrun0/000228.jpg"), Path("data/l1/tagrun1/000342.jpg")]
    if not kill.exists() or not all(p.exists() for p in real):
        pytest.skip("native frames not on this machine")
    boxes = find_enemies(cv2.imread(str(kill)), scale=2.0)
    assert not any(b.bbox[0] > 2200 and b.bbox[1] < 260 for b in boxes)              # nothing at the kill feed
    for p in real:                                                                    # a real bot at the top-right: still found
        assert any(b.bbox[0] > 2100 and b.bbox[1] < 260 for b in find_enemies(cv2.imread(str(p)), scale=2.0)), p


def test_an_aim_crop_passes_where_it_sits_so_the_hud_zones_stay_on_the_hud():
    """HUD zones are places on the screen. Given a crop without its origin they land on the scene inside it (postfreeze30: 32 aim-crop
    boxes removed, 16 of them 120 px or taller); with the origin they cover only what is really HUD."""
    crop = np.zeros((480, 480, 3), np.uint8)                   # a 720p-scale crop centred on the crosshair: x 400-880, y 120-600
    _body(crop, 20, 140, 425, 470)                             # in the crop's own top-right corner: mid-screen in the frame
    assert find_enemies(crop, scale=1.0) == []                 # the defect: the fps-readout zone applied to the crop
    assert len(find_enemies(crop, scale=1.0, origin=(400, 120), frame=(1280, 720))) == 1
    hud = np.zeros((480, 480, 3), np.uint8)                    # a crop that really does sit on the fps readout (top right of the screen)
    _body(hud, 60, 180, 400, 460)
    assert find_enemies(hud, scale=1.0, origin=(800, 0), frame=(1280, 720)) == []


def _hsv_bgr(h, s=200, v=220):
    import cv2
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def test_a_component_at_the_bands_low_edge_is_scenery_not_an_enemy():
    """The spawn room door's glass passes the band at hue 54 (61% of its pixels there); bots centre on 64-65. A component whose median
    hue is under GREEN_MIN_MEDIAN_HUE is dropped; its pixels still count for connectivity elsewhere."""
    lime, bot = _hsv_bgr(54), _hsv_bgr(64)
    f = _frame()
    f[300:440, 900:980] = lime
    f[306:434, 906:974] = 0
    assert find_enemies(f) == []
    g = _frame()
    g[300:440, 900:980] = bot
    g[306:434, 906:974] = 0
    assert len(find_enemies(g)) == 1
    k = _frame()                                     # a bot outline with some low-hue edge pixels: still one enemy, whole
    k[300:440, 900:980] = bot
    k[300:440, 900:915] = lime
    k[306:434, 906:974] = 0
    d, = find_enemies(k)
    assert d.bbox[2] - d.bbox[0] >= 78 and d.height >= 138          # the whole outline, the low-hue side included


def test_l4_trials_crop_call_passes_where_the_crop_sits_too():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import l4_trial
    f = np.zeros((1440, 2560, 3), np.uint8)
    f[300:520, 1640:1720] = GREEN_BGR                       # the crop's top-right corner, mid-screen in the frame
    f[312:508, 1652:1708] = 0
    f[600:820, 1100:1180] = GREEN_BGR                       # and a body mid-crop, so the crop is not empty (no whole-frame fallback)
    f[612:808, 1112:1168] = 0
    boxes = l4_trial.detect(f)
    assert len(boxes) == 2 and max(b.bbox[0] for b in boxes) >= 815    # in 1280x720 pixels, where l4_trial reports


def test_the_door_seen_from_the_plaza_is_under_the_hue_bar_too():
    """From the plaza side the door's boxes have a median hue of 54-58 (p50 55): a component at 57 is dropped, one at 60 kept."""
    for hue, kept in ((57, 0), (60, 1)):
        f = _frame()
        f[300:440, 900:980] = _hsv_bgr(hue)
        f[306:434, 906:974] = 0
        assert len(find_enemies(f)) == kept, hue
