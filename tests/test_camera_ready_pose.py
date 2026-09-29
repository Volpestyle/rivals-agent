"""Fixed-reference geometry controls; recorded PNG cases are explicit opt-in."""
import hashlib
import json
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


@pytest.mark.parametrize("dx,dy", [(4,0), (-4,0), (0,4), (0,-4)])
def test_agreeing_patch_motion_is_changed_even_with_low_phase(scenery, monkeypatch, dx, dy):
    monkeypatch.setattr(pose.cv2, "phaseCorrelate", lambda *a: ((0., 0.), .1))
    result = pose.analyze(scenery, np.roll(scenery, (dy, dx), (0,1)))
    assert result["agreeing_patches"] >= 3 and result["patch_spread"] <= .75
    assert result["status"] == "changed"
    assert result["reason"] == "shift_exceeds_original_bound"
    assert "registered_band_correlation" not in result


def test_low_phase_with_stationary_patches_still_cannot_pass(scenery, monkeypatch):
    monkeypatch.setattr(pose.cv2, "phaseCorrelate", lambda *a: ((0., 0.), .1))
    result = pose.analyze(scenery, scenery)
    assert result["agreeing_patches"] == 6
    assert result["status"] == "unprovable" and result["reason"] == "low_phase_confidence"


@pytest.mark.parametrize("kind", ["noise", "flat"])
def test_centre_content_change_is_not_hidden_by_outer_patch_agreement(scenery, kind):
    current = scenery.copy()
    current[120:420, 884:964] = (100 if kind == "flat" else
        np.random.default_rng(8).integers(0, 256, (300,80,3), np.uint8))
    result = pose.analyze(scenery, current)
    assert result["status"] != "unchanged"


def _pinned_native(relative, expected_sha256):
    raw = (ROOT / relative).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha256, relative
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


@pytest.mark.corpus
def test_september28b_terminal_and_prior_journal_frames():
    evidence = ROOT / "docs/evidence/camera-ready-proposal-20260928b"
    pins = json.loads((evidence / "probe.json").read_text())["source_sha256"]
    base = "data/calibration/alt-cam-20260928b/yaw-01/"
    reference = _pinned_native(base + "refusal-reference.png", pins[base + "refusal-reference.png"])
    terminal = _pinned_native(base + "refusal-current.png", pins[base + "refusal-current.png"])
    assert pose.analyze(reference, terminal)["status"] == "unchanged"
    # These are sampled journal frames, NOT the lost exact final audit frame.
    rows = json.loads((evidence / "preceding-frames.json").read_text())
    for number, status in ((150, "unchanged"), (148, "unprovable")):
        row = next(r for r in rows if r["path"].endswith(f"{number:07d}-guard.png"))
        current = _pinned_native(row["path"], row["sha256"])
        assert pose.analyze(reference, current)["status"] == status
    for kind in ("noise", "flat"):
        current = reference.copy()
        current[240:840, 1768:1928] = (100 if kind == "flat" else
            np.random.default_rng(8).integers(0, 256, (600,160,3), np.uint8))
        result = pose.analyze(reference, current)
        assert result["status"] == "unprovable"
        assert result["registered_band_correlation"] < .95
    for dx,dy in ((8,0),(-8,0),(0,8),(0,-8),(40,0),(0,40)):
        assert pose.analyze(reference,np.roll(reference,(dy,dx),(0,1)))["status"] != "unchanged"


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


def _sitting_c_reference():
    return _pinned_native("data/calibration/alt-cam-20260928c/yaw-01r/refusal-reference.png",
                          "3e992481bcb3f3d941ac92f8c0c0ceb48faac2ec0fe331c442049385f88fcaf8")


@pytest.mark.corpus
def test_fractional_scoring_accepts_sitting_c_without_changing_estimated_motion():
    reference = _sitting_c_reference()
    current = _pinned_native("data/calibration/alt-cam-20260928c/yaw-01r/refusal-current.png",
                            "1987561f1593789194d8786d24bbcab5f4028173783d003de78e478263e9cf69")
    result = pose.analyze(reference, current)
    assert result["status"] == "unchanged" and result["agreeing_patches"] == 6
    assert all(p["integer_ncc"] < .95 and p["ncc"] >= .95 for p in result["patches"])
    assert result["registered_band_correlation"] == pytest.approx(.97831496, abs=1e-6)
    # The original failed audit is useful specifically for unchanged offsets and
    # uniqueness: only the NCC sampling location changes in this repair.
    saved = json.loads((ROOT / "data/calibration/alt-cam-20260928c/yaw-01r/pose-refusal.json").read_text())["audit"]
    for old, new in zip(saved["patches"], result["patches"]):
        for key in ("dx", "dy", "uniqueness"):
            assert new[key] == pytest.approx(old[key], abs=1e-6)
        assert new["integer_ncc"] == pytest.approx(old["ncc"], abs=1e-6)


@pytest.mark.corpus
@pytest.mark.parametrize("dx,dy,status", [(-.5,0,"unchanged"), (.5,0,"unchanged"),
    (0,-.5,"unchanged"), (0,.5,"unchanged"), (-2,0,"changed"), (2,0,"changed"),
    (0,-2,"changed"), (0,2,"changed")])
def test_fractional_band_pixel_sampling_keeps_original_motion_bound(dx, dy, status):
    reference = _sitting_c_reference()
    # 2560 native pixels -> 265-pixel band: one band pixel is four native pixels.
    translated = cv2.warpAffine(reference, np.float32([[1,0,4*dx], [0,1,4*dy]]),
                                (reference.shape[1], reference.shape[0]), flags=cv2.INTER_LINEAR)
    result = pose.analyze(reference, translated)
    assert result["status"] == status
    assert result["shift_limit_band_px"] == 1.5
