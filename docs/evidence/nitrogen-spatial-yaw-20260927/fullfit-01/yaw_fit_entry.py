"""Place at cloud/yaw_fit_entry.py beside the unchanged accepted guard package.

The SDK mounts the complete cloud tree as immutable source. Its payload manifest
pins every policy/agent dependency and this bridge is pinned by source inventory.
"""
import hashlib
import importlib
import json
from pathlib import Path
import sys


def verify_payload(expected_sha256):
    cloud = Path(__file__).resolve().parent
    manifest_path = cloud / "yaw-payload-manifest.json"
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("payload manifest pin differs")
    manifest = json.loads(raw)
    payload = cloud / "yaw_payload"
    for relative, digest in manifest["files"].items():
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts or "\\" in relative:
            raise ValueError("invalid payload path")
        path = payload / part
        if path.is_symlink() or not path.resolve().is_relative_to(payload.resolve()):
            raise ValueError("payload escapes source mount")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("payload bytes differ: " + relative)
    for package in ("policy", "agent"):
        module = sys.modules.get(package)
        if module is not None and not Path(module.__file__).resolve().is_relative_to(payload):
            raise ValueError("another workload package is already imported")
    if str(payload) not in sys.path:
        sys.path.insert(0, str(payload))
    return importlib.import_module("policy.range_bc.spatial_yaw_train")


def fit(root, *, payload_manifest_sha256, spec_path, spec_sha256):
    return verify_payload(payload_manifest_sha256).fit(root, spec_path=spec_path, spec_sha256=spec_sha256)


def evaluate(root, *, payload_manifest_sha256, spec_path, spec_sha256):
    return verify_payload(payload_manifest_sha256).evaluate(root, spec_path=spec_path, spec_sha256=spec_sha256)
