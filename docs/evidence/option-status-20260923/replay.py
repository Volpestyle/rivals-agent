"""Replay one recording through one agent/ tree's Tracker, brain and Controller. Run by run.py; stdlib only.

usage: python -B replay.py <code_root> <trial0|plaza30> <feed.json|none> <out.json>

The base tree (holds) and this tree (options) run the same inputs. The kill-feed bit this tree reads is the read on the latest saved frame
at or before the decision's State (feed.py): the loop reads it on the decision's own frame, which was not saved. `none` leaves it unread,
so this tree must then end options only on arrival or loss.

plaza30: the order of docs/evidence/l4/postfreeze30_replay.py. Every row's aim-crop boxes update the tracker, in the camera the recorded
sticks commanded; a decision's whole-frame boxes update it too when that decision's crop was empty; each decision runs after its row's
updates, on the recorded State's HUD fields and the tracker's boxes. The controller steps every row with the latest intent (open loop: the
recorded pixels never saw the replayed sticks).

trial0: burst trial 0 of C:/rivals-agent/data/l4/burst, a pad script, not the brain, which pressed LT at 0.471 s. The tracker takes every
row's boxes, less the kill feed's own box (a finder artifact the outline finder no longer makes: postfreeze30_replay --no-kill-feed).
Decisions run on rows at 10 Hz with the HUD unknown; the burst is committed through brain.commit on the first decision at or
after the trial's burst phase (0.4 s), and the controller steps every row from then.
"""
import bisect
import json
import math
from pathlib import Path
import sys

code_root, which, feed_path, out_path = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3], Path(sys.argv[4])
sys.path.insert(0, str(code_root))
from agent import brain  # noqa: E402
from agent.controller import Controller, _interp  # noqa: E402
from agent.intents import BURST, Combo  # noqa: E402
from agent.state import ENEMY, Detection, State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402

OPTIONS = hasattr(brain, "OPTIONS")   # this tree: observed options. The base: holds (Memory.hold_until)
PLAZA30 = Path(r"C:\rivals-agent\data\l1\plaza30")
TRIAL0 = Path(r"C:\rivals-agent\data\l4\burst")


def feed_reader():
    if feed_path == "none":
        return lambda t: (None, None)
    reads = json.loads(Path(feed_path).read_text())["reads"]
    ts = [r[0] for r in reads]

    def at(t):
        i = bisect.bisect_right(ts, round(t, 4) + 1e-9) - 1   # rows log t to 4 places: a decision's own saved frame can read as
                                                             # later than it (25.0754 against 25.075384) and must still be its own
        return (reads[i][2], reads[i][1]) if i >= 0 else (None, None)   # the read, and the saved frame it was read on
    return at


def label(intent):
    name = type(intent).__name__
    target = getattr(intent, "target", None)
    return name + (f":{target.track}" if target is not None else "")


def state(t, size, dets, coasting, feed, **hud):
    kw = {"kill_feed": feed} if OPTIONS else {}
    return State(t=t, frame=size, detections=list(dets), coasting=tuple(coasting), **hud, **kw)


def record(m, t, intent, feed):
    row = {"t": t, "intent": label(intent), "feed": feed[0], "feed_frame": feed[1]}
    if OPTIONS:
        row["option"] = m.option.to_dict() if m.option is not None else None
        row["stop"] = label(m.stop) if m.stop is not None else None
    else:
        row["hold_until"] = m.hold_until if math.isfinite(m.hold_until) else None
        row["held"] = label(m.intent) if math.isfinite(m.hold_until) else None
    return row


def step(ctrl, st, intent, intent_t, stop):
    return ctrl.step(st, intent, intent_t=intent_t, **({"stop": stop} if OPTIONS and stop is not None else {}))


def recorded_camera(rows, cal):
    """(t, yaw, pitch) per row: the recorded sticks through the controller's measured maps (postfreeze30_replay.recorded_camera)."""
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
    i = bisect.bisect_left([c[0] for c in cams], t)
    if i <= 0:
        return cams[0][1:]
    if i >= len(cams):
        return cams[-1][1:]
    (t0, y0, p0), (t1, y1, p1) = cams[i - 1], cams[i]
    k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return y0 + k * (y1 - y0), p0 + k * (p1 - p0)


def plaza30():
    size = (2560, 1440)
    rows = [json.loads(line) for line in (PLAZA30 / "frames.jsonl").read_text().splitlines()]
    by_t = {r["t"]: i for i, r in enumerate(rows)}
    events = []
    for i, r in enumerate(rows):
        events.append(("aim", r["t"], r["dets"], i))
        if "state" in r:
            src = by_t.get(round(r["state"]["t"], 4))
            boxes = [d["bbox"] for d in r["state"]["detections"]]
            if src is not None and not rows[src]["dets"] and boxes:
                events.append(("wide", r["state"]["t"], boxes, i))
    last = {i: n for n, (_, _, _, i) in enumerate(events)}
    ctrl, tr, m, feed = Controller(), Tracker(), brain.Memory(), feed_reader()
    cams = recorded_camera(rows, ctrl.cal)
    aim, wide, decisions, pads = {}, {}, [], []
    intent = intent_t = stop = None
    for n, (kind, t, boxes, i) in enumerate(events):
        yaw, pitch = camera_at(cams, t - ctrl.cal.latency_s)
        extra = {"clip": (800, 240, 1760, 1200)} if kind == "aim" else {}
        got = tr.update([Detection(ENEMY, tuple(b), 0.9) for b in boxes], t, size, cam=(yaw, pitch, ctrl.cal.focal_1280 * size[0] / 1280),
                        **extra)
        (aim if kind == "aim" else wide)[i] = (got, tuple(tr.coasting))
        if last[i] != n:
            continue
        r = rows[i]
        if "state" in r:
            s = r["state"]
            use = wide[i] if i in wide else aim.get(by_t.get(round(s["t"], 4)), ([], tuple(tr.coasting)))
            base = State.from_dict({**s, "detections": []})
            f = feed(s["t"])
            intent = brain.decide(state(base.t, base.frame, use[0], use[1], f[0], hp=base.hp, max_hp=base.max_hp, webs=base.webs,
                                        abilities=base.abilities), m)
            intent_t, stop = base.t, getattr(m, "stop", None)
            decisions.append({"row": i, **record(m, base.t, intent, f)})
        if intent is not None:
            pad = step(ctrl, State(t=r["t"], frame=size, detections=list(aim[i][0]), coasting=aim[i][1]), intent, intent_t, stop)
            pads.append({"row": i, "t": r["t"], "pad": {**pad, "buttons": list(pad["buttons"])}, "seq": ctrl.seq_name if ctrl.seq else "",
                         "recorded": r["pad"]})
    return decisions, pads


def trial0():
    size = (1280, 720)
    rows = [json.loads(line) for line in (TRIAL0 / "log.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["t"] <= 4.0]
    kill_feed_box = lambda b: (b[0] + b[2]) / 2 > 0.89 * size[0] and (b[1] + b[3]) / 2 < 0.2 * size[1]   # noqa: E731
    ctrl, tr, m, feed = Controller(), Tracker(), brain.Memory(), feed_reader()
    decisions, pads, last_d = [], [], -math.inf
    intent = intent_t = stop = None
    for i, r in enumerate(rows):
        got = tr.update([Detection(ENEMY, tuple(float(v) for v in b), 0.9) for b in r["dets"] if not kill_feed_box(b)], r["t"], size)
        coasting = tuple(tr.coasting)
        if r["t"] - last_d >= 0.09:                                # the loop's 10 Hz: REFLEX_TOL / DECISION_HZ
            last_d, f = r["t"], feed(r["t"])
            st = state(r["t"], size, got, coasting, f[0])
            decided = brain.decide(st, m)
            if intent is None and r["t"] >= 0.4:                  # the trial's burst phase: the pad script started it, so commit it
                target = next(d for d in got if d.track is not None)
                c = Combo(BURST, target)
                intent = brain.commit(m, c, r["t"]) if OPTIONS else brain.commit(m, c, r["t"] + brain.BURST_HOLD_S)
            elif intent is not None:
                intent = decided
            if intent is not None:
                intent_t, stop = r["t"], getattr(m, "stop", None)
                decisions.append({"row": i, **record(m, r["t"], intent, f)})
        if intent is not None:
            pad = step(ctrl, State(t=r["t"], frame=size, detections=got, coasting=coasting), intent, intent_t, stop)
            pads.append({"row": i, "t": r["t"], "pad": {**pad, "buttons": list(pad["buttons"])}, "seq": ctrl.seq_name if ctrl.seq else "",
                         "recorded": r["pad"]})
    return decisions, pads


if __name__ == "__main__":
    decisions, pads = {"plaza30": plaza30, "trial0": trial0}[which]()
    out_path.write_text(json.dumps({"code_root": str(code_root), "which": which, "feed": feed_path, "options": OPTIONS,
                                    "decisions": decisions, "pads": pads}, default=list) + "\n", encoding="utf-8")
