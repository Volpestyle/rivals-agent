"""Countermeasures round 2 (fit-countermeasures-2-prereg.md 4d4576db): checks, S1-S4 per seed, K, and the outcome.
Stdlib only; reuses round 1's judge_cm.py for the unchanged rules (seed checks, stats, arm figures).

    python judge_cm2.py --d <cm2-d-s012/report.json> --e <cm2-e-s012/report.json> --a <A-reread.json>
                        --a-report <interim94-s012/report.json> --mac-sha <mac-sha256-cm2.txt> [--out reading.json]

Arms: A (the interim no-HUD, re-read), D (known-idle corruption P 0.5, runs 8-48), E (self-roll P 0.5, K 32, ramp 0.5).
Outcomes (pre-registered): A passes S -> sanity failure; D only (S and K) -> D works; E only -> E works; both -> the
higher mean F, D when within the two arms' combined F ranges; an arm passing S but failing K (and no arm passing both)
-> live but less skilled: round 3 tests that arm at half rate; neither passes S -> neither works."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_cm as J1                                                                   # noqa: E402

REVIEWED = {"policy/range_bc/train.py": "4c48a86558edbeb240c55a627cfa45b7c1b0a2c4a8be3ff3e40f19323369327c",
            "policy/range_bc/metrics.py": "ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5"}
OPTIONS = {"D": ("cm2-d-s012", "idle_corruption", {"p": .5, "run": [8, 48]}),
           "E": ("cm2-e-s012", "self_roll", {"p": .5, "steps": 32, "ramp": .5})}


def check_report(r, arm, mac):
    name, key, want_option = OPTIONS[arm]
    bad = []
    cfg = r["config"]
    want = {"epochs": 13, "weight_decay": 1e-4, "stride": 64, "lag": 0, "prev_dropout": .2, "arms": ["model_nohud"],
            "train_fraction": 1., "max_steps": None, "self_condition": None, "g1_press_source": "teacher_forced"}
    bad += [f"config.{k} = {cfg.get(k)!r}, pre-registered {v!r}" for k, v in want.items() if cfg.get(k) != v]
    for other in ("idle_corruption", "self_roll"):
        got = cfg.get(other)
        if other == key:
            if not got or {k: v for k, v in got.items() if k != "rule"} != want_option or not got.get("rule"):
                bad.append(f"config.{key} = {got!r}, pre-registered {want_option!r}")
        elif got is not None:
            bad.append(f"config.{other} = {got!r}, pre-registered null")
    if r.get("scope") != "plumbing":
        bad.append(f"scope {r.get('scope')!r}")
    if r.get("seeds") != [0, 1, 2]:
        bad.append(f"seeds {r.get('seeds')}")
    if (r.get("hud_parity") or {}).get("sha256") != J1.PARITY:
        bad.append("hud_parity.sha256")
    roles = {c["session_id"]: (c["role"], c["steps_sha256"]) for c in r["cohort"]}
    if roles != {s: ("dev" if s in J1.DEV else "train", h) for s, h in J1.STEPS.items()}:
        bad.append("cohort differs from the interim's")
    if r.get("test_opened"):
        bad.append("test_opened")
    names = {f"model_nohud-seed{s}.pt" for s in J1.SEEDS}
    if set(r["checkpoints"]) != names:
        bad.append(f"checkpoints {sorted(r['checkpoints'])}")
    for n, h in r["checkpoints"].items():
        if mac.get(f"{name}/{n}") != h:
            bad.append(f"checkpoint {name}/{n}: Mac {mac.get(name + '/' + n)} != report {h}")
    for path, h in REVIEWED.items():
        if r["code_closure"].get(path) != h:
            bad.append(f"code_closure {path} {r['code_closure'].get(path)}")
    return [f"{arm}: {b}" for b in bad]


def outcome(arms):
    if arms["A"]["passes_S"]:
        return "A passes: sanity failure (the metrics are wrong; stop and report)"
    ok = {k: arms[k]["passes_S"] and arms[k]["K"] for k in ("D", "E")}
    if ok["D"] and ok["E"]:
        d, e = arms["D"]["F"], arms["E"]["F"]
        pick = "E" if e["mean"] - d["mean"] > d["range"] + e["range"] else "D"
        return f"Both work: {pick} by the F rule, D on a tie (mean F D {d['mean']:.4f}, E {e['mean']:.4f})"
    if ok["D"]:
        return "D works"
    if ok["E"]:
        return "E works"
    live = [k for k in ("D", "E") if arms[k]["passes_S"]]
    if live:
        return f"Live but less skilled: {' and '.join(live)} (round 3 at half rate)"
    return "Neither works"


def main(argv=None):
    ap = argparse.ArgumentParser()
    for flag in ("--d", "--e", "--a", "--a-report", "--mac-sha"):
        ap.add_argument(flag, required=True)
    ap.add_argument("--out")
    x = ap.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    reports, a, ar = {"D": load(x.d), "E": load(x.e)}, load(x.a), load(x.a_report)
    mac = {}
    for line in Path(x.mac_sha).read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and len(parts[0]) == 64:
            mac[parts[1]] = parts[0]
    failures = [f for k, r in reports.items() for f in check_report(r, k, mac)]
    if not all(a["equal"].values()):
        failures.append(f"A-reread not byte-identical: {a['equal']}")
    arms = {"A": J1.arm(a["self_fed_checks"]["model_nohud"], a["executed_teacher_forced"]["model_nohud"],
                        ar["metrics"]["dev"]["self_fed"]["model_nohud"])}
    for k, r in reports.items():
        m = r["metrics"]["dev"]
        arms[k] = J1.arm(m["self_fed_checks"]["model_nohud"], m["executed_teacher_forced"]["model_nohud"],
                         m["self_fed"]["model_nohud"])
    ta = arms["A"]["T"]
    for k in ("D", "E"):
        bar = ta["mean"] - (ta["range"] + arms[k]["T"]["range"])
        arms[k]["K"], arms[k]["K_bar"] = arms[k]["T"]["mean"] >= bar, bar
    logs = lambda r: [r["epochs_log"][f"model_nohud-seed{s}.pt"] for s in J1.SEEDS]
    context = {k: {"argmin_epochs": [min(range(len(l)), key=lambda i: (l[i]["dev"]["total"], i)) + 1 for l in logs(r)],
                   "dev_total_last": [l[-1]["dev"]["total"] for l in logs(r)],
                   "train_loss_last": [l[-1]["train_loss"] for l in logs(r)],
                   "fit_seconds": [r["fit_seconds"][f"model_nohud-seed{s}.pt"] for s in J1.SEEDS],
                   "tf_camera_mae": [r["metrics"]["dev"]["teacher_forced"]["model_nohud"][s]["all"]["camera_mae_mean"]
                                     for s in J1.SEEDS]}
               for k, r in reports.items()}
    context["A"] = {"dev_total_last": [l[-1]["dev"]["total"] for l in logs(ar)],
                    "train_loss_last": [l[-1]["train_loss"] for l in logs(ar)]}
    out = {"arms": arms, "outcome": outcome(arms), "context": context, "check_failures": failures,
           "persistence_camera": .418, "ar2_camera": .376}
    text = json.dumps(out, indent=1, sort_keys=True)
    if x.out:
        Path(x.out).open("x", encoding="utf-8").write(text + "\n")
    print(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
