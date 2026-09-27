"""Synthetic training-step bench: determinism (checkpoint sha256 after N steps) and throughput per step.

No session data. Frames, previous actions and targets are drawn once from a seeded CPU generator into a small pool
that the timed steps cycle through, so generation is outside the timing; the host-to-device copy of each batch is
inside it, as it is in a real fit. The real loader's memmap gather is NOT measured here.

    python -m policy.range_bc.bench --device mps --batch 8 --steps 20 --out bench-b8.json

Run the same command twice in separate processes and compare `checkpoint_sha256` for determinism.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import platform
import time

import torch

from . import steps, vocab
from .model import Config, Policy, parameter_count
from .train import checkpoint_bytes, loss_terms, schedule, total_loss


def synthetic_pool(batch, window, config, pool, seed):
    gen = torch.Generator().manual_seed(seed)
    out = []
    for _ in range(pool):
        frames = {k: torch.randint(0, 256, (batch, window, 3, *hw), generator=gen, dtype=torch.uint8)
                  for k, hw in (("global", config.global_hw), ("crop", config.crop_hw), ("hud", config.hud_hw))}
        out.append({
            **frames,
            "prev": (torch.rand(batch, window, steps.PREV_DIM, generator=gen) < .1).float(),
            "act": (torch.rand(batch, window, 3, vocab.N, generator=gen) < .05).float(),
            "act_mask": torch.ones(batch, window, 3, vocab.N, dtype=torch.bool),
            "camera": torch.randint(0, vocab.CAMERA_CLASSES, (batch, window, 2), generator=gen),
            "camera_mask": torch.ones(batch, window, 2, dtype=torch.bool),
            "regime": torch.zeros(batch, window)})
    return out


def sync(device):
    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()


def run(*, device="cpu", batch=8, window=steps.WINDOW, n_steps=20, warmup=3, seed=0, deterministic=True,
        frames=True, pool=2, config=None):
    config = replace(config or Config(), frames=frames)
    torch.manual_seed(seed)
    det_error = None
    try:
        torch.use_deterministic_algorithms(deterministic)
    except Exception as exc:                                  # pragma: no cover - platform dependent
        det_error = repr(exc)
    data = synthetic_pool(batch, window, config, pool, seed)
    model = Policy(config).to(device)
    pw = torch.full((2, vocab.N), 5., device=device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, schedule(n_steps, warmup=min(500, n_steps)))
    times, losses, error = [], [], None
    try:
        for step in range(n_steps):
            sync(device)
            t0 = time.perf_counter()
            b = {k: v.to(device) for k, v in data[step % pool].items()}
            acts, cams, _ = model(b["global"], b["crop"], b["hud"], b["prev"], regime=b["regime"])
            loss = total_loss(loss_terms(acts, cams, b, pw))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            opt.step()
            sched.step()
            losses.append(float(loss.detach()))
            sync(device)
            times.append(time.perf_counter() - t0)
    except Exception as exc:
        error = repr(exc)[:2000]
    out = {"device": device, "torch": torch.__version__, "platform": platform.platform(), "batch": batch,
           "window": window, "frames_per_step": batch * window, "steps": len(times), "requested_steps": n_steps,
           "seed": seed, "deterministic": deterministic, "deterministic_error": det_error, "frames": frames,
           "parameters": parameter_count(model), "config": config.as_dict(), "error": error, "losses": losses}
    if times:
        timed = times[warmup:] or times
        mean = sum(timed) / len(timed)
        out.update(step_seconds=times, mean_step_seconds=mean, frames_per_second=batch * window / mean)
    if device == "mps":
        out.update(mps_current_allocated=torch.mps.current_allocated_memory(),
                   mps_driver_allocated=torch.mps.driver_allocated_memory())
    if error is None:
        data_bytes = checkpoint_bytes(model, {"bench": True, "seed": seed})
        out.update(checkpoint_sha256=hashlib.sha256(data_bytes).hexdigest(), checkpoint_bytes=len(data_bytes),
                   weights_sha256=hashlib.sha256(b"".join(v.detach().cpu().contiguous().numpy().tobytes()
                                                         for v in model.state_dict().values())).hexdigest())
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--device", default="cpu")
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--window", type=int, default=steps.WINDOW)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--nondeterministic", action="store_true")
    p.add_argument("--history-only", action="store_true")
    p.add_argument("--out")
    a = p.parse_args(argv)
    r = run(device=a.device, batch=a.batch, window=a.window, n_steps=a.steps, warmup=a.warmup, seed=a.seed,
            deterministic=not a.nondeterministic, frames=not a.history_only)
    text = json.dumps(r, sort_keys=True)
    if a.out:
        with open(a.out, "x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    summary = {k: r.get(k) for k in ("device", "batch", "frames", "deterministic", "steps", "mean_step_seconds",
                                     "frames_per_second", "checkpoint_sha256", "error", "deterministic_error")}
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
