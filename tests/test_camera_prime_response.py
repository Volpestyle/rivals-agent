"""Projected yaw and adversarial pixel controls, without corpus or live input."""
import json

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from perception import camera_prime_response as m


def texture(seed=4):
    rng = np.random.default_rng(seed)
    a = cv2.GaussianBlur(rng.normal(128, 45, (720, 1280)).astype(np.float32), (0, 0), 1)
    return np.clip(a, 0, 255).astype(np.uint8)


def translate(a, dx, dy=0):
    # Translation is a pixel-direction control, never full360 geometry.
    return cv2.warpAffine(a, np.float32([[1, 0, dx], [0, 1, dy]]), (1280, 720))


def projected_pair(angle):
    """Perspective pure yaw H=K R K^-1 on a distant scene, no flat-roll angle."""
    a = texture()
    k = np.array([[600., 0, 640], [0, 600, 360], [0, 0, 1]])
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    b = cv2.warpPerspective(a, k @ rotation @ np.linalg.inv(k), (1280, 720))
    return a, b


@pytest.mark.parametrize("angle", [.25, -.25])
def test_projected_yaw(angle):
    a, b = projected_pair(angle)
    direction = -1 if angle > 0 else 1
    result = m.analyze(a, b, direction)
    assert result["motion_present"], result
    assert result["dx"]*direction > 2
    assert result["confidence"] >= .8
    json.dumps(result, allow_nan=False)


def test_small_projected_yaw_safe_refusal_is_explicit():
    # A broad ROI can have appreciable vertical flow even on pure yaw. Keep
    # this observed false refusal visible instead of loosening consensus.
    a, b = projected_pair(.08)
    result = m.analyze(a, b)
    assert not result["motion_present"]
    assert result["refusal_reasons"] == ["incoherent_displacement"]


@pytest.mark.parametrize("kind", ["same", "noise", "brightness", "vertical", "wrong_sign", "periodic", "flat", "local_only"])
def test_false_motion_controls(kind):
    a = texture()
    if kind == "same":
        b = a.copy()
    elif kind == "noise":
        b = texture(19)
    elif kind == "brightness":
        b = np.clip(a.astype(float)+3, 0, 255).astype(np.uint8)
    elif kind == "vertical":
        b = translate(a, 0, 25)
    elif kind == "wrong_sign":
        b = translate(a, 80)
    elif kind == "periodic":
        a = np.tile(texture()[:32, :32], (23, 40))[:720]
        b = translate(a, -48)
    elif kind == "flat":
        a = np.full((720, 1280), 100, np.uint8)
        b = a+1
    else:
        b = a.copy()
        b[125:160, 360:392] = a[125:160, 440:472]
    result = m.analyze(a, b)
    assert not result["motion_present"], result
    assert "dx" not in result
    json.dumps(result, allow_nan=False)


def test_banner_change_alone_cannot_prove_motion():
    a = texture()
    b = a.copy()
    b[80:110, :] = translate(a, -170)[80:110, :]
    assert not m.analyze(a, b)["motion_present"]


def test_banner_overlay_does_not_hide_projected_motion():
    a, b = projected_pair(.25)
    a[80:110] = 90
    b[80:110] = 200
    assert m.analyze(a, b)["motion_present"]


@pytest.mark.parametrize("gap", [0, -.05, .02, .11, float("nan")])
def test_invalid_timestamps(gap):
    a = texture()
    result = m.analyze(a, translate(a, -80), before_t=0, after_t=gap)
    assert not result["motion_present"]
    json.dumps(result, allow_nan=False)


def test_small_bounded_motion_and_native_scale():
    a = texture()
    b = translate(a, -4)
    a, b = [cv2.resize(cv2.cvtColor(f, cv2.COLOR_GRAY2BGR), (2560, 1440)) for f in (a, b)]
    result = m.analyze(a, b, before_t=1, after_t=1.08)
    assert result["motion_present"]
    assert result["dx"] == pytest.approx(-4, abs=1)


def test_subthreshold_motion_refused():
    a = texture()
    assert not m.analyze(a, translate(a, -1))["motion_present"]


@pytest.mark.parametrize("direction", [0, 2, float("nan")])
def test_invalid_direction_is_serializable_refusal(direction):
    a = texture()
    result = m.analyze(a, a, direction)
    assert not result["motion_present"]
    json.dumps(result, allow_nan=False)


def test_invalid_pixels_refuse():
    assert not m.analyze(None, None)["motion_present"]
    assert not m.analyze(np.zeros((3, 3)), np.zeros((3, 3)))["motion_present"]
