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


@pytest.mark.parametrize('counts,passes,expected', [([8, 95], True, 2), ([8, 9, 7], False, 3),
                                                  ([0, 0, 95], True, 3), ([0, 0, 0], False, 3)])
def test_opt_in_rate_gate_retries_bounded_windows_and_releases_owned_camera(monkeypatch, counts, passes, expected):
    from types import SimpleNamespace
    state = SimpleNamespace(t=0., windows=0, releases=0, sleeps=[])
    def release():
        state.releases += 1
    cam = SimpleNamespace(backend='dxcam', cam=SimpleNamespace(release=release))
    monkeypatch.setattr(capture, 'Capture', lambda backend: cam)
    def frames_in(secs, camera, clock):
        assert camera is cam
        state.t += secs
        count = counts[state.windows]
        state.windows += 1
        return count, 1000
    monkeypatch.setattr(capture, 'frames_in', frames_in)
    def run():
        return capture.preflight(min_fps=60, attempts=3, clock=lambda: state.t, sleep=state.sleeps.append)
    if passes:
        assert run() == 95
    else:
        with pytest.raises(SystemExit, match='preflight FAILED'):
            run()
    assert state.windows == expected and state.releases == 1
    assert state.sleeps == [.5] * (expected - 1)


def test_rate_uses_actual_elapsed_time_not_requested_window(monkeypatch):
    ticks = iter([0., 3.])
    monkeypatch.setattr(capture, 'frames_in', lambda *args: (90, 90))
    with pytest.raises(SystemExit, match='30.0 fps < 60'):
        capture.preflight(cam=Cam(1), clock=lambda: next(ticks), min_fps=60)


@pytest.mark.parametrize('kwargs', [{'attempts': 0}, {'attempts': 4}, {'attempts': True},
                                   {'min_fps': float('nan')}, {'secs': 0}, {'retry_s': 2}])
def test_bad_preflight_arguments_never_open_capture(monkeypatch, kwargs):
    monkeypatch.setattr(capture, 'Capture', lambda backend: pytest.fail('opened hardware'))
    with pytest.raises(ValueError):
        capture.preflight(**kwargs)


def test_capture_exception_releases_duplicator(monkeypatch):
    from types import SimpleNamespace
    releases = []
    cam = SimpleNamespace(backend='dxcam', cam=SimpleNamespace(release=lambda: releases.append(True)))
    monkeypatch.setattr(capture, 'Capture', lambda backend: cam)
    def fail(*args):
        raise OSError('capture')
    monkeypatch.setattr(capture, 'frames_in', fail)
    with pytest.raises(OSError, match='capture'):
        capture.preflight(min_fps=60, attempts=3)
    assert releases == [True]
