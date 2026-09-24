"""Review re-check B1: the by-eye audit bound. Pre-registered before looking:

- Population: every zero-flow pair the landing estimator WITHHOLDS in the l2 proxies' full "no command" (still)
  stratum, per run (baseline1, baseline3), from regress_i.json.
- Sample: up to 20 per run, numpy default_rng(7) without replacement.
- Label, by eye, from frame / next frame / 4x absolute difference (saved native frames at 640x360): "still" when the
  difference is black except the character, bots, effects, damage numbers or UI; "moved" when static scene edges
  (floor lines, walls, pillars, horizon) show across the frame; "unclear" otherwise.
- A withheld pair counts as a regression only when labelled "still".
- Bound: estimated false withholds = (still / labelled) x withheld, in points of the stratum = / n x 100, must be <= 2.
  The Wilson 95 % upper bound on the still share is reported too. "unclear" pairs are reported and excluded from the rate.
Writes audit_<run>.json (pairs, frame hashes, labels to fill) and sheet_<run>_<i>.png (5 composites per sheet).
"""
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
import os
REG = json.loads((HERE.parent / "regress" / os.environ.get("REG_OUT", "regress_i.json")).read_text())
for run in ("baseline1", "baseline3"):
    d = Path(f"C:/rivals-agent/data/l1/{run}")
    rows = [json.loads(l) for l in (d / "frames.jsonl").read_text().splitlines() if l.strip()]
    saved = [r for r in rows if r.get("file")]
    still = REG[run]["strata"]["still_full"]
    withheld = still["withheld_ks"]
    rng = np.random.default_rng(7)
    pick = sorted(rng.choice(len(withheld), min(20, len(withheld)), replace=False).tolist()) if withheld else []
    audit = {"run": run, "stratum_n": still["n"], "withheld": len(withheld), "sample_seed": 7, "pairs": []}
    tiles = []
    for j in pick:
        k, reason = withheld[j]
        fa, fb = saved[k]["file"], saved[k + 1]["file"]
        ha = hashlib.sha256((d / fa).read_bytes()).hexdigest()
        hb = hashlib.sha256((d / fb).read_bytes()).hexdigest()
        a, b = (cv2.resize(cv2.imread(str(d / f)), (640, 360), interpolation=cv2.INTER_AREA) for f in (fa, fb))
        diff = np.clip(cv2.absdiff(a, b).astype(int) * 4, 0, 255).astype(np.uint8)
        tile = np.hstack([a, b, diff])
        cv2.putText(tile, f"{run} k={k} {reason[:40]}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(tile)
        audit["pairs"].append({"k": k, "reason": reason, "frames": [[fa, ha], [fb, hb]], "label": None})
    for i in range(0, len(tiles), 5):
        cv2.imwrite(str(HERE / f"sheet_{run}_{i // 5}.png"), np.vstack(tiles[i:i + 5]))
    (HERE / f"audit_{run}.json").write_text(json.dumps(audit, indent=1))
    print(run, "withheld", len(withheld), "sampled", len(pick), "sheets", (len(tiles) + 4) // 5)
