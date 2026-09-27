"""EXPLORATORY frozen SigLIP/NitroGen vision into the matched H1 heads.

No NitroGen code is imported. Its pinned checkpoint is read with weights_only=True;
only vision_encoder tensors are retained. Feature caches remove pixel augmentation
in BOTH arms. History dropout, windows, schedule, losses and decode stay unchanged.
"""

import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

from . import steps, train
from .explore_chunks import ChunkBatches, ChunkPolicy
from .explore_chunks_train import fit_chunks, load_manifest
from .explore_chunks_eval import evaluate
from .model import Config

STOCK = "google/siglip2-large-patch16-256"
STOCK_REV = "787800c8990e6f058423089178e718139608408c"
STOCK_SHA = "fa34f822f016dbb167d8d0e3a8af99b5e199aa28573360d4295252b9ec418e2a"
NITROGEN_REV = "584c8dded734d032f07a4bcc0ccb330e703298c4"
NITROGEN_SHA = "a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81"
WIDTH = 16 * 1024
GRAPH = {"views": ["global", "crop"], "resize": "bilinear antialias 256x256 squash",
         "normalization": "RGB / 127.5 - 1", "tokens": "last_hidden_state",
         "pool": "row-major 4x4 means of 4x4 patches", "precision": "bf16 encoder, float16 cache",
         "pixel_augmentation": False, "frozen": True}


def download_tower(arm, directory):
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open
    from safetensors.torch import save_file
    from transformers import SiglipVisionConfig, SiglipVisionModel
    directory = Path(directory)
    directory.mkdir(exist_ok=True, parents=True)
    config_file = hf_hub_download(STOCK, "config.json", revision=STOCK_REV)
    config = json.loads(Path(config_file).read_text())["vision_config"]
    train.require(config["hidden_size"] == 1024 and config["num_hidden_layers"] == 24
                  and config["image_size"] == 256, "unexpected stock architecture")
    model = SiglipVisionModel(SiglipVisionConfig(**config))
    if arm == "siglip":
        path = hf_hub_download(STOCK, "model.safetensors", revision=STOCK_REV)
        train.require(steps.sha256(path) == STOCK_SHA, "stock weight hash differs")
        with safe_open(path, framework="pt", device="cpu") as stream:
            weights = {k: stream.get_tensor(k) for k in stream.keys() if k.startswith("vision_model.")}
        receipt = {"model": STOCK, "revision": STOCK_REV, "source_sha256": STOCK_SHA}
    else:
        train.require(arm == "nitrogen", "unknown encoder arm")
        path = hf_hub_download("nvidia/NitroGen", "ng.pt", revision=NITROGEN_REV)
        train.require(steps.sha256(path) == NITROGEN_SHA, "NitroGen weight hash differs")
        # Never fall back to arbitrary pickle loading or import the official harness.
        payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        cfg = payload["ckpt_config"]["model_cfg"]
        train.require(cfg["vision_encoder_name"] == STOCK and cfg["vision_hidden_size"] == 1024,
                      "NitroGen and stock architecture mismatch")
        weights = {"vision_model." + k.removeprefix("vision_encoder."): v
                   for k, v in payload["model"].items() if k.startswith("vision_encoder.")}
        receipt = {"model": "nvidia/NitroGen vision only", "revision": NITROGEN_REV,
                   "source_sha256": NITROGEN_SHA, "checkpoint_model_config": cfg,
                   "license": "NVIDIA non-commercial research; derived weights retain restriction"}
    model.load_state_dict(weights, strict=True)
    save_file({k: v.contiguous() for k, v in weights.items()}, str(directory / "vision.safetensors"))
    receipt.update({"vision_sha256": steps.sha256(directory / "vision.safetensors"),
                    "config_sha256": steps.sha256(config_file), "graph": GRAPH})
    (directory / "assets.json").write_text(json.dumps(receipt, indent=2) + "\n")
    model.requires_grad_(False).eval()
    return model, receipt


def pool_tokens(tokens):
    train.require(tokens.ndim == 3 and tokens.shape[1:] == (256, 1024), "wrong vision tokens")
    return tokens.float().reshape(-1, 4, 4, 4, 4, 1024).mean((2, 4)).flatten(1)


@torch.no_grad()
def extract(arrays, tower, root, report, *, device="cuda", batch=32):
    """Only frame indices of already-authorized eligible runs; no future inputs."""
    root = Path(root)
    tower.to(device=device, dtype=torch.bfloat16).eval()
    result = {}
    for arr in arrays:
        dest = root / arr.session.session_id
        dest.mkdir(parents=True, exist_ok=False)
        ids = sorted({int(i) for a, b in arr.runs for i in arr.row_frame[a:b]})
        train.require(ids and min(ids) >= 0, "eligible row missing frame")
        n = len(arr.global_frames)
        paths = [dest / (view + ".npy") for view in ("global", "crop")]
        outputs = [np.lib.format.open_memmap(p, mode="w+", dtype=np.float16, shape=(n, WIDTH)) for p in paths]
        started = reported = time.monotonic()
        for start in range(0, len(ids), batch):
            selected = ids[start:start + batch]
            for source, output in zip((arr.global_frames, arr.crop_frames), outputs):
                x = torch.from_numpy(np.array(source[selected], copy=True)).permute(0, 3, 1, 2).to(device).float()
                x = F.interpolate(x, (256, 256), mode="bilinear", align_corners=False, antialias=True)
                x = (x / 127.5 - 1).to(torch.bfloat16)
                values = pool_tokens(tower(pixel_values=x).last_hidden_state)
                train.require(bool(torch.isfinite(values).all()), "nonfinite vision features")
                output[selected] = values.cpu().numpy().astype(np.float16)
            if time.monotonic() - reported > 30:
                report(f"features {arr.session.session_id}: {min(start + batch, len(ids))}/{len(ids)}")
                reported = time.monotonic()
        for output in outputs:
            output.flush()
        receipt = {"session": arr.session.session_id, "steps_sha256": arr.session.sha256,
                   "source_manifest": arr.manifest, "row_frame_sha256": __import__('hashlib').sha256(
                       arr.row_frame.numpy().tobytes()).hexdigest(), "selected_frames": ids,
                   "shape": [n, WIDTH], "seconds": time.monotonic() - started,
                   "files": {p.name: steps.sha256(p) for p in paths}, "graph": GRAPH}
        (dest / "features.json").write_text(json.dumps(receipt, indent=2) + "\n")
        result[arr.session.session_id] = {"seconds": receipt["seconds"], "frames": len(ids),
                                         "manifest_sha256": steps.sha256(dest / "features.json")}
        report(f"features complete {arr.session.session_id}: {len(ids)} frames")
    (root / "features.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


class FeatureArrays:
    """Reuse exact labels, masks, row/frame mapping and eligible runs."""

    def __init__(self, arr, root):
        self.__dict__.update(arr.__dict__)
        root = Path(root) / arr.session.session_id
        receipt = json.loads((root / "features.json").read_text())
        train.require(receipt["steps_sha256"] == arr.session.sha256 and receipt["graph"] == GRAPH,
                      "feature source/graph mismatch")
        self.feature_arrays = [np.load(root / (v + ".npy"), mmap_mode="r") for v in ("global", "crop")]
        selected = set(receipt["selected_frames"])
        train.require(all(int(i) in selected for a, b in arr.runs for i in arr.row_frame[a:b]),
                      "eligible frame absent from feature cache")
        train.require(all(a.shape == tuple(receipt["shape"]) and a.dtype == np.float16
                          for a in self.feature_arrays), "invalid feature dimensions")
        self.manifest = {"source": arr.manifest, "features_sha256": steps.sha256(root / "features.json")}

    def frames(self, rows):
        ids = self.row_frame[rows].numpy()
        return (*[torch.from_numpy(np.array(a[ids], copy=True)) for a in self.feature_arrays],
                torch.zeros(len(rows), 1))


class FeatureBatches(ChunkBatches):
    def __init__(self, arrays, **kwargs):
        super().__init__(arrays, frames=False, horizon=1, **kwargs)

    def batch(self, ids, generator=None, **kwargs):
        out = super().batch(ids, generator, **kwargs)
        # The base consumes the identical augmentation RNG draws before history
        # dropout, but does not touch pixels. Replace its blank image placeholders.
        g = torch.zeros(len(ids), self.window, WIDTH, dtype=torch.float16)
        c = torch.zeros_like(g)
        for i, w in enumerate(ids):
            si, start, n, _ = self.windows[w]
            gf, cf, _ = self.arrays[si].frames(torch.arange(start, start + n))
            g[i, :n], c[i, :n] = gf, cf
        out["global"], out["crop"], out["hud"] = g, c, torch.zeros(len(ids), self.window, 1)
        return out


class EncoderPolicy(ChunkPolicy):
    def __init__(self, config=Config(hud=False), horizon=1):
        train.require(horizon == 1 and config.frames and not config.hud, "encoder explore is no-HUD H1")
        super().__init__(config, horizon)
        # Constructing the original first preserves initial shared recurrent/head
        # weights exactly. Both encoder arms get identical fresh projection weights.
        self.global_enc = nn.Sequential(nn.Linear(WIDTH, config.embed), nn.ReLU())
        self.crop_enc = nn.Sequential(nn.Linear(WIDTH, config.embed), nn.ReLU())

    def features(self, global_frames, crop_frames, hud_frames, b, t, like):
        return torch.cat((self.global_enc(global_frames.float()), self.crop_enc(crop_frames.float())), -1)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("arm", "manifest", "registry", "tally", "out", "stop-file", "log"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--history", choices=("enabled", "disabled"), default="enabled")
    p.add_argument("--stop-on-persistence", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--job-name")
    p.add_argument("--confirm-prereg-sha256")
    a = p.parse_args(argv)
    if a.confirm_prereg_sha256:
        train.require(a.arm == "nitrogen" and a.seed in (1, 2, 3)
                      and len(a.confirm_prereg_sha256) == 64
                      and all(c in "0123456789abcdef" for c in a.confirm_prereg_sha256),
                      "invalid confirmation identity")
    train.require(torch.cuda.is_available() and torch.cuda.get_device_name() == "NVIDIA L40S",
                  "matched Modal L40S required")
    torch.set_num_threads(8)
    root = Path(a.out)
    from scripts.job_status import write
    job = a.job_name or "explore-encoder-" + ("historyoff-" if a.history == "disabled" else "") + a.arm
    tag = "CONFIRM" if a.confirm_prereg_sha256 else "EXPLORATORY"
    def report(message):
        write(job, root=root / "jobs", owner="explore-policy", host="modal", stage="running",
              evidence=a.log, progress=message)
        print(message, flush=True)
    report("Loading authorized full-cohort H1 inputs")
    arrays, dev = load_manifest(a.manifest, a.registry, a.tally, cohort="full")
    environment = {"tag": tag, "torch": str(torch.__version__), "cuda": torch.version.cuda,
                   "device": torch.cuda.get_device_name(), "arm": a.arm, "seed": a.seed,
                   "prereg_sha256": a.confirm_prereg_sha256}
    (root / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    report("Downloading pinned vision weights")
    tower, assets = download_tower(a.arm, root / "assets")
    # Large reproducible feature arrays are scratch, not a repeatedly committed
    # volume payload. Keep their hashes and source receipts in the run report.
    feature_root = Path("/tmp/encoder-features")
    extraction = extract(arrays + dev, tower, feature_root, report)
    (root / "features-summary.json").write_text(json.dumps(extraction, indent=2) + "\n")
    import shutil
    for arr in arrays + dev:
        shutil.copyfile(feature_root / arr.session.session_id / "features.json",
                        root / (arr.session.session_id + "-features.json"))
    del tower
    torch.cuda.empty_cache()
    train_arrays = [FeatureArrays(x, feature_root) for x in arrays]
    dev_arrays = [FeatureArrays(x, feature_root) for x in dev]
    stats = steps.train_statistics([x.session for x in arrays])
    identity = steps.sha256(a.manifest) + steps.sha256(feature_root / "features.json")
    extra = {"arm": a.arm, "assets": assets, "extraction": extraction, "history_input": a.history,
             "incumbent_difference": "frozen pretrained tower and cached features; no pixel jitter/DrQ"}
    if a.confirm_prereg_sha256:
        extra["prereg_sha256"] = a.confirm_prereg_sha256
    config = Config(hud=False, history=a.history == "enabled")
    _, _, status = fit_chunks(FeatureBatches(train_arrays, stride=64), config, stats, root,
                              dev=FeatureBatches(dev_arrays, stride=64), seed=a.seed, epochs=26, device="cuda",
                              stop_file=a.stop_file, run_identity=identity, model_factory=EncoderPolicy,
                              recipe_extra=extra, experiment_tag=tag,
                              progress=lambda n, total: report(f"fit {n}/{total}"))
    if status != "complete":
        return 75
    args = copy.copy(a)
    args.checkpoint, args.out = str(root / "epoch-26.pt"), str(root / "evaluation.json")
    result = evaluate(args, report, device="cuda", model_factory=EncoderPolicy,
                      array_loader=lambda *args, **kw: (train_arrays, dev_arrays),
                      stop_on_persistence=a.stop_on_persistence,
                      chance_floor=bool(a.confirm_prereg_sha256))
    message = result.get("stop_reason", "26 epochs and six decodes complete")
    write(job, root=root / "jobs", stage="done", progress=message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
