"""Record practice-range frames plus the synchronized pad state.

Usage (on the PC, inside the desktop session, game focused, in the Practice Range):
  uv run --no-project --with dxcam --with opencv-python --with pillow --with vgamepad \
      python record.py [--minutes 10.5] [--fps 10] [--run NAME] [--seed 0] [--switch] [--from-spawn] [--dry]

Holds ONE virtual pad open for the whole run and roams with a seeded scripted
routine. Writes C:\\rivals-agent\\data\\l1\\<run>\\NNNNNN.jpg (1280 wide, native
aspect), frames.jsonl (one line per saved frame) and meta.json (counts, duration,
measured capture fps).

Safety: input is only sent while the range HUD (health bar) is on screen. The
moment it disappears (menu, loading screen, lobby) every control is released and
the run stops with last.jpg saved. On the lobby X is START for a live match and
the left stick drives a click cursor, so the routine also never presses X,
START, BACK or the d-pad. If the idle-kick banner shows, it runs forward attacking. --dry opens no pad and sends nothing (capture only).
"""
import argparse
import json
import random
import time
from pathlib import Path

import cv2


OUT_ROOT = Path(r"C:\rivals-agent\data\l1")


class Pad:
    """One vgamepad held open; `state` is what the game currently sees."""

    def __init__(self):
        import vgamepad as vg
        self.vg = vg
        self.pad = vg.VX360Gamepad()
        self.state = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0, "lt": 0.0, "rt": 0.0, "buttons": []}
        self.t = time.perf_counter()
        time.sleep(3.0)  # enumerate + let the "Switching Devices" banner clear

    def set(self, **changes):
        self.state.update(changes)
        s, b = self.state, self.vg.XUSB_BUTTON
        codes = {"A": b.XUSB_GAMEPAD_A, "B": b.XUSB_GAMEPAD_B, "X": b.XUSB_GAMEPAD_X, "Y": b.XUSB_GAMEPAD_Y,
                 "LB": b.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": b.XUSB_GAMEPAD_RIGHT_SHOULDER}
        self.pad.reset()
        for name in s["buttons"]:
            self.pad.press_button(button=codes[name])
        self.pad.left_joystick_float(s["lx"], s["ly"])
        self.pad.right_joystick_float(s["rx"], s["ry"])
        self.pad.left_trigger_float(s["lt"])
        self.pad.right_trigger_float(s["rt"])
        self.pad.update()
        self.t = time.perf_counter()

    def release(self):
        self.set(lx=0.0, ly=0.0, rx=0.0, ry=0.0, lt=0.0, rt=0.0, buttons=[])


def _region(frame, x0, y0, x1, y1):
    """Crop given in 1280x720 coordinates from a frame of any 16:9 size."""
    k = frame.shape[1] / 1280.0
    return frame[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)]


_BANNER = None
BANNER_BOX = (24, 12, 208, 41)       # the "PRACTICE RANGE" banner, top left, in 1280x720 px
BANNER_MIN = 0.55                    # normalised correlation with scripts/templates/range_banner.png; range frames score 0.8-1.0


def _small_gray(frame):
    g = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return g if g.shape[1] == 1280 else cv2.resize(g, (1280, 720), interpolation=cv2.INTER_AREA)


def _banner_window(frame):
    """The banner window of the 1280x720 view (BANNER_BOX +-4 px), as grey pixels, without converting the whole frame.

    Crop-first is used only where it is EXACT: a frame whose width and height are whole multiples of 1280x720 (the 2560x1440
    capture, 3840x2160). There INTER_AREA is a plain k x k box average, so output pixel (x, y) depends on input pixels
    [x*k, (x+1)*k) x [y*k, (y+1)*k) and nothing else, and cropping those input pixels first gives bit-identical output;
    grey conversion is per pixel, so its order does not matter either. Every other size (1280 wide as it is, 1920x1080,
    non-16:9, anything smaller) takes the old whole-frame path unchanged: fractional area weights round differently on a
    crop (seen: +-1 grey level at 2560x1600), and those sizes are not the live capture, so nothing is gained by risking it.
    The point of all this: a full 2560x1440 grey conversion and resize cost 1.4 ms per call, twice a tick."""
    x0, y0, x1, y1 = BANNER_BOX
    x0, y0, x1, y1 = x0 - 4, y0 - 4, x1 + 4, y1 + 4
    h, w = frame.shape[:2]
    k = w // 1280
    if k < 2 or w != 1280 * k or h != 720 * k:
        return _small_gray(frame)[y0:y1, x0:x1]
    crop = frame[y0 * k:y1 * k, x0 * k:x1 * k]
    g = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)


def banner_score(frame):
    """How well the top-left corner matches the range's own "PRACTICE RANGE" banner (-1..1; 0 for a flat image)."""
    global _BANNER
    if _BANNER is None:
        _BANNER = cv2.imread(str(Path(__file__).parent / "templates" / "range_banner.png"), cv2.IMREAD_GRAYSCALE)
        assert _BANNER is not None, "scripts/templates/range_banner.png is missing"
    win = _banner_window(frame)
    if win.shape[0] < _BANNER.shape[0] or win.shape[1] < _BANNER.shape[1]:   # a frame too small to hold the banner
        return 0.0
    if float(win.std()) < 5.0:                                       # flat (all white, all black): correlation is undefined
        return 0.0
    score = float(cv2.minMaxLoc(cv2.matchTemplate(win, _BANNER, cv2.TM_CCOEFF_NORMED))[1])
    return score if score == score and abs(score) <= 1.0 else 0.0   # NaN / inf from a degenerate window -> no match


def in_range(frame):
    """True only on positive proof of the practice range's playing screen. Everything that sends input calls this.

    Both must hold: (1) the range's "PRACTICE RANGE" banner is drawn top left (template match: identity, not
    brightness), and (2) the HUD health bar is drawn bottom centre with darker screen under it (so a white or washed-out
    screen is not a HUD). False on the lobby, hero select, the pause menu and its pages (the banner is dimmed and blurred
    there), the held-BACK scoreboard (it keeps the banner but has no HUD bar), a desktop or any non-game window, an all-white or all-black frame, and on a lobby
    frame with the health-bar strip painted white (the review's reproduction of the old brightness-only test).

    ponytail: the bar test wants over half the strip bright, calibrated at full health; under ~50 % hp it reads False
    (fails closed: input stops). No range bot deals damage yet. Upgrade: match the bar's frame, not its fill.
    """
    if frame is None or frame.ndim != 3 or frame.shape[0] < 360:
        return False
    if banner_score(frame) < BANNER_MIN:
        return False
    bar = _region(frame, 520, 672, 760, 679).max(axis=2)
    under = _region(frame, 520, 688, 760, 700).max(axis=2)
    if float((bar > 190).mean()) <= 0.5 or float((under > 190).mean()) >= 0.3:
        return False
    # The bar is segmented (a dark divider every 25 hp: 10 at native resolution, 2-9 after a 720p JPEG). A slab of
    # white painted over the strip has none, which is what separates the held-BACK scoreboard (it keeps the banner)
    # with a bright strip from a real HUD.
    col = cv2.resize(bar.mean(axis=0)[None, :].astype("float32"), (240, 1))[0]
    return any(col[i] < min(col[i - 2], col[i + 2]) - 25 and col[i] <= col[i - 1] and col[i] <= col[i + 1]
               for i in range(2, 238))


def idle_warning(frame):
    """The red 'You are about to be removed from the game' banner."""
    b, g, r = cv2.split(_region(frame, 100, 30, 700, 90))
    return float(((r > 180) & (g < 120) & (b < 110)).mean()) > 0.5


def routine(rng):
    """Yield (label, seconds, pad changes) forever.

    There is no position feedback, so each cycle is a stack of legs (approach,
    strafe, orbit, camera sweep) that is then undone in reverse order with the
    opposite stick values, which walks the player back to where the cycle began.
    Start the run facing a target bot ~8 m away on open floor. Attacks and
    abilities go between legs. Never used: X (hold = change hero, START on the
    lobby), LB (web swing, leaves the anchor), START/BACK/d-pad (menus).

    ponytail: drift from collisions and melee lunges is uncorrected; a detector
    driven controller (L3+L4) is the upgrade.
    """
    rest = dict(lx=0.0, ly=0.0, rx=0.0, ry=0.0, lt=0.0, rt=0.0, buttons=[])
    clock, next_ok = 0.0, {"Y": 0.0, "RB": 0.0}

    def leg():
        kind = rng.choice(["approach", "approach", "strafe", "orbit", "orbit", "sweep", "pitch"])
        side = rng.choice([-1.0, 1.0])
        if kind == "approach":
            return kind, rng.uniform(0.4, 1.3), dict(ly=1.0)
        if kind == "strafe":
            return kind, rng.uniform(0.4, 1.2), dict(lx=side)
        if kind == "orbit":  # strafe one way while turning the other keeps the target in view
            return kind, rng.uniform(0.6, 1.6), dict(lx=side, rx=-side * rng.uniform(0.2, 0.4))
        if kind == "sweep":
            return kind, rng.uniform(0.15, 0.4), dict(rx=side * rng.uniform(0.4, 0.9))
        return kind, rng.uniform(0.2, 0.4), dict(ry=side * 0.3)

    def action():
        nonlocal clock
        act = rng.random()
        if act < 0.40:
            yield "rt", rng.uniform(0.6, 1.6), dict(rt=1.0)
        elif act < 0.65:
            for _ in range(rng.randint(1, 3)):
                yield "lt", 0.15, dict(lt=1.0)
                yield "lt", 0.35, dict(lt=0.0)
        elif act < 0.78:
            yield "jump", 0.15, dict(buttons=["A"])
        else:
            ready = [name for name, t in next_ok.items() if t <= clock]
            if ready:
                name = rng.choice(ready)
                next_ok[name] = clock + 8.0
                yield name.lower(), 0.2, dict(buttons=[name])
        yield "rest", 0.4, rest

    while True:
        legs = [leg() for _ in range(rng.randint(2, 4))]
        for back in (False, True):
            for kind, secs, sticks in (reversed(legs) if back else legs):
                if back:
                    sticks = {k: -v for k, v in sticks.items()}
                yield kind + ("-back" if back else ""), secs, {**rest, **sticks}
                yield "rest", 0.15, rest
                clock += secs + 0.15
                if rng.random() < 0.7:
                    for step in action():
                        clock += step[1]
                        yield step
        # Between cycles (so the reversal above stays exact) pan slowly: bots all over the
        # range cross the view at varied screen positions and distances.
        secs = rng.uniform(1.0, 2.5)
        yield "pan", secs, {**rest, "rx": rng.choice([-1.0, 1.0]) * rng.uniform(0.25, 0.45),
                            "lt": 1.0 if rng.random() < 0.3 else 0.0}
        yield "rest", 0.15, rest
        clock += secs + 0.15


def switch_to_spiderman(pad, cap, out):
    """Hold X (change hero), pick Spider-Man on the duelist tab, save the screen before confirming.

    ponytail: open loop. The cursor is first driven into the top-right corner so
    the move to the portrait starts from a known spot; the tab is assumed to be
    'all' (RB twice = duelist). Look at switch-before-confirm.jpg.
    """
    def hold(secs, **changes):
        pad.set(**changes); time.sleep(secs)
        pad.release(); time.sleep(0.4)
    hold(1.5, buttons=["X"]); time.sleep(2.5)
    hold(0.15, buttons=["RB"]); hold(0.15, buttons=["RB"])
    hold(3.0, lx=1.0, ly=1.0)             # cursor to the top-right corner
    hold(0.57, lx=-1.0, ly=-0.1)          # ~435 px left, ~45 px down at ~768 px/s (1280-wide units)
    frame = None
    while frame is None:
        frame = cap.grab()
    cv2.imwrite(str(out / "switch-before-confirm.jpg"), cv2.resize(frame, (1280, 720)))
    hold(0.15, buttons=["A"]); time.sleep(1.0)
    hold(0.15, buttons=["X"]); time.sleep(4.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10.5)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--switch", action="store_true", help="change hero to Spider-Man first")
    ap.add_argument("--from-spawn", action="store_true", help="first walk 6 s forward out of the spawn room")
    ap.add_argument("--dry", action="store_true", help="no pad, no input: capture only")
    ap.add_argument("--selftest", action="store_true", help="check the screen guards on docs/evidence/l1 frames")
    args = ap.parse_args()
    if args.selftest:
        ev = Path(__file__).parent.parent / "docs" / "evidence" / "l1"
        assert in_range(cv2.imread(str(ev / "dxcam-frame.jpg"))), "range frame must pass the guard"
        assert not in_range(cv2.imread(str(ev / "dropped-to-lobby.jpg"))), "lobby must fail the guard"
        assert not idle_warning(cv2.imread(str(ev / "dxcam-frame.jpg")))
        steps, t = routine(random.Random(0)), 0.0
        while t < 660:  # a full run never touches the buttons that leave the range or the anchor
            _, secs, changes = next(steps)
            assert not {"X", "LB"} & set(changes.get("buttons", [])) and 0 < secs < 3
            t += secs
        print("selftest ok")
        return

    from capture import open_capture  # dxcam only imports inside a Windows desktop session
    out = OUT_ROOT / args.run
    out.mkdir(parents=True, exist_ok=False)
    cap = open_capture()
    frame = None
    while frame is None:
        frame = cap.grab()
    if not args.dry and not in_range(frame):
        cv2.imwrite(str(out / "last.jpg"), cv2.resize(frame, (1280, 720)))
        raise SystemExit(f"record: range HUD not on screen, no input sent. See {out / 'last.jpg'}")

    if args.switch and idle_warning(frame):
        raise SystemExit("record: idle-kick countdown on screen, not opening the hero picker")
    pad = None if args.dry else Pad()
    if pad and args.switch:
        switch_to_spiderman(pad, cap, out)

    steps = routine(random.Random(args.seed))
    label, step_end = "start", 0.0
    if pad and args.from_spawn:  # from the spawn pose this ends on the plaza facing the Luna Snow bot
        label, step_end = "leave-spawn", time.perf_counter() + 6.0
        pad.set(ly=1.0)
    h = round(1280 * frame.shape[0] / frame.shape[1])
    saved, grabbed, missing, stop = 0, 0, 0.0, "completed"
    log = open(out / "frames.jsonl", "w", encoding="utf-8")
    t0 = last_seen = time.perf_counter()
    try:
        while (now := time.perf_counter()) - t0 < args.minutes * 60:
            new = cap.grab()
            if new is not None:
                frame, grabbed = new, grabbed + 1
                if pad:
                    missing = 0.0 if in_range(frame) else missing + (now - last_seen)
                    last_seen = now
                    if missing > 0.25:
                        stop = "range HUD lost"
                        break
            if pad and idle_warning(frame) and label != "idle-escape":
                label, step_end = "idle-escape", now + 2.0  # the kick timer wants movement or combat
                pad.set(lx=0.0, ly=1.0, rx=0.0, ry=0.0, lt=0.0, rt=1.0, buttons=[])
            if pad and now >= step_end:
                label, secs, changes = next(steps)
                pad.set(**changes)
                step_end = now + secs
            if now - t0 >= saved / args.fps:
                name = f"{saved:06d}.jpg"
                cv2.imwrite(str(out / name), cv2.resize(frame, (1280, h), interpolation=cv2.INTER_AREA),
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
                log.write(json.dumps({"i": saved, "t": round(now - t0, 4), "file": name, "step": label,
                                      "pad": pad.state if pad else None,
                                      "pad_age": round(max(0.0, now - pad.t), 4) if pad else None,
                                      "idle_warning": idle_warning(frame)}) + "\n")
                saved += 1
            time.sleep(0.002)
    finally:
        if pad:
            pad.release()
        log.close()
        dt = time.perf_counter() - t0
        cv2.imwrite(str(out / "last.jpg"), cv2.resize(frame, (1280, h)))
        meta = {"run": args.run, "stop": stop, "backend": cap.backend, "seed": args.seed, "dry": args.dry,
                "frames": saved, "seconds": round(dt, 2), "saved_fps": round(saved / dt, 2),
                "capture_fps": round(grabbed / dt, 1), "native": list(frame.shape[:2]), "saved_size": [h, 1280]}
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        print("record:", json.dumps(meta))


if __name__ == "__main__":
    main()
