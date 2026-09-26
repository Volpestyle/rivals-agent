"""Tests judge_cm2.py on synthetic reports built from arm A's data and the interim report (no D/E output exists or
is read here).   python test_judge_cm2.py <handoff dir> <scratch dir>"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys

H, SP = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(H / "countermeasures"))
import judge_cm2 as J                                                                   # noqa: E402

A = json.loads((H / "countermeasures/A-reread.json").read_text(encoding="utf-8"))
AR = json.loads((H / "interim94/runs/interim94-s012/report.json").read_text(encoding="utf-8"))


def fake(arm):
    name, key, option = J.OPTIONS[arm]
    r = copy.deepcopy(AR)
    r["config"].update(arms=["model_nohud"], prev_dropout=.2, self_condition=None, g1_press_source="teacher_forced",
                       idle_corruption=None, self_roll=None)
    r["config"][key] = {**option, "rule": "x"}
    r["checkpoints"] = {f"model_nohud-seed{s}.pt": f"{arm}{s}" * 32 for s in J.J1.SEEDS}
    r["code_closure"] = dict(J.REVIEWED)
    d = r["metrics"]["dev"]
    d["self_fed_checks"] = {"model_nohud": copy.deepcopy(A["self_fed_checks"]["model_nohud"])}
    d["executed_teacher_forced"] = {"model_nohud": copy.deepcopy(A["executed_teacher_forced"]["model_nohud"])}
    return r


def good(r):
    for c in r["metrics"]["dev"]["self_fed_checks"]["model_nohud"].values():
        c.update(hold_onset_recall=.1, press_ratio=1., camera_mae=1., any_hold_share=.6)
        for a in c["actions"].values():
            a["press_ratio"] = 1.
    return r


def run(d, e, a=A):
    w = SP / "jcm2"
    w.mkdir(exist_ok=True)
    for n, obj in (("d.json", d), ("e.json", e), ("a.json", a)):
        (w / n).write_text(json.dumps(obj))
    (w / "mac.txt").write_text("".join(f"{h}  {J.OPTIONS[k][0]}/{n}\n" for k, r in (("D", d), ("E", e))
                                       for n, h in r["checkpoints"].items()))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = J.main(["--d", str(w / "d.json"), "--e", str(w / "e.json"), "--a", str(w / "a.json"), "--a-report",
                     str(H / "interim94/runs/interim94-s012/report.json"), "--mac-sha", str(w / "mac.txt")])
    return rc, json.loads(buf.getvalue())


ok = True


def expect(c, msg):
    global ok
    print(("PASS " if c else "FAIL ") + msg)
    ok &= bool(c)


def set_t(r, value):
    for s in J.J1.SEEDS:
        r["metrics"]["dev"]["executed_teacher_forced"]["model_nohud"][s]["macro_press_f1_tol"] = value


def set_f(r, value):
    for s in J.J1.SEEDS:
        r["metrics"]["dev"]["self_fed"]["model_nohud"][s]["all"]["macro_press_f1_tol"] = value


rc, o = run(fake("D"), fake("E"))
expect(rc == 0 and o["check_failures"] == [] and o["outcome"] == "Neither works", f"A copies: neither ({o['outcome']})")
rc, o = run(good(fake("D")), fake("E"))
expect(o["outcome"] == "D works", f"D passes S and K: {o['outcome']}")
rc, o = run(fake("D"), good(fake("E")))
expect(o["outcome"] == "E works", f"E passes S and K: {o['outcome']}")
rc, o = run(good(fake("D")), good(fake("E")))
expect(o["outcome"].startswith("Both work: D"), f"both, equal F: D on a tie ({o['outcome']})")
e = good(fake("E"))
set_f(e, .5)
rc, o = run(good(fake("D")), e)
expect(o["outcome"].startswith("Both work: E"), f"both, E's F clearly higher: E ({o['outcome']})")
d = good(fake("D"))
set_t(d, 0.)
rc, o = run(d, fake("E"))
expect(o["outcome"] == "Live but less skilled: D (round 3 at half rate)" and not o["arms"]["D"]["K"],
       f"D passes S, fails K: {o['outcome']}")
e = good(fake("E"))
set_t(e, 0.)
rc, o = run(d, e)
expect(o["outcome"] == "Live but less skilled: D and E (round 3 at half rate)", f"both S-only: {o['outcome']}")
rc, o = run(d, good(fake("E")))
expect(o["outcome"] == "E works", f"D S-only and E works: E works ({o['outcome']})")
a2 = copy.deepcopy(A)
for c in a2["self_fed_checks"]["model_nohud"].values():
    c.update(hold_onset_recall=.1, press_ratio=1., camera_mae=1., any_hold_share=.6)
    for x in c["actions"].values():
        x["press_ratio"] = 1.
rc, o = run(fake("D"), fake("E"), a2)
expect(o["outcome"].startswith("A passes"), "A passing S is the sanity failure")
bad = fake("D")
bad["config"]["self_roll"] = {"p": .5, "steps": 32, "ramp": .5, "rule": "x"}
bad["config"]["idle_corruption"]["run"] = [8, 40]
bad["code_closure"]["policy/range_bc/train.py"] = "0" * 64
rc, o = run(bad, fake("E"))
f = o["check_failures"]
expect(rc == 1 and any("config.self_roll" in x for x in f) and any("config.idle_corruption" in x for x in f)
       and any("code_closure" in x for x in f), f"option, cross-option and code mismatches caught ({len(f)})")
d = fake("D")
rcx, ox = None, None
wdir = SP / "jcm2"
(wdir / "d.json").write_text(json.dumps(d))
(wdir / "e.json").write_text(json.dumps(fake("E")))
(wdir / "a.json").write_text(json.dumps(A))
(wdir / "mac.txt").write_text("".join(f"{'0' * 64}  cm2-d-s012/{n}\n" for n in d["checkpoints"]))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rcx = J.main(["--d", str(wdir / "d.json"), "--e", str(wdir / "e.json"), "--a", str(wdir / "a.json"), "--a-report",
                  str(H / "interim94/runs/interim94-s012/report.json"), "--mac-sha", str(wdir / "mac.txt")])
ox = json.loads(buf.getvalue())
expect(rcx == 1 and sum("Mac" in x for x in ox["check_failures"]) == 6, "Mac checkpoint hash mismatches caught (3 D, 3 E missing)")
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
