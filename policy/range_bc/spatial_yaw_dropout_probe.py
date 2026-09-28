"""Three-app dropout launcher shakedown; synthetic tokens, no scientific fit."""
import json
from pathlib import Path
import time


def exercise(base, *, device, seed, seconds=60, batch=8, window=96):
    import torch
    from . import steps, vocab
    from .spatial_yaw_train import SpatialYawPolicy, tensor_digest

    torch.manual_seed(seed)
    before = tensor_digest(base)
    model = SpatialYawPolicy(base, 4, hidden_dropout=.5).to(device).train()
    g = torch.randn(batch, window, 32768, device=device, dtype=torch.float16)
    c = torch.randn_like(g)
    prev = torch.zeros(batch, window, steps.PREV_DIM, device=device)
    target = torch.full((batch*window,), vocab.ZERO_CLASS, device=device, dtype=torch.long)
    with torch.no_grad():
        expected = base(g[..., :16384].contiguous(), c[..., :16384].contiguous(), None, prev)
    opt = torch.optim.AdamW(model.yaw.parameters(), lr=.0003, weight_decay=.0001)
    started_wall, started = time.time(), time.monotonic()
    updates = 0
    while updates < 3 or time.monotonic()-started < seconds:
        opt.zero_grad()
        actions, camera, _ = model(g, c, None, prev)
        if not torch.equal(actions, expected[0]) or not torch.equal(camera[:, :, 1], expected[1][:, :, 1]):
            raise ValueError("action/pitch retention changed")
        loss = torch.nn.functional.cross_entropy(camera[:, :, 0].flatten(0, 1), target)
        if not torch.isfinite(loss):
            raise ValueError("nonfinite probe loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.yaw.parameters(), 1.)
        opt.step()
        updates += 1
        if seconds:
            time.sleep(.1)
    if tensor_digest(base) != before or any(p.grad is not None for p in base.parameters()):
        raise ValueError("base changed")
    model.eval()
    with torch.no_grad():
        a, camera, _ = model(g, c, None, prev)
        repeated = model(g, c, None, prev)[1]
    if not torch.equal(camera, repeated):
        raise ValueError("dropout active during evaluation")
    if not torch.equal(a, expected[0]) or not torch.equal(camera[:, :, 1], expected[1][:, :, 1]):
        raise ValueError("evaluation retention changed")
    return {k: v.cpu() for k, v in model.yaw.state_dict().items()}, {
        "work_started_at": started_wall, "work_finished_at": time.time(), "updates": updates,
        "batch": batch, "window": window, "seed": seed, "hidden_dropout": .5,
        "base_tensor_sha256": before, "retention": "exact actions/pitch; base unchanged and gradient-free",
        "evaluation_dropout_disabled": True,
        "limitation": "Synthetic repeated tokens and a fixed base; launcher evidence only, no full-fit p95 or I/O throughput claim"}


def run_probe(root, *, spec_path, spec_sha256):
    import torch
    from .spatial_yaw import SpatialYawReadout
    from .spatial_yaw_cache import sha, write_new
    from .spatial_yaw_train import checked_spec, load_base, runtime

    spec = checked_spec(spec_path, spec_sha256)
    if spec["grid"] != 4 or spec.get("hidden_dropout") != .5:
        raise ValueError("only the approved dropout probe")
    device = runtime()
    # Check the existing cache identity without scanning the full dataset in a short probe.
    if sha(Path(spec["dataset_root"]) / "dataset.json") != spec["dataset_sha256"]:
        raise ValueError("dataset manifest differs")
    base, _ = load_base(spec["base_checkpoint"], spec["base_sha256"], spec["seed"])
    state, report = exercise(base, device=device, seed=spec["seed"])
    root = Path(root)
    path = root / "probe-yaw.pt"
    torch.save(state, path)
    loaded = torch.load(path, weights_only=True, map_location="cpu")
    check = SpatialYawReadout(4, hidden_dropout=.5)
    check.load_state_dict(loaded, strict=True)
    if any(not torch.equal(v, loaded[k]) for k, v in state.items()):
        raise ValueError("checkpoint round trip differs")
    report.update(tag="EXPLORATORY_LAUNCHER_SHAKEDOWN", spec_sha256=spec_sha256,
                  torch=str(torch.__version__), cuda=torch.version.cuda,
                  checkpoint_sha256=sha(path), device=torch.cuda.get_device_name(),
                  dataset_manifest_sha256=spec["dataset_sha256"])
    write_new(root / "probe.json", report)
    return 0
