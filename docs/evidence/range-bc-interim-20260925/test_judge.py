"""Re-test the adapted judge.py (amendment 1): figures against an independent read of the raw reports, checks, and the
determinism check on constructed equal / perturbed pairs."""
import copy, json, shutil, sys, io, contextlib
from pathlib import Path
H, SP, P5, S0 = map(Path, sys.argv[1:5])
sys.path.insert(0, str(H))
import judge

def indep(r, arm, seed):
    log = r["epochs_log"][arm + "-seed" + str(seed) + ".pt"]
    tot = [e["dev"]["total"] for e in log]
    m = min(tot)
    a = r["metrics"]["dev"]["teacher_forced"][arm][str(seed)]["all"]
    return tot[-1], tot.index(m) + 1, m, a["macro_press_f1_tol"], a["camera_mae_mean"]

ok = True
def expect(cond, msg):
    global ok
    print(("PASS " if cond else "FAIL ") + msg); ok &= bool(cond)

for label, path, seeds in (("p5", P5, [0, 1]), ("interim94-seed0", S0, [0])):
    r = json.loads(path.read_text(encoding="utf-8"))
    per, base = judge.extract(r, seeds)
    for seed in seeds:
        for arm in judge.ARMS:
            got = per[seed][arm]
            want = indep(r, arm, seed)
            expect((got["dev_total_last"], got["argmin_epoch"], got["dev_total_min"], got["tf_macro_press_f1_tol"],
                    got["tf_camera_mae_mean"]) == want, f"{label} {arm} seed {seed} figures {want}")
    tb = r["metrics"]["dev"]["teacher_forced"]
    expect(base["ar2"]["camera_mae_mean"] == tb["ar2"]["all"]["camera_mae_mean"] and base["persistence"]["camera_mae_mean"]
           == tb["persistence"]["all"]["camera_mae_mean"], f"{label} baselines ar2 {base['ar2']} persistence {base['persistence']}")
    print(f"{label} checks:", judge.check(r, "interim94", seeds))

# the p5 record's numbers (plumbing record): no-HUD 1.6719, twin 1.6314, ar2 0.376, persistence 0.418
p5 = json.loads(P5.read_text(encoding="utf-8")); per, base = judge.extract(p5, [0, 1])
expect(round(per[0]["model_nohud"]["dev_total_last"], 4) == 1.6719 and round(per[0]["history_only"]["dev_total_last"], 4) == 1.6314
       and round(base["ar2"]["camera_mae_mean"], 3) == .376 and round(base["persistence"]["camera_mae_mean"], 3) == .418,
       "p5 seed 0 equals the plumbing record")
p5_fail = judge.check(p5, "interim94", [0, 1, 2])
expect(any("seeds" in f for f in p5_fail) and any("epochs_log has no model_nohud-seed2" in f for f in p5_fail)
       and any("config.epochs" in f for f in p5_fail) and any("config.stride" in f for f in p5_fail),
       f"p5 against seeds [0,1,2] fails seeds, missing seed 2, epochs, stride: {len(p5_fail)} failures")

# full mode on constructed run dirs
s0 = json.loads(S0.read_text(encoding="utf-8"))
def multi(r):
    m = copy.deepcopy(r); m["seeds"] = [0, 1, 2]
    for arm in judge.ARMS:
        for k in (1, 2):
            m["epochs_log"][f"{arm}-seed{k}.pt"] = copy.deepcopy(r["epochs_log"][f"{arm}-seed0.pt"])
            m["checkpoints"][f"{arm}-seed{k}.pt"] = "x" * 64
            for block in ("teacher_forced", "self_fed", "sanity"):
                if arm in m["metrics"]["dev"][block]:
                    m["metrics"]["dev"][block][arm][str(k)] = copy.deepcopy(r["metrics"]["dev"][block][arm]["0"])
    for e in m["epochs_log"]["model_nohud-seed0.pt"]:
        e["seconds"] += 1                        # wall time may differ; it is not a determinism difference
    return m
def run(case, s012, ref):
    d = SP / "judge-test" / case
    shutil.rmtree(d, ignore_errors=True)
    for name, rep in (("interim94-s012", s012), ("interim94-control47-s012", s012), ("interim94-seed0", ref)):
        (d / name).mkdir(parents=True); (d / name / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = judge.main([str(d)])
    return rc, json.loads(buf.getvalue())
rc, out = run("equal", multi(s0), s0)
print("equal case failures:", out["check_failures"])
expect(out["determinism"]["equal"] and all("control47" in f for f in out["check_failures"]),
       "equal: determinism passes; only the control's cohort/builds fail (constructed from a 94-minute report)")
expect(out["groups"]["interim94"]["delta_loss"]["range"] == 0 and "reading" in out, "equal: reading computed")
bad = multi(s0); bad["checkpoints"]["history_only-seed0.pt"] = "0" * 64
bad["metrics"]["dev"]["teacher_forced"]["model_nohud"]["0"]["all"]["camera_mae_mean"] += 1e-12
bad["epochs_log"]["history_only-seed0.pt"][-1]["dev"]["total"] += 1e-12
rc, out = run("perturbed", bad, s0)
print("perturbed determinism:", out["determinism"]["differences"])
d = out["determinism"]["differences"]
expect(rc == 1 and not out["determinism"]["equal"] and any("checkpoint history_only" in x for x in d)
       and any("teacher_forced model_nohud" in x for x in d) and any("epochs_log history_only" in x for x in d) and len(d) == 3,
       "perturbed: all three differences reported, nothing else")
rc, out = run("p5", p5, s0)
expect(rc == 1 and not out["determinism"]["equal"], f"p5 against interim94-seed0: determinism differs ({len(out['determinism']['differences'])} differences)")
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
