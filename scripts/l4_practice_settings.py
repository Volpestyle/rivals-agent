"""Pause > PRACTICE SETTINGS on ONE pad: look at the page, or switch "No Ability Cooldown" off.

Usage (PC desktop session, in the range or on its pause menu):
  python scripts/l4_practice_settings.py look             # open the page, save data/l4/ps-*.jpg, close
  python scripts/l4_practice_settings.py cooldowns-off    # and click the No Ability Cooldown switch if it is on

Every confirm needs positive proof (VUH-1325): A on the pause menu only while the pause screen is matched AND the
PRACTICE SETTINGS row is the one lit; A on the page only while the page title is matched AND the help panel names the
No Ability Cooldown row AND the cursor was walked onto that row in this visit. Closing sends B only from a screen that
is positively the page or the pause menu; from anything else (black, white, lobby, unknown) nothing is sent at all. The
page's cursor cannot be found reliably (two sprites), so steering is by which row the game says is hovered.
"""
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from l4_menu import OUT, Menu, Stop, match, on_pause, on_practice_settings, pause_row, small  # noqa: E402
from record import in_range  # noqa: E402

HELP_BOX = (806, 130, 1210, 163)


def title_w(frame):
    """Width in px of the help panel's title, which names the hovered row: Friendly Fire ~150, No Ability Cooldown and
    Controller Operation ~205, No Ability Cooldown (Always On) ~340."""
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)[133:160, 808:1210]
    cols = (g > 200).any(axis=0).nonzero()[0]
    return int(cols.max()) if len(cols) else 0


def help_is_nac(frame):
    """Page matched AND its help title reads exactly "No Ability Cooldown" (the template spans the space where
    "(Always On)" would be, so that row does not match)."""
    return on_practice_settings(frame) and match(frame, "ps_help_nac", HELP_BOX) >= 0.8


def toggle_on(frame, y=127):
    """A switch's knob is the bright half: right = on (check mark), left = off (cross)."""
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    return float(g[y - 8:y + 8, 707:763].mean()) > float(g[y - 8:y + 8, 645:701].mean())


def open_page(menu):
    if in_range(menu.frame):
        menu.expect(in_range)
        menu.send("ls:0,1,0.2"); menu.send("ls:0,-1,0.2")           # the first input after a connect is swallowed
        menu.send("START")                                            # Menu itself refuses START off the range
    menu.expect(on_pause, timeout=3.0)
    for _ in range(12):
        row = pause_row(menu.fresh())
        if row == "practice":
            break
        if row is None:
            raise Stop("pause menu: no single lit row")
        menu.send("ls:0,-1,0.04" if row == "resume" else "ls:0,1,0.04")
    menu.expect(lambda f: pause_row(f) == "practice")                 # pause screen matched AND that row lit
    menu.send("A")
    menu.expect(on_practice_settings, timeout=3.0)
    menu.send("w:1.0")


def cooldowns_off(menu, shot):
    seen_short = seen_long = False
    for _ in range(30):                                               # walk up the rows: short -> long -> medium title
        w = title_w(menu.fresh())
        seen_short |= 100 < w < 180
        seen_long |= seen_short and w > 280
        if seen_long and w < 260:
            break
        menu.send("ls:0,1,0.035")
    else:
        raise Stop("never reached the No Ability Cooldown row")
    menu.send("ls:1,0,0.07")                                          # from just left of the switch onto it
    shot()
    menu.expect(help_is_nac)                                          # page AND row, proven again at the press
    if toggle_on(menu.fresh()):
        menu.send("A")
    time.sleep(2.5)                                                   # a "... Deactivated" toast shifts the page while it shows
    shot()
    print(f"ps: No Ability Cooldown on = {toggle_on(menu.fresh())}")


def close(menu):
    """B back to the range, only from screens positively identified. Anything else: send nothing."""
    for _ in range(3):
        frame = menu.fresh()
        if in_range(frame):
            return True
        if on_practice_settings(frame):
            menu.expect(on_practice_settings)
        elif on_pause(frame):
            menu.expect(on_pause)
        else:
            print("ps: unknown screen; nothing sent")
            return False
        menu.send("B")
        time.sleep(1.0)
    return in_range(menu.fresh())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "look"
    assert mode in ("look", "cooldowns-off"), __doc__
    menu, n = Menu(lambda f: in_range(f) or on_pause(f)), 0

    def shot():
        nonlocal n
        OUT.mkdir(parents=True, exist_ok=True)
        time.sleep(0.6)
        cv2.imwrite(str(OUT / f"ps-{n}.jpg"), small(menu.fresh()), [cv2.IMWRITE_JPEG_QUALITY, 92])
        n += 1

    try:
        open_page(menu)
        shot()
        if mode == "cooldowns-off":
            cooldowns_off(menu, shot)
    except Stop as e:
        print(f"ps: STOP {e}")
    finally:
        try:
            back = close(menu)
            print(f"ps: saved {n} shots, back in range: {back}")
        except Stop as e:
            print(f"ps: STOP while closing: {e}")
        finally:
            menu.close()                                              # pad neutral on every exit path


if __name__ == "__main__":
    main()
