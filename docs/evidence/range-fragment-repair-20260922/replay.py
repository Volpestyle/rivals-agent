"""Replay Galacta slot 4's recorded reflex ticks through one agent/ tree's Tracker and Controller. Run by run.py.

usage: python -B replay.py <code_root> <legacy|observe> <out.json>
  legacy : the recorded boxes and tracker ids, Controller.step with no witness (the HEAD contract)
  observe: a fresh Tracker.observe over the id-stripped recorded boxes (the loop's cam and aim-crop clip), its witness passed to step.
           The tracker's camera is the recording's: a second Controller steps the legacy inputs (which reproduce every recorded pad,
           run.py asserts it) and its commanded-camera model places the boxes. The pixels were taken under that camera; the replayed
           controller's own aim, which differs once it stops refusing, never turned it (open loop).

Pure: no model, perception, video decoder, Loop, Live or pad. Reads frames.jsonl only. Reflex rows log integer-rounded boxes and no
cls/conf/plate/distance, so each reflex box is rebuilt as ENEMY, conf .9 (the outline finder's), distance None (it never sets one).
Each intent is rebuilt from its logged decision: the target is the first same-id hostile in the decision State (brain._pick_target),
with the logged request, id, valid_until, resources, intent_t and execution_t. Rows with no range trace step Idle.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

code_root, mode, out_path = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, str(code_root))
from agent.controller import Controller  # noqa: E402
from agent.intents import Idle, RangeSkill, RangeSkillResources  # noqa: E402
from agent.state import Detection, ENEMY, TARGET, State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402

RUN = Path.cwd() / "data/l1/galacta-pilot-20260922-04-learned/frames.jsonl"
LOG_SHA = "1eadcb5efba274883e103ebfae5e5f62c4f720008c75c3ea5ec226baf9e071a6"
FRAME = (2560, 1440)
CROP = 960                                     # agent.loop.CROP; aim_window below is agent.loop's, so the Loop is never imported


def aim_window(size, crop=CROP):
    w, h = size
    side = round(crop * h / 1440)
    x0, y0 = (w - side) // 2, (h - side) // 2
    return x0, y0, x0 + side, y0 + side


def main():
    data = RUN.read_bytes()
    assert sha256(data).hexdigest() == LOG_SHA
    rows = [json.loads(line) for line in data.decode().splitlines()]
    decisions = {r["d"]: r for r in rows if "state" in r and "decision_trace" in r}
    ctrl, tracker, out = Controller(), Tracker(), []
    shown = Controller() if mode == "observe" else ctrl          # whose commanded camera the recorded pixels were taken under
    for i, r in enumerate(rows):
        if "dets" not in r:
            continue                                                   # executor events: no reflex step
        t, trace = r["observation_t"], r.get("range_skill_trace")
        boxes = [tuple(float(v) for v in b) for b in r["dets"]]
        kw, role = {}, None
        legacy = State(t=t, frame=FRAME, detections=[Detection(ENEMY, b, .9, track=k) for b, k in zip(boxes, r["ids"])],
                       coasting=tuple(r["coasting"]))
        if mode == "observe":
            at = shown._cam_at(t - shown.cal.latency_s)
            cam = (at[0], at[1], shown.cal.focal_1280 * FRAME[0] / 1280.0)
            snap = tracker.observe([Detection(ENEMY, b, .9) for b in boxes], t, FRAME, cam=cam, clip=aim_window(FRAME))
            dets, coasting, kw["tracking_observation"] = list(snap.raw), snap.coasting, snap
            body = next((b for b in snap.bodies if trace and b.track == trace.get("target_id")), None)
            role = body and {"how": body.how, "own": len(body.own), "pieces": [len(g) for g in body.pieces]}
        else:
            dets, coasting = legacy.detections, legacy.coasting
        state = State(t=t, frame=FRAME, detections=dets, coasting=coasting)
        if trace is not None and trace.get("event") == "step":
            dec = decisions[r["d"]]
            why, st = dec["decision_trace"], dec["state"]
            assert why["intent"] == "RangeSkill" and why["decision_id"] == trace["decision_id"]
            target = next(Detection(**{**d, "bbox": tuple(d["bbox"])}) for d in st["detections"]
                          if d["track"] == why["target"] and d["cls"] in (ENEMY, TARGET) and d["conf"] >= .4)
            intent = RangeSkill(target, why["web_cluster_request"], why["decision_id"], why["valid_until"],
                                RangeSkillResources(why["resources"]["webs"], why["resources"]["observed_t"]))
            pad = ctrl.step(state, intent, intent_t=st["t"], execution_t=trace["execution_t"], **kw)
            if shown is not ctrl:
                shown.step(legacy, intent, intent_t=st["t"], execution_t=trace["execution_t"])
        else:
            pad = ctrl.step(state, Idle(), execution_t=t, **kw)
            if shown is not ctrl:
                shown.step(legacy, Idle(), execution_t=t)
        got = ctrl.range_skill_trace if trace is not None else None
        out.append({"row": i, "t": t, "d": r.get("d"), "ids": [d.track for d in dets], "recorded_ids": r["ids"],
                    "recorded_reason": (trace or {}).get("reason"), "recorded_pad": r.get("proposed_pad"),
                    "reason": got and got["reason"], "accepted": got and got["accepted"],
                    "body_observation": got and got.get("body_observation"), "target_role": role,
                    "stable": ctrl.stable, "pad": deepcopy(pad), "n_boxes": len(boxes),
                    "camera_pad": deepcopy(shown.range_skill_trace["pad"]) if trace is not None and shown.range_skill_trace else None})
    out_path.write_text(json.dumps({"code_root": str(code_root), "mode": mode, "rows": out}, default=list) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
