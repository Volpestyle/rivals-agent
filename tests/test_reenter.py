"""scripts/reenter.py against the fixtures in tests/fixtures/reentry, a simulated cursor, a simulated game and a fake pad.

Needs opencv and numpy (`uv run --group perception pytest tests/test_reenter.py`). No game, no pad, no display.
"""
import json
import math
import random
import re
import sys
import types
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import reenter as R  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "reentry"


@lru_cache(maxsize=None)
def frame(name):
    f = cv2.imread(str(FIX / f"{name}.jpg"))
    assert f is not None and f.shape[:2] in ((1440, 2560), (720, 1280)), name
    f.setflags(write=False)
    return f


def edited(name, paint):
    """A writable copy of a fixture with `paint(frame)` applied: the synthetic negatives."""
    f = frame(name).copy()
    paint(f)
    return f


def fill(f, box, bgr):  # box in 1280x720 px, whatever the frame's size
    k = f.shape[1] // 1280
    x0, y0, x1, y1 = (v * k for v in box)
    f[y0:y1, x0:x1] = bgr


def spawn_frame(door_x=None, width=80):
    """The recorded spawn room with the door painted out and a tall green door painted at `door_x` (fraction of the width; by default on
    the hero's column, R.HERO_X: straight ahead of him)."""
    door_x = R.HERO_X if door_x is None else door_x
    lime = cv2.cvtColor(np.uint8([[[46, 140, 150]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()      # the door glass: hue ~46, S ~110-140, V ~125-150

    def paint(f):
        f[100:600, :1200] = (60, 50, 55)   # rows above 100 hold the "PRACTICE RANGE" banner that record.in_range proves the range by
        x = int(door_x * 2560)
        f[240:840, max(0, x - width // 2):x + width // 2] = lime
    return edited("arrival-spawn-room", paint)


BLACK = np.zeros((1440, 2560, 3), np.uint8)
NOISE = np.random.default_rng(0).integers(0, 255, (1440, 2560, 3), dtype=np.uint8)

POSES = ("arrival-spawn-door-ahead", "arrival-spawn-wall-left-of-door", "arrival-spawn-console-two-doors", "arrival-spawn-room")

SCREENS = {
    "lobby-cursor-far": "lobby", "lobby-cursor-left-of-practice": "lobby", "lobby-cursor-on-practice": "lobby",
    "lobby-cursor-on-try-competitive": "lobby", "lobby-cursor-at-try-competitive-corner": "lobby",
    "heroselect-all-tab-fading-in": "hero_select", "heroselect-all-tab-settled": "hero_select",
    "lobby-cursor-below-practice-tab": "lobby", "lobby-cursor-on-practice-tab-lower-half": "lobby",
    "panel-cursor-on-practice-range": "practice_panel", "panel-cursor-off-tiles": "practice_panel",
    "heroselect-all-tab-black-panther": "hero_select", "heroselect-duelists-cursor-off": "hero_select",
    "heroselect-cursor-on-spiderman": "hero_select", "heroselect-spiderman-tooltip-ring-lost": "hero_select",
    "heroselect-spiderman-tooltip-between-pixels": "hero_select",
    "in-range": "in_range", "arrival-spawn-room": "in_range", "arrival-plaza-bot-ahead": "in_range",
    "arrival-spawn-door-ahead": "in_range", "arrival-spawn-wall-left-of-door": "in_range", "arrival-spawn-console-two-doors": "in_range",
}


# --- the classifier ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,screen", SCREENS.items())
def test_every_fixture_is_classified(name, screen):
    assert R.classify(frame(name)) == screen


def test_classification_does_not_depend_on_the_frame_size():
    for name, screen in SCREENS.items():
        assert R.classify(cv2.resize(frame(name), (1280, 720), interpolation=cv2.INTER_AREA)) == screen
        assert R.classify(cv2.resize(frame(name), (1920, 1080), interpolation=cv2.INTER_AREA)) == screen


def test_anything_else_is_unknown():
    assert R.classify(BLACK) == "unknown" and R.classify(NOISE) == "unknown"  # a black loading screen is not the panel
    dimmed = edited("panel-cursor-on-practice-range", lambda f: fill(f, R.BOX["panel_title"], (20, 20, 20)))
    assert R.classify(dimmed) == "unknown"  # a dark band without the PRACTICE title
    assert R.classify(edited("in-range", lambda f: fill(f, (500, 660, 780, 690), (0, 0, 0)))) == "unknown"  # no HUD bar
    assert R.classify(edited("lobby-cursor-far", lambda f: fill(f, R.BOX["start"], (60, 20, 20)))) == "unknown"  # no START


def test_the_active_hero_tab():
    assert R.hero_tab(frame("heroselect-all-tab-black-panther")) == "all"
    assert R.hero_tab(frame("heroselect-duelists-cursor-off")) == "duelists"
    assert R.hero_tab(frame("heroselect-cursor-on-spiderman")) == "duelists"
    assert R.hero_tab(frame("lobby-cursor-far")) is None


# --- the cursor finder --------------------------------------------------------------------------------------------------
CURSORS = {  # read off the screenshots; the hover ring (with its centre dot) and the plain ring are both covered
    "lobby-cursor-far": (640, 256), "lobby-cursor-left-of-practice": (1146, 380), "lobby-cursor-on-practice": (1214, 380),
    "panel-cursor-on-practice-range": (780, 380), "heroselect-duelists-cursor-off": (780, 86),
    "heroselect-cursor-on-spiderman": (852, 48),
    "lobby-cursor-on-try-competitive": (1127, 414), "lobby-cursor-at-try-competitive-corner": (1242, 408),
    "lobby-cursor-below-practice-tab": (1210, 394),
    "lobby-cursor-on-practice-tab-lower-half": (1220, 390),  # the live refuse frame, 2026-09-20 18:47
    "heroselect-spiderman-tooltip-ring-lost": (860, 44),     # the live refuse frame, 2026-09-20 19:28: the ring over a busy portrait
}


@pytest.mark.parametrize("name,xy", CURSORS.items())
def test_the_cursor_is_found_where_it_is(name, xy):
    x, y = R.find_cursor(frame(name))
    assert abs(x - xy[0]) <= 4 and abs(y - xy[1]) <= 4


def test_no_cursor_is_invented_and_a_faint_one_is_not_guessed():
    assert R.find_cursor(frame("in-range")) is None  # l4_menu.find_cursor reports one here
    assert R.find_cursor(BLACK) is None and R.find_cursor(NOISE) is None
    assert R.find_cursor(frame("heroselect-all-tab-black-panther")) is None  # a faint halo over dark art: no press
    assert R.find_cursor(frame("panel-cursor-off-tiles")) is None  # the same over the dimmed panel: found nowhere


# --- the proofs that stand in front of every A ------------------------------------------------------------------------
def test_a_lobby_press_needs_the_cursor_on_the_practice_tab():
    ok = R.on_practice_tab(frame("lobby-cursor-on-practice"))
    assert ok.ok, ok.reason
    left = R.on_practice_tab(frame("lobby-cursor-left-of-practice"))
    assert not left.ok and "not inside the PRACTICE tab" in left.reason  # on TIMES SQUARE
    far = R.on_practice_tab(frame("lobby-cursor-far"))
    assert not far.ok and "not inside the PRACTICE tab" in far.reason
    for name in ("panel-cursor-on-practice-range", "heroselect-cursor-on-spiderman", "in-range"):
        assert not R.on_practice_tab(frame(name)).ok  # right cursor, wrong screen


def test_the_live_refuse_frame_is_a_cursor_on_the_tab_and_now_proves_it():
    """VUH-1299 live trial: 'the cursor did not reach the PRACTICE tab in 30 nudges'. The ring was found (1220,390), on the tab's
    lower half, and the old rectangle (rows 372-394, 5 px margin) accepted only y 377-389."""
    f = frame("lobby-cursor-on-practice-tab-lower-half")
    assert R.find_cursor(f) == pytest.approx((1220, 390), abs=1.5)
    old = R.Zone("old", ((1168, 372), (1256, 372), (1256, 394), (1168, 394)), 5)
    assert not old.contains((1220, 390)) and R.PRACTICE_TAB.contains((1220, 390))
    p = R.on_practice_tab(f)
    assert p.ok, p.reason
    assert "cursor at (1220" in R.describe(f)[-2] or "OK" in R.describe(f)[-2]


def test_the_tab_zone_is_the_drawn_tab_and_still_refuses_its_lower_edge_and_the_banner():
    z = R.PRACTICE_TAB
    assert z.contains((1214, 380)) and z.contains((1220, 390)) and z.contains((1214, 392))
    assert not z.contains((1210, 394)) and not z.contains((1214, 376)) and not z.contains((1146, 380)) and not z.contains((1214, 406))


def test_a_highlighted_try_competitive_blocks_the_lobby_press():
    for colour in ((40, 220, 240), (255, 255, 255), (0, 0, 0)):  # a yellow glow, a white flash, a black-out
        f = edited("lobby-cursor-on-practice", lambda f, c=colour: fill(f, R.BOX["try_comp"], c))
        p = R.on_practice_tab(f)
        assert not p.ok and "TRY COMPETITIVE" in p.reason, colour


# --- states that were once only painted: now real frames (the lead's manual navigations, 2026-09-20) -----------------------
HIGHLIGHTED = ("lobby-cursor-on-try-competitive", "lobby-cursor-at-try-competitive-corner")


def test_try_competitive_lights_up_when_hovered_and_the_banner_check_sees_it():
    idle = R._box(R.small(frame("lobby-cursor-on-practice")), "try_comp")
    assert float((idle.max(axis=2) < 75).mean()) == pytest.approx(R.TRY_COMP_DARK, abs=0.02)
    for name in HIGHLIGHTED:
        b = R._box(R.small(frame(name)), "try_comp")
        assert float((b.max(axis=2) < 75).mean()) < 0.1 and R._lum(b) > 105, name  # idle: dark share 0.75, luminance 78.6


def test_a_highlighted_try_competitive_refuses_the_lobby_press(monkeypatch):
    for name in HIGHLIGHTED:
        f = frame(name)
        assert R.classify(f) == "lobby"
        p = R.on_practice_tab(f)
        assert not p.ok and "not inside the PRACTICE tab" in p.reason, name  # the cursor is on the banner, not the tab
        with monkeypatch.context() as m:  # and the banner check alone would refuse it, cursor on the tab or not
            m.setattr(R, "find_cursor", lambda fr: (1214.0, 380.0))
            p = R.on_practice_tab(f)
        assert not p.ok and "TRY COMPETITIVE does not look idle" in p.reason, name


def test_a_cursor_on_the_lower_edge_of_the_practice_tab_does_not_press(monkeypatch):
    f = frame("lobby-cursor-below-practice-tab")  # centre at y 394, the tab's bottom edge, ring overlapping the banner
    p = R.on_practice_tab(f)
    assert not p.ok and "not inside the PRACTICE tab" in p.reason
    with monkeypatch.context() as m:  # the banner is idle here, so it is only the cursor position that refuses
        m.setattr(R, "find_cursor", lambda fr: (1214.0, 380.0))
        assert R.on_practice_tab(f).ok


def test_an_unhovered_practice_range_tile_refuses(monkeypatch):
    f = frame("panel-cursor-off-tiles")  # both tiles bright: nothing hovered
    assert R.classify(f) == "practice_panel"
    hovered, idle = frame("panel-cursor-on-practice-range"), f
    assert R._lum(R._box(R.small(hovered), "range_tile")) < 60 < 200 < R._lum(R._box(R.small(idle), "range_tile"))
    p = R.on_practice_range_tile(f)
    assert not p.ok and "cursor ring was not found" in p.reason
    with monkeypatch.context() as m:  # with the cursor where the tile is, it is the tile's look that refuses
        m.setattr(R, "find_cursor", lambda fr: (760.0, 400.0))
        p = R.on_practice_range_tile(f)
    assert not p.ok and "not highlighted" in p.reason


def test_a_hovered_doom_match_refuses(monkeypatch):
    """No real frame has the cursor on DOOM MATCH. The cursor position refuses it; and with DOOM MATCH hovered the PRACTICE
    RANGE tile is un-hovered, which the real un-hovered panel shows is bright, so the tile check refuses it either way."""
    f = frame("panel-cursor-off-tiles")
    with monkeypatch.context() as m:
        m.setattr(R, "find_cursor", lambda fr: (560.0, 400.0))
        p = R.on_practice_range_tile(f)
        assert not p.ok and "DOOM MATCH" in p.reason
        dark = edited("panel-cursor-off-tiles", lambda g: fill(g, R.BOX["doom"], (30, 30, 30)))  # painted: as if hovered
        assert not R.on_practice_range_tile(dark).ok
    with monkeypatch.context() as m:  # DOOM MATCH dark, the cursor claimed on the range tile: the tile is still bright
        m.setattr(R, "find_cursor", lambda fr: (760.0, 400.0))
        assert not R.on_practice_range_tile(dark).ok


def test_a_panel_press_needs_the_practice_range_tile_and_not_doom_match(monkeypatch):
    ok = R.on_practice_range_tile(frame("panel-cursor-on-practice-range"))
    assert ok.ok, ok.reason
    panel = frame("panel-cursor-on-practice-range")
    monkeypatch.setattr(R, "find_cursor", lambda f: (560.0, 400.0))  # the cursor on the DOOM MATCH tile
    p = R.on_practice_range_tile(panel)
    assert not p.ok and "DOOM MATCH" in p.reason
    monkeypatch.setattr(R, "find_cursor", lambda f: (300.0, 200.0))  # off both tiles
    assert not R.on_practice_range_tile(panel).ok
    assert not R.on_practice_range_tile(frame("lobby-cursor-on-practice")).ok


def test_a_panel_press_needs_the_range_tile_to_be_the_hovered_one():
    for paint in (lambda f: fill(f, R.BOX["range_tile"], (250, 250, 250)),  # the range tile not darkened
                  lambda f: fill(f, R.BOX["doom"], (30, 30, 30))):  # DOOM MATCH darkened, as if hovered
        p = R.on_practice_range_tile(edited("panel-cursor-on-practice-range", paint))
        assert not p.ok and ("not highlighted" in p.reason or "DOOM MATCH looks highlighted" in p.reason)


def test_a_hero_press_needs_spiderman_under_the_cursor_on_the_duelists_tab(monkeypatch):
    ok = R.on_spiderman(frame("heroselect-cursor-on-spiderman"))
    assert ok.ok, ok.reason
    off = R.on_spiderman(frame("heroselect-duelists-cursor-off"))  # the cursor is on the Punisher, and his tooltip says so
    assert not off.ok and "does not name SPIDER-MAN" in off.reason
    with monkeypatch.context() as m:  # without the tooltip the ring's position refuses it on its own
        m.setattr(R, "tooltip_up", lambda f: False)
        off = R.on_spiderman(frame("heroselect-duelists-cursor-off"))
    assert not off.ok and "not on the Spider-Man portrait" in off.reason
    black_panther = R.on_spiderman(frame("heroselect-all-tab-black-panther"))
    assert not black_panther.ok  # the all tab, and no cursor found
    monkeypatch.setattr(R, "find_cursor", lambda f: (852.0, 48.0))
    wrong_tab = R.on_spiderman(frame("heroselect-all-tab-black-panther"))
    assert not wrong_tab.ok and "not duelists" in wrong_tab.reason  # the right spot on the wrong tab
    def another_hero_in_the_slot(f):
        fill(f, (812, 12, 896, 74), (60, 60, 60))       # not his portrait
        fill(f, (850, 60, 1075, 100), (40, 30, 30))     # and no tooltip (its name would not say SPIDER-MAN)
    other_hero = R.on_spiderman(edited("heroselect-cursor-on-spiderman", another_hero_in_the_slot))
    assert not other_hero.ok and "not Spider-Man" in other_hero.reason  # the right spot, but not his portrait


# --- hero select, second live refusal (2026-09-20 19:28): the ring was "not found" with the cursor ON Spider-Man ---------------------
LOST = "heroselect-spiderman-tooltip-ring-lost"


def test_the_ring_is_found_on_a_busy_portrait_and_through_noise_and_compression():
    """The live frame: a white ring over a red-and-blue portrait, Iron Fist previewed. The first finder took Hough circles and missed it
    when the frame was a little noisy; the candidates are now ring matches, refined to the pixel."""
    f = frame(LOST)
    rng = np.random.default_rng(0)
    for sigma in (0, 3, 8, 12):
        for _ in range(6):
            g = np.clip(f.astype(float) + rng.normal(0, sigma, f.shape), 0, 255).astype(np.uint8) if sigma else f
            x, y = R.find_cursor(g)
            assert abs(x - 860) <= 3 and abs(y - 44) <= 3, (sigma, x, y)
    for q in (80, 50):
        _, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, q])
        x, y = R.find_cursor(cv2.imdecode(buf, 1))
        assert abs(x - 860) <= 3 and abs(y - 44) <= 3, q


def test_the_tooltip_names_the_hero_under_the_cursor_and_is_a_proof_of_its_own(monkeypatch):
    f = frame(LOST)
    assert R.classify(f) == "hero_select" and R.hero_tab(f) == "duelists"
    assert R.tooltip_spiderman(f) > 0.85 and R.tooltip_up(f)                    # "Request to Team-Up with SPIDER-MAN"
    p = R.on_spiderman(f)
    assert p.ok and "tooltip names SPIDER-MAN" in p.reason
    monkeypatch.setattr(R, "find_cursor", lambda fr: None)                       # no ring: the tooltip may be lingering where the cursor was
    p = R.on_spiderman(f)
    assert not p.ok and "cursor ring was not found" in p.reason


def test_the_ring_proof_still_stands_without_a_tooltip_and_a_tooltip_for_another_hero_refuses():
    no_tip = edited(LOST, lambda g: fill(g, (850, 60, 1075, 100), (40, 30, 30)))
    assert R.tooltip_up(no_tip) is False
    p = R.on_spiderman(no_tip)
    assert p.ok and "portrait" in p.reason                                       # ring inside the slot, and the slot is red
    other = edited(LOST, lambda g: fill(g, (996, 72, 1058, 90), (30, 20, 20)))    # the box is up, but its name is not SPIDER-MAN's
    assert R.tooltip_up(other) and R.tooltip_spiderman(other) < R.TOOLTIP_MATCH
    p = R.on_spiderman(other)
    assert not p.ok and "a tooltip is up and does not name SPIDER-MAN" in p.reason  # ring and colours say yes; the game says no


def test_the_tooltip_match_separates_spiderman_from_every_other_frame():
    scores = {n: R.tooltip_spiderman(frame(n)) for n in SCREENS}
    positives = {n for n, v in scores.items() if v >= R.TOOLTIP_MATCH}
    assert positives == {"heroselect-cursor-on-spiderman", LOST, BETWEEN}, scores
    assert max(v for n, v in scores.items() if n not in positives) < 0.6, scores    # a wide gap: 0.49 at most, 0.92 at least
    assert R.tooltip_spiderman(BLACK) < 0.3 and R.tooltip_spiderman(NOISE) < 0.3
    assert R.tooltip_spiderman(frame("heroselect-duelists-cursor-off")) < 0.4       # THE PUNISHER's tooltip: similar font, another name
    rng = np.random.default_rng(1)
    for _ in range(4):                                                               # and it survives noise
        g = np.clip(frame(LOST).astype(float) + rng.normal(0, 6, frame(LOST).shape), 0, 255).astype(np.uint8)
        assert R.tooltip_spiderman(g) > 0.75


BETWEEN = "heroselect-spiderman-tooltip-between-pixels"


def test_a_tooltip_landing_between_pixels_still_names_spiderman():
    """Live refusal 2026-09-21 10:37: the tooltip beside the ring read SPIDER-MAN (140 x 28 px from the ring, where it belongs), but its
    name fell half a pixel off the template's grid and one sharp match read 0.73, under TOOLTIP_MATCH: "a tooltip is up and does not
    name SPIDER-MAN". The proof was there; the refusal was the matcher's."""
    f = frame(BETWEEN)
    assert R.tooltip_spiderman(f) > 0.85
    p = R.on_spiderman(f)
    assert p.ok and "tooltip names SPIDER-MAN" in p.reason
    other = edited(BETWEEN, lambda g: fill(g, (996, 62, 1058, 80), (30, 20, 20)))  # the same box, its name blacked out: still a refusal
    assert R.tooltip_up(other) and not R.on_spiderman(other).ok


def test_steering_needs_no_ring_when_the_tooltip_already_says_the_cursor_is_on_spiderman():
    sim = SimCursor(640, 256)                                                        # a cursor whose ring is never found
    pos = R.steer(sim, R.SPIDER_SLOT, "hero_select", locate=lambda f: None, done=lambda f: True)
    assert pos is None and sim.sticks == 0                                           # nothing was sent: no jiggle, no nudge


def test_a_run_on_hero_select_never_presses_on_the_tooltip_alone(monkeypatch):
    """VUH-1325 (plausible item): a tooltip names SPIDER-MAN but no ring is found, so nothing says the cursor is still there. No A, no X."""
    monkeypatch.setattr(R, "find_cursor", lambda fr: None)
    sim = Sim("hero_lost", {("hero_lost", "X"): "loading_range", ("loading_range", "loaded"): "range"}, {"loading_range": 2})
    with pytest.raises(R.Refuse, match="cursor ring was not found"):
        R.run(sim)
    assert sim.taps() == []


def test_a_run_on_hero_select_presses_when_the_ring_and_the_tooltip_agree():
    sim = Sim("hero_lost", {("hero_lost", "X"): "loading_range", ("loading_range", "loaded"): "range"}, {"loading_range": 2})
    R.run(sim)
    assert [(b, s_) for b, s_, _ in sim.taps()] == [("A", "hero_select"), ("X", "hero_select"), ("RT", "in_range")]
    assert [i for i in sim.inputs if i[0] == "stick"] == []                      # nothing was steered: ring and tooltip said it was there


def test_the_hero_select_dry_run_reports_the_tooltip(capsys):
    assert R.main(["--dry-run", "--frame", str(FIX / f"{LOST}.jpg")]) == 0
    out = capsys.readouterr().out
    assert "hover tooltip names SPIDER-MAN: yes" in out and "proof for A right now: OK" in out


@pytest.mark.parametrize("name", [n for n, scr in SCREENS.items() if scr != "hero_select"])
def test_no_hero_press_is_proven_on_any_other_screen(name):
    p = R.on_spiderman(frame(name))
    assert not p.ok and "not hero_select" in p.reason, (name, p.reason)


def test_the_hud_hero_check():
    assert R.hero_is_spiderman(frame("in-range"))
    assert not R.hero_is_spiderman(edited("in-range", lambda f: fill(f, R.BOX["hud_hero"], (90, 90, 90))))


# --- steering: closed loop, bounded ------------------------------------------------------------------------------------
class SimCursor:
    """A cursor that obeys the measured step law (about 700 px/s at full stick, 35 ms dead time), with noise."""

    def __init__(self, x, y, rng=None, gain=1.0, frozen=False, hidden=0):
        self.x, self.y, self.rng, self.gain, self.frozen, self.hidden = x, y, rng or random.Random(0), gain, frozen, hidden
        self.sticks = 0

    def frame(self):
        return None

    def locate(self, _):
        if self.hidden > 0:
            return None
        return (self.x, self.y)

    def stick(self, x, y, secs, screen=None):
        self.sticks += 1
        if self.hidden > 0 and (x or y):
            self.hidden -= 1
        if self.frozen:
            return
        move = max(0.0, secs - R.DEADBAND_S) * R.SPEED * self.gain * self.rng.uniform(0.85, 1.15)
        self.x = min(1279, max(0, self.x + x * move))
        self.y = min(719, max(0, self.y - y * move))  # stick up = screen up


class PhysCursor:
    """A cursor whose short taps behave differently. dead: 35 ms of nothing, then 700 px/s (l4_menu's law). floor: the shortest tap
    already moves it 700 * secs, no dead time (a 24 px minimum step). ramp: it accelerates, so short taps move less than linear."""

    def __init__(self, x, y, rng, physics="dead", gain=1.0, noise=0.15):
        self.x, self.y, self.rng, self.physics, self.gain, self.noise, self.sticks = x, y, rng, physics, gain, noise, 0

    def locate(self, _):
        return (self.x, self.y)

    def frame(self):
        return None

    def stick(self, x, y, secs, screen=None):
        self.sticks += 1
        move = {"dead": max(0.0, secs - R.DEADBAND_S) * 700, "floor": secs * 700,
                "ramp": 700 * secs * (1 - math.exp(-secs / 0.06))}[self.physics]
        move *= self.gain * self.rng.uniform(1 - self.noise, 1 + self.noise)
        self.x, self.y = min(1279, max(0, self.x + x * move)), min(719, max(0, self.y - y * move))


@pytest.mark.parametrize("physics", ["dead", "floor", "ramp"])
@pytest.mark.parametrize("gain", [0.5, 1.0, 1.5, 2.5])
def test_steering_settles_into_the_18_px_tab_whatever_the_shortest_tap_does(physics, gain):
    """The live failure: a floor cursor cannot settle into an 18 px tab with a fixed step law, it alternates either side of it."""
    for seed in range(30):
        rng = random.Random(seed)
        sim = PhysCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, physics, gain)
        pos = R.steer(sim, R.PRACTICE_TAB, "lobby", locate=sim.locate)
        assert R.PRACTICE_TAB.contains(pos) and sim.sticks < R.MAX_STEPS, (physics, gain, seed, sim.sticks)


def _old_steer(io, zone, locate):
    """The law before the fix (fixed 0.035 s + d / 700, halved on a reversal): kept to show what the floor cursor did to it."""
    last, scale = {}, {"x": 1.0, "y": 1.0}
    for _ in range(R.MAX_STEPS):
        pos = locate(None)
        if zone.contains(pos):
            return pos
        dx, dy = zone.aim[0] - pos[0], zone.aim[1] - pos[1]
        axis, d, sign = ("x", abs(dx), math.copysign(1.0, dx)) if abs(dx) > 9 else ("y", abs(dy), math.copysign(1.0, dy))
        if last.get(axis, sign) != sign:
            scale[axis] *= 0.5
        last[axis] = sign
        io.stick(sign if axis == "x" else 0.0, -sign if axis == "y" else 0.0, min(0.5, R.DEADBAND_S + scale[axis] * d / R.SPEED))
    raise R.Refuse(f"the cursor did not reach the {zone.name} in {R.MAX_STEPS} nudges")


def test_the_old_step_law_alternated_around_the_tab_on_a_fast_floor_cursor():
    """Reproduces the class of failure in simulation: a cursor whose shortest tap already moves it (a floor) and is 1.5x faster than
    assumed. Nearly half the seeds never settled with the old law; none fail with the new one (the physics test above). The live
    trial failed every nudge, which no simulation here reproduces: the zone that rejected the live frame is pinned separately."""
    failed = 0
    for seed in range(60):
        rng = random.Random(seed)
        sim = PhysCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, "floor", 1.5)
        try:
            _old_steer(sim, R.PRACTICE_TAB, sim.locate)
        except R.Refuse:
            failed += 1
    assert failed >= 15, failed


def test_reach_learns_a_floor_and_a_dead_time_from_the_taps_it_sees():
    r = R.Reach()
    assert r.least() == pytest.approx(0.0, abs=1e-6)                       # the prior: dead time, so the shortest tap moves nothing
    for secs in (0.035, 0.05, 0.1, 0.2, 0.4):
        r.learn(secs, 700 * secs)                                          # a floor cursor
    assert r.least() == pytest.approx(24.5, abs=3) and r.secs(70) == pytest.approx(0.1, abs=0.012)
    dead = R.Reach()
    for secs in (0.05, 0.1, 0.2, 0.4):
        dead.learn(secs, 700 * (secs - 0.035))
    assert dead.least() < 3 and dead.secs(70) == pytest.approx(0.135, abs=0.012)


def test_steering_backs_off_instead_of_dithering_when_the_error_is_below_the_shortest_tap():
    """A floor cursor 7 px from the aim: the old law overshoots by ~17 px each way forever; now it steps away, then returns."""
    rng = random.Random(3)
    sim = PhysCursor(1214.0, 386.0 + 30, rng, "floor", 1.0, noise=0.05)
    positions = []
    orig = sim.stick
    sim.stick = lambda x, y, secs, screen=None: (orig(x, y, secs), positions.append(sim.y))
    assert R.PRACTICE_TAB.contains(R.steer(sim, R.PRACTICE_TAB, "lobby", locate=sim.locate))
    assert sim.sticks <= 6, positions


ZONE_SCREEN = {R.PRACTICE_TAB.name: "lobby", R.RANGE_TILE.name: "practice_panel", R.SPIDER_SLOT.name: "hero_select"}


@pytest.mark.parametrize("zone", [R.PRACTICE_TAB, R.RANGE_TILE, R.SPIDER_SLOT], ids=lambda z: z.name)
def test_steering_reaches_the_zone_from_anywhere_in_a_few_nudges(zone):
    for seed in range(12):
        rng = random.Random(seed)
        sim = SimCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, gain=rng.uniform(0.8, 1.2))
        pos = R.steer(sim, zone, ZONE_SCREEN[zone.name], locate=sim.locate)
        assert zone.contains(pos) and sim.sticks <= 16, (seed, sim.sticks)


def test_steering_corrects_y_when_x_is_already_on_target():
    """Regression: with x aligned and y a few px outside the zone, the loop once nudged x by nothing, forever."""
    for y in (391.4, 375.2, 389.9):
        sim = SimCursor(1212, y, gain=1.0)
        assert R.PRACTICE_TAB.contains(R.steer(sim, R.PRACTICE_TAB, "lobby", locate=sim.locate))


@pytest.mark.parametrize("gain", [0.4, 0.6, 2.0, 2.5])
def test_steering_survives_a_cursor_much_faster_or_slower_than_assumed(gain):
    """The measured speed is rough (about 1.1x the assumed one): overshoot halves an axis' steps, slowness just takes more."""
    for seed in range(10):
        rng = random.Random(seed)
        sim = SimCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, gain=gain)
        zone = (R.PRACTICE_TAB, R.RANGE_TILE, R.SPIDER_SLOT)[seed % 3]
        assert zone.contains(R.steer(sim, zone, ZONE_SCREEN[zone.name], locate=sim.locate))


def test_steering_is_bounded_when_the_cursor_never_moves():
    sim = SimCursor(640, 256, frozen=True)
    with pytest.raises(R.Refuse, match="did not reach the PRACTICE tab"):
        R.steer(sim, R.PRACTICE_TAB, "lobby", locate=sim.locate)
    assert sim.sticks == R.MAX_STEPS


def test_steering_wiggles_to_find_a_hidden_cursor_then_gives_up():
    sim = SimCursor(1210, 383, hidden=2)  # hidden until the stick has moved twice (the wiggles move it too)
    pos = R.steer(sim, R.PRACTICE_TAB, "lobby", locate=sim.locate)
    assert R.PRACTICE_TAB.contains(pos) and sim.sticks >= 3
    lost = SimCursor(640, 256, hidden=10**6)
    with pytest.raises(R.Refuse, match="cursor ring was not found"):
        R.steer(lost, R.PRACTICE_TAB, "lobby", locate=lost.locate)
    assert lost.sticks == R.MAX_MISSES  # one wiggle per miss, and the last miss stops without another


# --- the whole flow against a simulated game --------------------------------------------------------------------------
class Sim:
    """A game and pad in one: serves fixture frames, and each input may move it to another state. Records every input
    with the screen and cursor a fresh frame showed at that moment."""

    def __init__(self, start, table, loading=None):
        self.state, self.table, self.t, self.inputs, self.n = start, table, 0.0, [], {}
        self.loading = dict(loading or {})  # state -> frames of black before the next state
        self.walked, self.stuck = 0, False  # walks taken; stuck: walking changes nothing in the view (a wall, the console's rim)

    def moving(self, f):
        """A walk changes what he sees: a grey block off the door, the HUD and the hero alternates with each walk (unless stuck)."""
        if self.stuck or f is BLACK or not (self.state == "spawn" or self.state.startswith("p_")):   # the spawn room only, not menus
            return f
        g = f.copy()
        g[300:800, 1800:2500] = 255 * (self.walked % 2)
        return g

    FRAMES = {
        "lobby_far": "lobby-cursor-far", "lobby_left": "lobby-cursor-left-of-practice", "lobby_on": "lobby-cursor-on-practice",
        "panel": "panel-cursor-on-practice-range", "hero_all": "heroselect-all-tab-black-panther",
        "hero_duel": "heroselect-duelists-cursor-off", "hero_spider": "heroselect-cursor-on-spiderman",
        "spawn": lambda: spawn_frame(), "range": "arrival-plaza-bot-ahead",
        "hero_lost": "heroselect-spiderman-tooltip-ring-lost",
        "hero_fading": "heroselect-all-tab-fading-in", "hero_settled": "heroselect-all-tab-settled",
        "lobby_try": "lobby-cursor-on-try-competitive", "lobby_corner": "lobby-cursor-at-try-competitive-corner",
        "lobby_below": "lobby-cursor-below-practice-tab", "panel_off": "panel-cursor-off-tiles",
    }

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def frame(self):
        if self.state in self.loading:  # black until the frames run out, then the next state
            self.loading[self.state] -= 1
            if self.loading[self.state] >= 0:
                return BLACK
            del self.loading[self.state]
            self.state = self.table[(self.state, "loaded")]
        if self.state not in self.FRAMES:
            return BLACK
        v = self.FRAMES[self.state]
        return self.moving(v() if callable(v) else frame(v))

    def _fire(self, event):
        key = (self.state, event)
        self.n[key] = self.n.get(key, 0) + 1
        rule = self.table.get(key)
        if rule is not None:
            self.state = rule(self.n[key]) if callable(rule) else rule

    def stick(self, x, y, secs, screen=None):
        self.inputs.append(("stick", x, y))
        self.walked += 1
        self.t += secs + 0.25
        self._fire("stick")

    def rstick(self, x, y, secs, screen=None):
        self.inputs.append(("rstick", x, y))
        self.t += secs + 0.15
        self._fire("rstick")

    def tap(self, button, screen=None, proof_fn=None):
        f = self.frame()                                    # the pad layer's own frame, taken at the press
        now = R.classify(f)
        if screen is not None and now != screen:
            raise R.Refuse(f"the screen changed under the proof: proven on {screen}, now {now}", f)
        if button not in R.ALLOWED.get(now, ()) or (button == "A" and not (proof_fn and proof_fn(f).ok)):
            raise R.Refuse(f"{button} refused at the pad on {now}", f)
        self.inputs.append((button, R.classify(f), R.find_cursor(f)))
        self.t += 0.62
        self._fire(button)

    def taps(self):
        return [i for i in self.inputs if i[0] != "stick"]


HAPPY = {
    ("lobby_far", "stick"): "lobby_left", ("lobby_left", "stick"): "lobby_on",
    ("lobby_on", "A"): "loading_panel", ("loading_panel", "loaded"): "panel",
    ("panel", "A"): "loading_hero", ("loading_hero", "loaded"): "hero_all",
    ("hero_all", "RB"): lambda n: "hero_duel" if n >= 2 else "hero_all",
    ("hero_duel", "stick"): "hero_spider", ("hero_spider", "X"): "loading_range", ("loading_range", "loaded"): "spawn",
    ("spawn", "stick"): lambda n: "range" if n >= 3 else "spawn",   # three walk steps take him out of the spawn room
}
LOADING = {"loading_panel": 3, "loading_hero": 5, "loading_range": 4}


def happy():
    return Sim("lobby_far", HAPPY, LOADING)


ZONES = {("A", "lobby"): R.PRACTICE_TAB, ("A", "practice_panel"): R.RANGE_TILE, ("A", "hero_select"): R.SPIDER_SLOT}
ALLOWED_TAPS = {("A", "lobby"), ("A", "practice_panel"), ("A", "hero_select"), ("RB", "hero_select"),
                ("X", "hero_select"), ("RT", "in_range")}


def assert_only_safe_inputs(sim):
    """Every tap was on a screen that allows it; every A had the cursor inside the zone it must be on."""
    for button, screen, cursor in sim.taps():
        assert (button, screen) in ALLOWED_TAPS, (button, screen)
        if button == "A":
            assert cursor is not None and ZONES[(button, screen)].contains(cursor), (screen, cursor)


def test_the_happy_path_from_a_far_cursor_to_the_range():
    sim, lines = happy(), []
    R.run(sim, log=lines.append)
    assert [(b, s) for b, s, _ in sim.taps()] == [
        ("A", "lobby"), ("A", "practice_panel"), ("RB", "hero_select"), ("RB", "hero_select"),
        ("A", "hero_select"), ("X", "hero_select"), ("RT", "in_range")]
    assert_only_safe_inputs(sim)
    assert sim.state == "range" and sim.t < 120
    walked = sum(1 for i in sim.inputs if i[0] == "stick" and i[2] == 1.0)
    assert walked == 3  # out of the spawn room on the third step, and it stops walking as soon as the plaza is confirmed
    assert any("Practice" not in l and l.startswith("reenter: A (") for l in lines)


def test_from_the_panel_it_carries_on_and_from_the_range_it_only_keeps_the_timer():
    sim = Sim("panel", HAPPY, LOADING)
    R.run(sim)
    assert sim.state == "range" and [b for b, _, _ in sim.taps()][0] == "A"
    in_range = Sim("range", {})
    R.run(in_range)
    assert [b for b, *_ in in_range.taps()] == ["RT"] and all(i[0] in ("stick", "RT") for i in in_range.inputs)
    assert not [i for i in in_range.inputs if i[0] == "stick"]      # already on the plaza: nothing to walk


def test_arrival_stops_input_the_moment_the_range_hud_is_gone():
    sim = Sim("spawn", {("spawn", "stick"): "blackout"})  # the HUD vanishes after the first chunk of walking
    with pytest.raises(R.Refuse, match="range HUD is gone"):
        R.run(sim)
    assert [i[0] for i in sim.inputs] == ["stick"]  # one chunk, then nothing: no more walking, no attack


def test_arriving_as_another_hero_is_reported_not_hidden():
    other = edited("arrival-plaza-bot-ahead", lambda f: fill(f, R.BOX["hud_hero"], (90, 90, 90)))
    sim = Sim("range", {})
    sim.frame = lambda: other
    with pytest.raises(R.Refuse, match="HUD hero portrait is not Spider-Man"):
        R.run(sim)


def test_a_cursor_left_of_practice_never_presses_a():
    stuck = {("lobby_left", "stick"): "lobby_left"}
    sim = Sim("lobby_left", stuck)
    with pytest.raises(R.Refuse, match="did not reach the PRACTICE tab"):
        R.run(sim)
    assert sim.taps() == []  # nothing but stick nudges
    with pytest.raises(R.Refuse, match="no proof for A: cursor at .* is not inside the PRACTICE tab") as e:
        R.Safe(sim).press("A", R.on_practice_tab)
    assert sim.taps() == [] and e.value.frame is not None


@pytest.mark.parametrize("state", ["lobby_try", "lobby_corner", "lobby_below"])
def test_a_cursor_that_stays_on_try_competitive_or_its_edge_never_presses_a(state):
    sim = Sim(state, {(state, "stick"): state})  # the pad moves nothing: the cursor cannot get onto the tab
    with pytest.raises(R.Refuse, match="did not reach the PRACTICE tab"):
        R.run(sim)
    assert sim.taps() == []


def test_a_panel_with_nothing_hovered_never_presses_a():
    sim = Sim("panel_off", {})
    with pytest.raises(R.Refuse, match="cursor ring was not found"):
        R.run(sim)
    assert sim.taps() == []


def test_the_all_tab_with_black_panther_is_never_selected():
    sim = Sim("hero_all", {})  # RB does nothing
    with pytest.raises(R.Refuse, match="hero tab is all after RB"):
        R.run(sim)
    assert [b for b, *_ in sim.taps()] == ["RB", "RB"]  # no A, no X
    with pytest.raises(R.Refuse, match="no proof for A"):
        R.Safe(sim).press("A", R.on_spiderman)
    assert [b for b, *_ in sim.taps()] == ["RB", "RB"]


def test_the_duelists_tab_with_the_cursor_off_spiderman_never_presses_a():
    sim = Sim("hero_duel", {("hero_duel", "stick"): "hero_duel"})
    with pytest.raises(R.Refuse, match="did not reach the Spider-Man portrait"):
        R.run(sim)
    assert sim.taps() == []


def test_an_unknown_screen_sends_nothing():
    for f in (BLACK, NOISE):
        sim = Sim("nowhere", {})
        sim.frame = lambda f=f: f
        with pytest.raises(R.Refuse, match="unknown screen; nothing sent"):
            R.run(sim)
        assert sim.inputs == []


def test_a_screen_that_never_loads_stops_without_sending_anything_while_it_waits():
    table = dict(HAPPY)
    table[("loading_hero", "loaded")] = "loading_hero"  # never finishes
    sim = Sim("panel", table, {"loading_hero": 10**6})
    with pytest.raises(R.Refuse, match="did not reach hero_select or in_range within 40 s"):
        R.run(sim)
    assert [b for b, *_ in sim.taps()] == ["A"]  # the one press on the panel, then only waiting


def test_a_press_that_does_nothing_is_not_repeated_forever():
    table = dict(HAPPY)
    table[("lobby_on", "A")] = "lobby_on"  # the lobby ignores A
    with pytest.raises(R.Refuse, match="did not reach practice_panel within 10 s"):
        R.run(Sim("lobby_on", table, LOADING))


def test_forbidden_buttons_are_refused_wherever_they_are_asked_for():
    lobby = Sim("lobby_on", {})
    for button in ("X", "START", "UP", "DOWN", "LEFT", "RIGHT", "RB", "B", "Y"):
        with pytest.raises(R.Refuse, match="not allowed on screen lobby"):
            R.Safe(lobby).press(button, lambda f: R.Proof(True, "forced"))
    panel = Sim("panel", {})
    for button in ("X", "START", "RB"):
        with pytest.raises(R.Refuse, match="not allowed on screen practice_panel"):
            R.Safe(panel).press(button)
    assert lobby.taps() == [] and panel.taps() == []
    with pytest.raises(R.Refuse, match="no proof was supplied"):
        R.Safe(lobby).press("A")  # A without a proof function is refused too
    hero = Sim("hero_spider", {})
    R.Safe(hero).press("X")  # the one place X is allowed
    assert [b for b, *_ in hero.taps()] == ["X"]


def test_every_run_including_the_failing_ones_only_sends_allowed_buttons():
    for sim in (happy(), Sim("panel", HAPPY, LOADING), Sim("hero_all", {}), Sim("lobby_left", {("lobby_left", "stick"): "lobby_left"})):
        try:
            R.run(sim)
        except R.Refuse:
            pass
        assert_only_safe_inputs(sim)


# --- arrival: out of the spawn room, verified from frames -----------------------------------------------------------------
def test_the_plaza_is_told_from_the_spawn_room():
    spawn, plaza = frame("arrival-spawn-room"), frame("arrival-plaza-bot-ahead")
    assert R.classify(spawn) == R.classify(plaza) == "in_range"
    assert not R.plaza_view(spawn) and R.plaza_view(plaza)          # the spawn door makes an enemy box too, but at the left edge
    assert not R.plaza_view(frame("in-range")) and not R.plaza_view(BLACK)
    assert 0.2 < R.door(spawn) < 0.3 and R.door(plaza) is None and R.door(BLACK) is None


def test_the_door_and_the_plaza_are_read_correctly_on_every_recorded_spawn_pose():
    """The lead's re6 / re7 / q8 (native, 2026-09-20) and tagrun0 frame 0: the four ways a re-entry can leave the player in the spawn room."""
    ahead, wall, console, first = (frame(n) for n in POSES)
    assert 0.5 - R.DOOR_TOL <= R.door(ahead) <= 0.5 + R.DOOR_TOL          # dead ahead: 76k px of lime, walk
    assert R.door(wall) is None                                           # the wall left of the door: nothing to walk to
    assert R.door(console) == pytest.approx(0.19, abs=0.04)               # two doors to the left: the bigger one, turn left
    assert R.door(first) == pytest.approx(0.26, abs=0.04)                 # the door at the left edge
    for name in POSES:
        assert not R.plaza_view(frame(name)), name                        # in re6 the bot shows THROUGH the glass and the glow makes boxes
    assert R.plaza_view(frame("arrival-plaza-bot-ahead")) and R.door(frame("arrival-plaza-bot-ahead")) is None
    assert not R.plaza_view(frame("in-range")) and R.door(frame("in-range")) is None


def test_the_lime_door_is_told_from_an_enemy_outline():
    hsv = cv2.cvtColor(R.small(frame("arrival-spawn-door-ahead")), cv2.COLOR_BGR2HSV)[100:300, 480:800].reshape(-1, 3)
    lime = hsv[(hsv[:, 0] >= 30) & (hsv[:, 0] <= 56) & (hsv[:, 1] > 70) & (hsv[:, 2] > 70)]
    assert len(lime) > 10000 and 40 <= np.median(lime[:, 0]) <= 50                    # hue ~46, not the outline's ~67
    outline = np.uint8([[[67, 160, 175]]])                                            # a green enemy outline pixel (docs/lanes/l4-controller.md)
    assert not (R.LIME["h"][0] <= outline[0, 0, 0] <= R.LIME["h"][1])


def _lime_bgr():
    return cv2.cvtColor(np.uint8([[[46, 140, 150]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()


def test_a_small_lime_patch_is_not_the_door():
    f = edited("arrival-plaza-bot-ahead", lambda g: g.__setitem__((slice(300, 520), slice(300, 324)), _lime_bgr()))   # 110 x 12 px at 1280 scale: tall enough, far too small
    assert R.door(f) is None and R.plaza_view(f)


def test_a_door_filling_the_view_blocks_the_plaza_even_with_a_clear_bot():
    big = edited("arrival-plaza-bot-ahead", lambda g: g.__setitem__((slice(0, 900), slice(0, 800)), _lime_bgr()))     # the glass fills the left
    assert R.door(big) is not None and not R.plaza_view(big)


def test_a_bot_ringed_with_lime_is_seen_through_the_glass_not_in_the_open():
    box = None
    from perception.outline import find_enemies
    f = frame("arrival-plaza-bot-ahead")
    d, = find_enemies(f, scale=2.0)
    x1, y1, x2, y2 = (int(v) for v in d.bbox)
    px, py = int(0.25 * (x2 - x1)), int(0.25 * (y2 - y1))

    def glow(g):
        lime = _lime_bgr()
        g[max(0, y1 - py - 40):y2 + py + 40, max(0, x1 - px - 40):x2 + px + 40] = lime       # a lime frame round the box (its own box kept clear)
        g[y1 - py:y2 + py, x1 - px:x2 + px] = f[y1 - py:y2 + py, x1 - px:x2 + px]
        g[y1 - py:y1 - py + 24, x1 - px:x2 + px] = lime
        g[y2 + py - 24:y2 + py, x1 - px:x2 + px] = lime
        g[y1 - py:y2 + py, x1 - px:x1 - px + 24] = lime
        g[y1 - py:y2 + py, x2 + px - 24:x2 + px] = lime
    ringed = edited("arrival-plaza-bot-ahead", glow)
    assert R._lime(R.small(ringed)).mean() < R.PLAZA_LIME_MAX                            # not the share gate that refuses it
    assert not R.plaza_view(ringed)


def _pose_sim(start, table):
    sim = Sim(start, table)
    sim.FRAMES = dict(Sim.FRAMES, **{"p_ahead": "arrival-spawn-door-ahead", "p_wall": "arrival-spawn-wall-left-of-door",
                                     "p_console": "arrival-spawn-console-two-doors", "p_first": "arrival-spawn-room",
                                     "p_on": lambda: spawn_frame()})
    return sim


# the recorded door-ahead pose has the pane at x 0.557, right of his column (0.40): a turn puts it on his column, then three steps take him out
WALK_OUT = {("p_ahead", "rstick"): "p_on", ("p_on", "stick"): lambda n: "range" if n >= 3 else "p_on"}


@pytest.mark.parametrize("start,table,expected", [
    ("p_ahead", WALK_OUT, ["rstick", "stick", "stick", "stick", "RT"]),                                   # door ahead: onto his column, out
    ("p_console", {**WALK_OUT, ("p_console", "rstick"): "p_on"}, ["rstick", "stick", "stick", "stick", "RT"]),
    ("p_first", {**WALK_OUT, ("p_first", "rstick"): "p_on"}, ["rstick", "stick", "stick", "stick", "RT"]),
    ("p_wall", {**WALK_OUT, ("p_wall", "rstick"): lambda n: "p_console" if n >= 2 else "p_wall", ("p_console", "rstick"): "p_on"},
     ["rstick", "rstick", "rstick", "stick", "stick", "stick", "RT"]),                                    # no door in view: look around, then turn to it
])
def test_arrival_from_each_recorded_spawn_pose_gets_out_and_never_walks_toward_nothing(start, table, expected):
    sim = _pose_sim(start, table)
    R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert [i[0] for i in sim.inputs] == expected
    first_turn = next((i for i in sim.inputs if i[0] == "rstick"), None)
    if start in ("p_console", "p_first"):
        assert first_turn[1] < 0                                                                             # the doors are on the left: turn left
    if start == "p_wall":
        assert first_turn[1] > 0 and sim.inputs[0][0] == "rstick"                                            # nothing to walk to: it looks around first


def test_arrival_at_the_wall_only_looks_around_and_then_exits_unconfirmed():
    sim = _pose_sim("p_wall", {})
    with pytest.raises(R.Refuse, match="could not confirm the spawn room was left"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert all(i[0] == "rstick" for i in sim.inputs) and 15 <= len(sim.inputs) <= 32     # no walking blind, no attack, a bounded budget


def test_the_bot_seen_through_the_glass_never_confirms_the_plaza():
    sim = _pose_sim("p_ahead", {})                                                       # walking at the door but never getting through
    with pytest.raises(R.Refuse, match="could not confirm"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert "RT" not in [i[0] for i in sim.inputs]


def test_arrival_stops_walking_once_two_frames_show_the_plaza_then_attacks_once():
    sim = Sim("spawn", {("spawn", "stick"): lambda n: "range" if n >= 4 else "spawn"})
    R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert [i[0] for i in sim.inputs] == ["stick"] * 4 + ["RT"]      # the plaza first shows after step 4, is confirmed by a second look, then RT


def test_arrival_that_cannot_confirm_the_plaza_exits_after_its_budget_without_attacking():
    sim = Sim("spawn", {})                                            # a wall: the player never leaves the spawn room
    with pytest.raises(R.Refuse, match="could not confirm the spawn room was left within 14 s"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    walks = [i for i in sim.inputs if i[0] == "stick"]
    assert 15 <= len(walks) <= 20 and all(i[0] == "stick" for i in sim.inputs)          # bounded, and RT never sent
    assert sim.t <= R.ARRIVE_S + 1.5


def test_arrival_stops_at_once_on_the_idle_banner():
    banner = edited("arrival-spawn-room", lambda f: fill(f, (100, 30, 700, 90), (30, 30, 230)))
    sim = Sim("spawn", {})
    sim.frame = lambda: banner
    with pytest.raises(R.Refuse, match="idle-kick banner"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert sim.inputs == []                                           # not one input, not even a step towards the door


class TurnSim(Sim):
    """The spawn room with a tall green door painted at `door_x` (fraction of the width); a right-stick turn moves it across the
    view at the measured camera rate, and once it is centred the walk carries the player out onto the plaza."""

    def __init__(self, door_x):
        super().__init__("spawn", {})
        self.door_x, self.walks = door_x, 0

    def frame(self):
        if self.walks >= 3:
            return frame("arrival-plaza-bot-ahead")
        return self.moving(spawn_frame(self.door_x))

    def rstick(self, x, y, secs, screen=None):
        super().rstick(x, y, secs)
        self.door_x -= 465.0 * math.radians(x / R.YAW_STICK * R.YAW_DEG_S * secs) / 1280.0   # turning right slides the door left

    def stick(self, x, y, secs, screen=None):
        super().stick(x, y, secs)
        if abs(self.door_x - R.HERO_X) <= R.DOOR_TOL:
            self.walks += 1


@pytest.mark.parametrize("door_x", [0.15, 0.3, 0.7, 0.85])
def test_arrival_turns_toward_a_door_off_to_one_side_before_it_walks(door_x):
    sim = TurnSim(door_x)
    R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    kinds = [i[0] for i in sim.inputs]
    assert kinds[0] == "rstick" and math.copysign(1, sim.inputs[0][1]) == math.copysign(1, door_x - R.HERO_X)   # turns TOWARD it
    assert "stick" not in kinds[:kinds.index("stick")] and kinds.count("rstick") <= 3 and kinds[-1] == "RT"
    assert abs(sim.door_x - R.HERO_X) <= R.DOOR_TOL                            # and walks only once it is on his column


class Flicker(Sim):
    """One frame that looks like the plaza (a glitch, a passing bot) between spawn-room frames: never two in a row."""

    def __init__(self):
        super().__init__("spawn", {})
        self.seq = [spawn_frame(), frame("arrival-plaza-bot-ahead")] + [spawn_frame()] * 200

    def frame(self):
        return self.moving(self.seq.pop(0) if len(self.seq) > 1 else self.seq[0])


def test_a_single_plaza_looking_frame_is_not_enough_to_believe_the_spawn_room_was_left():
    sim = Flicker()
    with pytest.raises(R.Refuse, match="could not confirm"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert "RT" not in [i[0] for i in sim.inputs]


# --- dry run and main ------------------------------------------------------------------------------------------------
def test_dry_run_on_a_saved_frame_opens_nothing_and_says_what_it_would_do(capsys):
    def boom(*a):
        pytest.fail("a dry run must not touch the display or the pad")

    cases = {
        "lobby-cursor-on-practice": ["screen: lobby", "proof for A right now: OK", "then A opens the PRACTICE panel"],
        "lobby-cursor-left-of-practice": ["screen: lobby", "would steer the cursor to the PRACTICE tab", "not inside yet",
                                          "would NOT press A on this frame"],
        "lobby-cursor-far": ["would NOT press A on this frame"],
        "lobby-cursor-on-try-competitive": ["screen: lobby", "proof for A right now: NO", "would NOT press A on this frame"],
        "lobby-cursor-at-try-competitive-corner": ["proof for A right now: NO", "would NOT press A on this frame"],
        "lobby-cursor-below-practice-tab": ["proof for A right now: NO", "not inside the PRACTICE tab"],
        "panel-cursor-off-tiles": ["screen: practice_panel", "cursor: not found", "would jiggle the stick"],
        "panel-cursor-on-practice-range": ["screen: practice_panel", "proof for A right now: OK"],
        "heroselect-all-tab-black-panther": ["hero tab: all", "would press RB 2x to reach duelists", "cursor: not found",
                                              "would jiggle the stick"],
        "heroselect-duelists-cursor-off": ["hero tab: duelists", "already on duelists", "would NOT press A"],
        "heroselect-cursor-on-spiderman": ["proof for A right now: OK", "then A selects the hero, then X confirms"],
        "in-range": ["screen: in_range", "plaza with the bot ahead: no", "would turn to the door"],
        "arrival-spawn-room": ["screen: in_range", "plaza with the bot ahead: no", "glass door: centre x 0.2", "exit 1 if the plaza is not confirmed"],
        "arrival-plaza-bot-ahead": ["screen: in_range", "plaza with the bot ahead: yes"],
        "lobby-cursor-on-practice-tab-lower-half": ["screen: lobby", "proof for A right now: OK", "then A opens the PRACTICE panel"],
    }
    for name, expect in cases.items():
        assert R.main(["--dry-run", "--frame", str(FIX / f"{name}.jpg")], capture=boom, live=boom) == 0
        out = capsys.readouterr().out
        assert all(e in out for e in expect), (name, out)
        assert all(l.startswith("reenter: ") for l in out.strip().splitlines())


def test_dry_run_of_an_unknown_screen_exits_nonzero(tmp_path, capsys):
    path = tmp_path / "black.jpg"
    cv2.imwrite(str(path), BLACK)
    assert R.main(["--dry-run", "--frame", str(path)]) == 1
    assert "unknown screen" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        R.main(["--frame", str(path)])  # --frame without --dry-run is refused


class FakeCap:
    def __init__(self, f):
        self.f = f

    def grab(self):
        f, self.f = self.f, None
        return f


def test_live_dry_run_grabs_one_frame_and_never_builds_the_pad(capsys):
    def no_pad(*a):
        pytest.fail("a dry run must not open a pad")

    assert R.main(["--dry-run"], capture=lambda: FakeCap(frame("lobby-cursor-left-of-practice")), live=no_pad) == 0
    assert "screen: lobby" in capsys.readouterr().out


def test_a_run_stops_before_opening_a_pad_on_an_unknown_first_frame(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(R, "OUT", tmp_path)

    def no_pad(*a):
        pytest.fail("no pad on an unknown screen")

    assert R.main([], capture=lambda: FakeCap(NOISE), live=no_pad) == 1
    out = capsys.readouterr().out
    assert "unknown screen" in out and "no pad opened, nothing sent" in out and list(tmp_path.glob("refuse-*.jpg"))


def test_main_reports_success_and_a_refusal_with_a_saved_frame(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(R, "OUT", tmp_path)
    sim = happy()
    assert R.main([], capture=lambda: FakeCap(frame("lobby-cursor-far")), live=lambda cap, first: sim) == 0
    assert "in the Practice Range as Spider-Man" in capsys.readouterr().out
    stuck = Sim("lobby_left", {("lobby_left", "stick"): "lobby_left"})
    assert R.main([], capture=lambda: FakeCap(frame("lobby-cursor-left-of-practice")), live=lambda cap, first: stuck) == 1
    out = capsys.readouterr().out.strip().splitlines()
    stops = [l for l in out if "STOP" in l]
    assert len(stops) == 1 and stops[0].startswith("reenter: STOP: the cursor did not reach the PRACTICE tab")  # one line
    saved = list(tmp_path.glob("refuse-*.jpg"))
    assert len(saved) == 1 and cv2.imread(str(saved[0])).shape[:2] == (720, 1280)


# --- the pad code, against a fake vgamepad ----------------------------------------------------------------------------
def fake_vgamepad():
    calls = []

    class Pad:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a, k))

    mod = types.ModuleType("vgamepad")
    mod.XUSB_BUTTON = types.SimpleNamespace(XUSB_GAMEPAD_A="A", XUSB_GAMEPAD_X="X", XUSB_GAMEPAD_RIGHT_SHOULDER="RB",
                                            XUSB_GAMEPAD_START="START", XUSB_GAMEPAD_DPAD_UP="UP")
    mod.VX360Gamepad = Pad
    return mod, calls


class Clock:
    """A clock the test moves: `sleep` advances it, so a slow proof, a long hold and a 22 s wait are all just arithmetic."""

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class Screen:
    """A capture source. `frames` is what grab() returns in turn (None = dxcam has nothing new); the last entry repeats.
    `now` is the frame it returns once `frames` is used up, or None for 'the screen has not changed'."""

    def __init__(self, *frames, after=None, fails=None):
        self.frames, self.after, self.fails, self.grabs = list(frames), after, fails, 0

    def grab(self):
        self.grabs += 1
        if self.fails:
            raise self.fails
        return self.frames.pop(0) if self.frames else self.after


def make_live(monkeypatch, cap, gdi=None, clock=None):
    mod, calls = fake_vgamepad()
    monkeypatch.setitem(sys.modules, "vgamepad", mod)
    clock = clock or Clock()
    live = R.Live(cap, None, sleep=clock.sleep, settle_s=0, gdi=gdi, clock=clock)
    calls.clear()
    return live, calls, clock


def presses(calls):
    return [c[2]["button"] for c in calls if c[0] == "press_button"]


def touched(calls):
    """Did anything but a neutral reach the pad?"""
    return [c for c in calls if c[0] not in ("reset", "update")]


def test_live_writes_only_the_buttons_it_supports_each_on_a_frame_taken_at_the_press(monkeypatch):
    lobby, hero = frame("lobby-cursor-on-practice"), frame("heroselect-cursor-on-spiderman")
    live, calls, _ = make_live(monkeypatch, Screen(lobby, after=lobby))
    live.tap("A", screen="lobby", proof_fn=R.on_practice_tab)
    assert presses(calls) == ["A"] and [c[0] for c in calls][-2:] == ["reset", "update"]          # released in a finally, whole pad
    hero_live, hero_calls, _ = make_live(monkeypatch, Screen(hero, hero, after=hero))
    hero_live.tap("X")
    hero_live.tap("RB")
    assert presses(hero_calls) == ["X", "RB"]
    walk, walk_calls, _ = make_live(monkeypatch, Screen(frame("arrival-plaza-bot-ahead"), after=frame("arrival-plaza-bot-ahead")))
    walk.tap("RT")
    assert [c for c in walk_calls if c[0] == "right_trigger_float"] == [("right_trigger_float", (1.0,), {})]
    for forbidden in ("START", "UP", "B", "Y", "LB"):
        with pytest.raises(KeyError):
            walk.tap(forbidden)


def test_a_static_menu_gives_no_new_frame_and_the_press_reads_the_screen_as_it_is_not_the_last_frame(monkeypatch):
    """VUH-1325 (1): dxcam delivers a frame only when the screen changes. The proving frame was the hero-select screen; 22 s later the screen is
    the range and dxcam still has nothing new. The old Live.frame() handed back the proving frame, so X was sent; it now reads GDI."""
    hero, ranged = frame("heroselect-cursor-on-spiderman"), frame("arrival-plaza-bot-ahead")
    clock = Clock()
    live, calls, _ = make_live(monkeypatch, Screen(hero, after=None), gdi=Screen(after=ranged), clock=clock)
    assert R.classify(live.frame()) == "hero_select"                                  # the proof
    clock.t += 22.0                                                                   # a static menu: nothing new from dxcam for 22 s
    with pytest.raises(R.Refuse, match="the screen changed under the proof: proven on hero_select, now in_range"):
        live.tap("X", screen="hero_select")
    assert touched(calls) == []                                                       # not a button, not a stick, nothing


def test_the_live_frame_is_never_an_older_one(monkeypatch):
    a, b = frame("lobby-cursor-far"), frame("lobby-cursor-on-practice")
    clock = Clock()
    live, _, _ = make_live(monkeypatch, Screen(a, after=None), gdi=Screen(b, after=a), clock=clock)
    assert live.frame() is a
    first_t = live.frame_t
    clock.t += 5.0
    assert live.frame() is b and live.frame_t > first_t                              # no new dxcam frame: GDI, timestamped now
    assert live.frame() is a                                                          # and again: never a remembered frame


def test_no_frame_at_all_fails_closed_and_sends_nothing(monkeypatch):
    for gdi in (Screen(after=None), Screen(fails=OSError("gdi down"))):
        live, calls, _ = make_live(monkeypatch, Screen(after=None), gdi=gdi)
        with pytest.raises(R.Refuse, match="no current frame"):
            live.tap("X", screen="hero_select")
        with pytest.raises(R.Refuse, match="no current frame"):
            live.stick(0.0, 1.0, 0.1)
        assert touched(calls) == []


def test_a_proof_older_than_the_limit_is_refused_at_the_moment_of_the_press(monkeypatch):
    lobby = frame("lobby-cursor-on-practice")
    clock = Clock()

    def slow_proof(f):                                                                # the proof takes 2 s: the frame is 2 s old when the pad would be written
        clock.t += 2.0
        return R.on_practice_tab(f)

    live, calls, _ = make_live(monkeypatch, Screen(lobby, after=lobby), clock=clock)
    with pytest.raises(R.Refuse, match=r"the proof is 2\.\d\d s old \(limit 0\.3 s\)"):
        live.tap("A", screen="lobby", proof_fn=slow_proof)
    assert touched(calls) == []


def test_no_proof_frame_may_predate_the_last_inputs_settling(monkeypatch):
    lobby = frame("lobby-cursor-on-practice")
    live, calls, clock = make_live(monkeypatch, Screen(lobby, after=lobby))
    real_frame = live.frame

    def frame_from_before_the_input():
        f = real_frame()
        live.frame_t = live.settled_t - 0.5                                            # a frame taken before the last input finished
        return f

    live.frame = frame_from_before_the_input
    with pytest.raises(R.Refuse, match="predates the last input's settling"):
        live.tap("A", screen="lobby", proof_fn=R.on_practice_tab)
    assert touched(calls) == []
    live.frame = real_frame                                                            # and inputs advance the settling time
    before = live.settled_t
    live.stick(0.0, 0.0, 0.05, screen="lobby")
    assert live.settled_t > before


def test_a_tap_advances_the_settling_time_so_the_next_proof_must_be_newer(monkeypatch):
    hero = frame("heroselect-cursor-on-spiderman")
    live, calls, clock = make_live(monkeypatch, Screen(hero, hero, after=hero))
    before = live.settled_t
    live.tap("X", screen="hero_select")
    assert live.settled_t > before and live.settled_t == clock()                       # set when the press and its wait are over
    stamp = live.frame_t
    live.frame()
    assert live.frame_t > stamp and live.frame_t >= live.settled_t                      # and the next frame is taken after it


def test_the_arrivals_turns_are_gated_by_the_screen_too():
    class Io:
        sticks = []

        def frame(self):
            return BLACK

        def rstick(self, *a, **kw):
            self.sticks.append(a)

    io = Io()
    with pytest.raises(R.Refuse, match="the screen is unknown, not .*; no stick sent"):
        R.Safe(io, log=lambda *_: None).rstick(0.45, 0.0, 0.3)
    assert io.sticks == []


def test_a_refused_press_or_a_missing_proof_writes_nothing(monkeypatch):
    live, calls, _ = make_live(monkeypatch, Screen(frame("lobby-cursor-far"), after=frame("lobby-cursor-far")))
    with pytest.raises(R.Refuse, match="no proof for A at the moment of the press"):
        live.tap("A", screen="lobby", proof_fn=R.on_practice_tab)                    # the cursor is nowhere near the tab
    with pytest.raises(R.Refuse, match="no proof for A"):
        live.tap("A", screen="lobby")                                                 # no proof supplied at all
    with pytest.raises(R.Refuse, match="X is not allowed on screen lobby"):
        live.tap("X", screen="lobby")                                                 # X on the lobby is START for a live match
    assert touched(calls) == []


class Boom(Exception):
    pass


@pytest.mark.parametrize("failure", [Boom("pad died"), KeyboardInterrupt()])
def test_an_exception_or_ctrl_c_in_any_hold_still_releases_the_whole_pad(monkeypatch, failure):
    """VUH-1325 (5): every hold ends in a finally."""
    hero = frame("heroselect-cursor-on-spiderman")
    for hold in ("tap", "stick", "rstick"):
        live, calls, clock = make_live(monkeypatch, Screen(hero, after=hero))
        live.sleep = lambda s: (_ for _ in ()).throw(failure)                          # the sleep during the hold is interrupted
        with pytest.raises(type(failure)):
            {"tap": lambda: live.tap("X", screen="hero_select"), "stick": lambda: live.stick(1.0, 0.0, 0.5, screen="hero_select"),
             "rstick": lambda: live.rstick(1.0, 0.0, 0.5, screen="hero_select")}[hold]()
        assert [c[0] for c in calls][-2:] == ["reset", "update"], hold                # neutral was the last thing written


def test_a_pad_write_that_fails_mid_press_still_ends_neutral(monkeypatch):
    hero = frame("heroselect-cursor-on-spiderman")
    live, calls, _ = make_live(monkeypatch, Screen(hero, after=hero))
    seen = {"n": 0}
    orig = live.pad.__class__.__getattr__

    def flaky(self, name):
        fn = orig(self, name)
        if name == "update":
            def upd(*a, **k):
                seen["n"] += 1
                if seen["n"] == 1:
                    raise Boom("update failed after the press")
                return fn(*a, **k)
            return upd
        return fn

    monkeypatch.setattr(live.pad.__class__, "__getattr__", flaky)
    with pytest.raises(Boom):
        live.tap("X", screen="hero_select")
    assert "reset" in [c[0] for c in calls]


def test_opening_the_pad_ends_neutral_even_if_the_settle_wait_is_interrupted(monkeypatch):
    mod, calls = fake_vgamepad()
    monkeypatch.setitem(sys.modules, "vgamepad", mod)

    def interrupted(s):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        R.Live(Screen(after=None), None, sleep=interrupted, settle_s=3.0)
    assert [c[0] for c in calls][-2:] == ["reset", "update"]


# --- VUH-1325 (8): unknown sends nothing, sticks included ------------------------------------------------------------------
@pytest.mark.parametrize("screen_frame", ["black", "noise"])
def test_a_stick_on_an_unknown_screen_is_never_written(monkeypatch, screen_frame):
    unknown = BLACK if screen_frame == "black" else NOISE
    live, calls, _ = make_live(monkeypatch, Screen(unknown, after=unknown))
    with pytest.raises(R.Refuse, match="the screen is unknown, not .*; no stick sent"):
        live.stick(0.0, 1.0, 0.2)
    with pytest.raises(R.Refuse, match="no stick sent"):
        live.rstick(1.0, 0.0, 0.2)
    assert touched(calls) == []


def test_steering_on_a_black_frame_sends_no_jiggle_at_all():
    """The old steer jiggled the stick four times on any frame with no ring, black ones included, before refusing."""
    class Io:
        def __init__(self):
            self.sticks = []

        def frame(self):
            return BLACK

        def now(self):
            return 0.0

        def sleep(self, s):
            pass

        def stick(self, x, y, secs, screen=None):
            self.sticks.append((x, y))

        rstick = stick

    io = Io()
    safe = R.Safe(io, log=lambda *_: None)
    with pytest.raises(R.Refuse, match="the screen is unknown, not .*; no stick sent"):
        R.steer(safe, R.PRACTICE_TAB, "lobby")
    assert io.sticks == []
    with pytest.raises(R.Refuse, match="range HUD is gone|no stick sent"):
        R.arrive(io, safe)                                                             # the arrival never walks or turns on it either
    assert io.sticks == []


def test_the_whole_run_sends_no_stick_once_the_screen_goes_unknown_mid_steering():
    sim = Sim("lobby_far", {("lobby_far", "stick"): "blackout"})                        # the first nudge lands on a black screen (a load, a crash, an alt-tab)
    with pytest.raises(R.Refuse, match="no stick sent"):
        R.run(sim, log=lambda *_: None)
    assert [i[0] for i in sim.inputs] == ["stick"]                                      # the one nudge that was proven, and not a jiggle more


def test_a_lost_ring_on_a_known_screen_still_jiggles_to_find_it():
    sim = Sim("panel_off", {})                                                         # the panel just opened, cursor faint: a real screen, no ring
    with pytest.raises(R.Refuse, match="cursor ring was not found"):
        R.steer(R.Safe(sim, log=lambda *_: None), R.RANGE_TILE, "practice_panel")
    assert len([i for i in sim.inputs if i[0] == "stick"]) == R.MAX_MISSES


# --- VUH-1325 (5): the process never exits with anything held ---------------------------------------------------------------
class Released:
    """A stand-in for Live in main(): counts release_all and serves the lobby."""

    def __init__(self, fail=None):
        self.released, self.fail = 0, fail

    def release_all(self):
        self.released += 1

    def frame(self):
        return frame("lobby-cursor-far")

    def now(self):
        return 0.0

    def sleep(self, s):
        pass

    def stick(self, *a, **kw):
        raise Boom("boom") if self.fail else R.Refuse("stop")


@pytest.mark.parametrize("failure", [Boom("boom"), KeyboardInterrupt(), R.Refuse("stop"), SystemExit(3)])
def test_main_releases_the_pad_on_every_way_out(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(R, "OUT", tmp_path)
    io = Released()

    def run_that_ends_badly(io_, log=print):
        raise failure

    monkeypatch.setattr(R, "run", run_that_ends_badly)
    outcome = None
    try:
        outcome = R.main([], capture=lambda: FakeCap(frame("lobby-cursor-far")), live=lambda cap, first: io)
    except BaseException as e:  # noqa: BLE001
        outcome = e
    assert io.released >= 1 and outcome is not None
    io2 = Released()
    monkeypatch.setattr(R, "run", lambda io_, log=print: None)
    assert R.main([], capture=lambda: FakeCap(frame("lobby-cursor-far")), live=lambda cap, first: io2) == 0
    assert io2.released >= 1                                                           # and on success


def test_a_release_that_fails_is_reported_and_never_masks_the_stop(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(R, "OUT", tmp_path)

    class Bad(Released):
        def release_all(self):
            raise Boom("pad gone")

    monkeypatch.setattr(R, "run", lambda io_, log=print: (_ for _ in ()).throw(R.Refuse("nothing provable")))
    assert R.main([], capture=lambda: FakeCap(frame("lobby-cursor-far")), live=lambda cap, first: Bad()) == 1
    assert "could not release the pad" in capsys.readouterr().err


def test_the_first_frame_falls_back_to_gdi_and_no_frame_means_no_pad(monkeypatch):
    monkeypatch.setitem(sys.modules, "capture", types.SimpleNamespace(Capture=lambda kind: Screen(after=frame("lobby-cursor-far"))))
    assert R._first_frame(Screen(after=None), timeout=0.0) is frame("lobby-cursor-far")


# --- the tooltip must fit the cursor ---------------------------------------------------------------------------------------------
def test_a_tooltip_that_does_not_fit_the_cursor_position_is_not_a_proof(monkeypatch):
    f = frame(LOST)
    _, at = R.tooltip_at(f)
    assert (at[0] - 860, at[1] - 44) == pytest.approx((R.TIP_DX, R.TIP_DY), abs=2)      # 141 x 29 from the ring's centre, on both recorded frames
    _, at0 = R.tooltip_at(frame("heroselect-cursor-on-spiderman"))
    assert (at0[0] - 852, at0[1] - 48) == pytest.approx((R.TIP_DX, R.TIP_DY), abs=2)
    ok = R.on_spiderman(f)
    assert ok.ok
    monkeypatch.setattr(R, "find_cursor", lambda fr: (500.0, 300.0))                    # a ring found somewhere else: two cursors, or a stale tooltip
    p = R.on_spiderman(f)
    assert not p.ok and "does not fit the cursor" in p.reason
    monkeypatch.setattr(R, "find_cursor", lambda fr: (862.0, 46.0))                     # a ring where the tooltip says: fine
    assert R.on_spiderman(f).ok
    monkeypatch.setattr(R, "find_cursor", lambda fr: None)                              # no ring: the tooltip alone proves nothing
    assert not R.on_spiderman(f).ok


# --- the integrated re-review (b811f21): sticks carry their screen and a fresh, post-settle proof to the pad ---------------------------
@pytest.mark.parametrize("method", ["stick", "rstick"])
def test_a_stick_on_a_two_second_old_proof_is_refused(monkeypatch, method):
    """A classify delayed by 2 s still wrote either stick: buttons had the age check, sticks did not."""
    f = frame("arrival-spawn-door-ahead")
    live, calls, clock = make_live(monkeypatch, Screen(after=f))
    classify = R.classify

    def slow(fr):
        result = classify(fr)
        clock.t += 2.0
        return result

    monkeypatch.setattr(R, "classify", slow)
    with pytest.raises(R.Refuse, match="s old"):
        getattr(live, method)(0.45, 0.0, 0.1)
    assert touched(calls) == []


@pytest.mark.parametrize("pose", ["arrival-spawn-door-ahead", "arrival-spawn-wall-left-of-door"])
def test_an_arrival_stick_never_lands_on_the_lobby_that_replaced_the_range(monkeypatch, pose):
    """Arrival's look sees the range, Safe's gate sees the range, the pad's own frame is the lobby with the cursor on TRY COMPETITIVE:
    a recognized screen is not the screen the stick is for, so nothing is written."""
    ranged, lobby = frame(pose), frame("lobby-cursor-on-try-competitive")
    live, calls, _ = make_live(monkeypatch, Screen(ranged, ranged, lobby, after=lobby))
    with pytest.raises(R.Refuse, match="the screen is lobby, not in_range"):
        R.arrive(live, R.Safe(live, log=lambda *_: None))
    assert touched(calls) == []


def test_menu_steering_is_bound_to_its_own_screen_at_the_pad(monkeypatch):
    lobby, hero = frame("lobby-cursor-far"), frame("heroselect-duelists-cursor-off")
    live, calls, _ = make_live(monkeypatch, Screen(lobby, hero, after=hero))      # the pad's frame is another menu by the time it writes
    with pytest.raises(R.Refuse, match="the screen is hero_select, not lobby"):
        R.steer(R.Safe(live, log=lambda *_: None), R.PRACTICE_TAB, "lobby")
    assert touched(calls) == []
    with pytest.raises(R.Refuse, match="no stick is ever sent for screen unknown"):
        live.stick(1.0, 0.0, 0.1, screen="unknown")


@pytest.mark.parametrize("method", ["stick", "rstick"])
def test_a_stick_proof_frame_may_not_predate_the_last_inputs_settling(monkeypatch, method):
    f = frame("arrival-spawn-door-ahead")
    live, calls, _ = make_live(monkeypatch, Screen(after=f))
    real_frame = live.frame

    def frame_from_before_the_input():
        fr = real_frame()
        live.frame_t = live.settled_t - 0.1                                             # fresh by age, but taken before the last input settled
        return fr

    live.frame = frame_from_before_the_input
    with pytest.raises(R.Refuse, match="predates the last input's settling"):
        getattr(live, method)(0.45, 0.0, 0.1)
    assert touched(calls) == []


# --- live 2026-09-20 23:35: a static menu charged the dxcam wait to the GDI frame (0.47 s "old" proofs) ------------------------------------
class SlowGdi(Screen):
    """GDI that takes `secs` of the test clock per grab and remembers when each grab started."""

    def __init__(self, clock, secs, *frames, after=None):
        super().__init__(*frames, after=after)
        self.clock, self.secs, self.starts = clock, secs, []

    def grab(self):
        self.starts.append(self.clock.t)
        self.clock.t += self.secs
        return super().grab()


def slow(proof_fn, clock, secs):
    def fn(f):
        clock.t += secs
        return proof_fn(f)
    return fn


def test_a_gdi_fallback_frame_carries_the_gdi_start_time_not_the_dxcam_wait(monkeypatch):
    lobby, clock = frame("lobby-cursor-on-practice"), Clock()
    gdi = SlowGdi(clock, 0.05, after=lobby)
    live, _, _ = make_live(monkeypatch, Screen(after=None), gdi=gdi, clock=clock)
    t0 = clock.t
    assert live.frame() is lobby
    assert live.frame_t == gdi.starts[-1] and live.frame_t >= t0 + 0.15            # stamped when the GDI grab began, after the dxcam wait


def test_a_slow_dxcam_timeout_alone_no_longer_refuses_a_press(monkeypatch):
    """The live case: dxcam has nothing on a static lobby (0.15 s), GDI 0.05 s, a 0.2 s proof. Counted from the dxcam wait it was 0.4 s: refused.
    The frame's own age at the write is 0.25 s."""
    lobby, clock = frame("lobby-cursor-on-practice"), Clock()
    live, calls, _ = make_live(monkeypatch, Screen(after=None), gdi=SlowGdi(clock, 0.05, after=lobby), clock=clock)
    live.tap("A", screen="lobby", proof_fn=slow(R.on_practice_tab, clock, 0.2))
    assert presses(calls) == ["A"]


def test_a_genuinely_stale_gdi_proof_is_still_refused(monkeypatch):
    lobby, clock = frame("lobby-cursor-on-practice"), Clock()
    live, calls, _ = make_live(monkeypatch, Screen(after=None), gdi=SlowGdi(clock, 0.05, after=lobby), clock=clock)
    with pytest.raises(R.Refuse, match="the proof is 0.3[0-9] s old"):
        live.tap("A", screen="lobby", proof_fn=slow(R.on_practice_tab, clock, 0.28))   # 0.05 + 0.28 past the GDI grab's start
    assert touched(calls) == []


def test_the_timing_dry_run_runs_the_real_tap_path_and_opens_no_pad(monkeypatch):
    """The timing must be the number a press would see, so it runs Safe.press -> Live.tap's own code over a pad that is not there."""
    monkeypatch.setitem(sys.modules, "vgamepad", None)                               # importing vgamepad now raises: no device can be made
    lobby, clock = frame("lobby-cursor-on-practice"), Clock()
    cap = Screen(after=None)
    cap.grab = lambda: (setattr(clock, "t", clock.t + 0.01), None)[1]               # dxcam: nothing new, 10 ms a poll
    lines = []
    rows = R.timings(cap, SlowGdi(clock, 0.05, after=lobby), 2, clock=clock, sleep=clock.sleep, log=lines.append)
    assert [r["refused"] for r in rows] == ["no", "no"] and all(r["screen"] == "lobby" for r in rows)
    assert rows[0]["tap_gdi_ms"] == pytest.approx(50) and rows[0]["tap_frame_ms"] >= 150        # the tap's own frame: dxcam wait + GDI
    assert rows[0]["age_ms"] == pytest.approx(50, abs=1)                                         # GDI start to the write
    assert "limit 300 ms" in lines[-1]


def test_the_timing_reports_a_refusal_the_real_tap_would_make(monkeypatch):
    monkeypatch.setitem(sys.modules, "vgamepad", None)
    lobby, clock = frame("lobby-cursor-on-practice"), Clock()
    monkeypatch.setitem(R.PROOFS, "lobby", slow(R.on_practice_tab, clock, 0.3))
    rows = R.timings(Screen(after=None), SlowGdi(clock, 0.05, after=lobby), 1, clock=clock, sleep=clock.sleep, log=lambda *_: None)
    assert "s old" in rows[0]["refused"] and rows[0]["age_ms"] == pytest.approx(350, abs=1)
    assert rows[0]["tap_proof_ms"] == pytest.approx(300, abs=1)
    assert R.classify.__name__ == "classify"                                         # the real classify is back after the timing


def test_the_dxcam_probe_counts_frames_and_gaps():
    clock, n = Clock(), [0]

    def grab():
        clock.t += 0.001
        n[0] += 1
        return frame("lobby-cursor-far") if n[0] % 100 == 0 else None               # a frame every 100 ms
    cap, lines = Screen(), []
    cap.grab = grab
    got = R.dxcam_probe(cap, 1.0, clock=clock, log=lines.append)
    assert len(got) in (9, 10) and "gap p50 100 ms" in lines[0] and "first after 100 ms" in lines[0]


class ReachedPad(Exception):
    pass


@pytest.mark.parametrize("argv", [["--timing", "0"], ["--timing", "-1"], ["--timing", "3"],
                                  ["--dry-run", "--timing", "0"], ["--dry-run", "--timing", "-1"],
                                  ["--dry-run", "--timing", "3", "--frame", str(FIX / "lobby-cursor-far.jpg")],
                                  ["--frame", ""], ["--timing", "0", "--frame", ""]])
def test_a_diagnostic_flag_can_never_route_to_a_live_run(argv):
    """Input-safety review: `--timing 0` was falsy, skipped both checks and fell through to the LIVE path. Every bad combination is an argparse
    error before any capture or pad is constructed."""
    touched = []

    def capture():
        touched.append("capture")
        return Screen(after=frame("lobby-cursor-far"))

    def live(*a, **k):
        raise ReachedPad(argv)

    with pytest.raises(SystemExit) as e:
        R.main(argv, capture=capture, live=live)
    assert e.value.code == 2 and touched == []


def test_the_timing_dry_run_through_main_times_and_opens_no_pad(monkeypatch, capsys):
    import types
    lobby = frame("lobby-cursor-on-practice")
    monkeypatch.setitem(sys.modules, "capture", types.SimpleNamespace(Capture=lambda backend: Screen(after=lobby)))
    monkeypatch.setitem(sys.modules, "vgamepad", None)
    monkeypatch.setattr(R, "dxcam_probe", lambda cap: print("reenter: dxcam probe stub"))
    assert R.main(["--dry-run", "--timing", "2"], capture=lambda: Screen(after=None),
                  live=lambda *a, **k: (_ for _ in ()).throw(ReachedPad())) == 0
    out = capsys.readouterr().out
    assert "dxcam probe stub" in out and out.count("reenter: timing screen=lobby") == 2 and "limit 300 ms" in out



# --- live 2026-09-21 09:41: the first hero-select frame refused, "hero tab None" (the screen was fading in) -------------------------------
def test_the_active_tab_is_unreadable_while_the_screen_fades_in_and_readable_once_settled():
    """The saved live frame: the active tab's white reads 192 of 255 at game clock 00:02 against 250 settled; the pad's LB / RB glyphs sit
    outside the tab boxes. The reader stays strict; the flow waits instead."""
    assert R.classify(frame("heroselect-all-tab-fading-in")) == "hero_select" and R.hero_tab(frame("heroselect-all-tab-fading-in")) is None
    assert R.hero_tab(frame("heroselect-all-tab-settled")) == "all"


class Fading(Sim):
    """Hero select opening: `dim` fresh frames of the fading-in screen, then the settled one."""

    def __init__(self, dim, table=None, after="hero_settled"):
        super().__init__("hero_fading", table or {}, {})
        self.dim, self.after = dim, after

    def frame(self):
        if self.state == "hero_fading":
            if self.dim <= 0:
                self.state = self.after
            self.dim -= 1
        return super().frame()


def test_settle_looks_again_on_fresh_frames_sending_nothing_and_reads_the_tab_once_it_is_drawn():
    sim = Fading(dim=5)
    f, tab = R.settle(sim, "hero_select", R.hero_tab)
    assert tab == "all" and sim.inputs == [] and sim.t <= R.SETTLE_S


def test_settle_gives_up_after_its_bound_and_the_run_still_refuses_with_nothing_sent():
    sim = Fading(dim=10 ** 6)                                          # never readable
    with pytest.raises(R.Refuse, match="hero tab None is not recognised"):
        R.run(sim, log=lambda *_: None)
    assert sim.inputs == [] and R.SETTLE_S <= sim.t <= R.SETTLE_S + 1.0
    assert R.SETTLE_S <= 3.0                                           # the look is bounded, not a new way to wait on an unreadable screen


def test_settle_refuses_if_the_screen_changes_while_it_looks():
    sim = Fading(dim=3, after="lobby_far")
    with pytest.raises(R.Refuse, match="screen changed to lobby"):
        R.settle(sim, "hero_select", R.hero_tab)
    assert sim.inputs == []


def test_a_run_from_the_fading_in_hero_select_presses_rb_only_after_the_tab_is_read():
    sim = Fading(dim=4, table={("hero_settled", "RB"): lambda n: "hero_duel" if n >= 2 else "hero_settled",
                               ("hero_duel", "stick"): "hero_spider", ("hero_spider", "X"): "loading_range",
                               ("loading_range", "loaded"): "spawn",
                               ("spawn", "stick"): lambda n: "range" if n >= 3 else "spawn"})
    sim.loading = {"loading_range": 2}
    R.run(sim, log=lambda *_: None)
    taps = [(b, s_) for b, s_, _ in sim.taps()]
    assert taps[:2] == [("RB", "hero_select"), ("RB", "hero_select")] and ("A", "hero_select") in taps
    assert_only_safe_inputs(sim)


# --- the arrival log (a record for the live measurement; it must change nothing) -------------------------------------------------------
ARRIVALS = {
    "door ahead": lambda: _pose_sim("p_ahead", WALK_OUT),
    "console": lambda: _pose_sim("p_console", {**WALK_OUT, ("p_console", "rstick"): "p_on"}),
    "first spawn": lambda: _pose_sim("p_first", {**WALK_OUT, ("p_first", "rstick"): "p_on"}),
    "wall": lambda: _pose_sim("p_wall", {**WALK_OUT, ("p_wall", "rstick"): lambda n: "p_console" if n >= 2 else "p_wall",
                                         ("p_console", "rstick"): "p_on"}),
    "wall, never out": lambda: _pose_sim("p_wall", {}),
    "glass, never through": lambda: _pose_sim("p_ahead", {}),
    "turn to the side": lambda: TurnSim(0.15),
    "HUD gone": lambda: Sim("spawn", {("spawn", "stick"): "blackout"}),
    "flicker": lambda: Flicker(),
}


def _arrive_inputs(sim, trace):
    try:
        R.arrive(sim, R.Safe(sim, log=lambda *_: None), trace)
        end = "done"
    except R.Refuse as r:
        end = r.reason
    return sim.inputs, sim.t, end


class Broken:
    """A recorder whose every call fails."""
    def step(self, *a, **k):
        raise OSError("disk gone")


@pytest.mark.parametrize("name", sorted(ARRIVALS))
def test_the_arrival_log_changes_no_input(name, tmp_path):
    """The same pad writes, in the same order, at the same (simulated) times, and the same ending, with the log off, on, and failing."""
    off = _arrive_inputs(ARRIVALS[name](), None)
    on = _arrive_inputs(ARRIVALS[name](), R.ArrivalLog(tmp_path))
    unwritable = tmp_path / "a-file"
    unwritable.write_text("")
    failing = _arrive_inputs(ARRIVALS[name](), R.ArrivalLog(unwritable))          # its directory cannot be made
    broken = _arrive_inputs(ARRIVALS[name](), Broken())
    assert on == off and failing == off and broken == off


def test_the_arrival_log_records_each_step_with_its_frame_and_gate(tmp_path):
    log = R.ArrivalLog(tmp_path)
    sim = ARRIVALS["console"]()
    R.arrive(sim, R.Safe(sim, log=lambda *_: None), log)
    rows = [json.loads(l) for l in (log.dir / "steps.jsonl").read_text().splitlines()]
    assert [r["n"] for r in rows] == list(range(1, len(rows) + 1)) and log.failed == 0
    assert rows[0]["action"].startswith("door off his column: turn") and rows[0]["door_blob_x"] < R.HERO_X
    assert rows[0]["door_px"] >= R.DOOR_MIN_PX
    assert any(r["action"].startswith("door on his column: walk") for r in rows) and rows[-1]["action"] == "RT pressed once"
    assert all(r["gate"] == R.ARRIVAL_GATE and (log.dir / r["frame"]).exists() for r in rows)
    assert all(r["hero_x"] is None or 0.3 < r["hero_x"] < 0.5 for r in rows)


def test_a_refused_arrival_is_recorded_and_still_refuses(tmp_path):
    log = R.ArrivalLog(tmp_path)
    sim = ARRIVALS["HUD gone"]()
    with pytest.raises(R.Refuse, match="range HUD is gone"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None), log)
    rows = [json.loads(l) for l in (log.dir / "steps.jsonl").read_text().splitlines()]
    assert rows[-1]["action"] == "refused: the range HUD is gone"


def test_a_failing_log_is_counted_not_raised(tmp_path):
    f = tmp_path / "a-file"
    f.write_text("")
    log = R.ArrivalLog(f)
    log.step(0.0, frame("arrival-spawn-room"), "walk")
    assert log.failed == 1 and log.error and "write failures" in log.summary()


# --- the out state, the hero's column and the door kept (the live arrival of 2026-09-21 12:24, docs/evidence/l4/arrival-20260921-*) ----
def test_through_the_door_it_never_steers_to_a_door_again_and_looks_left():
    """Live: step 15 walked at the pane (33k px), step 16 showed none (the plaza-side planter): out. Then the old logic walked at a sliver
    of the pane seen from outside (step 17) and at the whole pane (steps 20-23) back into the spawn room. Out, only left turns."""
    m = R.ArrivalMemory(walked=True, walks=[33000])
    assert R.arrival_step(frame("arrival-live-out-planter"), m)[:3] == ("turn", -R.YAW_STICK, R.SWEEP_S) and m.out
    for name in ("arrival-live-out-pane-sliver", "arrival-live-out-pane"):
        assert R.door(frame(name)) is not None                                   # a door is in view
        assert R.arrival_step(frame(name), m)[:2] == ("turn", -R.YAW_STICK), name   # and is not steered to
    assert R.arrival_step(frame("arrival-plaza-bot-ahead"), m)[0] == "plaza?"


def test_a_door_that_leaves_the_view_by_a_turn_or_a_small_one_is_not_passing_through():
    m = R.ArrivalMemory(walked=False, walks=[33000])                              # turned, not walked
    R.arrival_step(frame("arrival-live-out-planter"), m)
    assert not m.out
    m = R.ArrivalMemory(walked=True, walks=[R.OUT_PX - 1])                        # walked at a small, far door
    R.arrival_step(frame("arrival-live-out-planter"), m)
    assert not m.out


def test_outside_with_no_bot_it_turns_left_a_bounded_number_of_times_then_refuses():
    sim = _pose_sim("p_on", {("p_on", "stick"): "outside"})
    big = lambda: spawn_frame(width=240)                                         # a door on his column, well over OUT_PX
    sim.FRAMES = dict(sim.FRAMES, p_on=big, outside="arrival-live-out-planter")
    with pytest.raises(R.Refuse, match="out, but no bot in view"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    kinds = [(i[0], i[1]) for i in sim.inputs]
    assert kinds == [("stick", 0.0)] + [("rstick", -R.YAW_STICK)] * R.OUT_SWEEPS         # one walk through, then left turns only


def test_the_pane_is_steered_onto_the_heros_column_not_the_screen_centre():
    """Live step 21 (and the four refusals): the pane centred on the screen (0.54) with him at 0.39, on the dark jamb left of it."""
    act = R.arrival_step(frame("arrival-live-jamb"), R.ArrivalMemory())
    assert act[0] == "turn" and act[1] > 0                                       # right, which moves the pane left onto his column


def test_a_door_being_walked_at_is_kept_when_a_bigger_one_comes_into_view():
    """Live steps 1-5: two lime doors in view, the biggest blob jumped between them and the steering with it."""
    f = frame("arrival-live-two-doors-left-bigger")                               # the kept door at 0.48, a bigger one at 0.12
    assert R.arrival_step(f, R.ArrivalMemory(chosen=0.47))[0] == "walk"
    far = R.ArrivalMemory(chosen=0.14)                                            # kept: the other door, bigger and far off his column
    assert R.arrival_step(f, far)[:2] == ("turn", -R.YAW_STICK)                   # turns to the kept one
    assert R.arrival_step(f, R.ArrivalMemory())[0] == "walk"                     # nothing kept: the one on his column, not the bigger


def test_at_spawn_the_door_on_his_column_is_taken_not_the_bigger_one():
    """Three supervised arrivals (2026-09-21): in two the other lime door was the bigger blob in frame 1 (8.2k at x 0.21 against the plaza
    door's 3.5k at 0.44; 7.3k against 5.6k); he took it, went through, and walked back in. On all four logged spawns the plaza door sits
    0.04 from his column and the other 0.19 off."""
    for name in ("arrival-live-spawn-other-door-bigger-1", "arrival-live-spawn-other-door-bigger-3"):
        f = frame(name)
        assert R.door_blobs(f)[0][0] < 0.3                                        # the bigger blob is the other door, on the left
        m = R.ArrivalMemory()
        assert R.arrival_step(f, m)[0] == "walk" and abs(m.chosen - 0.44) < 0.03, name


def test_out_is_the_panes_peak_over_its_last_walks_not_its_last_size():
    """The pane shrinks as he reaches it: arrival 3 walked at 16.0k, 15.7k, then 7.6k px, and the next frame had no door. The last walk
    alone (under OUT_PX) missed it; the peak of the last OUT_WALKS walks does not. A big peak older than that does not count."""
    through = frame("arrival-live-through-other-door")
    assert R.door(through) is None
    m = R.ArrivalMemory(walked=True, walks=[16011, 15701, 7628])
    R.arrival_step(through, m)
    assert m.out
    m = R.ArrivalMemory(walked=True, walks=[50000, 3000, 3000, 3000])
    R.arrival_step(through, m)
    assert not m.out


# --- a walk that does not move him (2026-09-21 14:01: 16 walks into the central console's rim, the door on his column throughout) ------
def _moved(a, b):
    return float(np.mean(np.abs(R._scene(frame(b)) - R._scene(frame(a)))))


def test_a_walk_into_the_rim_changes_nothing_a_walk_that_advances_or_slides_off_does():
    assert _moved("arrival-live-rim-a", "arrival-live-rim-b") < R.STILL / 2                    # 3 on the stuck steps
    assert _moved("arrival-live-brush-a", "arrival-live-brush-b") > R.STILL                    # brushed the rim, slid off: 11
    assert _moved("arrival-live-advance-a", "arrival-live-advance-b") > 2 * R.STILL            # advancing: 21-47 on the seven logs


def test_walking_into_something_sidesteps_left_a_bounded_number_of_times_then_refuses():
    sim = Sim("spawn", {})
    sim.stuck = True
    with pytest.raises(R.Refuse, match="walking does not move him"):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    walk, left = ("stick", 0.0, 1.0), ("stick", -1.0, 0.0)
    assert sim.inputs == [walk, walk, left, walk, walk, left, walk, walk]         # two walks unchanged, a sidestep; twice; then stop


class RimSim(Sim):
    """Stuck on the rim until a sidestep left; then walking moves him, and three walks take him out."""

    def __init__(self):
        super().__init__("spawn", {})
        self.stuck, self.after = True, 0

    def stick(self, x, y, secs, screen=None):
        super().stick(x, y, secs)
        if x < 0:
            self.stuck = False
        elif not self.stuck:
            self.after += 1
            if self.after >= 3:
                self.state = "range"


def test_a_sidestep_off_the_rim_lets_the_walk_carry_on_out():
    sim = RimSim()
    R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    sticks = [(i[1], i[2]) for i in sim.inputs if i[0] == "stick"]
    assert sticks == [(0.0, 1.0), (0.0, 1.0), (-1.0, 0.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0)] and sim.inputs[-1][0] == "RT"


class HalfStuckSim(Sim):
    """Every other walk moves him (a scuff, then a step): never two unchanged walks in a row."""

    def moving(self, f):
        if f is BLACK or self.state != "spawn":
            return f
        g = f.copy()
        g[300:800, 1800:2500] = 255 * ((self.walked // 2) % 2)
        return g


def test_only_unchanged_walks_in_a_row_are_no_progress():
    sim = HalfStuckSim("spawn", {})
    with pytest.raises(R.Refuse, match="could not confirm"):                      # the budget, not no-progress
        R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    assert all(i[1] == 0.0 for i in sim.inputs if i[0] == "stick")               # never a sidestep


def test_a_plaza_pause_after_an_advancing_walk_is_neither_a_walk_nor_a_stall(monkeypatch):
    """Review of cac94bd: walk 1 blocked (unchanged view), walk 2 advanced by 30 onto a plaza-looking frame (a second look, standing
    still), then the pause's near-identical frame no longer looked like the plaza: the advance had been skipped and the pause counted as a
    second failed walk, so it sidestepped. Each walk's evidence is used exactly once, and a pause is not a walk."""
    scenes = iter(np.full((68, 160), v, np.float32) for v in (0, 0, 30, 30))
    plaza = iter((False, False, True, False))
    monkeypatch.setattr(R, "_scene", lambda f: next(scenes))
    monkeypatch.setattr(R, "plaza_view", lambda f: next(plaza))
    monkeypatch.setattr(R, "door_blobs", lambda f: [(0.40, 6000)])
    m = R.ArrivalMemory()
    acts = [R.arrival_step(None, m)[0] for _ in range(4)]
    assert acts == ["walk", "walk", "plaza?", "walk"] and m.sidesteps == 0
    assert m.still == 0 and m.moved is None                                     # the advance cleared the stall; the pause was not a walk


def test_the_log_records_the_scene_change_the_decision_used(tmp_path):
    log = R.ArrivalLog(tmp_path)
    sim = Sim("spawn", {})
    sim.stuck = True
    with pytest.raises(R.Refuse):
        R.arrive(sim, R.Safe(sim, log=lambda *_: None), log)
    rows = [json.loads(l) for l in (log.dir / "steps.jsonl").read_text().splitlines()]
    assert rows[0]["moved"] is None and rows[0]["still"] == 0                   # no walk before the first decision
    assert rows[1]["moved"] is not None and rows[1]["moved"] < R.STILL and rows[1]["still"] == 1
    assert rows[2]["action"].startswith("no progress: sidestep left") and rows[2]["still"] == R.STILL_WALKS   # what it acted on
    assert rows[3]["moved"] is None                                             # after a sidestep: not a walk


def _scripted(monkeypatch, scenes, plazas, blobs):
    scenes, plazas, blobs = iter(scenes), iter(plazas), iter(blobs)
    monkeypatch.setattr(R, "_scene", lambda f: np.full((68, 160), next(scenes), np.float32))
    monkeypatch.setattr(R, "plaza_view", lambda f: next(plazas))
    monkeypatch.setattr(R, "door_blobs", lambda f: next(blobs))


def test_a_crossing_frame_that_looks_like_the_plaza_still_latches_out(monkeypatch):
    """Review of bc6f8b4: walk at a 20k door; the next frame has no door and looks like the plaza (a second look); the one after has no
    door and no plaza. The plaza's early return had dropped the crossing, so it searched right and walked at the pane's returning sliver:
    the walk-back the out state exists to prevent. The crossing is latched before the plaza returns; the plaza still acts first."""
    _scripted(monkeypatch, (0, 30, 30, 40), (False, True, False, False), ([(0.40, 20000)], [], [(0.40, 4000)]))
    m = R.ArrivalMemory()
    acts = [R.arrival_step(None, m) for _ in range(4)]
    assert [a[0] for a in acts[:2]] == ["walk", "plaza?"] and m.out
    assert [a[:2] for a in acts[2:]] == [("turn", -R.YAW_STICK)] * 2                # left, never back at the sliver


def test_a_crossing_frame_that_is_the_plaza_confirms_on_the_next_frame(monkeypatch):
    _scripted(monkeypatch, (0, 30, 30), (False, True, True), ([(0.40, 20000)], []))
    m = R.ArrivalMemory()
    assert [R.arrival_step(None, m)[0] for _ in range(3)] == ["walk", "plaza?", "done"] and m.out


# --- the cursor search, made cheaper (a live A refused at 0.31 / 0.32 s against the 0.3 s limit, the proof ~ all cursor search) ----------
# The version before, verbatim, as the reference: the search must answer exactly as it did, on every frame.
def _ref_ring_score(white, x, y):
    """Contrast of a cursor-sprite signature centred at (x, y), or 0. Needs a ring bright ALL the way round."""
    h, w = white.shape
    xs = np.clip((x + R._R[:, None] * R._COS).round().astype(int), 0, w - 1)
    ys = np.clip((y + R._R[:, None] * R._SIN).round().astype(int), 0, h - 1)
    v = white[ys, xs].astype(float)              # (radius, angle)
    mean, p20 = v.mean(axis=1), np.percentile(v, 20, axis=1)
    dot = mean[:3].mean()
    ra = 16 + int(p20[16:23].argmax())
    contrast_a = p20[ra] - mean[ra + 4:ra + 8].mean()
    rb = 23 + int(p20[23:31].argmax())
    contrast_b = p20[rb] - mean[min(rb + 4, 33):min(rb + 8, 35)].mean()
    hover = dot >= R.CURSOR_HOVER["dot"] and p20[ra] >= R.CURSOR_HOVER["ring"] and contrast_a >= R.CURSOR_HOVER["contrast"]
    plain = p20[rb] >= R.CURSOR_PLAIN["ring"] and contrast_b >= R.CURSOR_PLAIN["contrast"]
    return max(contrast_a if hover else 0.0, contrast_b if plain else 0.0)


def _ref_find_cursor(frame):
    """(x, y) of the pad cursor in 1280x720 px, or None. None is also the answer for a faint ring over dark art.

    Candidate centres are the strongest matches of a white ring (of each sprite radius) against the mask of bright-in-every-channel
    pixels, then judged by the ring signature, which is sharply peaked (one pixel off, its contrast falls from 130 to 50), so each is
    refined over a +-2 px window first. The first version took its candidates from a Hough transform, whose strongest circles on a
    busy portrait or a slightly noisy frame are other things: the ring was missed one frame in three, and a live run refused on hero
    select with the cursor sitting on Spider-Man."""
    s = R.small(frame)
    white = s.min(axis=2)  # bright only where bright in every channel: the sprite, not coloured art
    mask = cv2.resize((white > 190).astype(np.float32), None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    best = (0.0, 0, 0)
    for r in R.RING_R:
        t = R._ring_template(r)
        resp = cv2.matchTemplate(mask, t, cv2.TM_CCOEFF_NORMED)
        resp = np.nan_to_num(resp, nan=0.0, posinf=0.0, neginf=0.0)
        for _ in range(R.PEAKS):
            _, top, _, (px, py) = cv2.minMaxLoc(resp)
            if top < R.PEAK_MIN:
                break
            cx, cy = 2 * (px + t.shape[1] // 2), 2 * (py + t.shape[0] // 2)   # back to full size
            resp[max(0, py - 6):py + 7, max(0, px - 6):px + 7] = 0
            for dy in range(-R.REFINE_PX, R.REFINE_PX + 1):
                for dx in range(-R.REFINE_PX, R.REFINE_PX + 1):
                    score = _ref_ring_score(white, cx + dx, cy + dy)
                    if score > best[0]:
                        best = (score, cx + dx, cy + dy)
    return (float(best[1]), float(best[2])) if best[0] > 0 else None


def _cursor_frames():
    rng = np.random.default_rng(0)
    out = []
    for p in sorted(Path("tests/fixtures").rglob("*.jpg")) + sorted(Path("tests/fixtures").rglob("*.png")):
        f = cv2.imread(str(p))
        if f is None or abs(f.shape[1] * 9 - f.shape[0] * 16) > 16:
            continue
        out.append((p.name, f))
        if _ref_find_cursor(f) is not None:                                    # and the ring frames made noisier and more compressed
            out += [(f"{p.name} noise{s}", np.clip(f.astype(float) + rng.normal(0, s, f.shape), 0, 255).astype(np.uint8)) for s in (3, 8, 12)]
            out += [(f"{p.name} jpeg{q}", cv2.imdecode(cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)) for q in (80, 50)]
    return out


def test_the_cheaper_cursor_search_answers_exactly_as_before():
    frames = _cursor_frames()
    assert sum(_ref_find_cursor(f) is not None for _, f in frames) >= 30                   # the rings are really there
    assert [R.find_cursor(f) for _, f in frames] == [_ref_find_cursor(f) for _, f in frames]


def test_every_ring_score_is_bit_identical_to_the_one_centre_version():
    rng = np.random.default_rng(1)
    for name in ("panel-cursor-on-practice-range", "lobby-cursor-on-practice", "heroselect-spiderman-tooltip-ring-lost"):
        white = R.small(frame(name)).min(axis=2)
        cx, cy = (int(v) for v in R.find_cursor(frame(name)))
        xs = np.r_[cx + np.repeat(np.arange(-3, 4), 7), rng.integers(0, 1280, 200), 0, 1279]
        ys = np.r_[cy + np.tile(np.arange(-3, 4), 7), rng.integers(0, 720, 200), 0, 719]
        assert (R._ring_scores(white, xs, ys) == np.array([_ref_ring_score(white, x, y) for x, y in zip(xs, ys)])).all(), name


def test_a_press_prints_its_age_and_stages_after_the_write(monkeypatch):
    """Printed after the input and its settle, never between the proof and the write; a refused press writes and prints nothing."""
    lobby = frame("lobby-cursor-on-practice")
    live, calls, _ = make_live(monkeypatch, Screen(lobby, after=lobby))
    monkeypatch.setattr(R, "print", lambda *a, **k: calls.append(("print", " ".join(map(str, a)), {})), raising=False)
    live.tap("A", screen="lobby", proof_fn=R.on_practice_tab)
    kinds = [c[0] for c in calls]
    assert "press_button" in kinds and kinds[-1] == "print" and kinds.count("print") == 1
    out = calls[-1][1]
    assert re.search(r"A written at proof age \d+ ms \(limit 300\): grab \d+ ms \((dxcam|GDI)\), classify \d+, proof \d+, checks \d+", out)
    live, calls, _ = make_live(monkeypatch, Screen(lobby, after=lobby))
    monkeypatch.setattr(R, "print", lambda *a, **k: calls.append(("print", a, {})), raising=False)
    with pytest.raises(R.Refuse):
        live.tap("A", screen="lobby", proof_fn=lambda f: R.Proof(False, "no"))
    assert not touched(calls)


def test_the_ring_signature_matches_at_its_window_edges_on_a_built_sprite():
    """A plain ring at radius 30, where the outer window is clipped (33-35): random centres on real frames almost never light it."""
    yy, xx = np.mgrid[0:720, 0:1280]
    d = np.hypot(xx - 640, yy - 360)
    white = np.zeros((720, 1280), np.uint8)
    white[(d > 29.4) & (d < 30.6)] = 255
    white[(d > 32.5) & (d < 33.5)] = 120
    white[(d > 33.5) & (d < 34.5)] = 20
    xs, ys = np.r_[640 + np.arange(-2, 3), 640], np.r_[np.full(5, 360), 361]
    new = R._ring_scores(white, xs, ys)
    assert (new == np.array([_ref_ring_score(white, x, y) for x, y in zip(xs, ys)])).all() and new.max() > 0


def test_two_equally_good_rings_resolve_to_the_same_one_as_before():
    """The first best in the order the candidates were found wins, as it did: the real cursor copied to a second place ties exactly."""
    f = R.small(frame("panel-cursor-on-practice-range")).copy()                 # at 1280 x 720 the copy is pixel for pixel
    x, y = (int(v) for v in R.find_cursor(f))
    cx, cy = 300 + x % 2, 300 + y % 2                                              # the same parity: the ring's samples round alike
    f[cy - 40:cy + 40, cx - 40:cx + 40] = f[y - 40:y + 40, x - 40:x + 40]
    white = f.min(axis=2)
    assert _ref_ring_score(white, cx, cy) == _ref_ring_score(white, x, y) > 0                    # a real tie
    assert R.find_cursor(f) == _ref_find_cursor(f)
