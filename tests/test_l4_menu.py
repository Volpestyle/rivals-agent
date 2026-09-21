"""scripts/l4_menu.Menu and scripts/l4_practice_settings: every input needs fresh, positive proof (VUH-1325)."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import l4_menu as M  # noqa: E402
import l4_practice_settings as PS  # noqa: E402
from record import in_range  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def img(rel):
    f = cv2.imread(str(FIX / rel))
    assert f is not None, rel
    return f


RANGE, LOBBY = img("reentry/in-range.jpg"), img("reentry/lobby-cursor-far.jpg")
PAUSE_SET, PAUSE_PS = img("menus/pause-settings-lit.jpg"), img("menus/pause-practice-lit.jpg")
PS_OPEN, PS_NAC, PS_OFF, PS_CO = (img(f"menus/ps-{n}.jpg") for n in ("open", "on-nac-switch", "nac-off", "on-controller-operation"))
LEAVE = img("menus/leave-dialog.jpg")
BLACK, WHITE = np.zeros((720, 1280, 3), np.uint8), np.full((720, 1280, 3), 255, np.uint8)
OTHERS = {"lobby": LOBBY, "black": BLACK, "white": WHITE, "hero": img("reentry/heroselect-cursor-on-spiderman.jpg"),
          "panel": img("reentry/panel-cursor-on-practice-range.jpg"), "board": img("range/neg-scoreboard.jpg")}


class Pad:
    def __init__(self):
        self.held, self.reports = {}, []

    def reset(self):
        self.held = {}

    def press_button(self, button):
        self.held[button] = 1

    def left_joystick_float(self, x, y):
        self.held["ls"] = (x, y)

    def right_joystick_float(self, x, y):
        self.held["rs"] = (x, y)

    def left_trigger_float(self, v):
        self.held["lt"] = v

    def right_trigger_float(self, v):
        self.held["rt"] = v

    def update(self):
        self.reports.append(dict(self.held))

    def pressed(self):
        return [k for r in self.reports for k in r]


class Screen:
    """A scripted screen: `frames` is what each successive grab returns (the last one repeats)."""

    def __init__(self, *frames):
        self.frames, self.grabs = list(frames), 0

    def grab(self):
        self.grabs += 1
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    monkeypatch.setattr(PS.time, "sleep", lambda s: None)


def menu(check, *frames):
    scr, pad = Screen(*frames), Pad()
    return M.Menu(check, grab=scr.grab, pad=pad, settle_s=0), scr, pad


def test_each_screen_matches_only_itself():
    table = {"range": [RANGE], "pause": [PAUSE_SET, PAUSE_PS], "practice_settings": [PS_OPEN, PS_NAC, PS_OFF, PS_CO], "leave_dialog": [LEAVE]}
    for name, check in M.SCREENS.items():
        for other, frames in table.items():
            for f in frames:
                assert bool(check(f)) == (name == other), (name, other)
        for label, f in OTHERS.items():
            assert not check(f), (name, label)
        assert not check(None)


def test_rows_are_read_only_on_their_own_screen():
    assert M.pause_row(PAUSE_PS) == "practice" and M.pause_row(PAUSE_SET) == "settings"
    assert all(M.pause_row(f) is None for f in (RANGE, PS_OPEN, LEAVE, *OTHERS.values()))
    assert PS.help_is_nac(PS_NAC) and not any(PS.help_is_nac(f) for f in (PS_OPEN, PS_CO, PAUSE_PS, RANGE, *OTHERS.values()))
    assert PS.toggle_on(PS_NAC) and not PS.toggle_on(PS_CO)


def test_start_is_refused_off_the_range_whatever_the_callers_check_says():
    m, _, pad = menu(lambda f: True, LOBBY)                       # the review's reproduction: a permissive check on the lobby
    with pytest.raises(M.Stop):
        m.send("START")
    assert pad.pressed() == []
    m, _, pad = menu(in_range, RANGE)
    m.send("START")
    assert "START" in pad.pressed() and pad.reports[-1] == {}


@pytest.mark.parametrize("tok", ["X", "BACK", "Y", "UP", "DOWN", "LEFT", "RIGHT", "hold:X,1", "hold:RIGHT,1", "nonsense"])
def test_tokens_outside_the_menu_vocabulary_send_nothing(tok):
    m, _, pad = menu(in_range, RANGE)
    with pytest.raises(M.Stop):
        m.send(tok)
    assert pad.pressed() == []


def test_proof_is_a_new_grab_after_every_input_and_no_grab_means_no_input():
    m, scr, pad = menu(M.on_pause, PAUSE_PS, PAUSE_PS, LOBBY)     # the screen changes after the first input
    g0 = scr.grabs
    m.send("ls:0,1,0.04")
    assert scr.grabs == g0 + 1
    with pytest.raises(M.Stop):                                   # the old code re-used the pause frame here and pressed A
        m.send("A")
    assert "A" not in pad.pressed()
    m, scr, pad = menu(M.on_pause, PAUSE_PS, None)
    with pytest.raises(M.Stop, match="grab returned nothing"):
        m.send("A")
    assert pad.pressed() == []


def test_a_slow_grab_is_stale_proof(monkeypatch):
    m, _, pad = menu(M.on_pause, PAUSE_PS)
    clock = [100.0]
    monkeypatch.setattr(M.time, "perf_counter", lambda: clock.__setitem__(0, clock[0] + 0.5) or clock[0])
    with pytest.raises(M.Stop, match="stale"):
        m.send("A")
    assert pad.pressed() == []


def test_an_interrupt_mid_press_leaves_the_pad_neutral(monkeypatch):
    m, _, pad = menu(M.on_pause, PAUSE_PS)
    monkeypatch.setattr(M.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()))
    for tok in ("A", "ls:1,0,0.5", "hold:A,2"):
        with pytest.raises(KeyboardInterrupt):
            m.send(tok)
        assert pad.reports[-1] == {} and any(r for r in pad.reports)      # it was held, and it was let go


def test_a_lost_cursor_sends_nothing():
    m, _, pad = menu(M.on_practice_settings, PS_OPEN)
    with pytest.raises(M.Stop, match="cursor not found"):
        m.goto(700, 127, locate=lambda f: None)
    assert pad.pressed() == []                                    # the old code jiggled the stick here


def test_the_page_is_opened_only_through_proven_screens():
    m, _, pad = menu(lambda f: in_range(f) or M.on_pause(f), RANGE, RANGE, RANGE, RANGE, RANGE, PAUSE_SET, PAUSE_SET, PAUSE_SET, PAUSE_PS, PAUSE_PS, PAUSE_PS, PAUSE_PS, PS_OPEN)
    PS.open_page(m)
    assert pad.pressed().count("START") == 1 and pad.pressed().count("A") == 1 and M.on_practice_settings(m.frame)


@pytest.mark.parametrize("label", sorted(OTHERS))
def test_no_confirm_when_the_screen_turns_into_anything_else(label):
    # pause menu up, and at the moment of the A the screen is the lobby / black / white / ... : nothing may be pressed
    m, _, pad = menu(M.on_pause, PAUSE_PS, PAUSE_PS, PAUSE_PS, OTHERS[label])
    with pytest.raises(M.Stop):
        PS.open_page(m)
    assert "A" not in pad.pressed() and "START" not in pad.pressed()


def test_the_switch_is_clicked_only_on_its_own_row_and_page():
    m, _, pad = menu(M.on_practice_settings, PS_CO)               # cursor elsewhere on the page: help names another row
    m.expect(PS.help_is_nac)
    with pytest.raises(M.Stop):
        m.send("A")
    assert "A" not in pad.pressed()
    m, _, pad = menu(M.on_practice_settings, PS_NAC)
    m.expect(PS.help_is_nac)
    m.send("A")
    assert pad.pressed().count("A") == 1


@pytest.mark.parametrize("label", sorted(OTHERS))
def test_closing_sends_nothing_from_an_unknown_screen(label):
    m, _, pad = menu(M.on_practice_settings, PS_OPEN, OTHERS[label])
    assert PS.close(m) is False and pad.pressed() == []           # the old finally block pressed B and walked here


def test_closing_backs_out_of_the_page_and_the_pause_menu():
    m, _, pad = menu(M.on_practice_settings, PS_OPEN, PS_OPEN, PS_OPEN, PS_OPEN, PAUSE_PS, PAUSE_PS, PAUSE_PS, RANGE)
    assert PS.close(m) is True and pad.pressed() == ["B", "B"]
