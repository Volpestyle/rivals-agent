"""Allowlisted saved-pixel measurements; no input, capture, model or label edits."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BASE_SHA = "5ec7e109f168aeb05978724540eca1dace96fda981fea2861dc16ae3de2a5f58"
NEW_NAMES = ("000000.jpg", "000021.jpg", "000041.jpg")
PAD_NAMES = (
    ("t0-a-untagged-000.jpg", "95d98b19d860e3ced9037733c28a8cacbd6722846540926ebdb1f7ddcaad2549"),
    ("t0-b-after-web-cluster-003.jpg", "61aaca45d4d1a1ecf2bb2ef011258201640d0edd8ded8fc8d7e1ac47dccb876f"),
    ("t0-b-after-web-cluster-028.jpg", "4c46d2632dabb57707b971665b51d7be7928a5768c847623b3f68d6b76648cbe"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline():
    path = OUT / "baseline_hud.py"
    assert digest(path) == BASE_SHA
    spec = importlib.util.spec_from_file_location("frozen_hud_performance_baseline", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def references():
    rows = []
    for name in NEW_NAMES:
        report = json.loads((ROOT / "data/diagnostics/range-request-hud-cold-cost-20260922" / (name + ".json")).read_text())
        rows.append({"name": name, "path": ROOT / "data/l1/range-request-timing-20260922-1" / name,
                     "sha256": report["sha256"], "layout": "pad", "t": 0})
    diagnosis = json.loads((ROOT / "data/diagnostics/range-perception-20260922/diagnosis.json").read_text())
    expected = set(range(13121, 13522, 100)) | set(range(19421, 20022, 100)) | set(range(21521, 21922, 100))
    assert len(diagnosis["frames"]) == 17 and {r["pts_ms"] for r in diagnosis["frames"]} == expected
    for r in diagnosis["frames"]:
        rows.append({"name": f"source-{r['pts_ms']}", "path": ROOT / r["source"]["image"],
                     "sha256": r["source"]["image_sha256"], "layout": "mapped", "t": r["pts_ms"] / 1000})
    rows.extend({"name": name, "path": Path("C:/rivals-agent/l2tag") / name,
                 "sha256": sha, "layout": "pad", "t": 0} for name, sha in PAD_NAMES)
    return rows


def image(row):
    assert digest(row["path"]) == row["sha256"]
    frame = cv2.imread(str(row["path"]))
    assert frame.shape == (1440, 2560, 3)
    return frame


def layout(module, row):
    if row["layout"] == "pad":
        return module.PAD
    # Existing accepted mapping, not a new source-profile inference.
    return replace(module.MK, slot_cx={"swing": .795, "uppercut": .8348, "get_over_here": .8723})


def exported(value, frame, t):
    from agent.state import State
    state = State(t=t, frame=(frame.shape[1], frame.shape[0]), **value.state_kwargs())
    return {"hud": asdict(value), "state": state.to_dict()}


def reading(module, frame, chosen, t):
    return exported(module.read(frame, chosen), frame, t)


def masks(module, frame, chosen):
    regions = [(module.HP_TEXT, 115, module.CONTRASTS),
               (chosen.webs, module.WEBS_FLOOR, module.CONTRASTS)]
    regions += [(module._icon_box(cx), 115, (55, 30)) for cx in chosen.slot_cx.values()]
    return [[hashlib.sha256(m.tobytes()).hexdigest() for m in module._masks(frame, box, floor, contrasts)]
            for box, floor, contrasts in regions]


def snapshot(module, filename, crops=False):
    rows = []
    for ref in references():
        frame = image(ref)
        chosen = layout(module, ref)
        # Empty existing classifier/template caches to retain a cold-read control.
        module._SEEN.clear()
        module._CACHE.clear()
        module._FLAT.clear()
        start = time.perf_counter()
        result = reading(module, frame, chosen, ref["t"])
        elapsed = (time.perf_counter() - start) * 1000
        rows.append({**ref, "path": str(ref["path"]), **result,
                     "elapsed_ms_not_benchmark": elapsed, "masks": masks(module, frame, chosen)})
        if crops:
            # Exact pixels for inspection; originals preserved. No labels added.
            cv2.imwrite(str(OUT / (ref["name"].replace(".jpg", "") + "-hud.png")), frame[1190:1380])
        assert digest(ref["path"]) == ref["sha256"]
    report = {"hud_sha256": digest(Path(module.__file__)), "rows": rows,
              "opencv": cv2.__version__, "numpy": np.__version__, "opencv_threads": cv2.getNumThreads()}
    with (OUT / filename).open("x") as out:
        json.dump(report, out, indent=2)
    return report


def profile(module, name):
    ref = next(r for r in references() if r["name"] == name)
    frame = image(ref)
    counts = Counter()
    functions = {}
    for owner, names in ((module, ("_mask", "_segment", "_classify", "classify")),
                         (cv2, ("morphologyEx", "connectedComponentsWithStats", "resize"))):
        for key in names:
            fn = getattr(owner, key)
            functions[owner, key] = fn
            def wrapped(*args, _fn=fn, _key=key, **kwargs):
                counts[_key] += 1
                return _fn(*args, **kwargs)
            setattr(owner, key, wrapped)
    results = []
    try:
        for kind in ("process_cold", "identical_pixels_warm"):
            counts.clear()
            start = time.perf_counter()
            value = module.read(frame, module.PAD)
            elapsed = (time.perf_counter() - start) * 1000
            results.append({"kind": kind, "elapsed_ms": elapsed, "calls": dict(counts),
                            **exported(value, frame, ref["t"])})
    finally:
        for (owner, key), fn in functions.items():
            setattr(owner, key, fn)
    assert results[0]["hud"] == results[1]["hud"]
    assert digest(ref["path"]) == ref["sha256"]
    return {"name": name, "source_sha256": ref["sha256"], "hud_sha256": digest(Path(module.__file__)),
            "timed_boundary": "hud.read_only_state_export_excluded",
            "opencv_threads": cv2.getNumThreads(), "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("snapshot", "profile"))
    ap.add_argument("variant", choices=("baseline", "candidate"))
    ap.add_argument("--name", choices=NEW_NAMES)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crops", action="store_true")
    args = ap.parse_args()
    if args.variant == "baseline":
        module = baseline()
    else:
        from perception import hud as module
    if args.action == "snapshot":
        result = snapshot(module, args.out, args.crops)
        print(json.dumps({"out": args.out, "frames": len(result["rows"])}))
    else:
        result = profile(module, args.name)
        with (OUT / args.out).open("x") as out:
            json.dump(result, out, indent=2)
        print(json.dumps({"name": args.name, "ms": [r["elapsed_ms"] for r in result["results"]],
                          "cold_calls": result["results"][0]["calls"]}))
    assert not any(n in sys.modules for n in ("torch", "agent.loop", "agent.controller", "dxcam", "vgamepad"))


if __name__ == "__main__":
    main()
