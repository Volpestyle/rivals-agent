"""Versioned camera measurements. Loading a candidate never authorizes live input.

Signed directions are independent. Missing knots are holes, not permission to
interpolate across them; interpolation itself needs an explicit model record.
The legacy profile preserves its historical symmetry/linear-origin assumptions.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


MAPS = Path(__file__).with_name("camera_maps")
LEGACY = "legacy-265-75"


class CameraMapError(ValueError):
    pass


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class Measurement:
    value: float | str | None
    status: str
    sitting: str | None
    receipt: str | None
    uncertainty: dict

    @classmethod
    def parse(cls, raw):
        try:
            m = cls(**raw)
        except (TypeError, KeyError) as e:
            raise CameraMapError("invalid measurement record") from e
        if m.status not in {"accepted", "candidate", "missing"}:
            raise CameraMapError("unknown measurement status")
        if not isinstance(m.uncertainty, dict) or not m.uncertainty.get("note"):
            raise CameraMapError("per-point uncertainty (including explicit unknown) required")
        bound = m.uncertainty.get("plus_minus")
        if bound is not None and (not _number(bound) or bound < 0):
            raise CameraMapError("invalid uncertainty bound")
        interval = m.uncertainty.get("interval")
        if interval is not None and (not isinstance(interval, list) or len(interval) != 2
                                     or not all(_number(x) for x in interval) or not _number(m.value)
                                     or not interval[0] <= m.value <= interval[1]):
            raise CameraMapError("invalid uncertainty interval")
        if m.status == "missing":
            if m.value is not None:
                raise CameraMapError("missing measurement must be null")
        elif m.value is None or not all(isinstance(v, str) and v for v in (m.sitting, m.receipt)):
            raise CameraMapError("measurement needs value, sitting and receipt")
        return m

    def use(self, live, label):
        if self.status == "missing" or (live and self.status != "accepted"):
            raise CameraMapError(f"{label}: {self.status} measurement is not usable" + (" live" if live else ""))
        return self.value


@dataclass(frozen=True)
class CameraMap:
    profile: str
    sha256: str
    settings: dict
    focal: Measurement
    latency: Measurement
    interpolation: Measurement
    axes: dict
    live: bool = False

    def scalar(self, name):
        return getattr(self, name).use(self.live, name)

    def points(self, axis, sign):
        if axis not in {"yaw", "pitch"}:
            raise CameraMapError(f"unknown camera axis: {axis}")
        return self.axes[axis]["positive" if sign >= 0 else "negative"]

    def _linear(self):
        if self.scalar("interpolation") != "piecewise_linear":
            raise CameraMapError("unsupported camera interpolation model")

    def rate(self, axis, stick):
        if not _number(stick) or abs(stick) > 1:
            raise CameraMapError("stick must be finite and within [-1,1]")
        if stick == 0:
            return 0.0  # neutral command model, not a claim about attach drift
        points = self.points(axis, stick)
        x = abs(stick)
        for d, m in points:
            if x == d:
                return math.copysign(m.use(self.live, f"{axis} {stick:+g}"), stick)
        previous = (0.0, 0.0)
        for d, m in points:
            if x < d:
                self._linear()
                x0, y0 = previous
                if isinstance(y0, Measurement):
                    y0 = y0.use(self.live, f"{axis} lower bracket")
                y1 = m.use(self.live, f"{axis} upper bracket")
                return math.copysign(y0 + (y1 - y0) * (x - x0) / (d - x0), stick)
            previous = (d, m)
        raise CameraMapError(f"{axis}: missing rate coverage for {stick}")

    def table(self, axis, sign):
        self._linear()
        points = self.points(axis, sign)
        if not points or points[-1][0] != 1:
            raise CameraMapError(f"{axis}: missing full-stick coverage")
        table = ((0.0, 0.0),) + tuple((d, m.use(self.live, f"{axis} {sign:+g} * {d}")) for d, m in points)
        if table[-1][1] <= 0:
            raise CameraMapError(f"{axis}: missing positive rate coverage")
        return table

    def stick(self, axis, rate):
        if not _number(rate):
            raise CameraMapError("rate must be finite")
        if rate == 0:
            return 0.0
        # A complete directional table is required for inversion/saturation.
        points = self.table(axis, rate)
        mag = min(abs(rate), points[-1][1])
        for (d0, r0), (d1, r1) in zip(points, points[1:]):
            if mag <= r1:
                return math.copysign(d0 + (d1 - d0) * (mag - r0) / (r1 - r0), rate)
        raise CameraMapError(f"{axis}: missing inverse coverage")

    def require_controller(self):
        self.scalar("focal")
        self.scalar("latency")
        for axis in ("yaw", "pitch"):
            for sign in (-1, 1):
                self.table(axis, sign)
        for axis, stick in (("yaw", .45), ("yaw", -.45), ("pitch", 1.0), ("pitch", -.5)):
            if self.rate(axis, stick) == 0:
                raise CameraMapError(f"{axis} {stick}: controller timed turn needs nonzero response")
        return self

    def receipt(self):
        return {"profile": self.profile, "sha256": self.sha256, "live": self.live,
                "settings": self.settings}


def load_camera_map(profile=LEGACY, *, live=False):
    """A built-in profile name or explicit JSON path. No data/ or corpus access."""
    path = MAPS / f"{profile}.json" if str(profile) in {LEGACY, "alt-247-124"} else Path(profile)
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
        if data["schema"] != "rivals-camera-map-v1" or not isinstance(data["profile"], str) or not data["profile"]:
            raise CameraMapError("unsupported camera map schema/profile")
        if not isinstance(data["settings"], dict):
            raise CameraMapError("camera settings record required")
        focal, latency, interpolation = (Measurement.parse(data[k]) for k in ("focal", "latency", "interpolation"))
        for label, m in (("focal", focal), ("latency", latency)):
            if m.value is not None and (not _number(m.value) or m.value <= 0):
                raise CameraMapError(f"{label} must be a positive finite number")
        if interpolation.value not in (None, "piecewise_linear"):
            raise CameraMapError("unsupported camera interpolation model")
        axes = {}
        for axis in ("yaw", "pitch"):
            axes[axis] = {}
            for direction in ("positive", "negative"):
                points, last_d, last_r = [], 0.0, -1.0
                for point in data[axis][direction]:
                    d, m = point["stick"], Measurement.parse(point["measurement"])
                    if not _number(d) or not last_d < d <= 1:
                        raise CameraMapError("stick knots must strictly increase in (0,1]")
                    if m.value is not None:
                        if not _number(m.value) or m.value < last_r or m.value < 0:
                            raise CameraMapError("rate knots must be nonnegative, finite and nondecreasing")
                        last_r = m.value
                    points.append((d, m))
                    last_d = d
                axes[axis][direction] = tuple(points)
        return CameraMap(data["profile"], hashlib.sha256(raw).hexdigest(), data["settings"],
                         focal, latency, interpolation, axes, live)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise CameraMapError(f"invalid camera map {path}: {e}") from e
