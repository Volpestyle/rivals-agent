"""Replay the postfreeze30 trace (the first supervised post-freeze run: 30 s, ~50 Hz) through a tracker and the scripted brain, in live
order, and score it against labels fixed by eye on the saved frames. Stdlib; reads data/l1/postfreeze30/frames.jsonl.

  python docs/evidence/l4/postfreeze30_replay.py [--no-kill-feed] [TRACKER.py ...]   # default: agent/tracker.py
  uv run --group perception python docs/evidence/l4/postfreeze30_replay.py --refind OUTLINE.py [TRACKER.py]
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
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agent import brain  # noqa: E402
from agent.state import ENEMY, Detection, State  # noqa: E402

RUN = Path("data/l1/postfreeze30")
SIZE = (2560, 1440)
KILL_FEED_BOX = [2319, 128, 2426, 247]


def label(t, b):
    cx, cy, h = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[3] - b[1]
    if cx > 2300 and cy < 260:
        return "killfeed"
    if t < 13.8:
        return "door"
    if t >= 15.3 and h >= 120:
        return "luna"
    return "other"


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
    tr, m, aim, wide, ticks, cost, intent = mod.Tracker(), brain.Memory(), {}, {}, [], [], None
    last = {i: n for n, (_, _, _, i) in enumerate(events)}
    for n, (kind, t, boxes, i) in enumerate(events):
        c0 = time.perf_counter()
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
        tgt = m.target
        acting = intent is not None and type(intent).__name__ not in ("Search", "Idle")   # the target is only what the pad acts on while engaging
        ticks.append((r["t"], None if tgt is None or not acting else label(m.target_t, tgt.bbox),
                      tgt is not None and any(d.track == tgt.track for d in aim[i][0]), None if tgt is None else tgt.track))
    return rows, aim, wide, ticks, cost


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
            "update_ms_p50": round(c[len(c) // 2], 4), "update_ms_p95": round(c[int(0.95 * len(c))], 4)}


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
    if "--refind" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--refind"]
        secs, _ = refind(*rest)
        print(json.dumps({"finder": rest[0], "target_seconds_by_label": secs}))
        sys.exit(0)
    args = sys.argv[1:]
    nokf = "--no-kill-feed" in args
    for path in [a for a in args if a != "--no-kill-feed"] or ["agent/tracker.py"]:
        print(json.dumps(report(path, nokf)))
