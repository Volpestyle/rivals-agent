"""The confirmation of pitch fix A on fresh held-out sessions (lane doc section, LF sha256 a967962a): arm A's FROZEN
parameters (round 3, pitch_fix3-params.json 6f8dba7b, key "A"; nothing is fitted, no arm B) applied to the per-row
predictions of all seven beta-NLL checkpoints on the three newly admitted takes (21 files). `apply`, `coverage` and the
bin rule are round 3's (pitch_fix3.py 6769ad60), copied verbatim; the pooled figures sum the same tallies.
Judge, all required: (1) pooled over the 3 sessions x 7 checkpoints, per TRUE band, answered pitch rows under s': within
1 sigma' >= 0.70 and within 2 sigma' >= 0.90 in both bands; (2) per checkpoint, pooled over the 3 sessions, per true band,
>= 90 % of answered pitch rows have |error| <= the bound of their predicted regime; (3) yaw identical row for row on every
checkpoint and session. Support floor: a session's true band with < 500 evaluable distinct pitch rows is reported per
session as "under the floor", not interpreted, and stays in the pool. Reading: pass -> A confirmed, the Gate 2
precondition closes; fail -> A is not the fix, the failing component named."""
import copy
import hashlib
import json
from bisect import bisect_right
from pathlib import Path

HERE = Path(__file__).parent
BOUND = {"calibrated": 1.0, "extrapolated": 3.0}
BANDS = ("calibrated", "extrapolated")
MOVING = 0.5
FLOOR = 500
PARAMS_SHA256 = "6f8dba7b04336c3fd4ce5dcd2acaa8b5a6e4578678643dedb7d942b1549bcff3"
EDGES = [0.06059320594627363, 0.10755754546016058, 0.16996028513718056, 0.351656956463779]      # as registered
K = [1, 1, 1, 1.6005068343947064, 1.242973089376128]
CHECKPOINTS = {"T": "yaw-t0", "T1": "yaw-t1", "T2": "yaw-t2", "s0": "a1-beta-s0", "s1": "a1-beta-s1",
               "s2": "a1-beta-s2", "a4": "a4-beta"}
SESSIONS = ["232304", "021320", "025230"]

raw = (HERE / "pitch_fix3-params.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == PARAMS_SHA256, "pitch_fix3-params.json changed"
A = json.loads(raw)["A"]
assert A["edges"] == EDGES and A["k"] == K, "the frozen parameters differ from the registered ones"
A = {"edges": A["edges"], "k": A["k"]}


def apply(rows, params):                                  # pitch_fix3.py, verbatim
    out = []
    for r in rows:
        c = copy.deepcopy(r)
        if r["std_pitch"] is not None and r["pred_regime"] is not None and r["std_yaw"] is not None:
            c["std_pitch"] = r["std_pitch"] * params["k"][bisect_right(params["edges"], r["std_yaw"])]
            c["ans_pitch"] = None if c["std_pitch"] > BOUND[r["pred_regime"]] else r["mu_pitch"]
        out.append(c)
    return out


def coverage(rows):                                       # pitch_fix3.py, verbatim
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


def tallies(rows):
    """coverage()'s integer counts, so pooled figures are sums of the same tallies."""
    res = {}
    for band in BANDS:
        ev = [r for r in rows if r["pitch"] is not None and r["regime"] == band]
        ans = [r for r in ev if r["ans_pitch"] is not None]
        z = [abs(r["ans_pitch"] - r["pitch"]) / r["std_pitch"] for r in ans]
        res[band] = {"n": len(ev), "answered": len(ans), "w1": sum(v <= 1 for v in z), "w2": sum(v <= 2 for v in z),
                     "inb": sum(abs(r["ans_pitch"] - r["pitch"]) <= BOUND[r["pred_regime"]] for r in ans)}
    return res


def ratios(t):
    return {"n": t["n"], "answered": t["answered"], "abst": 1 - t["answered"] / t["n"] if t["n"] else None,
            "w1": t["w1"] / t["answered"] if t["answered"] else None,
            "w2": t["w2"] / t["answered"] if t["answered"] else None,
            "inb": t["inb"] / t["answered"] if t["answered"] else None}


def add(acc, t):
    for band in BANDS:
        for key, v in t[band].items():
            acc[band][key] = acc[band].get(key, 0) + v


def empty():
    return {band: {} for band in BANDS}


def agree(pairs):                                         # analyse.py's definition, verbatim
    return sum((p > 0) == (t > 0) and p != 0 for t, p in pairs) / len(pairs) if pairs else None


def f(v, d=3):
    return "-" if v is None else f"{v:.{d}f}"


def fmt(c):
    return f"{f(c['w1'])} / {f(c['w2'])} / {f(c['abst'])} / {f(c['inb'])}"


before, after = {}, {}                  # (checkpoint, session) -> band -> tallies
yaw_same, yaw_agree, distinct, hashes = {}, {}, {}, {}
for sess in SESSIONS:
    key0 = None
    for label, run in CHECKPOINTS.items():
        name = f"{run}-on-{sess}-predictions"
        path = HERE / f"{name}.jsonl"
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        key = [(r["run"], r["i"], r["t0_ns"], r["pitch"], r["regime"]) for r in rows]
        if key0 is None:
            key0 = key
            distinct[sess] = {band: sum(r["pitch"] is not None and r["regime"] == band for r in rows) for band in BANDS}
        assert key == key0, f"{name}: rows differ from the session's first checkpoint"
        cal = apply(rows, A)
        yaw_same[(label, sess)] = all(a["ans_yaw"] == b["ans_yaw"] and a["std_yaw"] == b["std_yaw"]
                                      and a["mu_yaw"] == b["mu_yaw"] for a, b in zip(rows, cal)) and len(rows) == len(cal)
        pairs = [(r["yaw"], r["mu_yaw"]) for r in rows if r["yaw"] is not None and abs(r["yaw"]) >= MOVING]
        yaw_agree[(label, sess)] = (agree(pairs), len(pairs))
        tb, ta = tallies(rows), tallies(cal)
        for band in BANDS:                                # the tallies reproduce coverage() exactly
            assert ratios(tb[band]) == coverage(rows)[band] and ratios(ta[band]) == coverage(cal)[band], name
        before[(label, sess)], after[(label, sess)] = tb, ta
        del rows, cal


def pooled(table, labels, sessions):
    acc = empty()
    for lab in labels:
        for s in sessions:
            add(acc, table[(lab, s)])
    return {band: ratios(acc[band]) for band in BANDS}


LABELS = list(CHECKPOINTS)
out = []
pb, pa = pooled(before, LABELS, SESSIONS), pooled(after, LABELS, SESSIONS)
cov_ok = {band: pa[band]["w1"] >= 0.70 and pa[band]["w2"] >= 0.90 for band in BANDS}
bounds = {lab: pooled(after, [lab], SESSIONS) for lab in LABELS}
bounds_ok = {lab: all(bounds[lab][band]["inb"] is None or bounds[lab][band]["inb"] >= 0.90 for band in BANDS)
             for lab in LABELS}
yaw_ok = all(yaw_same.values())
passes = all(cov_ok.values()) and all(bounds_ok.values()) and yaw_ok

out.append(f"Frozen parameters (A): edges {EDGES}; k {K}; pitch_fix3-params.json {PARAMS_SHA256}\n")
out.append("Evaluable distinct pitch rows per session and true band (support floor 500):")
for s in SESSIONS:
    out.append(f"- {s}: " + "; ".join(f"{band} {distinct[s][band]:,}" + (" (UNDER THE FLOOR)" if distinct[s][band] < FLOOR
                                                                          else "") for band in BANDS))
out.append("\n## Judge\n")
out.append("| True band | Pooled before A: 1s / 2s / abstention / in-bound | Pooled after A: 1s / 2s / abstention / in-bound "
           "| (1) |\n|---|---|---|---|")
for band in BANDS:
    out.append(f"| {band} | {fmt(pb[band])} | **{fmt(pa[band])}** | {'meets' if cov_ok[band] else 'FAILS'} |")
out.append("\n(2) Bounds per checkpoint, pooled over the three sessions (answered within the predicted regime's bound, "
           "after A):\n\n| Checkpoint | Calibrated | Extrapolated | (2) |\n|---|---|---|---|")
for lab in LABELS:
    out.append(f"| {lab} ({CHECKPOINTS[lab]}) | {f(bounds[lab]['calibrated']['inb'])} | "
               f"{f(bounds[lab]['extrapolated']['inb'])} | {'met' if bounds_ok[lab] else 'NOT met'} |")
out.append(f"\n(3) Yaw identical row for row on all 21 files: {'met' if yaw_ok else 'NOT met'}")
out.append(f"\n(1) coverage {'met' if all(cov_ok.values()) else 'NOT met'}; (2) bounds "
           f"{'met' if all(bounds_ok.values()) else 'NOT met'}; (3) yaw {'met' if yaw_ok else 'NOT met'} -> "
           f"**{'PASS' if passes else 'FAIL'}**")
out.append("reading: " + ("A is confirmed on fresh held-out sessions; the Gate 2 precondition closes, and the deployment "
                          "change (A in policy.idm.train._camera) is written for review" if passes else
                          "A is not the fix; the pitch item needs a new direction, with these three sessions as a second "
                          "fold family"))

out.append("\n## Reported beside (not judged)\n")
out.append("Per session, pooled over the seven checkpoints (before -> after; 1s / 2s / abstention / in-bound):\n")
out.append("| Session | True band | Before A | After A |\n|---|---|---|---|")
for s in SESSIONS:
    b, a = pooled(before, LABELS, [s]), pooled(after, LABELS, [s])
    for band in BANDS:
        note = " (under the floor: not interpreted)" if distinct[s][band] < FLOOR else ""
        out.append(f"| {s} | {band}{note} | {fmt(b[band])} | {fmt(a[band])} |")
out.append("\nPer checkpoint, pooled over the three sessions:\n")
out.append("| Checkpoint | True band | Before A | After A |\n|---|---|---|---|")
for lab in LABELS:
    b, a = pooled(before, [lab], SESSIONS), pooled(after, [lab], SESSIONS)
    for band in BANDS:
        out.append(f"| {lab} | {band} | {fmt(b[band])} | {fmt(a[band])} |")
out.append("\nPer session x checkpoint:\n")
out.append("| Session | Checkpoint | True band | Before A | After A |\n|---|---|---|---|---|")
for s in SESSIONS:
    for lab in LABELS:
        b = {band: ratios(before[(lab, s)][band]) for band in BANDS}
        a = {band: ratios(after[(lab, s)][band]) for band in BANDS}
        for band in BANDS:
            out.append(f"| {s} | {lab} | {band}{' (under the floor)' if distinct[s][band] < FLOOR else ''} | "
                       f"{fmt(b[band])} | {fmt(a[band])} |")
out.append("\nYaw raw-mu direction agreement on moving rows (|true| >= 0.5 deg), a transfer check:\n")
out.append("| Checkpoint | " + " | ".join(SESSIONS) + " |\n|---|" + "---|" * len(SESSIONS))
for lab in LABELS:
    out.append(f"| {lab} | " + " | ".join(f"{f(yaw_agree[(lab, s)][0])} (n {yaw_agree[(lab, s)][1]:,})"
                                          for s in SESSIONS) + " |")
out.append("\nInput sha256:")
for name, h in hashes.items():
    out.append(f"- {name}.jsonl {h}")
text = "\n".join(out) + "\n"
print(text)
(HERE / "confirm_score-out.md").write_text(text, encoding="utf-8", newline="\n")
json.dump({"passes": passes, "coverage_ok": cov_ok, "bounds_ok": bounds_ok, "yaw_ok": yaw_ok,
           "pooled_before": pb, "pooled_after": pa, "bounds": bounds, "distinct": distinct,
           "yaw_agree": {f"{k[0]}|{k[1]}": v for k, v in yaw_agree.items()}, "inputs": hashes},
          open(HERE / "confirm_score-results.json", "w", encoding="utf-8", newline="\n"), indent=1)
