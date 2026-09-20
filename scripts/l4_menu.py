"""Step through the game's own menus on the pad, one verified screen at a time.

Usage (PC desktop session): l4_menu.py STAGE TOKENS [STAGE TOKENS ...]
  python scripts/l4_menu.py range "START"                                  # open the pause menu from the range
  python scripts/l4_menu.py shot.jpg:0,0,400,80 "ls:0,-1,0.3 A"            # act only while that region still matches
  python scripts/l4_menu.py range "START" pause.jpg:500,110,780,320 "A"    # stages chain; each has its own check
Always saves the resulting screen to data/l4/menu.jpg (and menu-<n>.jpg history).

Tokens: A B Y LB RB UP DOWN LEFT RIGHT START (taps), LT RT (sub-tab), hold:A,2.0, ls:x,y,secs (cursor),
rs:x,y,secs (scroll), goto:x,y (closed-loop cursor move, 1280x720 px), w:secs.

Menus hide the range HUD, so the HUD guard cannot cover them. Instead every token is sent only if a fresh frame
still matches, inside the given region (1280x720 px), a screenshot a person/agent has already looked at. X is never
sent (START on the lobby), and START is only sent from the range itself. `Menu` is importable (l4_swatch.py).
"""
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
from reenter import find_cursor  # noqa: E402  (checks ring and dot; the game draws two cursor sprites)

OUT = ROOT / "data" / "l4"
TAPS = ("A", "B", "Y", "LB", "RB", "UP", "DOWN", "LEFT", "RIGHT", "START")


class Stop(Exception):
    """The screen is not the one the next input was meant for. Nothing more is sent."""


def small(frame):
    return cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)


def region_check(image_path, box):
    x0, y0, x1, y1 = box
    ref = cv2.cvtColor(small(cv2.imread(str(image_path))), cv2.COLOR_BGR2GRAY).astype(np.float32)[y0:y1, x0:x1]
    assert ref.size, image_path

    def check(frame):
        now = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY).astype(np.float32)[y0:y1, x0:x1]
        return float(np.abs(now - ref).mean()) < 10.0
    return check


class Menu:
    """One capture + one pad. `expect` sets the check every later token must pass on a fresh frame."""

    def __init__(self, first_check, cap=None):
        self.cap = cap or Capture("dxcam")
        self.last = None
        while self.last is None:
            self.last = self.cap.grab()
        self.check = first_check
        if not first_check(self.last):
            raise Stop("screen does not match what was expected; no pad opened, nothing sent")
        import vgamepad as vg
        b = vg.XUSB_BUTTON
        self.codes = {"A": b.XUSB_GAMEPAD_A, "B": b.XUSB_GAMEPAD_B, "Y": b.XUSB_GAMEPAD_Y,
                      "START": b.XUSB_GAMEPAD_START, "LB": b.XUSB_GAMEPAD_LEFT_SHOULDER,
                      "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER, "UP": b.XUSB_GAMEPAD_DPAD_UP,
                      "DOWN": b.XUSB_GAMEPAD_DPAD_DOWN, "LEFT": b.XUSB_GAMEPAD_DPAD_LEFT,
                      "RIGHT": b.XUSB_GAMEPAD_DPAD_RIGHT}
        self.pad = vg.VX360Gamepad()
        time.sleep(3.0)

    def fresh(self, wait=0.5):
        f, t = None, time.perf_counter()
        while f is None and time.perf_counter() - t < wait:
            f = self.cap.grab()
        self.last = self.last if f is None else f  # a static menu sends no new frame: unchanged since the last check
        return self.last

    def expect(self, check, timeout=0.0):
        """Switch to the next screen's check; optionally wait for that screen to appear."""
        self.check, t = check, time.perf_counter()
        while not check(self.fresh()) and time.perf_counter() - t < timeout:
            time.sleep(0.1)

    def _guard(self, tok):
        if not self.check(self.fresh()):
            raise Stop(f"before '{tok}': screen does not match this stage")

    def _stick(self, right, x, y, secs, rest=0.25):
        stick = self.pad.right_joystick_float if right else self.pad.left_joystick_float
        stick(x, y); self.pad.update(); time.sleep(secs)
        stick(0.0, 0.0); self.pad.update(); time.sleep(rest)

    def send(self, tok):
        assert tok != "X", "X is never sent from the menu tool"
        self._guard(tok)
        pad = self.pad
        if tok in TAPS:
            pad.press_button(button=self.codes[tok]); pad.update(); time.sleep(0.12)
            pad.release_button(button=self.codes[tok]); pad.update(); time.sleep(0.5)
        elif tok.startswith("hold:"):
            name, secs = tok[5:].split(",")
            assert name in ("A", "LEFT", "RIGHT"), name
            pad.press_button(button=self.codes[name]); pad.update(); time.sleep(float(secs))
            pad.release_button(button=self.codes[name]); pad.update(); time.sleep(0.5)
        elif tok in ("LT", "RT"):
            trig = pad.left_trigger_float if tok == "LT" else pad.right_trigger_float
            trig(1.0); pad.update(); time.sleep(0.12)
            trig(0.0); pad.update(); time.sleep(0.5)
        elif tok.startswith(("ls:", "rs:")):
            x, y, secs = (float(v) for v in tok[3:].split(","))
            self._stick(tok[0] == "r", x, y, secs, rest=0.3)
        elif tok.startswith("goto:"):
            self.goto(*(float(v) for v in tok[5:].split(",")))
        elif tok.startswith("w:"):
            time.sleep(float(tok[2:]))
        else:
            raise Stop(f"unknown token {tok}")

    def goto(self, tx, ty, tol=9):
        """Step the cursor to (tx, ty), one axis at a time, re-finding it after every step."""
        misses = 0
        for _ in range(30):
            pos = find_cursor(self.fresh())
            if pos is None:  # lost over a busy widget: jiggle onto plainer ground and look again
                misses += 1
                if misses > 4:
                    raise Stop("cursor not found")
                self._stick(False, -1.0 if misses % 2 else 0.0, 0.0 if misses % 2 else 1.0, 0.12)
                continue
            dx, dy = tx - pos[0], ty - pos[1]
            if abs(dx) <= tol and abs(dy) <= tol:
                return pos
            if abs(dx) > tol:
                x, y, d = math.copysign(1.0, dx), 0.0, abs(dx)
            else:
                x, y, d = 0.0, -math.copysign(1.0, dy), abs(dy)  # stick up = screen up
            self._guard("goto")
            self._stick(False, x, y, min(0.5, 0.035 + 0.8 * d / 560))
        raise Stop("cursor did not converge")

    def snap(self, name="menu"):
        OUT.mkdir(parents=True, exist_ok=True)
        time.sleep(0.6)
        img = small(self.fresh())
        n = len(list(OUT.glob("menu-*.jpg")))
        for path in (OUT / f"{name}.jpg", OUT / f"menu-{n:03d}.jpg"):
            cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return img


def parse_check(spec):
    if spec == "range":
        return in_range
    img, box = spec.rsplit(":", 1)
    return region_check(img, tuple(int(v) for v in box.split(",")))


def main():
    args = sys.argv[1:]
    assert args and len(args) % 2 == 0, __doc__
    stages = [(spec, toks.split()) for spec, toks in zip(args[::2], args[1::2])]
    for spec, toks in stages:
        assert spec == "range" or "START" not in toks, "START only from the range"
    sent = 0
    try:
        menu = Menu(parse_check(stages[0][0]))
    except Stop as e:
        raise SystemExit(f"menu: {e}")
    try:
        for spec, toks in stages:
            menu.expect(parse_check(spec))
            for tok in toks:
                menu.send(tok)
                sent += 1
    except Stop as e:
        print(f"menu: STOP {e} ({sent} tokens sent)")
    menu.snap()
    print(f"menu: sent {sent} tokens")


if __name__ == "__main__":
    main()
