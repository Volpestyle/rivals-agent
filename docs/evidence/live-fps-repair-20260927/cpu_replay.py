"""Fixed authorized sitting PNGs only; CPU, no desktop, video or corpus reads."""
import builtins
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
from scripts.profile_range_bc_live import PCGuard
from scripts import job_status


def main():
    guard = PCGuard(OUT)
    status = dict(root=OUT, owner="live-fps", host="pc", evidence=str(OUT), started=int(time.time()))
    job_status.write("fps-cpu-replay", stage="running", **status)
    def deadline():
        (OUT / "cpu-replay-timeout.json").write_text('{"deadline_seconds": 60}')
        os._exit(4)
    timer = threading.Timer(60, deadline)
    timer.daemon = True
    timer.start()
    original_import = builtins.__import__
    def passive(name, globals=None, locals=None, fromlist=(), level=0):
        if name in ("dxcam", "vgamepad", "pad", "agent.loop", "scripts.run_range_bc_live"):
            raise AssertionError(f"Forbidden import {name}")
        if set(fromlist or ()) & {"Live", "Pad"}:
            raise AssertionError("Forbidden actuator class")
        return original_import(name, globals, locals, fromlist, level)
    builtins.__import__ = passive
    predictor = worker = None
    try:
        import cv2
        import torch
        cv2.setNumThreads(2)
        def no_cuda(*args, **kwargs):
            raise AssertionError("CUDA forbidden in CPU replay")
        torch.cuda._lazy_init = no_cuda
        from scripts import measure_inference_fps as fps
        from scripts.record import in_range, idle_warning
        from policy.range_bc.live_inference import DevicePredictor
        source = ROOT / "data/calibration/alt-cam-20260927/inference-fps-aba-2"
        manifest = json.loads((source / "manifest.json").read_text())
        for key in ("settings", "support"):
            (OUT / f"replay-{key}.json").write_text(json.dumps(manifest[key], indent=2))
        args = fps.parser().parse_args([
            "--checkpoint", manifest["checkpoint"], "--checkpoint-sha256", manifest["checkpoint_sha256"],
            "--settings-json", str(OUT / "replay-settings.json"),
            "--support-json", str(OUT / "replay-support.json"), "--output", str(OUT / "unused")])
        model, backbone, preprocess, prepared = fps.prepare(args)
        predictor = DevicePredictor(model, preprocess, cooldowns="normal", backbone=backbone, device="cpu")
        worker = fps.DiscardWorker(predictor)
        observations = []
        for name in ("0000000-fps.png", "0000010-fps.png", "0000040-fps.png"):
            guard.check()
            path = source / "frames" / name
            frame = cv2.imread(str(path))
            assert frame.shape == (1440, 2560, 3)
            for repeat in range(2):
                t = time.perf_counter()
                range_ok = in_range(frame)
                range_s = time.perf_counter() - t
                t = time.perf_counter()
                idle = idle_warning(frame)
                idle_s = time.perf_counter() - t
                submitted = time.perf_counter()
                worker.submit(frame, submitted)
                result = None
                while result is None:
                    result = worker.poll()
                    time.sleep(.001)
                assert result["error"] is None, result
                observations.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    repeat=repeat, shape=list(frame.shape), range_ok=bool(range_ok), idle_warning=bool(idle),
                    range_s=range_s, idle_s=idle_s, prediction_s=result["finished"] - result["started"],
                    prediction_age_s=result["finished"] - result["captured"]))
            del frame
        guard.check()
        report = dict(device="cpu", cuda_used=False, desktop_opened=False, no_actuator=True,
                      checkpoint_sha256=manifest["checkpoint_sha256"], script_sha256=prepared["script_sha256"],
                      python=sys.executable, torch=torch.__version__, cpu_threads=2,
                      observations=observations, peak_rss_bytes=guard.peak,
                      limitation="Saved PNG replay excludes capture and game contention; cannot diagnose CUDA initialization")
        (OUT / "cpu-replay.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        job_status.write("fps-cpu-replay", root=OUT, stage="done", progress="6 CPU predictions; outputs discarded")
    except BaseException:
        job_status.write("fps-cpu-replay", root=OUT, stage="failed")
        raise
    finally:
        timer.cancel()
        stopped = worker.close() if worker is not None else True
        if predictor is not None and stopped:
            predictor.close()
        guard.close()


if __name__ == "__main__":
    main()
