"""Read-only, stdlib training board. No model imports, data loaders or job controls.

Only shallow metadata paths are scanned; stores, recordings, checkpoints and sealed
payloads are never opened. Evidence URLs return the cached metadata projection.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import threading
import time
from urllib.parse import urlsplit


@dataclass
class Job:
    name: str
    stage: str = "unknown"
    progress: str = "unknown"
    eta: str = "unknown"
    verdict: str = "undecided"
    evidence: str = ""
    arm: str = "unknown"
    seed: str = "unknown"
    started: str = "unknown"
    pid: str = "unknown"
    detail: str = ""
    updated: float = 0


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read(path, limit=131072, tail=False):
    """Bound every read, reject symlinks (including symlinked parent directories)."""
    if (any("sealed" in part.lower() for part in path.parts)
            or path.is_symlink() or any(p.is_symlink() for p in path.parents)):
        return ""
    try:
        with path.open("rb") as f:
            size = os.fstat(f.fileno()).st_size
            if size > limit:
                if not tail:
                    return ""
                f.seek(size - limit)
            return f.read(limit).decode("utf-8", errors="replace")
    except OSError:
        return ""


def load(path):
    try:
        value = json.loads(read(path, 4 * 1024 * 1024))
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def command(args, timeout=2):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def processes():
    rows = {}
    for line in command(["/bin/ps", "-axo", "pid=,ppid=,lstart=,command="]).splitlines():
        bits = line.split(None, 7)
        if len(bits) == 8 and bits[0].isdigit():
            rows[int(bits[0])] = (int(bits[1]), " ".join(bits[2:7]), bits[7])
    return rows


def process_for(pidpath, token, procs):
    def matches(info):
        return re.search(re.escape(token) + r'''(?=$|[\s/'"])''', info[2]) is not None

    raw = read(pidpath, 128).strip()
    if raw.isdigit():
        pid = int(raw)
        if pid not in procs:
            return f"{pid}: not alive", None
        if matches(procs[pid]):
            return f"{pid}: alive, command matched", procs[pid]
        return f"{pid}: alive, identity unconfirmed", None
    # Match a full output directory or script path, not a generic job name.
    for pid, info in procs.items():
        if matches(info) and re.search(r"python|zsh|bash", info[2]):
            return f"{pid}: alive, command matched", info
    return "unknown (no matching PID)", None


def log_progress(text, epochs=None, max_steps=None):
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get("epoch"), int):
            rows.append(row)
    if not rows:
        return "unknown", "unknown", "unknown", "unknown"
    last = rows[-1]
    progress = f"epoch {last['epoch'] + 1}" + (f"/{epochs}" if epochs and not max_steps else "")
    if "steps" in last:
        progress += f"; step {last['steps']}"
        if max_steps:
            progress += f"/{max_steps}"
    # These logs record cumulative seconds, reset for each arm and seed.
    deltas = []
    for a, b in zip(rows, rows[1:]):
        if (a.get("seed") == b.get("seed") and b["epoch"] == a["epoch"] + 1
                and isinstance(a.get("seconds"), (int, float))
                and isinstance(b.get("seconds"), (int, float))):
            delta = b["seconds"] - a["seconds"]
            if delta > 0:
                deltas.append(delta)
            else:
                deltas = []
        else:
            deltas = []
    eta = "unknown"
    if not max_steps and epochs and epochs > last["epoch"] + 1 and len(deltas) >= 2:
        minutes = statistics.median(deltas[-3:]) * (epochs - last["epoch"] - 1) / 60
        eta = f"~{minutes:.0f} min for current arm/seed training only; job ETA unknown"
    return progress, str(last.get("seed", "unknown")), str(last.get("arm", "unknown")), eta


def report_verdict(report):
    """Expose existing gate decisions; incomplete gates do not mean FAIL."""
    gates = report.get("gates", {})
    notes = []
    for split, arms in gates.items() if isinstance(gates, dict) else []:
        for arm, gate in arms.items() if isinstance(arms, dict) else []:
            if isinstance(gate, dict):
                state = "undecided"
                if gate.get("complete") is True and isinstance(gate.get("pilot_worthy"), bool):
                    state = "PASS" if gate["pilot_worthy"] else "FAIL"
                notes.append(f"{split}/{arm}: {state} (pilot gate)")
    gate = report.get("gate1")
    if isinstance(gate, dict):
        for key in ("passed", "pass", "passes", "gate1_pass"):
            if isinstance(gate.get(key), bool):
                notes.append("Gate 1: " + ("PASS" if gate[key] else "FAIL"))
                break
    return "; ".join(notes) or "undecided (no explicit complete gate verdict)"


def waiting_items(text):
    """Keep wrapped lines and sub-bullets with the parent's hand-edited request."""
    items = []
    for line in text.splitlines():
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif items and line.startswith(" ") and line.strip():
            items[-1] += " " + line.strip().removeprefix("- ")
    return items


class Board:
    def __init__(self, repo, roots, result_root=None):
        self.repo, self.roots, self.result_root = repo, roots, result_root
        self.lock = threading.Lock()
        self.cached = None
        self.deadline = 0
        self.evidence = {}

    def add_evidence(self, path, metadata):
        key = hashlib.sha256(str(path).encode()).hexdigest()[:20]
        self.evidence[key] = {"path": str(path), "metadata": metadata}
        return "/evidence/" + key

    def scan(self):
        started = time.monotonic()
        self.evidence = {}
        procs = processes()
        jobs, results, warnings = [], [], []
        for family, root in self.roots:
            if not root.is_dir():
                warnings.append(f"Unavailable metadata root: {root}")
                continue
            # One level only. Never descend into data payloads or code snapshots.
            folders = [root, root / "runs"]
            folders += [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
                        and p.name not in {"runs", "originals", "inputs", "stores", "steps", "steps15",
                                           "caches", "caches15", "diag"}
                        and not p.name.startswith(("code-", "."))]
            recipes = {}
            for folder in folders:
                for status in sorted(folder.glob("*queue*.status")):
                    text = read(status).strip()
                    script = status.with_suffix(".zsh")
                    source = read(script)
                    epoch_match = re.search(r"--epochs\s+(\d+)", source)
                    arm_match = re.search(r"--arms\s+([\w ]+?)(?=\s+--|\s*\\|$)", source)
                    for name in re.findall(r"^\s*(?:train|run)\s+([\w-]+)(?=\s|$)", source, re.M):
                        recipes[name] = (int(epoch_match[1]) if epoch_match else None,
                                         arm_match[1].split() if arm_match else [])
                    pid, proc = process_for(status.with_suffix(".pid"), str(script), procs)
                    word = text.split()[0].upper() if text else ""
                    stage = {"DONE": "done", "FAILED": "failed", "QUEUED": "queued"}.get(word, "unknown")
                    if word == "RUNNING" and proc:
                        stage = "running"
                    job = Job(f"{family} / {status.relative_to(root).as_posix()}", stage=stage, pid=pid,
                              detail=text, started=proc[1] + " (Mac local)" if proc else "unknown",
                              updated=status.stat().st_mtime)
                    if word == "RUNNING" and not proc:
                        job.detail += "; running marker unconfirmed by a matching process"
                    job.evidence = self.add_evidence(status, {"status": text, "pid": pid})
                    jobs.append(job)
                    results.append({"name": family + " / " + folder.name, "verdict": "undecided",
                                    "detail": "No experiment judge output found; queue completion is not a verdict.",
                                    "evidence": job.evidence, "updated": 0, "kind": "experiment"})
            runs = root / "runs"
            stems = {p.stem for suffix in ("*.log", "*.exit", "*.pid") for p in runs.glob(suffix)}
            for name in sorted(stems):
                log, exitfile = runs / (name + ".log"), runs / (name + ".exit")
                reportpath = runs / name / "report.json"
                report = load(reportpath)
                pid, proc = process_for(runs / (name + ".pid"), str(runs / name), procs)
                if not proc:
                    script_pid, script_proc = process_for(runs / (name + ".pid"),
                                                          str(root / "jobs" / (name + ".zsh")), procs)
                    if script_proc:
                        pid, proc = script_pid, script_proc
                rc = read(exitfile, 128).strip()
                stage = "done" if rc == "0" else "failed" if re.fullmatch(r"-?\d+", rc) else "running" if proc else "unknown"
                config = report.get("config", {})
                recipe_epochs, recipe_arms = recipes.get(name, (None, []))
                epochs = config.get("epochs", recipe_epochs) if isinstance(config, dict) else recipe_epochs
                if epochs is None and family == "IDM":
                    source = read(root / "jobs" / (name + ".zsh"))
                    totals = set(re.findall(r"--epochs\s+(\d+)", source))
                    if len(totals) == 1:
                        epochs = int(next(iter(totals)))
                max_steps = config.get("max_steps") if isinstance(config, dict) else None
                progress, seed, arm, eta = log_progress(read(log, tail=True), epochs, max_steps)
                arms = config.get("arms", recipe_arms) if isinstance(config, dict) else recipe_arms
                if arm == "unknown" and len(arms) == 1:
                    arm = arms[0]
                elif arm == "unknown" and arms:
                    arm = ", ".join(arms) + " (run arms; current unknown)"
                begin = read(runs / (name + ".start"), 256).strip() or "unknown"
                if proc:
                    begin = proc[1] + " (Mac local)"
                elif begin == "unknown" and log.exists():
                    birth = getattr(log.stat(), "st_birthtime", None)
                    if birth:
                        begin = stamp(birth) + " (log created)"
                verdict = report_verdict(report)
                job = Job(f"{family} / {name}", stage, progress,
                          eta if stage == "running" else "unknown" if stage == "unknown" else "—",
                          verdict, arm=arm, seed=seed, started=begin, pid=pid,
                          detail=f"exit {rc}" if rc else "no exit marker",
                          updated=max((p.stat().st_mtime for p in (log, exitfile, runs / (name + ".pid"))
                                       if p.exists()), default=0))
                projection = {"progress": progress, "arm": arm, "seed": seed, "exit": rc or None,
                              "gates": report.get("gates"), "gate1": report.get("gate1")}
                job.evidence = self.add_evidence(reportpath if report else log, projection)
                jobs.append(job)
                # Some IDM invocations emit several reports under one job log.
            for reportpath in sorted(runs.glob("*/report.json")):
                report = load(reportpath)
                results.append({"name": f"{family} / {reportpath.parent.name}",
                                "verdict": report_verdict(report), "detail": "Stored report gates; not an experiment judge.",
                                "evidence": self.add_evidence(reportpath, {"gates": report.get("gates"),
                                                                           "gate1": report.get("gate1")}),
                                "updated": reportpath.stat().st_mtime, "kind": "report"})
            for folder in folders:
                for pattern in ("reading*.json", "*verdict*.json", "judge*.json"):
                    for p in folder.glob(pattern):
                        results.append(self.reading(p, family + " / " + folder.name))
        if self.result_root and self.result_root.is_dir():
            for p in self.result_root.glob("*/*.json"):
                results.append(self.reading(p, "range_bc / " + p.parent.name))
        # Keep the latest judge output for each experiment; reports remain separately named.
        latest = {}
        for result in results:
            if result["name"] not in latest or result["updated"] > latest[result["name"]]["updated"]:
                latest[result["name"]] = result
        waiting = waiting_items(read(self.repo / "docs/waiting-on-james.md"))
        jobs.sort(key=lambda j: (j.stage != "running", -j.updated, j.name))
        machine_health = health()
        snapshot = {"updated": stamp(time.time()), "jobs": [asdict(j) for j in jobs],
                    "results": sorted(latest.values(), key=lambda r: -r["updated"]),
                    "waiting": waiting, **machine_health, "warnings": warnings,
                    "scan_seconds": round(time.monotonic() - started, 3)}
        return snapshot

    def reading(self, path, name):
        data = load(path)
        verdict, detail = "undecided", "No explicit experiment verdict recorded."
        if data.get("check_failures"):
            detail = "Judge input checks failed; experiment verdict unavailable."
        elif isinstance(data.get("outcome"), str):
            detail = data["outcome"]
            if detail.lower() == "neither works":
                verdict = "FAIL"
            elif detail.upper() in ("PASS", "FAIL"):
                verdict = detail.upper()
        elif isinstance(data.get("verdict"), str):
            detail = data["verdict"]
            if detail.upper() in ("PASS", "FAIL"):
                verdict = detail.upper()
        elif isinstance(data.get("reading"), dict):
            reading = data["reading"]
            flags = [k for k in ("opens_f1", "closes", "reverses", "not_resolved") if reading.get(k) is True]
            detail = "Recorded scaling reading: " + ", ".join(flags) + "; not a binary pass bar."
        projection = {k: data[k] for k in ("outcome", "verdict", "reading", "check_failures", "arms") if k in data}
        return {"name": name, "verdict": verdict, "detail": detail,
                "evidence": self.add_evidence(path, projection), "updated": path.stat().st_mtime, "kind": "experiment"}

    def snapshot(self):
        with self.lock:
            if self.cached is None or time.monotonic() >= self.deadline:
                try:
                    self.cached = self.scan()
                except Exception as error:
                    if self.cached is None:
                        self.cached = {"updated": "unavailable", "jobs": [], "results": [],
                                       "waiting": [], "health": "unknown", "warnings": []}
                    self.cached["warnings"] = [f"Scan failed; showing last snapshot: {type(error).__name__}"]
                self.deadline = time.monotonic() + 30
            return self.cached


def swap_summary(raw):
    values = {}
    for key, value, unit in re.findall(r"\b(total|used)\s*=\s*(\d+(?:\.\d+)?)\s*([KMGT])B?\b", raw):
        values[key] = float(value) * {"K": 0.000001, "M": 0.001, "G": 1, "T": 1000}[unit]
    if not {"used", "total"} <= values.keys():
        return "swap unknown", False
    used, total = values["used"], values["total"]
    return f"swap used {used:.1f} of {total:.1f} GB", total > 0 and used / total > 0.8


def health():
    loadavg = ", ".join(f"{n:.2f}" for n in os.getloadavg()) if hasattr(os, "getloadavg") else "unknown"
    pressure = command(["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"]).strip()
    pressure = {"1": "normal", "2": "warning", "4": "critical"}.get(pressure, "unknown")
    swap, amber = swap_summary(command(["/usr/sbin/sysctl", "-n", "vm.swapusage"]))
    gpu = command(["/usr/sbin/ioreg", "-r", "-c", "AGXAccelerator", "-l"], timeout=2)
    match = re.search(r'"Device Utilization %"\s*=\s*(\d+)', gpu)
    usage = match[1] + "%" if match else "unknown (no cheap utilization counter)"
    summary = f"Mac GPU {usage} · memory pressure {pressure} · load 1/5/15 min {loadavg}"
    return {"health": summary + " · " + swap, "health_summary": summary,
            "swap_text": swap, "swap_amber": amber}


# Editorial descriptions explain the registered question, never manufacture a verdict.
# Sources: range-bc-{countermeasures,countermeasures-2,interim,plumbing} evidence;
# idm-plumbing-20260924 and idm-beta-nll-20260925 pre-registrations.
EXPERIMENTS = {
    'countermeasures2': ('02', 'Can it learn to break out of idle?',
        'Train directly on the situations where the policy gets stuck: standing still, or following its own recent actions.',
        [('D', 'Recover from idle', 'Replace stretches of action history with known idle inputs.'),
         ('E', 'Learn from its own decisions', 'Feed back a sequence of the model’s own actions during training.')]),
    'countermeasures': ('01', 'Can it stop copying its last action?',
        'Test two ways to make decisions from the screen instead of simply repeating the previous input.',
        [('B', 'Use only the frames', 'Remove the previous-action history from the model.'),
         ('C', 'Practice with predicted actions', 'Mix the model’s one-step predictions into its training history.')]),
    'interim94': ('00', 'Does more human play help?',
        'Compare the same training recipe on 80.5 minutes and 33.6 minutes of play, with three random seeds each.',
        [('A', 'Learn from the screen', 'Compare the visual policy with a model that sees only action history.')]),
    'runs': ('BASE', 'Find a repeatable training recipe',
        'Check repeatability, training duration, regularization, timing, and the amount of demonstration data.', []),
}


def describe_job(name):
    family, separator, raw = name.partition(' / ')
    if not separator:
        raw, family = family, 'Job'
    if raw.endswith('.status'):
        key = raw.split('/')[0]
        title, purpose = EXPERIMENTS.get(key, ('', 'Training queue', 'Coordinate the experiment’s ordered jobs.', []))[1:3]
        return title + ' · queue', purpose, 'Queue'
    if family == 'range_bc':
        if raw.startswith('cm2-d'):
            return 'Learn to recover from standing still', 'Train with stretches of known-idle history so the model must use the frames to decide when to act.', 'Round 2 · Arm D'
        if raw.startswith('cm2-e'):
            return 'Practice with its own decisions', 'Feed back a sequence of the model’s own actions during training, including the states where it gets stuck.', 'Round 2 · Arm E'
        if raw == 'cm-s012':
            return 'Test two ways out of copycat behavior', 'Compare a frames-only model with one trained partly on its own one-step action predictions.', 'Round 1 · Arms B + C'
        if 'repro-control' in raw:
            return 'Check that the baseline still reproduces', 'Repeat the smaller-data control with the updated code to check that its behavior stays consistent.', 'Reproducibility'
        if raw.startswith('interim94-control'):
            return 'Train the smaller-data control', 'Fit the comparison models on 33.6 minutes of human play using the same recipe as the larger run.', 'Data scaling · control'
        if raw.startswith('interim94'):
            return 'Learn from more human play', 'Fit the visual policy and action-history baseline on 80.5 minutes, then compare with the smaller-data control.', 'Data scaling'
        plumbing = {
            'plumb-p1': ('Find a useful training duration', 'Measure the learning curve before choosing how long the real fit should run.'),
            'plumb-p2': ('Check training repeatability', 'Repeat the fit to see whether the same inputs and seed produce the same result.'),
            'plumb-p3': ('Check regularization', 'Test the weight-decay setting in the training recipe.'),
            'plumb-p4': ('Check action timing', 'Test how the alignment between observations and action targets affects the fit.'),
            'plumb-p5': ('Measure the effect of more data', 'Compare demonstration-data fractions using a fixed optimizer-step budget.'),
        }
        for prefix, (title, purpose) in plumbing.items():
            if raw.startswith(prefix):
                return title, purpose, 'Training recipe'
    else:
        descriptions = {
            'resume-confirm': ('Continue the pitch-confidence check', 'Finish checking the frozen pitch-uncertainty correction on fresh held-out sessions.'),
            'confirm': ('Check pitch confidence on new sessions', 'Apply the frozen uncertainty correction to previously unused sessions; do not refit it.'),
            'a1': ('Does the camera fix generalize?', 'Compare the original and revised camera losses on a second held-out session and three seeds.'),
            'a4': ('Recheck the camera-learning gate', 'Evaluate the revised camera loss at the registered Gate 1 scope.'),
            'e2': ('Repeat the delayed-HUD experiment', 'Check whether later HUD evidence improves action-onset predictions across more folds and seeds.'),
            'b': ('Can later HUD changes reveal a press?', 'Give the action reader later HUD crops, where an ability’s visible response may appear.'),
            'yaw2': ('Repeat the yaw-loss treatment', 'Repeat the revised camera-loss test with two additional random seeds.'),
            'yaw': ('Check whether turn direction is learned', 'Compare the original camera loss with a revised loss on left/right turn predictions.'),
            'yo': ('Apply the camera fix to yaw only', 'Test the revised loss on horizontal turning while keeping the original pitch loss.'),
            'loso': ('Check transfer to an unseen session', 'Leave one recording session out of training, then evaluate the model on that session.'),
            'press': ('Inspect action-press predictions', 'Run action-onset diagnostics on the stored models.'),
            'stores': ('Prepare the frame stores', 'Build the offline frame inputs used by the inverse-dynamics experiments.'),
            'chain': ('Coordinate the IDM job sequence', 'Run the registered inverse-dynamics jobs in their scheduled order.'),
        }
        for prefix, (title, purpose) in descriptions.items():
            if raw == prefix or raw.startswith(prefix + '-') or (prefix in ('stores', 'chain') and raw.startswith(prefix)):
                return title, purpose, 'Input learning · IDM'
    if raw.startswith('smoke'):
        return 'Check that the pipeline runs', 'Run a small plumbing check. Successful completion does not establish model quality.', family
    return raw.replace('-', ' ').replace('_', ' ').capitalize(), 'No plain-language description has been recorded for this run yet. Its source metadata is available below.', family


def progress_markup(job):
    # The logs measure one arm/seed, not the entire multi-seed job.
    text = job['progress']
    match = re.search(r'(epoch|step) (\d+)/(\d+)', text)
    if not match:
        return '<div class="progress-unknown"></div><small>Progress not yet reported</small>'
    unit, done, total = match[1], int(match[2]), int(match[3])
    if total <= 0 or done > total:
        return '<small>' + escape(text) + '</small>'
    caption = 'Current arm / seed' + (' · budget reached; process still running' if done == total else '')
    return (f'<div class="progress-label"><b>{unit.capitalize()} {done} of {total}</b><span>{escape(caption)}</span></div>'
            f'<progress max="{total}" value="{done}" aria-label="{unit.capitalize()} progress for current arm and seed">{done}/{total}</progress>')


CSS = """
:root{color-scheme:dark;--bg:#101315;--panel:#181d20;--raised:#1e2528;--line:#30383c;--text:#f1ede5;--muted:#a7afb0;--orange:#ff9b62;--mint:#9bd8be;--coral:#ed8b83;--amber:#f2c178;--radius:12px;font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}
*{box-sizing:border-box}body{margin:0}a{color:var(--mint);text-underline-offset:3px}a:hover{color:var(--text)}a:focus-visible,summary:focus-visible{outline:2px solid var(--orange);outline-offset:5px}h1,h2,h3,p{margin:0}h1{font-size:32px;line-height:1.18;letter-spacing:-1px}h2{font-size:21px;letter-spacing:-.5px}h3{font-size:17px;line-height:1.4;letter-spacing:-.2px}small,.muted{color:var(--muted)}small{font-size:12px}code,.mono,.eyebrow,.badge{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}code{overflow-wrap:anywhere;font-size:12px}.eyebrow{font-size:10px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted)}.shell{max-width:1460px;margin:auto;padding:0 32px 40px}.masthead{min-height:86px;display:flex;justify-content:space-between;align-items:center;gap:20px;border-bottom:1px solid var(--line)}.brand{font-size:19px;letter-spacing:4px;font-weight:800}.brand span{font:11px ui-monospace,monospace;color:var(--muted);letter-spacing:2px;margin-left:16px}.live-label{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px}.dot{height:7px;width:7px;background:var(--mint);border-radius:50%;display:inline-block}.overview{display:grid;grid-template-columns:1.6fr 1fr;gap:32px;padding:32px 0}.overview p{margin-top:12px;max-width:620px;color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(3,1fr);align-items:center}.stat{padding:0 20px;border-left:1px solid var(--line)}.stat b{font-size:34px;line-height:1.1;display:block;font-weight:600;letter-spacing:-1px;margin-bottom:9px}.stat span{display:block;font-size:11px;color:var(--muted)}.layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:24px;align-items:start}.main,.sidebar{min-width:0}.panel{border:1px solid var(--line);border-radius:var(--radius);background:var(--panel);margin-bottom:20px;overflow:hidden}.panel-header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:16px}.panel-header small{font-size:11px}.panel-body{padding:24px}.section-heading{display:flex;align-items:baseline;justify-content:space-between;margin:28px 0 15px;gap:12px}.section-heading:first-child{margin-top:0}.idle{display:flex;gap:18px;align-items:center;padding:26px 24px}.idle-mark{width:42px;height:42px;display:grid;place-items:center;background:#23312d;border-radius:50%;color:var(--mint);font-size:18px;flex-shrink:0}.idle p{color:var(--muted);font-size:13px;margin-top:5px}.job{border-top:1px solid var(--line);padding:22px 24px}.job:first-child{border-top:0}.job.running{border-left:3px solid var(--orange);padding-left:21px}.job-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}.job-head>div{min-width:0}.job .eyebrow{margin-bottom:7px}.purpose{color:var(--muted);font-size:13px;margin-top:7px;max-width:680px}.badge{font-size:10px;line-height:1.4;letter-spacing:.6px;text-transform:uppercase;border:1px solid currentColor;border-radius:5px;padding:5px 8px;white-space:nowrap;display:inline-block;flex-shrink:0}.running .badge,.orange{color:var(--orange)}.badge.done,.badge.pass,.mint{color:var(--mint)}.badge.failed,.badge.fail{color:var(--coral)}.badge.unknown,.amber,.badge.undecided{color:var(--amber)}.job-facts{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:15px;font-size:12px;color:var(--muted)}.job-facts strong{color:var(--text);font-weight:500}.progress-label{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:20px 0 9px;font-size:12px}.progress-label span{font-size:11px;color:var(--muted)}progress,meter{display:block;width:100%;height:7px;border:0;border-radius:6px;overflow:hidden;background:#30383c;appearance:none}progress::-webkit-progress-bar{background:#30383c;border-radius:6px}progress::-webkit-progress-value{background:var(--orange);border-radius:6px}progress::-moz-progress-bar{background:var(--orange)}.progress-unknown{height:5px;background:repeating-linear-gradient(110deg,#38403f 0 8px,#252d2d 8px 16px);margin:18px 0 8px;border-radius:4px}.eta{margin-top:9px;font-size:12px;color:var(--muted)}.eta b{color:var(--text);font-weight:500}.technical{margin-top:14px;color:var(--muted);font-size:12px}.technical summary{cursor:pointer;width:fit-content}.technical[open] summary{margin-bottom:12px}.technical dl{display:grid;grid-template-columns:90px minmax(0,1fr);gap:7px;margin:12px 0}dd{margin:0;overflow-wrap:anywhere}dt{color:var(--muted)}.technical p{margin:8px 0}.technical a{display:inline-block;margin-top:8px}.experiment{padding:24px;margin-bottom:16px;border:1px solid var(--line);border-radius:var(--radius);background:var(--panel)}.experiment-head{display:flex;gap:15px;align-items:flex-start}.experiment-num{font:12px ui-monospace,monospace;color:var(--orange);border-right:1px solid var(--line);padding-right:15px;min-width:45px;line-height:26px}.experiment-heading{flex:1;min-width:0}.experiment .purpose{margin-top:12px}.outcome{display:flex;align-items:flex-start;gap:12px;margin:18px 0;padding:14px 16px;background:#212729;border-radius:6px;font-size:13px}.outcome .badge{margin-top:1px}.outcome p{color:var(--text)}.arms{border-top:1px solid var(--line)}.arm{display:grid;grid-template-columns:30px minmax(0,1fr);gap:12px;padding-top:13px;font-size:13px}.arm-id{font:11px ui-monospace,monospace;background:var(--raised);border:1px solid var(--line);border-radius:4px;display:grid;place-items:center;width:28px;height:28px;color:var(--orange)}.arm p{color:var(--muted);font-size:12px;margin-top:3px}.experiment footer{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:20px;font-size:11px;color:var(--muted)}.experiment footer a{font-size:12px}.machine-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.machine-heading h2{font-size:18px}.machine-metric{margin:18px 0}.metric-label{display:flex;justify-content:space-between;gap:10px;font-size:12px;margin-bottom:9px}.metric-label strong{font-weight:500}.capacity{height:6px;background:var(--line);border-radius:4px;overflow:hidden}.capacity span{display:block;background:var(--mint);height:100%;border-radius:4px}.capacity.amber span{background:var(--amber)}.machine-details{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);display:grid;grid-template-columns:1fr auto;gap:8px;font-size:12px}.machine-details dt,.machine-details dd{color:var(--muted)}.machine-warning{font-size:11px;color:var(--amber);margin-top:8px}.waiting{list-style:none;padding:0;margin:0;counter-reset:waiting}.waiting li{counter-increment:waiting;position:relative;padding:17px 0 17px 32px;border-top:1px solid var(--line);font-size:12px;line-height:1.75;color:var(--muted)}.waiting li:first-child{border-top:0;padding-top:0}.waiting li::before{content:counter(waiting,decimal-leading-zero);position:absolute;left:0;color:var(--orange);font:11px ui-monospace,monospace;top:21px}.waiting li:first-child::before{top:4px}.waiting strong{color:var(--text);font-weight:500}.glossary{font-size:12px;color:var(--muted)}.glossary p+p{margin-top:12px}.glossary strong{color:var(--text);font-weight:500}.fold>summary{cursor:pointer;padding:18px 24px;font-size:13px}.fold>summary .muted{font-size:11px;margin-left:10px}.fold[open]>summary{border-bottom:1px solid var(--line)}.warning-banner,.preview-banner{padding:12px 18px;border:1px solid var(--amber);color:var(--amber);border-radius:8px;margin-bottom:18px;font-size:13px}.page-footer{border-top:1px solid var(--line);padding-top:20px;margin-top:12px;display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:11px}.empty-note{font-size:13px;color:var(--muted);padding:24px}.report-row{padding:16px 24px;border-top:1px solid var(--line)}.report-row h3{font-size:14px}.report-row p{font-size:12px;color:var(--muted);margin:6px 0}
@media(min-width:1500px){.shell{padding:0 48px 40px}}@media(max-width:1000px){.layout{grid-template-columns:minmax(0,1fr) 280px;gap:16px}.shell{padding:0 22px 28px}.overview{grid-template-columns:1fr}.stats{max-width:540px}.stat:first-child{border-left:0;padding-left:0}.panel-body,.experiment,.job{padding:20px}.job.running{padding-left:17px}}@media(max-width:760px){.layout{display:flex;flex-direction:column}.main,.sidebar{width:100%}.sidebar{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.sidebar .panel{margin:0}.sidebar .glossary-panel{grid-column:1/-1}.masthead{min-height:72px}.brand{font-size:16px}.brand span{font-size:9px;margin-left:8px}.live-label .refresh-label{display:none}.overview{padding:26px 0;gap:24px}h1{font-size:29px}.job-head{gap:8px}.badge{font-size:9px}.experiment footer{align-items:flex-start}.progress-label{flex-wrap:wrap;gap:3px}.page-footer{margin-top:24px}}@media(max-width:480px){.shell{padding:0 16px 24px}.sidebar{grid-template-columns:1fr}.sidebar .glossary-panel{grid-column:auto}.overview p{font-size:13px}.stat{padding:0 14px}.stat b{font-size:28px}.panel-header{padding:17px 18px}.panel-body,.experiment,.job{padding:18px}.job.running{padding-left:15px}.experiment-head{gap:10px}.experiment-num{padding-right:10px;min-width:36px}.experiment h3{font-size:17px}.outcome{flex-direction:column;gap:9px}.job-head{flex-wrap:wrap}.job-head>div{flex-basis:100%}.job-head>.badge{margin-top:4px}.job-facts{gap:6px 14px}.fold>summary{padding:16px 18px}.fold>summary .muted{display:block;margin-left:0;margin-top:3px}.page-footer{flex-direction:column;gap:5px}.live-label{font-size:10px}.technical dl{grid-template-columns:70px minmax(0,1fr)}}
"""


def render(snapshot, evidence):
    now = time.time()
    cutoff = now - 48 * 3600
    jobs = snapshot['jobs']
    history = [j for j in jobs if j['stage'] in ('done', 'failed', 'unknown') and 0 < j['updated'] < cutoff]
    current = [j for j in jobs if j not in history]
    active = [j for j in current if j['stage'] in ('running', 'queued')]
    finished = [j for j in current if j['stage'] in ('done', 'failed')]
    unconfirmed = [j for j in current if j['stage'] == 'unknown']
    queues = [j for j in active if j['name'].endswith('.status')]
    active_runs = [j for j in active if j not in queues]
    recent_runs = [j for j in finished if not j['name'].endswith('.status')]
    running_count = sum(j['stage'] == 'running' for j in active_runs)
    queued_count = sum(j['stage'] == 'queued' for j in active_runs)

    def age(timestamp):
        if not timestamp:
            return 'Update time unknown'
        seconds = max(0, now - timestamp)
        if seconds < 60:
            return 'Updated just now'
        if seconds < 3600:
            return f'Updated {int(seconds / 60)} min ago'
        if seconds < 86400:
            return f'Updated {int(seconds / 3600)} h ago'
        return f'Updated {int(seconds / 86400)} d ago'

    def link(url, full=False):
        path = evidence.get(url.rsplit('/', 1)[-1], {}).get('path', 'Source metadata')
        label = '<code>' + escape(path) + '</code>' if full else 'View evidence ↗'
        return f'<a href="{escape(url)}">{label}</a>'

    def job_card(job):
        title, purpose, category = describe_job(job['name'])
        stage = job['stage']
        label = {'running': 'In progress', 'queued': 'Queued', 'done': 'Finished', 'failed': 'Run failed', 'unknown': 'Unconfirmed'}.get(stage, stage)
        details = ''.join(f'<dt>{name}</dt><dd>{escape(str(job[key]))}</dd>' for name, key in
                          [('Run ID', 'name'), ('Started', 'started'), ('Arm', 'arm'), ('Seed', 'seed'), ('PID', 'pid'), ('Report gate', 'verdict')])
        facts = f'<span>{escape(age(job["updated"]))}</span>'
        if job['seed'] != 'unknown':
            facts += f'<span>Random seed <strong>{escape(job["seed"])}</strong></span>'
        if stage not in ('running', 'queued') and job['progress'] != 'unknown':
            facts += f'<span>{escape(job["progress"])}</span>'
        live = ''
        if stage == 'running':
            live = progress_markup(job)
            eta = job['eta'] if job['eta'] not in ('unknown', '—') else 'Not enough timing evidence yet'
            live += '<p class="eta"><b>ETA</b> · ' + escape(eta) + '</p>'
        elif stage == 'queued':
            live = '<p class="eta">Waiting to start · no training progress reported yet</p>'
        return (f'<article class="job {escape(stage)}"><div class="job-head"><div><div class="eyebrow">{escape(category)}</div>'
                f'<h3>{escape(title)}</h3></div><span class="badge {escape(stage)}">{escape(label)}</span></div>'
                f'<p class="purpose">{escape(purpose)}</p>{live}<div class="job-facts">{facts}</div>'
                f'<details class="technical"><summary>Run details &amp; evidence</summary><dl>{details}</dl>'
                f'<p>{escape(job["detail"])}</p>{link(job["evidence"], True)}</details></article>')

    def experiment_card(result):
        key = result['name'].split(' / ')[-1]
        serial, title, question, arms = EXPERIMENTS.get(key, ('EXP', result['name'], 'Read the recorded experiment decision and its source evidence.', []))
        verdict, explanation = result['verdict'], result['detail']
        label = {'FAIL': 'Did not meet the bar', 'PASS': 'Met the bar'}.get(verdict, 'Awaiting a verdict')
        if verdict == 'FAIL' and explanation.lower() == 'neither works':
            explanation = 'Neither approach passed the pre-registered checks. Finishing the runs does not make either approach ready to use.'
        elif key == 'interim94' and 'opens_f1' in result['detail']:
            label = 'Mixed finding'
            explanation = 'The recorded score gap grew with more data. That score was later qualified: it does not show that the policy can act successfully on its own.'
        elif verdict == 'undecided' and 'No experiment judge' in explanation:
            explanation = 'Job status is available, but no experiment-level judge decision has been copied to the board yet.'
        arm_html = ''.join(f'<div class="arm"><span class="arm-id">{escape(mark)}</span><div><b>{escape(name)}</b><p>{escape(text)}</p></div></div>' for mark, name, text in arms)
        return (f'<article class="experiment"><div class="experiment-head"><span class="experiment-num">{escape(serial)}</span>'
                f'<div class="experiment-heading"><h3>{escape(title)}</h3></div></div><p class="purpose">{escape(question)}</p>'
                f'<div class="outcome"><span class="badge {escape(verdict.lower())}">{escape(label)}</span><p>{escape(explanation)}</p></div>'
                f'<div class="arms">{arm_html}</div><footer><span>{escape(result["name"])}</span>{link(result["evidence"])}</footer>'
                f'<details class="technical"><summary>Recorded verdict</summary><p>{escape(verdict)} · {escape(result["detail"])}</p></details></article>')

    # Put the current experiments first, rather than ordering by when a copy landed.
    experiments = [r for r in snapshot['results'] if r.get('kind') == 'experiment']
    order = {'countermeasures2': 0, 'countermeasures': 1, 'interim94': 2}
    experiments.sort(key=lambda r: order.get(r['name'].split(' / ')[-1], 3))
    reports = [r for r in snapshot['results'] if r.get('kind') == 'report']
    report_html = ''.join(f'<article class="report-row"><h3>{escape(describe_job(r["name"])[0])}</h3>'
                          f'<p>{escape(r["name"])} · {escape(r["verdict"])}</p>{link(r["evidence"])}</article>' for r in reports)
    health_text = snapshot.get('health_summary', snapshot['health'])
    gpu = re.search(r'Mac GPU (\d+)%', health_text)
    pressure = re.search(r'memory pressure ([^·]+)', health_text)
    load = re.search(r'load 1/5/15 min ([^·]+)', health_text)
    swap = snapshot.get('swap_text', 'swap unknown')
    swap_values = re.search(r'swap used ([\d.]+) of ([\d.]+) GB', swap)
    warning = snapshot.get('swap_amber', False)
    gpu_bar = f'<div class="capacity"><span style="width:{min(100, int(gpu[1]))}%"></span></div>' if gpu else ''
    swap_bar = ''
    if swap_values and float(swap_values[2]) > 0:
        percent = min(100, 100 * float(swap_values[1]) / float(swap_values[2]))
        swap_bar = f'<div class="capacity {"amber" if warning else ""}"><span style="width:{percent:.1f}%"></span></div>'
    machine = ('<section class="panel"><div class="panel-body"><div class="machine-heading"><h2>Machine</h2><span class="eyebrow">Mac</span></div>'
               f'<div class="machine-metric"><div class="metric-label"><span>GPU utilization</span><strong>{gpu[1] + "%" if gpu else "Unknown"}</strong></div>{gpu_bar}</div>'
               f'<div class="machine-metric"><div class="metric-label"><span class="{"amber" if warning else ""}">{escape(swap)}</span></div>{swap_bar}'
               + ('<p class="machine-warning">Above 80% of available swap</p>' if warning else '') + '</div>'
               f'<dl class="machine-details"><dt>Memory pressure</dt><dd>{escape(pressure[1].strip()) if pressure else "Unknown"}</dd>'
               f'<dt>Load · 1 / 5 / 15 min</dt><dd>{escape(load[1].strip()) if load else "Unknown"}</dd></dl></div></section>')
    waiting = ''.join('<li>' + re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escape(item)) + '</li>' for item in snapshot['waiting'])
    waiting_panel = '<section class="panel"><div class="panel-header"><h2>Up next for James</h2></div><div class="panel-body"><ol class="waiting">' + (waiting or '<li>No requests recorded.</li>') + '</ol></div></section>'
    glossary = ('<section class="panel glossary-panel"><div class="panel-body glossary"><div class="eyebrow">Reading the board</div>'
                '<p style="margin-top:14px"><strong>Finished ≠ passed.</strong> A finished run exited successfully. A verdict says whether its approach met the experiment’s bar.</p>'
                '<p><strong>Arms</strong> are the approaches being compared. <strong>Seeds</strong> repeat an approach with different random starting points. '
                '<strong>Epochs</strong> are passes through its training examples.</p>'
                '<p><strong>Range learning</strong> teaches actions from gameplay. <strong>IDM</strong> learns to infer the human’s inputs from video.</p></div></section>')
    if active_runs:
        live_jobs = ''.join(job_card(j) for j in active_runs)
    elif queues:
        live_jobs = ''.join(job_card(j) for j in queues)
    else:
        live_jobs = '<div class="idle"><span class="idle-mark">—</span><div><h3>No training jobs confirmed running</h3><p>Recent results are below. Jobs without a confirmed exit remain listed separately.</p></div></div>'
    if queues and active_runs:
        live_jobs += '<details class="fold"><summary>Queue status <span class="muted">Orchestration, separate from training runs</span></summary>' + ''.join(job_card(j) for j in queues) + '</details>'
    headline = 'Training is in progress.' if running_count else 'The queue is moving.' if queues else 'Training, at a glance.'
    summary = 'Follow the runs. Understand what they tested. See what is ready for the next step.'
    preview = '<div class="preview-banner">LOCAL DESIGN PREVIEW · simulated running states; no training was started.</div>' if snapshot.get('preview') else ''
    warning_html = ''.join('<div class="warning-banner">' + escape(w) + '</div>' for w in snapshot['warnings'])
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="30"><title>Rivals · Training lab</title><style>{CSS}</style></head><body><div class="shell">'
            '<header class="masthead"><div class="brand">RIVALS<span>/ TRAINING LAB</span></div><div class="live-label"><span class="dot"></span>'
            '<span class="refresh-label">Updates every 30 seconds</span><a href="/api/status">Snapshot ↗</a></div></header>'
            f'<section class="overview"><div><h1>{headline}</h1><p>{summary}</p></div><div class="stats">'
            f'<div class="stat"><b class="orange">{running_count}</b><span>RUNNING JOBS</span></div><div class="stat"><b>{sum(j["stage"] == "done" for j in recent_runs)}</b><span>FINISHED · LAST 48 H</span></div>'
            f'<div class="stat"><b class="{"amber" if unconfirmed else "mint"}">{len(unconfirmed)}</b><span>UNCONFIRMED · CURRENT</span></div></div></section>'
            f'{preview}{warning_html}<div class="layout"><main class="main"><section class="panel"><div class="panel-header"><h2>Running now</h2>'
            f'<small>{running_count} running · {queued_count} queued</small></div>{live_jobs}</section>'
            '<div class="section-heading"><h2>What the experiments tested</h2><small>Recorded decisions</small></div>'
            + (''.join(experiment_card(r) for r in experiments) or '<div class="panel empty-note">No experiment decisions have been recorded yet.</div>') +
            f'<details class="panel fold"><summary>Recent runs ({len(finished)})<span class="muted">Last 48 hours · completion is separate from acceptance</span></summary>'
            f'{"".join(job_card(j) for j in finished)}</details>'
            f'<details class="panel fold"><summary>Unconfirmed jobs ({len(unconfirmed)})<span class="muted">No confirmed terminal state</span></summary>{"".join(job_card(j) for j in unconfirmed)}</details>'
            f'<details class="panel fold" id="history"><summary>History ({len(history)})<span class="muted">Finished or unconfirmed · older than 48 hours</span></summary>{"".join(job_card(j) for j in history)}</details>'
            f'<details class="panel fold"><summary>Per-run report gates ({len(reports)})<span class="muted">Technical results, without recomputing metrics</span></summary>{report_html}</details></main>'
            f'<aside class="sidebar">{machine}{waiting_panel}{glossary}</aside></div><footer class="page-footer"><span>Snapshot · {escape(snapshot["updated"])}</span>'
            '<span>Read-only · tailnet only · source evidence stays on the Mac</span></footer></div></body></html>')

def serve(board, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            snapshot = board.snapshot()
            path = urlsplit(self.path).path
            if path == "/":
                body, mime = render(snapshot, board.evidence).encode(), "text/html; charset=utf-8"
            elif path == "/api/status":
                body, mime = json.dumps(snapshot).encode(), "application/json"
            elif path.startswith("/evidence/") and path[10:] in board.evidence:
                body = json.dumps(board.evidence[path[10:]], indent=2).encode()
                mime = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # No growing access log from phone refreshes.

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--range-root", type=Path, default=Path.home() / "dev/range-bc-data")
    parser.add_argument("--idm-root", type=Path, default=Path.home() / "dev/idm-data")
    parser.add_argument("--result-root", type=Path)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--dump", action="store_true")
    args = parser.parse_args()
    if hasattr(os, "nice") and os.getpriority(os.PRIO_PROCESS, 0) < 10:
        os.nice(10 - os.getpriority(os.PRIO_PROCESS, 0))
    board = Board(args.repo, [("range_bc", args.range_root), ("IDM", args.idm_root)], args.result_root)
    if args.dump:
        print(json.dumps(board.snapshot(), indent=2))
    else:
        serve(board, args.port)


if __name__ == "__main__":
    main()
