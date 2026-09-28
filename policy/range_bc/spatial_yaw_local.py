"""Verified ephemeral cache for the unchanged fit and evaluation stages.

The shared guard still owns fit completion and partial-fit refusal. A fresh
container may copy inputs again for a completed fit's evaluation; it never refits.
"""
import json
from pathlib import Path
import tempfile

from .spatial_yaw_cache import sha, write_new
from .spatial_yaw_io_probe import copy_dataset


def prepare_cache(source, dataset_sha, spec_sha, *, parent=None):
    for digest in (dataset_sha, spec_sha):
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid local cache identity")
    root = Path(tempfile.gettempdir() if parent is None else parent) / ("yaw-fit-cache-" + spec_sha)
    dataset = root / "dataset"
    identity = {"dataset_sha256": dataset_sha, "spec_sha256": spec_sha,
                "source": str(Path(source).resolve())}
    if root.exists():
        marker = root / "copy-complete.json"
        if root.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise ValueError("partial local cache refused")
        before = sha(marker)
        receipt = json.loads(marker.read_bytes())
        if receipt["identity"] != identity or not receipt["copy"]["source_and_destination_verified"]:
            raise ValueError("local cache identity differs")
        for relative, pin in receipt["copy"]["files"].items():
            path = dataset / relative
            if (Path(relative).is_absolute() or ".." in Path(relative).parts or "\\" in relative
                    or path.is_symlink() or not path.resolve().is_relative_to(dataset.resolve())
                    or not path.is_file() or path.stat().st_size != pin["bytes"] or sha(path) != pin["sha256"]):
                raise ValueError("local cache bytes differ")
        if sha(dataset / "dataset.json") != dataset_sha or sha(marker) != before:
            raise ValueError("local cache receipt changed")
        print("Completed local cache streaming verification PASS", flush=True)
        return dataset
    root.mkdir(exist_ok=False)
    copy = copy_dataset(source, dataset, dataset_sha)
    write_new(root / "copy-complete.json", {"identity": identity, "copy": copy})
    print(f"Local cache copy/hash PASS: {copy['bytes']} bytes in {copy['seconds']:.3f}s", flush=True)
    return dataset
