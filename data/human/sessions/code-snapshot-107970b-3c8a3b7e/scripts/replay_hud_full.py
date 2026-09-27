"""Read the followed player's HUD on every frame of a replay recording, in resumable windows, under the decode gate.

    python scripts/replay_hud_full.py [--video ...] [--start 464.938] [--end 2062.887] [--window 30] [--workers 4]
    python scripts/replay_hud_full.py --finish          # events and manifest from the windows written so far

Per window [t0, t0 + window) of the original's clock (the intake README's clock):
- The gate is checked first: free physical memory above GATE_FREE_GB and no other ffmpeg or ffprobe running.
  Otherwise the run stops (exit 3) and a later run resumes.
- ffmpeg (4 threads, the caller's low priority inherited) decodes ONLY two bands, the viewer's POV bar (rows
  POV_Y0..POV_Y1) and the HUD strip (rows HUD_Y0..1440), stacked. It streams them raw to this process (nothing
  decoded is written to disk), with -copyts and a trim on the frames' own PTS, and showinfo giving each frame's PTS.
- Each frame is put back into a 2560x1440 canvas and read by perception.replay_hud.read_frame in `--workers`
  processes, in order.
- At most IN_FLIGHT frames are held between the decoder and the readers. Free memory is checked every MEMORY_EVERY
  frames; under STOP_FREE_GB, ffmpeg is killed, the partial window is discarded, and the run stops (exit 3);
  rerunning resumes at that window.
- The window's rows go to hud/rows-<t0>.jsonl.gz (the per-frame table of the contract, one JSON object per
  (frame, field)), and the window is recorded in hud/progress.json with the file's sha256, frame count and first and
  last PTS.
When every window is done (or with --finish), cast_events runs over all rows (min_run 3; the team-up is Symbiote
Bond, 15 s) and writes hud/events.json (events, coverage, flags, withheld share by reason, per-ability counts) and
hud/manifest.json (sha256 of every output, the tool, the reader, the video's recorded sha256 and the order evidence).
"""
import argparse
import collections
import ctypes
import dataclasses
import gzip
import hashlib
import json
import re
import subprocess
import sys
import threading
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

REPLAY = ROOT / "data" / "demos" / "replays" / "daymr-20260923-004325"
VIDEO = Path("C:/Users/volpe/Videos/2026-09-23 00-43-25.mkv")
OUT = REPLAY / "hud"
W, H = 2560, 1440
POV_Y0, POV_Y1 = 266, 292          # replay_hud.POV_BAR_Y (270-289) with margin
HUD_Y0 = 1180                      # every hud.MK region and the timeline markers lie below this row
BAND_H = (POV_Y1 - POV_Y0) + (H - HUD_Y0)
FRAME_BYTES = W * BAND_H * 3
GATE_FREE_GB, STOP_FREE_GB = 5.0, 4.0
MEMORY_EVERY = 240
IN_FLIGHT = 48                     # frames decoded but not yet read: bounds memory to about 100 MB
FOLLOW = "B5"
TEAMUP_S = 15.0                    # DayMR's team-up: Symbiote Bond (kit)
MIN_RUN = 3
COVERAGE_MAX_GAP_S = 0.25          # at 120 fps, reads further apart than this bridge unread frames


class Paused(Exception):
    pass


def free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise Paused("cannot read free memory: treated as below the gate")
    return m.ullAvailPhys / 2 ** 30


def other_decoders():
    run = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=30)
    if run.returncode != 0 or not run.stdout.strip():
        raise Paused("tasklist failed: the gate cannot be checked")
    names = [line.split('","')[0].strip('"').lower() for line in run.stdout.splitlines() if line.strip()]
    return sorted({n for n in names if n in ("ffmpeg.exe", "ffprobe.exe")})


def lower_priority():
    """This process to below-normal priority; ffmpeg and the reader workers inherit it. True if set."""
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.SetPriorityClass.restype = wintypes.BOOL
    return bool(k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000))


def gate():
    free, others = free_gb(), other_decoders()
    if free <= GATE_FREE_GB or others:
        raise Paused(f"decode gate closed: {free:.1f} GB free, other decoders {others}")
    return free


# --- worker ----------------------------------------------------------------------------------------------------

_ORDER = None


def _init(order):
    global _ORDER
    _ORDER = tuple(order)


def _read(job):
    import numpy as np
    from perception import replay_hud as rh
    t, raw = job
    band = np.frombuffer(raw, np.uint8).reshape(BAND_H, W, 3)
    frame = np.zeros((H, W, 3), np.uint8)
    frame[POV_Y0:POV_Y1] = band[:POV_Y1 - POV_Y0]
    frame[HUD_Y0:] = band[POV_Y1 - POV_Y0:]
    return [dataclasses.asdict(r) for r in rh.read_frame(frame, t, _ORDER, source="replay", follow=FOLLOW)]


# --- one window ------------------------------------------------------------------------------------------------

def window(video, t0, t1, pool, out_path):
    """Decode and read [t0, t1). Returns (frames, first_pts, last_pts). Raises Paused on low memory."""
    vf = (f"trim=start={t0:.3f}:end={t1:.3f},split=2[a][b];[a]crop={W}:{POV_Y1 - POV_Y0}:0:{POV_Y0}[p];"
          f"[b]crop={W}:{H - HUD_Y0}:0:{HUD_Y0}[h];[p][h]vstack,showinfo")
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "4", "-copyts", "-ss", f"{max(0.0, t0 - 2):.3f}",
           "-i", str(video), "-an", "-filter_complex", vf, "-fps_mode", "passthrough", "-enc_time_base:v", "1/1000",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=FRAME_BYTES)
    pts, err_tail = [], collections.deque(maxlen=20)

    def stderr():
        for line in proc.stderr:
            text = line.decode("utf-8", "replace")
            m = re.search(r"n:\s*\d+\s+pts:\s*\d+\s+pts_time:([0-9.]+)", text)
            if m:
                pts.append(float(m.group(1)))
            else:
                err_tail.append(text.strip())

    reader = threading.Thread(target=stderr, daemon=True)
    reader.start()

    inflight = threading.BoundedSemaphore(IN_FLIGHT)     # Pool.imap drains its input eagerly: bound it here

    def frames():
        i = 0
        while True:
            inflight.acquire()
            raw = proc.stdout.read(FRAME_BYTES)
            if len(raw) < FRAME_BYTES:
                inflight.release()
                return
            while len(pts) <= i and reader.is_alive():
                time.sleep(0.001)
            if len(pts) <= i:
                raise RuntimeError("a frame arrived without its showinfo PTS")
            yield pts[i], raw
            i += 1

    n = 0
    tmp = out_path.with_suffix(".partial")
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for rows in pool.imap(_read, frames(), chunksize=4):
                inflight.release()
                for r in rows:
                    fh.write(json.dumps(r) + "\n")
                n += 1
                if n % MEMORY_EVERY == 0 and free_gb() < STOP_FREE_GB:
                    proc.kill()
                    raise Paused(f"free memory under {STOP_FREE_GB} GB during the window at {t0:.3f}")
        proc.wait(timeout=60)
        reader.join(timeout=10)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg exited {proc.returncode}: {list(err_tail)[-3:]}")
        if n != len(pts):
            raise RuntimeError(f"{n} frames read but {len(pts)} PTS logged")
        tmp.replace(out_path)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        tmp.unlink(missing_ok=True)
    return n, (pts[0] if pts else None), (pts[-1] if pts else None)


# --- finish ----------------------------------------------------------------------------------------------------

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def finish(progress, order_doc, args):
    from perception import replay_hud as rh
    rows, reasons, frames = [], collections.Counter(), 0
    for key in sorted(progress["windows"], key=float):
        path = OUT / progress["windows"][key]["file"]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                rows.append(rh.Row(**d))
                if d["ability"] == "teamup":
                    frames += 1
                    reasons[d["reason"] if d["state"] == "unknown" else "read"] += 1
    # Coverage ends at withheld frames (the module), and at the operator's seeks and excluded footage (review R3);
    # reads 120 per second: a gap over COVERAGE_MAX_GAP_S is itself unread time, never evidence of "no cast"
    from replay_steps import EXCLUDE, SEEKS
    breaks = [(t, t) for t in SEEKS] + [(a_, b_) for a_, b_, _ in EXCLUDE]
    events, coverage, flags = rh.cast_events(rows, cooldowns={"teamup": TEAMUP_S}, min_run=MIN_RUN, breaks=breaks,
                                             max_gap_s=COVERAGE_MAX_GAP_S)
    # Press-time coverage (review item 2): HUD spans shrunk by the press -> first-evidence lag measured on James's
    # own footage (press-lags.json). Provisional: James's lags, n per ability as reported, not DayMR's.
    lags_doc = json.loads((ROOT / "docs" / "evidence" / "replay-hud-20260923" / "press-lags.json").read_text(
        encoding="utf-8"))["abilities"]
    lags = {a: (d["first_seen_lag_s"]["min"], d["first_seen_lag_s"]["max"], d["first_seen_lag_s"]["n"],
                d["first_seen_lag_s"]["median"]) if d["first_seen_lag_s"]["n"] else None
            for a, d in lags_doc.items()}
    press_cov = rh.press_coverage(coverage, events, lags)          # merged, cut at events, floored lag (round 2 P1)
    by = collections.Counter()
    for e in events:
        if e.basis != "flagged":                  # a flagged stretch is listed, never counted as a cast
            by[e.ability] += e.count
    prec = {}
    for ab in sorted({e.ability for e in events if e.basis != "flagged"}):
        p = sorted(e.precision for e in events if e.ability == ab and e.basis != "flagged")
        prec[ab] = {"median_s": round(p[len(p) // 2], 4), "p90_s": round(p[int(len(p) * 0.9)], 4)}
    doc = {
        "video": str(args.video), "follow": FOLLOW, "order": order_doc, "teamup_s": TEAMUP_S, "min_run": MIN_RUN,
        "frames": frames,
        "withheld_by_reason": {k: {"frames": v, "share": round(v / frames, 4)} for k, v in reasons.most_common()},
        "casts_by_ability": dict(by),
        "events_by_ability_basis": {f"{a}/{b}": n for (a, b), n in
                                    collections.Counter((e.ability, e.basis) for e in events).items()},
        "precision_by_ability": prec,
        "coverage_s": {k: round(sum(b - a for a, b in v), 2) for k, v in coverage.items()},
        "press_coverage_s": {k: round(sum(b - a for a, b in v), 2) for k, v in press_cov.items()},
        "press_lags_used": {a: {"measured_s": lags.get(a) and lags[a][:2], "n": lags_doc[a]["first_seen_lag_s"]["n"],
                                "floored_s": lags.get(a) and rh.floored_lag(*lags[a])} for a in lags_doc},
        "flags": flags,
        "events": [{"t": round(e.t, 4), "t_lo": round(e.t_lo, 4), "t_hi": round(e.t_hi, 4),
                    "precision": round(e.precision, 4), "ability": e.ability, "count": e.count, "basis": e.basis}
                   for e in events],
        "coverage": {k: [[round(a, 4), round(b, 4)] for a, b in v] for k, v in coverage.items()},
        "press_coverage": {k: [[round(a, 4), round(b, 4)] for a, b in v] for k, v in press_cov.items()},
    }
    (OUT / "events.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    recorded = (REPLAY / "sha256-original.txt").read_text(encoding="utf-8").split()[0]
    manifest = {
        "video": {"path": str(args.video), "recorded_sha256": recorded,
                  "note": "the original's sha256 as recorded by the intake (sha256-original.txt); not re-hashed"},
        "tool": {"path": "scripts/replay_hud_full.py", "sha256": sha256(__file__)},
        "reader": {"path": "perception/replay_hud.py", "sha256": progress.get("reader_sha256"),
                   "note": "the bytes that read every rows file (progress.json pins one per run)"},
        "finish_module": {"path": "perception/replay_hud.py", "sha256": sha256(ROOT / "perception" / "replay_hud.py"),
                          "note": "the bytes that turned the rows into events and coverage (this finish step)"},
        "hud_reader": {"path": "perception/hud.py", "sha256": sha256(ROOT / "perception" / "hud.py")},
        "files": {p.name: sha256(p) for p in sorted(OUT.glob("rows-*.jsonl.gz")) + [OUT / "events.json"]},
        "windows": progress["windows"],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--video", default=str(VIDEO))
    ap.add_argument("--start", type=float, default=464.938)
    ap.add_argument("--end", type=float, default=2062.887)
    ap.add_argument("--window", type=float, default=30.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--finish", action="store_true")
    ap.add_argument("--max-windows", type=int, help="stop after this many windows (for a trial)")
    a = ap.parse_args(argv)
    if not lower_priority():
        print("REFUSED: cannot lower this process to below-normal priority")
        return 2
    OUT.mkdir(exist_ok=True)
    prog_path = OUT / "progress.json"
    progress = json.loads(prog_path.read_text(encoding="utf-8")) if prog_path.is_file() else {"windows": {}}
    order_doc = json.loads((ROOT / "data" / "replay-hud" / REPLAY.name / "events.json").read_text(
        encoding="utf-8"))["order"]
    if order_doc.get("order") is None:
        print("REFUSED: the column order was not identified for this source")
        return 2
    if a.finish:
        doc = finish(progress, order_doc, a)
        print(json.dumps({k: doc[k] for k in ("frames", "withheld_by_reason", "casts_by_ability",
                                              "precision_by_ability", "coverage_s", "press_coverage_s")}, indent=1))
        return 0
    starts, t = [], a.start
    while t < a.end:
        starts.append(round(t, 3))
        t += a.window
    todo = [s for s in starts if f"{s:.3f}" not in progress["windows"]]
    reader_sha = sha256(ROOT / "perception" / "replay_hud.py")          # the bytes that read these windows
    # One reader for the whole run (review round 2, P3): the first window pins it, and a resumed run whose reader
    # bytes differ is refused rather than mixing versions. A new reader means a new run folder.
    pinned = progress.setdefault("reader_sha256", reader_sha)
    if pinned != reader_sha:
        print(f"REFUSED: this run was read by replay_hud.py {pinned[:12]}; the file is now {reader_sha[:12]}. "
              "Start a new run folder instead of mixing reader versions.")
        return 2
    done_now = 0
    with Pool(a.workers, initializer=_init, initargs=(order_doc["order"],)) as pool:
        for t0 in todo:
            if a.max_windows is not None and done_now >= a.max_windows:
                break
            try:
                free = gate()
                t1 = min(round(t0 + a.window, 3), a.end)
                out_path = OUT / f"rows-{t0:09.3f}.jsonl.gz"
                started = time.perf_counter()
                n, p0, p1 = window(Path(a.video), t0, t1, pool, out_path)
            except Paused as e:
                print(f"PAUSED at window {t0:.3f}: {e}")
                return 3
            progress["windows"][f"{t0:.3f}"] = {"t0": t0, "t1": t1, "file": out_path.name, "sha256": sha256(out_path),
                                                "frames": n, "first_pts": p0, "last_pts": p1,
                                                "free_gb_at_start": round(free, 1), "reader_sha256": reader_sha,
                                                "seconds": round(time.perf_counter() - started, 1)}
            prog_path.write_text(json.dumps(progress, indent=1) + "\n", encoding="utf-8")
            done_now += 1
            print(f"window {t0:.3f}-{t1:.3f}: {n} frames in {progress['windows'][f'{t0:.3f}']['seconds']} s")
    if len(progress["windows"]) == len(starts):
        doc = finish(progress, order_doc, a)
        print(json.dumps({k: doc[k] for k in ("frames", "withheld_by_reason", "casts_by_ability")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
