"""Does the nearby-target repair's evidence survive the frame-terms player zone? (VUH-1355 acceptance 4)

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/player-zone-20260923/repair_preservation.py

Read-only against data/diagnostics/range-perception-20260922 (nothing there is written). For the 21 authorized native
frames (17 candidate-history frames and the four PAD fixtures) it recomputes the wide and aim outputs with HEAD's
outline.py, which must reproduce the recorded evidence-ownership-results.json exactly, and with this change's outline.py,
and lists every difference. It then replays the four causal histories (candidate-rows.json) with both, as
evidence_ownership_eval.py does, and compares the selected targets. Writes repair-preservation.json next to this file.
"""
import hashlib
import json
import subprocess
import sys
import types
from dataclasses import asdict, replace
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DIAG = ROOT / "data/diagnostics/range-perception-20260922"
SOURCE = ROOT / "data/human/semantic-candidates/20260922T032454-642Z-24328-1"
sys.path.insert(0, str(ROOT))
from agent import brain  # noqa: E402
from agent.loop import aim_window  # noqa: E402
from agent.state import State  # noqa: E402
from agent.tracker import Tracker  # noqa: E402
from perception import outline as new  # noqa: E402

cv2.setNumThreads(1)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def find(module, image, crop=False):
    """repair_eval.find, verbatim in effect: scale from height, aim crop with origin/frame."""
    h, w = image.shape[:2]
    if not crop:
        return module.find_enemies(image, scale=h / 720)
    x1, y1, x2, y2 = aim_window((w, h))
    return [replace(d, bbox=(d.bbox[0] + x1, d.bbox[1] + y1, d.bbox[2] + x1, d.bbox[3] + y1))
            for d in module.find_enemies(image[y1:y2, x1:x2], scale=h / 720, origin=(x1, y1), frame=(w, h))]


def plain(ds):
    return json.loads(json.dumps(list(map(asdict, ds))))


def main():
    recorded = json.loads((DIAG / "evidence-ownership-results.json").read_text())
    diagnosis = json.loads((DIAG / "diagnosis.json").read_text())
    before_hashes = {p.name: sha(p) for p in DIAG.iterdir() if p.is_file()}
    head = types.ModuleType("outline_head")
    head.__file__ = str(ROOT / "perception/outline.py")
    exec(compile(subprocess.check_output(["git", "show", "HEAD:perception/outline.py"], cwd=ROOT), head.__file__, "exec"),
         head.__dict__)
    report = {"head_outline_sha256_lf": hashlib.sha256(subprocess.check_output(["git", "show", "HEAD:perception/outline.py"],
                                                                                 cwd=ROOT)).hexdigest(),
              "new_outline_sha256": sha(ROOT / "perception/outline.py"), "frames": [], "replays": {}}
    for rec in recorded["native"]:
        path = Path(rec["path"])
        assert sha(path) == rec["sha256"], path
        image = cv2.imread(str(path))
        entry = {"path": str(path)}
        for mode, crop in (("wide", False), ("aim", True)):
            assert plain(find(head, image, crop)) == rec[mode], (path, mode, "HEAD does not reproduce the record")
            got = plain(find(new, image, crop))
            entry[mode] = {"same": got == rec[mode], "recorded": rec[mode], "new": got}
        report["frames"].append(entry)
    # the causal histories reference frames by file pts; map them from the rows themselves
    rows = json.loads((SOURCE / "candidate-rows.json").read_text())
    assert sha(SOURCE / "candidate-rows.json") == diagnosis["rows_sha256"]
    by_pts = {}
    for rec in diagnosis["frames"]:
        by_pts[rec["pts_ms"]] = cv2.imread(str(ROOT / rec["source"]["image"]))
    for row in rows:
        traces = {}
        for label, module in (("head", head), ("new", new)):
            memory, tracker, trace = brain.Memory(), Tracker(), []
            for history in row["history"]:
                pts = history["frame"]["file_pts_num"]
                state = State.from_dict(history["state"])
                found = find(module, by_pts[pts], True)
                clip = aim_window(state.frame) if found else None
                ds = tracker.update(found or find(module, by_pts[pts]), state.t, frame=state.frame, clip=clip)
                _, target = brain.gate(replace(state, detections=ds, coasting=tracker.coasting), memory)
                trace.append({"pts_ms": pts, "target": json.loads(json.dumps(asdict(target))) if target else None})
            traces[label] = trace
        assert traces["head"] == recorded["replays"][row["id"]], (row["id"], "HEAD does not reproduce the recorded trace")
        report["replays"][row["id"]] = {"same": traces["new"] == traces["head"], "recorded": traces["head"], "new": traces["new"]}
    assert before_hashes == {p.name: sha(p) for p in DIAG.iterdir() if p.is_file()}, "a diagnostics artifact changed"
    report["summary"] = {"frames_same_wide": sum(f["wide"]["same"] for f in report["frames"]),
                         "frames_same_aim": sum(f["aim"]["same"] for f in report["frames"]),
                         "frames": len(report["frames"]),
                         "replays_same": sum(r["same"] for r in report["replays"].values()), "replays": len(report["replays"]),
                         "diagnostics_files_unchanged": len(before_hashes)}
    (HERE / "repair-preservation.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["summary"]))
    for f in report["frames"]:
        for mode in ("wide", "aim"):
            if not f[mode]["same"]:
                print("DIFF", Path(f["path"]).parent.name, Path(f["path"]).name, mode,
                      "recorded", [d["bbox"] for d in f[mode]["recorded"]], "new", [d["bbox"] for d in f[mode]["new"]])
    for k, r in report["replays"].items():
        print(k, "same" if r["same"] else "DIFF",
              [(t["pts_ms"], (t["target"] or {}).get("bbox"), (t["target"] or {}).get("track")) for t in r["new"]])


if __name__ == "__main__":
    main()
