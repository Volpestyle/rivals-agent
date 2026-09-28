"""Fixed-reference geometry controls; recorded PNG cases are explicit opt-in."""
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")
from perception import camera_ready_pose as pose

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scenery():
    return np.random.default_rng(57).integers(0, 256, (720, 1280, 3), dtype=np.uint8)


@pytest.mark.parametrize("dx,dy", [(0,0),(2,0),(-2,0),(0,2),(0,-2)])
def test_same_reference_accepts_only_small_bounded_motion(scenery, dx, dy):
    before = scenery.copy()
    result = pose.analyze(scenery, np.roll(scenery, (dy, dx), (0,1)))
    assert result["status"] == "unchanged"
    assert np.array_equal(before, scenery)
    assert result["agreeing_patches"] >= 3
    assert result["shift_limit_band_px"] == 1.5


@pytest.mark.parametrize("dx,dy", [(4,0),(-4,0),(0,4),(0,-4),(20,0),(0,20),(60,0),(0,60)])
def test_motion_beyond_existing_bound_never_passes(scenery, dx, dy):
    assert pose.analyze(scenery, np.roll(scenery, (dy,dx), (0,1)))["status"] != "unchanged"


@pytest.mark.parametrize("kind", ["blank", "stripes", "blur", "unrelated", "single_patch"])
def test_ambiguous_or_local_evidence_cannot_prove_pose(scenery, kind):
    other = scenery.copy()
    if kind == "blank":
        scenery[:] = other[:] = 42
    elif kind == "stripes":
        pattern = np.tile(((np.arange(1280)//8)%2*255).astype(np.uint8), (720,1))
        scenery[:] = other[:] = pattern[:,:,None]
    elif kind == "blur":
        other = cv2.GaussianBlur(scenery, (31,31), 10)
    else:
        other = np.random.default_rng(21).integers(0,256,scenery.shape,dtype=np.uint8)
        if kind == "single_patch":
            other[150:300, 680:930] = scenery[150:300,680:930]
    assert pose.analyze(scenery, other)["status"] != "unchanged"


def test_hero_animation_outside_scenery_does_not_change_pose(scenery):
    other = scenery.copy()
    other[300:720, 250:640] = 255 - other[300:720, 250:640]
    assert pose.analyze(scenery, other)["status"] == "unchanged"


def test_fixed_reference_catches_accumulated_drift(scenery):
    statuses = [pose.analyze(scenery, np.roll(scenery, dx, axis=1))["status"] for dx in (0,2,4,6)]
    assert statuses[:2] == ["unchanged", "unchanged"]
    assert "unchanged" not in statuses[2:]


def test_geometry_change_is_not_quality_recovery(scenery):
    with pytest.raises(ValueError, match="geometry"):
        pose.analyze(scenery, scenery[:360])


@pytest.mark.corpus
def test_retained_yaw01_frames_and_translated_native_controls():
    directory = ROOT / "data/calibration/alt-cam-20260928/yaw-01"
    reference = cv2.imread(str(directory / "ready-attach.png"))
    paths = sorted((directory / "frames").glob("*-before-attach.png"))
    assert len(paths) == 30
    for path in paths:
        assert pose.analyze(reference, cv2.imread(str(path)))["status"] == "unchanged", path.name
    for dx,dy in ((8,0),(-8,0),(0,8),(0,-8),(40,0),(0,40)):
        assert pose.analyze(reference,np.roll(reference,(dy,dx),(0,1)))["status"] != "unchanged"


@pytest.mark.corpus
def test_yesterday_accepted_prime_is_motion_and_never_ready():
    from perception.camera_prime_response import analyze as response
    directory = ROOT / "data/calibration/alt-cam-20260927/yaw-01b"
    before = cv2.imread(str(directory / "initialization-motion-before.png"))
    after = cv2.imread(str(directory / "initialization-motion-after.png"))
    assert response(before,after,direction=-1)["motion_present"]
    assert pose.analyze(before,after)["status"] != "unchanged"
