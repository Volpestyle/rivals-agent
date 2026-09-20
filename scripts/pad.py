"""Send a scripted sequence to a ViGEm virtual Xbox 360 pad.

Usage: uv run --no-project --with vgamepad python pad.py "LB w:1 ls:0,1,1.5 A"
  A B X Y LB RB LS RS START BACK UP DOWN LEFT RIGHT   tap (150 ms)
  LT RT                                               trigger tap
  ls:x,y,secs / rs:x,y,secs                           hold a stick, then centre it
  w:secs                                              wait
"""
import sys
import time

import vgamepad as vg

B = vg.XUSB_BUTTON
BUTTONS = {
    "A": B.XUSB_GAMEPAD_A, "B": B.XUSB_GAMEPAD_B, "X": B.XUSB_GAMEPAD_X, "Y": B.XUSB_GAMEPAD_Y,
    "LB": B.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "LS": B.XUSB_GAMEPAD_LEFT_THUMB, "RS": B.XUSB_GAMEPAD_RIGHT_THUMB,
    "START": B.XUSB_GAMEPAD_START, "BACK": B.XUSB_GAMEPAD_BACK,
    "UP": B.XUSB_GAMEPAD_DPAD_UP, "DOWN": B.XUSB_GAMEPAD_DPAD_DOWN,
    "LEFT": B.XUSB_GAMEPAD_DPAD_LEFT, "RIGHT": B.XUSB_GAMEPAD_DPAD_RIGHT,
}


def run(pad, token):
    if token in BUTTONS:
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
    pad = vg.VX360Gamepad()
    time.sleep(2.0)  # let Windows and the game enumerate the device
    for token in sys.argv[1].split():
        run(pad, token)
    time.sleep(0.5)
    print("pad: sent", sys.argv[1])
