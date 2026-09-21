"""Classical enemy finder: locate hostiles by the game's own red nameplate, no ML.

Usage: uv run --no-project --with opencv-python --with numpy \
         python perception/outline.py <image> [annotated-out.jpg]

Why this exists: the open-vocabulary auto-labeller is about half wrong on these
frames -- it boxes pillars, fire and foliage as readily as bots -- and that
ceiling caps the fine-tuned detector. The game already marks every hostile for
the player: a red health bar with the bot's name above its head. That mark is
cheap and unambiguous to find in colour space.

Spider-Man's own suit is the largest red object in most frames. Aspect ratio removes
the bulk of it -- the suit is *tall* (0.4-0.9), a nameplate is a wide thin bar (aspect
7-10, ~10 px high at 720p) -- but not his belt, which is genuinely a wide thin bright-red
bar. Player exclusion therefore needs the second test in SUIT_ABOVE_MAX below: what sits
above the bar. Do not assume shape alone keeps the player out; it does not.

Two paths: the green one (Accessibility > Custom Colors > Enemy Color = Green, which
L4 has set) and the original red-nameplate one, kept because every frame recorded so
far predates the setting. `detect(..., mode="auto")` prefers green and falls back.

Returns agent.state.Detection(cls=ENEMY) boxes. Checks live in tests/test_outline.py;
run them with `uv run --group perception pytest`.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.state import ENEMY, Detection  # noqa: E402

# Red in HSV wraps hue 0. Thresholds measured, not guessed, off a known nameplate and
# its two competitors in the same frame (trial1/000094):
#   nameplate    H~174  S 111-151  V~229 (BGR 105,102,229 -- a bright red)
#   Spider-Man   H~150  S~189      V~200 (BGR  91, 75,148 -- a *darker* red)
#   pink masonry H~  8  S~ 48      V~178 (the map is full of this)
# Brightness separates the bar from the player's suit; saturation drops the masonry.
# A first attempt at S>120,V>110 alone boxed half the architecture.
# HUE_LO is deliberately tight. Red wraps hue 0, so the band is two-sided, but a real
# nameplate sits at hue ~174 while the warm-lit tan railings and ledges that produced
# most of the false boxes measure hue 7-8, S~100, V~200-216 -- right at the old
# HUE_LO=8 edge. Pulling it to 4 cut detections over 531 frames from 154 to 55 (-64%)
# and the verified LUNA SNOW nameplate is still found.
HUE_LO, HUE_HI, SAT_MIN, VAL_MIN = 4, 168, 100, 195
# A nameplate bar, measured at 1280x720: 8-10 px tall, 80-105 px wide. Profiling the
# components found across 40 bot-bearing frames splits cleanly in two: real nameplates
# at w 80-105 h 8-10, and a tail of w 20-40 h 3-5 slivers, which are specular highlights
# on Spider-Man's own suit. The height floor is what separates them; it also serves as
# the player-exclusion rule, since the player is never drawn a nameplate.
BAR_MIN_ASPECT, BAR_MIN_W, BAR_MAX_W, BAR_MIN_H, BAR_MAX_H = 4.0, 35, 300, 6, 22
# The GREEN mark is the health bar *and* the name text as one component -- 53 px tall
# at native, where the red nameplate alone was 16-20. Measured on tagrun0; without
# this the whole plate failed the bar test, fell through to the outline branch and
# was reported as a second enemy above every visible one.
GREEN_BAR_MAX_H = 30
# A mark this much wider than tall is a plate, never a body.
FLAT_ASPECT = 3.0
# The body hangs under the bar, offset by a gap that scales with the bar (both shrink
# with distance). Ratios to bar width, from 152 bars matched against a labelled box
# underneath: gap p25/median/p75 0.31/0.48/0.63, body height 0.57/1.62/2.33, body width
# 0.48/0.96/1.37. The spread is wide because the reference labels are themselves noisy,
# so these sit near the low end of the measured range, where the boxes visibly land on
# the character. This geometry is the weakest part of the file -- see the README.
BODY_W, BODY_H, BODY_GAP = 0.85, 0.95, 0.42
FRAME_H = 720.0  # size the pixel thresholds above were measured at
# Player exclusion. Spider-Man's belt and suit highlights are wide thin bright-red bars
# of almost exactly nameplate geometry, so neither colour nor shape separates them --
# this boxed the player himself and the ground beside him (docs/evidence/l2/
# l6-outline-false-positives.png). What does separate them is what sits *above* the bar:
# a nameplate floats in open space, a belt has the red-and-blue torso over it. Measured
# over 266 bars in run1, the fraction of saturated suit-coloured pixels in the strip
# directly above splits cleanly -- real nameplates 0.000, suit bars 0.94-0.98 (all of
# them at the player's own screen position), p75 of all bars 0.076.
# ponytail: keyed to Spider-Man's red+blue; a red-suited *enemy* would be excluded too.
# Revisit if the agent ever plays another hero, or once the green enemy outline is on.
SUIT_ABOVE_MAX = 0.30
SUIT_STRIP = 3  # strip height above the bar, in bar heights

# --- green path: Accessibility > Custom Colors > Enemy Color = Green (set by L4) ---
# Sampled from the game's own swatch in docs/evidence/l4/settings-enemy-color-green.jpg:
# BGR (92,199,83) = HSV H62 S149 V199. That lands in the emptiest part of the range's
# palette: over 531 run1 frames (recorded *before* the setting, so this is pure
# background) the band below holds 0.021% of pixels and 78 components >= 40 px in
# total -- about 0.15 per frame, largest 399 px. The range's bright green door and its
# green cross are NOT in this band; they are an emerald green at hue 75-79.
class Band(NamedTuple):
    """An enemy-colour band in HSV. One constant to change if L4 picks another swatch."""
    hue_lo: int
    hue_hi: int
    sat_min: int
    val_min: int


# Accessibility > Custom Colors > Enemy Color = Green. The menu swatch is #53C75C but
# it renders muted in game, about #40AF58 = OpenCV H67 S~160 V~175, so the band is
# centred on 67 rather than on the menu value.
GREEN = Band(54, 70, 90, 120)
# The game's default enemy colour, for VOD footage where the streamer never changed it.
# Hue wraps 0 for red, so hue_lo > hue_hi means "outside the gap" -- see find_green.
# Values from the range's own default-red enemy plate: H~174, S 111-151, V~229.
RED = Band(168, 6, 90, 120)
# An enemy marker is either a thin closed contour around the body or a recoloured
# health bar. Neither is a filled region, so a solid patch is scenery: a signboard, a
# lit panel, foliage in sun. Background components already sit at fill p50 0.34 / p99
# 0.78, so fill alone is weak -- it is the size floor that does most of the work.
GREEN_FILL_MAX = 0.80
GREEN_MIN_H = 14   # px at 720p; below this a body outline is not resolvable anyway
GREEN_MIN_AREA = 60
# The outline is a 1-2 px contour that the body's own shape breaks into arcs -- a
# shoulder, an arm, a leg each come back separately, and the first attempt returned
# eight boxes for one Galacta bot. Close hard enough to rejoin the arcs of one body.
# Too large merges two adjacent enemies, which is the failure to watch for.
GREEN_CLOSE = 14   # px at 720p
GREEN_MERGE_GAP = 12  # px at 720p; boxes closer than this are arcs of one body
BAR_ABOVE = 0.8  # a nameplate floats up to this share of the body height above its top
# HUD elements that are green in this band and are not enemies, as fractions of the
# frame: the fps/ping overlay is green text, and the player's own HP bar has green
# segments. Same idea as autolabel's DEAD_ZONES, kept here because outline.py is used
# on its own by the aim path.
PLAYER_ZONE = (0.28, 0.33, 0.64, 1.00)  # where the third-person hero is drawn
PLAYER_ZONE_MIN_H = 60  # px at 720p; above this it is a close enemy, not junk
GREEN_DEAD_ZONES = [
    (0.00, 0.88, 1.00, 1.00),  # bottom HUD strip: own HP bar, ability row
    (0.86, 0.06, 1.00, 0.32),  # top-right fps / ping / packet-loss readout, all green text
    (0.00, 0.00, 0.26, 0.20),  # top-left practice-range key hints
]


# The kill feed's first row, above that readout: the victim's name is drawn in enemy green, one text line at a fixed place (every one of
# 18 marks on loop30a and postfreeze30: y 59-75 native, 12-16 px tall, ending at x 2416-2433). It became a name bar with a projected body,
# the brain's target for 6 s of postfreeze30. A mark is dropped only if it lies WHOLLY inside this band: a real bot's name bar at the
# top-right is taller or touches the top edge (tagrun0 70, 206, 228, tagrun1 342), and survives. Fractions of the frame.
KILL_FEED = (0.86, 0.034, 0.96, 0.058)

# The spawn room's lime glass door passes the band at its low edge: from inside, 61% of its masked pixels are at hue 54 and 89% at 54-56;
# from the plaza side (lit differently) its boxes' median hue is 54-58 (p50 55). Bots centre on 64-65. A component whose median hue is
# under this is dropped. Raising the band's lower bound instead cuts the bots' edge pixels too, splitting outlines into pieces and losing
# a ground-truth enemy; this keeps every pixel for connectivity and judges the component. Measured (docs/lanes/l3-detector.md): at 58 the
# door's boxes on stall30's plaza side 41 -> 13 and postfreeze30's 66 -> 3, bot boxes 100 px+ on three runs 554 -> 553, ground truth
# count P 0.931 / R 0.859 as at 56.
GREEN_MIN_MEDIAN_HUE = 58


def find_bars(frame_bgr, scale=None):
    """Red horizontal bars: (x, y, w, h) per nameplate, largest first.

    `scale` is how large this frame's pixels are relative to the 1280x720 the size
    thresholds were measured at -- 1.0 for a 720p frame, 2.0 for anything cut from a
    2560x1440 capture. It cannot be inferred from a *crop*: a 960 px square cut out of
    a native 1440p capture is 960 tall but its nameplates are 2.0x, not 1.33x. So
    callers working on crops must pass it; left None it is inferred from frame height,
    which is right only for a full frame.
    """
    s = (frame_bgr.shape[0] / FRAME_H) if scale is None else scale
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    red = ((H <= HUE_LO) | (H >= HUE_HI))
    mask = (red & (S > SAT_MIN) & (V > VAL_MIN)).astype(np.uint8)
    # red or blue, dimmer floor: the player's suit in shadow still counts as suit
    suit = (red | ((H >= 100) & (H <= 130))) & (S > 120) & (V > 60)
    # close small gaps: the bar is broken up by the name text drawn over it
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1, max(3, int(9 * s))), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    bars = []
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if not (w / max(h, 1) >= BAR_MIN_ASPECT and BAR_MIN_W * s <= w <= BAR_MAX_W * s
                and BAR_MIN_H * s <= h <= BAR_MAX_H * s):
            continue
        strip = suit[max(0, y - SUIT_STRIP * h):y, x:x + w]
        if strip.size and strip.mean() > SUIT_ABOVE_MAX:
            continue  # the player's own suit, not a nameplate
        bars.append((int(x), int(y), int(w), int(h)))
    return sorted(bars, key=lambda b: -b[2])


def find_green(frame_bgr, scale=None, band=GREEN, origin=(0, 0), frame=None):
    """Enemy marks in the game's green: (x, y, w, h, kind), kind in {'outline', 'bar'}, in the pixels of the image passed in.

    `origin` and `frame` say where that image sits in the whole frame: the (x, y) of its top-left corner and the frame's (w, h). The HUD
    and kill-feed zones are places on the screen, so an aim crop must pass them, or the zones land on the scene inside the crop (on
    postfreeze30 that removed 32 aim-crop boxes in 27 of 273 frames, 16 of them 120 px or taller). A whole frame needs neither.

    `Enemy Color = Green` recolours the enemy marks. Whether that is a contour around
    the body, a health bar, or both is a question for the first recording made with the
    setting on, so both shapes are accepted and the kind is reported.

    An outline's bounding box *is* the silhouette, so unlike the red path this needs no
    bar-to-body geometry -- the weakest part of that path disappears.
    """
    s = (frame_bgr.shape[0] / FRAME_H) if scale is None else scale
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    # cv2.inRange, not numpy comparisons: the numpy form casts three full-size planes to
    # int64 first, which on the PC cost more than everything else in the function put
    # together (960 px crop 11.1 ms -> see the lane doc). This runs in one pass, uint8.
    lo = (band.hue_lo, band.sat_min + 1, band.val_min + 1)
    if band.hue_lo <= band.hue_hi:
        mask = cv2.inRange(hsv, lo, (band.hue_hi, 255, 255))
    else:  # wraps hue 0 (red): two ranges, OR'd
        mask = cv2.inRange(hsv, lo, (179, 255, 255)) | cv2.inRange(
            hsv, (0, band.sat_min + 1, band.val_min + 1), (band.hue_hi, 255, 255))
    # a contour drawn 1-2 px wide breaks into arcs over a body; rejoin them before
    # components are taken, or one bot comes back as eight boxes
    k = max(3, int(GREEN_CLOSE * s))
    raw = mask if band is GREEN else None           # the band's own pixels, before closing: the hue test below reads only these
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    ih, iw = frame_bgr.shape[:2]
    ox, oy = origin
    fw, fh = frame if frame is not None else (iw, ih)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < GREEN_MIN_AREA * s * s:
            continue
        if raw is not None:                             # a component whose own pixels sit at the band's low edge is scenery (the door)
            hues = hsv[y:y + h, x:x + w, 0][(labels[y:y + h, x:x + w] == i) & (raw[y:y + h, x:x + w] > 0)]
            if hues.size and float(np.median(hues)) < GREEN_MIN_MEDIAN_HUE:
                continue
        cx, cy = (ox + x + w / 2) / fw, (oy + y + h / 2) / fh
        if any(zx1 <= cx <= zx2 and zy1 <= cy <= zy2 for zx1, zy1, zx2, zy2 in GREEN_DEAD_ZONES):
            continue
        kx1, ky1, kx2, ky2 = KILL_FEED
        if kx1 <= (ox + x) / fw and (ox + x + w) / fw <= kx2 and ky1 <= (oy + y) / fh and (oy + y + h) / fh <= ky2:
            continue
        # The player's own band. Only enemies are outlined, so nothing here produced a
        # false box in the tagrun footage -- but junk in front of the player is what
        # caused a stray ability press, so small marks are dropped. The height test is
        # the point: a bot at point blank stands exactly here and must survive.
        # The player zone stays in the passed image's own fractions, as it always has: placed in frame terms on the aim crop it covers
        # most of the crop and drops small marks the crop exists to see (postfreeze30 and tagrun0: 17 frames emptied, among them Luna's
        # pieces in a fight and a bot's bar). Where the hero really is in the crop is an open question (docs/lanes/l3-detector.md).
        pcx, pcy = (x + w / 2) / iw, (y + h / 2) / ih
        if (PLAYER_ZONE[0] <= pcx <= PLAYER_ZONE[2] and PLAYER_ZONE[1] <= pcy <= PLAYER_ZONE[3]
                and h < PLAYER_ZONE_MIN_H * s):
            continue
        if (w / max(h, 1) >= BAR_MIN_ASPECT and BAR_MIN_W * s <= w <= BAR_MAX_W * s
                and BAR_MIN_H * s <= h <= GREEN_BAR_MAX_H * s):
            out.append((int(x), int(y), int(w), int(h), "bar"))
        elif h >= GREEN_MIN_H * s and area / (w * h) <= GREEN_FILL_MAX:
            out.append((int(x), int(y), int(w), int(h), "outline"))
    return sorted(_merge(out, GREEN_MERGE_GAP * s), key=lambda b: -b[2] * b[3])


def _merge(marks, gap):
    """Join marks whose boxes are within `gap` px: arcs of one silhouette, not two bots.

    Closing the mask alone cannot bridge a raised arm held away from the body, and that
    came back as a second box on the same Galacta bot. Merging boxes afterwards is the
    cheaper half of the fix; the risk is two enemies standing shoulder to shoulder
    becoming one, which is why the gap is small relative to a body.
    """
    boxes = [list(m) for m in marks]
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if (a[0] - gap < b[0] + b[2] and b[0] - gap < a[0] + a[2]
                        and a[1] - gap < b[1] + b[3] and b[1] - gap < a[1] + a[3]):
                    x1, y1 = min(a[0], b[0]), min(a[1], b[1])
                    x2, y2 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
                    kind = "outline" if "outline" in (a[4], b[4]) else "bar"
                    boxes[i] = [x1, y1, x2 - x1, y2 - y1, kind]
                    boxes.pop(j)
                    changed = True
                    break
            if changed:
                break
    return [tuple(b) for b in boxes]


def find_enemies(frame_bgr, scale=None, band=GREEN, origin=(0, 0), frame=None):
    """Enemy boxes from the green marks. An outline box is the silhouette as drawn.

    One enemy usually carries both marks -- a contour round the body and a nameplate
    above it -- so a bar whose projected body overlaps an outline is dropped rather
    than counted as a second enemy. A bar on its own is kept: that is an enemy whose
    body is occluded, which the brain still wants to know about. `origin` / `frame`: as for find_green (an aim crop passes both).
    """
    out = []
    outlines = []
    for x, y, w, h, kind in find_green(frame_bgr, scale, band, origin, frame):
        if kind == "outline":
            box = (float(x), float(y), float(x + w), float(y + h))
            if not _flat((x, y, x + w, y + h)):
                outlines.append(box)   # a flat mark is a plate, not a body to anchor on
            conf = 0.9
        else:  # a bar sits above the body, same geometry as the red path
            bw, bh = w * BODY_W, w * BODY_H
            cx, top = x + w / 2, y + h + w * BODY_GAP
            ih, iw = frame_bgr.shape[:2]
            box = (max(0.0, cx - bw / 2), min(float(ih), top),
                   min(float(iw), cx + bw / 2), min(float(ih), top + bh))
            conf = round(min(0.95, 0.5 + w / 400), 3)
        if box[2] > box[0] and box[3] > box[1]:
            # keep the mark's own rect: the dedupe below must test where the *bar* is,
            # not where its projected body would be
            out.append((kind, box, conf, (x, y, x + w, y + h)))
    # Drop any *plate* -- wide, flat, bar-like -- that belongs to a body already found.
    # Testing flatness rather than the 'bar' label matters: when the plate is tall enough
    # to miss the bar thresholds it is labelled an outline, and a label-based test then
    # reports it as a second enemy.
    plates = [raw for _k, _b, _c, raw in out if _flat(raw)]
    keep = [(k, b, c, raw) for k, b, c, raw in out
            if not (_flat(raw) and any(_belongs_to(raw, o) for o in outlines))]
    return [Detection(cls=ENEMY, bbox=tuple(round(v, 1) for v in b), conf=c, plate=_plate(k, raw, plates)) for k, b, c, raw in keep]


def _plate(kind, raw, plates):
    """Was this box's name-and-health bar seen ON its body? An outline: True if a bar belongs to it, None if where the bar would float is
    above the image (cut off, so not seen either way), else False. A bar with no body (a projected box) is None: a bar alone is exactly what
    green scenery fakes (the spawn room door's flat glass edges read as bars on 18-23% of its sightings), so it is no evidence either way."""
    if kind != "outline" or _flat(raw):
        return None
    if any(_belongs_to(p, raw) for p in plates):
        return True
    return None if raw[1] - BAR_ABOVE * (raw[3] - raw[1]) < 0 else False


def _flat(rect):
    return (rect[2] - rect[0]) / max(rect[3] - rect[1], 1) >= FLAT_ASPECT


def _belongs_to(bar, outline):
    """Is this bar the mark of the enemy that `outline` traces?

    Overlap alone is not enough: the health bar and name float *above* the body, clear
    of the silhouette, so an overlap test left one spare box per visible enemy -- the
    single largest error in the first ground-truth pass. The bar belongs to the body if
    it sits horizontally within it and starts no higher than BAR_ABOVE of the body's
    height over its top.
    """
    ox1, oy1, ox2, oy2 = outline
    if not (bar[0] < ox2 and ox1 < bar[2]):
        return False
    return oy1 - BAR_ABOVE * (oy2 - oy1) <= bar[3] <= oy2


def detect(frame_bgr, scale=None, mode="auto"):
    """Enemy boxes. mode: 'green' (Enemy Color=Green), 'red' (nameplate), 'auto'.

    'auto' prefers green and falls back to the red nameplate path, so it works on
    footage recorded before the accessibility setting was changed as well as after.
    Boxes are in the pixels of the frame passed in, like detect.Detector, so a crop
    returns crop coordinates; the caller adds the crop origin. `scale` as in find_bars.
    """
    if mode in ("green", "auto"):
        green = find_enemies(frame_bgr, scale)
        if green or mode == "green":
            return green
    ih, iw = frame_bgr.shape[:2]
    out = []
    for x, y, w, h in find_bars(frame_bgr, scale):
        bw, bh = w * BODY_W, w * BODY_H
        cx = x + w / 2
        top = y + h + w * BODY_GAP
        box = (max(0.0, cx - bw / 2), min(float(ih), top),
               min(float(iw), cx + bw / 2), min(float(ih), top + bh))
        if box[2] > box[0] and box[3] > box[1]:
            # confidence is not a probability here: bar width stands in for how
            # legible the marker is, squashed into a 0.5-0.95 band so downstream
            # code can rank detections without reading it as a calibrated score.
            out.append(Detection(cls=ENEMY, bbox=tuple(round(v, 1) for v in box),
                                 conf=round(min(0.95, 0.5 + w / 400), 3)))
    return out


if __name__ == "__main__":
    frame = cv2.imread(sys.argv[1])
    assert frame is not None, f"cannot read {sys.argv[1]}"
    dets = detect(frame)
    for d in dets:
        print(d)
    if len(sys.argv) > 2:
        from detect import draw
        for x, y, w, h in find_bars(frame):
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 255), 1)
        for x, y, w, h, _kind in find_green(frame):
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 1)
        cv2.imwrite(sys.argv[2], draw(frame, dets))
