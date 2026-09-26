"""Countermeasures test (fit-countermeasures-prereg.md 078d5351): checks, the self-fed checks S1-S4 per seed, the
skill-retention rule K, and the pre-registered outcome. Stdlib only; reads JSON, changes nothing.

    python judge_cm.py --cm <cm-s012/report.json> --a <A-reread.json> --a-report <interim94-s012/report.json>
                       --mac-sha <mac-sha256-cm.txt> [--out reading.json]

Arm A: interim94-s012's model_nohud, re-read on 807d35f (A-reread.json); its self-fed F from the stored report.
Arm B: cm-s012's frames_only_nohud.  Arm C: cm-s012's model_nohud (self-conditioned, p 0.5, ramp 0.5).
Rules (fixed in the pre-registration):
  S1 hold_onset_recall >= 0.05
  S2 pooled press_ratio in [0.5, 2] and >= 6 of the 10 live actions' press_ratio in [0.5, 2]
  S3 camera_mae <= 0.95 x zero_motion_camera_mae
  S4 any_hold_share in [0.5, 1.3] x human_any_hold_share (observable rows); fails if either is None
  seed passes S = S1..S4; arm passes S = >= 2 of 3 seeds
  K  mean T(arm) >= mean T(A) - (range T(A) + range T(arm)); T = executed teacher-forced macro press-F1
  outcome: A passes S -> sanity failure; C only (S and K) -> C works; B only -> B works; both -> higher mean F
  (self-fed macro press-F1), B when within the two arms' combined F ranges; neither -> neither works."""
import argparse
import json
from pathlib import Path
import sys

SEEDS = ("0", "1", "2")
PARITY = "e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801"
STEPS = {"20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
         "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
         "20260924T232304-170Z-12024-1": "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
         "20260925T021320-371Z-7804-1": "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
         "20260925T025230-605Z-7804-2": "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288",
         "20260923T171533-187Z-33696-5": "dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e",
         "20260923T205528-900Z-45572-3": "941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98"}
DEV = {"20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3"}
REVIEWED = {"policy/range_bc/train.py": "dbfd8b1d99f196e5a01e9bbcfa31ccd19f14193ec1bd1b5ae9df573698d0883f",
            "policy/range_bc/metrics.py": "ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5"}
ARMS = {"B": "frames_only_nohud", "C": "model_nohud"}


def check_report(r, mac):
    bad = []
    cfg = r["config"]
    want = {"epochs": 13, "weight_decay": 1e-4, "stride": 64, "lag": 0, "prev_dropout": .2,
            "arms": ["model_nohud", "frames_only_nohud"], "train_fraction": 1., "max_steps": None}
    bad += [f"config.{k} = {cfg.get(k)!r}, pre-registered {v!r}" for k, v in want.items() if cfg.get(k) != v]
    sc = cfg.get("self_condition") or {}
    if sc.get("p") != .5 or sc.get("ramp") != .5 or not sc.get("rule"):
        bad.append(f"config.self_condition {sc}")
    if r.get("scope") != "plumbing":
        bad.append(f"scope {r.get('scope')!r}")
    if r.get("seeds") != [0, 1, 2]:
        bad.append(f"seeds {r.get('seeds')}")
    if (r.get("hud_parity") or {}).get("sha256") != PARITY:
        bad.append("hud_parity.sha256")
    roles = {c["session_id"]: (c["role"], c["steps_sha256"]) for c in r["cohort"]}
    if roles != {s: ("dev" if s in DEV else "train", h) for s, h in STEPS.items()}:
        bad.append("cohort differs from the interim's")
    if r.get("test_opened"):
        bad.append("test_opened")
    names = {f"{a}-seed{s}.pt" for a in ARMS.values() for s in SEEDS}
    if set(r["checkpoints"]) != names:
        bad.append(f"checkpoints {sorted(r['checkpoints'])}")
    for n, h in r["checkpoints"].items():
        if mac.get(f"cm-s012/{n}") != h:
            bad.append(f"checkpoint {n}: Mac {mac.get('cm-s012/' + n)} != report {h}")
    for path, h in REVIEWED.items():
        if r["code_closure"].get(path) != h:
            bad.append(f"code_closure {path} {r['code_closure'].get(path)}")
    return bad


def seed_checks(c):
    s1 = c["hold_onset_recall"] is not None and c["hold_onset_recall"] >= .05
    ratios = [a["press_ratio"] for a in c["actions"].values()]
    in_band = sum(1 for x in ratios if x is not None and .5 <= x <= 2.)
    s2 = c["press_ratio"] is not None and .5 <= c["press_ratio"] <= 2. and in_band >= 6
    s3 = c["camera_mae"] is not None and c["camera_mae"] <= .95 * c["zero_motion_camera_mae"]
    m, h = c["any_hold_share"], c["human_any_hold_share"]
    s4 = m is not None and h is not None and .5 * h <= m <= 1.3 * h
    return {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "pass": s1 and s2 and s3 and s4,
            "values": {"hold_onset_recall": c["hold_onset_recall"], "press_ratio": c["press_ratio"],
                       "actions_in_band": in_band, "live_actions": len(ratios), "camera_mae": c["camera_mae"],
                       "camera_bar": .95 * c["zero_motion_camera_mae"], "any_hold_share": m,
                       "human_any_hold_share": h, "any_hold_excluded_steps": c.get("any_hold_excluded_steps")}}


def stats(v):
    return {"values": v, "mean": sum(v) / len(v), "range": max(v) - min(v)}


def arm(checks, executed, self_fed):
    seeds = {s: seed_checks(checks[s]) for s in SEEDS}
    t = stats([executed[s]["macro_press_f1_tol"] for s in SEEDS])
    f = stats([self_fed[s]["all"]["macro_press_f1_tol"] for s in SEEDS])
    return {"seeds": seeds, "passes_S": sum(x["pass"] for x in seeds.values()) >= 2, "T": t, "F": f,
            "self_fed_camera_mae": [checks[s]["camera_mae"] for s in SEEDS]}


def outcome(arms):
    a, b, c = arms["A"], arms["B"], arms["C"]
    if a["passes_S"]:
        return "A passes: sanity failure (the metrics are wrong; stop and report)"
    ok = {k: arms[k]["passes_S"] and arms[k]["K"] for k in ("B", "C")}
    if ok["B"] and ok["C"]:
        d = c["F"]["mean"] - b["F"]["mean"]
        pick = "C" if d > b["F"]["range"] + c["F"]["range"] else "B"
        return f"Both work: {pick} by the F rule, B on a tie (mean F B {b['F']['mean']:.4f}, C {c['F']['mean']:.4f})"
    if ok["C"]:
        return "C works"
    if ok["B"]:
        return "B works"
    return "Neither works"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cm", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--a-report", required=True)
    ap.add_argument("--mac-sha", required=True)
    ap.add_argument("--out")
    x = ap.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    cm, a, ar = load(x.cm), load(x.a), load(x.a_report)
    mac = {}
    for line in Path(x.mac_sha).read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            mac[parts[1]] = parts[0]
    failures = check_report(cm, mac)
    if not all(a["equal"].values()):
        failures.append(f"A-reread not byte-identical: {a['equal']}")
    m = cm["metrics"]["dev"]
    arms = {"A": arm(a["self_fed_checks"]["model_nohud"], a["executed_teacher_forced"]["model_nohud"],
                     ar["metrics"]["dev"]["self_fed"]["model_nohud"])}
    for k, name in ARMS.items():
        arms[k] = arm(m["self_fed_checks"][name], m["executed_teacher_forced"][name], m["self_fed"][name])
    ta = arms["A"]["T"]
    for k in ("B", "C"):
        bar = ta["mean"] - (ta["range"] + arms[k]["T"]["range"])
        arms[k]["K"], arms[k]["K_bar"] = arms[k]["T"]["mean"] >= bar, bar
    context = {k: {"argmin_epochs": [min(range(len(log)), key=lambda i: (log[i]["dev"]["total"], i)) + 1
                                     for log in (cm["epochs_log"][f"{ARMS[k]}-seed{s}.pt"] for s in SEEDS)],
                   "train_loss_last": [cm["epochs_log"][f"{ARMS[k]}-seed{s}.pt"][-1]["train_loss"] for s in SEEDS],
                   "dev_total_last": [cm["epochs_log"][f"{ARMS[k]}-seed{s}.pt"][-1]["dev"]["total"] for s in SEEDS]}
               for k in ARMS}
    context["A"] = {"train_loss_last": [ar["epochs_log"][f"model_nohud-seed{s}.pt"][-1]["train_loss"] for s in SEEDS],
                    "dev_total_last": [ar["epochs_log"][f"model_nohud-seed{s}.pt"][-1]["dev"]["total"] for s in SEEDS]}
    out = {"arms": arms, "outcome": outcome(arms), "context": context, "check_failures": failures,
           "persistence_camera": .418, "ar2_camera": .376}
    text = json.dumps(out, indent=1, sort_keys=True)
    if x.out:
        Path(x.out).open("x", encoding="utf-8").write(text + "\n")
    print(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
