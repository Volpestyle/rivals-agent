"""Tests judge_cm.py on synthetic reports built from arm A's data (A-reread.json) and the interim report; the real
cm-s012 report is not read here."""
import copy, io, json, contextlib, sys
from pathlib import Path
H, SP = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(H / "countermeasures"))
import judge_cm as J
A = json.loads((H / "countermeasures/A-reread.json").read_text(encoding="utf-8"))
AR = json.loads((H / "interim94/runs/interim94-s012/report.json").read_text(encoding="utf-8"))
def fake():
    r = copy.deepcopy(AR)
    r["config"].update(arms=["model_nohud", "frames_only_nohud"], prev_dropout=.2,
                       self_condition={"p": .5, "ramp": .5, "rule": "x"})
    r["checkpoints"] = {f"{a}-seed{s}.pt": f"{i}{s}" * 32 for i, a in enumerate(J.ARMS.values()) for s in J.SEEDS}
    r["code_closure"] = dict(J.REVIEWED)
    d = r["metrics"]["dev"]
    d["self_fed_checks"] = {n: copy.deepcopy(A["self_fed_checks"]["model_nohud"]) for n in J.ARMS.values()}
    d["executed_teacher_forced"] = {n: copy.deepcopy(A["executed_teacher_forced"]["model_nohud"]) for n in J.ARMS.values()}
    d["self_fed"]["frames_only_nohud"] = copy.deepcopy(d["self_fed"]["model_nohud"])
    r["epochs_log"] = {f"{n}-seed{s}.pt": AR["epochs_log"][f"model_nohud-seed{s}.pt"] for n in J.ARMS.values() for s in J.SEEDS}
    return r
def good(c):
    c.update(hold_onset_recall=.1, press_ratio=1., camera_mae=1., any_hold_share=.6)
    for a in c["actions"].values():
        a["press_ratio"] = 1.
def run(r, a=A):
    d = SP / "jcm"; d.mkdir(exist_ok=True)
    (d / "cm.json").write_text(json.dumps(r)); (d / "a.json").write_text(json.dumps(a))
    (d / "mac.txt").write_text("".join(f"{h}  cm-s012/{n}\n" for n, h in r["checkpoints"].items()))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = J.main(["--cm", str(d / "cm.json"), "--a", str(d / "a.json"), "--a-report",
                     str(H / "interim94/runs/interim94-s012/report.json"), "--mac-sha", str(d / "mac.txt")])
    return rc, json.loads(buf.getvalue())
ok = True
def expect(c, msg):
    global ok; print(("PASS " if c else "FAIL ") + msg); ok &= bool(c)
rc, o = run(fake())
expect(rc == 0 and o["check_failures"] == [] and o["outcome"] == "Neither works" and not o["arms"]["A"]["passes_S"],
       f"A copies: neither works, no check failures ({o['outcome']})")
expect(abs(o["arms"]["A"]["T"]["mean"] - 0.0351) < 1e-3 and o["arms"]["B"]["K"] and o["arms"]["C"]["K"],
       "A's T mean 0.0351; an arm equal to A keeps K")
r = fake()
for s in J.SEEDS: good(r["metrics"]["dev"]["self_fed_checks"]["frames_only_nohud"][s])
rc, o = run(r); expect(o["outcome"] == "B works" and o["arms"]["B"]["passes_S"], f"B passes S and K: {o['outcome']}")
r2 = copy.deepcopy(r)
for s in J.SEEDS: r2["metrics"]["dev"]["executed_teacher_forced"]["frames_only_nohud"][s]["macro_press_f1_tol"] = 0.
rc, o = run(r2); expect(o["outcome"] == "Neither works" and not o["arms"]["B"]["K"], "B passes S but loses K: neither")
r3 = copy.deepcopy(r)
for s in J.SEEDS: good(r3["metrics"]["dev"]["self_fed_checks"]["model_nohud"][s])
rc, o = run(r3); expect(o["outcome"].startswith("Both work: B"), f"both, equal F: B by the tie rule ({o['outcome']})")
for s in J.SEEDS: r3["metrics"]["dev"]["self_fed"]["model_nohud"][s]["all"]["macro_press_f1_tol"] = .5
rc, o = run(r3); expect(o["outcome"].startswith("Both work: C"), f"both, C's F clearly higher: C ({o['outcome']})")
r4 = copy.deepcopy(r)
good(r4["metrics"]["dev"]["self_fed_checks"]["model_nohud"]["0"])      # C passes one seed only
rc, o = run(r4); expect(o["outcome"] == "B works" and not o["arms"]["C"]["passes_S"], "C with 1 of 3 seeds does not pass S")
a2 = copy.deepcopy(A)
for s in J.SEEDS: good(a2["self_fed_checks"]["model_nohud"][s])
rc, o = run(fake(), a2); expect(o["outcome"].startswith("A passes"), "A passing S is the sanity failure")
c = copy.deepcopy(A["self_fed_checks"]["model_nohud"]["0"]); good(c)
c["hold_onset_recall"] = .05; expect(J.seed_checks(c)["S1"], "S1 at exactly 0.05 passes")
c["hold_onset_recall"] = .0499; expect(not J.seed_checks(c)["S1"], "S1 at 0.0499 fails")
c = copy.deepcopy(A["self_fed_checks"]["model_nohud"]["0"]); good(c)
for i, a in enumerate(c["actions"].values()):
    if i < 5: a["press_ratio"] = 3.
expect(not J.seed_checks(c)["S2"], "S2 with only 5 of 10 actions in band fails")
c = copy.deepcopy(A["self_fed_checks"]["model_nohud"]["0"]); good(c); c["human_any_hold_share"] = None
expect(not J.seed_checks(c)["S4"], "S4 with a None human share fails")
c = copy.deepcopy(A["self_fed_checks"]["model_nohud"]["0"]); good(c); c["camera_mae"] = .95 * c["zero_motion_camera_mae"] + 1e-9
expect(not J.seed_checks(c)["S3"], "S3 just above 0.95 x zero motion fails")
bad = fake(); bad["config"]["stride"] = 48; bad["code_closure"]["policy/range_bc/train.py"] = "0" * 64
rc, o = run(bad); expect(rc == 1 and any("stride" in f for f in o["check_failures"]) and any("code_closure" in f for f in o["check_failures"]),
                         "config and code-closure mismatches are caught")
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
