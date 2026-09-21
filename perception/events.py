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
import sys
import zlib
from dataclasses import asdict, dataclass, field
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
FORMAT_VERSION = 2
ULT = "ult"

# --- is Spider-Man the hero being played? ---------------------------------
PORTRAIT = (0.015, 0.84, 0.100, 0.96)   # bottom-left hero portrait, frame fractions
PORTRAIT_SCALES = (0.8, 0.95, 1.1, 1.3, 1.5)
# Measured: Spider-Man 0.347-0.516 across the range captures, a 1080p stream and a
# second streamer on a different skin; other heroes 0.225-0.304, including the
# spectating still. The band between is reported as unknown rather than guessed.
PORTRAIT_MATCH, PORTRAIT_CLEAR = 0.34, 0.31
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


_PORTRAIT_CACHE: list = []


def _portraits():
    if not _PORTRAIT_CACHE:
        raw = zlib.decompress(base64.b64decode("".join(_PORTRAITS_B64)))
        _PORTRAIT_CACHE.extend(np.frombuffer(raw, np.uint8).reshape(-1, 40, 30, 3).astype(np.float32))
    return _PORTRAIT_CACHE


def portrait_score(frame) -> float:
    """Best colour match for the Spider-Man portrait in the hero slot."""
    import cv2

    height, width = frame.shape[:2]
    x0, y0, x1, y1 = PORTRAIT
    region = frame[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)]
    region = region.astype(np.float32)
    best = 0.0
    for tpl in _portraits():
        for scale in PORTRAIT_SCALES:
            t = cv2.resize(tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
                continue
            best = max(best, float(cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


def playing_spiderman(frame) -> bool | None:
    """True, False, or None when the portrait slot is too ambiguous to call."""
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
    started_by: str   # run_start | respawn | hero_returned | hud_returned
    ended_by: str     # run_end | death | killcam | spectating | scoreboard
                      #   | not_our_hero | no_hud

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
    """
    # Reads are (i, t, hud, playing) and may carry a fifth item: the word in the
    # top-left status banner, when one is up.
    # "" rather than None for "no banner": absence here is a real reading, not an
    # unknown, and _steady carries unknowns forward from the last belief.
    banners = _steady([(r[4] if len(r) > 4 else None) or "" for r in reads], BANNER_HOLD)
    playing_steady = _steady([r[3] for r in reads], PORTRAIT_HOLD)
    # The HUD gets the same treatment. A handful of frames where neither the hp
    # digits nor the bar could be read is the readers struggling, not a menu:
    # untreated it cuts one 60 s clip into nine pieces.
    hud_steady = _steady([_hud_present(r[2]) for r in reads], HUD_HOLD)
    segments, start, last, reason = [], None, None, "run_start"
    for n, read in enumerate(reads):
        i, t, hud = read[0], read[1], read[2]
        playing = playing_steady[n]
        dead = hud.hp == 0
        # Death first: it is the earlier and more specific fact, and the killcam
        # that follows is then simply outside any segment. The banner comes next
        # because killcam looks exactly like spectating to every other signal --
        # a foreign hero with a perfectly readable HUD -- and the two are
        # different things to anything learning from these labels.
        broken = (dead and "death") or banners[n] \
            or (playing is False and "not_our_hero") \
            or (not hud_steady[n] and "no_hud")
        if broken:
            if start is not None:
                segments.append(Segment(start[0], start[1], last[0], last[1], reason, broken))
                start = None
            reason = {"death": "respawn", "not_our_hero": "hero_returned",
                      "killcam": "killcam_over", "spectating": "spectating_over",
                      "scoreboard": "scoreboard_closed"}.get(broken, "hud_returned")
            continue
        if start is None:
            start = (i, t)
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
    slot: str | None = None
    amount: float | None = None
    before: object = None
    after: object = None
    segment: int = 0  # index into the segment list this event belongs to
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
        # "off" rather than None, so a countdown ending is a transition and not
        # an unknown. None here would mean "could not read the slot at all".
        cd = (hud.cooldowns or {}).get(slot, None)
        out[f"cooldown:{slot}"] = "off" if cd is None else cd
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
        # An icon going dim or red only says the slot cannot be used right now.
        # It happens while climbing a wall, mid-swing, and through any other
        # lockout, and it is *not* a cast: on this clip every one of these lasted
        # 0.1-1.4 s with the charge count unchanged.
        return ("slot_available" if after else "slot_unavailable"), slot, None
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
        return ("hp_gained" if delta > 0 else "hp_lost"), None, abs(delta)
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


def extract_one(reads, debounce=None, seg_index=0):
    """[Event] for a single segment of (i, t, Hud) reads, in time order."""
    holds = {**DEBOUNCE, **(debounce or {})}

    def hold_for(name):
        return holds.get(name.split(":", 1)[0], 2)

    channels, events, max_seen = {}, [], {}
    # A countdown that blinks "off" for one frame and comes back is the reader
    # losing it, not the ability being cast twice. Hand-checking 30 events found
    # three phantom casts from exactly this, all of them mid-countdown.
    slots = sorted({s for r in reads for s in (r[2].cooldowns or {})})
    cd_clean = {}
    for slot in slots:
        seq = [(r[2].cooldowns or {}).get(slot) for r in reads]
        seq = ["off" if v is None else v for v in seq]
        fixed = list(seq)
        for k in range(1, len(seq) - 1):
            if seq[k] == "off" and seq[k - 1] != "off" and seq[k + 1] != "off":
                fixed[k] = None          # unknown: no transition either way
        cd_clean[slot] = fixed
    hp_clean = _despike([r[2].hp for r in reads],
                        [(r[2].bar_damage or 0) > DAMAGE_STRIPE for r in reads],
                        [r[2].max_hp for r in reads])
    for n, read in enumerate(reads):
        i, t, hud = read[0], read[1], read[2]
        if hud.max_hp is not None:
            max_seen[i] = hud.max_hp
        signals = _signals(hud)
        signals["hp"] = hp_clean[n]
        for slot, value in cd_clean.items():
            signals[f"cooldown:{slot}"] = value[n]
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
            kind, slot, amount = described
            events.append(Event(kind=kind, i_from=from_i, t_from=from_t, i_to=i, t_to=t,
                                slot=slot, amount=amount, before=before, after=after,
                                segment=seg_index))
    events.sort(key=lambda e: (e.t_to, e.kind))
    return _merge_shield(events)


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


def extract(reads, debounce=None):
    """Segment the run, then pull events inside each segment.

    `reads` are (i, t, Hud, playing). Returns (events, segments); channels are
    reset at every boundary, so no event spans one.
    """
    segments = segment(reads)
    by_i = {r[0]: (r[0], r[1], r[2], r[5] if len(r) > 5 else None) for r in reads}
    events = []
    for n, seg in enumerate(segments):
        inside = [by_i[i] for i in range(seg.start_i, seg.end_i + 1) if i in by_i]
        events.extend(extract_one(inside, debounce, seg_index=n))
    events.sort(key=lambda e: (e.t_to, e.kind))
    return events, segments


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
    out = []
    for n, row in enumerate(rows, 1):
        frame = cv2.imread(str(Path(run_dir) / row["file"]))
        if frame is not None:
            # One slot for "why we are out of the fight": the banner word when
            # one is up, otherwise the scoreboard, which is the other thing that
            # covers the HUD for seconds at a time.
            from perception.scoreboard import is_scoreboard

            from perception.scoreboard import is_killfeed

            aside = banner_word(frame) or ("scoreboard" if is_scoreboard(frame) is True
                                           else None)
            out.append((row["i"], float(row["t"]), read_hud(frame, layout),
                        playing_spiderman(frame), aside, is_killfeed(frame)))
        if progress and n % progress == 0:
            print(f"  {n}/{len(rows)} frames", file=sys.stderr)
    return out


def counts(events):
    out = {}
    for e in events:
        key = e.kind if e.slot is None else f"{e.kind}:{e.slot}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def sampling_fps(reads):
    """Frames per second the run was sampled at, from the times themselves."""
    times = sorted(r[1] for r in reads)
    gaps = sorted(b - a for a, b in zip(times, times[1:]) if b > a)
    if not gaps:
        return None
    return round(1.0 / gaps[len(gaps) // 2], 3)


def dump(events, segments, reads, layout="pad", source=None):
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
        "duration_s": round(max(r[1] for r in reads) - min(r[1] for r in reads), 3) if reads else 0.0,
        "segments": len(segments),
        "events": len(events),
    })]
    lines += [json.dumps({"type": "segment", **asdict(s)}) for s in segments]
    lines += [json.dumps(asdict(e)) for e in events]
    return "\n".join(lines) + "\n"


def segment_summary(segments):
    return [{"n": n, "frames": s.frames, "start_i": s.start_i, "end_i": s.end_i,
             "start_t": round(s.start_t, 2), "end_t": round(s.end_t, 2),
             "started_by": s.started_by, "ended_by": s.ended_by}
            for n, s in enumerate(segments)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("out")
    p.add_argument("--limit", type=int)
    p.add_argument("--progress", type=int, default=1000)
    p.add_argument("--layout", default="pad", choices=("pad", "mk"),
                   help="which HUD the source draws; never guessed from the frames")
    a = p.parse_args(argv)
    from perception.hud import LAYOUTS
    reads = read_run(a.run_dir, a.limit, a.progress or None, LAYOUTS[a.layout])
    events, segments = extract(reads)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # The clip stem, not the frame directory: that is a scratch path on whoever
    # ran this, and the stem is what a manifest joins on.
    out.write_text(dump(events, segments, reads, layout=a.layout, source=out.stem))
    summary = segment_summary(segments)
    print(json.dumps({"run": str(a.run_dir), "layout": a.layout,
                      "frames": len(reads), "events": len(events),
                      "out": a.out, "fps": sampling_fps(reads),
                      "counts": counts(events),
                      "segments": len(segments),
                      "segment_detail": summary if len(summary) <= 12 else summary[:12]},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
