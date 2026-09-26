"""Interim fit (fit-interim-prereg.md 8094bdd1): check the six-run queue's reports against the pre-registration and
compute the pre-registered reading. Stdlib only; reads report.json files, changes nothing.

    python judge.py <runs dir holding interim94-seed{0,1,2} and interim94-control47-seed{0,1,2}>/ [--out reading.json]

Checks per report (a failure is printed and makes the exit status 1; the reading is still computed):
  scope plumbing; config epochs 13, weight_decay 1e-4, stride 64, lag 0, arms [model_nohud, history_only],
  train_fraction 1, max_steps None; seeds [k]; hud_parity.sha256 e9efe999; patch_equivalence kit_version and builds;
  the cohort (session ids, roles and step-table sha256) equal to the pre-registration's; test_opened false.
Reading (descriptive, no gate): per arm and seed the dev total loss at the last epoch, its argmin epoch and minimum,
teacher-forced macro press-F1 (macro_press_f1_tol) and camera MAE (camera_mae_mean) from the "all" stratum; the
ar2 and persistence baselines; Δloss = no-HUD - twin (last-epoch dev total) and ΔF1 = no-HUD - twin (tf macro press-F1)
per seed, their means and ranges; the pre-registered rules closes / reverses / opens / not resolved; the recipe-health
note (no-HUD argmin epoch vs 13)."""
import argparse
import json
from pathlib import Path
import sys

PARITY = "e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801"
KIT = "Season 10, Version 20260911"
STEPS = {"20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
         "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
         "20260924T232304-170Z-12024-1": "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
         "20260925T021320-371Z-7804-1": "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
         "20260925T025230-605Z-7804-2": "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288",
         "20260923T171533-187Z-33696-5": "dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e",
         "20260923T205528-900Z-45572-3": "941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98"}
DEV = {"20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3"}
TRAIN = {"interim94": set(STEPS) - DEV,
         "control47": {"20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6"}}
OLD, NEW = "1.1.3870120/build25364676", "1.1.3892207/build25501035"
BUILDS = {"interim94": [OLD, NEW], "control47": [OLD]}
ARMS = ("model_nohud", "history_only")


def check(report, group, seed):
    bad = []
    cfg = report["config"]
    want = {"epochs": 13, "weight_decay": 1e-4, "stride": 64, "lag": 0, "arms": list(ARMS), "train_fraction": 1.0,
            "max_steps": None}
    for k, v in want.items():
        if cfg.get(k) != v:
            bad.append(f"config.{k} = {cfg.get(k)!r}, pre-registered {v!r}")
    if report.get("scope") != "plumbing":
        bad.append(f"scope {report.get('scope')!r}")
    if report.get("seeds") != [seed]:
        bad.append(f"seeds {report.get('seeds')}")
    if (report.get("hud_parity") or {}).get("sha256") != PARITY:
        bad.append(f"hud_parity.sha256 {(report.get('hud_parity') or {}).get('sha256')}")
    pe = report.get("patch_equivalence") or {}
    if pe.get("kit_version") != KIT or pe.get("builds") != BUILDS[group] or pe.get("default") is not True:
        bad.append(f"patch_equivalence {pe}")
    roles = {c["session_id"]: (c["role"], c["steps_sha256"]) for c in report["cohort"]}
    want_roles = {s: ("dev" if s in DEV else "train", STEPS[s]) for s in DEV | TRAIN[group]}
    if roles != want_roles:
        bad.append(f"cohort {sorted(roles)} differs from the pre-registration")
    if report.get("test_opened"):
        bad.append("test_opened")
    return bad


def arm_numbers(report, arm, seed):
    log = report["epochs_log"][f"{arm}-seed{seed}.pt"]
    total = [e["dev"]["total"] for e in log]
    i = min(range(len(total)), key=lambda j: (total[j], j))
    tf = report["metrics"]["dev"]["teacher_forced"][arm][str(seed)]["all"]
    return {"dev_total_last": total[-1], "dev_heads_last": log[-1]["dev"], "argmin_epoch": i + 1, "dev_total_min": total[i],
            "tf_macro_press_f1_tol": tf["macro_press_f1_tol"], "tf_camera_mae_mean": tf["camera_mae_mean"]}


def stats(values):
    return {"values": values, "mean": sum(values) / len(values), "min": min(values), "max": max(values),
            "range": max(values) - min(values)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    runs, failures, out = Path(a.runs), [], {"groups": {}}
    for group, prefix in (("interim94", "interim94-seed"), ("control47", "interim94-control47-seed")):
        g = {"per_seed": {}}
        for seed in (0, 1, 2):
            path = runs / f"{prefix}{seed}" / "report.json"
            if not path.exists():
                failures.append(f"{path}: missing")
                continue
            report = json.loads(path.read_text(encoding="utf-8"))
            failures += [f"{prefix}{seed}: {b}" for b in check(report, group, seed)]
            g["per_seed"][seed] = {arm: arm_numbers(report, arm, seed) for arm in ARMS}
            base = report["metrics"]["dev"]["teacher_forced"]
            g["baselines"] = {b: {k: base[b]["all"][k] for k in ("macro_press_f1_tol", "camera_mae_mean")}
                              for b in ("ar2", "persistence")}
        if g["per_seed"]:
            ps = g["per_seed"].values()
            g["delta_loss"] = stats([s["model_nohud"]["dev_total_last"] - s["history_only"]["dev_total_last"] for s in ps])
            g["delta_f1"] = stats([s["model_nohud"]["tf_macro_press_f1_tol"] - s["history_only"]["tf_macro_press_f1_tol"]
                                   for s in ps])
            g["nohud_argmin_epochs"] = [s["model_nohud"]["argmin_epoch"] for s in ps]
            for arm in ARMS:
                for k in ("dev_total_last", "tf_macro_press_f1_tol", "tf_camera_mae_mean"):
                    g[f"{arm}.{k}"] = stats([s[arm][k] for s in ps])
        out["groups"][group] = g
    i, c = out["groups"].get("interim94", {}), out["groups"].get("control47", {})
    if "delta_loss" in i and "delta_loss" in c:
        dl, cl, df, cf = i["delta_loss"], c["delta_loss"], i["delta_f1"], c["delta_f1"]
        closes = cl["mean"] - dl["mean"] > dl["range"] + cl["range"]
        reverses = dl["max"] < 0
        opens = df["mean"] - cf["mean"] > df["range"] + cf["range"]
        out["reading"] = {"closes": closes, "reverses": reverses, "opens_f1": opens,
                          "not_resolved": not (closes or reverses or opens),
                          "rule": "closes: Δloss(80.5) < Δloss(33.6) by more than both seed ranges combined; reverses: every "
                                  "seed's Δloss(80.5) < 0; opens: ΔF1(80.5) > ΔF1(33.6) by more than both ranges combined",
                          "recipe_health": {"interim94_nohud_argmin_epochs": i["nohud_argmin_epochs"],
                                            "control47_nohud_argmin_epochs": c["nohud_argmin_epochs"],
                                            "note": "argmin well before 13 = overfitting; 13 = still falling; report, do not act"}}
    out["check_failures"] = failures
    text = json.dumps(out, indent=1, sort_keys=True, default=str)
    if a.out:
        Path(a.out).open("x", encoding="utf-8").write(text + "\n")
    print(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
