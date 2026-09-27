"""Synthetic owner checks only; no recording table, native media or raw log opens."""
import math

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from scripts import fit_focal_train as m


def scene(focal=640., sign=1):
    angles = np.linspace(0, sign*.3, 25)
    theta = np.linspace(-.5, .5, 12)
    x = focal*np.tan(theta[None, :]-angles[:, None])
    heights = np.linspace(-.3, .1, 12)
    y = heights[None, :]*np.hypot(focal, x)
    return np.stack([x+640, y+360], axis=-1), angles


@pytest.mark.parametrize("focal", [465., 640., 760.])
@pytest.mark.parametrize("sign", [-1, 1])
def test_actual_perspective_tracks_recover_focal(focal, sign):
    xy, angles = scene(focal, sign)
    result = m.fit_tracks(xy, angles)
    assert result["diagnostic_focal_px_1280"] == pytest.approx(focal, abs=5)
    assert result["rms_x_px"] < .001
    assert not result["refusal_reasons"]


@pytest.mark.parametrize("kind", ["parallax", "pitch", "roll", "too_short", "outside_search"])
def test_bad_geometry_is_refused(kind):
    xy, angles = scene(1250. if kind == "outside_search" else 640.)
    if kind == "parallax":
        xy[:, :6, 0] += np.linspace(0, 30, len(xy))[:, None]
    elif kind == "pitch":
        xy[:, :, 1] += np.linspace(0, 20, len(xy))[:, None]
    elif kind == "roll":
        xy[:, :, 1] += np.linspace(0, .1, len(xy))[:, None]*(xy[:, :, 0]-640)
    elif kind == "too_short":
        xy, angles = xy[:5], angles[:5]
    assert m.fit_tracks(xy, angles)["refusal_reasons"]


def test_delayed_smoothing_does_not_assign_counts_to_visual_edge():
    values = m.count_signal([0., .1, .2, .3], [.1], [100], .05, .05)
    assert values[1] == 0
    assert values[2] == pytest.approx(100*(1-math.exp(-1)))
    assert 0 < values[2] < values[3] < 100


def test_missing_continuous_tracks_refuses_instead_of_guessing():
    with pytest.raises(ValueError, match="four frames"):
        m.fit_tracks(np.zeros((3, 0, 2)), np.zeros(3))


def test_scan_does_not_promote_no_buttons_to_stationarity():
    rows = [dict(i=i, suitability="accepted", gap_free=True, regime="normal", relative_known=True,
                 held_known=[True], held_start=[0], held_end=[0], press=[0], release=[0], unsupported={},
                 mouse_dx=20, mouse_dy=0, frame={"pts": i, "timebase": [1, 30]}) for i in range(20)]
    windows = m.scan_windows(rows)
    assert len(windows) == 1 and windows[0]["provisional_slow_yaw"]
    assert windows[0]["stationarity"].startswith("unknown")
    rows[5]["held_known"] = [False]
    assert all(w["start"] != 0 for w in m.scan_windows(rows))


def test_existing_output_is_never_replaced(tmp_path):
    path = tmp_path / "result.json"
    m.write(path, {"retained": True})
    with pytest.raises(FileExistsError):
        m.write(path, {"retained": False})
