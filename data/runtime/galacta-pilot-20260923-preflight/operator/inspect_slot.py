"""Per-slot native checks, read-only on the run: readiness bin on the first-phase frame, and multi-member body frames.

    python inspect_slot.py <index>

1. Runs the loop's own readers (live tree) on <run>/episode-first-phase.png: range HUD, HP, webs, boxes, height bins.
2. For each fragment-accounting 'inspect' row, draws the union bbox on the nearest saved frame (scaled to that frame's
   size) and writes <slot>/inspect-<row>.jpg for eye inspection. Writes <slot>/inspect.json (mode 'x').
"""
import json
import sys
from pathlib import Path

import cv2

REPO = Path(r"C:\Users\volpe\repos\rivals-agent")
LIVE = Path(r"C:\Users\volpe\repos\rivals-agent-live")
sys.path.insert(0, str(LIVE))
from agent.brain import range_of  # noqa: E402
from agent.loop import default_perception  # noqa: E402
from agent.state import State  # noqa: E402

index = int(sys.argv[1])
slot = next(t for t in json.loads((REPO / "data/benchmarks/galacta-pilot-20260923/schedule.json").read_text("utf-8"))["trials"]
            if t["schedule_index"] == index)
slot_dir = REPO / "data/runtime/galacta-pilot-20260923-preflight/slots" / f"{index:02d}-{slot['policy_role']}"
run = REPO / "data/l1" / slot["planned_run_name"]
p = default_perception()
out = {"slot": index, "planned_bin": slot["spec"]["scenario"], "first_phase": None, "inspected": []}
fp = cv2.imread(str(run / "episode-first-phase.png"))
if fp is not None:
    w, h = p.size(fp)
    hud = p.hud(fp)
    state = State(t=0.0, frame=(w, h), **hud)
    boxes = [{"finder": s, "bbox": [round(v) for v in d.bbox], "h": round((d.bbox[3] - d.bbox[1]) / h, 4), "bin": range_of(d, state)}
             for s, d in [("aim", d) for d in p.aim(fp)] + [("wide", d) for d in p.wide(fp)]]
    out["first_phase"] = {"size": [w, h], "in_range": bool(p.in_range(fp)), "hp": hud.get("hp"), "max_hp": hud.get("max_hp"),
                          "webs": hud.get("webs"), "boxes": boxes}
acc_path = slot_dir / "fragment-accounting.json"
if acc_path.exists():
    for row in json.loads(acc_path.read_text("utf-8"))["inspect"]:
        img = cv2.imread(str(run / row["nearest_saved_frame"]))
        sx = img.shape[1] / 2560.0
        x1, y1, x2, y2 = (int(v * sx) for v in row["bbox"])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)
        name = f"inspect-{row['row']}.jpg"
        cv2.imwrite(str(slot_dir / name), img)
        out["inspected"].append({**row, "drawn_on": row["nearest_saved_frame"], "file": name})
with (slot_dir / "inspect.json").open("x", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, indent=2)
    f.write("\n")
print(json.dumps({"planned": out["planned_bin"], "first_phase": out["first_phase"] and {k: out["first_phase"][k] for k in ("in_range", "hp", "webs")},
                  "fp_boxes": out["first_phase"] and [(b["finder"], b["bbox"], b["h"], b["bin"]) for b in out["first_phase"]["boxes"]],
                  "inspected": [i["file"] for i in out["inspected"]]}))
