"""Recorder combat commands and its device reports, entirely offline."""
import random
from types import SimpleNamespace

import cv2  # noqa: F401  record.py needs perception; skip the stdlib-only suite
import pytest

from agent.controller import NEUTRAL
from agent.pad_bindings import XUSB_NAMES, combat_controls
from scripts import record
from test_live_pad import FakePad


def test_record_routine_uses_alt_jump_team_up_and_pull_but_never_swing_or_menus():
    seen = set()
    routine = record.routine(random.Random(0))
    for _ in range(2000):
        label, _, changes = next(routine)
        buttons = set(changes.get("buttons", ()))
        assert not buttons & {"A", "X", "Y", "START", "BACK", "LS"}
        if label in ("jump", "team_up", "get_over_here"):
            assert buttons == {"jump": {"LB"}, "team_up": {"RS"}, "get_over_here": {"RB"}}[label]
            seen.add(label)
    assert seen == {"jump", "team_up", "get_over_here"}


def test_recorder_supports_thumb_clicks_and_writes_the_ultimate_atomically():
    pad = object.__new__(record.Pad)  # never construct a device or import vgamepad
    pad.pad = FakePad()
    pad.vg = SimpleNamespace(XUSB_BUTTON=SimpleNamespace(**{value: key for key, value in XUSB_NAMES.items()}))
    pad.state = dict(NEUTRAL)
    pad.set(**combat_controls("ultimate"))
    pad.release()
    assert [buttons for buttons, _ in pad.pad.reports] == [{"LS", "RS"}, set()]


@pytest.mark.parametrize("button", ["START", "BACK", "UP", "DOWN", "LEFT", "RIGHT", "Y"])
def test_recorder_rejects_noncombat_buttons_before_writing_a_report(button):
    pad = object.__new__(record.Pad)
    pad.pad = FakePad()
    pad.vg = SimpleNamespace(XUSB_BUTTON=SimpleNamespace(**{value: key for key, value in XUSB_NAMES.items()}))
    pad.state = dict(NEUTRAL)
    with pytest.raises(KeyError):
        pad.set(buttons=("A", button))
    assert pad.pad.reports == []


def test_hero_picker_keeps_ui_buttons(monkeypatch, tmp_path):
    import numpy as np
    reports = []
    pad = SimpleNamespace(set=lambda **changes: reports.append(changes), release=lambda: None)
    monkeypatch.setattr(record, "time", SimpleNamespace(sleep=lambda _: None))
    monkeypatch.setattr(record.cv2, "imwrite", lambda *args: True)
    cap = SimpleNamespace(grab=lambda: np.zeros((720, 1280, 3), dtype=np.uint8))
    record.switch_to_spiderman(pad, cap, tmp_path)
    assert [r["buttons"] for r in reports if "buttons" in r] == [["X"], ["RB"], ["RB"], ["A"], ["X"]]
