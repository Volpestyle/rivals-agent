"""The pitch-uncertainty fix, FINAL ROUND (lane doc section, LF sha256 f1385679): as round 2 (5f94a529) except that
k per bin is fitted on the bin's TRULY FAST (true regime extrapolated) fit rows only, k = 1 where fewer than 50.
Round 2's description: the stated pitch std s inflated per quintile bin of
the row's stated YAW std, k_b = max(1, q0.683(r), q0.954(r) / 2), r = |mu_pitch - truth| / s over the fit set's rows in
bin b with known pitch truth (before abstention; nearest-rank); bin edges = the fit set's 20/40/60/80 % quantiles of the
yaw std (a value on an edge goes up); s' = k * s; pitch answered iff s' <= the 1 / 3 degree bound of its predicted
regime; yaw untouched.
Arm A: fit on a4-beta / 171533 (never judged), judged on both folds. Arm B: fit on one fast-heavy fold (seeds pooled),
judged on the other, both directions. Judge per arm: per fold pooled, per TRUE band, answered pitch rows within
1 sigma' >= 0.70 and 2 sigma' >= 0.90 in both bands on both folds; bounds (>= 90 % answered within the bound of the
predicted regime) on all six runs; yaw identical row for row. Reading: A passes -> A; A fails and B passes -> B (deploy
parameters fitted on both fast folds pooled); both fail -> the pitch cost stands."""
import copy
import json
import math
from bisect import bisect_right
from pathlib import Path

HERE = Path(__file__).parent
BOUND = {"calibrated": 1.0, "extrapolated": 3.0}
BANDS = ("calibrated", "extrapolated")
MIN_FAST = 50                     # a bin with fewer truly fast fit rows gets k = 1
DEV = ["a4-beta-on-171533-predictions"]
FOLDS = {"051828": ["yaw-t0-on-051828-predictions", "yaw-t1-on-051828-predictions", "yaw-t2-on-051828-predictions"],
         "205528": ["a1-beta-s0-on-205528-predictions", "a1-beta-s1-on-205528-predictions",
                    "a1-beta-s2-on-205528-predictions"]}
_cache = {}


def load(name):
    if name not in _cache:
        _cache[name] = [json.loads(x) for x in (HERE / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()]
    return _cache[name]


def q(values, p):
    s = sorted(values)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def truth_rows(rows):
    return [r for r in rows if r["pitch"] is not None and r["std_pitch"] and r["std_yaw"] is not None]


def fit(names):
    rows = [r for n in names for r in truth_rows(load(n))]
    edges = [q([r["std_yaw"] for r in rows], p) for p in (0.2, 0.4, 0.6, 0.8)]
    ks, counts = [], []
    for b in range(5):
        rs = [abs(r["mu_pitch"] - r["pitch"]) / r["std_pitch"] for r in rows
              if bisect_right(edges, r["std_yaw"]) == b and r["regime"] == "extrapolated"]   # truth: fitting only
        counts.append(len(rs))
        ks.append(1.0 if len(rs) < MIN_FAST else max(1.0, q(rs, 0.683), q(rs, 0.954) / 2))
    return {"edges": edges, "k": ks, "n": counts}


def apply(rows, params):
    out = []
    for r in rows:
        c = copy.deepcopy(r)
        if r["std_pitch"] is not None and r["pred_regime"] is not None and r["std_yaw"] is not None:
            c["std_pitch"] = r["std_pitch"] * params["k"][bisect_right(params["edges"], r["std_yaw"])]
            c["ans_pitch"] = None if c["std_pitch"] > BOUND[r["pred_regime"]] else r["mu_pitch"]
        out.append(c)
    return out


def coverage(rows):
    res = {}
    for band in BANDS:
        ev = [r for r in rows if r["pitch"] is not None and r["regime"] == band]
        ans = [r for r in ev if r["ans_pitch"] is not None]
        z = [abs(r["ans_pitch"] - r["pitch"]) / r["std_pitch"] for r in ans]
        inb = [abs(r["ans_pitch"] - r["pitch"]) <= BOUND[r["pred_regime"]] for r in ans]
        res[band] = {"n": len(ev), "answered": len(ans), "abst": 1 - len(ans) / len(ev) if ev else None,
                     "w1": sum(v <= 1 for v in z) / len(z) if z else None,
                     "w2": sum(v <= 2 for v in z) / len(z) if z else None,
                     "inb": sum(inb) / len(inb) if inb else None}
    return res


def fmt(c):
    return f"{c['w1']:.3f} / {c['w2']:.3f} / abst {c['abst']:.3f} / in-bound {c['inb']:.3f}"


def judge(label, params_for_fold):
    """params_for_fold: fold -> parameters used to judge it. Returns (passes, lines)."""
    lines, cov_ok, bounds_ok, yaw_ok = [], True, True, True
    for fold, runs in FOLDS.items():
        params = params_for_fold[fold]
        before_all, after_all = [], []
        for name in runs:
            rows = load(name)
            cal = apply(rows, params)
            yaw_ok &= all(a["ans_yaw"] == b["ans_yaw"] and a["std_yaw"] == b["std_yaw"] and a["mu_yaw"] == b["mu_yaw"]
                          for a, b in zip(rows, cal))
            cb, ca = coverage(rows), coverage(cal)
            for band in BANDS:
                lines.append(f"| {label} | {fold} | {name.split('-on-')[0]} | {band} | {fmt(cb[band])} | {fmt(ca[band])} |")
                bounds_ok &= ca[band]["inb"] is None or ca[band]["inb"] >= 0.90
            before_all += rows
            after_all += cal
        pb, pa = coverage(before_all), coverage(after_all)
        for band in BANDS:
            ok = pa[band]["w1"] >= 0.70 and pa[band]["w2"] >= 0.90
            cov_ok &= ok
            lines.append(f"| {label} | {fold} | **pooled** | {band} | {fmt(pb[band])} | **{fmt(pa[band])}** "
                         f"{'(meets)' if ok else '(FAILS)'} |")
    return cov_ok and bounds_ok and yaw_ok, (cov_ok, bounds_ok, yaw_ok), lines


def show_params(label, p):
    print(f"{label}: yaw-std edges " + ", ".join(f"{e:.4f}" for e in p["edges"]) + "; k per bin "
          + ", ".join(f"{k:.4f}" for k in p["k"]) + "; truly fast fit rows per bin " + ", ".join(f"{n:,}" for n in p["n"]))


# --- arm A ---
pa = fit(DEV)
show_params("Arm A (fit on a4-beta / 171533)", pa)
print("  A fit set in-sample, after:", {b: fmt(c) for b, c in coverage(apply(load(DEV[0]), pa)).items()})
a_pass, a_parts, a_lines = judge("A", {"051828": pa, "205528": pa})
# --- arm B (cross-fitted) ---
pb_from_051828, pb_from_205528 = fit(FOLDS["051828"]), fit(FOLDS["205528"])
show_params("Arm B, fitted on fold 051828 (judges 205528)", pb_from_051828)
show_params("Arm B, fitted on fold 205528 (judges 051828)", pb_from_205528)
for lab, p, fold in (("B fit 051828", pb_from_051828, "051828"), ("B fit 205528", pb_from_205528, "205528")):
    pooled = [r for n in FOLDS[fold] for r in load(n)]
    print(f"  {lab} in-sample, after:", {b: fmt(c) for b, c in coverage(apply(pooled, p)).items()})
b_pass, b_parts, b_lines = judge("B", {"051828": pb_from_205528, "205528": pb_from_051828})

print("\n| Arm | Fold | Run | True band | Before: 1s / 2s / abstention / in-bound | After: 1s / 2s / abstention / in-bound |")
print("|---|---|---|---|---|---|")
for line in a_lines + b_lines:
    print(line)
for arm, parts in (("A", a_parts), ("B", b_parts)):
    print(f"\nArm {arm}: (1) coverage {'met' if parts[0] else 'NOT met'}; (2) bounds on all six runs "
          f"{'met' if parts[1] else 'NOT met'}; (3) yaw identical {'met' if parts[2] else 'NOT met'} -> "
          f"{'PASS' if all(parts) else 'FAIL'}")
if a_pass:
    print("\nreading: A is the fix (deployable parameters: A's dev-fold fit)")
elif b_pass:
    deploy = fit(FOLDS["051828"] + FOLDS["205528"])
    show_params("\nreading: A fails, B passes -> B is the fix; deployable parameters (both fast folds pooled)", deploy)
else:
    print("\nreading: both arms fail -> the pitch cost stands; fast-band replay pitch labels stay untrusted; the pitch item "
          "waits for the three new admitted takes as fresh held-out sessions (no further round on these judge sets)")

# --- NOT pre-registered: the share of truly fast rows per yaw-std bin on each judge fold ---
print("\nNOT pre-registered: share of truly fast (extrapolated) rows per yaw-std bin, and their share predicted slow")
for lab, p in (("A bins", pa), ("B bins fit 051828", pb_from_051828), ("B bins fit 205528", pb_from_205528)):
    for fold, runs in FOLDS.items():
        rows = [r for n in runs for r in truth_rows(load(n))]
        cells = []
        for b in range(5):
            br = [r for r in rows if bisect_right(p["edges"], r["std_yaw"]) == b]
            fast = [r for r in br if r["regime"] == "extrapolated"]
            slow_pred = [r for r in fast if r["pred_regime"] == "calibrated"]
            cells.append(f"bin{b}: {len(fast) / len(br):.2f} fast ({len(slow_pred) / len(fast) if fast else 0:.2f} of them "
                         f"predicted slow), n {len(br):,}")
        print(f"  {lab} on {fold}: " + "; ".join(cells))
json.dump({"A": pa, "B_fit_051828": pb_from_051828, "B_fit_205528": pb_from_205528},
          open(HERE / "pitch_fix3-params.json", "w", encoding="utf-8"), indent=1)
