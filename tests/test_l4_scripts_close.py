"""scripts/l4_trial.py and scripts/l4_measure.py open a Live: every exit path must end in Live.close(), not only
release(), because close owns the lease watchdog and refuses any later write."""
import sys
from pathlib import Path

import cv2  # noqa: F401  (both scripts import it; keeps this module out of the stdlib-only run)
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import l4_measure  # noqa: E402
import l4_trial  # noqa: E402


class FakeLive:
    """Counts close(); `boom` names the first method that raises."""

    def __init__(self, boom=None, error=RuntimeError):
        self.boom, self.error, self.closed, self.calls = boom, error, 0, []
        self.frame, self.frame_t, self.cap = None, 0.0, self

    def _hit(self, name):
        self.calls.append(name)
        if name == self.boom:
            raise self.error(name)

    def keepalive(self):
        self._hit("keepalive")

    def fresh(self, timeout=0.1):
        self._hit("fresh")
        return np.zeros((1440, 2560, 3), np.uint8)

    def grab(self):
        return self.fresh()

    def send(self, **pad):
        self._hit("send")

    def hold(self, secs, **pad):
        self._hit("hold")

    def scoreboard(self, hold_s=1.0):
        return self.fresh()

    def release(self):
        self.calls.append("release")

    def close(self):
        self.closed += 1


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(l4_trial, "ROOT", tmp_path)
    monkeypatch.setattr(l4_measure, "OUT", tmp_path / "l4")
    monkeypatch.setattr(l4_trial.time, "sleep", lambda s: None)


@pytest.mark.parametrize("boom,error", [("keepalive", RuntimeError), ("fresh", RuntimeError), ("hold", RuntimeError),
                                        ("hold", KeyboardInterrupt), ("keepalive", KeyboardInterrupt)])
def test_measure_closes_live_however_it_ends(boom, error):
    live = FakeLive(boom, error)
    with pytest.raises(error):
        l4_measure.main(["yawleft"], live_factory=lambda: live)
    assert live.closed == 1


def test_measure_closes_live_on_success(monkeypatch):
    live = FakeLive()
    monkeypatch.setitem(l4_measure.__dict__, "press", lambda lv: {"ok": True})
    l4_measure.main(["press"], live_factory=lambda: live)
    assert live.closed == 1 and "keepalive" in live.calls


@pytest.mark.parametrize("mode", [["aim", "1"], ["prim", "web_cluster", "1"], ["tagrb", "1"], ["scoreboard", "1"], ["tagged", "1"], ["tagrun", "0.01"]])
@pytest.mark.parametrize("boom,error", [("keepalive", RuntimeError), ("fresh", RuntimeError), ("fresh", KeyboardInterrupt)])
def test_trial_closes_live_however_it_ends(mode, boom, error):
    live = FakeLive(boom, error)
    with pytest.raises(error):
        l4_trial.main(mode, live_factory=lambda: live)
    assert live.closed == 1


def test_trial_closes_live_when_the_log_cannot_be_opened(monkeypatch, tmp_path):
    live = FakeLive()
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        l4_trial.Rig(tmp_path / "x", live_factory=lambda: live)
    assert live.closed == 1


def test_rig_close_closes_live_even_if_the_rest_of_close_fails(tmp_path):
    live = FakeLive()
    rig = l4_trial.Rig(tmp_path / "y", live_factory=lambda: live)
    rig.log.close()
    rig.q = None                                            # make the rest of close() blow up
    with pytest.raises(AttributeError):
        rig.close()
    assert live.closed == 1
