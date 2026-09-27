"""EXPLORATORY temporal-feature SSL pilot on an explicit inspected packet.

Only local pinned images/features. No discovery, original-video access, actions,
downstream evaluation or cloud provisioning. SSL loss is not a transfer result.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np
import torch

from policy import idm_targets as T
from policy.idm import ssl, ssl_sample
from policy.range_bc.cm3_features import FrozenDino, preprocess
from scripts.job_status import write

CONFIG_SHA = "1809f83e3bdb1609a501a610ad4a742f4fd8ae44d72ca4aa0df52d1f2ac8628d"
# Fixed union of inspected overlay regions at 256x144. Same mask required in
# both downstream arms; native HUD is separate and never inferred from this view.
MASK = ((0, 0, 256, 36), (0, 118, 256, 144), (0, 55, 88, 112),
        (230, 25, 256, 48), (124, 68, 133, 77), (114, 89, 145, 100))


def masked(rgb):
    if rgb.dtype != np.uint8 or rgb.shape[-3:] != (144, 256, 3):
        raise ValueError("uint8 RGB world input required")
    out = rgb.copy()
    for x0, y0, x1, y1 in MASK:
        out[..., y0:y1, x0:x1, :] = (124, 116, 104)
    return out


def packet(path, sha256, admission, admission_sha):
    path = Path(path)
    if T.sha256(path) != sha256:
        raise ValueError("sampled clip manifest pin mismatch")
    doc = json.loads(path.read_text())
    sources = {s["source_family"]: s for s in ssl_sample.admitted(admission, admission_sha)}
    if (doc.get("schema") != "rivals-ssl-inspected-clips-v1" or doc.get("semantic_labels") is not False
            or doc.get("admission_sha256") != admission_sha or not doc.get("inspector")):
        raise ValueError("inspected SSL-only packet required")
    counts, rates = Counter(), Counter()
    seen = set()
    for clip in doc["clips"]:
        source = sources.get(clip["source_family"])
        if source is None or clip["media_sha256"] != source["media_sha256"]:
            raise ValueError("clip source not admitted")
        if clip.get("eligibility") != "accepted_ssl_only" or not clip["scene_check"]["pass"]:
            raise ValueError("clip inspection/scene check missing")
        if len(clip["frames"]) != 16 or len(clip["pts"]) != 16 or clip["stride"] not in (2, 15):
            raise ValueError("clip sampling contract")
        num, den = clip["timebase"]
        if num <= 0 or den <= 0:
            raise ValueError("invalid timebase")
        times = np.asarray(clip["pts"], dtype=np.float64) * num / den
        if (not np.isfinite(times).all() or not (np.diff(times) > 0).all()
                or (np.abs(np.diff(times) - clip["stride"] / 120) > num / den + 1e-9).any()):
            raise ValueError("clip timestamp gap")
        identity = (source["media_sha256"], tuple(clip["pts"]))
        if identity in seen:
            raise ValueError("duplicate clip")
        seen.add(identity)
        counts[clip["source_family"]] += 1
        rates[clip["source_family"], clip["stride"]] += 1
        for frame in clip["frames"]:
            image = path.parent / frame["path"]
            if not image.resolve().is_relative_to(path.parent.resolve()) or image.is_symlink():
                raise ValueError("frame escapes packet")
            if T.sha256(image) != frame["sha256"]:
                raise ValueError("frame pin mismatch")
    if len(counts) < 4 or len(set(counts.values())) != 1:
        raise ValueError("four balanced source sessions required")
    if any(rates[s, 2] != rates[s, 15] for s in counts):
        raise ValueError("balanced short/long clips required per source")
    return doc


def extract(doc, root, assets, out, *, device, progress):
    from PIL import Image
    start = time.monotonic()
    backbone = FrozenDino(assets, config_sha256=CONFIG_SHA).to(device)
    n = len(doc["clips"])
    features = np.lib.format.open_memmap(out / "features.npy", mode="w+", dtype=np.float32,
                                         shape=(n, 16, 17, 384))
    times = np.empty((n, 16), np.float32)
    for i, clip in enumerate(doc["clips"]):
        num, den = clip["timebase"]
        times[i] = (np.asarray(clip["pts"], dtype=np.float64) - clip["pts"][0]) * num / den
        for start_frame in (0, 8):
            frames = []
            for frame in clip["frames"][start_frame:start_frame + 8]:
                with Image.open(root / frame["path"]) as image:
                    if image.mode != "RGB" or image.size != (256, 144):
                        raise ValueError("exact sampled RGB size/mode required")
                    frames.append(np.asarray(image))
            pixels = preprocess(torch.from_numpy(masked(np.stack(frames))), "global").to(device)
            with torch.no_grad():
                features[i, start_frame:start_frame + 8] = backbone(pixels).cpu().numpy().reshape(8, 17, 384)
        progress({"n": i + 1, "total": n})
    features.flush()
    np.save(out / "times.npy", times, allow_pickle=False)
    receipt = {"seconds": time.monotonic() - start, "frames": n * 16, "assets": backbone.asset_receipt,
               "mask_rectangles_256x144": MASK, "features_sha256": T.sha256(out / "features.npy"),
               "times_sha256": T.sha256(out / "times.npy")}
    del backbone
    torch.cuda.empty_cache()
    return features, times, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet", "packet-sha256", "admission", "admission-sha256", "assets", "out"):
        parser.add_argument("--" + name, required=True)
    a = parser.parse_args(argv)
    if not torch.cuda.is_available() or torch.cuda.get_device_name() != "NVIDIA L40S":
        raise ValueError("authorized L40S required")
    torch.set_num_threads(8)
    doc = packet(a.packet, a.packet_sha256, a.admission, a.admission_sha256)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    job = "idm-ssl-pilot"
    write(job, root=out / "jobs", owner="idm-owner", host="modal", stage="running", evidence=str(out / "report.json"))
    progress = lambda value: write(job, root=out / "jobs", progress=value)
    report = {"scope": "EXPLORATORY", "review": "provisional", "packet_sha256": a.packet_sha256,
              "admission_sha256": a.admission_sha256, "clips": len(doc["clips"]), "seeds": {},
              "limitations": "Small temporal-feature pilot only; no IDM/policy transfer result. "
                             "All SSL losses are in-training. Matched downstream F/U fits remain required."}
    try:
        features, times, report["extraction"] = extract(doc, Path(a.packet).parent, a.assets, out,
                                                        device="cuda", progress=progress)
        for seed in (0, 1, 2):
            start = time.monotonic()
            model, history = ssl.fit(features, times, seed=seed, device="cuda", progress=progress)
            checkpoint = out / f"temporal-seed{seed}.pt"
            torch.save({"encoder": model.encoder.state_dict(), "config": model.encoder.config.as_dict(),
                        "seed": seed, "packet_sha256": a.packet_sha256, "mask": MASK}, checkpoint)
            report["seeds"][str(seed)] = {"history": history, "seconds": time.monotonic() - start,
                                           "checkpoint_sha256": T.sha256(checkpoint)}
            (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            del model
            torch.cuda.empty_cache()
        write(job, stage="done", root=out / "jobs")
    except BaseException:
        write(job, stage="failed", root=out / "jobs")
        raise


if __name__ == "__main__":
    main()
