"""Read the kill feed (perception.scoreboard.is_killfeed) on every saved frame of the two replayed recordings, and time each read.

  uv run --offline --no-project --with opencv-python-headless --with numpy python -B docs/evidence/option-status-20260923/feed.py

Writes feed-trial0.json and feed-plaza30.json next to this file: the source, its log's sha256, one digest over every frame read (each
file's sha256, in order), and per saved frame [t, file, read]. Frames are read in place and never copied or written. The timing is
is_killfeed alone on an already decoded frame, which is what the loop's decision worker adds per decision (Perception.killfeed).
"""
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from perception.scoreboard import is_killfeed  # noqa: E402

HERE = Path(__file__).resolve().parent
SOURCES = {
    # burst trial 0: docs/lanes/l4-controller.md, "Durations seen in burst trial 0"; 720p saved frames; the trial is t 0-4 s of the log
    "trial0": (Path(r"C:\rivals-agent\data\l4\burst"), "log.jsonl", 4.0),
    # plaza30: the brain-chosen bursts and two KOs (docs/lanes/l4-controller.md); native 2560x1440 saved frames
    "plaza30": (Path(r"C:\rivals-agent\data\l1\plaza30"), "frames.jsonl", None),
}


def main():
    for name, (run, log, until) in SOURCES.items():
        raw = (run / log).read_bytes()
        rows = [json.loads(line) for line in raw.decode().splitlines()]
        reads, ms, digest = [], [], sha256()
        is_killfeed(cv2.imread(str(run / next(r["file"] for r in rows if "file" in r))))   # first call: imports and warm-up, not timed
        for r in rows:
            if "file" not in r or (until is not None and r["t"] > until):
                continue
            data = (run / r["file"]).read_bytes()
            digest.update(sha256(data).digest())
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            c0 = time.perf_counter()
            read = is_killfeed(frame)
            ms.append((time.perf_counter() - c0) * 1000)
            reads.append([r["t"], r["file"], read])
        q = sorted(ms)
        out = {"source": str(run), "log": log, "log_sha256": sha256(raw).hexdigest(), "frames": len(reads),
               "frames_digest": digest.hexdigest(), "size": [frame.shape[1], frame.shape[0]],
               "read_ms": {"p50": round(statistics.median(q), 3), "p95": round(q[int(0.95 * len(q))], 3), "max": round(q[-1], 3)},
               "reads": reads}
        (HERE / f"feed-{name}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(name, out["frames"], "frames", out["size"], out["read_ms"])


if __name__ == "__main__":
    main()
