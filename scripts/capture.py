"""Grab game frames from the primary display on the PC.

Usage: uv run --no-project --with dxcam --with opencv-python --with pillow python capture.py [dxcam|gdi] [secs]
  Benchmarks the backend for `secs` (default 5), prints measured fps, and writes
  one frame to capture-<backend>.jpg next to this file.

Must run inside the interactive desktop session (an SSH session has no screen).
dxcam is the Desktop Duplication API; gdi is a plain GDI screen copy. Both are
ordinary OS screen capture. If one is blocked, use the other; nothing here hooks
the game.
"""
import sys
import time
from pathlib import Path

import numpy as np


class Capture:
    """grab() returns the latest full-screen BGR frame, or None if the screen has not changed (dxcam)."""

    def __init__(self, backend="dxcam"):
        self.backend = backend
        if backend == "dxcam":
            import dxcam
            self.cam = dxcam.create(output_color="BGR")
            if self.cam is None:
                raise RuntimeError("dxcam.create() returned None")
        elif backend == "gdi":
            from PIL import ImageGrab
            self._grab = ImageGrab.grab
        else:
            raise ValueError(backend)

    def grab(self):
        if self.backend == "dxcam":
            return self.cam.grab()
        return np.asarray(self._grab())[:, :, ::-1]  # RGB -> BGR


def open_capture():
    """dxcam if it delivers a non-black frame, else GDI."""
    try:
        cap = Capture("dxcam")
        deadline = time.time() + 2.0
        while time.time() < deadline:
            frame = cap.grab()
            if frame is not None and frame.mean() > 1.0:
                return cap
        print("capture: dxcam gave no usable frame, falling back to gdi")
    except Exception as e:  # noqa: BLE001 - any dxcam failure means use the fallback
        print(f"capture: dxcam unavailable ({e!r}), falling back to gdi")
    return Capture("gdi")


if __name__ == "__main__":
    import cv2

    backend = sys.argv[1] if len(sys.argv) > 1 else "dxcam"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    cap = Capture(backend)
    frames, polls, last = 0, 0, None
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < secs:
        frame = cap.grab()
        polls += 1
        if frame is not None:
            frames, last = frames + 1, frame
    dt = time.perf_counter() - t0
    assert last is not None, f"{backend}: no frames in {secs}s"
    out = Path(__file__).with_name(f"capture-{backend}.jpg")
    cv2.imwrite(str(out), last)
    print(f"{backend}: {frames} frames in {dt:.2f}s = {frames / dt:.1f} fps "
          f"({polls} polls), shape {last.shape}, mean {last.mean():.1f}, wrote {out}")
