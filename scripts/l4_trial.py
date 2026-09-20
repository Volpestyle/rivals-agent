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
from agent.controller import NEUTRAL, Controller, Live, in_hero_box  # noqa: E402
from agent.intents import BURST, Combo, Engage, Pull, Search, SwingTo, WebStrike  # noqa: E402
from agent.state import ENEMY, State  # noqa: E402
from outline import detect  # noqa: E402

FRAME = (1280, 720)


class Rig:
    """Live + perception + a frame/log writer thread (JPEG encoding must not stall the 60 Hz loop)."""

    def __init__(self, out, native=False, fps=15.0):
        self.out, self.native, self.period = Path(out), native, 1.0 / fps
        self.out.mkdir(parents=True, exist_ok=True)
        self.live, self.ctrl = Live(), Controller()
        self.t0, self.saved, self.next_save = time.perf_counter(), 0, 0.0
        self.q = queue.Queue(maxsize=64)
        self.log = open(self.out / ("frames.jsonl" if native else "log.jsonl"), "w", encoding="utf-8")
        threading.Thread(target=self._writer, daemon=True).start()

    def _writer(self):
        while True:
            name, img = self.q.get()
            if name is None:
                return
            cv2.imwrite(str(self.out / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

    def see(self):
        frame = self.live.fresh()
        small = cv2.resize(frame, FRAME, interpolation=cv2.INTER_LINEAR)
        dets = [d for d in detect(small, scale=1.0) if not in_hero_box(d, FRAME)]
        state = State(t=self.live.frame_t - self.t0, frame=FRAME, detections=dets)
        return frame, small, state

    def act(self, pad, frame, small, state, note=None):
        self.live.send(**pad)
        row = {"t": round(state.t, 4), "pad": {**pad, "buttons": list(pad["buttons"])}, "note": note,
               "dets": [[round(v) for v in d.bbox] for d in state.detections]}
        if state.t >= self.next_save and not self.q.full():
            row["file"] = row["i"] = None
            name = f"{self.saved:06d}.jpg"
            self.q.put((name, frame.copy() if self.native else small))
            row["file"], row["i"] = name, self.saved
            self.saved, self.next_save = self.saved + 1, state.t + self.period
        self.log.write(json.dumps(row) + "\n")

    def close(self):
        self.live.release()
        self.q.put((None, None))
        time.sleep(0.5)
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


def aim(rig, n):
    results, f = [], rig.ctrl.cal.focal_1280
    for i in range(n):
        target = rig.acquire()
        if target is None:
            results.append({"trial": i, "error": "no bot acquired"})
            continue
        side = 1.0 if i % 2 == 0 else -1.0
        rig.hold(30.0 / 88.0, "offset", rx=0.6 * side)   # 0.6 stick is the top of the linear zone: 88 deg/s
        rig.hold(0.3, "rest")
        rig.ctrl.track = None
        frame, small, state = rig.see()
        det = rig.nearest(state)
        if det is None:
            results.append({"trial": i, "error": "bot not in view after the offset"})
            continue
        off_deg = math.degrees(math.atan((det.center[0] - 640) / f))
        t_start, inside_since, settle, errs = state.t, None, None, []
        while state.t - t_start < 1.0:
            pad, on = rig.ctrl.aim_only(state, det)
            rig.act(pad, frame, small, state, f"aim{i}")
            frame, small, state = rig.see()
            now = rig.nearest(state)
            if now is not None:
                ex = now.center[0] - 640
                errs.append((round(state.t - t_start, 3), round(ex)))
                inside = abs(ex) <= max(6.0, 0.5 * (now.bbox[2] - now.bbox[0]))
                inside_since = (inside_since or state.t) if inside else None
                if inside_since and state.t - inside_since >= 0.15 and settle is None:
                    settle = inside_since - t_start
        results.append({"trial": i, "offset_deg": round(off_deg, 1), "settle_ms": None if settle is None else round(settle * 1000),
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
    t_end = time.perf_counter() + secs
    while time.perf_counter() < t_end:
        frame, small, state = rig.see()
        det = rig.nearest(state)
        phase = (time.perf_counter() - rig.t0) % 20.0
        if det is None:
            intent = Search()
        elif phase < 8.0:
            intent = Engage(det)
        elif phase < 9.0:
            intent = Combo(BURST, det)
        else:
            intent = None      # stand still, aimed, and let it shoot back
        pad = rig.ctrl.step(state, intent) if intent is not None else rig.ctrl.aim_only(state, det)[0]
        if intent is None and phase > 14.0:
            pad["ly"] = -1.0   # back off so the next engage starts from range
        rig.act(pad, frame, small, state, type(intent).__name__ if intent else "stand")
    return {"frames": rig.saved, "seconds": secs}


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "tagrun":
        rig = Rig(ROOT / "data" / "l1" / "tagrun", native=True, fps=10.0)
        run = lambda: tagrun(rig, float(sys.argv[2]) if len(sys.argv) > 2 else 60.0)  # noqa: E731
    elif what == "aim":
        rig = Rig(ROOT / "data" / "l4" / "aim")
        run = lambda: aim(rig, int(sys.argv[2]) if len(sys.argv) > 2 else 10)  # noqa: E731
    else:
        rig = Rig(ROOT / "data" / "l4" / sys.argv[2])
        run = lambda: prim(rig, sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)  # noqa: E731
    try:
        result = run()
    finally:
        rig.close()
    (rig.out / "result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result))
