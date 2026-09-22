"""Bounded saved-frame equality/timing against an immutable production reader."""
import argparse
import cProfile
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import pstats
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
BASE_SHA = "5f865e5567f16cf72962cb5148e2e7342272229ec59f54fe5082df90d9b0d3e2"
NAMES = ("000000.jpg", "000012.jpg", "000054.jpg")
PAD = (
    ("t0-a-untagged-000.jpg", "95d98b19d860e3ced9037733c28a8cacbd6722846540926ebdb1f7ddcaad2549"),
    ("t0-b-after-web-cluster-003.jpg", "61aaca45d4d1a1ecf2bb2ef011258201640d0edd8ded8fc8d7e1ac47dccb876f"),
    ("t0-b-after-web-cluster-028.jpg", "4c46d2632dabb57707b971665b51d7be7928a5768c847623b3f68d6b76648cbe"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline():
    path = OUT / "baseline_hud.py"
    assert digest(path) == BASE_SHA
    spec = importlib.util.spec_from_file_location("countdown_baseline", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def references():
    context = json.loads((ROOT / "data/diagnostics/range-perception-cost-20260922/context.json").read_text())
    hashes = {str(Path(k)): v for k, v in context["source_and_input_sha256"].items()}
    rows = []
    for row in context["frames"]:
        assert row["file"] in NAMES
        path = Path("data/l1/range-request-efficiency-20260922-1") / row["file"]
        rows.append(dict(name=row["file"], path=ROOT / path, sha256=hashes[str(path)],
                         layout="pad", t=row["observation_t"]))
    assert len(rows) == 3
    diagnosis = json.loads((ROOT / "data/diagnostics/range-perception-20260922/diagnosis.json").read_text())
    expected = set(range(13121, 13522, 100)) | set(range(19421, 20022, 100)) | set(range(21521, 21922, 100))
    assert len(diagnosis["frames"]) == 17 and {r["pts_ms"] for r in diagnosis["frames"]} == expected
    rows += [dict(name=f"source-{r['pts_ms']}", path=ROOT / r["source"]["image"],
                  sha256=r["source"]["image_sha256"], layout="mapped", t=r["pts_ms"] / 1000)
             for r in diagnosis["frames"]]
    rows += [dict(name=name, path=Path("C:/rivals-agent/l2tag") / name, sha256=sha,
                  layout="pad", t=0) for name, sha in PAD]
    return rows


def image(row):
    assert digest(row["path"]) == row["sha256"]
    frame = cv2.imread(str(row["path"]))
    assert frame.shape == (1440, 2560, 3)
    return frame


def layout(module, row):
    return (module.PAD if row["layout"] == "pad" else
            replace(module.MK, slot_cx={"swing": .795, "uppercut": .8348, "get_over_here": .8723}))


def export(value, frame, t):
    from agent.state import State
    return {"hud": asdict(value), "state": State(t=t, frame=(frame.shape[1], frame.shape[0]),
                                                **value.state_kwargs()).to_dict()}


def reading(module, frame, row):
    chosen = layout(module, row)
    return {**export(module.read(frame, chosen), frame, row["t"]),
            "cooldowns": {key: module.read_cooldown(frame, key, chosen) for key in chosen.slot_cx}}


def clear(module):
    module._SEEN.clear()
    module._CACHE.clear()
    module._FLAT.clear()


def context(module):
    return dict(hud_sha256=digest(Path(module.__file__)), python=sys.version,
                platform=platform.platform(), executable=sys.executable,
                numpy=np.__version__, opencv=cv2.__version__, opencv_threads=cv2.getNumThreads(),
                opencv_build=cv2.getBuildInformation(), torch_imported="torch" in sys.modules)


def snapshot(module):
    results = []
    for row in references():
        frame = image(row)
        clear(module)
        results.append({**row, "path": str(row["path"]), **reading(module, frame, row)})
    return {**context(module), "rows": results}


def timed(module, name):
    row = next(r for r in references() if r["name"] == name)
    frame = image(row)
    # One unprofiled process-cold reader call. Decode/import/export are excluded.
    start = time.perf_counter()
    value = module.read(frame, module.PAD)
    elapsed_ms = (time.perf_counter() - start) * 1000
    result = export(value, frame, row["t"])
    # One separate cache-cleared call for work attribution, NOT unprofiled timing.
    clear(module)
    profiler = cProfile.Profile()
    profiler.enable()
    checked = module.read(frame, module.PAD)
    profiler.disable()
    assert result == export(checked, frame, row["t"])
    stats = []
    for (file, line, fn), (primitive, calls, self_s, cumulative_s, _) in pstats.Stats(profiler).stats.items():
        if file == module.__file__ or "min" in fn or "reduce" in fn:
            stats.append(dict(file=file, line=line, function=fn, calls=calls, primitive=primitive,
                              self_ms=self_s * 1000, cumulative_ms=cumulative_s * 1000))
    return {**context(module), "name": name, "input_sha256": row["sha256"],
            "unprofiled_cold_read_ms": elapsed_ms, "output": result,
            "separate_cache_cleared_profile": stats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("snapshot", "timed"))
    ap.add_argument("variant", choices=("baseline", "candidate"))
    ap.add_argument("--name", choices=NAMES)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.variant == "baseline":
        module = baseline()
    else:
        from perception import hud as module
    result = snapshot(module) if args.action == "snapshot" else timed(module, args.name)
    assert not any(n in sys.modules for n in ("torch", "agent.loop", "agent.controller", "dxcam", "vgamepad"))
    with (OUT / args.out).open("x") as out:
        json.dump(result, out, indent=2)
    print(json.dumps({"out": args.out, "rows": len(result.get("rows", [])),
                      "cold_read_ms": result.get("unprofiled_cold_read_ms")}))


if __name__ == "__main__":
    main()
