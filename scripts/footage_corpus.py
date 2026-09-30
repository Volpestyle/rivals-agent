"""Acquire and screen public expert VODs on external storage; never drives the game.

Metadata, sparse keyframe screening and consumer spans are deliberately separate.
Sparse spans are candidates until a human spot-check is recorded, not exact labels.
Run with uv run python scripts/footage_corpus.py --help.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path("D:/rivals-expert-footage")
SEALED = {"2871472478", "2877719252", "d0C8RMBnFfA", "yjc51uOjKEQ"}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


def source_id(info):
    return str(info["id"]).removeprefix("v") if info.get("extractor_key", "").startswith("Twitch") else info["id"]


def catalogue(root):
    rows = []
    experts = json.loads((root / "experts.json").read_text()) if (root / "experts.json").exists() else {}
    for path in sorted((root / "media").rglob("*.info.json")):
        info = json.loads(path.read_text(encoding="utf-8"))
        sid = source_id(info)
        if sid in SEALED:
            raise ValueError(f"sealed source refused: {sid}")
        media = path.with_name(path.name.replace(".info.json", "." + info.get("ext", "mp4")))
        channel = info.get("uploader_id", info.get("uploader"))
        review_path = root / "reviews" / f"{sid}.json"
        review = json.loads(review_path.read_text()) if review_path.exists() else {}
        if review.get("media_path_override"):
            media = Path(review["media_path_override"])
        complete = media.exists() and not media.with_name(media.stem + ".temp" + media.suffix).exists() \
            and not media.with_suffix(media.suffix + ".part").exists()
        probe = {}
        if complete:
            probe_path = root / "probes" / f"{sid}.json"
            if not probe_path.exists():
                try:
                    answer = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height,avg_frame_rate,start_time,duration", "-of", "json", str(media)],
                                            capture_output=True, text=True, check=True, timeout=30)
                    write_json(probe_path, json.loads(answer.stdout)["streams"][0])
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
                    write_json(probe_path, dict(probe_error=type(error).__name__))
            probe = json.loads(probe_path.read_text())
        rate = probe.get("avg_frame_rate")
        native_fps = (float(rate.split("/")[0]) / float(rate.split("/")[1])) if rate and rate != "0/0" else info.get("fps")
        date = info.get("upload_date")
        season = "Season 10 (estimated from date/title; exact patch unverified)" if date and date >= "20260911" else "unknown"
        rows.append(dict(source_id=sid, url=info.get("webpage_url"), channel=channel,
                         video_id=sid, bitrate_kbps=info.get("tbr"),
                         title=info.get("title"), upload_date=date, estimated_patch_or_season=season,
                         duration_s=float(probe.get("duration", info.get("duration"))),
                         resolution=[probe.get("width", info.get("width")), probe.get("height", info.get("height"))],
                         fps=native_fps, container_video_start_s=probe.get("start_time"),
                         fps_basis="ffprobe" if rate else "provider metadata; native probe pending",
                         timestamp_basis="seconds relative to decoded local video start (container PTS origin excluded)",
                         input_device=review.get("input_device"),
                         input_device_basis=review.get("input_device_basis", "unknown until inspected"),
                         overlay_rects=review.get("overlay_rects"), facecam_rects=review.get("facecam_rects"),
                         rect_coordinates="normalized xyxy; null means unreviewed, [] means reviewed absent",
                         expert_basis=experts.get(channel), media_path=str(media.resolve()),
                         download_complete=complete, review=review))
    # Failed and successful downloader attempts can leave two metadata files.
    # Keep one source row, preferring finalized media, without deleting attempts.
    unique = {}
    for row in rows:
        old = unique.get(row["source_id"])
        if old is None or (row["download_complete"] and not old["download_complete"]):
            unique[row["source_id"]] = row
    rows = [unique[sid] for sid in sorted(unique)]
    jsonl(root / "catalogue.jsonl", rows)
    return rows


def portrait_crop(frame):
    import cv2
    from perception.events import PORTRAIT
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = PORTRAIT
    return cv2.resize(frame[int(y0*h):int(y1*h), int(x0*w):int(x1*w)], (64, 64))


def verdict(frame, portrait_template=None):
    from perception import events, hud, scoreboard, replay_hud
    hp, max_hp = hud.read_hp(frame, hud.MK)
    bar = hud.read_bar_fill(frame)
    if events.is_black(frame) or (hp is None and bar is None):
        return dict(accepted=False, reason="no_hud", hp=hp, max_hp=max_hp)
    if hp == 0:
        return dict(accepted=False, reason="death", hp=hp, max_hp=max_hp)
    banner = events.banner_word(frame)
    if banner:
        return dict(accepted=False, reason=banner, hp=hp, max_hp=max_hp)
    if scoreboard.is_scoreboard(frame) is True:
        return dict(accepted=False, reason="scoreboard", hp=hp, max_hp=max_hp)
    if replay_hud.followed_slot(frame) is not None:
        return dict(accepted=False, reason="replay_roster", hp=hp, max_hp=max_hp)
    if portrait_template is not None:
        import cv2
        score = float(cv2.matchTemplate(portrait_crop(frame), portrait_template, cv2.TM_CCOEFF_NORMED)[0, 0])
        hero = True if score >= .80 else None
    else:
        hero, score = events.hero_read(frame)
    icons = []
    if portrait_template is None and hero is True and score is not None and score < events.PORTRAIT_WEAK:
        # New heroes share the old one-class portrait's weak colour match.
        # A weak match needs independent ability evidence; otherwise unknown.
        hero = None
        icons = [hud.identify_slot(frame, cx) for cx in hud.MK.slot_cx.values()]
        if set(icons) & {"swing", "get_over_here", "uppercut"}:
            hero = True
    elif hero is not True and score is not None:
        icons = [hud.identify_slot(frame, cx) for cx in hud.MK.slot_cx.values()]
        # Two distinct Spider-Man abilities are independent visible evidence,
        # including under skins/colour grading the portrait templates miss.
        if len(set(icons) & {"swing", "get_over_here", "uppercut"}) >= 2:
            hero = True
    alive = (hp > 0) if hp is not None else (bar is not None and bar > 0.01)
    return dict(accepted=hero is True and alive,
                reason="gameplay" if hero is True and alive else "not_our_hero" if hero is False else "unknown",
                hp=hp, max_hp=max_hp, bar=bar, hero=hero, portrait_score=score, icon_evidence=icons)


def spans_from_reads(reads, max_gap=2.5, trim_s=2.0, min_s=8.0, bridge_unknown=0):
    """Never bridge rejects/unknowns or a missing sample; trim both ends inward."""
    reads = [dict(r) for r in reads]
    # Follow events.segment's temporal support for brief unknown reads, but
    # bound it and require positive evidence on both sides. Never bridge a
    # death, menu, foreign hero, replay, scoreboard, or missing sample.
    for i, row in enumerate(reads):
        if row.get("reason") != "unknown" or row["accepted"]:
            continue
        left = i - 1
        while left >= 0 and reads[left].get("reason") == "unknown":
            left -= 1
        right = i + 1
        while right < len(reads) and reads[right].get("reason") == "unknown":
            right += 1
        if (right - left - 1 <= bridge_unknown and left >= 0 and right < len(reads)
                and reads[left]["accepted"] and reads[right]["accepted"]
                and all(reads[k + 1]["t"] - reads[k]["t"] <= max_gap for k in range(left, right))):
            row["accepted"] = True
            row["temporally_supported"] = True
    spans, run = [], []
    def finish():
        if run:
            lo, hi = run[0]["t"] + trim_s, run[-1]["t"] - trim_s
            if hi - lo >= min_s:
                spans.append(dict(start_s=round(lo, 6), end_s=round(hi, 6),
                                  confidence="sparse_hud_candidate", samples=len(run),
                                  weak_samples=sum(r.get("temporally_supported", False) for r in run)))
            run.clear()
    for row in reads:
        if not row["accepted"]:
            finish()
            continue
        if run and row["t"] - run[-1]["t"] > max_gap:
            finish()
        run.append(row)
    finish()
    return spans


def jpeg_frames(stream):
    """Bounded streaming JPEG transport avoids megabytes per Windows pipe write."""
    pending = bytearray()
    while block := stream.read1(65536):
        pending.extend(block)
        while (end := pending.find(b"\xff\xd9")) >= 0:
            frame = bytes(pending[:end + 2])
            del pending[:end + 2]
            if not frame.startswith(b"\xff\xd8"):
                raise ValueError("invalid JPEG frame boundary")
            yield frame
        if len(pending) > 16 * 1024 * 1024:
            raise ValueError("analysis JPEG exceeds bounded transport size")
    if pending:
        raise ValueError("incomplete JPEG frame")


def screen(root, media, sid, duration=None):
    import cv2
    cv2.setNumThreads(1)
    if sid in SEALED:
        raise ValueError("sealed source refused")
    folder = root / "keyframes" / sid
    folder.mkdir(parents=True, exist_ok=True)
    done = folder / "decode.json"
    if not done.exists():
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1",
                   "-skip_frame", "nokey", "-i", str(media)]
        if duration:
            command += ["-t", str(duration)]
        command += ["-an", "-fps_mode", "passthrough", "-enc_time_base", "1:1000",
                    "-frame_pts", "1", "-threads", "1", "-q:v", "3", "-y", str(folder / "%012d.jpg")]
        with (folder / "decode.log").open("w") as log:
            subprocess.run(command, stdout=log, stderr=log, check=True, timeout=3600)
        write_json(done, dict(media=str(media), duration_limit_s=duration))
    reads = []
    read_path = root / "screening" / f"{sid}.jsonl"
    read_path.parent.mkdir(parents=True, exist_ok=True)
    with read_path.open("w", encoding="utf-8") as stream:
        for number, path in enumerate(sorted(folder.glob("*.jpg"))):
            frame = cv2.imread(str(path))
            if frame is None:
                raise ValueError(f"unreadable frame: {path}")
            row = dict(t=int(path.stem) / 1000, frame_path=str(path), **verdict(frame))
            reads.append(row)
            stream.write(json.dumps(row) + "\n")
            if number % 500 == 0:
                stream.flush()
                print(f"{sid}: screened {number} keyframes at {row['t']:.1f}s", flush=True)
    spans = spans_from_reads(reads)
    result = dict(source_id=sid, media_path=str(media.resolve()), spans=spans,
                  gameplay_candidate_s=sum(s["end_s"] - s["start_s"] for s in spans),
                  sampled_until_s=reads[-1]["t"] if reads else 0,
                  sample_counts=dict(Counter(r["reason"] for r in reads)),
                  limitation="Keyframe sampling ~2s misses shorter exclusions; endpoints trimmed 2s. Human spot-check required; dense validation remains open.")
    write_json(root / "sparse-spans" / f"{sid}.json", result)
    if not (root / "spans" / f"{sid}.json").exists():
        write_json(root / "spans" / f"{sid}.json", result)
    refresh(root)
    return result


def dense(root, sid, start=0, duration=None, cuda=False):
    """Decode a bounded interval on CPU at 2 Hz, retain timestamped verdicts.

    Native video remains the authoritative consumer media. Keep one frame in RAM.
    Two-Hz screening still cannot rule out a sub-500ms overlay between samples.
    """
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    if sid in SEALED:
        raise ValueError("sealed source refused")
    meta = next(r for r in catalogue(root) if r["source_id"] == sid)
    media = Path(meta["media_path"])
    if not media.exists():
        media = media.with_suffix(media.suffix + ".part")
    width, height = meta["resolution"]
    duration = duration or meta["duration_s"] - start
    def game_running():
        # Read-only process inventory; no game or desktop input.
        probe = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Marvel-Win64-Shipping.exe", "/FO", "CSV", "/NH"],
                               capture_output=True, text=True, timeout=10)
        if probe.returncode:
            raise RuntimeError("could not verify GPU availability")
        return "Marvel-Win64-Shipping.exe" in probe.stdout
    if cuda and game_running():
        raise RuntimeError("game owns GPU; use CPU")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "1"]
    if cuda:
        command += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    command += ["-ss", str(start), "-i", str(media), "-t", str(duration), "-an", "-vf",
               "fps=2,hwdownload,format=nv12" if cuda else "fps=2", "-threads", "1",
               "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "3", "pipe:1"]
    reads = []
    log_path = root / "logs" / f"dense-{sid}-{int(start)}.log"
    read_path = root / "screening" / f"{sid}-dense-{int(start)}.jsonl"
    begun = time.monotonic()
    last_gpu_guard = begun
    with log_path.open("w") as log, read_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log)
        try:
            for raw in jpeg_frames(process.stdout):
                if time.monotonic() - begun > 14400:
                    raise TimeoutError("four-hour dense screening deadline")
                if cuda and time.monotonic() - last_gpu_guard > 10:
                    if game_running():
                        raise RuntimeError("game started; yielding GPU")
                    last_gpu_guard = time.monotonic()
                frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if frame is None or frame.shape[:2] != (height, width):
                    raise ValueError("invalid native analysis frame")
                row = dict(t=start + len(reads) / 2, **verdict(frame))
                reads.append(row)
                output.write(json.dumps(row) + "\n")
                if len(reads) % 500 == 0:
                    output.flush()
                    print(f"{sid}: dense {row['t']:.1f}s ({len(reads)} samples)", flush=True)
            if process.wait(timeout=30):
                raise RuntimeError(f"ffmpeg failed; see {log_path}")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            process.stdout.close()
    if len(reads) < duration * 2 - 4:
        raise ValueError("interval not completely decoded; do not export truncated download")
    spans = spans_from_reads(reads, max_gap=0.6, trim_s=0.5, min_s=4, bridge_unknown=2)
    for span in spans:
        span["confidence"] = "2hz_hud_candidate"
    result = dict(source_id=sid, media_path=str(Path(meta["media_path"]).resolve()), spans=spans,
                  gameplay_candidate_s=sum(s["end_s"] - s["start_s"] for s in spans),
                  sample_counts=dict(Counter(r["reason"] for r in reads)),
                  sampled_until_s=reads[-1]["t"] if reads else 0, dense_validated=True,
                  limitation="2-Hz HUD screening and inward 0.5s trims; sub-500ms exclusions may escape sampling. Spot-check and source replay review required.")
    result["interval"] = [start, start + duration]
    chunk_path = root / "dense-spans" / sid / f"{start:g}-{duration:g}.json"
    write_json(chunk_path, result)
    chunks = [json.loads(p.read_text()) for p in chunk_path.parent.glob("*.json")]
    # A longer check supersedes an entirely contained pilot; partial overlap is
    # refused rather than double-counting the same frames.
    chunks = [c for c in chunks if not any(c is not d and d["interval"][0] <= c["interval"][0]
              and d["interval"][1] >= c["interval"][1] and d["interval"] != c["interval"] for d in chunks)]
    chunks.sort(key=lambda c: c["interval"][0])
    if any(a["interval"][1] > b["interval"][0] for a, b in zip(chunks, chunks[1:])):
        raise ValueError("overlapping dense intervals; choose disjoint intervals or a containing replacement")
    merged = dict(result, spans=[s for c in chunks for s in c["spans"]],
                  gameplay_candidate_s=sum(c["gameplay_candidate_s"] for c in chunks),
                  dense_intervals=[c["interval"] for c in chunks],
                  sampled_until_s=max(c["sampled_until_s"] for c in chunks),
                  sample_counts=dict(sum((Counter(c["sample_counts"]) for c in chunks), Counter())))
    write_json(root / "spans" / f"{sid}.json", merged)
    refresh(root)
    return result


def exclude_review_intervals(spans, intervals):
    """Withhold any span touching a human-identified non-player interval."""
    return [s for s in spans if not any(s["start_s"] < i["end_s"] and s["end_s"] > i["start_s"]
                                       for i in intervals)]


def refresh(root):
    rows = catalogue(root)
    by_id = {r["source_id"]: r for r in rows}
    exports = []
    for path in sorted((root / "spans").glob("*.json")):
        result = json.loads(path.read_text())
        meta = by_id.get(result["source_id"])
        if not meta or not meta["download_complete"]:
            continue
        review = meta["review"]
        if not review.get("spot_check_pass"):
            (root / "manifests" / f"{result['source_id']}.manifest.jsonl").unlink(missing_ok=True)
            continue
        spans = exclude_review_intervals(result["spans"], review.get("exclude_intervals", []))
        for span in spans:
            exports.append(dict(source_id=result["source_id"], span_id=f"{result['source_id']}:{span['start_s']:.3f}-{span['end_s']:.3f}",
                                video_id=result["source_id"], local_path=meta["media_path"],
                                sha256=review.get("sha256"), width=meta["resolution"][0], height=meta["resolution"][1],
                                hero="spider_man", pov="player", input="mkb" if meta["input_device"] == "keyboard_mouse" else "unknown",
                                hud="partial" if review.get("hud_occluded") else "full",
                                overlays=(meta["overlay_rects"] or []) + (meta["facecam_rects"] or []),
                                source_url=meta["url"], media_path=meta["media_path"],
                                fps=meta["fps"], resolution=meta["resolution"],
                                input_device=meta["input_device"], overlay_rects=meta["overlay_rects"],
                                facecam_rects=meta["facecam_rects"], **{k: v for k, v in span.items() if k != "confidence"},
                                confidence="hud_screened_human_spot_checked", dense_validated=result.get("dense_validated", False),
                                classifier_version=result.get("classifier_version", "v2_or_sparse"),
                                notes=result["limitation"]))
        from agent.demos import write_manifest
        header = dict(id=f"expert:{result['source_id']}", kind="vod", source_url=meta["url"],
                      run=None, vod_id=result["source_id"], creator=meta["channel"],
                      retrieved=datetime.now(timezone.utc).isoformat(), source_start_s=0,
                      source_end_s=meta["duration_s"], duration_s=meta["duration_s"],
                      resolution=meta["resolution"], fps=meta["fps"], hero="Spider-Man",
                      overlays=[r["kind"] for r in (meta["overlay_rects"] or [])], split="inspection_only",
                      media=dict(kind="video", path=meta["media_path"]), inputs=None,
                      events=None, annotations=None, segments_from="annotator", cooldowns="unknown",
                      cooldowns_from="none", patch="unknown", patch_from="none", splittable=False,
                      edited_upload=False, group=f"twitch:{result['source_id']}",
                      notes=result["limitation"])
        write_manifest(root / "manifests" / f"{result['source_id']}.manifest.jsonl", header,
                       [dict(start_t=s["start_s"], end_t=s["end_s"], started_by="hud_returned", ended_by="no_hud")
                        for s in spans])
    jsonl(root / "idm-spans.jsonl", exports)
    totals = dict(downloaded_hours=sum(r["duration_s"] or 0 for r in rows if r["download_complete"]) / 3600,
                  screened_candidate_hours=sum(s["end_s"]-s["start_s"] for s in exports) / 3600,
                  usable_spans=len(exports), completed_sources=sum(r["download_complete"] for r in rows),
                  updated=datetime.now(timezone.utc).isoformat())
    write_json(root / "totals.json", totals)
    return totals


def import_cloud(root, folder):
    """Adopt metadata-only cloud results after checking source and geometry."""
    known = {r["source_id"]: r for r in catalogue(root)}
    imported = []
    for path in sorted(folder.glob("*.json")):
        result = json.loads(path.read_text())
        sid = result["source_id"]
        if "error" in result:
            continue
        if sid in SEALED:
            raise ValueError("sealed source refused")
        if sid not in known:
            continue  # download not yet started on PC
        meta = known[sid]
        info = result["info"]
        if info["id"].removeprefix("v") != sid or [info["width"], info["height"]] != meta["resolution"]:
            raise ValueError("cloud source/geometry differs from local media")
        previous = -1
        for span in result["spans"]:
            lo, hi = span["start_s"], span["end_s"]
            if lo < previous or hi <= lo or hi > meta["duration_s"] + 1:
                raise ValueError("invalid cloud segment timeline")
            previous = hi
        result["media_path"] = meta["media_path"]
        write_json(root / "spans" / f"{sid}.json", result)
        imported.append(sid)
    return dict(imported=imported, **refresh(root))


def watch(root, hours, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for row in catalogue(root):
            sid = row["source_id"]
            if row["download_complete"] and not (root / "spans" / f"{sid}.json").exists():
                screen(root, Path(row["media_path"]), sid)
        totals = refresh(root)
        print(json.dumps(totals), flush=True)
        if totals["screened_candidate_hours"] >= hours:
            return
        time.sleep(30)
    raise TimeoutError("bounded corpus watch ended; completed artifacts retained")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("catalogue")
    sub.add_parser("summary")
    s = sub.add_parser("import-cloud")
    s.add_argument("folder", type=Path)
    s = sub.add_parser("screen")
    s.add_argument("media", type=Path)
    s.add_argument("source_id")
    s.add_argument("--duration", type=float)
    s = sub.add_parser("watch")
    s.add_argument("--hours", type=float, default=20)
    s.add_argument("--timeout", type=float, default=28800)
    s = sub.add_parser("dense")
    s.add_argument("source_id")
    s.add_argument("--start", type=float, default=0)
    s.add_argument("--duration", type=float)
    s.add_argument("--cuda", action="store_true", help="NVDEC only while game is absent; checked throughout")
    a = p.parse_args()
    for name in ("manifests", "reviews", "spans", "screening"):
        (a.root / name).mkdir(parents=True, exist_ok=True)
    if a.command == "catalogue":
        print(json.dumps(catalogue(a.root), indent=2))
    elif a.command == "summary":
        print(json.dumps(refresh(a.root), indent=2))
    elif a.command == "screen":
        result = screen(a.root, a.media, a.source_id, a.duration)
        print(json.dumps({k: v for k, v in result.items() if k != "spans"}, indent=2))
    elif a.command == "dense":
        result = dense(a.root, a.source_id, a.start, a.duration, a.cuda)
        print(json.dumps({k: v for k, v in result.items() if k != "spans"}, indent=2))
    elif a.command == "import-cloud":
        print(json.dumps(import_cloud(a.root, a.folder), indent=2))
    else:
        watch(a.root, a.hours, a.timeout)


if __name__ == "__main__":
    main()
