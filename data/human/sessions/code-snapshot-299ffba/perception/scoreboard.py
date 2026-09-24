"""Read the scoreboard overlay: whether it is open, and what the range one says.

  uv run --group perception python -m perception.scoreboard <frame.jpg>

Two jobs, and only the first works on any scoreboard:

`is_scoreboard(frame)` says whether the overlay is up. It keys on the long
horizontal rule the game draws under the team headers, which spans most of the
screen and exists on every scoreboard -- the practice range's and a live match's,
pad HUD and mouse-and-keyboard alike. Brightness is deliberately not the test:
the overlay dims the scene, but so does a dark corner of a map.

`read_scoreboard(frame)` reads the **practice range** scoreboard only, and
returns a plain dict the live loop can store. Reading a live match's scoreboard
is a different layout and is not attempted here.

Two things the range scoreboard teaches that are easy to get wrong:

* **The KO/death/assist digits are gold, not white.** A min-channel mask, which
  is what reads the rest of the HUD, sees nothing at all there: gold has almost
  no blue. They are read off the strongest channel instead.
* **Do not key on red for the enemy panel.** Its tint follows the Enemy Color
  accessibility setting and is currently green. Nothing here looks at panel
  colour; the rows are found by position.

Every value is an int or None, and None means the reader could not read it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

from perception.hud import (  # noqa: E402
    GLYPH_H, GLYPH_W, MAX_DIST, MIN_MARGIN, STRONG, _groups, _mask, _normalise,
    _number, _segment, crop,
)

# --- is the overlay up? ---------------------------------------------------
# The rule under the team headers. Measured over every frame of two 60 s clips
# and the range capture, not a handful of stills: real scoreboards score
# 0.91-0.97, and ordinary play tops out at 0.79 -- a ledge or an objective
# banner can make a long horizontal edge too, just never as long or as straight.
# An earlier threshold of 0.70, set from eighteen sampled negatives, fired on 48
# frames of one clip and shattered its segments.
RULE_BAND = (0.08, 0.23, 0.92, 0.32)   # x0, y0, x1, y1 where the rule is drawn
RULE_DROP = 22                          # grey levels darker, five rows below
RULE_SPAN = 5
SCOREBOARD_OPEN, SCOREBOARD_SHUT = 0.85, 0.80


def rule_score(frame) -> float:
    """How much of one row is a bright edge over the row just below it."""
    height, width = frame.shape[:2]
    x0, y0, x1, y1 = RULE_BAND
    strip = cv2.cvtColor(frame[int(y0 * height):int(y1 * height),
                               int(x0 * width):int(x1 * width)],
                         cv2.COLOR_BGR2GRAY).astype(int)
    if strip.shape[0] <= RULE_SPAN:
        return 0.0
    drops = strip[:-RULE_SPAN] - strip[RULE_SPAN:]
    return float((drops > RULE_DROP).mean(axis=1).max())


def is_scoreboard(frame) -> bool | None:
    """True, False, or None in the band between, where it is not worth a guess.

    Callers that only want a name for a break (the segmenter) can treat None as
    False: something else already describes that frame.
    """
    score = rule_score(frame)
    if score >= SCOREBOARD_OPEN:
        return True
    if score <= SCOREBOARD_SHUT:
        return False
    return None


# The scoreboard sets its numbers in a narrower face than the HUD -- glyphs
# 10-13 px wide at 2560 against the HUD's 14-21 -- so the HUD bank does not
# read them and this one exists. Learned with `learn()` from nine native boards
# whose values a human read: docs/evidence/l4/scoreboard-back-native.jpg and
# the eight in docs/evidence/l4/scoreboard/ (truth.json). "%" is the slash of the
# percent sign, the only part of it tall enough to segment. Do not hand-edit.
GLYPHS: dict[str, list[str]] = {
    "%": [
        "4AfgH+Ac4BzgHOA44Djg+ODg4ODg4OPDw8cDxwcHBwcHBxwHHAccBzgHOAc4B+AD",
    ],
    "0": [
        "f/7//P//+B/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/gf/////H/4",
        "BgAf/n//f/94H3gP+A/4D/gPeA94D3gPeA94D3gPOA84DzgPeA/4D3gff/9//h/4",
        "H/5//3//OB/4H3gfeB84HzgfeA94H3gPeA94D3gPOA84D3gPeA84Dzgff/9//h/4",
    ],
    "1": [
        "/+D/4D/gB+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4Afg////////",
        "/8D/wH/AA8ADwAPAA8ADwAPAA8ADwAPAA8ADwAPAA8ADwAPAA8ADwAPA////////",
    ],
    "2": [
        "D/B//v/////wD/AP8A8AHwAcAHwA+AHwA+APgB8APgA8APgA8ADwAPAA////////",
        "f/7///3/+B/wD/AP8A8APwB8AHgB+APwD8AfgB4APgD8APAA8ADwAPgA////////",
    ],
    "3": [
        "f/7//Px/+B/wD/AP8A8ADwAfAD8P/A/+D/4ADwAPAA8AD/AP8A/wD/gf/////H/4",
        "f/7/////8A/wD/APAA8ADwAPAB8P/g/+B/8ADwAPAA8AD/AP8A/wD/Af/////h/4",
    ],
    "4": [
        "AD4AfgB+Af4B/gP+A/4Hvge+D74OPj4+PD58Png+////////AD4APgA+AD4APgA+",
    ],
    "5": [
        "///////+8ADwAPAA8ADwAPf+//////AP8A8ADwAPAA8AD/AP8A/wD/Af/////n/4",
    ],
    "6": [
        "DcB//v/////wD/AP8A/wAPAA8OD//P////////AP8A/wP/A/8A/wD/AP/////n/4",
        "D+B//v/////wD/AP8A/wAPAA8ADx+P/++B/wD/AP8A/wD/AP8A/wD/Af/////h/4",
    ],
    "7": [
        "////////8B/wH/AfAB4AfgB+AH4AeAD4APgA+ADwAfAB8AHwAeAH4AfgB+AH4AeA",
        "ADD////////wP/A/8D4APAB8AHwAeAB4AHgB+AH4AfgB4AHgA+AD8APAD8APwA/A",
    ],
    "8": [
        "f/7/////8A/wD/AP8A/wD/AP+B9//n/+///wD/AP8A/wD/AP8A/wD/Af/////h/4",
        "f/7//P2/+B/wD/AP8A/wD/Af8D///H/+///wD/AP8A/wD/AP8A/wD/gf/////H/4",
    ],
    "9": [
        "D+B//v/////wD/AP8A/wD/AP8A/wD/AP//9/7wAPAA8AD/AP8A/wD/Af/////n/4",
        "B/Af/n//f//4H/gf+B/4H/gf+B/4H3//f/8//x//AB8AHwAf+B/4H/gff/9//h/4",
    ],
}

_CACHE: list = []


def _templates():
    """(stacked bitmaps, labels) for the scoreboard face."""
    if not _CACHE:
        import base64 as _b64
        chars, rows = [], []
        for ch, packed in GLYPHS.items():
            for blob in packed:
                bits = np.unpackbits(np.frombuffer(_b64.b64decode(blob), np.uint8),
                                     count=GLYPH_H * GLYPH_W)
                chars.append(ch)
                rows.append(bits.astype(bool))
        _CACHE.append(np.array(rows, bool))
        _CACHE.append(np.array(chars))
    return _CACHE[0], _CACHE[1]


def classify_digit(glyph) -> str | None:
    """Nearest scoreboard template, or None when unsure. Same rule as the HUD
    classifier: a near-exact match stands, otherwise it must beat the runner-up."""
    rows, chars = _templates()
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


# --- the kill feed --------------------------------------------------------
# A KO draws a banner top right: killer portrait and name, weapon, victim. It is
# the fastest KO signal there is -- it appears the moment the KO lands, long
# before anyone opens a scoreboard -- so it is what ends an attack option.
#
# The banner is semi-transparent, so its brightness follows whatever is behind
# it (V ~160 over a dark ceiling, ~230 over sky). What does not change is that
# it is nearly colourless (saturation falls from ~80 to ~20) and that it is a
# crisp rectangle. Pale sky is colourless too, which is why saturation alone
# fired on a ceiling at 0.61; sky never has the crisp edge. Measured on L4's two
# kill-feed frames and 115 ordinary ones: the feed scores 0.88-0.90 on the slab
# and 0.94-0.99 on the edge, and no ordinary frame clears 0.5 on both.
KILLFEED = (0.77, 0.022, 0.975, 0.070)
KILLFEED_ON, KILLFEED_OFF = 0.70, 0.50


def killfeed_scores(frame):
    """(slab, edge) for the top-right banner slot."""
    height, width = frame.shape[:2]
    x0, y0, x1, y1 = KILLFEED
    hsv = cv2.cvtColor(frame[int(y0 * height):int(y1 * height),
                             int(x0 * width):int(x1 * width)],
                       cv2.COLOR_BGR2HSV).astype(int)
    sat, val = hsv[:, :, 1], hsv[:, :, 2]
    floor = np.percentile(val, 20)
    slab = ((sat < 45) & (val > floor + 40) & (val > 110)).mean(axis=1).max()
    edge = ((val[2:] - val[:-2]) > 35).mean(axis=1).max() if val.shape[0] > 2 else 0.0
    return float(slab), float(edge)


def is_killfeed(frame) -> bool | None:
    """Whether a kill-feed line is on screen.

    In the practice range every line is ours: nothing else can score a KO. In a
    live match the feed shows everyone's kills, and attributing a line to us would
    mean reading the killer's name or portrait, which is not done here.
    """
    slab, edge = killfeed_scores(frame)
    if slab >= KILLFEED_ON and edge >= KILLFEED_ON:
        return True
    if slab < KILLFEED_OFF or edge < KILLFEED_OFF:
        return False
    return None


# --- the range scoreboard -------------------------------------------------
# Fractions of the frame, measured on docs/evidence/l4/scoreboard-back-native.jpg
# (2560x1440). The three tallies sit in the player's row; the six stats sit in
# the bar under both panels, each centred over its printed label.
KDA_Y = (0.290, 0.322)
KDA_X = {"kos": (0.396, 0.424), "deaths": (0.428, 0.456), "assists": (0.460, 0.488)}
STATS_Y = (0.672, 0.718)
STATS_CX = {
    "accuracy": 0.3235,
    "damage": 0.3831,
    "damage_blocked": 0.4538,
    "healing": 0.5245,
    "web_cluster_accuracy": 0.6876,
    "spin_kos": 0.8026,
}
STATS_BAND = (0.28, 0.85)          # x range holding all six
STAT_REACH = 0.028                 # how far a digit may sit from its label centre
# The scoreboard face is small: about 12 px per glyph on a 2560-wide capture, so
# about 6 px on a 1280-wide one. Upscaling that does not recover the shape, it
# invents one -- the 720p copy of the reference frame reads assists as 0 when it
# is 1 and Spectacular Spin KOs as 0 when it is 3. Values are only attempted at
# a width where the glyphs are really there.
MIN_WIDTH = 1920
PERCENTAGES = ("accuracy", "web_cluster_accuracy")
FIELDS = tuple(KDA_X) + tuple(STATS_CX)


# The scoreboard is semi-transparent, so the gold digits' anti-aliased edges take
# the scene's brightness: an edge pixel a third covered is ~130 over the dark
# panels the templates were learned on, but ~145 over a pale one, where the fixed
# floor alone let it in. That fattened glyph is a pixel wider and taller than any
# template; the "3" of a pale board's 13 sat 0.138 from both 3 and 9, so KOs read
# unknown. An edge pixel must also rise a third of the crop's peak contrast above
# the background. Over the nine labelled boards this changes not one pixel (the
# first moves at 0.375), so `learn()` gives the same templates; 0.30 is the least
# that reads that 13.
GOLD_EDGE = 1 / 3


def _gold_mask(img, scale):
    """Gold text off the strongest channel. The tallies are drawn in gold and a
    min-channel mask -- what reads the rest of the HUD -- sees nothing there."""
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    mx = img.max(axis=2)
    top = cv2.morphologyEx(mx, cv2.MORPH_TOPHAT,
                           cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)))
    edge = GOLD_EDGE * int(top.max())
    return ((top > 40) & (mx > 140) & (top > edge)).astype(np.uint8)


def _read_tally(frame, box):
    scale = 2560 / frame.shape[1]
    mask = _gold_mask(crop(frame, box), scale)
    glyphs = [(b, classify_digit(_normalise(mask, b))) for b in _segment(mask)]
    groups = _groups(glyphs)
    return _number(groups[0]) if len(groups) == 1 else None


def read_tallies(frame) -> dict:
    """KOs, deaths and assists from the player's row."""
    return {name: _read_tally(frame, (x0, KDA_Y[0], x1, KDA_Y[1]))
            for name, (x0, x1) in KDA_X.items()}


def _stat_glyphs(frame):
    """(label, [(box, char), ...]) for every stat, glyphs in left-to-right order.

    Every digit is assigned to the label it sits over, rather than the band
    being cut into groups first. Values past 999 carry a thousands separator --
    "1,375" -- and the comma is a 5x8 mark far below glyph size, so it drops out
    and leaves a gap wide enough to split one number into "1" and "375". Grouped
    first, the damage read "1". Labels are at least 0.06 of the width apart, so
    a digit can only ever belong to one of them.
    """
    width = frame.shape[1]
    scale = 2560 / width
    box = (STATS_BAND[0], STATS_Y[0], STATS_BAND[1], STATS_Y[1])
    mask, _ = _mask(crop(frame, box), scale, 150)
    by_label = {name: [] for name in STATS_CX}
    for b in _segment(mask):
        if b[2] > b[3]:                       # wider than tall: not a digit
            continue
        centre = STATS_BAND[0] + (b[0] + b[2] / 2) / 2560
        name = min(STATS_CX, key=lambda k: abs(STATS_CX[k] - centre))
        if abs(STATS_CX[name] - centre) <= STAT_REACH:
            by_label[name].append((b, classify_digit(_normalise(mask, b))))
    return mask, {k: sorted(v, key=lambda g: g[0][0]) for k, v in by_label.items()}


def _drop_percent(glyphs):
    """The % sign's two little circles are too small to segment, but its slash is
    as tall as a digit and survives as one trailing glyph. It is dropped only when
    the classifier positively names it "%". An earlier version dropped any
    unnamed trailing glyph, which silently turned "12" into "1" whenever the 2
    had no template yet -- a wrong number from a rule meant to avoid one."""
    if len(glyphs) > 1 and glyphs[-1][1] == "%":
        return glyphs[:-1]
    return glyphs


def read_stats(frame) -> dict:
    """The six numbers in the hero bar, each read from the digits over its label."""
    _, by_label = _stat_glyphs(frame)
    out = {}
    for name, glyphs in by_label.items():
        if name in PERCENTAGES:
            glyphs = _drop_percent(glyphs)
        out[name] = _number(glyphs) if glyphs else None
    return out


def learn(specs):
    """Print the GLYPHS literal from boards whose values a human has read.

    `specs` are (frame_path, {field: value}) pairs using this module's field
    names. Glyphs are labelled by position against the known value -- so a
    template can only be wrong if the hand-read value was -- and a field is
    skipped when the glyph count does not match, rather than guessed at.
    """
    import base64

    samples = {}
    for path, values in specs:
        frame = cv2.imread(str(path))
        if frame is None or frame.shape[1] < MIN_WIDTH:
            continue
        scale = 2560 / frame.shape[1]
        for name, (x0, x1) in KDA_X.items():
            if values.get(name) is None:
                continue
            mask = _gold_mask(crop(frame, (x0, KDA_Y[0], x1, KDA_Y[1])), scale)
            boxes = _segment(mask)
            text = str(values[name])
            if len(boxes) == len(text):
                for b, ch in zip(boxes, text):
                    samples.setdefault(ch, []).append(_normalise(mask, b))
        mask, by_label = _stat_glyphs(frame)
        for name, glyphs in by_label.items():
            if values.get(name) is None:
                continue
            text = str(values[name]) + ("%" if name in PERCENTAGES else "")
            if len(glyphs) == len(text):
                for (b, _), ch in zip(glyphs, text):
                    samples.setdefault(ch, []).append(_normalise(mask, b))
    lines = ["GLYPHS: dict[str, list[str]] = {"]
    for ch in sorted(samples):
        kept = []
        for g in samples[ch]:
            if not any(np.count_nonzero(g != k) <= 10 for k in kept):
                kept.append(g)
        lines.append(f'    "{ch}": [')
        lines += [f'        "{base64.b64encode(np.packbits(g.ravel()).tobytes()).decode()}",'
                  for g in kept]
        lines.append("    ],")
    lines.append("}")
    return "\n".join(lines)


def read_scoreboard(frame) -> dict:
    """Everything the range scoreboard says, as a plain dict.

    Keys: kos, deaths, assists, accuracy, damage, damage_blocked, healing,
    web_cluster_accuracy, spin_kos -- each an int or None -- plus `open`, which
    says whether a scoreboard was there at all. The two accuracies are whole
    percents; the rest are counts.

    None never means zero. A run that ends with `damage: None` did not deal no
    damage, it means nobody can say from this frame.
    """
    open_now = is_scoreboard(frame)
    blank = dict.fromkeys(FIELDS)
    if open_now is not True:
        return {"open": open_now, **blank}
    if frame.shape[1] < MIN_WIDTH:
        # Readable as a scoreboard, not readable as numbers.
        return {"open": True, "too_small": frame.shape[1], **blank}
    return {"open": True, **read_tallies(frame), **read_stats(frame)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("frames", nargs="+")
    a = p.parse_args(argv)
    for path in a.frames:
        frame = cv2.imread(path)
        if frame is None:
            print(json.dumps({"frame": path, "error": "unreadable"}))
            continue
        print(json.dumps({"frame": path, "rule_score": round(rule_score(frame), 3),
                          **read_scoreboard(frame)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
