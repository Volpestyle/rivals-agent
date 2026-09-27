"""Tiny atomic job receipts for the read-only board (one writer per job name).

On the Mac, call write('decoder-audit', owner='r3-sidecar', stage='running',
host='mac', evidence='/path/to/audit.log'), then write the same name at progress
and exit. Fields persist across updates; a fresh attempt should set started
explicitly or use a new name. This module never launches or inspects a job.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile
import subprocess
import time

FIELDS = {"name", "owner", "stage", "started", "updated", "progress", "eta", "host", "evidence"}
STAGES = {"queued", "running", "done", "failed"}
HOSTS = {"mac", "pc", "modal"}


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0:
        return float(value)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.timestamp()
    raise ValueError("timestamps need a positive epoch or timezone-aware ISO 8601 value")


def validate(data):
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise ValueError("status needs exactly: " + ", ".join(sorted(FIELDS)))
    if not isinstance(data["name"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", data["name"]):
        raise ValueError("name must be a simple job filename (letters, digits, dots, dashes, underscores)")
    if data["stage"] not in STAGES or data["host"] not in HOSTS:
        raise ValueError("unsupported stage or host")
    for key in ("owner", "evidence"):
        if not isinstance(data[key], str) or not data[key].strip() or len(data[key]) > 4096:
            raise ValueError(key + " must be nonempty text")
    if timestamp(data["updated"]) < timestamp(data["started"]):
        raise ValueError("updated precedes started")
    progress = data["progress"]
    if isinstance(progress, dict):
        if (set(progress) != {"n", "total"} or any(type(v) is not int for v in progress.values())
                or not 0 <= progress["n"] <= progress["total"] or progress["total"] <= 0):
            raise ValueError("progress needs integer 0 <= n <= total and total > 0")
    elif not isinstance(progress, str) or len(progress) > 4096:
        raise ValueError("progress must be text or {n, total}")
    if data["eta"] is not None and (not isinstance(data["eta"], str) or len(data["eta"]) > 4096):
        raise ValueError("eta must be text or null")
    return data


def write(name, *, root=None, **fields):
    """Merge fields into ~/dev/jobs/<name>.status.json and atomically replace it.

    New entries require owner, stage, host and evidence; timestamps are UTC now,
    progress defaults to 'unknown', ETA to null. root is for explicit destinations
    and synthetic tests, not automatic remote transport. Do not put secrets here.
    """
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", name):
        raise ValueError("invalid job name")
    if set(fields) - FIELDS or "name" in fields:
        raise ValueError("unknown status fields")
    directory = Path(root) if root is not None else Path.home() / ("jobs" if os.name == "nt" else "dev/jobs")
    path = directory / (name + ".status.json")
    if path.is_symlink():
        raise ValueError("status cannot be a symlink")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if old:
        validate(old)
        if old["name"] != name:
            raise ValueError("existing status belongs to another job")
    data = {"name": name, "started": now, "progress": "unknown", "eta": None,
            **old, **fields, "updated": fields.get("updated", now)}
    validate(data)
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=directory,
                                         prefix="." + name + ".", suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
            json.dump(data, out, sort_keys=True, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def _metadata(path, limit=131072, tail=False):
    if path.is_symlink() or any(p.is_symlink() or 'sealed' in p.name.lower() for p in (path, *path.parents)):
        return ''
    try:
        with path.open('rb') as stream:
            size = os.fstat(stream.fileno()).st_size
            if size > limit:
                if not tail:
                    return ''
                stream.seek(size-limit)
            return stream.read(limit).decode('utf-8', errors='replace')
    except OSError:
        return ''


def matches_receipt(data, command, host):
    """Correlate a fresh receipt's log stem and directory with a driver path.
    Do not merge by lane/name alone: unrelated jobs can share both.
    """
    evidence = data.get('evidence', '').replace('\\', '/')
    if '/' not in evidence or data.get('host') != host or data.get('stage') != 'running':
        return False
    if time.time() - timestamp(data['updated']) > 1800:
        return False
    parent, filename = evidence.rsplit('/', 1)
    stem = filename.rsplit('.', 1)[0]
    cmd = command.replace('\\', '/')
    return len(stem) >= 4 and parent + '/' in cmd and re.search('/' + re.escape(stem) + r'(?=[._-])', cmd) is not None


def pc_snapshot(root=None, compression_log=None, procs=None, locations=None):
    """Read-only SSH probe: receipts, compression log tail, known compute PIDs.

    Never reads media or scripts. CLI prints metadata only, not process command
    lines. Explicit parameters allow wholly synthetic offline tests.
    """
    root = Path(root) if root is not None else Path.home() / 'jobs'
    log = Path(compression_log) if compression_log is not None else Path('D:/SPIDEY CLIPS/_hevc_compress_log.jsonl')
    receipts, warnings, observations = [], [], []
    for path in sorted(root.glob('*.status.json')):
        try:
            data = validate(json.loads(_metadata(path)))
            if path.name != data['name'] + '.status.json':
                raise ValueError('filename mismatch')
            receipts.append({'path': str(path), 'data': data})
        except (ValueError, TypeError, KeyError, OSError):
            warnings.append('Invalid PC receipt: ' + path.name)
    if procs is None:
        query = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|python3|ffmpeg|scp|rsync|robocopy|powershell|pwsh)(.exe)?$' } | "
                 "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', query],
                                    capture_output=True, text=True, timeout=6, check=True)
            procs = json.loads(result.stdout or '[]')
            if isinstance(procs, dict):
                procs = [procs]
        except (OSError, ValueError, subprocess.SubprocessError):
            procs = []
            warnings.append('PC process probe unavailable; activity is unconfirmed.')
    matched = []
    for p in procs:
        cmd = (p.get('CommandLine') or '').replace('\\', '/')
        executable = p.get('Name', '').lower()
        if executable in ('powershell.exe', 'pwsh.exe') and '-file ' not in cmd.lower():
            continue
        compression = 'd:/spidey clips/' in cmd.lower()
        script = re.search(r'([A-Za-z]:/[^\r\n"\']*/(?:[^/\s"\']*(?:transfer|compress)[^/\s"\']*)\.(?:py|ps1))', cmd, re.I)
        if script and 'dashboard' in script[1].lower():
            continue  # status heartbeat observer, not the transfer/compute driver
        if compression or script:
            location = str(log.parent) if compression else str(Path(script[1]).parent)
            matched.append((p, location, compression))
    matched_ids = {p['ProcessId'] for p, _, _ in matched}
    for p, location, compression in matched:
        if p.get('ParentProcessId') in matched_ids:
            continue  # one card per driver, not every child encoder/SSH
        registered = next((item for item in receipts if matches_receipt(item['data'], p.get('CommandLine') or '', 'pc')), None)
        if registered:
            registered['pid'] = str(p['ProcessId'])
            continue
        observations.append({'name': ('SPIDEY CLIPS compression' if compression else
                                      f'unregistered: {location}/pid {p["ProcessId"]}'),
                             'stage': 'running', 'pid': str(p['ProcessId']), 'location': location,
                             'updated': time.time(), 'detail': 'Known compute process observed; no exit verdict inferred.'})
    if log.exists():
        last = {}
        for line in _metadata(log, tail=True).splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    last = {k: row[k] for k in ('file', 'status', 'will_retry', 'elapsed_s', 'saved_bytes') if k in row}
            except ValueError:
                pass
        compression = next((o for o in observations if o['name'] == 'SPIDEY CLIPS compression'), None)
        if compression is None:
            compression = {'name': 'SPIDEY CLIPS compression', 'stage': 'unknown', 'pid': 'unknown',
                           'location': str(log), 'updated': log.stat().st_mtime,
                           'detail': 'No matching compression process; last log is historical evidence, not current progress.'}
            observations.append(compression)
        compression['log'] = {'path': str(log), 'updated': log.stat().st_mtime, 'last': last}
    if locations is None:
        scratch = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Temp/claude'
        locations = list(scratch.glob('C--Users-volpe/*/scratchpad/handoff/explore'))
    for folder in locations:
        folder = Path(folder)
        if not folder.is_dir() or folder.is_symlink():
            continue
        metadata = [p for p in folder.iterdir() if p.suffix in ('.log', '.jsonl', '.status', '.exit', '.pid') and not p.is_symlink()]
        latest = max([folder.stat().st_mtime] + [p.stat().st_mtime for p in metadata])
        if time.time()-latest <= 1800 and not any(o['location'] == str(folder) for o in observations):
            observations.append({'name': 'unregistered: ' + str(folder), 'stage': 'unknown', 'location': str(folder),
                                 'updated': latest, 'pid': 'unknown', 'detail': 'Known transfer location changed in the last 30 minutes; no receipt.'})
    return {'receipts': receipts, 'observations': observations, 'warnings': warnings, 'observed': time.time()}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-pc', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(pc_snapshot(), allow_nan=False))
