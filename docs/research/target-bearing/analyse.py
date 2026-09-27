"""EXPLORATORY: statistics over probe.py's samples-*.jsonl. Prints markdown tables to stdout.

    uv run --no-project --with numpy python docs/research/target-bearing/analyse.py
"""
import glob
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
rng = np.random.default_rng(20260926)
NPERM = 1000
RED_ENEMY_SESSIONS = {"20260926T035932-508Z-63684-14"}


def load():
    rows = []
    for p in sorted(glob.glob(str(HERE / "samples-*.jsonl"))):
        with open(p, encoding="utf-8") as fh:
            rows += [json.loads(line) for line in fh]
    return rows


def pick(r, mode):
    if not r["dets"]:
        return None
    W, H, f = r["W"], r["H"], r["focal_px"]
    if mode == "nearest":
        d = min(r["dets"], key=lambda d: math.dist(((d[0] + d[2]) / 2, (d[1] + d[3]) / 2), (W / 2, H / 2)))
    else:  # largest box height
        d = max(r["dets"], key=lambda d: d[3] - d[1])
    x, y = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
    return math.degrees(math.atan2(x - W / 2, f)), math.degrees(math.atan2(y - H / 2, f)), d[3] - d[1]


def future_windows(rows, windows):
    """{(session, i): {window: (yaw, pitch) or None}} from the train step files, same run and usable steps only."""
    root = HERE.parents[2]
    need = {}
    for r in rows:
        need.setdefault(r["session"], set()).add(r["i"])
    out = {}
    for sid, idx in need.items():
        steps = []
        with open(root / "data/human/sessions" / sid / f"{sid}.steps.jsonl", encoding="utf-8") as fh:
            head = json.loads(fh.readline())
            assert head["split"] == "train"
            g, gp = head["calibration"]["yaw_deg_per_count"], head["calibration"]["pitch_deg_per_count"]
            for line in fh:
                s = json.loads(line)
                ok = s["suitability"] == "accepted" and s["regime"] == "normal" and s["gap_free"] and s["relative_known"]
                steps.append((s["run"], ok, s["mouse_dx"] if ok else 0, s["mouse_dy"] if ok else 0))
                assert s["i"] == len(steps) - 1
        for i in idx:
            res = {}
            for a, b in windows:
                seg = steps[i + a:i + b]
                if len(seg) == b - a and all(s[1] and s[0] == steps[i][0] for s in seg):
                    res[(a, b)] = (sum(s[2] for s in seg) * g, sum(s[3] for s in seg) * gp)
                else:
                    res[(a, b)] = None
            out[(sid, i)] = res
    return out


def ols_r2(X, y):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    return 1 - res.var() / y.var(), beta


def stats(b, t):
    """b: bearing (deg), t: summed future turn (deg)."""
    r = float(np.corrcoef(b, t)[0, 1])
    nz = t != 0
    sign = float(np.mean(np.sign(b[nz]) == np.sign(t[nz]))) if nz.any() else float("nan")
    r2, beta = ols_r2(b, t)
    perm_r, perm_s = [], []
    for _ in range(NPERM):
        bp = rng.permutation(b)
        perm_r.append(np.corrcoef(bp, t)[0, 1])
        perm_s.append(np.mean(np.sign(bp[nz]) == np.sign(t[nz])))
    perm_r, perm_s = np.array(perm_r), np.array(perm_s)
    return {"n": len(b), "r": r, "sign": sign, "r2": r2, "slope": float(beta[1]),
            "perm_r_mean": float(perm_r.mean()), "perm_r_p95": float(np.quantile(np.abs(perm_r), .95)),
            "perm_sign_mean": float(perm_s.mean()), "perm_sign_p95": float(np.quantile(perm_s, .95)),
            "p_r": float((np.sum(np.abs(perm_r) >= abs(r)) + 1) / (NPERM + 1))}


def fmt(s):
    return (f"| {s['n']} | {s['r']:+.3f} | {s['r2']:.3f} | {s['slope']:+.3f} | {s['sign']:.3f} | "
            f"{s['perm_r_mean']:+.3f} (|r| p95 {s['perm_r_p95']:.3f}) | {s['perm_sign_mean']:.3f} (p95 {s['perm_sign_p95']:.3f}) |")


def main():
    rows = load()
    sessions = sorted({r["session"] for r in rows})
    print(f"samples {len(rows)} from {len(sessions)} sessions\n")
    print("| session | samples | no target | share no target | median dets/frame (found) |")
    print("|---|---:|---:|---:|---:|")
    for s in sessions + ["ALL"]:
        rs = [r for r in rows if s in ("ALL", r["session"])]
        none = sum(1 for r in rs if not r["dets"])
        nd = [len(r["dets"]) for r in rs if r["dets"]]
        print(f"| {s} | {len(rs)} | {none} | {none / len(rs):.3f} | {np.median(nd):.0f} |")
    # 035932 was played on James's main account, whose Enemy Color is the default red (checked on 40 of its frames):
    # the green finder is blind there, so its few green marks are not enemies. Everything below uses the other sessions.
    rows = [r for r in rows if r["session"] not in RED_ENEMY_SESSIONS]
    sessions = [s for s in sessions if s not in RED_ENEMY_SESSIONS]
    print(f"\nBelow: {len(rows)} samples from the {len(sessions)} green-enemy sessions "
          f"({sum(1 for r in rows if not r['dets']) / len(rows):.3f} with no target)")

    for mode in ("nearest", "largest"):
        found = [(r, pick(r, mode)) for r in rows if r["dets"]]
        by = np.array([p[0] for _, p in found])
        bp = np.array([p[1] for _, p in found])
        hh = np.array([p[2] for _, p in found])
        print(f"\n### target = {mode} detection\n")
        if mode == "nearest":
            print(f"box height native px: p10 {np.quantile(hh, .1):.0f} p50 {np.median(hh):.0f} p90 {np.quantile(hh, .9):.0f}; "
                  f"at the policy's 256-wide view (x0.1): p10 {np.quantile(hh, .1) / 10:.1f} p50 {np.median(hh) / 10:.1f} "
                  f"p90 {np.quantile(hh, .9) / 10:.1f} px")
            inside = [abs(p[0]) < 1e9 and abs(math.tan(math.radians(p[0])) * r["focal_px"]) < 128
                      and abs(math.tan(math.radians(p[1])) * r["focal_px"]) < 128 for r, p in found]
            print(f"nearest target centre inside the policy's native 256x256 crosshair crop: {np.mean(inside):.3f} of found "
                  f"({np.sum(inside)} / {len(inside)})")
            print(f"|bearing yaw| deg: p25 {np.quantile(np.abs(by), .25):.1f} p50 {np.median(np.abs(by)):.1f} "
                  f"p75 {np.quantile(np.abs(by), .75):.1f}; |pitch| p50 {np.median(np.abs(bp)):.1f}\n")
        print("| axis | horizon | subset | n | r | R^2 | slope (deg turn per deg bearing) | sign agree | shuffled r | shuffled sign |")
        print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
        for axis, b, key in (("yaw", by, "yaw_next"), ("pitch", bp, "pitch_next")):
            for hz in (4, 8):
                t = np.array([sum(r[key][:hz]) for r, _ in found])
                for sub, m in (("all found", np.ones(len(t), bool)), ("|turn| > 1 deg", np.abs(t) > 1)):
                    print(f"| {axis} | {hz} | {sub} " + fmt(stats(b[m], t[m])))
        if mode != "nearest":
            continue
        # incremental value over the camera's own recent motion (the policy sees its action history)
        print("\nIncremental value over past motion (OLS on found samples with a known 4-step past):\n")
        print("| axis | horizon | n | R^2 past only | R^2 past + bearing | R^2 bearing only |")
        print("|---|---|---:|---:|---:|---:|")
        for axis, idx, key, pk in (("yaw", 0, "yaw_next", "yaw_past4"), ("pitch", 1, "pitch_next", "pitch_past4")):
            sel = [(r, p) for r, p in found if r[pk] is not None]
            past = np.array([r[pk] for r, _ in sel])
            b = np.array([p[idx] for _, p in sel])
            for hz in (4, 8):
                t = np.array([sum(r[key][:hz]) for r, _ in sel])
                print(f"| {axis} | {hz} | {len(t)} | {ols_r2(past, t)[0]:.3f} | "
                      f"{ols_r2(np.column_stack([past, b]), t)[0]:.3f} | {ols_r2(b, t)[0]:.3f} |")
        # binned: mean next-8 yaw by bearing bin
        print("\nMean summed yaw over the next 8 steps by nearest-target yaw bearing:\n")
        print("| bearing bin (deg) | n | mean next-8 yaw (deg) | median | share turning toward |")
        print("|---|---:|---:|---:|---:|")
        t8 = np.array([sum(r["yaw_next"][:8]) for r, _ in found])
        edges = [-90, -30, -15, -5, -1, 1, 5, 15, 30, 90]
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (by >= lo) & (by < hi)
            if m.sum() == 0:
                continue
            tow = np.mean(np.sign(t8[m]) == np.sign((lo + hi) / 2)) if abs(lo + hi) > 0 else float("nan")
            print(f"| [{lo}, {hi}) | {m.sum()} | {t8[m].mean():+.2f} | {np.median(t8[m]):+.2f} | {tow:.3f} |")
        # per session r
        print("\nPer-session yaw r (nearest, next 4 / next 8):\n")
        print("| session | n found | r4 | r8 |")
        print("|---|---:|---:|---:|")
        for s in sessions:
            sel = [(r, p) for r, p in found if r["session"] == s]
            b = np.array([p[0] for _, p in sel])
            t4 = np.array([sum(r["yaw_next"][:4]) for r, _ in sel])
            t8 = np.array([sum(r["yaw_next"][:8]) for r, _ in sel])
            print(f"| {s} | {len(sel)} | {np.corrcoef(b, t4)[0, 1]:+.3f} | {np.corrcoef(b, t8)[0, 1]:+.3f} |")

    # later windows (reaction delay): re-read the train step files for windows beyond the probe's 8 steps
    found = [(r, pick(r, "nearest")) for r in rows if r["dets"]]
    windows = ((0, 4), (0, 8), (4, 12), (8, 16), (0, 16), (12, 24))
    fut = future_windows(rows, windows)
    print("\nLater windows, nearest target, steps [a, b) after the frame (33.3 ms steps; rows whose window leaves the run "
          "or touches a masked step are dropped):\n")
    print("| axis | window | subset | n | r | R^2 | slope | sign agree | shuffled r | shuffled sign |")
    print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
    for axis, idx in (("yaw", 0), ("pitch", 1)):
        for w in windows:
            sel = [(p[idx], fut[(r["session"], r["i"])][w][idx]) for r, p in found
                   if fut[(r["session"], r["i"])][w] is not None]
            b, t = np.array([s[0] for s in sel]), np.array([s[1] for s in sel])
            for sub, m in (("all found", np.ones(len(t), bool)), ("|turn| > 1 deg", np.abs(t) > 1)):
                print(f"| {axis} | [{w[0]}, {w[1]}) | {sub} " + fmt(stats(b[m], t[m])))
    # decision points: the camera was still for the last 4 steps, so past motion cannot say where the next turn goes
    print("\nCamera still over the previous 4 steps (|past yaw| and |past pitch| < 0.5 deg), nearest target:\n")
    print("| axis | window | subset | n | r | R^2 | slope | sign agree | shuffled r | shuffled sign |")
    print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
    still = [(r, p) for r, p in found if r["yaw_past4"] is not None and abs(r["yaw_past4"]) < .5
             and abs(r["pitch_past4"]) < .5]
    for axis, idx in (("yaw", 0), ("pitch", 1)):
        for w in ((0, 8), (0, 16)):
            sel = [(p[idx], fut[(r["session"], r["i"])][w][idx]) for r, p in still
                   if fut[(r["session"], r["i"])][w] is not None]
            b, t = np.array([s[0] for s in sel]), np.array([s[1] for s in sel])
            for sub, m in (("all", np.ones(len(t), bool)), ("|turn| > 1 deg", np.abs(t) > 1)):
                if m.sum() >= 10:
                    print(f"| {axis} | [{w[0]}, {w[1]}) | {sub} " + fmt(stats(b[m], t[m])))

    # the policy's direct history input is the previous step's camera (as a class); its LSTM carries earlier steps
    prev = future_windows(rows, ((-1, 0),))
    print("\nIncremental value over the previous single step's motion (what the policy's history input carries):\n")
    print("| axis | window | n | R^2 prev step only | R^2 prev step + bearing | R^2 bearing only |")
    print("|---|---|---:|---:|---:|---:|")
    for axis, idx in (("yaw", 0), ("pitch", 1)):
        for w in ((0, 4), (0, 8), (0, 16)):
            sel = [(prev[(r["session"], r["i"])][(-1, 0)][idx], p[idx], fut[(r["session"], r["i"])][w][idx])
                   for r, p in found if prev[(r["session"], r["i"])][(-1, 0)] is not None
                   and fut[(r["session"], r["i"])][w] is not None]
            a = np.array(sel)
            print(f"| {axis} | [{w[0]}, {w[1]}) | {len(a)} | {ols_r2(a[:, 0], a[:, 2])[0]:.3f} | "
                  f"{ols_r2(a[:, :2], a[:, 2])[0]:.3f} | {ols_r2(a[:, 1], a[:, 2])[0]:.3f} |")

    # by target size (a proxy for distance / engagement)
    print("\nBy nearest-target box height (native px), window [0, 8):\n")
    print("| axis | box height | n | r | R^2 | slope | sign agree | shuffled r | shuffled sign |")
    print("|---|---|---:|---:|---:|---:|---:|---|---|")
    for axis, idx, key in (("yaw", 0, "yaw_next"), ("pitch", 1, "pitch_next")):
        for lo, hi in ((0, 60), (60, 150), (150, 10000)):
            sel = [(p[idx], sum(r[key][:8])) for r, p in found if lo <= p[2] < hi]
            b, t = np.array([s[0] for s in sel]), np.array([s[1] for s in sel])
            print(f"| {axis} | [{lo}, {hi}) " + fmt(stats(b, t)))

    # turn magnitude with and without a target
    print("\nTurn magnitude by visibility (|summed yaw| next 8, deg):\n")
    for lab, rs in (("target found", [r for r in rows if r["dets"]]), ("no target", [r for r in rows if not r["dets"]])):
        a = np.abs([sum(r["yaw_next"][:8]) for r in rs])
        print(f"- {lab}: n {len(a)}, median {np.median(a):.2f}, mean {a.mean():.2f}, share > 1 deg {np.mean(a > 1):.3f}")


if __name__ == "__main__":
    main()
