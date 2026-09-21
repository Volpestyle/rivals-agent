"""L4 live trials: aim settle time, primitive replays, and the tag/damage recording for L2.

Usage (PC desktop session, game focused, in the range near the Luna Snow bot on the plaza):
  python scripts/l4_trial.py aim [n]            # n trials: turn ~30 deg off a standing bot, time the re-aim
  python scripts/l4_trial.py prim <name> [n]    # web_cluster melee_combo uppercut pull web_strike burst swing
  python scripts/l4_trial.py tagrun [secs]      # fight the bot while recording NATIVE frames + pad state to data/l1/tagrun
Writes data/l4/<what>/ (frames NNNNNN.jpg at 1280 wide, log.jsonl, result.json). Input goes through Live (HUD guard).
"""
import json
import math
import queue
import sys
import threading
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "perception"))
from agent.controller import NEUTRAL, Controller, Live  # noqa: E402
from agent.intents import BURST, Combo, Engage, Pull, Search, SwingTo, WebStrike  # noqa: E402
from agent.state import ENEMY, State  # noqa: E402
from outline import find_enemies  # noqa: E402  (L3's green finder; Enemy Color = Green in the game)
from agent.state import Detection  # noqa: E402

CROP = 960  # native px square around the crosshair: the aim sensor (4.4 ms on the PC); full frame only for search


def detect(frame):
    """Detections in 1280x720 pixels (the size State.frame declares). Crop first; whole view only if it is empty."""
    h, w = frame.shape[:2]
    k = w / 1280.0
    x0, y0 = (w - CROP) // 2, (h - CROP) // 2
    found = [(d, x0, y0) for d in find_enemies(frame[y0:y0 + CROP, x0:x0 + CROP], scale=k)]
    if not found:
        found = [(d, 0, 0) for d in find_enemies(frame, scale=k)]
    return [Detection(cls=d.cls, conf=d.conf, bbox=tuple(round((v + (ox, oy)[i % 2]) / k, 1) for i, v in enumerate(d.bbox)))
            for d, ox, oy in found]


FRAME = (1280, 720)


class Rig:
    """Live + perception + a frame/log writer thread (JPEG encoding must not stall the 60 Hz loop)."""

    def __init__(self, out, native=False, fps=15.0, live_factory=Live):
        self.out, self.native, self.period = Path(out), native, 1.0 / fps
        self.out.mkdir(parents=True, exist_ok=True)
        self.q, self.log = queue.Queue(maxsize=64), None
        self.live, self.ctrl = live_factory(), Controller()
        try:                           # from here the pad is open: any failure closes it before it propagates
            self.live.keepalive()
            self.t0, self.saved, self.next_save = time.perf_counter(), 0, 0.0
            self.log = open(self.out / ("frames.jsonl" if native else "log.jsonl"), "w", encoding="utf-8")
            threading.Thread(target=self._writer, daemon=True).start()
        except BaseException:
            self.live.close()
            raise

    def _writer(self):
        while True:
            name, img = self.q.get()
            if name is None:
                return
            cv2.imwrite(str(self.out / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

    def see(self):
        frame = self.live.fresh()
        small = cv2.resize(frame, FRAME, interpolation=cv2.INTER_LINEAR)
        dets = detect(frame)   # HUD and player-region exclusion are inside find_enemies
        state = State(t=self.live.frame_t - self.t0, frame=FRAME, detections=dets)
        return frame, small, state

    def act(self, pad, frame, small, state, note=None):
        self.live.send(**pad)
        row = {"t": round(state.t, 4), "pad": {**pad, "buttons": list(pad["buttons"])}, "note": note, "cam": [round(v, 1) for v in self.ctrl.cam], "pitch_used": round(self.ctrl.pitch_used, 3),
               "dets": [[round(v) for v in d.bbox] for d in state.detections]}
        if state.t >= self.next_save and not self.q.full():
            row["file"] = row["i"] = None
            name = f"{self.saved:06d}.jpg"
            self.q.put((name, frame.copy() if self.native else small))
            row["file"], row["i"] = name, self.saved
            self.saved, self.next_save = self.saved + 1, state.t + self.period
        self.log.write(json.dumps(row) + "\n")

    def close(self):
        try:
            self.live.close()          # first, and whatever else fails: close owns the lease watchdog
        finally:
            self.q.put((None, None))
            time.sleep(0.5)
            if self.log is not None:
                self.log.close()

    def nearest(self, state):
        return min(state.detections, key=lambda d: abs(d.center[0] - 640) + abs(d.center[1] - 360), default=None)

    def acquire(self, timeout=12.0):
        """Pan until a bot is in view, then aim at it until on target for 0.25 s. Returns the Detection or None."""
        t_end, held, target = time.perf_counter() + timeout, 0.0, None
        while time.perf_counter() < t_end:
            frame, small, state = self.see()
            det = self.nearest(state)
            if det is None and target is None:
                self.act(self.ctrl.step(state, Search()), frame, small, state, "search")
                continue
            if det is None and self.ctrl.track is not None and state.t - self.ctrl.track.seen_t > 0.8:
                target, self.ctrl.track, held = None, None, 0.0      # it was junk or it is gone: search again
                continue
            if det is not None and det.height < 24:                  # too small to be worth a trial
                det = None
                if target is None:
                    self.act(self.ctrl.step(state, Search()), frame, small, state, "search")
                    continue
            target = det or target
            pad, on = self.ctrl.aim_only(state, target)
            self.act(pad, frame, small, state, "pre-aim")
            held = held + 1 / 60 if on else 0.0
            if held > 0.25:
                return target
        return None

    def hold(self, secs, note, **pad):
        t_end = time.perf_counter() + secs
        while time.perf_counter() < t_end:
            frame, small, state = self.see()
            self.act({**NEUTRAL, **pad}, frame, small, state, note)


def aim(rig, n, offset_deg=30.0):
    """Turn `offset_deg` off a standing bot while the tracker keeps hold of THAT bot (several are in view), then time the re-aim."""
    results, c = [], rig.ctrl
    for i in range(n):
        target = rig.acquire()
        if target is None:
            results.append({"trial": i, "error": "no bot acquired"})
            continue
        side, t_off = (1.0 if i % 2 == 0 else -1.0), time.perf_counter()
        want_px = c.cal.focal_1280 * math.tan(math.radians(offset_deg))   # measured on screen, not from the camera model
        while abs(c.track.ex) < want_px and time.perf_counter() - t_off < 1.0:
            frame, small, state = rig.see()
            pad, _ = c.aim_only(state, target)
            pad["rx"], pad["ry"] = 0.45 * side, 0.0          # override the aim: turn away at 172 deg/s
            c.stick = (pad["rx"], pad["ry"])                 # so the commanded-camera model stays true
            rig.act(pad, frame, small, state, "offset")
        off_deg = c.track.yaw - c.cam[0]
        frame, small, state = rig.see()
        t_start, inside_since, settle, errs = state.t, None, None, []
        while state.t - t_start < 1.0:
            pad, on = c.aim_only(state, target)
            rig.act(pad, frame, small, state, f"aim{i}")
            fresh = state.t - c.track.seen_t < 0.05
            if fresh:
                errs.append((round(state.t - t_start, 3), round(c.track.ex)))
            inside = fresh and abs(c.track.ex) <= max(6.0, 0.5 * c.track.w)
            inside_since = (inside_since if inside_since is not None else state.t) if inside else (None if fresh else inside_since)
            if inside_since is not None and state.t - inside_since >= 0.15 and settle is None:
                settle = inside_since - t_start
            frame, small, state = rig.see()
        results.append({"trial": i, "model_offset_deg": round(off_deg, 1),
                        "offset_deg": round(math.degrees(math.atan(errs[0][1] / c.cal.focal_1280)), 1) if errs else None, "first_err_px": errs[0][1] if errs else None,
                        "settle_ms": None if settle is None else round(settle * 1000), "box_w": round(c.track.w),
                        "err_px": errs[::4]})
    return results


def prim(rig, name, n):
    results = []
    for i in range(n):
        target = rig.acquire()
        if target is None:
            results.append({"trial": i, "error": "no bot acquired"})
            continue
        h0 = target.height
        intent = {"pull": Pull, "web_strike": WebStrike}.get(name)
        intent = intent(target) if intent else Combo(BURST, target) if name == "burst" else None
        if name == "swing":
            from agent.anchors import anchors
            frame, small, state = rig.see()
            found = anchors(small)
            if not found:
                results.append({"trial": i, "error": "no anchor"})
                continue
            intent = SwingTo(found[0])
        t_start, heights = None, []
        rig.ctrl.played = None
        while True:
            frame, small, state = rig.see()
            t_start = state.t if t_start is None else t_start
            if intent is not None:
                if name == "swing":
                    state.detections = state.detections + [intent.anchor]
                pad = rig.ctrl.step(state, intent)
            else:  # bare primitives: keep aiming, play it once
                pad, _ = rig.ctrl.aim_only(state, target)
                if not rig.ctrl.seq and rig.ctrl.played != (name, i):
                    rig.ctrl.play(name, state.t); rig.ctrl.played = (name, i)
                while rig.ctrl.seq and state.t >= rig.ctrl.seq[0][0]:
                    rig.ctrl.seq.pop(0)
                if rig.ctrl.seq:
                    pad.update(rig.ctrl.seq[0][1])
            rig.act(pad, frame, small, state, f"{name}{i}")
            det = rig.nearest(state)
            if det is not None:
                heights.append((round(state.t - t_start, 2), round(det.height)))
            if state.t - t_start > 3.5:
                break
        results.append({"trial": i, "box_h_before": round(h0), "box_h": heights[::6]})
        rig.hold(1.5, "rest")
    return results


def tagrun(rig, secs):
    """Engage the bot (tags, strikes, melee at varied range), then stand in front of it to take damage."""
    t_end, combo = time.perf_counter() + secs, None
    while time.perf_counter() < t_end:
        frame, small, state = rig.see()
        det = rig.nearest(state)
        phase = (time.perf_counter() - rig.t0) % 20.0
        if det is None:
            intent = Search()
        elif phase < 6.0:
            intent, combo = Engage(det), None
        elif phase < 11.0:
            intent = combo = combo or Combo(BURST, det)   # one instance = one play of the burst
        else:
            intent = None      # stand still, aimed, and let it shoot back
        pad = rig.ctrl.step(state, intent) if intent is not None else rig.ctrl.aim_only(state, det)[0]
        if intent is None and 17.0 < phase < 18.5:
            pad["ly"] = -1.0   # back off a little so the next engage starts from range
        rig.act(pad, frame, small, state, type(intent).__name__ if intent else "stand")
    return {"frames": rig.saved, "seconds": secs}


def _native(path, frame):
    cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])


def _play(rig, target, secs, intent=None, prim_name=None, save=None):
    """Aim at `target` for `secs`, playing a burst intent or one bare primitive; optionally save native frames at 10 fps."""
    c, t_end, n, t_next, played = rig.ctrl, time.perf_counter() + secs, 0, 0.0, False
    c.played = None
    while time.perf_counter() < t_end:
        frame, small, state = rig.see()
        if intent is not None:
            pad = c.step(state, intent)
        else:
            pad, _ = c.aim_only(state, target)
            if prim_name and not played:
                c.play(prim_name, state.t); played = True
            while c.seq and state.t >= c.seq[0][0]:
                c.seq.pop(0)
            if c.seq:
                pad.update(c.seq[0][1])
        rig.act(pad, frame, small, state, prim_name or "burst")
        if save is not None and state.t >= t_next:
            _native(save[0] / f"{save[1]}-{n:03d}.jpg", frame)
            n, t_next = n + 1, state.t + 0.1
    rig.live.release()
    return n


def scoreboard(rig, rounds):
    """Fixtures for the scoreboard reader: hold View/BACK after each fight, native frames through the hold."""
    out, res = rig.out, []
    for r in range(rounds):
        if r:   # round 0 is the board as it stands
            target = rig.acquire(8.0)
            if target is not None:
                _play(rig, target, 3.6, intent=Combo(BURST, target), save=(out, f"fight{r}"))
        time.sleep(0.4)
        board = rig.live.scoreboard(1.3)          # the one door to BACK: range confirmed first, nothing else held, always released
        if board is not None:                     # None: the board was never positively recognised
            _native(out / f"board{r}.jpg", board)
        time.sleep(0.8)
        res.append({"round": r})
    return res


def tagged(rig, n):
    """Native frames of one bot untagged, then with the Spider-Tracer icon after a Web Cluster (the tag lasts 3 s)."""
    res = []
    for i in range(n):
        target = rig.acquire(8.0)
        if target is None:
            res.append({"trial": i, "error": "no bot acquired"})
            continue
        a = _play(rig, target, 1.0, save=(rig.out, f"t{i}-a-untagged"))
        b = _play(rig, target, 3.0, prim_name="web_cluster", save=(rig.out, f"t{i}-b-after-web-cluster"))
        rig.hold(4.0, "tag-expire")               # let the tag run out so the next trial starts untagged
        res.append({"trial": i, "untagged_frames": a, "after_shot_frames": b})
    return res


def tagrb(rig, n):
    """Kit check: Web Cluster tag, then RB. Does RB on a TAGGED target pull it to us, or zip us to it? Frames tell."""
    res = []
    for i in range(n):
        target = rig.acquire(10.0)
        if target is None:
            res.append({"trial": i, "error": "no bot acquired"})
            continue
        c, t0, fired, rb, hs = rig.ctrl, None, False, False, []
        while True:
            frame, small, state = rig.see()
            t0 = state.t if t0 is None else t0
            t = state.t - t0
            pad, _ = c.aim_only(state, target)
            if not fired:
                c.play("web_cluster", state.t); fired = True
            if t >= 0.7 and not rb:                      # the tag lasts 3 s; 0.7 s leaves the projectile time to land
                c.play("pull", state.t); rb = True       # the primitive is just an RB tap
            while c.seq and state.t >= c.seq[0][0]:
                c.seq.pop(0)
            if c.seq:
                pad.update(c.seq[0][1])
            rig.act(pad, frame, small, state, f"tagrb{i}")
            det = rig.nearest(state)
            if det is not None:
                hs.append((round(t, 2), round(det.height), round(936.0 / max(det.height, 1), 1)))   # (t, box h at 720p, metres by L3's rule)
            if t > 3.2:
                break
        rig.live.release()
        res.append({"trial": i, "range_m_before": round(936.0 / max(target.height, 1), 1), "t_h_m": hs[::5]})
        rig.hold(4.0, "rest")
    return res


def main(argv, live_factory=Live):
    what, n = argv[0], (lambda i, d: type(d)(argv[i]) if len(argv) > i else d)
    data = ROOT / "data"
    if what == "tagrun":
        rig, run = Rig(data / "l1" / "tagrun", native=True, fps=10.0, live_factory=live_factory), lambda: tagrun(rig, n(1, 60.0))
    elif what == "tagrb":
        rig, run = Rig(data / "l4" / n(2, "tagrb"), live_factory=live_factory), lambda: tagrb(rig, n(1, 2))
    elif what in ("scoreboard", "tagged"):
        rig = Rig(data / "l4" / {"scoreboard": "scoreboard", "tagged": "tagged-native"}[what], live_factory=live_factory)
        run = (lambda: scoreboard(rig, n(1, 6))) if what == "scoreboard" else (lambda: tagged(rig, n(1, 6)))
    elif what == "aim":
        rig, run = Rig(data / "l4" / "aim", live_factory=live_factory), lambda: aim(rig, n(1, 10))
    else:
        rig, run = Rig(data / "l4" / argv[1], live_factory=live_factory), lambda: prim(rig, argv[1], n(2, 5))
    try:
        result = run()
    finally:
        rig.close()                    # Rig.close() closes Live first, on every exit path
    (rig.out / "result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1:])
