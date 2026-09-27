"""Bounded CPU focal diagnostic on three explicitly authorized CALIBRATION takes.

Lead must release the game/recording hold before inspect/window. Metadata mode
never accesses video. Times are LOGGER seconds, not seek positions. Old records
stay immutable; numerical diagnostics are not calibration acceptance.
"""
import argparse
from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CALIBRATION = ROOT / "data/human/calibration"
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
ENV_PYTHON = "C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe"
EVIDENCE = ROOT / "docs/evidence/focal-calibration-20260927"

# Windows selected from old input-only stroke/rest plans before any new pixels.
# First native inspection will be on alt_left only, then a small adjacent sample.
SOURCES = {
    "alt_left": {
        "session": "20260926T162648-153Z-116800-4", "account": "alt",
        "account_source": "calibration.json account; recording-log 2026-09-26 11:26 row",
        "video_path": "C:/Users/volpe/Videos/2026-09-26 11-26-48.mkv",
        "expected_media_sha256": "764f3fbce3cdb1eee8fbbcfe16f06e132c302b38cd7d5f06e3349fc9aeb72923",
        "start_ns": 507882435693300, "direction": -1,
        "inspect_logger_s": [4.018, 6.4, 10.0, 14.177],
        "track_windows_logger_s": [[6.0, 6.8], [9.5, 10.3], [16.0, 16.4], [22.0, 22.2]],
        "still_control_logger_s": [13.972, 14.383],
        "pitch_control_logger_s": [27.918, 28.319],
        "settings_status": "alt identity explicit; numeric settings not stated in this calibration JSON",
        "gain_reference": .0330738, "reported_gain_tolerance_fraction": .0008,
        "gain_caveat": "endpoint excess was estimated with assumed focal465; not independent focal truth",
    },
    "rightward_unassigned": {
        "session": "20260925T030045-211Z-7804-3", "account": None,
        "account_source": "no explicit account in inspected calibration/registry records; do not infer alt",
        "video_path": "C:/Users/volpe/Videos/2026-09-24 22-00-45.mkv",
        "expected_media_sha256": "ff6b1fa017cb251c599603a7d10f6ddb03ef832c15c71af6270b8c4ff07c0aca",
        "start_ns": 373120052255200, "direction": 1,
        "inspect_logger_s": [2.298, 6.1, 7.7, 9.598],
        "track_windows_logger_s": [[5.8, 6.4], [7.4, 8.0], [11.0, 11.4], [14.7, 14.9]],
        "still_control_logger_s": [9.598, 9.998],
        "settings_status": "dated unchanged-settings statement: 1.89/1.89,800DPI,acceleration1.00,smoothing on",
        "gain_reference": .0330738, "reported_gain_tolerance_fraction": .0008,
        "gain_caveat": "endpoint correction depends on focal; slow turn has8.3deg pitch and a mouse1 press at4.520s",
    },
    "main_right": {
        "session": "20260926T060921-977Z-60612-1", "account": "main",
        "account_source": "calibration.json main settings folder1859995554; dated James statement",
        "video_path": "C:/Users/volpe/Videos/2026-09-26 01-09-21.mkv",
        "expected_media_sha256": "becf4c8ca197d0803ad5129c135881c49f9243ddfd3f24ad8c96159b5438264b",
        "start_ns": 470836463375400, "direction": 1,
        "inspect_logger_s": [1.94, 3.5, 6.1, 9.263],
        "track_windows_logger_s": [[3.2, 3.8], [5.8, 6.4], [10.8, 11.2], [15.0, 15.25]],
        "still_control_logger_s": [9.045, 9.482],
        "settings_status": "James confirms main sensitivity1.89; calibration record states800DPI",
        "gain_reference": .0330738, "reported_gain_tolerance_fraction": .0025,
        "gain_caveat": "slow turn outside .08% scripted gate, accepted under .25% tolerance; focal465-dependent excess",
    },
}


def proposal(name):
    if name not in SOURCES:
        raise ValueError("only the three explicitly authorized calibration sources are allowed")
    return {"phase": "static_preparation_only", "source": deepcopy(SOURCES[name]),
            "time_basis": "(composition_ns - logger start_ns)/1e9; never assume logger_s equals video PTS",
            "candidate_focal_px_1280": None, "candidate_bounds_px_1280": None,
            "video_verified_this_task": False, "tests_run": False, "automatic_probe_queued": False,
            "requires_explicit_lead_game_closed_release": True, "cross_account_transfer_verified": False}


def load_static_metadata(name):
    """Only the two small metadata JSON files; no glob, video stat/hash or frames."""
    result = proposal(name)
    expected = result["source"]
    calibration_path = CALIBRATION / expected["session"] / "calibration.json"
    logger_path = RAW / expected["session"] / "metadata.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8-sig"))
    logger = json.loads(logger_path.read_text(encoding="utf-8-sig"))
    if (calibration.get("session") != expected["session"] or logger.get("session_id") != expected["session"]
            or calibration["media"]["path"] != expected["video_path"]
            or calibration["media"]["sha256"] != expected["expected_media_sha256"]
            or logger.get("video_path") != expected["video_path"]
            or logger.get("start_ns") != expected["start_ns"]):
        raise ValueError("authorized source metadata identity changed")
    result["metadata"] = {"calibration_ref": str(calibration_path), "logger_ref": str(logger_path),
        "capture_latency_calibrated": logger.get("capture_latency_calibrated"),
        "native_size": [logger.get("width"), logger.get("height")],
        "native_fps": [logger.get("fps_num"), logger.get("fps_den")],
        "settings_provenance": calibration.get("settings"),
        "account_provenance": calibration.get("account"), "clean_stop": logger.get("clean_stop")}
    return result


def proposed_packets(name, window, video_packet_rows):
    """Pure metadata selection for later use; selected packets still need decode verification.

    Sort by PTS, not callback order (B frames). Do not invent native ordinals
    from frame-rate multiplication; muxer-discarded tail packets are possible.
    Caller supplies this named source's frames.csv video rows after identity
    validation. No media is opened here.
    """
    source = proposal(name)["source"]
    if list(window) not in source["track_windows_logger_s"]:
        raise ValueError("window not in fixed proposal")
    start = source["start_ns"]
    selected = [dict(row) for row in video_packet_rows if int(row["track"]) == 0 and
                window[0] <= (int(row["composition_ns"])-start)/1e9 < window[1]]
    selected.sort(key=lambda r: int(r["pts"])*int(r["timebase_num"])/int(r["timebase_den"]))
    return selected


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def selected_packets(name, mode, index):
    source = proposal(name)["source"]
    path = RAW / source["session"] / "frames.csv"
    with path.open(newline="") as stream:
        packets = [r for r in csv.DictReader(stream) if int(r["track"]) == 0]
    if mode == "inspect":
        rows = [min(packets, key=lambda r: abs(int(r["composition_ns"])-source["start_ns"]-t*1e9))
                for t in source["inspect_logger_s"]]
    else:
        rows = proposed_packets(name, source["track_windows_logger_s"][index], packets)
    rows.sort(key=lambda r: int(r["composition_ns"]))
    if not 1 <= len(rows) <= 100:
        raise ValueError("selected native sample must contain1..100 frames")
    for r in rows:
        # Existing calibration anchor: nearest-ms muxer PTS = packet time +21ms.
        # FFmpeg's showinfo must verify exact timebase and every selected PTS.
        r["expected_mkv_pts"] = round(int(r["pts"])*int(r["timebase_num"])*1000/int(r["timebase_den"]))+21
    if len({r["expected_mkv_pts"] for r in rows}) != len(rows):
        raise ValueError("duplicate selected timestamps")
    return rows, digest(path)


def decode_sample(source, rows, output, guard):
    """One owned FFmpeg process, native BGR, checked timestamps and bounded RAM."""
    import cv2
    import numpy as np
    from policy.range_bc import cache
    tasks = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=True).stdout
    if tasks.lower().count('"ffmpeg.exe"') >= 2:
        raise RuntimeError("global two-decode slots occupied")
    # Available physical memory, checked independently of this process's RSS.
    import ctypes
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (k, ctypes.c_ulonglong) for k in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
    memory = Memory(); memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)) or memory.available < 3_000_000_000:
        raise RuntimeError("insufficient free RAM for bounded native sample")
    graph = "select='" + "+".join(f"eq(pts,{r['expected_mkv_pts']})" for r in rows) + "',showinfo," + cache.CONVERT.replace("format=rgb24", "format=bgr24")
    script = output / "filter.txt"
    script.write_text(graph, encoding="ascii")
    cmd = ["ffmpeg", "-v", "info", "-nostdin", "-threads", "2", "-i", source["video_path"],
           "-map", "0:v:0", "-filter_threads", "1", "-filter_script:v", str(script),
           "-frames:v", str(len(rows)), "-fps_mode", "passthrough", "-an", "-sn", "-threads", "2",
           "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1"]
    write(output / "decode-command.json", cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    guard.child = proc
    deadline = threading.Timer(90, lambda: proc.kill() if proc.poll() is None else None)
    deadline.daemon = True
    deadline.start()
    started, errors = time.monotonic(), []
    def drain():
        try:
            with (output / "showinfo.log").open("xb") as log:
                for line in iter(proc.stderr.readline, b""):
                    log.write(line)
        except BaseException as exc:
            errors.append(str(exc))
    thread = threading.Thread(target=drain, daemon=True); thread.start()
    frames, kept = [], []
    try:
        for i, row in enumerate(rows):
            if time.monotonic()-started > 90:
                raise TimeoutError("native sample exceeded90 seconds")
            raw = proc.stdout.read(2560*1440*3)
            if len(raw) != 2560*1440*3:
                raise ValueError("truncated native sample")
            native = np.frombuffer(raw, np.uint8).reshape(1440, 2560, 3)
            frames.append(cv2.resize(native, (1280, 720), interpolation=cv2.INTER_AREA))
            if len(rows) <= 4 or i in (0, len(rows)//2, len(rows)-1):
                path = output / f"native-{i:03}.png"
                if not cv2.imwrite(str(path), native):
                    raise ValueError("native PNG write failed")
                kept.append({"index": i, "path": path.name, "sha256": digest(path), "packet": row})
        if proc.stdout.read(1) or proc.wait(timeout=10) != 0:
            raise ValueError("extra native pixels or failed FFmpeg")
        thread.join(5)
        log = (output / "showinfo.log").read_text(errors="replace")
        shown = [(int(n), int(p)) for n, p in cache._SHOWINFO.findall(log)]
        if errors or thread.is_alive() or cache._TIMEBASE.findall(log) != [("1", "1000")]:
            raise ValueError("native decoder timebase/log mismatch")
        if shown != [(i, r["expected_mkv_pts"]) for i, r in enumerate(rows)]:
            raise ValueError("native PTS selection does not match logger packets")
        write(output / "native-evidence.json", {"frames": len(frames), "shape": [1440,2560,3],
              "shown": shown, "retained": kept, "decoder_pid": proc.pid, "decoder_exit": proc.returncode})
        return frames
    finally:
        deadline.cancel()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10); thread.join(5)
        proc.stdout.close(); proc.stderr.close(); guard.child = None


def run_sample(args):
    from scripts.profile_range_bc_live import PCGuard
    from scripts import job_status
    import cv2
    cv2.setNumThreads(1)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    output = EVIDENCE / (args.source+"-"+args.mode+"-"+time.strftime("%Y%m%dT%H%M%S", time.gmtime()))
    output.mkdir(parents=True, exist_ok=False)
    job = "focal-calibration-"+args.source
    job_status.write(job, owner="camera-analysis", stage="running", host="pc", started=int(time.time()), evidence=str(output))
    class Guard(PCGuard):
        child = None
        def watch(self):
            while not self.done.wait(.5):
                try:
                    self.check()
                except BaseException as exc:
                    if self.child is not None and self.child.poll() is None:
                        self.child.kill(); self.child.wait(timeout=5)
                    write(output / "ABORT.json", {"reason": str(exc)})
                    job_status.write(job, stage="failed", progress=str(exc))
                    os._exit(3)
    guard = None
    try:
        guard = Guard(output)
        metadata = load_static_metadata(args.source)
        source = metadata["source"]
        write(output / "source.json", metadata)
        if digest(Path(source["video_path"])) != source["expected_media_sha256"]:
            raise ValueError("named calibration video identity changed")
        rows, frames_sha = selected_packets(args.source, args.mode, args.window_index)
        write(output / "selection.json", {"mode": args.mode, "window_index": args.window_index,
              "frames_csv_sha256": frames_sha, "packets": rows, "media_sha256_verified": True})
        frames = decode_sample(source, rows, output, guard)
        if args.mode == "window":
            from scripts.fit_focal_train import track_frames, fit_nuisance
            import numpy as np
            xy = track_frames(frames)
            origin = int(rows[0]["composition_ns"])
            raw_path = RAW / source["session"] / "inputs.jsonl"
            events = []
            with raw_path.open() as stream:
                for line in stream:
                    e = json.loads(line)
                    if e.get("type") == "mouse" and e.get("relative") and e.get("device") and origin-1e9 <= e["t_ns"] <= int(rows[-1]["composition_ns"])+1e8:
                        events.append(e)
            ft = [(int(r["composition_ns"])-origin)/1e9 for r in rows]
            et = [(e["t_ns"]-origin)/1e9 for e in events]
            dx = [e["dx"] for e in events]
            np.savez_compressed(output / "tracks.npz", xy=xy, frame_times=ft, event_times=et, dx=dx)
            try:
                fit = fit_nuisance(xy, ft, et, dx)
            except ValueError as exc:
                fit = {"refusal_reasons": [str(exc)], "candidate_focal_px_1280": None}
            # Prior helper's historical .02% widening is NOT this source's bound.
            # Preserve its diagnostic, invalidate any unconditional interval.
            fit.update(source_gain_tolerance_fraction=source["reported_gain_tolerance_fraction"],
                       gain_focal_coupling_unresolved=True, candidate_focal_bounds_px_1280=None,
                       conditional_bounds_are_source_uncertainty=False,
                       account=source["account"], raw_mouse_sha256=digest(raw_path), tracks=int(xy.shape[1]),
                       frames=len(frames), candidate_focal_px_1280=None)
            write(output / "fit.json", fit)
        guard.check()
        write(output / "completion.json", {"all_owned_decoders_stopped": True, "peak_rss_bytes": guard.peak, "gpu": False})
        job_status.write(job, stage="done", progress=args.mode+" completed; no calibration accepted")
        print(str(output))
    except BaseException as exc:
        write(output / "refusal.json", {"reason": str(exc), "candidate_focal_px_1280": None})
        job_status.write(job, stage="failed", progress=str(exc))
        raise
    finally:
        if guard is not None:
            guard.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=tuple(SOURCES), required=True)
    parser.add_argument("--mode", choices=("metadata", "inspect", "window"), default="metadata")
    parser.add_argument("--window-index", type=int, choices=range(4), default=0)
    args = parser.parse_args(argv)
    if args.mode == "metadata":
        print(json.dumps(load_static_metadata(args.source), indent=2, allow_nan=False))
    else:
        run_sample(args)


if __name__ == "__main__":
    main()
