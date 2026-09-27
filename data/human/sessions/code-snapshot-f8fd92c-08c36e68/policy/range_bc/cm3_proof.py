"""Staged round-3 proofs; synthetic tests may exercise primitives without real data.

These functions do not discover datasets or launch queues. The lead supplies approved
train-only arrays, frozen receipts and a device after independent implementation review.
"""
import copy
import hashlib
import os
import platform
import random
import time

import torch
import torch.nn.functional as F

from . import cm3, cm3_features, cm3_train, executor, fixture, metrics, steps, train, vocab

TRAIN_SESSIONS = (
    "20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6", "20260924T232304-170Z-12024-1",
    "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2")
TRAIN_TABLE_HASHES = (
    "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
    "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
    "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
    "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
    "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def configure_backend(device):
    require(device in ("cpu", "mps", "cuda"), "no automatic device fallback")
    require(os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") == "0", "MPS fallback must be disabled at startup")
    require(os.environ.get("PYTORCH_MPS_FAST_MATH", "0") == "0", "MPS fast math must be disabled at startup")
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    detail = {"device": device, "machine": platform.machine(), "os": platform.platform(),
              "float32_matmul_precision": torch.get_float32_matmul_precision(), "deterministic": True,
              "mps_fallback": False, "mps_fast_math": False}
    if device == "mps":
        require(torch.backends.mps.is_available(), "MPS unavailable")
        detail["hardware"] = "lead must bind exact Mac model in device-choice receipt"
    if device == "cuda":
        require(platform.system() != "Windows", "PC CUDA is not authorized")
        require(torch.cuda.is_available(), "CUDA unavailable")
        require(os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":4096:8", "pin CUBLAS_WORKSPACE_CONFIG before startup")
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        detail.update(hardware=torch.cuda.get_device_name(), cuda=torch.version.cuda,
                      cudnn=torch.backends.cudnn.version(), tf32=False, flash=False)
    return detail


def sample_frames(arrays):
    """Lead-filled field: 128 unique cached frames, in preregistered session order.

    One random.Random(20260928) stream samples each session in that order. Candidates
    are unique frame IDs from eligible normal runs. Allocation is 26/26/26/25/25.
    """
    require(tuple(a.session.session_id for a in arrays) == TRAIN_SESSIONS, "wrong training cohort/order")
    rng = random.Random(20260928)
    selections = []
    for i, arr in enumerate(arrays):
        require(arr.session.split == "train" and arr.session.sha256 == TRAIN_TABLE_HASHES[i], "wrong train role/table")
        require(arr.lag == 0 and arr.regimes == ("normal",), "probe requires normal, lag-zero arrays")
        candidates = sorted({int(arr.row_frame[r]) for start, end in arr.runs for r in range(start, end)})
        n = (26, 26, 26, 25, 25)[i]
        require(len(candidates) >= n, "not enough unique eligible training frames")
        selections.append({"session_id": arr.session.session_id, "steps_sha256": arr.session.sha256,
                           "frame_ids": rng.sample(candidates, n)})
    return {"seed": 20260928, "unit": "unique_cached_frame", "views": ["global", "crop"],
            "sessions": selections, "sha256": cm3.digest(selections)}


def paired_receipt(batches):
    """All seeds/arms, reordered construction, shared tensor identity and 13 epochs."""
    receipts = {}
    for seed in (0, 1, 2):
        arms = {arm: cm3.tensor_manifest(cm3.Policy(cm3.Config(arm, seed))) for arm in cm3.ARMS}
        h = {x["name"]: x for x in arms["H"]["tensors"]}
        for arm in reversed(cm3.ARMS):
            cm3.initialized(seed, "proof/dummy", lambda: torch.nn.Linear(19, 17))
            current = cm3.tensor_manifest(cm3.Policy(cm3.Config(arm, seed)))
            require(current == arms[arm], "construction ordering changed initialized tensors")
            for row in current["tensors"]:
                shared = row["name"].startswith(("core.", "actions.", "camera.")) or arm in ("H", "W")
                if shared and not row["name"].startswith("hist."):
                    require(row == h[row["name"]], "paired tensor mismatch")
        receipts[str(seed)] = {"arms": arms,
                               "window_orders": [cm3.window_order(batches, seed, epoch)[1] for epoch in range(13)]}
    return {"format": "range-bc-cm3-paired-v1", "seeds": receipts, "sha256": cm3.digest(receipts)}


def compare_float(cpu, selected):
    require(cpu.dtype == selected.dtype == torch.float32 and cpu.shape == selected.shape, "probe dtype/shape")
    require(bool(torch.isfinite(cpu).all()) and bool(torch.isfinite(selected).all()), "nonfinite probe")
    error = (selected.cpu() - cpu.cpu()).abs()
    allowed = 1e-4 + 1e-4 * cpu.cpu().abs()
    require(bool((error <= allowed).all()), "CPU/backend numerical tolerance failed")
    return {"max_abs_error": float(error.max()), "atol": 1e-4, "rtol": 1e-4, "elements": cpu.numel()}


def f32_digest(value):
    """Canonical cached bytes, including the sign bit of zero (numeric equality is insufficient)."""
    require(value.dtype == torch.float32, "byte proof requires float32")
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().astype("<f4", copy=False).tobytes()).hexdigest()


def parameter_digests(model):
    return {name: {"shape": list(value.shape), "sha256": f32_digest(value)}
            for name, value in sorted(model.state_dict().items())}


def decisions(actions, camera, live_mask, pitch_known):
    """Exact executor feedback path, carrying its own held state; no true labels."""
    previous = torch.zeros(actions.shape[0], steps.PREV_DIM)
    output = []
    for t in range(actions.shape[1]):
        previous = next_previous(actions[:, t], camera[:, t], previous, live_mask, pitch_known)
        output.append(previous.clone())
    return torch.stack(output, 1)


def next_previous(actions, camera, previous, live_mask, pitch_known):
    """One executed step; own_previous's sequence-shift API does not decode length one."""
    dev = actions.device
    live = torch.tensor(live_mask, dtype=torch.bool, device=dev)
    pk = torch.tensor(pitch_known, dtype=torch.bool, device=dev)
    classes = train._median_classes(camera.float().softmax(-1))
    yaw, pitch = (x.to(dev) for x in train._saturated_classes())
    sent, _ = train._sent_vector(actions.float().sigmoid(), yaw[classes[:, 0]], pitch[classes[:, 1]],
                                 (previous[:, :vocab.N] >= .5) & live, live, pk,
                                 torch.arange(len(previous), device=dev), steps.PREV_DIM)
    return sent


def policy_comparison(model, global_features, crop_features, prev, *, device, live_mask, pitch_known):
    cpu = copy.deepcopy(model).cpu().eval()
    selected = copy.deepcopy(model).to(device).eval()
    with torch.no_grad():
        a = cpu(global_features.cpu(), crop_features.cpu(), None, prev.cpu())
        b = selected(global_features.to(device), crop_features.to(device), None, prev.to(device))
    result = {"actions": compare_float(a[0], b[0].cpu()), "camera": compare_float(a[1], b[1].cpu())}
    require(torch.equal(decisions(a[0], a[1], live_mask, pitch_known),
                        decisions(b[0].cpu(), b[1].cpu(), live_mask, pitch_known)), "executed decisions differ")
    result["executed_identical"] = True
    return result


@torch.no_grad()
def numerical_features(backbone, arrays, selection, *, device):
    """Only the approved 128-frame selection. No full extraction or cache writes."""
    import numpy as np
    require(device in ("mps", "cuda"), "selected numerical proof needs the approved accelerator")
    require(selection == sample_frames(arrays), "changed numerical probe selection")
    cpu, selected = copy.deepcopy(backbone).cpu().eval(), copy.deepcopy(backbone).to(device).eval()
    original = parameter_digests(selected)
    comparisons, blocks = [], {"global": [], "crop": []}
    for arr, take in zip(arrays, selection["sessions"]):
        ids = take["frame_ids"]
        for start in range(0, len(ids), 8):
            group = ids[start:start + 8]
            rgb = [torch.from_numpy(np.array(a[group], copy=True)) for a in (arr.global_frames, arr.crop_frames)]
            reference = cm3_features.extract_views(cpu, *rgb, device="cpu")
            first = cm3_features.extract_views(selected, *rgb, device=device)
            second = cm3_features.extract_views(selected, *rgb, device=device)
            for name, c, a, b in zip(("global", "crop"), reference, first, second):
                require(a.shape == b.shape and f32_digest(a) == f32_digest(b), "same-backend feature bytes differ")
                comparisons.append({"session": arr.session.session_id, "frame_ids": group, "view": name,
                                    "repeat_sha256": f32_digest(a),
                                    **compare_float(c, a)})
                blocks[name].append(a)
    require(original == parameter_digests(selected), "backbone parameter bytes changed")
    require(all(p.grad is None and not p.requires_grad for p in selected.parameters()), "backbone gradients")
    values = {k: torch.cat(v) for k, v in blocks.items()}
    return values, {"format": "range-bc-cm3-numerical-v1", "selection_sha256": selection["sha256"],
                    "device": device, "comparisons": comparisons, "repeat_identical": True,
                    "backbone_unchanged": True, "parameter_digests": original, "dev_opened": False}


@torch.no_grad()
def normalization_diagnostics(model, global_frames, crop_frames, prev):
    """No tuning: report feature scale and sigmoid/tanh saturation of actual LSTM gates."""
    g, c = model.view_features(global_frames, crop_frames)
    normalized = torch.cat((model.global_norm(g), model.crop_norm(c)), -1)
    h = model.hist(prev) if model.config.arm == "W" else normalized.new_zeros(*normalized.shape[:2], 64)
    inputs = torch.cat((normalized, h), -1)
    hidden = inputs.new_zeros(len(inputs), 512)
    cell = hidden.clone()
    gates = []
    for t in range(inputs.shape[1]):
        z = F.linear(inputs[:, t], model.core.weight_ih_l0, model.core.bias_ih_l0)
        z = z + F.linear(hidden, model.core.weight_hh_l0, model.core.bias_hh_l0)
        i, f, candidate, o = z.chunk(4, -1)
        cell = torch.sigmoid(f) * cell + torch.sigmoid(i) * torch.tanh(candidate)
        hidden = torch.sigmoid(o) * torch.tanh(cell)
        gates.append(z)
    z = torch.stack(gates, 1)
    sig = torch.sigmoid(torch.cat((z[..., :1024], z[..., 1536:]), -1))
    candidate = torch.tanh(z[..., 1024:1536])
    return {"pre_range": [float(torch.cat((g, c), -1).min()), float(torch.cat((g, c), -1).max())],
            "post_range": [float(normalized.min()), float(normalized.max())],
            "gate_preactivation_range": [float(z.min()), float(z.max())],
            "sigmoid_saturated_share": float(((sig <= .01) | (sig >= .99)).float().mean()),
            "tanh_saturated_share": float((candidate.abs() >= .99).float().mean())}


def verify_smoke_repeat(first_model, first_receipt, second_model, second_receipt):
    ignore = {"seconds", "seconds_per_update", "updates_per_second", "peak_memory_bytes", "mps_current_allocated_bytes"}
    require({k: v for k, v in first_receipt.items() if k not in ignore} ==
            {k: v for k, v in second_receipt.items() if k not in ignore}, "non-timing smoke blocks differ")
    a, b = cm3_train.checkpoint_bytes(first_model), cm3_train.checkpoint_bytes(second_model)
    require(a == b, "smoke checkpoint bytes differ")
    return {"checkpoint_sha256": hashlib.sha256(a).hexdigest(), "identical": True}


@torch.no_grad()
def time_evaluation(model, run_lengths, *, device, path, window_count):
    """Synthetic-only workload timing. Run lengths are frozen metadata, never dev payloads.

    Times both TF and scalar SF with the existing decode/feedback arithmetic. Synthetic
    images/features use S(0, smoke/<path>/timing-inputs); no scores or targets exist here.
    """
    require((path in cm3.ARMS and getattr(model.config, "arm", None) == path) or
            (path == "A" and model.config == train.Config(hud=False)), "timing recipe mismatch")
    require(run_lengths and all(type(n) is int and n > 0 for n in run_lengths), "invalid timing dimensions")
    require(type(window_count) is int and window_count > 0, "frozen dev window count required for loss timing")
    generator = torch.Generator().manual_seed(0 if path == "A" else cm3.stream_seed(0, f"smoke/{path}/timing-inputs"))
    model.eval()
    sync = torch.mps.synchronize if device == "mps" else torch.cuda.synchronize if device == "cuda" else lambda: None
    result = {}
    # Synthetic targets only, built before timing; their values are never reported as scores.
    header, rows = fixture.session("cm3-synthetic-eval-timing", runs=tuple(run_lengths), seed=20260928)
    session = steps.Session("synthetic", "0" * 64, header, rows)
    offsets, running = [], 0
    for length in run_lengths:
        offsets.append(running)
        running += length
    for mode in ("teacher", "self"):
        sync()
        start = time.perf_counter()
        metric_runs = []
        for ri, length in enumerate(run_lengths):
            state = None
            previous = torch.zeros(1, 1, steps.PREV_DIM, device=device)
            predictions = []
            previous_hold = [0] * vocab.N
            for offset in range(0, length, 96):
                n = min(96, length - offset)
                if path in ("I", "A"):
                    g = torch.randint(0, 256, (1, n, 3, 144, 256), generator=generator, dtype=torch.uint8)
                    c = torch.randint(0, 256, (1, n, 3, 128, 128), generator=generator, dtype=torch.uint8)
                else:
                    g = torch.randn(1, n, cm3.FEATURE_DIM, generator=generator)
                    c = torch.randn(1, n, cm3.FEATURE_DIM, generator=generator)
                prev = torch.zeros(1, n, steps.PREV_DIM, device=device)
                feats = model.features(g.to(device), c.to(device), None, 1, n, prev)
                if mode == "teacher":
                    a, m, state = model.step(feats, prev, state)
                    # Includes CPU probability conversion/median class overhead without scores.
                    probabilities, camera = a.sigmoid().cpu(), m.softmax(-1).cpu()
                    for t in range(n):
                        p, m = probabilities[0, t], camera[0, t]
                        predictions.append({"held": p[0].tolist(), "press": p[1].tolist(), "release": p[2].tolist(),
                                            "yaw": vocab.class_degrees(vocab.median_class(m[0].tolist())),
                                            "pitch": vocab.class_degrees(vocab.median_class(m[1].tolist()))})
                else:
                    for t in range(n):
                        a, m, state = model.step(feats[:, t:t + 1], previous, state)
                        p, camera = a[0, 0].sigmoid().cpu(), m[0, 0].softmax(-1).cpu()
                        held, press, release = executor.decode_step(p[0].tolist(), p[1].tolist(), p[2].tolist(),
                                                                    previous_hold, [True] * vocab.N)
                        yaw, pitch = executor.saturate(vocab.class_degrees(vocab.median_class(camera[0].tolist())),
                                                       vocab.class_degrees(vocab.median_class(camera[1].tolist())))
                        sent = {"held": held, "press": press, "release": release, "known": [True] * vocab.N,
                                "camera_known": True, "cy": vocab.camera_class(yaw), "cp": vocab.camera_class(pitch)}
                        previous = torch.tensor(steps.prev_vector(sent))[None, None].to(device)
                        previous_hold = held
                        predictions.append({"held": held, "press": press, "release": release, "yaw": yaw,
                                            "pitch": pitch, "margin": train._margin(p, camera, [True] * vocab.N, True)})
            records = steps.step_records(session, offsets[ri], offsets[ri] + length, lag=0)
            metric_runs.append(list(zip(records, predictions)))
        sync()
        result[mode + "_seconds"] = time.perf_counter() - start
        start = time.perf_counter()
        # Exercise the unchanged metric math, then discard all synthetic score values.
        metrics.stratified(metric_runs, **(metrics.TEACHER if mode == "teacher" else metrics.SELF))
        if mode == "teacher":
            metrics.evaluate(train.executed_runs(metric_runs, [True] * vocab.N), **metrics.EXECUTED_TEACHER)
        else:
            metrics.selffed_checks(metric_runs, [True] * vocab.N)
            metrics.sanity(metric_runs)
        result[mode + "_metric_seconds"] = time.perf_counter() - start
    sync()
    start = time.perf_counter()
    for offset in range(0, window_count, 8):
        b = min(8, window_count - offset)
        if path in ("I", "A"):
            g = torch.randint(0, 256, (b, 96, 3, 144, 256), generator=generator, dtype=torch.uint8)
            c = torch.randint(0, 256, (b, 96, 3, 128, 128), generator=generator, dtype=torch.uint8)
        else:
            g = torch.randn(b, 96, cm3.FEATURE_DIM, generator=generator)
            c = torch.randn(b, 96, cm3.FEATURE_DIM, generator=generator)
        batch = {"global": g, "crop": c, "hud": torch.zeros(b, 96, 1), "prev": torch.zeros(b, 96, steps.PREV_DIM),
                 "act": torch.zeros(b, 96, 3, vocab.N), "act_mask": torch.ones(b, 96, 3, vocab.N, dtype=torch.bool),
                 "camera": torch.full((b, 96, 2), vocab.ZERO_CLASS, dtype=torch.long),
                 "camera_mask": torch.ones(b, 96, 2, dtype=torch.bool), "regime": torch.zeros(b, 96), "aug": None}
        batch = train.to_device(batch, device)
        train.loss_terms(*train.forward(model, batch)[:2], batch, torch.ones(2, vocab.N, device=device))
    sync()
    result["per_epoch_dev_loss_seconds"] = time.perf_counter() - start
    return {"format": "range-bc-cm3-synthetic-eval-timing-v1", "path": path, "run_lengths": list(run_lengths),
            "window_count": window_count, "loss_evaluations_per_fit": 13,
            "source": "synthetic tensors; frozen workload dimensions only", "dev_scores": False, **result}
