"""The player guard is a place on the screen where the hero is drawn, measured (VUH-1355).

Evidence: docs/evidence/player-zone-20260923. The old zone was applied in the passed image's own fractions, so on the
960 px aim crop it sat on the crosshair: it dropped the bot James was webbing and kept junk drawn round the hero's head.
The zone is now (.27, .39, .47, .90) of the whole frame in both views. Synthetic checks run everywhere
(`uv run --group perception pytest`); the native fixtures from recordings under data/l1 are hash-pinned and marked `corpus`.
The take's own demonstrated drops are pinned by docs/evidence/player-zone-20260923/rises.py, which needs the original video.
"""
import hashlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from perception.outline import find_enemies

GREEN_BGR = (83, 199, 92)            # the game's own Enemy Color swatch
AIM = (800, 240, 1760, 1200)         # agent.loop.aim_window((2560, 1440))


def _frame():
    return np.zeros((1440, 2560, 3), np.uint8)


def _hollow(f, x1, y1, x2, y2, t=6):
    f[y1:y2, x1:x2] = GREEN_BGR
    f[y1 + t:y2 - t, x1 + t:x2 - t] = 0


def _views(f):
    """The live loop's two calls (agent.loop.default_perception): the whole frame, and the aim crop with where it sits."""
    x0, y0, x1, y1 = AIM
    aim = [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
           for d in find_enemies(f[y0:y1, x0:x1], scale=2.0, origin=(x0, y0), frame=(2560, 1440))]
    return {"wide": find_enemies(f, scale=2.0), "aim": aim}


def _at(ds, x1, y1, x2, y2):
    return [d for d in ds if x1 <= d.center[0] <= x2 and y1 <= d.center[1] <= y2]


def test_a_small_body_at_the_crosshair_survives_in_both_views():
    """The demonstrated drop: a partly seen bot at the crosshair, under the 60 px (720p) height rule. The hero is drawn left
    of the crosshair (his box holds it in 4.8% of 1,373 native frames), so the guard must not cover it in either view."""
    f = _frame()
    _hollow(f, 1250, 670, 1310, 770)                 # 100 px tall at native, centred on the crosshair
    for view, ds in _views(f).items():
        assert len(_at(ds, 1240, 660, 1320, 780)) == 1, view


def test_small_junk_where_the_hero_is_drawn_is_dropped_in_both_views():
    """Where tagrun0 000422's effect strokes were drawn round his head: the aim crop kept them under the old rule."""
    f = _frame()
    _hollow(f, 884, 619, 939, 676)
    for view, ds in _views(f).items():
        assert _at(ds, 870, 600, 950, 690) == [], view


def test_a_close_bot_where_the_hero_is_drawn_survives():
    """The height rule is the point of the guard: a bot at point blank stands beside or behind him."""
    f = _frame()
    _hollow(f, 900, 600, 1000, 880)                  # 280 px tall at native
    for view, ds in _views(f).items():
        assert len(_at(ds, 890, 590, 1010, 890)) == 1, view


@pytest.mark.parametrize("cx", [880, 1060, 1280, 1500, 1680])
@pytest.mark.parametrize("cy", [320, 520, 720, 920, 1120])
def test_the_player_zone_is_the_same_place_in_both_views(cx, cy):
    """A small mark wholly inside the aim crop is kept or dropped alike by the whole-frame call and the crop call."""
    f = _frame()
    _hollow(f, cx - 20, cy - 30, cx + 20, cy + 30)
    v = _views(f)
    assert len(v["wide"]) == len(v["aim"])


def test_an_origin_without_its_frame_is_refused():
    """With `origin` but no `frame` the zone fractions pass 1 and every screen zone switches off: on tagrun0 000422 the head-stroke
    junk came back as an enemy box (VUH-1355 review, F3). It raises instead, and so does an image that does not fit its frame."""
    from perception.outline import find_green
    crop = np.zeros((960, 960, 3), np.uint8)
    with pytest.raises(ValueError):
        find_enemies(crop, scale=2.0, origin=(800, 240))
    with pytest.raises(ValueError):
        find_green(crop, 2.0, origin=(800, 240))
    with pytest.raises(ValueError):
        find_enemies(crop, scale=2.0, origin=(1700, 240), frame=(2560, 1440))      # runs off the frame's right edge
    find_enemies(crop, scale=2.0, origin=(800, 240), frame=(2560, 1440))           # the aim crop, as agent.loop passes it
    find_enemies(crop, scale=2.0, origin=(0, 0), frame=(2560, 1440))               # a crop at the frame's top-left corner


def test_a_whole_frame_scores_the_same_with_or_without_its_frame():
    f = _frame()
    _hollow(f, 884, 619, 939, 676)                   # junk where the hero is drawn
    _hollow(f, 1250, 670, 1310, 770)                 # a small body at the crosshair
    assert find_enemies(f, scale=2.0) == find_enemies(f, scale=2.0, origin=(0, 0), frame=(2560, 1440))


def _fixture(rel):
    """A native recording under data/, in this checkout or the PC runtime checkout; skipped when absent."""
    path = next((root / rel for root in (Path("."), Path("C:/rivals-agent")) if (root / rel).is_file()), None)
    if path is None:
        pytest.skip(f"native fixture missing: {rel}")
    return path


def _pinned(rel, digest):
    import cv2
    path = _fixture(rel)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    return cv2.imread(str(path))


_JUNK = {
    # effect strokes drawn round his head, 57 px: native (884, 619)-(939, 676)
    "data/l1/tagrun0/000422.jpg": ("a9853a9f2f187eab615497f44e89152616d2fa99f0713e4ce62bb10e21562a7d", (874, 609, 949, 686)),
    # the lime spawn door's glass seen between his hand and hip, 47 px: native (780, 1009)-(823, 1056)
    "data/l1/plaza30/000184.jpg": ("7b7a5815665c637fbb28fcc741ce0e4219697080c5308e798e39040047ac23e2", (770, 999, 833, 1066)),
}


@pytest.mark.corpus
@pytest.mark.parametrize("name", sorted(_JUNK))
def test_native_junk_round_the_hero_is_dropped(name):
    """The only two non-enemy marks among 569 small marks next to the hero in 1,373 native frames (evidence README)."""
    digest, region = _JUNK[name]
    for view, ds in _views(_pinned(name, digest)).items():
        assert _at(ds, *region) == [], view


@pytest.mark.corpus
def test_native_crop_passed_without_its_frame_raises_rather_than_boxing_junk():
    digest, _ = _JUNK["data/l1/tagrun0/000422.jpg"]
    f = _pinned("data/l1/tagrun0/000422.jpg", digest)
    with pytest.raises(ValueError):
        find_enemies(f[240:1200, 800:1760], scale=2.0, origin=(800, 240))


_PAIRS = {
    # two Galacta bots on the lane 80 px apart (native), both inside the aim crop
    "data/l1/plaza30/000021.jpg": ("d1d12da7a9cbb4cb18157869509a97e49e67da446a64d6e9e5f254f7c0e261e2",
                                   ((1239, 1129, 1269, 1162), (1349, 1131, 1380, 1165)), ("wide", "aim")),
    # the closest two separate bots in tagrun0 and plaza30: 78 px apart, above the aim crop
    "data/l1/plaza30/000065.jpg": ("b13d723d3c384c77c2928265b096d2d547aba55513005e14b6ec5e5a01d384e7",
                                   ((1918, 153, 1987, 206), (2065, 183, 2154, 245)), ("wide",)),
    # two far Luna bots 32 px apart on the 2026-09-23 calibration take, inside the aim crop (review F4)
    "data/hud/calib-20260923/frames5/0315.jpg": ("817b19380e820bbaffd98f92a21f9130defed826d10a24c7646ba041043ecd84",
                                                 ((1636, 669, 1658, 719), (1690, 664, 1707, 707)), ("wide", "aim")),
}


@pytest.mark.corpus
@pytest.mark.parametrize("name", sorted(_PAIRS))
def test_native_two_adjacent_bots_stay_two_boxes(name):
    """Pieces of one close bot are joined by the tracker, never by fusing boxes: two bots side by side must come back as two, down to
    32 px apart when their marks do not touch. Every other adjacent pair the finder returns on tagrun0 and plaza30 is one close bot in
    pieces (evidence README)."""
    digest, bots, views = _PAIRS[name]
    found = _views(_pinned(name, digest))
    for view in views:
        for bot in bots:
            assert len(_at(found[view], *bot)) == 1, (view, bot)
        assert not any(d.bbox[0] <= bots[0][2] and bots[1][0] <= d.bbox[2] for d in found[view]), view   # no box spans both


@pytest.mark.corpus
@pytest.mark.xfail(strict=True, reason="residual (VUH-1355 review F4): two Luna bots whose name plates touch close into ONE component, "
                                       "a flat 276x70 box centred on the floor between them; no splitting rule exists or is proposed")
def test_native_bots_with_touching_plates_come_back_as_two():
    """frames5/0305: the plates 'LUNA SNOW-Easy' touch, so closing joins both plates and both bodies into one component (1185, 651,
    1461, 721). HEAD's aim-crop zone dropped it; this change keeps it at the crosshair. Pinned as a known fusion: if the finder ever
    returns the two bodies apart, this XPASSes and must be promoted to a control."""
    f = _pinned("data/hud/calib-20260923/frames5/0305.jpg", "49ade314ae4b6a7d1cc7e6cb54e6a926999b94dbbdb140e5bde8e1c87bce0449")
    for view, ds in _views(f).items():
        assert len(_at(ds, 1240, 675, 1275, 735)) == 1, view        # the left Luna's body
        assert len(_at(ds, 1370, 675, 1405, 735)) == 1, view        # the right Luna's body
