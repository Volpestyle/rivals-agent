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


@pytest.mark.corpus
def test_native_kill_feed_frames_lose_only_the_kill_feed():
    import cv2
    from pathlib import Path
    def fixture(name):
        # The same four reviewed PAD fixtures, also present in the PC runtime
        # checkout. No directory enumeration or alternative corpus search.
        for root in (Path("data/l1"), Path("C:/rivals-agent/data/l1")):
            if (root / name).is_file():
                return root / name
        pytest.skip(f"native fixture missing: {name}")
    kill = fixture("postfreeze30/000150.jpg")
    real = [fixture(name) for name in ("tagrun0/000206.jpg", "tagrun0/000228.jpg", "tagrun1/000342.jpg")]
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


@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("gap", [10, 22])
def test_partial_player_zone_body_needs_its_own_filled_health_strip(scale, gap):
    """Same partial body, with/without a health strip; merged and separate marks."""
    import cv2
    base = _frame()
    top = 308 + gap
    _body(base, top, top + 40, 590, 620)
    bare = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    assert find_enemies(bare, scale=scale) == []
    base[300:308, 560:640] = GREEN_BGR
    paired = cv2.resize(base, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    wide = find_enemies(paired, scale=scale)
    assert len(wide) == 1 and wide[0].bbox[3] >= (top + 38) * scale
    x,y = 400*scale,120*scale
    crop = paired[y:600*scale, x:880*scale]
    close = find_enemies(crop, scale=scale, origin=(x,y), frame=(1280*scale,720*scale))
    assert len(close) == 1
    assert np.allclose(close[0].bbox, np.array(wide[0].bbox) - (x,y,x,y))


@pytest.mark.parametrize("placement", ["none", "far_above", "below", "beside", "hud"])
def test_partial_player_junk_cannot_borrow_an_unrelated_or_hud_bar(placement):
    f = _frame()
    _body(f, 360, 400, 590, 630)  # even thick hollow edges are not a separate bar
    locations = {"far_above":(560,200), "below":(560,410), "beside":(750,330), "hud":(30,90)}
    if placement in locations:
        x,y = locations[placement]
        f[y:y+8,x:x+80] = GREEN_BGR
    assert not any(570 < d.center[0] < 650 and 340 < d.center[1] < 430 for d in find_enemies(f))


def test_chat_region_keeps_a_real_health_bar_but_not_sender_text_in_full_or_crop():
    import cv2
    f = _frame()
    cv2.putText(f, "[Squad] player:", (25, 450), cv2.FONT_HERSHEY_SIMPLEX, .5, GREEN_BGR, 1)
    assert find_enemies(f) == []
    assert find_enemies(f[380:500,:400], scale=1, origin=(0,380),frame=(1280,720)) == []
    # A real enemy in the same screen area, with a filled strip, must survive.
    f = _frame()
    f[430:438,25:125] = GREEN_BGR
    assert len(find_enemies(f)) == 1
    assert len(find_enemies(f[380:500,:400], scale=1, origin=(0,380),frame=(1280,720))) == 1


_CANDIDATE_20021 = (
    ("0001", "c62f578ac6f82354c3d38fea04970e236d6c9ce38344476cb55ac3c9673c3320"),
    ("0013", "718183798033c975647a7a81923370f860f366a78d061e4649c07d5e5fe9606a"),
    ("0025", "5fc3db35988afa268dd5e230d3b5c4e321a98bb6a36b497f735bcc041e02ac26"),
    ("0037", "05d89f0fe3635aad1c04e395b37038ebe6d9f18e297c3278458f4cea054bfd3c"),
    ("0049", "b8280a6bde010bdccab609edd74b8034985d20e44b53280f0cf53bc985dd59a2"),
)


def _candidate_frame(candidate, number, digest):
    """Only explicitly reviewed diagnostic native frames; not admitted labels."""
    import hashlib
    from pathlib import Path
    import cv2
    path = Path("data/human/semantic-candidates/20260922T032454-642Z-24328-1") / candidate / f"frame-{number}.png"
    if not path.is_file():
        pytest.skip(f"diagnostic native frame missing: {path}")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    frame = cv2.imread(str(path))
    assert frame is not None and frame.shape == (1440,2560,3)
    return frame


@pytest.mark.corpus
def test_native_candidate20021_partial_target_and_causal_track_correspondence():
    """Observed development replay, not a human target/admission annotation."""
    from dataclasses import replace
    from agent import brain
    from agent.state import State
    from agent.tracker import Tracker
    memory, tracker, selected = brain.Memory(), Tracker(), []
    for i,(number,digest) in enumerate(_CANDIDATE_20021):
        f = _candidate_frame("candidate-20021",number,digest)
        wide = find_enemies(f, scale=2)
        aim = [replace(d,bbox=(d.bbox[0]+800,d.bbox[1]+240,d.bbox[2]+800,d.bbox[3]+240))
               for d in find_enemies(f[240:1200,800:1760],scale=2,origin=(800,240),frame=(2560,1440))]
        # Nearby partial body is observed from the second causal frame onward.
        near = lambda ds: [d for d in ds if 1100 < d.center[0] < 1350 and 550 < d.center[1] < 820]
        if i >= 1:
            assert len(near(wide)) == len(near(aim)) == 1
            assert near(wide)[0].bbox == near(aim)[0].bbox
        t=19.621+i*.1
        ds=tracker.update(aim or wide,t,frame=(2560,1440),clip=(800,240,1760,1200) if aim else None)
        _,target=brain.gate(State(t=t,frame=(2560,1440),detections=ds,coasting=tracker.coasting),memory)
        if i >= 2:
            assert target in near(ds)
            selected.append(target.track)
    assert len(set(selected)) == 1
    assert target.bbox == (1243.,708.,1305.,795.) and target.plate is True


@pytest.mark.corpus
def test_native_squad_chat_removed_while_nearby_luna_survives():
    f = _candidate_frame("candidate-13521","0049","b8f369a9b0dc3fcfdf0df792ef1c87ec3cb8e3d5a1443d7c76d39420876910fc")
    ds=find_enemies(f,scale=2)
    assert any(d.bbox == (1276.,555.,1371.,754.) and d.plate is True for d in ds)
    assert not any(d.bbox[0] < 300 and d.bbox[1] > 800 for d in ds)
    assert find_enemies(f[800:1040,:800],scale=2,origin=(0,800),frame=(2560,1440)) == []


@pytest.mark.corpus
def test_same_native_partial_body_without_its_health_strip_stays_guarded():
    number,digest = _CANDIDATE_20021[-1]
    original = _candidate_frame("candidate-20021",number,digest)
    no_bar = original.copy()
    no_bar[630:685,1140:1340] = 0  # remove only the separate name/health mark
    assert np.array_equal(no_bar[708:795,1243:1305], original[708:795,1243:1305])
    for image,origin in ((no_bar,(0,0)), (no_bar[240:1200,800:1760],(800,240))):
        ds=find_enemies(image,scale=2,origin=origin,frame=(2560,1440))
        assert not any(1200 < d.center[0]+origin[0] < 1350 and
                       690 < d.center[1]+origin[1] < 820 for d in ds)
        assert any(1490 < d.bbox[0]+origin[0] < 1510 for d in ds)  # distant bot preserved


@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("crop", [False, True])
def test_rejected_component_inside_body_bbox_cannot_supply_health_evidence(scale, crop):
    import cv2
    f = _frame()
    f[350:406,560:700] = _hsv_bgr(65,200,200)
    f[352:404,562:698] = 0
    f[373:379,590:625] = _hsv_bgr(55,200,200)  # separately rejected scenery component
    f = cv2.resize(f,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    if crop:
        ds = find_enemies(f[120*scale:600*scale,400*scale:880*scale],scale=scale,
                          origin=(400*scale,120*scale),frame=(1280*scale,720*scale))
    else:
        ds = detect(f,scale=scale,mode="green")
    assert ds == []


@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("crop", [False, True])
def test_supported_body_cannot_transfer_strip_evidence_to_adjacent_junk(scale, crop):
    import cv2
    f = _frame()
    color = _hsv_bgr(65,200,200)
    f[300:420,500:550] = color
    f[304:416,504:546] = 0
    f[260:268,490:555] = color
    f[430:470,560:595] = color  # no horizontal overlap with the health strip
    f[434:466,564:591] = 0
    f = cv2.resize(f,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST)
    if crop:
        ds = find_enemies(f[120*scale:600*scale,400*scale:880*scale],scale=scale,
                          origin=(400*scale,120*scale),frame=(1280*scale,720*scale))
        offset=(400*scale,120*scale,400*scale,120*scale)
    else:
        ds = detect(f,scale=scale,mode="green")
        offset=(0,0,0,0)
    assert len(ds) == 1
    assert np.allclose(np.array(ds[0].bbox)+offset,
                       np.array((500,300,550,420))*scale+1)
