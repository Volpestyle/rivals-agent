"""Step through the game's own menus on the pad. Every input needs fresh, POSITIVE proof, enforced at the actuator.

Usage (PC desktop session): l4_menu.py SCREEN TOKENS [SCREEN TOKENS ...]        SCREEN is one of SCREENS below
  python scripts/l4_menu.py range "START" pause "ls:0,1,0.04 A:pause.practice_settings"
Saves the resulting screen to data/l4/menu.jpg.

Tokens: B LB RB (taps), LT RT (sub-tab), ls:x,y,secs (cursor), rs:x,y,secs (scroll), goto:x,y, w:secs, START (range
only), A:<control> (a confirm, only for a control in CONFIRMABLE). Plain A, hold:, X, BACK, Y and the d-pad: never.

Safety rules (VUH-1325). All of them live in Menu, the lowest layer that touches this pad; a caller cannot weaken them:
- Screens are NAMED (SCREENS); Menu takes no caller-supplied check, so a permissive caller is not expressible. Each name
  is a positive template match of something only that screen draws; black, white and unknown screens match nothing.
- A confirm is `A:<control>` for a control in CONFIRMABLE, and needs proof of its screen AND of that control under the
  cursor, at the press. LEAVE GAME, the leave dialog's CONFIRM, EXIT TO DESKTOP and RESTORE DEFAULTS are not in it.
- Proof is a frame whose grab STARTED after the previous input, from GDI (always the current screen). Its age is checked
  at COMMIT, after every proof has been computed, so a slow grab or a slow check cannot authorise a press.
- START only on a proven practice-range frame. No held buttons; a stick is held at most STICK_MAX_S and every nudge is
  proven again. A lost cursor sends nothing. Every press is try/finally reset + update; close() too.
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
PROOF_MAX_AGE_S = 0.35               # grab (~45 ms) + proof (~5 ms); measured from when the grab STARTED to the commit
STICK_MAX_S = 0.6                    # one cursor nudge or scroll; longer moves are several proven nudges
TAPS = ("B", "LB", "RB")
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


def help_is_nac(frame):
    """Practice Settings matched AND its help panel titled exactly "No Ability Cooldown": the game's own statement that
    the cursor is on that row (the template spans the space where "(Always On)" would be)."""
    return on_practice_settings(frame) and match(frame, "ps_help_nac", (806, 130, 1210, 163)) >= 0.8


def pause_row(frame):
    """Which pause-menu row is lit (the hovered row is drawn wider than the rest), or None. Needs the pause screen."""
    if not on_pause(frame):
        return None
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    rows = {name: max(float(g[y - 8:y + 8, 745:748].mean()), float(g[y - 8:y + 8, 531:534].mean()))
            for name, y in (("resume", 253), ("practice", 300), ("settings", 346), ("missions", 393),
                            ("support", 440), ("leave", 486))}
    lit = [n for n, v in rows.items() if v > 150]
    return lit[0] if len(lit) == 1 else None          # two lit rows is not a state this menu has


SCREENS = {"range": in_range, "pause": on_pause, "practice_settings": on_practice_settings}
# The ONLY things A may be pressed on: control -> (its screen, proof that the cursor is on it).
CONFIRMABLE = {
    "pause.practice_settings": ("pause", lambda f: pause_row(f) == "practice"),
    "practice_settings.no_ability_cooldown": ("practice_settings", help_is_nac),
}


class Menu:
    """One screen grabber + one pad. `expect(name)` names the screen every later input must be proven on."""

    def __init__(self, first, grab=None, pad=None, settle_s=3.0):
        if grab is None:
            from capture import Capture
            grab = Capture("gdi").grab                # always the current screen, static or not
        self._grab, self.last_input_t = grab, 0.0
        self.frame, self.frame_t = None, 0.0
        self.screens = self._names(first)
        if not self._on_expected(self.fresh()):
            raise Stop("screen does not match what was expected; no pad opened, nothing sent")
        if pad is None:
            import vgamepad as vg
            b = vg.XUSB_BUTTON
            self._codes = {"A": b.XUSB_GAMEPAD_A, "B": b.XUSB_GAMEPAD_B, "START": b.XUSB_GAMEPAD_START,
                           "LB": b.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER}
            pad = vg.VX360Gamepad()
        else:
            self._codes = {n: n for n in ("A", "B", "START", "LB", "RB")}
        self._pad = pad
        time.sleep(settle_s)

    # -- proof ------------------------------------------------------------------------------------------------------
    @staticmethod
    def _names(screens):
        names = (screens,) if isinstance(screens, str) else tuple(screens) if isinstance(screens, (tuple, list)) else ()
        if not names or any(not isinstance(n, str) or n not in SCREENS for n in names):
            raise Stop(f"unknown screen {screens!r}; screens are named, never supplied as code")
        return names

    def _on_expected(self, frame):
        return any(SCREENS[n](frame) for n in self.screens)

    def fresh(self):
        """A frame grabbed now, stamped with the time the grab STARTED. Fails closed: no frame, no proof."""
        t0 = time.perf_counter()
        frame = self._grab()
        if frame is None:
            raise Stop("screen grab returned nothing")
        self.frame, self.frame_t = frame, t0
        return frame

    def expect(self, screens, timeout=0.0):
        """Name the next screen (or several, any of which will do); optionally wait for it to appear."""
        self.screens, t = self._names(screens), time.perf_counter()
        while not self._on_expected(self.fresh()) and time.perf_counter() - t < timeout:
            time.sleep(0.1)

    def _commit(self, what, press, proofs=()):
        """Grab, compute ALL proof, then check the frame is still young and postdates the last input, then press."""
        frame = self.fresh()
        ok = self._on_expected(frame) and all(p(frame) for p in proofs)     # may be slow: age is judged after it
        age = time.perf_counter() - self.frame_t
        if not ok:
            raise Stop(f"before '{what}': screen or control is not positively the expected one")
        if self.frame_t <= self.last_input_t or age > PROOF_MAX_AGE_S:
            raise Stop(f"before '{what}': proof is stale at commit ({age:.2f} s)")
        press()

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

    def _tap(self, name):
        self._hold(lambda: self._pad.press_button(button=self._codes[name]), 0.12, 0.5)

    def _stick(self, what, right, x, y, secs, rest=0.25):
        if not (0 < secs <= STICK_MAX_S and abs(x) <= 1 and abs(y) <= 1):
            raise Stop(f"refused {what}: a stick is held at most {STICK_MAX_S} s")
        stick = self._pad.right_joystick_float if right else self._pad.left_joystick_float
        self._commit(what, lambda: self._hold(lambda: stick(x, y), secs, rest))

    def confirm(self, control):
        """Press A on `control`: only a control in CONFIRMABLE, only with its screen AND the cursor on it proven now."""
        if control not in CONFIRMABLE:
            raise Stop(f"refused A on {control!r}: not a confirmable control")
        screen, on_control = CONFIRMABLE[control]
        self._commit(f"A:{control}", lambda: self._tap("A"), proofs=(SCREENS[screen], on_control))

    def send(self, tok):
        if tok.startswith("w:"):
            time.sleep(min(float(tok[2:]), 5.0))
        elif tok.startswith("A:"):
            self.confirm(tok[2:])
        elif tok == "START":
            self._commit(tok, lambda: self._tap("START"), proofs=(in_range,))   # whatever screen was named
        elif tok in TAPS:
            self._commit(tok, lambda: self._tap(tok))
        elif tok in ("LT", "RT"):
            trig = self._pad.left_trigger_float if tok == "LT" else self._pad.right_trigger_float
            self._commit(tok, lambda: self._hold(lambda: trig(1.0), 0.12, 0.5))
        elif tok.startswith(("ls:", "rs:")):
            x, y, secs = (float(v) for v in tok[3:].split(","))
            self._stick(tok, tok[0] == "r", x, y, secs, rest=0.3)
        elif tok.startswith("goto:"):
            self.goto(*(float(v) for v in tok[5:].split(",")))
        else:
            raise Stop(f"refused token {tok}")             # plain A, hold:, X, BACK, Y, the d-pad and anything unknown

    def goto(self, tx, ty, tol=9, locate=find_cursor):
        """Step the cursor to (tx, ty), one axis at a time, re-finding it after every step. A lost cursor sends nothing."""
        for _ in range(30):
            pos = locate(self.fresh())
            if pos is None:
                raise Stop("cursor not found; nothing sent")
            dx, dy = tx - pos[0], ty - pos[1]
            if abs(dx) <= tol and abs(dy) <= tol:
                return pos
            if abs(dx) > tol:
                x, y, d = math.copysign(1.0, dx), 0.0, abs(dx)
            else:
                x, y, d = 0.0, -math.copysign(1.0, dy), abs(dy)       # stick up = screen up
            self._stick("goto", False, x, y, min(0.5, 0.035 + 0.8 * d / 560))   # proven again inside
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
    stages = [(name, toks.split()) for name, toks in zip(args[::2], args[1::2])]
    try:
        menu = Menu(stages[0][0])
    except Stop as e:
        raise SystemExit(f"menu: {e}")
    sent = 0
    try:
        for name, toks in stages:
            menu.expect(name, timeout=3.0)
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
