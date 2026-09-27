"""EXPLORATORY Mac-only, resumable chunk sweep entry point (never a real fit).

One invocation trains one H/seed. The explicit manifest names the eight admitted
TRAIN sessions and the two frozen dev sessions, plus each existing cache path.
No directory glob is used to discover data. Metrics use the unchanged trainer.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import time

import torch

from . import cache, steps, train, vocab
from .explore_chunks import ChunkBatches, ChunkPolicy, chunk_loss_terms
from .model import Config

TRAIN_IDS = frozenset((
    "20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6",
    "20260924T232304-170Z-12024-1", "20260925T021320-371Z-7804-1",
    "20260925T025230-605Z-7804-2", "20260925T203745-207Z-49728-2",
    "20260926T035932-508Z-63684-14", "20260926T045729-166Z-79780-1",
))
DEV_IDS = frozenset(("20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3"))
INTERIM_IDS = TRAIN_IDS - {"20260925T203745-207Z-49728-2", "20260926T035932-508Z-63684-14",
                           "20260926T045729-166Z-79780-1"}
FORMAT = "EXPLORATORY-range-chunks-v1"
EPOCH_REASON = ("26 matched epochs for H=1/4/8: twice the inherited 13-epoch cap, because the prior curves "
                "often reached that cap while falling. Retain per-head dev curves and epoch 13; its LR is from "
                "a 26-epoch cosine schedule, so it is not a replication of the legacy 13-epoch fit. "
                "Use final epoch, not a dev-selected checkpoint; convergence is measured, not assumed.")


def load_manifest(path, registry_path, tally_path, *, cohort="full"):
    """Reject forbidden roles by the reviewed roster before opening step payloads."""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    placement = {r["session_id"]: r for r in registry["sessions"]}
    tally = json.loads(Path(tally_path).read_text(encoding="utf-8"))
    admitted = {r["session"] for r in tally["rows"] if r.get("split") == "train"
                and r.get("status") == "admitted" and (r.get("trainable_min") or 0) > 0}
    train.require(admitted == TRAIN_IDS | DEV_IDS, "admitted roster changed; review before opening payloads")
    train.require(cohort in ("full", "interim"), "unknown cohort")
    train_ids = TRAIN_IDS if cohort == "full" else INTERIM_IDS
    all_items = []
    for role, expected in (("train", train_ids), ("dev", DEV_IDS)):
        items = manifest[role]
        names = [Path(item["steps"]).stem for item in items]
        train.require(len(names) == len(expected) and set(names) == expected,
                      f"{role} must contain exactly the authorized full-cohort roster")
        for name in names:
            train.require(placement.get(name, {}).get("split") == "train",
                          f"{name}: not TRAIN in corpus registry (dev is a frozen TRAIN holdout)")
        all_items.extend(items)
    denylist, equivalence = steps.load_denylist(), steps.load_patch_equivalence()
    # Headers are checked before any body, including cross-checks with registry.
    for item in all_items:
        p = Path(item["steps"])
        with p.open(encoding="utf-8") as stream:
            header = json.loads(stream.readline())
        train.require(header["session_id"] == p.stem and header["split"] == "train",
                      "step header differs from allowed TRAIN placement")
        steps.check_sealed(header["session_id"], header["media_sha256"], denylist)
        train.require(header["media_sha256"] == placement[p.stem]["expected_media_sha256"],
                      "step media identity differs from registry")
    sessions = steps.load_cohort([i["steps"] for i in all_items], splits=("train",),
                                denylist=denylist, equivalence=equivalence)
    arrays = {s.session_id: train.SessionArrays(s, cache.open_cache(i["cache"], s), lag=0,
                                               regimes=("normal",))
              for s, i in zip(sessions, all_items)}
    return ([arrays[Path(i["steps"]).stem] for i in manifest["train"]],
            [arrays[Path(i["steps"]).stem] for i in manifest["dev"]])


def save_state(path, payload):
    temporary = path.with_suffix(".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def batch_identity(batches):
    """Bind resume to the actual target tensors and full ordered window schedule."""
    digest = hashlib.sha256()
    digest.update(json.dumps({"window": batches.window, "burn_in": batches.burn_in,
                              "frames": batches.load_frames, "windows": batches.windows},
                             sort_keys=True).encode())
    for arr in batches.arrays:
        digest.update(json.dumps({"runs": arr.runs, "manifest": getattr(arr, "manifest", None),
                                  "source_sha256": getattr(arr.session, "sha256", None)},
                                 sort_keys=True).encode())
        for name in ("act", "act_known", "camera", "camera_known", "valid", "prev", "regime", "row_frame"):
            value = getattr(arr, name, None)
            if value is not None:
                value = value.detach().cpu().contiguous()
                digest.update(f"{name}:{value.dtype}:{list(value.shape)}".encode())
                digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def fit_chunks(batches, config, stats, out, *, dev=None, seed=0, epochs=26, batch_size=8,
               lr=3e-4, weight_decay=1e-4, warmup=500, device="mps", resume=False,
               stop_file=None, run_identity="", stop_after_steps=None, cohort="full", progress=None):
    """Checkpoint at each epoch, and at next update when STOP is requested.

    A resumed arm restores optimizer, scheduler, CPU augmentation RNG and epoch
    cursor. stop_after_steps exists for the synthetic interruption check only.
    """
    train.require(all(a.session.split == "train" for a in batches.arrays), "train split required")
    train.require(batches.windows and epochs > 0, "nonempty windows and positive epochs required")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "latest.pt"
    train.require(resume == checkpoint.exists(), "use --resume for an existing arm; fresh output otherwise")
    train.seed_everything(seed)
    model = ChunkPolicy(config, batches.horizon).to(device)
    pw = train.pos_weights(stats).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    total = epochs * math.ceil(len(batches.windows) / batch_size)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, train.schedule(total, min(warmup, total)))
    generator = torch.Generator().manual_seed(seed)
    recipe = {"tag": "EXPLORATORY", "horizon": batches.horizon, "seed": seed, "epochs": epochs,
              "batch": batch_size, "lr": lr, "weight_decay": weight_decay, "warmup": warmup,
              "device": device, "config": config.as_dict(), "prev_dropout": .2, "lag": 0, "cohort": cohort,
              "run_identity": run_identity, "batch_identity": batch_identity(batches),
              "windows": len(batches.windows), "total_steps": total,
              "pos_weight": pw.detach().cpu().tolist()}
    epoch = cursor = updates = count = 0
    loss_sum = elapsed = 0.
    history = []
    if resume:
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        train.require(saved["format"] == FORMAT and saved["recipe"] == recipe, "resume recipe differs")
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        scheduler.load_state_dict(saved["scheduler"])
        generator.set_state(saved["generator"])
        torch.set_rng_state(saved["torch_rng"])
        epoch, cursor, updates = saved["epoch"], saved["cursor"], saved["updates"]
        count, loss_sum = saved["count"], saved["loss_sum"]
        history, elapsed = saved["history"], saved["seconds"]
    started = time.perf_counter()
    reported = started
    if progress:
        progress(updates, total)

    def snapshot(status):
        if device == "mps":
            torch.mps.synchronize()
        payload = {"format": FORMAT, "tag": "EXPLORATORY", "recipe": recipe, "epoch_reason": EPOCH_REASON,
                   "model": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                   "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                   "generator": generator.get_state(), "torch_rng": torch.get_rng_state(),
                   "epoch": epoch, "cursor": cursor, "updates": updates, "count": count, "loss_sum": loss_sum,
                   "history": history, "seconds": elapsed + time.perf_counter() - started, "status": status}
        save_state(checkpoint, payload)
        status_doc = {k: payload[k] for k in ("tag", "recipe", "epoch_reason", "epoch", "cursor", "updates",
                                             "history", "seconds", "status")}
        (out / "status.json").write_text(json.dumps(status_doc, indent=2) + "\n", encoding="utf-8")
        return payload

    while epoch < epochs:
        order = list(range(len(batches.windows)))
        random.Random(seed * 1000003 + epoch).shuffle(order)
        model.train()
        while cursor < len(order):
            if ((stop_file and Path(stop_file).exists())
                    or (stop_after_steps is not None and updates >= stop_after_steps)):
                snapshot("yielded")
                return model, history, "yielded"
            ids = order[cursor:cursor + batch_size]
            b = train.to_device(batches.batch(ids, generator, prev_dropout=.2), device)
            outputs = model.forward_chunks(b["global"], b["crop"], b["hud"], b["prev"], regime=b["regime"])
            loss = train.total_loss(chunk_loss_terms(*outputs[:2], b, pw))
            train.require(bool(torch.isfinite(loss)), "nonfinite chunk loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            scheduler.step()
            loss_sum += float(loss.detach())
            count += 1
            updates += 1
            cursor += len(ids)
            if progress and time.perf_counter() - reported >= 30:
                progress(updates, total)
                reported = time.perf_counter()
        entry = {"epoch": epoch + 1, "steps": updates, "train_chunk_loss": loss_sum / count,
                 "seconds": elapsed + time.perf_counter() - started}
        if dev is not None:
            # First-step per-head curve is directly comparable across horizons.
            entry["dev_step_one"] = train.dev_loss(model, dev, pw, device=device, batch_size=batch_size)
        history.append(entry)
        epoch += 1
        cursor = count = 0
        loss_sum = 0.
        payload = snapshot("complete" if epoch == epochs else "running")
        if epoch in (13, epochs):
            save_state(out / f"epoch-{epoch}.pt", payload)
        print(json.dumps({"tag": "EXPLORATORY", "horizon": batches.horizon, "seed": seed, **entry}), flush=True)
        if progress:
            progress(updates, total)
    return model, history, "complete"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--tally", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--horizon", type=int, choices=(1, 4, 8), required=True)
    p.add_argument("--cohort", choices=("full", "interim"), default="full")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--stop-file", required=True)
    p.add_argument("--job-name", required=True)
    p.add_argument("--log", required=True, help="Absolute path used by the launcher's log redirection")
    a = p.parse_args(argv)
    train.require(platform.system() == "Darwin" and platform.machine() == "arm64", "Mac only")
    root = Path("/Users/james/dev/range-bc-data/explore").resolve()
    train.require(Path(a.out).resolve().is_relative_to(root), "outputs must stay under explore/")
    train.require(torch.backends.mps.is_available(), "MPS required; no silent CPU fallback")
    train.require(Path(a.log).is_absolute(), "dashboard evidence log must be absolute")
    from scripts.job_status import write
    write(a.job_name, owner="explore-policy", stage="running", host="mac", evidence=a.log,
          started=int(time.time()), progress="EXPLORATORY: loading authorized cohort", eta=None)
    try:
        train_arrays, dev_arrays = load_manifest(a.manifest, a.registry, a.tally, cohort=a.cohort)
        batches = ChunkBatches(train_arrays, horizon=a.horizon, stride=64)
        dev = train.Batches(dev_arrays, stride=64)
        stats = steps.train_statistics([arr.session for arr in train_arrays])
        identity = hashlib.sha256(Path(a.manifest).read_bytes() + Path(a.registry).read_bytes()
                                  + Path(a.tally).read_bytes()).hexdigest()
        def report(n, total):
            write(a.job_name, progress={"n": n, "total": total})
        _, _, status = fit_chunks(batches, Config(hud=False), stats, a.out, dev=dev, seed=a.seed,
                                  resume=a.resume, stop_file=a.stop_file, run_identity=identity,
                                  cohort=a.cohort, progress=report)
        write(a.job_name, stage="queued" if status == "yielded" else "done",
              progress="Yielded with resume checkpoint" if status == "yielded" else "26 epochs complete")
    except BaseException as exc:
        write(a.job_name, stage="failed", progress=f"{type(exc).__name__}: {exc}"[:4096])
        raise
    return 75 if status == "yielded" else 0


if __name__ == "__main__":
    raise SystemExit(main())
