"""IDM bridge copied to cloud/idm_entry.py in the immutable native source mount.

No Modal resources or budgets are created here. The unchanged shared runner owns
stage claims, deadlines, redelivery and teardown.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import sys


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_payload(cloud, expected_sha256):
    cloud = Path(cloud).resolve()
    manifest_path = cloud / "idm-payload-manifest.json"
    if manifest_path.is_symlink() or digest(manifest_path) != expected_sha256:
        raise ValueError("IDM payload manifest pin differs")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("format") != "idm-native-payload-v1" or not manifest.get("files"):
        raise ValueError("IDM payload manifest format")
    payload = cloud / "idm_payload"
    if payload.is_symlink() or not payload.is_dir():
        raise ValueError("IDM payload root differs")
    actual = {p.relative_to(payload).as_posix() for p in payload.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts}
    if actual != set(manifest["files"]):
        raise ValueError("IDM payload inventory differs")
    for relative, pin in manifest["files"].items():
        part = PurePosixPath(relative)
        if (part.is_absolute() or ".." in part.parts or "\\" in relative
                or ":" in relative or str(part) != relative):
            raise ValueError("invalid IDM payload path")
        path = payload / relative
        if path.is_symlink() or not path.resolve().is_relative_to(payload):
            raise ValueError("IDM payload escapes source mount")
        if digest(path) != pin:
            raise ValueError("IDM payload bytes differ: " + relative)
    return payload, manifest


def activate(payload):
    for package in ("policy", "agent", "perception", "scripts"):
        for name, module in tuple(sys.modules.items()):
            if name != package and not name.startswith(package + "."):
                continue
            paths = list(getattr(module, "__path__", ()))
            origin = getattr(module, "__file__", None)
            if origin:
                paths.append(origin)
            if not paths or any(not Path(p).resolve().is_relative_to(payload) for p in paths):
                raise ValueError("another workload package is already imported: " + name)
    if str(payload) not in sys.path:
        sys.path.insert(0, str(payload))


def input_ref(ref):
    path = Path(ref["path"])
    if not path.is_absolute() or not path.is_relative_to("/inputs") or ".." in path.parts:
        raise ValueError("IDM input reference outside read-only mount")
    if path.is_symlink() or digest(path) != ref["sha256"]:
        raise ValueError("IDM input reference pin differs")
    return str(path)


def run(root, *, payload_manifest_sha256, phase, input_volume_id, output_volume_id):
    payload, manifest = verify_payload(Path(__file__).resolve().parent, payload_manifest_sha256)
    activate(payload)
    worker = importlib.import_module("policy.idm.refit_stages")
    if phase not in (*worker.ARTIFACTS, "probe") or Path(root).name != phase:
        raise ValueError("IDM stage name differs")
    kwargs = dict(manifest=input_ref(manifest["inputs"]),
                  manifest_sha256=manifest["inputs"]["sha256"],
                  registry=input_ref(manifest["registry"]),
                  input_volume_id=input_volume_id, output_volume_id=output_volume_id)
    if phase == "probe":
        return worker.probe(root, **kwargs)
    return worker.stage(root, phase=phase, **kwargs)


def run_local(root, *, payload_manifest_sha256, phase, input_volume_id, output_volume_id):
    """Fresh local-disk route; shared guard still owns every stage boundary."""
    payload, manifest = verify_payload(Path(__file__).resolve().parent, payload_manifest_sha256)
    activate(payload)
    worker = importlib.import_module("policy.idm.local_run")
    return worker.run(root, phase=phase, manifest=input_ref(manifest["inputs"]),
                      manifest_sha256=manifest["inputs"]["sha256"],
                      registry=input_ref(manifest["registry"]), input_volume_id=input_volume_id,
                      output_volume_id=output_volume_id)


def run_resumable(root, *, payload_manifest_sha256, phase, input_volume_id, output_volume_id,
                  scientific_identity, commit=None, resume_state=None, local_data_root=None):
    """v2 supplies local staging and durable output commit; IDM owns epoch state."""
    payload, manifest = verify_payload(Path(__file__).resolve().parent, payload_manifest_sha256)
    activate(payload)
    worker = importlib.import_module("policy.idm.resumable_run")
    return worker.run(root, phase=phase, manifest=input_ref(manifest["inputs"]),
                      manifest_sha256=manifest["inputs"]["sha256"], registry=input_ref(manifest["registry"]),
                      input_volume_id=input_volume_id, output_volume_id=output_volume_id,
                      scientific_identity=scientific_identity, commit=commit, resume_state=resume_state,
                      local_data_root=local_data_root)


def validate_epoch(root, *, payload_manifest_sha256, scientific_identity, source_ref=None):
    payload, _ = verify_payload(Path(__file__).resolve().parent, payload_manifest_sha256)
    activate(payload)
    worker = importlib.import_module("policy.idm.epoch_resume")
    return worker.validate_resume(root, scientific_identity=scientific_identity, source_ref=source_ref)
