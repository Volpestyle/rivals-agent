"""EXPLORATORY unique-frame DINO/HUD store, separate from all range/CM3 caches."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from policy import idm_targets as T
from policy.idm import decode, temporal
from policy.idm.frames import FrameStore, FORMAT as FRAME_FORMAT, HUD_SHAPE
from policy.range_bc import cm3_features

FORMAT = "rivals-idm-temporal-features-v1"
RECIPE = "idm-rgb448-area256-cm3-preprocess-global-v1"


def prepare(targets, target_sha, *, video, demo, out, backbone, device, progress=lambda _: None):
    """Mac-only, stream each selected original frame once; write manifests last.

    Caller has already admitted targets and pinned this preparation recipe. The
    original media hash must match; transcode relocation is deliberately refused
    until its timestamp-equivalence path has been reviewed for this new store.
    """
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("real preparation is Mac arm64 only")
    video = Path(video)
    if "spidey clips" in str(video.resolve()).lower():
        raise ValueError("unlabelled clip library is outside this paired-data job")
    before = video.stat()
    if T.sha256(video) != targets.header["media_sha256"]:
        raise ValueError("source media mismatch; relocation requires reviewed equivalence")
    tb, pts, header = decode.read_demo_frames(demo, targets.header["source"]["imported_demo"]["sha256"])
    if header["media_sha256"] != targets.header["media_sha256"] or header["session_id"] != targets.session_id:
        raise ValueError("decoded frame table identity mismatch")
    for row in targets.rows:
        for key in ("frame0", "frame1"):
            f = row[key]
            if not 0 <= f["frame_index"] < len(pts) or pts[f["frame_index"]] != f["pts"]:
                raise ValueError("target PTS differs from decoded source table")
    colour = decode.cache.probe_colour(video, "ffprobe")
    decode.cache.check_colour(colour)
    if decode.cache.probe_size(video, "ffprobe") != [2560, 1440]:
        raise ValueError("only native 2560x1440 admitted source geometry")
    edge, _ = temporal.context_rows(targets, temporal.BANK)
    camera, _ = temporal.context_rows(targets, tuple(range(-8, 9)))
    keys = sorted({r["frame1"]["frame_index"] for _, context in edge + camera for r in context} |
                  {r["frame0"]["frame_index"] for r, _ in camera})
    if not keys:
        raise ValueError("no contiguous context to prepare")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    hashes = {k: hashlib.sha256() for k in ("frames", "hud", "features")}
    with (out / "frames.u8").open("xb") as fr, (out / "hud.u8").open("xb") as hd, \
            (out / "features.f32").open("xb") as ft:
        def sink(index, rgb, hud):
            # Reuse the pinned global 256x144 representation and DINO preprocessing;
            # this is a new 60 Hz source/frame contract, never the old CM3 cache.
            image = torch.from_numpy(rgb.copy()).permute(2, 0, 1)[None].float()
            image = F.interpolate(image, size=(144, 256), mode="area").round().clamp(0, 255).to(torch.uint8)
            pixels = cm3_features.preprocess(image.permute(0, 2, 3, 1), "global").to(device)
            with torch.no_grad():
                feature = backbone(pixels).cpu().numpy().astype("<f4")
            if feature.shape != (1, 6528) or not np.isfinite(feature).all():
                raise ValueError("invalid frozen feature output")
            for name, stream, data in (("frames", fr, decode.grey(rgb).tobytes()),
                                       ("hud", hd, hud.tobytes()), ("features", ft, feature.tobytes())):
                stream.write(data)
                hashes[name].update(data)
            if index % 300 == 0:
                progress({"n": index + 1, "total": len(keys)})
        shown, actual_tb = decode._decode(video, keys, sink, "ffmpeg", 2)
    if actual_tb != tb or shown != [pts[k] for k in keys]:
        raise ValueError("decoded PTS/timebase mismatch")
    after = video.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during preparation")
    common = {"session_id": targets.session_id, "media_sha256": targets.header["media_sha256"],
              "frame_indices": keys, "frame_pts": shown, "target_sha256": target_sha,
              "scope": "EXPLORATORY", "timebase": tb}
    frames = {**common, "format": FRAME_FORMAT, "height": 252, "width": 448,
              "hud_shape": list(HUD_SHAPE), "frames_sha256": hashes["frames"].hexdigest(),
              "hud_sha256": hashes["hud"].hexdigest()}
    features = {**common, "format": FORMAT, "feature_dim": 6528, "dtype": "<f4",
                "features_sha256": hashes["features"].hexdigest(), "assets": backbone.asset_receipt,
                "recipe": RECIPE, "decode_graph": decode.GRAPH,
                "frame_manifest_sha256": hashlib.sha256(json.dumps(frames, sort_keys=True).encode()).hexdigest()}
    (out / "frames.json").write_text(json.dumps(frames, sort_keys=True), encoding="utf-8")
    (out / "features.json").write_text(json.dumps(features, sort_keys=True), encoding="utf-8")
    return features


class FeatureStore:
    def __init__(self, directory, targets, target_sha, *, manifest_sha256):
        path = Path(directory) / "features.json"
        if T.sha256(path) != manifest_sha256:
            raise ValueError("feature manifest pin mismatch")
        self.manifest = json.loads(path.read_text(encoding="utf-8"))
        m = self.manifest
        if (m.get("format") != FORMAT or m.get("scope") != "EXPLORATORY" or m.get("dtype") != "<f4"
                or m.get("feature_dim") != 6528 or m.get("session_id") != targets.session_id
                or m.get("target_sha256") != target_sha or m.get("media_sha256") != targets.header["media_sha256"]
                or m.get("recipe") != RECIPE or m.get("decode_graph") != decode.GRAPH):
            raise ValueError("feature identity/format mismatch")
        if T.sha256(Path(directory) / "frames.json") != m["frame_manifest_sha256"]:
            raise ValueError("frame manifest pin mismatch")
        self.frames = FrameStore(directory, verify=True)
        if self.frames.keys != m["frame_indices"] or self.frames.frame_pts != m["frame_pts"]:
            raise ValueError("feature frame index/PTS mismatch")
        if self.frames.keys != sorted(set(self.frames.keys)):
            raise ValueError("feature frame indices must be unique and sorted")
        file = Path(directory) / "features.f32"
        if file.stat().st_size != len(self.frames.keys) * 6528 * 4 or T.sha256(file) != m["features_sha256"]:
            raise ValueError("feature array length/hash mismatch")
        self.values = np.memmap(file, dtype="<f4", mode="r", shape=(len(self.frames.keys), 6528))
        self.index = {f: i for i, f in enumerate(self.frames.keys)}

    def inputs(self, rows):
        keys = [r["frame1"]["frame_index"] for r in rows]
        for r in rows:
            f = r["frame1"]
            if self.frames.pts(f["frame_index"]) != f["pts"]:
                raise ValueError("temporal frame PTS differs from target")
        features = np.asarray(self.values[[self.index[k] for k in keys]])
        if not np.isfinite(features).all():
            raise ValueError("nonfinite cached features")
        hud = self.frames.hud(keys)
        if hud is None:
            raise ValueError("missing temporal HUD frame")
        return torch.from_numpy(features), torch.from_numpy(hud).permute(0, 3, 1, 2).float() / 255
