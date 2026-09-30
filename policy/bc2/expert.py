"""bc2 features from IDM-labelled expert footage (a REPLAY step table per video, from the idm lane).

Two stages, so the slow part needs no GPU:
  views     CPU: decode each row's frame (software, matched by pts) and area-downscale it straight to the cache's
            two views: global 144x256 = the whole frame, crop 128x128 = the centre square of width*256/2560 (the
            same field of view as the 256 px crop at 2560x1440). -> <out>/<session>/{global.u8, crop.u8, views.json}
  features  GPU: frozen tower, grayscale motion frames, green profile and targets from those views, in the layout of
            `features.extract` (feats.npy, gray_g.npy, gray_c.npy, green.npy, targets.npz, meta.json).
Targets come from steps.target's replay path: unknown channels stay masked; camera degrees are the IDM's, on James's
scale (the expert's FOV and sensitivity are uncalibrated).

    python -m policy.bc2.expert views <labels.steps.jsonl> [...] --out D:/rivals-policy/expert-views --jobs 6
    python -m policy.bc2.expert features <labels.steps.jsonl> [...] --views D:/rivals-policy/expert-views \
        --out D:/rivals-policy/expert-features
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np

GLOBAL, CROP = (144, 256, 3), (128, 128, 3)


def load_labels(path):
    """steps.load without the exact-stride sequence check: expert anchors are decoded 60 fps frames, two per step,
    so consecutive anchors differ by the frames' pts (about 33.0-33.4 ms), not exactly step_ns."""
    from policy.range_bc import steps
    path = Path(path)
    with path.open(encoding="utf-8") as stream:
        header = json.loads(stream.readline())
        steps.check_header(header)
        rows = [json.loads(line) for line in stream if line.strip()]
    for k, r in enumerate(rows):
        steps.check_row(r, header, k)
    return steps.Session(str(path), steps.sha256(path), header, rows)


def decode_rows(video, rows, threads=4):
    """Yield (row index, BGR ndarray) for each row's frame, matched by pts, one seek per run."""
    import av
    runs = {}
    for k, r in enumerate(rows):
        runs.setdefault(r["run"], []).append(k)
    with av.open(video) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        stream.codec_context.thread_count = threads
        for ks in runs.values():
            want = {rows[k]["frame"]["pts"]: k for k in ks}
            first, last = min(want), max(want)
            container.seek(first, stream=stream, backward=True)
            for frame in container.decode(stream):
                if frame.pts is None or frame.pts < first:
                    continue
                if frame.pts > last:
                    break
                k = want.pop(frame.pts, None)
                if k is not None:
                    yield k, frame.to_ndarray(format="bgr24")
            if want:
                raise ValueError(f"{len(want)} row frames not found in {video} (run {rows[ks[0]]['run']})")


def views_of(bgr):
    """(global RGB 144x256, crop RGB 128x128) uint8 by direct area downscaling of a frame of any size."""
    import cv2
    h, w = bgr.shape[:2]
    g = cv2.resize(bgr, (GLOBAL[1], GLOBAL[0]), interpolation=cv2.INTER_AREA)
    side = round(256 * w / 2560)
    y0, x0 = (h - side) // 2, (w - side) // 2
    c = cv2.resize(bgr[y0:y0 + side, x0:x0 + side], (CROP[1], CROP[0]), interpolation=cv2.INTER_AREA)
    return g[..., ::-1], c[..., ::-1]


class NpyRows:
    """Row-range reads/writes of a .npy file through plain file IO, not a memmap: pages touched through a memmap
    stay in the process working set, which broke the PC's per-process memory cap. With dtype and shape, creates
    the file (header plus sized body); otherwise opens an existing one read-only."""

    def __init__(self, path, dtype=None, shape=None):
        if dtype is not None:
            m = np.lib.format.open_memmap(path, "w+", dtype, shape)
            mode = "r+b"
        else:
            m = np.load(path, mmap_mode="r")
            mode = "rb"
        self.offset, self.dtype, self.shape = m.offset, m.dtype, m.shape
        self.row = int(np.prod(self.shape[1:])) * self.dtype.itemsize
        del m
        self.file = open(path, mode)

    def read(self, start, count):
        count = max(0, min(count, self.shape[0] - start))
        self.file.seek(self.offset + start * self.row)
        return np.frombuffer(self.file.read(count * self.row), self.dtype).reshape(count, *self.shape[1:]).copy()

    def write(self, start, rows):
        self.file.seek(self.offset + start * self.row)
        self.file.write(np.ascontiguousarray(rows, self.dtype).tobytes())

    def close(self):
        self.file.close()


def views(labels, out_root, *, log=print):
    import cv2
    cv2.setNumThreads(1)
    session = load_labels(labels)
    rows, n = session.rows, len(session.rows)
    out = Path(out_root) / session.session_id
    out.mkdir(parents=True, exist_ok=True)
    # Positioned writes into .npy files, not memmaps: a written memmap stays in the process working set, which
    # broke the PC's per-process memory cap on long shards.
    files = []
    for name, shape in (("global.npy", GLOBAL), ("crop.npy", CROP)):
        m = np.lib.format.open_memmap(out / name, "w+", np.uint8, (n, *shape))
        offset, size = m.offset, int(np.prod(shape))
        del m
        files.append(((out / name).open("r+b"), offset, size))
    started, done = time.monotonic(), 0
    try:
        for k, bgr in decode_rows(rows[0]["frame"]["video_path"], rows):
            for (f, offset, size), view in zip(files, views_of(bgr)):
                f.seek(offset + k * size)
                f.write(np.ascontiguousarray(view).tobytes())
            done += 1
            if done % 5000 == 0:
                log(f"{session.session_id}: {done}/{n} rows, {time.monotonic() - started:.0f} s")
    finally:
        for f, _, _ in files:
            f.close()
    meta = {"session": session.session_id, "steps_sha256": session.sha256, "rows": n, "decoded": done,
            "seconds": time.monotonic() - started, "labels": str(labels)}
    (out / "views.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(json.dumps(meta))
    return meta


def features(labels, views_root, out_root, tower, *, device="cuda", batch=256, log=print):
    import torch
    from policy.bc2 import data
    from policy.bc2.features import tower_features
    from policy.bc2.model import FEAT, GREEN_DIM, gray_small, green_profile
    session = load_labels(labels)
    n = len(session.rows)
    src = Path(views_root) / session.session_id
    vmeta = json.loads((src / "views.json").read_text())
    if vmeta["steps_sha256"] != session.sha256 or vmeta["decoded"] != n:
        raise ValueError(f"{src}: views do not match these labels")
    g_in, c_in = NpyRows(src / "global.npy"), NpyRows(src / "crop.npy")
    out = Path(out_root) / session.session_id
    out.mkdir(parents=True, exist_ok=True)
    outs = {"feats": NpyRows(out / "feats.npy", np.float16, (n, 2, FEAT)),
            "gray_g": NpyRows(out / "gray_g.npy", np.uint8, (n, 72, 128)),
            "gray_c": NpyRows(out / "gray_c.npy", np.uint8, (n, 64, 64)),
            "green": NpyRows(out / "green.npy", np.float16, (n, GREEN_DIM))}
    started = time.monotonic()
    try:
        with torch.no_grad():
            for s in range(0, n, batch):
                g = torch.from_numpy(g_in.read(s, batch)).to(device)
                c = torch.from_numpy(c_in.read(s, batch)).to(device)
                f = tower_features(tower, [g, c])
                m = len(g)
                outs["feats"].write(s, torch.stack((f[:m], f[m:]), 1).cpu().numpy())
                outs["gray_g"].write(s, gray_small(g).cpu().numpy())
                outs["gray_c"].write(s, gray_small(c).cpu().numpy())
                outs["green"].write(s, green_profile(g).cpu().numpy().astype(np.float16))
    finally:
        for a in (g_in, c_in, *outs.values()):
            a.close()
    np.savez(out / "targets.npz", **data.session_arrays(session, list(range(n))))
    meta = {"session": session.session_id, "split": session.split, "source_kind": "replay",
            "steps_sha256": session.sha256, "steps": n, "runs": len({r["run"] for r in session.rows}),
            "seconds": time.monotonic() - started, "labels": str(labels), "calibration": session.header["calibration"],
            "expert_context": session.header.get("expert_context")}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(json.dumps(meta))
    return meta


def shard(labels, out_dir, rows_per_shard=30000):
    """Split one video's label file into ~rows_per_shard sessions by run (whole runs only), for parallel views.
    Each shard is its own session (steps.check_header wants session_group == session_id); the source video
    stays in `source_video_group`, which is the unit for any expert hold-out."""
    import zlib
    labels = Path(labels)
    with labels.open(encoding="utf-8") as stream:
        header = json.loads(stream.readline())
        rows = [json.loads(line) for line in stream if line.strip()]
    n = max(1, round(len(rows) / rows_per_shard))
    parts = [[] for _ in range(n)]
    for r in rows:
        parts[zlib.crc32(r["run"].encode()) % n].append(r)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, part in enumerate(parts):
        if not part:
            continue
        h = dict(header, session_id=f"{header['session_id']}-s{i}", source_video_group=header["session_id"])
        h["session_group"] = h["session_id"]
        path = out_dir / f"{h['session_id']}.steps.jsonl"
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(h) + "\n")
            for k, r in enumerate(part):
                f.write(json.dumps(dict(r, i=k)) + "\n")
        paths.append(str(path))
    return paths


def _jpeg_params():
    import cv2
    return [cv2.IMWRITE_JPEG_QUALITY, 98, cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444]


def pack(views_dir, *, batch=2000):
    """<name>.jpgs (concatenated JPEGs) and <name>.idx.npy (int64 offsets, n + 1) for global and crop, so a
    shard's views cross the ~5-10 MB/s PC-to-Mac link 3.3x faster. unpack() restores the .npy views."""
    import cv2
    views_dir = Path(views_dir)
    params = _jpeg_params()
    for name in ("global", "crop"):
        rows = NpyRows(views_dir / f"{name}.npy")
        offsets = [0]
        with (views_dir / f"{name}.jpgs").open("wb") as out:
            for s in range(0, rows.shape[0], batch):
                for x in rows.read(s, batch):
                    ok, buf = cv2.imencode(".jpg", x[..., ::-1], params)
                    if not ok:
                        raise ValueError("jpeg encode failed")
                    out.write(buf.tobytes())
                    offsets.append(offsets[-1] + len(buf))
        rows.close()
        np.save(views_dir / f"{name}.idx.npy", np.array(offsets, np.int64))


def unpack(views_dir, *, batch=2000):
    import cv2
    views_dir = Path(views_dir)
    for name, shape in (("global", GLOBAL), ("crop", CROP)):
        offsets = np.load(views_dir / f"{name}.idx.npy")
        n = len(offsets) - 1
        out = NpyRows(views_dir / f"{name}.npy", np.uint8, (n, *shape))
        with (views_dir / f"{name}.jpgs").open("rb") as src:
            for s in range(0, n, batch):
                e = min(n, s + batch)
                src.seek(int(offsets[s]))
                blob = src.read(int(offsets[e] - offsets[s]))
                rows = [cv2.imdecode(np.frombuffer(blob[offsets[k] - offsets[s]:offsets[k + 1] - offsets[s]], np.uint8),
                                     cv2.IMREAD_COLOR)[..., ::-1] for k in range(s, e)]
                out.write(s, np.stack(rows))
        out.close()


def free_ram_gb():
    """Available physical memory (Windows GlobalMemoryStatusEx; elsewhere /proc/meminfo)."""
    import ctypes
    import sys
    if sys.platform != "win32":
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 2 ** 20
    class Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = Status(dwLength=ctypes.sizeof(Status))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullAvailPhys / 2 ** 30


def pipeline(labels, views_root, features_root, *, floor_gb=6., poll=60, log=print, features=True):
    """Shared-PC supervisor: at most one views worker and one feature process; every `poll` seconds, if free RAM
    is under floor_gb or the game is running, stop both (a stopped session simply reruns later). Returns when
    every session has features."""
    import subprocess
    import sys
    base = [sys.executable, "-m", "policy.bc2.expert"]
    sid = lambda p: json.loads(open(p, encoding="utf-8").readline())["session_id"]
    ids = {p: sid(p) for p in labels}
    views_done = lambda p: (Path(views_root) / ids[p] / "views.json").exists()
    feats_done = lambda p: (Path(features_root) / ids[p] / "meta.json").exists()
    running = {}

    def stop(reason):
        for name, proc in running.items():
            if proc.poll() is None:
                if sys.platform == "win32":           # the whole tree, not just the parent
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.kill()
                proc.wait()
                log(f"stopped {name}: {reason}")
        running.clear()

    finished = (lambda p: feats_done(p)) if features else (lambda p: views_done(p))
    while not all(finished(p) for p in labels):
        for name in [k for k, proc in running.items() if proc.poll() is not None]:
            log(f"{name} exited {running.pop(name).returncode}")
        free = free_ram_gb()
        if game_running() or free < floor_gb:
            stop("game running" if game_running() else f"free RAM {free:.1f} GB < {floor_gb} GB")
            time.sleep(poll)
            continue
        pending_views = [p for p in labels if not views_done(p)]
        if "views" not in running and pending_views:
            running["views"] = subprocess.Popen(base + ["views", pending_views[0], "--out", str(views_root),
                                                        "--jobs", "1"])
            log(f"views {ids[pending_views[0]]} (free {free:.1f} GB)")
        ready = [p for p in labels if views_done(p) and not feats_done(p)]
        if features and "features" not in running and ready:
            running["features"] = subprocess.Popen(base + ["features", *ready, "--views", str(views_root),
                                                           "--out", str(features_root)])
            log(f"features for {len(ready)} sessions (free {free:.1f} GB)")
        time.sleep(poll)
    stop("done")
    log("pipeline complete")


def game_running():
    import subprocess
    import sys
    if sys.platform != "win32":
        return False            # the game only runs on the PC
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Marvel-Win64-Shipping.exe", "/NH"], capture_output=True,
                         text=True).stdout
    return "Marvel-Win64-Shipping" in out


def _views_job(args):
    labels, out = args
    sid = json.loads(open(labels, encoding="utf-8").readline())["session_id"]
    if (Path(out) / sid / "views.json").exists():
        return sid, "done before"
    if game_running():
        return sid, "skipped: game running"
    return sid, views(labels, out, log=lambda m: print(m, flush=True))["seconds"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("shard", "views", "features", "pipeline", "pack", "unpack"))
    p.add_argument("--features-out", help="features root (pipeline stage)")
    p.add_argument("--floor-gb", type=float, default=6.)
    p.add_argument("--views-only", action="store_true", help="pipeline: views here, features elsewhere")
    p.add_argument("--device", default="cuda", help="features: cuda or mps")
    p.add_argument("labels", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--views", help="views root (features stage)")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--vision", default="D:/rivals-policy/bundles/ng-nohist-s1/vision.safetensors")
    p.add_argument("--vision-config", default="D:/rivals-policy/bundles/ng-nohist-s1/siglip2-large-config.json")
    a = p.parse_args(argv)
    if a.stage == "pipeline":
        pipeline(a.labels, a.out, a.features_out, floor_gb=a.floor_gb, features=not a.views_only,
                 log=lambda m: print(time.strftime("%H:%M:%S"), m, flush=True))
        return 0
    if a.stage in ("pack", "unpack"):
        for d in a.labels:                 # here: view directories
            (pack if a.stage == "pack" else unpack)(d)
            print(a.stage, d, flush=True)
        return 0
    if a.stage == "shard":
        for labels in a.labels:
            for path in shard(labels, a.out):
                print(path)
        return 0
    if a.stage == "views" and a.jobs == 1:      # inline: no pool worker to outlive a killed parent
        for x in a.labels:
            print(_views_job((x, a.out)), flush=True)
        return 0
    if a.stage == "views":
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.jobs) as pool:
            for result in pool.map(_views_job, [(x, a.out) for x in a.labels]):
                print(result, flush=True)
        return 0
    if game_running():
        raise SystemExit("the game is running; the PC GPU belongs to it")
    import torch
    from policy.bc2.features import load_tower
    torch.set_num_threads(2)
    tower = load_tower(a.vision, a.vision_config, a.device)
    for labels in a.labels:
        sid = json.loads(open(labels, encoding="utf-8").readline())["session_id"]
        if (Path(a.out) / sid / "meta.json").exists() or not (Path(a.views) / sid / "views.json").exists():
            continue                       # done, or its views are not finished yet
        if game_running():
            raise SystemExit("the game started; stopping between videos")
        features(labels, a.views, a.out, tower, device=a.device, log=lambda m: print(m, flush=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
