"""Build the IDM frame store (policy.idm.frames, "rivals-idm-frames-v1") for one admitted session from its original.

    uv run --offline --locked --group execution python -m policy.idm.decode build TARGETS.idm.jsonl STEPS.jsonl \
        IMPORTED-DEMO.jsonl OUT_DIR --video-root DIR [--media-relocation F --media-relocation-sha256 S]
    uv run --offline --locked --group execution python -m policy.idm.decode inspect STORE_DIR OUT_DIR [--count 6]

`inspect` writes a few stored frames for a person to look at before the other stores are built: each sampled frame's
motion image, HUD crop and the window's first-to-last difference (128 = no change), as PNG.

Inputs, each pinned before any frame is decoded:
    TARGETS        the session's rivals-idm-targets-v1 file (policy.idm_targets.load: sealed and test refused)
    STEPS          the admitted step table the targets were built from: its sha256 equals the targets header's
                   source.steps.sha256; it names the one video (by base name, resolved under --video-root), its size,
                   timebase and HUD layout, and its anchor frames' pts
    IMPORTED-DEMO  the imported demo the targets were built from (sha256 = source.imported_demo.sha256): its decoded
                   frame table (ordinal -> pts, and the timebase) is the pts of EVERY frame, not only the rows'

The sealed denylist is loaded first (pinned), and a denylisted session id or media hash is refused before any path under
the inputs is decoded. The video's bytes must be the targets' media_sha256, or the transcode a pinned media relocation
names (intake's own check_media, as range_bc's cache).

What is decoded: for every usable row (policy.idm_targets.training_rows), its end frame +- 2k video frames, k in
[-WINDOW, WINDOW] (the model's +-8-interval motion window at 120 fps), and its start and end frames (HUD). Ordinals
outside the video are left out, so those rows abstain. Every decoded frame's showinfo pts must equal the demo's pts for
that ordinal, and every target row's and step table anchor's pts must equal it too; the stream timebase must equal
both. A disagreement refuses the store.

Pixels (range_bc's cache, review K9): YUV -> RGB pinned (tv range, BT.709, full-range RGB, accurate_rnd+bitexact+
full_chroma_int) at native size; the motion frame is area-scaled to 448x252 (area+accurate_rnd+bitexact) and made grey
in numpy with a fixed integer luma, (77 R + 150 G + 29 B + 128) >> 8; the HUD crop is the cache's own M&K crop (the
ability row over the webs box, 80x200x3). swscale output can still differ between CPU architectures, so stores are
built on the Mac only (refused elsewhere; tests pass any_platform=True).

The store is written as frames.u8 and hud.u8 (created exclusively, streamed, hashed as written) and frames.json last,
so an interrupted build leaves no manifest and cannot be opened. The manifest adds the decode provenance to the
frame store's fields: the targets, step table and demo sha256, the video, the graph, ffmpeg and the platform.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from policy import idm_targets as T  # noqa: E402
from policy.idm import frames as FR  # noqa: E402
from policy.range_bc import cache, steps  # noqa: E402

WINDOW = 8                        # intervals either side (policy.idm.model.Config.window)
STEP = 2                          # video frames per 60 Hz interval at 120 fps
FRAME_PERIOD_NS = 8_333_333
MOTION = (252, 448)               # height, width: the F3 minimum width
LUMA = (77, 150, 29)              # integer weights, sum 256
_STACK = (MOTION[0] + FR.HUD_SHAPE[0], MOTION[1], 3)
GRAPH = ("{select},showinfo," + cache.CONVERT + ",split=2[m][h];"
         "[m]scale=%d:%d:flags=area+" + cache.BITEXACT + "[g];"
         "[h]split=2[h1][h2];"
         "[h1]crop=iw*%.6f:ih*%.6f:iw*%.6f:ih*%.6f,scale=200:50:flags=area+" + cache.BITEXACT + "[ab];"
         "[h2]crop=iw*%.6f:ih*%.6f:iw*%.6f:ih*%.6f,scale=40:30:flags=area+" + cache.BITEXACT + ",pad=200:30[wb];"
         "[ab][wb]vstack,pad=%d:80[hd];[g][hd]vstack") % (
    MOTION[1], MOTION[0],
    cache.ABILITY_ROW[2], cache.ABILITY_ROW[3], cache.ABILITY_ROW[0], cache.ABILITY_ROW[1],
    cache.WEBS_BOX_MK[2], cache.WEBS_BOX_MK[3], cache.WEBS_BOX_MK[0], cache.WEBS_BOX_MK[1], MOTION[1])


class DecodeError(ValueError):
    pass


def require(cond, message):
    if not cond:
        raise DecodeError(message)


def grey(rgb):
    """[..., 3] uint8 RGB -> uint8 luma, integer arithmetic only (identical on every machine)."""
    r, g, b = (rgb[..., c].astype(np.uint32) for c in range(3))
    return ((LUMA[0] * r + LUMA[1] * g + LUMA[2] * b + 128) >> 8).astype(np.uint8)


def needed_frames(targets, n_frames):
    """Sorted ordinals the store must hold: each usable row's motion window and its start and end frames."""
    need = set()
    for r in T.training_rows(targets):
        f1 = r["frame1"]["frame_index"]
        need.update(f1 + STEP * k for k in range(-WINDOW, WINDOW + 1))
        need.update((r["frame0"]["frame_index"], f1))
    return sorted(o for o in need if 0 <= o < n_frames)


def read_demo_frames(path, sha256_pin):
    """(timebase [num, den], [pts per decoded ordinal], demo header) from an imported demo's decoded table. The file is
    read once, and its bytes are parsed only after they hash to the targets' pin (a wrong demo, sealed or not, is
    refused unparsed)."""
    data = Path(path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == sha256_pin, "imported demo differs from the one the targets pin")
    first, rest = data.split(b"\n", 1)
    header, payload = json.loads(first), json.loads(rest.split(b"\n", 1)[0])
    decoded = payload["decoded"]
    pts = decoded["pts"]
    require(isinstance(pts, list) and pts and all(isinstance(p, int) for p in pts), "demo has no decoded pts")
    require(all(a < b for a, b in zip(pts, pts[1:])), "demo's decoded pts do not increase")
    return [int(decoded["timebase_num"]), int(decoded["timebase_den"])], pts, header


def check_inputs(targets, session, demo_header, denylist):
    """Every input names the same recording (the pins were checked before each was parsed); sealed refused."""
    h = targets.header
    T.refuse_sealed(targets.session_id, h["media_sha256"], denylist)
    T.refuse_sealed(demo_header.get("session_id") or targets.session_id, demo_header.get("media_sha256"), denylist)
    require(session.session_id == targets.session_id and session.header["media_sha256"] == h["media_sha256"],
            "step table is another recording")
    require(demo_header.get("media_sha256") == h["media_sha256"], "imported demo is another recording")
    require(h["frame_period_ns"] == FRAME_PERIOD_NS, f"frame period {h['frame_period_ns']} ns; the window assumes "
            "120 fps")
    require(session.header.get("hud_layout") == "mk", "the HUD crop regions are the M&K layout's")
    require(not steps.is_replay(session.header), "a replay source is not an admitted session")


def _decode(path, ordinals, sink, ffmpeg, threads):
    """Stream the selected frames into sink(ordinal_position, motion_rgb, hud_rgb); return (showinfo pts, timebase)."""
    with tempfile.TemporaryDirectory(prefix="rivals-idm-store-") as tmp:
        script = Path(tmp) / "graph.txt"
        script.write_text(GRAPH.format(select=cache.select_expression(ordinals)), encoding="ascii")
        proc = subprocess.Popen([ffmpeg, "-v", "info", "-nostdin", "-threads", str(threads), "-i", str(path),
                                 "-map", "0:v:0", "-filter_script:v", str(script), "-fps_mode", "passthrough",
                                 "-an", "-sn", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err = []
        drain = threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)
        drain.start()
        size = _STACK[0] * _STACK[1] * 3
        count = 0
        while True:
            block = proc.stdout.read(size)
            if not block:
                break
            require(len(block) == size, "truncated frame from ffmpeg")
            if count < len(ordinals):
                img = np.frombuffer(block, dtype=np.uint8).reshape(_STACK)
                sink(count, img[:MOTION[0]], img[MOTION[0]:, :FR.HUD_SHAPE[1]])
            count += 1
        proc.wait()
        drain.join()
        text = err[0].decode(errors="replace") if err else ""
        require(proc.returncode == 0, f"ffmpeg failed on {path}: {text[-2000:]}")
        shown = [int(p) for _, p in cache._SHOWINFO.findall(text)]
        require(count == len(ordinals) == len(shown), f"{path}: selected {len(ordinals)}, decoded {count}, "
                f"showinfo {len(shown)}")
        tb = cache._TIMEBASE.findall(text)
        require(len(tb) == 1, f"{path}: showinfo did not report one input timebase")
        return shown, [int(tb[0][0]), int(tb[0][1])]


def prepare(targets_path, steps_path, demo_path, *, denylist=None):
    """Every check that needs no video: sealed refused, pins, one recording, and the targets' and the step table's
    pts against the demo's frame table. Returns (targets, targets_sha, session, timebase, demo_pts, video_path,
    ordinals). Reads the three inputs only; decodes nothing."""
    denylist = denylist or T.load_denylist()
    targets_sha = T.sha256(targets_path)
    targets = T.load(targets_path, denylist=denylist)                  # sealed id / media and test refused here
    require(T.sha256(targets_path) == targets_sha, f"{targets_path} changed while it was loaded")
    src = targets.header["source"]
    require(T.sha256(steps_path) == src["steps"]["sha256"], "step table differs from the one the targets pin")
    session = steps.load(steps_path, denylist=denylist)                  # pinned before it is parsed
    require(session.sha256 == src["steps"]["sha256"], "step table changed while it was loaded")
    timebase, demo_pts, demo_header = read_demo_frames(demo_path, src["imported_demo"]["sha256"])
    check_inputs(targets, session, demo_header, denylist)

    videos = {r["frame"]["video_path"] for r in session.rows}
    require(len(videos) == 1, "one recording is one video: its media_sha256 names one file")
    require({tuple(r["frame"]["timebase"]) for r in session.rows} == {tuple(timebase)},
            "step table timebase differs from the demo's decoded timebase")
    for r in session.rows:                                             # the anchors' pts agree with the demo's table
        f = r["frame"]
        require(0 <= f["frame_index"] < len(demo_pts) and demo_pts[f["frame_index"]] == f["pts"],
                f"step table frame {f['frame_index']} has pts {f['pts']}, the demo's decoded table says otherwise")
    for r in targets.rows:
        for key in ("frame0", "frame1"):
            f = r[key]
            require(0 <= f["frame_index"] < len(demo_pts) and demo_pts[f["frame_index"]] == f["pts"],
                    f"target row {r['i']} {key} {f['frame_index']} has pts {f['pts']}, the demo's table differs")
    ordinals = needed_frames(targets, len(demo_pts))
    require(ordinals, "no frame to decode")
    return targets, targets_sha, session, timebase, demo_pts, videos.pop(), ordinals


def build(targets_path, steps_path, demo_path, out_dir, *, video_root=None, ffmpeg="ffmpeg", ffprobe="ffprobe",
          any_platform=False, relocation=None, denylist=None, threads=4, denylist_source=None):
    """Decode one session's store into out_dir (created; must not exist). Returns the manifest. denylist_source:
    {path, sha256_pin} recorded in the manifest (the CLI's pinned default)."""
    require(any_platform or (platform.system() == "Darwin" and platform.machine() == "arm64"),
            "frame stores are built on the Mac only (swscale output can differ between CPU architectures)")
    targets, targets_sha, session, timebase, demo_pts, video, ordinals = prepare(targets_path, steps_path, demo_path,
                                                                                denylist=denylist)
    path = cache.resolve(relocation["transcoded_path"] if relocation else video, video_root)
    require(path.is_file(), f"video not found: {path}")
    require(cache.probe_size(path, ffprobe) == session.header["video_size"],
            f"{path}: size differs from the step table's video_size")
    colour = cache.probe_colour(path, ffprobe)
    try:
        cache.check_colour(colour)
    except cache.CacheError as e:
        raise DecodeError(str(e)) from None
    before = path.stat()
    media = cache.file_sha256(path)
    try:
        media_kind = cache.check_media(path, session, relocation)
    except cache.CacheError as e:
        raise DecodeError(str(e)) from None

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    hashes = {"frames": hashlib.sha256(), "hud": hashlib.sha256()}
    with (out / "frames.u8").open("xb") as fr, (out / "hud.u8").open("xb") as hd:
        def sink(_, motion_rgb, hud_rgb):
            g = grey(motion_rgb).tobytes()
            c = np.ascontiguousarray(hud_rgb).tobytes()
            fr.write(g)
            hashes["frames"].update(g)
            hd.write(c)
            hashes["hud"].update(c)
        shown, stream_tb = _decode(path, ordinals, sink, ffmpeg, threads)
    after = path.stat()
    require((after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns),
            f"{path} changed while it was hashed and decoded")
    require(stream_tb == timebase, f"{path}: stream timebase {stream_tb} differs from the demo's {timebase}")
    for ordinal, pts in zip(ordinals, shown):
        require(pts == demo_pts[ordinal], f"{path}: ordinal {ordinal} has pts {pts}, the demo's table says "
                f"{demo_pts[ordinal]}: decoded ordinals differ from the importer's")
    src = targets.header["source"]
    manifest = {"format": FR.FORMAT, "session_id": targets.session_id, "media_sha256": targets.header["media_sha256"],
                "width": MOTION[1], "height": MOTION[0], "hud_shape": list(FR.HUD_SHAPE), "frame_indices": ordinals,
                "frame_pts": [demo_pts[o] for o in ordinals],
                "frames_sha256": hashes["frames"].hexdigest(), "hud_sha256": hashes["hud"].hexdigest(),
                "decode": {"targets_sha256": targets_sha, "steps_sha256": src["steps"]["sha256"],
                           "imported_demo_sha256": src["imported_demo"]["sha256"], "timebase": timebase,
                           "window": WINDOW, "step": STEP, "luma": list(LUMA), "graph": GRAPH,
                           "video": {"resolved": str(path), "bytes": path.stat().st_size, "media_sha256": media,
                                     "media_kind": media_kind, "colour": colour},
                           "media_relocation": None if relocation is None else {
                               k: relocation[k] for k in ("identity_sha256", "transcoded_sha256", "transcoded_path",
                                                          "receipt")},
                           "sealed_denylist": denylist_source or {"path": steps.DENYLIST,
                                                                  "sha256_pin": steps.DENYLIST_SHA256,
                                                                  "passed_in": denylist is not None},
                           "ffmpeg": cache.ffmpeg_version(ffmpeg),
                           "platform": f"{platform.system()} {platform.machine()}"}}
    with (out / "frames.json").open("x", encoding="utf-8") as fh:
        json.dump(manifest, fh, sort_keys=True)
    return manifest


def _png(path, array):
    """A PNG of uint8 pixels, grey (H x W) or RGB (H x W x 3), with the standard library only."""
    import struct
    import zlib
    h, w = array.shape[:2]
    rows = np.ascontiguousarray(array).reshape(h, -1)
    raw = b"".join(b"\x00" + rows[y].tobytes() for y in range(h))            # filter type 0 per row

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    colour = 2 if array.ndim == 3 else 0
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, colour, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def inspect(store_dir, out_dir, *, count=6):
    """Sample `count` evenly spaced stored frames whose +-WINDOW window is complete; write <frame>-grey.png,
    <frame>-hud.png and <frame>-diff.png (last minus first window frame, offset to 128). Returns the frames sampled."""
    store = FR.FrameStore(store_dir, verify=True)
    offsets = [STEP * k for k in range(-WINDOW, WINDOW + 1)]
    full = [f for f in store.keys if store.window(f, offsets) is not None]
    require(full, "no stored frame has a complete window")
    picks = [full[round(j * (len(full) - 1) / max(count - 1, 1))] for j in range(count)]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    for f in picks:
        win = store.window(f, offsets).astype(np.int16)
        _png(out / f"{f}-grey.png", np.asarray(store.window(f, [0])[0]))
        _png(out / f"{f}-hud.png", np.asarray(store.hud([f])[0]))
        _png(out / f"{f}-diff.png", np.clip(win[-1] - win[0] + 128, 0, 255).astype(np.uint8))
    return picks


def main(argv=None):
    import argparse
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["inspect"]:
        q = argparse.ArgumentParser(description="Write a few stored frames as images for inspection")
        q.add_argument("store")
        q.add_argument("out")
        q.add_argument("--count", type=int, default=6)
        a = q.parse_args(argv[1:])
        print(json.dumps({"frames": inspect(a.store, a.out, count=a.count)}))
        return 0
    require(argv[:1] == ["build"], "usage: python -m policy.idm.decode build ... | inspect STORE OUT")
    argv = argv[1:]
    p = argparse.ArgumentParser(description="Build the IDM frame store for one admitted session")
    p.add_argument("targets")
    p.add_argument("steps")
    p.add_argument("imported_demo")
    p.add_argument("out")
    p.add_argument("--video-root")
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.add_argument("--ffprobe", default="ffprobe")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--sealed-denylist", default=str(ROOT / steps.DENYLIST), help="intake's denylist (always loaded)")
    p.add_argument("--sealed-denylist-sha256", default=steps.DENYLIST_SHA256)
    p.add_argument("--media-relocation", help="the session's media-relocation.json when its original was transcoded")
    p.add_argument("--media-relocation-sha256", help="its pinned sha256 (required with --media-relocation)")
    a = p.parse_args(argv)
    default = (Path(a.sealed_denylist).resolve() == (ROOT / steps.DENYLIST).resolve()
               and a.sealed_denylist_sha256 == steps.DENYLIST_SHA256)
    require(default, "the store is built with the pinned default sealed denylist only (review: a store's pixels are "
            "decoded to disk before any later check could refuse them)")
    denylist = T.load_denylist(a.sealed_denylist, a.sealed_denylist_sha256)
    relocation = cache.load_relocation(a.media_relocation, a.media_relocation_sha256) if a.media_relocation else None
    m = build(a.targets, a.steps, a.imported_demo, a.out, video_root=a.video_root, ffmpeg=a.ffmpeg,
              ffprobe=a.ffprobe, relocation=relocation, denylist=denylist, threads=a.threads,
              denylist_source={"path": steps.DENYLIST, "sha256_pin": steps.DENYLIST_SHA256, "passed_in": False})
    print(json.dumps({"session_id": m["session_id"], "frames": len(m["frame_indices"]),
                      "frames_sha256": m["frames_sha256"], "hud_sha256": m["hud_sha256"],
                      "ffmpeg": m["decode"]["ffmpeg"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
