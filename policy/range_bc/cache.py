"""Frame cache: each step-table row's frame, decoded once, as raw uint8 files the trainer memory-maps.

Per session directory:
    global.u8   N x 144 x 256 x 3   full frame, area-downscaled
    crop.u8     N x 128 x 128 x 3   native 256x256 at the screen centre, area-downscaled
    hud.u8      N x  80 x 200 x 3   native HUD crops at 1/3: the ability row (608x152 -> 200x50) over the M&K webs
                                    box (120x90 -> 40x30, left-aligned); zero padding elsewhere (lead decision, F5)
    cache.json  manifest: step-table sha256, ffmpeg version, the exact filter graph, per-video ordinal ranges,
                row -> frame positions, sha256 of the data files

Frames are selected by decoded ordinal (`frame_index`, the importer's definition, as `policy.execution.decode_frames`)
in one ffmpeg pass per video, and every selected frame's pts and the stream timebase are checked against the step
table's FrameRef, so a wrong ordinal fails rather than shifting the cache. Stdlib only; numpy is imported lazily by
`open_cache`.

Reproducibility (review K9): the YUV -> RGB conversion is pinned (tv range, BT.709 matrix, to full-range RGB) and
done once at native size with `accurate_rnd+bitexact+full_chroma_int`; every scale uses `area+accurate_rnd+bitexact`.
A video tagged otherwise is refused. swscale output can still differ between CPU architectures, so caches are built on
the Mac only (the builder refuses elsewhere; tests pass `any_platform=True`). The video's bytes must hash to the step
table's `media_sha256`, and the sealed denylist is always loaded by the CLI.
"""
import hashlib
import json
from pathlib import Path, PureWindowsPath
import platform
import re
import subprocess
import tempfile
import threading

from . import steps

FORMAT = "rivals-range-cache-v1"
GLOBAL = (144, 256, 3)
CROP = (128, 128, 3)
HUD = (80, 200, 3)
CROP_NATIVE = 256
# M&K HUD regions as fractions of the frame (perception/hud.py: the ability row x 0.735-0.972, y 0.845-0.95; the MK
# webs box 0.2455-0.2700 x 0.905-0.950, with margin). At 2560x1440: 608x152 at (1880, 1216) and 120x90 at (600, 1280).
ABILITY_ROW = (0.734375, 0.844444, 0.2375, 0.105556)     # x, y, w, h
WEBS_BOX_MK = (0.234375, 0.888889, 0.046875, 0.0625)
_STACK = (GLOBAL[0] + CROP[0] + HUD[0], GLOBAL[1], 3)     # global over a padded crop over the padded HUD
BITEXACT = "accurate_rnd+bitexact"
CONVERT = ("scale=in_range=tv:in_color_matrix=bt709:out_range=pc:flags=accurate_rnd+bitexact+full_chroma_int,"
           "format=rgb24")
GRAPH = ("{select},showinfo," + CONVERT + ",split=3[a][b][h];[a]scale=256:144:flags=area+" + BITEXACT + "[g];"
         "[b]crop=256:256:(iw-256)/2:(ih-256)/2,scale=128:128:flags=area+" + BITEXACT + ",pad=256:128[c];"
         "[h]split=2[h1][h2];"
         "[h1]crop=iw*%.6f:ih*%.6f:iw*%.6f:ih*%.6f,scale=200:50:flags=area+" + BITEXACT + "[ab];"
         "[h2]crop=iw*%.6f:ih*%.6f:iw*%.6f:ih*%.6f,scale=40:30:flags=area+" + BITEXACT + ",pad=200:30[wb];"
         "[ab][wb]vstack,pad=256:80[hd];[g][c][hd]vstack=inputs=3") % (
    ABILITY_ROW[2], ABILITY_ROW[3], ABILITY_ROW[0], ABILITY_ROW[1],
    WEBS_BOX_MK[2], WEBS_BOX_MK[3], WEBS_BOX_MK[0], WEBS_BOX_MK[1])
_SHOWINFO = re.compile(r"Parsed_showinfo\S* @ \S+\] n:\s*(\d+)\s+pts:\s*(-?\d+)")
_TIMEBASE = re.compile(r"Parsed_showinfo\S* @ \S+\] config in time_base: (\d+)/(\d+)")
# Accepted source colour tagging: OBS's yuv420p / nv12, tv range, BT.709 (probed on James's recordings); lossless RGB
# (the test videos) needs no conversion.
YUV_FORMATS = ("yuv420p", "nv12")
RGB_FORMATS = ("bgr0", "rgb24", "bgr24", "rgba", "bgra", "gbrp")


class CacheError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CacheError(message)


def progressions(indices):
    """Sorted unique ints -> [(first, last, step)] arithmetic runs, greedily."""
    out, i = [], 0
    while i < len(indices):
        if i + 1 == len(indices):
            out.append((indices[i], indices[i], 1))
            break
        step = indices[i + 1] - indices[i]
        j = i + 1
        while j + 1 < len(indices) and indices[j + 1] - indices[j] == step:
            j += 1
        out.append((indices[i], indices[j], step))
        i = j + 1
    return out


def select_expression(indices):
    terms = []
    for a, b, step in progressions(indices):
        if a == b:
            terms.append(f"eq(n\\,{a})")
        else:
            terms.append(f"between(n\\,{a}\\,{b})*not(mod(n-{a}\\,{step}))")
    return "select=" + "+".join(terms)


def plan(session):
    """Unique frames in (video, ordinal) order, their expected pts, and each row's position among them."""
    seen = {}
    for r in session.rows:
        f = r["frame"]
        key = (f["video_path"], f["frame_index"])
        if key in seen:
            require(seen[key] == (f["pts"], tuple(f["timebase"])), f"frame {key} has two different pts")
        seen[key] = (f["pts"], tuple(f["timebase"]))
    frames = sorted(seen)
    position = {key: i for i, key in enumerate(frames)}
    rows = [position[(r["frame"]["video_path"], r["frame"]["frame_index"])] for r in session.rows]
    return frames, [seen[k] for k in frames], rows


def probe_colour(path, ffprobe="ffprobe"):
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=pix_fmt,color_range,color_space", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


def check_colour(tags):
    fmt = tags.get("pix_fmt")
    if fmt in RGB_FORMATS:
        return
    require(fmt in YUV_FORMATS and tags.get("color_range") == "tv" and tags.get("color_space") == "bt709",
            f"source colour {tags} differs from the pinned tv-range BT.709 YUV the conversion assumes")


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def resolve(video_path, video_root=None):
    if video_root is None:
        return Path(video_path)
    name = PureWindowsPath(video_path).name if "\\" in video_path else Path(video_path).name
    return Path(video_root) / name


def ffmpeg_version(ffmpeg="ffmpeg"):
    out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout
    return out.splitlines()[0].strip()


def probe_size(path, ffprobe="ffprobe"):
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    w, h = (int(v) for v in out.split(",")[:2])
    return [w, h]


def _decode(path, ordinals, sinks, ffmpeg):
    """Stream the selected frames of one video into the two sinks; return [(n, pts)] from showinfo."""
    with tempfile.TemporaryDirectory(prefix="rivals-range-cache-") as tmp:
        script = Path(tmp) / "graph.txt"
        script.write_text(GRAPH.format(select=select_expression(ordinals)), encoding="ascii")
        proc = subprocess.Popen([ffmpeg, "-v", "info", "-nostdin", "-i", str(path), "-map", "0:v:0",
                                 "-filter_script:v", str(script), "-fps_mode", "passthrough", "-an", "-sn",
                                 "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err = []
        drain = threading.Thread(target=lambda: err.append(proc.stderr.read()), daemon=True)
        drain.start()
        size = _STACK[0] * _STACK[1] * 3
        line = _STACK[1] * 3
        split = GLOBAL[0] * line
        hud_at = split + CROP[0] * line
        count = 0
        while True:
            block = proc.stdout.read(size)
            if not block:
                break
            require(len(block) == size, "truncated frame from ffmpeg")
            sinks[0](block[:split])
            # The padded rows are 256 wide; keep the left pixels of each row.
            sinks[1](b"".join(block[split + y * line: split + y * line + CROP[1] * 3] for y in range(CROP[0])))
            sinks[2](b"".join(block[hud_at + y * line: hud_at + y * line + HUD[1] * 3] for y in range(HUD[0])))
            count += 1
        proc.wait()
        drain.join()
        text = err[0].decode(errors="replace") if err else ""
        require(proc.returncode == 0, f"ffmpeg failed on {path}: {text[-2000:]}")
        shown = [(int(n), int(p)) for n, p in _SHOWINFO.findall(text)]
        require(count == len(ordinals) == len(shown), f"{path}: selected {len(ordinals)}, decoded {count}, "
                f"showinfo {len(shown)}")
        tb = _TIMEBASE.findall(text)
        require(len(tb) == 1, f"{path}: showinfo did not report one input timebase")
        return shown, [int(tb[0][0]), int(tb[0][1])]


def build(session, out_dir, *, video_root=None, ffmpeg="ffmpeg", ffprobe="ffprobe", any_platform=False):
    """Decode every row's frame of one validated session into out_dir (created; must not exist)."""
    require(any_platform or (platform.system() == "Darwin" and platform.machine() == "arm64"),
            "caches are built on the Mac only (swscale output can differ between CPU architectures)")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    frames, expected, row_frame = plan(session)
    by_video = {}
    for i, (video, ordinal) in enumerate(frames):
        by_video.setdefault(video, []).append((ordinal, i))
    names = [resolve(v, video_root).name for v in by_video]
    require(len(set(names)) == len(names), "two different video paths share a file name")
    require(len(by_video) == 1, "one recording is one video: its media_sha256 names one file")
    timebases = {tuple(r["frame"]["timebase"]) for r in session.rows}
    require(session.header["hud_layout"] == "mk", "the HUD crop regions are the M&K layout's")
    hashes = {"global": hashlib.sha256(), "crop": hashlib.sha256(), "hud": hashlib.sha256()}
    videos = []
    with (out / "global.u8").open("xb") as g, (out / "crop.u8").open("xb") as c, (out / "hud.u8").open("xb") as hd:
        def sink(stream, h):
            def write(block):
                stream.write(block)
                h.update(block)
            return write
        sinks = (sink(g, hashes["global"]), sink(c, hashes["crop"]), sink(hd, hashes["hud"]))
        for video, items in by_video.items():
            path = resolve(video, video_root)
            require(path.is_file(), f"video not found: {path}")
            require(probe_size(path, ffprobe) == session.header["video_size"],
                    f"{path}: size differs from the step table's video_size")
            colour = probe_colour(path, ffprobe)
            check_colour(colour)
            media = file_sha256(path)
            require(media == session.header["media_sha256"], f"{path}: bytes differ from the step table's media_sha256")
            ordinals = [o for o, _ in items]
            shown, timebase = _decode(path, ordinals, sinks, ffmpeg)
            require(timebases == {tuple(timebase)}, f"{path}: stream timebase {timebase} differs from the step "
                    f"table's {sorted(timebases)}")
            for (ordinal, i), (_, pts) in zip(items, shown):
                require(pts == expected[i][0], f"{path}: ordinal {ordinal} has pts {pts}, step table says "
                        f"{expected[i][0]}: decoded ordinals differ from the importer's")
            videos.append({"video_path": video, "resolved": str(path), "bytes": path.stat().st_size,
                           "media_sha256": media, "colour": colour, "timebase": timebase,
                           "frames": len(items), "first_ordinal": ordinals[0], "last_ordinal": ordinals[-1]})
    manifest = {"format": FORMAT, "session_id": session.session_id, "steps_sha256": session.sha256,
                "frames": len(frames), "global_shape": list(GLOBAL), "crop_shape": list(CROP),
                "hud_shape": list(HUD), "hud_layout": "mk", "crop_native": CROP_NATIVE, "graph": GRAPH,
                "platform": f"{platform.system()} {platform.machine()}", "ffmpeg": ffmpeg_version(ffmpeg), "videos": videos,
                "row_frame": row_frame, **{f"{k}_sha256": h.hexdigest() for k, h in hashes.items()}}
    with (out / "cache.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, sort_keys=True)
    return manifest


def open_cache(cache_dir, session, *, verify_hashes=False):
    """(global, crop, hud memmaps, row_frame list, manifest), refusing a cache made from another step table."""
    import numpy as np
    d = Path(cache_dir)
    manifest = json.loads((d / "cache.json").read_text(encoding="utf-8"))
    require(manifest.get("format") == FORMAT, "not a range frame cache")
    require(manifest["steps_sha256"] == session.sha256, "cache was built from a different step table")
    require(len(manifest["row_frame"]) == len(session.rows), "cache row count differs from the step table")
    n = manifest["frames"]
    arrays = []
    for name, shape in (("global", GLOBAL), ("crop", CROP), ("hud", HUD)):
        path = d / f"{name}.u8"
        require(path.stat().st_size == n * shape[0] * shape[1] * shape[2], f"{name}.u8 has the wrong size")
        if verify_hashes:
            require(steps.sha256(path) == manifest[f"{name}_sha256"], f"{name}.u8 hash differs from the manifest")
        arrays.append(np.memmap(path, dtype=np.uint8, mode="r", shape=(n, *shape)))
    return arrays[0], arrays[1], arrays[2], manifest["row_frame"], manifest


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Build the frame cache for one step table")
    p.add_argument("steps")
    p.add_argument("out")
    p.add_argument("--video-root")
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.add_argument("--ffprobe", default="ffprobe")
    p.add_argument("--sealed-denylist", default=steps.DENYLIST, help="intake's sealed denylist (always loaded)")
    p.add_argument("--sealed-denylist-sha256", default=steps.DENYLIST_SHA256)
    a = p.parse_args(argv)
    session = steps.load(a.steps, denylist=steps.load_denylist(a.sealed_denylist, a.sealed_denylist_sha256))
    m = build(session, a.out, video_root=a.video_root, ffmpeg=a.ffmpeg, ffprobe=a.ffprobe)
    print(json.dumps({k: m[k] for k in ("session_id", "frames", "global_sha256", "crop_sha256", "hud_sha256",
                                         "ffmpeg")}))


if __name__ == "__main__":
    main()
