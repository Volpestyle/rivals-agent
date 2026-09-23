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

def title_w(frame):
    """Width in px of the help panel's title, which names the hovered row: Friendly Fire ~150, No Ability Cooldown and
    Controller Operation ~205, No Ability Cooldown (Always On) ~340."""
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)[133:160, 808:1210]
    cols = (g > 200).any(axis=0).nonzero()[0]
    return int(cols.max()) if len(cols) else 0


def toggle_on(frame, y=127):
    """The No Ability Cooldown switch: True = on (check mark, knob right), False = off (cross, knob left), None = cannot
    tell. Read only on the Practice Settings page AT REST: while a "... Deactivated" toast shows, the page slides up
    ~20 px and the fixed row position would read the wrong pixels."""
    if match(frame, "ps_title", (512, 47, 772, 85), slack=4) < 0.7:
        return None
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    left, right = float(g[y - 8:y + 8, 645:701].mean()), float(g[y - 8:y + 8, 707:763].mean())
    if abs(left - right) < 25:
        return None
    return right > left


def read_toggle(menu, timeout=4.0):
    t0 = time.perf_counter()
    while True:
        state = toggle_on(menu.fresh())
        if state is not None or time.perf_counter() - t0 > timeout:
            return state
        time.sleep(0.2)


def open_page(menu):
    if in_range(menu.frame):
        menu.expect("range")
        menu.send("ls:0,1,0.2"); menu.send("ls:0,-1,0.2")           # the first input after a connect is swallowed
        menu.send("START")                                            # Menu itself refuses START off the range
    menu.expect("pause", timeout=3.0)
    for _ in range(12):
        row = pause_row(menu.fresh())
        if row == "practice":
            break
        if row is None:
            raise Stop("pause menu: no single lit row")
        menu.send("ls:0,-1,0.04" if row == "resume" else "ls:0,1,0.04")
    menu.confirm("pause.practice_settings")                           # Menu proves the pause screen AND that row lit, at the press
    menu.expect("practice_settings", timeout=3.0)
    menu.send("w:1.0")


def cooldowns_off(menu, shot):
    """True when No Ability Cooldown ends up OFF. Reads the switch first: already off means no presses at all (its
    "(Always On)" sub-row, which the walk below steers by, only exists while the parent is on)."""
    state = read_toggle(menu)
    if state is None:
        raise Stop("cannot read the No Ability Cooldown switch")
    if state is False:
        print("ps: No Ability Cooldown is already off; nothing pressed")
        return True
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
    menu.confirm("practice_settings.no_ability_cooldown")             # Menu proves the page AND the row, at the press
    state = read_toggle(menu, timeout=6.0)                            # waits out the toast
    shot()
    print(f"ps: No Ability Cooldown on = {state}")
    return state is False


def close(menu):
    """B back to the range, only from screens positively identified. Anything else: send nothing."""
    for _ in range(3):
        frame = menu.fresh()
        if in_range(frame):
            return True
        if on_practice_settings(frame):
            menu.expect("practice_settings")
        elif on_pause(frame):
            menu.expect("pause")
        else:
            print("ps: unknown screen; nothing sent")
            return False
        menu.send("B")
        time.sleep(1.0)
    return in_range(menu.fresh())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "look"
    assert mode in ("look", "cooldowns-off"), __doc__
    menu, n = Menu(("range", "pause")), 0

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
            print(f"ps: cooldowns off: {cooldowns_off(menu, shot)}")
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
