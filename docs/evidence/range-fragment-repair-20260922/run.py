"""Before/after for the VUH-1314 fragment repair: HEAD 83c6739 against the working tree, on recorded slot 4 and the review scenarios.

Run from the repository root: uv run --offline --no-project python -B docs/evidence/range-fragment-repair-20260922/run.py
Writes only summary.json beside this script; per-row replays go to a temporary directory and are discarded.
HEAD's agent/ is exported with `git archive` into that directory. No model, perception, Loop, Live or pad is imported.
"""
from collections import Counter
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT, HERE = Path.cwd(), Path(__file__).resolve().parent
BASE = "83c6739"
LOG = ROOT / "data/l1/galacta-pilot-20260922-04-learned/frames.jsonl"
REFUSED_DECISIONS = list(range(53, 59)) + list(range(155, 161))
PINNED = ["agent/tracker.py", "agent/controller.py", "agent/loop.py", "agent/state.py", "agent/intents.py", "agent/brain.py",
          "scripts/range_cast_probe.py"]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def text_digest(path):                         # code as committed: line endings normalized, so a CRLF checkout pins the same
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def py(*args):
    subprocess.run([sys.executable, "-B", *map(str, args)], cwd=ROOT, check=True)


def pad_diff(a, b):
    return max(abs(float(a[k]) - float(b[k])) for k in ("lx", "ly", "rx", "ry", "lt", "rt"))


def main():
    log_before = digest(LOG)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        zipped = subprocess.run(["git", "archive", "--format=zip", BASE, "agent"], cwd=ROOT, check=True, capture_output=True).stdout
        zipfile.ZipFile(io.BytesIO(zipped)).extractall(tmp / "head")
        py(HERE / "replay.py", tmp / "head", "legacy", tmp / "head.json")
        py(HERE / "replay.py", ROOT, "legacy", tmp / "tree-legacy.json")
        py(HERE / "replay.py", ROOT, "observe", tmp / "tree-observe.json")
        py(HERE / "scenarios.py", tmp / "head", tmp / "head-scenarios.json")
        py(HERE / "scenarios.py", ROOT, tmp / "tree-scenarios.json")
        load = lambda n: json.loads((tmp / n).read_text())                               # noqa: E731
        head, legacy, after = load("head.json")["rows"], load("tree-legacy.json")["rows"], load("tree-observe.json")["rows"]
        scen_head, scen_after = load("head-scenarios.json"), load("tree-scenarios.json")
    assert digest(LOG) == log_before

    steps = [r for r in head if r["recorded_reason"] is not None]
    fidelity = {"range_steps": len(steps),
                "reason_mismatches": sum(r["reason"] != r["recorded_reason"] for r in steps),
                "max_pad_abs_diff": max(pad_diff(r["pad"], r["recorded_pad"]) for r in steps),
                "rows_with_ids_differing": sum(r["ids"] != r["recorded_ids"] for r in head)}
    assert fidelity["reason_mismatches"] == 0 and fidelity["max_pad_abs_diff"] == 0 and fidelity["rows_with_ids_differing"] == 0
    camera = sum(r["camera_pad"] != r["recorded_pad"] for r in after if r["recorded_reason"] is not None)
    assert camera == 0                          # the observe replay's tracker camera is the recording's
    rows = [json.loads(line) for line in LOG.read_text().splitlines()]
    last_one_box_w, width_before = None, {}
    for i, r in enumerate(rows):                # the recorded width of the target's last one-box tick before each row
        width_before[i] = last_one_box_w
        if len(r.get("dets", [])) == 1:
            last_one_box_w = r["dets"][0][2] - r["dets"][0][0]
    no_witness = {"reason_changes": sum(a["reason"] != b["reason"] for a, b in zip(head, legacy)),
                  "pad_changes": sum(a["pad"] != b["pad"] for a, b in zip(head, legacy))}
    observe_ids = sum(r["ids"] != r["recorded_ids"] for r in after)

    former = [(b, a) for b, a in zip(head, after) if b["reason"] == "target_missing_or_ambiguous"]
    ticks = []
    for b, a in former:
        body = a["body_observation"] or {}
        ticks.append({"row": b["row"], "d": b["d"], "boxes": b["n_boxes"], "before": b["reason"], "after": a["reason"],
                      "target_association": a["target_role"], "member_count": body.get("member_count"),
                      "union_h": body and round(body["bbox"][3] - body["bbox"][1]),
                      "union_w": body and round(body["bbox"][2] - body["bbox"][0]), "last_one_box_w": width_before[b["row"]],
                      "approach_withheld": body.get("approach_withheld"), "ly_before": b["pad"]["ly"], "ly_after": a["pad"]["ly"],
                      "lt_after": a["pad"]["lt"]})
    first = {}
    for b, a in zip(head, after):
        if b["recorded_reason"] is not None and b["d"] not in first:
            first[b["d"]] = {"d": b["d"], "row": b["row"], "before": b["reason"], "after": a["reason"],
                             "target_association": a["target_role"],
                             "member_count": (a["body_observation"] or {}).get("member_count")}
    changed = [(b, a) for b, a in zip(head, after) if b["reason"] != a["reason"]]
    summary = {
        "inputs": {"slot4_log": {"path": LOG.relative_to(ROOT).as_posix(), "sha256": log_before},
                   "base_commit": BASE,
                   "working_tree_lf": {p: text_digest(ROOT / p) for p in PINNED},
                   "scripts_lf": {p.name: text_digest(p) for p in (HERE / "run.py", HERE / "replay.py", HERE / "scenarios.py")}},
        "head_replay_fidelity_to_recording": fidelity,
        "tree_without_witness_vs_head": no_witness,
        "tree_observe_rows_with_ids_differing_from_recording": observe_ids,
        "tree_observe_camera_pads_differing_from_recording": camera,
        "former_refusal_ticks": {"count": len(ticks),
                                 "after_census": Counter(t["after"] for t in ticks),
                                 "association_census": Counter(json.dumps(t["target_association"]) for t in ticks),
                                 "ly_after_census": Counter(t["ly_after"] for t in ticks),
                                 "measured_union_w_range": [min(t["union_w"] for t in ticks if t["union_w"]),
                                                            max(t["union_w"] for t in ticks if t["union_w"])],
                                 "measured_union_w_over_last_one_box_w_max": max(t["union_w"] / t["last_one_box_w"]
                                                                                 for t in ticks if t["union_w"]),
                                 "table": ticks},
        "refused_decisions_first_consumed": [first[d] for d in REFUSED_DECISIONS],
        "whole_run": {"reason_changes": Counter(f"{b['reason']} -> {a['reason']}" for b, a in changed),
                      "reason_changes_outside_former_refusals": sum(b["reason"] != "target_missing_or_ambiguous" for b, a in changed),
                      "accepted_starts": [sum(bool(r["accepted"]) for r in head), sum(bool(r["accepted"]) for r in after)],
                      "lt_down_ticks": [sum(r["pad"]["lt"] > 0 for r in head), sum(r["pad"]["lt"] > 0 for r in after)],
                      "ly_forward_ticks": [sum(r["pad"]["ly"] > 0 for r in head), sum(r["pad"]["ly"] > 0 for r in after)],
                      "ticks_with_any_pad_change": sum(b["pad"] != a["pad"] for b, a in zip(head, after))},
        "scenarios": {name: {"head": scen_head[name], "tree": scen_after[name]} for name in scen_head},
    }
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, default=list) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("head_replay_fidelity_to_recording", "tree_without_witness_vs_head",
                                              "tree_observe_rows_with_ids_differing_from_recording")}))
    print(json.dumps({k: v for k, v in summary["former_refusal_ticks"].items() if k != "table"}))
    print(json.dumps(summary["whole_run"]))


if __name__ == "__main__":
    main()
