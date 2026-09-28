"""Verified ephemeral inputs, from yaw 4487b42 and IDM local_store's copy contract."""
import hashlib
from pathlib import Path
import shutil
import tempfile

from .common import artifact, pinned, read, require, sha256
from .stages import claim


def validate(stage):
    access = stage.get("data_access", {})
    mode = access.get("mode", "local")
    if mode == "none":
        require(stage.get("kind") in ("diagnostic", "report"), "training inputs require local staging")
    elif mode == "sequential_stream":
        require(bool(access.get("reason")), "sequential streaming needs an explicit reason")
    else:
        require(mode == "local" and set(access) >= {"manifest_ref", "source_root", "argument"},
                "training Volume reads require hash-verified local staging")
        require(access["argument"].isidentifier(), "invalid local root argument")
    return mode


def prepare(access, *, parent=None):
    manifest = pinned(access["manifest_ref"])
    pins = manifest["files"]
    require(type(pins) is dict and pins, "empty local staging manifest")
    for value in pins.values():
        require(type(value["bytes"]) is int and value["bytes"] >= 0
                and isinstance(value["sha256"], str) and len(value["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in value["sha256"]), "invalid local file pin")
    source = Path(access["source_root"]).resolve(strict=True)
    base = Path(parent or tempfile.gettempdir()).resolve(strict=True)
    require(not base.is_relative_to(source) and not base.is_relative_to("/inputs")
            and not base.is_relative_to("/outputs"), "cache must be on local disk")
    root = base / ("modal-inputs-" + access["manifest_ref"]["sha256"])
    binding = {"manifest_sha256": access["manifest_ref"]["sha256"], "source": str(source), "files": pins}
    marker = root / "copy-complete.json"
    if root.exists():
        require(not root.is_symlink() and marker.is_file() and not marker.is_symlink(), "partial local cache refused")
        before = sha256(marker)
        require(read(marker)["binding"] == binding, "local cache identity mismatch")
    else:
        require(shutil.disk_usage(base).free >= sum(p["bytes"] for p in pins.values()) + (2 << 30),
                "insufficient local disk")
        root.mkdir()
        for relative, pin in pins.items():
            src, dst = artifact(source, relative), artifact(root, relative)
            require(src.is_file() and src.stat().st_size == pin["bytes"], "source size mismatch")
            dst.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with src.open("rb") as inp, dst.open("xb") as out:
                for block in iter(lambda: inp.read(1 << 20), b""):
                    out.write(block)
                    digest.update(block)
            require(digest.hexdigest() == pin["sha256"], "source copy hash mismatch")
        before = None
    # Verify destination on every entry. A previous container's receipt cannot
    # stand in for bytes on this container's /tmp disk.
    for relative, pin in pins.items():
        dst = artifact(root, relative)
        require(dst.is_file() and dst.stat().st_size == pin["bytes"] and sha256(dst) == pin["sha256"],
                "local copy hash mismatch")
    if before is None:
        claim(marker, {"binding": binding, "source_and_destination_verified": True})
    else:
        require(sha256(marker) == before, "local cache receipt changed")
    return root
