"""The match / round timer on the HUD, read from native 2560x1440 frames, and the frame of each displayed-second change.

Gate 2's alignment anchors (docs/lanes/inverse-dynamics.md, "Gate 2 protocol" and "Gate 2 step 1"). Three channels:
    centre   the live HUD's top-centre timer: MM:SS in white (yellow in its last seconds), or the SS.d countdown in larger
             yellow digits, which "pops" (redrawn up to ~2x and shrinking) at each whole second
    team_a   the replay viewer's team-box clocks (spectator bar, "04:00 / 0.00 M"), smaller white MM:SS
    team_b
A reader returns a `Read` or None, never a guess: every glyph must match its template (masked normalised correlation over
the glyph's box), be as bright as a glyph fill, and beat every close rival where the two differ (interior pixels only).
Anything else (no timer drawn, a menu, a blurred death screen, an overlay across it, a pop that the undone scales do not
read the same way) is None.

    from perception.match_timer import read_frame, second_changes
    reads = [read_frame(frame) for frame in frames]          # {channel: Read | None}
    changes = second_changes([r["centre"] for r in reads])   # [(k, old second, new second)]

Glyph templates: match_timer_glyphs.json (development recordings only; its note says which).
"""
from __future__ import annotations

import base64
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

SHEAR = 0.24                         # the italic slant, removed before matching: x' = x + SHEAR (y - pivot)
RING = 2                             # template padding (the outline ring around a glyph)
MIN_NCC = 0.70                       # masked normalised correlation a glyph must reach
MIN_FILL, MIN_CONTRAST = 170.0, 40.0 # ink level of the glyph's fill, and fill minus its outline ring
MIN_PAIR = 30.0                      # against a rival: its distinguishing pixels must be this much darker than the fill
FILL_TOL = 25.0                      # ... and the winner's own distinguishing pixels within this of the fill
PAIR_WINDOW = 0.25                   # rivals within this NCC of the winner are checked pairwise
MIN_PAIR_PX = 6
ERODE_MIN_H = 30                     # glyphs at least this tall are compared on eroded (interior) pixels
DIGITS = [str(k) for k in range(10)]


@dataclass(frozen=True)
class Channel:
    name: str
    box: tuple                       # native (x0, y0, x1, y1) the channel reads
    sub: tuple                       # the matching region inside box (x0, y0, x1, y1)
    pivot: int                       # shear pivot row, in sub coordinates
    top: int                         # MM:SS digit top row in the upright sub-crop
    colon_drop: int                  # the colon's top below the digit top
    colon_x: tuple                   # the colon template's left edge search range (sub coordinates)
    glyphs: str                      # template set
    gap: int                         # the largest gap searched between neighbouring glyphs
    decimal: bool = False            # whether the SS.d format (and its pop) is read here


CENTRE = Channel("centre", (1140, 0, 1420, 150), (40, 30, 240, 120), 44, 26, 12, (84, 106), "mmss", 7, decimal=True)
TEAM_A = Channel("team_a", (955, 55, 1065, 115), (0, 0, 110, 60), 27, 18, 6, (40, 58), "team", 6)
TEAM_B = Channel("team_b", (1395, 55, 1505, 115), (0, 0, 110, 60), 27, 18, 6, (40, 58), "team", 6)
CHANNELS = (CENTRE, TEAM_A, TEAM_B)
DEC_TOP = 20                         # SS.d digit top row in the centre's upright sub-crop
POP_CENTRE = (138.0, 72.5)           # the SS.d text centre in the centre box, about which the pop scales
POP_SCALES = tuple(round(1.1 + 0.05 * k, 2) for k in range(23))    # 1.10 .. 2.20
POP_MIN_H = 52                       # a yellow blob at least this tall means a pop may be up


class Glyph:
    def __init__(self, fill):
        pad = np.pad(fill.astype(np.uint8), RING)
        ring = cv2.dilate(pad, np.ones((2 * RING + 1, 2 * RING + 1), np.uint8)) - pad
        self.pattern = pad.astype(np.float32)
        self.mask = np.ones_like(pad)               # the whole box: counters and gaps score as background
        self.fillm = pad.astype(bool)
        self.ring = ring.astype(bool)
        self.h, self.w = pad.shape


def _load(path=Path(__file__).with_name("match_timer_glyphs.json")):
    raw = json.loads(path.read_text(encoding="utf-8"))
    sets = {}
    for name, glyphs in raw["sets"].items():
        sets[name] = {}
        for c, g in glyphs.items():
            bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(g["bits"])), np.uint8))
            sets[name][c] = Glyph(bits[:g["h"] * g["w"]].reshape(g["h"], g["w"]))
    return sets


GLYPHS = _load()


@dataclass
class Read:
    text: str
    seconds: float
    fmt: str                         # "mmss" | "decimal" | "decimal_pop"
    color: str                       # "white" | "yellow"
    score: float                     # the weakest glyph's correlation


@dataclass
class _Place:
    char: str
    x: int
    y: int
    score: float
    margin: float
    fill: float
    contrast: float


def _upright(img, pivot):
    m = np.float32([[1, SHEAR, -SHEAR * pivot], [0, 1, 0]])
    return cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR)


def _ink(up, color):
    """White text is matched on min(R, G, B) (sky, stone and skin fall well below the fill there); yellow on
    min(R, G) - B / 2."""
    b, g, r = (up[..., k].astype(np.float32) for k in range(3))
    return np.minimum(np.minimum(r, g), b) if color == "white" else np.minimum(r, g) - b / 2


def _pair(L, a, ga, gb, anchor):
    h, w = min(ga.h, gb.h), min(ga.w, gb.w)
    if anchor == "left":
        fa, fb, win = ga.fillm[:h, :w], gb.fillm[:h, :w], L[a.y:a.y + h, a.x:a.x + w]
    else:
        fa, fb = ga.fillm[:h, ga.w - w:], gb.fillm[:h, gb.w - w:]
        win = L[a.y:a.y + h, a.x + ga.w - w:a.x + ga.w]
    fill = float(L[a.y:a.y + ga.h, a.x:a.x + ga.w][ga.fillm].mean())
    k = np.ones((3, 3), np.uint8)
    ero = lambda m: cv2.erode(m.astype(np.uint8), k).astype(bool)          # noqa: E731
    dil = lambda m: cv2.dilate(m.astype(np.uint8), k).astype(bool)         # noqa: E731
    if ga.h - 2 * RING >= ERODE_MIN_H:                                     # interior pixels: edges jitter by a pixel
        only_a, only_b = ero(fa) & ~dil(fb), ero(fb) & ~dil(fa)
    else:                                     # thin strokes and small counters would vanish: plain fills
        only_a, only_b = fa & ~fb, fb & ~fa
    slack = []
    if only_a.sum() >= MIN_PAIR_PX:
        slack.append(MIN_PAIR + FILL_TOL - (fill - float(win[only_a].mean())))
    if only_b.sum() >= MIN_PAIR_PX:
        slack.append(fill - float(win[only_b].mean()))
    return min(slack) if slack else 0.0


def _best(L, glyphs, chars, x0, x1, y0, y1, anchor="left"):
    """The best char over placements whose left (or right) fill edge is in [x0, x1] and top in [y0, y1]; its margin
    is the smallest pairwise slack against the rivals scoring within PAIR_WINDOW of it."""
    scores = []
    for c in chars:
        g = glyphs[c]
        lx0, lx1 = (x0, x1) if anchor == "left" else (x0 - g.w + 1 + RING, x1 - g.w + 1 + RING)
        lx0, lx1, ya, yb = lx0 - RING, lx1 - RING, y0 - RING, y1 - RING
        if lx0 < 0 or ya < 0 or lx1 + g.w > L.shape[1] or yb + g.h > L.shape[0]:
            continue
        r = cv2.matchTemplate(L[ya:yb + g.h, lx0:lx1 + g.w], g.pattern, cv2.TM_CCOEFF_NORMED, mask=g.mask)
        r = np.nan_to_num(r, nan=-1.0, posinf=-1.0, neginf=-1.0)
        k = np.unravel_index(np.argmax(r), r.shape)
        x, y = lx0 + int(k[1]), ya + int(k[0])
        win = L[y:y + g.h, x:x + g.w]
        scores.append(_Place(c, x, y, float(r[k]), 0.0, float(win[g.fillm].mean()),
                             float(win[g.fillm].mean() - win[g.ring].mean())))
    if not scores:
        return None
    scores.sort(key=lambda p: -p.score)
    top = scores[0]
    rivals = [p for p in scores[1:] if p.score >= top.score - PAIR_WINDOW]
    top.margin = min([_pair(L, top, glyphs[top.char], glyphs[p.char], anchor) for p in rivals], default=255.0)
    return top


def _ok(p):
    return p is not None and p.score >= MIN_NCC and p.fill >= MIN_FILL and p.contrast >= MIN_CONTRAST


def _ok_digit(p):
    return _ok(p) and p.margin >= MIN_PAIR


def _color(up, places, glyphs):
    vals = [up[p.y:p.y + glyphs[p.char].h, p.x:p.x + glyphs[p.char].w][glyphs[p.char].fillm].astype(np.float32)
            .mean(axis=0) for p in places]
    b, g, r = np.mean(vals, axis=0)
    if b >= 170 and g >= 170 and r >= 170:
        return "white"
    if r >= 170 and g >= 140 and b <= 120:
        return "yellow"
    return None


def _read_mmss(up, L, ch):
    G = GLYPHS[ch.glyphs]
    c = _best(L, G, [":"], ch.colon_x[0], ch.colon_x[1], ch.top + ch.colon_drop - 3, ch.top + ch.colon_drop + 3)
    if not _ok(c):
        return None
    cl, cr = c.x + RING, c.x + G[":"].w - RING - 1
    y0, y1, gap = ch.top - 3, ch.top + 3, ch.gap
    m2 = _best(L, G, DIGITS, cl - gap, cl - 1, y0, y1, anchor="right")
    s1 = _best(L, G, DIGITS, cr + 1, cr + gap, y0, y1)
    if not (_ok_digit(m2) and _ok_digit(s1)):
        return None
    m2l, s1r = m2.x + RING, s1.x + G[s1.char].w - RING - 1
    m1 = _best(L, G, DIGITS, m2l - gap, m2l - 1, y0, y1, anchor="right")
    s2 = _best(L, G, DIGITS, s1r + 1, s1r + gap, y0, y1)
    if not (_ok_digit(m1) and _ok_digit(s2)) or int(s1.char) > 5:
        return None
    places = [m1, m2, c, s1, s2]
    col = _color(up, places, G)
    if col is None:
        return None
    text = f"{m1.char}{m2.char}:{s1.char}{s2.char}"
    return Read(text, float(int(text[:2]) * 60 + int(text[3:])), "mmss", col, min(p.score for p in places))


def _read_decimal(up, L):
    G = GLYPHS["decimal"]
    gd = G["."]
    dy = DEC_TOP + (G["0"].h - 2 * RING) - (gd.h - 2 * RING)            # the point sits on the digits' baseline
    d = _best(L, G, ["."], 80, 125, dy - 3, dy + 3)
    if not _ok(d):
        return None
    dl, dr = d.x + RING, d.x + gd.w - RING - 1
    y0, y1 = DEC_TOP - 3, DEC_TOP + 3
    tenth = _best(L, G, DIGITS, dr + 1, dr + 9, y0, y1)
    unit = _best(L, G, DIGITS, dl - 9, dl - 1, y0, y1, anchor="right")
    if not (_ok_digit(tenth) and _ok_digit(unit)):
        return None
    tens = _best(L, G, DIGITS, unit.x + RING - 9, unit.x + RING - 1, y0, y1, anchor="right")
    places = [unit, d, tenth]
    if tens is not None and _ok_digit(tens):
        places = [tens] + places
    elif tens is not None and (tens.score >= 0.4 or tens.fill >= MIN_FILL):
        return None                                                     # something is there, and it does not read
    if _color(up, places, G) != "yellow":
        return None
    text = "".join(p.char for p in places)
    return Read(text, float(text), "decimal", "yellow", min(p.score for p in places))


def _read_sub(sub, ch):
    up = _upright(sub, ch.pivot)
    found = []
    for color in ("white", "yellow"):
        L = _ink(up, color)
        r = _read_mmss(up, L, ch)
        if r is not None and r.color == color:
            found.append(r)
        if ch.decimal:
            r = _read_decimal(up, L)
            if r is not None and r.color == color:
                found.append(r)
    return found[0] if len(found) == 1 else None


def _yellow_tall(box):
    b, g, r = (box[..., k].astype(np.int16) for k in range(3))
    n, _, stats, _ = cv2.connectedComponentsWithStats(((r >= 200) & (g >= 170) & (b <= 110)).astype(np.uint8))
    return any(stats[i, cv2.CC_STAT_HEIGHT] >= POP_MIN_H for i in range(1, n))


def read_box(box, ch=CENTRE):
    """box: the frame's pixels inside ch.box (BGR). The displayed time, or None. On the centre channel, SS.d text
    caught mid-pop is read by undoing the pop's scale about the text centre: one value, read at two adjacent scales at
    least, and no other value at any scale."""
    x0, y0, x1, y1 = ch.sub
    r = _read_sub(box[y0:y1, x0:x1], ch)
    if r is not None or not ch.decimal or not _yellow_tall(box):
        return r
    cx, cy = POP_CENTRE
    got = []
    for s in POP_SCALES:
        m = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])      # output(x) samples input at the popped place
        shrunk = cv2.warpAffine(box, m, (box.shape[1], box.shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        q = _read_sub(shrunk[y0:y1, x0:x1], ch)
        got.append(q if q is not None and q.fmt == "decimal" else None)
    texts = {q.text for q in got if q is not None}
    adjacent = any(a is not None and b is not None and a.text == b.text for a, b in zip(got, got[1:]))
    if len(texts) == 1 and adjacent:
        q = next(q for q in got if q is not None)
        return Read(q.text, q.seconds, "decimal_pop", q.color, q.score)
    return None


def crop(frame, ch=CENTRE):
    x0, y0, x1, y1 = ch.box
    return frame[y0:y1, x0:x1]


def read_frame(frame):
    """{channel name: Read | None} for one native 2560x1440 BGR frame; anything else is refused."""
    if frame.shape[:2] != (1440, 2560):
        raise ValueError(f"the timer reader reads native 2560x1440 frames, not {frame.shape[1]}x{frame.shape[0]}")
    return {ch.name: read_box(crop(frame, ch), ch) for ch in CHANNELS}


def displayed_second(r):
    """The whole second a read displays: MM:SS's value, SS.d's integer part."""
    return None if r is None else int(r.seconds)


def second_changes(reads, confirm=2, settle=36):
    """[(k, old, new)] for one channel's reads: k is the first frame showing a new displayed second. Taken only when
    frame k-1 was read (the old second); the next `confirm` read frames from k show the new second (unread frames
    between them allowed, within `settle`); |new - old| == 1; the old second is not read again within `settle` frames
    after k (the SS.d pop can briefly redraw the previous value); and the new second was not already read in the
    `settle` frames before k (after such a redraw, the true first frame has passed)."""
    out = []
    for k in range(1, len(reads)):
        a, b = displayed_second(reads[k - 1]), displayed_second(reads[k])
        if a is None or b is None or abs(a - b) != 1:
            continue
        known = [v for v in (displayed_second(r) for r in reads[k:k + settle]) if v is not None]
        before = [displayed_second(r) for r in reads[max(0, k - settle):k - 1]]
        if len(known) < confirm or any(v != b for v in known[:confirm]) or a in known or b in before:
            continue
        out.append((k, a, b))
    return out
