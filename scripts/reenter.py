"""Take the game from the PLAY lobby into the Practice Range as Spider-Man, and stop at the first thing it cannot verify.

Usage (PC desktop session, game focused, PLAY lobby on screen):
  python scripts/reenter.py                    # do it
  python scripts/reenter.py --dry-run          # classify one live frame, print what it would do, open no pad
  python scripts/reenter.py --dry-run --frame shot.jpg   # the same on a saved frame (no capture, no pad)
Exit 0: in the range as Spider-Man. Exit 1: stopped; the last frame is saved to data/reenter/ and one line says why.

Rules (docs/plan.md scope boundary; .agents/skills/rivals-live-game/SKILL.md):
- Every A is preceded by a fresh frame that proves what the cursor is on: the PRACTICE tab with TRY COMPETITIVE not
  highlighted; then the PRACTICE RANGE tile (and DOOM MATCH not); then the Spider-Man portrait on the duelists tab.
  No proof, no press.
- The proof is the CURRENT screen (VUH-1325): `Live.frame()` never hands back an older frame (a static menu delivers no dxcam frame; it asks
  GDI, and fails closed if it cannot), every press re-grabs, re-classifies and re-proves at the pad and refuses a frame older than
  MAX_PROOF_AGE_S or taken before the last input settled, an unknown screen sends nothing (sticks included), and every hold ends in a
  `finally` with one neutral written on every exit of the process.
- X, START and the d-pad are never sent on the lobby. X is sent only on hero select, on a fresh frame classified as
  hero select. RB only on hero select.
- An unrecognised screen: send nothing and stop. While waiting for a screen to load nothing is sent either.
- Cursor steering and every wait are bounded.
- On arrival the player is in the SPAWN ROOM, where the range's idle drop fires. It walks toward the green door, steering the
  camera from the frames, and only stops when two frames in a row show the plaza with the Luna Snow bot ahead; then it attacks
  once (only moving or attacking resets the idle timer) and checks the HUD hero. It exits 1 if that is not confirmed in
  ARRIVE_S seconds, or the idle banner shows, or the range HUD is gone.

Everything that decides is a pure function of one frame (`look`, `on_practice_tab`, `on_practice_range_tile`,
`on_spiderman`), tested offline on tests/fixtures/reentry. Coordinates are 1280x720 px; any 16:9 frame is scaled.
"""
import argparse
import atexit
import base64
import json
import math
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from record import idle_warning, in_range  # noqa: E402  (the range HUD test every input loop uses, and the idle-kick banner)

OUT = ROOT / "data" / "reenter"

# --- thresholds: every number was measured on tests/fixtures/reentry (docs/lanes/reentry.md) ------------------------
START_YELLOW = 0.5      # lobby: yellow START bar. Lobby 0.91, every other screen 0.00
CONFIRM_YELLOW = 0.5    # hero select: yellow CONFIRM button. Hero select 0.86, every other screen 0.00
PANEL_DARK = 40         # practice panel: mean luminance of the dimmed band. Panel 15.6; lobby 85, hero select 140, range 118
PANEL_TITLE = 0.15      # ...and the white PRACTICE title in it: 0.326, every other frame <= 0.036. A black loading screen has neither
TAB_WHITE = 0.4         # hero select: the active tab is a white diamond. Active 0.65-0.69, inactive <= 0.08
TRY_COMP_DARK, TRY_COMP_LUM = 0.75, 78.6   # the unhighlighted banner, identical in three frames
TRY_COMP_DARK_TOL, TRY_COMP_LUM_TOL = 0.12, 12.0
TILE_DARK, TILE_BRIGHT = 100, 150   # panel: the hovered tile darkens (measured 45), the other stays bright (232)
SLOT_RED = 0.03         # hero select: red-hue share of Spider-Man's slot. Unhovered 0.276, hovered 0.076, another hero 0.005
HUD_RED = 0.10          # range: red-hue share of the HUD hero portrait. Spider-Man 0.247
ARRIVE_S, WALK_CHUNK_S = 14.0, 0.5   # arrival: the whole budget to get out of the spawn room, and one walk step
# Arrival cues, calibrated on five poses: tagrun0 frame 0 (the spawn room, door at the left edge) and frames 4-14 (the plaza with the
# bot ahead), and the lead's re6 (door DEAD AHEAD), re7 (the wall left of the door, where a blind walk ended) and q8 (the central console,
# two doors to the left). The spawn room's exit is a glowing LIME glass door (hue ~46, S ~110, V ~125; 6% of the view dead ahead, and the
# plaza with the bot is visible THROUGH it); an enemy outline is hue ~67, V ~170. Confirmation stays strict: no confirmation is an exit 1.
LIME = dict(h=(30, 56), s=70, v=70)       # the door glass, in HSV (OpenCV hue 0-179)
DOOR_H, DOOR_MIN_PX, DOOR_TOL = 100, 3000, 0.08   # a tall lime blob (px at 1280x720, area), and how far off-centre it may be and still be "ahead"
PLAZA_BOT_H, PLAZA_BOT_X, PLAZA_BOT_Y = (0.08, 0.6), (0.35, 0.95), (0.2, 0.85)   # the Luna Snow bot's box, fractions of the frame
PLAZA_LIME_MAX, PLAZA_BOX_LIME = 0.03, 0.15   # the door may fill at most this share of the upper view, and this share of a box's surroundings
SWEEP_S = 0.3                                  # a look-around turn (about 50 deg) when no door is in view
# The third-person camera draws the hero left of the screen centre (his column, the median x of his suit: 0.37-0.42 on 14 recorded
# frames); he walks along the camera's axis on that column, so the door's pane is steered onto his column, not the centre: centred, it
# left him on the dark jamb to its left (four refusals; the live arrival of 2026-09-21 12:24, step 21: pane 0.42-0.63, hero 0.39).
HERO_X = 0.40
DOOR_KEEP = 0.25     # once walking at a door, the blob nearest where that door should be now (after our own turn) is it, within this share
                     # of the width: two lime doors can be in view inside, and the biggest one jumped between them (live, steps 1-5).
                     # With none kept, the door nearest his column is chosen, not the biggest: on all four logged spawns the plaza door sits
                     # 0.04 from his column (x 0.44) and the other door 0.19 off (x 0.21), and the other one was the bigger blob in two
OUT_PX = 10000       # passing through a door: a walk step at it, then a frame with no door, and the door's biggest blob over its last
OUT_WALKS = 3        # OUT_WALKS walk steps at least this (px at 1280x720). The pane shrinks as he reaches it (the last walk before it vanished
                     # was 3.4-33k on the five logged crossings), but its peak over the last three walks was 16-54k; a sliver of the pane
                     # walked at from outside after a look-around was 3.8k
STILL = 8.0          # a walk that moved him changes the view: the mean grey difference of the masked scene (_scene) between the frame a
STILL_WALKS = 2      # walk decided on and the next is 21-47 on every advancing walk of the seven logged arrivals, 11-12 when he brushed the
                     # console's rim and slid off it, and 2-3 on every step walked into it (2026-09-21 14:01, steps 6-20: 16 walks, no
                     # advance). This many walks in a row under STILL is no progress.
SIDESTEP_S, SIDESTEP_TRIES = 0.4, 2   # then strafe LEFT this long, at most this many times: the rim he walks into lies ahead of him to his
                     # right (the door beyond it, up to the left), so left is the side it is clear; after the last try, no progress refuses
OUT_SWEEPS = 7       # outside, turn LEFT at most this many SWEEP_S steps (~360 deg) looking for the bot: live, from the exit she stood
                     # 25-45 deg left of the heading he left by (steps 12-15), one step brings her into plaza_view's window
YAW_STICK, YAW_DEG_S, FOCAL = 0.45, 172.0, 465.0   # the camera: deg/s at that right-stick deflection, and the focal length at 1280 wide (l4)
# The pad cursor sprite: a small ring (r ~19) with a bright centre dot when it hovers a widget, a plain larger ring (r ~26)
# otherwise. Both are white, so the search runs on min(B, G, R). l4_menu.find_cursor is not used: it takes the first
# Hough circle unchecked with minRadius 20, so on the 8 fixtures it is right on 3 of the 7 that show a cursor, wrong on
# 4, and invents one on the in-range frame (docs/lanes/reentry.md).
CURSOR_HOVER = dict(dot=150, ring=170, contrast=40)
CURSOR_PLAIN = dict(ring=180, contrast=70)

# --- geometry, 1280x720 px, read off the fixtures ---------------------------------------------------------------------
BOX = dict(
    start=(1010, 585, 1250, 608), confirm=(1040, 476, 1200, 496), try_comp=(1040, 414, 1240, 438),
    panel_title=(570, 214, 715, 250), panel_band=(100, 215, 440, 500), panel_above=(100, 30, 440, 170), panel_below=(100, 570, 440, 700),
    doom=(486, 346, 560, 440), range_tile=(818, 346, 846, 416),
    slot=(818, 14, 892, 72), hud_hero=(38, 608, 122, 678),
)
# The game's own hover tooltip on hero select ("Request to Team-Up with SPIDER-MAN"): it names the hovered hero in white text, right-aligned
# in a box that follows the cursor. TOOLTIP_PNG is that name's text, cut from the fixture heroselect-cursor-on-spiderman (min of B, G, R,
# 1280x720 scale); it matches 1.00 on its own frame and 0.92 on an independent one (the live refuse frame of 2026-09-20 19:28, a different
# icon and JPEG), and at most 0.49 on every other frame, THE PUNISHER's tooltip (0.31) included.
TOOLTIP_ROI, TOOLTIP_MATCH = (780, 55, 1130, 125), 0.75
TOOLTIP_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAADYAAAAQCAAAAAB429MqAAAClklEQVQoFZ3BS0gUcRgA8O/7z6xQioQE+cgiHR8hFISRIOmpNM1Kd3bWLct8B5ngC1N381kmlheLLnkosEMF5cEi053d2dEVIU0pjA5KFmKZPUAkd3f+X2DXTv5+KMFWoARbgRIAAhD8gwSbkGATEvwXxhLbk2pa0GOS0ecOi3mdFQKLXinZIPWoyfRpjDPYd3jQtyt9+Oe20zMfjZPzcyemlhBjuTC48T3NllQ3EfVVz7W4llbTCvbXennfw88r6QWzJMqtFd6iGmXu0IMXdaBPV73q0A2UONPaR7xXI8z5FvPzPFlrdXpawvNkErRmfbRd5WBr7e/tP2KbKb+8nMHHQ9MedY8EYRyHrtiKX5SvKLYzTxWzbnfpjog8mbMxu1O3qyQqTfM2r+ns7B0jI+W3x9Rb0ulGjOcUfHtn2Q9b5ZOk4Jdmi6tF1e2Rzcbj6/rEQlGllzOLHN9YIhW+c9+8Vq9rrqiIGxpgYoBwe++OAkvVsO/ZQYvsalM9jkhr8brP+SF2qjExbF3KWdvttJUtjx5ve9vncfSwag0wIYA506valb1WmfDcKavWoupNkXIuMt1+ILq+LG5lMdtVX3T3fHRPZ5a/VK+xZpdrgIkGebq9Qw3hVjOQYjOrt/Qhe4RSiGuqfaMvdQNQyekaSPFezMx+HyqluqtD7pVrgAlgdCjwzXwsN5/8F/Jkz078omQ6AHPvN+tvLo0LgYLM4q6GydLayb7I0YyB6hl3k8owHgmY6Q8REoh+kRMCIy4YgABoMCRCIEYsgAJwLhDziwZDlBAADMZNfoGQuMAJKWhDIBI5IBqIGADRQEIAYgBAhIxzjOMIgEQkGgQIwBlwhhwE4gjEOOPAOAIhAgEBCcwnEqAEW/EXHjA0aXhNW5EAAAAASUVORK5CYII="
)
_TOOLTIP = []
TABS = {"all": (1078, 109), "tab2": (1118, 149), "duelists": (1153, 193), "tab4": (1184, 243), "tab5": (1208, 296)}
RB_PRESSES = {"all": 2, "tab2": 1, "duelists": 0}  # RB moves one tab right; twice from "all" reaches duelists (skill)


@dataclass(frozen=True)
class Zone:
    """A polygon on screen. The cursor centre must sit inside it by `margin` px."""
    name: str
    poly: tuple
    margin: float

    def contains(self, p):
        return cv2.pointPolygonTest(np.array(self.poly, np.float32), (float(p[0]), float(p[1])), True) >= self.margin

    @property
    def aim(self):
        return tuple(np.array(self.poly, float).mean(axis=0))


# The drawn tab, profiled on a frame with no cursor near it (rows 377-394, edges slanted; the lightning icon ends it at ~1262) and
# on the live refuse frame data/reenter/refuse-20260920-184737.jpg, whose ring sat at (1220,390): INSIDE the tab, and refused by
# the old rectangle (rows 372-394, 5 px margin, so a 12 px band 3 px above the tab's middle). TRY COMPETITIVE starts to react at
# y ~406, and is checked separately before every A, so a 2 px margin on the true edge is safe.
PRACTICE_TAB = Zone("PRACTICE tab", ((1172, 377), (1262, 377), (1259, 395), (1166, 395)), 2)
RANGE_TILE = Zone("PRACTICE RANGE tile", ((677, 329), (860, 329), (835, 469), (652, 469)), 10)
DOOM_TILE = Zone("DOOM MATCH tile", ((449, 329), (675, 329), (639, 469), (420, 469)), 0)
SPIDER_SLOT = Zone("Spider-Man portrait", ((812, 12), (896, 12), (896, 74), (812, 74)), 6)


class Refuse(Exception):
    """The first thing that could not be verified. Carries the frame that showed it."""

    def __init__(self, reason, frame=None):
        super().__init__(reason)
        self.reason, self.frame = reason, frame


@dataclass(frozen=True)
class Proof:
    ok: bool
    reason: str  # one line, either way


@dataclass(frozen=True)
class Look:
    screen: str      # lobby | practice_panel | hero_select | in_range | unknown
    cursor: tuple    # (x, y) or None


# --- one frame in, one answer out ----------------------------------------------------------------------------------
def small(frame):
    return frame if frame.shape[1] == 1280 else cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)


def _box(s, name):
    x0, y0, x1, y1 = BOX[name]
    return s[y0:y1, x0:x1]


def _yellow(b):
    B, G, R = (b[..., i].astype(int) for i in range(3))
    return float(((R > 200) & (G > 170) & (B < 90)).mean())


def _lum(b):
    return float(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).mean())


def _red_hue(b, vmin=60):
    h = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    H, S, V = h[..., 0], h[..., 1], h[..., 2]
    return float((((H < 8) | (H > 172)) & (S > 110) & (V > vmin)).mean())


_TH = np.linspace(0, 2 * np.pi, 72, endpoint=False)
_R = np.arange(36)
_COS, _SIN = np.cos(_TH), np.sin(_TH)


def _ring_score(white, x, y):
    """Contrast of a cursor-sprite signature centred at (x, y), or 0. Needs a ring bright ALL the way round."""
    h, w = white.shape
    xs = np.clip((x + _R[:, None] * _COS).round().astype(int), 0, w - 1)
    ys = np.clip((y + _R[:, None] * _SIN).round().astype(int), 0, h - 1)
    v = white[ys, xs].astype(float)              # (radius, angle)
    mean, p20 = v.mean(axis=1), np.percentile(v, 20, axis=1)
    dot = mean[:3].mean()
    ra = 16 + int(p20[16:23].argmax())
    contrast_a = p20[ra] - mean[ra + 4:ra + 8].mean()
    rb = 23 + int(p20[23:31].argmax())
    contrast_b = p20[rb] - mean[min(rb + 4, 33):min(rb + 8, 35)].mean()
    hover = dot >= CURSOR_HOVER["dot"] and p20[ra] >= CURSOR_HOVER["ring"] and contrast_a >= CURSOR_HOVER["contrast"]
    plain = p20[rb] >= CURSOR_PLAIN["ring"] and contrast_b >= CURSOR_PLAIN["contrast"]
    return max(contrast_a if hover else 0.0, contrast_b if plain else 0.0)


RING_R, PEAKS, PEAK_MIN, REFINE_PX = (19, 26), 6, 0.2, 3   # sprite ring radii (hover, plain), peaks tried per radius, weakest peak, nudge window
_RINGS = {}


def _ring_template(r):
    """A ring of radius r/2 (the search runs on a half-size mask: 4x cheaper), two px thick."""
    if r not in _RINGS:
        h = r // 2
        m = np.zeros((2 * h + 5, 2 * h + 5), np.float32)
        cv2.circle(m, (h + 2, h + 2), h, 1.0, 2)
        _RINGS[r] = m
    return _RINGS[r]


def find_cursor(frame):
    """(x, y) of the pad cursor in 1280x720 px, or None. None is also the answer for a faint ring over dark art.

    Candidate centres are the strongest matches of a white ring (of each sprite radius) against the mask of bright-in-every-channel
    pixels, then judged by the ring signature, which is sharply peaked (one pixel off, its contrast falls from 130 to 50), so each is
    refined over a +-2 px window first. The first version took its candidates from a Hough transform, whose strongest circles on a
    busy portrait or a slightly noisy frame are other things: the ring was missed one frame in three, and a live run refused on hero
    select with the cursor sitting on Spider-Man."""
    s = small(frame)
    white = s.min(axis=2)  # bright only where bright in every channel: the sprite, not coloured art
    mask = cv2.resize((white > 190).astype(np.float32), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    best = (0.0, 0, 0)
    for r in RING_R:
        t = _ring_template(r)
        resp = cv2.matchTemplate(mask, t, cv2.TM_CCOEFF_NORMED)
        resp = np.nan_to_num(resp, nan=0.0, posinf=0.0, neginf=0.0)
        for _ in range(PEAKS):
            _, top, _, (px, py) = cv2.minMaxLoc(resp)
            if top < PEAK_MIN:
                break
            cx, cy = 2 * (px + t.shape[1] // 2), 2 * (py + t.shape[0] // 2)   # back to full size
            resp[max(0, py - 6):py + 7, max(0, px - 6):px + 7] = 0
            for dy in range(-REFINE_PX, REFINE_PX + 1):
                for dx in range(-REFINE_PX, REFINE_PX + 1):
                    score = _ring_score(white, cx + dx, cy + dy)
                    if score > best[0]:
                        best = (score, cx + dx, cy + dy)
    return (float(best[1]), float(best[2])) if best[0] > 0 else None


def classify(frame):
    """The screen: lobby, practice_panel, hero_select, in_range or unknown. Menus are told apart before the HUD test."""
    s = small(frame)
    if _yellow(_box(s, "start")) >= START_YELLOW:
        return "lobby"
    if _yellow(_box(s, "confirm")) >= CONFIRM_YELLOW:
        return "hero_select"
    title = _box(s, "panel_title")
    if (_lum(_box(s, "panel_band")) < PANEL_DARK and _lum(_box(s, "panel_above")) < 60
            and _lum(_box(s, "panel_below")) < 60 and float((title.min(axis=2) > 200).mean()) >= PANEL_TITLE):
        return "practice_panel"
    return "in_range" if in_range(s) else "unknown"


def hero_tab(frame):
    """Name of the active hero-select tab (a white diamond), or None if none stands out."""
    s = small(frame)
    white = {}
    for name, (x, y) in TABS.items():
        b = s[y - 14:y + 14, x - 14:x + 14]
        white[name] = float((b.min(axis=2) > 200).mean())
    name = max(white, key=white.get)
    return name if white[name] >= TAB_WHITE else None


def look(frame):
    screen = classify(frame)
    return Look(screen, find_cursor(frame) if screen in ("lobby", "practice_panel", "hero_select") else None)


def _need(frame, screen):
    lk = look(frame)
    if lk.screen != screen:
        return lk, Proof(False, f"the screen is {lk.screen}, not {screen}")
    if lk.cursor is None:
        return lk, Proof(False, "the cursor ring was not found")
    return lk, None


def on_practice_tab(frame):
    """Cursor centre inside the PRACTICE tab, and TRY COMPETITIVE (directly below, one A from a live queue) not highlighted."""
    lk, bad = _need(frame, "lobby")
    if bad:
        return bad
    if not PRACTICE_TAB.contains(lk.cursor):
        return Proof(False, f"cursor at ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}) is not inside the PRACTICE tab")
    b = _box(small(frame), "try_comp")
    dark, lum = float((b.max(axis=2) < 75).mean()), _lum(b)
    if abs(dark - TRY_COMP_DARK) > TRY_COMP_DARK_TOL or abs(lum - TRY_COMP_LUM) > TRY_COMP_LUM_TOL:
        return Proof(False, f"TRY COMPETITIVE does not look idle (dark {dark:.2f}, luminance {lum:.0f})")
    return Proof(True, f"cursor ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}) is on the PRACTICE tab; TRY COMPETITIVE is idle")


def on_practice_range_tile(frame):
    """Cursor inside the PRACTICE RANGE tile, that tile hovered (dark), DOOM MATCH (live mode) not."""
    lk, bad = _need(frame, "practice_panel")
    if bad:
        return bad
    if DOOM_TILE.contains(lk.cursor):
        return Proof(False, "cursor is on DOOM MATCH")
    if not RANGE_TILE.contains(lk.cursor):
        return Proof(False, f"cursor at ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}) is not inside the PRACTICE RANGE tile")
    s = small(frame)
    range_lum, doom_lum = _lum(_box(s, "range_tile")), _lum(_box(s, "doom"))
    if range_lum >= TILE_DARK:
        return Proof(False, f"the PRACTICE RANGE tile is not highlighted (luminance {range_lum:.0f})")
    if doom_lum <= TILE_BRIGHT:
        return Proof(False, f"DOOM MATCH looks highlighted (luminance {doom_lum:.0f})")
    return Proof(True, "cursor is on the PRACTICE RANGE tile; DOOM MATCH is not")


TIP_DX, TIP_DY, TIP_TOL = 141, 29, 8   # the name text sits this far right of and below the cursor ring's centre (both recorded frames: 141 x 29, +-1)


def tooltip_at(frame):
    """(match 0-1, (x, y) of the name text's top-left in 1280x720 px) of the hover tooltip's hero name against SPIDER-MAN.

    The best of the template at three horizontal half-pixel offsets: the name follows the cursor, so where it lands between pixels of the
    1280 x 720 frame varies, and one sharp template read a plainly legible SPIDER-MAN at 0.73 (live 2026-09-21 10:37, refused; the same
    tooltip read 0.92 on the re-invocation). Shifted: 0.87-1.00 on the three real tooltips, another hero's tooltip 0.37, every other
    fixture 0.61 or less. Vertical offsets as well lifted the non-tooltip frames to 0.66 and are not used."""
    if not _TOOLTIP:
        t = cv2.imdecode(np.frombuffer(base64.b64decode(TOOLTIP_PNG), np.uint8), cv2.IMREAD_GRAYSCALE)
        _TOOLTIP.extend(cv2.warpAffine(t, np.float32([[1, 0, dx], [0, 1, 0]]), t.shape[::-1], flags=cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_REPLICATE) for dx in (-0.5, 0.0, 0.5))
    x0, y0, x1, y1 = TOOLTIP_ROI
    roi = small(frame).min(axis=2)[y0:y1, x0:x1]
    _, top, _, (px, py) = max((cv2.minMaxLoc(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED)) for t in _TOOLTIP), key=lambda m: m[1])
    return float(top), (px + x0, py + y0)


def tooltip_spiderman(frame):
    """Match (0-1) of the hover tooltip's hero name against SPIDER-MAN: the game's own statement of which portrait is under the cursor."""
    return tooltip_at(frame)[0]


def tooltip_up(frame):
    """Is a hover tooltip drawn beside the top-left portrait? Its box has a white border, a row of it 190 px wide."""
    x0, y0, x1, y1 = TOOLTIP_ROI
    white = small(frame).min(axis=2)[y0:y1, x0:x1] > 205
    return bool((white.sum(axis=1) >= 150).any())


def on_spiderman(frame):
    """Duelists tab, and Spider-Man under the cursor, with the cursor ring FOUND: either the game's tooltip names SPIDER-MAN and sits where
    it is drawn relative to that ring (a tooltip can linger after the cursor has moved, so on its own it proves nothing), or the ring is
    inside the top-left portrait slot and that slot looks like Spider-Man (red). The pad layer supplies a frame taken after the cursor settled."""
    lk = look(frame)
    if lk.screen != "hero_select":
        return Proof(False, f"the screen is {lk.screen}, not hero_select")
    tab = hero_tab(frame)
    if tab != "duelists":
        return Proof(False, f"the hero tab is {tab}, not duelists")
    if lk.cursor is None:
        return Proof(False, "the cursor ring was not found")
    tip, at = tooltip_at(frame)
    if tip >= TOOLTIP_MATCH:
        if abs(at[0] - (lk.cursor[0] + TIP_DX)) > TIP_TOL or abs(at[1] - (lk.cursor[1] + TIP_DY)) > TIP_TOL:
            return Proof(False, f"the tooltip names SPIDER-MAN but sits at ({at[0]},{at[1]}), which does not fit the cursor at "
                                f"({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}): a stale tooltip or two cursors")
        return Proof(True, f"the game's tooltip names SPIDER-MAN (match {tip:.2f}) beside the cursor at ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f})")
    if tooltip_up(frame):  # the game names a hero, and it is not Spider-Man: whatever the ring and the colours say, it is not him
        return Proof(False, f"a tooltip is up and does not name SPIDER-MAN (match {tip:.2f})")
    if not SPIDER_SLOT.contains(lk.cursor):
        return Proof(False, f"cursor at ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}) is not on the Spider-Man portrait")
    red = _red_hue(_box(small(frame), "slot"))
    if red < SLOT_RED:
        return Proof(False, f"the portrait under the cursor is not Spider-Man (red share {red:.3f})")
    return Proof(True, f"cursor is on the Spider-Man portrait (red share {red:.3f})")


def hero_is_spiderman(frame):
    """The HUD hero portrait in the range is Spider-Man's (red)."""
    return _red_hue(_box(small(frame), "hud_hero")) >= HUD_RED


def _lime(s):
    """Mask (uint8) of the spawn room's lime glass door in a 1280x720 frame's upper 70%, small holes closed."""
    hsv = cv2.cvtColor(s[:504], cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = ((H >= LIME["h"][0]) & (H <= LIME["h"][1]) & (S > LIME["s"]) & (V > LIME["v"])).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))


def door(frame):
    """Centre x (0-1 of the width) of the biggest tall lime blob in the upper part of the view, or None: the spawn room's glass door.
    The plaza has none that big (at most 1.7k px on tagrun0, the door needs 3k); dead ahead it is 76k px."""
    return door_blob(frame)[0]


def door_blob(frame):
    """(centre x 0-1, area px at 1280x720) of the door's blob, or (None, 0): door() and the arrival log read the same one."""
    blobs = door_blobs(frame)
    return blobs[0] if blobs else (None, 0)


def door_blobs(frame):
    """Every tall lime blob big enough to be a door, [(centre x 0-1, area px)], biggest first."""
    n, _, st, cen = cv2.connectedComponentsWithStats(_lime(small(frame)), connectivity=8)
    blobs = [(float(cen[i][0] / 1280.0), int(st[i, 4])) for i in range(1, n) if st[i, 3] >= DOOR_H and st[i, 4] >= DOOR_MIN_PX]
    return sorted(blobs, key=lambda b: -b[1])


def hero_column(frame):
    """Median x (0-1 of the width) of Spider-Man's red suit in the middle of the view, or None: where the third-person camera draws him
    (0.37-0.42 on the recorded arrival frames). For the arrival log only; nothing is steered by it."""
    hsv = cv2.cvtColor(small(frame), cv2.COLOR_BGR2HSV)
    red = ((hsv[..., 0] < 8) | (hsv[..., 0] > 172)) & (hsv[..., 1] > 150) & (hsv[..., 2] > 120)
    red[:200], red[600:], red[:, :300] = False, False, False       # below the key hints, above the HUD row, off the portrait at the left
    xs = np.nonzero(red)[1]
    return round(float(np.median(xs)) / 1280.0, 3) if xs.size > 300 else None


ARRIVAL_GATE = ("a fresh frame showed the range HUD and no idle banner (arrive.look); Safe re-read the screen as in_range on a fresh frame; "
                "Live re-proves it at the write")


class ArrivalLog:
    """What `arrive` saw and did, one record and one frame per step, for the live measurement of the walk out of the spawn room
    (docs/lanes/reentry.md). Writes data/reenter/arrive-<time>/steps.jsonl and NNN.jpg, where the refusal frames already go.

    It is a record, not a control: it sends nothing, and it never raises into the flow. A failed write is counted and its first error
    kept (`failed`, `error`), and the arrival carries on exactly as without it."""

    def __init__(self, root=None):
        self.dir, self.n, self.failed, self.error = None, 0, 0, None
        try:
            self.dir = (OUT if root is None else root) / f"arrive-{time.strftime('%Y%m%d-%H%M%S')}"
        except Exception as e:                                          # noqa: BLE001 - a record must not stop the flow
            self._fail(e)

    def _fail(self, e):
        self.failed += 1
        self.error = self.error or repr(e)

    def step(self, t, frame, action, door_x=None, plaza=None):
        try:
            self.n += 1
            self.dir.mkdir(parents=True, exist_ok=True)
            name = f"{self.n:03d}.jpg"
            if not cv2.imwrite(str(self.dir / name), small(frame), [cv2.IMWRITE_JPEG_QUALITY, 92]):
                raise OSError(f"could not write {name}")
            x, px = door_blob(frame)
            rec = {"n": self.n, "t": round(float(t), 3), "action": action, "door_x": None if door_x is None else round(door_x, 3),
                   "door_blob_x": None if x is None else round(x, 3), "door_px": px, "hero_x": hero_column(frame),
                   "plaza_view": plaza, "gate": ARRIVAL_GATE, "frame": name}
            with open(self.dir / "steps.jsonl", "a") as fh:
                fh.write(json.dumps(rec) + "\n")
        except Exception as e:                                          # noqa: BLE001
            self._fail(e)

    def summary(self):
        return f"{self.n} arrival steps logged to {self.dir}" + (f"; {self.failed} write failures, first {self.error}" if self.failed else "")


def plaza_view(frame):
    """The plaza with the Luna Snow bot ahead, in the open: an enemy box (L3's green finder, on the NATIVE frame) of a plausible size in the
    middle of the view, that is not the door. Facing the door from inside, the bot shows THROUGH its glass and the glow makes boxes of its
    own (re6), so a box counts only if lime is not all round it and the door does not fill the view."""
    from perception.outline import find_enemies
    lime = _lime(small(frame))
    if lime.mean() >= PLAZA_LIME_MAX:
        return False
    h, w = frame.shape[:2]
    for d in find_enemies(frame, scale=w / 1280.0):
        x1, y1, x2, y2 = d.bbox
        if not (PLAZA_BOT_H[0] <= (y2 - y1) / h <= PLAZA_BOT_H[1] and PLAZA_BOT_X[0] <= (x1 + x2) / 2 / w <= PLAZA_BOT_X[1]
                and PLAZA_BOT_Y[0] <= (y1 + y2) / 2 / h <= PLAZA_BOT_Y[1]):
            continue
        k, pad = 1280.0 / w, 0.25
        bw, bh = (x2 - x1) * k, (y2 - y1) * k
        ring = lime[max(0, int(y1 * k - pad * bh)):int(y2 * k + pad * bh), max(0, int(x1 * k - pad * bw)):int(x2 * k + pad * bw)]
        if ring.size and ring.mean() < PLAZA_BOX_LIME:
            return True
    return False


def describe(frame):
    """What a run would do from this frame, as printable lines. Pure: sends nothing."""
    lk = look(frame)
    cur = "not found" if lk.cursor is None else f"({lk.cursor[0]:.0f},{lk.cursor[1]:.0f})"
    out = [f"screen: {lk.screen}", f"cursor: {cur}"]
    if lk.screen == "unknown":
        return out + ["would send nothing and stop: unknown screen"]
    if lk.screen == "in_range":
        dr = door(frame)
        return out + [f"plaza with the bot ahead: {'yes' if plaza_view(frame) else 'no'}",
                      f"glass door: {'not in view' if dr is None else f'centre x {dr:.2f} of the width'}",
                      f"would turn to the door and walk to it (camera steered from the frames; a look-around when none is in view) until two frames show the plaza, for at most "
                      f"{ARRIVE_S:.0f} s, attack once, then check the HUD hero is Spider-Man; exit 1 if the plaza is not confirmed"]
    steps = {"lobby": (PRACTICE_TAB, on_practice_tab, "A opens the PRACTICE panel"),
             "practice_panel": (RANGE_TILE, on_practice_range_tile, "A loads hero select (about 12 s)"),
             "hero_select": (SPIDER_SLOT, on_spiderman, "A selects the hero, then X confirms")}[lk.screen]
    zone, proof_fn, does = steps
    if lk.screen == "hero_select":
        tab = hero_tab(frame)
        out.append(f"hero tab: {tab}")
        tip = tooltip_spiderman(frame)
        out.append(f"hover tooltip names SPIDER-MAN: {'yes' if tip >= TOOLTIP_MATCH else 'no'} (match {tip:.2f})")
        n = RB_PRESSES.get(tab)
        out.append("would stop: the tab is not recognised" if n is None else
                   f"would press RB {n}x to reach duelists" if n else "already on duelists")
    if lk.cursor is None:
        out.append(f"would jiggle the stick to find the cursor (at most {MAX_MISSES} tries), then stop")
        return out
    inside = lk.cursor is not None and zone.contains(lk.cursor)
    out.append(f"would steer the cursor to the {zone.name} (aim {zone.aim[0]:.0f},{zone.aim[1]:.0f}); it is "
               + ("already inside" if inside else "not inside yet"))
    proof = proof_fn(frame)
    out.append(f"proof for A right now: {'OK' if proof.ok else 'NO'} - {proof.reason}")
    out.append(f"then {does}" if proof.ok else "would NOT press A on this frame")
    return out


# --- the machine: capture + one pad, and a guard that decides what may be sent -----------------------------------------
MAX_STEPS, MAX_MISSES = 30, 4              # cursor steering: at most this many nudges / lost-ring jiggles
SPEED, DEADBAND_S = 700.0, 0.035           # px/s at full stick (1280x720), and the shortest useful tap; l4_menu's step law
ALLOWED = {"lobby": {"A"}, "practice_panel": {"A"}, "hero_select": {"A", "RB", "X"}, "in_range": {"RT"}}


MAX_PROOF_AGE_S = 0.3   # a proof frame may be this old when the pad is written
STICK_OK = ("lobby", "practice_panel", "hero_select", "in_range")   # the screens a stick may move on; "unknown" sends nothing, sticks included


class Live:
    """A capture path and ONE virtual pad held open for the whole run. Built only when input is about to be sent.

    This is the lowest layer that touches the pad, so the rules are enforced here, not left to the callers:

    - `frame()` is always the CURRENT screen, timestamped (`frame_t`). dxcam delivers a frame only when the screen changes, so a static menu
      gives none, and none is not "unchanged" (a live review got X sent 22 s after the frame that proved it). It falls back to GDI, which
      reads the screen as it is now, and if neither can produce a frame it raises: fail closed. An older frame is never handed back.
    - a stick moves only on a screen in STICK_OK; a button only on a screen ALLOWED lists for it, and `tap` grabs its OWN frame at the
      moment of the press, checks the screen is the one that was proven, re-runs the proof on it, and refuses one older than
      MAX_PROOF_AGE_S when the pad is written. `settled_t` says when the last input finished and the screen had settled; no proof
      frame is older than that.
    - every hold ends in a `finally`: an exception or Ctrl-C can never leave a button or a stick held. `release_all` zeroes the whole pad.
    """

    def __init__(self, cap, first_frame=None, sleep=time.sleep, settle_s=3.0, gdi=None, clock=time.perf_counter):
        import vgamepad as vg
        self.sleep, self.vg, self.cap, self.clock, self._gdi = sleep, vg, cap, clock, gdi
        self.frame_t, self.settled_t = clock(), -math.inf
        self.pad = vg.VX360Gamepad()
        try:
            self.sleep(settle_s)  # Windows and the game enumerate the pad, and show their banner
        finally:
            self.release_all()
        self.settled_t = self.clock()

    def now(self):
        return self.clock()

    def gdi(self):
        if self._gdi is None:
            from capture import Capture
            self._gdi = Capture("gdi")
        return self._gdi

    def frame(self, timeout=0.15):
        """The screen as it is now. Sets `frame_t` to when the grab that produced it STARTED, so a frame is never younger than it says:
        a dxcam frame is stamped with this call's start, a GDI frame with the moment the GDI grab began (the time spent waiting for a
        dxcam frame that never came is not this frame's age)."""
        t0 = self.clock()
        while True:
            f = self.cap.grab() if self.cap is not None else None
            if f is not None:
                self.frame_t = t0
                return f
            if self.clock() - t0 > timeout:
                break
            self.sleep(0.005)
        t_gdi = self.clock()
        try:
            f = self.gdi().grab()  # the screen right now, changed or not
        except Exception as e:  # noqa: BLE001 - any capture failure means no proof
            raise Refuse(f"no current frame from the display ({e!r}); nothing sent") from None
        if f is None:
            raise Refuse("no current frame from the display; nothing sent")
        self.frame_t = t_gdi
        return f

    def release_all(self):
        """Every button, trigger and stick to neutral. Safe to call at any time and more than once."""
        self.pad.reset()
        self.pad.update()

    def _gate_stick(self, screen):
        """A stick moves only on the screen its caller is working on (a recognized screen is not an acceptable one: an arrival stick
        must not land on the lobby's cursor), proven on a frame taken after the last input settled and still fresh at the write."""
        if screen not in STICK_OK:
            raise Refuse(f"no stick is ever sent for screen {screen}")
        f = self.frame()
        now = classify(f)
        if now != screen:
            raise Refuse(f"the screen is {now}, not {screen}; no stick sent", f)
        if self.frame_t < self.settled_t:
            raise Refuse("the stick's proof frame predates the last input's settling; no stick sent", f)
        age = self.clock() - self.frame_t
        if age > MAX_PROOF_AGE_S:
            raise Refuse(f"the stick's proof is {age:.2f} s old (limit {MAX_PROOF_AGE_S} s); no stick sent", f)

    def stick(self, x, y, secs, screen="in_range"):
        self._gate_stick(screen)
        try:
            self.pad.left_joystick_float(x, y)
            self.pad.update()
            self.sleep(secs)
        finally:
            self.release_all()
        self.sleep(0.25)
        self.settled_t = self.clock()

    def rstick(self, x, y, secs, screen="in_range"):
        self._gate_stick(screen)
        try:
            self.pad.right_joystick_float(x, y)
            self.pad.update()
            self.sleep(secs)
        finally:
            self.release_all()
        self.sleep(0.15)
        self.settled_t = self.clock()

    def tap(self, button, screen=None, proof_fn=None):
        b = self.vg.XUSB_BUTTON
        codes = {"A": b.XUSB_GAMEPAD_A, "X": b.XUSB_GAMEPAD_X, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER}
        if button != "RT" and button not in codes:
            raise KeyError(button)
        f = self.frame()                      # the screen NOW, not the one that was proven a moment ago
        now_screen = classify(f)
        if screen is not None and now_screen != screen:
            raise Refuse(f"the screen changed under the proof: proven on {screen}, now {now_screen}; {button} not sent", f)
        if button not in ALLOWED.get(now_screen, ()):
            raise Refuse(f"{button} is not allowed on screen {now_screen}", f)
        if button == "A":
            proof = proof_fn(f) if proof_fn else Proof(False, "no proof was supplied")
            if not proof.ok:
                raise Refuse(f"no proof for A at the moment of the press: {proof.reason}", f)
        if self.frame_t < self.settled_t:
            raise Refuse(f"the proof frame predates the last input's settling; {button} not sent", f)
        age = self.clock() - self.frame_t
        if age > MAX_PROOF_AGE_S:
            raise Refuse(f"the proof is {age:.2f} s old (limit {MAX_PROOF_AGE_S} s); {button} not sent", f)
        try:
            if button == "RT":
                self.pad.right_trigger_float(1.0)
                self.pad.update()
                self.sleep(0.15)
            else:
                self.pad.press_button(button=codes[button])
                self.pad.update()
                self.sleep(0.12)
        finally:
            self.release_all()
        self.sleep(0.5)
        self.settled_t = self.clock()


class Safe:
    """Everything the flow sends goes through here: the screen must allow the button, and A needs a proof. `Live` re-checks all of it at the pad."""

    def __init__(self, io, log=print):
        self.io, self.log = io, log

    def frame(self):
        return self.io.frame()

    def now(self):
        return self.io.now()

    def sleep(self, s):
        self.io.sleep(s)

    def _gate_stick(self, screen):
        f = self.io.frame()
        now = classify(f)
        if screen not in STICK_OK or now != screen:
            raise Refuse(f"the screen is {now}, not {screen}; no stick sent", f)

    def stick(self, x, y, secs, screen="in_range"):
        self._gate_stick(screen)
        self.io.stick(x, y, secs, screen=screen)

    def rstick(self, x, y, secs, screen="in_range"):
        self._gate_stick(screen)
        self.io.rstick(x, y, secs, screen=screen)

    def press(self, button, proof_fn=None):
        f = self.io.frame()  # current, and re-taken by the pad layer at the press
        screen = classify(f)
        if button not in ALLOWED.get(screen, ()):
            raise Refuse(f"{button} is not allowed on screen {screen}", f)
        if button == "A":
            proof = proof_fn(f) if proof_fn else Proof(False, "no proof was supplied")
            if not proof.ok:
                raise Refuse(f"no proof for A: {proof.reason}", f)
            self.log(f"reenter: A ({proof.reason})")
        else:
            self.log(f"reenter: {button}")
        self.io.tap(button, screen=screen, proof_fn=proof_fn)


class Reach:
    """What a tap does to the cursor along one axis, learned from the taps themselves: moved = a * (secs - c).

    The prior is l4_menu's law (700 px/s after 35 ms of dead time). The real cursor may instead move a long way on the shortest
    tap (a floor: c < 0), which no fixed law survives: a 24 px floor step cannot settle into an 18 px tab, it just alternates
    either side of it. Every tap seen outweighs the prior, so the law follows the cursor that is really there."""

    def __init__(self):
        self.pts = [(DEADBAND_S, 0.0, 0.2), (0.5, SPEED * (0.5 - DEADBAND_S), 0.2)]   # (secs, px moved, weight)

    def learn(self, secs, moved, weight=1.0):
        self.pts.append((secs, max(0.0, moved), weight))

    def fit(self):
        w = sum(p[2] for p in self.pts)
        ms, mm = sum(p[0] * p[2] for p in self.pts) / w, sum(p[1] * p[2] for p in self.pts) / w
        var = sum(p[2] * (p[0] - ms) ** 2 for p in self.pts)
        a = sum(p[2] * (p[0] - ms) * (p[1] - mm) for p in self.pts) / var if var > 1e-9 else SPEED
        a = min(3000.0, max(150.0, a))
        return a, ms - mm / a

    def secs(self, d):
        """Tap length expected to move the cursor d px (d > 0)."""
        a, c = self.fit()
        return min(0.5, max(DEADBAND_S, c + d / a))

    def least(self):
        """What the shortest tap moves the cursor by: 0 for a dead-time cursor, tens of px for a floor one."""
        a, c = self.fit()
        return max(0.0, a * (DEADBAND_S - c))


def steer(io, zone, screen, locate=None, done=None):
    """Nudge the cursor into `zone`, one axis at a time (l4_menu's axis rule). Bounded: at most MAX_STEPS nudges.

    `done(frame)` is an independent way to know the cursor is where it must be (hero select: the game's tooltip names the hero); when it
    holds, steering stops without needing the ring at all.

    Each axis learns its own tap law (Reach). A correction shorter than the shortest tap can move is not attempted: the cursor
    steps AWAY by that much and comes back with a real move, which lands within the noise of a move that size instead of
    overshooting by half a floor step every time.
    """
    locate = locate or find_cursor  # looked up now, so a test can replace the finder
    misses, reach, prev = 0, {"x": Reach(), "y": Reach()}, None
    for _ in range(MAX_STEPS):
        f = io.frame()
        pos = locate(f)
        if done is not None and done(f):
            return pos
        if pos is None:  # hidden until the stick moves, or lost over busy art: wiggle onto plainer ground
            misses, prev = misses + 1, None
            if misses > MAX_MISSES:
                raise Refuse("the cursor ring was not found", f)
            io.stick(-1.0 if misses % 2 else 0.0, 0.0 if misses % 2 else 1.0, 0.12, screen=screen)   # only on the menu being steered
            continue
        if prev:
            axis, sign, secs, before = prev
            i, edge = "xy".index(axis), (1279, 719)["xy".index(axis)]
            pinned = pos[i] >= edge - 1 if sign > 0 else pos[i] <= 1   # the screen edge stopped it: it went at LEAST this far
            reach[axis].learn(secs, sign * (pos[i] - before[i]), 0.5 if pinned else 1.0)
            prev = None
        if zone.contains(pos):
            return pos
        dx, dy = zone.aim[0] - pos[0], zone.aim[1] - pos[1]
        axis, d = ("x", dx) if abs(dx) > 9 else ("y", dy)
        sign, least = math.copysign(1.0, d), reach[axis].least()
        if abs(d) < 0.7 * least:  # nearer than the shortest tap can reach: back off by it, then come back
            sign, d = -sign, least
        secs = reach[axis].secs(abs(d))
        io.stick(sign if axis == "x" else 0.0, -sign if axis == "y" else 0.0, secs, screen=screen)  # stick up = screen up
        prev = (axis, sign, secs, pos)
    raise Refuse(f"the cursor did not reach the {zone.name} in {MAX_STEPS} nudges", io.frame())


SETTLE_S = 3.0   # a just-opened screen may take this long to be readable: live, hero select's active tab read 192 of 255 on the first frame
                 # (the screen fading in, game clock 00:02) against 250 settled, under TAB_WHITE's bar; 30 s later it read "all"


def settle(io, screen, read, timeout=SETTLE_S, poll=0.1):
    """(frame, value) once `read(frame)` is not None on a fresh frame that still shows `screen`. Sends nothing while it looks; the screen
    changing, or nothing readable within `timeout`, is a Refuse, as an unreadable screen always was."""
    end = io.now() + timeout
    while True:
        f = io.frame()
        now = classify(f)
        if now != screen:
            raise Refuse(f"the screen changed to {now} while waiting to read {screen}", f)
        value = read(f)
        if value is not None or io.now() >= end:
            return f, value
        io.sleep(poll)


def wait_for(io, screens, timeout, poll=0.3):
    """Send nothing until the frame classifies as one of `screens`; Refuse after `timeout` seconds."""
    end, f = io.now() + timeout, None
    while io.now() < end:
        f = io.frame()
        if classify(f) in screens:
            return f
        io.sleep(poll)
    raise Refuse(f"did not reach {' or '.join(sorted(screens))} within {timeout:.0f} s", f)


def arrive(io, safe, trace=None):
    """In the range, in the spawn room: walk to the door and out onto the plaza, steering the camera from the frames.

    Every step re-reads a fresh frame: the range HUD gone or the idle banner up stops it with no further input. It is done only
    when two frames in a row show the plaza (plaza_view); the budget is ARRIVE_S, and a run that cannot confirm exits 1 rather
    than leave the player where the idle drop fires.

    `trace` (an ArrivalLog; by default the one `main` attached to the live io as `arrival_log`, None in a simulation): each step is
    recorded AFTER its input has gone out, so no record ever sits between a proof frame and the write it gates, and a record that fails
    is swallowed here as well as inside it."""
    trace = getattr(io, "arrival_log", None) if trace is None else trace
    def note(f, action, x=None, plaza=None):
        if trace is not None:
            try:
                trace.step(io.now(), f, action, x, plaza)
            except Exception:                                           # noqa: BLE001 - a record must never change the flow
                pass

    try:
        _arrive(io, safe, note)
    except Refuse as r:
        if r.frame is not None:                                         # no capture here: the refusal carries its frame or is not recorded
            note(r.frame, f"refused: {r.reason}")
        raise


@dataclass
class ArrivalMemory:
    """What arrival_step carries from one frame to the next."""
    plaza: int = 0                 # frames in a row that showed the plaza
    chosen: float | None = None    # x of the door being walked at, as the last frame showed it, moved by our own turn since
    walks: list = field(default_factory=list)   # its size on the walk steps taken at it (a new or lost door starts it again)
    walked: bool = False           # the last step walked
    out: bool = False              # through the door: from here on no door is steered to or walked at
    scene: object = None           # the masked scene of the last frame decided on (_scene)
    still: int = 0                 # walks in a row that did not change the view
    sidesteps: int = 0             # strafes taken to get off something walked into
    sweeps: int = 0                # look-around turns taken outside


def _scene(f):
    """The view as a small grey thumbnail, the hero and the key hints blanked: what a walk that moves him changes."""
    g = cv2.cvtColor(small(f), cv2.COLOR_BGR2GRAY)[60:600].astype(np.float32)
    g[140:, 330:610] = 0                              # the hero, drawn around x 0.40 in the lower part
    g[:60, :300] = 0                                  # the key hints, top left
    return cv2.resize(g, (160, 68), interpolation=cv2.INTER_AREA)


def arrival_step(f, m):
    """The arrival's decision on one frame: ("plaza?", why) a second look standing still, ("done", why), ("turn", stick, secs, why),
    ("walk", secs, why), ("strafe", stick x, secs, why) sideways off something walked into, or ("give up", why). Pure: it reads only the
    frame and `m`, which it updates; it sends nothing."""
    scene = _scene(f)
    moved = None if (m.scene is None or not m.walked) else float(np.mean(np.abs(scene - m.scene)))
    m.scene = scene
    if plaza_view(f):
        m.plaza += 1
        return ("done", "plaza confirmed on a second frame") if m.plaza >= 2 else ("plaza?", "plaza seen: a second look, standing still")
    m.plaza = 0
    blobs = door_blobs(f)
    if not m.out and not blobs and m.walked and max(m.walks[-OUT_WALKS:], default=0) >= OUT_PX:
        m.out = True                                  # walked at a big door, and now none: through it
    if m.out:                                         # never a door again, not even a sliver of its pane seen from outside (live step 17)
        m.walked = False
        if m.sweeps >= OUT_SWEEPS:
            return ("give up", f"out, but no bot in view after {OUT_SWEEPS} look-around turns")
        m.sweeps += 1
        return ("turn", -YAW_STICK, SWEEP_S, f"out: look around left, rstick {-YAW_STICK:+.2f} for {SWEEP_S:.2f} s")
    if moved is not None:
        m.still = m.still + 1 if moved < STILL else 0
    if m.still >= STILL_WALKS:                        # walking into something: the view does not change
        m.still, m.walked = 0, False
        if m.sidesteps >= SIDESTEP_TRIES:
            return ("give up", f"walking does not move him, after {SIDESTEP_TRIES} sidesteps")
        m.sidesteps += 1
        return ("strafe", -1.0, SIDESTEP_S, f"no progress: sidestep left, stick -1.00 for {SIDESTEP_S:.2f} s ({m.sidesteps} of {SIDESTEP_TRIES})")
    kept = min(blobs, key=lambda b: abs(b[0] - m.chosen)) if m.chosen is not None and blobs else None
    if kept is not None and abs(kept[0] - m.chosen) <= DOOR_KEEP:
        x, px = kept
    else:                                             # nothing kept (or it is gone): the door nearest his column, not the biggest
        x, px = min(blobs, key=lambda b: abs(b[0] - HERO_X)) if blobs else (None, 0)
        m.walks = []
    m.walked = False
    if x is None:  # nothing to walk toward (a wall, the plaza with no bot in view): look around, do not walk blind
        m.chosen = None
        return ("turn", YAW_STICK, SWEEP_S, f"no door: look around, rstick {YAW_STICK:+.2f} for {SWEEP_S:.2f} s")
    if abs(x - HERO_X) > DOOR_TOL:  # the pane is off his column: turn it onto his column first, no walking
        deg = math.degrees(math.atan((x - HERO_X) * 1280.0 / FOCAL))
        secs = min(0.6, abs(deg) / YAW_DEG_S)
        m.chosen = x - math.copysign(secs * YAW_DEG_S, deg) * math.pi / 180 * FOCAL / 1280.0   # where our turn moves it
        return ("turn", math.copysign(YAW_STICK, deg), secs,
                f"door off his column: turn, rstick {math.copysign(YAW_STICK, deg):+.2f} for {secs:.2f} s")
    m.chosen, m.walked = x, True
    m.walks.append(px)
    return ("walk", WALK_CHUNK_S, f"door on his column: walk, stick forward for {WALK_CHUNK_S:.2f} s")


def _arrive(io, safe, note):
    def look():
        f = safe.frame()
        if not in_range(small(f)):
            raise Refuse("the range HUD is gone", f)
        if idle_warning(small(f)):
            raise Refuse("the idle-kick banner is up: still in the spawn room?", f)
        return f

    f, m, spent = look(), ArrivalMemory(), 0.0
    while spent < ARRIVE_S:
        x = m.chosen
        act = arrival_step(f, m)
        if act[0] == "done":
            note(f, act[-1], plaza=True)
            break
        if act[0] == "give up":
            note(f, act[-1], plaza=False)
            raise Refuse(act[-1], f)
        if act[0] == "plaza?":
            safe.sleep(0.15)
            spent += 0.15
            note(f, act[-1], plaza=True)
        elif act[0] == "turn":
            safe.rstick(act[1], 0.0, act[2], screen="in_range")
            spent += act[2] + 0.15
            note(f, act[-1], x, False)
        elif act[0] == "strafe":
            safe.stick(act[1], 0.0, act[2], screen="in_range")
            spent += act[2] + 0.25
            note(f, act[-1], x, False)
        else:
            safe.stick(0.0, 1.0, act[1], screen="in_range")
            spent += act[1] + 0.25
            note(f, act[-1], m.chosen, False)
        f = look()
    else:
        raise Refuse(f"could not confirm the spawn room was left within {ARRIVE_S:.0f} s", f)
    safe.press("RT")
    f = look()
    note(f, "RT pressed once")
    if not hero_is_spiderman(f):
        raise Refuse("in the range, but the HUD hero portrait is not Spider-Man", f)


def run(io, log=print):
    """Lobby to range. Returns on success; raises Refuse at the first step that cannot be verified."""
    safe, seen = Safe(io, log), {}
    for _ in range(12):
        f = io.frame()
        screen = classify(f)
        seen[screen] = seen.get(screen, 0) + 1
        if seen[screen] > 2 and screen != "in_range":
            raise Refuse(f"still on {screen} after trying to leave it", f)
        log(f"reenter: screen {screen}")
        if screen == "unknown":
            raise Refuse("unknown screen; nothing sent", f)
        if screen == "in_range":
            arrive(io, safe)
            return
        if screen == "lobby":
            steer(safe, PRACTICE_TAB, "lobby")
            safe.press("A", on_practice_tab)
            wait_for(io, {"practice_panel"}, 10)
        elif screen == "practice_panel":
            steer(safe, RANGE_TILE, "practice_panel")
            safe.press("A", on_practice_range_tile)
            wait_for(io, {"hero_select", "in_range"}, 40)  # loading screens between are unknown: nothing is sent
        elif screen == "hero_select":
            f, tab = settle(io, "hero_select", hero_tab)          # the screen fades in: its active tab is dim for the first moments
            n = RB_PRESSES.get(tab)
            if n is None:
                raise Refuse(f"hero tab {tab} is not recognised", f)
            for _ in range(n):
                safe.press("RB")
            f, tab = settle(io, "hero_select", hero_tab)
            if tab != "duelists":
                raise Refuse(f"the hero tab is {tab} after RB, not duelists", f)
            steer(safe, SPIDER_SLOT, "hero_select", done=lambda fr: on_spiderman(fr).ok)   # the tooltip beside the ring counts; the tooltip alone does not
            safe.press("A", on_spiderman)
            safe.press("X")  # hero select only: Safe re-classifies the frame first
            wait_for(io, {"in_range"}, 40)
    raise Refuse("too many screen changes")


def save(frame, tag):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}.jpg"
    cv2.imwrite(str(path), small(frame), [cv2.IMWRITE_JPEG_QUALITY, 92])
    return path


def _dxcam():
    from capture import Capture
    return Capture("dxcam")


def _first_frame(cap, timeout=5.0):
    """The screen now: dxcam if it delivers one (it does not on a static menu), else GDI, else None (and the run stops before any pad opens)."""
    end, f = time.perf_counter() + timeout / 5, None
    while f is None and time.perf_counter() < end:
        f = cap.grab()
    if f is None:
        try:
            from capture import Capture
            f = Capture("gdi").grab()
        except Exception:  # noqa: BLE001 - no frame means no run
            f = None
    return f


def _release(io):
    """Neutral, whatever happened. Never raises: this runs in a finally and at exit."""
    try:
        fn = getattr(io, "release_all", None)
        if fn:
            fn()
    except Exception as e:  # noqa: BLE001
        print(f"reenter: WARNING: could not release the pad: {e!r}", file=sys.stderr)


def _last(io):
    """A frame for the refuse picture, or a black one if the display gives none: the report must not itself fail."""
    try:
        return io.frame()
    except Exception:  # noqa: BLE001
        return np.zeros((720, 1280, 3), np.uint8)


PROOFS = {"lobby": on_practice_tab, "practice_panel": on_practice_range_tile, "hero_select": on_spiderman}


class _NoPad:
    """vgamepad's surface with no device behind it: records when the pad WOULD have been written. Used only by the timing dry run."""

    def __init__(self, clock):
        self.clock, self.writes = clock, []

    def press_button(self, button):
        self.writes.append(self.clock())

    def right_trigger_float(self, v):
        self.writes.append(self.clock())

    def left_joystick_float(self, x, y):
        pass

    right_joystick_float = left_joystick_float

    def reset(self):
        pass

    def update(self):
        pass


class DryLive(Live):
    """Live's REAL frame() and tap() code over a pad that is not there: vgamepad is never imported and no device is created."""

    def __init__(self, cap, gdi, clock=time.perf_counter, sleep=time.sleep):   # noqa: super().__init__ would open a pad: not called
        self.cap, self._gdi, self.clock, self.sleep = cap, gdi, clock, sleep
        codes = {"XUSB_GAMEPAD_A": "A", "XUSB_GAMEPAD_X": "X", "XUSB_GAMEPAD_RIGHT_SHOULDER": "RB"}
        self.vg = type("vg", (), {"XUSB_BUTTON": type("XUSB_BUTTON", (), codes)})
        self.pad = _NoPad(clock)
        self.frame_t, self.settled_t = clock(), -math.inf


def dxcam_probe(cap, secs=2.0, clock=time.perf_counter, log=print):
    """How dxcam delivers on this screen: grabs that returned a frame over `secs` of back-to-back polling, and the gaps between them."""
    t0, got, polls = clock(), [], 0
    while clock() - t0 < secs:
        polls += 1
        if cap.grab() is not None:
            got.append(clock())
    gaps = sorted((b - a) * 1e3 for a, b in zip(got, got[1:]))
    first = f"{(got[0] - t0) * 1e3:.0f} ms" if got else "never"
    log(f"reenter: dxcam probe {len(got)} frames in {polls} grabs over {secs:.1f} s; first after {first}; "
        + (f"gap p50 {gaps[len(gaps) // 2]:.0f} ms, max {gaps[-1]:.0f} ms" if gaps else "no gaps (fewer than two frames)"))
    return got


def timings(cap, gdi, n, clock=time.perf_counter, sleep=time.sleep, log=print):
    """What a press costs on the live screen, with no pad: each round runs the REAL Safe.press -> Live.tap code (DryLive: the same frame(),
    classify, proof and age check, the pad write a no-op) and times every stage from outside. `age` is what tap compared with
    MAX_PROOF_AGE_S at the write, and `refused` says whether it refused. Returns the rows."""
    dry, ev = DryLive(cap, gdi, clock, sleep), []
    real_frame, real_classify, real_gdi = dry.frame, globals()["classify"], gdi.grab

    def frame(*a, **k):
        s = clock()
        f = real_frame(*a, **k)
        ev.append(("frame", s, clock(), dry.frame_t))
        return f

    def gdi_grab():
        s = clock()
        f = real_gdi()
        ev.append(("gdi", s, clock(), None))
        return f

    def classify_timed(f):
        s = clock()
        r = real_classify(f)
        ev.append(("classify", s, clock(), None))
        return r

    dry.frame, gdi.grab = frame, gdi_grab
    globals()["classify"] = classify_timed
    rows = []
    try:
        for _ in range(n):
            ev.clear()
            screen = real_classify(dry.frame())
            fn = PROOFS.get(screen)
            if fn is None:
                log(f"reenter: timing screen={screen}: no A to prove here, round skipped")
                continue

            def proof(f, fn=fn):
                s = clock()
                r = fn(f)
                ev.append(("proof", s, clock(), None))
                return r

            ev.clear()
            dry.pad.writes.clear()
            refused, t_check = None, None
            try:
                Safe(dry, log=lambda *_: None).press("A", proof)
            except Refuse as r:
                refused, t_check = r.reason, clock()
            top = [e for e in ev if e[0] != "classify" or not any(p[0] == "proof" and p[1] <= e[1] <= p[2] for p in ev)]
            frames = [e for e in top if e[0] == "frame"]
            tap_t0 = frames[-1][1] if len(frames) >= 2 else None       # Safe.press's frame, then tap's own
            in_tap = [e for e in top if tap_t0 is not None and e[1] >= tap_t0]
            dur = lambda kind, es: sum((e[2] - e[1]) * 1e3 for e in es if e[0] == kind)   # noqa: E731
            end = dry.pad.writes[0] if dry.pad.writes else t_check
            row = dict(screen=screen, safe_ms=((tap_t0 or clock()) - (top[0][1] if top else clock())) * 1e3,
                       tap_frame_ms=dur("frame", in_tap), tap_gdi_ms=dur("gdi", in_tap), tap_classify_ms=dur("classify", in_tap),
                       tap_proof_ms=dur("proof", in_tap), age_ms=((end - frames[-1][3]) * 1e3) if tap_t0 is not None and end else float("nan"),
                       refused=refused or "no")
            rows.append(row)
            log("reenter: timing " + " ".join(f"{k}={v:.1f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()))
    finally:
        globals()["classify"], gdi.grab = real_classify, real_gdi
    ages = sorted(r["age_ms"] for r in rows)
    if ages:
        log(f"reenter: timing age at the write p50 {ages[len(ages) // 2]:.0f} ms, max {ages[-1]:.0f} ms (limit {MAX_PROOF_AGE_S * 1e3:.0f} ms)")
    return rows


def main(argv=None, capture=_dxcam, live=Live):
    """`capture()` returns something with grab(); `live(cap, first_frame)` opens the pad. Both are injectable for tests."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="classify a frame and print what would be done; open no pad")
    p.add_argument("--frame", help="with --dry-run: a saved frame instead of a live capture")
    p.add_argument("--timing", type=int, metavar="N", help="with --dry-run: time N press-proofs on the live screen (capture only, no pad)")
    a = p.parse_args(argv)
    if a.frame is not None and not a.dry_run:           # `is not None`: an empty or zero value must never fall through to a live run
        p.error("--frame needs --dry-run")
    if a.timing is not None and (not a.dry_run or a.frame is not None or a.timing <= 0):
        p.error("--timing needs --dry-run, the live screen and N >= 1")
    if a.timing is not None:
        import logging
        logging.basicConfig(level=logging.WARNING, format="reenter: dxcam log %(message)s")   # dxcam reports access loss and recovery here
        from capture import Capture
        cap = capture()
        dxcam_probe(cap)
        timings(cap, Capture("gdi"), a.timing)
        return 0
    if a.frame is not None:
        first = cv2.imread(a.frame)
        if first is None:
            sys.exit(f"reenter: cannot read {a.frame}")
        cap = None
    else:
        cap = capture()
        first = _first_frame(cap)
    if a.dry_run:
        if first is None:
            sys.exit("reenter: no frame from the display")
        lines = describe(first)
        for line in lines:
            print("reenter:", line)
        return 1 if lines[0].endswith("unknown") else 0

    # a real run: the pad is opened only once the first frame is recognised
    if first is None or classify(first) == "unknown":
        why = "no frame from the display" if first is None else f"unknown screen (frame: {save(first, 'refuse')})"
        print(f"reenter: STOP: {why}; no pad opened, nothing sent")
        return 1
    io = live(cap, first)
    release = getattr(io, "release_all", None)
    if release:
        atexit.register(_release, io)       # one unconditional neutral on every exit of the process: a return, an exception, sys.exit
        try:
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # a kill is an exit too
        except (ValueError, OSError):       # not the main thread, or no such signal here
            pass
    trace = ArrivalLog()
    try:
        io.arrival_log = trace                                          # arrive() records its steps here; nothing else reads it
    except Exception:                                                   # noqa: BLE001 - an io that takes no attribute runs unrecorded
        pass
    try:
        run(io)
    except Refuse as r:
        print(f"reenter: STOP: {r.reason} (frame: {save(r.frame if r.frame is not None else _last(io), 'refuse')})")
        return 1
    finally:
        _release(io)
        if trace.n or trace.failed:
            print(f"reenter: {trace.summary()}")
    print("reenter: in the Practice Range as Spider-Man")
    return 0


if __name__ == "__main__":
    sys.exit(main())
