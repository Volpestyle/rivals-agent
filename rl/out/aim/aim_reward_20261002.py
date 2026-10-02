"""Offline validation of the dense aim reward (rl.aim.reward) on retained range frames (VUH-1321). CPU only.

Reads rl/out/aim/aim_reward_scan_20261002.jsonl (made by aim_reward_scan_20261002.py from retained JPEGs) and writes
aim_reward_20261002.json: per-run shaping, the hit/KO-preceding test against all other windows, the cut accounting
and the farming checks. `--sheet` also draws the contact sheet from the frames listed in SHEET.

    python rl/out/aim/aim_reward_20261002.py [--sheet]
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import numpy as np  # noqa: E402

from rl.aim.reward import AimShaper, nearest, potential  # noqa: E402
from rl.rewards import RewardTracker  # noqa: E402

SCAN = Path("rl/out/aim/aim_reward_scan_20261002.jsonl")
OUT = Path("rl/out/aim/aim_reward_20261002.json")
WINDOW_S = 1.0
EPS = .005                      # |sum| below this (3 px at 720p) counts as no change


def load():
    by = defaultdict(list)
    for line in open(SCAN, encoding="utf-8"):
        r = json.loads(line)
        by[r["dir"]].append(r)
    return by


def run(rows):
    shaper, tracker, events = AimShaper(), RewardTracker(), []
    for r in rows:
        s = shaper.update(r["t"], r["vec"])
        r["phi"], r["f"], r["why"] = s.phi, s.shaping, s.reason
        e = tracker.update(r["t"], r["hit"], r["ko"], None, None)
        if e.hit or e.ko:
            events.append({"t": r["t"], "file": r["file"], "kind": "ko" if e.ko else "hit"})
    return events


def window_sum(rows, t_end):
    terms = [r["f"] for r in rows if t_end - WINDOW_S < r["t"] <= t_end and r["f"] is not None]
    return (sum(terms), len(terms)) if terms else (None, 0)


def classify(sums):
    n = len(sums)
    pos = sum(s is not None and s > EPS for s in sums)
    neg = sum(s is not None and s < -EPS for s in sums)
    flat = sum(s is not None and abs(s) <= EPS for s in sums)
    none = sum(s is None for s in sums)
    with_term = n - none
    vals = [s for s in sums if s is not None]
    return {"n": n, "positive": pos, "negative": neg, "flat": flat, "no_term": none,
            "p_positive": round(pos / n, 3) if n else None,
            "p_positive_given_term": round(pos / with_term, 3) if with_term else None,
            "p_negative_given_term": round(neg / with_term, 3) if with_term else None,
            "mean_given_term": round(float(np.mean(vals)), 4) if vals else None}


def binom_tail(k, n, p):
    """P(X >= k), X ~ Binomial(n, p)."""
    return float(sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1)))


def main():
    by = load()
    out = {"window_s": WINDOW_S, "eps": EPS, "runs": {}}
    ev_sums, ev_phi, base_sums, base_phi, base_same, all_events = [], [], [], [], [], []
    reasons, cut_drop, gross, net = Counter(), [], 0., 0.
    for d, rows in by.items():
        events = run(rows)
        for r in rows:
            reasons[r["why"]] += 1
        for a, b in zip(rows, rows[1:]):
            if b["why"] == "switch":
                cut_drop.append(b["phi"] - a["phi"])
        terms = [r["f"] for r in rows if r["f"] is not None]
        gross += sum(abs(x) for x in terms)
        net += sum(terms)
        ets = [e["t"] for e in events]
        for e in events:
            s, n = window_sum(rows, e["t"])
            e.update(sum=None if s is None else round(s, 4), terms=n,
                     phi=next(r["phi"] for r in rows if r["t"] == e["t"]))
            ev_sums.append(s)
            ev_phi.append(e["phi"])
            all_events.append({"dir": d, **e})
        t0 = rows[0]["t"]
        for r in rows:
            if r["t"] - t0 < WINDOW_S or any(-.25 <= te - r["t"] <= 1.5 for te in ets):
                continue
            s, _ = window_sum(rows, r["t"])
            base_sums.append(s)
            base_phi.append(r["phi"])
            if events:
                base_same.append(s)
        out["runs"][d] = {"frames": len(rows), "hits": sum(e["kind"] == "hit" for e in events),
                          "kos": sum(e["kind"] == "ko" for e in events),
                          "target_share": round(sum(r["phi"] is not None for r in rows) / len(rows), 3),
                          "terms": len(terms), "net": round(sum(terms), 4),
                          "gross": round(sum(abs(x) for x in terms), 4)}
    ev, base, same = classify(ev_sums), classify(base_sums), classify(base_same)
    k, n = ev["positive"], ev["n"] - ev["no_term"]
    p0 = base["positive"] / max(1, base["n"] - base["no_term"])
    out["prehit"] = {"events": ev, "baseline_all_runs": base, "baseline_runs_with_events": same,
                     "binomial_p_positive_given_term_vs_all": binom_tail(k, n, p0) if n else None,
                     "events_detail": all_events}

    def near(phis, lim):
        known = [p for p in phis if p is not None]
        return {"known": len(known), "of": len(phis),
                "share_within": round(sum(p >= lim for p in known) / len(known), 3) if known else None,
                "median_phi": round(float(np.median(known)), 3) if known else None}
    out["phi_at_event_vs_baseline"] = {"limit_phi": -.1, "events": near(ev_phi, -.1), "baseline": near(base_phi, -.1)}
    out["reasons"] = dict(reasons)
    cd = np.array(cut_drop)
    out["cuts"] = {"switches": len(cd), "sum_dropped_phi": round(float(cd.sum()), 3) if len(cd) else 0,
                   "sum_abs_dropped_phi": round(float(np.abs(cd).sum()), 3) if len(cd) else 0,
                   "gross_paid": round(gross, 3), "net_paid": round(net, 3)}
    out["farming"] = farming(by)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("runs",)} | {"prehit": {
        k: v for k, v in out["prehit"].items() if k != "events_detail"}}, indent=1))


def farming(by):
    """Oscillation over a target: (a) real known runs replayed forth and back k times (a camera sweeping over the same
    target again and again), (b) the camera-period runs (continuous full turns past the same bots), (c) holding still."""
    res = {}
    # (a) every unbroken run of >= 6 'ok' frames, played forward then backward 5 times.
    nets, gross = [], []
    for rows in by.values():
        seg = []
        for r in rows + [{"why": "end"}]:
            if r["why"] == "ok" or (r["why"] in ("first", "gap", "switch") and not seg):
                seg.append(r)
                continue
            if len(seg) >= 6:
                vecs = [s["vec"] for s in seg]
                seq = (vecs + vecs[::-1][1:-1]) * 5 + [vecs[0]]
                sh = AimShaper()
                fs = [sh.update(k * .1, v).shaping for k, v in enumerate(seq)]
                fs = [x for x in fs if x is not None]
                nets.append(sum(fs))
                gross.append(sum(abs(x) for x in fs))
            seg = [r] if r.get("why") in ("first", "gap", "switch") else []
    res["replayed_oscillation"] = {"segments": len(nets), "max_abs_net": float(np.max(np.abs(nets))) if nets else None,
                                   "median_gross": float(np.median(gross)) if gross else None}
    # (b) camera-period runs: continuous turning through the same bots.
    per = {}
    for d, rows in by.items():
        if "period" in d:
            terms = [r["f"] for r in rows if r["f"] is not None]
            per[d.split("/")[-1]] = {"terms": len(terms), "net": round(sum(terms), 3),
                                     "gross": round(sum(abs(x) for x in terms), 3),
                                     "switches": sum(r["why"] == "switch" for r in rows)}
    res["camera_period_runs"] = per
    # (c) synthetic: a centred target swept +-200 px for 50 cycles at 10 Hz, with a flicker every 7th frame.
    xs = [640 + 200 * math.sin(2 * math.pi * k / 10) for k in range(500)]
    sh = AimShaper()
    fs = []
    for k, x in enumerate(xs):
        v = None if k % 7 == 3 else [1, 1, x / 1280 - .5, 0, .3, 1, x / 1280 - .5, 0, .3, math.log1p(1)]
        fs.append(sh.update(k * .1, v).shaping)
    paid = [x for x in fs if x is not None]
    res["synthetic_sweep_with_flicker"] = {"frames": 500, "terms": len(paid), "net": round(sum(paid), 4),
                                           "gross": round(sum(abs(x) for x in paid), 3)}
    return res


SHEET = [
    ('data/calibration/rl-sitting-20260930-07/ep-001-rl', '000076.jpg', 'abstain: green foliage, no door'),
    ('data/calibration/rl-sitting-20260930-01/ep-002-bc', '000064.jpg', 'door view: abstain'),
    ('data/calibration/rl-sitting-20260930-07/ep-011-rl', '000027.jpg', 'empty view'),
    ('data/calibration/rl-sitting-20260930-01/ep-005-rl', '000041.jpg', 'empty view'),
    ('data/calibration/rl-sitting-20260930-07/ep-000-bc', '000063.jpg', 'two bots'),
    ('data/l1/scripted-diagnostic-20260922-1130', '000095.jpg', 'two bots'),
    ('data/calibration/rl-sitting-20260930-04/ep-000-bc', '000078.jpg', 'two bots'),
    ('data/calibration/rl-sitting-20260930-07/ep-013-rl', '000076.jpg', 'small/partial bot'),
    ('data/calibration/rl-sitting-20260930-01/ep-001-rl', '000038.jpg', 'small/partial bot'),
    ('data/l1/range-request-20s-20260922-1', '000024.jpg', 'on target'),
    ('data/calibration/rl-sitting-20260930-07/ep-005-rl', '000099.jpg', 'turning onto target'),
    ('data/calibration/rl-sitting-20260930-07/ep-005-rl', '000132.jpg', 'target moving away'),
    ('data/l1/scripted-diagnostic-20260922-1130', '000078.jpg', 'switch: cut'),
    ('data/calibration/rl-sitting-20260930-07/ep-016-bc', '000029.jpg', 'switch: cut'),
    ('data/calibration/rl-sitting-20260930-07/ep-013-rl', '000012.jpg', 'reacquired after gap'),
    ('data/l1/range-request-owned-pulse-20260922-1', '000014.jpg', 'hit (1 s sum +0.16)'),
    ('data/l1/range-request-efficiency-20260922-1', '000013.jpg', 'hit (1 s sum +0.15)'),
    ('data/l1/scripted-diagnostic-20260922-1130', '000041.jpg', 'KO (1 s sum -0.04)'),
    ('data/l1/scripted-diagnostic-20260922-1130', '000040.jpg', 'hit before that KO'),
]


def sheet(path="rl/out/aim/aim_reward_20261002_sheet.jpg"):
    import cv2
    from policy.bc2.target_features import detect_boxes
    by = load()
    for rows in by.values():
        run(rows)
    index = {(r["dir"], r["file"]): r for rows in by.values() for r in rows}
    tw, th, cols = 640, 360, 4
    img = np.full((((len(SHEET) + cols - 1) // cols) * (th + 44), cols * tw, 3), 18, np.uint8)
    for k, (d, f, label) in enumerate(SHEET):
        r = index[(d, f)]
        frame = cv2.imread(str(Path(d) / f))
        small = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
        if r["reason"] != "teacher_door_abstention":
            for b in detect_boxes(frame):
                cv2.rectangle(small, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (0, 220, 255), 2)
        cv2.drawMarker(small, (640, 360), (255, 255, 255), cv2.MARKER_CROSS, 30, 2)
        p = nearest(r["vec"])
        if p is not None:
            c = (int(640 + p[0] * 640), int(360 + p[1] * 640))
            cv2.line(small, (640, 360), c, (255, 0, 255), 3)
            cv2.circle(small, c, 9, (255, 0, 255), -1)
        tile = cv2.resize(small, (tw, th), interpolation=cv2.INTER_AREA)
        y, x = (k // cols) * (th + 44), (k % cols) * tw
        img[y:y + th, x:x + tw] = tile
        phi = "None" if r["phi"] is None else f"{r['phi']:+.3f}"
        fv = "None" if r["f"] is None else f"{r['f']:+.3f}"
        run_name = d.split("/")[-2][-11:] + "/" + d.split("/")[-1][:14] if "calibration" in d else d.split("/")[-1][:24]
        cv2.putText(img, f"{k:02d} {label}", (x + 6, y + th + 17), 0, .5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img, f"Phi {phi}  F {fv}  [{r['why']}]  {run_name}/{f}", (x + 6, y + th + 37), 0, .42,
                    (190, 220, 255), 1, cv2.LINE_AA)
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return path


if __name__ == "__main__":
    if "--sheet" in sys.argv:
        print(sheet())
    else:
        main()
