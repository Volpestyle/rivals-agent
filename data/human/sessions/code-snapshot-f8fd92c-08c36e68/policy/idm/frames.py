"""The IDM's frame store: what the model reads for one session, keyed by the recording's video frame index.

Format "rivals-idm-frames-v1", one directory per session:
    frames.json   {format, session_id, media_sha256, width, height, hud_shape, frame_indices (sorted, unique),
                   frame_pts (each frame's pts in the recording, parallel to frame_indices), frames_sha256, hud_sha256}
    frames.u8     len(frame_indices) x height x width, grey (uint8), the frame downscaled with area filtering
    hud.u8        len(frame_indices) x 80 x 200 x 3 (RGB, uint8): the native M&K HUD crop (policy.range_bc.hudmap's
                  hud_stream, the same crop the range fit reads)

The store holds the frames a target file's windows need: for every interval, its end frame and the frames at
+-2, +-4, ... +-16 video frames (a +-8-interval window at 60 Hz from a 120 fps recording). Filling it from the video
is a decode job and is not written here. That job must load the pinned sealed denylist and refuse a denylisted
session id or media before it decodes, record the media_sha256 it decoded and each frame's pts (policy.idm.train.bind
refuses a store whose media or pts differ from the target file's, review K2). Opening a store refuses a denylisted
session id or media (budget it with the lane doc's F10 plan); tests write synthetic stores with
`write_store`.
"""
from __future__ import annotations

import hashlib
import json
from bisect import bisect_left
from pathlib import Path

import numpy as np

FORMAT = "rivals-idm-frames-v1"
HUD_SHAPE = (80, 200, 3)


class StoreError(ValueError):
    pass


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_store(directory, *, session_id, media_sha256, frames, hud, pts):
    """Write a store from {frame_index: grey HxW uint8}, {frame_index: 80x200x3 uint8} and {frame_index: pts}
    (same keys)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    keys = sorted(frames)
    if keys != sorted(hud) or keys != sorted(pts):
        raise StoreError("frames, hud crops and pts must cover the same frame indices")
    h, w = frames[keys[0]].shape
    if any(frames[k].shape != (h, w) or frames[k].dtype != np.uint8 for k in keys):
        raise StoreError("every frame must be the same uint8 shape")
    if any(hud[k].shape != HUD_SHAPE or hud[k].dtype != np.uint8 for k in keys):
        raise StoreError(f"every HUD crop must be {HUD_SHAPE} uint8")
    np.stack([frames[k] for k in keys]).tofile(directory / "frames.u8")
    np.stack([hud[k] for k in keys]).tofile(directory / "hud.u8")
    manifest = {"format": FORMAT, "session_id": session_id, "media_sha256": media_sha256, "width": w, "height": h,
                "hud_shape": list(HUD_SHAPE), "frame_indices": keys,
                "frame_pts": [int(pts[k]) for k in keys], "frames_sha256": _sha(directory / "frames.u8"),
                "hud_sha256": _sha(directory / "hud.u8")}
    (directory / "frames.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


class FrameStore:
    """A session's store, memory-mapped. `verify=True` re-hashes both arrays against the manifest."""

    def __init__(self, directory, *, verify=False, denylist=None):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "frames.json").read_text(encoding="utf-8"))
        if self.manifest.get("format") != FORMAT:
            raise StoreError(f"not a {FORMAT} store")
        from policy import idm_targets
        try:
            idm_targets.refuse_sealed(self.manifest["session_id"], self.manifest["media_sha256"],
                                      denylist or idm_targets.load_denylist())
        except idm_targets.TargetError as e:
            raise StoreError(str(e)) from None
        if verify and (_sha(self.directory / "frames.u8") != self.manifest["frames_sha256"]
                       or _sha(self.directory / "hud.u8") != self.manifest["hud_sha256"]):
            raise StoreError("store arrays differ from their manifest")
        self.keys = self.manifest["frame_indices"]
        self.frame_pts = self.manifest["frame_pts"]
        if len(self.frame_pts) != len(self.keys):
            raise StoreError("frame_pts and frame_indices differ in length")
        n, h, w = len(self.keys), self.manifest["height"], self.manifest["width"]
        self.frames = np.memmap(self.directory / "frames.u8", dtype=np.uint8, mode="r", shape=(n, h, w))
        self.huds = np.memmap(self.directory / "hud.u8", dtype=np.uint8, mode="r", shape=(n, *HUD_SHAPE))

    @property
    def session_id(self):
        return self.manifest["session_id"]

    def _at(self, frame_index):
        k = bisect_left(self.keys, frame_index)
        return k if k < len(self.keys) and self.keys[k] == frame_index else None

    def pts(self, frame_index):
        """The stored frame's pts, or None when the store does not hold it."""
        k = self._at(frame_index)
        return None if k is None else self.frame_pts[k]

    def window(self, frame_index, offsets):
        """Grey frames at frame_index + each offset, [T, H, W] uint8; None if any is missing."""
        ks = [self._at(frame_index + o) for o in offsets]
        return None if any(k is None for k in ks) else np.asarray(self.frames[ks])

    def hud(self, frame_indices):
        """HUD crops at the given frame indices, [K, 80, 200, 3] uint8; None if any is missing."""
        ks = [self._at(f) for f in frame_indices]
        return None if any(k is None for k in ks) else np.asarray(self.huds[ks])
