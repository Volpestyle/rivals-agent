"""Read finalized slot 4 JSON and reproduce its contract mismatch without IO devices.

Run from the repository root. Writes only report.json beside this script.
No model, perception, video decoder, Loop, or Live import.
"""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))
from agent.controller import ARM_FRAMES, Controller
from agent.intents import RangeSkill, RangeSkillResources
from agent.state import Detection, ENEMY, State
from agent.tracker import Tracker

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
RUN = ROOT / "data/l1/galacta-pilot-20260922-04-learned"
LOG_SHA = "1eadcb5efba274883e103ebfae5e5f62c4f720008c75c3ea5ec226baf9e071a6"


def pin(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()}


def paired(request):
    frame = (1280, 720)
    whole = Detection(ENEMY, (600, 260, 680, 460), .9, distance=13)
    pieces = [replace(whole, bbox=(600, 260, 680, 350)),
              replace(whole, bbox=(600, 355, 680, 460))]
    results = {}
    for name, detections in (("whole", [whole]), ("split", pieces)):
        tracker, controller = Tracker(), Controller()
        for i in range(ARM_FRAMES):
            t = i * .02
            tracked = tracker.update([whole], t, frame)
            intent = RangeSkill(tracked[0], "no_new_start", i, t + .1, RangeSkillResources(5, t))
            controller.step(State(t, frame, detections=tracked), intent, intent_t=t)
        tracked = tracker.update(detections, .1, frame)
        intent = RangeSkill(replace(whole, track=1), request, 10, .2, RangeSkillResources(5, .1))
        pad = controller.step(State(.1, frame, detections=tracked), intent, intent_t=.1)
        results[name] = {"ids": [d.track for d in tracked], "pad_request": pad,
                         "reason": controller.range_skill_trace["reason"], "stable": controller.stable}
    assert results["whole"]["reason"] == ("accepted" if request == "start" else "no_new_start")
    assert results["split"]["ids"] == [1, 1]
    assert results["split"]["reason"] == "target_missing_or_ambiguous"
    assert results["split"]["pad_request"]["lt"] == 0
    return results


def main():
    before = pin(RUN / "frames.jsonl")
    assert before["sha256"] == LOG_SHA
    rows = [json.loads(line) for line in (RUN / "frames.jsonl").read_text().splitlines()]
    decisions = {r["d"]: r for r in rows if "state" in r and "decision_trace" in r}
    samples = []
    for number, filename in ((52, "000048.jpg"), (53, "000049.jpg"), (59, "000054.jpg")):
        row = decisions[number]
        image_row = next(r for r in rows if r.get("file") == filename)
        samples.append({"d": number, "state": row["state"], "decision_trace": row["decision_trace"],
                        "first_consumed_observation_t": row["observation_t"],
                        "reflex_boxes": row["dets"], "reflex_ids": row["ids"],
                        "controller_reason": row["range_skill_trace"]["reason"],
                        "context_image": pin(RUN / filename),
                        "context_image_observation_t": image_row["observation_t"],
                        "context_image_minus_decision_s": image_row["observation_t"] - row["state"]["t"],
                        "context_image_boxes": image_row["dets"], "context_image_ids": image_row["ids"],
                        "image_limit": "Nearby saved reflex frame, not proven exact decision pixels."})
    ambiguous = [r for r in decisions.values()
                 if r.get("range_skill_trace", {}).get("reason") == "target_missing_or_ambiguous"]
    assert sorted(r["d"] for r in ambiguous) == list(range(53, 59)) + list(range(155, 161))
    assert all(r["decision_trace"]["web_cluster_request"] == "no_new_start" for r in ambiguous)

    # Native logged geometry, artificial time/control history: a mechanism check,
    # not reconstruction of the original interleaved continuous tracker state.
    tracker = Tracker()
    native_whole = [replace(d, track=None) for d in State.from_dict(decisions[52]["state"]).detections]
    native_parts = [replace(d, track=None) for d in State.from_dict(decisions[53]["state"]).detections]
    for i in range(5):
        tracker.update(native_whole, i * .02, (2560, 1440))
    native_ids = [d.track for d in tracker.update(native_parts, .1, (2560, 1440))]
    assert native_ids == [1] * 5
    report = {
        "status": "reproduced_contract_mismatch_no_production_change",
        "source": before,
        "code": [pin(ROOT / p) for p in ("agent/tracker.py", "agent/controller.py", "agent/state.py", "agent/brain.py")],
        "synthetic_start_pair": paired("start"),
        "synthetic_no_new_pair": paired("no_new_start"),
        "native_geometry_control": {"ids": native_ids, "synthetic_time_and_preconditioning": True},
        "recorded_first_consumed_ambiguous_decisions": sorted(r["d"] for r in ambiguous),
        "all_ambiguous_decisions_already_proposed_no_new_start": True,
        "samples": samples,
        "limits": ["No inference, new labels, deployment or native input.",
                   "Fragment sharing is intentional Tracker.update behavior; duplicate ID allocation is not demonstrated.",
                   "The pure example proves a producer/consumer contract mismatch, not safe arbitrary duplicate union.",
                   "This refusal is not the cause of the pilot's zero learned start proposals.",
                   "Native target identity uses inspected nearby saved frames and the accepted slot 4 audit; no exact decision pixel claim."]}
    assert pin(RUN / "frames.jsonl") == before
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT / "report.json"), "native_ids": native_ids,
                      "ambiguous_decisions": report["recorded_first_consumed_ambiguous_decisions"]}))


if __name__ == "__main__":
    main()
