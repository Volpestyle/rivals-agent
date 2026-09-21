"""Open Pause > PRACTICE SETTINGS, screenshot it (scrolled top to bottom), and close the menu again, on ONE pad.

Usage (PC desktop session, in the range): python scripts/l4_practice_settings.py [tokens after opening, e.g. "goto:700,300 A"]
Saves data/l4/ps-<n>.jpg. The menu is always closed (B until the range HUD is back) before the pad-holding process
exits: a pad disconnecting while the top-level pause menu was open is the working cause of one drop to the lobby.
"""
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from l4_menu import OUT, Menu, Stop, region_check, small  # noqa: E402
from record import in_range  # noqa: E402
from reenter import classify, find_cursor  # noqa: E402


def not_lobby(frame):
    return classify(frame) not in ("lobby", "hero_select")   # the dim pause menu reads as "practice_panel"; B is harmless there


def find_disc(frame):
    """The Practice Settings page draws the cursor as a filled disc with a white rim (r ~ 26 px at 1280x720), which
    reenter.find_cursor (ring + centre dot) does not match. Pick the Hough circle whose rim is brightest all round."""
    import numpy as np
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1, minDist=20, param1=40, param2=18, minRadius=20, maxRadius=32)
    if c is None:
        return None
    th = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    best = (0.0, None)
    for x, y, r in c[0]:
        xs = np.clip((x + r * np.cos(th)).astype(int), 0, 1279)
        ys = np.clip((y + r * np.sin(th)).astype(int), 0, 719)
        rim = float(np.percentile(g[ys, xs], 25))
        if rim > best[0]:
            best = (rim, (float(x), float(y)))
    return best[1] if best[0] > 170 else None


def title_w(frame):
    """Width in px of the help panel's title, which names the hovered row: Friendly Fire ~150, No Ability Cooldown and
    Controller Operation ~205, No Ability Cooldown (Always On) ~340. Steering by it needs no cursor finder."""
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)[133:160, 808:1210]
    cols = (g > 200).any(axis=0).nonzero()[0]
    return int(cols.max()) if len(cols) else 0


def toggle_on(frame, y):
    """A toggle's knob is the bright half: right = on (check mark), left = off (cross)."""
    g = cv2.cvtColor(small(frame), cv2.COLOR_BGR2GRAY)
    x0 = 645 if y < 150 else 655
    return float(g[y - 8:y + 8, x0 + 62:x0 + 118].mean()) > float(g[y - 8:y + 8, x0:x0 + 56].mean())


def cooldowns_off(menu, shot):
    """Walk the cursor up the rows by the help title (short -> long -> medium), switch both cooldown toggles off."""
    seen_short = seen_long = False
    for _ in range(30):
        w = title_w(menu.fresh())
        seen_short |= 100 < w < 180
        seen_long |= seen_short and w > 280
        if seen_long and w < 260:
            break                                   # on the No Ability Cooldown row
        menu.send("ls:0,1,0.035")
    else:
        raise Stop("never reached the No Ability Cooldown row")
    menu.send("ls:1,0,0.07")                        # the cursor arrives just left of the switch; step onto it
    shot()
    if toggle_on(menu.fresh(), 127):
        menu.send("A"); menu.send("w:0.6")
    shot()
    for _ in range(10):                             # back down one row to (Always On), if it is still there
        if title_w(menu.fresh()) > 280:
            break
        menu.send("ls:0,-1,0.03")
    if title_w(menu.fresh()) > 280 and toggle_on(menu.fresh(), 163):
        menu.send("A"); menu.send("w:0.6")
    shot()
    f = menu.fresh()
    print(f"ps: No Ability Cooldown on={toggle_on(f, 127)}  (Always On) on={toggle_on(f, 163)}")


def main():
    extra = sys.argv[1].split() if len(sys.argv) > 1 else []
    on_pause = region_check(OUT / "ref-pause.jpg", (520, 100, 760, 230))
    menu, n = Menu(lambda f: in_range(f) or on_pause(f)), 0

    def shot():
        nonlocal n
        time.sleep(0.6)
        cv2.imwrite(str(OUT / f"ps-{n}.jpg"), small(menu.fresh()), [cv2.IMWRITE_JPEG_QUALITY, 92])
        n += 1

    try:
        if in_range(menu.last):
            menu.check = in_range
            menu.send("ls:0,1,0.2"); menu.send("ls:0,-1,0.2")        # throwaway + keep-alive
            menu.send("START")
        else:
            menu.send("ls:0,1,0.05")                                 # throwaway cursor nudge: first input is swallowed
        menu.expect(on_pause, timeout=3.0)
        menu.send("w:0.6")
        def lit_row(f):      # the hovered row is drawn wider than the rest: white beyond the normal button edges (536..744)
            g = cv2.cvtColor(small(f), cv2.COLOR_BGR2GRAY)
            rows = {name: max(float(g[y - 8:y + 8, 745:748].mean()), float(g[y - 8:y + 8, 531:534].mean()))
                    for name, y in (("resume", 253), ("practice", 300), ("settings", 346), ("missions", 393),
                                    ("support", 440), ("leave", 486))}
            name = max(rows, key=rows.get)
            return name if rows[name] > 150 else None

        for _ in range(12):  # steer by which row lights up, not by finding the cursor ring (it hides over button text)
            row = lit_row(menu.fresh())
            if row == "practice":
                break
            menu.send("ls:0,-1,0.04" if row == "resume" else "ls:0,1,0.04")
        menu.expect(lambda f: on_pause(f) and lit_row(f) == "practice")
        menu.send("A")
        menu.expect(not_lobby)                                        # unknown screen from here: read-only moves
        menu.send("w:1.2")
        shot()
        if extra == ["cooldowns-off"]:
            cooldowns_off(menu, shot)
            extra = []
        for tok in extra:
            if tok.startswith("goto:"):
                menu._guard(tok)
                menu.goto(*(float(v) for v in tok[5:].split(",")), locate=lambda f: find_cursor(f) or find_disc(f))   # the page draws both cursor sprites
            else:
                menu.send(tok)
            shot()
    except Stop as e:
        print(f"ps: STOP {e}")
        shot()
    finally:                                                          # never leave with the menu up
        for _ in range(4):
            if in_range(menu.fresh()):
                break
            if not not_lobby(menu.last):
                print("ps: lobby-like screen, not pressing B")
                break
            menu.check = not_lobby
            menu.send("B"); time.sleep(1.0)
        print(f"ps: saved {n} shots, back in range: {in_range(menu.fresh())}")
        if in_range(menu.last):
            menu.check = in_range
            menu.send("ls:0,1,0.2"); menu.send("ls:0,-1,0.2")


if __name__ == "__main__":
    main()
