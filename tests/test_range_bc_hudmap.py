"""The pad->M&K HUD transform (`policy.range_bc.hudmap`) and its parity test (`hudparity`). Synthetic checks need
numpy (the perception group); the parity run on real stills is marked `corpus`."""
import glob
from pathlib import Path

import numpy as np
import pytest

from policy.range_bc import hudmap

W, H = 2560, 1440


def _px(x, y):
    return int(round(x * W)), int(round(y * H))


def test_slot_columns_three_and_four_swap_exactly():
    f = np.zeros((H, W, 3), np.uint8)
    x3, y = _px(hudmap.SLOT3_CX, .90)
    x4, _ = _px(hudmap.SLOT4_CX, .90)
    f[y, x3], f[y, x4] = (10, 20, 30), (40, 50, 60)
    g = hudmap.pad_to_mk(f)
    assert tuple(g[y, x4]) == (10, 20, 30) and tuple(g[y, x3]) == (40, 50, 60)
    assert tuple(f[y, x3]) == (10, 20, 30)                  # the input is not modified


def test_the_web_count_moves_right_by_the_measured_shift():
    f = np.zeros((H, W, 3), np.uint8)
    y = int(1340)
    f[y, 440] = (200, 200, 200)                             # the pad digit's right edge sits at x 444.7
    g = hudmap.pad_to_mk(f)
    assert tuple(g[y, 440 + 241]) == (200, 200, 200)


def test_a_light_badge_disc_is_inverted_and_ringed():
    f = np.full((H, W, 3), 60, np.uint8)
    cx, cy = _px(hudmap.BADGE_SLOTS[0], (hudmap.BADGE_Y[0] + hudmap.BADGE_Y[1]) / 2)
    yy, xx = np.ogrid[:H, :W]
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= 16 ** 2
    f[disc] = 235
    f[cy - 4:cy + 4, cx - 2:cx + 2] = 30                    # the dark digit
    g = hudmap.pad_to_mk(f)
    assert g[cy, cx].min() > 200                            # the digit is now light
    assert g[cy + 8, cx].max() < 40                         # the disc is now dark
    assert g[cy, cx + 16].min() == hudmap.RING or g[cy, cx + 15].min() == hudmap.RING
    assert tuple(g[cy, cx + 40]) == (60, 60, 60)            # outside the disc: untouched


def test_frames_without_a_disc_are_left_alone_and_bad_frames_refused():
    f = np.full((H, W, 3), 90, np.uint8)
    assert np.array_equal(hudmap.pad_to_mk(f), f)           # uniform: swaps and moves change nothing, no disc
    with pytest.raises(ValueError):
        hudmap.pad_to_mk(np.zeros((1600, 2560, 3), np.uint8))
    with pytest.raises(ValueError):
        hudmap.pad_to_mk(np.zeros((H, W), np.uint8))


def test_hud_stream_shape_matches_the_cache():
    from policy.range_bc import cache
    out = hudmap.hud_stream(np.full((H, W, 3), 128, np.uint8))
    assert out.shape == cache.HUD and out[:50, :200].min() == 128 and out[50:, 40:].max() == 0


PAD = sorted(glob.glob("data/l1/galacta-pilot-*/*.jpg"))


@pytest.mark.corpus
def test_parity_regressions_on_the_pilot_stills_and_james_frames():
    """P1 and P3 passed and P2 had no contradiction on 2026-09-23 (parity-1). Whether P2 passes is the lead's decision
    (its slot-4 losses match the M&K reader's own abstention); this pins only what held."""
    import cv2
    from policy.range_bc import hudparity
    mk_dir = Path("data/diagnostics/hud-parity-mk-frames")
    mk = sorted(glob.glob(str(mk_dir / "*.png")))
    if not PAD or not mk:
        pytest.skip("needs the pilot stills and James's decoded M&K frames (local to the machine that ran parity-1)")
    r = hudparity.parity([cv2.imread(p) for p in PAD[::4]], [cv2.imread(p) for p in mk])
    assert r["P1"]["pass"] and r["P3"]["pass"]
    assert all(q["contradict"] == 0 for q in r["P2"]["quantities"].values())
