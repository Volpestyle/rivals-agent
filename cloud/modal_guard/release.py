"""Future packets pin one shared checkout's release manifest, never copied helpers."""
from pathlib import Path

from .common import atomic, read, require, sha256


def freeze(root):
    root = Path(root)
    paths = sorted(p for p in root.glob("*.py") if p.is_file())
    manifest = {"format": "modal-guard-release-v1", "version": "1.0.1", "sdk": "1.5.5",
                "files": {p.name: sha256(p) for p in paths}}
    atomic(root / "RELEASE.json", manifest, fresh=True)
    return sha256(root / "RELEASE.json")


def verify(root, expected):
    root = Path(root).resolve()
    manifest = root / "RELEASE.json"
    require(sha256(manifest) == expected, "shared library release pin mismatch")
    value = read(manifest)
    require(value["format"] == "modal-guard-release-v1" and value["version"] == "1.0.1"
            and value["sdk"] == "1.5.5", "unsupported release")
    require(set(value["files"]) == {p.name for p in root.glob("*.py")}, "unlisted library module")
    for name, digest in value["files"].items():
        require(Path(name).name == name and not (root / name).is_symlink()
                and sha256(root / name) == digest, "shared library bytes changed")
    return value


def reviewed(workspace_root, expected):
    receipt = Path(workspace_root) / "reviews" / (expected + ".json")
    require(receipt.is_file(), "spend guard needs fit-review before use")
    value = read(receipt)
    require(value["reviewer"] == "fit-review" and value["decision"] == "LAND"
            and value["release_sha256"] == expected and value["scope"] == "spend-guard",
            "missing matching spend-guard acceptance")
    # Receipt is lead-installed authority, not a self-issued command-line boolean.
    return value
