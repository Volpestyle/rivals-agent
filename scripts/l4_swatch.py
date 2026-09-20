"""Record the same view under several Enemy Color swatches, for L3 to pick the colour that separates best.

Usage (PC desktop session, in the range, standing where you want the view, game set to Green):
  python scripts/l4_swatch.py view 0.29   # frame the view first: turn right 0.29 s at 0.45 stick (173 deg/s), save data/l4/view.jpg
  python scripts/l4_swatch.py <spot> [turn_s pitch_s]   # optional framing first: seconds right (+) / up (+)
  # writes data/l1/swatch-<spot>-<name>/ for Green, Blue-Green, Yellow-Green, Default
50 native-resolution frames (JPEG q90, 10 fps) per swatch, camera untouched between them; leaves the game on Green.
One pad for the whole run. Between menu visits it walks 0.25 s forward and back, which leaves the camera alone. Every menu input is screen-checked (l4_menu.Menu).
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from l4_menu import OUT, Menu, Stop, region_check, small  # noqa: E402
from record import in_range  # noqa: E402

REF = OUT  # ref-pause.jpg, ref-settings.jpg, ref-access.jpg: screenshots that have been looked at
ON_PAUSE = lambda: region_check(REF / "ref-pause.jpg", (500, 110, 780, 320))        # noqa: E731
ON_SETTINGS = lambda: region_check(REF / "ref-settings.jpg", (50, 8, 135, 42))      # noqa: E731
ON_ACCESS = lambda: region_check(REF / "ref-access.jpg", (55, 140, 500, 230))       # noqa: E731
HUES = {"Blue-Green": 84, "Green": 62, "Yellow-Green": 43, "Default": None}        # OpenCV H of the menu swatch
SLOTS = (312, 345, 379, 412, 446)                                                 # dropdown rows under Enemy Color
HEADER = (640, 283)


def swatch_at(img, y):
    """OpenCV hue of the colour square in a dropdown row (or the header), None if the row has no square."""
    hsv = cv2.cvtColor(img[y - 7:y + 7, 557:573], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    vivid = hsv[(hsv[:, 1] > 90) & (hsv[:, 2] > 120)]
    return int(np.median(vivid[:, 0])) if len(vivid) > 0.6 * len(hsv) else None


def is_wanted(hue, want):
    return hue is None if want is None else hue is not None and abs(hue - want) <= 6


def hovered(img):
    rows = [float(cv2.cvtColor(img[y - 8:y + 8, 680:740], cv2.COLOR_BGR2GRAY).mean()) for y in SLOTS]
    return int(np.argmax(rows)) if max(rows) > 50 else None


def set_swatch(menu, name):
    want = HUES[name]
    menu.expect(in_range)
    menu.send("START")
    menu.expect(ON_PAUSE(), timeout=3.0)
    menu.send("w:0.5"); menu.send("A")
    menu.expect(ON_SETTINGS(), timeout=4.0)
    menu.send("w:1.0")
    on_access = ON_ACCESS()
    for _ in range(12):   # RB presses get dropped; press until the Accessibility page is up
        if on_access(menu.fresh()):
            break
        menu.send("RB"); menu.send("w:0.4")
    menu.expect(on_access)
    menu.goto(*HEADER)
    menu.send("A"); menu.send("w:0.8")
    menu.expect(ON_SETTINGS())   # the open list covers the rows ON_ACCESS looks at
    if want is None:
        menu.send("rs:0,1,0.6")  # Default is the first row
    for _ in range(25):
        img = small(menu.fresh())
        slot = next((i for i, y in enumerate(SLOTS) if is_wanted(swatch_at(img, y), want)), None)
        if want is None and slot != 0:
            slot = None
        if slot is None:
            menu.send("rs:0,-1,0.1" if want is not None else "rs:0,1,0.3")
            continue
        at = hovered(img)
        if at == slot:
            break
        menu.send("ls:0,-1,0.07" if at is None or at < slot else "ls:0,1,0.07")
    else:
        raise Stop(f"could not put the cursor on {name}")
    menu.send("A"); menu.send("w:0.8")
    got = swatch_at(small(menu.fresh()), HEADER[1])
    if not is_wanted(got, want):
        raise Stop(f"Enemy Color header shows hue {got}, wanted {name}")
    menu.snap(f"swatch-set-{name}")
    menu.expect(on_access)
    menu.send("B")
    menu.expect(in_range, timeout=4.0)
    menu.send("w:1.0")


def record(menu, out, n=50, fps=10.0):
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    for i in range(n):
        while time.perf_counter() - t0 < i / fps:
            time.sleep(0.002)
        frame = menu.fresh(0.05)
        if not in_range(frame):
            raise Stop("range HUD lost while recording")
        cv2.imwrite(str(out / f"{i:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    (out / "meta.json").write_text(json.dumps({"frames": n, "fps": fps, "native": list(frame.shape[:2])}))


def keepalive(menu):
    menu.expect(in_range)
    # Walk only. A Web Cluster here knocked down the bot in view and spoiled one swatch set; a sweep lasts ~3 min,
    # well inside the ~10 min inactivity window, so no attack is needed.
    for tok in ("ls:0,1,0.25", "ls:0,-1,0.25", "w:1.5"):
        menu.send(tok)


def main():
    spot = sys.argv[1]
    menu = Menu(in_range)
    if spot == "view":   # python l4_swatch.py view <secs>: keep-alive, turn right at 0.45 stick (negative = left), save one frame
        keepalive(menu)
        secs = float(sys.argv[2])
        menu.send(f"rs:{0.45 if secs > 0 else -0.45},0,{abs(secs)}")
        menu.snap("view")
        return
    try:
        keepalive(menu)   # also absorbs the pad-connect disturbance: a new pad nudges the camera and eats the first input
        turn, pitch = (float(v) for v in sys.argv[2:4]) if len(sys.argv) > 3 else (0.0, 0.0)
        if turn:
            menu.send(f"rs:{0.45 if turn > 0 else -0.45},0,{abs(turn)}")     # 173 deg/s
        if pitch:
            menu.send(f"rs:0,{0.5 if pitch > 0 else -0.5},{abs(pitch)}")     # 43 deg/s, + is up
        for i, name in enumerate(("Green", "Blue-Green", "Yellow-Green", "Default")):
            keepalive(menu)
            if i:                       # the run starts with the game already on Green
                set_swatch(menu, name)
            record(menu, ROOT / "data" / "l1" / f"swatch-{spot}-{name}")
            print(f"swatch: recorded swatch-{spot}-{name}", flush=True)
        keepalive(menu)
        set_swatch(menu, "Green")
        print("swatch: done, game left on Green")
    except Stop as e:
        print(f"swatch: STOP {e}")
        menu.snap("swatch-stop")


if __name__ == "__main__":
    main()
