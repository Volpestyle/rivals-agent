"""Offline-only stage timing of the unchanged range_bc harness.

Fixed tracked fixtures, seeded architectures or explicitly pinned model artifacts:
no corpus, downloads, desktop capture, pad driver or live-input entry point.
"""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import csv
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = tuple(ROOT / "tests/fixtures/range" / f"pos-fight-{n}.jpg" for n in ("017", "060", "101"))


class Timings:
    def __init__(self):
        self.values = defaultdict(list)
        self.events = defaultdict(list)

    def gpu_wrap(self, name, function):
        def measured(*args, **kwargs):
            import torch
            start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
            start.record()
            value = function(*args, **kwargs)
            end.record()
            self.events[name + "_gpu"].append((start, end))
            return value
        return measured

    def wrap(self, name, function):
        def measured(*args, **kwargs):
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.values[name].append((time.perf_counter() - started) * 1000)
        return measured

    def report(self):
        from agent.live_range_bc import distribution
        if self.events:
            import torch
            torch.cuda.synchronize()
            for name, events in self.events.items():
                self.values[name].extend(a.elapsed_time(b) for a, b in events)
            self.events.clear()
        return {name: distribution(values) for name, values in sorted(self.values.items())}


def conflicting_processes(tasklist):
    return [row[0] for row in csv.reader(io.StringIO(tasklist))
            if row and (row[0].lower().startswith("marvel") or row[0].lower() == "obs64.exe")]


class PCGuard:
    """BelowNormal CPU job; a conflicting process or >3 GB RSS terminates it."""
    def __init__(self, output):
        if os.name != "nt":
            raise RuntimeError("This measurement is for the Windows PC")
        self.output, self.done, self.peak = output, threading.Event(), 0
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
        self.handle = self.kernel.GetCurrentProcess()
        self.kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not self.kernel.SetPriorityClass(self.handle, 0x4000):
            raise ctypes.WinError(ctypes.get_last_error())
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        self.check()
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def check(self):
        tasks = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                               text=True, check=True, timeout=3).stdout
        conflicts = conflicting_processes(tasks)
        if conflicts:
            raise RuntimeError(f"game/OBS present: {conflicts}")
        class Memory(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in
                ("peak_rss", "rss", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        if not self.psapi.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        self.peak = max(self.peak, memory.peak_rss)
        if memory.rss > 3_000_000_000:
            raise RuntimeError("profile RSS exceeded 3 GB")

    def watch(self):
        while not self.done.wait(.5):
            try:
                self.check()
            except BaseException as exc:
                (self.output / "ABORT.json").write_text(json.dumps({"reason": str(exc)}))
                os._exit(3)  # No actuator exists; also stops a stuck inference thread.

    def close(self):
        self.done.set()
        self.thread.join(4)


class ReplayOnly:
    """Duck-typed Live replacement. Never constructs the real Live class."""
    def __init__(self, frames):
        self.frames, self.index, self.frame_t, self.closed = frames, 0, 0., False
        self.sends = 0

    def fresh(self):
        self.frame_t = time.perf_counter()
        frame = self.frames[self.index % len(self.frames)]
        self.index += 1
        return frame.copy()

    def send_guarded(self, pad, *, not_after, release_at, scope_not_after):
        if self.closed or time.perf_counter() >= min(not_after, release_at, scope_not_after):
            from agent.controller import RangeLost
            raise RangeLost("offline sink closed or deadline elapsed")
        self.sends += 1  # Not a hardware send; this measures Python sink overhead only.

    def release(self):
        pass

    def close(self):
        self.closed = True


def architecture(name):
    import torch
    from policy.range_bc import model, cm3
    torch.manual_seed(0)
    policy = model.Policy(model.Config(hud=False)) if name == "legacy" else cm3.Policy(cm3.Config(arm=name, seed=0))
    # Deterministic nonneutral output makes command duty comparable across arms.
    with torch.no_grad():
        from policy.range_bc import vocab
        policy.actions.weight.zero_()
        policy.actions.bias.fill_(-20)
        policy.actions.bias[vocab.INDEX["web_cluster"]] = 20
    backbone = None
    if name in ("H", "W"):
        from transformers import Dinov2Config, Dinov2Model
        from policy.range_bc.cm3_features import pool_tokens
        config = Dinov2Config(hidden_size=384, num_hidden_layers=12, num_attention_heads=6,
                              intermediate_size=1536, patch_size=14, image_size=224)
        config._attn_implementation = "eager"
        class SyntheticDino(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.model = Dinov2Model(config).eval()

            def forward(self, pixels):
                return pool_tokens(self.model(pixel_values=pixels).last_hidden_state)
        backbone = SyntheticDino().eval()
    return policy.cpu().eval(), backbone


def instrument(policy, backbone, timings, stack, device="cpu"):
    wrap = timings.gpu_wrap if device == "cuda" else timings.wrap
    for name in ("global_enc", "crop_enc", "hist", "core", "actions", "camera"):
        module = getattr(policy, name, None)
        if module is not None:
            stack.enter_context(patch.object(module, "forward", wrap(name, module.forward)))
    if backbone is not None:
        from policy.range_bc import cm3_features
        stack.enter_context(patch.object(backbone, "forward", wrap("dino_encoder_call", backbone.forward)))
        stack.enter_context(patch.object(cm3_features, "preprocess", timings.wrap("dino_preprocess_per_view", cm3_features.preprocess)))


def profile(args):
    import cv2
    import torch
    from agent import live_range_bc as h
    from scripts.record import in_range
    from perception.scoreboard import is_killfeed
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    cv2.setNumThreads(1)
    frames = [cv2.resize(cv2.imread(str(p)), (2560, 1440)) for p in FIXTURES]
    if not all(in_range(frame) for frame in frames):
        raise RuntimeError("fixed replay fixture failed range guard")
    from policy.range_bc.live_inference import PersistentCachePreprocessor, InProcessCachePreprocessor, DevicePredictor, EncoderPredictor, load_explore_checkpoint
    preprocessor = InProcessCachePreprocessor(compact_bgr=args.compact_bgr) if args.inprocess else (
        PersistentCachePreprocessor() if args.optimized else h.CachePreprocessor())
    recipe, artifacts = None, {}
    support = None
    if args.checkpoint is not None:
        policy, recipe = h.load_checkpoint(args.checkpoint, args.checkpoint_sha256)
        h.validate_distribution(recipe, "normal")
        actual_arm = getattr(policy.config, "arm", "legacy")
        if actual_arm != args.arm:
            raise ValueError("arm label differs from loaded checkpoint")
        support = json.loads(args.support_json.read_text(encoding="utf-8-sig"))
        h.support_mask(support, args.checkpoint_sha256)
        artifacts = {"checkpoint": {"path": str(args.checkpoint), "sha256": args.checkpoint_sha256},
                     "support": {"path": str(args.support_json), "sha256": h.sha256(args.support_json)}}
        backbone = None
    elif args.arm in ("h1", "siglip", "nitrogen"):
        if args.weights_dir is None or args.artifact_manifest is None:
            raise ValueError("trained arms require weights-dir and artifact-manifest")
        artifacts = json.loads(args.artifact_manifest.read_text())
        key = "h1" if args.arm == "h1" else args.arm + "_head"
        policy, recipe = load_explore_checkpoint(args.weights_dir / (key + ".pt"), artifacts[key]["sha256"],
                                                  encoder=args.arm != "h1")
        backbone = None
    else:
        policy, backbone = architecture(args.arm)
    if args.dino_assets:
        if args.arm not in ("H", "W"):
            raise ValueError("DINO assets apply only to H/W")
        from policy.range_bc.cm3_features import FrozenDino
        backbone = FrozenDino(args.dino_assets, config_sha256=args.dino_config_sha256)
    timings = Timings()
    with ExitStack() as stack:
        if hasattr(preprocessor, "close"):
            stack.callback(preprocessor.close)
        preprocess = timings.wrap("ffmpeg_preprocess", preprocessor)
        if args.arm in ("siglip", "nitrogen"):
            predictor = EncoderPredictor(policy, preprocess, device=args.device,
                vision_path=args.weights_dir / (args.arm + "_vision.safetensors"),
                vision_sha256=artifacts[args.arm + "_vision"]["sha256"],
                config_path=args.weights_dir / "config.json",
                config_sha256="172e39dbf0143b8fe22d2f08921730eb8c397967e58cb37d133161e28aa34104")
            wrap = timings.gpu_wrap if args.device == "cuda" else timings.wrap
            stack.enter_context(patch.object(predictor.tower, "forward", wrap("two_view_tower", predictor.tower.forward)))
        elif args.optimized:
            predictor = DevicePredictor(policy, preprocess, cooldowns="normal", backbone=backbone, device=args.device)
        else:
            predictor = h.Predictor(policy, preprocess, cooldowns="normal", backbone=backbone)
        instrument(policy, backbone, timings, stack, args.device)
        predict = timings.wrap("predict_total", predictor)
        for _ in range(3):
            predict(frames[0], None)
        warmup = timings.report()
        timings.values.clear()
        predictor.state = None
        for i in range(args.samples):
            predict(frames[i % len(frames)], h.neutral_history())
        isolated = timings.report()
        timings.values.clear()
        predictor.state = None
        sink = ReplayOnly(frames)
        sink.fresh = timings.wrap("replay_frame_copy", sink.fresh)
        sink.send_guarded = timings.wrap("mock_send", sink.send_guarded)
        manifest = {"mode": "offline replay; no actual pad/capture", "arm": args.arm,
                    "weights": "trained; unchanged outputs" if recipe else "seeded random; web hold forced only to measure duty",
                    "recipe": recipe, "artifacts": artifacts, "device": args.device,
                    "dino_assets": getattr(backbone, "asset_receipt", None),
                    "optimized": args.optimized,
                    "inprocess": args.inprocess,
                    "compact_bgr": args.compact_bgr,
                    "tower_precision": str(predictor.tower_dtype) if hasattr(predictor, "tower_dtype") else "float32",
                    "frames": "tracked 1280x720 range JPEG fixtures, upscaled to 2560x1440",
                    "fixture_sha256": {str(p.relative_to(ROOT)): h.sha256(p) for p in FIXTURES},
                    "source_sha256": {p: h.sha256(ROOT / p) for p in (
                        "agent/live_range_bc.py", "policy/range_bc/model.py", "policy/range_bc/cm3.py",
                        "policy/range_bc/cm3_features.py", "scripts/profile_range_bc_live.py", "policy/range_bc/live_inference.py")},
                    "torch": torch.__version__, "threads": args.threads, "interop_threads": 1,
                    "ffmpeg": preprocessor.version, "graph": preprocessor.graph}
        journal = h.Journal(args.output / "replay", manifest)
        journal.frame = timings.wrap("retention_enqueue", journal.frame)
        journal.event = timings.wrap("event_write", journal.event)
        stack.enter_context(patch.object(h, "decode", timings.wrap("decode", h.decode)))
        mask = h.support_mask(support, args.checkpoint_sha256) if support else h.vocab.live_mask([50] * h.vocab.N)
        report = h.run(sink, predict, journal, mask=mask,
                       levels=(.5,) * h.vocab.N, cal=None, duration=args.seconds,
                       stop_requested=lambda: False, range_guard=timings.wrap("range_guard", in_range),
                       feed_reader=timings.wrap("feed_reader", is_killfeed))
        # run() deliberately does not join a potentially stuck inference worker.
        # Offline we must finish it before collecting or unpatching timing hooks.
        for thread in threading.enumerate():
            if thread.name.endswith("(_run)"):
                thread.join(5)
                if thread.is_alive():
                    raise RuntimeError("offline inference did not finish")
        if "vgamepad" in sys.modules or "dxcam" in sys.modules:
            raise RuntimeError("offline profile imported a hardware dependency")
        return {"manifest": manifest, "warmup_ms": warmup, "isolated_ms": isolated,
                "replay_ms": timings.report(), "loop": report,
                "unmeasured": ["desktop capture", "actual guarded actuator and USB delivery",
                               "game contention", "native 1440p image distribution"] + ([] if recipe else ["trained weights"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("legacy", "I", "H", "W", "h1", "siglip", "nitrogen"), required=True)
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--inprocess", action="store_true")
    parser.add_argument("--compact-bgr", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--weights-dir", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="exact legacy/CM3 artifact; no seeded weights")
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--support-json", type=Path, help="that run's checkpoint-pinned train support")
    parser.add_argument("--artifact-manifest", type=Path)
    parser.add_argument("--dino-assets", type=Path)
    parser.add_argument("--dino-config-sha256")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--seconds", type=float, default=4.)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if any((args.checkpoint, args.checkpoint_sha256, args.support_json)):
        if not all((args.checkpoint, args.checkpoint_sha256, args.support_json)):
            parser.error("checkpoint, checkpoint-sha256 and support-json are required together")
        if args.arm not in ("legacy", "I", "A", "H", "W"):
            parser.error("explicit checkpoint uses the existing legacy/CM3 loader only")
    if args.device == "cuda" and not args.optimized:
        parser.error("CUDA requires the explicit optimized predictor")
    if args.compact_bgr and not args.inprocess:
        parser.error("compact-bgr requires inprocess")
    if not 1 <= args.samples <= 100 or not 0 < args.seconds <= 15:
        parser.error("bounded probe: samples 1..100 and seconds (0,15]")
    args.output.mkdir(parents=True, exist_ok=False)
    guard = PCGuard(args.output)
    from scripts import job_status
    job = "live-loop-profile-" + args.arm.lower()
    job_status.write(job, owner="live-loop", host="pc", stage="running",
                     started=int(time.time()), evidence=str(args.output.resolve()))
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    try:
        result = profile(args)
        guard.check()
        result["peak_working_set_bytes"] = guard.peak
        (args.output / "profile.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        job_status.write(job, stage="done", progress="offline profile saved")
        print(json.dumps({"output": str(args.output), "stop": result["loop"]["stop_reason"],
                          "peak_rss_bytes": guard.peak}))
    except BaseException:
        job_status.write(job, stage="failed", progress="see process output or ABORT.json")
        raise
    finally:
        guard.close()


if __name__ == "__main__":
    main()
