"""Synthetic outgoing XUSB reports; no device, capture or game imports."""
from types import SimpleNamespace
from ctypes import Structure, c_ushort, c_byte, c_ubyte, c_short

import pytest

from agent.startup import watch_pad


class ReportPad:
    def __init__(self):
        self.updates = 0
        self.reset()

    def reset(self):
        self.report = SimpleNamespace(wButtons=0, sThumbLX=0, sThumbLY=0, sThumbRX=0, sThumbRY=0,
                                      bLeftTrigger=0, bRightTrigger=0)

    def press_button(self, button):
        self.report.wButtons |= {"LS": 0x40, "RS": 0x80, "LB": 0x100}[button]

    def left_joystick_float(self, x, y):
        self.report.sThumbLX, self.report.sThumbLY = int(x * 32767), int(y * 32767)

    def right_joystick_float(self, x, y):
        self.report.sThumbRX, self.report.sThumbRY = int(x * 32767), int(y * 32767)

    def left_trigger_float(self, value):
        self.report.bLeftTrigger = int(value * 255)

    def right_trigger_float(self, value):
        self.report.bRightTrigger = int(value * 255)

    def update(self):
        self.updates += 1
        return "real update result"


class XusbReport(Structure):
    # Signed layout described by review; some cached builds alias c_byte=c_ubyte.
    _fields_ = [("wButtons", c_ushort), ("bLeftTrigger", c_byte), ("bRightTrigger", c_byte),
                ("sThumbLX", c_short), ("sThumbLY", c_short), ("sThumbRX", c_short), ("sThumbRY", c_short)]


@pytest.mark.parametrize("value", [0, 127, 128, 255])
@pytest.mark.parametrize("trigger_type", [c_byte, c_ubyte])
def test_real_ctypes_layout_decodes_unsigned_trigger_bytes(value, trigger_type):
    class Report(Structure):
        _fields_ = [(name, trigger_type if name in ("bLeftTrigger", "bRightTrigger") else kind)
                    for name, kind in XusbReport._fields_]
    pad = ReportPad()
    pad.report = Report(0xc0, value, value, -32768, 32767, -123, 456)
    record = watch_pad(pad, clock=lambda: 1., full_report=True)
    pad.update()
    assert record["full_reports"] == [dict(t=1., buttons=0xc0, lx=-32768, ly=32767,
                                          rx=-123, ry=456, lt=value, rt=value)]


def test_full_reports_snapshot_both_clicks_signed_sticks_triggers_and_release():
    pad = ReportPad()
    record = watch_pad(pad, clock=lambda: float(pad.updates), full_report=True)
    pad.press_button("LS")
    pad.press_button("RS")
    pad.left_joystick_float(-1, 1)
    pad.right_joystick_float(.5, -.5)
    pad.left_trigger_float(1)
    pad.right_trigger_float(.5)
    assert pad.update() == "real update result"
    pad.reset()
    pad.update()
    assert record["failed"] is None
    assert record["reports"] == [(1., True), (2., False)]
    assert record["full_reports"] == [
        {"t": 1., "buttons": 0xc0, "lx": -32767, "ly": 32767, "rx": 16383, "ry": -16383, "lt": 255, "rt": 127},
        {"t": 2., "buttons": 0, "lx": 0, "ly": 0, "rx": 0, "ry": 0, "lt": 0, "rt": 0},
    ]


def test_report_is_observed_after_real_update_not_reconstructed_from_setters():
    pad = ReportPad()
    def update():
        pad.report.wButtons = 0x80
        pad.report.sThumbLY = -32768
    pad.update = update
    record = watch_pad(pad, clock=lambda: 1., full_report=True)
    pad.update()
    assert record["full_reports"][0]["buttons"] == 0x80
    assert record["full_reports"][0]["ly"] == -32768


def test_broken_report_read_does_not_prevent_updates_or_neutral():
    pad = ReportPad()
    record = watch_pad(pad, full_report=True)
    pad.report = None
    pad.update()
    assert record["failed"] and record["full_reports"] == []
    pad.reset()
    pad.update()
    assert pad.updates == 2 and record["full_reports"][-1]["buttons"] == 0


def test_underlying_update_error_propagates_and_is_not_logged_as_sent():
    pad = ReportPad()
    def fail():
        raise OSError("device update failed")
    pad.update = fail
    record = watch_pad(pad, full_report=True)
    with pytest.raises(OSError, match="device update failed"):
        pad.update()
    assert record["reports"] == record["full_reports"] == []


def test_legacy_observer_does_not_require_report_attribute():
    pad = ReportPad()
    del pad.report
    record = watch_pad(pad, clock=lambda: 1.)
    pad.update()
    assert record == {"reports": [(1., False)], "failed": None}
