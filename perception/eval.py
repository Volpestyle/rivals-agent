"""Report mAP on the held-out split and per-frame latency for the fine-tuned detector.

Usage: uv run --no-project --with ultralytics python perception/eval.py <weights.pt> <dataset-dir> [--sheet out.jpg]

Latency is measured the way the agent will call it: one frame at a time through
detect.Detector, after warm-up. L3 is done when mAP50 is reported and latency is
under 10 ms on the 4080.
"""
import argparse
import time
from pathlib import Path

import cv2

from autolabel import contact_sheet, sheet_path
from detect import Detector, pick_device


EVAL_SHEET = "data/l3/eval-sheet.jpg"   # gitignored; the committed sheets under docs/evidence/l3/ are a record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights")
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--sheet", type=sheet_path, default=EVAL_SHEET)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--sheet-n", type=int, default=12)
    a = ap.parse_args()

    from ultralytics import YOLO
    device = pick_device()
    m = YOLO(a.weights).val(data=str((a.dataset / "data.yaml").resolve()), imgsz=a.imgsz,
                            device=device, project=str(Path("data/runs").resolve()),
                            name="eval", exist_ok=True).box
    print(f"eval: mAP50={m.map50:.3f} mAP50-95={m.map:.3f} P={m.mp:.3f} R={m.mr:.3f}")
    for i, name in enumerate(m.ap_class_index):
        print(f"eval:   class {name}: mAP50={m.ap50[i]:.3f}")

    det = Detector(a.weights, imgsz=a.imgsz)
    frames = sorted((a.dataset / "images" / "val").iterdir())
    imgs = [cv2.imread(str(p)) for p in frames]
    assert imgs, f"no val images under {a.dataset}"
    for img in imgs[:5]:  # warm-up: first calls pay for graph build and autocast setup
        det(img)
    times = []
    for img in imgs:
        t0 = time.perf_counter()
        det(img)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    print(f"eval: latency over {len(times)} frames on {device}: "
          f"median {times[len(times) // 2]:.1f} ms, p95 {times[round(len(times) * 0.95) - 1]:.1f} ms, max {times[-1]:.1f} ms")

    step = max(1, len(frames) // a.sheet_n)
    contact_sheet([(p, det(cv2.imread(str(p)))) for p in frames[::step][:a.sheet_n]], a.sheet)
    print(f"eval: sheet {a.sheet}")


if __name__ == "__main__":
    main()
