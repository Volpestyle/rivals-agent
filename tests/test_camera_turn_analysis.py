"""CPU-only projected geometry and adversarial controls; no recorded corpus."""
import json
import math
import hashlib
import subprocess
import sys

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from perception import camera_turn_analysis as m


def panorama(period, hz, *, focal=600., direction=1, halves=False, turns=5.3, seed=42):
    """Static cylindrical world sampled by yawing rectilinear camera rays.

    Unlike np.roll of a flat strip, 2*pi is explicitly one world revolution.
    Rays hit a unit cylinder: azimuth atan(x/f)+yaw, height y/hypot(f,x).
    Texture wraps at 2*pi (or pi for the deliberately symmetric world).
    """
    rng = np.random.default_rng(seed)
    texture = cv2.GaussianBlur(rng.normal(size=(256, 2048)).astype(np.float32), (0, 0), 2)
    texture = (texture - texture.mean()) / texture.std() * 35 + 128
    x = np.arange(265, dtype=np.float32)[None, :] * 2 + 20.5
    y = np.arange(150, dtype=np.float32)[:, None] * 2 - 239.5
    base_azimuth = np.arctan(x / focal)
    map_y = np.broadcast_to(128 + y / np.hypot(focal, x) * 200, (150, 265)).astype(np.float32).copy()
    rows = []
    for t in np.arange(math.ceil((.5 + turns * period) * hz)) / hz:
        azimuth = base_azimuth + direction * 2 * np.pi * t / period
        map_x = np.broadcast_to(azimuth / (np.pi if halves else 2*np.pi) * 2048,
                                (150, 265)).astype(np.float32).copy()
        f = cv2.remap(texture, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        rows.append((float(t), f))
    return rows


@pytest.mark.parametrize("period", [2.23, .87])
@pytest.mark.parametrize("hz", [30, 60, 120])
def test_projected_full_turns(period, hz):
    rows = panorama(period, hz)
    result = m.analyze(rows, 0, rows[-1][0], .45)
    rate = result["candidate_signed_deg_s"]
    # A refusal at insufficient sampling is safe; never allow a wrong rate.
    if rate is None:
        assert hz == 30 and period == .87, result["refusal_reasons"]
    else:
        assert rate == pytest.approx(360 / period, rel=.01)
        assert result["candidate_signed_deg_s_bounds"][0] <= 360/period <= result["candidate_signed_deg_s_bounds"][1]
        assert all(i["timing_pass"] and i["one_turn_pass"] for i in result["intervals"])
        assert any(abs(r[0]*hz - round(r[0]*hz)) > .01 for r in result["returns"])
        # Motion audit really is full rate, including at 120 Hz; no fixed 40 ms
        # separation can masquerade as independent adjacent-frame integration.
        pairs = result["motion"]["pairs"]
        assert len(pairs) == sum(.5 <= t <= rows[-1][0] for t, _ in rows) - 1
        assert all(p["tb"]-p["ta"] == pytest.approx(1/hz) for p in pairs)
    assert result["acceptance"] == "candidate_only_native_turn_count_unverified"
    json.dumps(result, allow_nan=False)


def test_two_identical_halves_refuse_half_turn_alias():
    rows = panorama(2.23, 60, halves=True)
    result = m.analyze(rows, 0, rows[-1][0], .45)
    assert result["candidate_signed_deg_s"] is None
    assert "integrated_angle_not_one_turn" in result["refusal_reasons"]
    assert result["repeatability_pass"]


def test_every_fifth_return_is_not_one_turn(monkeypatch):
    # Model a detector missing four out of every five returns. Motion pixels and
    # all adjacent shifts stay intact; do not spoof them with the proposed rate.
    rows = panorama(.87, 60, turns=21.3)
    crossings = m._crossings
    monkeypatch.setattr(m, "_crossings", lambda *a: crossings(*a)[1::5])
    result = m.analyze(rows, 0, rows[-1][0], 1.)
    assert result["candidate_signed_deg_s"] is None
    assert result["repeatability_pass"]
    assert "integrated_angle_not_one_turn" in result["refusal_reasons"]
    assert all(i["integrated_angle_bracket_deg"][0] > 720 for i in result["intervals"])


@pytest.mark.parametrize("kind", ["static", "sign", "offaxis", "ambiguous", "flat", "flat_periodic"])
def test_invalid_motion_controls(kind):
    rng = np.random.default_rng(7)
    frame = cv2.GaussianBlur(rng.normal(128, 30, (150, 265)).astype(np.float32), (0, 0), 1)
    rows = []
    for i in range(400):
        if kind == "sign":
            f = np.roll(frame, i * 3, axis=1)
        elif kind == "offaxis":
            f = np.roll(frame, -i * 3, axis=0)
        elif kind == "ambiguous":
            f = rng.normal(128, 30, frame.shape).astype(np.float32)
        elif kind == "flat":
            f = np.full_like(frame, 128)
        elif kind == "flat_periodic":
            f = np.roll(frame, -i * 5, axis=1)
        else:
            f = frame
        rows.append((i/60, f))
    result = m.analyze(rows, 0, rows[-1][0], .45)
    assert result["candidate_signed_deg_s"] is None
    json.dumps(result, allow_nan=False)


def test_bracket_counts_band_halfscale_and_offcenter():
    _, _, scale = m._rectifier()
    lo, hi = m._angle_bracket(10., scale)
    assert lo < math.degrees(10 * scale) < hi
    assert lo > 1 and hi < 3


@pytest.mark.parametrize("kind", ["duplicate_time", "gap", "shape", "nan"])
def test_malformed_input_refused(kind):
    rows = panorama(2.23, 30, turns=1)
    t, frame = rows[20]
    if kind == "duplicate_time":
        rows[20] = (rows[19][0], frame)
    elif kind == "gap":
        rows = rows[:20] + rows[25:]
    elif kind == "shape":
        rows[20] = (t, frame[:, :-1])
    else:
        frame[0, 0] = np.nan
    result = m.analyze(rows, 0, rows[-1][0], .45)
    assert result["candidate_signed_deg_s"] is None
    assert result["refusal_reasons"]


@pytest.mark.parametrize("focal", [465., 600., 760.])
@pytest.mark.parametrize("period", [2.23, .87])
def test_both_signs_and_focal_bracket_controls(focal, period):
    rows = panorama(period, 60, focal=focal, direction=-1, seed=91)
    result = m.analyze(rows, 0, rows[-1][0], -.45)
    rate = result["candidate_signed_deg_s"]
    if focal == 600:
        assert rate == pytest.approx(-360/period, rel=.01), result["refusal_reasons"]
    elif rate is not None:
        assert rate == pytest.approx(-360/period, rel=.01)
    else:
        assert result["refusal_reasons"]


def test_timing_gate_keeps_full_crossing_bracket():
    # Even a repeatable one-turn candidate is refused if its explicit sample
    # brackets cannot support <=5% error. No interpolation-confidence shortcut.
    times = np.arange(0., 7., .1)
    pairs = [{"usable": True, "angle_bracket_deg": [30., 42.]} for _ in times[1:]]
    returns = [{"t": float(t), "uncertainty_s": .08} for t in (1., 2., 3., 4.)]
    intervals = m._intervals(returns, times, pairs)
    assert all(i["one_turn_pass"] and not i["timing_pass"] for i in intervals)
    assert intervals[0]["uncertainty_s"] == pytest.approx(.16)


def count_sweeps():
    return [dict(far_landmark=True, level_camera=True, signed_counts=d*2721.0,
                 endpoint_count_uncertainty=[2., 3.],
                 gain_evidence={"ref": "synthetic/closure.json", "sha256": "a"*64},
                 native_evidence={"ref": f"synthetic/sweep-{i}.mp4", "sha256": f"{i+1:064x}"})
            for i, d in enumerate((1, 1, 1, -1, -1, -1))]


def test_focal_from_counts_propagates_endpoint_and_gain_error():
    rows = count_sweeps()
    result = m.focal_from_counts(rows, .0330738, .0002)
    fov = 2721 * .0330738
    error = .0330738 * (5 + (2721+5)*.0002)
    assert result["hfov_deg"] == pytest.approx(fov)
    assert result["combined_uncertainty_deg"] == pytest.approx([error]*6)
    assert result["hfov_deg_bounds"] == pytest.approx([fov-error, fov+error])
    assert result["focal_px_1280"] == pytest.approx(640/math.tan(math.radians(fov/2)))
    assert result["focal_px_1280_bounds"][0] < result["focal_px_1280"] < result["focal_px_1280_bounds"][1]
    assert result["acceptance"] == "candidate_only_landmark_review_required"
    assert result["evidence_refs_verified"] is False
    assert result["sweeps"][0]["native_evidence"] == rows[0]["native_evidence"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("kind", ["endpoint", "gain", "near", "level", "direction", "repeat",
                                   "missing_pin", "invalid_pin", "mixed_gain", "zero_error", "nan"])
def test_focal_counts_refuses_bad_evidence(kind):
    rows, gain_error = count_sweeps(), .0002
    if kind == "endpoint":
        rows[0]["endpoint_count_uncertainty"] = [8., 8.]  # each alone passes; sum fails
    elif kind == "gain":
        gain_error = .02  # .02% is .0002, not .02
    elif kind == "near":
        rows[0]["far_landmark"] = False
    elif kind == "level":
        rows[0]["level_camera"] = False
    elif kind == "direction":
        rows[0]["signed_counts"] *= -1
    elif kind == "repeat":
        rows[0]["signed_counts"] += 31  # >1 degree repeat spread
    elif kind == "missing_pin":
        del rows[0]["gain_evidence"]
    elif kind == "invalid_pin":
        rows[0]["native_evidence"]["sha256"] = "not-a-hash"
    elif kind == "mixed_gain":
        rows[0]["gain_evidence"]["sha256"] = "b"*64
    elif kind == "zero_error":
        rows[0]["endpoint_count_uncertainty"] = [0., 0.]
    else:
        rows[0]["signed_counts"] = float("nan")
    with pytest.raises(ValueError):
        m.focal_from_counts(rows, .0330738, gain_error)


def test_focal_counts_includes_gain_count_product_at_boundary():
    rows = count_sweeps()
    gain, relative = .0330738, .0002
    # Omitting the product term would pass this row by a tiny margin.
    count_error = (.5 - 2721*gain*relative) / gain
    rows[0]["endpoint_count_uncertainty"] = [count_error/2, count_error/2]
    with pytest.raises(ValueError, match="uncertainty"):
        m.focal_from_counts(rows, gain, relative)


def test_counts_module_cli_pins_exact_input_bytes(tmp_path):
    source, output = tmp_path / "sweeps.json", tmp_path / "candidate.json"
    raw = b"\xef\xbb\xbf" + json.dumps(count_sweeps(), indent=2).encode() + b"\r\n"
    source.write_bytes(raw)
    subprocess.run([sys.executable, "-m", "perception.camera_turn_analysis", "--counts-json", str(source),
                    "--gain", ".0330738", "--gain-relative-uncertainty", ".0002", "--output", str(output)],
                   check=True, capture_output=True, text=True)
    result = json.loads(output.read_text())
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["source_path"] == str(source)
    assert result["acceptance"] == "candidate_only_landmark_review_required"
    assert not result["evidence_refs_verified"]  # nonexistent synthetic refs were not opened


def test_counts_cli_never_overwrites(tmp_path):
    source, output = tmp_path / "sweeps.json", tmp_path / "candidate.json"
    source.write_text(json.dumps(count_sweeps()))
    output.write_bytes(b"preserve existing output exactly")
    with pytest.raises(SystemExit) as error:
        m.main(["--counts-json", str(source), "--gain", ".0330738",
                "--gain-relative-uncertainty", ".0002", "--output", str(output)])
    assert error.value.code == 2
    assert output.read_bytes() == b"preserve existing output exactly"


@pytest.mark.parametrize("kind", ["syntax", "object", "six_rows", "gain", "missing_gain", "oversized"])
def test_counts_cli_invalid_input_does_not_create_output(tmp_path, kind):
    source, output = tmp_path / "sweeps.json", tmp_path / "candidate.json"
    payload = {"syntax": "{", "object": "{}", "six_rows": "[]", "oversized": " "*1_048_577}
    source.write_text(payload.get(kind, json.dumps(count_sweeps())))
    args = ["--counts-json", str(source), "--gain-relative-uncertainty", ".0002", "--output", str(output)]
    if kind != "missing_gain":
        args += ["--gain", "nan" if kind == "gain" else ".0330738"]
    with pytest.raises(SystemExit) as error:
        m.main(args)
    assert error.value.code == 2
    assert not output.exists()
