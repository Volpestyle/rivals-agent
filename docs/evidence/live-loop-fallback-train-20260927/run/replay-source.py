"""Fixed 120-s admitted TRAIN replay. No capture, input, corpus scan or source CLI.

inspect hashes the original and extracts three native inspection frames. After
their manual inspection receipt, run streams the fixed 3600 native frames through
the exact fallback, self-fed, at unchanged .5 thresholds and support mask.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SESSION = "20260923T051828-422Z-33696-1"
STEPS = ROOT / "data/human/sessions" / SESSION / (SESSION + ".steps.jsonl")
STEPS_SHA = "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb"
VIDEO = Path("C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv")
VIDEO_SHA = "ad14e5bc0a1e0da23527a8f4a092e591ddf568ac925cfd0b2907e38dc94b9aaf"
VIDEO_BYTES = 6892293372
CHECKPOINT = ROOT / "data/diagnostics/live-loop-fallback-20260927/model_nohud-seed0.pt"
CHECKPOINT_SHA = "2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18"
CONTRACT = ROOT / "docs/evidence/live-loop-fallback-20260927"
EVIDENCE = ROOT / "docs/evidence/live-loop-fallback-train-20260927"
START, STOP = 7, 3607
INSPECT_ROWS = (7, 1807, 3606)
DEADLINE_S = 900


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def fixed_selection():
    """Existing denylist/header/row checks run before any original-media access."""
    from policy.range_bc import steps
    denylist = steps.load_denylist()
    session = steps.load(STEPS, denylist=denylist)
    require(session.sha256 == STEPS_SHA, "fixed step-table hash changed")
    require(session.session_id == SESSION and session.split == "train", "only named TRAIN session permitted")
    require(session.header["media_sha256"] == VIDEO_SHA, "original media identity changed")
    require(session.header["video_size"] == [2560, 1440], "native geometry changed")
    require(steps.runs(session, regimes=("normal",)) == [(7, 12557)], "fixed admitted run changed")
    rows = session.rows[START:STOP]
    require(len(rows) == 3600 and all(r["gap_free"] for r in rows), "fixed contiguous selection changed")
    require(all(Path(r["frame"]["video_path"]).resolve() == VIDEO.resolve() for r in rows), "source path changed")
    ordinals = [r["frame"]["frame_index"] for r in rows]
    require(all(a < b for a, b in zip(ordinals, ordinals[1:])), "selected ordinals must increase uniquely")
    return session, rows


def selection_contract(session, rows):
    return {"session_id": SESSION, "split": "train", "steps_sha256": STEPS_SHA,
            "media_sha256": VIDEO_SHA, "media_path": str(VIDEO), "row_slice": [START, STOP],
            "selected_before_predictions": True, "step_ns": session.header["step_ns"],
            "duration_s": len(rows) * session.header["step_ns"] / 1e9,
            "calibration": session.calibration, "admission_provenance": session.header["source"],
            "frames": [{"row": r["i"], "anchor_ns": r["anchor_ns"], **r["frame"]} for r in rows]}


def verify_media():
    from policy.range_bc import cache
    require(VIDEO.stat().st_size == VIDEO_BYTES, "fixed original size changed")
    require(digest(VIDEO) == VIDEO_SHA, "fixed original hash changed")
    require(cache.probe_size(VIDEO) == [2560, 1440], "decoded geometry changed")
    colour = cache.probe_colour(VIDEO)
    cache.check_colour(colour)
    return {"sha256": VIDEO_SHA, "bytes": VIDEO_BYTES, "colour": colour,
            "ffmpeg": cache.ffmpeg_version(), "verified_utc": datetime.now(timezone.utc).isoformat()}


def check_frame_identity(index, shown, row):
    n, pts, tb = shown
    require(n == index and pts == row["frame"]["pts"] and list(tb) == row["frame"]["timebase"],
            f"decoded ordinal/PTS/timebase mismatch at selected row {row['i']}: {shown}")


def native_frames(rows, output):
    """One native BGR frame at a time, strict showinfo checked BEFORE yield."""
    import numpy as np
    from policy.range_bc import cache
    graph = cache.select_expression([r["frame"]["frame_index"] for r in rows]) + ",showinfo," + \
        cache.CONVERT.replace("format=rgb24", "format=bgr24")
    script = output / "native-filter.txt"
    script.write_text(graph, encoding="ascii")
    cmd = ["ffmpeg", "-v", "info", "-nostdin", "-threads", "2", "-i", str(VIDEO), "-map", "0:v:0",
           "-filter_threads", "1", "-filter_script:v", str(script), "-fps_mode", "passthrough",
           "-frames:v", str(len(rows)), "-an", "-sn", "-threads", "2", "-pix_fmt", "bgr24",
           "-f", "rawvideo", "pipe:1"]
    write(output / "decode-command.json", cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    shown = queue.Queue()  # metadata only; pipe backpressure bounds native pixels
    errors = []
    def drain():
        tb = None
        try:
            with (output / "ffmpeg-showinfo.log").open("xb") as log:
                for raw in iter(proc.stderr.readline, b""):
                    log.write(raw)
                    line = raw.decode(errors="replace")
                    match = cache._TIMEBASE.search(line)
                    if match:
                        require(tb is None, "multiple input timebases")
                        tb = tuple(map(int, match.groups()))
                    match = cache._SHOWINFO.search(line)
                    if match:
                        require(tb is not None, "showinfo missing timebase")
                        shown.put((*map(int, match.groups()), tb))
        except BaseException as exc:
            errors.append(str(exc))
        finally:
            shown.put(None)
    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    size = 2560 * 1440 * 3
    try:
        for i, row in enumerate(rows):
            raw = proc.stdout.read(size)
            require(len(raw) == size, f"truncated native frame {i}: {len(raw)} bytes")
            identity = shown.get(timeout=10)
            require(identity is not None and not errors, f"missing showinfo: {errors}")
            check_frame_identity(i, identity, row)
            yield np.frombuffer(raw, dtype=np.uint8).reshape(1440, 2560, 3), identity
        require(not proc.stdout.read(1), "unexpected extra decoded frame")
        require(proc.wait(timeout=10) == 0, "ffmpeg decode failed")
        thread.join(10)
        require(not thread.is_alive() and not errors and shown.get(timeout=1) is None,
                "showinfo stream did not end exactly")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
        thread.join(10)
        proc.stdout.close()
        proc.stderr.close()


def raw_decode(probabilities, cameras, previous, mask):
    """Pure semantic decode. No Cal/pad state: raw requested camera stays visible."""
    from policy.range_bc import executor, vocab
    require(len(probabilities) == 3 and all(len(p) == vocab.N for p in probabilities), "action shape")
    require(len(cameras) == 2 and all(len(p) == vocab.CAMERA_CLASSES for p in cameras), "camera shape")
    require(all(math.isfinite(p) and 0 <= p <= 1 for row in [*probabilities, *cameras] for p in row),
            "nonfinite/out-of-range probability")
    require(all(abs(sum(p) - 1) < 1e-4 for p in cameras), "camera probabilities must sum to one")
    held, press, release = executor.decode_step(*probabilities, previous["held"] if previous else [0] * vocab.N,
                                                 mask, threshold=.5)
    cy, cp = (vocab.median_class(p) for p in cameras)
    return {"held": held, "press": press, "release": release, "known": [True] * vocab.N,
            "cy": cy, "cp": cp, "yaw": vocab.class_degrees(cy), "pitch": vocab.class_degrees(cp)}


def metrics(targets, mask, duration):
    from policy.range_bc import vocab
    from scripts.measure_inference_fps import percentiles
    targets = list(targets)
    per_action = {}
    for c, name in enumerate(vocab.NAMES):
        known = [t for t in targets if t.get("press_known", t["known"])[c]]
        presses = sum(t["press"][c] for t in known)
        per_action[name] = {"supported": bool(mask[c]), "press_steps": presses,
                            "press_hz": presses / duration, "known_steps": len(known),
                            "held_steps": sum(t["held"][c] for t in targets if t["known"][c])}
    axes = {}
    for axis in ("yaw", "pitch"):
        values = [abs(t[axis]) for t in targets if t[axis] is not None]
        axes[axis] = {"known_steps": len(values), "abs_mean_deg": sum(values) / len(values) if values else None,
                      "abs_p95_deg": percentiles(values)["p95"], "abs_total_deg": sum(values),
                      "signed_total_deg": sum(t[axis] for t in targets if t[axis] is not None)}
    neutral = {}
    for label, active_mask in (("all", [True] * vocab.N), ("supported", mask)):
        eligible = [t for t in targets if all(t["known"][i] and t.get("press_known", t["known"])[i]
                                             for i in range(vocab.N) if active_mask[i])]
        action_neutral = lambda t: not any(active_mask[i] and (t["held"][i] or t["press"][i])
                                          for i in range(vocab.N))
        camera_known = [t for t in eligible if t["yaw"] is not None and t["pitch"] is not None]
        neutral[label] = {"action_known_steps": len(eligible), "action_camera_known_steps": len(camera_known),
            "action_only_fraction": sum(action_neutral(t) for t in eligible) / len(eligible) if eligible else None,
            "action_and_raw_camera_fraction": sum(action_neutral(t) and t["yaw"] == t["pitch"] == 0
                for t in camera_known) / len(camera_known) if camera_known else None,
            "action_and_camera_zero_class_fraction": sum(action_neutral(t) and t["cy"] == t["cp"] == vocab.ZERO_CLASS
                for t in camera_known) / len(camera_known) if camera_known else None}
    all_p = sum(v["press_steps"] for v in per_action.values())
    supported_p = sum(v["press_steps"] for v in per_action.values() if v["supported"])
    return {"steps": len(targets), "duration_s": duration, "per_action": per_action, "camera": axes,
            "neutral": neutral, "all_press_steps": all_p, "supported_press_steps": supported_p,
            "all_press_hz": all_p / duration, "supported_press_hz": supported_p / duration}


def replay(rows, calibration, frames, predictor, mask, stream, progress=lambda n: None):
    from policy.range_bc import steps
    previous, human, predicted, timings = None, [], [], []
    for row, (frame, identity) in zip(rows, frames, strict=True):
        started = time.perf_counter()
        probabilities, cameras = predictor(frame, previous)
        timings.append(time.perf_counter() - started)
        current = raw_decode(probabilities, cameras, previous, mask)
        target = steps.target(row, calibration)
        value = {"row": row["i"], "anchor_ns": row["anchor_ns"], "frame": row["frame"],
                 "showinfo": identity, "prediction_s": timings[-1], "model": current,
                 "human": target, "human_raw_press_counts": row["press"],
                 "probabilities": probabilities, "camera_probabilities": cameras}
        stream.write(json.dumps(value, allow_nan=False) + "\n")
        human.append(target)
        predicted.append(current)
        previous = current  # self-fed decoded actions AND raw requested camera classes
        if len(predicted) % 300 == 0:
            stream.flush()
            progress(len(predicted))
    return human, predicted, timings


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("inspect", "run"))
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    a = p.parse_args(argv)
    output = EVIDENCE / a.mode
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "attempt directory must be empty; preserve prior evidence")
    from scripts.profile_range_bc_live import PCGuard
    from scripts import job_status
    job = "live-fallback-train-" + a.mode
    job_status.write(job, owner="live-fps", host="pc", stage="running", started=int(time.time()), evidence=str(output))
    guard = None
    timer = None
    predictor = None
    try:
        guard = PCGuard(output)
        def deadline():
            write(output / "DEADLINE.json", {"seconds": DEADLINE_S})
            job_status.write(job, stage="failed", progress="hard wall deadline")
            os._exit(4)
        timer = threading.Timer(DEADLINE_S, deadline)
        timer.daemon = True
        timer.start()
        session, rows = fixed_selection()
        selection = selection_contract(session, rows)
        write(output / "selection.json", selection)
        job_status.write(job, progress="stream hashing fixed original before media decode")
        write(output / "media.json", verify_media())
        if a.mode == "inspect":
            job_status.write(job, progress="decoding three fixed native inspection frames")
            import cv2
            cv2.setNumThreads(1)
            chosen = [session.rows[i] for i in INSPECT_ROWS]
            images = []
            for row, (frame, identity) in zip(chosen, native_frames(chosen, output), strict=True):
                name = f"row-{row['i']}-native.png"
                require(cv2.imwrite(str(output / name), frame), "native inspection PNG write failed")
                images.append({"row": row["i"], "file": name, "sha256": digest(output / name),
                               "showinfo": identity, "shape": list(frame.shape)})
            write(output / "images.json", images)
            job_status.write(job, stage="done", progress="three native frames await manual inspection")
            return 0
        inspection = json.loads((EVIDENCE / "inspection.json").read_text())
        require(inspection["accepted"] is True and inspection["selection_sha256"] == digest(EVIDENCE / "inspect/selection.json")
                == digest(output / "selection.json"), "manual inspection selection mismatch")
        for item in inspection["images"]:
            require(digest(EVIDENCE / "inspect" / item["file"]) == item["sha256"], "inspection image changed")
        require([v["row"] for v in inspection["images"]] == list(INSPECT_ROWS), "all three native inspections required")
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        if a.device == "cpu":
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
        import torch
        import cv2
        cv2.setNumThreads(1)
        torch.set_num_interop_threads(1)
        from scripts.measure_inference_fps import parser, prepare, percentiles
        args = parser().parse_args(["--checkpoint", str(CHECKPOINT), "--checkpoint-sha256", CHECKPOINT_SHA,
            "--support-json", str(CONTRACT / "support.json"), "--settings-json", str(CONTRACT / "settings-offline-only.json"),
            "--output", str(output), "--device", a.device])
        model, backbone, preprocess, manifest = prepare(args)
        from policy.range_bc.live_inference import DevicePredictor
        predictor = DevicePredictor(model, preprocess, cooldowns="normal", backbone=backbone, device=a.device)
        manifest.update(source="fixed admitted training rows, native BGR from original recording",
            history="initial None; self-fed decoded masked held/press/release and RAW requested camera classes; recurrent state continuous",
            camera="raw requested median class degrees; no saturation/Cal or actual pad rotation claim",
            script_sha256=digest(Path(__file__)), selection_sha256=digest(output / "selection.json"),
            historical_failure="original frozen-dev self-fed press F1 0.0; this training diagnostic cannot promote model",
            neutral_verdict_rule="recommend camera+FPS only if >=99% action+raw-camera neutral")
        write(output / "manifest.json", manifest)
        guard.check()
        job_status.write(job, progress={"n": 0, "total": len(rows)})
        started = time.perf_counter()
        with gzip.open(output / "per-step.jsonl.gz", "xt", encoding="utf-8", compresslevel=1) as stream:
            human, predicted, timings = replay(rows, session.calibration, native_frames(rows, output), predictor,
                manifest["live_mask"], stream, progress=lambda n: job_status.write(job, progress={"n": n, "total": len(rows)}))
        guard.check()
        hm, pm = (metrics(v, manifest["live_mask"], selection["duration_s"]) for v in (human, predicted))
        report = {"human": hm, "model": pm, "prediction_seconds": percentiles(timings),
                  "elapsed_seconds": time.perf_counter() - started, "peak_rss_bytes": guard.peak,
                  "human_raw_press_count_all": sum(sum(r["press"]) for r in rows),
                  "human_raw_press_count_supported": sum(sum(v for v, enabled in zip(r["press"], manifest["live_mask"]) if enabled) for r in rows),
                  "historical_self_fed_failure_unchanged": True, "actual_pad_rotation": "unknown until accepted map",
                  "degree_caveat": "slow-turn yaw gain; pitch derived_equal_sensitivity, not independently measured",
                  "recommendation": "camera+FPS only" if pm["neutral"]["supported"]["action_and_raw_camera_fraction"] >= .99
                    else "not near-total neutral; integration owner must assess action/camera deficit; no promotion"}
        write(output / "report.json", report)
        job_status.write(job, stage="done", progress=report["recommendation"])
        print(json.dumps({"output": str(output), "recommendation": report["recommendation"], "model": pm}))
    except BaseException as exc:
        write(output / "ERROR.json", {"type": type(exc).__name__, "error": str(exc)})
        job_status.write(job, stage="failed", progress=str(exc)[:1000])
        raise
    finally:
        if predictor is not None:
            predictor.close()
        if timer is not None:
            timer.cancel()
        if guard is not None:
            guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
