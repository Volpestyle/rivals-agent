"""Step through the game's own menus on the pad. Every input needs fresh, POSITIVE proof of the screen it is meant for.

Usage (PC desktop session): l4_menu.py SCREEN TOKENS [SCREEN TOKENS ...]
  python scripts/l4_menu.py range "START" pause "w:0.5"        # SCREEN is one of SCREENS below
Saves the resulting screen to data/l4/menu.jpg.

Tokens: A B LB RB (taps), LT RT (sub-tab), hold:A,2.0, ls:x,y,secs (cursor), rs:x,y,secs (scroll),
goto:x,y (closed-loop cursor move, 1280x720 px), w:secs. START only from `range`. X, BACK, Y and the d-pad: never.

Safety rules (VUH-1325), all enforced inside Menu, not by callers:
- Proof is a frame grabbed AFTER the previous input and under PROOF_MAX_AGE_S old at the press. Frames come from GDI
  (capture.Capture("gdi")), which always returns the current screen; dxcam returns nothing on a static menu, and the old
  code then reused a frame from before the last input.
- A check is a positive match of a named screen (a template of something only that screen draws). There are no
  negative checks ("not the lobby"): black, white and unknown screens match nothing, so nothing is sent.
- START is sent only when the proof frame is the practice range, whatever check the caller set.
- Unknown sends nothing: a lost cursor raises Stop without touching a stick.
- Every press is try/finally pad.reset()+update, so an interrupt cannot leave a button or a stick held; close() too.
"""
import math
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from record import in_range  # noqa: E402
from reenter import find_cursor  # noqa: E402  (checks ring and dot; the game draws two cursor sprites)

OUT = ROOT / "data" / "l4"
TEMPLATES = Path(__file__).parent / "templates"
PROOF_MAX_AGE_S = 0.35               # a GDI grab takes ~45 ms; the proof is taken immediately before the press
TAPS = ("A", "B", "LB", "RB", "START")
_T = {}


class Stop(Exception):
    """The screen is not positively the one the next input was meant for. Nothing more is sent."""


def small(frame):
    return frame if frame.shape[1] == 1280 else cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)


def match(frame, name, box, slack=6):
    """Normalised correlation (0..1) of templates/<name>.png inside `box` (x0, y0, x1, y1 at 1280x720), 0 if flat."""
    if frame is None or getattr(frame, "ndim", 0) != 3 or frame.shape[0] < 360:
        return 0.0
    if name not in _T:
        _T[name] = cv2.imread(str(TEMPLATES / f"{name}.png"), cv2.IMREAD_GRAYSCALE)
        assert _T[name] is not None, name
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    x0, y0, x1, y1 = box
    win = g[max(0, y0 - slack):y1 + slack, max(0, x0 - slack):x1 + slack]
    if float(win.std()) < 5.0:
        return 0.0
    score = float(cv2.minMaxLoc(cv2.matchTemplate(win, _T[name], cv2.TM_CCOEFF_NORMED))[1])
    return score if score == score and abs(score) <= 1.0 else 0.0


def on_pause(frame):
    """The logo AND the button column on a dark ground. The logo alone also shows behind the LEAVE GAME dialog, whose
    white band covers the buttons."""
    if match(frame, "pause_logo", (505, 115, 775, 220)) < 0.7:
        return False
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    return all(float(g[y - 6:y + 6, 560:720].mean()) > 150 and float(g[y - 6:y + 6, 330:480].mean()) < 110
               for y in (393, 440, 556))          # VIEW MISSIONS, CUSTOMER SUPPORT, EXIT TO DESKTOP rows


def on_practice_settings(frame):
    # the title slides up ~20 px while a "... Deactivated" toast shows, hence the slack
    return match(frame, "ps_title", (512, 47, 772, 85), slack=26) >= 0.7


def on_leave_dialog(frame):
    return match(frame, "leave_title", (558, 236, 728, 276)) >= 0.7


SCREENS = {"range": in_range, "pause": on_pause, "practice_settings": on_practice_settings, "leave_dialog": on_leave_dialog}


def pause_row(frame):
    """Which pause-menu row is lit (the hovered row is drawn wider than the rest), or None. Positive: needs the pause screen."""
    if not on_pause(frame):
        return None
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    rows = {name: max(float(g[y - 8:y + 8, 745:748].mean()), float(g[y - 8:y + 8, 531:534].mean()))
            for name, y in (("resume", 253), ("practice", 300), ("settings", 346), ("missions", 393),
                            ("support", 440), ("leave", 486))}
    lit = [n for n, v in rows.items() if v > 150]
    return lit[0] if len(lit) == 1 else None          # two lit rows is not a state this menu has


class Menu:
    """One screen grabber + one pad. `expect(check)` names the screen every later input must be proven on."""

    def __init__(self, first_check, grab=None, pad=None, settle_s=3.0):
        if grab is None:
            from capture import Capture
            grab = Capture("gdi").grab                # always the current screen, static or not
        self._grab, self.check, self.last_input_t = grab, first_check, 0.0
        self.frame, self.frame_t = None, 0.0
        if not first_check(self.fresh()):
            raise Stop("screen does not match what was expected; no pad opened, nothing sent")
        if pad is None:
            import vgamepad as vg
            b = vg.XUSB_BUTTON
            self._codes = {"A": b.XUSB_GAMEPAD_A, "B": b.XUSB_GAMEPAD_B, "START": b.XUSB_GAMEPAD_START,
                           "LB": b.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER}
            pad = vg.VX360Gamepad()
        else:
            self._codes = {n: n for n in TAPS}
        self._pad = pad
        time.sleep(settle_s)

    # -- proof ------------------------------------------------------------------------------------------------------
    def fresh(self):
        """A frame grabbed now, stamped after the grab returns. Fails closed: no frame, no proof."""
        frame = self._grab()
        if frame is None:
            raise Stop("screen grab returned nothing")
        self.frame, self.frame_t = frame, time.perf_counter()
        return frame

    def expect(self, check, timeout=0.0):
        """Name the next screen; optionally wait for it to appear."""
        self.check, t = check, time.perf_counter()
        while not check(self.fresh()) and time.perf_counter() - t < timeout:
            time.sleep(0.1)

    def _prove(self, what, extra=None):
        frame = self.fresh()                                           # always AFTER the last input
        age = time.perf_counter() - self.frame_t
        if self.frame_t <= self.last_input_t or age > PROOF_MAX_AGE_S:
            raise Stop(f"before '{what}': proof frame is stale ({age:.2f} s)")
        if not self.check(frame) or (extra is not None and not extra(frame)):
            raise Stop(f"before '{what}': screen is not positively the expected one")
        return frame

    # -- input ------------------------------------------------------------------------------------------------------
    def _neutral(self):
        self._pad.reset()
        self._pad.update()
        self.last_input_t = time.perf_counter()

    def _hold(self, apply, secs, rest):
        try:
            apply()
            self._pad.update()
            time.sleep(secs)
        finally:                                                       # KeyboardInterrupt included: never leave it held
            self._neutral()
        time.sleep(rest)

    def _stick(self, right, x, y, secs, rest=0.25):
        stick = self._pad.right_joystick_float if right else self._pad.left_joystick_float
        self._hold(lambda: stick(x, y), secs, rest)

    def send(self, tok):
        if tok.startswith("w:"):
            time.sleep(float(tok[2:]))
            return
        if tok == "START":
            self._prove(tok, extra=in_range)                           # whatever the caller's check says
        else:
            self._prove(tok)
        if tok in TAPS:
            self._hold(lambda: self._pad.press_button(button=self._codes[tok]), 0.12, 0.5)
        elif tok.startswith("hold:"):
            name, secs = tok[5:].split(",")
            if name != "A":
                raise Stop(f"refused {tok}")
            self._hold(lambda: self._pad.press_button(button=self._codes["A"]), float(secs), 0.5)
        elif tok in ("LT", "RT"):
            trig = self._pad.left_trigger_float if tok == "LT" else self._pad.right_trigger_float
            self._hold(lambda: trig(1.0), 0.12, 0.5)
        elif tok.startswith(("ls:", "rs:")):
            x, y, secs = (float(v) for v in tok[3:].split(","))
            self._stick(tok[0] == "r", x, y, min(secs, 3.0), rest=0.3)
        elif tok.startswith("goto:"):
            self.goto(*(float(v) for v in tok[5:].split(",")))
        else:
            raise Stop(f"refused token {tok}")                         # X, BACK, Y, the d-pad and anything unknown

    def goto(self, tx, ty, tol=9, locate=find_cursor):
        """Step the cursor to (tx, ty), one axis at a time, re-finding it after every step. A lost cursor sends nothing."""
        for _ in range(30):
            frame = self._prove("goto")
            pos = locate(frame)
            if pos is None:
                raise Stop("cursor not found; nothing sent")
            dx, dy = tx - pos[0], ty - pos[1]
            if abs(dx) <= tol and abs(dy) <= tol:
                return pos
            if abs(dx) > tol:
                x, y, d = math.copysign(1.0, dx), 0.0, abs(dx)
            else:
                x, y, d = 0.0, -math.copysign(1.0, dy), abs(dy)       # stick up = screen up
            self._stick(False, x, y, min(0.5, 0.035 + 0.8 * d / 560))
        raise Stop("cursor did not converge")

    def close(self):
        self._neutral()

    def snap(self, name="menu"):
        OUT.mkdir(parents=True, exist_ok=True)
        time.sleep(0.6)
        img = small(self.fresh())
        cv2.imwrite(str(OUT / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return img


def main():
    args = sys.argv[1:]
    assert args and len(args) % 2 == 0 and all(a in SCREENS for a in args[::2]), __doc__
    stages = [(SCREENS[name], toks.split()) for name, toks in zip(args[::2], args[1::2])]
    try:
        menu = Menu(stages[0][0])
    except Stop as e:
        raise SystemExit(f"menu: {e}")
    sent = 0
    try:
        for check, toks in stages:
            menu.expect(check, timeout=3.0)
            for tok in toks:
                menu.send(tok)
                sent += 1
    except Stop as e:
        print(f"menu: STOP {e} ({sent} tokens sent)")
    finally:
        menu.close()
    menu.snap()
    print(f"menu: sent {sent} tokens")


if __name__ == "__main__":
    main()
