"""Live admission for whole camera maps; no accepted profile ships in this delta.

Only independent review may add a profile -> (record path, SHA-256) entry to
REVIEWED_ACCEPTANCES. Neither CLI arguments nor map status strings extend it.
The pinned record binds a whole map, settings and retained evidence bytes.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .camera_map import CameraMapError, load_camera_map

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_ACCEPTANCES: dict[str, tuple[str, str]] = {}
YAW_COMPAT_ACCEPTANCES = {
    "alt-247-124": ("agent/camera_maps/alt-247-124-yaw-compat.json",
                    "a55979781567808b2b490032759d76e64e6b34fccb4594594c4e50c81a5df7df"),
}


@dataclass(frozen=True)
class YawCompatibility:
    """A scoped command whitelist, deliberately not a complete CameraMap."""
    knots: tuple
    receipt: dict

    def yaw_command(self, value):
        if value not in self.knots or isinstance(value, bool):
            raise CameraMapError("compatibility yaw must be an exact measured signed knot")
        return value


def load_yaw_compatibility(profile, *, settings_match):
    camera = load_camera_map(profile)  # candidate data stays candidate globally
    try:
        path, digest = YAW_COMPAT_ACCEPTANCES[camera.profile]
        record = json.loads(_pinned_bytes(path, digest))
        if (record["schema"] != "rivals-yaw-compat-acceptance-v1"
                or record["scope"] != "measured_yaw_knots_pixel_compat_only"
                or record["profile"] != camera.profile or record["map_sha256"] != camera.sha256
                or record["settings"] != camera.settings or settings_match != camera.profile):
            raise CameraMapError("scoped camera acceptance/settings mismatch")
        knots = tuple(sorted(sign * d for sign in (-1, 1) for d, m in camera.points("yaw", sign)
                             if m.value is not None and m.status in {"candidate", "accepted"}))
        if list(knots) != record["yaw_knots"] or len(knots) != 14:
            raise CameraMapError("scoped yaw knots missing")
        if (record["missing"] != ["focal", "pitch_degrees", "latency", "interpolation"]
                or any(getattr(camera, k).status != "missing" for k in ("focal", "latency", "interpolation"))
                or any(m.status != "missing" for sign in (-1, 1) for _, m in camera.points("pitch", sign))
                or record["pitch_sign"]["positive_ry"] != "look_up"
                or record["pitch_sign"]["negative_ry"] != "look_down"):
            raise CameraMapError("scoped holes or pitch sign changed; re-review required")
        if not record["evidence"]:
            raise CameraMapError("scoped evidence required")
        for source, pin in record["evidence"].items():
            _pinned_bytes(source, pin)
        return YawCompatibility(knots, {**camera.receipt(), "scope": record["scope"],
                                "record": path, "record_sha256": digest, "missing": record["missing"],
                                "pitch_sign": record["pitch_sign"], "settings_match": settings_match})
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise CameraMapError(f"invalid scoped camera acceptance: {e}") from e


def _pinned_bytes(relative, digest):
    if not isinstance(relative, str) or not isinstance(digest, str) or len(digest) != 64:
        raise CameraMapError("invalid acceptance artifact pin")
    path = (ROOT / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(ROOT.resolve()):
        raise CameraMapError("acceptance artifact must stay within repository")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise CameraMapError(f"acceptance artifact hash mismatch: {relative}")
    return raw


def load_reviewed_camera_map(profile, *, settings_match):
    """Validate before hardware. The settings declaration is operator evidence,
    not pixel verification; it must name this exact reviewed profile.
    """
    camera = load_camera_map(profile, live=True).require_controller()
    try:
        entry = REVIEWED_ACCEPTANCES.get(camera.profile)
        if entry is None:
            raise CameraMapError(f"no reviewed camera acceptance for {camera.profile}")
        record_path, record_sha256 = entry
        record = json.loads(_pinned_bytes(record_path, record_sha256))
        if (record["schema"] != "rivals-camera-acceptance-v1"
                or record["scope"] != "controller_complete"
                or record["profile"] != camera.profile
                or record["map_sha256"] != camera.sha256
                or record["settings"] != camera.settings):
            raise CameraMapError("reviewed acceptance does not match camera map/settings")
        evidence = record["evidence"]
        if not isinstance(evidence, dict) or not evidence:
            raise CameraMapError("reviewed acceptance requires pinned evidence")
        for path, digest in evidence.items():
            _pinned_bytes(path, digest)
        if settings_match != camera.profile:
            raise CameraMapError("explicit operator settings match must name the reviewed profile")
        receipt = {"record": record_path, "sha256": record_sha256,
                   "evidence": evidence, "operator_settings_match": settings_match}
        return camera, receipt
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise CameraMapError(f"invalid reviewed camera acceptance: {e}") from e
