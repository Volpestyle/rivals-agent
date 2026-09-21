"""scripts/reenter.py against the fixtures in tests/fixtures/reentry, a simulated cursor, a simulated game and a fake pad.

Needs opencv and numpy (`uv run --group perception pytest tests/test_reenter.py`). No game, no pad, no display.
"""
import math
import random
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


def spawn_frame(door_x=0.5):
    """The recorded spawn room with the door painted out and a tall green door painted at `door_x` (fraction of the width)."""
    def paint(f):
        f[:600, :1200] = (60, 50, 55)
        x = int(door_x * 2560)
        f[240:840, max(0, x - 40):x + 40] = (88, 175, 64)
    return edited("arrival-spawn-room", paint)


BLACK = np.zeros((1440, 2560, 3), np.uint8)
NOISE = np.random.default_rng(0).integers(0, 255, (1440, 2560, 3), dtype=np.uint8)

SCREENS = {
    "lobby-cursor-far": "lobby", "lobby-cursor-left-of-practice": "lobby", "lobby-cursor-on-practice": "lobby",
    "lobby-cursor-on-try-competitive": "lobby", "lobby-cursor-at-try-competitive-corner": "lobby",
    "lobby-cursor-below-practice-tab": "lobby", "lobby-cursor-on-practice-tab-lower-half": "lobby",
    "panel-cursor-on-practice-range": "practice_panel", "panel-cursor-off-tiles": "practice_panel",
    "heroselect-all-tab-black-panther": "hero_select", "heroselect-duelists-cursor-off": "hero_select",
    "heroselect-cursor-on-spiderman": "hero_select", "heroselect-spiderman-tooltip-ring-lost": "hero_select",
    "in-range": "in_range", "arrival-spawn-room": "in_range", "arrival-plaza-bot-ahead": "in_range",
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
    monkeypatch.setattr(R, "find_cursor", lambda fr: None)                       # the live failure: no ring found
    p = R.on_spiderman(f)
    assert p.ok and "tooltip names SPIDER-MAN" in p.reason                       # ...and the press is still proven
    no_tip = edited(LOST, lambda g: fill(g, (850, 60, 1075, 100), (40, 30, 30)))
    p = R.on_spiderman(no_tip)                                                   # without the tooltip the ring is needed
    assert not p.ok and "no tooltip names SPIDER-MAN" in p.reason


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
    assert positives == {"heroselect-cursor-on-spiderman", LOST}, scores
    assert max(v for n, v in scores.items() if n not in positives) < 0.6, scores    # a wide gap: 0.49 at most, 0.92 at least
    assert R.tooltip_spiderman(BLACK) < 0.3 and R.tooltip_spiderman(NOISE) < 0.3
    assert R.tooltip_spiderman(frame("heroselect-duelists-cursor-off")) < 0.4       # THE PUNISHER's tooltip: similar font, another name
    rng = np.random.default_rng(1)
    for _ in range(4):                                                               # and it survives noise
        g = np.clip(frame(LOST).astype(float) + rng.normal(0, 6, frame(LOST).shape), 0, 255).astype(np.uint8)
        assert R.tooltip_spiderman(g) > 0.75


def test_steering_needs_no_ring_when_the_tooltip_already_says_the_cursor_is_on_spiderman():
    sim = SimCursor(640, 256)                                                        # a cursor whose ring is never found
    pos = R.steer(sim, R.SPIDER_SLOT, locate=lambda f: None, done=lambda f: True)
    assert pos is None and sim.sticks == 0                                           # nothing was sent: no jiggle, no nudge


def test_a_run_on_hero_select_carries_on_when_the_ring_is_lost_but_the_tooltip_names_spiderman(monkeypatch):
    """The live refusal, end to end: no ring anywhere, the tooltip on screen. No jiggle, no nudge: A on the tooltip's proof, then X."""
    monkeypatch.setattr(R, "find_cursor", lambda fr: None)
    sim = Sim("hero_lost", {("hero_lost", "X"): "loading_range", ("loading_range", "loaded"): "range"}, {"loading_range": 2})
    R.run(sim)
    assert [(b, s_) for b, s_, _ in sim.taps()] == [("A", "hero_select"), ("X", "hero_select"), ("RT", "in_range")]
    assert [i for i in sim.inputs if i[0] == "stick"] == []                      # nothing was steered: the tooltip said it was there


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

    def stick(self, x, y, secs):
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

    def stick(self, x, y, secs):
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
        pos = R.steer(sim, R.PRACTICE_TAB, locate=sim.locate)
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
    sim.stick = lambda x, y, secs: (orig(x, y, secs), positions.append(sim.y))
    assert R.PRACTICE_TAB.contains(R.steer(sim, R.PRACTICE_TAB, locate=sim.locate))
    assert sim.sticks <= 6, positions


@pytest.mark.parametrize("zone", [R.PRACTICE_TAB, R.RANGE_TILE, R.SPIDER_SLOT], ids=lambda z: z.name)
def test_steering_reaches_the_zone_from_anywhere_in_a_few_nudges(zone):
    for seed in range(12):
        rng = random.Random(seed)
        sim = SimCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, gain=rng.uniform(0.8, 1.2))
        pos = R.steer(sim, zone, locate=sim.locate)
        assert zone.contains(pos) and sim.sticks <= 16, (seed, sim.sticks)


def test_steering_corrects_y_when_x_is_already_on_target():
    """Regression: with x aligned and y a few px outside the zone, the loop once nudged x by nothing, forever."""
    for y in (391.4, 375.2, 389.9):
        sim = SimCursor(1212, y, gain=1.0)
        assert R.PRACTICE_TAB.contains(R.steer(sim, R.PRACTICE_TAB, locate=sim.locate))


@pytest.mark.parametrize("gain", [0.4, 0.6, 2.0, 2.5])
def test_steering_survives_a_cursor_much_faster_or_slower_than_assumed(gain):
    """The measured speed is rough (about 1.1x the assumed one): overshoot halves an axis' steps, slowness just takes more."""
    for seed in range(10):
        rng = random.Random(seed)
        sim = SimCursor(rng.uniform(40, 1240), rng.uniform(40, 680), rng, gain=gain)
        zone = (R.PRACTICE_TAB, R.RANGE_TILE, R.SPIDER_SLOT)[seed % 3]
        assert zone.contains(R.steer(sim, zone, locate=sim.locate))


def test_steering_is_bounded_when_the_cursor_never_moves():
    sim = SimCursor(640, 256, frozen=True)
    with pytest.raises(R.Refuse, match="did not reach the PRACTICE tab"):
        R.steer(sim, R.PRACTICE_TAB, locate=sim.locate)
    assert sim.sticks == R.MAX_STEPS


def test_steering_wiggles_to_find_a_hidden_cursor_then_gives_up():
    sim = SimCursor(1210, 383, hidden=2)  # hidden until the stick has moved twice (the wiggles move it too)
    pos = R.steer(sim, R.PRACTICE_TAB, locate=sim.locate)
    assert R.PRACTICE_TAB.contains(pos) and sim.sticks >= 3
    lost = SimCursor(640, 256, hidden=10**6)
    with pytest.raises(R.Refuse, match="cursor ring was not found"):
        R.steer(lost, R.PRACTICE_TAB, locate=lost.locate)
    assert lost.sticks == R.MAX_MISSES  # one wiggle per miss, and the last miss stops without another


# --- the whole flow against a simulated game --------------------------------------------------------------------------
class Sim:
    """A game and pad in one: serves fixture frames, and each input may move it to another state. Records every input
    with the screen and cursor a fresh frame showed at that moment."""

    def __init__(self, start, table, loading=None):
        self.state, self.table, self.t, self.inputs, self.n = start, table, 0.0, [], {}
        self.loading = dict(loading or {})  # state -> frames of black before the next state

    FRAMES = {
        "lobby_far": "lobby-cursor-far", "lobby_left": "lobby-cursor-left-of-practice", "lobby_on": "lobby-cursor-on-practice",
        "panel": "panel-cursor-on-practice-range", "hero_all": "heroselect-all-tab-black-panther",
        "hero_duel": "heroselect-duelists-cursor-off", "hero_spider": "heroselect-cursor-on-spiderman",
        "spawn": lambda: spawn_frame(0.5), "range": "arrival-plaza-bot-ahead",
        "hero_lost": "heroselect-spiderman-tooltip-ring-lost",
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
        return v() if callable(v) else frame(v)

    def _fire(self, event):
        key = (self.state, event)
        self.n[key] = self.n.get(key, 0) + 1
        rule = self.table.get(key)
        if rule is not None:
            self.state = rule(self.n[key]) if callable(rule) else rule

    def stick(self, x, y, secs):
        self.inputs.append(("stick", x, y))
        self.t += secs + 0.25
        self._fire("stick")

    def rstick(self, x, y, secs):
        self.inputs.append(("rstick", x, y))
        self.t += secs + 0.15
        self._fire("rstick")

    def tap(self, button):
        f = self.frame()
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
        return spawn_frame(self.door_x)

    def rstick(self, x, y, secs):
        super().rstick(x, y, secs)
        self.door_x -= 465.0 * math.radians(x / R.YAW_STICK * R.YAW_DEG_S * secs) / 1280.0   # turning right slides the door left

    def stick(self, x, y, secs):
        super().stick(x, y, secs)
        if abs(self.door_x - 0.5) <= 0.08:
            self.walks += 1


@pytest.mark.parametrize("door_x", [0.15, 0.3, 0.7, 0.85])
def test_arrival_turns_toward_a_door_off_to_one_side_before_it_walks(door_x):
    sim = TurnSim(door_x)
    R.arrive(sim, R.Safe(sim, log=lambda *_: None))
    kinds = [i[0] for i in sim.inputs]
    assert kinds[0] == "rstick" and math.copysign(1, sim.inputs[0][1]) == math.copysign(1, door_x - 0.5)   # turns TOWARD it
    assert "stick" not in kinds[:kinds.index("stick")] and kinds.count("rstick") <= 3 and kinds[-1] == "RT"
    assert abs(sim.door_x - 0.5) <= 0.08                                      # and walks only once it is ahead


class Flicker(Sim):
    """One frame that looks like the plaza (a glitch, a passing bot) between spawn-room frames: never two in a row."""

    def __init__(self):
        super().__init__("spawn", {})
        self.seq = [spawn_frame(0.5), frame("arrival-plaza-bot-ahead")] + [spawn_frame(0.5)] * 200

    def frame(self):
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


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
        "in-range": ["screen: in_range", "plaza with the bot ahead: no", "would walk toward the door"],
        "arrival-spawn-room": ["screen: in_range", "plaza with the bot ahead: no", "green door: centre x 0.2", "exit 1 if the plaza is not confirmed"],
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


def test_live_sends_only_the_buttons_it_supports_in_the_right_order(monkeypatch):
    mod, calls = fake_vgamepad()
    monkeypatch.setitem(sys.modules, "vgamepad", mod)
    live = R.Live(FakeCap(None), frame("lobby-cursor-far"), sleep=lambda s: None, settle_s=0)
    live.tap("A")
    assert [c[0] for c in calls] == ["press_button", "update", "release_button", "update"] and calls[0][2] == {"button": "A"}
    calls.clear()
    live.tap("X")
    live.tap("RB")
    assert [c[2]["button"] for c in calls if c[0] == "press_button"] == ["X", "RB"]
    calls.clear()
    live.stick(0.0, 1.0, 0.5)
    assert [(c[0], c[1]) for c in calls if c[0] == "left_joystick_float"] == [("left_joystick_float", (0.0, 1.0)),
                                                                              ("left_joystick_float", (0.0, 0.0))]
    calls.clear()
    live.tap("RT")
    assert [(c[0], c[1]) for c in calls if c[0] == "right_trigger_float"] == [("right_trigger_float", (1.0,)),
                                                                              ("right_trigger_float", (0.0,))]
    for forbidden in ("START", "UP", "B", "Y", "LB"):
        with pytest.raises(KeyError):
            live.tap(forbidden)
    assert live.frame(timeout=0.01) is frame("lobby-cursor-far")  # a static screen: the last frame stands
