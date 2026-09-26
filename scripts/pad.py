"""Send a scripted sequence to a ViGEm virtual Xbox 360 pad.

Usage: uv run --no-project --with vgamepad python scripts/pad.py "combat:jump:0.15 w:1 ls:0,1,1.5" [--dangerous]
  A B X Y LB RB LS RS START BACK UP DOWN LEFT RIGHT   tap (150 ms)
  LT RT                                               trigger tap
  combat:action:secs                                  semantic hold, then release (0 < secs <= 10)
  LS+RS                                               simultaneous ultimate chord (150 ms)
  ls:x,y,secs / rs:x,y,secs                           hold a stick, then centre it
  w:secs                                              wait

This is the lead's hand tool: it checks no screen. On the PLAY lobby X is START for Quick Match, so
X, START, BACK and the d-pad are refused unless --dangerous is passed by someone who has just read
a screenshot. The whole sequence is validated before the pad is opened, and the pad is always
left neutral, including on Ctrl-C.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.pad_bindings import XUSB_NAMES, button_codes, combat_controls  # noqa: E402

import vgamepad as vg

BUTTONS = button_codes(vg, XUSB_NAMES)


DANGEROUS = {"X", "START", "BACK", "UP", "DOWN", "LEFT", "RIGHT"}


def semantic(token):
    """Resolve the complete command before touching a device."""
    if token == "LS+RS":
        return combat_controls("ultimate"), 0.15
    _, action, duration = token.split(":")
    secs = float(duration)
    state = combat_controls(action)
    if not state or not 0 < secs <= 10:
        raise ValueError("unbound action or hold outside (0, 10] seconds")
    return state, secs


def check(tokens, dangerous=False):
    """Reject the whole sequence before any input is sent."""
    for token in tokens:
        if token.startswith("combat:") or token == "LS+RS":
            try:
                state, _ = semantic(token)
            except (KeyError, ValueError) as exc:
                raise SystemExit(f"refused: {token}: {exc}") from exc
            if DANGEROUS & set(state.get("buttons", ())) and not dangerous:
                raise SystemExit(f"refused: {token} needs --dangerous")
        elif token in BUTTONS or token in ("LT", "RT"):
            if token in DANGEROUS and not dangerous:
                raise SystemExit(f"refused: {token} needs --dangerous (on the PLAY lobby X starts a live match)")
        elif token.startswith(("ls:", "rs:")):
            x, y, secs = (float(v) for v in token[3:].split(","))
            if not (-1 <= x <= 1 and -1 <= y <= 1 and 0 <= secs <= 10):
                raise SystemExit(f"refused: {token} out of range")
        elif token.startswith("w:"):
            float(token[2:])
        else:
            raise SystemExit(f"unknown token: {token}")


def run(pad, token):
    if token.startswith("combat:") or token == "LS+RS":
        state, secs = semantic(token)
        pad.reset()
        try:
            for name in state.get("buttons", ()):
                pad.press_button(button=BUTTONS[name])
            pad.left_trigger_float(state.get("lt", 0.0))
            pad.right_trigger_float(state.get("rt", 0.0))
            pad.update()  # BOTH ultimate clicks in this report, never separate updates
            time.sleep(secs)
        finally:
            pad.reset(); pad.update()
        time.sleep(0.4)
    elif token in BUTTONS:
        pad.press_button(button=BUTTONS[token]); pad.update(); time.sleep(0.15)
        pad.release_button(button=BUTTONS[token]); pad.update(); time.sleep(0.4)
    elif token in ("LT", "RT"):
        trig = pad.left_trigger_float if token == "LT" else pad.right_trigger_float
        trig(1.0); pad.update(); time.sleep(0.15)
        trig(0.0); pad.update(); time.sleep(0.4)
    elif token.startswith(("ls:", "rs:")):
        x, y, secs = (float(v) for v in token[3:].split(","))
        stick = pad.left_joystick_float if token[0] == "l" else pad.right_joystick_float
        stick(x, y); pad.update(); time.sleep(secs)
        stick(0.0, 0.0); pad.update(); time.sleep(0.2)
    elif token.startswith("w:"):
        time.sleep(float(token[2:]))
    else:
        raise SystemExit(f"unknown token: {token}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dangerous"]
    tokens = args[0].split()
    check(tokens, dangerous="--dangerous" in sys.argv)
    pad = vg.VX360Gamepad()
    try:
        time.sleep(2.0)  # let Windows and the game enumerate the device
        for token in tokens:
            run(pad, token)
        time.sleep(0.5)
        print("pad: sent", args[0])
    finally:
        pad.reset(); pad.update()  # never leave a button or stick held, whatever ended the sequence
