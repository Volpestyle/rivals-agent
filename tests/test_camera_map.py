"""Synthetic profile checks; no recordings, game, capture or pad."""
import hashlib
import json
import math

import pytest

from agent.camera_map import LEGACY, MAPS, CameraMapError, load_camera_map


def legacy_data():
    return json.loads((MAPS / f"{LEGACY}.json").read_text())


def write_map(tmp_path, data, *, live=False):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_camera_map(path, live=live)


def test_legacy_preserves_deployed_values_and_provenance():
    c = load_camera_map(live=True).require_controller()
    assert c.scalar("focal") == 465
    assert c.scalar("latency") == .045
    yaw = ((0., 0.), (.1, 18.5), (.2, 61.5), (.3, 110.), (.45, 172.), (.6, 241.), (.8, 320.), (1., 415.))
    pitch = ((0., 0.), (.5, 43.), (1., 99.))
    for axis, expected in (("yaw", yaw), ("pitch", pitch)):
        assert c.table(axis, 1) == c.table(axis, -1) == expected
        for d, rate in expected:
            for sign in (-1, 1):
                assert c.rate(axis, sign*d) == sign*rate
                assert c.stick(axis, sign*rate) == pytest.approx(sign*d)
    assert c.sha256 == hashlib.sha256((MAPS / f"{LEGACY}.json").read_bytes()).hexdigest()
    assert c.receipt()["profile"] == LEGACY
    assert c.interpolation.uncertainty["plus_minus"] is None
    assert c.interpolation.sitting and c.interpolation.receipt


def test_alt_all_signed_yaw_knots_are_candidates_and_all_holes_stay_missing():
    c = load_camera_map("alt-247-124")
    assert c.rate("yaw", .45) == 154
    assert c.rate("yaw", -.45) == pytest.approx(-159.09615325715495)
    present = [m for sign in (-1, 1) for _, m in c.points("yaw", sign)]
    assert len(present) == 14 and all(m.status == "candidate" and m.value > 0 for m in present)
    for sign in (-1, 1):
        for d, m in c.points("yaw", sign):
            assert c.rate("yaw", sign*d) == sign*m.value
            with pytest.raises(CameraMapError, match="candidate"):
                load_camera_map("alt-247-124", live=True).rate("yaw", sign*d)
        for d, _ in c.points("pitch", sign):
            with pytest.raises(CameraMapError, match="missing"):
                c.rate("pitch", sign*d)
    for f in ("focal", "latency", "interpolation"):
        with pytest.raises(CameraMapError, match="missing"):
            c.scalar(f)
    for query in (lambda: c.require_controller(), lambda: c.rate("yaw", .15), lambda: c.stick("yaw", 50)):
        with pytest.raises(CameraMapError, match="missing"):
            query()
    positive = dict(c.points("yaw", 1))[.45]
    assert positive.uncertainty["plus_minus"] is None
    assert positive.uncertainty["interval"] == [151.397, 156.473]


def test_interpolation_and_inverse_preserve_asymmetry(tmp_path):
    data = legacy_data()
    for p in data["yaw"]["negative"]:
        p["measurement"]["value"] *= .5
    c = write_map(tmp_path, data, live=True).require_controller()
    assert c.rate("yaw", -.375) == pytest.approx(-70.5)
    assert c.rate("yaw", .375) == pytest.approx(141)
    assert c.stick("yaw", -70.5) == pytest.approx(-.375)
    assert c.stick("yaw", 141) == pytest.approx(.375)
    assert c.stick("yaw", -1000) == -1  # clamp to measured maximum; no extrapolation
    assert c.rate("yaw", .05) == 9.25  # explicitly recorded linear-origin assumption


@pytest.mark.parametrize("status", ["candidate", "missing"])
@pytest.mark.parametrize("index", [2, 3])
def test_live_refuses_both_brackets_and_never_skips_a_hole(tmp_path, status, index):
    data = legacy_data()
    point = data["yaw"]["positive"][index]["measurement"]
    point["status"] = status
    if status == "missing":
        point["value"] = None
    c = write_map(tmp_path, data, live=True)
    with pytest.raises(CameraMapError, match=status):
        c.rate("yaw", .375)
    with pytest.raises(CameraMapError, match=status):
        c.require_controller()
    # A point outside the refused bracket remains independently queryable.
    assert c.rate("yaw", .8) == 320
    offline = write_map(tmp_path, data)
    if status == "candidate":
        assert offline.rate("yaw", .375) == 141
    else:
        with pytest.raises(CameraMapError, match="missing"):
            offline.rate("yaw", .375)


def test_unaccepted_interpolation_cannot_authorize_live_in_between_knots(tmp_path):
    data = legacy_data()
    data["interpolation"]["status"] = "candidate"
    c = write_map(tmp_path, data, live=True)
    assert c.rate("yaw", .45) == 172
    with pytest.raises(CameraMapError, match="candidate"):
        c.rate("yaw", .4)
    with pytest.raises(CameraMapError, match="candidate"):
        c.stick("yaw", 140)


@pytest.mark.parametrize("field", ["focal", "latency"])
def test_controller_requires_accepted_scalar_geometry_and_latency(tmp_path, field):
    data = legacy_data()
    data[field]["status"] = "candidate"
    with pytest.raises(CameraMapError, match="candidate"):
        write_map(tmp_path, data, live=True).require_controller()
    write_map(tmp_path, data).require_controller()


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(schema="v2"),
    lambda d: d["focal"].update(value=float("nan")),
    lambda d: d["latency"].update(value=-1),
    lambda d: d["focal"].update(receipt=None),
    lambda d: d["focal"].update(uncertainty={}),
    lambda d: d["focal"]["uncertainty"].update(plus_minus=-1),
    lambda d: d["focal"]["uncertainty"].update(interval=[470, 460]),
    lambda d: d["yaw"]["positive"][1].update(stick=.1),
    lambda d: d["yaw"]["positive"][1]["measurement"].update(value=10),
    lambda d: d["yaw"]["positive"][1]["measurement"].update(value=True),
    lambda d: d["yaw"]["positive"][1]["measurement"].update(status="approved"),
    lambda d: d["yaw"].pop("negative"),
    lambda d: d["interpolation"].update(value="guess"),
])
def test_invalid_maps_fail_closed(tmp_path, mutation):
    data = legacy_data()
    mutation(data)
    with pytest.raises(CameraMapError):
        write_map(tmp_path, data)


def test_missing_endpoint_refuses_inversion_and_full_controller(tmp_path):
    data = legacy_data()
    data["pitch"]["negative"].pop()
    c = write_map(tmp_path, data, live=True)
    with pytest.raises(CameraMapError, match="coverage"):
        c.require_controller()
    with pytest.raises(CameraMapError, match="coverage"):
        c.stick("pitch", -90)
    with pytest.raises(CameraMapError, match="coverage"):
        c.rate("pitch", -1)


def test_measured_deadzone_knots_do_not_reintroduce_linear_origin_motion(tmp_path):
    data = legacy_data()
    data["yaw"]["positive"][0]["measurement"]["value"] = 0
    c = write_map(tmp_path, data, live=True).require_controller()
    assert c.rate("yaw", .05) == c.rate("yaw", .1) == 0
    assert c.stick("yaw", 1) > .1
    assert c.stick("yaw", 0) == 0


def test_controller_refuses_zero_rate_at_a_scheduled_turn(tmp_path):
    data = legacy_data()
    for point in data["yaw"]["positive"][:4]:
        point["measurement"]["value"] = 0
    with pytest.raises(CameraMapError, match="timed turn"):
        write_map(tmp_path, data, live=True).require_controller()


@pytest.mark.parametrize("value", [math.nan, math.inf, True, "0.45", 1.1])
def test_invalid_stick_is_refused(value):
    with pytest.raises(CameraMapError):
        load_camera_map().rate("yaw", value)
