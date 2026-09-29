"""One fresh-process observation, optionally pre-warmed; no game IO."""
import json
import sys
from pathlib import Path

import cv2
from measure_observe import C, default_perception, measure

frame = cv2.imread("D:/rivals-offline/live-loop-compat-20260929-v3/frame-09.png")
percept = default_perception()
warmup = C.warm_perception(percept) if sys.argv[1] == "warm" else None
result = measure(frame, percept)
Path(sys.argv[2]).write_text(json.dumps({"mode": sys.argv[1], "warmup": warmup,
    "first": result["samples"][0], "p50_ms": result["p50_ms"], "p95_ms": result["p95_ms"]}, indent=2) + "\n")
