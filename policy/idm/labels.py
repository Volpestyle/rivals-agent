"""Label expert footage with an IDM and export policy's REPLAY step tables (VUH-1353, lean mode).

    python -m policy.idm.labels run CKPT SPANS.jsonl WORK_DIR [--video ID] [--shard K/N] [--device cuda]
    python -m policy.idm.labels export CKPT SPANS.jsonl WORK_DIR OUT_DIR [--video ID]

For cached features, add --anchor-dir OLD_MODEL_LABEL_DIR and a fresh OUT_DIR. This preserves the old anchors,
run and exact frame identity while summing the new model's interval answers. Unsupported boundary/gap rows are
omitted, i is compact, and existing aligned outputs are refused. Neither old labels nor features are modified.

`run` labels every span of the footage worker's export (one npz per span under WORK_DIR/<model>/, skipped when
present) with policy.idm.vod.label_span, masking the span's overlay rects. On the PC it pauses while Marvel Rivals
is running (the GPU and CPU belong to the game). `export` writes one rivals-range-steps-v1 table per video with
source_kind "replay" (policy/range_bc/steps.py): one row per 30 Hz anchor, one run per span.

Row semantics: anchors lie on the nominal 30 Hz grid from the span's first labelled frame; the row's frame is the last
decoded frame at or before the anchor, and the step covers the 60 Hz intervals ending in (anchor, anchor + 33.3 ms]
(two, occasionally one or three on a variable-rate VOD). yaw/pitch are their summed camera answers (null if any
abstains). press is 1 when a predicted onset (an above-threshold run's peak) falls in
the step, for actions the checkpoint has a threshold for; other actions are null. held_* come from a held head (v2)
at 0.5, else null. release is null. Extra fields: press_p (step max probability), camera_std (deg), camera_conf.
Third-party frames and labels stay local: never git, never Linear.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from policy.idm import vod

STEP_NS = 33_333_333
FRAME_PERIOD_NS = 16_666_667
PAD_ENVELOPE = {"yaw_deg_per_s": 415.0, "pitch_deg_per_s": 99.0}      # the targets headers' pad_envelope
HELD_ACTIONS = ("move_forward", "move_left", "move_back", "move_right", "web_swing", "spider_power")


GAME = os.environ.get("IDM_GAME_PROCESS", "Marvel-Win64-Shipping.exe")    # overridable for testing only
EXIT_FOR_GAME = 75                                                          # EX_TEMPFAIL: rerun after the game


def game_running():
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME}"], capture_output=True, text=True).stdout
    return GAME.lower() in out.lower()


def exit_when_game_starts(period=5.0):
    """The GPU (VRAM included) belongs to the game: exit the whole process as soon as it starts. Finished spans are
    already saved one file each, so a rerun resumes from them; the in-flight span's .tmp file is discarded."""
    import threading

    def watch():
        while True:
            if game_running():
                print(json.dumps({"event": "exit_for_game", "process": GAME}), flush=True)
                os._exit(EXIT_FOR_GAME)
            time.sleep(period)
    threading.Thread(target=watch, daemon=True).start()


def spans(path, video=None):
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if video is None or r["video_id"] == video]


def span_file(work, model, span):
    return Path(work) / model / f"{span['span_id'].replace(':', '_')}.npz"


def model_name(ckpt):
    return Path(ckpt).stem if Path(ckpt).stem not in ("refit", "v2") else Path(ckpt).parent.name + "-" + Path(ckpt).stem


def _rects(s):
    return [o["rect"] for o in s.get("overlays", [])] + [o["rect"] for o in s.get("facecam_rects", [])
                                                         if isinstance(o, dict) and "rect" in o]


def run(ckpt, spans_path, work, *, video=None, shard=(0, 1), device="cuda", model=None, fast=False, workers=1):
    """Label each span not yet labelled. workers > 1 decodes that many spans at once in threads (ffmpeg
    subprocesses) while this process runs the model on the GPU: several processes sharing one GPU time-slice it
    badly on Windows. At most workers + 2 decoded spans are held in memory.
    Several label sets from one decode: ckpt 'a.pt,b.pt+c.pt' with model 'name-a,name-bc' (a '+' joins an
    ensemble). Spans still missing the first set go first."""
    from collections import deque
    from concurrent.futures import ThreadPoolExecutor
    todo = [s for k, s in enumerate(spans(spans_path, video)) if k % shard[1] == shard[0]]
    ckpts = str(ckpt).split(",")
    names = model.split(",") if model else [model_name(c) for c in ckpts]
    assert len(names) == len(ckpts), "one --model name per checkpoint"
    sets = [(n, c, vod.load_any(c, device)) for n, c in zip(names, ckpts)]
    for n, _, _ in sets:
        (Path(work) / n).mkdir(parents=True, exist_ok=True)
    todo = [s for s in todo if any(not span_file(work, n, s).exists() for n, _, _ in sets)]
    exit_when_game_starts()
    todo.sort(key=lambda s: span_file(work, names[0], s).exists())
    done, t_last = 0, time.time()

    def prep(s):
        try:
            return vod.prepare_span(s["local_path"], s["start_s"], s["end_s"], rects=_rects(s), fast=fast)
        except Exception as e:                                          # reported when the span is consumed
            return e
    with ThreadPoolExecutor(max(1, workers)) as pool:
        queue, it = deque(), iter(todo)
        while True:
            while len(queue) < max(1, workers) + 2:
                s = next(it, None)
                if s is None:
                    break
                queue.append((s, pool.submit(prep, s)))
            if not queue:
                break
            s, fut = queue.popleft()
            prepared = fut.result()
            try:
                if isinstance(prepared, Exception):
                    raise prepared
                for name, c, loaded in sets:
                    out = span_file(work, name, s)
                    if out.exists():
                        continue
                    n = vod.label_file(c, s["local_path"], str(out) + ".tmp.npz", start=s["start_s"],
                                       end=s["end_s"], rects=_rects(s), device=device, span_id=s["span_id"],
                                       loaded=loaded, fast=fast, prepared=prepared)
                    Path(str(out) + ".tmp.npz").replace(out)
            except Exception as e:                                      # one bad span must not stop the batch
                print(json.dumps({"event": "span_failed", "span": s["span_id"], "error": str(e)[:300]}),
                      flush=True)
                continue
            done += 1
            now = time.time()
            print(json.dumps({"event": "span", "span": s["span_id"], "rows": n, "s": round(now - t_last, 1),
                              "done": done, "of": len(todo)}), flush=True)
            t_last = now
    print(json.dumps({"event": "all_done", "labelled": done, "of": len(todo)}), flush=True)


def _sha(path, cache):
    key = str(path)
    if key not in cache:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 24), b""):
                h.update(block)
        cache[key] = h.hexdigest()
    return cache[key]


def _video_index(video, cache_dir):
    """(every frame's pts in seconds, sorted; stream timebase [num, den]), cached next to the labels."""
    cache = Path(cache_dir) / (Path(video).stem + ".frames.npz")
    if cache.exists():
        z = np.load(cache)
        return z["pts"], [int(v) for v in z["tb"]]
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=time_base",
                           "-of", "json", str(video)], check=True, capture_output=True, text=True).stdout
    # MPEG-TS reports the stream both inside its program and at top level.
    tb = json.loads(info)["streams"][0]["time_base"]
    num, den = (int(v) for v in tb.split("/"))
    pts = np.array(vod.probe_pts(video), np.int64) * num / den
    np.savez(cache, pts=pts, tb=np.array([num, den]))
    return pts, [num, den]


def step_rows(z, thresholds, *, video_path, index_pts, tb, run_id, i0, anchor_rows=None):
    """The span's 30 Hz replay rows, numbered from i0."""
    t, cam = z["t"], z["cam"]
    prob = z["prob"]
    held = z["held"] if "held" in z else None
    yaw, pitch = z["yaw_ans"], z["pitch_ans"]
    ystd, pstd = z["yaw_std"], z["pitch_std"]
    actions = json.loads(str(z["meta"]))["actions"]
    onset = np.zeros(prob.shape, bool)
    for a, thr in thresholds.items():
        c = actions.index(a)
        onset[vod.onsets(prob[:, c], thr), c] = True
    rows = []
    step_s = STEP_NS / 1e9
    base_ns = int(round(float(t[0]) * 1e9))
    prev = None                                                    # (grid step, held_end) of the last row written
    grid = ((base_ns + k * STEP_NS, None) for k in range(int((t[-1] - t[0]) / step_s)))
    if anchor_rows is not None:
        grid = ((r["anchor_ns"], r["frame"]) for r in anchor_rows)
    for anchor_ns, expected_frame in grid:
        anchor = anchor_ns / 1e9
        a = int(np.searchsorted(t, anchor + 1e-9, side="right")) - 1   # last decoded frame at or before the anchor
        js = []
        b = a + 1
        while b < len(t) and t[b] <= anchor + step_s + 1e-9:
            js.append(b)
            b += 1
        if (a < 0 or not js or anchor + step_s > t[-1] + 1e-9
                or np.any(np.diff(t[a:js[-1] + 1]) > 0.025)):   # no complete step, or a hole in the span
            continue
        if anchor - t[a] > 2 * FRAME_PERIOD_NS / 1e9:
            continue
        frame_s = float(t[a])
        ordinal = int(np.searchsorted(index_pts, frame_s - 1e-6))
        pts = int(round(frame_s * tb[1] / tb[0]))
        if expected_frame is not None and (expected_frame["frame_index"] != ordinal
                or expected_frame["pts"] != pts or expected_frame["timebase"] != tb):
            raise ValueError(f"anchor source-frame mismatch: {run_id} at {anchor_ns}")
        y = None if np.isnan(yaw[js]).any() else float(yaw[js].sum())
        p = None if np.isnan(pitch[js]).any() else float(pitch[js].sum())
        press = [None] * len(actions)
        press_p = [None] * len(actions)
        for name in thresholds:
            c = actions.index(name)
            press[c] = int(onset[js, c].any())
            press_p[c] = round(float(prob[js, c].max()), 4)
        hs = he = [None] * len(actions)
        if held is not None:
            hs, he = list(hs), list(he)
            for name in HELD_ACTIONS:
                c = actions.index(name)
                hs[c], he[c] = int(held[a, c] >= 0.5), int(held[js[-1], c] >= 0.5)
            if prev is not None and prev[0] + STEP_NS == anchor_ns:  # holds continue across consecutive steps
                hs = list(prev[1])
            prev = (anchor_ns, he)
        std = (None if np.isnan(ystd[js]).any() else
               [round(float(np.sqrt((ystd[js] ** 2).sum())), 4), round(float(np.sqrt((pstd[js] ** 2).sum())), 4)])
        rows.append({
            "i": i0 + len(rows), "run": run_id, "anchor_ns": anchor_ns,
            "frame": {"video_path": str(video_path), "frame_index": ordinal,
                      "pts": pts, "timebase": tb,
                      "composition_ns": min(int(round(frame_s * 1e9)), anchor_ns)},
            "gap_free": True, "segment": run_id, "suitability": "accepted", "regime": "normal", "tags": [],
            "tag_source": "untagged", "held_start": hs, "held_end": he,
            "held_known": [hs[c] is not None and he[c] is not None for c in range(len(actions))],
            "press": press, "release": [None] * len(actions), "press_known": [v is not None for v in press],
            "release_known": [False] * len(actions), "yaw_deg": y, "pitch_deg": p,
            "beyond_pad_envelope": bool((y is not None and abs(y) / step_s > PAD_ENVELOPE["yaw_deg_per_s"])
                                        or (p is not None and abs(p) / step_s > PAD_ENVELOPE["pitch_deg_per_s"])),
            "press_p": press_p, "camera_std": std,
            "camera_conf": None if std is None else round(float(np.exp(-std[0])), 4)})
    return rows


def export(ckpt, spans_path, work, out_dir, *, video=None, model=None, anchor_dir=None, camera_scale=None):
    from policy.range_bc import vocab
    _, supported, thresholds = vod.load_any(ckpt, "cpu")
    thresholds = {a: t for a, t in (thresholds or vod.FULL03_THRESHOLDS).items() if t < 1.0}
    name = model or model_name(ckpt)
    out_dir = Path(out_dir) / name
    out_dir.mkdir(parents=True, exist_ok=True)
    shas_path = Path(work) / "media-sha256.json"
    shas = json.loads(shas_path.read_text()) if shas_path.exists() else {}
    by_video = {}
    for s in spans(spans_path, video):
        by_video.setdefault(s["video_id"], []).append(s)
    written = {}
    for vid, ss in sorted(by_video.items()):
        ss = sorted(ss, key=lambda s: s["start_s"])
        path = ss[0]["local_path"]
        if not any(span_file(work, name, s).exists() for s in ss):
            continue
        index_pts, tb = _video_index(path, Path(work))
        anchors = None
        reference = None
        if anchor_dir is not None:
            from policy.range_bc import steps
            reference = Path(anchor_dir) / f"expert-{vid}.steps.jsonl"
            anchors = {}
            with reference.open(encoding="utf-8") as fh:
                old_header = json.loads(next(fh))
                steps.check_header(old_header)
                if (old_header["session_id"] != f"expert-{vid}"
                        or old_header["media_sha256"] != _sha(path, shas)
                        or old_header["step_ns"] != STEP_NS):
                    raise ValueError("anchor reference is from a different source or step size")
                for i, line in enumerate(line for line in fh if line.strip()):
                    r = json.loads(line)
                    steps.check_row(r, old_header, i)
                    group = anchors.setdefault(r["run"], [])
                    if group and r["anchor_ns"] <= group[-1]["anchor_ns"]:
                        raise ValueError("anchor reference is not strictly increasing within run")
                    group.append(r)
            if set(anchors) - {s["span_id"] for s in ss}:
                raise ValueError("anchor reference contains unknown spans")
            if (out_dir / reference.name).exists():
                raise FileExistsError("aligned export must use a new output file")
        rows, has_held = [], False
        for s in ss:
            f = span_file(work, name, s)
            if f.exists():
                with np.load(f) as z:
                    z = {k: z[k] for k in z.files}
                has_held = has_held or "held" in z
                rows += step_rows(z, thresholds, video_path=path, index_pts=index_pts, tb=tb,
                                  run_id=s["span_id"], i0=len(rows),
                                  anchor_rows=None if anchors is None else anchors.get(s["span_id"], []))
        if not rows:
            continue
        sha = _sha(path, shas)
        if anchor_dir is None:
            shas_path.write_text(json.dumps(shas, indent=1))
        player = Path(path).parent.name
        header = {
            "format": "rivals-range-steps-v1", "source_kind": "replay", "session_id": f"expert-{vid}",
            "media_sha256": sha, "session_group": f"expert-{vid}", "sitting": f"expert-footage-{player}",
            "split": "replay", "step_ns": STEP_NS, "frame_period_ns": FRAME_PERIOD_NS, "actions": list(vocab.NAMES),
            "calibration": {"kind": "replay_degrees", "source": f"idm {name} ({Path(ckpt).name})",
                            "label_sources": {"camera": f"idm {name}", "edges": f"idm {name} onset thresholds",
                                              "movement": f"idm {name} held head" if has_held else "none (unknown)"}},
            "expert_context": {"player": player, "match_id": "unknown",
                               "viewer_fov_assumption": "unknown: degrees are on James's FOV/sensitivity scale, "
                                                        "not calibrated per source",
                               "replay_source": ss[0].get("source_url") or vid},
            "hud_layout": "mk", "swing_mode": {"automatic_swing": None, "hold_to_swing": None},
            "video_size": [ss[0]["width"], ss[0]["height"]], "patch": "unknown",
            "idm": {"checkpoint": str(ckpt), "thresholds": thresholds, "spans": len(ss),
                    "labelled_spans": sum(span_file(work, name, s).exists() for s in ss)}}
        if camera_scale is not None:
            # true_deg ~= yaw_deg * camera_scale. Applied values come from the scale file; degrees are never rewritten.
            applied = float(camera_scale.get("applied", {}).get(player, camera_scale.get("default", 1.0)))
            header["camera_scale"] = {"applied": applied, "measured": camera_scale.get("creators", {}).get(player),
                                      "basis": camera_scale.get("basis"),
                                      "flag": camera_scale.get("flags", {}).get(player)}
            for r in rows:
                r["camera_scale"] = applied
        out = out_dir / f"expert-{vid}.steps.jsonl"
        if reference is not None:
            header["idm"]["anchor_reference"] = str(reference)
            header["idm"]["anchor_contract"] = "original anchors and exact source frames; new interval answers"
        with open(out, "x" if reference is not None else "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(header) + "\n")
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        written[str(out)] = len(rows)
    return written


def clips(spans_path, out_dir, *, videos, remote_prefix, margin=(3.0, 1.0)):
    """Stream-copy each span of `videos` into its own mkv (timestamps kept: -copyts with an input-side duration), for
    labelling on another machine. Writes out_dir/spans.jsonl with local_path pointing at remote_prefix/<clip>."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for s in spans(spans_path):
        if s["video_id"] not in videos:
            continue
        name = s["span_id"].replace(":", "_") + ".mkv"
        clip = out_dir / name
        if not clip.exists():
            start = max(0.0, s["start_s"] - margin[0])
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{start:.3f}",
                            "-t", f"{s['end_s'] + margin[1] - start:.3f}", "-copyts", "-i", s["local_path"],
                            "-map", "0:v:0", "-c", "copy", str(clip) + ".part.mkv"], check=True)
            Path(str(clip) + ".part.mkv").replace(clip)
        rows.append({**s, "local_path": f"{remote_prefix}/{name}", "source_path": s["local_path"]})
    (out_dir / "spans.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("ckpt")
    r.add_argument("spans")
    r.add_argument("work")
    r.add_argument("--video")
    r.add_argument("--shard", default="0/1")
    r.add_argument("--device", default="cuda")
    r.add_argument("--model")
    r.add_argument("--fast", action="store_true", help="resize in YUV before RGB and decode on the GPU")
    r.add_argument("--workers", type=int, default=1, help="spans decoded concurrently in threads")
    e = sub.add_parser("export")
    e.add_argument("ckpt")
    e.add_argument("spans")
    e.add_argument("work")
    e.add_argument("out")
    e.add_argument("--video")
    e.add_argument("--model")
    e.add_argument("--anchor-dir", help="reuse this label directory's anchors; requires new output files")
    e.add_argument("--camera-scale", help="JSON {default, applied: {creator: scale}, creators: {creator: measured}, "
                                          "basis}: adds camera_scale (row column and header)")
    c = sub.add_parser("clips")
    c.add_argument("spans")
    c.add_argument("out")
    c.add_argument("--videos", nargs="+", required=True)
    c.add_argument("--remote-prefix", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "clips":
        print(clips(a.spans, a.out, videos=set(a.videos), remote_prefix=a.remote_prefix))
    elif a.cmd == "run":
        k, n = (int(v) for v in a.shard.split("/"))
        run(a.ckpt, a.spans, a.work, video=a.video, shard=(k, n), device=a.device, model=a.model, fast=a.fast,
            workers=a.workers)
    else:
        scale = json.loads(Path(a.camera_scale).read_text(encoding="utf-8")) if a.camera_scale else None
        print(json.dumps(export(a.ckpt, a.spans, a.work, a.out, video=a.video, model=a.model,
                                anchor_dir=a.anchor_dir, camera_scale=scale), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
