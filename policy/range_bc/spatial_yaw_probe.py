"""Six-app launcher shakedown, not a fit or an estimate of full-workload p95.

The shared guard calls run_probe(root, ...) inside its completed-stage contract.
Imports of torch and workload modules occur inside the call, not at worker import.
"""
import hashlib
import json
from pathlib import Path
import time


def verify_input_blocks(spec):
    # Fixed admitted TRAIN source only; no caller-selected source discovery.
    sid = "20260923T051828-422Z-33696-1"
    root = Path("/inputs/caches") / sid
    if spec["session"] != sid or spec["frame_ids"] != [7, 8]:
        raise ValueError("probe source differs")
    raw = (root / "cache.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["cache_manifest_sha256"]:
        raise ValueError("probe cache identity differs")
    expected = {(str(root / (v + ".u8")), i * size, size)
                for v, size in (("global", 144 * 256 * 3), ("crop", 128 * 128 * 3)) for i in (7, 8)}
    actual = {(p["path"], p["offset"], p["bytes"]) for p in spec["blocks"]}
    if actual != expected or len(spec["blocks"]) != 4:
        raise ValueError("probe block closure differs")
    for pin in spec["blocks"]:
        with Path(pin["path"]).open("rb") as stream:
            stream.seek(pin["offset"])
            value = stream.read(pin["bytes"])
        if len(value) != pin["bytes"] or hashlib.sha256(value).hexdigest() != pin["sha256"]:
            raise ValueError("probe block differs")


def exercise(device, *, batch=8, window=96, seconds=110, updates_min=4):
    """Real frozen-base operations and optimizers with labelled synthetic tokens."""
    import torch
    from . import steps, vocab
    from .explore_encoder import EncoderPolicy
    from .model import Config
    from .spatial_yaw import FrozenBaseYaw

    torch.set_num_threads(2)
    torch.manual_seed(0)
    base = EncoderPolicy(Config(history=False, hud=False)).to(device).eval()
    before = {k: v.cpu().clone() for k, v in base.state_dict().items()}
    models, optimizers = {}, {}
    for grid in (4, 8):
        torch.manual_seed(1)
        models[grid] = FrozenBaseYaw(base, grid).to(device).train()
        optimizers[grid] = torch.optim.AdamW(models[grid].yaw.parameters(), lr=.0003, weight_decay=.0001)
    g4 = torch.randn(batch, window, 16384, device=device, dtype=torch.float16)
    c4 = torch.randn_like(g4)
    g8 = torch.randn(batch, window, 65536, device=device, dtype=torch.float16)
    c8 = torch.randn_like(g8)
    prev = torch.zeros(batch, window, steps.PREV_DIM, device=device)
    target = torch.full((batch * window,), vocab.ZERO_CLASS, device=device, dtype=torch.long)
    with torch.no_grad():
        expected_a, expected_c, _ = base(g4, c4, None, prev)
    def sync():
        if device == "cuda":
            torch.cuda.synchronize()
    sync()
    started = time.time()
    monotonic = time.monotonic()
    durations = {4: [], 8: []}
    updates = 0
    while updates < updates_min or time.monotonic() - monotonic < seconds:
        for grid, (g, c) in ((4, (g4, c4)), (8, (g8, c8))):
            sync()
            at = time.perf_counter()
            opt, model = optimizers[grid], models[grid]
            opt.zero_grad(set_to_none=True)
            actions, camera, _ = model(g4, c4, g, c, prev)
            if not torch.equal(actions, expected_a) or not torch.equal(camera[:, :, 1], expected_c[:, :, 1]):
                raise ValueError("frozen action/pitch outputs changed")
            loss = torch.nn.functional.cross_entropy(camera[:, :, 0].reshape(-1, 31), target)
            if not torch.isfinite(loss):
                raise ValueError("probe nonfinite loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.yaw.parameters(), 1.)
            opt.step()
            sync()
            durations[grid].append(time.perf_counter() - at)
        updates += 1
        if seconds:
            time.sleep(.1)  # sustained overlap without pretending to saturate the GPU
    sync()
    finished = time.time()
    if any(p.grad is not None for p in base.parameters()):
        raise ValueError("base received gradients")
    if any(not torch.equal(v.cpu(), before[k]) for k, v in base.state_dict().items()):
        raise ValueError("base tensors changed")
    state = {str(g): {k: v.cpu() for k, v in m.yaw.state_dict().items()} for g, m in models.items()}
    return state, {"work_started_at": started, "work_finished_at": finished, "updates_per_grid": updates,
                   "batch": batch, "window": window, "synthetic_batch_seconds": durations,
                   "retention": "exact action/pitch outputs; base tensors unchanged; no base gradients"}


def run_probe(root, *, slot, input_spec, input_spec_sha256, seconds=110):
    entered = time.time()
    import torch
    from .spatial_yaw import SpatialYawReadout

    if slot not in range(1, 7) or seconds != 110:
        raise ValueError("unregistered probe slot/duration")
    if not torch.cuda.is_available() or torch.cuda.get_device_name() != "NVIDIA L40S":
        raise ValueError("L40S required")
    raw = Path(input_spec).read_bytes()
    if hashlib.sha256(raw).hexdigest() != input_spec_sha256:
        raise ValueError("probe input spec pin differs")
    verify_input_blocks(json.loads(raw))
    state, report = exercise("cuda", seconds=seconds)
    root = Path(root)
    checkpoint = root / "probe-yaw.pt"
    torch.save(state, checkpoint)
    loaded = torch.load(checkpoint, weights_only=True, map_location="cpu")
    for grid in (4, 8):
        model = SpatialYawReadout(grid)
        model.load_state_dict(loaded[str(grid)], strict=True)
        if any(not torch.equal(value, loaded[str(grid)][key]) for key, value in state[str(grid)].items()):
            raise ValueError("serialization round trip differs")
    import resource
    report.update({"tag": "EXPLORATORY_LAUNCHER_SHAKEDOWN", "slot": slot, "entered_at": entered,
                   "completed_at": time.time(), "torch": str(torch.__version__), "cuda": torch.version.cuda,
                   "device": torch.cuda.get_device_name(), "peak_allocated_gpu_bytes": torch.cuda.max_memory_allocated(),
                   "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "input_spec_sha256": input_spec_sha256, "input_blocks_verified": 4,
                   "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                   "limitation": "Random untrained base/synthetic spatial tokens; actual admitted pixel blocks read/hash-checked. "
                                 "No tower extraction, scientific evaluation or full-fit p95 claim."})
    with (root / "probe.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return 0
