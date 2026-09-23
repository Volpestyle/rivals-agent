"""Can a width/height limit refuse the fused two-bot box without refusing a real single bot? (VUH-1356)

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/flat-target-20260923/thresholds.py <measure-out-dir>

<measure-out-dir> is measure_aspect.py's output (boxes.jsonl). This script:

1. replays the calibration take's frames5/0301-0309 (5 fps) through the aim crop (agent.loop's call), one Tracker and the
   scripted brain.gate, and records the selected target per tick. It then steps HEAD's Controller in range-skill mode on
   that target: one decision per tick, `no_new_start`, ammo 5, valid for 0.1 s. That shows what the executor does with the
   fused box today. The controller is the working tree's agent/controller.py, which this task did not change.
2. scores candidate limits: of the seven fused ticks, of the 39 labelled single-bot anchors of the 2026-09-23 take (v3,
   each target-agreed), of every other selected target, and of every range step's target box on Galacta slot 4
   (galacta-pilot-20260922-04-learned, the fragment-repair replay's recording) - how many a limit `w / h > limit` refuses.

Writes thresholds.json next to this file.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from agent import brain  # noqa: E402
from agent.controller import Controller  # noqa: E402
from agent.intents import RangeSkill, RangeSkillResources  # noqa: E402
from agent.loop import aim_window  # noqa: E402
from agent.state import State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402
from perception.outline import find_enemies  # noqa: E402

cv2.setNumThreads(1)
W, H = 2560, 1440
FRAMES5 = ROOT / "data/hud/calib-20260923/frames5"
SLOT4 = ROOT / "data/l1/galacta-pilot-20260922-04-learned/frames.jsonl"
LIMITS = (1.9, 2.0, 2.2, 2.3, 2.5, 3.0, 3.5, 4.0, 4.5)


def aspect(b):
    return (b[2] - b[0]) / max(b[3] - b[1], 1e-9)


def frames5_replay():
    tracker, memory, ctrl, out = Tracker(), brain.Memory(), Controller(), []
    for i, n in enumerate(range(301, 310)):
        f = cv2.imread(str(FRAMES5 / f"{n:04d}.jpg"))
        x0, y0, x1, y1 = aim_window((W, H))
        aim = [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
               for d in find_enemies(f[y0:y1, x0:x1], scale=2.0, origin=(x0, y0), frame=(W, H))]
        t = i * 0.2
        dets = tracker.update(aim, t, (W, H), clip=(x0, y0, x1, y1)) if aim else tracker.update(find_enemies(f, scale=2.0), t, (W, H))
        state = State(t=t, frame=(W, H), detections=dets, coasting=tuple(tracker.coasting))
        _, target = brain.gate(state, memory)
        row = dict(frame=f"{n:04d}", boxes=[[round(v) for v in d.bbox] for d in dets],
                   target=target and [round(v) for v in target.bbox], target_aspect=target and round(aspect(target.bbox), 3))
        if target is not None:
            pad = ctrl.step(state, RangeSkill(target, "no_new_start", i, t + 0.1, RangeSkillResources(5, t)), intent_t=t)
            trace = ctrl.range_skill_trace
            row.update(reason=trace["reason"], stable=ctrl.stable, ly=pad["ly"], rx=round(pad["rx"], 3), ry=round(pad["ry"], 3))
        out.append(row)
    return out


def main(measure_dir):
    rows = [json.loads(line) for line in (Path(measure_dir) / "boxes.jsonl").read_text().splitlines()]
    replay = frames5_replay()
    fused = [r for r in replay if r["target"] and r["target_aspect"] > 2.0]       # 0303-0309, inspected: one box on two Lunas
    labelled = [r for r in rows if r["src"] == "labelled"]
    ids = {r["frame"] for r in fused}
    others = [r for r in rows if r["src"] == "target" and not (r["rec"] == "frames5" and r["id"] in ids)]
    slot4 = []
    for r in map(json.loads, SLOT4.read_text().splitlines()):
        trace = r.get("range_skill_trace")
        if trace and trace.get("event") == "step" and "dets" in r:
            slot4 += [aspect(b) for b, k in zip(r["dets"], r["ids"]) if k == trace.get("target_id")]
    table = [dict(limit=lim,
                  fused_refused=sum(r["target_aspect"] > lim for r in fused), fused=len(fused),
                  labelled_refused=sum(r["aspect"] > lim for r in labelled), labelled=len(labelled),
                  labelled_refused_ids=[r["id"].split("/")[0] for r in labelled if r["aspect"] > lim],
                  other_targets_refused=sum(r["aspect"] > lim for r in others), other_targets=len(others),
                  slot4_refused=sum(a > lim for a in slot4), slot4=len(slot4))
             for lim in LIMITS]
    out = dict(frames5_0301_0309=replay, table=table, slot4_target_aspect_max=round(max(slot4), 3),
               labelled_aspects=sorted((round(r["aspect"], 3), r["id"].split("/")[0]) for r in labelled))
    (HERE / "thresholds.json").write_text(json.dumps(out, indent=1))
    for r in replay:
        print(r["frame"], r["target"], r["target_aspect"], r.get("reason"), r.get("stable"), r.get("ly"), r.get("rx"))
    for t in table:
        print(t["limit"], f"fused {t['fused_refused']}/{t['fused']}", f"labelled {t['labelled_refused']}/{t['labelled']}",
              t["labelled_refused_ids"], f"others {t['other_targets_refused']}/{t['other_targets']}", f"slot4 {t['slot4_refused']}/{t['slot4']}")


if __name__ == "__main__":
    main(sys.argv[1])
