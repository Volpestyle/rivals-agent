"""The review's conflict scenarios (tracker-review S0-S6) through one agent/ tree: real Tracker -> State -> Controller. Run by run.py.

usage: python -B scenarios.py <code_root> <out.json>
Each arms ARM_FRAMES ticks on the target alone (live-like: conf .9, distance None), then steps one tick of `pieces` with a `start`
request. A tree whose Tracker has `observe` passes its witness, as the loop does in range mode; HEAD has none and uses `update`.
"""
from dataclasses import replace
import json
from pathlib import Path
import sys

code_root, out_path = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
sys.path.insert(0, str(code_root))
from agent.controller import ARM_FRAMES, Controller  # noqa: E402
from agent.intents import RangeSkill, RangeSkillResources  # noqa: E402
from agent.state import Detection, ENEMY, State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402

E = lambda box: Detection(ENEMY, tuple(float(v) for v in box), .9)          # noqa: E731
F720, F1440 = (1280, 720), (2560, 1440)
WHOLE = E((1047, 564, 1521, 1090))
SCENARIOS = {
    "S0 one whole body (control)": (F720, E((600, 260, 680, 460)), [E((600, 260, 680, 460))]),
    "S1 native d53 reflex fragments (row 290)": (F1440, WHOLE, [E((1376, 650, 1509, 858)), E((1140, 610, 1223, 817)),
                                                               E((1154, 892, 1234, 1091)), E((1451, 931, 1521, 969))]),
    "S1b native d53 decision fragments": (F1440, WHOLE, [E((1140, 610, 1223, 815)), E((1156, 892, 1235, 1091)),
                                                         E((1376, 650, 1479, 731)), E((1450, 762, 1509, 859)), E((1451, 931, 1521, 969))]),
    "S2 smaller bot inside a near bot (lane residual)": (F1440, E((1000, 400, 1250, 1000)),
                                                         [E((1000, 400, 1250, 1000)), E((1030, 450, 1155, 750))]),
    "S3 smaller bot stacked on the target's head": (F720, E((600, 380, 680, 580)), [E((600, 380, 680, 580)), E((610, 270, 660, 375))]),
    "S4 lane hole: two 250x200 boxes 10 px apart": (F1440, E((1100, 300, 1350, 500)),
                                                    [E((1100, 300, 1350, 500)), E((1100, 510, 1350, 710))]),
    "S5 far small body alone (control)": (F720, E((630, 350, 640, 370)), [E((630, 350, 640, 370))]),
    "S5b two stacked beyond-reach boxes": (F720, E((630, 350, 640, 370)), [E((630, 350, 640, 370)), E((631, 372, 639, 388))]),
    "S5c two stacked beyond-reach boxes, other way up": (F720, E((630, 350, 640, 370)), [E((630, 350, 640, 370)), E((631, 332, 639, 348))]),
}


def run(frame, whole, pieces):
    tracker, c = Tracker(), Controller()
    for i in range(ARM_FRAMES):
        t = i * .02
        raw = tracker.update([whole], t, frame)
        c.step(State(t, frame, detections=raw), RangeSkill(raw[0], "no_new_start", i, t + .1, RangeSkillResources(5, t)), intent_t=t)
    t, kw = ARM_FRAMES * .02, {}
    if hasattr(tracker, "observe"):
        snap = tracker.observe(pieces, t, frame)
        raw, kw["tracking_observation"] = list(snap.raw), snap
    else:
        raw = tracker.update(pieces, t, frame)
    pad = c.step(State(t, frame, detections=raw, coasting=tuple(tracker.coasting)),
                 RangeSkill(replace(whole, track=1), "start", 100, t + .1, RangeSkillResources(5, t)), intent_t=t, **kw)
    trace = c.range_skill_trace
    return {"ids": [d.track for d in raw], "reason": trace["reason"], "lt": pad["lt"], "ly": pad["ly"],
            "body_observation": trace.get("body_observation")}


def s6():
    """The target expired (not held, not coasting); the crop holds only another bot."""
    tracker, c = Tracker(), Controller()
    for i in range(ARM_FRAMES):
        t = i * .02
        raw = tracker.update([E((600, 260, 680, 460))], t, F720)
        c.step(State(t, F720, detections=raw), RangeSkill(raw[0], "no_new_start", i, t + .1, RangeSkillResources(5, t)), intent_t=t)
    kw = {}
    if hasattr(tracker, "observe"):
        snap = tracker.observe([E((100, 100, 140, 200))], 3.0, F720)
        raw, kw["tracking_observation"] = list(snap.raw), snap
    else:
        raw = tracker.update([E((100, 100, 140, 200))], 3.0, F720)
    c.step(State(3.0, F720, detections=raw, coasting=tuple(tracker.coasting)),
           RangeSkill(replace(E((600, 260, 680, 460)), track=1), "start", 100, 3.1, RangeSkillResources(5, 3.0)), intent_t=3.0, **kw)
    return {"reason": c.range_skill_trace["reason"]}


def chain(target, intruder):
    """Review T3: a smaller bot appears inside the target's box after 6 ticks and walks right 4 px/tick (60 Hz, 1440p), a start proposed
    every tick. The tracker keeps both under id 1."""
    tracker, c, starts, widths, refused_from = Tracker(), Controller(), [], [], None
    on = lambda b: b[0] <= 1280 <= b[2] and b[1] <= 720 <= b[3]                  # noqa: E731
    for i in range(66):
        t, k = i / 60, max(0, i - 6)
        walker = (intruder[0] + 4 * k, intruder[1], intruder[2] + 4 * k, intruder[3])
        boxes = [E(target)] if i < 6 else [E(target), E(walker)]
        kw = {}
        if hasattr(tracker, "observe"):
            snap = tracker.observe(boxes, t, F1440)
            raw, kw["tracking_observation"] = list(snap.raw), snap
        else:
            raw = tracker.update(boxes, t, F1440)
        c.step(State(t, F1440, detections=raw, coasting=tuple(tracker.coasting)),
               RangeSkill(replace(E(target), track=1), "start", i, t + .1, RangeSkillResources(5, t)), intent_t=t, **kw)
        trace = c.range_skill_trace
        body = trace.get("body_observation")
        if i >= 6:
            widths.append(body and body["bbox"][2] - body["bbox"][0])
            if trace["accepted"]:
                starts.append({"tick": k, "crosshair_on": "target" if on(target) else "second bot" if on(walker) else "neither",
                               "union": body and list(body["bbox"])})
            if refused_from is None and trace["reason"] == "target_missing_or_ambiguous" and widths[-1] is None and k > 0:
                refused_from = k
    return {"accepted_starts_with_second_bot_present": starts, "max_union_width": max((w for w in widths if w), default=None),
            "target_width": target[2] - target[0], "refused_from_tick": refused_from}


out = {name: run(*spec) for name, spec in SCENARIOS.items()}
out["S6 target gone, another bot in the crop"] = s6()
out["T3a second bot walks out of a near target"] = chain((1150, 420, 1400, 1020), (1300, 650, 1395, 950))
out["T3b ... across the crosshair, target left of it"] = chain((950, 420, 1200, 1020), (1100, 650, 1195, 950))
out_path.write_text(json.dumps(out, default=list) + "\n", encoding="utf-8")
