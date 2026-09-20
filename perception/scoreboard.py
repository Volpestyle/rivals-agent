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
# read them and this one exists. Learned from the values on
# docs/evidence/l4/scoreboard-back-native.jpg, which a human read off the
# image: 3/0/1 tallies and 0% 845 0 0 50% 3 in the hero bar. Digits 2, 6, 7
# and 9 do not appear there yet; they will come from L4's extra frames, and
# until then a value containing one reads None rather than wrong.
GLYPHS: dict[str, list[str]] = {
    "0": [
        "f/7//P//+B/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/AP8A/wD/gf/////H/4",
    ],
    "1": [
        "/+D/4D/gB+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4AfgB+AH4Afg////////",
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
    "8": [
        "f/7/////8A/wD/AP8A/wD/AP+B9//n/+///wD/AP8A/wD/AP8A/wD/Af/////h/4",
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
# The scoreboard face is small: about 12 px per glyph on a 2560-wide capture, so
# about 6 px on a 1280-wide one. Upscaling that does not recover the shape, it
# invents one -- the 720p copy of the reference frame reads assists as 0 when it
# is 1 and Spectacular Spin KOs as 0 when it is 3. Values are only attempted at
# a width where the glyphs are really there.
MIN_WIDTH = 1920
PERCENTAGES = ("accuracy", "web_cluster_accuracy")
FIELDS = tuple(KDA_X) + tuple(STATS_CX)


def _gold_mask(img, scale):
    """Gold text off the strongest channel. The tallies are drawn in gold and a
    min-channel mask -- what reads the rest of the HUD -- sees nothing there."""
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    mx = img.max(axis=2)
    top = cv2.morphologyEx(mx, cv2.MORPH_TOPHAT,
                           cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)))
    return ((top > 40) & (mx > 140)).astype(np.uint8)


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


def read_stats(frame) -> dict:
    """The six numbers in the hero bar, matched to their labels by position.

    Read as one band and assigned to the nearest label centre rather than cut
    into six boxes: the numbers are centred over their labels, so a wider value
    grows both ways and a fixed box clips it.
    """
    out = dict.fromkeys(STATS_CX)
    width = frame.shape[1]
    scale = 2560 / width
    box = (STATS_BAND[0], STATS_Y[0], STATS_BAND[1], STATS_Y[1])
    mask, _ = _mask(crop(frame, box), scale, 150)
    glyphs = [(b, classify_digit(_normalise(mask, b))) for b in _segment(mask)]
    for group in _groups(glyphs):
        digits = [g for g in group if g[1] is None or g[1].isdigit()]
        if not digits:
            continue
        first, last = digits[0][0], digits[-1][0]
        centre = STATS_BAND[0] + ((first[0] + last[0] + last[2]) / 2) / 2560
        name = min(STATS_CX, key=lambda k: abs(STATS_CX[k] - centre))
        if abs(STATS_CX[name] - centre) > 0.025:   # nowhere near a label
            continue
        value = _number(digits)
        if value is not None and out[name] is None:
            out[name] = value
    return out


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
