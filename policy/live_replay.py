"""Offline replay of a LivePolicy on a recorded session: predicted versus James's actions, plus an overlay video.

Frames are decoded from the session's original recording (bt709 limited range to full-range BGR, as the capture
delivers) and fed to `LivePolicy.step` exactly as live, one per 30 Hz step, over one contiguous eligible run.
No game or pad IO.

    python -m policy.live_replay D:/rivals-policy/bundles/ng-nohist-s1 \
        data/human/sessions/<id>/<id>.steps.jsonl --seconds 60 --out D:/rivals-policy/replay/<name>
"""
import argparse
import json
from pathlib import Path

SHOWN = ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing", "get_over_here",
         "amazing_combo", "spider_power", "web_cluster")
SHORT = {"move_forward": "W", "move_left": "A", "move_back": "S", "move_right": "D", "jump": "jump",
         "web_swing": "swing", "get_over_here": "GOH", "amazing_combo": "combo", "spider_power": "LMB",
         "web_cluster": "RMB"}


def frames_for(video, rows, hwaccel=True):
    """Yield (row, BGR frame) for rows whose frame pts appear in order in the video (NVDEC when available)."""
    import av
    wanted = {r["frame"]["pts"]: r for r in rows}
    first = rows[0]["frame"]["pts"]
    accel = None
    if hwaccel:
        try:
            from av.codec.hwaccel import HWAccel
            accel = HWAccel(device_type="cuda", allow_software_fallback=True)
        except Exception:
            accel = None
    with av.open(video, hwaccel=accel) if accel else av.open(video) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        tb = rows[0]["frame"]["timebase"]
        if [stream.time_base.numerator, stream.time_base.denominator] != tb:
            raise ValueError(f"stream timebase {stream.time_base} differs from rows {tb}")
        container.seek(max(0, first - 2000), stream=stream, backward=True)
        last = rows[-1]["frame"]["pts"]
        for frame in container.decode(stream):
            if frame.pts is None or frame.pts < first:
                continue
            if frame.pts > last:
                break
            row = wanted.get(frame.pts)
            if row is not None:
                yield row, frame.to_ndarray(format="bgr24", src_colorspace="ITU709", src_color_range="MPEG",
                                            dst_color_range="JPEG")


def pick_run(session, seconds, start_s=None):
    from policy.range_bc import steps
    runs = [(a, b) for a, b in steps.runs(session)]
    n = int(round(seconds * 30))
    if start_s is not None:
        for a, b in runs:
            k = a + int(start_s * 30)
            if k + n <= b:
                return k, k + n
    a, b = max(runs, key=lambda r: r[1] - r[0])
    return a, min(b, a + n)


def target_bearing(frame):
    """Horizontal bearing of the enemy nearest the crosshair, as a fraction of frame width from centre (None if no
    green-outline enemy is found). Finder on a 1280x720 copy, where its thresholds were measured."""
    import cv2
    from perception.outline import find_enemies
    small = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
    xs = [((d.bbox[0] + d.bbox[2]) / 2) / 1280 - .5 for d in find_enemies(small, 1.0)]
    return min(xs, key=abs) if xs else None


def target_check(records, min_dx=.05):
    """On steps where James turns (|yaw| >= .5) and an enemy sits off-centre: how often he turns toward it, and
    how often the model's yaw sign matches his on those toward-target turns (overall and at onsets)."""
    import numpy as np
    out = {}
    for label, pick in (("all", lambda i: True), ("onset", lambda i: i >= 3 and all(
            records[i - k]["human_yaw"] is not None and abs(records[i - k]["human_yaw"]) < .5 for k in (1, 2, 3)))):
        turns = [i for i, r in enumerate(records) if r.get("target_dx") is not None and abs(r["target_dx"]) >= min_dx
                 and r["human_yaw"] is not None and abs(r["human_yaw"]) >= .5 and pick(i)]
        toward = [i for i in turns if np.sign(records[i]["human_yaw"]) == np.sign(records[i]["target_dx"])]
        agree = [i for i in toward if np.sign(records[i]["pred_yaw"]) == np.sign(records[i]["human_yaw"])]
        out[label] = {"turns_with_offcentre_target": len(turns), "james_toward_share": len(toward) / max(1, len(turns)),
                      "toward_turns": len(toward), "model_sign_agree_on_toward": len(agree) / max(1, len(toward))}
    return out


def summarize(records):
    """Per-action held accuracy/F1 and press counts; camera MAE against zero and persistence."""
    import numpy as np
    out = {"steps": len(records), "actions": {}}
    for name in SHOWN:
        p = np.array([r["pred_held"][name] for r in records])
        h = np.array([r["human_held"][name] for r in records])
        pp = np.array([r["pred_press"][name] for r in records])
        hp = np.array([r["human_press"][name] for r in records])
        tp = int((p & h).sum())
        f1 = 2 * tp / max(1, int(p.sum() + h.sum()))
        out["actions"][name] = {"held_f1": f1, "pred_held_share": float(p.mean()), "human_held_share": float(h.mean()),
                                "pred_presses": int(pp.sum()), "human_presses": int(hp.sum())}
    for axis in ("yaw", "pitch"):
        pairs = [(r["pred_" + axis], r["human_" + axis]) for r in records if r["human_" + axis] is not None]
        pred, human = map(np.array, zip(*pairs))
        persist = np.abs(human[1:] - human[:-1]).mean()
        moving = np.abs(human) > 0.5
        steps_ = [r for r in records]
        onset = np.array([i >= 3 and r["human_" + axis] is not None and abs(r["human_" + axis]) >= .5 and all(
            steps_[i - k]["human_" + axis] is not None and abs(steps_[i - k]["human_" + axis]) < .5 for k in (1, 2, 3))
            for i, r in enumerate(steps_) if r["human_" + axis] is not None])
        out[axis + "_onset"] = {"steps": int(onset.sum()),
                                "sign_agree": float((np.sign(pred) == np.sign(human))[onset].mean()) if onset.any() else None,
                                "mae": float(np.abs(pred - human)[onset].mean()) if onset.any() else None,
                                "zero_mae": float(np.abs(human)[onset].mean()) if onset.any() else None}
        out[axis] = {"mae": float(np.abs(pred - human).mean()), "zero_mae": float(np.abs(human).mean()),
                     "persistence_mae": float(persist),
                     "moving_mae": float(np.abs(pred - human)[moving].mean()) if moving.any() else None,
                     "moving_zero_mae": float(np.abs(human)[moving].mean()) if moving.any() else None,
                     "moving_sign_agree": float((np.sign(pred) == np.sign(human))[moving].mean()) if moving.any() else None,
                     "moving_steps": int(moving.sum())}
    return out


def draw(frame, r, size=(960, 540)):
    import cv2
    img = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    y0 = 18
    cv2.rectangle(img, (0, 0), (300, 40 + 22 * len(SHOWN) + 70), (0, 0, 0), -1)
    cv2.putText(img, "action   human  model", (8, y0), cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 1)
    for i, name in enumerate(SHOWN):
        y = y0 + 24 + 22 * i
        cv2.putText(img, SHORT[name], (8, y), cv2.FONT_HERSHEY_SIMPLEX, .5, (220, 220, 220), 1)
        for j, (held, press) in enumerate(((r["human_held"][name], r["human_press"][name]),
                                           (r["pred_held"][name], r["pred_press"][name]))):
            x = 110 + 70 * j
            colour = (0, 200, 255) if j == 0 else (80, 255, 80)
            if held or press:
                cv2.rectangle(img, (x, y - 12), (x + 40, y + 2), colour, -1 if held else 2)
            else:
                cv2.rectangle(img, (x, y - 12), (x + 40, y + 2), (90, 90, 90), 1)
    y = y0 + 24 + 22 * len(SHOWN) + 6
    for j, (label, yaw, pitch, colour) in enumerate((("human", r["human_yaw"], r["human_pitch"], (0, 200, 255)),
                                                      ("model", r["pred_yaw"], r["pred_pitch"], (80, 255, 80)))):
        yaw_s = "?" if yaw is None else f"{yaw:+5.1f}"
        pitch_s = "?" if pitch is None else f"{pitch:+5.1f}"
        cv2.putText(img, f"{label} yaw {yaw_s} pitch {pitch_s} deg/step", (8, y + 20 * j),
                    cv2.FONT_HERSHEY_SIMPLEX, .45, colour, 1)
    # Camera arrows at the crosshair: requested rotation over this step, scaled.
    cx, cy = size[0] // 2, size[1] // 2
    for yaw, pitch, colour in ((r["human_yaw"], r["human_pitch"], (0, 200, 255)), (r["pred_yaw"], r["pred_pitch"], (80, 255, 80))):
        if yaw is None:
            continue
        end = (int(cx + 12 * max(-20, min(20, yaw))), int(cy + 12 * max(-20, min(20, pitch or 0))))
        cv2.arrowedLine(img, (cx, cy), end, colour, 2, tipLength=.25)
    cv2.putText(img, f"step {r['index']}  {r['latency_ms']:.0f} ms", (size[0] - 190, 20), cv2.FONT_HERSHEY_SIMPLEX, .5,
                (255, 255, 255), 1)
    return img


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle")
    p.add_argument("steps")
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--start", type=float, help="seconds into an eligible run long enough for --seconds")
    p.add_argument("--device", default="cuda")
    p.add_argument("--out", required=True)
    p.add_argument("--video", action="store_true", help="write overlay.mp4 (960x540, 30 fps)")
    p.add_argument("--targets", action="store_true", help="also run the green-outline finder for the target check")
    a = p.parse_args(argv)
    from policy.live_policy import LivePolicy
    from policy.range_bc import steps, vocab
    session = steps.load(a.steps)
    lo, hi = pick_run(session, a.seconds, a.start)
    rows = session.rows[lo:hi]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    policy = LivePolicy(a.bundle, device=a.device)
    writer = None
    if a.video:
        import cv2
        writer = cv2.VideoWriter(str(out / "overlay.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (960, 540))
    records = []
    video = rows[0]["frame"]["video_path"]
    named = lambda bits: {n: bool(bits[vocab.INDEX[n]]) for n in SHOWN}
    with (out / "steps.jsonl").open("w") as log:
        for row, frame in frames_for(video, rows):
            s = policy.step(frame, t=row["anchor_ns"] / 1e9)      # video time, not replay wall time
            t = steps.target(row, session.calibration)
            r = {"index": s.index, "row": row["i"], "latency_ms": s.latency_ms,
                 "pred_held": {n: s.held[n] for n in SHOWN}, "pred_press": {n: s.press[n] for n in SHOWN},
                 "human_held": named(t["held"]), "human_press": named(t["press"]),
                 "pred_yaw": s.yaw_deg, "pred_pitch": s.pitch_deg, "human_yaw": t["yaw"], "human_pitch": t["pitch"]}
            if a.targets:
                r["target_dx"] = target_bearing(frame)
            records.append(r)
            log.write(json.dumps(r) + "\n")
            if writer is not None:
                writer.write(draw(frame, r))
    if writer is not None:
        writer.release()
    policy.close()
    summary = {"session": session.session_id, "rows": [lo, hi], "bundle": a.bundle, "decoded": len(records),
               "expected": len(rows), **summarize(records)}
    if a.targets:
        summary["target_check"] = target_check(records)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
