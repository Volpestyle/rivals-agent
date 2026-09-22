"""Read the Rivals HUD out of one frame with fixed regions. No ML.

Every reader returns a value or None. None means "could not read this frame";
it is never zero, never "not ready". Callers must not treat it as either.

Regions are fractions of the frame, so they hold at 2560x1440 (the PC's native
size) and at the 1280-wide frames L1 records. Everything is measured off the
practice-range HUD: hp digits and bar bottom centre, ammo bottom left, ability
row bottom right. Damage numbers are not read: they float away from the hit and
fade, so no fixed region holds them.

    from perception.hud import read
    hud = read(bgr_frame)          # Hud
    h, w = bgr_frame.shape[:2]
    state = State(t=t, frame=(w, h), **hud.state_kwargs())

`state_kwargs()` deliberately leaves `frame` out; it belongs to the caller that
owns the image.

Self-check: `python -m perception.hud check` runs the labelled set in
perception/hud_truth.json. `python -m perception.hud learn <frame>=<values>...`
rebuilds the glyph templates from frames whose values a human has read.
"""
from __future__ import annotations

import base64
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

# --- regions, as (x0, y0, x1, y1) fractions of the frame -------------------

HP_TEXT = (0.440, 0.896, 0.560, 0.9315)  # "250 / 250", current in white, max in grey
# HP_TEXT stops short of HP_BAR on purpose: the bar is a bright horizontal strip
# and a digit that touches it merges into one component far too wide to be a glyph.
HP_BAR = (0.4055, 0.9335, 0.5945, 0.9425)
WEBS = (0.1620, 0.905, 0.1790, 0.950)    # count beside the left (LT) weapon icon
# Cropped tight to the digit: the weapon icon sits immediately to its left and
# on a busy background the two merge into one component too wide to be a glyph.
# The count is right-aligned at 0.1738, so a two-digit count would be clipped —
# Spider-Man's Web-Cluster never goes past one digit, but another hero's might.
# The ammo count is drawn near-white, and a bright diagonal of scenery behind it
# will otherwise merge with the digit into one component too wide to be a glyph.
# The hp region keeps the lower default floor because max hp is drawn grey.
WEBS_FLOOR = 140
WEBS_RIGHT = (24, 38)   # the count is right-aligned within its box

# Ability row, Spider-Man's four slots: same width, evenly spaced. Keys match
# agent.state; "tracer" is his 4th slot, which agent/state.py has no name for.
# The row is laid out per hero — Human Torch has five slots at other centres —
# so these hold for Spider-Man only.
SLOT_CX = {"teamup": 0.7516, "swing": 0.7950, "get_over_here": 0.8348, "uppercut": 0.8723}
ICON_DX, ICON_Y = 0.0165, (0.890, 0.933)   # the icon glyph itself
BADGE_DX, BADGE_Y = 0.0105, (0.849, 0.879)  # charge count above the icon
ULT = (0.902, 0.872, 0.972, 0.950)


@dataclass(frozen=True)
class Layout:
    """Where this HUD puts the things the readers look for.

    Two exist. `PAD` is the console/controller HUD our own captures use. `MK` is
    the mouse-and-keyboard HUD a PC streamer shows, measured off a 1080p Twitch
    clip. The caller picks one; nothing here guesses per frame, because guessing
    wrong is silent and the answer is a property of the source, not the frame.

    The two differ less than they look. hp text, hp bar, the ability row and the
    ult sit at the same fractions on both -- only these move:

    * **The ammo slots are mirrored.** On the pad HUD the web count is the left
      slot and melee is the right; on M&K it is the other way round.
    * **The charge badge inverts.** Pad draws a dark digit on a light disc; M&K
      draws a light digit and ring on a dark centre.
    """

    name: str
    webs: tuple
    webs_right: tuple
    badge_light_disc: bool   # True: dark digit punched out of a light disc
    # How much ink may sit in the gaps beside a slot before something is being
    # drawn over it. This is a property of the layout, not of the reader: the pad
    # HUD puts its own separators in those gaps and measures up to 0.91 on clean
    # captures, while the M&K row leaves them empty (0.09 clean, 0.22 under
    # chat). One global number cannot serve both.
    slot_spill: float = 1.01   # 1.01 = never fires
    hp_text: tuple = HP_TEXT
    hp_bar: tuple = HP_BAR
    slot_cx: dict = field(default_factory=lambda: dict(SLOT_CX))
    ult: tuple = ULT


# Our own captures have nothing drawn over the HUD, so the pad guard sits above
# anything measured on 580 clean slot readings and is effectively dormant.
PAD = Layout(name="pad", webs=WEBS, webs_right=WEBS_RIGHT, badge_light_disc=True,
             slot_spill=0.95)
# Measured on reqmr-2873352801-1920: the count sits at x 0.2602-0.2672 on every
# still, right-aligned like the pad one, so the box is the pad box shifted right.
MK = Layout(name="mk", webs=(0.2455, 0.905, 0.2700, 0.950), webs_right=(48, 66),
            badge_light_disc=False, slot_spill=0.15)
LAYOUTS = {"pad": PAD, "mk": MK}

# A ready icon is drawn in white, or gold while a buff is up; one that is
# cooling or unavailable is drawn in red. Brightness alone does not separate
# them — a red icon can be brighter than a thin white one — so the test is how
# much of the icon's ink is red. Between the two thresholds the reader says
# None rather than guess.
ICON_COOLING, ICON_READY = 0.55, 0.40     # red fraction of the icon's ink
SLOT_GAP = 0.010          # width of the gap either side of a slot that is checked
ICON_MIN_INK = 40                          # px at 2560 scale; fewer means no icon
ULT_READY, ULT_CHARGING = 0.22, 0.05      # yellow-pixel fraction of the ult box


def crop(frame, box):
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = box
    return frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def _scale(frame):
    """Glyph sizes are quoted at 2560 wide; bring any frame onto that scale."""
    return 2560 / frame.shape[1]


# --- glyphs ---------------------------------------------------------------
# HUD text is light-on-anything. A tophat kills the slow background gradient and
# leaves the thin bright strokes; the brightness floor drops pale scenery.
# Three kernels, because the HUD draws its numbers over whatever the camera is
# pointing at. The wide one is the general-purpose background remover; the
# narrower two pass only marks about as thin as a stroke, which is what rescues
# bright white digits sitting on a bright wall. Readers try all three and keep
# whichever passes their layout checks. Measured over run1: the wide kernel
# alone leaves 9.8% of frames with unreadable hp, all three leave 6.8%.
_TOPHAT = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
_TOPHAT_NARROW = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
_TOPHAT_THIN = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
KERNELS = (_TOPHAT, _TOPHAT_NARROW, _TOPHAT_THIN)
# 16x24 rather than something smaller: an 8 loses its waist at 12x18 and starts
# matching a 0, which is the difference between a wrong number and a right one.
GLYPH_H, GLYPH_W = 24, 16


def _mask(img, scale=1.0, floor=115, kernel=_TOPHAT, contrast=55):
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    mn = img.min(axis=2)
    top = cv2.morphologyEx(mn, cv2.MORPH_TOPHAT, kernel)
    return ((top > contrast) & (mn > floor)).astype(np.uint8), img


# Max hp is drawn small and grey and answers to a much lower contrast than the
# white current hp beside it. Readers see every combination and let their layout
# checks pick; over the labelled set the extra passes take max hp from 0.890 to
# 0.952 coverage without producing a single wrong number.
CONTRASTS = (55, 30, 20)


def _masks(frame, box, floor=115, contrasts=CONTRASTS):
    """The region thresholded every way a reader is allowed to look at it.

    A generator on purpose: most frames are read from the first pass, and the
    tophats behind the later ones are the bulk of this module's running time.
    """
    crop_img = crop(frame, box)
    scale = _scale(frame)
    if scale != 1.0:
        crop_img = cv2.resize(crop_img, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)
    for c in contrasts:
        for k in KERNELS:
            yield _mask(crop_img, 1.0, floor, k, c)[0]


# Digit sizes at 2560 wide: current hp and the ammo count are ~20x32, max hp is
# ~15x25, the "/" ~15x33, a charge badge's digit ~12x18. Anything outside the
# window a region asks for is scenery, not text.
TEXT_SIZE = (20, 36, 8, 26)   # min_h, max_h, min_w, max_w for the hp and ammo rows
BADGE_SIZE = (10, 24, 5, 20)
# A cooldown replaces the slot's icon with a countdown, set much larger than any
# other number on the HUD: 42-43 px tall at 2560 against the hp row's 23-33.
COOLDOWN_SIZE = (36, 52, 12, 30)
COOLDOWN_CENTRE = 0.18   # how far off the slot's middle a countdown may sit


def _segment(mask, size=TEXT_SIZE, min_area=35):
    """Glyph boxes, left to right, within the size window."""
    min_h, max_h, min_w, max_w = size
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if min_h <= h <= max_h and min_w <= w <= max_w and area >= min_area:
            out.append((int(x), int(y), int(w), int(h)))
    return sorted(out)


def _normalise(mask, box):
    x, y, w, h = box
    g = mask[y:y + h, x:x + w]
    return cv2.resize(g, (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA) > 0.4


# Templates learned from frames whose values a human read (see `learn`), packed
# one GLYPH_H x GLYPH_W bitmap per base64 string. Several variants per
# character: the HUD draws the same digit at two sizes (current hp large and
# white, max hp small and grey) and they do not normalise onto one bitmap. A
# glyph is classified by Hamming distance to the nearest variant; ties and poor
# matches return None. Do not hand-edit -- re-run `learn`.
GLYPHS: dict[str, list[str]] = {
    "/": [
        "AAMAAwAHAA8AHAA8ADwAeABwAOAB4AHAAYAHgAcADgAeADwAPAA4AHAA4ADgAMAA",
        "AAcADwAPAB4AHAA8AHgAeADwAOAB4APAA8AHgAcADwAOAB4APAA4AHgAcADwAEAA",
        "AAEABwAPAA8AHgAcADgAeABwAPAA4AHgA8ADgAeABwAOAA4AHAA8AHgAeABwAGAA",
        "AAIABgAGAA4AHAAYADgAcABwAOAA4AGAAQAHAA8ADgAcABwAOAAwAHAA8ADgAMAA",
        "AAIABwAGAA4AGAAYADgAcABwAOAA4AHAAYADgAeABgAOAB4AHAAYADgAeABwAOAA",
        "AAMAAwAHAAcADgAMABwAOAA4AHAAcADAAIADwAeAAwAOAA4AHAA8ADgAcABwAOAA",
        "AAIABwAPAA8AHgA+ADwAeABwAPAA4ADgAMADgAOABwAPAA8AHgAeADwAeAD4APAA",
        "AA8AHgAeAD4AOAA4ADAA4ADgAcADwAPAB4APgA+AHwA/AHwAOAAwAHAA4ADgAMAA",
        "AAMAAwAHAA4AHAAMADAAcABgAGABwAGAAYADgAYABgAOAAwAMAA4AHAAYADAAIAA",
        "AAcABgAGAAYAGAAYABgAcABAAGAAgAGAAQADAAYADAAMAAgAMAAwACAAYADAAIAA",
        "AA8ADgAMABgAOAAwAHAA8ADgAeADwAfAB4AHAA4ADgAMABwAGAAwAHAAcADgACAA",
        "AAMADAAMAAwAHAA4ADAAcADgAOABwAHAAYADAAMABgAOABwAHAAYADgAcABgAOAA",
        "CB4APgA+ADwAOABwAGAA4ADAAcADgAOAAwAHAA4ADgAcABwAOAB4APAA8ADgAMAA",
        "AAcAHwAeAA4APAA4AHAAcADgAMABwAPAA4AHAA8ADgAcABwAOAB4APAA8ADgAMAA",
        "AAcABgAOAB4AGAAYAHgAYABAAMABwAGAAwAHgA8ADAAMADgAOAAwAHAAYADgAMAA",
        "AAMAAwAHAB8ADgAcADwAcABwAOAA4AHAAYADgAeABwAGAAYAEAAwADAAIADAAMAA",
        "AAcADwAPAA4AHAAcADgAcABwAMAB4AHAAYADgA8ADgAOAAwAEAAwADAAIADgAMAA",
        "AAIABgAGAA4AHAAYADgAcABgAOAA4AGAAYAHgAcABwAPAA4AGDAYMHAAYADgAGAA",
        "AAIABgAGAA4AHAAYADgAcABwAGAA4ADAAYADgAOAAwAHAA4ADDAMEDgAMABwAHAA",
        "AAMAAwAHAA4ADgAcABwAOABwAPAB8AHAA8APwA+ADwAfAB4APAA8AHgA+ADwACAA",
        "AAIABgAGAA4AHAAcADgAcADwAOAB8APAc48fwA8ADgAMABgAOAAwAHAA4ADgAMAA",
        "AAYADwAeAB4APAB4AHgAcADwAOABwAHAA4ADAAcABwAOAB4AHAA8AHgAeABwAOAA",
        "AAIAAgAGAA4APwA/ADgAeAHwA+ADwAeADgAOAB4AHAAcABgAGAAYADAA4ADAAMAA",
        "AAMABwAPAA8AHgAeADwAOAB4APAA4ADAAYAHwAcAAwAOABwAGAAYAHAA8ADwAGAA",
        "AA4AHgAeABwAPAB8APgA+ADwAeAD4APAA4AHAAcADwAPAB4APAA8AHgA8ADgAEAA",
        "AAIAAwACAAYADAAMAAgAEAAwAHAA4ADAAIADwAMAAwAGAAwAHAAYADgAcABgAGAA",
        "AAEAAwADAAMADAAcABgAcABgAOAA4AHAAYADgAMABgAOABwAMAAwAPAA4ADAAMAA",
        "AAYAHgAeAB4APAA4AHAA8ADgAOAA4AEAAwAHAAYADAAMAAwAMAAwAGAAYADAAIAA",
        "AAMABwAPAA8AHgAcADgAeABwAHAAYAAAAQADAAYADAAMAAwAMAAwACAAYADAAIAA",
    ],
    "0": [
        "AfiP/p//H/8fHx4ePh48Hjw+PDw8PDw8fDx8PHh8+Hz4ePB48Pjw+P/w//D/4D+A",
        "B/4f/h8/Pgc8BzwHPB88HnwefB54HngeeBz4PPg8+DzgPOA84HzgfOB4//j/4H+A",
        "A/4P/x//Hw8eDx4PHg4eDhwOPB48Hjw+ODx4PHg8eDx4OHB48HjwePD4//j/8H/A",
        "B/4f/h8/PAc8BzwHPAc4BjgeOB44HHgceBx4HPg8+DzgPOA84HzAfOB4//j/4AOA",
        "ABDD/sf/z/+f/x8fHx8/Hj4ePh4+Pjw8PDw8PHx8fHx4fHh4ePh8+P/4//B/4D+A",
        "B/4P/x//H/8fDz4PPg8+DzwfPB88H3wfeB54HngeeDx4PPg88DzwPPx8//j/+H/w",
        "B/wP/h/+H/4fPz4ePh4+Hjw+PD48Pnw+eDx4PHg8eHh4ePh48HjwePz4//D/8H/g",
        "h/6P/p//n/8/Hz4ePh4+Pj4+PD48PDw8fDx8fPx8+Hz4fPh48Pjw+P/4//D/4H+A",
        "AfgH/h//H/8eHx4ePB48Hjw+PDw8PDw8PDx8PHg8eHx4fHh48Hjw+P34//D/8H/g",
        "ABCH/o//n/8f/z4/Pj8+Pj4+fj58Pnw+fHx8fPx8/Hz4fPj8+Pz5+P/4//D/8BgA",
        "A/4P/x//H/8eDz4PPg8+Dz4fPB98H3wffB54Hng+eD74PPg8+Dz8/P/4//h/4AMA",
        "g/yP/5//n/8/Pz4/Pj4+Pj4+fD58Pnw+fHx8fPx8+Hz4fPj8+Pj5+P/4//B/8BgA",
        "AfCP/p/+n/8//z8+Pj4+Pj48fHx8fHx8eHx4/Pj4+Pj4+Pj4+Pj58P/w/+D/4BgA",
        "B/wP/h/+H/8/Pz4ePh4+Hjw+PD58Pnw+fDx4PHh8eHz4ePh4+Hj9+P/w//B/wAMA",
        "gfjH/s//j/8PHx8eHh4+Hj4ePhw8PDw8PDw8PDh8eHx4fHh4eHh4+H/w//B/4B+A",
        "w/7H/8//j/8fHx8fHx4/Hj4ePh4+PDw8PDw8PHx8eHx4fHh8ePh8+P/4//B/4D+A",
        "A/wP/w//H/8eDx4PHg8cDzwPPA48DjwOOB54HngeeBx4PHA8cDxwPPh8//h/8D/g",
        "B/4P/w+fHgccBxwHHA88DjwOPA44DjgOOB44HngceBxwHHAccDxwPHh8//h/8D/g",
        "AOAH/h//P/8+BzwHPA8YDzwPeA54HngeeB74HPA88DzwGPA84HzgfPD8//j/4H/A",
        "AMAH/h//D/88BzwHPAcYDjAOMA44HjgceBx4HPAM8BzwGOA84HzgfOBw//j/4B+A",
        "A/wf/h8fPAc8BzwHOAY4BjgEOBw4HHgceBx4HGAcYDzgPOA84DzAPOB4/+B/4AIA",
        "w/zH/8//n/8fPx8fPx4/Hj8ePj4+Pj58PHx8fHx8fHx4fPj8/Pz/+P/w//B/4AQA",
        "g/iH/o/+n/+f/x8+Pj4+Pj4+Pj5+fn5+fHx8fHx4fHh8ePj4/Pj/+P/w//B/4AQA",
        "B/wP/h/+H/8/Pz4fPj4+Pn4+fD58Pnw+/H58fnx8/Pz8/Ph8+Pz/+P/4//B/4B+A",
        "ABAAOAf+D/8fHx4PHg8eDh4OHA4cHjgeOBw4HDg8eDh4OHA4cDjwePB4//D/4D+A",
        "A/gP/x8HHgccBxwHHAccDzwPOA44DngeeB54HHAccDxwPGA84DjgOOB48fB/8B8A",
        "ADgD/gf/n/8fDx4PHg8eDh4eHB48HjweOD44PHg8eDx4ePh48HjweP/4//j/4AgA",
        "ADgD/g//n/+fnx8PHw8eHz4ePh48HjwePD58PHw8eDx4fPh88Hjw+P/4//j/4D+A",
        "gfiH/p//v/8+Hz4ePh58Hnw8fDx8PHx8fHx8fPx8/Hz4ePj48Pjw+P/w//D/4B+A",
        "ADAD/w//H/8eDx4PHg8eDhwOHA48HjwcODw4PHg4eDh4OHB48HjwePD4//D/8D/A",
        "AfwH/g//HgceBxwOHA4cDhwOHB4YHDgcODw4PDg4eDhwOHA4cDjwePB4//B/4D+A",
        "Af6H/p//n/8fPx4/PD48Pjw+PDw8PDw8fHx8fHx8eHj4ePh4+Pj5+P/4//D/4D+A",
        "B/4f/h//Ph88HzwfPB98H3wePD54Png+eD74Pvg8+DzgfOB84HzgfOD4//j/4H/A",
        "AeAH/w//H/8fDx4PHg8eHx4ePB48Hjw8ODx4PHh8eHj4ePB48Hj4+P/4//B/4A4A",
        "ADjD/8f/z//f/x8fHh8+Hj4ePh4+PD48PHw8fHx8fHx8fHj4ePz9/P/4//h/8B/A",
        "APgH/A/+H/4/Hj4ePj8+Pz4+PD48Pnw+fDx4PHh8eHx4fPh48Hj/+P/w//B/4B8A",
        "AHwH/g//H/8eDxwPHA88DzwOHB44HjweeB54HngeeBx4PHg88Dz4fP/4//g/8AMA",
        "g/6H/w//Dw8ODw4PHg4eDh4ePB48Hjw+PD48PHw8fDx8/Px8/Pz//P/8//h/8B+A",
        "AfgD/g8PHgYeBh4GHA4cDhwOHA44DDgcOBw4GDg4MDgwOHA4YDjgeGB4e/B/4AMA",
        "g/6H/4//j/8P3x8fHh4eHj4ePh4+Pjw8PDw8PDg8ODx4fHh8ePj4+P/4//D/8H/g",
        "A/4P/w//H/8eDxwHHA8cDxwPPA4YDjgOOB54HngeeB54HHAccBxwPPA8/Hz/+H/w",
        "B/4P/x//H/8eBxwPHA8cDzwPPA48DjwefB98Png+eD54PHg8+Dz4fv/8//h/8B/g",
        "A/4H/h8fPAc8BzwHOAYQBhAOMA4wDDgceBxwDHAMYBhgGOA84DzgPMA84Hj/4H/A",
        "A/wH/x//D/8+Dz4PPg8YDzwPPA44HDgceBx4HHA8YDxgGOA84DzAPOBw/+D/4AEA",
        "AYAH/g/+H/8eHx4eHB48HDwcPDw8PDw8PDw4PHg8eDh4OHh48Hjw+PDw//D/4H/A",
        "AfAH/h/+H/8eHx4ePB48HjwcPDw8PDw8ODx4PHg8eHj4ePB48Hjw8P/w//D/wAIA",
        "AfwH/w//n/+fDx4PHg8eDxwfHB48HjwePBw4PHg8eDx4fHB48HjwePj4//j/8H/A",
        "Af4D/h4fPAc8BzwHPAY8BnwEfBx4HHgceBx4HHg8YDzgPOB84HzAfOB4//h/4AYA",
        "B/4P/g//Hh8eHhwePB48HDw8PDw8PDw8ODx4PHg4eDh4ePB48Hjw+PDw//D/4H/A",
        "AOAD/Af+Hx8cBzwHPAc8BjgGOB44HngceBx4HHgcYBxgPOA84DzAPMA4wHj/4H/A",
        "AfiH/4//z//fH98fnh6eHr4ePh48PDw8PDw8PHh8eH14fXh5ePv8+//5//F/4T+A",
        "AfiH/s//z//PH98enx6+Hr4evhw8PDw8PDw8PDx8fHx8fHh4+Pj8+H/4//B/4D+A",
        "AHAH/g//H/8eDxwPHA8cDxwPPA44DngOeB54HngceDxwPHA8cDxwPHg4//j/8H/A",
        "AB8B/wPwB/Af+Bw4ODg4eDh4OHA4cDjwOPAw8HDwcPBw8GDgYODg4PDA/8B/gD8A",
        "A/gP/5//n/+/Hz4fPD48Pjw+PD48PHw8fDx8PHh8eH34ffB58Hnw+f/5//H/4T8A",
        "A/wP/g+PDAccBxwHHAccBhgOOA54DHgMeAw4DDgceBxwPHA8cDxwPHA4//h/8D/A",
        "ADMAeAD4B/4PDxwHHAccDxwOPA44DjgeOB44HjgecB54HHAccDzwPPg4//h/8D/g",
        "A/4P/w//Hw8eDx4PHg8eDhwePB48HjwcPDx4PHg8eDxwePB48Hj4eP/4//D/4AIA",
        "H/4eBxgHPAc8BzwHPAYYDnAOcAxwDHgceBxwHHA8YBjgOOB84HzAfOBw//j/4D8A",
        "GAY8BzwHPAc8DzgGOAQwDDAMMA44HHgceBzgPOA84DzgPOA84HzgePBw//D/4D/A",
        "AfwH/o//z//fH58enh6eHp4ePhw8PDw8PDw8PDh8OHx4fXh5eHl4+f/xf/F/4B+A",
        "A/wP/h/+H/4fHz4ePh48HjwePBw8PHw8eDx4PHg8eHh4eHh48Hj4+P/wf/A/4AcA",
        "AfgH/h//P/8+Dz4Pfg94DzwPOA84HngceBz4HPA88DzwGPB84HzgfPDw//j/4H+A",
        "AHgH/g//H/8eDxwHHA88DzwOPA48DzwfOB44HngceBx4HHAccDxwPPg8//h/8D/g",
        "A/4f/z+/Pgc8BzwHOAY4BDgEeBx4HjgceBx4HPgc+Dz4POA84HzgfOB4//j/4D+A",
        "A/wP/h/+P/4/Pj4ePh8+Pz4+PD44PjgeOBx4OHg4eDh4OHB4cHhwePj4//B/4D/A",
        "A/wP/h/+H/4fHj4ePh4+Hj4+fj58Pnw/OD44Png8eDh4OHA4cHhwePj4//B/4D/A",
        "AfwH/4//z//PD58Pnw+eHx4fPh48HjwePD48PDw8PDx8PHw8eHz8/P/4f/h/8B+A",
        "A/wH/x//P/8fDz4PPg8+Dx4fHB84HzgOOA54HHgceBx4HHA8cDxwPPh8//h/8D/g",
        "A/4f/x8/Pgc8BzwHPAc8BjgeeB54HngeeBx4HPg84DzgPOA84DzgPOB4/+D/4B8A",
        "AHgH/o//D/8eBxwHHA8cDxwOOA44DjgOOA54HngceBx4PHg8cDzwPPB4f/h/8B/g",
        "ABgD/gf/D/88BzwHPA8QDzAOMA44HngeeB74HPAc4DzgGOA84DzgfOBw//j/4B+A",
        "g/yP/p//n/+/Pz4fPj4+Pjw+fD58PHw8fHx8fHh8eHz4ePB48Hjw+P/w//D/4D8A",
        "A/wf/j//P/8/D34Pfg9+H34/fD94P3g+eD54PvA88DzwGOA84HzgfOBw//j/4D+A",
        "AOAD/h//H/8cBzwHPAc4BzgGOB44HDgcOBx4HGAcYBxgGGA4QDjAOMA4wCD44H/A",
        "j/4f/x//H/8eHx4PHg8eDz4fPB48Hjw+ODx4PHg8eDj4ePB48Hj4+P/4//D/4AEA",
        "B/4f/x//Pg88BzwHPAcYDhAOMA4wDngeeB5wPHA8YBjgGOA84DzgPOAw+Hj/4P/g",
        "AdgH/w//H/8fDx4PPg9+D34ePh48Hjw+PD54PHg8eDx4ePB48Hjw+P/4//D/4A4A",
        "AfiD/s//3//fH94enh6+Hr4evhw8HDwcPDw8PDh8eHx4eHh5eHn48f/x//F/wD+A",
        "HAc8BzwHPA84DzAOMA44HngecA5wDHAMcBzwPPA84DzgPOB84HzgeOBw//D/4B+A",
        "A/4f/x//P/8/D34Pfg94D3wPfB94Png++D74PvA+8DzwGPB84HzgfPD8//h/4B/A",
        "AfCH/of+j/8PHw4eHh4eHh4ePhw8HDw8PDw4PHg8eDh8eHx4ePh5+H/4//B/4B+A",
        "D/4f/j//P/9+P3wffB98HnweeD54Png+8DzwPPA88DzweOB44HjgePD4//B/4B/A",
        "APgH/w//H/8fHx4PHg8+Dz4fPh48HjweOD54PHg8eDh4OHA48HjwePD4//j/8D/A",
        "AfwH/w//DgcOBw4HDAccDxwPHA4YDjgOOA44DDgcMBxwHHAccDjwOPB4//B/8B+A",
        "ABwD/gf/D58eBxwHHg88DzwPPB48HjgeOB54HHgceBxwHHAccDxwPHB8//h/8D/g",
        "ADwD/gf/D78+BzwHPA84D3wOeA54HngeeBz4HPAc8DzwGOA84HzgfODw//j/4H/A",
        "A/4H/w//H/8eDx4PPg88DzwfPB88HjgeeB54HngeeB54Png88Dz5/P/4//B/8BoA",
        "g/yP/p//v/8/vz4/Pj4+Pn4+fj5+Pnx+fH58fHx8eHz4fPj88Pjw+P/4//D/4D8A",
        "EAAQAB/+P/58D3gHeB94H3ge+B74HvgY+BDwEMAwwHDAcMBwwHCAcP/gf8AHAAIA",
        "AfyH/o//D/8PHw4eHh4eHj4cPBw8HDw8PDx8PHx8eHx4fPj4+Pz//P/4//B/4B4A",
        "AfyD/o//j/8PHw4eHh4eHj4cPhw8HDw8PDw8PDx8eHx4eHh4ePh5+P/4//D/8D+A",
        "AfgH/w/fHgceBx4OHg4+DjwOPB48HjgcODx4PHg8+Dz4fPh48Hj8+P/4//D/4B+A",
        "ADgH/4//H/8fDx8PHg8eHz4fPh9+fjw8fDx8PHg8eDz4fPh48Hj4+P/4//D/4B+A",
        "AfwH/w//Hw8eDx4PHA4cDhwOHB48Hjg8ODx8PHg4eDhwePB48Hj8+P/4//D/4D8A",
        "ADgH/h//Dz8+DzwHPAcYBxgOOA4wBDgMOBxwDHAMcBhwGOA84DzwfOBwwDjAIMBA",
        "AfwH/w4DDAMYARgDGAMYAxgCGAYYDjgOOA44DnAOYAZgDnAYQBjAGMAYwBD/8H/g",
        "AHyH/o//Hx8fDx8PHg8eHz4fPh48Hjw+PD58PPx8+Hz4fPB88Pj4+P/4//D/4D+A",
        "g/7H/8//Dw8PDw4PDg8eDhwePB48Hjw+PDw8PDw8ODw4PHg4eHj4+H/wf/AcAAgA",
        "B8AH/A/+H/4YHjgMOA4wDiAOIA/gHvAYcBhwGCAQABAAAGAQ4DDgMOBg/+B/wDgA",
        "A/wH/x//P/8+DzwHPA84D3wPfA54HngeeB74PvA88DzwGOB84HzgfOBw//j/4D+A",
        "APgH/h/+Pz8+BzwHPA8YDjgOMA54HngeeBx4HHA88DzgGOA84DzgfOBw//j/4B8A",
        "AGAD/h//P78+BzwHPA8YDzgOMA54HHgceB54PnA84DzgGOA84HzAfOBw/+D/4H+A",
        "A/wH/h4GDAcwBzAGMAYQBhAEMAQwDDgcOBxwDGAMYAhgGGAwQDDAMMAw4Dj/4H/A",
        "AHgH/g//H/8eHxwfHB48Pjw+PDw8PDg8ODx4PHg8eDx4OPB48HjwePD4//D/8H+A",
        "AHgD/g//D/8cHxweHB4cHhwcPDw4PDg8ODw4PDg8cDhwOHA48HjgePDw//D/4D+A",
        "AfwP/g//HB8cDxgPGA4YDhgeMB5wHnAccDxwPHA8cDhwOOA44HjgeOBw8fB/4A8A",
        "AEAB4If+j/8PHx4eHB4cHhwePDw8PDw8ODw4PDg8ODx4OHB4cHjwePDw//D/8H/g",
        "A/4P/x4HHgceBx4HHg8cDzwOOA44DjgeeBx4HHgceDxwPOA44DjgeOB48fD/8AYA",
        "wfzD/8f/j/8Pnw8fDx4fHh4eHh4+Pjw8PDw8PDx8PHw4fHh8+Pz8+P/4//h/8B/A",
        "gHyD/4//H/8fDx8PHw8fHx4ePh48Hjw+PD48PHw8fDx4fHB48Hjw+P/4//B/4A+A",
        "AfzH/s//3/+f/x+fHx8/Hj8ePx4+Pj4+Pjx8PHx8fHx4fPh8+Pz8+P/4//D/8D/A",
        "AH4B/wf/D/8fnx8PHg8cDzwPPA48DjgeeB54HHgceBz4HPg8+Dz4OP/4//B/gDwA",
        "A/4P/w//H/8eDx4PHA8cDjwOOA44DjgMeBx4HHgceBx4HHg8eDz8eP/4f/A/wBgA",
        "A/4H/w//H/8f/z4fHh8eHzwfPB58HnwefB58Hng8+Dz8PPw8+Dz//P/wf+A+ABAA",
        "Af6H/4//z//fP98fnx++Hr4evj4+fjx8PHw8fDx8fHx8fHh8ePh9+H/4//B/4D+A",
        "A/wf/h8fPgY8BjwGOAY4HjgcOBwgHGAcYBhgGOAY4BjgOOA4wHzAfMB4//h/4AOA",
        "A/wH/w//D/8eDx4PHA88DzwPPB88H3wfeB94H3g+eD54Png88Dz8fP/4f/h/8AAA",
        "A/gf/j//P/8+Bz4HPg84DngOcA54HHgc+BzgHOA84DzgGOB84HzgfOD8//j/4H/A",
        "APiD/of/j/8PHw8eHh4eHB4cPBw8PDw8PDw4PHg8eDx4PHh4eHh4+P/w//A/wBgA",
        "AAQD/gcfHgceBh4OHg4eDhwOPB44HjgcOBw4OHg4cDhwOHA48HjgeOH4//j/8D+A",
        "A/4H/g8PDAccBxwHHAcYBxgPGA84HzgeOD48Pnw8eDz4PPg8+Dz+fP/4//h/8A+A",
        "A/4H/g+PDAccBxwHHAcYBxgPGA84HjgeOB44Hjw+fDx4PPg8+DzwPPx8//j/8D/w",
        "A/wH/A8eDA4cDhwOHA8YDxgeGD44Pjg+PHw8fHx8fPz4/Pj4+Pz/+P/4//B/4h/A",
        "A/4f/j//Ph88BzwfPB88HzgeOB54HHgeeB54PmA8YDzgPOB84HzgfPj4//j/4H8A",
        "A/gH/h//P/8+D3wHfA94D3wffD58Pvw/+D74PvB+8H7wfPB8wHzAfMB8/uD/wD+A",
        "AHAH/g//Hx8eBzwHHg8cDzwPPA88DjgOeB54HngceDx4PPg8+DzwPPx8//h/8D/w",
        "A/gH/h//D/88DzwHPAcYDjwOfA54HngeeB54HPA88DzwGGA8wDzAPMAw/uD/wD+A",
        "A/gH/g//H/8eDzwHPAc8DzwPPB48HnwfeB54Hng+eD54PHA8YDxgPHA8//B/4D/A",
        "AeAD/g/+n/6f/54fPh8+Pjw+PD48PDw8PDx8PHh8eHz4ePh48Hjw+P/w//D/4D+A",
        "D/g//j//H/8YDjgOOAx4DHgcOD4wHjAY8BjwGPA48DjwOOA44HjgeOBw//D/4D+A",
        "AfgP/H/+f/5//zwfOB8wDjAMMAj4GPg8cD5gPGAY4DjgOOA44HjgePBw//D/4D4A",
        "A/gf/h//D/8MBzwHPAZ4DnweOB84HzgceBx4HPAc8DzwGOA84HzgfOBw//h/4B8A",
        "Afgf/j//Ph88BzwHOAY4BjgE/Bz8Pnw/eD9gPmAc4DzgPOA84HzgfOB4//h/4AcA",
        "APAB/of+z/7f/98fnx+/Hr4evh4+Pj48PDw8PHx8fHx4fHh8ePj8+P/4//B/4B+A",
        "BD8ODw4ADgAeAR4BHgEeAR4BHgAeADwAfAB8B3wPfA98H3gfeB/4H/g///7//H/8",
        "A4AP/D/+f/98D3gPeA94HngecB5wHnAe8B7AHsA+wDzAPMA8wDyAPAA8AHAP8A/A",
        "D/w//h4+GA94D3gOeA54BHAAcAhwGPAc4BzAGMAYwBjAGMA4wDiAOAA4AHAP8A/A",
        "AfQD/wz/HD8cBxwHPAc8BzwHPAc8BjwAOAB4HHgeeBx4PHA8cDzwPPB8//j/8H/w",
        "B/gf/j//P/8/Pz4PPg8eHzw/fB94H3geeD54PnA+cD5wfPB8YHxAfEH8f/gf4APA",
        "A/gf/h//P/8+Dz4PPg8eDzwOfA54HngeeB54HnAccDxwGPB8YHxAfEH8f/gf4APA",
        "AfgD/o//z//PH44enh6eHr4ePh48Pjw+PHw8fHx8fHx4fHh8ePz9+P/4//B/4D+A",
        "ADAH/o//z//f/98/3x+/Hr4+vj6+Pj48Pjx8fHx8fH14/Xj9ePv8+//7//N/8T+A",
        "A/yP/8//3//fP98fvx6/Hr4evj4+Pj58Pnw8fHx8fHx8fPh8+Pz9+P/4//D/8D/A",
        "Af6H/8//3//fv98fnx++Pr4+vj4+PD48Pjw8fHx9eP14/Xj9ePv8+//7//N/8T+A",
        "A/gH/o/+n/+f/5++nj6+Pr4+vj5+fH58fnx8fHx4fHh8ePj4+Pj58P/w//D/4D/A",
        "A/4P/w//H/8fDz4PPA88DzwPPA48HnweeB54HngeeDx4PHg88Dz8fP/4f/g/8AcA",
        "A/4H/g+fHgccBxwHHAYYDhgOGA44DjgOOAw4DHgccBxwHHAc8BzgHPA4//B/8A+A",
        "A/6P/4//z8+PD54Pnh++Hx4fHh48Pjw+PD48Pjw8PDx8PHg8+Hx4eH/4f/g/8ADA",
        "AfwP/h/fH4ceBx4PHg4eDxweHB48HjwcPBx4PHg8eDxweHB48HjwePj4//h/8D/A",
        "I/6P/4//nx+fHp4evh6+H74fPjw+PDw8PDw8PDg8OHx4eXh5+Hn/+X/xf/F/4AGA",
        "A/gP/g/+H/8/Pz4ePh4+Pj4+fj58Pnw+fH58fHx8eHh4eHB4cHhweHjw//B/4D/A",
        "A/gP/g/+H/8ePhweHB48HjwePBw8HDwceDx4PHg4eHh4eHB4cHhweHjw//B/4D/A",
        "H/h//n//+B/4D/gP+A/4D/gP+A/4D/gP+A/4D/gP+B/4H/gf+B/4H/gf//9//j/8",
    ],
    "1": [
        "/8D/wP/gf+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4Afg/////v//",
        "f8B/wH/AB+AD4APgA+AD4APgA+AD4APgA+AD4APgA8ADwAPAA8AD4Afwf/9//v//",
        "ecB/4P/wf/AD4APgA+AD4APgA+AD4APgA+AD4APgA+AH4APgA+AD4Afgf/9//3//",
        "APgD/wP/AH8APwA/AD4AfgB4AHgAeAB4AHgAeADwAPAA+AHwA/AD4Afgf/7/////",
    ],
    "2": [
        "AfwH/g//D/8PHx8eHh4APgB8APwB+APwB8APwB+APgA8AHgBeAF4Af/x//H/8H/w",
        "ACAD/g//H58eBxwHHA8ADwAeADwA8AHwAeADwAeAHwA+AHgAcABwAHAA//D/+H/w",
        "AAgH/w//H/8fDx4PHg8eHwA+AH4A+APwB+APwB+APwA+AHwA+ADwAPAA//D/+P/w",
        "AEAD/h/+Dz8+BzwHPA8AHgA+ADgAcADgA4AHAA8AHgB8APgA4ADAAOAA/+D/+H/A",
        "A/4P/x//H/8fDx4PHg8cHwAfAD4A+AHwA+AHwA+APwB+AHwA+ADwAPgA//j/+P/4",
        "APgH/g//H/8eHxweHB4YPAA8AHgA8AHgA8AHgA8AHgA8AHgA8ADwAfAB/+H/4P/g",
        "A/4f/h8fPgc8BzwHAB4AHgA8AHgA4AHAA4AHAB8APgB8AHgA4ADAAOAA/+D/+APA",
        "A/wP/h/+H/4fHj4fHD4AfgD8AfgD8APwB+APgB+APwB+APwA+AH9wf/x//n/8D+A",
        "A/4P/x//H/8fDx4PHB8AHwB+APwD+APwB+APwB8APwB+AHwA8AD8wP/4//z/+D/A",
        "APAH/g/+H/8/Pz4fPh4cPgB+APwB+APwB+APgB+APwB+APwA+AH4Af/x//n/8D+A",
        "P/w//H/8/Dz4H3geOBwAPAD8AfgB+APgB+AfwB+APwA8APgA+AD4APw4//z//P/8",
        "A/4P/x+PHgccBxwHAA8AHgA8AHgB8AHgA+AHwA+AHgA8AHgAcABwAHAA//B/+D/w",
        "A/4P/x//Hw8eDx4PHh4APgB+APwB+APwB+APwB+APwA+AHwA+ADgAPAA//D/+P/w",
        "AOAD/gf/D/8f/x8fHx8/PgY+AHwA+AHwA+AHwB+APwA+AHwAeAH4A//z//H/8P/w",
        "AOAD/g//D/8P/w8fHx8fPg4+APwB+AHwA+AH4A/AHwA+AH4BfAF8AX/5f/n/8X/w",
        "A/4H/w//D/8PPw8fDx4PHgA+APwA+AHwA+AHwA+AHwA+AH4BfAF8AX/5f/n/8H/w",
        "AfwH/gf/D/8PHw8ODx4AHgA+AHwA+AHwA+AHwA+AHwA+ADwBeAF4AX/xf/F/8APw",
        "A/gH/A/+H/8f/x8+Hz4fPg48APwB+AHxA+EHwQ+AHwA+AX4BfAF8A3/zf/P/8X/g",
        "AGAD/g/+H/8fvx8fHx8fPgR+APwB/AHwB/AH4B/AH4A+AHwAfAF8Af/5//n/+H/g",
        "AfgD/gf/D/8PHw4eDh4APAB8APwA+AHwA8AHwA8gHgA8ADgAeAB4AX/hf+H/4AQA",
        "A/4P/w//H/8eDxwPCB8AHgA8AHwA+APwB+APwB8APwB8AHgA+AD4wP/4//z/+APg",
        "AwA//D/8//z8PPgfeB8wHwA8APwD+AHgA+AH4B/APwA8AHwA/AD4APw4//z//P/8",
        "AfgH/g//D/8PHw4eHh4APAB8AHgB8APwB8APwB+APgA8AHgAeAB4AX/h//H/8ABg",
        "AfwH/g//H/8fDx4PHg8AHgB+AHgA+AHwA8AHgB+APgB8AHgA8ADwAP/w//j/8AAg",
        "A/wP/g//Hw8eBx4PHB4APgB8AHgA+AHwA8AHgA8AHgA+AHgAcADgAOAA+/D/8F/w",
        "AfwP/x//H/8eDxwHHA8ADwAeADwA+AHwA+AHwAeAHwA+AHgAeABwAPgA//j/+H/w",
        "AfgP/h//H/8eHx4ePh4APgB+APgB8APgB8APgB8APgB8APgB8AHwAf/x//H/8ABg",
        "AeAD/g//D/8P/w+fDx8fPgR+AHwA+QH4B/APwB+AHwA/AH4BfAF/wX/5f/n/+X/w",
        "AfwP/g//H/8fHx8eHh4APgB8APgA8AHwA8AHgA8AHwA8ADwBfAF8wf/x//l/8B/A",
        "A/wP/h/+H/8fHh4eGB4APAD8APgB8APgB8APgB8APwB8AHgA+AH5wf/x//h/8AMA",
        "ABAH/g/+D/8OHg4eDh4AHAA8AHwA+APwB8AHwA+AHgA8AHgBeAF8AX/x//H/4H/A",
        "A/wH/g//HwceBx4GCA4AHgAcADgAcADgAcAHgAcAHgA8AHgAcADgAOAA+4D/8F/g",
        "AHgP/g8fHA8cDhwOGA4AHgAcADgAcADgAcAHgA8AHgA8AHAA8ADgAMAA4AD/4P/g",
        "A/AP/h//H/8fHx8eHh4AHgA8AHwA+AHwA8AHwA+AHgA8AHgBeAF4AX/h//H/4E4A",
        "ACAH/g//D/8f/x8PHAccDwAPAB4AOABwAPAB4APAB4AfAD4AeAB4APAA8AD/+H/w",
        "B/4P/h//Hh8eHhweHB4AHAB8APgA8AHgB8APgA8AHgA8AHAA8ADgAfAB//H/8H/g",
        "AfgH/g//D/8fnx8fHh4OHgA+AHwA+AHwA+AHwA/AHwA+AHwAeAF4AXgBf/H/8X/w",
        "B/4P/w//H/8eBxwHHA8cDwAeADwA8AHwA+AHwA+APwB+AH4A+AD4APng//h/+D/w",
        "H+A//D/8///8P/g/+D/wPyA/APwD+Af4B/gf4B/APwD8APwA/AD8AP/8////////",
        "AfgP/x//H/8eDx4PHg8ADwAeAD4AOABwAcADgAcAHgA4AHgAcABwAHgA//D/+H/w",
        "ANAH/h/+H/8eHh4ePB4cPgB8APwB+APwB+APwB+APwA+AHgA8ADwAfAB/+H/8P/g",
        "A/4f/h8fPAc8BzAHAA4ADAAYAHgA4AHAAcADgA8AHgA4AHAAcADgAMAAwAD/4P/g",
        "D/gf/D//P/8+P3w/fD8cPwB+AHwB/AP4D/APwB+AH4A/gH4AfgA//P////8//w+I",
        "H/g//P/////8//g/+D84PwD8APwB/Af4H+AfgD8APwD/APwA/AD//P///////xgY",
        "AfwD/o//j/+PH44enh6APIB8AHwB+APwA8AHwA+AHgA8AHgAeAB4AH/w//D/8H5g",
        "AQADAAOAB/wH/w//Dx8PDw4eDj4MfB34Gfg/4H/AD4CfAL4APAF8AX9hf/F/8D8w",
        "AEAH/g//Dx8eBxwHHAcADgAeADwAMABwA+AHwAeAHwA4ADgAcABwAHAA//B/+DBg",
        "AwAHAAMAB/4P/x//Hw8eDx4PHB4APgB8AfgB8AfADwAeADwAOABwAPAA//D/+H/w",
        "AwADAAeAB/wP/g//Dx8eHh4eHDwYfBn4Mfgj4A/AH4C+ADwBeAF4AX1j//P/8QAg",
        "B/4f/z+/Pgc8BzwHGB4APgB8APwA+AHgA8AHgB8APgB8APgA4ADAAOAA//j/+GZA",
        "Af4H/w//D/8PDx8PHg8AHwA+AHwA+AHwB+APwB+AHwA+AHwAeAD4AP/4//j/+H/g",
        "ADgD/g//D/8eBxwHGA8ADwAOABwAMABwA8AHwAeAHgA4AHgAcABwAHAA//D/+D/w",
        "A/4f/j8/Pgc8BzwfGB8APgB8APwB+APgB8AfgD8APgB8APgA4ADgAOAA//j/+P/g",
        "AHgH/o//D/8eBxwHGA4AHgA8AHgA8APwB+APwB8AHgA8AHgA8AD4AP/4//j/+BgA",
        "AHgD/w//D/8PDw8PHg8cHgA+AHwA/AHwA/ADwAeAHwAeAHwAeAB4AHgAf/j/+H/w",
        "B/4P/x//Hh8eHjwePB4AfAD8AfgD8AfgD8AfgD8APgB8AHgA8ADwAP/g//D/8ABg",
        "ANjH/sf/z/+Pv48fHh8eHgA8AHwA+AHwA+AHwB+APwA+AHwAeAB4AH/w//D/8H/g",
        "g/6P/4//n/+eDx4PHA8AHgA+AHwA+APwB+APwB8APgB8AHgA8AD4AP/4//j/+BgA",
        "gfzH/8//j/+PH54eHh4APgB8APwB+APwB8APwB+APgA8AHgAeAB4AH/w//D/8E/g",
        "A/6P/8//z//fH98fnh4MPgB+APwB+APwB8APwB+APgA8AHgAeAD4AP/w//D/8P/w",
        "AOAD/gf/D/4f/h4eHA4IHgA8AHgA8AHgAeADgAeADwAeADwAcABwAHAA//D/8H/g",
        "D/wf/j//P/8+PzwfOB4QHgB8APAB4APgA8APgB8APgB4APAA4ADgAOAA//D/8P/g",
        "B/4f/z//P/8/PzwPPA8AHwA+AHgA8AHgA4AHgA8AHgB8APgA4ADgAOAA/+D/+P/g",
        "A/gH/h//P/8+DzwHPAcADgAcADgAcADgA4AHgA8AHgB8APgA4ADgAOAA/+D/+H/g",
        "B/wP/h//H/8fPx4fHB4IHgA8AHgA8AHgB8APgB8AHgA8AHgAeABwAPgB//H/8P/w",
        "AfgH/h//Pz8+BzwHPB8QHwA+AHwA+AHwB8APgB8APgB8APwA8ADgAPAA//j/+H/4",
        "AfgH/h//Pz8+BzwHPA8AHgA+ADgAcAHgA8AHgA8AHgB8APgA4ADgAOAA//j/+ABA",
        "AfgD/h//Hx8+BzwHPB8AHgA+ADwAeAHgAeADwAeAHwA+AHwA+ADgAOAA4AD/4P/4",
        "A/wP/h/+H/8/Hj4eHh4MPgA+AHwA+ADgA8AHgA8AHgA8AHgAcABwAPAA//D/8H/g",
        "AH4A/wcDBgEEAQQDAAMABgAEABAAIABgAMABgAMABgAYADgAcAB4AP/wf/h/8BwA",
        "AOAD/h//P/8+BzwHPA8ADgAeADgAcADgA8AHgB8APAB4AHgA4ADgAOAA//j/+Ofg",
        "AAgH/g//H/8eDx4PHg8MHgAeAHwA+AHgA8AHgA8AHgA+AHgA+ADwAPAA//D/8P/w",
        "AYAD/Af+D/8Pvw+fHh4OHgA8AHwA+AHwA+AHwB+APwA+AHwAeAF4AX/x//H/8AHg",
        "ABgAcAP+D/8f/z8HHgcMDwAeADwAcADgAeADwAeAHwA+AHgA4ADgAOAA/+D/8H/g",
        "H/j//P/8//////g/+D/4Pzj/APwD/Af4B/gf4B/APwA8AHwA+AD4APw4//z//P/8",
        "Af4f/z//Pw4AAgAHPA8AHwA+ADgA8AHgA8AHgA8AHgB8APgA4ADgAOAA//j/+H/g",
        "8/7n/gf/D58PDx8PHg8AHwA+AHwA+AHwB+APwB+APwA+AHwAeAB4AH/5//j/+Afw",
        "8cH3/Of+j/4PHg8fHh4eHgA+AHwA+AHwA+AHwB+APwA+AHwAeAF4AX/z//H/8H/w",
        "AYAD/gf/Dj88BzwHMAcADgAcADgAcADgA4AHAA4AHAB4AHAA4ADAAMAA/+D/4EBA",
        "AfgH/g/+D/8eHx4eHh4APgB8APgB8APgB8APgB8APgB8AHgBcAFwA3/j//H/8Ufg",
        "/YAB+Af+D/4P/x4/Hh8eHgA+AHwA+AHwA+AHwA+AHwA+AHwBeAF4A3/j//P/8X/g",
        "A/wP/x//Hh8cHxweDBwAPAB4APAB8APgB4APgB4APAB8APgA8ADwAf/h//H/8EAA",
        "APgH/A//H/8fPx4eHh4APAB8APgB8APhB8EPgB8APgB+AXwBeAH4Af/h//H/8X/g",
        "A/4H/w//H/8ePx4PDA4AHgA8AHwA+ADwA+APwB8AHwA8AHgAcABwAP/4//j/+AMA",
        "A/4P/w//D/8fHx8eDh4EfgB8APgB8APgB8APxB+APiA+IXwBeAF/gX/x//n/8Efw",
        "AYAH/A/+D/8P/w4+Hh4ePgB8APgB8APgB8APgB8AHgA8AHgBcAF4AX/h//H/4X/A",
        "AHwB/wP/Bw8GBw4HAA4ADAAcAHgA8AHwAeAHwA+ADwA+AD4AeAB/4P/4//z//H/w",
        "/////v/8//j/8P/w/+D/4P+A/wD/APwB/AH4AfgA8ADwBOAE4ATABMAAgACAAIAA",
        "A/wP/w//H/8fPx8fHx4ePgB+APwB+APwB+APwB+APwA+AHgBeAF4A//z//H/8H/g",
        "A/4P/x//Hw8eDx4PHB4APgB+APwB+APgB8AfgD8APgB8AHgA8ADwAP/w//j/8AAg",
        "Af4H/wfvDgcOBw4OBA4AHgA8AHgA8AHgA+AHwA8AHgA8AHgAeAB/4P/4//j/8H/g",
        "AAgD/w//D/8PDx4PHg8AHgAeAHwA+AHwB+APwB8AHgA8ADwAeAB4AH/4//j/8G/g",
        "AfwH/g//HgceBx4OCA4AHAA8AHgA8AHgAcADgA8AHgA8AHgA8ADgAOAA+HD/8APw",
        "AfgH/h/+H/8eHx4eHB4APgB8APgB8APgB8APgB8APgB8AHgA8ADgAfhA/+D/4ABg",
        "AHgH/w//H/8eDxwHHAcADwAeABwAOABwAeADwAeADgAMABgAMABwAHAA+AB/+H/4",
        "AHAH/g//H/8eBxwHHA8ADwAeAD4A/gP4B/AP4B/APwA+AHgAcABwAHAA//D/+H/w",
        "A/4P/w+PDAccBxwPAA4ADAAcADgAeAHwA+AHwA4ADAAYAHgAcABwAHAA//D/+H/g",
        "ADAH/o//z//f/98f3x+eHoQ+gHyA+AHwA+AHwB+APwA+AHwAeAD4AP/w//D/8P/w",
        "AHwD/x//H/88DzwPPA8cHwAfAB4AOAHwA8AHwA+AHwA+AHgAcABwAHAA//j/+H/4",
        "AHgA/gP/Hz8cDxwHGA8ADwAeABwAMABgAcADgAcAHwA+ADgAcABgAHAAf/D/+D/4",
        "AfAD/Af+B/8P/w8fDx4PHgR8AHwA+AHxA+HHwD+AP4A/AD7xfAF8w3/zf/F/8T/w",
        "AP4B/w//H/8fDx4PHh8MHwA+AHwB+APgB8AHwA+AH4A/AD4AOAB/8H/4//h/+AH4",
        "AP4D/x//H/88DzwPHB8QHwA+ADwA+APgB8APwB8AHwA8AHgAcAD4wP/4//j/+AAY",
        "P/z//P/8/Dz4H/ge+BwgPAD8AfgD+Af4H+AfwB+APwD/AP4A/AD8AP/8////////",
        "Af4H/w4PDAMIAwgDAAMABgAcADAAcADAAYADgAcABgAMADgAcADwAMAAwAD4IH/w",
        "APgD/gP/H/8eHxwfPB8AHgA+AHwAeADgAcADgAcAHgA8AHgAeADgAOAA4AD/+P/4",
        "B8A//D/8//z8P/gf+D/wPwA8APwD+AfgB+AH4B/APwA8AHwA/AD8AP/4///////8",
        "AAgH/h//P/8/Bz4HPg8cHwB/AH4A+AHwA+ADwAeAHwA+AHgAcABwAHAA//j/+H/w",
        "APgH/h//P78+DzwHPA8AHwA+AHgA8AHgB8AHgA8AHgAYAHAA4ADgAOAA/+D/+B/g",
        "ADwD/of/z//Pv48fnh6eHgA8AHwA+AHwA+AHwB+APwA+AHwAeAD4MP/4//j/8H/w",
        "AfAH/g//D/8eDxwHHAcADwAOABwA8AHwA+AHwA+APwA+AHgAcABwAHAA//D/+H+A",
        "ANAD/gf+D/8OHg4eDh4MHAA8AHgA8AHgA8AHgA8AHgA+ADwAeAB4AXgBf/H/8H/w",
        "AfwH/h8fDAcABwAGAAYADAAYAHAA4AHAAcADgAMADgAYADAAYABgAMAAwAD/wP/g",
        "AfgH/A/+H/8f/x6+Hh4ePgB8APgB8APhB8EPwB8APgB8AHgB+AP4A//z//P/8f/g",
        "A/4H/w//D/8fPx8fHh4APgB8APgB8APgB8APgB+APgB8AHgBeAH/8//z//H/8AGA",
        "A/4P/x//H/8eDxwHGB8AHwB+AHwA+APwB+APwB+AHwA+AHwAcAD4gP/4//h/+A4A",
        "AAgH/A/+D/8f/h4+Hj4cPgB8APgB8APxB8EPwB+APwB8AXgBeAP/8//z//P/4QOA",
        "B/4f/j+fPAc8BzwGAB4APAA8AHgA4AHAA4AHAB4APAB4AOAA4ADAAMAA//j/+AcY",
        "A/4P/x//H/8+Bz4HPA8cDgAeADwA8AHwA+AHgA8APwB+AHgAcADwAPEA//j/+H/Y",
        "ABgA3A//H/8fHx4eHB4cHgAeAHwA8AHwA8AHgA+AHgA8ADgAeAHwAfAB//H/8P/g",
        "B/4P/w4PDgYeBhwPAB4APgB8APgB8APgB8APgB8AHgA8AHgAYADgAPAA//j/8B/w",
        "DAIMAhwHHAcADwAeAB4AHAB4AHAA4APgB8AOAB4AHgA4AHAAcABwAHAA//B/+D/w",
        "H/j//P/8///8//g/eB8wHwA8APwD+AHgA+AH4B/APwA8AHwA+AD4APw4//z//P/8",
        "AcAH/h//Pw88BzwHPA8AHwA+AHwA+AHgA8AHgA8AHgB8APgA4ADAAOAA//j/+H/g",
        "P/z//P/8/Dz4HzgcADwAPAD8A/gH+B/gH+AfwD8A/wD8APwA/AD//P///////xgA",
        "A/4P/x//H/8eDz4PPg8cHwB/AP4B/gP4A/AH4A/AP4B/AP4A+ADwAPAA//j/+H/w",
        "AeCH/sf+z//P388Pjg6OHoA+gHyA+IHwg+CHwA+AHwA+AHwAeAB/8H/4//D/8HAA",
        "AfwH/w//H/8eDxwPHA8YDwAeADwA+AHwA+AH4A/AP4B/AP4A+ADwAPAA//j/+H/g",
        "A/gH/g/+H/4eHx4fHh4efgB+APwB+APwB8APgA8AHgA8AHgAcABwAHAA/+D/8H/A",
        "gfzH/s//z//PD84Ojh6APoB8gPiB8IPgh8CPgB8APgA8AHgAeAB/8H/4//B/8GAA",
        "AfgH/g//H/8eDxwHHA8ADwAeADwA+AHwA+AHwA+APwB+AHwAeADwAPAA//B/8AIA",
        "AfAD/of+j/+OHp4enh6ePgA8AHwA+AHwA+AHwA+AHwA+ADwAeABwAHgAf/D/8H/w",
        "APgH/h//P/8+DzwHPA8AHwA+AHgAcADgA4AHAA8AHAB4APgA4ADgAMAA/+B/4AIA",
        "AHAH/g/+Hw8cBxwHHAcADgAeABwAMABgAcADgAcAHgA4AHgAcABwAHAA/+D/8DgA",
        "AfzH/sf/z/+PD44Ojh6AHoA+gHyA+IHwA+AHwA+AHwA+ADwAeAB8AH/4f/j/8H/w",
        "P/z//P/+/D/4H/gf+B8APAD8AfgB+APgB+AfwB+APwA8APgA+AD4APz4////////",
        "H/h//H/+/D94Png+eD4APgB8APgB+APwB+APwB+AHwA+AHwAeAB4AHwAf/5//n/+",
        "H/x//n/+eB94D3gPcB8APgB+AHwB+AHwA+APwA+APwA+AHwA+AD4APgA////////",
        "B+A//n/+f/94H3wffB9gPwB+AP4A+AHwA/AHwA+AHwA+AHwAfAD4APwA////////",
    ],
    "3": [
        "P/z//P/+/D/4H+A/4D8APwA/Af4D/Af8B/wAfwA/AB8AP/g/+D/4P/////7//D/4",
        "B+A//D/8//////g/+D/wPwA/AP8H/wf+B/4H/wD/AD/gP+A/+D/4P/////z//D/8",
        "H+D//P////////g/+D8gPwD/AP8H/x//B/8A/wA/AD/4P/g//D////////8//AfA",
        "AfAH/g/+H/8eHx4eHB4cHgAcADwD/Af4B/gAfAA8ADgAOHB48Hnw+fDx//H/4X/A",
        "ABwD/h//Hz88BzwHOAcABwAGAB4APAP8A/wA/AA8ABwAPAA8QDzgPMA4wHj/4H/A",
        "A/wH/h8fDAc8BzwHAAcABgAOABwD/AP8A/wAPAAMAAgAGAA8QDzgMMAwwHj/4H/A",
        "AfwH/g//D/8fHx8fHh4AHgAeAfwH/Af8A/wAfAB9AHwAfXh5ePl8+X/z//F/4D+A",
        "B/8f/z//fh9+B34fPB8AHwA+A/4H/gf8A/wAPAA8ADwAfPh8+HzgfOD8//j/4D/A",
        "A/4f/z//Ph98BzwHOB8AHgAeAH4D/AP8A/wAPAA8ADwAPOB84HzgfOB8//j/4B+A",
        "A/4P/x//Hw8eDx4PHg8AHwAeAB4H/Af4B/wAPAA8ADwAOHB48HjwePD4//D/8D/A",
        "A/wP/h/+P/8/Hz4ePh4AHgA+A/4H/Af4B/wA/AB9AHwAffD58Pnw+f/x//H/4H8A",
        "AfgP/h//H/8fHx4ePB4AHgA+APwH/Af4B/wAfAA8AHgAePB58Hnw+f/x//H/4D8A",
        "A/4f/x8/Pgc8BzwHAAcABgAcABwD/AP8A3wAHAAcADwAPEA84DzAfOB4//h/wAeA",
        "A/4P/x//H/8fDx4PHA8ADwAfAf4H/gf+B/4APgAeADwAPHA88Dz8fP/4//h/4A8A",
        "AAgH/g//H/8fDx4PHg8MDwAfAB4D/gf4B/wAfAA8ADwAPHB48HjwePD4//D/8D/A",
        "A/gH/h//H/8eDxwHHAcABwAGAA4A/Af8A/wAHAAcABwAHHA88DzwPPB8f/h/8D/A",
        "AOAH/h//P/8ODzwHPAcABgAOAB4APAP8A/wAPAA8ADwAGMB84HzAfOBw//j/4B+A",
        "AgAH/B/+H/8f/x8/HB8AHgAeABwB+Af4B/gD+AA4ADgAOAB48HjwePj4f/B/4D+A",
        "B/wP/h//H/8fPhweHB4AHgAeABwB+Af4A/gAOAA4ADgAeHB48HjwePj4f/B/4D+A",
        "AIgH/w//H/8fDx4PHg8ADwAeAD4H/gf8B/wAPAA8ADwAePB48Hjw+P/4//D/4BkA",
        "D/g//D//f/////4/fD88PwB/AH8D/w//D/8AfwA/AD88P34/fj8//z//P/8//A/w",
        "A/4f/h8/PAc8BzwHAAYAHgAeADwD/AP8APwAPAA8ADwAPEA84DzAPOB4/+D/4B8A",
        "BAA//D/8//z8//g/+D/wPwA/AD8D/Af8B/wH/AA/AD8APwA/+D/4P/////z//D/8",
        "H/A//H/+//7//v//f/9//3/+D/8P/g/8D/wP/gD+AH8QfxA/eH94fn/+f/g/+B/4",
        "P/z////////4P/g/+D8APwD/B/8H/x/8B/8A/wD/AD/gP/g/+D/8P////////z/8",
        "AJAH/h/+H/8eHx4eHB4AHAAcADwH/Af4B/wAfAA8ADgAePB58Hnw8f/x//F/wAoA",
        "A/wH/h/fPgc8BzwHAAYABgAcAPwD/AP8A/wAHAA8ADwAfGB84HzgfPj4//j/4D/A",
        "A+AH/w//H/8eBx4HHA8ADwAOAf4D/gf+A/4AfgA+AD4APHg8+Dz//P/4f/h/8A8A",
        "A8AH/w//H/8+Bz4HPB8ADwAOAf4D/gf+A/wAPAA8AHgAfPh8+Hz4/P/4//B/4AYA",
        "H+A//D/8//////g/4D/gPwA/AD8H/wf+B/wH/AA/AB8APwA/+D/4P/////z//D/4",
        "A/gf/j//P/8/Dz4PPg8YDwAfAD8D/gP+AP4AHgAMAAwAGOAw4HzgfOBw//j/4D+A",
        "AcAH/h/+P/8+DzwHPA8ADwAPAB4A/AP8ADwAHAAMAAwAGOAw4HzgfOBw//j/4D+A",
        "A/gP/h//H/8/Dz4PHg8cDwAPAB8D/gP+AH4ADgAMAAwAHHg8+DzwPPh8//j/8D/g",
        "Af8D/wP/Dw8/Bj4PPA8ADwAOAAwAHAf8A/wAPAA8ADwAGOA84HzgfOBw//j/4D+A",
        "AHgA/gAGAAI+Aj4GPA8ADwAOAAwAHAf8A/wAPAA8ADwAGOA84HzgfOBw//j/4D+A",
        "AfwH/wf/D/8PHw8fHh4AHgAeAf4D/Af8A/wAPAA9AD0AfXh5eH34+//z/+F/wR+A",
        "A/wH/h8fHAc8BzwHAB8AHgAeADwD/Af8A/wAPAA8ADwAPOA84HzgfOB4//j/4B+A",
        "AYAD/g//D/8f/x8fHx8eHggeAf4H/gf8B/wH/AB9AH0wfXh9+P39+//7//H/4T+A",
        "A/wH/w//H/8fPx8fHh4cHgAeA/4H/Af8B/wAfAB9AH0wfXh9+P39+//7//H/4T+A",
        "A/gH/A/+H/8f/x8+Hj4ePgw+A/4H/A/5D/kH/QB5AHkweXj5+Pv58//z//P/4T+A",
        "A/wP/h//P/8/Hz4ePh4cPgA+A/4P/A/8D/wA/AB8AH1wffD98Pn5+//7//H/4X+A",
        "B/wP/h//H/8/Pj4eHB4AHgA+B/wH/Af8B/wAfAA8AHwAeHh48Hj9+P/4//B/wA8A",
        "AfwP/h/+H/8fnx4fHB4cHgAeAHwH/Af4D/gH/AB8AHwAfHB98Hnwe/Dx//H/4H/A",
        "A/4P/x+fHgccBxwHAA8ADwAOAF4D/Af8A/wAHAAcABwAHHA88DxwPHA4f/g/8A/g",
        "AAQB/A/+H/4fPx4ePh4+HgAeAD4A/sf8D/gP/AB8AHwAfHB98H3w+/D5//H/4X/A",
        "A/wP/x//H/8fDx4PHg8cDwAPAB8D/gf+B/4APgAeADwAPHA8+DzwPPh8f/h/+B/g",
        "P/z//P/8/D/4H+A/AD8APwA/A/wH/Af8B/4A/wA/+D/4P/g//D//////P/w//Afg",
        "f/x//P/++D74Pvg++D4APgA+Bf8P/g/+D/4APgA+AD4APvg++D74Pvh+//5//D/4",
        "H/x//n/++B/4H/gfcB8AHwAfAB8H/gf+B/8AHwAfAB8AH/gf+B94H3gff/9//h/8",
        "P/x//n/+fj54HngfeD8APwAeAL4P/gf8B/4APgA+AD4APng++D74Pnw+f/5//j/8",
    ],
    "4": [
        "AAbAH8A/gD6AfoD+AfwD/AP8B/wP/B88Hnw8fDz8f/z//P/8P/gA8AHwAfAB4ADg",
        "AAKABwAfAD8APwB/AP4A/gH+A/4Dvgc+Hjw8PHw8f/7//v/+A/wAfABwAPgA+ADg",
        "AAIADwAfAD8APwB+AP4B/gP+B/4GPg4+PDw4OPg4//z//v/+B/gAeABwAHAB4ABg",
        "AA8AHwAfAD8APwD+AfwD/AecBxwfHB48Pnx4eHx8//7//P/8APgA8ADwAfAB8ADA",
        "AA8ADgAeAD4APgB8AHwATAYMBgwMHDw8ODx4PPg8//z//v/8AfwAcABwAHAB4ABg",
        "gA6AH4A/gD6AfgD+Af4D/gP+B/wP/A48HDw4OHh8f/z//P/8f/wAeABwAPAA8AHg",
        "AA+AH8AfgD+AP4B/Af4B/gP8B5wPnA88Hjw+fD58f/7//v/8P/gA+AD4APAA8ADg",
        "AA4AH4A/gH6A/gD+Af4D/Af8D/wPfB94Pvh8+Hz4//z//P/8c/AA8AHwAfAB4AHA",
        "AAIAHwAfAD8AfwB/Af8D/gP+B/4PPg4+PD44PPh8//7//v/+f/gAeABwAfAB8ABg",
        "AAIADwAfAB4APgA+AP4B+AP4BggGGA4cPDw4OPg8//7//v/+APgAcABwAHAAcABg",
        "AA8AHwA/AD4AfgH+Af4D/gf+Bh4OHjw8ODx4PHg8/H7//v/+AfwAcABwAfAB8ABg",
        "AA8ADwAeAD4APAB8AfwBzAIMBhwOHDwcODx4PHg8/D7//v/+AfAAcABwAfAB8ABg",
        "AAYAPgA/AH4A/gH+Af4D/gP8D/wffB58PHx4fPj8//z//v/8f/wA4ADgAeAB4ADA",
        "AAYADwAfAD8AfwD/Af4B/gP+B/wPnA88Hjw8ODh4//z//v/8//wA+ADwAPAB8ADg",
        "AA4AHwAeAD4AfgB+AP4D/gOeBh4OHAwcDBwYODg4eDz4/v/+//gAcABwAHAAcABg",
        "AHwAfAD8AfwB/AP8A/wH/A+8DzwfPD48fj58Pnx+////////f/8AfAA8ADwAPAB8",
    ],
    "5": [
        "B/4P/4//z/7PAJ8AngAeAD/8P/w//D48PDwAPAB8AH0AfXh5eHn4+X/xf/F/4D+A",
        "AHAP/x//H/4cABwAHAA8AD7wP/w//H/8MBwAHAA8ADwAPGA44DjgOOB4//D/8D/A",
        "D/8P/x//HwAeAB4AHgAccB/8H/wf/BwcPBw4PAA8ADwAOHB48HjwePD4//h/8H/g",
        "AEAP/w//H/4cABwAHAAYABgAHfg//D58IBwAHAAcADwAOGA44DDgOOB4//B/4D+A",
        "D/+P/8//3//fgN8AnwCfAD/8P/w//D+8PDwAPAB9AH0AfXh9eHn8+f/5f/F/8T/A",
        "B/8P/w//D/4fAB8AHwAf8D/8P/w//D58PDgAeAB4AHgAeHhw+Pj4+P/wf+A/wA8A",
        "B/4P/4/+n/4fAB4APAA8AD/4P/w//Dw8ODwAPAA8AHgAeHB48Hnw8f/x//F/wAcA",
        "D/8P/x+eHAAcABwAPAA8cD/8P/x//HgcIBwAHAAcADwAOGA44DjgOOB4//D/4D+A",
        "B/8P/4/+nwAeAB4AHgAe+B/8P/4/vjweAB4APAA8ADxgeHB48Hj4eP/4//B/4AOA",
        "D/8P/x+AHAAYABgAGAAYADn4P/w8fDAcABwAHAAcABwAOGA44DDgOOBw//B/4D4A",
        "B/gP/w//j/+f/h8AHAA8MD74P/w//D/8ODwAPAA8AD0AeXB48Hnwef/x//F/4AcA",
        "D/8P/5//n/6fAJ8AHwA/+D/4P/w//D78PHwAeAB4AHgAeHj4+Pj5+P/w/+B/wA+A",
        "B4wf/x/+H/weABwAHAA8ADzwP/w//D/8ODwgPAA8ADgAeHB48HjwePD4//j/8D/A",
        "D/4P/5//n/6fAB4APAA+AD/4P/w//D58ODwAPAB8AH0Affh58Hn4+f/x//H/4D+A",
        "B/8P/w//D/8PAA4AHgAf+B/8P/4//jw+PBwAPAA8ADwAPHg48Hj4+P/4f/A/4A8A",
        "B/8P/w//D/8PAB4AHgAeAB/4H/w//D/+OBwAPAA8ADwAPDA4eDhwePj4//B/8D/g",
        "H/4f/x/+HgAeABwAHAA88D/8P/w//Dw8ODwAPAA8AHgAeHB48HjwePD4//h/8D/A",
        "D/8f/x/+HAAcABgAGAAYAD34P/w+fDgcMBwAHAAcADwAPGA44DjgOOB4//D/4D+A",
        "ADAP/4//z//f/98AnwC/IL/4P/w//D/8PDw4PAA8AH0wfXh9eHn8+f/7f/F/8T/A",
        "B/4P/4//n/8fAB4AHgAeAB/8P/4//j4+PD4APAA8AHwAfHB88Hj4+P/4//D/4D+A",
        "D/+P/8//z//fgN8AnwC/+D/8P/w//D/8PDwAPAB9AH0wfXj9eP/8+//7//t/8T/A",
        "D/4P/4//z//f/98A3wC/8L/8P/w//D/8Pjw8PAh9AH14fXj9eP38+//7//t/8T/A",
        "AGAP/w//n/+fvp8AnwA/YD/4P/w//H/8fHwMfAB8AHwg/Hj4+Pj4+P/4//B/4B+A",
        "D/6P/4//z/7fAJ8AngCeAB/8H/w//D48PjwcPAB9AH14fXj9ePn8+f/5//l/8T/A",
        "D/8P/x/+HgAcABwAHAA8AD/8P/4+PjgeAB4AHgA+ADxwPPA88Dz4eP/4//h/4AQA",
        "D/8P/x/+HgAcABwAHAAcAD/4P/4+fjgeMB4AHgA+ADwAPHA88DzwOPh4//h/+D/g",
        "B/4P/5/+n8CfAB4APgA8ADzwP/g//D/8ODwAPAA8ADwAOGA4cHjwcfBx//H/4H/A",
        "DgAP/x//H+AeAB4APAA4ABwAH/g//HwceBwAHAAcABgAOGA44HjgcOBw8PD/4B8A",
        "B/4P/o/+j/6PAJ4AngAe8B/4H/wf/D58fHwAeQB5AHkgeXh5eHH88f/zf+N/4R+A",
        "A/7H/sf+5/7HAM8AzgCOcI/4D/wP/D48PjzMOQA5ADkYeTx5PHl8eX/5P/E/8Q+A",
        "B/4H/w//D/4OAA4ADgAeAB74H/gf/Dz8PDgAOAB4AHgAeHB4+Hj4cPjwf/B/4D+A",
        "D/4P/w8AHAAcABwAHAAcANz4n/4cHjgeOB4QHgAeADwAPHA88DjwOPh4//h/8D/g",
        "D/wP/x//n/+f/58wPgA+YD/4P/w//D/8PDw4PAA8AD0AfXB5cHnwef/x//F/4A8A",
        "B/8P/w//DwAOAB4AHgAe8B/8H/wf/DwcOBwAHAA8ADhwOHA48Hj4eP/4//B/4A+A",
        "B84H/w8ADgAOAB4AHAAcAB/4H/wePBgcOBwQHAAcADwAOHA4cDhwePB4//h/8D/g",
        "AYAP/4//n/8fAB8AHgAeAB/4H/w//jw+fD4APAA8ADxwfPh88Hj4eP/4//j/8D+A",
        "BbwH/4//z//f/88AnwCf8J/8P/x//D+8PDwYPAA9AH14fXh5eHn/+f/7f/F/4A+A",
        "D/8P/w8+HgAcABwAHAAe8D/8f/5//jwePB4YHAAcADwAPHA88DhwOHh4f/h/+D/g",
        "D/8f/x8APgA8ADwAPAA8AD3wP/w4HjgeMBwAHAA8ADwAPOA48HjgeOB4//j/8B+A",
        "D/4f/x//H/4eAB4AHgAeAD/4P/w//jw8PDw4PAB8AHwAePB48Hj4+P/4//j/8B+A",
        "B/8P/w//n/4fAB8AHgA+AD/wP/w//Dw8eBwwHAA8ADwAfHB88Hnwefj5//n/4T/A",
        "D/4P/w9gHgAcABwAPAA4ADnwP/w8PDgcMBwAHAA8ADwAOGB48HjwcPBw//D/4D8A",
        "D/8PfgwADAAIABgAGAAQ4B/4GPwwHDAcABwAHAAYADgAOOA44HjgcOBw8fD/4AQA",
        "D/4P/5/+n/6/6D8APgA+AD/wP/g//Dw8eDwwPAA8AHwAfXj98Pnw+fv7//P/8X/A",
        "B/8P/w//H/4PAA4ADgAOAAwADHAP/B/8OBwAHAA8ADwAPHg4eDj4ePz4f/B/4B+A",
        "D/8P/4/+nwAeAB4AHgAccB/8H/wcPDw8ODwQPAA8AHwAfHB88HjwePD4//h/8D/A",
        "Bj4P/5/+n/6eAB4APgA8AD/wP/g//Hx8fDx4PAB8AHwgfXD98Pnw+fv5//n/8X/g",
        "B/4P/w/+D/wOAA4ADgAMAAwAHfg//D/8fDwAPAB8AHgAeHhw+HD4eP/w//B/wB8A",
        "AAIAAx//H/8eBxwAOAA4ADgAPPh//nweeA4wDgAMABwAHAAQ4DDgMOBw//B/4A8A",
        "B4AP/x/+n/4eAB4AHAA8ADzwP/g//D/8PDw4PAA8ADwAfHB48HnwefD5//H/8X/g",
        "B/8H/x8AHgAcABwAHAAcADz8P/4+fjweAAYAHgAeABwAHAA8YDjgOOA4//h/4AcA",
        "BAAPwB//H/4eAB4AHAAcADzwP/g//D/8PDwwPAA8AHwAeHB48HjwePB4+fD/4D/D",
        "BAAP/h//H/4eAB4AHAAcAD3wP/w//D/8ODwAPAA8AHwAePB48HjweP/4//B/4AGP",
        "AYwf/x/+H/weABwAHAA8AD/4P/w//Dw8ODwAPAB8AHgAePB48HjweP/4//D/4A+A",
        "AY4f/x/+H/weABwAHAA+8D/8P/w//Dw8MDwAPAB8AHhwePB48Hjw+P/w//B/4CAA",
        "B84P/x/+H/weAB4AHAAeAD/4P/w//D48GDwAPAA8ADwAPHg8eDh4eH/4//h/8AfA",
        "A/wP/x//P/4/AD4APgA/ED/8P/4//n/+MBwAHAAcADwAPGA44DDgOOBw//D/4D+A",
        "A/8H/x+AHwAeAD4APgA+/D//P/8/fzwfOB4AHgAeAD4APmA84DjgPOB4//j/4D+A",
        "AAIP/w//H/8fAB4AHgAeABxwH/wf/h/8PBw4PAA8ADwAfHB48HjwePj4//j/8D/A",
        "A/8H/wcAHgAeABwAHAAceBz+H/4cPjgeOB4AHgAeAD4APmA84DjgPOB4//j/4D+A",
        "Af4H/4//n/6fgJ8AHwAfEB/8H/4f/j/+GBwAHAAcADwAPDA4eDBwOPh4//B/8D/g",
        "B/+P/4//jwCPAI4AngAecB/8H/wf/BwcHBwAPAA8ADw4PHg8eDz4eH/4f/g/8ACA",
        "B/8H/w/+DgAOAA4AHgAeeB/8H/w//DweGBwAHAA8ADwAPHA4eDhwOPj4f/B/8D/A",
        "B/4P/w//D/4OAB4AHgAfAB/4P/w//D/8PDwAPAB4AHgAeHBweHBwcPjw//B/4D/A",
        "A/8P/x//H/4eABwAHAA8AD/4f/x//n/8OBwAPAA8ADwAPGA44DjgOOBw//D/4H+A",
        "D/4P/x/+HgAeABwAPAA84D/4P/w//Dx8ODwwPAA8ADwAePB48HjwefD5//H/8X/h",
        "D/4f/x/+H/4eAD4APAA+AD/wf/h//H/8ODgAeAB4AHgAeGBw4HDgcODg/+D/wH+A",
        "ABwf/z//P/48ADwAOAA4AHzwf/h//H/8eDwgPAA8AHgAeGB44HjgcPBw//D/4B+A",
        "B/4P/x//H/4eABwAHAAc8D/8P/w//Dw8EDwAPAA8ADx4PPw4/Hh//H/4f/g/8AkA",
        "BYAP/w//n/8fAB4AHgAeAB/4H/w//jw8PBwAHAA8ADwAfHB48HjweP/4//B/4BMA",
        "D/8P/p/+n/weADwAPAA8AD/wP/g//Dh8OHgAeAB5AHkA+XDz8PPw8//j/+N/wR8A",
        "B/8P/w4ADAAYABgAGAAYABhwH/g4HHAOIAwACAAIABgAGAAYABDAEIAQwDD2cH/g",
        "B/4f/w//HwwcABwAHAAcAD7wP/w//H/8ABwAHAA8ADwAOGA44DjgOOBw//D/4D/A",
        "BAAP/x/+n/4eAB4APAA8AD/4P/w//Dx8ODwAPAA8AHwAeHB58Hnw+f/x//F/4AEA",
        "B/8H/x8ADgAMAAwADAAIABh4P/48PjgeEB4ADgAOAA4AGAA8QDzgMOAw4Dj/+H/g",
        "D/8P/w/iHwAeAB4AHgAe8D/8P/w8PDwcODwAPAA8ADxwfHh48HjweP/4//B/4BAA",
        "DgAOAA4ADgAOAB8AH/4//z//fA84BwAPAA8AHwAfAB9wHvAe4B7wPvA8//j/8D/A",
        "BAcH/w8CHwAeAB4AHgAccB/8H/wf/jw8PBw4PAA8ADwAeHB48HjwePD4//h/8H/g",
        "AAYH/4f+jw6fAJ8AngCeAB/8P/w//D48PDwAPAA8AH0AfXh5eHn4+f/xf/F/4D+A",
        "H/4f/x/+HgAcABwAHAA98D/8P/w//Dw8MDwAPAA8AHhwePB48Hj4eP/4//B/4AGA",
        "AP8H/wYAHAAeAB4AHAAcAD78P/4efhgeAB4AHgAeAB4AHgAY4DjgOOA4//h/4AeA",
        "A/4f/x//H/4cABwAHAA8AD/wP/g//D/8ADgAeAB4ADgAOAAw4GDgYOBg/+B/wA8A",
        "AIAP/x//H/8f/x4AHAA8AD/wP/g//D/8ODgAOAB4AHgAOAA44GDgYOBg/+B/wA8A",
        "B/8P/5//nwCeAB4AHAAcAB/8P/w+/DwcABwAHAA8ADxweHB48HjweP/4//B/4AIA",
        "Af8P/5////7/AL4APgA8AD/4P/x//Hx8eDwAPAA8AHxw/fD58Hn4+//7//H/4H+A",
        "D/8f/5//nwCeAB4AHgAccB/8H/4//nw8ODwAPAA8IDxwfPB48Hj4eP/4//D/4A8A",
        "D/8f/5//v/+/EL4AvwA/8D/8P/w//D58ODwAPAA8AHwAeHh58Hn4+f/x//H/4D+A",
        "D/wf/5/+/////7/8PgA/4T/5P/0//T/9PH04fQB5AHsA+3D78PP48//z/+P/wT+A",
        "BgAPgA8AD4AXnh//D/4P+A/ADDAMeAz8HBw4HBAcABwAPAA8MDxwOPBw//B/wB8A",
        "B/6P/8/+z/7fAJ8AnwC/+D/8P/w//D/8PDwYfAB8MH14/Xj5+vn/+f/xf/E/4AGA",
        "AIAH/x//D8YOAA4ADgAIABw4P/w//j/+OB4AHgAOAB4AHGA84DDgPOB8//h/4B/A",
        "B/4P/w/+DwAOAB4AHgAccB/8H/4//jw+ABwAPAA8AHxwfPh48Hj6+P/4//D/4D+A",
        "D/8P/x//HwAeAB4AHgAcAB34H/5+PnweeBwAPAA8AHxwfPh48Hj6+P/4//D/4D+A",
        "AGYP/x//P/4+ADwAPAA8AD3gP/g//D/8ODwwPAB8AHgAePB48HDwcP/w//B/4AQA",
        "B/8P/w/+HwAeAB4AHAAcAB34H/wePBgcABwAHAA4ADhgOHB48Hj4eP/4//D/4D+A",
        "B+4P/w+ADwAeABwAHAAcAB3wH/gcHBgcABwAHAAYADgAOGB48HjweP/4//B/4AGA",
        "B/4P/x//H/4cABwAHAAYABgAPfg//D/8eBwwHAAcABwAPAA8ADjgMOA44HD34BwA",
        "D/8f/x//H/8eADwAPAA/8H/8f/x//nw8cBwAPAA8ADwAPPA44Hjw+P/4//B/4AgA",
        "A/8H/wcABgAMAAwADAAIAAh4D/4MHhgGEAQABAAOAAgACAAMAABgAGAA4Dh4+D/g",
        "BaAP/x//H/8eAB4APAA8AD/4P/g+/Dx8GDwAPAA8ADwAPHB88Hnw8f/z//H/4BwA",
        "DAACAAHAAPwP/g//DwccABgAGAAYABj4PDwwHAAcABwAHAA4QDjgMOA44DD/4B4A",
        "B/8P/w4ADgAOABwAHAAccB/8H/4YHjAeABwAHAAcABwAPOA48DjgeOB4+/h/8B+A",
        "B/6H/8//z/7PDM8AnwC/eD/8P/w//D48PDwAPAB9AP0A/Xj9+P3/+//7//t/8Q/A",
        "BZ4H/4//z/zPAI8AngCeAB/8H/wf/Dw8PDwAPAA8AHwAfTh5eHn4+f/5//E/4A+A",
        "AP4P/w//D/4OAB4AHAAcABz4H/w//D/8OBwAHAA8ADwAPHA48DDwePj4//B/4D+A",
        "D4IP/8//3//f/t8AnwC/ED/8P/w//D58PDwQPAB8AHx4fHj5+Pv/+//7f/F/4AGA",
        "D/+P/8//3/7fAJ8AngCe+B/8H/w//D48PDwAPAB8MHx4/Hj4+Pn/+f/5f/B/4AGA",
        "B/+P/8//z//fAJ8AnwCf+D/8P/w//D48PDwAPQB9AH14/Xj/ePv/+//7f/E/4AOA",
        "A/8H/wf/D/4ODA4ADgAf+B/4P/w//D74PHgAeAB4AHgAeHhw+HD48P/w/+B/wBwA",
        "B+aH/8//j/+PAI4AngCcAB/4H/wffD4cGBwAHAAcADwAPHg8eDz4OH/5f/E/4AGA",
        "B8cP/w+AHwAOABwAHAAcABz4H/wcPBgcEBwAHAAcADgAOHA48HjwePB4/vB/4D/A",
        "AH4H/w/+DgAMABwAHAAYABhgPfw//D/8ABwAHAAcADwAOGA44DjgOOB4//D/4D+A",
        "D/4P/5//n/6fAD4APgA8AD/4P/w//D/8PDw4PAA8ADwAOHB48Hnwcfjx//H/8X/A",
        "A/8H/wcADgAMAAwADAAIABz8P/44PhAeAB4AHgAOAAxgGOA44DDgPP/8f/wB+ADA",
        "B/4P/g4AHAAYABgAGAAYABn4P/w4fBAcABwAHAAcABhgOOAw4DjgP//4f/gD8AHg",
        "Bs4P/x/+H/4eAB4AHgA+AD/4P/w//D/8PDw4PAA8ADwAPHh8eHz4fP/8//j/8D/g",
        "A/AP/w/+H/AeABwAHAAcABgAPfg//D/8MBwAHAAcADwAOGA44DDgOOAw//D/8D/A",
        "B/8H/wcADgAMAAwADAAIAA74H/4+HjwGGAYABgAOAA4AHgA8ADBgMOAw4Dj/+H/g",
        "B/8P/x//H/8eAj4APgA/AH/8f/5//n/+eD4APgA+ADwAPPA48DjgOOB4//D/8D/A",
        "//7//v/++AD4APgA+AD4AP/8//7//vge+B4AHgAeAB8AH/g/+B/4H/gf//5//j/4",
        "f/5//n/+eAB4AHgA+AD54Pv+//////wfeB94HwgfAB8IH3wPfB94H3gff/9//h/+",
        "D/6f/5/8HgAeAB4AHgA8AD/4H/w//Dw8ODwwPAA4ADgAeHB48Hjg+PD4//D/4H/A",
    ],
    "6": [
        "AfgP/h//H/8eHx4ePB48ADwAPuA/+D/8P/w8fHg8eDh4ePB48Hjw+P/w//D/4B8A",
        "AGAD/g//Hw8cBxwHHAYYADgAOAA84D/4PDxwHHAccBxgOGA44DjgOOBw//D/4B+A",
        "A/4P/x+fHAccBxwGGAAYADgAOGA/+D/8PDx4HHAccBxgOGA4YDDgOOAw//D/4D+A",
        "AfgH/w//H/8fDx4PHg8eAB4AHHA//D/8P/w8PHg8eDx4OPh48Hjw+P/4//D/4AkA",
        "A/wP/5//n/+fHx4ePB48ADwAP+A/+D/8f/x8fHg8eHx4fPh58Hn4+f/x//H/4D+A",
        "AHAD/gf/D/8PDw4HDgYcABwAH/gf/D/8Pjw8HDg8ODx4PHg8+Hj4eP/w//B/wAQA",
        "AHAH/g//H/8eDxwHHA84BDgAOAB98H/4fnx4PHA8cDxwPOA44DjgOPBw//D/8H/A",
        "AfgH/g//n/+eHh4eHB48DDwAPOA/+D/8P/w8PHg8eDx4fHh48HjwefD5//H/8X/g",
        "A/4P/5//Hw8eDx4PHg4eABwAPHA//D/8P/w8PHg8eDx4eHh48HjwePD4//j/8H/g",
        "AJgH/g//n/+fH54fPh48HjwAPOA/+D/8f/x8/Hg8eHx4fPh48Hn4+f/x//H/4D+A",
        "B/4P/5//v/+/Pz4/Ph4+DjwAPvA/+D/8P/x8fHg8eHx4fPh48Hjw+P/w//D/4D+A",
        "AfwH/w//D/8fDx8PHg4eAB4AH/g//D/+P/48PDw8ODx4PHg8+Hj4+P/4//B/4A4A",
        "AfwH/w//D/8PDx4PHg8eBh4APgA/+D/8P/w8PDw8PDw4PHg8cDhwOPh4//B/8D/g",
        "AfwH/o//z//PH58enh4eAD4AP/A/+D/8P/w+fDg8eDx4fHh8eHj8+P/4//B/8B/A",
        "AHgH/g//H/8eDxwHHAcYADgAOAA5+D/8Pfx4HHAccDxgOGA44DjgOPB4//D/4D+A",
        "A/4P/w//Hw8eDx4PHgYeABwAH/g//D/8PHw4PHg8eDh4eHB48Hjw+P/4//B/4AOA",
        "B/wP/5//n/+/Hz4fPh48DDwAP/A/+H/8f/x+/Hx8+H34/fh98Hn4+//7//H/4D+A",
        "A/wP/p//n/+fH54ePh48DDwAPvA/+D/8P/x8/Hh8eHz4fPh88Hjw+P/4//D/8D/A",
        "AfiH/o//z//PH58enh4eAB4AP/A/+D/8P/w8PDg8OHw4fHh5eHn4+X/xf/N/4x+B",
        "B/4P/h//Hg8cBxwPGAAYADgAOHA9/D/8fHxwPHAccDxgOGA44DjgOOBw//B/4D/A",
        "A/yH/8//3//fn98fnh6eAD4AP/A/+D/8P/w+fDx8eHx4fHh9eHn8+f/7f/N/8x/D",
        "AfyH/o//z/+fH58enh4eAD4AP/A/+D/8P/w8fDw8eH14fXh9ePn8+3/7f/F/8R+A",
        "B/4P/x//Hg8cDxwPPAA4ADgAP/h//H/8f/x4PHA8cDxwPPA44DjgOOB4//D/4D/A",
        "B/gf/B/+H/8fPxwfPB48DDgAOAA58D/4fvh4OHA4cHhwcGBw4HDgcPDw/+D/4D+A",
        "B/gf/h//H/8fHxwPHA88BjgAOAA58D/4PHxwHHAccDxgOGA44DjgOPB4//D/4D/A",
        "AMAH/w//H/8fDx4HHg8eBhwAHAA//D/8P/w8PHw8eDxwfHB48HjwePD4//j/8H/g",
        "A/iP/A/+D/8PPw4fHh4cDBwAHAAd+D/4P/g8ODg4eDh4eHhweHD4cPjw/+B/4D/A",
        "A/4H/w//H/8cDxwHHAccADwAPAA/+H/8fHx4PHAccDxwPPA44DjgOPB4//D/4D+A",
        "w/7H/8//j/8fPx8fHx4+DD4AP/A/+D/8P/w+fDw8fHx4fHh8eHh8+P/4//B/4D/A",
        "Af4D/wf/D/8ODw4HHgAeAB4AH/g//D/8Pvw8PDg8eDx4PHg88Hj4+P/4f/A/4AYA",
        "AGAH/g//H/8cDxwHHA8YABgAGAA58D/4OHxwPHAccDxwOOA44DjgOOBw//B/4BwA",
        "A/wP/x//H/8eDzwPPA88BjwAfAB/+H/8f/x4PHg88DzwPPA88HjwePD4//j/8H/A",
        "A/6P/8//3//fP98fnx6+Dr4AP/A/+D/8P/w+fDx8fHx4fHh8ePz8+P/4//B/8D+A",
        "A/wH/g/+D/8fHh8eHh4eAD4AP/g/+D/4P/g8eHh4eHh4eHh4+PD48P/w/+B/wAYA",
        "AfgH/g//H/8eDxwPHA8YBjgAOAB98H/8f/z4PPg8+DzwPPA84HjgfOB4//j/8D/A",
        "AHAH/g//H58eBxwHHA8YBjgAOAA4AH/4f/x4PHAccDxwPGA4YDjgOOB4//D/4D/A",
        "APyH/4//z/+fD58Pnw+eAB4APvg//D/8P/w+PDw8PDw8PHw8fHz8fP/4f/l/8B/g",
        "APAD/gf/D/8PDx4PHgYeAB4AH/gf/B/8Pvw4PDgceBx4OHg4+Hj4+P/4f/A/4AGA",
        "AfAH/g//H/8eDxwHHAccADgAOAA/+D/8PfxwPHAccBzwOPA44DjgePD4//j/8D/g",
        "AfAH/g//H58cDxwHHAcYABgAOAA88D/8OHxwHGAcYBxgOGA44DDgMOBw//D/4D/A",
        "Af4D/w//H/8cDxwHGAcYAxgAOAA48D/4OHxwPHA8cDxgPGA44DjgOOB4//h/+D+A",
        "AHgD/gf/D/8PDw4HDg8eBB4AHgAf8D/8P/w8PDgcODx4PHg4cDhwOPhwf/B/4B+A",
        "H/h//n//+B/wHvAe8A/wAPAA+AD//P/+//74Hvge+B74Hvge+B74Hvge//9//j/4",
        "H/w//H/8eB54HngeeA54AHgA//j//P/+///8P/w//D/8Hvwe+B74Pvg+//5//j/8",
    ],
    "7": [
        "P/x//3//f//8fvx++HwA/AD4AfgB8APgB+AH4AfAD4EfgR8DPwA/AH4AfAD8AHgA",
        "P4B//3/+f/74PvA+4DjAOAB4AHAB8AHwA+AD4AfAB8APgQ8BDwAeABwAfAB8AHgA",
        "EwA//3//f/98H/g++D4AfAD8APwB+APwA/AD4AfAD8APgB+AHwA/AH4AfgB8AHgA",
        "F4B//3//f59wD/AO8BwAHAA4AHgA+ADwAfAB4AGAA4APgA+ADwAPAB4AfgB+ABgA",
        "f/9////////4f/A+4D7geAB4APAB8APwA+AD4AfAD8APgQ8BHwAeAH4AfAB8AHgA",
        "f/5//3/////4P/A+4DhAeAB4APgB8AHwAeADwAfAB4APAA8ADgAeAB4AfAF8ATgA",
        "P/9//3//f/9+f/w+/H5weAB8APgA+ADwAeABwAPAA4AHgAeABwAPAA8APgE+ARwA",
        "Pgx//n//f/54PvA+4D5AeAB4AHAB8AHwA+AD4AfAB8APgA8ADwAeAX4BfAF8AXwB",
        "HAb/////+//4Hvg+8D4APgA+AHwAfAD8APgA+AD4AfAD8APgA+AD4APgB+AHwAfA",
        "AAN//3////94HngeeD4APgA+ADwAfAD8APgA+AD4AfgB8AHwA/AD4APgA+AH4AfA",
        "f/5//3//+B74HvgecD4AfAB4AHgA+AHwA/AD4AfAB4AHgA+AHwEeAT4BPgF8AXwA",
    ],
    "8": [
        "AfwH/4//n/8fDx4PHg8eHx4eHj4f/B/8P/x8PHg8eHx4fPB48Hj4+P/4//D/4BmA",
        "A/4f/x+/Pgc8BzwHPAc8HjwePjw//D/8PPx4PPg84DzgPOA84DzAPOB4//j/4B8A",
        "AfwH/o//z//PH54eHh4+Hj48P/wf/B/8P/w+fDw8PHx4eXh5+nn/8f/xf+E/gAwA",
        "AOAH/h//P788BzwHPA8YDzAOOB48fD/8PHx4PPA88DzwGOA84HzgPOBw//j/4DwA",
        "APwH/x//H/8fDx4PHg8eDxweH/4f/B/8Pnw8PHg8eHxwePB48Hjz+P/4//A/wAwA",
        "gfjH/s//j/8fHx8fHh4+Hj4eP/wf/B/8P/w+fHg8eDx4eHh4ePh4+H/w//B/4B+A",
        "A/gf/h//P/8+Pz4PPg84D3wP/h5//n/+f/78fvg+8D7wHPB84HzgfOBw//j/4H+A",
        "AfgH/h/+P/8+DzwHPA84D3wPfB5//H/8f/z4fvA+8DzwGOB84HzgfOBw//j/4D+A",
        "ADAH/g//H/8fDx4PHg8eDx4fHh4f/h/4P/g8fHg8eDx4fHB48HjwePD4//j/8D/A",
        "AHgD/gf+Dj88DzwHPA8YDzgPPAw/HD/8P/x4PPA88DzwGOB84HzgfOBw//j/4D8A",
        "A/yP/p/+H/4fHx4ePB48Pjw+Pn4//D/8P/x8/Ph8+Hz4fPB48Pjw+P/w//D/4D+A",
        "A/4P/4//Hw8eDx4PHg8eDh4eHh4f/B/4P/x8PHg8eDx4eHh48HjwePj4//j/8H/A",
        "A/gP/p//n/+fHx4ePB48Pjw+P3w//D/4f/x8fHg8eH34efB58Hjw8P/w//D/4D8A",
        "APgH/h//P/8+BzwHPA8YDzwPPB4//D/8P/x4PPA88DzgGOA84DzgfPB8//j/4D+A",
        "AfwP/p//n/+fH54evB48Hjw+P/4//j/8f/x//Px8+Hj4ePB48Hjw+P/w//D/4D+A",
        "AOAH/A/+Dz4eHhwOHA4cHjwePn8//n/8f/x8OHg4eDhwOHA4cHhweHBw//B/4B+A",
        "AcAP/B/+Hj48DjgOOA44HngefP9//v/8//z4OPA48DjgOOA44HjgeOBw//D/4D+A",
        "A/4H/x8/PAc8BzwHPB84Hzw/P/4//n/8f/x4PPgc+DzgPOA84HzgfOB4//j/4D+A",
        "AfgH/o//z//fH58enh6eHj4+P7wf/B/8P/w+fDg8eHx4fXh5eHn4+f/xf/F/4B+A",
        "AfyH/8//z//fv98fnx6+Hj4+P/wf/D/8P/w+fDh8eH14fXh5ePn8+f/7//F/4T+A",
        "A/4P/x//H/8fDz4PPA88Dz4fP/4//j/+P/58PngeeDx4PHg88Dz8fP/4//h/8AYA",
        "AP4H/4//z/+fD58Pnw+eDx4fH74f/h/8P/w+PDw8fDx8PHw8eHz4/P/8f/h/8B+A",
        "A/wH/h8fDAc8BzwHOAYQBhAMOBw//D/4P/gwHHAMYAhgGOA84DzAPMAwwDj/4H/A",
        "P/x//n///B/4H/gf+B/4H/gf/B9//j/8///4H/gf+B/4H/gf+B/4H/gf//9//h/8",
        "H/w//n/+/B/8D3wPeA94D3gPeB9//n/+f/94H3wffB94H3gffB94H3wff/8//h/8",
    ],
    "9": [
        "AfwH/4//n/8fDx4PHg8eHx4fPB4+Hj/+P/wf/Ac8ADwAfHB48Hj4eP/4//D/4B+A",
        "ACAH/g//Hx8cBxwHHAcYDhgOOA44DjgMP/wf/AAcABwAOGA44DDgMOBw//D/4B+A",
        "A/gH/p//n/8fHh4ePB48Hjw+PDw8PD/8P/wf/AZ8AHwAfHB58Hnw8f/x//N/4x8A",
        "AfyH/o//z//PH58enh4eHj4ePhw+fD/8P/wf/A98AHwAfTh5eHn4+X/xf/F/4B+A",
        "AHgH/g//H/8eDxwPHA88DzwOOA44DngcP/wf/AA8ADwAPGA48DjgOPB4//D/8D+A",
        "AMAH/w//H/8fDx4PHg8eHx4ePB48Hj/8P/wf/AQ8ADwAPHh48Hj4eP/4//B/4BAA",
        "A/gP/p//n/+fHx4fPh88Pjw+Pj5//v/+P/x//B/9AH0AfXh58Hnw8f/x//H/4D+A",
        "ADgH/g//H/8eDxwPHA88DzwOfB58H/////4//AQ8ADwAPGA44DjgOOBw//D/8D/A",
        "APAH/w//H/8fDx4PHg8eDx4fHB48Hj48P/wf/A/8ADwAOHB4+HjwePD4//j/8H/g",
        "A/wP/5//n/8/Hz4fPh48Hjw+PD4+fD/8P/w//AB8AHwAfXh58Hnw8f/x//H/4D+A",
        "A/4P/w//Hw8eBx4PHg8eDhwOPB48Hj/8P/wf/AAcADwAOHA48HjwePD4//h/8H/A",
        "A/6P/8//3//fn98fnx++Hj4ePh4+fj/8P/wf/A/8AHwwfHh9eHn8+//zf/N/4z+D",
        "Af4H/w//D/8Pjx8PHg8eHx4ePB4+Hj/+P/wf/A98ADwAPHA8cHj4+P/4f/A/4AYA",
        "Af6P/8//3//fH58enh4eHh4eHjw+PD/8P/wf/Af8AHw4fHh5ePn/+X/7f/M/4wgB",
        "A/gP/g/+H/4eHhweHB48HjgeOD88Pn/8//w/+B/4AHhAeOBw4HDgcODw/+B/4D+A",
        "A/4P/5//v/+fHx4ePB48Pjw+PDw8PD/8P/w//A/8AHwAfHh98Hnw8f/x//P/4z+D",
        "AfgH/g//H/8eDxwHHA8cDxgPOA84H35+f/w//B/8AHwAOOA44DDgOOB4//B/8D/A",
        "AHAH/g//H58eDxwHHA8YDhgOGA44DjwcP/wf/AA4ABgAOEA44DDgOOB4//B/8D/A",
        "Af6H/9//3//fH58enh4eHh4eHhw+PD/8P/wf/A/8AHwAfDh9eHn4+X/xf/t/8z/D",
        "AHAD/g//D/8cBxwHHA8YDhgOOAw4DDgcP/wf/AA8ADwAPGA44DjgOOBw//B/4B4A",
        "H/w//n//eB94D3gPeA94D3gPeA94D3//f/8//wAfAA8gH/gf+B/4H/wff/9//h/8",
    ],
}

_CACHE: dict[str, np.ndarray] = {}  # char -> (variant, GLYPH_H, GLYPH_W) bools
_FLAT: list = []  # every template as one (N, GLYPH_H*GLYPH_W) array, plus labels


def _templates():
    if not _CACHE:
        for ch, variants in GLYPHS.items():
            _CACHE[ch] = np.array([
                np.unpackbits(np.frombuffer(base64.b64decode(v), np.uint8),
                              count=GLYPH_H * GLYPH_W).reshape(GLYPH_H, GLYPH_W)
                for v in variants], bool)
    return _CACHE


def _flat_templates():
    """All templates stacked flat, so one glyph is classified in one pass
    instead of a Python loop over several hundred bitmaps."""
    if not _FLAT:
        chars, rows = [], []
        for ch, variants in _templates().items():
            for v in variants:
                chars.append(ch)
                rows.append(v.ravel())
        _FLAT.append(np.array(rows, bool))
        _FLAT.append(np.array(chars))
    return _FLAT[0], _FLAT[1]


MAX_DIST = 0.22    # fraction of the GLYPH_W*GLYPH_H cells that may disagree
MIN_MARGIN = 0.04  # best must beat runner-up by this much, else it is unknown
STRONG = 0.05      # a near-exact match stands whatever the runner-up does


_SEEN: dict[bytes, str | None] = {}  # glyph bits -> verdict, within one process


def classify(glyph) -> str | None:
    """Nearest template by Hamming distance, or None if unsure.

    Memoised on the glyph's bits: a frame is thresholded several ways and the
    same digit comes out identical in most of them, so without this the same
    comparison against every template runs again and again.
    """
    key = np.packbits(glyph.ravel()).tobytes()
    if key in _SEEN:
        return _SEEN[key]
    verdict = _classify(glyph)
    if len(_SEEN) > 20000:
        _SEEN.clear()
    _SEEN[key] = verdict
    return verdict


def _classify(glyph) -> str | None:
    rows, chars = _flat_templates()
    if not len(rows):
        return None
    dist = (rows != glyph.ravel()).sum(axis=1) / glyph.size
    i = int(dist.argmin())
    best, ch = float(dist[i]), str(chars[i])
    if best > MAX_DIST:
        return None
    other = dist[chars != ch]
    second = float(other.min()) if other.size else 1.0
    if best > STRONG and second - best < MIN_MARGIN:
        return None
    return ch


SEPARATORS = "/"
GROUP_GAP = 6       # px at 2560 scale; digits of one number sit 0-4 apart
HEIGHT_TOL = 0.25   # a step in glyph height also starts a new number


def _groups(glyphs):
    """Split (box, char) pairs into the numbers they belong to.

    Digits of one number sit shoulder to shoulder and share a height. A
    separator, a wide gap, or a step in height starts a new number. Height
    matters because the "/" between current and max hp is thin enough to drop
    out at 1280 wide, while the size difference between the two never does.
    """
    out: list[list[tuple]] = []
    brk = True
    for box, ch in glyphs:
        if ch is not None and ch in SEPARATORS:
            brk = True
            continue
        x, _, _, h = box
        if not brk and out:
            px, _, pw, ph = out[-1][-1][0]
            brk = x - (px + pw) > GROUP_GAP or abs(h - ph) > HEIGHT_TOL * max(h, ph)
        if brk:
            out.append([])
        out[-1].append((box, ch))
        brk = False
    return out


def _glyphs(mask, size=TEXT_SIZE, **kw):
    """(box, char) left to right, dropping marks too wide to be a digit —
    the weapon icons that share the ammo region, mostly."""
    out = []
    for b in _segment(mask, size, **kw):
        if b[2] <= b[3]:  # width <= height
            out.append((b, classify(_normalise(mask, b))))
    return out


def _number(group) -> int | None:
    chars = [ch for _, ch in group]
    return None if any(c is None for c in chars) else _int("".join(chars))


def read_numbers(frame, box, floor=115) -> list[int | None]:
    """The numbers in a region, left to right. An entry is None when that
    number has a glyph the classifier will not commit to."""
    mask, _ = _mask(crop(frame, box), _scale(frame), floor)
    return [_number(g) for g in _groups(_glyphs(mask))]


def _int(text) -> int | None:
    return int(text) if text and text.isdigit() else None


# --- readers --------------------------------------------------------------

# Current hp is right-aligned against the "/" and max hp starts just after it,
# both at fixed offsets in the region (2560 scale). Checking the two numbers
# land there catches a partial read, where a digit was lost to the background
# and the remaining ones would otherwise be handed on as a plausible number.
HP_CUR_RIGHT = (140, 156)
HP_MAX_LEFT = (166, 182)
HP_CUR_BAND = (80, 158)    # every glyph of the current number falls in here
HP_MAX_BAND = (164, 228)


def _lost_digit(mask, box, side):
    """True when tall ink sits just outside a number: a digit the background
    swallowed. Without this a "250" whose first digits merged into a bright wall
    reads as a well-formed 0, which is the worst kind of wrong. Thin scenery
    streaks do not count — only columns filled like a digit stroke.

    Current hp is right-aligned, so it loses digits on its left; max hp is
    left-aligned, so it loses them on its right.
    """
    x, y, w, h = box
    if side == "left":
        band = mask[y:y + h, max(0, x - 45):max(0, x - 3)]
    else:
        band = mask[y:y + h, x + w + 3:x + w + 45]
    return band.size > 0 and int((band.sum(axis=0) >= 0.5 * h).sum()) >= 3


def _sole_occupant(groups, group, band):
    """True when `group` holds every glyph that falls inside `band`. A second
    group in the same band means the number broke apart and what is left is a
    fragment, not a number."""
    for g in groups:
        for box, _ in g:
            if band[0] <= box[0] <= band[1] and g is not group:
                return False
    return True


def read_hp(frame, layout=None) -> tuple[int | None, int | None]:
    """(hp, max_hp) from the "250 / 250" digits. Either may be None on its own.

    The two numbers are read independently at their own anchors, so a mangled
    max hp does not cost the current hp that was perfectly legible beside it.
    """
    hp = max_hp = None
    for mask in _masks(frame, HP_TEXT):
        if hp is not None and max_hp is not None:
            break  # both numbers read; the remaining passes cost time for nothing
        groups = _groups(_glyphs(mask))
        for g in groups:
            left, last = g[0][0][0], g[-1][0]
            right = last[0] + last[2]
            if (hp is None and HP_CUR_RIGHT[0] <= right <= HP_CUR_RIGHT[1]
                    and _sole_occupant(groups, g, HP_CUR_BAND)
                    and not _lost_digit(mask, g[0][0], "left")):
                hp = _number(g)
            elif (max_hp is None and HP_MAX_LEFT[0] <= left <= HP_MAX_LEFT[1]
                    # No hero has single-digit maximum health, so one glyph here
                    # is a partial read of a longer number, not a small number.
                    # Current hp has no such floor -- 6 hp is perfectly real.
                    and len(g) >= 2
                    and _sole_occupant(groups, g, HP_MAX_BAND)
                    and not _lost_digit(mask, g[-1][0], "right")):
                max_hp = _number(g)
    if hp is not None and max_hp is not None and hp > max_hp:
        return None, None  # a glyph came out wrong; do not hand on either number
    return hp, max_hp


def read_bar_fill(frame) -> float | None:
    """Filled fraction of the health bar, 0..1. A cross-check on the digits.

    The bar is drawn white for the base pool, green above it, and blue for the
    shield a practice-range buff adds; all three count as filled. Its span does
    not change with max hp on the two heroes measured so far.
    """
    bar = crop(frame, HP_BAR).astype(np.int16)
    if bar.size == 0:
        return None
    col = bar.mean(axis=0)
    # Strongest channel, so white, green and the blue of a shield all count as
    # filled while the dark empty slot does not.
    filled = col.max(axis=1) > 140
    if not filled.any():
        return 0.0
    # Trailing run: the bar empties right to left, and tick marks punch small
    # gaps in the fill, so take the last filled column rather than the count.
    return float((np.flatnonzero(filled)[-1] + 1) / len(filled))


def read_damage_segment(frame) -> float | None:
    """The red stripe the bar leaves where health was just lost, 0..1 of the bar.

    It is drawn for about a second after a hit and nothing else on the bar is
    red, so it is an independent witness that damage happened -- which matters
    when hp drops for a single frame and comes straight back: that shape is also
    what a misread looks like, and only the stripe tells them apart.
    """
    bar = crop(frame, HP_BAR)
    if bar.size == 0:
        return None
    hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0].astype(int), hsv[:, :, 1], hsv[:, :, 2]
    return float((((hue < 10) | (hue > 170)) & (sat > 110) & (val > 110)).mean())


def read_webs(frame, layout=PAD) -> int | None:
    """Web-Cluster count by the left weapon icon.

    None when the slot shows infinity, or a glyph the classifier will not
    commit to. The box also catches the slot separator and, on heroes that show
    "6/6", the reserve count, so this takes the first number only.
    """
    # One contrast: the count is drawn bright white, and the extra passes only
    # ever added junk here.
    for mask in _masks(frame, layout.webs, WEBS_FLOOR, contrasts=(55,)):
        for g in _groups(_glyphs(mask)):
            last = g[-1][0]
            right = last[0] + last[2]
            if layout.webs_right[0] <= right <= layout.webs_right[1]:
                n = _number(g)
                if n is not None:
                    return n
    return None


def _icon_box(cx):
    return (cx - ICON_DX, ICON_Y[0], cx + ICON_DX, ICON_Y[1])


def _badge_box(cx):
    return (cx - BADGE_DX, BADGE_Y[0], cx + BADGE_DX, BADGE_Y[1])


def _red_fraction(img):
    """How much of an icon's ink is red, or None when there is no icon there."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2]
    # The brightness floor matters: a reddish-brown beam of scenery running
    # behind the ability row is red enough to count, and at a lower floor it
    # pushes a perfectly ready icon over the line. At 140 the ready icons in the
    # labelled set top out at 0.26 red and the cooling ones start at 0.64.
    ink = (val > 140) & (cv2.morphologyEx(val, cv2.MORPH_TOPHAT, _TOPHAT) > 35)
    n = int(ink.sum())
    if n < ICON_MIN_INK:
        return None
    red = ink & ((hue < 12) | (hue > 168)) & (sat > 90)
    return float(red.sum()) / n


def _badge_mask(frame, cx, layout=PAD):
    """Charge badges invert the HUD: a dark digit punched out of a light disc.
    Returns the digit as ordinary foreground, or None when no disc is drawn."""
    img = crop(frame, _badge_box(cx))
    s = _scale(frame)
    if s != 1.0:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    # Pad: a light disc with the digit punched out of it. M&K: the opposite, a
    # light ring and digit around a dark centre, so the digit is the bright ink
    # itself rather than a hole in it.
    if not layout.badge_light_disc:
        return _ring_badge(img)
    return _disc_badge(img)


def _disc_badge(img):
    """(mask, disc height) for a badge drawn as a dark digit in a light disc."""
    disc = (img.min(axis=2) > 150).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(disc, connectivity=8)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[i]
    # A badge disc is round: across run1 the legitimate ones measure 0.86-1.03
    # wide-over-tall. A wider blob is the disc fused with something bright beside
    # it, and its extra hole gets read as a leading digit -- that is how a plain
    # "3" came back as 23 on 13 frames of run1.
    if area < 250 or h < 18 or not 0.75 < w / h < 1.25:
        return None
    hole = (lab[y:y + h, x:x + w] != i).astype(np.uint8)
    hole[:2, :] = hole[-2:, :] = hole[:, :2] = hole[:, -2:] = 0  # drop the ring itself
    return hole, h


def _ring_badge(img):
    """(mask, disc height) for a badge drawn as light ink on a dark centre."""
    ink = (img.max(axis=2) > 170).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    if n < 2:
        return None
    # the ring is the biggest bright thing; the digit is the next one inside it
    order = sorted(range(1, n), key=lambda i: -stats[i][cv2.CC_STAT_AREA])
    ring = stats[order[0]]
    rx, ry, rw, rh = ring[0], ring[1], ring[2], ring[3]
    if rh < 14 or not 0.7 < rw / max(rh, 1) < 1.5:
        return None
    inner = np.zeros_like(ink)
    for i in order[1:]:
        x, y, w, h, area = stats[i]
        if area >= 25 and rx < x and y > ry and x + w < rx + rw and y + h < ry + rh:
            inner[lab == i] = 1
    if not inner.any():
        return None
    return inner[ry:ry + rh, rx:rx + rw], int(rh)


def _lone_badge_digit(img):
    """(mask, disc height) for an M&K badge whose ring is too faint to find: one
    bright digit, centred, on the badge's dark centre. Day uppercut draws its
    "1" this way at 46.7, 241.0, 321.0, 613.0, 721.5, 749.0 and 759.1 s."""
    ink = (img.max(axis=2) > 170).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    H, W = ink.shape
    found = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        cxr = (x + w / 2) / W
        if area < 25 or not 0.3 * H <= h <= 0.55 * H or not 0.4 <= cxr <= 0.75:
            continue
        pad = max(3, h // 3)
        ring = img[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad].max(axis=2)
        around = ring[(lab[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad] != i)]
        if around.size and float(np.median(around)) < LONE_DIGIT_DARK:
            found.append(i)
    # Chat text over the badge is bright letters on dark too (Req 163.9-167.2:
    # "for some 1v1s"). A badge digit is the only digit-sized shape there; its
    # progress arc is not digit-sized.
    sized = [i for i in range(1, n) if stats[i][4] >= 25 and 0.3 * H <= stats[i][3] <= 0.55 * H]
    if len(found) != 1 or len(sized) != 1:
        return None
    x, y, w, h, _ = stats[found[0]]
    return (lab == found[0]).astype(np.uint8), int(h / 0.6)


LONE_DIGIT_DARK = 110    # the badge's dark centre around a lone digit, max channel


def read_charges(frame, cx, layout=PAD) -> int | None:
    """The charge badge's number, or None. On M&K the badge is drawn in two
    styles -- a light ring and digit around a dark centre, or a light disc
    with a dark digit -- and the ring is sometimes too faint to find; each is
    tried in turn, the ring first, and only when the one before reads nothing."""
    found = _badge_mask(frame, cx, layout)
    n = _badge_number(found)
    if n is not None or layout.badge_light_disc:
        return n
    img = crop(frame, _badge_box(cx))
    s = _scale(frame)
    if s != 1.0:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    for other in (_disc_badge, _lone_badge_digit):
        n = _badge_number(other(img), max_aspect=DIGIT_MAX_ASPECT)
        if n is not None:
            return n
    return None


# A badge digit is 9-12 px wide against 18-19 high. A wider blob in a fallback
# read is the digit merged with something bright beside it: a Twitch emote band
# abutting the badge read a "2" as "1" on all 37 Req uppercut disc reads of "1"
# (237.5-240.1, 250.7, 443.0-444.5). The census of every fallback read: this
# rejects those 37 and one correct "2" (Day 807.7, a badge fading in).
DIGIT_MAX_ASPECT = 0.75


def _badge_number(found, max_aspect=None):
    if found is None:
        return None
    mask, disc_h = found
    # A badge digit fills most of the disc. Anything much shorter is a scrap of
    # the ring that survived, not a glyph, and must not be read as one.
    glyphs = [g for g in _glyphs(mask, BADGE_SIZE, min_area=25)
              if g[0][3] >= 0.45 * disc_h]
    if max_aspect is not None and any(g[0][2] > max_aspect * g[0][3] for g in glyphs):
        return None
    return _number(glyphs) if glyphs else None


# Countdown digits that the template margin cannot tell apart are told apart by
# topology instead. A countdown 6 and 8 differ only at the 6's open top-right,
# and normalising to 16x24 smears that gap: every visible countdown the reader
# returned nothing for on the two train sections was a 6 within 0.04 of an 8, or
# a 9 within 0.04 of an 8. Holes, counted on the glyph before normalising, do
# not smear: a 6 has one hole in its lower half, a 9 one in its upper half, an 8
# one in each, a 0 one tall one. Used only to choose between candidates the
# templates already rank close -- never to override a confident template read.
_TOPOLOGY = {"6": "low", "9": "high", "8": "both", "0": "tall"}
HOLE_MIN_AREA = 6          # px; smaller "holes" are JPEG speckle


def _holes(mask, box):
    """Shape of the glyph's holes: "none", "low", "high", "both", "tall" or "other"."""
    x, y, w, h = box
    g = cv2.copyMakeBorder(mask[y:y + h, x:x + w].astype(np.uint8), 1, 1, 1, 1,
                           cv2.BORDER_CONSTANT, value=0)
    contours, hier = cv2.findContours(g, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is None:
        return "none"
    spans = []
    for c, link in zip(contours, hier[0]):
        if link[3] != -1 and cv2.contourArea(c) >= HOLE_MIN_AREA:   # an inner contour
            _, cy, _, ch = cv2.boundingRect(c)
            spans.append(((cy - 1) / h, (cy - 1 + ch) / h))
    if not spans:
        return "none"
    if len(spans) == 2:
        (a0, a1), (b0, b1) = sorted(spans)
        return "both" if a1 <= 0.55 and b0 >= 0.45 else "other"
    if len(spans) > 2:
        return "other"
    top, bottom = spans[0]
    if bottom - top >= 0.45:
        return "tall"
    centre = (top + bottom) / 2
    return "low" if centre >= 0.55 else ("high" if centre <= 0.45 else "other")


def _countdown_char(mask, box):
    """classify(), with the topology tie-break for close 0/6/8/9 candidates."""
    glyph = _normalise(mask, box)
    ch = classify(glyph)
    if ch is not None:
        return ch
    rows, chars = _flat_templates()
    dist = (rows != glyph.ravel()).sum(axis=1) / glyph.size
    close = {str(c) for c, d in zip(chars, dist) if d <= MAX_DIST and d - dist.min() < MIN_MARGIN}
    if not close or not close <= set(_TOPOLOGY):
        return None
    shape = _holes(mask, box)
    fits = [c for c in close if _TOPOLOGY[c] == shape]
    return fits[0] if len(fits) == 1 else None


def _countdown_boxes(mask):
    """Countdown glyph boxes; a pair of digits drawn touching is split in two.

    A countdown's two 1s in "11" are set close enough to merge into one
    component twice a digit's width, which the size window then throws away:
    team-up's 11 was never read. Such a component is cut at its ink valley.
    """
    min_h, max_h, min_w, max_w = COOLDOWN_SIZE
    wide = _segment(mask, (min_h, max_h, max_w + 1, 2 * max_w + 4))
    out = list(_segment(mask, COOLDOWN_SIZE))
    for x, y, w, h in wide:
        cols = mask[y:y + h, x:x + w].sum(axis=0)
        lo, hi = int(w * 0.35), int(w * 0.65)
        cut = lo + int(np.argmin(cols[lo:hi]))
        out += [(x, y, cut, h), (x + cut, y, w - cut, h)]
    return sorted(b for b in out if b[2] >= min_w)


def read_cooldown(frame, name, layout=PAD) -> int | None:
    """Seconds left on this slot's cooldown, or None when no number is read.

    None is *not* "no countdown": it is also a countdown the reader could not
    read. The event logic keeps a cooldown's identity through such frames (see
    perception.events), and never treats a None as the cooldown having ended.
    """
    cx = layout.slot_cx[name]
    masks = list(_masks(frame, _icon_box(cx), 115, contrasts=(55, 30)))
    # Templates first, exactly as before: the first pass that reads wins, so
    # every countdown this reader already read comes out the same.
    for m in masks:
        value = _countdown_in(m, False)
        if value is not None:
            return value
    # Only where that read nothing, the topology tie-break -- and only when every
    # pass agrees on it. A real
    # 6 or 8 shows the same holes in the same places on all six passes; a 9
    # whose tail has half-closed over a busy background grows a second "hole"
    # on some passes and not others, and one such pass would otherwise read 8.
    tied = [_countdown_in(m, True) for m in masks]
    return tied[0] if tied and tied[0] is not None and len(set(tied)) == 1 else None


def _countdown_in(mask, tiebreak) -> int | None:
    """The centred countdown one threshold pass shows, or None."""
    middle = mask.shape[1] / 2
    if tiebreak:
        glyphs = [(b, _countdown_char(mask, b)) for b in _countdown_boxes(mask) if b[2] <= b[3]]
    else:                                 # exactly the reader as it was
        glyphs = [(b, classify(_normalise(mask, b)))
                  for b in _segment(mask, COOLDOWN_SIZE) if b[2] <= b[3]]
    for group in _groups(glyphs):
        # A countdown is at most two digits: the slot draws whole seconds
        # and the longest cooldown in the kit is 15 s. Three digits is never
        # a countdown, and letting them through cost real data -- chat that
        # happened to sit centred in the slot read as 120..188 and each one
        # became a phantom cast, about twenty of them in one 15 min section.
        if len(group) > 2:
            continue
        value = _number(group)
        if value is None:
            continue
        # A countdown is centred in its slot. On a stream, chat scrolls
        # across the ability row and its letters are the right size to read
        # as digits -- that is where eight uppercut "casts" in 2.6 seconds
        # came from, on a 7 second cooldown. Off-centre text is not ours.
        first, last = group[0][0], group[-1][0]
        centre = (first[0] + last[0] + last[2]) / 2
        if abs(centre - middle) <= COOLDOWN_CENTRE * mask.shape[1]:
            return value
    return None


def _slot_occluded(frame, cx, limit) -> bool:
    """True when something is drawn straight through the slot.

    An ability icon is confined to its own box; a stream's chat is a band of text
    that runs across the whole row. Measuring the ink in the narrow gaps either
    side of the slot tells them apart: chat leaves 0.22 there, a clean slot at
    most 0.09. Without this the availability reader committed to a verdict on a
    slot it could not see, which is the one thing every reader here must not do.
    """
    height, width = frame.shape[:2]
    y0, y1 = ICON_Y

    def ink(x0, x1):
        patch = frame[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)]
        if patch.size == 0:
            return 0.0
        grey = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        return float(((grey > 110)
                      & (cv2.morphologyEx(grey, cv2.MORPH_TOPHAT, _TOPHAT) > 35)).mean())

    left = ink(cx - ICON_DX - SLOT_GAP - 0.002, cx - ICON_DX - 0.002)
    right = ink(cx + ICON_DX + 0.002, cx + ICON_DX + SLOT_GAP + 0.002)
    return max(left, right) > limit


def read_ability(frame, name, layout=PAD) -> tuple[bool | None, int | None]:
    """(ready, charges), reconciling icon, badge and readable countdown.

    None charges means an absent or unreadable badge, never zero charges.
    """
    return _read_ability(frame, name, layout, read_cooldown(frame, name, layout))


def _read_ability(frame, name, layout, countdown):
    cx = layout.slot_cx[name]
    charges = read_charges(frame, cx, layout)
    if _slot_occluded(frame, cx, layout.slot_spill):
        return None, charges
    frac = _red_fraction(crop(frame, _icon_box(cx)))
    if frac is None:
        ready = None
    elif frac <= ICON_READY:
        ready = True
    elif frac >= ICON_COOLING:
        ready = False
    else:
        ready = None
    # White countdown ink is not a ready icon. Swing and uppercut can recharge
    # one charge while another remains usable; a missing badge cannot establish
    # that a spare exists. Preserve independent red/uncertain icon evidence.
    if charges == 0:
        ready = False
    elif countdown is not None:
        if name in ("swing", "uppercut"):
            if charges is None and ready is True:
                ready = None
        elif countdown > 0:
            ready = False
        elif ready is True:
            # A zero countdown at the transition is not proof of a ready icon.
            ready = None
    return ready, charges


def read_ult(frame, layout=PAD) -> tuple[bool | None, float | None]:
    """(ready, charge 0..1). Charge is the yellow fill of the ult diamond."""
    hsv = cv2.cvtColor(crop(frame, layout.ult), cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    frac = float(((h > 18) & (h < 35) & (s > 110) & (v > 140)).mean())
    charge = min(1.0, frac / ULT_READY)
    if frac >= ULT_READY:
        return True, 1.0
    if frac <= ULT_CHARGING:
        return False, charge
    return None, charge


# The Spider-Tracer a hit web-cluster leaves on an enemy: a white hexagonal web
# emblem drawn above the enemy's health bar, and the thing Amazing Combo keys
# off. Harvested at 1280 wide, which is the size the agent runs at.
TRACER = [
    "........#.........",
    "........##........",
    ".......####.......",
    "......######......",
    "....###....##.....",
    "######......######",
    "###....###.....##.",
    ".#.#..######...##.",
    ".##.##.....##..##.",
    "..#..#.####.#..#..",
    "..#..#..##..#..#..",
    "..#..#.####.#..#..",
    ".##.##.....##..#..",
    ".###.####.##..###.",
    "###....###.....##.",
    "######..#...######",
    "....###....##.....",
    "......###.##......",
    ".......####.......",
    "........##........",
    "........#.........",
]
TRACER_MATCH, TRACER_CLEAR = 0.60, 0.45   # peak correlation for yes / for no
TRACER_BAND = (1.6, 0.15)   # search from y1 - 1.6*box_h up to y1 - 0.15*box_h
TRACER_BAND_PX = 130        # ... but never a band shallower than this
TRACER_SCALES = (0.7, 0.85, 1.0, 1.2, 1.5)
TRACER_HARVEST_WIDTH = 1280   # the frame width the template was cut from
_TRACER_CACHE: dict = {}


def _tracer_templates(frame_width=TRACER_HARVEST_WIDTH):
    """The marker at the sizes it can appear, for a frame of this width.

    The scales are *relative to the frame*, not absolute. The template was cut
    from a 1280-wide capture; on a 2560-wide one the marker is twice the size,
    and a fixed 0.7-1.5 ladder misses it completely -- which made read_tagged
    answer False, confidently, on native frames where the marker was plainly
    there. Distance still moves it within the ladder; resolution no longer does.
    """
    key = round(frame_width / TRACER_HARVEST_WIDTH, 3)
    if key not in _TRACER_CACHE:
        built = []
        base = np.array([[c == "#" for c in r] for r in TRACER], np.float32)
        for s in TRACER_SCALES:
            scale = s * key
            h, w = int(round(base.shape[0] * scale)), int(round(base.shape[1] * scale))
            built.append(cv2.resize(base, (max(w, 4), max(h, 4)), interpolation=cv2.INTER_AREA))
        _TRACER_CACHE[key] = built
    return _TRACER_CACHE[key]


# Ability icons as ink shapes, for working out which slot holds which
# ability. Shape rather than colour: the same icon is white normally and
# gold while a team-up buff is up. Harvested from two sources whose slot
# order was checked by eye -- and which disagree, which is the whole point:
# the ability-to-key binding is a player setting, so a slot position names
# nothing on its own.
ICONS: dict[str, list[str]] = {
    "get_over_here": [
        "AAAACAAAAACAAAA4OAAABgeAAADA/AAACB3AAAAHjAAAAPDgAAA+BgAADzAwAAPBAYAP8AAAB//AAA//////AP///+A//gAcAf+AA4AA+AgwAAHhhgAAB7DAAAAfDAAAAHnAAAAD3AAADA/AAABAeAAABgOAAAB8HAAAAADA",
        "AAAAGAAAA4OAAAA8OAAABw+AAADg+AAACD+AAAAHHAAAAeDgAAA+DgAADzBwAA/hA4AD+AAYD////w//////P////+Af///4AP/AA4AD+AxwAAfhxgAAD/DgAAAfDAAAAPHAAAAHmAAABB+AAADA+AAABgeAAAB4OAAAAGGA",
    ],
    "swing": [
        "AAAAACAOAAAEADgAAMAA4OAYAAf/gQAAf/gwAAP/hgAAHvjgAAHviAAAHn+AAAD88AAADx8AAAD/8AAAH/8+AAH89/AAf57+AB/538AD/7n4AP/3PwA//+PAD//eOAP/wcYA/+A4wA/wA4gA/wDwAAAAAAAAAAHAAAAAPAAA",
        "AAAAAGADAAAMABwAAcAA+fgYAAf/gYAAf/xwAAP/xwAAH/3gAAH/zAAAD++AAAD/8AAAD/8AAAD//+AAH//+AAH/9/AA/97+AB/538AD/73wAf//vwA///PAD//+OAf/4cYA/+A44A/4B5gAf8BgAAAABgAAAAHgAAAAPAAA",
    ],
    "teamup": [
        "AAAgAAAAAgAAAAgwAAAAQwAAAAB4AAAAB4BAAAB4DAADj/zAAB8DGDEB8DOeHg8D/4D/8B/oAH8D+QAB+D4AAZ4B5AAHgD/AAHgGPAAHwAfgAfwA/wCD+A/48D8B8McP8B4HAf/+IAAfH8AAAgB8AgAAA4AwAAA4AAAAAwAA",
        "AAAgAAAAAgAAAAgwAAAAhwAAAAh4AAAAD4AAAAD5HAADj//AAD/v3AAB8DufeB8D/+H/8B/wA/8D/ABj8D8wAx4B4gAPgD/AAHgEfAAPgIfgA/wA/gGH+A/48H8B4+AP8D4HAf/8AAB8D8AAAAD8AgAAB4AwAAAwAAAAAwAA",
    ],
    "uppercut": [
        "AAAAwAAAAPwAAAAPwAAAAR4AAAAx4AAAA54AAAA/5AAAA/5gAAA/4gAAA/4gAAA/4wAAAX4wAAAP4gAAAP5AAAA/5AAAB/xAAAH/xAAAf/hAAA//iAAB//CAAB/+AAAB/+GQ8///n88///348///2Y8//32Y8/832Y8+832Y",
        "AAAB4AAAAf4AAAA/4AAABP+AAAPD+AAAPj+AAAH/+YAAH/+MAAH/+OAAH/+OAAH/+PAAD/+PAAA/+PAAA/8MAAD/8MAAP/8MAA//4MAD//4YA///4YB///gYB///AwD//+BgH//8BAH//4AAP//wAAP//gAA///AAA8gAAAA",
    ],
}

ICON_H, ICON_W = 28, 36
ICON_MATCH = 0.78      # share of cells that must agree with the best icon
ICON_MARGIN = 0.05     # ... and by this much over the runner-up
_ICON_CACHE: list = []


def _icon_templates():
    if not _ICON_CACHE:
        names, rows = [], []
        for name, packed in ICONS.items():
            for blob in packed:
                bits = np.unpackbits(np.frombuffer(base64.b64decode(blob), np.uint8),
                                     count=ICON_H * ICON_W).astype(bool)
                names.append(name)
                rows.append(bits)
        _ICON_CACHE.append(np.array(rows, bool))
        _ICON_CACHE.append(np.array(names))
    return _ICON_CACHE[0], _ICON_CACHE[1]


def _icon_shape(frame, cx):
    """The slot's ink, cropped to it and normalised, or None if the slot is empty."""
    img = crop(frame, _icon_box(cx))
    if img.size == 0:
        return None
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = ((grey > 110) & (cv2.morphologyEx(grey, cv2.MORPH_TOPHAT, _TOPHAT) > 30)).astype(np.uint8)
    ys, xs = np.where(mask)
    if len(xs) < 30:
        return None
    mask = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(mask * 255, (ICON_W, ICON_H), interpolation=cv2.INTER_AREA) > 110


def identify_slot(frame, cx) -> str | None:
    """Which ability's icon is in this slot, or None when it cannot be told.

    None covers an empty slot, a slot showing a countdown instead of an icon, a
    slot under an overlay, and a shape that matches nothing well enough. Callers
    must treat it as unknown, never as a default.
    """
    shape = _icon_shape(frame, cx)
    if shape is None:
        return None
    rows, names = _icon_templates()
    agree = (rows == shape.ravel()).mean(axis=1)
    best = int(agree.argmax())
    name = str(names[best])
    other = agree[names != name]
    if agree[best] < ICON_MATCH:
        return None
    if other.size and agree[best] - other.max() < ICON_MARGIN:
        return None
    return name


# --- glyph evidence: measured, not used --------------------------------------
# A running countdown replaces the ability's icon glyph, so a frame whose slot
# matches the EXPECTED glyph is a candidate witness that no countdown is drawn
# there. Admitted only as this named, switchable, per-frame observation, to be
# measured (docs/learning-plan.md, glyph contract): it bounds when a countdown
# appears, never when the ability was used -- Day uppercut's badge drops at
# 46.7 s while the glyph still matches at 46.8 and the lock reads at 46.9 --
# and it certifies neither readiness nor no-cast. Nothing in the event logic
# reads it. The thresholds are identify_slot's (ICON_MATCH, ICON_MARGIN), frozen
# for the audit at GLYPH_READER.
GLYPH_READER = "identify_slot/ICON_MATCH+ICON_MARGIN/1"


def glyph_evidence(frame, slot, layout=None) -> bool | None:
    """True when `slot`'s own glyph is matched in its position; None otherwise.

    One-sided: no match is unknown, never "a countdown is drawn". The team-up
    template is generic, so a match there says nothing about which team-up.
    """
    layout = layout or PAD
    return True if identify_slot(frame, layout.slot_cx[slot]) == slot else None


def slot_mapping(frames, layout=None):
    """{slot position key: ability} for a source, by voting over many frames.

    A slot shows a countdown, an overlay or nothing often enough that one frame
    cannot decide. Positions whose icon never identifies are left out, and their
    casts are reported with no ability name rather than a guessed one.
    """
    layout = layout or PAD
    votes = {key: {} for key in layout.slot_cx}
    for frame in frames:
        for key, cx in layout.slot_cx.items():
            name = identify_slot(frame, cx)
            if name:
                votes[key][name] = votes[key].get(name, 0) + 1
    out = {}
    for key, tally in votes.items():
        if not tally:
            continue
        winner, count = max(tally.items(), key=lambda kv: kv[1])
        if count >= max(3, 0.6 * sum(tally.values())):
            out[key] = winner
    return out


def read_tagged(frame, bbox) -> bool | None:
    """Is this enemy carrying a Spider-Tracer?

    `bbox` is an agent.state.Detection box, (x1, y1, x2, y2) in pixels of this
    frame. The marker is drawn above the enemy, over the world rather than at a
    fixed place on screen, so the search follows the box: a band above its top,
    centred on it and wide enough for the marker to drift within.

    Returns True, False, or None. None means the band could not be searched —
    the enemy is against the top of the screen, or the box is too small to place
    the band — which is not the same as "no tracer".
    """
    x1, y1, x2, y2 = (float(v) for v in bbox)
    height, width = frame.shape[:2]
    # The marker sits above the enemy's health bar and name, which is most of a
    # box height clear of the box itself, and the whole stack rides up and down
    # with distance -- so the band is sized from the box, with a pixel floor for
    # a far-off enemy whose box is tiny.
    box_h = y2 - y1
    band_top = int(y1 - max(TRACER_BAND_PX, TRACER_BAND[0] * box_h))
    band_bottom = int(y1 - max(8.0, TRACER_BAND[1] * box_h))
    half = max(36.0, 0.5 * (x2 - x1))
    band_left, band_right = int((x1 + x2) / 2 - half), int((x1 + x2) / 2 + half)
    # Clamp both ends into the frame. Letting a negative index through here
    # turns "the enemy is at the top of the screen" into a search of almost the
    # whole frame, which finds a tracer belonging to somebody else.
    band_top, band_bottom = max(0, min(height, band_top)), max(0, min(height, band_bottom))
    band_left, band_right = max(0, min(width, band_left)), max(0, min(width, band_right))
    band = frame[band_top:band_bottom, band_left:band_right]
    templates = _tracer_templates(width)
    if band.size == 0 or any(band.shape[i] < templates[0].shape[i] for i in (0, 1)):
        return None
    ink = (cv2.cvtColor(band, cv2.COLOR_BGR2GRAY) > 200).astype(np.float32)
    best = 0.0
    for tpl in templates:
        if tpl.shape[0] > ink.shape[0] or tpl.shape[1] > ink.shape[1]:
            continue
        best = max(best, float(cv2.matchTemplate(ink, tpl, cv2.TM_CCOEFF_NORMED).max()))
    if best >= TRACER_MATCH:
        return True
    if best <= TRACER_CLEAR:
        return False
    return None


@dataclass
class Hud:
    hp: int | None = None
    max_hp: int | None = None
    bar_fill: float | None = None
    webs: int | None = None
    abilities: dict[str, tuple[bool | None, int | None]] = field(default_factory=dict)
    ult_ready: bool | None = None
    ult_charge: float | None = None
    # Seconds left per slot, or None when absent or unreadable. Readiness has
    # already been reconciled with these values before conversion to State.
    cooldowns: dict[str, int | None] = field(default_factory=dict)
    bar_damage: float | None = None   # red stripe on the hp bar: damage just taken

    def state_kwargs(self):
        """The subset agent.state.State accepts today. ult_charge has no field
        there yet; ult lands as an Ability with its ready flag."""
        from agent.state import Ability

        # agent/state.py still calls this slot PULL = "pull"; the event stream
        # calls it get_over_here (format 2). Translated here rather than in the
        # brain's file, so the live loop keeps working until rivals-brain moves.
        ab = {("pull" if k == "get_over_here" else k): Ability(ready=r, charges=c)
              for k, (r, c) in self.abilities.items()}
        ab["ult"] = Ability(ready=self.ult_ready)
        return dict(hp=self.hp, max_hp=self.max_hp, webs=self.webs, abilities=ab)


def read(frame, layout=PAD) -> Hud:
    hp, max_hp = read_hp(frame)
    bar = read_bar_fill(frame)
    if hp is None and not bar:
        # No hp digits and no bar: a menu, a loading screen, the hero picker.
        # The ability row would otherwise read as "not ready", which is a guess.
        return Hud()
    ult_ready, ult_charge = read_ult(frame, layout)
    cooldowns = {n: read_cooldown(frame, n, layout) for n in layout.slot_cx}
    return Hud(
        hp=hp,
        max_hp=max_hp,
        bar_fill=bar,
        bar_damage=read_damage_segment(frame),
        webs=read_webs(frame, layout),
        abilities={n: _read_ability(frame, n, layout, cooldowns[n]) for n in layout.slot_cx},
        cooldowns=cooldowns,
        ult_ready=ult_ready,
        ult_charge=ult_charge,
    )


# --- building the glyph bank ----------------------------------------------

def learn(specs, out=None):
    """Build the GLYPHS literal from frames whose values are already known.

    Each spec is `path=hp:300/300;webs:5;swing:3` — a frame and what a human
    read off it. The glyphs of a region are matched to that string positionally,
    so a template can only be mislabelled if the hand-read value was wrong,
    which is a far smaller target than labelling 100 glyph bitmaps by eye.
    """
    variants: dict[str, list] = {}
    for spec in specs:
        path, _, fields = spec.partition("=")
        frame = cv2.imread(path)
        if frame is None:
            print(f"{path}: not readable", file=sys.stderr)
            continue
        for field_spec in fields.split(";"):
            key, _, want = field_spec.partition(":")
            if key == "cd":
                # cd:<slot>:<layout>:<seconds> -- the countdown drawn in a slot.
                # Its digits are half again as tall as the hp row's and do not
                # match those templates: an 8 read as 3 until these were learned.
                slot, lay, want = want.split(":")
                cx = LAYOUTS[lay].slot_cx[slot]
                for mask in _masks(frame, _icon_box(cx), 115, contrasts=(55, 30)):
                    boxes = [b for b in _segment(mask, COOLDOWN_SIZE) if b[2] <= b[3]]
                    if len(boxes) != len(want):
                        continue
                    for b, ch in zip(boxes, want):
                        g = _normalise(mask, b)
                        kept = variants.setdefault(ch, [])
                        if not any(np.count_nonzero(g != k) <= 18 for k in kept):
                            kept.append(g)
                    break
                continue
            if key in ("hp", "webs"):
                box, floor = ((HP_TEXT, 115) if key == "hp" else (WEBS, WEBS_FLOOR))
                # Both kernels, so every mask a reader can produce has templates.
                for mask in _masks(frame, box, floor):  # noqa: B007
                    boxes = [b for b in _segment(mask) if b[2] <= b[3]]
                    if key == "webs":  # anchor exactly as read_webs does
                        boxes = [b for b in boxes
                                 if WEBS_RIGHT[0] <= b[0] + b[2] <= WEBS_RIGHT[1]]
                    want_here = want
                    if key == "hp" and len(boxes) != len(want) and "/" in want:
                        # Only the current-hp number surfaced in this mask. Take
                        # it alone, anchored the way read_hp anchors it, rather
                        # than dropping a frame that carries a digit we lack.
                        cur = want.split("/")[0]
                        groups = [g for g in _groups(_glyphs(mask))
                                  if HP_CUR_RIGHT[0] <= g[-1][0][0] + g[-1][0][2] <= HP_CUR_RIGHT[1]]
                        if len(groups) == 1 and len(groups[0]) == len(cur):
                            boxes, want_here = [b for b, _ in groups[0]], cur
                    if len(boxes) != len(want_here):
                        continue
                    for b, ch in zip(boxes, want_here):
                        g = _normalise(mask, b)
                        kept = variants.setdefault(ch, [])
                        if not any(np.count_nonzero(g != k) <= 18 for k in kept):
                            kept.append(g)
                continue
            else:
                found = _badge_mask(frame, SLOT_CX[key])
                if found is None:
                    print(f"{path} {key}: no badge", file=sys.stderr)
                    continue
                mask, disc_h = found
                boxes = [b for b in _segment(mask, BADGE_SIZE, min_area=25)
                         if b[3] >= 0.45 * disc_h]
            if key == "webs":
                boxes = boxes[:len(want)]  # the separator after the count is not a glyph
            if len(boxes) != len(want):
                print(f"{path} {key}: {len(boxes)} glyphs for {want!r} -- skipped",
                      file=sys.stderr)
                continue
            for b, ch in zip(boxes, want):
                g = _normalise(mask, b)
                kept = variants.setdefault(ch, [])
                if not any(np.count_nonzero(g != k) <= 18 for k in kept):
                    kept.append(g)
    lines = ["GLYPHS: dict[str, list[str]] = {"]
    for ch in sorted(variants):
        packed = [base64.b64encode(np.packbits(v.ravel())).decode() for v in variants[ch]]
        lines.append(f'    "{ch}": [')
        lines += [f'        "{b}",' for b in packed]
        lines.append("    ],")
    lines.append("}")
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text + "\n")
        print(f"{sum(len(v) for v in variants.values())} templates "
              f"({''.join(sorted(variants))}) -> {out}", file=sys.stderr)
    else:
        # stdout by default, so this never litters the working directory with a
        # half-finished template file someone else has to wonder about.
        print(text)


def sheet(paths, out="sheet.png", rows=10, height=64):
    """One row per frame: the crops a human needs to read the truth off, in
    region order. Written for hand-checking a labelled set; the reader's own
    answers are deliberately not drawn on it."""
    def tile(img, w=None):
        h = height
        if img is None or img.size == 0:
            return np.zeros((h, w or h, 3), np.uint8)
        s = h / img.shape[0]
        t = cv2.resize(img, (max(1, int(img.shape[1] * s)), h), interpolation=cv2.INTER_CUBIC)
        return t if w is None else cv2.resize(t, (w, h), interpolation=cv2.INTER_CUBIC)

    sheets, row_imgs = [], []
    for i, p in enumerate(paths):
        frame = cv2.imread(p)
        if frame is None:
            continue
        parts = [tile(crop(frame, HP_TEXT), 210), tile(crop(frame, HP_BAR), 260),
                 tile(crop(frame, WEBS), 70)]
        for cx in SLOT_CX.values():
            parts.append(tile(crop(frame, _badge_box(cx)), 46))
            parts.append(tile(crop(frame, _icon_box(cx)), 64))
        parts.append(tile(crop(frame, ULT), 78))
        row = np.hstack([np.pad(p_, ((0, 0), (0, 3), (0, 0))) for p_ in parts])
        label = np.zeros((height, 74, 3), np.uint8)
        cv2.putText(label, str(i), (4, height - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)
        row_imgs.append(np.pad(np.hstack([label, row]), ((0, 4), (0, 0), (0, 0))))
        if len(row_imgs) == rows:
            sheets.append(row_imgs)
            row_imgs = []
    if row_imgs:
        sheets.append(row_imgs)
    for n, chunk in enumerate(sheets):
        w = max(r.shape[1] for r in chunk)
        img = np.vstack([np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in chunk])
        path = out.replace(".png", f"-{n}.png")
        cv2.imwrite(path, img)
        print(path)
    print("columns: idx | hp text | hp bar | webs | (badge, icon) x4 | ult")


def annotate(path, out):
    """Draw every region on a frame with what the reader got out of it."""
    frame = cv2.imread(path)
    hud = read(frame)
    h, w = frame.shape[:2]
    img = frame.copy()
    boxes = [(HP_TEXT, f"hp {hud.hp}/{hud.max_hp}"),
             (HP_BAR, f"bar {hud.bar_fill:.2f}" if hud.bar_fill is not None else "bar ?"),
             (WEBS, f"webs {hud.webs}"),
             (ULT, f"ult {hud.ult_ready} {hud.ult_charge:.2f}")]
    for name, cx in SLOT_CX.items():
        ready, charges = hud.abilities[name]
        boxes.append((_icon_box(cx), f"{name} {ready}"))
        if charges is not None:
            boxes.append((_badge_box(cx), f"x{charges}"))
    for i, (box, text) in enumerate(boxes):
        x0, y0, x1, y1 = (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 230, 255), 1)
        ty = y0 - 5 if i % 2 == 0 else y1 + 13
        cv2.putText(img, text, (x0, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3)
        cv2.putText(img, text, (x0, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 255), 1)
    crop_img = img[int(0.80 * h):, :]
    cv2.imwrite(out, crop_img)
    print(out, crop_img.shape)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "learn":
        learn(sys.argv[2:])   # prints the GLYPHS literal; redirect it where you want it
    elif cmd == "sheet":
        sheet(sys.argv[2:])
    elif cmd == "annotate":
        annotate(sys.argv[2], sys.argv[3])
    else:
        from tests.test_hud import main
        sys.exit(main())
