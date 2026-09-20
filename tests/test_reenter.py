"""scripts/reenter.py against the fixtures in tests/fixtures/reentry, a simulated cursor, a simulated game and a fake pad.

Needs opencv and numpy (`uv run --group perception pytest tests/test_reenter.py`). No game, no pad, no display.
"""
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
    assert f is not None and f.shape[:2] == (1440, 2560), name
    f.setflags(write=False)
    return f


def edited(name, paint):
    """A writable copy of a fixture with `paint(frame)` applied: the synthetic negatives."""
    f = frame(name).copy()
    paint(f)
    return f


def fill(f, box, bgr):  # box in 1280x720 px
    x0, y0, x1, y1 = (v * 2 for v in box)
    f[y0:y1, x0:x1] = bgr


BLACK = np.zeros((1440, 2560, 3), np.uint8)
NOISE = np.random.default_rng(0).integers(0, 255, (1440, 2560, 3), dtype=np.uint8)

SCREENS = {
    "lobby-cursor-far": "lobby", "lobby-cursor-left-of-practice": "lobby", "lobby-cursor-on-practice": "lobby",
    "lobby-cursor-on-try-competitive": "lobby", "lobby-cursor-at-try-competitive-corner": "lobby",
    "lobby-cursor-below-practice-tab": "lobby",
    "panel-cursor-on-practice-range": "practice_panel", "panel-cursor-off-tiles": "practice_panel",
    "heroselect-all-tab-black-panther": "hero_select", "heroselect-duelists-cursor-off": "hero_select",
    "heroselect-cursor-on-spiderman": "hero_select",
    "in-range": "in_range",
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
    off = R.on_spiderman(frame("heroselect-duelists-cursor-off"))  # the cursor is on the Punisher
    assert not off.ok and "not on the Spider-Man portrait" in off.reason
    black_panther = R.on_spiderman(frame("heroselect-all-tab-black-panther"))
    assert not black_panther.ok  # the all tab, and no cursor found
    monkeypatch.setattr(R, "find_cursor", lambda f: (852.0, 48.0))
    wrong_tab = R.on_spiderman(frame("heroselect-all-tab-black-panther"))
    assert not wrong_tab.ok and "not duelists" in wrong_tab.reason  # the right spot on the wrong tab
    other_hero = R.on_spiderman(edited("heroselect-cursor-on-spiderman", lambda f: fill(f, (812, 12, 896, 74), (60, 60, 60))))
    assert not other_hero.ok and "not Spider-Man" in other_hero.reason  # the right spot, but not his portrait


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
        "hero_duel": "heroselect-duelists-cursor-off", "hero_spider": "heroselect-cursor-on-spiderman", "range": "in-range",
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
        return frame(self.FRAMES[self.state]) if self.state in self.FRAMES else BLACK

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
    ("hero_duel", "stick"): "hero_spider", ("hero_spider", "X"): "loading_range", ("loading_range", "loaded"): "range",
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
    assert walked >= 6  # about 6 s of forward chunks
    assert any("Practice" not in l and l.startswith("reenter: A (") for l in lines)


def test_from_the_panel_it_carries_on_and_from_the_range_it_only_keeps_the_timer():
    sim = Sim("panel", HAPPY, LOADING)
    R.run(sim)
    assert sim.state == "range" and [b for b, _, _ in sim.taps()][0] == "A"
    in_range = Sim("range", {})
    R.run(in_range)
    assert [b for b, *_ in in_range.taps()] == ["RT"] and all(i[0] in ("stick", "RT") for i in in_range.inputs)


def test_arrival_stops_input_the_moment_the_range_hud_is_gone():
    sim = Sim("range", {("range", "stick"): "blackout"})  # the HUD vanishes after the first chunk of walking
    with pytest.raises(R.Refuse, match="range HUD is gone"):
        R.run(sim)
    assert [i[0] for i in sim.inputs] == ["stick"]  # one chunk, then nothing: no more walking, no attack


def test_arriving_as_another_hero_is_reported_not_hidden():
    other = edited("in-range", lambda f: fill(f, R.BOX["hud_hero"], (90, 90, 90)))
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
        "in-range": ["screen: in_range", "would walk forward ~6 s"],
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
