"""Offline-only VUH-1346 diagnosis; never imports capture or pad drivers.

Run from repo root with the rivals-live-cu128 Python. Reads only named admitted
James sessions and existing live episode logs/frames. One CPU decoder, two threads.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "rl/out/idle"
BUNDLE = Path("D:/rivals-policy/bundles/bc2-mix399-s0")
JAMES = "20260923T171533-187Z-33696-5"
PEAK_RSS = 0


def resources():
    global PEAK_RSS
    processes = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                               text=True, check=True).stdout.lower()
    if any(x in processes for x in ('"obs64.exe"', '"marvelrivals', '"rivals-win64')):
        raise RuntimeError("Game/OBS started; offline GPU work stops")
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ("peak", "rss", "pp", "p", "pn", "n", "pf", "peakpf")]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                 ctypes.byref(c), c.cb):
        raise ctypes.WinError()
    PEAK_RSS = max(PEAK_RSS, c.rss, c.peak)
    if c.rss > 3 * 1024 ** 3:
        raise RuntimeError(f"RAM cap exceeded: {c.rss / 1024 ** 3:.2f} GiB")


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def merged_seconds(intervals):
    total, end = 0., -float("inf")
    for a, b in sorted(intervals):
        if b > max(a, end):
            total += b - max(a, end)
        end = max(end, b)
    return total


def log_stats(folder):
    rr = rows(folder / "frames.jsonl")
    dec = [r for r in rr if r["event"] == "decision"]
    sends = [r for r in rr if r["event"] == "send"]
    end = max(r["t"] for r in rr)
    start = next((r["t"] for r in rr if r["event"] == "policy_start"), 0.)
    # A later send overwrites the previous command. Camera pulses release at
    # release_at; stale decisions explicitly release. Neutral leases are not activity.
    all_intervals, nonzero_intervals, camera_intervals = [], [], []
    releases = [r["t"] + r.get("age_s", 0.) for r in dec
                if r.get("disposition") == "stale_after_inference"]
    releases += [r["t"] for r in rr if r["event"] in ("discard", "stop")]
    for i, r in enumerate(sends):
        a = r["t"]
        b = min(r["release_at"], end, sends[i + 1]["t"] if i + 1 < len(sends) else end)
        b = min([b] + [t for t in releases if a < t <= b])
        interval = (a, max(a, b))
        all_intervals.append(interval)
        if any(bool(v) for v in r["pad"].values()):
            nonzero_intervals.append(interval)
        if r["pad"].get("rx") or r["pad"].get("ry"):
            camera_intervals.append(interval)
    import numpy as np
    pct = lambda key: {f"p{p}": float(np.percentile([r[key] for r in dec], p)) for p in (50, 95)}
    result = {"source": folder.relative_to(ROOT).as_posix(), "seconds": end - start,
              "decisions": len(dec), "ready": sum(r.get("disposition") == "ready" for r in dec),
              "stale": sum(r.get("disposition") == "stale_after_inference" for r in dec),
              "sends": len(sends), "sent_ticks": len({r["tick"] for r in sends}),
              "nonzero_sends": sum(any(bool(v) for v in r["pad"].values()) for r in sends),
              "lease_seconds_including_neutral": merged_seconds(all_intervals),
              "nonzero_command_seconds": merged_seconds(nonzero_intervals),
              "camera_command_seconds": merged_seconds(camera_intervals),
              "inference_s": pct("inference_s"), "age_s": pct("age_s"),
              "decoded_action_steps": sum(any(r.get("held", {}).values()) or any(r.get("press", {}).values())
                                          for r in dec),
              "capture_gap_s": {f"p{p}": float(np.percentile(np.diff([r["t"] for r in dec]), p))
                                for p in (50, 95)},
              "abs_yaw_median": float(np.median([abs(r["yaw_deg"]) for r in dec]))}
    result["nonzero_time_share"] = result["nonzero_command_seconds"] / result["seconds"]
    return result, (dec, all_intervals, nonzero_intervals)


def live_frames(folder, limit=None):
    import cv2
    dd = [r for r in rows(folder / "frames.jsonl") if r["event"] == "decision" and "file" in r]
    for r in dd[:limit]:
        yield cv2.imread(str(folder / r["file"])), r.get("policy_frame_t", r["t"])


def describe(a, c, policy):
    import numpy as np
    from policy.range_bc import vocab
    reps = np.array([vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)])
    yaw = (c[:, 0] * reps).sum(-1)
    held = (a[:, 0] >= np.array(policy.levels)) & np.array(policy.mask)
    prev = np.concatenate([np.zeros_like(held[:1]), held[:-1]])
    tap = ~held & ~prev & (a[:, 1] >= policy.levels) & (a[:, 2] >= policy.levels) & policy.mask
    return {"n": len(a), "hold_max_median": float(np.median(a[:, 0].max(-1))),
            "press_max_median": float(np.median(a[:, 1].max(-1))),
            "turn_mass_median": float(np.median(c[:, 0, abs(reps) >= .5].sum(-1))),
            "zero_class_mass_median": float(np.median(c[:, 0, vocab.ZERO_CLASS])),
            "abs_yaw_median": float(np.median(abs(yaw))),
            "decoded_active_steps": int((held | tap).any(-1).sum()),
            "median_zero_steps": int(((np.cumsum(c[:, 0], -1) >= .5).argmax(-1) == vocab.ZERO_CLASS).sum())}


def eager_inputs(policy, iterator):
    """Record the actual LivePolicy model inputs, excluding its recurrent state."""
    import numpy as np
    import torch
    captured, aa, cc = [], [], []
    original = policy.model.forward
    def record(*args, **kwargs):
        # feats, gp, gc, cp, cc, state, green, dt. target is unused in mix399.
        captured.append(tuple(x.detach().cpu().clone() if x is not None else None
                              for x in (*args[:5], args[6], args[7])))
        return original(*args, **kwargs)
    policy.model.forward = record
    policy.reset()
    try:
        for k, (frame, stamp) in enumerate(iterator):
            if k % 20 == 0:
                resources()
            a, c = policy._bc2_predict(frame, stamp)
            aa.append(a)
            cc.append(c)
    finally:
        policy.model.forward = original
    inputs = [torch.cat([r[k] for r in captured], dim=1) if captured[0][k] is not None else None
              for k in range(7)]
    return inputs, np.asarray(aa), np.asarray(cc)


def offline(policy, inputs, chunk=512):
    """Use the real whole-run offline evaluator on a small reconstructed session."""
    import torch
    from policy.bc2.train import predict
    device_inputs = [x.to(policy.device) if x is not None else None for x in inputs]
    n = inputs[0].shape[1]
    def take(idx):
        return tuple(x[:, idx[0]] if x is not None else None for x in device_inputs[:5]) + (
            None, None if device_inputs[5] is None else device_inputs[5][:, idx[0]],
            device_inputs[6][:, idx[0]], torch.zeros(1, idx.shape[1], 10, device=policy.device))
    session = SimpleNamespace(n=n, runs=[(0, n)], feats=device_inputs[0], inputs=take)
    with torch.inference_mode():
        a, c = predict(policy.model, session, chunk=chunk)
    return a.cpu().numpy(), c.cpu().numpy()


def cached_inputs(feature_dir, ids, stride):
    import numpy as np
    import torch
    arr = {}
    for key, name in (("f", "feats.npy"), ("g", "gray_g.npy"), ("c", "gray_c.npy"), ("green", "green.npy")):
        file = feature_dir / name
        if file.exists():
            mm = np.load(file, mmap_mode="r")
            arr[key] = mm
    prev = ids - stride
    prev[0] = ids[0]
    tensor = lambda key, ix: torch.from_numpy(np.array(arr[key][ix]))[None]
    return [tensor("f", ids), tensor("g", prev), tensor("g", ids), tensor("c", prev), tensor("c", ids),
            tensor("green", ids) if "green" in arr else None, torch.full((1, len(ids)), float(stride))]


def run():
    import numpy as np
    resources()
    ctypes.windll.kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    os.environ["OMP_NUM_THREADS"] = "2"
    import cv2
    import torch
    cv2.setNumThreads(2)
    torch.set_num_threads(2)
    from policy.live_policy import LivePolicy
    from policy.live_replay import frames_for
    from policy.range_bc import steps
    OUT.mkdir(parents=True, exist_ok=True)
    results = {"method": "offline-only; same checkpoint; actual live inputs vs train.predict; CPU decode",
               "logs": [], "parity": {}, "conditions": {}}
    timeline = None
    live = ROOT / "data/calibration/compat-check-20260929/learned-01-a"
    folders = [live]
    for sitting in ("01", "07"):
        folders += sorted((ROOT / f"data/calibration/rl-sitting-20260930-{sitting}").glob("ep-*-bc"))
    for folder in folders:
        result, intervals = log_stats(folder)
        results["logs"].append(result)
        if folder == live:
            timeline = intervals
    (OUT / "logs.json").write_text(json.dumps(results["logs"], indent=2) + "\n")
    print("Logs read: " + str(len(folders)), flush=True)
    policy = LivePolicy(BUNDLE, cuda_graph=False)
    resources()
    results["config"] = policy.model.config.as_dict()
    step_path = ROOT / f"data/human/sessions/{JAMES}/{JAMES}.steps.jsonl"
    session = steps.load(step_path, denylist=steps.load_denylist())
    assert session.split == "train"
    fd = Path("D:/rivals-policy/dev-features") / JAMES
    with np.load(fd / "targets.npz") as target_file:
        target = {k: target_file[k] for k in target_file.files}
    ids = np.arange(900, 1260, 3)
    assert not target["run_start"][ids[1:]].any()
    picked = [session.rows[int(target["row"][i])] for i in ids]
    def james_frames():
        yield from ((frame, row["anchor_ns"] / 1e9) for row, frame in
                    frames_for(picked[0]["frame"]["video_path"], picked, hwaccel=False, threads=2))
    sources = {"live_A": lambda: live_frames(live), "James_10Hz": james_frames,
               "BC07_ep000": lambda: live_frames(ROOT / "data/calibration/rl-sitting-20260930-07/ep-000-bc", 81)}
    recorded = {}
    outputs = {}
    for name, source in sources.items():
        resources()
        started = time.monotonic()
        inp, a, c = eager_inputs(policy, source())
        recorded[name] = inp
        outputs[name] = (a, c)
        ao, co = offline(policy, inp)
        outputs[name + "_offline"] = (ao, co)
        a1, c1 = offline(policy, inp, chunk=1)
        results["conditions"][name + "_live"] = describe(a, c, policy)
        results["conditions"][name + "_offline"] = describe(ao, co, policy)
        results["parity"][name] = {"action_probability_max_abs_difference": float(abs(a - ao).max()),
                                   "camera_probability_max_abs_difference": float(abs(c - co).max()),
                                   "single_step_action_max_abs_difference": float(abs(a - a1).max()),
                                   "single_step_camera_max_abs_difference": float(abs(c - c1).max())}
        print(name + " " + json.dumps(results["conditions"][name + "_live"]) +
              f" ({time.monotonic() - started:.1f}s)", flush=True)
    ci = cached_inputs(fd, ids, 3)
    ci[6][0, 0] = 1.  # first live frame has no preceding capture clock interval
    ca, cc = offline(policy, ci)
    results["conditions"]["James_cache_offline"] = describe(ca, cc, policy)
    results["cache_vs_live_inputs"] = {"feature_mean_abs_difference": float(abs(ci[0] - recorded["James_10Hz"][0]).float().mean()),
                                      "gray_global_mean_abs_difference": float(abs(ci[2].float() - recorded["James_10Hz"][2].float()).mean()),
                                      "gray_crop_mean_abs_difference": float(abs(ci[4].float() - recorded["James_10Hz"][4].float()).mean())}
    # Isolate motion dependence with labelled diagnostic counterfactuals (not aiming evidence).
    li, ji = recorded["live_A"], recorded["James_10Hz"]
    n = min(li[0].shape[1], ji[0].shape[1])
    for name, visual, motion in (("live_visual_James_motion", li, ji), ("James_visual_live_motion", ji, li)):
        ab = [visual[0][:, :n], *[motion[k][:, :n] for k in range(1, 5)],
              visual[5][:, :n] if visual[5] is not None else None, li[6][:, :n]]
        a, c = offline(policy, ab)
        results["conditions"][name] = describe(a, c, policy)
    frozen = [x[:, :1].expand(-1, n, *x.shape[2:]).clone() if x is not None else None for x in ji]
    frozen[1], frozen[3], frozen[6] = frozen[2].clone(), frozen[4].clone(), li[6][:, :n]
    a, c = offline(policy, frozen)
    results["conditions"]["James_first_frame_frozen"] = describe(a, c, policy)
    # Changing dt alone does not provide missing motion/intent.
    dt30 = list(li)
    dt30[6] = torch.ones_like(li[6])
    a, c = offline(policy, dt30)
    results["conditions"]["live_A_dt1"] = describe(a, c, policy)
    # Exact deployed CUDA graph parity, including reset/reuse on two source domains.
    policy.graph = {}
    for name in ("live_A", "James_10Hz"):
        resources()
        policy.reset()
        aa, cc = [], []
        for k, (frame, stamp) in enumerate(sources[name]()):
            if k % 20 == 0:
                resources()
            a, c = policy._bc2_predict(frame, stamp)
            aa.append(a)
            cc.append(c)
        a, c = np.array(aa), np.array(cc)
        eager_a, eager_c = outputs[name]
        results["parity"][name]["graph_action_max_abs_difference"] = float(abs(a - eager_a).max())
        results["parity"][name]["graph_camera_max_abs_difference"] = float(abs(c - eager_c).max())
        results["conditions"][name + "_graph"] = describe(a, c, policy)
    # Activity in two admitted TRAIN range sessions, and conditional restart support.
    results["human_activity"] = []
    for sid in (JAMES, "20260923T205528-900Z-45572-3", "20260925T212646-322Z-49728-6"):
        path = ROOT / f"data/human/sessions/{sid}/{sid}.steps.jsonl"
        admitted = steps.load(path, denylist=steps.load_denylist())
        assert admitted.split in ("train", "val")
        base = Path("D:/rivals-policy/dev-features" if sid != "20260925T212646-322Z-49728-6"
                    else "D:/rivals-policy/local-features") / sid
        with np.load(base / "targets.npz") as z:
            t = {k: z[k] for k in z.files}
        mask = t["valid"] & t["cam_known"].all(-1) & t["act_known"][:, :2].all((1, 2))
        still_yaw = abs(t["yaw"]) < .5
        strict_yaw = abs(t["yaw"]) < .05
        idle = still_yaw & (abs(t["pitch"]) < .5) & ~t["act"][:, :2].any((1, 2))
        def longest(bits):
            best = current = 0
            for b, reset in zip(bits, t["run_start"]):
                current = 0 if reset or not b else current
                current = current + 1 if b else 0
                best = max(best, current)
            return best
        history = np.ones(len(mask), bool)
        for back in (1, 2, 3):
            history[back:] &= idle[:-back] & (np.cumsum(t["run_start"])[back:] == np.cumsum(t["run_start"])[:-back])
            history[:back] = False
        sel = mask & history
        results["human_activity"].append({"session": sid, "split": admitted.split, "valid_steps": int(mask.sum()),
            "yaw_still_share": float(still_yaw[mask].mean()), "fully_idle_share": float(idle[mask].mean()),
            "strict_yaw_still_share": float(strict_yaw[mask].mean()),
            "longest_strict_yaw_still_steps": longest(strict_yaw & mask),
            "longest_yaw_still_steps": longest(still_yaw & mask), "longest_fully_idle_steps": longest(idle & mask),
            "steps_after_3_idle": int(sel.sum()), "active_next_share_after_3_idle": float((~idle)[sel].mean()) if sel.any() else None})
        if admitted.split == "train":
            # Scene similarity is a proxy, not equality of gameplay state. Read
            # only these named admitted train features, in bounded CPU blocks.
            reference = li[0][0, 5:].float().mean(0).numpy().reshape(-1)
            reference /= np.linalg.norm(reference)
            # Do not let an entire mapped feature file stay resident on Windows.
            # Bounded sequential reads release each block instead of faulting in
            # another gigabyte of mapped pages over the policy's resident memory.
            with (base / "feats.npy").open("rb") as feature_stream:
                version = np.lib.format.read_magic(feature_stream)
                read_header = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                               else np.lib.format.read_array_header_2_0)
                shape, fortran, dtype = read_header(feature_stream)
                assert not fortran and shape[1:] == (2, reference.size // 2)
                cosines = np.zeros(shape[0], np.float32)
                for first in range(0, shape[0], 128):
                    if first % 2560 == 0:
                        resources()
                    count = min(128, shape[0] - first)
                    block = np.frombuffer(feature_stream.read(count * reference.size * dtype.itemsize), dtype)
                    block = block.astype(np.float32).reshape(count, reference.size)
                    cosines[first:first + count] = block @ reference / np.linalg.norm(block, axis=1).clip(1e-6)
            top = np.argsort(np.where(mask, cosines, -1))[-100:]
            near = (cosines >= .90) & mask
            results["human_activity"][-1]["scene_proxy"] = {
                "method": "cosine to mean live_A features after first 5 retained decisions; no motion input",
                "top100_cosine_min": float(cosines[top].min()), "top100_cosine_max": float(cosines[top].max()),
                "top100_fully_idle_share": float(idle[top].mean()),
                "top100_strict_yaw_still_share": float(strict_yaw[top].mean()),
                "near90_steps": int(near.sum()),
                "near90_fully_idle_share": float(idle[near].mean()) if near.any() else None,
                "near90_after3idle_steps": int((near & sel).sum()),
                "near90_active_next_after3idle": float((~idle)[near & sel].mean()) if (near & sel).any() else None}
    resources()
    results["peak_rss_gib"] = PEAK_RSS / 1024 ** 3
    results["gpu_peak_allocated_gib"] = torch.cuda.max_memory_allocated() / 1024 ** 3
    np.savez(OUT / "comparison.npz", **{name + "_" + key: arr for name, (a, c) in outputs.items()
                                      for key, arr in (("actions", a), ("cameras", c))})
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    plot(results, outputs, timeline)
    policy.close()
    print("Complete; peak RSS GiB " + str(results["peak_rss_gib"]), flush=True)


def plot(results, outputs, timeline):
    # Pillow avoids another plotting dependency and publishes no source frames.
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from policy.range_bc import vocab
    img = Image.new("RGB", (1500, 960), "#101923")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 25)
    small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    big = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 32)
    draw.text((35, 20), "mix399: idle survives the offline path", font=big, fill="white")
    draw.text((35, 65), "Offline replay, PC / same actual inputs / mean camera decode / no game input", font=font, fill="#b7cadb")
    reps = np.array([vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)])
    for panel, name in enumerate(("live_A", "James_10Hz")):
        x, y, w, h = 100, 160 + panel * 245, 1310, 145
        a, c = outputs[name]
        tm = c[:, 0, abs(reps) >= .5].sum(-1)
        draw.text((35, y - 43), name + f"  n={len(a)}; hold/turn probability", font=font, fill="white")
        draw.rectangle((x, y, x + w, y + h), outline="#657b8b")
        draw.text((48, y - 12), "1.0", font=small, fill="#b7cadb")
        draw.text((48, y + h - 15), "0.0", font=small, fill="#b7cadb")
        for vals, color in ((a[:, 0].max(-1), "#55d8ba"), (tm, "#f7b55d")):
            pts = [(x + i * w / max(1, len(vals) - 1), y + h * (1 - float(v))) for i, v in enumerate(vals)]
            draw.line(pts, fill=color, width=3)
        ao, co = outputs[name + "_offline"]
        for vals in (ao[:, 0].max(-1), co[:, 0, abs(reps) >= .5].sum(-1)):
            pts = [(x + i * w / max(1, len(vals) - 1), y + h * (1 - float(v))) for i, v in enumerate(vals)]
            for i in range(0, len(pts) - 1, 3):
                draw.line(pts[i:i + 2], fill="#e4edf5", width=2)
        draw.text((x, y + h + 7), "Decision index: 0", font=small, fill="#b7cadb")
        draw.text((x + w - 50, y + h + 7), str(len(a) - 1), font=small, fill="#b7cadb")
    draw.text((50, 645), "Teal = maximum hold probability; orange = P(|yaw class| >= 0.5 degrees)", font=font, fill="white")
    draw.text((50, 689), "White dashes = offline train.predict on identical inputs (overlapping both live traces).", font=font, fill="#b7cadb")
    dec, leases, nonzero = timeline
    end = results["logs"][0]["seconds"]
    x, y, w = 100, 790, 1310
    draw.text((35, 740), "learned-01 A: when did a nonzero pad command actually get sent?", font=font, fill="white")
    draw.rectangle((x, y, x + w, y + 35), fill="#324556")
    for aa, bb in nonzero:
        draw.rectangle((x + aa / end * w, y, x + max(aa + .01, bb) / end * w, y + 35), fill="#f7b55d")
    s = results["logs"][0]
    draw.text((x, y + 48), f"0 - {end:.2f} seconds; nonzero {s['nonzero_command_seconds']:.3f}s "
              f"({s['nonzero_time_share']:.3%}); {s['stale']}/{s['decisions']} stale", font=font, fill="white")
    draw.text((35, 914), "Sources: compat-check-20260929/learned-01-a; James TRAIN 171533 feature rows 900:1260:3.",
              font=small, fill="#b7cadb")
    img.save(OUT / "comparison.png")


if __name__ == "__main__":
    run()
