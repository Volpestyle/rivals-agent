"""Guarded Windows native spot checks on a pinned, admitted SSL allowlist.

CPU-only, one ffmpeg child, two threads. This produces inspection evidence,
not a gameplay interval admission or a training packet.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

from policy import idm_targets as T
from scripts.job_status import write

BELOW_NORMAL = 0x4000
NO_WINDOW = 0x08000000


class Memory(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                *[(n, ctypes.c_ulonglong) for n in ("total", "available", "page_total", "page_available",
                                                   "virtual_total", "virtual_available", "extended")]]


class ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong),
                *[(n, ctypes.c_size_t) for n in ("peak_working", "working", "quota_peak_paged", "quota_paged",
                                                "quota_peak_nonpaged", "quota_nonpaged", "page", "peak_page")]]


def guard(child=None):
    m = Memory()
    m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise RuntimeError("memory check unavailable")
    if m.available < 4 * 1024**3:
        raise RuntimeError("free physical RAM below 4 GiB")
    rows = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                          check=True, timeout=5, creationflags=BELOW_NORMAL | NO_WINDOW).stdout.lower()
    if any(r.startswith(('"marvel', '"obs64')) for r in rows.splitlines()):
        raise RuntimeError("game/OBS started")
    for handle in (ctypes.windll.kernel32.GetCurrentProcess(), getattr(child, "_handle", None)):
        if handle is None:
            continue
        info = ProcessMemory()
        info.cb = ctypes.sizeof(info)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(handle)), ctypes.byref(info), info.cb):
            raise RuntimeError("process memory check unavailable")
        if info.working >= 3 * 1024**3:
            raise RuntimeError("process memory reached 3 GiB")
    return m.available


def admitted(path, pin):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("SSL admission pin mismatch")
    doc = json.loads(raw)
    if doc.get("schema") != "rivals-ssl-whole-file-admission-v1" or doc.get("status") != "accepted_ssl_only":
        raise ValueError("accepted SSL-only admission required")
    if doc.get("forbidden_family_overlap_result") != "pass_filename_date_and_exact_digest_checks":
        raise ValueError("source overlap check absent")
    deny = T.load_denylist()
    sources = doc["sources"]
    if len({s["media_sha256"] for s in sources}) != len(sources):
        raise ValueError("duplicate SSL source")
    # Existing sealed guard is used before any source file is opened or statted.
    for source in sources:
        T.refuse_sealed(source["source_family"], source["media_sha256"], deny)
        if (source.get("status") != "accepted_ssl_only" or source.get("semantic_labels_allowed") is not False
                or source.get("season") != "S6.5" or source.get("codec") != "hevc"):
            raise ValueError("source not admitted to this pilot")
        if Path(source["path"]).name != source["name"] or "DayMR" in source["path"]:
            raise ValueError("source name mismatch/forbidden family")
    return sources


def source_unchanged(source):
    log = Path(source["replaced_log_identity"]["path"])
    latest = None
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("file") == source["name"]:
                latest = row
    if latest != source["replaced_log_identity"]["record"] or latest.get("status") != "replaced":
        raise ValueError("source replacement identity changed")
    p = Path(source["path"])
    if p.is_symlink() or p.stat().st_size != source["bytes"]:
        raise ValueError("source path/size changed")
    expected = datetime.fromisoformat(source["last_write_utc"].replace("Z", "+00:00")).timestamp()
    if abs(p.stat().st_mtime - expected) > .001:
        raise ValueError("source modification time differs from freshly hashed admission")
    return p.stat()


def bounded_ffmpeg(command, log):
    guard()
    with Path(log).open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=stream,
                                   creationflags=BELOW_NORMAL | NO_WINDOW)
        start = time.monotonic()
        try:
            while process.poll() is None:
                guard(process)
                if time.monotonic() - start > 120:
                    raise TimeoutError("sample decode exceeded 120 seconds")
                time.sleep(1)
            if process.returncode:
                raise RuntimeError("ffmpeg failed; see " + str(log))
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait()
            raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--admission", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)
    sources = admitted(a.admission, a.sha256)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    job = "idm-ssl-native-inspection-20260927-01"
    write(job, owner="idm-owner", host="pc", stage="running", evidence=str(out / "samples.json"))
    records = []
    try:
        for i, source in enumerate(sources):
            guard()
            before = source_unchanged(source)
            for j, fraction in enumerate((.2, .4, .6, .8)):
                seconds = round(source["duration_seconds"] * fraction, 3)
                target = out / f"source-{i}-sample-{j}.png"
                log = out / f"source-{i}-sample-{j}.log"
                command = ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "2", "-hwaccel", "none",
                           "-ss", str(seconds), "-copyts", "-i", source["path"], "-an", "-sn", "-dn",
                           "-filter_threads", "2", "-vf", "showinfo", "-frames:v", "1", "-threads", "2",
                           "-update", "1", str(target)]
                bounded_ffmpeg(command, log)
                record = {"source_family": source["source_family"], "media_sha256": source["media_sha256"],
                          "requested_seconds": seconds, "native_image": str(target), "ffmpeg_log": str(log),
                          "image_sha256": T.sha256(target)}
                records.append(record)
                write(job, progress={"n": len(records), "total": len(sources) * 4})
            after = source_unchanged(source)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("source changed during sampling")
        (out / "samples.json").write_text(json.dumps({"admission_sha256": a.sha256, "samples": records,
                                                    "purpose": "inspection only; not interval admission"}, indent=2) + "\n")
        write(job, stage="done")
    except BaseException:
        write(job, stage="failed")
        raise


if __name__ == "__main__":
    main()
