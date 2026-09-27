"""Prepare, or explicitly capture a guarded 120-second inference-cost A/B/A.

No input device is imported or constructed. Preparation loads/validates on CPU;
only --desktop-capture permits screen access or placement on explicit CUDA.
Game FPS is manually read from retained native overlay PNGs, never capture FPS.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import queue
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WARMUP_S, MEASURE_S = 10., 30.
PHASES = ("A1", "B", "A2")
FRESH_S, PREDICTION_LIMIT_S = .1, .25


def require(ok, message):
    if not ok:
        raise ValueError(message)


def percentiles(values):
    values = sorted(values)
    def at(q):
        if not values:
            return None
        position = (len(values) - 1) * q
        low = int(position)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)
    return {"count": len(values), "p10": at(.1), "p50": at(.5), "p95": at(.95), "p99": at(.99)}


class DiscardWorker:
    """One in-flight prediction; only timings/errors leave this daemon worker."""
    def __init__(self, predict, clock=time.perf_counter):
        self.predict, self.clock = predict, clock
        self.requests, self.results = queue.Queue(1), queue.Queue(1)
        self.stopping = threading.Event()
        self.busy = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="fps-inference")
        self.thread.start()

    def submit(self, frame, captured):
        require(not self.busy and not self.stopping.is_set(), "prediction already in flight or closed")
        self.busy = True
        # Capture may reuse its buffer. Copy only for B; this is inference input cost.
        self.requests.put_nowait((frame.copy(), captured))

    def _run(self):
        while not self.stopping.is_set():
            try:
                frame, captured = self.requests.get(timeout=.02)
            except queue.Empty:
                continue
            began, error = self.clock(), None
            try:
                self.predict(frame, None)  # unknown previous input; outputs deliberately discarded
            except BaseException as exc:
                error = f"{type(exc).__name__}: {exc}"
            self.results.put_nowait({"captured": captured, "started": began,
                                     "finished": self.clock(), "error": error})
            del frame

    def poll(self):
        try:
            value = self.results.get_nowait()
        except queue.Empty:
            return None
        self.busy = False
        return value

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=.05)
        return not self.thread.is_alive()


def run(capture, worker, journal, *, focused, key_pressed, in_range, idle_warning,
        memory, capture_hz=30., clock=time.perf_counter, sleep=time.sleep):
    """Fixed schedule, same capture/proof/1-Hz native evidence in every phase.

    Dependencies are injected for hardware-free tests. Slow external calls are
    detected on return; Python cannot cancel a blocked native capture/driver.
    Inference has a 250-ms age limit and cannot leak into the next interval.
    """
    require(math.isfinite(capture_hz) and 15 <= capture_hz <= 60, "capture Hz must be 15..60")
    started = clock()
    result = {"started": started, "phases": [], "stop_reason": "complete",
              "game_fps": "unmeasured: annotate native overlay samples", "samples": []}
    phase_length = WARMUP_S + MEASURE_S
    pending = None
    previous_shape = None
    last_fresh = started
    phase = interval = None
    next_capture = next_evidence = started
    stats = None

    def abort(reason):
        result["stop_reason"] = reason

    def external_stop():
        if key_pressed():
            return "keypress"
        if not focused():
            return "focus_lost"
        return None

    def finish_interval(now):
        if stats is None:
            return
        stats["stopped"] = now
        elapsed = now - stats["started"]
        stats["actual_seconds"] = elapsed
        stats["capture_hz"] = stats["captures"] / elapsed if elapsed else 0.
        stats["inference_hz"] = len(stats["prediction_age_s"]) / elapsed if elapsed else 0.
        stats["evidence_hz"] = stats["evidence_accepted"] / elapsed if elapsed else 0.
        for key in ("capture_duration_s", "proof_age_s", "prediction_age_s", "prediction_duration_s"):
            stats[key] = percentiles(stats[key])
        stats["memory_end"] = memory()
        journal.event(kind="interval_end", phase=phase, interval=interval, **stats)

    try:
        while True:
            now = clock()
            stop = external_stop()
            if stop:
                abort(stop)
                break
            if worker.busy:
                value = worker.poll()
                if value is not None:
                    age = value["finished"] - value["captured"]
                    stats["prediction_age_s"].append(age)
                    stats["prediction_duration_s"].append(value["finished"] - value["started"])
                    journal.event(kind="prediction", phase=phase, interval=interval, age_s=age, **value)
                    pending = None
                    if value["error"] or age > PREDICTION_LIMIT_S:
                        abort("prediction_error" if value["error"] else "prediction_age_exceeded")
                        break
                elif now - pending >= PREDICTION_LIMIT_S:
                    abort("prediction_timeout")
                    break
            elapsed = now - started
            if elapsed >= 3 * phase_length:
                break
            index = int(elapsed / phase_length)
            new_phase = PHASES[index]
            new_interval = "warmup" if elapsed - index * phase_length < WARMUP_S else "measured"
            boundary = started + index * phase_length + (WARMUP_S if new_interval == "warmup" else phase_length)
            if (new_phase, new_interval) != (phase, interval):
                if worker.busy:
                    abort("prediction_crossed_boundary")
                    break
                finish_interval(now)
                phase, interval = new_phase, new_interval
                stats = {"started": now, "scheduled_end": boundary, "captures": 0, "capture_attempts": 0,
                         "capture_missed_slots": 0, "no_frame": 0, "inference_started": 0,
                         "inference_busy_slots": 0, "evidence_requested": 0, "evidence_accepted": 0,
                         "capture_duration_s": [], "proof_age_s": [], "prediction_age_s": [],
                         "prediction_duration_s": [], "memory_start": memory()}
                result["phases"].append({"phase": phase, "interval": interval, "stats": stats})
                journal.event(kind="interval_start", phase=phase, interval=interval, at=now,
                              scheduled_end=boundary, memory=stats["memory_start"])
                next_capture = next_evidence = now
            # Reserve the same final freshness window in every interval. Do not
            # begin a native call that could contaminate the following interval.
            if now + FRESH_S >= boundary:
                sleep(min(.005, boundary - now))
                continue
            if now < next_capture:
                if now - last_fresh > FRESH_S:
                    abort("capture_stale")
                    break
                sleep(min(.005, next_capture - now, boundary - now))
                continue
            missed = max(0, int((now - next_capture) * capture_hz))
            stats["capture_missed_slots"] += missed
            next_capture += (missed + 1) / capture_hz
            captured = clock()  # freshness starts BEFORE acquisition
            frame = capture.grab()
            stats["capture_attempts"] += 1
            stats["capture_duration_s"].append(clock() - captured)
            stop = external_stop()
            if stop:
                abort(stop)
                break
            if frame is None:
                stats["no_frame"] += 1
                if clock() - last_fresh > FRESH_S:
                    abort("capture_stale")
                    break
                continue
            stats["captures"] += 1
            shape = tuple(frame.shape)
            if len(shape) != 3 or shape[2] != 3 or min(shape[:2]) < 360:
                abort("invalid_native_frame")
                break
            if previous_shape is not None and shape != previous_shape:
                abort("capture_geometry_changed")
                break
            previous_shape = shape
            range_ok, idle = in_range(frame), idle_warning(frame)
            proof_age = clock() - captured
            stats["proof_age_s"].append(proof_age)
            journal.event(kind="capture", phase=phase, interval=interval, captured=captured,
                          proof_age_s=proof_age, range_ok=bool(range_ok), idle_warning=bool(idle), shape=shape)
            stop = external_stop()
            if stop or proof_age > FRESH_S or not range_ok or idle or clock() >= boundary:
                abort(stop or ("stale_proof" if proof_age > FRESH_S else "range_lost" if not range_ok
                               else "idle_warning" if idle else "capture_crossed_boundary"))
                break
            last_fresh = captured
            if captured >= next_evidence:
                next_evidence += (int(captured - next_evidence) + 1)
                sample = {"phase": phase, "interval": interval, "captured": captured,
                          "relative_s": captured - started, "path": "", "fps": ""}
                stats["evidence_requested"] += 1
                frame_index = journal.index
                if journal.frame(frame, captured, "fps"):
                    sample["path"] = f"frames/{frame_index:07d}-fps.png"
                    stats["evidence_accepted"] += 1
                result["samples"].append(sample)
                journal.event(kind="fps_sample", **sample)
            # No catch-up inference, no reused frame, no inference across boundaries.
            if phase == "B" and clock() + PREDICTION_LIMIT_S < boundary:
                if worker.busy:
                    stats["inference_busy_slots"] += 1
                elif clock() - captured <= FRESH_S:
                    worker.submit(frame, captured)
                    pending = captured
                    stats["inference_started"] += 1
    except KeyboardInterrupt:
        abort("keyboard_interrupt")
    except Exception as exc:
        abort("runtime_error")
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["stopped"] = clock()
        result["elapsed_s"] = result["stopped"] - started
        result["inference_worker_stopped"] = worker.close()
        finish_interval(result["stopped"])
        result["evidence"] = journal.finish_frames()
        if result["stop_reason"] == "complete" and not result["evidence"]["drain_complete"]:
            abort("evidence_incomplete")
        journal.write("result.json", result)
        journal.close()
    return result


def desktop_guards(pid):
    """Read-only Win32 foreground/keyboard polling; never changes focus."""
    import ctypes
    from ctypes import wintypes
    require(type(pid) is int and 0 < pid <= 0xffffffff, "explicit foreground game PID required")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    def focused():
        current = wintypes.DWORD()
        window = user32.GetForegroundWindow()
        return bool(window and user32.GetWindowThreadProcessId(window, ctypes.byref(current)) and current.value == pid)
    def key_pressed():
        states = [user32.GetAsyncKeyState(vk) for vk in range(8, 255) if not 0xC3 <= vk <= 0xDA]
        return any(value & 0x8001 for value in states)
    return focused, key_pressed


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--checkpoint-sha256", required=True)
    p.add_argument("--support-json", type=Path, required=True)
    p.add_argument("--settings-json", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--preprocessor", choices=("compact-bgr",), default="compact-bgr")
    p.add_argument("--cpu-threads", type=int, choices=(2,), default=2)
    p.add_argument("--capture-hz", type=float, default=30.)
    p.add_argument("--desktop-capture", action="store_true")
    p.add_argument("--game-pid", type=int)
    p.add_argument("--sitting")
    p.add_argument("--native-video", help="operator's native OBS recording reference; not opened")
    p.add_argument("--fps-cap", type=float, help="configured game FPS cap, if any")
    p.add_argument("--dino-assets", type=Path)
    p.add_argument("--dino-config-sha256")
    t = p.add_mutually_exclusive_group()
    t.add_argument("--threshold", type=float, default=.5)
    t.add_argument("--thresholds-json", type=Path)
    return p


def prepare(a):
    """Existing exact-byte CM3/legacy contracts; no capture, forward pass or CUDA."""
    from agent import live_range_bc as harness
    from policy.range_bc import vocab
    import torch
    def read(path):
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()
    settings, settings_hash = read(a.settings_json)
    support, support_hash = read(a.support_json)
    require(settings.get("cooldowns") == "normal", "FPS sitting requires normal cooldowns")
    # Capture/inference does not consume a camera map. Validate the settings
    # header without inventing maps or creating a pre-booking calibration cycle.
    harness.calibration(settings, camera_disabled=True)
    mask = harness.support_mask(support, a.checkpoint_sha256)
    require(support.get("swing_mode") == settings["swing_mode"], "support/settings swing mismatch")
    decoder, decoder_hash = read(a.thresholds_json) if a.thresholds_json else (a.threshold, None)
    levels = harness.thresholds(decoder, a.checkpoint_sha256)
    torch.set_num_threads(a.cpu_threads)
    model, metadata = harness.load_checkpoint(a.checkpoint, a.checkpoint_sha256)
    distribution = harness.validate_distribution(metadata, settings["cooldowns"])
    from policy.range_bc.live_inference import InProcessCachePreprocessor
    preprocess = InProcessCachePreprocessor(compact_bgr=True)
    backbone = None
    if getattr(model.config, "arm", "I") in ("H", "W"):
        require(a.dino_assets is not None and a.dino_config_sha256, "local pinned DINO assets required")
        from policy.range_bc.cm3_features import FrozenDino
        backbone = FrozenDino(a.dino_assets, config_sha256=a.dino_config_sha256).cpu()
    manifest = {"format": "range-bc-inference-fps-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "checkpoint": str(a.checkpoint.resolve()), "checkpoint_sha256": a.checkpoint_sha256,
                "checkpoint_metadata": metadata, "distribution": distribution, "settings": settings,
                "no_actuator": True, "calibration_status": "execution_maps_not_validated_or_consumed",
                "support": support, "live_mask": list(mask), "thresholds": dict(zip(vocab.NAMES, levels)),
                "input_sha256": {"settings": settings_hash, "support": support_hash, "decoder": decoder_hash},
                "device": a.device, "preparation_device": "cpu", "cpu_threads": a.cpu_threads,
                "preprocessor": a.preprocessor, "cache_graph": preprocess.graph, "libraries": preprocess.version,
                "dino": backbone.asset_receipt if backbone is not None else None,
                "torch": torch.__version__, "python": sys.version, "platform": platform.platform(),
                "script_sha256": harness.sha256(Path(__file__)),
                "runtime_sha256": {name: harness.sha256(ROOT / name) for name in (
                    "agent/live_range_bc.py", "policy/range_bc/live_inference.py", "scripts/capture.py",
                    "scripts/record.py", "agent/controller.py", "policy/range_bc/vocab.py")},
                "desktop_capture": a.desktop_capture, "game_pid": a.game_pid, "sitting": a.sitting,
                "native_video": a.native_video, "fps_cap": a.fps_cap,
                "phases": PHASES, "warmup_s": WARMUP_S, "measured_s": MEASURE_S,
                "capture_hz": a.capture_hz, "evidence_hz": 1., "prediction_age_limit_s": PREDICTION_LIMIT_S,
                "comparison": "active-inference cost; model resident throughout; no game-only reference",
                "history": "unknown previous input on every prediction; recurrent state retained in B",
                "decoder": "pinned for identity only; outputs discarded without decoding",
                "fixed_conditions": "operator holds pose, resolution, graphics, cap, OBS and other workloads constant"}
    return model, backbone, preprocess, manifest


def memory_snapshot(device):
    """Own-process memory only; never reads the game process."""
    import tracemalloc
    current, peak = tracemalloc.get_traced_memory()
    value = {"python_traced_bytes": current, "python_peak_bytes": peak, "process_working_set_bytes": None,
             "cuda_allocated_bytes": None, "cuda_reserved_bytes": None, "cuda_peak_allocated_bytes": None}
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("peak_ws", "ws", "peak_pool", "pool", "peak_nonpaged",
                                                    "nonpaged", "pagefile", "peak_pagefile")]
        kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            value["process_working_set_bytes"] = counters.ws
    if device == "cuda":
        import torch
        value.update(cuda_allocated_bytes=torch.cuda.memory_allocated(),
                     cuda_reserved_bytes=torch.cuda.memory_reserved(),
                     cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated())
    return value


def annotate(directory, annotations):
    """Offline manual FPS summary; bind row identity to retained run evidence."""
    def read(name):
        return json.loads((directory / name).read_text(encoding="utf-8"))
    result, manifest = read("result.json"), read("manifest.json")
    require(result.get("stop_reason") == "complete", "incomplete A/B/A cannot yield paired FPS cost")
    originals = result["samples"]
    with annotations.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == len(originals), "annotation row count changed")
    written = {row["path"] for row in (json.loads(line) for line in
               (directory / "frames.jsonl").read_text(encoding="utf-8").splitlines())}
    samples = {phase: [] for phase in PHASES}
    for row, original in zip(rows, originals):
        require(set(row) == set(original), "annotation columns changed")
        require(all(row[key] == str(original[key]) for key in original if key != "fps"),
                "annotation sample identity changed")
        if not row["fps"].strip():
            continue
        value = float(row["fps"])
        require(math.isfinite(value) and value > 0, "FPS must be finite and positive or blank/unknown")
        require(row["path"] in written and (directory / row["path"]).is_file(),
                "FPS annotation lacks retained native evidence")
        if row["interval"] == "measured":
            samples[row["phase"]].append(value)
    cap = manifest.get("fps_cap")
    report = {"metric": "visible game FPS samples; not frame times or 1% lows", "phases": {},
              "annotations_sha256": hashlib.sha256(annotations.read_bytes()).hexdigest(),
              "cap": cap, "limitation": "cap saturation conceals unused rendering headroom"}
    for phase in PHASES:
        require(samples[phase], f"no measured FPS samples for {phase}")
        duration = next(p["stats"]["actual_seconds"] for p in result["phases"]
                        if p["phase"] == phase and p["interval"] == "measured")
        report["phases"][phase] = {**percentiles(samples[phase]), "sample_hz": len(samples[phase]) / duration,
                                   "cap_saturation_fraction": sum(v >= .99 * cap for v in samples[phase]) /
                                   len(samples[phase]) if cap else None}
    a1, b, a2 = (report["phases"][p]["p50"] for p in PHASES)
    reference = (a1 + a2) / 2
    report.update(paired_loss_percent=100 * (reference - b) / reference,
                  a1_a2_drift_fps=a2 - a1, a1_a2_drift_percent=100 * (a2 - a1) / a1)
    with (directory / "annotated-fps.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    return report


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "annotate":
        p = argparse.ArgumentParser(description="Summarize a copy of the manually filled FPS CSV, offline.")
        p.add_argument("directory", type=Path)
        p.add_argument("annotations", type=Path)
        a = p.parse_args(argv[1:])
        print(json.dumps(annotate(a.directory, a.annotations), indent=2))
        return 0
    a = parser().parse_args(argv)
    require(not a.output.exists(), "output must be a new directory")
    require(math.isfinite(a.capture_hz) and 15 <= a.capture_hz <= 60, "capture Hz must be 15..60")
    require(a.fps_cap is None or math.isfinite(a.fps_cap) and a.fps_cap > 0, "invalid FPS cap")
    if a.desktop_capture:
        require(sys.platform == "win32", "desktop capture requires Windows")
        require(a.game_pid is not None and 0 < a.game_pid <= 0xffffffff, "explicit foreground game PID required")
        require(a.sitting and a.native_video, "sitting and native OBS video reference required")
    model, backbone, preprocess, manifest = prepare(a)
    from agent import live_range_bc as harness
    journal = harness.Journal(a.output, manifest)
    if not a.desktop_capture:
        preprocess.close()
        journal.write("result.json", {"stop_reason": "prepared_only", "desktop_opened": False,
                                      "inference_ran": False, "cuda_used": False})
        journal.close()
        return 0
    predictor = cap = worker = None
    try:
        import tracemalloc
        tracemalloc.start()
        from policy.range_bc.live_inference import DevicePredictor
        predictor = DevicePredictor(model, preprocess, cooldowns="normal", backbone=backbone, device=a.device)
        focused, keys = desktop_guards(a.game_pid)
        keys()  # clear historical tap bits; held keys still fail the next poll
        require(focused() and not keys(), "foreground/keyboard preflight refused")
        from capture import Capture
        from record import in_range, idle_warning
        cap = Capture("dxcam")
        worker = DiscardWorker(predictor)
        journal.event(kind="ready", monotonic=time.perf_counter(), utc=datetime.now(timezone.utc).isoformat(),
                      resident_memory=memory_snapshot(a.device))
        result = run(cap, worker, journal, focused=focused, key_pressed=keys,
                     in_range=in_range, idle_warning=idle_warning, memory=lambda: memory_snapshot(a.device),
                     capture_hz=a.capture_hz)
        with (a.output / "fps-annotations.csv").open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("phase", "interval", "captured", "relative_s", "path", "fps"))
            writer.writeheader()
            writer.writerows(result["samples"])
        return 0 if result["stop_reason"] == "complete" else 1
    except BaseException as exc:
        if not journal.stream.closed:
            journal.write("result.json", {"stop_reason": "startup_error", "error": f"{type(exc).__name__}: {exc}"})
            journal.close()
        raise
    finally:
        stopped = worker.close() if worker is not None else True
        if stopped:
            if predictor is not None:
                predictor.close()
            else:
                preprocess.close()
        if cap is not None:
            cap.cam.release()


if __name__ == "__main__":
    raise SystemExit(main())
