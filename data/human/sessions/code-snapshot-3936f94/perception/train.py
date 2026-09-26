"""Fine-tune a small YOLO on the auto-labelled range frames.

Usage: uv run --no-project --with ultralytics python perception/train.py <dataset-dir> [--epochs N] [--model yolo11s.pt]

Writes to data/runs/<name>/; the weights the agent loads are
data/runs/<name>/weights/best.pt. Detection stays at 1280 imgsz: a bot across
the range is ~60 px tall in a 2560-wide frame and vanishes at 640.
"""
import argparse
from pathlib import Path

from detect import pick_device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("--model", default="yolo11s.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--batch", type=int, default=-1, help="-1 = auto by VRAM (CUDA only); set explicitly on MPS")
    ap.add_argument("--name", default="range")
    a = ap.parse_args()

    from ultralytics import YOLO
    device = pick_device()
    r = YOLO(a.model).train(
        data=str((a.dataset / "data.yaml").resolve()),
        epochs=a.epochs, imgsz=a.imgsz, batch=a.batch if device == 0 else max(a.batch, 2),
        # absolute: a relative project is resolved against ultralytics' own runs_dir setting
        device=device, project=str(Path("data/runs").resolve()), name=a.name, exist_ok=True,
        # the range is one fixed arena: flips and scale help, colour/mosaic chaos does not
        hsv_h=0.0, hsv_s=0.3, hsv_v=0.3, degrees=0.0, fliplr=0.5, mosaic=0.3,
        workers=4, patience=20, plots=True,
    )
    print(f"train: device={device} weights={Path(r.save_dir) / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
