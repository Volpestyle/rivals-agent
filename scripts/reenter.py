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
- X, START and the d-pad are never sent on the lobby. X is sent only on hero select, on a fresh frame classified as
  hero select. RB only on hero select.
- An unrecognised screen: send nothing and stop. While waiting for a screen to load nothing is sent either.
- Cursor steering and every wait are bounded.
- On arrival: walk forward ~6 s and attack once (only moving or attacking resets the idle timer), confirm the range.

Everything that decides is a pure function of one frame (`look`, `on_practice_tab`, `on_practice_range_tile`,
`on_spiderman`), tested offline on tests/fixtures/reentry. Coordinates are 1280x720 px; any 16:9 frame is scaled.
"""
import argparse
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from record import in_range  # noqa: E402  (the range HUD test every input loop uses)

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
WALK_S, WALK_CHUNK_S = 6.0, 0.5
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


PRACTICE_TAB = Zone("PRACTICE tab", ((1168, 372), (1256, 372), (1256, 394), (1168, 394)), 5)
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


def find_cursor(frame):
    """(x, y) of the pad cursor in 1280x720 px, or None. None is also the answer for a faint ring over dark art."""
    s = small(frame)
    circles = cv2.HoughCircles(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY), cv2.HOUGH_GRADIENT, dp=1, minDist=20,
                               param1=40, param2=20, minRadius=16, maxRadius=32)
    if circles is None:
        return None
    white = s.min(axis=2)  # bright only where bright in every channel: the sprite, not coloured art
    best = max(((_ring_score(white, int(round(x)), int(round(y))), x, y) for x, y, _ in circles[0]), default=(0, 0, 0))
    return (float(round(best[1])), float(round(best[2]))) if best[0] > 0 else None


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


def on_spiderman(frame):
    """Duelists tab, cursor inside the top-left portrait slot, and that slot looks like Spider-Man (red)."""
    lk, bad = _need(frame, "hero_select")
    if bad:
        return bad
    tab = hero_tab(frame)
    if tab != "duelists":
        return Proof(False, f"the hero tab is {tab}, not duelists")
    if not SPIDER_SLOT.contains(lk.cursor):
        return Proof(False, f"cursor at ({lk.cursor[0]:.0f},{lk.cursor[1]:.0f}) is not on the Spider-Man portrait")
    red = _red_hue(_box(small(frame), "slot"))
    if red < SLOT_RED:
        return Proof(False, f"the portrait under the cursor is not Spider-Man (red share {red:.3f})")
    return Proof(True, f"cursor is on the Spider-Man portrait (red share {red:.3f})")


def hero_is_spiderman(frame):
    """The HUD hero portrait in the range is Spider-Man's (red)."""
    return _red_hue(_box(small(frame), "hud_hero")) >= HUD_RED


def describe(frame):
    """What a run would do from this frame, as printable lines. Pure: sends nothing."""
    lk = look(frame)
    cur = "not found" if lk.cursor is None else f"({lk.cursor[0]:.0f},{lk.cursor[1]:.0f})"
    out = [f"screen: {lk.screen}", f"cursor: {cur}"]
    if lk.screen == "unknown":
        return out + ["would send nothing and stop: unknown screen"]
    if lk.screen == "in_range":
        return out + ["would walk forward ~6 s, attack once, then check the HUD hero is Spider-Man"]
    steps = {"lobby": (PRACTICE_TAB, on_practice_tab, "A opens the PRACTICE panel"),
             "practice_panel": (RANGE_TILE, on_practice_range_tile, "A loads hero select (about 12 s)"),
             "hero_select": (SPIDER_SLOT, on_spiderman, "A selects the hero, then X confirms")}[lk.screen]
    zone, proof_fn, does = steps
    if lk.screen == "hero_select":
        tab = hero_tab(frame)
        out.append(f"hero tab: {tab}")
        n = RB_PRESSES.get(tab)
        out.append("would stop: the tab is not recognised" if n is None else
                   f"would press RB {n}x to reach duelists" if n else "already on duelists")
    if lk.cursor is None:
        out.append(f"would jiggle the stick to find the cursor (at most {MAX_MISSES} tries), then stop")
        return out
    inside = zone.contains(lk.cursor)
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


class Live:
    """dxcam + one virtual pad held open for the whole run. Built only when input is about to be sent."""

    def __init__(self, cap, first_frame, sleep=time.sleep, settle_s=3.0):
        import vgamepad as vg
        self.sleep, self.vg, self.cap, self.last = sleep, vg, cap, first_frame
        self.pad = vg.VX360Gamepad()
        self.sleep(settle_s)  # Windows and the game enumerate the pad, and show their banner

    def now(self):
        return time.perf_counter()

    def frame(self, timeout=0.5):
        end = self.now() + timeout
        while True:
            f = self.cap.grab()
            if f is not None:
                self.last = f
                return f
            if self.now() > end:
                return self.last  # a static screen delivers no new frame: the last one is still the truth
            self.sleep(0.005)

    def stick(self, x, y, secs):
        self.pad.left_joystick_float(x, y)
        self.pad.update()
        self.sleep(secs)
        self.pad.left_joystick_float(0.0, 0.0)
        self.pad.update()
        self.sleep(0.25)

    def tap(self, button):
        b = self.vg.XUSB_BUTTON
        codes = {"A": b.XUSB_GAMEPAD_A, "X": b.XUSB_GAMEPAD_X, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER}
        if button == "RT":
            self.pad.right_trigger_float(1.0)
            self.pad.update()
            self.sleep(0.15)
            self.pad.right_trigger_float(0.0)
        else:
            self.pad.press_button(button=codes[button])
            self.pad.update()
            self.sleep(0.12)
            self.pad.release_button(button=codes[button])
        self.pad.update()
        self.sleep(0.5)


class Safe:
    """Everything the flow sends goes through here: the screen must allow the button, and A needs a proof."""

    def __init__(self, io, log=print):
        self.io, self.log = io, log

    def frame(self):
        return self.io.frame()

    def stick(self, x, y, secs):
        self.io.stick(x, y, secs)

    def press(self, button, proof_fn=None):
        f = self.io.frame()  # fresh, and re-checked right before the press
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
        self.io.tap(button)


def steer(io, zone, locate=find_cursor):
    """Nudge the cursor into `zone`, one axis at a time (l4_menu's step law). Bounded: at most MAX_STEPS nudges.

    An axis whose direction reverses has overshot, so the real cursor is faster than SPEED: its steps are halved.
    """
    misses, last, scale = 0, {}, {"x": 1.0, "y": 1.0}
    for _ in range(MAX_STEPS):
        f = io.frame()
        pos = locate(f)
        if pos is None:  # hidden until the stick moves, or lost over busy art: wiggle onto plainer ground
            misses += 1
            if misses > MAX_MISSES:
                raise Refuse("the cursor ring was not found", f)
            io.stick(-1.0 if misses % 2 else 0.0, 0.0 if misses % 2 else 1.0, 0.12)
            continue
        if zone.contains(pos):
            return pos
        dx, dy = zone.aim[0] - pos[0], zone.aim[1] - pos[1]
        axis, d, sign = ("x", abs(dx), math.copysign(1.0, dx)) if abs(dx) > 9 else ("y", abs(dy), math.copysign(1.0, dy))
        if last.get(axis, sign) != sign:
            scale[axis] *= 0.5
        last[axis] = sign
        secs = min(0.5, DEADBAND_S + scale[axis] * d / SPEED)
        io.stick(sign if axis == "x" else 0.0, -sign if axis == "y" else 0.0, secs)  # stick up = screen up
    raise Refuse(f"the cursor did not reach the {zone.name} in {MAX_STEPS} nudges", io.frame())


def wait_for(io, screens, timeout, poll=0.3):
    """Send nothing until the frame classifies as one of `screens`; Refuse after `timeout` seconds."""
    end, f = io.now() + timeout, None
    while io.now() < end:
        f = io.frame()
        if classify(f) in screens:
            return f
        io.sleep(poll)
    raise Refuse(f"did not reach {' or '.join(sorted(screens))} within {timeout:.0f} s", f)


def arrive(io, safe):
    """In the range: walk forward, attack once, and confirm. Input stops the moment the HUD is gone."""
    def hud():
        f = io.frame()
        if not in_range(small(f)):
            raise Refuse("the range HUD is gone", f)
        return f

    hud()
    walked = 0.0
    while walked < WALK_S:
        hud()
        io.stick(0.0, 1.0, WALK_CHUNK_S)
        walked += WALK_CHUNK_S + 0.25
    hud()
    safe.press("RT")
    f = hud()
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
            steer(io, PRACTICE_TAB)
            safe.press("A", on_practice_tab)
            wait_for(io, {"practice_panel"}, 10)
        elif screen == "practice_panel":
            steer(io, RANGE_TILE)
            safe.press("A", on_practice_range_tile)
            wait_for(io, {"hero_select", "in_range"}, 40)  # loading screens between are unknown: nothing is sent
        elif screen == "hero_select":
            n = RB_PRESSES.get(hero_tab(f))
            if n is None:
                raise Refuse(f"hero tab {hero_tab(f)} is not recognised", f)
            for _ in range(n):
                safe.press("RB")
            f = io.frame()
            if hero_tab(f) != "duelists":
                raise Refuse(f"the hero tab is {hero_tab(f)} after RB, not duelists", f)
            steer(io, SPIDER_SLOT)
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
    end, f = time.perf_counter() + timeout, None
    while f is None and time.perf_counter() < end:
        f = cap.grab()
    return f


def main(argv=None, capture=_dxcam, live=Live):
    """`capture()` returns something with grab(); `live(cap, first_frame)` opens the pad. Both are injectable for tests."""
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="classify a frame and print what would be done; open no pad")
    p.add_argument("--frame", help="with --dry-run: a saved frame instead of a live capture")
    a = p.parse_args(argv)
    if a.frame and not a.dry_run:
        p.error("--frame needs --dry-run")
    if a.frame:
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
    try:
        run(io)
    except Refuse as r:
        print(f"reenter: STOP: {r.reason} (frame: {save(r.frame if r.frame is not None else io.frame(), 'refuse')})")
        return 1
    print("reenter: in the Practice Range as Spider-Man")
    return 0


if __name__ == "__main__":
    sys.exit(main())
