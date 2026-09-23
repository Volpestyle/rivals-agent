"""Range BC plumbing fit: the command sequence from the pre-registration, and the real fit's pre-registration from the
plumbing reports (VUH-1359, VUH-1346). Stdlib only; it never trains and never opens a validation or test recording.

    commands --commit SHA --out-dir DIR [--prereg range_bc_plumbing_prereg.json]
        Refuses (exit 2) until every cohort step table exists, loads under the fit's reader with the pinned denylist,
        is a train-split recording with the 15-action vocabulary, and the dev rule holds. Then writes to DIR:
          plan.json         the resolved cohort (step-table sha256, counted minutes, windows), the scaling curve's
                            --max-steps, each fraction's minutes, and the budget estimate
          transfer.ps1      Windows: hash and send the new recordings' originals, the four step tables, the code
                            archive and the two Mac scripts
          mac-prepare.zsh   Mac: verify hashes, unpack the code, sync its venv, check the tables, build the caches
          mac-queue.zsh     Mac: every pre-registered run in order, one log and exit file each, stop at a failure
          launch.ps1        Windows: prepare (foreground), then the queue as one niced durable job
          collect.ps1       Windows: copy the reports back and run derive
    derive --plan plan.json --runs DIR --hud-parity FILE --out preregistration.json
        Checks every report against the plan (scope, cohort and step-table sha256, arguments), checks p1/p2 byte
        repeatability, applies the pre-registered derivation and writes the real fit's --preregistration file, with
        the dev curves and the scaling table it was read from.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from policy.range_bc import steps, vocab  # noqa: E402

HERE = Path(__file__).resolve().parent
PREREG = HERE / "range_bc_plumbing_prereg.json"
MAC_ROOT = "/Users/james/dev/range-bc-data"
VIDEOS = r"C:\Users\volpe\Videos\RivalsInput"
# The smoke fit's measured throughput on the Mac (fit-smoke; frames per second with the real loader) and evaluation
# cost; the budget is an estimate from these, never a gate.
FPS = {"model": 802., "model_nohud": 1056., "history_only": 52000.}
EVAL_S_PER_ROW = 22. / 4800         # every arm tf + sf and the baselines, three arms
DEV_PASS_FACTOR = 1 / 3             # a forward-only dev window against a training window
ADMITTED = ("20260923T051828-422Z-33696-1", "20260923T171533-187Z-33696-5")    # before this pre-registration


class PlanError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise PlanError(message)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def load_prereg(path=PREREG):
    raw = Path(path).read_bytes()
    pre = json.loads(raw)
    require(pre.get("format") == "rivals-range-plumbing-prereg-v1", "not a plumbing pre-registration")
    require(pre["vocabulary"]["actions"] == list(vocab.NAMES), "the pre-registration's actions differ from the fit's")
    require(not pre["cohort"]["val"], "the plumbing fit reads no validation")
    return pre, sha256_bytes(raw.replace(b"\r\n", b"\n"))


def values(args, flag):
    """The values after `flag` in an argument list, up to the next flag."""
    i = args.index(flag) + 1
    j = next((k for k in range(i, len(args)) if args[k].startswith("--")), len(args))
    return args[i:j]


def step_path(pre, sid, root=ROOT):
    return Path(root) / pre["cohort"]["step_table_path"].format(id=sid)


def run_list(pre, max_steps):
    """[(name, args)] in queue order, with the scaling curve expanded."""
    out = []
    for r in pre["runs"]:
        if "fractions" not in r:
            out.append((r["name"], list(r["args"])))
            continue
        for f in r["fractions"]:
            args = [a.replace("{fraction}", repr(f)).replace("{max_steps}", str(max_steps)) for a in r["args"]]
            out.append((r["name"].replace("{fraction}", f"{f:.2f}"), args))
    return out


def resolve(pre, root=ROOT):
    """The admitted cohort, checked: every table exists and loads, is train-split, 15 actions, dev rule holds."""
    missing = [sid for role in ("train", "dev") for sid in pre["cohort"][role] if not step_path(pre, sid, root).exists()]
    require(not missing, f"waiting for admission: no step table yet for {missing}")
    denylist = steps.load_denylist()
    sessions = {}
    for role in ("train", "dev"):
        for sid in pre["cohort"][role]:
            s = steps.load(step_path(pre, sid, root), denylist=denylist)
            require(s.session_id == sid, f"{sid}: the step table names {s.session_id}")
            require(s.split == "train", f"{sid}: split {s.split}; the plumbing fit uses train-split recordings only")
            sessions[sid] = (role, s)
    new = [sid for sid in pre["cohort"]["train"] + pre["cohort"]["dev"] if sid not in ADMITTED]
    require(len(new) == 2, "the dev rule is written for exactly two new sessions")
    later = max(new)                          # a logger session id starts with its UTC start time
    require(later in pre["cohort"]["dev"] and ADMITTED[1] in pre["cohort"]["dev"],
            f"the dev rule puts 171533 and the later-recorded new session ({later}) in dev")
    return sessions


def plan(pre, pre_sha, commit, root=ROOT):
    sessions = resolve(pre, root)
    train = [s for role, s in sessions.values() if role == "train"]
    dev = [s for role, s in sessions.values() if role == "dev"]
    regimes = tuple(pre["fixed"]["regimes"])
    windows, _ = steps.windows(train, regimes=regimes, stride=48)
    dev_windows, _ = steps.windows(dev, regimes=regimes, stride=48)
    max_steps = 10 * math.ceil(len(windows) / pre["fixed"]["batch"])
    fractions = {}
    for r in pre["runs"]:
        for f in r.get("fractions", ()):
            cut = [steps.truncate(s, f, regimes=regimes) for s in train]
            fractions[repr(f)] = {"train_minutes": steps.train_minutes(cut, regimes=regimes)["total"],
                                  "windows": len(steps.windows(cut, regimes=regimes, stride=48)[0])}
    runs = run_list(pre, max_steps)
    budget = {}
    dev_rows = sum(len(s.rows) for s in dev)
    for name, args in runs:
        arms, seeds = values(args, "--arms"), values(args, "--seeds")
        if "--max-steps" in args:
            opt_steps, epochs = max_steps, max_steps / math.ceil(len(windows) / pre["fixed"]["batch"])
        else:
            epochs = int(args[args.index("--epochs") + 1])
            opt_steps = epochs * math.ceil(len(windows) / pre["fixed"]["batch"])
        secs = 0.
        for arm in arms:
            train_s = opt_steps * pre["fixed"]["batch"] * pre["fixed"]["window"] / FPS[arm]
            dev_s = math.ceil(epochs) * len(dev_windows) * pre["fixed"]["window"] / FPS[arm] * DEV_PASS_FACTOR
            secs += len(seeds) * (train_s + dev_s)
        secs += EVAL_S_PER_ROW * dev_rows * len(arms) * len(seeds) / 3
        budget[name] = round(secs / 60, 1)
    return {"format": "rivals-range-plumbing-plan-v1", "prereg_sha256": pre_sha, "commit": commit,
            "cohort": {sid: {"role": role, "steps_sha256": s.sha256, "media_sha256": s.header["media_sha256"],
                             "rows": len(s.rows), "counted_minutes":
                                 steps.train_minutes([s], regimes=regimes)["total"]}
                       for sid, (role, s) in sessions.items()},
            "train_windows_stride48": len(windows), "dev_windows_stride48": len(dev_windows),
            "max_steps": max_steps, "fractions": fractions,
            "runs": [{"name": n, "args": a} for n, a in runs],
            "budget_minutes": budget, "budget_total_hours": round(sum(budget.values()) / 60, 2),
            "budget_note": "estimate from the smoke's throughput (HUD 802, no-HUD 1,056, twin 52k frames/s), plus "
                           "cache builds (about 12 s per recorded minute) and transfer; not a gate"}


# ---- the scripts -----------------------------------------------------------------------------------------------------

def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


def scripts(p, pre, mac_root=MAC_ROOT):
    short = p["commit"][:7]
    code, st, ca, rn, pl = (f"{mac_root}/code-{short}", f"{mac_root}/steps15", f"{mac_root}/caches15",
                            f"{mac_root}/runs", f"{mac_root}/plumb-{short}")
    new = [sid for sid in p["cohort"] if sid not in ADMITTED]
    train = [f"{st}/{sid}.jsonl" for sid in pre["cohort"]["train"]]
    dev = [f"{st}/{sid}.jsonl" for sid in pre["cohort"]["dev"]]
    ps = [f"# Range BC plumbing transfer (generated by range_bc_plumbing.py from prereg {p['prereg_sha256'][:12]}).",
          "# Run from the repo root on Windows. It sends only the two new recordings (the sealed take is never named).",
          "$ErrorActionPreference = 'Stop'",
          f"$D = '{mac_root}'; $P = '{pl}'; $COMMIT = '{p['commit']}'",
          "git archive --format=tar -o \"$PSScriptRoot\\plumb-code.tar\" $COMMIT    # outputs stay in this folder",
          f"ssh -o BatchMode=yes mac \"mkdir -p $D/originals $D/steps15 $D/caches15 $D/runs $P\""]
    for sid in new:
        media = p["cohort"][sid]["media_sha256"]
        ps += [f"# {sid}: logger files, then the video named by its metadata.json (its sha256 must be the header's)",
               f"$L = '{VIDEOS}\\{sid}'",
               "$V = (Get-Content -Raw \"$L\\metadata.json\" | ConvertFrom-Json).video_path",
               f"if ((Get-FileHash -Algorithm SHA256 $V).Hash.ToLower() -ne '{media}') "
               "{ throw \"$V is not the step table's media (a transcode needs the runbook's --media-relocation)\" }",
               f"Get-FileHash -Algorithm SHA256 $V, \"$L\\metadata.json\", \"$L\\inputs.jsonl\", \"$L\\frames.csv\" |",
               "    ForEach-Object { \"$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)\" } |",
               f"    Set-Content -Encoding ascii \"$PSScriptRoot\\{sid}.sha256\"",
               f"ssh -o BatchMode=yes mac \"mkdir -p $D/originals/{sid}\"",
               f"scp -o BatchMode=yes \"$L\\metadata.json\" \"$L\\inputs.jsonl\" \"$L\\frames.csv\" \"$PSScriptRoot\\{sid}.sha256\" "
               f"mac:$D/originals/{sid}/",
               "scp -o BatchMode=yes \"$V\" mac:$D/originals/          # unquoted remote path (SFTP-mode scp)"]
    ps += ["# the four 15-action step tables (051828 and 171533 re-emitted by intake; the old caches do not match them)"]
    for sid in p["cohort"]:
        ps.append(f"scp -o BatchMode=yes '{pre['cohort']['step_table_path'].format(id=sid)}' mac:$D/steps15/{sid}.jsonl")
    ps += ["scp -o BatchMode=yes \"$PSScriptRoot\\plumb-code.tar\" mac:$P/",
           "scp -o BatchMode=yes \"$PSScriptRoot\\mac-prepare.zsh\" \"$PSScriptRoot\\mac-queue.zsh\" mac:$P/"]
    table_sums = "\n".join(f"{v['steps_sha256']}  {sid}.jsonl" for sid, v in p["cohort"].items())
    prep = ["#!/bin/zsh -l", f"# Range BC plumbing, Mac prepare (commit {p['commit']}). Outside every checkout.",
            "set -eu", f"D={mac_root}; P={pl}; C={code}; S={st}; K={ca}",
            "uvr() { uv run --offline --locked --group execution \"$@\"; }",
            "# 1. the new recordings' originals, against their Windows hashes"]
    for sid in new:
        prep += [f"cd $D/originals; while read -r want name; do f={sid}/$name; [[ -e $f ]] || f=$name;",
                 "  got=$(shasum -a 256 \"$f\" | cut -c1-64); [[ $got == $want ]] || { echo \"BAD $name\"; exit 2; }; "
                 "echo \"ok $name\";",
                 f"done < {sid}/{sid}.sha256"]
    prep += ["# 2. the step tables, against the plan", "cd $S", f"shasum -a 256 -c <<'SUMS'\n{table_sums}\nSUMS",
             "# 3. the code: the landed commit's archive, its own venv", "mkdir -p $C; tar -xf $P/plumb-code.tar -C $C",
             "cd $C; uv sync --locked --group execution",
             "# 4. every table loads under the fit's reader and the pinned denylist",
             "for t in $S/*.jsonl; do uvr python -c 'import sys; from policy.range_bc import steps; "
             "s=steps.load(sys.argv[1], denylist=steps.load_denylist()); print(s.session_id, s.split, len(s.rows))' "
             "$t; done",
             "# 5. caches, Homebrew ffmpeg 8.1.2_1 (about 12 s per recorded minute)"]
    for sid in p["cohort"]:
        prep.append(f"[[ -e $K/{sid}/cache.json ]] || nice -n 10 uv run --offline --locked --group execution "
                    f"python -m policy.range_bc.cache $S/{sid}.jsonl $K/{sid} --video-root $D/originals")
    prep.append("echo PREPARED")
    common = (f"--scope plumbing --device mps --cache-root {ca} --batch {pre['fixed']['batch']} "
              f"--lr {pre['fixed']['lr']} --regimes {' '.join(pre['fixed']['regimes'])} "
              f"--train {' '.join(train)} --dev {' '.join(dev)}")
    queue = ["#!/bin/zsh -l", f"# Range BC plumbing queue (commit {p['commit']}): launched niced as one durable job.",
             "set -u", f"R={rn}; cd {code}",
             "run() {",
             "  local name=$1; shift",
             f"  uv run --offline --locked --group execution python -m policy.range_bc.train {common} "
             "--out $R/$name \"$@\" >$R/$name.log 2>&1",
             "  local rc=$?; echo $rc >$R/$name.exit; return $rc",
             "}"]
    for name, args in p_runs(p):
        queue.append(f"run {name} {' '.join(args)} || {{ echo FAILED {name} >$R/plumb-queue.status; exit 1; }}")
    queue.append("echo DONE >$R/plumb-queue.status")
    launch = [f"# Range BC plumbing launch (commit {p['commit']}).",
              "$ErrorActionPreference = 'Stop'",
              f"ssh -o BatchMode=yes mac 'zsh -l {pl}/mac-prepare.zsh'",
              "if ($LASTEXITCODE) { throw 'prepare failed' }",
              f"ssh -o BatchMode=yes mac 'nohup nice -n 10 zsh -l {pl}/mac-queue.zsh >/dev/null 2>&1 & "
              f"echo $! > {pl}/queue.pid'",
              f"# Status: ssh mac 'cat {rn}/plumb-queue.status; tail -n 3 {rn}/plumb-*.log; cat {rn}/plumb-*.exit'",
              "# Report from the .exit files, the logs and the reports, never from the launch."]
    collect = [f"# Range BC plumbing collect (commit {p['commit']}): reports back, then derive.",
               "$ErrorActionPreference = 'Stop'", "$H = $PSScriptRoot",
               f"if ((ssh -o BatchMode=yes mac 'cat {rn}/plumb-queue.status') -ne 'DONE') {{ throw 'queue not done' }}"]
    for name, _ in p_runs(p):
        collect += [f"New-Item -ItemType Directory -Force \"$H\\runs\\{name}\" | Out-Null",
                    f"scp -o BatchMode=yes mac:{rn}/{name}/report.json \"$H\\runs\\{name}\\\""]
    collect += ["# the parity file: a P2' result if one exists, else run 1 (hud-parity-1.json)",
                "$PARITY = '<path to the parity JSON>'",
                "uv run --offline --locked --group execution python docs\\evidence\\fit-readiness-20260923\\"
                "range_bc_plumbing.py derive --plan \"$H\\plan.json\" --runs \"$H\\runs\" --hud-parity $PARITY "
                "--out \"$H\\preregistration.json\""]
    lf = lambda lines: "\n".join(lines) + "\n"
    return {"transfer.ps1": lf(ps), "mac-prepare.zsh": lf(prep), "mac-queue.zsh": lf(queue),
            "launch.ps1": lf(launch), "collect.ps1": lf(collect)}


def p_runs(p):
    return [(r["name"], r["args"]) for r in p["runs"]]


def commands(a):
    pre, pre_sha = load_prereg(a.prereg)
    try:
        p = plan(pre, pre_sha, a.commit)
    except (PlanError, steps.StepError) as e:
        print(f"NOT READY: {e}", file=sys.stderr)
        return 2
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(p, indent=1) + "\n", encoding="utf-8", newline="\n")
    for name, text in scripts(p, pre).items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"cohort": {k: [v["role"], round(v["counted_minutes"], 2)] for k, v in p["cohort"].items()},
                      "max_steps": p["max_steps"], "budget_total_hours": p["budget_total_hours"]}, indent=1))
    print(f"next: {out / 'transfer.ps1'}, then {out / 'launch.ps1'}; later {out / 'collect.ps1'}")
    return 0


# ---- derive ----------------------------------------------------------------------------------------------------------

def _curve(report, checkpoint):
    return [e["dev"]["total"] for e in report["epochs_log"][checkpoint]]


def _argmin(values):
    return min(range(len(values)), key=lambda i: (values[i], i))       # ties to the earliest (fewer epochs)


def check_report(report, name, args, p):
    require(report.get("scope") == "plumbing", f"{name}: scope {report.get('scope')}, not plumbing")
    require(not report.get("test_opened"), f"{name}: opened the test split")
    roles = {c["session_id"]: (c["role"], c["steps_sha256"]) for c in report["cohort"]}
    want = {sid: (v["role"], v["steps_sha256"]) for sid, v in p["cohort"].items()}
    require(roles == want, f"{name}: cohort or step-table sha256 differs from the plan")
    cfg = report["config"]
    opt = lambda flag, cast=str: cast(args[args.index(flag) + 1]) if flag in args else None
    expect = {"weight_decay": opt("--weight-decay", float), "stride": opt("--stride", int), "lag": opt("--lag", int),
              "train_fraction": opt("--train-fraction", float) or 1.,
              "arms": values(args, "--arms")}
    if "--max-steps" in args:
        expect["max_steps"] = opt("--max-steps", int)
    else:
        expect["epochs"], expect["max_steps"] = opt("--epochs", int), None
    for k, v in expect.items():
        require(cfg.get(k) == v, f"{name}: {k} {cfg.get(k)} differs from the pre-registered {v}")
    seeds = [int(s) for s in values(args, "--seeds")]
    require(report["seeds"] == seeds, f"{name}: seeds {report['seeds']} differ from {seeds}")


def derive(a):
    p = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    pre, pre_sha = load_prereg(a.prereg)
    require(p["prereg_sha256"] == pre_sha, "the plan was made from another pre-registration")
    reports, sources = {}, {}
    for name, args in p_runs(p):
        path = Path(a.runs) / name / "report.json"
        require(path.exists(), f"{name}: no report")
        raw = path.read_bytes()
        reports[name] = json.loads(raw)
        sources[name] = sha256_bytes(raw)
        check_report(reports[name], name, args, p)
    p1, p2 = reports["plumb-p1-curve"], reports["plumb-p2-repeat"]
    for ck in p2["checkpoints"]:
        require(p2["checkpoints"][ck] == p1["checkpoints"][ck],
                f"repeatability: {ck} differs between p1 and p2 (the reproduction rule needs byte repeatability)")
    arm = "model_nohud-seed0.pt"
    low, high = _curve(p1, arm), _curve(reports["plumb-p3-wd"], arm)
    wd, curve = (1e-3, high) if min(high) < min(low) else (1e-4, low)
    epochs = 1 + _argmin(curve)
    stride = 48 if epochs <= 10 else 64
    parity_raw = Path(a.hud_parity).read_bytes()
    parity = json.loads(parity_raw)
    require("rule" in parity and "pass" in parity, "--hud-parity is not a hudparity result")
    scaling = []
    for f, info in p["fractions"].items():
        rep = reports[f"plumb-p5-scale-{float(f):.2f}"]
        tf = rep["metrics"]["dev"]["teacher_forced"]
        mean = lambda xs: sum(xs) / len(xs)
        f1 = lambda arm_: mean([v["all"]["macro_press_f1_tol"] for v in tf[arm_].values()])
        scaling.append({"fraction": float(f), "train_minutes": rep["train_minutes"]["total"],
                        "dev_total": {k: v[-1]["dev"]["total"] for k, v in rep["epochs_log"].items()},
                        "train_loss": {k: v[-1]["train_loss"] for k, v in rep["epochs_log"].items()},
                        "gap_tf_macro_press_f1_tol": f1("model_nohud") - f1("history_only"),
                        "camera_mae_mean": mean([v["all"]["camera_mae_mean"] for v in tf["model_nohud"].values()])})
    gaps = [s["gap_tf_macro_press_f1_tol"] for s in scaling if s["fraction"] >= .5]
    out = {"epochs": epochs, "weight_decay": wd, "stride": stride, "lag": 0, "seeds": pre["derivation"]["seeds"],
           "hud_parity_sha256": sha256_bytes(parity_raw), "hud_parity_pass": parity["pass"],
           "source": {"plumbing_prereg_sha256": pre_sha, "plan_sha256": sha256_bytes(Path(a.plan).read_bytes()),
                      "reports": sources, "commit": p["commit"]},
           "derivation": {"arm": arm, "dev_total_wd_1e-4": low, "dev_total_wd_1e-3": high,
                          "dev_total_hud_arm_wd_1e-4": _curve(p1, "model-seed0.pt"),
                          "lag_dev_total_min": {n: min(_curve(reports[n], arm)) for n in ("plumb-p4-lag1",
                                                                                         "plumb-p4-lag2")},
                          "repeatability": "p1 and p2 checkpoints byte-identical"},
           "scaling": scaling,
           "scaling_reading_a": {"gap_positive_from_half": all(g > 0 for g in gaps),
                                 "gap_rising_from_half": all(x < y for x, y in zip(gaps, gaps[1:]))},
           "scaling_reading_bc": "read by the lead from the table (pre-registration scaling_reading b and c)"}
    Path(a.out).open("x", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("epochs", "weight_decay", "stride", "hud_parity_pass")}))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("commands")
    c.add_argument("--commit", required=True)
    c.add_argument("--out-dir", required=True)
    c.add_argument("--prereg", default=PREREG)
    d = sub.add_parser("derive")
    d.add_argument("--plan", required=True)
    d.add_argument("--runs", required=True)
    d.add_argument("--hud-parity", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--prereg", default=PREREG)
    a = p.parse_args(argv)
    return commands(a) if a.cmd == "commands" else derive(a)


if __name__ == "__main__":
    sys.exit(main())
