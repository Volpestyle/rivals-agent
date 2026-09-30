"""Select an explicit expert cohort while new feature shards are arriving."""
import json
from pathlib import Path
import re


def expert_dirs(root, sessions=None, label_source=None):
    root = Path(root)
    names = sorted(p.name for p in root.iterdir() if (p / "meta.json").is_file()) if sessions is None else sessions
    if not names or len(set(names)) != len(names):
        raise ValueError("expert cohort must be nonempty and contain no duplicate sessions")
    dirs, sources = [], set()
    for name in names:
        if not re.fullmatch(r"expert-\d+-s\d+", name):
            raise ValueError(f"invalid expert shard: {name}")
        d = root / name
        meta = json.loads((d / "meta.json").read_text())
        if meta["session"] != name:
            raise ValueError(f"expert session mismatch: {name}")
        for f in ("feats.npy", "gray_g.npy", "gray_c.npy", "green.npy", "targets.npz"):
            if not (d / f).is_file():
                raise ValueError(f"incomplete expert shard: {name}/{f}")
        sources.add(meta.get("relabel", {}).get("calibration", meta.get("calibration", {})).get("source"))
        dirs.append(d)
    if None in sources or len(sources) != 1:
        raise ValueError("expert cohort mixes label sources or has unknown provenance")
    if label_source is not None and sources != {label_source}:
        raise ValueError(f"expert label source differs from requested {label_source}")
    return dirs
