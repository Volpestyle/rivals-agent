"""Portable, hash-bound labels and compact features of the already admitted cohort.

Export receives arrays from the existing admission loader; it admits no new source.
Cloud readers open only fixed session names from that export, never videos or loggers.
"""
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import torch

from . import steps, train
from .explore_chunks import ChunkBatches
from .explore_chunks_train import DEV_IDS, TRAIN_IDS
from .spatial_yaw_cache import INPUTS, compact_indices, sha, write_new

TENSORS = ("act", "act_known", "camera", "camera_known", "valid", "prev", "regime", "row_frame")


def export_labels(arrays, dev, root):
    """Called only after load_manifest/authenticate_cohort by the Mac cache owner."""
    root = Path(root)
    if (root / "dataset.json").exists():
        old = json.loads((root / "dataset.json").read_text())
        expected = [(role, a.session.session_id, a.session.sha256)
                    for role, group in (("train", arrays), ("dev", dev)) for a in group]
        train.require([(e["role"], e["session"], e["steps_sha256"]) for e in old["sessions"]] == expected
                      and old["inputs_sha256"] == INPUTS, "existing label export differs")
        for entry in old["sessions"]:
            dest = root / entry["session"]
            train.require(sha(dest / "labels.pt") == entry["labels_sha256"]
                          and sha(dest / "completed.json") == entry["features_sha256"], "label export corrupted")
        return old
    entries = []
    for role, group in (("train", arrays), ("dev", dev)):
        for arr in group:
            dest = root / arr.session.session_id
            path = dest / "labels.pt"
            payload = {"session": asdict(arr.session), "runs": arr.runs,
                       "tensors": {name: getattr(arr, name) for name in TENSORS}}
            # Existing partial exports are refused, just like partial feature stages.
            with path.open("xb") as stream:
                torch.save(payload, stream)
            entries.append({"session": arr.session.session_id, "role": role,
                            "steps_sha256": arr.session.sha256, "labels_sha256": sha(path),
                            "features_sha256": sha(dest / "completed.json")})
    value = {"format": "spatial-yaw-data-v1", "inputs_sha256": INPUTS, "sessions": entries,
             "stats": steps.train_statistics([a.session for a in arrays])}
    write_new(root / "dataset.json", value)
    return value


class SpatialArrays:
    def __init__(self, root, entry, grid):
        root = Path(root) / entry["session"]
        train.require(sha(root / "labels.pt") == entry["labels_sha256"], "labels hash differs")
        train.require(sha(root / "completed.json") == entry["features_sha256"], "feature receipt differs")
        payload = torch.load(root / "labels.pt", map_location="cpu", weights_only=True)
        self.session = steps.Session(**payload["session"])
        train.require(self.session.session_id == entry["session"] and self.session.split == "train"
                      and self.session.sha256 == entry["steps_sha256"], "label source differs")
        self.__dict__.update(payload["tensors"])
        self.runs = payload["runs"]
        self.lag, self.regimes, self.press_windows = 0, ("normal",), None
        receipt = json.loads((root / "completed.json").read_text())
        train.require(receipt["exit"] == 0 and receipt["identity"]["session"] == self.session.session_id
                      and receipt["identity"]["steps_sha256"] == self.session.sha256, "feature source differs")
        names = {"frame_ids.npy"} | {f"{v}-{g}.npy" for v in ("global", "crop") for g in {4, grid}}
        for name in sorted(names):
            pin = receipt["files"][name]
            train.require((root / name).stat().st_size == pin["bytes"]
                          and sha(root / name) == pin["sha256"], "feature bytes differ")
        self.ids = np.load(root / "frame_ids.npy", mmap_mode="r", allow_pickle=False)
        self.features = {(v, g): np.load(root / f"{v}-{g}.npy", mmap_mode="r", allow_pickle=False)
                         for v in ("global", "crop") for g in {4, grid}}
        train.require(self.ids.dtype == np.int64, "frame ids dtype differs")
        for (_, g), values in self.features.items():
            train.require(values.shape == (len(self.ids), g*g*1024) and values.dtype == np.float16,
                          "compact features shape/dtype differs")
        for start, end in self.runs:
            compact_indices(self.ids, self.row_frame[start:end].numpy())
        self.grid, self.width = grid, (16 + grid*grid)*1024
        # Batches reads shapes, but frames=False prevents any pixel allocation/read.
        self.global_frames = self.crop_frames = self.hud_frames = np.empty((0, 1, 1, 3), dtype=np.uint8)
        self.manifest = entry

    def frames(self, rows):
        ix = compact_indices(self.ids, self.row_frame[rows].numpy())
        values = [torch.from_numpy(np.concatenate((self.features[v, 4][ix],
                                                  self.features[v, self.grid][ix]), axis=-1))
                  for v in ("global", "crop")]
        return (*values, torch.zeros(len(rows), 1))


def load_dataset(root, digest, grid, *, dev_only=False):
    root = Path(root)
    train.require(grid in (4, 8) and sha(root / "dataset.json") == digest, "dataset/grid pin differs")
    value = json.loads((root / "dataset.json").read_text())
    train.require(value["format"] == "spatial-yaw-data-v1" and value["inputs_sha256"] == INPUTS,
                  "wrong admitted source")
    # Validate the entire allowlist before touching a single payload path.
    entries = value["sessions"]
    train.require(len(entries) == 10 and all(e["role"] in ("train", "dev") for e in entries), "wrong roster")
    for role, expected in (("train", TRAIN_IDS), ("dev", DEV_IDS)):
        names = [e["session"] for e in entries if e["role"] == role]
        train.require(len(names) == len(expected) and set(names) == expected, "wrong admitted roster")
    groups = [[SpatialArrays(root, e, grid) for e in entries if e["role"] == role]
              if role != "train" or not dev_only else [] for role in ("train", "dev")]
    if not dev_only:
        train.require(steps.train_statistics([a.session for a in groups[0]]) == value["stats"], "TRAIN stats differ")
    return *groups, value["stats"]


class SpatialBatches(ChunkBatches):
    def __init__(self, arrays, **kwargs):
        super().__init__(arrays, frames=False, horizon=1, **kwargs)

    def batch(self, ids, generator=None, **kwargs):
        out = super().batch(ids, generator, **kwargs)
        g = torch.zeros(len(ids), self.window, self.arrays[0].width, dtype=torch.float16)
        c = torch.zeros_like(g)
        for i, w in enumerate(ids):
            si, start, n, _ = self.windows[w]
            gf, cf, _ = self.arrays[si].frames(torch.arange(start, start+n))
            g[i, :n], c[i, :n] = gf, cf
        out["global"], out["crop"], out["hud"] = g, c, torch.zeros(len(ids), self.window, 1)
        return out
