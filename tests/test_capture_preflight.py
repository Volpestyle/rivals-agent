"""scripts/capture.preflight: fail loudly when Desktop Duplication delivers nothing (the monitor dropped off DisplayPort
at 23:08 on 2026-09-20 and dxcam returned None for ever while GDI kept working)."""
import sys
from pathlib import Path

import numpy as np  # noqa: F401  (capture imports it; keeps this module out of the stdlib-only run)
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import capture  # noqa: E402


class Cam:
    def __init__(self, every):
        self.every, self.n = every, 0

    def grab(self):
        self.n += 1
        return "frame" if self.every and self.n % self.every == 0 else None


def clock():
    clock.t += 0.001
    return clock.t


def test_a_dead_duplicator_fails_loudly():
    clock.t = 0.0
    with pytest.raises(SystemExit) as e:
        capture.preflight(1.0, cam=Cam(0), clock=clock)
    assert "0 frames" in str(e.value) and "Get-PnpDevice -Class Monitor" in str(e.value) and e.value.code != 0


def test_a_live_duplicator_passes_and_counts():
    clock.t = 0.0
    assert capture.preflight(1.0, cam=Cam(4), clock=clock) > 100
    clock.t = 0.0
    frames, calls = capture.frames_in(0.5, cam=Cam(2), clock=clock)
    assert 0 < frames < calls
