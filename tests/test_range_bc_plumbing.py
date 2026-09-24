"""The plumbing fit's pre-registration, its command sequence and the derivation of the real fit's pre-registration
(docs/evidence/fit-readiness-20260923/range_bc_plumbing.py), plus the scaling curve's nested prefixes. Stdlib only."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from policy.range_bc import fixture, steps, vocab

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "range_bc_plumbing", ROOT / "docs/evidence/fit-readiness-20260923/range_bc_plumbing.py")
plumbing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plumbing)

NEW_TRAIN, NEW_DEV = "20260923T200129-346Z-33696-6", "20260923T205528-900Z-45572-3"


def session(tmp_path, name="t", **kw):
    header, rows = fixture.session(name, **kw)
    return steps.load(fixture.write(tmp_path / f"{name}.jsonl", header, rows))


# ---- the scaling curve's prefixes ------------------------------------------------------------------------------------

def test_truncate_keeps_a_nested_time_prefix_and_never_touches_the_file(tmp_path):
    s = session(tmp_path, runs=(150, 120, 90))
    assert steps.truncate(s, 1.) is s
    counts, previous = [], None
    for f in (.25, .5, .75):
        t = steps.truncate(s, f)
        assert t.sha256 == s.sha256 and t.header == s.header and len(t.rows) == len(s.rows)
        eligible = [k for a, b in steps.runs(t) for k in range(a, b) if t.rows[k]["gap_free"]]
        counts.append(len(eligible))
        if previous is not None:
            assert set(previous) <= set(eligible)                          # nested
        assert max(eligible) < min(k for k in range(len(s.rows)) if t.rows[k]["suitability"] != s.rows[k][
            "suitability"])                                                 # a prefix: everything after is cut
        previous = eligible
    total = sum(1 for a, b in steps.runs(s) for k in range(a, b) if s.rows[k]["gap_free"])
    assert [round(c / total, 2) for c in counts] == [.25, .5, .75]
    assert steps.sha256(s.path) == s.sha256
    for bad in (0, -.1, 1.5):
        with pytest.raises(steps.StepError, match="fraction"):
            steps.truncate(s, bad)


# ---- the pre-registration --------------------------------------------------------------------------------------------

def test_the_pre_registration_names_the_cohort_the_runs_and_the_derivation():
    pre, sha = plumbing.load_prereg()
    assert len(sha) == 64 and pre["vocabulary"]["actions"] == list(vocab.NAMES) and vocab.N == 15
    assert pre["cohort"]["dev"] == [plumbing.ADMITTED[1], NEW_DEV] and pre["cohort"]["val"] == []
    assert pre["cohort"]["train"] == [plumbing.ADMITTED[0], NEW_TRAIN]
    assert NEW_DEV > NEW_TRAIN                                             # the later-recorded new session is dev
    runs = plumbing.run_list(pre, 777)
    assert [n for n, _ in runs] == ["plumb-p1-curve", "plumb-p2-repeat", "plumb-p3-wd", "plumb-p4-lag1",
                                    "plumb-p4-lag2", "plumb-p5-scale-0.25", "plumb-p5-scale-0.50",
                                    "plumb-p5-scale-0.75", "plumb-p5-scale-1.00"]
    args = dict(runs)
    assert plumbing.values(args["plumb-p1-curve"], "--arms") == ["model", "model_nohud", "history_only"]
    assert plumbing.values(args["plumb-p3-wd"], "--weight-decay") == ["0.001"]
    assert plumbing.values(args["plumb-p5-scale-0.50"], "--max-steps") == ["777"]
    assert plumbing.values(args["plumb-p5-scale-0.50"], "--train-fraction") == ["0.5"]
    assert plumbing.values(args["plumb-p5-scale-0.50"], "--seeds") == ["0", "1"]
    for _, a in runs:
        assert "--val" not in a and "--scope" not in a and "053616" not in " ".join(a)
    assert pre["derivation"]["seeds"] == [0, 1, 2]


# ---- commands --------------------------------------------------------------------------------------------------------

def write_cohort(root, pre, *, late_dev=True):
    for i, sid in enumerate(pre["cohort"]["train"] + pre["cohort"]["dev"]):
        path = plumbing.step_path(pre, sid, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        header, rows = fixture.session(sid, runs=(150, 120), seed=i)
        fixture.write(path, header, rows)


def test_commands_refuse_until_both_sessions_are_admitted(tmp_path, capsys):
    pre, sha = plumbing.load_prereg()
    with pytest.raises(plumbing.PlanError, match=f"waiting for admission.*{NEW_TRAIN}"):
        plumbing.plan(pre, sha, "abc1234", root=tmp_path)
    assert plumbing.main(["commands", "--commit", "abc1234", "--out-dir", str(tmp_path / "o"),
                          "--prereg", str(plumbing.PREREG)]) in (0, 2)     # 2 until intake admits them


def test_commands_write_the_plan_and_the_scripts(tmp_path):
    pre, sha = plumbing.load_prereg()
    write_cohort(tmp_path, pre)
    p = plumbing.plan(pre, sha, "0123456789abcdef", root=tmp_path)
    assert {k: v["role"] for k, v in p["cohort"].items()} == {plumbing.ADMITTED[0]: "train", NEW_TRAIN: "train",
                                                              plumbing.ADMITTED[1]: "dev", NEW_DEV: "dev"}
    per_epoch = -(-p["train_windows_stride48"] // 8)
    assert p["max_steps"] == 10 * per_epoch
    minutes = [p["fractions"][f]["train_minutes"] for f in ("0.25", "0.5", "0.75", "1.0")]
    assert minutes == sorted(minutes) and minutes[0] > 0
    assert set(p["budget_minutes"]) == {r["name"] for r in p["runs"]} and p["budget_total_hours"] > 0
    s = plumbing.scripts(p, pre)
    assert set(s) == {"transfer.ps1", "mac-prepare.zsh", "mac-queue.zsh", "launch.sh", "collect.sh"}
    assert all("053616" not in text and "\r" not in text for text in s.values())
    q = s["mac-queue.zsh"]
    assert q.count("\nrun plumb-") == 9 and "--scope plumbing" in q and "--val" not in q
    assert f"--max-steps {p['max_steps']}" in q and "/code-0123456\n" in q     # the commit's archive
    assert q.index("plumb-p1-curve") < q.index("plumb-p2-repeat") < q.index("plumb-p5-scale-1.00")
    prep = s["mac-prepare.zsh"]
    assert all(v["steps_sha256"] in prep for v in p["cohort"].values())
    assert prep.count("policy.range_bc.cache") == 4 and prep.count("/cache.json ]]") == 4
    assert "steps.load_denylist()" in prep
    assert prep.count("name=${name%$'\\r'}") == 2           # PowerShell writes the hash lists with CRLF
    t = s["transfer.ps1"]
    assert NEW_TRAIN in t and NEW_DEV in t and "mac:'" not in t and "\"mac:" not in t and "git archive" in t
    assert all(p["cohort"][sid]["media_sha256"] in t for sid in (NEW_TRAIN, NEW_DEV))
    # launch and collect are Git Bash scripts: ssh under PowerShell 5.1 hung twice after the remote command finished
    for name in ("launch.sh", "collect.sh"):
        text = s[name]
        assert text.startswith("#!/bin/bash\n") and "\nset -u\n" in text and "powershell" not in text.lower()
        assert "$LASTEXITCODE" not in text and "ErrorActionPreference" not in text
        ssh_lines = [line for line in text.splitlines() if "ssh " in line and not line.startswith("#")]
        assert ssh_lines and all("-o BatchMode=yes -o ServerAliveInterval=15" in line for line in ssh_lines)
    launch = s["launch.sh"]
    assert launch.index("pgrep -f mac-queue.zsh") < launch.index("mac-prepare.zsh")       # one queue only
    assert "plumb-queue.status 2>/dev/null" in launch
    assert "mac-prepare.zsh' || { echo 'prepare failed' >&2; exit 1; }" in launch      # no queue after a failed prepare
    assert launch.index("mac-prepare.zsh") < launch.index("nohup nice -n 10 zsh -l")
    collect = s["collect.sh"]
    assert "[ $# -eq 1 ]" in collect and "--hud-parity \"$PARITY\"" in collect         # the parity file is required
    assert '[ "$st" = DONE ]' in collect and "copied reports differ from the Mac" in collect
    assert all(r["name"] in collect for r in p["runs"]) and "|| { echo 'derive refused' >&2; exit 1; }" in collect
    assert "--group execution" not in collect                                          # derive is stdlib: no torch sync


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="bash -n where bash is POSIX bash")
def test_the_generated_bash_scripts_parse(tmp_path):
    pre, sha = plumbing.load_prereg()
    write_cohort(tmp_path, pre)
    for name, text in plumbing.scripts(plumbing.plan(pre, sha, "0123456789abcdef", root=tmp_path), pre).items():
        if name.endswith(".sh"):
            (tmp_path / name).write_text(text, encoding="utf-8", newline="\n")
            assert subprocess.run(["bash", "-n", str(tmp_path / name)]).returncode == 0, name


def test_commands_refuse_a_broken_dev_rule_and_a_validation_recording(tmp_path):
    pre, sha = plumbing.load_prereg()
    swapped = copy.deepcopy(pre)
    swapped["cohort"]["train"][1], swapped["cohort"]["dev"][1] = NEW_DEV, NEW_TRAIN
    write_cohort(tmp_path, swapped)
    with pytest.raises(plumbing.PlanError, match="dev rule"):
        plumbing.plan(swapped, sha, "abc", root=tmp_path)
    path = plumbing.step_path(pre, NEW_DEV, tmp_path)
    header, rows = fixture.session(NEW_DEV, split="val", runs=(150, 120))
    path.unlink()
    fixture.write(path, header, rows)
    with pytest.raises(plumbing.PlanError, match="train-split"):
        plumbing.plan(pre, sha, "abc", root=tmp_path)


# ---- derive ----------------------------------------------------------------------------------------------------------

def fake_reports(tmp_path, p, *, p1_nohud, p3_nohud, repeat_ok=True):
    """Plumbing reports as the fit writes them, with chosen dev curves."""
    cohort = [{"session_id": sid, "role": v["role"], "steps_sha256": v["steps_sha256"]} for sid, v in p["cohort"].items()]
    runs = tmp_path / "runs"
    for name, args in plumbing.p_runs(p):
        arms = plumbing.values(args, "--arms")
        seeds = [int(x) for x in plumbing.values(args, "--seeds")]
        fraction = float(plumbing.values(args, "--train-fraction")[0]) if "--train-fraction" in args else 1.
        curve = {"plumb-p1-curve": p1_nohud, "plumb-p3-wd": p3_nohud}.get(name, [1.] * 20)
        log = {f"{arm}-seed{s}.pt": [{"epoch": e, "train_loss": 1. / (e + 1), "dev": {"total": v}}
                                     for e, v in enumerate(curve)] for arm in arms for s in seeds}
        tf = {arm: {str(s): {"all": {"macro_press_f1_tol": (.1 + fraction / 10 if arm != "history_only" else .05),
                                     "camera_mae_mean": 1.}} for s in seeds} for arm in arms}
        cfg = {"arms": arms, "weight_decay": float(plumbing.values(args, "--weight-decay")[0]),
               "stride": int(plumbing.values(args, "--stride")[0]), "lag": int(plumbing.values(args, "--lag")[0]),
               "train_fraction": fraction}
        if "--max-steps" in args:
            cfg["max_steps"], cfg["epochs"] = int(plumbing.values(args, "--max-steps")[0]), 20
        else:
            cfg["max_steps"], cfg["epochs"] = None, int(plumbing.values(args, "--epochs")[0])
        ck = {k: ("x" if repeat_ok or name != "plumb-p2-repeat" else "y") * 64 for k in log}
        report = {"scope": "plumbing", "test_opened": False, "cohort": cohort, "config": cfg, "seeds": seeds,
                  "epochs_log": log, "checkpoints": ck, "metrics": {"dev": {"teacher_forced": tf}},
                  "train_minutes": {"total": 10 * fraction}}
        (runs / name).mkdir(parents=True)
        (runs / name / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return runs


def derive_setup(tmp_path, **kw):
    pre, sha = plumbing.load_prereg()
    write_cohort(tmp_path, pre)
    p = plumbing.plan(pre, sha, "0123456789abcdef", root=tmp_path)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(p), encoding="utf-8")
    parity = tmp_path / "parity.json"
    parity.write_text(json.dumps({"rule": "P2", "pass": False}), encoding="utf-8")
    runs = fake_reports(tmp_path, p, **kw)
    return ["derive", "--plan", str(plan), "--runs", str(runs), "--hud-parity", str(parity)], runs


def test_derive_applies_the_pre_registered_rules(tmp_path):
    low = [5 - .3 * e for e in range(8)] + [2.9 + .1 * e for e in range(12)]       # minimum at epoch index 7
    args, _ = derive_setup(tmp_path, p1_nohud=low, p3_nohud=[x + .01 for x in low])
    assert plumbing.main(args + ["--out", str(tmp_path / "pre.json")]) == 0
    out = json.loads((tmp_path / "pre.json").read_text())
    assert (out["epochs"], out["weight_decay"], out["stride"], out["lag"]) == (8, 1e-4, 48, 0)
    assert out["seeds"] == [0, 1, 2] and out["hud_parity_pass"] is False and len(out["hud_parity_sha256"]) == 64
    assert out["scaling_reading_a"] == {"gap_positive_from_half": True, "gap_rising_from_half": True}
    assert [s["fraction"] for s in out["scaling"]] == [.25, .5, .75, 1.]
    with pytest.raises(FileExistsError):                                       # written once
        plumbing.main(args + ["--out", str(tmp_path / "pre.json")])


def test_derive_takes_the_higher_weight_decay_only_when_strictly_lower_and_falls_back_to_stride_64(tmp_path):
    late = [5 - .1 * e for e in range(20)]                                          # still falling at epoch 20
    args, _ = derive_setup(tmp_path, p1_nohud=late, p3_nohud=[x - .5 for x in late])
    plumbing.main(args + ["--out", str(tmp_path / "pre.json")])
    out = json.loads((tmp_path / "pre.json").read_text())
    assert (out["epochs"], out["weight_decay"], out["stride"]) == (20, 1e-3, 64)


def test_derive_refuses_unrepeatable_or_off_plan_runs(tmp_path):
    curve = [1.] * 20
    args, _ = derive_setup(tmp_path / "a", p1_nohud=curve, p3_nohud=curve, repeat_ok=False)
    with pytest.raises(plumbing.PlanError, match="repeatability"):
        plumbing.main(args + ["--out", str(tmp_path / "a" / "pre.json")])
    args, runs = derive_setup(tmp_path / "b", p1_nohud=curve, p3_nohud=curve)
    report = json.loads((runs / "plumb-p4-lag1" / "report.json").read_text())
    report["config"]["lag"] = 0
    (runs / "plumb-p4-lag1" / "report.json").write_text(json.dumps(report))
    with pytest.raises(plumbing.PlanError, match="lag"):
        plumbing.main(args + ["--out", str(tmp_path / "b" / "pre.json")])
    args, runs = derive_setup(tmp_path / "c", p1_nohud=curve, p3_nohud=curve)
    report = json.loads((runs / "plumb-p3-wd" / "report.json").read_text())
    report["cohort"][0]["steps_sha256"] = "0" * 64
    (runs / "plumb-p3-wd" / "report.json").write_text(json.dumps(report))
    with pytest.raises(plumbing.PlanError, match="cohort"):
        plumbing.main(args + ["--out", str(tmp_path / "c" / "pre.json")])
