"""Validate perception.replay_hud's cast logic on known-input sources: 20 s windows of James's own first-person takes.

    uv run --group perception python scripts/replay_hud_validate.py [--window SESSION:START ...] [--pool]

Each window (SESSION:START in logger seconds, 20 s):
- the HUD strip of every frame (rows 1180-1440) is decoded ONCE into data/replay-hud/<take>-<start>/strip/, under
  the decode gate (free memory > 5 GB, no other ffmpeg or ffprobe, 4 threads, low priority inherited from the
  caller), with ffmpeg's showinfo giving each frame's original PTS;
- each frame's PTS is mapped to the logger clock. An imported session (data/human/sessions/<id>/imported-demo.jsonl)
  uses intake's independently anchored frame references. A session that is not imported uses its logger's
  frames.csv and the OBS profile's muxer offset (MUXER_OFFSET_MS, as intake anchored it for the same profile):
  every decoded PTS must lie within 1 ms of a logged packet shifted by it, and the residuals are reported;
- the strips are padded back to 2560x1440 and read with read_frame(..., JAMES_ORDER, source="first_person"). The
  events of cast_events (min_run 3, team-up 10 s) are matched to the latest press of their binding (C team-up,
  E Amazing Combo, F Get Over Here!, RMB Web Cluster, Shift / Caps Lock swing, Q ult) at most MATCH_BEFORE_S before
  the first read showing the cast;
- writes docs/evidence/replay-hud-20260923/validation-<take>[-<start>].json.
--pool writes docs/evidence/replay-hud-20260923/press-lags.json: per ability, n and the spread of the lag from press
to the first HUD evidence and, for countdown abilities, to the cooldown's start, pooled over every validation file.
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agent import human_demos as hd  # noqa: E402
from perception import replay_hud as rh  # noqa: E402

RAW = Path("C:/Users/volpe/Videos/RivalsInput")
EVIDENCE = ROOT / "docs" / "evidence" / "replay-hud-20260923"
STRIP_Y0 = 1180
DURATION_S = 20.0
KEYS = {67: "teamup", 69: "uppercut", 70: "get_over_here", 16: "swing", 20: "swing", 81: "ult"}   # James's bindings
RMB = 2
MATCH_BEFORE_S = 2.5          # a press may precede the first HUD evidence by at most this much
MIN_RUN = 3                   # frames: at 120 fps the ready read flickers for 1-3 frames
EDGE_S = 0.1                  # events starting within this of the window's first frame are edge effects
COUNTDOWN_PRESS_TOL_S = 0.05  # a countdown's press lies before its cooldown start (+ this, for the window's edges)
MUXER_OFFSET_MS = 21.0        # intake's independent anchor for this OBS profile: file ms - logged ms
FIRST = ("20260923T051828-422Z-33696-1", 30.31)
DEFAULT_WINDOWS = ("20260923T051828-422Z-33696-1:30.31", "20260923T051828-422Z-33696-1:133.8",
                   "20260923T051828-422Z-33696-1:78.3", "20260923T200129-346Z-33696-6:1003.5")


def take(session):
    return session[9:15]                                     # "051828"


def names(session, start_s):
    """(decode folder, evidence file) for a window; the first window keeps its landed names."""
    if (session, start_s) == FIRST:
        return ROOT / "data" / "replay-hud" / "051828-validation", EVIDENCE / "validation-051828.json"
    return (ROOT / "data" / "replay-hud" / f"{take(session)}-{start_s}",
            EVIDENCE / f"validation-{take(session)}-{start_s}.json")


def gate():
    from replay_hud_full import gate as full_gate
    return full_gate()


def logger_map(session):
    """({file pts ms: composition_ns}, start_ns, video path, how)."""
    meta = json.loads((RAW / session / "metadata.json").read_text(encoding="utf-8"))
    imported = ROOT / "data" / "human" / "sessions" / session / "imported-demo.jsonl"
    if imported.is_file():
        with imported.open(encoding="utf-8") as fh:
            header, payload = json.loads(fh.readline()), json.loads(fh.readline())
        refs, audit = hd.match_frames(payload["packets"], payload["decoded"], header["video_path"],
                                      pts_anchor=payload["review"].get("pts_anchor"))
        assert refs[0].timebase_den == 1000 and refs[0].timebase_num == 1
        how = {"kind": "intake anchored frame references",
               "muxer_offset_ms": audit["muxer_offset_num"] * 1000 / audit["muxer_offset_den"],
               "verified": audit["pts_alignment_verified"]}
        return {r.pts: r.composition_ns for r in refs}, meta["start_ns"], meta["video_path"], how
    out = {}
    with (RAW / session / "frames.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ms = int(row["pts"]) * 1000 * int(row["timebase_num"]) / int(row["timebase_den"]) + MUXER_OFFSET_MS
            out[ms] = int(row["composition_ns"])
    return out, meta["start_ns"], meta["video_path"], {"kind": "logger frames.csv + declared OBS-profile offset",
                                                       "muxer_offset_ms": MUXER_OFFSET_MS}


def decode(session, video, t0_video, t1_video, folder):
    """The HUD strip of [t0, t1) of the video into folder/strip, once; returns the PTS list (ms)."""
    log = folder / "showinfo.log"
    if not log.is_file():                       # no finished decode: start clean (an interrupted one leaves no log)
        gate()
        if (folder / "strip").is_dir():
            shutil.rmtree(folder / "strip")
        (folder / "strip").mkdir(parents=True)
        partial = folder / "showinfo.partial"
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "4", "-copyts", "-ss", f"{t0_video - 2:.3f}",
               "-i", video, "-an", "-vf", f"trim=start={t0_video:.3f}:end={t1_video:.3f},crop=2560:260:0:{STRIP_Y0},"
               "showinfo", "-fps_mode", "passthrough", "-enc_time_base:v", "demux", "-q:v", "2",
               str(folder / "strip" / "%05d.jpg")]
        with partial.open("w", encoding="utf-8") as fh:
            run = subprocess.run(cmd, stderr=fh, stdout=subprocess.DEVNULL)
        if run.returncode != 0:
            raise RuntimeError(f"ffmpeg failed for {session}: see {partial}")
        partial.replace(log)
    return [round(float(m.group(1)) * 1000) for m in
            re.finditer(r"n:\s*\d+\s+pts:\s*\d+\s+pts_time:([0-9.]+)", log.read_text(encoding="utf-8"))]


def presses(session, start, t0, t1):
    out = []
    for line in (RAW / session / "inputs.jsonl").open(encoding="utf-8"):
        e = json.loads(line)
        t = (e["t_ns"] - start) / 1e9
        if not t0 - MATCH_BEFORE_S <= t <= t1:
            continue
        if e["type"] == "key" and e.get("down") and e["vk"] in KEYS:
            out.append((t, KEYS[e["vk"]]))
        elif e["type"] == "mouse" and RMB in (e.get("buttons_down") or []):
            out.append((t, "web_cluster"))
    return sorted(out)


def validate(session, start_s):
    pmap, start_ns, video, how = logger_map(session)
    comps = sorted(pmap.items())
    lo_ns, hi_ns = start_ns + start_s * 1e9, start_ns + (start_s + DURATION_S) * 1e9
    in_window = [ms for ms, c in comps if lo_ns <= c < hi_ns]
    folder, out = names(session, start_s)
    pts = decode(session, video, in_window[0] / 1000 - 0.3, in_window[-1] / 1000 + 0.3, folder)
    strips = sorted((folder / "strip").glob("*.jpg"))
    assert len(pts) == len(strips), (len(pts), len(strips))
    keys = np.array([ms for ms, _ in comps])
    frames, residuals = [], []
    for path, ms in zip(strips, pts):
        j = int(np.argmin(np.abs(keys - ms)))
        residuals.append(abs(float(keys[j]) - ms))
        if residuals[-1] <= 1.0:
            frames.append((path, (comps[j][1] - start_ns) / 1e9))
    how.update(decoded_frames=len(pts), mapped_frames=len(frames), max_residual_ms=round(max(residuals), 3))
    rows = []
    for path, t in frames:
        strip = cv2.imread(str(path))
        full = np.zeros((1440, 2560, 3), np.uint8)
        full[STRIP_Y0:STRIP_Y0 + strip.shape[0]] = strip
        rows += rh.read_frame(full, t, rh.JAMES_ORDER, source="first_person")
    t0, t1 = frames[0][1], frames[-1][1]
    events, coverage, flags = rh.cast_events(rows, cooldowns={"teamup": rh.TEAMUP_S["james_051828"]},
                                             min_run=MIN_RUN)
    press = presses(session, start_ns, t0, t1)
    used, matched = set(), []
    for e in events:
        seen = e.first_seen if e.first_seen is not None else e.t_hi
        # a countdown gives the cooldown's start, and the press cannot come after it (a second press during the
        # cooldown did not cast); otherwise the press precedes the first read showing the cast
        latest = min(seen, e.t_hi + COUNTDOWN_PRESS_TOL_S) if e.basis == "countdown" else seen
        cands = [(i, t) for i, (t, a) in enumerate(press) if a == e.ability and i not in used
                 and seen - MATCH_BEFORE_S <= t <= latest]
        row = {"ability": e.ability, "t_lo": round(e.t_lo, 4), "t_hi": round(e.t_hi, 4), "first_seen": round(seen, 4),
               "basis": e.basis, "count": e.count, "press_t": None,
               # cast before the window: its press is outside the log span read here, so it is not scored
               "edge": e.t_hi < t0 + EDGE_S}
        if cands:
            for i, _ in cands[-e.count:]:          # a count-k drop consumes up to k presses
                used.add(i)
            i, t = cands[-1]
            row.update(press_t=round(t, 4), lag_first_seen_s=round(seen - t, 4),
                       lag_interval_s=[round(e.t_lo - t, 4), round(e.t_hi - t, 4)])
        matched.append(row)
    unmatched = [{"t": round(t, 4), "ability": a} for i, (t, a) in enumerate(press) if i not in used and t0 <= t <= t1]
    doc = {"session": session, "window_logger_s": [round(t0, 4), round(t1, 4)], "video": video, "time_map": how,
           "frames": len(frames), "min_run": MIN_RUN, "match_before_s": MATCH_BEFORE_S, "flags": flags,
           "events": matched, "unmatched_presses": unmatched,
           "coverage_s": {k: round(sum(b - a for a, b in v), 3) for k, v in coverage.items()}}
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return out, doc


def pool():
    per, files = {}, sorted(EVIDENCE.glob("validation-*.json"))

    def slot(a):
        return per.setdefault(a, {"first_seen": [], "cooldown_start": [], "unmatched_events": 0,
                                  "unmatched_presses": 0, "windows": set()})
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        for e in doc["events"]:
            d = slot(e["ability"])
            d["windows"].add(f.name)
            if e.get("edge") or e.get("basis") == "flagged":
                d["excluded_edge_or_flagged"] = d.get("excluded_edge_or_flagged", 0) + 1
                continue
            if e["press_t"] is None:
                d["unmatched_events"] += 1
                continue
            d["first_seen"].append(e["lag_first_seen_s"])
            if e["basis"] == "countdown":
                d["cooldown_start"].append(sum(e["lag_interval_s"]) / 2)
        for u in doc["unmatched_presses"]:
            slot(u["ability"])["unmatched_presses"] += 1

    def spread(v):
        v = sorted(v)
        return {"n": len(v), "min": v[0], "median": v[len(v) // 2], "max": v[-1]} if v else {"n": 0}

    out = {"files": [f.name for f in files], "match_before_s": MATCH_BEFORE_S, "abilities": {
        a: {"first_seen_lag_s": spread(d["first_seen"]), "cooldown_start_lag_s": spread(d["cooldown_start"]),
            "unmatched_events": d["unmatched_events"], "unmatched_presses": d["unmatched_presses"],
            "excluded_edge_or_flagged": d.get("excluded_edge_or_flagged", 0),
            "windows": len(d["windows"])}
        for a, d in sorted(per.items())}}
    (EVIDENCE / "press-lags.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", action="append", help="SESSION:START (logger seconds); default: the four windows")
    ap.add_argument("--pool", action="store_true", help="only pool the validation files already written")
    a = ap.parse_args(argv)
    from replay_hud_full import Paused, lower_priority
    if not lower_priority():
        print("REFUSED: cannot lower this process to below-normal priority")
        return 2
    if not a.pool:
        for w in a.window or DEFAULT_WINDOWS:
            session, start = w.split(":")
            try:
                out, doc = validate(session, float(start))
            except Paused as e:
                print(f"PAUSED at {w}: {e}")
                return 3
            print(out.name, doc["time_map"], "events", len(doc["events"]),
                  "unmatched events", sum(1 for e in doc["events"] if e["press_t"] is None))
    print(json.dumps(pool(), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
