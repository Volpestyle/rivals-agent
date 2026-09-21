"""Ability events from HUD reads over time, for labelling video that has no input log.

  uv run --group perception python -m perception.events <run_dir> <out.jsonl>

Input is one `perception.hud.Hud` per frame with its index and time; output is
one event per line. Two ideas carry the whole file.

**Segment first.** A stream of frames is not one continuous performance: the
player dies, respawns, spectates someone else, swaps hero, opens a menu, or goes
to a BRB screen. `segment()` cuts the run at those points and records why each
piece started and ended, and `extract()` restarts every channel at each
boundary, so no event is ever produced across one. The minimum gate is a
hero-portrait check that Spider-Man is the hero being *played*: without it the
spectating stretch of the sample VOD reads a stranger's health as ours (665 hp
on a Spider-Man whose maximum is 250).

**Events are weak labels.** A transition says an ability was used *somewhere
between two frames*, not at an instant. Every event therefore carries an
interval - `i_from`/`t_from`, the last frame showing the old value, and
`i_to`/`t_to`, the first frame showing the new one - and no field claims a press
time. At 10 fps that interval is about 100 ms wide; at 60 fps it is narrower.

What counts as a value:

- **An unknown read (None) is not a value.** It emits nothing and it does not end
  the run of the value before it: a frame the readers could not read leaves the
  state exactly as it was.
- **A new value must persist to be confirmed**, for as many frames as that
  channel's `DEBOUNCE` says. Slow channels get 2, so a single-frame misread
  cannot invent an event.
- **`ready` is the exception and gets 1**, because on this HUD a real ability use
  is a *one-frame* red flash at 10 fps. Of the 179 red stretches in run1, 165 are
  a single frame and 12 are two; debouncing that channel at 2 would throw away
  nearly every real use. Verified by eye on frames 49-51 and 245-247, where the
  Web-Swing icon is plainly red for one frame while its neighbours stay white.
  The cost is that a single-frame *misread* there also becomes an event; the
  guard is that the readers return None rather than a wrong boolean.

Nothing here is specialised to the practice range. The range simply never
produces some of these events - its ammo count never moves off 5, the bots never
damage the player, and a roaming routine never casts the ult - so a range
recording yields no `web_cluster_fired`, `hp_lost`, `death`, `respawn` or
`ult_spent`. A real match produces all of them, and the same code reads them.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import zlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `agent`

from perception.hud import SLOT_CX, Hud  # noqa: E402

# Frames a new value must hold before it is believed. `ready` is 1 on purpose;
# see the module docstring.
# hp is 1 on purpose: at 10 Hz a burst of hits shows as one value per frame, and
# asking a step to persist for two merges them. A 250 -> 195 -> 220 sequence came
# out as a single net loss of 30, which is not a thing that happened to anybody.
# Raw steps, always; a net figure is never reported as damage.
DEBOUNCE = {"ready": 1, "charges": 2, "webs": 2, "hp": 1, "max_hp": 2, "ult_ready": 1,
            "killfeed": 2, "cooldown": 1}
SHIELD_WINDOW = 3   # frames apart that an hp and a max-hp change may still be one shield tick
# 1: ability_used / ability_ready, slot "pull".
# 2: those split into ability_cast (a cooldown number appeared or a charge went
#    down -- proof the ability fired) and slot_unavailable / slot_available (the
#    icon dimmed, which is a lockout and happens on wall climbs and mid-swing);
#    slot "pull" renamed get_over_here; hp emits raw steps, never a net.
# 3: `slot` is the ability the icon says is in that position, or null when the
#    icon could not be identified; `slot_pos` keeps the layout position. The
#    meta line carries the mapping and how it was decided. A slot position names
#    no ability by itself -- the binding is a player setting, and the two guide
#    sources have Web-Swing and Get Over Here the other way round from the clip
#    the layout was measured on.
# 4: edited sources. Segments break on an editorial cut, with `ended_by`
#    "hard_cut" and `started_by` "after_cut"; the meta line gains `cuts` (how
#    many were found, 0 for a continuous capture) and `observed` (the cooldowns
#    this source's own HUD showed, a patch fingerprint). `slot_mapping` is null
#    when no mapping was attempted, where it was previously {} -- {} now means
#    only that the icons were read and none identified.
#    Later additions, all optional so a format-4 reader stays correct: meta
#    `cut_times` and `recipe`, segment `cooldowns`, and a cut inside a gap
#    marking both sides with the existing hard_cut / after_cut values -- which
#    only ever makes a reader more conservative. `check` finds files written
#    before them by the keys they lack (REQUIRED_META), not by a version bump.
# 5: cooldowns are timers identified by expiry, so a countdown read again after
#    unread frames is the same cooldown, not a new cast. New kinds
#    `ability_uncertain` (a cast that cannot be told from a timer becoming
#    readable) and `cooldown_ended` (a timer ran out inside watched play). The
#    icon events are display state, renamed `icon_dimmed` / `icon_lit` from
#    slot_unavailable / slot_available. hp_lost / hp_gained carry `cause`:
#    damage / heal only with max hp read unchanged on both sides, else unknown.
#    The meta line gains `timer_lengths`.
FORMAT_VERSION = 5
REQUIRED_META = ("recipe", "cut_times", "observed", "slot_mapping", "writer",
                 "container_start_s", "stream_start_s", "timer_lengths")
# The code whose behaviour decides what an events file contains.
WRITER_FILES = ("perception/events.py", "perception/hud.py", "perception/scoreboard.py")


def writer_version():
    """Fingerprint of the code that writes events files: the first 12 hex of a
    SHA-256 over WRITER_FILES. A file stamped with anything else was written by
    other code -- even a fix that left the format number alone -- and `check`
    reports it, so "every file is from the current writer" is verified, not
    asserted."""
    import hashlib

    root = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()
    for name in WRITER_FILES:
        h.update((root / name).read_bytes())
    return h.hexdigest()[:12]
ULT = "ult"

# --- is Spider-Man the hero being played? ---------------------------------
PORTRAIT = (0.015, 0.84, 0.100, 0.96)   # bottom-left hero portrait, frame fractions
PORTRAIT_SCALES = (0.8, 0.95, 1.1, 1.3, 1.5)
# Measured: Spider-Man 0.347-0.516 across the range captures, a 1080p stream and a
# second streamer on a different skin; other heroes 0.225-0.304, including the
# spectating still. The band between is reported as unknown rather than guessed.
PORTRAIT_MATCH, PORTRAIT_CLEAR = 0.34, 0.31
# A one-class threshold cannot reject a hero it never saw: Doctor Strange scores
# 0.32-0.40 against the Spider-Man template, inside Spider-Man's own band, and a
# minute of DayMR on Strange passed as ours. Known other heroes are therefore
# matched as negatives too, on an absolute bar -- not "nearer class wins", which
# fails because the colour match is weak: real Spider-Man frames score 0.46-0.48
# against the Strange template, *higher* than against his own. Measured over 89
# kept frames from every source, the highest against Strange is 0.69 (a frame an
# editor had blurred whole); Strange himself is 0.78-1.00. The bar sits between,
# and PORTRAIT_HOLD absorbs the odd blurred frame. The gap is narrow -- see the
# lane notes -- and hp cannot back it up: Spider-Man in his ultimate with a
# shield reads 650/650, exactly Strange's base maximum.
PORTRAIT_OTHER = 0.75
# The verdict gets the same debounce treatment as any other channel. Without it
# the spectating stretch of the sample VOD, where the portrait sits near the
# boundary, shatters into ten two-frame segments instead of one.
PORTRAIT_HOLD = 3
# A real menu, death screen or BRB card lasts far longer than half a second; a
# shorter gap in the HUD is the readers losing it against the scenery.
HUD_HOLD = 6

# Two 40x30 BGR crops of the hero portrait, one from the 1280x720 range capture and one
# from a 1080p stream frame, zlib+base64. Matched in colour: greyscale gives no
# separation at all (every hero scores 0.34-0.45), while colour puts Spider-Man at
# 0.35-0.52 and everyone else at 0.23-0.30.
_PORTRAITS_B64 = (
    "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"
    "vjuE+r8C/tJm"
)


# Other heroes' portraits, same 40x30 BGR layout, one per hero found passing as
# ours: Doctor Strange (DayMR playing him, daymr-2879354299 at 830 s), then the
# two teammates DayMR spectates in that section -- a bearded hero (80.5 s) and a
# white-haired one (84.3 s). Each teammate passed the one-class match at
# 0.36-0.38 and was kept as own play in several stretches (around 81, 85, 201,
# 363, 693 and 718 s). Measured on 391 real Spider-Man frames from every source
# and both train sections, the highest score against these three is 0.705; the
# teammates themselves score 0.72-0.99, and the one frame under the bar is
# absorbed by PORTRAIT_HOLD.
_OTHER_HEROES_B64 = (
    "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"
    "toTBfOU/m9fFRhw+kJSbdbSuuuz4QPfJ8eOnJkbAOnq8b6C3M+toxt4dScU5xR+888EPf/vh43efdjR0RbqiVVLtqzfvf/z4"
    "k9baDoPCLGHDz7oP5CvV4HMYClhsM+vWr40EOcuK81oaa/q620aGesdHBvu7eptrm8cGxr7/5ntg/vDxx9Njs+X5VaAI3339"
    "t6fvflaRX4MIVFIOsjlKY4KZIipOJxRaYLlDpQk1mmND3Qkb41KSdxfnZVSWlBTkVlZV9tbUD9e1nOwaujR06u7A9IOB0+90"
    "nHyzeuBuYcv17NrF3PrLFe23mwZebx95q23sYVnPkkvH1ojICJtgELPNkNCqkIUaNeu8IUlb1+ek7K8tzW2oqirNr66v6W9q"
    "HGlsPdU3cnVk5t7I3JvD878cnH/SdvKtsu6lzKqFI4UzR/Km0gpmjhadTi2YCd9S7dLyPeC/AxXbImcaYYYBDrapBVEhmj3x"
    "UQVp+1sqijrr6ioLappq+1qaRlvaTw2MXR07fX9s/uHowuMTix/1n363uvfltNLZhMN9cTsaojZVhseVuGKKBJqkzKT4TV69"
    "XcmyKIOtSqZDw42wwttjHOm7N1dlpnSUFXVU1dQU1rTW9bU1j7Z1nBoauzo+d398/uHYwrvAPHDmSW3/K+lls9sPdgGtMyLX"
    "6s4whaQ7Y0one1pyD2zfGecI1Qu9RvGWSMvR3Ruqsw53lhV0l5W0FBTU5hTUFtS01fZ2NI92dEwOjV0eP31vfP7B2MI74xfe"
    "H5p/t3XstdLWK+kl0/uPDu060JW4tz1xb/exwnPvP7jXVVu2Nz7SoxducClzkjYO1RQtDvddGxuebmtuycksPniovqCio7ar"
    "u+l4d9vJsdErp2ZePTX35uTZd6YW3j959oORmXd7x99sG7jb3HW7ueNWW9fttu5Xmzve+NXTDxcX5spyj+xZby45EHO+u+LJ"
    "+ZmPLl98fWpytrG69vDO3MT46a6e8baB2f7pyZ65cxO3z5y4uzD11uzEm2emH585/f7szJPp6Xenpp9MzTyZPPX4xIlHQ0Nv"
    "1dbdefrrz15/+Nrs1EBBWkxbwfobg8W/vjb751dvfLx4+lxrcdGu0NR4+2Rb/VBN01hD72BV/3zf4lTHpdM9SzO9r8wM3J8c"
    "uD/e9+pI753jfXcGel/pbL/ZWLdYUjgfF1P/5Tf/8esvP7//+vmmuoRjycraVMebUzXfPJj/9Prxcz1p2fu1+zYrGvMOVR9N"
    "b8svb89vGCgf6i4eGamdP9F8eazl6lDT5a66C82VZ2pKp4vzxjPSBvYntW2Lb1BBRz7/6o//+c2fPnl6b2wkbesG+hYv6mJf"
    "0p/e7P/4Zt2547vzM1VJCdKKzB3Fh/Y35xW05FXVZ9Q2HGsfrDo1VHfmeMPCQMNCe/VcbfHJwqzBlANtO7ZVxkXnhTlzot21"
    "N+4++uLpb7/6/IOly63ZKbp4r3/9MdXd2f2PLmecH9tWkqU+sBNurzjYU5XfUVpYm5XfkF3VUdzZVznSXzN5vPHMYNPZztrZ"
    "+tITBcd6D+9v2BZfFBOe6XEc2xjZWll74sLUK2/fvPfha/OLJzOy9ooSIv0bcxUvn9l9dXJPbZY9JUFdn7dzpKW4r6aoqSCv"
    "vbhmoKant7JvoG5ssOFUX/1UV92ppsrx0rz+jCPNexMrtm8s2hBVHG4rjd5w7GhyU2tJ9xuXzr3/ynh/7YZ4L25fPGWqd93t"
    "2ayRqt15u0IPb7VXZe083lwy3dvWWlTcXlLbWdbaVdHVXt7bXjnYXjPSUjNSWzZUktuTfbQ943Br6r6OpM2dnnUpUdEZCRsz"
    "Oyqb3roxf2Wq+tB2pduwOvuA9vJY0WJ3bXPanqQ4w6GEkM6q9Eun+iszU4tT0ioz84tTckvTS6pz6+tL25sqexsrB2pKByqL"
    "ByuLjlcVTdTkn8lp7Nmb3Ri/N+dw2rGb1849fnBhsCNt5yZ1erLn/FjNrRODYzXF2fsiDyc6ClPje+tycvYlHN25PXVn4sEt"
    "O4/s2J+5Pz0/taAku6oiv7GioK2qqLu2ZLC+fKK36dKrv/lw/sk7PTeujC1dvP72rXc+fvWTT+4+fDBz81r3vRvjb92a/+XL"
    "5167PnzjbOvUQElzyeHcA9uSN69NiI7Y5PVuCovYHBm7NWbjjg0JSVv3H0hMS9mbk5FcknW4tr9l/pMf/vzw+y9vfv3h0teP"
    "Xv36jXe+evDlt+/95dt3vv7qzm8/u/HuG2fuLA5M9GX3NBwsy9x8cIt7Y6g23IA4VTKbXGZVwGY5YoQRnUyhk2kMiMmscNg1"
    "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"
    "Tyk="
)


_PORTRAIT_CACHE: list = []
_OTHER_CACHE: list = []


def _others():
    if not _OTHER_CACHE:
        raw = zlib.decompress(base64.b64decode("".join(_OTHER_HEROES_B64)))
        _OTHER_CACHE.extend(np.frombuffer(raw, np.uint8).reshape(-1, 40, 30, 3).astype(np.float32))
    return _OTHER_CACHE


def _portraits():
    if not _PORTRAIT_CACHE:
        raw = zlib.decompress(base64.b64decode("".join(_PORTRAITS_B64)))
        _PORTRAIT_CACHE.extend(np.frombuffer(raw, np.uint8).reshape(-1, 40, 30, 3).astype(np.float32))
    return _PORTRAIT_CACHE


def portrait_score(frame, templates=None) -> float:
    """Best colour match for the Spider-Man portrait (or `templates`) in the hero slot."""
    import cv2

    height, width = frame.shape[:2]
    x0, y0, x1, y1 = PORTRAIT
    region = frame[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)]
    region = region.astype(np.float32)
    best = 0.0
    for tpl in (_portraits() if templates is None else templates):
        for scale in PORTRAIT_SCALES:
            t = cv2.resize(tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
                continue
            best = max(best, float(cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


def playing_spiderman(frame) -> bool | None:
    """True, False, or None when the portrait slot is too ambiguous to call."""
    if portrait_score(frame, _others()) >= PORTRAIT_OTHER:
        return False
    score = portrait_score(frame)
    if score >= PORTRAIT_MATCH:
        return True
    if score <= PORTRAIT_CLEAR:
        return False
    return None



# --- the yellow status banner, top left ----------------------------------
# While the player is out of the fight the game draws a yellow banner beside the
# respawn countdown. The word in it says which state this is, and the two look
# identical to everything except their ink: PAST LIVES is the killcam, showing
# the killer's view and *their* HUD, and SPECTATING is watching a teammate.
# Both must end a segment; they are different reasons and the lead wants them
# told apart, so the words are matched as 32x112 ink masks.
BANNER = (0.075, 0.052, 0.215, 0.092)
BANNER_WORDS = ("killcam", "spectating")   # order matches the packed templates
BANNER_MATCH = 0.55        # agreement with the better word
BANNER_MARGIN = 0.03       # ... and by this much over the other one
BANNER_HOLD = 3            # frames the banner must persist to be believed
SCOREBOARD_HOLD = 2        # a scoreboard tap: see segment()
# The game area's brightest channel, averaged, on a respawn or loading black is
# 0-5; on every other frame of the two train sections it is 22 or more.
BLACK_LEVEL = 8.0
BLACK_AREA = (0.2, 0.2, 0.8, 0.75)     # the game area, clear of overlays at the edges


def is_black(frame) -> bool:
    x0, y0, x1, y1 = BLACK_AREA
    h, w = frame.shape[:2]
    return float(frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].max(axis=2).mean()) < BLACK_LEVEL
_BANNER_B64 = (
    "eNrtmEkWgzAMQ6X7X7oL0uAhDdgE6MLalIbhvwz2swyUSiUnrtAf80qlUunmDNou+0DPdNsAvj/9f7uZyGbyu5Jjxxtm"
    "u2g3E+lzT7l6XvzJ4y08vMKD3T+67YvzYHj7NkHwqHn63QSPgocJj5qXCIcBD2d5XMDjAU9uKZENv2MeJE8/e4EHcyxl"
    "OMCcZeTTizhqOo39A0+seVWDpdK7/u98FPJhXqlUKt2dQk0pxOEwZAGjCv94B637FuN8qHn7U8a78DFeMF9zxuOEx3U8"
    "eJ4zv+7FgF9BXyFacynPCWTZ65Y2xDN2JMpDkAeM5gfTtJjwwtGnugGe5+anjEfYcNqwECFM4pAXCvhR28Xx+rpRd3yY"
    "6Blc5vEaT/vINbwP4AYFJA=="
)
_BANNER_CACHE: list = []


def _banner_templates():
    if not _BANNER_CACHE:
        raw = zlib.decompress(base64.b64decode("".join(_BANNER_B64)))
        _BANNER_CACHE.extend(np.frombuffer(raw, np.uint8).reshape(-1, 32, 112).astype(bool))
    return _BANNER_CACHE


def banner_word(frame):
    """'killcam', 'spectating', or None when no banner is legible."""
    import cv2

    height, width = frame.shape[:2]
    x0, y0, x1, y1 = BANNER
    region = frame[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)]
    if region.size == 0:
        return None
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    ink = ((hue > 20) & (hue < 40) & (sat > 110) & (val > 150)).astype(np.uint8)
    if ink.mean() < 0.04:                      # no banner drawn at all
        return None
    ink = cv2.resize(ink * 255, (112, 32), interpolation=cv2.INTER_AREA) > 127
    scores = [float((ink == t).mean()) for t in _banner_templates()]
    best = max(range(len(scores)), key=lambda i: scores[i])
    others = [s for i, s in enumerate(scores) if i != best]
    if scores[best] < BANNER_MATCH or (others and scores[best] - max(others) < BANNER_MARGIN):
        return None
    return BANNER_WORDS[best]


# --- segments -------------------------------------------------------------

@dataclass(frozen=True)
class Segment:
    """A stretch of frames that is one continuous performance by our hero."""

    start_i: int
    start_t: float
    end_i: int
    end_t: float
    started_by: str   # run_start | respawn | hero_returned | hud_returned | ... | after_cut
    ended_by: str     # run_end | death | killcam | spectating | scoreboard
                      #   | not_our_hero | no_hud | hard_cut
    # What the HUD proves about cooldowns here: "normal" once a countdown was
    # seen, "unknown" otherwise. Never "off" -- the HUD cannot prove an absence.
    cooldowns: str = "unknown"

    @property
    def frames(self):
        return self.end_i - self.start_i + 1


def _hud_present(hud):
    return hud.hp is not None or hud.bar_fill is not None


def _steady(verdicts, hold):
    """Per-frame verdicts with brief blips absorbed into their surroundings.

    A run shorter than `hold` is only noise if the value returns to what it was
    either side of it -- a two-frame dropout inside a minute of play. A short
    run that sits between two *different* values, or at either end of the clip,
    is a real change caught briefly and is kept. None always inherits whatever
    was last believed.
    """
    runs, start = [], 0
    for i in range(1, len(verdicts) + 1):
        if i == len(verdicts) or verdicts[i] != verdicts[start]:
            runs.append([start, i, verdicts[start]])
            start = i
    resolved = []
    for n, (begin, end, value) in enumerate(runs):
        if value is None:
            resolved.append(None)         # fill from the left below
        elif (end - begin) >= hold:
            resolved.append(value)
        else:
            before = next((runs[m][2] for m in range(n - 1, -1, -1)
                           if runs[m][2] is not None), None)
            after = next((runs[m][2] for m in range(n + 1, len(runs))
                          if runs[m][2] is not None), None)
            resolved.append(None if before is not None and before == after else value)
    steady, believed = [], None
    for (begin, end, _), value in zip(runs, resolved):
        if value is not None:
            believed = value
        steady.extend([believed] * (end - begin))
    first = next((v for v in steady if v is not None), None)
    return [first if v is None else v for v in steady]


def segment(reads):
    """[Segment] over (i, t, hud, playing) reads.

    A segment breaks where the hero being played is *known* not to be ours,
    where the HUD is gone (menu, BRB, loading, spectating overlay), and where hp
    reaches zero. An unknown portrait verdict does not break it, for the same
    reason an unknown HUD read does not: not knowing is not evidence.

    An edited source breaks on its cuts too: a seventh item in a read marks a
    frame the editor spliced to, so no segment spans an edit. See `scene_cuts`.
    """
    # Reads are (i, t, hud, playing) and may carry a fifth item: the word in the
    # top-left status banner, when one is up.
    # "" rather than None for "no banner": absence here is a real reading, not an
    # unknown, and _steady carries unknowns forward from the last belief.
    asides = [(r[4] if len(r) > 4 else None) or "" for r in reads]
    banners = _steady([a if a in BANNER_WORDS else "" for a in asides], BANNER_HOLD)
    # The scoreboard votes on its own, shorter hold. A player tapping the board
    # holds it up for two or three frames at 10 Hz, one of them a fade the
    # detector does not score; three frames of agreement missed those taps, and
    # a countdown unreadable behind the board then came back as a new cast.
    boards = _steady([a == "scoreboard" for a in asides], SCOREBOARD_HOLD)
    # A black game area is a screen transition -- respawn, a loading cut -- and
    # breaks at once: it is one or two frames long, far shorter than HUD_HOLD,
    # and the HUD on its far side may belong to a different life.
    black = [a == "black" for a in asides]
    playing_steady = _steady([r[3] for r in reads], PORTRAIT_HOLD)
    # The HUD gets the same treatment. A handful of frames where neither the hp
    # digits nor the bar could be read is the readers struggling, not a menu:
    # untreated it cuts one 60 s clip into nine pieces.
    hud_steady = _steady([_hud_present(r[2]) for r in reads], HUD_HOLD)
    segments, start, last, reason = [], None, None, "run_start"
    cut_in_gap = False   # a cut has fallen somewhere in the current gap
    for n, read in enumerate(reads):
        i, t, hud = read[0], read[1], read[2]
        playing = playing_steady[n]
        dead = hud.hp == 0
        # The cut comes before every game-side reason: it says the two sides of
        # this boundary are unrelated footage, which is true whatever the HUD
        # was doing. Nothing else can be trusted across it.
        cut = len(read) > 6 and read[6]
        # Death first: it is the earlier and more specific fact, and the killcam
        # that follows is then simply outside any segment. The banner comes next
        # because killcam looks exactly like spectating to every other signal --
        # a foreign hero with a perfectly readable HUD -- and the two are
        # different things to anything learning from these labels.
        broken = (cut and "hard_cut") or (dead and "death") \
            or (black[n] and "no_hud") or banners[n] or (boards[n] and "scoreboard") \
            or (playing is False and "not_our_hero") \
            or (not hud_steady[n] and "no_hud")
        if broken:
            if start is not None:
                segments.append(Segment(start[0], start[1], last[0], last[1], reason, broken))
                start = None
            elif broken == "hard_cut" and segments and not cut_in_gap:
                # A cut inside a gap that opened for another reason -- most often a
                # scoreboard tap. The far side is unrelated footage, so the gap must
                # never be bridged, and a loader that bridges short scoreboard gaps
                # would do exactly that. The cut outranks the reason the gap opened.
                segments[-1] = replace(segments[-1], ended_by="hard_cut")
            cut_in_gap = cut_in_gap or broken == "hard_cut"
            reason = "after_cut" if cut_in_gap else {
                "death": "respawn", "not_our_hero": "hero_returned",
                "killcam": "killcam_over", "spectating": "spectating_over",
                "scoreboard": "scoreboard_closed"}.get(broken, "hud_returned")
            continue
        if start is None:
            start = (i, t)
            cut_in_gap = False
        last = (i, t)
    if start is not None:
        segments.append(Segment(start[0], start[1], last[0], last[1], reason, "run_end"))
    return segments


# --- events ---------------------------------------------------------------

@dataclass(frozen=True)
class Event:
    """One transition. The press happened somewhere in [t_from, t_to]."""

    kind: str
    i_from: int       # last frame proving the old value
    t_from: float
    i_to: int         # first frame proving the new value
    t_to: float
    slot: str | None = None       # the ability, or None when the icon is unknown
    slot_pos: str | None = None   # the layout position it fired in
    amount: float | None = None
    before: object = None
    after: object = None
    segment: int = 0  # index into the segment list this event belongs to
    # hp_lost / hp_gained only: "damage" / "heal" when max hp was read unchanged
    # on both sides, else "unknown". A change in hp alone does not say why.
    cause: str | None = None


class _Channel:
    """One signal through time, with debounce and None-means-nothing."""

    __slots__ = ("hold", "value", "at_i", "at_t", "cand", "count", "cand_i", "cand_t")

    def __init__(self, hold):
        self.hold = hold
        self.value = self.cand = _MISSING
        self.at_i = self.cand_i = -1
        self.at_t = self.cand_t = 0.0
        self.count = 0

    def push(self, i, t, v):
        """Returns (before, after, from_i, from_t) when a transition is confirmed."""
        if v is None:                      # unknown: not a value, not a break
            return None
        if self.value is _MISSING:         # first sighting: nothing to debounce against
            self.value, self.at_i, self.at_t = v, i, t
            return None
        if v == self.value:                # still the confirmed value
            self.at_i, self.at_t, self.cand, self.count = i, t, _MISSING, 0
            return None
        if v != self.cand:                 # a new candidate starts counting again
            self.cand, self.count, self.cand_i, self.cand_t = v, 1, i, t
        else:
            self.count += 1
        if self.count < self.hold:
            return None
        before, from_i, from_t = self.value, self.at_i, self.at_t
        self.value, self.at_i, self.at_t = v, i, t
        self.cand, self.count = _MISSING, 0
        if before is _MISSING:             # first reading of this channel is not a change
            return None
        return before, v, from_i, from_t


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


def _signals(hud: Hud):
    """The channels one frame contributes, as {name: value or None}."""
    out = {"hp": hud.hp, "max_hp": hud.max_hp, "webs": hud.webs, "ult_ready": hud.ult_ready}
    for slot in hud.abilities or SLOT_CX:
        ready, charges = hud.abilities.get(slot, (None, None))
        out[f"ready:{slot}"] = ready
        out[f"charges:{slot}"] = charges
    # Countdowns are not a channel: they are timers, handled by _timer_events.
    return out


def _near(known, i, span=4):
    """The nearest recorded value within `span` frames of `i`, or None.

    max hp is unreadable on a few per cent of frames and its debounce coalesces
    consecutive shield ticks, so asking for its value at one exact frame misses
    more often than it should.
    """
    for d in range(span + 1):
        for j in (i - d, i + d):
            if j in known:
                return known[j]
    return None


def _kind(name, before, after, max_before=None, max_after=None):
    """(kind, slot, amount) for a confirmed transition, or None to emit nothing."""
    if name == "ult_ready":
        return ("ult_ready" if after else "ult_spent"), ULT, None
    if name.startswith("ready:"):
        slot = name.split(":", 1)[1]
        if slot == ULT:                    # the ult has its own channel above
            return None
        # What the icon looks like, and nothing more. It dims or shows a red
        # prohibition mark while crawling, wall-running, charmed, mid-swing --
        # and on a stream HUD it stays lit through much of its own cooldown. It
        # certifies neither a cast nor availability: only a countdown (ability_
        # cast, cooldown_ended) or a charge change (charges_*) does that.
        return ("icon_lit" if after else "icon_dimmed"), slot, None
    if name.startswith("cooldown:"):
        slot = name.split(":", 1)[1]
        if before == "off" and after != "off":
            return "ability_cast", slot, after    # amount = the cooldown it started
        return None                               # a countdown ticking or ending
    if name.startswith("charges:"):
        slot = name.split(":", 1)[1]
        delta = after - before
        return ("charges_regained" if delta > 0 else "charges_spent"), slot, abs(delta)
    if name == "webs":
        delta = after - before
        return ("web_cluster_reloaded" if delta > 0 else "web_cluster_fired"), None, abs(delta)
    if name == "hp":
        if after == 0:
            return "death", None, before
        if before == 0:
            return "respawn", None, after
        delta = after - before
        # Damage leaves hp below max. If hp is still exactly max after the drop,
        # the pool itself shrank -- the team-up shield bleeding away -- and
        # calling that `hp_lost` would teach anything learning from these labels
        # that the practice range hurts you, which it never does.
        # >= rather than ==: max hp is read a frame or two behind hp, so hp can
        # briefly look higher than the last max we managed to read.
        if max_before is not None and max_after is not None \
                and before >= max_before and after >= max_after:
            return ("shield_gained" if delta > 0 else "shield_decayed"), None, abs(delta)
        # A change in hp alone is not damage or healing. Bonus health -- a
        # team-up shield decaying, an ultimate's +250 -- moves hp too, and moves
        # max hp with it. Only with max hp read, and unchanged, on both sides
        # is the cause known. Unreadable max hp is common exactly there (Day
        # 63-70 s: ten "damage" events that were a shield decaying; 342 s: a
        # "heal" of 255 that was an ultimate), so the rest say so.
        known = max_before is not None and max_after is not None and max_before == max_after
        cause = ("heal" if delta > 0 else "damage") if known else "unknown"
        return ("hp_gained" if delta > 0 else "hp_lost"), None, abs(delta), cause
    if name == "max_hp":
        return "max_hp_changed", None, after - before
    if name == "killfeed":
        # Only the appearance is an event. A line fading out means nothing.
        return ("ko_feed", None, None) if after else None
    return None


DAMAGE_STRIPE = 0.03    # red on the bar above this means a hit really landed
SPIKE_FRACTION = 0.4    # a one-frame excursion bigger than this share of max hp


def _despike(values, damaged=None, max_hp=None):
    """Drop a one-frame excursion that is too big to be real and that the hp bar
    does not corroborate.

    hp confirms on a single frame so that consecutive steps stay separate: at
    10 Hz, 250 -> 195 -> 220 is three things that happened, and asking each step
    to persist merged them into one net loss of 30, which is not a thing that
    happened to anybody. Raw steps are what this emits.

    The cost of a one-frame confirm is that a misread becomes two events, so it
    is worth removing the ones that cannot be real. Two conditions, both needed:
    the value jumps and the *exact* previous number comes straight back, and the
    jump is more than SPIKE_FRACTION of maximum health, and the bar shows no
    fresh red damage stripe. An earlier version filtered on the shape alone and
    deleted a real 25 hp hit that was healed straight back -- and, worse, the
    heal frame between two hits, which erased the second hit as well.
    """
    out = list(values)
    ceiling = max((v for v in (max_hp or []) if v), default=None) or 250
    for i in range(1, len(out) - 1):
        if out[i] is None or out[i - 1] is None or out[i + 1] is None:
            continue
        if out[i] == out[i - 1] or out[i + 1] != out[i - 1]:
            continue
        if damaged and damaged[i]:
            continue                       # the bar says this hit was real
        if abs(out[i] - out[i - 1]) > SPIKE_FRACTION * ceiling:
            out[i] = None
    return out


def extract_one(reads, debounce=None, seg_index=0, mapping=None, timers=None):
    """[Event] for a single segment of (i, t, Hud) reads, in time order.

    `timers` is {position: full countdown length in s} for this source (see
    timer_lengths); without it casts are still found, with fewer kit checks.
    """
    holds = {**DEBOUNCE, **(debounce or {})}

    def hold_for(name):
        return holds.get(name.split(":", 1)[0], 2)

    channels, events, max_seen = {}, [], {}
    hp_clean = _despike([r[2].hp for r in reads],
                        [(r[2].bar_damage or 0) > DAMAGE_STRIPE for r in reads],
                        [r[2].max_hp for r in reads])
    for n, read in enumerate(reads):
        i, t, hud = read[0], read[1], read[2]
        if hud.max_hp is not None:
            max_seen[i] = hud.max_hp
        signals = _signals(hud)
        signals["hp"] = hp_clean[n]
        if len(read) > 3:                 # optional: is a kill-feed line up?
            signals["killfeed"] = read[3]
        for name, value in signals.items():
            ch = channels.get(name)
            if ch is None:
                ch = channels[name] = _Channel(hold_for(name))
            moved = ch.push(i, t, value)
            if moved is None:
                continue
            before, after, from_i, from_t = moved
            described = _kind(name, before, after,
                              _near(max_seen, from_i), _near(max_seen, i))
            if described is None:
                continue
            kind, slot, amount, *rest = described
            cause = rest[0] if rest else None
            # `slot` here is the layout POSITION. Turning it into an ability
            # name needs the icon mapping, and without one the name is unknown:
            # the position order differs per player, so copying the position
            # across is a guess, and wrong on every source that swaps two slots.
            # A mapping that omits a position means its icon could not be read,
            # which is the same unknown. The ult is exempt -- there is one, and
            # no icon has to be identified to know which.
            if not slot or slot == ULT:
                named = slot
            else:
                named = mapping.get(slot) if mapping else None
            events.append(Event(kind=kind, i_from=from_i, t_from=from_t, i_to=i, t_to=t,
                                slot=named, slot_pos=slot, amount=amount,
                                before=before, after=after, segment=seg_index, cause=cause))
    positions = sorted({p for r in reads for p in (r[2].cooldowns or {})})
    for pos in positions:
        ability = mapping.get(pos) if mapping else None
        events.extend(_timer_events(reads, pos, ability, (timers or {}).get(pos), seg_index))
    events.sort(key=lambda e: (e.t_to, e.kind))
    return _merge_shield(events)


# --- countdown timers --------------------------------------------------------
# A countdown is a timer, and a timer is identified by when it will expire. The
# slot draws whole seconds rounded up, so a read of N at time t says the timer
# expires in (t + N - 1, t + N]. Two reads whose expiry windows overlap are the
# same timer, however many frames between them went unread. That is the whole
# fix for "a continuing cooldown re-read as a new cast": the old channel treated
# a countdown it failed to read for two frames as ended ("off"), and its return
# as a fresh one. A missing read now changes nothing -- it is never taken as the
# cooldown ending (it is also every visible digit the reader could not read).
TIMER_EPS = 0.15        # s of slack on an expiry window: frame timing and rounding
TIMER_CONFIRM = 2       # reads that must agree before a new timer is believed
KIT_TOL = 0.6           # s: how early a restart may look and still fit the kit
BLIND_LOOKBACK = 3.0    # s before a charged slot's new timer that must have been observable
# Slots that hold charges. A use while a recharge runs does not restart it (the
# charge count drops instead, a separate channel), and a finished recharge
# starts the next at once. Hero structure from docs/spiderman-kit.md, not a
# balance value: charge counts and lengths vary by patch, which charges do not.
CHARGED = {"swing", "uppercut"}
# A charged slot's timer is the recharge of its next charge, and it is rarely
# first seen full, so its length cannot be measured the way a one-charge slot's
# can (timer_lengths gives 3-5 for these on the train sections). It comes from
# the kit instead: 6 s per charge for both, in docs/spiderman-kit.md, and the
# same on both patches in its balance history (Season 10 moved only Amazing
# Combo's 2 s -> 1 s between-cast time, which this model does not use).
RECHARGE_S = {"swing": 6.0, "uppercut": 6.0}
TIMER_MIN_SPAN = 1.5    # s a timer must be seen ticking to count towards a full length


def timer_lengths(reads):
    """{position: full countdown length}, measured from this source's own reads.

    Taken from real timers only: reads grouped by a shared expiry that tick --
    span at least TIMER_MIN_SPAN seconds and show at least two values. Each
    timer's largest value is how full it was when first seen; a timer seen from
    its start shows the full length, so the most common largest value is it.
    A number that merely sits in the slot (Twitch chat read as "12" on Req, for
    long enough to look like the largest common value) never ticks, and so
    never counts. Measured, not tabled, so a patch that moves a cooldown cannot
    silently break the timer model; recorded in the meta line.
    """
    by_pos = {}
    for r in reads:
        for pos, v in ((r[2].cooldowns or {}).items() if len(r) > 2 else ()):
            if isinstance(v, int) and 0 < v <= 30:
                by_pos.setdefault(pos, []).append((r[1], v))
    out = {}
    for pos, seq in by_pos.items():
        timers = []
        for t, v in seq:
            lo, hi = t + v - 1 - TIMER_EPS, t + v + TIMER_EPS
            tm = next((x for x in reversed(timers[-4:]) if lo <= x["hi"] and hi >= x["lo"]), None)
            if tm is None:
                timers.append({"lo": lo, "hi": hi, "t0": t, "t1": t, "vals": {v}})
            else:
                tm["lo"], tm["hi"] = max(tm["lo"], lo), min(tm["hi"], hi)
                if tm["lo"] > tm["hi"]:
                    tm["lo"], tm["hi"] = lo, hi
                tm["t1"] = t
                tm["vals"].add(v)
        tops = [max(x["vals"]) for x in timers
                if x["t1"] - x["t0"] >= TIMER_MIN_SPAN and len(x["vals"]) >= 2]
        if tops:
            out[pos] = max(set(tops), key=lambda v: (tops.count(v), v))
    return out


def _timer_events(reads, pos, ability, full, seg_index):
    """ability_cast / ability_uncertain events for one slot over one segment.

    A newly seen timer (confirmed on TIMER_CONFIRM reads) is classified once:

      one-charge slot (Get Over Here, team-up): only a cast starts a timer, so a
        timer expiring later than the last one is a cast -- if it could have
        started after that one ended, which is what restarting at the kit's
        full value means. One that would have to start earlier is not something
        the kit allows: uncertain. A timer already running when the segment
        began is nobody's cast in this segment.
      charged slot (swing, uppercut): see _classify_charged. Its countdown
        shows only with no charges left, so one becoming visible -- after the
        last expired -- is a use; a return with the same expiry is the reader,
        not a use. First seen part-way through right after an out-of-kit read:
        uncertain. A use while charges remain shows as charges_spent only.

    "Uncertain" is emitted as its own event so that a consumer treats that
    interval as unknown rather than reading the stream's silence as "no cast".
    """
    seg_start = reads[0][1]
    if ability in CHARGED:
        full = RECHARGE_S[ability]        # see RECHARGE_S: not measurable per source
    seq = []
    for r in reads:
        cds = r[2].cooldowns or {}
        ready = ((r[2].abilities or {}).get(pos) or (None, None))[0]
        v = cds.get(pos)
        valid = isinstance(v, int) and v > 0 and (full is None or v <= full)
        # Unobservable: nothing read of the slot at all, or a number the kit
        # cannot produce here (chat over the slot read as a countdown).
        blind = ready is None or (v is not None and not valid)
        seq.append((r[0], r[1], v if valid else None, ready, blind, v is not None and not valid))
    timers, out = [], []
    for k, (i, t, v, *_) in enumerate(seq):
        if v is None:
            continue
        lo, hi = t + v - 1 - TIMER_EPS, t + v + TIMER_EPS
        match = next((tm for tm in reversed(timers) if lo <= tm["hi"] and hi >= tm["lo"]), None)
        if match is not None:
            match["lo"], match["hi"] = max(match["lo"], lo), min(match["hi"], hi)
            if match["lo"] > match["hi"]:          # drifted: trust the newest read
                match["lo"], match["hi"] = lo, hi
            match["n"] += 1
            match["last"] = k
        else:
            match = {"lo": lo, "hi": hi, "k": k, "i": i, "t": t, "v": v, "n": 1, "done": False,
                     "last": k, "kind": None}
            timers.append(match)
        if match["n"] >= TIMER_CONFIRM and not match["done"]:
            match["done"] = True
            kind = _classify_timer(match, timers, seq, ability, full, seg_start)
            match["kind"] = kind
            if kind:
                out.append(_timer_event(kind, match, seq, full, ability, pos, seg_index, seg_start))
    # A certified return: the timer ran out, by its own clock, inside play we
    # watched. Not "the number is gone" -- that is also every unread digit.
    # One-charge slots only; a charged slot's return is charges_regained.
    if ability not in CHARGED:
        for tm in timers:
            if not tm["done"] or tm["kind"] == "ability_uncertain":
                continue
            after = next((sv for sv in seq[tm["last"] + 1:] if sv[1] >= tm["hi"]), None)
            if after is None:
                continue                  # the segment ended first
            last = seq[tm["last"]]
            out.append(Event(kind="cooldown_ended", i_from=last[0], t_from=last[1],
                             i_to=after[0], t_to=after[1], slot=ability, slot_pos=pos,
                             amount=None, before=last[2], after=None, segment=seg_index))
    return out


def _classify_timer(tm, timers, seq, ability, full, seg_start):
    earlier = [o for o in timers if o is not tm and o["done"] and o["t"] < tm["t"]]
    prev = earlier[-1] if earlier else None
    k = tm["k"]
    if ability in CHARGED:
        return _classify_charged(tm, prev, seq, full)
    seen_before = k > 0 and seq[k - 1][2] is None and seq[k - 1][3] is True
    if full is not None and tm["lo"] - full < seg_start - TIMER_EPS and not seen_before:
        return None                       # may have started before this segment began
    if prev is None:
        # With the full length known, the check above already placed its start
        # inside the segment. Without it, the slot must have been seen before
        # the timer -- read, lit, no number -- or the timer may simply have been
        # running when the segment opened.
        if full is not None or any(sv[3] is True and sv[2] is None for sv in seq[:k]):
            return "ability_cast"
        return None
    if tm["lo"] <= prev["hi"]:
        return "ability_uncertain"        # earlier expiry: the kit has no way to do that
    if full is not None and tm["hi"] - full < prev["lo"] - KIT_TOL:
        return "ability_uncertain"        # would have to start before the last one ended
    return "ability_cast"


def _classify_charged(tm, prev, seq, full):
    """A charged slot's newly visible countdown.

    A charged slot draws its big countdown only while it has no charges left
    (checked frame by frame on Day swing 48-52 s: badge 1 and no number; a use,
    badge 0 and "2"; the recharge completes, badge 1 and the number gone; a
    second use, badge 0 and "5"). So a countdown becoming visible means a use
    just emptied the slot -- even when it is the next recharge in a chain,
    which is exactly when a second use lands. A recharge completing shows the
    other way round: the number disappears and charges_regained fires.

    A countdown whose start cannot be placed from the recharge length (an
    uppercut use shows a short between-cast "1"), so only the frozen writer's
    rule applies at a segment start: something without a number first.
    """
    k = tm["k"]
    if prev is None and not any(sv[2] is None for sv in seq[:k]):
        return None                       # already running when the segment began
    # First seen part-way through a recharge right after the slot showed a
    # number it cannot show (chat over it): a use that just emptied the slot and
    # a timer becoming readable cannot be told apart. Req uppercut 52.0: chat
    # read as "7" 2.5 s before a "5". An unreadable frame alone is not this --
    # on the stream HUD most frames of these slots are unreadable.
    recent = [sv for sv in seq[:k] if tm["t"] - BLIND_LOOKBACK <= sv[1]]
    if full is not None and 1 < tm["v"] < full and any(sv[5] for sv in recent):
        return "ability_uncertain"
    return "ability_cast"


def _timer_event(kind, tm, seq, full, ability, pos, seg_index, seg_start):
    """The event, with its interval honest about when the use could have been."""
    k = tm["k"]
    i_to, t_to = seq[k][0], seq[k][1]
    lower = max(seg_start, tm["lo"] - full) if full is not None else None
    before = seq[k - 1] if k > 0 else None
    # The frame before counts as "not yet" only when the slot was read there
    # (lit, no number); otherwise the use could be anywhere the timer allows.
    if before is not None and before[2] is None and before[3] is True and \
            (lower is None or before[1] >= lower):
        i_from, t_from = before[0], before[1]
    elif lower is not None:
        cand = [s for s in seq[:k] if s[1] <= lower] or seq[:1]
        i_from, t_from = cand[-1][0], cand[-1][1]
    else:
        i_from, t_from = (before[0], before[1]) if before else (i_to, t_to)
    return Event(kind=kind, i_from=i_from, t_from=t_from, i_to=i_to, t_to=t_to,
                 slot=ability, slot_pos=pos, amount=tm["v"],
                 before=None, after=tm["v"], segment=seg_index)


def _merge_shield(events):
    """Fold the team-up shield's decay into one event instead of two.

    The buff raises max hp by 50 and then bleeds it back, so hp and max hp fall
    together, two at a time. Left alone that reads as `hp_lost`, which to anything
    learning from these labels means "took damage" -- and nothing in the practice
    range ever damages the player. When both channels confirm the same signed
    change on the same frame, it is the shield, and it is reported as such.
    """
    # The two channels debounce independently, so their confirmations can land a
    # frame or two apart; pair within a short window rather than on equality.
    hps = [e for e in events if e.kind in ("hp_lost", "hp_gained",
                                           "shield_decayed", "shield_gained")]
    maxes = [e for e in events if e.kind == "max_hp_changed"]
    drop, add, taken = set(), [], set()
    for hp in hps:
        hp_delta = (hp.after - hp.before) if hp.after is not None else 0
        mx = next((m for m in maxes
                   if id(m) not in taken and abs(m.i_to - hp.i_to) <= SHIELD_WINDOW
                   and m.amount == hp_delta), None)
        if mx is None:                     # no partner: real damage or a real heal
            continue
        taken.add(id(mx))
        drop.add(id(mx))               # the max change is the same move, reported twice
        if hp.kind in ("hp_lost", "hp_gained"):
            drop.add(id(hp))
        else:
            continue                   # already a shield event; just absorb the max one
        add.append(Event(kind="shield_decayed" if hp_delta < 0 else "shield_gained",
                         i_from=hp.i_from, t_from=hp.t_from, i_to=hp.i_to, t_to=hp.t_to,
                         amount=abs(hp_delta), before=hp.before, after=hp.after,
                         segment=hp.segment))
    out = [e for e in events if id(e) not in drop] + add
    out.sort(key=lambda e: (e.t_to, e.kind))
    return out


def extract(reads, debounce=None, mapping=None):
    """Segment the run, then pull events inside each segment.

    `reads` are (i, t, Hud, playing). Returns (events, segments); channels are
    reset at every boundary, so no event spans one.
    """
    segments = segment(reads)
    timers = timer_lengths(reads)
    by_i = {r[0]: (r[0], r[1], r[2], r[5] if len(r) > 5 else None) for r in reads}
    events = []
    for n, seg in enumerate(segments):
        inside = [by_i[i] for i in range(seg.start_i, seg.end_i + 1) if i in by_i]
        events.extend(extract_one(inside, debounce, seg_index=n, mapping=mapping, timers=timers))
    events.sort(key=lambda e: (e.t_to, e.kind))
    counted = {e.segment for e in events if e.kind == "ability_cast"}
    segments = [replace(s, cooldowns="normal" if n in counted else "unknown")
                for n, s in enumerate(segments)]
    return events, segments


# A cut scores 0.67 and up; the highest thing that is *not* a cut scores 0.45.
# That gap is where this sits. What lives in the 0.40-0.45 band is the in-game
# scoreboard opening and closing -- a real full-frame change, but an overlay
# over continuous footage, and already its own break reason. Calling those cuts
# would label every scoreboard peek an edit.
CUT_SCORE = 0.55


def _pts_times(log):
    """Every `pts_time:` ffmpeg's showinfo filter logged, in order."""
    import re

    return [float(m) for m in re.findall(r"pts_time:\s*(-?[\d.]+)", log)]


def _window(start, duration):
    """ffmpeg input options for a window. -copyts keeps the source's own
    timestamps, so what showinfo reports is source time, not time since the seek."""
    out = []
    if start is not None:
        out += ["-ss", str(start)]
    if duration is not None:
        out += ["-t", str(duration)]
    return out + ["-copyts"]


def scene_cuts(video, threshold=CUT_SCORE, pts_origin=0.0, start=None, duration=None):
    """[seconds] where the source cuts, from ffmpeg's own scene detection.

    Measured at the source's native frame rate, which is the only place a cut is
    obvious: adjacent 60 fps frames barely differ, so a splice stands out. At the
    10 Hz grid these files are sampled on it does not -- a fast camera whip moves
    as much in 0.1 s as a cut does, and the two distributions overlap so far that
    no threshold separates them (measured: median 20.5, cuts 52-80 on a 0-255
    mean absolute difference).

    A fade is not a cut and must not be reported as one: it changes the frame
    gradually, so every step scores low and none crosses the threshold.

    `start`/`duration` restrict it to the same window the frames were taken
    from, with the same seek, so the two timelines agree.
    """
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", *_window(start, duration), "-i", str(video),
         "-vf", f"select=gt(scene\\,{threshold}),showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=True).stderr
    times = [t - pts_origin for t in _pts_times(log)]
    # A wipe or a flash trips several adjacent frames; they are one edit.
    return [t for n, t in enumerate(times) if n == 0 or t - times[n - 1] > 0.5]


def _cut_flags(cuts, rows):
    """Which sampled frames are the first on the far side of a cut."""
    flags, pending = [], list(cuts)
    for row in rows:
        hit = False
        while pending and pending[0] <= float(row["t"]):
            pending.pop(0)
            hit = True
        flags.append(hit)
    return flags


def read_run(run_dir, limit=None, progress=None, layout=None):
    """[(i, t, Hud, playing)] by running the readers over a frame directory.

    `layout` says which HUD this source draws -- perception.hud.PAD for our own
    captures, MK for a mouse-and-keyboard stream. It is the caller's to state:
    guessing it per frame would be silent when wrong, and it is a property of
    the source, not of any one frame.
    """
    import cv2

    from perception.hud import PAD, read as read_hud

    layout = layout or PAD

    index = Path(run_dir) / "frames.jsonl"
    if not index.exists():
        sys.exit(f"{index}: not found (is {run_dir} an L1 run directory?)")
    rows = [json.loads(line) for line in index.read_text().splitlines() if line.strip()]
    if limit:
        rows = rows[:limit]
    # cuts.json is written next to the frames by whoever extracted them, because
    # the cut can only be seen in the video the frames came from.
    cuts_file = Path(run_dir) / "cuts.json"
    # No cuts.json means nobody ran the detection, which is not the same as
    # finding no cuts: the flag is None, and the meta line says null rather
    # than claiming a continuous capture that was never checked.
    flags = (_cut_flags(json.loads(cuts_file.read_text()), rows)
             if cuts_file.exists() else [None] * len(rows))
    out = []
    for n, row in enumerate(rows, 1):
        frame = cv2.imread(str(Path(run_dir) / row["file"]))
        if frame is not None:
            # One slot for "why we are out of the fight": the banner word when
            # one is up, otherwise the scoreboard, which is the other thing that
            # covers the HUD for seconds at a time.
            from perception.scoreboard import is_scoreboard

            from perception.scoreboard import is_killfeed

            aside = ("black" if is_black(frame) else None) or banner_word(frame) \
                or ("scoreboard" if is_scoreboard(frame) is True else None)
            out.append((row["i"], float(row["t"]), read_hud(frame, layout),
                        playing_spiderman(frame), aside, is_killfeed(frame),
                        flags[n - 1]))
        if progress and n % progress == 0:
            print(f"  {n}/{len(rows)} frames", file=sys.stderr)
    return out


def counts(events):
    out = {}
    for e in events:
        key = e.kind if e.slot is None else f"{e.kind}:{e.slot}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _mapping_for(run_dir, layout, n_frames, sample=60):
    """Work out which ability is in each slot for this source, once."""
    import cv2

    from perception.hud import slot_mapping

    index = Path(run_dir) / "frames.jsonl"
    rows = [json.loads(line) for line in index.read_text().splitlines() if line.strip()]
    step = max(1, len(rows) // sample)
    frames = []
    for row in rows[::step]:
        frame = cv2.imread(str(Path(run_dir) / row["file"]))
        if frame is not None:
            frames.append(frame)
    return slot_mapping(frames, layout)


def sampling_fps(reads):
    """Frames per second the run was sampled at, from the times themselves."""
    times = sorted(r[1] for r in reads)
    gaps = sorted(b - a for a, b in zip(times, times[1:]) if b > a)
    if not gaps:
        return None
    return round(1.0 / gaps[len(gaps) // 2], 3)


def observed(events):
    """What this source's own footage says each ability's timings are.

    A balance patch changes cooldowns, so the cooldowns visible in a recording
    date it: footage whose only date is an upload can be placed against the
    patch history in docs/spiderman-kit.md. Every number here is measured off
    the HUD in this one source. **No kit value appears in this file** -- the
    patch is stated in one place, that doc, and a copy here would drift from it.

    Per slot:
      casts           how many cooldown-proved casts it rests on
      countdown_mode  **the fingerprint.** The most common countdown number seen
                      the instant after a cast: the ability's cooldown as the
                      game itself printed it. Lower numbers in `countdown` are
                      reads that caught the timer after it had already ticked,
                      so the mode is the full value and the tail sits below it.
      countdown       every number seen, and how often -- so the mode can be
                      judged rather than trusted
      relock_s        median seconds from a cast to its cooldown running out
      recast_s        p10 and median gap between consecutive casts, as support
      charges         the highest charge count the badge ever showed. **This
                      reads one below the true maximum**, because the badge is
                      not drawn while the ability is at full charge: measured
                      as 1 against a kit 2 for Amazing Combo and 2 against a kit
                      3 for Web-Swing, on all six sources. Compare it to
                      kit - 1, or use it only to tell two patches apart.

    **The gap between casts is not the cooldown and must not be used as one.**
    A player presses when the fight allows, not the instant the timer clears, so
    the distribution has no floor at the true value; and its minimum is worse
    still, being whatever artifact is shortest -- measured here at 0.4-0.6 s for
    Get Over Here, which has an 8 s cooldown. The countdown the HUD prints is
    the game's own statement and needs no such inference.
    """
    by_slot = {}
    for e in events:
        by_slot.setdefault(e.slot, []).append(e)
    out = {}
    # An unidentified slot is dropped: its casts are real but nobody knows which
    # ability they belong to, so they cannot time one.
    for slot in sorted(s for s in by_slot if s is not None):
        evs = by_slot[slot]
        casts = [e for e in evs if e.kind == "ability_cast"]
        available = [e for e in evs if e.kind == "cooldown_ended"]
        row = {"casts": len(casts)}
        numbers = [int(e.amount) for e in casts if e.amount is not None]
        if numbers:
            row["countdown_mode"] = max(set(numbers), key=numbers.count)
            row["countdown"] = {str(v): numbers.count(v) for v in sorted(set(numbers))}
        # Cast -> usable again, inside one segment: across a break the slot may
        # have come back during footage nobody saw. Each availability is paired
        # with the *nearest preceding* cast -- pairing every cast with its next
        # availability instead credits one recharge to a whole combo, and turns
        # a 2 s relock into the length of the combo that preceded it.
        relock = []
        for a in available:
            prior = [c for c in casts if c.t_to <= a.t_to and c.segment == a.segment]
            if prior:
                relock.append(a.t_to - prior[-1].t_to)
        if relock:
            row["relock_s"] = round(sorted(relock)[len(relock) // 2], 2)
            row["relock_n"] = len(relock)
        gaps = sorted(round(b.t_to - a.t_to, 2) for a, b in zip(casts, casts[1:])
                      if b.segment == a.segment)
        if gaps:
            row["recast_s"] = {"p10": gaps[int(len(gaps) * 0.1)],
                               "median": gaps[len(gaps) // 2], "n": len(gaps)}
        charges = [v for e in evs if e.kind.startswith("charges_")
                   for v in (e.before, e.after) if isinstance(v, int)]
        if charges:
            row["charges"] = max(charges)
        out[slot] = row
    return out


def dump(events, segments, reads, layout="pad", source=None, mapping=None,
         pts_origin=None, recipe=None, starts=None):
    """The per-clip JSONL: one meta line, then a segment line each, then events.

    Three line kinds, told apart by `type`, which events omit for the sake of
    the readers already consuming them:

      {"type": "meta", ...}     once, first: sampling fps, layout, frame count
      {"type": "segment", ...}  one per segment, in time order
      {...}                     one per event, in time order, no `type` key

    `t` values everywhere are seconds from the first frame of the media, and
    `i` values are that media's frame index at the sampling fps in the meta
    line -- not the source video's native frame numbers.
    """
    lines = [json.dumps({
        "type": "meta",
        "format": FORMAT_VERSION,
        "source": str(source) if source else None,
        "layout": layout,
        "frames": len(reads),
        "fps": sampling_fps(reads),
        "t_origin": "first frame of the media",
        # Three clocks, kept apart. `t` counts from the first decoded video
        # frame; `pts_origin_s` is that frame's PTS on the video stream's own
        # clock (decoded with -copyts, so not rebased). A container can start
        # before its video stream -- one retained section has audio from 1.589 s
        # and video from 1.616 s -- and players and ffmpeg's -ss count from the
        # container's start. So:
        #   stream PTS          = t + pts_origin_s
        #   player / -ss time   = t + pts_origin_s - container_start_s
        "pts_origin_s": pts_origin,
        "container_start_s": (starts or {}).get("container"),
        "stream_start_s": (starts or {}).get("stream"),
        "writer": writer_version(),
        "duration_s": round(max(r[1] for r in reads) - min(r[1] for r in reads), 3) if reads else 0.0,
        # How many editorial cuts were found in this source, and 0 for a
        # continuous capture. A null says nobody looked, which is not the same.
        "cuts": (sum(1 for r in reads if len(r) > 6 and r[6]) if reads
                 and any(len(r) > 6 and r[6] is not None for r in reads) else None),
        # Each cut's time: the first decoded frame on its far side, in the same
        # `t` as everything else. With these a loader can check any gap for a
        # cut before bridging it, not only the gaps whose reason says so.
        "cut_times": ([round(r[1], 3) for r in reads if len(r) > 6 and r[6]]
                      if any(len(r) > 6 and r[6] is not None for r in reads) else None),
        # Cooldowns as this source's own HUD showed them: a patch fingerprint
        # for footage dated only by an upload. See `observed`.
        "observed": observed(events),
        "segments": len(segments),
        "events": len(events),
        # Which ability sits in each layout position, and how that was decided.
        # Positions missing from this map could not be identified; their events
        # carry slot: null rather than a guessed ability. **null, not {}, when
        # no mapping was attempted at all** -- a file nobody identified must not
        # read as one whose icons were checked and found absent.
        "slot_mapping": mapping if mapping is not None else None,
        "slot_mapping_from": (
            "ability icon matched by shape, voted over sampled frames"
            if mapping is not None else None),
        # How this file was made, complete enough for `regenerate` to make it
        # again: source video, sampling rate, window, layout. null for a file
        # built from a frame directory, which only its recorder can rebuild.
        "recipe": recipe,
        # The full countdown length the timer model used per layout position:
        # measured from this source's ticking timers for one-charge slots,
        # the kit's recharge for charged ones (see timer_lengths, RECHARGE_S).
        "timer_lengths": {p: (RECHARGE_S[mapping[p]] if mapping and mapping.get(p) in CHARGED else v)
                          for p, v in timer_lengths(reads).items()},
    })]
    lines += [json.dumps({"type": "segment", **asdict(s)}) for s in segments]
    lines += [json.dumps(asdict(e)) for e in events]
    return "\n".join(lines) + "\n"


EVENTS_DIR = Path("data/demos/events")


def _probe_fps(video):
    rate = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True).stdout.strip().rstrip(",")
    num, _, den = rate.partition("/")
    return float(num) / float(den or 1)


def probe_starts(video):
    """{"container": format start_time, "stream": video stream start_time}, seconds."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "format=start_time:stream=start_time", "-of", "json", str(video)],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    as_float = lambda v: None if v in (None, "N/A") else round(float(v), 3)  # noqa: E731
    return {"container": as_float(info.get("format", {}).get("start_time")),
            "stream": as_float((info.get("streams") or [{}])[0].get("start_time"))}


def extract_frames(video, run_dir, hz=10.0, start=None, duration=None):
    """Sample `video` onto an exact grid into `run_dir`; returns the PTS origin.

    Every Nth *decoded* frame, never `-vf fps=N`, which resamples and lands a
    source frame off. `t` in frames.jsonl is each frame's own decoded PTS minus
    the first one's, so a source whose rate is not exactly 60 does not drift
    against a grid assumed from the frame index. The origin is returned in
    source seconds: the first decoded frame of the window.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    step = max(1, round(_probe_fps(video) / hz))
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", *_window(start, duration), "-i", str(video),
         "-vf", f"select=not(mod(n\\,{step})),showinfo", "-vsync", "0", "-q:v", "6",
         "-an", str(run_dir / "%06d.jpg"), "-y"],
        capture_output=True, text=True, check=True).stderr
    times = _pts_times(log)
    files = sorted(p.name for p in run_dir.glob("*.jpg"))
    if len(times) != len(files):
        raise RuntimeError(f"{video}: {len(files)} frames written, {len(times)} timestamps logged")
    origin = times[0] if times else 0.0
    with open(run_dir / "frames.jsonl", "w") as fh:
        for i, (name, pts) in enumerate(zip(files, times)):
            fh.write(json.dumps({"i": i, "t": round(pts - origin, 3), "file": name}) + "\n")
    return round(origin, 3)


def from_video(video, out, hz=10.0, start=None, duration=None, layout="mk",
               workdir=None, progress=None):
    """A video (or a window of one) to an events file, recording its recipe.

    This is the one path demonstration files are made by. Everything needed to
    make the file again goes into its meta line, so `regenerate` can rebuild it
    after a format change without anybody remembering how it was cut. Cuts are
    always detected: a continuous capture then records a verified 0 rather than
    a null nobody checked.
    """
    import shutil
    import tempfile

    from perception.hud import LAYOUTS

    video, out = Path(video), Path(out)
    # Frames from a VOD stay under data/, which is gitignored; never /tmp on a
    # shared machine, and never anywhere that could be committed.
    base = Path(workdir) if workdir else Path("data/.work")
    base.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=out.stem + "-", dir=base))
    try:
        origin = extract_frames(video, run_dir, hz, start, duration)
        cuts = scene_cuts(video, pts_origin=origin, start=start, duration=duration)
        (run_dir / "cuts.json").write_text(json.dumps(cuts))
        lay = LAYOUTS[layout]
        reads = read_run(run_dir, progress=progress, layout=lay)
        mapping = _mapping_for(run_dir, lay, len(reads))
        events, segments = extract(reads, mapping=mapping)
        recipe = {"video": str(video), "hz": hz, "start": start,
                  "duration": duration, "layout": layout}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(dump(events, segments, reads, layout=layout, source=out.stem,
                            mapping=mapping, pts_origin=origin, recipe=recipe,
                            starts=probe_starts(video)))
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
    return {"out": str(out), "frames": len(reads), "events": len(events),
            "segments": len(segments), "cuts": len(cuts), "pts_origin_s": origin}


def check(root=EVENTS_DIR):
    """[(path, why)] for every events file under `root` a loader should not see.

    Stale means written at another format, or carrying no recipe, which means
    nobody can rebuild it the next time the format moves. An empty list is the
    only state in which the directory holds one format throughout.
    """
    stale, current = [], writer_version()
    for path in sorted(Path(root).rglob("*.jsonl")):
        try:
            meta = json.loads(path.open().readline())
        except (OSError, ValueError):
            stale.append((path, "unreadable meta line"))
            continue
        missing = [k for k in REQUIRED_META if k not in meta]
        if meta.get("format") != FORMAT_VERSION:
            stale.append((path, f"format {meta.get('format')}, current is {FORMAT_VERSION}"))
        elif not meta.get("recipe"):
            stale.append((path, "no recipe, so it cannot be regenerated"))
        elif missing:
            stale.append((path, f"written by older code: lacks {', '.join(missing)}"))
        elif meta["writer"] != current:
            stale.append((path, f"writer {meta['writer']}, current is {current}"))
    return stale


def regenerate(root=EVENTS_DIR, everything=False, progress=None):
    """Rebuild every stale file under `root` from its own recipe.

    A file with no recipe cannot be rebuilt here and is reported, not skipped
    silently. `everything` rebuilds current files too, for after a reader fix.
    """
    targets = [p for p in sorted(Path(root).rglob("*.jsonl"))] if everything \
        else [p for p, _ in check(root)]
    done, orphans = [], []
    for path in targets:
        recipe = json.loads(path.open().readline()).get("recipe")
        if not recipe:
            orphans.append(str(path))
            continue
        print(f"  regenerating {path}", file=sys.stderr)
        done.append(from_video(recipe["video"], path, recipe["hz"], recipe.get("start"),
                               recipe.get("duration"), recipe["layout"], progress=progress))
    return {"regenerated": done, "no_recipe": orphans}


def segment_summary(segments):
    return [{"n": n, "frames": s.frames, "start_i": s.start_i, "end_i": s.end_i,
             "start_t": round(s.start_t, 2), "end_t": round(s.end_t, 2),
             "started_by": s.started_by, "ended_by": s.ended_by}
            for n, s in enumerate(segments)]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["video"]:
        p = argparse.ArgumentParser(prog="perception.events video")
        p.add_argument("video")
        p.add_argument("out")
        p.add_argument("--hz", type=float, default=10.0)
        p.add_argument("--start", type=float, help="window start, source seconds")
        p.add_argument("--duration", type=float, help="window length, seconds")
        p.add_argument("--layout", default="mk", choices=("pad", "mk"),
                       help="which HUD the source draws; never guessed from the frames")
        p.add_argument("--progress", type=int, default=2000)
        a = p.parse_args(argv[1:])
        print(json.dumps(from_video(a.video, a.out, a.hz, a.start, a.duration, a.layout,
                                    progress=a.progress), indent=1))
        return 0
    if argv[:1] == ["check"]:
        stale = check(argv[1] if len(argv) > 1 else EVENTS_DIR)
        for path, why in stale:
            print(f"{path}: {why}")
        print(f"{len(stale)} stale" if stale else f"all format {FORMAT_VERSION}, all regenerable")
        return 1 if stale else 0
    if argv[:1] == ["regenerate"]:
        p = argparse.ArgumentParser(prog="perception.events regenerate")
        p.add_argument("root", nargs="?", default=str(EVENTS_DIR))
        p.add_argument("--all", action="store_true", help="rebuild current files too")
        p.add_argument("--progress", type=int, default=2000)
        a = p.parse_args(argv[1:])
        result = regenerate(a.root, a.all, a.progress)
        print(json.dumps(result, indent=1))
        return 1 if result["no_recipe"] or check(a.root) else 0
    if argv[:1] == ["frames"]:
        argv = argv[1:]
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("out")
    p.add_argument("--limit", type=int)
    p.add_argument("--progress", type=int, default=1000)
    p.add_argument("--pts-origin", type=float, default=None,
                   help="seconds of the source's first decoded video PTS")
    p.add_argument("--layout", default="pad", choices=("pad", "mk"),
                   help="which HUD the source draws; never guessed from the frames")
    p.add_argument("--cuts-from", metavar="VIDEO",
                   help="detect this source's editorial cuts and write cuts.json "
                        "into run_dir before reading; for edited uploads")
    a = p.parse_args(argv)
    from perception.hud import LAYOUTS
    layout = LAYOUTS[a.layout]
    if a.cuts_from:
        cuts = scene_cuts(a.cuts_from, pts_origin=a.pts_origin or 0.0)
        (Path(a.run_dir) / "cuts.json").write_text(json.dumps(cuts))
        print(f"  {len(cuts)} cuts at score >= {CUT_SCORE}", file=sys.stderr)
    reads = read_run(a.run_dir, a.limit, a.progress or None, layout)
    mapping = _mapping_for(a.run_dir, layout, len(reads))
    events, segments = extract(reads, mapping=mapping)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # The clip stem, not the frame directory: that is a scratch path on whoever
    # ran this, and the stem is what a manifest joins on.
    out.write_text(dump(events, segments, reads, layout=a.layout, source=out.stem,
                        mapping=mapping, pts_origin=a.pts_origin))
    summary = segment_summary(segments)
    print(json.dumps({"run": str(a.run_dir), "layout": a.layout,
                      "pts_origin_s": a.pts_origin,
                      "frames": len(reads), "events": len(events),
                      "out": a.out, "fps": sampling_fps(reads),
                      "counts": counts(events),
                      "segments": len(segments),
                      "segment_detail": summary if len(summary) <= 12 else summary[:12]},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
