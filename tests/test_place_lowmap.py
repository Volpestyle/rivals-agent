"""scripts/place.py --lowmap (fit review K3) on synthetic frames: no game, no pad.

A textured sphere is rendered through the calibrated focal length at the simulated camera's yaw and pitch. A fake
Live turns that camera from the right stick through a map with a deadzone, one 50 ms write at a time, and the mode
measures the rotation with perception/camera_motion.py's own fit. Needs opencv and numpy (the perception group).
"""
import copy
import json
import math
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import place  # noqa: E402
from agent.controller import Cal, stick_for  # noqa: E402
from test_place import GAME, NOW, _measurement, no_pad  # noqa: E402,F401  (no_pad is a fixture)

W, H = 1280, 720
FOCAL = Cal().focal_1280


def _texture(seed=0, w=4096, h=2048):
    rng = np.random.default_rng(seed)
    t = cv2.GaussianBlur(rng.integers(0, 256, (h, w), dtype=np.uint8), (0, 0), 2.0)
    for _ in range(2500):                                         # corners for ORB
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        cv2.rectangle(t, (x, y), (x + int(rng.integers(6, 40)), y + int(rng.integers(6, 40))),
                      int(rng.integers(0, 256)), -1)
    return cv2.normalize(t, None, 0, 255, cv2.NORM_MINMAX)


TEXTURE = _texture()
U, V = np.meshgrid(np.arange(W, dtype=np.float64), np.arange(H, dtype=np.float64))
RAYS = np.stack([(U - W / 2) / FOCAL, (V - H / 2) / FOCAL, np.ones_like(U)], axis=-1)


def render(yaw_deg, pitch_deg):
    """The view at (yaw right, pitch up): camera x right, y down, z forward; world = R_yaw R_pitch ray."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    x0, y0, z0 = RAYS[..., 0], RAYS[..., 1], RAYS[..., 2]
    y1, z1 = math.cos(p) * y0 - math.sin(p) * z0, math.sin(p) * y0 + math.cos(p) * z0
    x2, z2 = math.cos(y) * x0 + math.sin(y) * z1, -math.sin(y) * x0 + math.cos(y) * z1
    lon, lat = np.arctan2(x2, z2), np.arctan2(-y1, np.hypot(x2, z2))
    th, tw = TEXTURE.shape
    mx = ((lon / (2 * math.pi) + 0.5) * tw).astype(np.float32)
    my = ((0.5 - lat / math.pi) * th).astype(np.float32)
    g = cv2.remap(TEXTURE, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


class Game:
    """A camera turned by the right stick: rate = 0 inside the deadzone, then linear to the map point above it."""

    def __init__(self, yaw_dz=0.045, pitch_dz=0.12, yaw_at_01=18.5, pitch_at_05=43.0):
        self.yaw_dz, self.pitch_dz, self.yaw_at_01, self.pitch_at_05 = yaw_dz, pitch_dz, yaw_at_01, pitch_at_05
        self.yaw = self.pitch = 0.0
        self.t = 0.0
        self.rx = self.ry = 0.0
        self.sent, self.releases = [], 0

    def rate(self, s, dz, top_stick, top_rate):
        return 0.0 if abs(s) <= dz else math.copysign(top_rate * (abs(s) - dz) / (top_stick - dz), s)

    # the clock and sleep the mode is given
    def clock(self):
        return self.t

    def sleep(self, dt):
        self.yaw += self.rate(self.rx, self.yaw_dz, 0.1, self.yaw_at_01) * dt
        self.pitch += self.rate(self.ry, self.pitch_dz, 0.5, self.pitch_at_05) * dt
        self.t += dt

    # Live's surface
    def fresh(self):
        # only a neutral stick's frame is ever measured (the settled frames); mid-hold frames only feed the proof
        if self.rx or self.ry:
            return None
        key = (round(self.yaw, 9), round(self.pitch, 9))
        if getattr(self, "_key", None) != key:
            self._key, self._frame = key, render(self.yaw, self.pitch)
        return self._frame

    def send(self, **pad):
        self.sent.append(dict(pad))
        self.rx, self.ry = pad.get("rx", self.rx), pad.get("ry", self.ry)

    def release(self):
        self.releases += 1
        self.rx = self.ry = 0.0


def run(game, proof=lambda f: None):
    rows = place.lowmap(game, proof, place.camera_rotation(), clock=game.clock, sleep=game.sleep, log=lambda *_: None)
    return rows, place.lowmap_fit(rows)


def test_the_renderer_and_the_estimator_agree_on_signs():
    rot = place.camera_rotation()
    y, p, _ = rot(render(0, 0), render(3.0, 0))
    assert y == pytest.approx(3.0, abs=0.1) and abs(p) < 0.1               # right is + yaw
    y, p, _ = rot(render(0, 0), render(0, 2.0))
    assert p == pytest.approx(2.0, abs=0.1) and abs(y) < 0.1               # up is + pitch


@pytest.fixture(scope="module")
def default_run():
    game = Game(yaw_dz=0.045, pitch_dz=0.12)
    rows, fit = run(game)
    return game, rows, fit


def test_the_low_end_map_finds_each_axis_deadzone_and_writes_cals_fields(default_run):
    game, rows, fit = default_run
    assert fit["ok"], fit["why"]
    assert fit["axes"]["yaw"]["deadzone"] == 0.04 and fit["axes"]["yaw"]["edge"] == [0.04, 0.05]
    assert fit["axes"]["pitch"]["deadzone"] == 0.1 and fit["axes"]["pitch"]["edge"] == [0.1, 0.15]
    yaw = {p["stick"]: p for p in fit["axes"]["yaw"]["deflections"]}
    assert yaw[0.1]["rate_deg_s"] == pytest.approx(18.5, rel=0.08)
    assert yaw[0.07]["rate_deg_s"] == pytest.approx(18.5 * 0.025 / 0.055, rel=0.12)
    pitch = {p["stick"]: p for p in fit["axes"]["pitch"]["deflections"]}
    assert pitch[0.5]["rate_deg_s"] == pytest.approx(43.0, rel=0.08)
    # Cal's own fields: loadable, and the feedforward commands a small turn just past the measured deadzone
    cal = Cal(**{k: tuple(map(tuple, v)) if k.endswith("_map") else v for k, v in fit["cal"].items()})
    assert cal.yaw_map[0] == (0.0, 0.0) and cal.yaw_map[-1] == Cal().yaw_map[-1] and (0.04, 0.0) in cal.yaw_map
    assert 0.04 < stick_for(2.0, cal.yaw_map, cal.yaw_deadzone) < 0.06
    assert 0.1 < stick_for(3.0, cal.pitch_map, cal.pitch_deadzone) < 0.2
    json.dumps(fit)


def test_it_sends_the_right_stick_only_and_ends_neutral(default_run):
    game = default_run[0]
    keys = {k for pad in game.sent for k in pad}
    assert keys <= {"rx", "ry"} and all(len(pad) == 1 for pad in game.sent)
    assert max(abs(v) for pad in game.sent for v in pad.values()) <= 0.5
    assert game.rx == game.ry == 0.0 and game.releases >= 2 * place.LOWMAP_REPEATS * (
        len(place.LOWMAP_YAW) + len(place.LOWMAP_PITCH))
    assert abs(game.yaw) < 0.5 and abs(game.pitch) < 0.5                     # every hold was turned back


def test_other_pad_settings_are_not_ok():
    rows, fit = run(Game(yaw_at_01=37.0))                                    # twice the calibrated yaw rate
    assert not fit["ok"] and "yaw" in fit["why"] and "pad settings" in fit["why"]


def test_no_movement_up_to_the_top_deflection_is_not_ok_and_leaves_the_deadzone_unmeasured():
    rows, fit = run(Game(yaw_dz=0.2))
    assert not fit["ok"] and "yaw: no deflection" in fit["why"]
    assert fit["cal"]["yaw_deadzone"] is None and fit["axes"]["pitch"]["deadzone"] == 0.1


def test_a_deadzone_below_the_grid_is_zero_with_its_edge():
    rows, fit = run(Game(yaw_dz=0.01))
    assert fit["ok"], fit["why"]
    assert fit["axes"]["yaw"]["deadzone"] == 0.0 and fit["axes"]["yaw"]["edge"] == [0.0, 0.02]


def test_an_abstaining_fit_or_a_mixed_deflection_is_not_ok(default_run):
    rows = copy.deepcopy(default_run[1])
    rows["yaw"][4]["back"] = None
    assert "abstained" in place.lowmap_fit(rows)["why"]
    rows = copy.deepcopy(default_run[1])
    k = next(i for i, r in enumerate(rows["pitch"]) if r["stick"] == 0.1)
    rows["pitch"][k]["forward"] = {**rows["pitch"][k]["forward"], "deg": 1.0}
    fit = place.lowmap_fit(rows)
    assert not fit["ok"] and "moved on some holds only" in fit["why"]


def test_a_wrong_sign_is_not_ok(default_run):
    rows = copy.deepcopy(default_run[1])
    r = rows["yaw"][-1]
    r["forward"] = {**r["forward"], "deg": -r["forward"]["deg"]}
    assert "against the stick" in place.lowmap_fit(rows)["why"]


def test_a_failed_proof_stops_it_neutral():
    game = Game()
    calls = {"n": 0}

    def proof(f):
        calls["n"] += 1
        return "game not in the foreground (kill switch)" if calls["n"] > 40 else None

    with pytest.raises(place.Stopped, match="kill switch"):
        place.lowmap(game, proof, place.camera_rotation(), clock=game.clock, sleep=game.sleep, log=lambda *_: None)
    assert game.rx == game.ry == 0.0 and game.releases >= 1


# --- the gate ----------------------------------------------------------------------------------------------------

def test_lowmap_needs_its_own_mode_and_the_pad_settings(tmp_path):
    ok = _measurement(tmp_path, "lowmap", pad_settings=place.LOWMAP_PAD_SETTINGS)
    assert place.check_measurement_declaration(ok, "lowmap", process_info=GAME, now=NOW)["modes"] == ["lowmap"]
    for over in ({}, {"pad_settings": {**place.LOWMAP_PAD_SETTINGS, "horizontal": 130}}):
        with pytest.raises(place.Refused, match="pad_settings"):
            place.check_measurement_declaration(_measurement(tmp_path, "lowmap", **over), "lowmap",
                                                process_info=GAME, now=NOW)
    with pytest.raises(place.Refused, match="modes must include 'lowmap'"):
        place.check_measurement_declaration(_measurement(tmp_path, "measure-pitch"), "lowmap", process_info=GAME,
                                            now=NOW)


def test_main_lowmap_refuses_before_any_pad_opens(tmp_path, monkeypatch, capsys, no_pad):
    monkeypatch.setattr(place, "_process_info", GAME)
    assert place.main(["--lowmap"]) == 2 and "needs --declaration" in capsys.readouterr().out
    decl = _measurement(tmp_path, "lowmap")                                   # no pad_settings
    assert place.main(["--lowmap", "--declaration", str(decl)]) == 2 and "pad_settings" in capsys.readouterr().out
