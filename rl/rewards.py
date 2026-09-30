"""Reward readers for the practice range, from pixels only (VUH-1321).

Every reader takes one BGR frame (any 16:9 size; geometry is in 1440p pixels scaled by
frame height) and returns a value or None when it cannot tell. None is never zero.

    hit_marker(frame)    -> bool | None   the four white diagonal strokes round the crosshair
    killfeed_rows(frame) -> int | None    kill-feed lines in the top-right slot; in the range every line is ours
    own_hp(frame)        -> (hp, max) | (None, None)     perception.hud.read_hp
    RewardTracker        turns a frame stream into per-step events: hits, KOs, own damage taken, death

Findings, precision/recall and what is not on screen are in docs/lanes/rl.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# --- hit marker -----------------------------------------------------------------------------------
# Measured on James's 2026-09-23 range take (051828) at 2560x1440: the crosshair dot sits at the exact
# screen centre, and a hit draws four elongated white diamonds on the diagonals. They animate from
# about r 8-30 px to r 20-65 px and fade, so the reader looks for a bright ridge along each diagonal
# anywhere in r 8-68 and needs it on at least three of the four.
HIT_R = (8, 68)         # radii searched along each diagonal, 1440p px
HIT_OFF = 10            # perpendicular offset of the two side samples, 1440p px
HIT_RIDGE = 35          # grey levels brighter than the brighter side sample
HIT_FLOOR = 150         # min-channel floor: the strokes are white or near-white
HIT_RUN = 10            # consecutive ridge samples that make a stroke, 1440p px. 6 fired on water foam in a live
                        # fall (rl-sitting-20260930-01 ep 5, arms 6/2/7/7); 10 keeps P 1.00, R 0.969 on the 900 labels
HIT_ARMS = 3            # strokes needed out of four
DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _scale(frame):
    return frame.shape[0] / 1440.0


def hit_arms(frame, centre=None, scale=None):
    """Longest bright-ridge run (1440p px) along each of the four diagonals from the crosshair.

    `centre` and `scale` let a caller pass a crop round the crosshair instead of the whole frame.
    """
    h, w = frame.shape[:2]
    s = scale or _scale(frame)
    cx, cy = centre or (w / 2.0, h / 2.0)
    # Only the square the arms can reach; the min over a whole native frame cost 45 ms.
    reach = int(np.ceil((HIT_R[1] + HIT_OFF + 2) * s))
    x0, y0 = max(0, int(cx) - reach), max(0, int(cy) - reach)
    white = frame[y0:int(cy) + reach + 1, x0:int(cx) + reach + 1].min(axis=2).astype(np.int16)
    h, w = white.shape
    cx, cy = cx - x0, cy - y0
    runs = []
    for dx, dy in DIAGONALS:
        ux, uy = dx / np.sqrt(2), dy / np.sqrt(2)      # along the arm
        px, py = -uy, ux                                # perpendicular
        r = np.arange(HIT_R[0], HIT_R[1] + 1) * s
        xs, ys = cx + ux * r, cy + uy * r
        o = HIT_OFF * s

        def at(x, y):
            xi = np.clip(np.rint(x).astype(int), 0, w - 1)
            yi = np.clip(np.rint(y).astype(int), 0, h - 1)
            return white[yi, xi]

        on = at(xs, ys)
        side = np.maximum(at(xs + px * o, ys + py * o), at(xs - px * o, ys - py * o))
        ridge = (on >= HIT_FLOOR) & (on - side >= HIT_RIDGE)
        best = cur = 0
        for v in ridge:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        runs.append(best / s)
    return runs


def hit_marker(frame, centre=None, scale=None) -> bool | None:
    runs = hit_arms(frame, centre, scale)
    arms = sum(r >= HIT_RUN for r in runs)
    if arms >= HIT_ARMS:
        return True
    if arms <= 1:
        return False
    return None


# --- KO marker ------------------------------------------------------------------------------------
# A KO draws a red diamond at the crosshair inside a thin red ring, for about half a second, then fades.
# The ring is the specific part: measured on three sessions it sits at r = 54 px (1440p) with red on
# 94-100% of its circumference and almost none 6 px either side. Spider-Man's red arm crossing the
# crosshair is red at every radius, so the reader tests the ring against its two sides, not redness.
KO_R = (52, 56)          # ring radii searched, 1440p px
KO_SIDES = (46, 62)      # inside and outside comparison radii
KO_ON, KO_OFF = 0.45, 0.2  # ring red share minus the redder side


def _red(px):
    b, g, r = px[..., 0].astype(np.int16), px[..., 1].astype(np.int16), px[..., 2].astype(np.int16)
    return (r > 150) & (r - g > 80) & (r - b > 60)


def _ring_red(frame, cx, cy, radius):
    h, w = frame.shape[:2]
    a = np.linspace(0, 2 * np.pi, 180, endpoint=False)
    xi = np.clip(np.rint(cx + radius * np.cos(a)).astype(int), 0, w - 1)
    yi = np.clip(np.rint(cy + radius * np.sin(a)).astype(int), 0, h - 1)
    return float(_red(frame[yi, xi]).mean())


def ko_ring(frame, centre=None, scale=None) -> float:
    """Ring red share minus the redder of the two side circles; about 0.6-1.0 on a KO marker."""
    h, w = frame.shape[:2]
    s = scale or _scale(frame)
    cx, cy = centre or (w / 2.0, h / 2.0)
    ring = max(_ring_red(frame, cx, cy, r * s) for r in range(KO_R[0], KO_R[1] + 1))
    side = max(_ring_red(frame, cx, cy, r * s) for r in KO_SIDES)
    return ring - side


def ko_marker(frame, centre=None, scale=None) -> bool | None:
    score = ko_ring(frame, centre, scale)
    if score >= KO_ON:
        return True
    if score < KO_OFF:
        return False
    return None


# --- own hp and death -----------------------------------------------------------------------------
def own_hp(frame):
    """(hp, max_hp) from the HUD digits; either may be None. perception.hud.read_hp, unchanged."""
    from perception.hud import read_hp
    return read_hp(frame)


# --- events ---------------------------------------------------------------------------------------
@dataclass
class Step:
    """What happened since the previous frame. Unknowns stay None; they are never zero."""
    t: float
    hit: bool = False            # a hit marker appeared (rising edge)
    ko: bool = False             # a KO ring appeared (rising edge, refractory KO_GAP)
    hp: int | None = None
    hp_lost: int | None = None   # confirmed drop in own hp since the last confirmed read
    death: bool = False          # own hp confirmed at 0
    reward: float = 0.0


@dataclass
class Weights:
    """Starting reward shape (docs/lanes/rl.md). Tune against the scoreboard, not by feel."""
    hit: float = 1.0
    ko: float = 10.0
    hp_lost: float = -0.02       # per hp point: 250 hp lost is -5
    death: float = -10.0


KO_GAP = 1.0      # s: one KO ring lasts ~0.5 s; two KOs closer than this count once
HP_CONFIRM = 2    # consecutive equal hp reads before a change counts; a single misread never pays


@dataclass
class RewardTracker:
    weights: Weights = field(default_factory=Weights)
    _hit: bool = False
    _ko_t: float = -1e9
    _ko: bool = False
    _pair: tuple | None = None    # last confirmed (hp, max_hp)
    _cand: tuple | None = None
    _cand_n: int = 0
    _zero_n: int = 0
    _dead: bool = False
    _respawn_n: int = 0
    _death_max: int | None = None

    def update(self, t, hit, ko, hp, max_hp=None, own=None) -> Step:
        """Feed one frame's reads (hit_marker, ko_marker, own_hp(), perception.events.playing_spiderman).

        None means unread. `own` False (another hero's HUD: spectating a teammate after death) drops the frame.
        After a confirmed death every read is dropped until the respawn: own not False and hp confirmed full,
        because the death screen shows the killer's cam, a teammate's HUD, and a scoreboard whose Spider-Man row
        fools the portrait check (match 052001 at 215 s).

        Damage taken is a rise in the deficit (max_hp - hp), counted only between confirmed reads of both numbers:
        Spider-Man's bonus health decays 300 -> 250 with max and current falling together, and that is not damage.
        Death is hp confirmed at 0 on its own, since max_hp may be unread on the death frame.
        """
        s = Step(t=t)
        if own is False:
            hit = ko = hp = max_hp = None
        if self._dead:
            # Full hp at the max we died with; a teammate at full hp with another max never counts. A teammate with
            # the same max still can, which is why a match run also passes `own` (the portrait read).
            if own is not False and hp is not None and hp == max_hp == self._death_max and hp > 0:
                self._respawn_n = self._respawn_n + 1
            else:
                self._respawn_n = 0
            if self._respawn_n < HP_CONFIRM:
                s.hp = None
                return s
            self._dead, self._pair, self._cand, self._cand_n, self._zero_n = False, (hp, max_hp), (hp, max_hp), 2, 0
        if hit is not None:
            s.hit = bool(hit) and not self._hit
            self._hit = bool(hit)
        if ko is not None:
            if ko and not self._ko and t - self._ko_t >= KO_GAP:
                s.ko = True
                self._ko_t = t
            self._ko = bool(ko)
        if hp is not None and max_hp is not None:
            pair = (hp, max_hp)
            self._cand_n = self._cand_n + 1 if pair == self._cand else 1
            self._cand = pair
            if self._cand_n >= HP_CONFIRM and pair != self._pair:
                if self._pair is not None:
                    lost = (max_hp - hp) - (self._pair[1] - self._pair[0])
                    if lost > 0:
                        s.hp_lost = lost
                self._pair = pair
        if hp is not None:
            self._zero_n = self._zero_n + 1 if hp == 0 else 0
            if self._zero_n >= HP_CONFIRM:
                s.death = self._dead = True
                self._respawn_n = 0
                self._death_max = self._pair[1] if self._pair else max_hp
        s.hp = self._pair[0] if self._pair else None
        w = self.weights
        s.reward = (w.hit * s.hit + w.ko * s.ko + w.hp_lost * (s.hp_lost or 0) + w.death * s.death)
        return s
