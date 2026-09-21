"""Pause > LEAVE GAME on ONE pad that stays connected for the whole visit, with a human/agent look at the dialog.

Usage (PC desktop session, in the range; run detached): python scripts/l4_leave.py
  1. START, steer to LEAVE GAME, confirm the row is highlighted, A, save data/l4/leave-dialog.jpg.
  2. Wait (pad held, up to 5 min) for data/l4/leave-go.txt: tokens such as "goto:560,420 A", or "abort" (B back to the range).
  3. After the tokens, save data/l4/leave-after.jpg. On the lobby nothing more is ever sent.
A pad disconnecting while the pause menu is open is the working cause of an earlier drop, so this never exits mid-menu
unless the game has already left the range.
"""
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from l4_menu import OUT, Menu, Stop, region_check, small  # noqa: E402
from record import in_range  # noqa: E402
from reenter import classify  # noqa: E402

GO = OUT / "leave-go.txt"


def not_lobby(frame):
    return classify(frame) not in ("lobby", "hero_select")


def save(menu, name):
    time.sleep(0.8)
    cv2.imwrite(str(OUT / name), small(menu.fresh()), [cv2.IMWRITE_JPEG_QUALITY, 92])


def main():
    GO.unlink(missing_ok=True)
    on_pause = region_check(OUT / "ref-pause.jpg", (520, 100, 760, 230))
    menu = Menu(lambda f: in_range(f) or on_pause(f))
    try:
        if in_range(menu.last):
            menu.check = in_range
            menu.send("ls:0,1,0.2"); menu.send("ls:0,-1,0.2")
            menu.send("START")
        else:
            menu.send("ls:0,1,0.04")                                   # throwaway: the first input after a connect is swallowed
        menu.expect(on_pause, timeout=3.0)
        menu.send("w:0.6")
        try:
            menu.goto(640, 486)
        except Stop as e:                                              # the ring is hard to find over button text
            print(f"leave: goto gave up ({e}); relying on the highlight check", flush=True)
        menu.expect(region_check(OUT / "ref-pause-leave.jpg", (700, 470, 748, 503)))   # LEAVE GAME row highlighted
        menu.send("A")
        menu.expect(not_lobby)
        save(menu, "leave-dialog.jpg")
        print("leave: A pressed on LEAVE GAME; dialog saved; waiting for go", flush=True)
        t0 = time.time()
        while time.time() - t0 < 300:
            if GO.exists():
                text = GO.read_text().strip()
                GO.unlink()
                if text == "abort":
                    break
                for tok in text.split():
                    menu.send(tok)
                save(menu, "leave-after.jpg")
                print(f"leave: sent '{text}', screen now {classify(menu.fresh())}", flush=True)
                if not not_lobby(menu.last):
                    print("leave: on the lobby; nothing more is sent")
                    return
            time.sleep(0.5)
        for _ in range(4):                       # abort or timeout: close the menu before the pad goes away
            if in_range(menu.fresh()) or not not_lobby(menu.last):
                break
            menu.send("B"); time.sleep(1.0)
        print(f"leave: closed, in range: {in_range(menu.fresh())}")
    except Stop as e:
        print(f"leave: STOP {e}")
        save(menu, "leave-after.jpg")


if __name__ == "__main__":
    main()
