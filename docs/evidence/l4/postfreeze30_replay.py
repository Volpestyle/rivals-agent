"""Replay the postfreeze30 trace (the first supervised post-freeze run: 30 s, ~50 Hz) through a tracker and the scripted brain, in live
order, and score it against labels fixed by eye on the saved frames. Stdlib; reads DIR/frames.jsonl (default data/l1/postfreeze30); the
labels are per run (LABELS), a run without its own gets the generic ones. The trace replay also steps the controller each tick with the
brain's intent and reports STALLS: engaged on a target with no stick, no move and no press.

  python docs/evidence/l4/postfreeze30_replay.py [--run DIR] [--no-kill-feed] [TRACKER.py ...]   # default: postfreeze30, agent/tracker.py
  uv run --group perception python docs/evidence/l4/postfreeze30_replay.py [--run DIR] --refind OUTLINE.py [TRACKER.py]
      # re-run a finder (perception/outline.py, or an older copy) on the 273 saved frames (~9 Hz) instead of the trace's recorded boxes

Live order: every tick's aim-crop boxes update the tracker; when that tick's crop was empty, the decision's whole-frame search updates it
too; each decision runs after its row's updates. A tick counts toward a target only while the brain's intent engages (not Search or
Idle): that is what the pad acts on. Labels (docs/lanes/tracker.md): every box before t 13.8 s is the spawn room's lime glass
door; the kill feed's box is (2319,128)-(2426,247), identical in all 68 sightings; after t 15.3 s a box 120 px or taller is the Luna Snow
bot. --no-kill-feed drops that box, which the finder no longer makes (perception/outline.py KILL_FEED).
"""
import collections
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agent import brain  # noqa: E402
from agent.state import ENEMY, Detection, State  # noqa: E402

RUN = Path("data/l1/postfreeze30")
# Labels fixed by eye on each run's saved frames (docs/lanes/tracker.md). The kill feed's box is the same place on every run.
LABELS = {
    "postfreeze30": dict(door=[(0.0, 13.8)], bot_after=15.3, bot_h=120),  # the spawn door until 13.8 s; the Luna Snow bot from 15.3 s
    "trackerlive30": dict(door=[(0.0, 4.5)], bot_after=0.0, bot_h=100),   # the spawn room until 4.5 s; then a box 100 px+ is the bot, a
                                                                          # smaller one the downed bot (38 x 43) or a stray (22 x 31)
    "stall30": dict(door=[(0.0, 3.5), (11.6, 15.4)], junk=[(22.0, 25.2)], bot_after=3.5, bot_h=60),
    # the spawn room until 3.5 s (at 3.7 s he is outside, and a bot is in view); the door again from the plaza side 11.6-15.4 s (ids 45 46 48); a lit glass dome in the ceiling 22-25 s
    # (id 98); otherwise a box 60 px+ is a bot (far ones on the plaza at 4.4-6.8 s are 60-160 px)
    "handoff30": dict(door=[(0.0, 3.95)], bot_after=3.95, bot_h=60),
    "reach30": dict(door=[(3.9, 5.0), (14.8, 19.8), (22.7, 25.5, 700, 2560), (28.4, 29.6)], bot_after=5.0, bot_h=60),
    # the plaza side of the door in four windows (docs/lanes/l4-controller.md, reach30 forward walks and targets); in 22.7-25.5 s only right
    # of x 700, where the door's edge is while the Luna bot stands left of the crop (id 44, x 327-600)
    # the plaza side of the door at the left until 3.9 s; then a box 60 px+ is a bot; the 30-42 px boxes are robot dummies far down the
    # shooting lane (native frames 000096 and the small-box sheet), labelled "small" below
}
SMALL_H = 47          # px at 1440p: brain.RANGES.reach_h (40 m). A box this size or less outside the door and junk windows is "small": on the
                      # four runs mostly the lane's dummies ~45 m off, some scenery; past the 40 m engagement cap either way
SIZE = (2560, 1440)
KILL_FEED_BOX = [2319, 128, 2426, 247]


def label(t, b):
    cx, cy, h = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[3] - b[1]
    lab = LABELS.get(RUN.name, dict(bot_after=0.0, bot_h=100))
    if cx > 2300 and cy < 260:
        return "killfeed"
    if any(w[0] <= t < w[1] and (len(w) == 2 or w[2] <= cx < w[3]) for w in lab.get("door", ())):   # (from, to[, x from, x to])
        return "door"
    if any(lo <= t < hi for lo, hi in lab.get("junk", ())):
        return "other"
    if t >= lab["bot_after"] and h >= lab["bot_h"]:
        return "luna"                                  # the run's real bot
    return "small" if h <= SMALL_H else "other"


def load(no_kill_feed=False):
    """The trace rows, and the tracker updates in live order: (kind, t, boxes, row index)."""
    rows = [json.loads(line) for line in (RUN / "frames.jsonl").read_text().splitlines()]
    if no_kill_feed:
        for r in rows:
            r["dets"] = [b for b in r["dets"] if [round(v) for v in b] != KILL_FEED_BOX]
            if "state" in r:
                r["state"]["detections"] = [d for d in r["state"]["detections"] if [round(v) for v in d["bbox"]] != KILL_FEED_BOX]
    by_t = {r["t"]: r for r in rows}
    events = []
    for i, r in enumerate(rows):
        events.append(("aim", r["t"], r["dets"], i))
        if "state" in r:
            s = r["state"]
            src = by_t.get(round(s["t"], 4))              # rows carry t to 4 places, the State at full precision
            boxes = [d["bbox"] for d in s["detections"]]
            if src is not None and not src["dets"] and boxes:
                events.append(("wide", s["t"], boxes, i))
    return rows, events


def tracker_module(path):
    spec = importlib.util.spec_from_file_location(f"trk{abs(hash(path))}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def replay(mod, no_kill_feed=False):
    rows, events = load(no_kill_feed)
    by_t = {r["t"]: i for i, r in enumerate(rows)}
    import inspect
    from agent.controller import Controller
    ctrl, intent, intent_t, pads, walks = Controller(), None, None, [], []
    measured = [None]                                      # the tracker id of the box the controller measured on this step, any version
    own_measure = ctrl._measure
    def spy(det, state):
        measured[0] = det.track
        return own_measure(det, state)
    ctrl._measure = spy
    takes_t = "intent_t" in inspect.signature(ctrl.step).parameters
    tr, m, aim, wide, ticks, cost = mod.Tracker(), brain.Memory(), {}, {}, [], []
    with_cam = "cam" in inspect.signature(tr.update).parameters
    cams = recorded_camera(rows, ctrl.cal)                  # what the LIVE sticks commanded: the replay's own controller is open loop
    last = {i: n for n, (_, _, _, i) in enumerate(events)}
    for n, (kind, t, boxes, i) in enumerate(events):
        c0 = time.perf_counter()
        if with_cam:
            yaw, pitch = camera_at(cams, t - ctrl.cal.latency_s)
            extra = {"clip": (800, 240, 1760, 1200)} if kind == "aim" and "clip" in inspect.signature(tr.update).parameters else {}
            got = tr.update([Detection(ENEMY, tuple(b), 0.9) for b in boxes], t, SIZE, cam=(yaw, pitch, ctrl.cal.focal_1280 * SIZE[0] / 1280), **extra)
        else:
            got = tr.update([Detection(ENEMY, tuple(b), 0.9) for b in boxes], t, SIZE)
        cost.append((time.perf_counter() - c0) * 1e3)
        (aim if kind == "aim" else wide)[i] = (got, tuple(tr.coasting))
        if last[i] != n:
            continue
        r = rows[i]
        if "state" in r:
            s = r["state"]
            src = by_t.get(round(s["t"], 4))
            use = wide[i] if i in wide else aim.get(src, ([], tuple(tr.coasting)))
            base = State.from_dict({**s, "detections": []})
            intent = brain.decide(State(t=base.t, frame=base.frame, hp=base.hp, max_hp=base.max_hp, webs=base.webs, abilities=base.abilities,
                                        detections=list(use[0]), coasting=use[1]), m)
            intent_t = base.t
        if intent is not None:
            measured[0] = None
            st = State(t=r["t"], frame=SIZE, detections=list(aim[i][0]), coasting=aim[i][1])
            pad = ctrl.step(st, intent, intent_t=intent_t) if takes_t else ctrl.step(st, intent)
            pads.append((r["t"], type(intent).__name__ not in ("Search", "Idle"), pad))
            if pad["ly"] > 0 and type(intent).__name__ == "Engage" and ctrl.track is not None:
                held = getattr(intent, "target", None)
                walks.append((r["t"], ctrl.track.h, None if m.target is None else label(m.target_t, m.target.bbox),
                              measured[0] is not None and held is not None and held.track is not None and measured[0] != held.track))
        tgt = m.target
        acting = intent is not None and type(intent).__name__ not in ("Search", "Idle")   # the target is only what the pad acts on while engaging
        ticks.append((r["t"], None if tgt is None or not acting else label(m.target_t, tgt.bbox),
                      tgt is not None and any(d.track == tgt.track for d in aim[i][0]), None if tgt is None else tgt.track))
    replay.pads, replay.walks = pads, walks
    return rows, aim, wide, ticks, cost


def recorded_camera(rows, cal):
    """(t, yaw, pitch) per tick, integrating the sticks the run actually sent through the controller's measured maps."""
    from agent.controller import _interp
    out, cam, last = [], [0.0, 0.0], None
    for r in rows:
        if last is not None:
            dt = min(0.1, r["t"] - last[0])
            cam = [cam[0] + math.copysign(_interp(abs(last[1]), cal.yaw_map), last[1]) * dt,
                   cam[1] + math.copysign(_interp(abs(last[2]), cal.pitch_map), last[2]) * dt]
        out.append((r["t"], cam[0], cam[1]))
        last = (r["t"], r["pad"]["rx"], r["pad"]["ry"])
    return out


def camera_at(cams, t):
    import bisect
    i = bisect.bisect_left([c[0] for c in cams], t)
    if i <= 0:
        return cams[0][1:]
    if i >= len(cams):
        return cams[-1][1:]
    (t0, y0, p0), (t1, y1, p1) = cams[i - 1], cams[i]
    k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return y0 + k * (y1 - y0), p0 + k * (p1 - p0)


def handoffs(rows, aim, ticks):
    """One row per hold the aim crop had not seen when it began: (t the crop first shows a bot while it is still held, held id, the crop's
    bot ids then, kept?). A hold the crop never sees, or that ends first, has no row."""
    out, held, armed = [], None, False
    for (t, lab, vis, tid), i in zip(ticks, sorted(aim)):
        if tid != held:
            held, armed = tid, tid is not None and lab == "luna" and not vis
        crop = [d.track for d in aim[i][0] if label(t, d.bbox) == "luna"]
        if armed and crop:
            out.append((round(t, 2), held, crop, held in crop))
            armed = False
    return out


def live_handoffs(rows, aim, wide):
    """The run's own hand-offs, by its recorded boxes: every time the live brain's target was only in the whole-frame search and the aim
    crop then saw it under ANOTHER live id. For each: the replay's id of the last whole-frame box and of the first crop box (kept if equal)."""
    out, held, last_wide = [], None, None
    for i, r in enumerate(rows):
        tg = r.get("target")
        if tg != held:
            held, last_wide = tg, None
        if tg is None:
            continue
        if "state" in r:
            box = next((d["bbox"] for d in r["state"]["detections"] if d.get("track") == tg), None)
            if box is not None and tg not in r["ids"]:
                last_wide = (i, box)
        if last_wide is not None and r["ids"] and tg not in r["ids"]:
            wi, wb = last_wide
            first = r["dets"][0]
            rid = lambda got, b: next((d.track for d in got if [round(v) for v in d.bbox] == [round(v) for v in b]), None)   # noqa: E731
            was = rid(wide.get(wi, ([], ()))[0], wb) or rid(aim.get(wi, ([], ()))[0], wb)
            now = rid(aim[i][0], first)
            out.append((round(r["t"], 2), tg, r["ids"][0], was, now, was is not None and was == now))
            last_wide = None
    return out


def stalls(pads, min_s=0.5):
    """Runs of ticks engaging a target while the pad does nothing at all (no stick, no move, no press): (start, seconds)."""
    out, start, last = [], None, None
    for t, engaging, p in pads:
        idle = engaging and max(abs(p["rx"]), abs(p["ry"]), abs(p["lx"]), abs(p["ly"]), p["lt"], p["rt"]) < 0.02 and not p["buttons"]
        if idle and start is None:
            start = t
        if not idle and start is not None:
            out.append((start, t - start))
            start = None
        last = t
    if start is not None:
        out.append((start, last - start))
    return [(round(a, 2), round(b, 2)) for a, b in out if b >= min_s]


def report(path, no_kill_feed=False):
    rows, aim, wide, ticks, cost = replay(tracker_module(path), no_kill_feed)
    luna_ids, switches, prev = collections.Counter(), 0, None
    for i, (got, _) in sorted(aim.items()):
        luna = [d for d in got if label(rows[i]["t"], d.bbox) == "luna"]
        for d in luna:
            luna_ids[d.track] += 1
        if luna:
            top = max(luna, key=lambda d: d.bbox[3] - d.bbox[1]).track
            switches += prev is not None and top != prev
            prev = top
    held = [x for x in ticks if x[1] is not None]
    on_luna = [x for x in ticks if x[1] == "luna"]
    why = collections.Counter()
    for t, lab, vis, _ in on_luna:
        i = next(k for k, r in enumerate(rows) if r["t"] == t)
        here = [d for d in aim[i][0] if label(t, d.bbox) == "luna"]
        why["visible" if vis else "Luna under another id" if here else "nothing Luna-sized in the crop"] += 1
    c = sorted(cost)
    return {"tracker": path, "no_kill_feed": no_kill_feed,
            "ids": len({d.track for g, _ in list(aim.values()) + list(wide.values()) for d in g}),
            "luna_ids": len(luna_ids), "luna_switches": switches,
            "target_ticks": dict(collections.Counter(x[1] for x in ticks)),
            "held_id_visible": round(sum(x[2] for x in held) / max(len(held), 1), 3),
            "held_id_visible_on_luna": round(sum(x[2] for x in on_luna) / max(len(on_luna), 1), 3),
            "luna_target_ticks_by_cause": dict(why), "luna_target_ids": len({x[3] for x in on_luna}),
            "update_ms_p50": round(c[len(c) // 2], 4), "update_ms_p95": round(c[int(0.95 * len(c))], 4),
            "engaged_s": {k: round(v, 2) for k, v in engaged_seconds(ticks).items()},
            "engaged_active_s": {k: round(v, 2) for k, v in engaged_seconds(ticks, replay.pads).items()},
            "stalls_over_0.5s": stalls(replay.pads), "handoffs": handoffs(rows, aim, ticks),
            "engage_walk_ticks_by_label": dict(collections.Counter(w[2] for w in replay.walks)),
            "engage_walk_min_crop_h": min((w[1] for w in replay.walks), default=None),
            "engage_walk_ticks_on_another_id": sum(w[3] for w in replay.walks),
            "live_handoffs(t, live held, live crop id, replay id then, replay id now, kept)": live_handoffs(rows, aim, wide)}


def engaged_seconds(ticks, pads=None):
    """Seconds engaging each label; with `pads`, only the ticks on which the pad did something (a stick, a move or a press)."""
    busy = None if pads is None else {t: max(abs(p["rx"]), abs(p["ry"]), abs(p["lx"]), abs(p["ly"]), p["lt"], p["rt"]) >= 0.02 or bool(p["buttons"])
                                      for t, _, p in pads}
    secs = collections.Counter()
    for (t0, lab, _, _), (t1, _, _, _) in zip(ticks, ticks[1:]):
        if lab is not None and (busy is None or busy.get(t0)):
            secs[lab] += t1 - t0
    return secs


def refind(outline_path, tracker_path="agent/tracker.py", brain_decide=None):
    """Finder -> tracker -> brain on the saved frames: the aim crop (passing where it sits in the frame, if the finder takes that), the
    whole frame when the crop is empty; one decision per saved frame (~9 Hz, the loop decides at 10 Hz), the HUD fields from the nearest
    recorded State. Returns seconds of brain target by label (counted only while the intent engages: Search and Idle act on no target),
    and the per-frame target labels."""
    import inspect
    from dataclasses import replace
    import cv2
    fnd = tracker_module(outline_path)
    crop_kw = "origin" in inspect.signature(fnd.find_enemies).parameters
    rows = [json.loads(line) for line in (RUN / "frames.jsonl").read_text().splitlines()]
    states = [r["state"] for r in rows if "state" in r]
    tr, m, out, last_t = tracker_module(tracker_path).Tracker(), brain.Memory(), [], None
    for r in rows:
        if "file" not in r:
            continue
        f = cv2.imread(str(RUN / r["file"]))
        kw = {"origin": (800, 240), "frame": SIZE} if crop_kw else {}
        dets = [replace(d, bbox=(d.bbox[0] + 800, d.bbox[1] + 240, d.bbox[2] + 800, d.bbox[3] + 240))
                for d in fnd.find_enemies(f[240:1200, 800:1760], scale=2.0, **kw)] or fnd.find_enemies(f, scale=2.0)
        got = tr.update(dets, r["t"], SIZE)
        s = min(states, key=lambda x: abs(x["t"] - r["t"]))
        base = State.from_dict({**s, "detections": []})
        intent = (brain_decide or brain.decide)(State(t=r["t"], frame=SIZE, hp=base.hp, max_hp=base.max_hp, webs=base.webs,
                                             abilities=base.abilities, detections=got, coasting=tuple(tr.coasting)), m)
        tgt, acting = m.target, type(intent).__name__ not in ("Search", "Idle")
        out.append((r["t"], None if tgt is None or not acting else label(m.target_t, tgt.bbox), None if tgt is None else tgt.track,
                    tgt is not None and any(d.track == tgt.track for d in got)))
    secs = collections.Counter()
    for (t0, lab, _, _), (t1, _, _, _) in zip(out, out[1:]):
        secs[lab] += t1 - t0
    return {k: round(v, 2) for k, v in secs.items()}, out


if __name__ == "__main__":
    if "--run" in sys.argv:
        k = sys.argv.index("--run")
        RUN = Path(sys.argv[k + 1])
        del sys.argv[k:k + 2]
    if "--refind" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--refind"]
        secs, _ = refind(*rest)
        print(json.dumps({"finder": rest[0], "target_seconds_by_label": secs}))
        sys.exit(0)
    args = sys.argv[1:]
    nokf = "--no-kill-feed" in args
    for path in [a for a in args if a != "--no-kill-feed"] or ["agent/tracker.py"]:
        print(json.dumps(report(path, nokf)))
