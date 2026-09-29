"""Offline retained-frame timings. Never constructs capture, pad or LiveSafety."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent import camera_compat as C
from agent.loop import default_perception


def percentile(rows, fraction):
    values = sorted(rows)
    return values[round((len(values) - 1) * fraction)]


def measure(frame, percept, module=C):
    durations, samples = [], []
    for _ in range(50):
        stamp = [None]
        def next_frame():
            stamp[0] = time.perf_counter()
            return frame.copy(), stamp[0]
        io = SimpleNamespace(now=time.perf_counter, next=next_frame)
        guard = lambda f: not percept.idle(f) and percept.in_range(f)
        check = module.CompatibilityCheck(io, percept, guard, None, time.perf_counter() + 10)
        started = time.perf_counter()
        reason = "observed"
        try:
            obs = check.observe()
            # Same identity matching used before a pulse, without any input.
            if obs[2]:
                check.target(obs, obs[2][0].track)
        except module.CompatStop as e:
            reason = str(e)
        durations.append((time.perf_counter() - started) * 1000)
        samples.append({"elapsed_ms": durations[-1], "result": reason,
                        "observation": getattr(check, "observation", {})})
    return {"runs": 50, "p50_ms": percentile(durations, .5),
            "p95_ms": percentile(durations, .95), "max_ms": max(durations), "samples": samples}


if __name__ == "__main__":
    source = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data/calibration/alt-cam-20260929b/yaw-01/ready-attach.png"
    frame = cv2.imread(str(source))
    assert frame.shape == (1440, 2560, 3)
    percept = default_perception()
    spec = importlib.util.spec_from_file_location("agent.compat_before", Path(__file__).parent / "before/camera_compat.py")
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    output = {"source": str(source),
              "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "opencv_threads": cv2.getNumThreads(),
              "scope": "retained-frame copy + native pixel guards + finder + tracker + identity match; no dxcam acquisition or disk decode in timed section",
              "baseline_v2": measure(frame, percept, baseline),
              "native_v3": measure(frame, percept)}
    output["warmup"] = C.warm_perception(percept)
    output["warmed_v3"] = measure(frame, percept)
    Path(sys.argv[1]).write_text(json.dumps(output, indent=2) + "\n")
    print({label: {k: v for k, v in output[label].items() if k != "samples"}
           for label in ("baseline_v2", "native_v3", "warmed_v3")})
