"""One explicitly authorized saved-PNG qualification; no capture/input/training.

Reuses the production warmup and worker, then checks the 250-ms deadline after
40 seconds without inference (A1's duration). Hard job cap: 120 seconds total.
"""
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


class Journal:
    def __init__(self):
        self.stream = (OUT / "cuda-replay-events.jsonl").open("x")

    def event(self, **row):
        self.stream.write(json.dumps(row) + "\n")
        self.stream.flush()

    def write(self, name, value):
        with (OUT / ("cuda-" + name)).open("x") as stream:
            json.dump(value, stream, indent=2)


def main():
    guard = PCGuard(OUT)
    def deadline():
        (OUT / "cuda-replay-timeout.json").write_text('{"deadline_seconds": 120}')
        os._exit(4)
    timer = threading.Timer(120, deadline)
    timer.daemon = True
    timer.start()
    job_status.write("fps-cuda-replay", root=OUT, owner="live-fps", host="pc", stage="running",
                     started=int(time.time()), evidence=str(OUT / "cuda-replay.json"))
    original_import = builtins.__import__
    def passive(name, globals=None, locals=None, fromlist=(), level=0):
        assert name not in ("dxcam", "vgamepad", "pad", "agent.loop", "scripts.run_range_bc_live"), name
        assert not set(fromlist or ()) & {"Live", "Pad"}
        return original_import(name, globals, locals, fromlist, level)
    builtins.__import__ = passive
    worker = predictor = journal = None
    try:
        import cv2
        import torch
        from scripts import measure_inference_fps as fps
        from scripts.record import in_range, idle_warning
        from policy.range_bc.live_inference import DevicePredictor
        cv2.setNumThreads(2)
        torch.set_num_threads(2)
        source = ROOT / "data/calibration/alt-cam-20260927/inference-fps-aba-2"
        manifest = json.loads((source / "manifest.json").read_text())
        frames, sources = [], []
        for name in ("0000000-fps.png", "0000010-fps.png", "0000040-fps.png"):
            path = source / "frames" / name
            frame = cv2.imread(str(path))
            assert frame.shape == (1440, 2560, 3)
            frames.append(frame)
            sources.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        args = fps.parser().parse_args([
            "--checkpoint", manifest["checkpoint"], "--checkpoint-sha256", manifest["checkpoint_sha256"],
            "--settings-json", str(OUT / "replay-settings.json"), "--support-json", str(OUT / "replay-support.json"),
            "--output", str(OUT / "unused-cuda"), "--device", "cuda"])
        model, backbone, preprocess, prepared = fps.prepare(args)
        guard.check()  # immediately before ANY CUDA availability/placement call
        predictor = DevicePredictor(model, preprocess, cooldowns="normal", backbone=backbone, device="cuda")
        device = dict(count=torch.cuda.device_count(), name=torch.cuda.get_device_name(), cuda=torch.version.cuda)
        worker = fps.DiscardWorker(predictor)
        journal = Journal()
        class SavedFrames:
            index = 0
            def grab(self):
                frame = frames[self.index % len(frames)]
                self.index += 1
                return frame
        capture = SavedFrames()
        startup = fps.warm_start(capture, worker, journal, focused=lambda: True, key_pressed=lambda: False,
                                 in_range=in_range, idle_warning=idle_warning,
                                 memory=lambda: fps.memory_snapshot("cuda"))
        report = dict(device=device, saved_frames=sources, checkpoint_sha256=manifest["checkpoint_sha256"],
                      script_sha256=prepared["script_sha256"], no_actuator=True, desktop_opened=False,
                      startup=startup, post_idle_predictions=[], steady_limit_s=fps.PREDICTION_LIMIT_S,
                      limitations="Offline saved PNGs, synthetic focus/keyboard; no capture or game-FPS claim")
        if startup["stop_reason"] == "ready":
            # A1-length inference idle, with the same saved-frame proof polling.
            idle_start = time.perf_counter()
            while time.perf_counter() - idle_start < 40:
                frame = capture.grab()
                assert in_range(frame) and not idle_warning(frame)
                time.sleep(1 / 30)
            report["inference_idle_s"] = time.perf_counter() - idle_start
            for _ in range(6):
                guard.check()
                captured = time.perf_counter()
                frame = capture.grab()
                assert in_range(frame) and not idle_warning(frame)
                worker.submit(frame, captured)
                value = None
                while value is None and time.perf_counter() - captured < fps.PREDICTION_LIMIT_S:
                    value = worker.poll()
                    if value is None:
                        time.sleep(.001)
                if value is None:
                    report["stop_reason"] = "prediction_timeout"
                    break
                value["age_s"] = value["finished"] - value["captured"]
                value["duration_s"] = value["finished"] - value["started"]
                report["post_idle_predictions"].append(value)
                if value["error"] or value["age_s"] > fps.PREDICTION_LIMIT_S:
                    report["stop_reason"] = "prediction_error_or_age_exceeded"
                    break
            else:
                report["stop_reason"] = "qualified_offline"
        else:
            report["stop_reason"] = "startup_" + startup["stop_reason"]
        guard.check()
        report.update(peak_rss_bytes=guard.peak, memory_end=fps.memory_snapshot("cuda"))
        with (OUT / "cuda-replay.json").open("x") as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps(report, indent=2))
        job_status.write("fps-cuda-replay", root=OUT,
                         stage="done" if report["stop_reason"] == "qualified_offline" else "failed")
        return int(report["stop_reason"] != "qualified_offline")
    finally:
        timer.cancel()
        stopped = worker.close() if worker is not None else True
        if predictor is not None and stopped:
            predictor.close()
        if journal is not None:
            journal.stream.close()
        guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
