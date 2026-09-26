"""Re-validation timer scoring (seed 20260927): T1, T2 as registered, and T3' (amendment 3). The live half is undecided
by the support floor (69 < 100 changes): its T2 / T3' numbers are information only. Memory: one window at a time."""
import gc, hashlib, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "."); sys.path.insert(0, "C:/Users/volpe/repos/rivals-agent")
from g2decode import clock
from peakmem import peak_gb
from perception import match_timer as M

FRAME_MS = 1000 / 120
CODE = Path("C:/Users/volpe/repos/rivals-agent/perception/match_timer.py")
LOGGER = {"19-53-04": "20260926T005304-628Z-63684-4", "20-25-52": "20260926T012552-291Z-63684-6",
          "20-56-10": "20260926T015610-960Z-63684-8", "21-13-21": "20260926T021321-378Z-63684-9",
          "22-48-05": "20260926T034805-307Z-63684-13"}
T = "C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/gate2-readers/reval/truth/"
coarse = json.load(open(T + "timer_coarse.json"))
truth = json.load(open(T + "timer_changes.json"))
values = json.load(open(T + "timer_values.json"))


def sec(label):
    if label in (None, "none", "illegible"):
        return None
    return int(float(label)) if "." in label else int(label[:2]) * 60 + int(label[3:])


def label_at(runs, k):
    for a, b, lab in runs:
        if a <= k <= b:
            return lab
    return None


def fmt(label):
    return None if sec(label) is None else ("decimal" if "." in label else "mmss")


def segments(rows):
    """rows [(t_ms, value, fmt)] -> continuous segments (amendment 3: break at |dv + dt| > 0.5 s or a format change)."""
    segs, cur = [], []
    for r in rows:
        if cur and (r[2] != cur[-1][2] or abs((r[1] - cur[-1][1]) + (r[0] - cur[-1][0]) / 1000.0) > 0.5):
            segs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        segs.append(cur)
    return [s for s in segs if len(s) >= 3]


def offset(seg):
    return float(np.median([t + 1000.0 * v for t, v, _ in seg]))


out = {"code_sha256_lf": hashlib.sha256(CODE.read_bytes().replace(b"\r\n", b"\n")).hexdigest(), "t1": [], "t2": {}, "t3p": {}}
for rec, labs in values["frames"].items():
    with np.load(f"val2/values_{rec}.npz") as d:
        C = d["centre"]
    for j, lab in enumerate(labs):
        want = lab["centre"]
        r = M.read_box(C[j], M.CENTRE)
        got = None if r is None else r.text
        legible = want not in ("none", "illegible")
        out["t1"].append({"rec": rec, "j": j, "want": want, "got": got, "wrong": got is not None and got != want,
                          "unknown": legible and got is None, "legible": legible})
    del C
    gc.collect()
clocks = {}
for win, chans in truth["changes"].items():
    rec = win.rsplit("_", 1)[0]
    if rec not in clocks:
        clocks[rec] = clock("C:/Users/volpe/Videos/RivalsInput/" + LOGGER[rec])
    clk = clocks[rec]
    with np.load(f"val2/timer_{win}.npz") as d:
        C, pts = d["centre"], d["pts"]
    reads = [M.read_box(f, M.CENTRE) for f in C]
    det = M.second_changes(reads)
    tks = chans.get("centre", [])
    used, match = set(), []
    for k in tks:
        c = [(abs(dk - k), dk, b) for dk, a, b in det if abs(dk - k) <= 1 and dk not in used]
        if c:
            _, dk, b = min(c)
            used.add(dk)
            match.append({"k": k, "det": dk, "err": dk - k, "det_new": b, "true_new": sec(label_at(coarse[win]["centre"], ((k + 11) // 12) * 12))})
        else:
            match.append({"k": k, "det": None})
    out["t2"][win] = {"truth": len(tks), "detected": len(det), "matches": match,
                      "false": [{"det": dk, "a": a, "b": b} for dk, a, b in det if dk not in used]}
    # T3': segments from the reader's anchors and from the truth anchors; compare matched segments' median offsets
    def rows(pairs, fmts):
        o = []
        for (k, v), f in zip(pairs, fmts):
            c = clk.get(int(pts[k]))
            if c is not None and v is not None and f is not None:
                o.append((c / 1e6, v, f))
        return o
    d_rows = rows([(dk, b) for dk, a, b in det], [None if reads[dk] is None else ("mmss" if reads[dk].fmt == "mmss" else "decimal") for dk, a, b in det])
    t_labs = [label_at(coarse[win]["centre"], ((k + 11) // 12) * 12) for k in tks]
    t_rows = rows([(k, sec(l)) for k, l in zip(tks, t_labs)], [fmt(l) for l in t_labs])
    dsegs, tsegs = segments(d_rows), segments(t_rows)
    pairs = []
    for ts in tsegs:
        tv = {v for _, v, _ in ts}
        best = max(dsegs, key=lambda s: len(tv & {v for _, v, _ in s}), default=None)
        if best is not None and tv & {v for _, v, _ in best}:
            err = offset(best) - offset(ts)
            jitter_d = [t + 1000.0 * v - offset(best) for t, v, _ in best]
            jitter_t = [t + 1000.0 * v - offset(ts) for t, v, _ in ts]
            pairs.append({"n_truth": len(ts), "n_reader": len(best), "offset_error_ms": round(err, 3),
                          "reader_jitter_ms": [round(x, 2) for x in jitter_d], "truth_jitter_ms": [round(x, 2) for x in jitter_t]})
        else:
            pairs.append({"n_truth": len(ts), "n_reader": 0, "offset_error_ms": None})
    out["t3p"][win] = pairs
    del C
    gc.collect()

t1 = out["t1"]
leg = [x for x in t1 if x["legible"]]
m = [x for v in out["t2"].values() for x in v["matches"]]
f = [x for x in m if x["det"] is not None]
segs = [p for v in out["t3p"].values() for p in v]
errs = [abs(p["offset_error_ms"]) for p in segs if p["offset_error_ms"] is not None]
jit_t = [abs(x) for p in segs for x in p.get("truth_jitter_ms", [])]
jit_d = [abs(x) for p in segs for x in p.get("reader_jitter_ms", [])]
out["summary"] = {
    "T1": {"value_reads": len(t1), "wrong": sum(x["wrong"] for x in t1), "legible": len(leg),
           "unknown_of_legible": sum(x["unknown"] for x in leg) / len(leg) if leg else None},
    "T2 (information only: 69 < 100)": {"true_changes": len(m), "recall": len(f) / len(m) if m else None,
           "exact": sum(x["err"] == 0 for x in f) / len(f) if f else None, "all_within_1": all(abs(x["err"]) <= 1 for x in f),
           "false_changes": sum(len(v["false"]) for v in out["t2"].values()),
           "wrong_valued": sum(1 for x in f if x["true_new"] is not None and x["det_new"] != x["true_new"])},
    "T3' (information only)": {"segments": len(segs), "unmatched": sum(p["offset_error_ms"] is None for p in segs),
           "max_offset_error_ms": max(errs) if errs else None, "p90_offset_error_ms": float(np.percentile(errs, 90)) if errs else None,
           "every_segment_within_1_frame": all(e <= FRAME_MS for e in errs) and len(errs) == len(segs),
           "p90_within_2_frames": (float(np.percentile(errs, 90)) <= 2 * FRAME_MS) if errs else None,
           "display_jitter_truth_ms_p50_p90_max": [float(np.percentile(jit_t, q)) for q in (50, 90)] + [max(jit_t)] if jit_t else None,
           "display_jitter_reader_ms_p50_p90_max": [float(np.percentile(jit_d, q)) for q in (50, 90)] + [max(jit_d)] if jit_d else None},
    "peak_gb": round(peak_gb(), 2)}
json.dump(out, open("val2/score_timer.json", "w"), indent=1)
print(json.dumps(out["summary"], indent=1))
