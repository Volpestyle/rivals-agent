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

Returns agent.state.Detection(cls=ENEMY) boxes for the body under each bar.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.state import ENEMY, Detection  # noqa: E402

# Red in HSV wraps hue 0. Thresholds measured, not guessed, off a known nameplate and
# its two competitors in the same frame (trial1/000094):
#   nameplate    H~174  S 111-151  V~229 (BGR 105,102,229 -- a bright red)
#   Spider-Man   H~150  S~189      V~200 (BGR  91, 75,148 -- a *darker* red)
#   pink masonry H~  8  S~ 48      V~178 (the map is full of this)
# Brightness separates the bar from the player's suit; saturation drops the masonry.
# A first attempt at S>120,V>110 alone boxed half the architecture.
HUE_LO, HUE_HI, SAT_MIN, VAL_MIN = 8, 168, 100, 195
# A nameplate bar, measured at 1280x720: 8-10 px tall, 80-105 px wide. Profiling the
# components found across 40 bot-bearing frames splits cleanly in two: real nameplates
# at w 80-105 h 8-10, and a tail of w 20-40 h 3-5 slivers, which are specular highlights
# on Spider-Man's own suit. The height floor is what separates them; it also serves as
# the player-exclusion rule, since the player is never drawn a nameplate.
BAR_MIN_ASPECT, BAR_MIN_W, BAR_MAX_W, BAR_MIN_H, BAR_MAX_H = 4.0, 35, 300, 6, 22
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


def detect(frame_bgr, scale=None):
    """Enemy boxes inferred from the nameplate above each hostile.

    Boxes are in the pixels of the frame passed in, like detect.Detector, so a crop
    returns crop coordinates; the caller adds the crop origin. `scale` as in find_bars.
    """
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
    # self-check: a wide thin bar is a nameplate, a tall red blob (the player's suit) is not
    _f = np.zeros((720, 1280, 3), np.uint8)
    _f[287:297, 449:554] = (0, 0, 255)   # nameplate, open space above it
    _f[323:454, 453:560] = (0, 0, 255)   # Spider-Man's torso, below
    _bars = find_bars(_f)
    assert len(_bars) == 1 and _bars[0][:2] == (449, 287), _bars
    _d = detect(_f)
    assert len(_d) == 1 and _d[0].cls == ENEMY and _d[0].bbox[1] > 297, _d
    # a native-resolution crop: same bar at 2x, found only when the caller says scale=2
    _c = np.zeros((960, 960, 3), np.uint8)
    _c[400:420, 100:310] = (0, 0, 255)
    assert len(find_bars(_c, scale=2.0)) == 1, find_bars(_c, scale=2.0)
    assert detect(_c, scale=2.0)[0].bbox[0] > 0
    # the player's belt: nameplate geometry, but the suit sits directly above it
    _p = np.zeros((720, 1280, 3), np.uint8)
    _p[300:390, 430:530] = (0, 0, 200)   # torso
    _p[392:400, 430:500] = (0, 0, 255)   # belt, a wide thin bright-red bar
    assert find_bars(_p) == [], find_bars(_p)

    frame = cv2.imread(sys.argv[1])
    assert frame is not None, f"cannot read {sys.argv[1]}"
    dets = detect(frame)
    for d in dets:
        print(d)
    if len(sys.argv) > 2:
        from detect import draw
        for x, y, w, h in find_bars(frame):
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 255), 1)
        cv2.imwrite(sys.argv[2], draw(frame, dets))
