"""Five balanced fresh-process HUD-only pairs per named JPEG; never overwrite."""
import json
from pathlib import Path
import statistics
import subprocess
import sys

OUT = Path(__file__).resolve().parent
rows = []
for repeat in range(5):
    for name in ("000000.jpg", "000021.jpg", "000041.jpg"):
        order = ("baseline", "candidate") if repeat % 2 == 0 else ("candidate", "baseline")
        for variant in order:
            filename = f"hud-only-{repeat}-{variant}-{name}.json"
            subprocess.run([sys.executable, str(OUT / "measure.py"), "profile", variant,
                            "--name", name, "--out", filename], check=True, capture_output=True, text=True)
            row = json.loads((OUT / filename).read_text())
            rows.append({"repeat": repeat, "variant": variant, "file": filename, **row})
summary = []
for name in ("000000.jpg", "000021.jpg", "000041.jpg"):
    for kind in ("process_cold", "identical_pixels_warm"):
        record = {"name": name, "kind": kind}
        for variant in ("baseline", "candidate"):
            selected = [r for r in rows if r["name"] == name and r["variant"] == variant]
            results = [x for r in selected for x in r["results"] if x["kind"] == kind]
            assert all(x["hud"] == results[0]["hud"] and x["state"] == results[0]["state"] for x in results)
            values = [x["elapsed_ms"] for x in results]
            record[variant] = {"n": len(values), "median_ms": statistics.median(values),
                               "min_ms": min(values), "max_ms": max(values), "values_ms": values}
        a = next(r for r in rows if r["name"] == name and r["variant"] == "baseline")
        b = next(r for r in rows if r["name"] == name and r["variant"] == "candidate")
        assert a["source_sha256"] == b["source_sha256"]
        for x, y in zip(a["results"], b["results"]):
            assert x["hud"] == y["hud"] and x["state"] == y["state"]
        record["median_reduction_percent"] = 100 * (1 - record["candidate"]["median_ms"] / record["baseline"]["median_ms"])
        summary.append(record)
report = {"scope": "five_fresh_processes_per_variant_frame_balanced_order_saved_JPEG_not_live",
          "timed_boundary": "hud.read_only_state_export_excluded", "rows": summary,
          "child_reports": [r["file"] for r in rows]}
with (OUT / "hud-only-summary.json").open("x") as f:
    json.dump(report, f, indent=2)
print(json.dumps(summary, indent=2))
