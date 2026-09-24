"""Pad-HUD -> M&K-HUD transform for the live HUD stream (lead decision on the HUD layout gap, 2026-09-23).

Every training frame shows James's mouse-and-keyboard HUD; the live agent plays on the pad, whose HUD differs in three
places the HUD stream sees. A fixed geometric transform, applied to the native live frame before the HUD stream is
cropped, maps the pad layout onto James's M&K layout:

1. Ability slots 3 and 4 swap. Measured with `perception.hud.identify_slot` / `slot_mapping` (the repo's icon
   templates): on the pad stills (data/l1/galacta-pilot-*, 603 frames) slot 3 is Get Over Here! and slot 4 the
   Amazing Combo fist ("uppercut"); on James's M&K frames (051828, 171533; 47 frames) slot 3 is the fist and slot 4
   Get Over Here!. His HUD labels them E and F (his binding, not the kit's). The two 96 px slot columns are exchanged.
2. The web count moves from the pad's left weapon slot to the M&K right one ("mirror the webs box": the slots swap
   sides; the glyphs are not flipped). Measured digit right edges: pad x 444.7, M&K x 685.5, same rows (1323-1353)
   at 2560x1440; the shift is +241 px, no vertical shift.
3. Charge badges invert: the pad draws a dark digit in a light disc, M&K a light digit and ring on a dark centre.
   Inside each detected light disc the pixels are inverted and a light ring is drawn on the disc boundary.

All constants are fractions of the frame (measured at 2560x1440; `MEASURED` records the numbers). The transform is
fixed: changing a constant is a new pre-registration. Whether it is good enough is the parity test (`hudparity`),
whose failure makes the no-HUD arm the pilot candidate (pre-registered). Known and not measured by that test: the
swapped and moved regions carry their scene background, so seams appear at their edges (visible on the transform
contact sheet); reader parity is blind to them.
Needs numpy and cv2 (cv2 is already the live path's dependency).
"""

# Ability row (cache.ABILITY_ROW, y span) and the swapped slot columns.
ROW_Y = (0.844444, 0.950694)
SLOT3_CX, SLOT4_CX = 0.8348, 0.8723          # perception/hud.py SLOT_CX, positions 3 and 4 on both layouts
SLOT_HALF = (SLOT4_CX - SLOT3_CX) / 2        # 0.01875 = 48 px at 2560: the columns tile exactly
# Web count: source on the pad, destination on M&K (x0, x1) and the rows, as fractions.
WEBS_SHIFT = 241 / 2560
WEBS_DST_X = (600 / 2560, 692 / 2560)        # the M&K HUD crop's webs box up to 6 px right of the digit
WEBS_Y = (1280 / 1440, 1370 / 1440)
# Badges: perception/hud.py BADGE_DX, BADGE_Y around each slot centre that can carry charges.
BADGE_DX, BADGE_Y = 0.0105, (0.849, 0.879)
BADGE_SLOTS = (0.7950, SLOT3_CX, SLOT4_CX)   # swing, and both swapped positions
DISC_MIN = 170          # grey level of the pad's light disc
DISC_MIN_AREA = 0.25    # of the badge box: smaller bright blobs are not a disc
RING = 230              # grey level of the drawn M&K ring
RING_PX = 2
MEASURED = {"pad_slots": {"3": "get_over_here", "4": "uppercut"}, "mk_slots": {"3": "uppercut", "4": "get_over_here"},
            "pad_digit_right_px": 444.7, "mk_digit_right_px": 685.5, "digit_rows_px": [1323.2, 1353.2],
            "pad_frames": 603, "mk_frames": 47, "date": "2026-09-23"}


BAND_Y = (min(ROW_Y[0], BADGE_Y[0], WEBS_Y[0]), max(ROW_Y[1], BADGE_Y[1], WEBS_Y[1]))   # every region touched


def _px(frac, size):
    return int(round(frac * size))


def _swap_slots(out, band, top, w, h):
    y0, y1 = _px(ROW_Y[0], h) - top, _px(ROW_Y[1], h) - top
    a0, a1 = _px(SLOT3_CX - SLOT_HALF, w), _px(SLOT3_CX + SLOT_HALF, w)
    b0, b1 = _px(SLOT4_CX - SLOT_HALF, w), _px(SLOT4_CX + SLOT_HALF, w)
    n = min(a1 - a0, b1 - b0)
    out[y0:y1, a0:a0 + n] = band[y0:y1, b0:b0 + n]
    out[y0:y1, b0:b0 + n] = band[y0:y1, a0:a0 + n]


def _move_webs(out, band, top, w, h):
    y0, y1 = _px(WEBS_Y[0], h) - top, _px(WEBS_Y[1], h) - top
    d0, d1 = _px(WEBS_DST_X[0], w), _px(WEBS_DST_X[1], w)
    s0 = d0 - _px(WEBS_SHIFT, w)
    out[y0:y1, d0:d1] = band[y0:y1, s0:s0 + (d1 - d0)]


def _invert_badges(out, top, w, h):
    import cv2
    import numpy as np
    y0, y1 = _px(BADGE_Y[0], h) - top, _px(BADGE_Y[1], h) - top
    for cx in BADGE_SLOTS:
        x0, x1 = _px(cx - BADGE_DX, w), _px(cx + BADGE_DX, w)
        box = out[y0:y1, x0:x1]
        bright = (box.min(axis=2) >= DISC_MIN).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=4)
        if n < 2:
            continue
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[k, cv2.CC_STAT_AREA] < DISC_MIN_AREA * bright.size:
            continue                                  # no light disc: nothing to invert
        disc = (labels == k).astype(np.uint8)
        # holes (the digit): background not reachable from the border
        outside = np.pad(1 - disc, 1, constant_values=1).astype(np.uint8)
        mask = np.zeros((outside.shape[0] + 2, outside.shape[1] + 2), np.uint8)
        cv2.floodFill(outside, mask, (0, 0), 2, flags=4)
        disc = (outside[1:-1, 1:-1] != 2)
        inner = cv2.erode(disc.astype(np.uint8), np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], np.uint8),
                          iterations=RING_PX, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
        ring = disc & ~inner
        box[inner] = 255 - box[inner]
        box[ring] = RING


def pad_to_mk(frame, *, inplace=False):
    """A native pad-HUD frame (H x W x 3 uint8, any channel order) with its HUD in James's M&K layout.

    Only the bottom HUD band is copied as the source (review L2); `inplace=True` rewrites the caller's frame (the live
    loop owns its capture buffer), otherwise a full copy is returned and the input is untouched."""
    import numpy as np
    src = np.asarray(frame)
    if src.ndim != 3 or src.shape[2] != 3 or src.dtype != np.uint8:
        raise ValueError("pad_to_mk takes an H x W x 3 uint8 frame")
    h, w = src.shape[:2]
    if w * 9 != h * 16:
        raise ValueError("pad_to_mk takes a 16:9 frame")
    top, bottom = _px(BAND_Y[0], h), _px(BAND_Y[1], h)
    band = src[top:bottom].copy()
    out = src if inplace else src.copy()
    view = out[top:bottom]
    _swap_slots(view, band, top, w, h)
    _move_webs(view, band, top, w, h)
    _invert_badges(view, top, w, h)
    return out


def live_streams(frame, *, pad_hud=True):
    """The three model streams from one native live frame, as the cache builds them from training frames (review L1):
    the pad->M&K transform is applied ONCE to the native frame, so the global stream (which also shows the HUD at 1/10)
    and the HUD stream both see the M&K layout; the crosshair crop is central and unaffected. Returns
    (global 144x256x3, crop 128x128x3, hud 80x200x3) uint8 in the frame's channel order (RGB for the model).
    `frame` is transformed in place: pass a buffer the caller owns."""
    import cv2
    import numpy as np
    from . import cache
    if pad_hud:
        pad_to_mk(frame, inplace=True)
    h, w = frame.shape[:2]
    g = cv2.resize(frame, (cache.GLOBAL[1], cache.GLOBAL[0]), interpolation=cv2.INTER_AREA)
    x0, y0 = (w - cache.CROP_NATIVE) // 2, (h - cache.CROP_NATIVE) // 2
    c = cv2.resize(np.ascontiguousarray(frame[y0:y0 + cache.CROP_NATIVE, x0:x0 + cache.CROP_NATIVE]),
                   (cache.CROP[1], cache.CROP[0]), interpolation=cv2.INTER_AREA)
    return g, c, hud_stream(frame)


def hud_stream(frame_rgb, *, subsampled=False):
    """The 80x200 RGB HUD stream from a native frame in the M&K layout, as the cache's ffmpeg graph builds it:
    crop sizes and offsets truncated to ints (ffmpeg `crop`); the cache converts to RGB before cropping, so offsets
    are not floored to even (`subsampled=True` reproduces a crop on YUV); area downscale (cv2 INTER_AREA against
    ffmpeg `flags=area+accurate_rnd+bitexact`: their equality is part of the frame-parity check)."""
    import cv2
    import numpy as np
    from . import cache
    h, w = frame_rgb.shape[:2]

    def crop(box, size):
        x, y, bw, bh = (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
        if subsampled:
            x, y = x - x % 2, y - y % 2
        return cv2.resize(np.ascontiguousarray(frame_rgb[y:y + bh, x:x + bw]), size, interpolation=cv2.INTER_AREA)
    out = np.zeros(cache.HUD, dtype=np.uint8)
    out[:50, :200] = crop((cache.ABILITY_ROW[0], cache.ABILITY_ROW[1], cache.ABILITY_ROW[2], cache.ABILITY_ROW[3]),
                          (200, 50))
    out[50:80, :40] = crop(cache.WEBS_BOX_MK, (40, 30))
    return out
