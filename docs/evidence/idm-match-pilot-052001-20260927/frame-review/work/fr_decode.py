"""frame-review's own native-frame decoder for the match-mode pilot 20260927T052001-827Z-150600-5.

    python fr_decode.py TARGETS.json OUT_DIR

TARGETS.json: [{"key": str, "file_ms": int, "frame_index": int, "composition_ns": int}, ...]
Independent of intake's _decode: coarse input seek, pts-select, and `showinfo` after the select so every emitted
frame's PTS is proved equal to the wanted file_ms. frame_index -> composition_ns is re-derived from the logger's
frames.csv (by pts). Each frame: sha256 of raw BGR24 2560x1440, the snapshot's match_timer read, and a
1280x720 JPEG for visual inspection. One window per call of ffmpeg, frames streamed one at a time (~11 MB each).
Refuses to start a window while obs64 or Marvel* runs.
"""
import csv
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

SID = "20260927T052001-827Z-150600-5"
VIDEO = "C:/Users/volpe/Videos/2026-09-27 00-20-01.mkv"
FRAMES_CSV = f"C:/Users/volpe/Videos/RivalsInput/{SID}/frames.csv"
SESS = Path(f"C:/Users/volpe/repos/rivals-agent/data/human/sessions/{SID}")
SNAP = Path("C:/Users/volpe/repos/rivals-agent/data/human/sessions/code-snapshot-f8fd92c")
W, H = 2560, 1440
SIZE = W * H * 3
BELOW = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)


def game_or_obs_running():
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout.lower()
    return [n for n in ("obs64", "marvel") if n in out]


def load_reader():
    """The snapshot's scan.py reader (secondary machine read; the verdict is from looking at the frame)."""
    sys.path.insert(0, str(SNAP))
    spec = importlib.util.spec_from_file_location(
        "fr_scan", SNAP / "data/human/inspection/20260922T033319-205Z-24328-2/regime-scan/scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mapping = json.loads((SESS / "slot-mapping.json").read_text())["mapping"]
    layout = mod.source_layout(mapping)
    return lambda img: mod.read_sample(img, layout, mapping)


def comp_by_index():
    """frames.csv video rows (track 0) keyed by presentation index: rank of pts (1/120 s). Rows are in packet order,
    not presentation order (B-frames), so packet_index is not the frame index."""
    rows = []
    with open(FRAMES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r["track"] == "0":
                rows.append((int(r["pts"]), int(r["composition_ns"])))
    rows.sort()
    return {i: c for i, (_, c) in enumerate(rows)}


def windows(ms_list, gap=1100, cap=120):
    ms_list = sorted(set(ms_list))
    out, cur = [], [ms_list[0]]
    for ms in ms_list[1:]:
        if ms - cur[-1] <= gap and len(cur) < cap:
            cur.append(ms)
        else:
            out.append(cur)
            cur = [ms]
    out.append(cur)
    return out


def decode_window(win):
    """Yield (ms, frame) one at a time (one ~11 MB frame alive); stderr is drained on a thread (showinfo writes a
    line per frame). Raises after the last frame unless showinfo's pts list equals `win` exactly."""
    expr = "+".join(f"eq(pts\\,{ms})" for ms in win)
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-copyts", "-threads", "4",
           "-ss", f"{max(0.0, win[0] / 1000 - 0.3):.3f}", "-i", VIDEO, "-an", "-sn", "-dn", "-filter_threads", "1",
           "-vf", f"select='{expr}',showinfo", "-fps_mode", "passthrough", "-frames:v", str(len(win)),
           "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=BELOW)
    chunks = []
    t = threading.Thread(target=lambda: chunks.append(p.stderr.read()), daemon=True)
    t.start()
    n = 0
    for ms in win:
        buf = p.stdout.read(SIZE)
        if len(buf) != SIZE:
            break
        n += 1
        yield ms, np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    p.stdout.close()
    p.wait()
    t.join()
    pts = [int(x) for x in re.findall(r"\bpts:\s*(-?\d+)", b"".join(chunks).decode(errors="replace"))]
    if n != len(win) or pts != win:
        raise SystemExit(f"window {win[0]}..{win[-1]}: got {n} frames, showinfo pts {pts[:5]}..., wanted {win}")


def main():
    targets = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    (out / "img").mkdir(parents=True, exist_ok=True)
    comp = comp_by_index()
    read = load_reader()
    rec_path = out / "frames.jsonl"
    done = set()
    if rec_path.exists():
        done = {json.loads(l)["file_ms"] for l in rec_path.read_text().splitlines() if l.strip()}
    by_ms = {}
    for t in targets:
        by_ms.setdefault(t["file_ms"], []).append(t)
    todo = [ms for ms in by_ms if ms not in done]
    if not todo:
        print("nothing to decode")
        return
    with rec_path.open("a") as rec:
        for win in windows(todo):
            running = game_or_obs_running()
            if running:
                raise SystemExit(f"stop: {running} running")
            pending = []
            for ms, img in decode_window(win):
                digest = hashlib.sha256(img.tobytes()).hexdigest()
                r = read(img)
                name = f"{ms:07d}.jpg"
                cv2.imwrite(str(out / "img" / name), cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA),
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                for t in by_ms[ms]:
                    pending.append(dict(key=t["key"], file_ms=ms, frame_index=t["frame_index"],
                                        composition_ns=t["composition_ns"],
                                        csv_composition_ns=comp.get(t["frame_index"]),
                                        decoded_bgr_sha256=digest,
                                        hp=r.get("hp"), max_hp=r.get("max_hp"), webs=r.get("webs"),
                                        hud_present=bool(r.get("hud_present")),
                                        own_hud=r.get("webs") is not None and (r.get("hp") or 0) > 0,
                                        image=f"img/{name}"))
                del img
            for d in pending:          # written only after the window's pts proof passed
                rec.write(json.dumps(d) + "\n")
            rec.flush()
            print(f"window {win[0]}..{win[-1]} ok ({len(win)} frames)", flush=True)


if __name__ == "__main__":
    main()
