"""Unwired development candidate for white MM:SS over bright scenery.

Keep the existing glyph/rival/colour checks. A 9-pixel opening removes broad
background illumination; its size exceeds the observed thin glyph strokes.
Require unchanged reader and transformed reader to agree whenever both answer.
No temporal fill, expected-time prior, threshold relaxation or decimal fallback.
"""
from __future__ import annotations

import cv2
import numpy as np
from perception import match_timer as M


def white_contrast(box):
    ink = box.min(axis=2)
    background = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    # Existing minimum contrast defines full ink. Large bright fields vanish;
    # no division by local maxima makes a weak stroke bright by itself.
    high = np.clip((ink.astype(np.float32) - background) * (255 / M.MIN_CONTRAST), 0, 255)
    return np.repeat(high.astype(np.uint8)[..., None], 3, axis=2)


def read_box(box, ch=M.CENTRE):
    if box.dtype != np.uint8 or box.shape != (ch.box[3]-ch.box[1], ch.box[2]-ch.box[0], 3):
        raise ValueError('native channel crop required')
    raw = M.read_box(box, ch)
    x0, y0, x1, y1 = ch.sub
    up = M._upright(white_contrast(box)[y0:y1, x0:x1], ch.pivot)
    candidate = M._read_mmss(up, M._ink(up, 'white'), ch)
    if candidate is not None:
        # Transformed values never override original chromatic evidence.
        native_up = M._upright(box[y0:y1, x0:x1], ch.pivot)
        # Only a predominantly white original crop is insufficient evidence;
        # require actual white fill at the parsed timer using original parser
        # placements, checked by its _color routine in the geometry below.
        g = M.GLYPHS[ch.glyphs]
        light = M._ink(up, 'white')
        c = M._best(light, g, [':'], *ch.colon_x, ch.top+ch.colon_drop-3, ch.top+ch.colon_drop+3)
        cl, cr = c.x+M.RING, c.x+g[':'].w-M.RING-1
        m2 = M._best(light,g,M.DIGITS,cl-ch.gap,cl-1,ch.top-3,ch.top+3,anchor='right')
        s1 = M._best(light,g,M.DIGITS,cr+1,cr+ch.gap,ch.top-3,ch.top+3)
        m1 = M._best(light,g,M.DIGITS,m2.x+M.RING-ch.gap,m2.x+M.RING-1,
                     ch.top-3,ch.top+3,anchor='right')
        edge = s1.x+g[s1.char].w-M.RING-1
        s2 = M._best(light,g,M.DIGITS,edge+1,edge+ch.gap,ch.top-3,ch.top+3)
        if M._color(native_up,[m1,m2,c,s1,s2],g) != 'white':
            candidate = None
    if raw is not None and candidate is not None and raw.text != candidate.text:
        return None
    return raw if raw is not None else candidate
