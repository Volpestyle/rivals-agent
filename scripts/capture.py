"""Grab game frames from the primary display on the PC.

Usage: uv run --no-project --with dxcam --with opencv-python --with pillow python capture.py [dxcam|gdi] [secs]
       ... python capture.py preflight      # non-zero exit, loudly, when Desktop Duplication delivers no frames in 1 s
       ... python capture.py preflight --min-fps 60 --attempts 3  # bounded learned/RL launch-rate check
  Benchmarks the backend for `secs` (default 5), prints measured fps, and writes
  one frame to capture-<backend>.jpg next to this file.

Must run inside the interactive desktop session (an SSH session has no screen).
dxcam is the Desktop Duplication API; gdi is a plain GDI screen copy. Both are
ordinary OS screen capture. If one is blocked, use the other; nothing here hooks
the game.
"""
import math
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


NO_FRAMES = """capture preflight FAILED: dxcam (Desktop Duplication) delivered 0 frames in {secs:.0f} s ({calls} grabs).
Seen 2026-09-20 23:08: the monitor dropped off DisplayPort (display idle-off or switched off at the panel), Windows kept
the 2560x1440 desktop, GDI kept working, and AcquireNextFrame timed out for ever. Check on the PC:
  Get-PnpDevice -Class Monitor | Where-Object Present     # empty = no monitor attached: wake the display / switch the monitor on
Do not start a run: the loop and the menu tools would have no fresh frames."""


def frames_in(secs=1.0, cam=None, clock=time.perf_counter):
    """(frames, grabs) a dxcam camera delivers in `secs`. 0 frames on a live game means Desktop Duplication is dead."""
    cam = cam or Capture("dxcam")
    frames = calls = 0
    t0 = clock()
    while clock() - t0 < secs:
        calls += 1
        frames += cam.grab() is not None
    return frames, calls


def preflight(secs=1.0, cam=None, clock=time.perf_counter, *, min_fps=0., attempts=1,
              retry_s=.5, sleep=time.sleep):
    """Optional launch-rate gate; three bounded measurement windows at most.

    This reads pixels only. A passing count does not relax live frame-age checks.
    Caller-supplied cameras stay caller-owned; our own duplicator is released.
    """
    if (not math.isfinite(secs) or secs <= 0 or not math.isfinite(min_fps) or min_fps < 0
            or type(attempts) is not int or not 1 <= attempts <= 3
            or not math.isfinite(retry_s) or not 0 <= retry_s <= 1):
        raise ValueError('positive seconds, nonnegative min_fps, 1-3 attempts, retry_s in [0,1] required')
    owned = cam is None
    cam = Capture('dxcam') if owned else cam
    try:
        for attempt in range(1, attempts + 1):
            started = clock()
            frames, calls = frames_in(secs, cam, clock)
            elapsed = clock() - started
            fps = frames / elapsed if elapsed > 0 else 0.
            if frames and fps >= min_fps:
                print(f'capture preflight ok: {frames} dxcam frames in {elapsed:.3f} s '
                      f'({fps:.1f} fps, attempt {attempt}/{attempts})')
                return frames
            print(f'capture preflight not ready: {frames} frames / {elapsed:.3f} s '
                  f'= {fps:.1f} fps, need {min_fps:g}; attempt {attempt}/{attempts}')
            if attempt < attempts:
                sleep(retry_s)
        if frames == 0:
            raise SystemExit(NO_FRAMES.format(secs=elapsed, calls=calls))
        raise SystemExit(f'capture preflight FAILED: {fps:.1f} fps < {min_fps:g} '
                         f'after {attempts} attempts; do not start a run')
    finally:
        if owned and cam.backend == 'dxcam':
            cam.cam.release()


if __name__ == "__main__":
    import cv2

    if sys.argv[1:2] == ["preflight"]:
        import argparse
        ap = argparse.ArgumentParser(description='Read-only dxcam launch preflight')
        ap.add_argument('--min-fps', type=float, default=0.)
        ap.add_argument('--attempts', type=int, default=1)
        args = ap.parse_args(sys.argv[2:])
        preflight(min_fps=args.min_fps, attempts=args.attempts)
        sys.exit(0)
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
