"""Gate 2 step 1, kill-feed items K1-K3 (lane doc section 3fc13f3b, amendment 2), scored against the frozen truth.

The frozen reader (perception.killfeed, LF sha256 e21e5a40...) runs over each validation window, streamed in chunks
(CHUNK_S with MARGIN_S either side; an entry belongs to the chunk its settled frame falls in), which bounds memory; the
layout comes from perception.killfeed.recognise_layout over the window's team-box reads (fail closed). Everything is
keyed by pts (ms). K1-K3 are judged on arrivals after a shift; empty-feed arrivals are reported beside."""
import gc
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "C:/Users/volpe/repos/rivals-agent")
from g2decode import frames  # noqa: E402
from peakmem import peak_gb  # noqa: E402
from perception import killfeed as KF, match_timer as M  # noqa: E402

H = "C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/gate2-readers/"
S2 = json.load(open(H + "sample-2.json")); S3 = json.load(open(H + "sample-3.json"))
CODE = Path("C:/Users/volpe/repos/rivals-agent/perception/killfeed.py")
CHUNK_S, MARGIN_S = 10.0, 1.0
USE_PROMPT = hasattr(KF, "viewer_prompt")
OUT = sys.argv[1] if len(sys.argv) > 1 else "val2/score_feed.json"
TRUTH = sys.argv[2] if len(sys.argv) > 2 else "C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/gate2-readers/reval/truth/feed_truth.json"
MATCH = 12                                      # frames: a detection within this of a true first frame matches it
FRAME_MS = 1000 / 120
truth = json.load(open(TRUTH))


def run_window(rec, i):
    r = (S3 if rec in S3["recordings"] else S2)["recordings"][rec]
    a, b = r["feed_windows"][i]
    with np.load(f"val2/feed_{rec}_{i}.npz") as d:
        teams = d["teams"]
    viewer = [bool(M.read_box(t[:, 0:110], M.TEAM_A) or M.read_box(t[:, 110:220], M.TEAM_B)) for t in teams]
    if USE_PROMPT:
        gen = frames("C:/Users/volpe/Videos/" + r["video"], a, b - a, KF.PROMPT_BOX)
        try:
            pr = [KF.viewer_prompt(c, cropped=True) for n, (_, c) in enumerate(gen) if n % 60 == 0]
        finally:
            gen.close()
        viewer = [x or y for x, y in zip(viewer, pr)]
    layout = KF.recognise_layout(viewer)
    if layout is None:
        return layout, None
    box = KF.LAYOUTS[layout]["region"]
    found, t = [], a
    while t < b:
        P, R = [], []
        for pts, c in frames("C:/Users/volpe/Videos/" + r["video"], max(0.0, t - MARGIN_S), CHUNK_S + 2 * MARGIN_S, box):
            P.append(pts)
            R.append(c.copy())
        for e in KF.entries(R, layout, cropped=True) or []:
            ts = P[e.settled]
            if t * 1000 <= ts < min(t + CHUNK_S, b) * 1000:
                found.append({"k_pts": None if e.k is None else int(P[e.k]), "via": e.via, "settled_pts": int(ts)})
        del P, R
        gc.collect()
        t += CHUNK_S
    return layout, found


out = {"code_sha256_lf": hashlib.sha256(CODE.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), "windows": {}}
for key, tw in truth["windows"].items():
    rec, i = key.rsplit("_", 1)
    layout, found = run_window(rec, int(i))
    out["windows"][key] = {"layout": layout, "detected": found, "truth": tw}
    print(key, layout, len(found or []), "detected", f"peak {peak_gb():.2f} GB", flush=True)


def score(keys):
    s = {"true_shift": 0, "true_empty": 0, "det_shift": 0, "matched": [], "false_shift": 0, "empty_detected": 0,
         "empty_timing_frames": [], "layout_unknown": 0}
    for key in keys:
        w = out["windows"][key]
        if w["detected"] is None:
            s["layout_unknown"] += 1
            s["true_shift"] += sum(bool(e["after_shift"]) for e in w["truth"]["entries"] if not e["excluded"])
            s["true_empty"] += sum(not e["after_shift"] for e in w["truth"]["entries"] if not e["excluded"])
            continue
        det_shift = [d for d in w["detected"] if d["via"] == "shift"]
        s["det_shift"] += len(det_shift)
        used = set()
        for e in w["truth"]["entries"]:
            if e["excluded"]:
                s["excluded"] = s.get("excluded", 0) + 1
                continue
            if e["after_shift"]:
                s["true_shift"] += 1
                c = [(abs(d["k_pts"] - e["first_pts"]), j) for j, d in enumerate(det_shift)
                     if j not in used and abs(d["k_pts"] - e["first_pts"]) <= MATCH * FRAME_MS + 1]
                if c:
                    _, j = min(c)
                    used.add(j)
                    s["matched"].append(round((det_shift[j]["k_pts"] - e["first_pts"]) / FRAME_MS))
            else:
                s["true_empty"] += 1
                c = [d for d in w["detected"] if d["via"] != "shift" and
                     abs((d["k_pts"] if d["k_pts"] is not None else d["settled_pts"] - 30 * FRAME_MS) - e["first_pts"])
                     <= 60 * FRAME_MS]
                if c:
                    s["empty_detected"] += 1
                    timed = [d for d in c if d["k_pts"] is not None]
                    if timed:
                        s["empty_timing_frames"].append(round((timed[0]["k_pts"] - e["first_pts"]) / FRAME_MS))
        s["false_shift"] += len(det_shift) - len(used)
    m = s["matched"]
    s["K1 recall"] = len(m) / s["true_shift"] if s["true_shift"] else None
    s["K2 precision"] = len(m) / s["det_shift"] if s["det_shift"] else None
    s["K3 within 2"] = sum(abs(x) <= 2 for x in m) / len(m) if m else None
    s["K3 within 1"] = sum(abs(x) <= 1 for x in m) / len(m) if m else None
    s["empty detection rate"] = s["empty_detected"] / s["true_empty"] if s["true_empty"] else None
    floor = 30 if keys and not keys[0].startswith("daymr") else 10
    s["PASS"] = bool(s["true_shift"] >= floor and s["K1 recall"] is not None and s["K1 recall"] >= 0.90
                     and s["K2 precision"] is not None and s["K2 precision"] >= 0.95 and s["K3 within 2"] >= 0.95
                     and s["K3 within 1"] >= 0.80)
    s["undecided (under the support floor)"] = s["true_shift"] < floor
    return s


keys = list(out["windows"])
out["summary"] = {"live": score([k for k in keys if not k.startswith("daymr")]),
                  "replay": score([k for k in keys if k.startswith("daymr")])}
out["peak_gb"] = round(peak_gb(), 2)
json.dump(out, open(OUT, "w"), indent=1)
print(json.dumps(out["summary"], indent=1))
