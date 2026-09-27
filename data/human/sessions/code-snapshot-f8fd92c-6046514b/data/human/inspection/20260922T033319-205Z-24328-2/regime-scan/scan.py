"""Read-only resource-regime scan of one finalized recording's ORIGINAL video.

Decodes every `--every`-th presentation frame on the CPU (ffmpeg, 4 decoder threads,
1 filter thread, below-normal priority), runs the repo's HUD readers on the full
native 2560x1440 frame in `--workers` single-threaded below-normal processes and writes one JSON row per sample. Readers return values or
None; nothing here fills an unknown. No game input, labels, admission or source edits.

    UV_PROJECT_ENVIRONMENT=<scratch venv> uv run --group perception python scan.py \
        --video V --session S --scratch DIR [--ss SEC --t SEC] [--mapping JSON]

Frame identity comes from the decoded PTS (file milliseconds, time base 1/1000),
matched exactly to the recorder's callback rows via round(pts_1_120 * 1000/120) + 21,
the independently accepted +21/1000 s anchor for this original only.
"""
import argparse
import collections
import csv
import ctypes
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from perception import hud  # noqa: E402

W, H = 2560, 1440
# Slot positions are named by the key label the HUD draws under them, never by a
# guessed ability: the default MK slot keys are positional only.
POSITIONS = {"C": "teamup", "LSHIFT": "swing", "E": "get_over_here", "F": "uppercut"}
AMMO_CROP = (520, 1285, 720, 1385)      # x0, y0, x1, y1 native px: melee inf + web count
ABILITY_CROP = (1860, 1200, 2500, 1395)  # badges, icons/countdowns, key labels, ult


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def below_normal():
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def callback_index(session):
    """file ms -> (presentation frame index, composition_ns, pts in 1/120)."""
    with open(Path(session) / "frames.csv") as f:
        rows = list(csv.DictReader(f))
    by_ms = {}
    for r in rows:
        ms = round(int(r["pts"]) * 1000 / 120) + 21
        assert ms not in by_ms, ms
        by_ms[ms] = (int(r["composition_ns"]), int(r["pts"]))
    order = sorted(by_ms)
    return {ms: (i, *by_ms[ms]) for i, ms in enumerate(order)}, int(rows[0]["composition_ns"])


def source_layout(mapping):
    """The source-owned mapped MK layout, exactly as the 032454 packet built it."""
    return replace(hud.MK, slot_cx={ability: hud.MK.slot_cx[pos] for pos, ability in mapping.items()})


def read_sample(frame, layout, mapping):
    reading = hud.read(frame, layout)
    positions = {}
    for key, pos in POSITIONS.items():
        cx = hud.MK.slot_cx[pos]
        ability = mapping.get(pos)
        if ability and reading.abilities:
            charges, countdown = reading.abilities[ability][1], reading.cooldowns[ability]
        elif ability:            # hud.read found no hp/bar and read nothing else either
            charges = countdown = None
        else:                    # a position the source mapping left unnamed (C)
            charges, countdown = hud.read_charges(frame, cx, hud.MK), hud.read_cooldown(frame, pos, hud.MK)
        positions[key] = dict(glyph=hud.identify_slot(frame, cx), charges=charges, countdown=countdown)
    centre = cv2.cvtColor(frame[360:1080, 640:1920], cv2.COLOR_BGR2GRAY)
    return dict(
        hud_present=reading.hp is not None or bool(reading.bar_fill),
        hp=reading.hp, max_hp=reading.max_hp, bar_fill=reading.bar_fill,
        webs=reading.webs, ult_ready=reading.ult_ready, ult_charge=reading.ult_charge,
        mapped_abilities={k: list(v) for k, v in reading.abilities.items()},
        mapped_cooldowns=reading.cooldowns,
        positions=positions,
        # crude scene statistics for locating menus/loading; never a regime reading
        centre_mean=float(centre.mean()), centre_std=float(centre.std()),
    )


_WORKER = {}


def _init(scratch, mapping):
    below_normal()
    cv2.setNumThreads(1)
    _WORKER.update(scratch=Path(scratch), mapping=mapping, layout=source_layout(mapping))


def _work(row, buf):
    frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    row.update(read_sample(frame, _WORKER["layout"], _WORKER["mapping"]))
    scratch, name = _WORKER["scratch"], f"{row['frame_index']:05d}.jpg"
    cv2.imwrite(str(scratch / "thumb" / name), cv2.resize(frame, (256, 144), interpolation=cv2.INTER_AREA),
                [cv2.IMWRITE_JPEG_QUALITY, 80])
    a = frame[AMMO_CROP[1]:AMMO_CROP[3], AMMO_CROP[0]:AMMO_CROP[2]]
    b = frame[ABILITY_CROP[1]:ABILITY_CROP[3], ABILITY_CROP[0]:ABILITY_CROP[2]]
    strip = np.zeros((b.shape[0], a.shape[1] + 10 + b.shape[1], 3), np.uint8)
    strip[:a.shape[0], :a.shape[1]] = a
    strip[:, a.shape[1] + 10:] = b
    cv2.imwrite(str(scratch / "hud" / name), strip, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--scratch", required=True, help="per-sample JPEGs and samples.jsonl")
    ap.add_argument("--every", type=int, default=24, help="120 fps / 24 = 5 samples per second")
    ap.add_argument("--ss", type=float)
    ap.add_argument("--t", type=float)
    ap.add_argument("--mapping", help="JSON {position key: ability}; omit to compute and print it")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    below_normal()
    cv2.setNumThreads(2)
    index, t0 = callback_index(args.session)
    scratch = Path(args.scratch)
    (scratch / "thumb").mkdir(parents=True, exist_ok=True)
    (scratch / "hud").mkdir(parents=True, exist_ok=True)

    # -copyts keeps the file's own PTS (first video frame 21 ms), never re-zeroed
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info", "-copyts", "-threads", "4"]
    if args.ss is not None:
        cmd += ["-ss", str(args.ss)]
    if args.t is not None:   # input-side duration: with -copyts an output -t would be absolute
        cmd += ["-t", str(args.t)]
    cmd += ["-i", args.video]
    cmd += ["-an", "-sn", "-dn", "-filter_threads", "1",
            "-vf", f"select='not(mod(n\\,{args.every}))',showinfo",
            "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                            creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    infos = queue.Queue()
    log = []

    def pump():
        pat = re.compile(r"showinfo.*\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:(-?[\d.]+)")
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            m = pat.search(line)
            if m:
                infos.put((int(m.group(1)), int(m.group(2)), float(m.group(3))))
            elif "showinfo" not in line:
                log.append(line)
        infos.put(None)

    threading.Thread(target=pump, daemon=True).start()
    mapping = json.loads(args.mapping) if args.mapping else None
    votes = []
    out = open(scratch / "samples.jsonl", "w")
    size = W * H * 3
    n = 0
    pool = ProcessPoolExecutor(args.workers, initializer=_init, initargs=(str(scratch), mapping)) if mapping else None
    pending = collections.deque()

    def drain(limit):
        while len(pending) > limit:
            out.write(json.dumps(pending.popleft().result()) + "\n")

    while True:
        # Windows pipes deliver small chunks; fill one preallocated buffer in place.
        buf, got = bytearray(size), 0
        view = memoryview(buf)
        while got < size:
            k = proc.stdout.readinto(view[got:])
            if not k:
                break
            got += k
        if got == 0:
            break
        assert got == size, "short frame"
        buf = bytes(buf)
        info = infos.get(timeout=120)
        assert info is not None and info[0] == n, (info, n)
        pts_ms = info[1]
        frame_index, comp_ns, pts120 = index[pts_ms]
        row = dict(sample=n, file_pts_ms=pts_ms, file_s=pts_ms / 1000, frame_index=frame_index,
                   composition_ns=comp_ns, composition_s=(comp_ns - t0) / 1e9)
        if mapping is None:
            votes.append(np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy())
            out.write(json.dumps(row) + "\n")
        else:
            pending.append(pool.submit(_work, row, buf))
            drain(2 * args.workers)   # bounded: never more than 2x workers frames in flight
        n += 1
        if n % 100 == 0:
            print(f"{n} samples, file {pts_ms / 1000:.2f}s", flush=True)
    drain(0)
    if pool:
        pool.shutdown()
    out.close()
    rc = proc.wait()
    print("ffmpeg exit", rc, "samples", n)
    (scratch / "ffmpeg-log.txt").write_text("\n".join(log) + "\n")
    if mapping is None:
        # the existing voting rule, on this source's own frames (as the 032454 packet did)
        print("MAPPING", json.dumps(hud.slot_mapping(votes, hud.MK)))
        print("PER-FRAME", json.dumps([{k: hud.identify_slot(f, hud.MK.slot_cx[p]) for k, p in POSITIONS.items()}
                                       for f in votes]))
    assert rc == 0


if __name__ == "__main__":
    main()
