"""Step through the game's own menus on the pad, one verified screen at a time.

Usage (PC desktop session): l4_menu.py STAGE TOKENS [STAGE TOKENS ...]
  python scripts/l4_menu.py range "START"                                  # open the pause menu from the range
  python scripts/l4_menu.py shot.jpg:0,0,400,80 "ls:0,-1,0.3 A"            # act only while that region still matches
  python scripts/l4_menu.py range "START" pause.jpg:500,110,780,320 "A"    # stages chain; each has its own check
Always saves the resulting screen to data/l4/menu.jpg (and menu-<n>.jpg history).

Menus hide the range HUD, so the HUD guard cannot cover them. Instead every token is
sent only if a fresh frame still matches, inside the given region (1280x720 px), the
screenshot a person/agent has already looked at. X is never sent (START on the lobby),
and START is only sent from the range itself.
"""
import argparse
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from capture import Capture  # noqa: E402
from record import in_range  # noqa: E402

OUT = ROOT / "data" / "l4"
TAPS = {"A", "B", "Y", "LB", "RB", "UP", "DOWN", "LEFT", "RIGHT", "START"}


def small(frame):
    return cv2.cvtColor(cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)


def find_cursor(frame):
    """Centre (x, y) in 1280x720 px of the pad cursor (a crisp white ring, r ~ 26 px), or None."""
    g = cv2.cvtColor(cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    # parameters swept on five saved menu screenshots with known cursor positions: 5/5 within 6 px
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=200, param1=40, param2=26, minRadius=20, maxRadius=32)
    return None if c is None else (float(c[0][0][0]), float(c[0][0][1]))


def main():
    args = sys.argv[1:]
    assert args and len(args) % 2 == 0, __doc__
    stages = []  # (check(frame_small_or_raw) -> bool, tokens)
    for spec, toks in zip(args[::2], args[1::2]):
        tokens = toks.split()
        assert "X" not in tokens, "X is never sent from the menu tool"
        assert spec == "range" or "START" not in tokens, "START only from the range"
        if spec == "range":
            stages.append((in_range, tokens))
        else:
            img, box = spec.rsplit(":", 1)
            x0, y0, x1, y1 = (int(v) for v in box.split(","))
            ref = small(cv2.imread(img))[y0:y1, x0:x1]
            stages.append((lambda f, ref=ref, x0=x0, y0=y0, x1=x1, y1=y1:
                           float(np.abs(small(f)[y0:y1, x0:x1] - ref).mean()) < 10.0, tokens))

    cap = Capture("dxcam")

    def fresh():
        f, t = None, time.perf_counter()
        while f is None and time.perf_counter() - t < 0.5:
            f = cap.grab()
        return f

    first = None
    while first is None:
        first = cap.grab()
    last = first
    OUT.mkdir(parents=True, exist_ok=True)
    if not stages[0][0](first):
        cv2.imwrite(str(OUT / "menu.jpg"), cv2.resize(first, (1280, 720)))
        raise SystemExit("menu: screen does not match what was expected; no pad opened, nothing sent")

    import vgamepad as vg
    b = vg.XUSB_BUTTON
    codes = {"A": b.XUSB_GAMEPAD_A, "B": b.XUSB_GAMEPAD_B, "Y": b.XUSB_GAMEPAD_Y, "START": b.XUSB_GAMEPAD_START,
             "LB": b.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER,
             "UP": b.XUSB_GAMEPAD_DPAD_UP, "DOWN": b.XUSB_GAMEPAD_DPAD_DOWN,
             "LEFT": b.XUSB_GAMEPAD_DPAD_LEFT, "RIGHT": b.XUSB_GAMEPAD_DPAD_RIGHT}
    pad = vg.VX360Gamepad()
    time.sleep(3.0)
    def send(tok):
        if tok in TAPS:
            pad.press_button(button=codes[tok]); pad.update(); time.sleep(0.12)
            pad.release_button(button=codes[tok]); pad.update(); time.sleep(0.5)
        elif tok.startswith("hold:"):  # hold:A,2.0 (slider auto-repeat)
            name, secs = tok[5:].split(",")
            assert name in ("A", "LEFT", "RIGHT"), name
            pad.press_button(button=codes[name]); pad.update(); time.sleep(float(secs))
            pad.release_button(button=codes[name]); pad.update(); time.sleep(0.5)
        elif tok in ("LT", "RT"):  # sub-tab switch in Settings
            trig = pad.left_trigger_float if tok == "LT" else pad.right_trigger_float
            trig(1.0); pad.update(); time.sleep(0.12)
            trig(0.0); pad.update(); time.sleep(0.5)
        elif tok.startswith(("ls:", "rs:")):  # ls = cursor, rs = scroll
            x, y, secs = (float(v) for v in tok[3:].split(","))
            stick = pad.left_joystick_float if tok[0] == "l" else pad.right_joystick_float
            stick(x, y); pad.update(); time.sleep(secs)
            stick(0.0, 0.0); pad.update(); time.sleep(0.3)
        elif tok.startswith("goto:"):  # closed loop: step the cursor ring to x,y (1280x720 px), one axis at a time
            tx, ty = (float(v) for v in tok[5:].split(","))
            misses = 0
            for _ in range(30):
                f = fresh()
                pos = find_cursor(f if f is not None else last)
                if pos is None:  # the ring is lost over busy widgets: jiggle it onto plainer ground and look again
                    misses += 1
                    if misses > 4:
                        raise SystemExit("menu: cursor ring not found; stopping")
                    pad.left_joystick_float(-1.0 if misses % 2 else 0.0, 0.0 if misses % 2 else 1.0); pad.update(); time.sleep(0.12)
                    pad.left_joystick_float(0.0, 0.0); pad.update(); time.sleep(0.25)
                    continue
                dx, dy = tx - pos[0], ty - pos[1]
                if abs(dx) <= 9 and abs(dy) <= 9:
                    break
                if abs(dx) > 9:
                    x, y, d = math.copysign(1.0, dx), 0.0, abs(dx)
                else:
                    x, y, d = 0.0, -math.copysign(1.0, dy), abs(dy)  # stick up = screen up
                pad.left_joystick_float(x, y); pad.update(); time.sleep(min(0.5, 0.035 + 0.8 * d / 560))
                pad.left_joystick_float(0.0, 0.0); pad.update(); time.sleep(0.25)
            else:
                raise SystemExit("menu: cursor did not converge; stopping")
            print(f"menu: cursor at {pos[0]:.0f},{pos[1]:.0f}")
        elif tok.startswith("w:"):
            time.sleep(float(tok[2:]))
        else:
            raise SystemExit(f"menu: unknown token {tok}")
    sent, stopped = 0, False
    for check, tokens in stages:
        for tok in tokens:
            f = fresh()
            last = last if f is None else f  # static menu: no new frame = unchanged since the last check
            if not check(last):
                print(f"menu: STOP before '{tok}': screen does not match this stage ({sent} tokens sent)")
                stopped = True
                break
            send(tok)
            sent += 1
        if stopped:
            break
    time.sleep(0.8)
    f = fresh()
    last = last if f is None else f
    n = len(list(OUT.glob("menu-*.jpg")))
    img = cv2.resize(last, (1280, 720), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(OUT / "menu.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(str(OUT / f"menu-{n:03d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"menu: sent {sent} tokens, saved menu-{n:03d}.jpg")


if __name__ == "__main__":
    main()
