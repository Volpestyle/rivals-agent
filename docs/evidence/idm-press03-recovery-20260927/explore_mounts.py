"""Authenticate Modal's volume aliases while preserving logical mount paths.

Uses the namespace checks reviewed in cm3_run (770d000). No corpus selection.
"""

from pathlib import Path
import re

MOUNT_ROOTS = ("/inputs", "/outputs")
MODAL_VOLUMES = Path("/__modal/volumes")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_mounts(pins):
    require(set(pins) == set(MOUNT_ROOTS), "both pinned mount aliases required")
    require(len(set(pins.values())) == 2, "distinct volumes required")
    targets = {}
    for alias, volume in pins.items():
        require(isinstance(volume, str) and re.fullmatch(r"vo-[a-zA-Z0-9]+", volume),
                "invalid volume ID")
        root, expected = Path(alias), MODAL_VOLUMES / volume
        require(root.is_symlink() and root.readlink() == expected
                and root.resolve(strict=True) == expected and expected.is_dir()
                and not expected.is_symlink(), "mount differs from pinned volume")
        targets[root] = expected
    return targets


def logical_path(path, targets):
    path = Path(path)
    root = next((root for root in targets if path.is_relative_to(root)), None)
    require(root is not None, "path outside logical mounts")
    require(".." not in path.parts, "mount path traversal")
    child = root
    for part in path.relative_to(root).parts:
        child /= part
        require(not child.is_symlink(), "child symlink in mount namespace")
    require(path.resolve(strict=False) == targets[root] / path.relative_to(root),
            "path differs from pinned volume")
    return path
