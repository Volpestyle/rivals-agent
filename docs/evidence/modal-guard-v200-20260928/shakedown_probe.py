"""Synthetic diagnostic only. Copied as cloud.v2_probe in the immutable source mount."""
import hashlib
import json
import time
from pathlib import Path


def run(root, *, seconds, commit):
    import torch
    root = Path(root)
    torch.manual_seed(17)
    torch.cuda.manual_seed_all(17)
    model = torch.nn.Sequential(torch.nn.Linear(4, 4), torch.nn.Dropout(.5)).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    inputs = torch.arange(32, dtype=torch.float32, device="cuda").reshape(8, 4) / 32
    for _ in range(3):
        optimizer.zero_grad()
        model(inputs).square().mean().backward()
        optimizer.step()
    checkpoint = {"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                  "rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all(), "epoch": 1}
    path = root / "epoch-1.pt"
    torch.save(checkpoint, path)
    commit()  # payload before receipt
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = {"epoch": 1, "sha256": digest, "bytes": path.stat().st_size,
               "artifact": path.name, "scientific_identity": "synthetic-v2-shakedown"}
    (root / "epoch-1.complete.json").write_text(json.dumps(receipt))
    commit()
    # Strict restore includes CUDA RNG; compare the next stochastic result.
    expected = model(inputs).detach().clone()
    loaded = torch.load(path, map_location="cuda", weights_only=False)
    model.load_state_dict(loaded["model"])
    optimizer.load_state_dict(loaded["optimizer"])
    torch.set_rng_state(loaded["rng"].cpu())
    torch.cuda.set_rng_state_all([x.cpu() for x in loaded["cuda_rng"]])
    actual = model(inputs).detach()
    assert torch.equal(expected, actual)
    (root / "checkpoint-verified.json").write_text(json.dumps({"cuda_rng_restore_exact": True, "epoch": 1}))
    commit()
    started = time.time()
    time.sleep(seconds)
    (root / "probe.json").write_text(json.dumps({"started": started, "ended": time.time(),
                                                "cuda_rng_restore_exact": True}))
    return 0
