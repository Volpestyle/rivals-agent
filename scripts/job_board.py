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
        waiting = [line.strip()[2:] for line in read(self.repo / "docs/waiting-on-james.md").splitlines()
                   if line.strip().startswith("- ")]
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


CSS = """
:root{color-scheme:dark;font:16px system-ui;background:#111820;color:#e8edf3}
body{max-width:1160px;margin:auto;padding:24px}h1{font-size:2rem;margin-bottom:8px}
h2{margin-top:32px}a{color:#8dc6ff}p,small{color:#afbdca}small{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:12px}
article,.health{border:1px solid #344453;border-radius:12px;padding:16px;background:#18232e}
article h3{margin:0 0 12px;overflow-wrap:anywhere;font-size:1rem}.badge{font-weight:700}
.running,.PASS{color:#7eecb1}.failed,.FAIL{color:#ffa4a4}.unknown,.undecided,.amber{color:#ffd38d}
dl{display:grid;grid-template-columns:80px 1fr;gap:6px;font-size:14px}dt{color:#afbdca}dd{margin:0;overflow-wrap:anywhere}
li{margin:10px 0}code{overflow-wrap:anywhere;font-size:12px}details{margin:18px 0}summary{cursor:pointer}
@media(max-width:500px){body{padding:16px}h1{font-size:1.7rem}}
"""


def render(snapshot, evidence):
    def link(url):
        path = evidence.get(url.rsplit("/", 1)[-1], {}).get("path", "metadata")
        return f'<a href="{escape(url)}"><code>{escape(path)}</code></a>'

    def card(job):
        fields = [(label, job[key]) for label, key in (("Progress", "progress"), ("Arm", "arm"),
                  ("Seed", "seed"), ("Started", "started"), ("ETA", "eta"), ("PID", "pid"), ("Verdict", "verdict"))]
        return (f'<article><h3>{escape(job["name"])}</h3><span class="badge {escape(job["stage"])}">'
                f'{escape(job["stage"]).upper()}</span><dl>' +
                "".join(f"<dt>{label}</dt><dd>{escape(str(value))}</dd>" for label, value in fields) +
                f'</dl><p>{escape(job["detail"])}</p>{link(job["evidence"])}</article>')

    cutoff = time.time() - 48 * 60 * 60
    history = [j for j in snapshot["jobs"]
               if j["stage"] in ("done", "failed", "unknown") and 0 < j["updated"] < cutoff]
    current = [j for j in snapshot["jobs"] if j not in history]
    active = [j for j in current if j["stage"] in ("running", "queued")]
    unconfirmed = [j for j in current if j["stage"] == "unknown"]
    finished = [j for j in current if j["stage"] in ("done", "failed")]
    health_html = escape(snapshot.get("health_summary", snapshot["health"]))
    if "swap_text" in snapshot:
        warning = snapshot.get("swap_amber", False)
        health_html += (f' · <span class="{"amber" if warning else ""}">'
                        f'{escape(snapshot["swap_text"])}{" · above 80%" if warning else ""}</span>')
    def result_cards(kind):
        return "".join(f'<article><h3>{escape(r["name"])}</h3><b>{escape(r["verdict"])}</b>'
                       f'<p>{escape(r["detail"])}</p>{link(r["evidence"])}</article>'
                       for r in snapshot["results"] if r.get("kind") == kind)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="refresh" content="30"><title>Rivals training</title>'
            f'<style>{CSS}</style></head><body><h1>Rivals training</h1>'
            '<p>Read-only · refreshes every 30 seconds · job completion is separate from experiment acceptance.</p>'
            f'<small>Snapshot: {escape(snapshot["updated"])}</small>'
            + "".join(f'<p class="unknown">{escape(w)}</p>' for w in snapshot["warnings"]) +
            f'<h2>Waiting on James</h2><ul>{"".join("<li>" + escape(x) + "</li>" for x in snapshot["waiting"])}</ul>'
            f'<div class="health">{health_html}</div><h2>Jobs</h2>'
            f'<p>{len(active)} running or queued · {len(unconfirmed)} unconfirmed · {len(finished)} finished in the last 48 h</p>'
            f'<div class="grid">{"".join(card(j) for j in active)}</div>'
            f'<details><summary>Unconfirmed jobs ({len(unconfirmed)})</summary><div class="grid">'
            f'{"".join(card(j) for j in unconfirmed)}</div></details>'
            f'<details><summary>Finished jobs ({len(finished)})</summary><div class="grid">'
            f'{"".join(card(j) for j in finished)}</div></details>'
            f'<details id="history"><summary>History ({len(history)}) · older than 48 h</summary><div class="grid">'
            f'{"".join(card(j) for j in history)}</div></details>'
            f'<h2>Results</h2><p>Existing judge decisions and report gates only. Unknown or incomplete bars stay undecided. '
            f'Evidence links show metadata only.</p><div class="grid">{result_cards("experiment")}</div>'
            f'<details><summary>Per-run report gates</summary><div class="grid">{result_cards("report")}'
            '</div></details></body></html>')


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
