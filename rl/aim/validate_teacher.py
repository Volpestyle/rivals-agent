"""Validate the aim teacher (rl/aim/teacher.py) on run-05 and on James's acquisition frames. CPU, no game.

  python -m rl.aim.validate_teacher OUT_DIR --run05 RESULT_JSON [--per-session 40]

run-05: every pulse the compat aimer sent, against the teacher's label on the observation that authorised it (same
target id, same frame). The axis signs must agree: yaw + right = stick +; pitch + down = stick - (camera_compat
`command`). This checks the teacher's sign conventions, not its skill.

James: steps inside his engagement-onset windows (rl/labels/kill_windows_20260930.json, the 2 s before the first hit
of each engagement, when he is bringing the crosshair onto a bot), train/dev sessions only (no val, nothing sealed:
steps.load with intake's denylist). Each sampled step's native frame is decoded from his recording; the teacher picks
the outline nearest the crosshair. James's turn is his summed mouse yaw/pitch over the next TURN_STEPS steps.
Reported: sign agreement where the teacher asks for a turn and James turned at least MIN_TURN_DEG; the per-step gain
that matches his mean rate (least squares through the origin, and the median ratio); how often a target is visible.
A contact sheet shows a sample: teacher box and arrow (green), James's turn (orange).
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
from pathlib import Path

import numpy as np

from rl.aim import teacher as T

TURN_STEPS = 10           # 0.33 s of James's mouse after the frame
MIN_TURN_DEG = 1.0
KILL_WINDOWS = Path("rl/labels/kill_windows_20260930.json")


def run05(result_json, size_check=True):
    r = json.loads(Path(result_json).read_text())
    ev = r["events"]
    obs = {e["t"]: e for e in ev if e.get("event") == "observe"}
    rows = []
    for e in ev:
        if e.get("event") != "pulse":
            continue
        o = obs.get(e["proof_t"])
        box = next((d["bbox"] for d in (o or {}).get("detections", []) if d.get("id") == e["target"]), None)
        if box is None:
            continue
        lab = T.label(box, tuple(o["size"]))
        axis = e["axis"]
        want = np.sign(e["value"]) * (1 if axis == 0 else -1)
        rows.append({"t": e["t"], "axis": axis, "value": e["value"], "teacher_step_deg": lab.step_deg[axis],
                     "agree": bool(np.sign(lab.step_deg[axis]) == want)})
    return {"pulses": len(rows), "sign_agree": round(sum(x["agree"] for x in rows) / max(1, len(rows)), 3),
            "rows": rows}


def decode(video, pts_s):
    import cv2
    out = subprocess.run(["ffmpeg", "-v", "error", "-threads", "2", "-ss", f"{pts_s:.3f}", "-i", video,
                          "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True).stdout
    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)


def james_samples(per_session, seed=0, late=None):
    from policy.range_bc import steps
    windows = json.loads(KILL_WINDOWS.read_text())["sessions"]
    deny = steps.load_denylist()
    rng = random.Random(seed)
    out = []
    for sid, w in windows.items():
        path = Path("data/human/sessions") / sid / f"{sid}.steps.jsonl"
        if not path.exists():
            continue
        s = steps.load(path, denylist=deny)
        if s.split != "train":
            continue
        cal = s.header["calibration"]
        spans = w["onset_windows_ns"]
        rows = s.rows
        cand = []
        j = 0
        for k, r in enumerate(rows[:-TURN_STEPS]):
            while j < len(spans) and spans[j][1] < r["anchor_ns"]:
                j += 1
            lo, hi = (spans[j] if j < len(spans) else (0, -1))
            if late is not None and j < len(spans):          # only the end of the window, just before the first hit
                lo, hi = max(lo, hi - int(late[0] * 1e9)), hi - int(late[1] * 1e9)
            if j < len(spans) and lo <= r["anchor_ns"] <= hi and r["regime"] == "normal":
                nxt = rows[k:k + TURN_STEPS]
                if all(x["relative_known"] and x["run"] == r["run"] for x in nxt):
                    cand.append(k)
        picks, last = [], -10 ** 9
        for k in sorted(rng.sample(cand, min(len(cand), per_session * 4))):
            if k - last >= 15:                       # at least 0.5 s apart
                picks.append(k)
                last = k
        for k in rng.sample(picks, min(per_session, len(picks))):
            r = rows[k]
            tg = [steps.target(x, cal) for x in rows[k:k + TURN_STEPS]]
            out.append({"session": sid, "step": k, "video": r["frame"]["video_path"],
                        "pts_s": r["frame"]["pts"] * r["frame"]["timebase"][0] / r["frame"]["timebase"][1],
                        "yaw_sum": sum(t["yaw"] for t in tg), "pitch_sum": sum(t["pitch"] or 0. for t in tg)})
    return out


def james(per_session, sheet_path=None, finder=None, late=None):
    finder = finder or T.default_finder()
    teacher = T.Teacher(finder=finder)
    samples = james_samples(per_session, late=late)
    rows, thumbs = [], []
    for s in samples:
        frame = decode(s["video"], s["pts_s"])
        if frame is None:
            continue
        # Samples are disconnected, so reset tracking but keep the dataset's
        # frame-level abstention rules (notably spawn-door rejection).
        teacher.reset()
        lab = teacher(frame)
        row = {**{k: s[k] for k in ("session", "step", "pts_s", "yaw_sum", "pitch_sum")}, "target": lab is not None}
        if lab is not None:
            row.update(err_px_1280=[round(v, 1) for v in lab.err_px_1280], angle_deg=[round(v, 2) for v in lab.angle_deg],
                       step_deg=[round(v, 3) for v in lab.step_deg])
            if len(thumbs) < 24:
                thumbs.append(_thumb(frame, lab.box, lab, s))
        rows.append(row)
    if sheet_path and thumbs:
        import cv2
        grid = [np.hstack(thumbs[i:i + 4] + [np.zeros_like(thumbs[0])] * (4 - len(thumbs[i:i + 4])))
                for i in range(0, len(thumbs), 4)]
        cv2.imwrite(str(sheet_path), np.vstack(grid))
    return summarise(rows)


def summarise(rows):
    seen = [r for r in rows if r["target"]]
    out = {"samples": len(rows), "target_visible": round(len(seen) / max(1, len(rows)), 3)}
    rng = np.random.default_rng(0)
    for axis, key in ((0, "yaw"), (1, "pitch")):
        ask = [r for r in seen if r["step_deg"][axis] != 0]
        turned = [r for r in ask if abs(r[f"{key}_sum"]) >= MIN_TURN_DEG]
        agree = [r for r in turned if np.sign(r[f"{key}_sum"]) == np.sign(r["step_deg"][axis])]
        shuffled = rng.permutation([r[f"{key}_sum"] for r in turned]) if turned else []
        control = (float(np.mean([np.sign(v) == np.sign(r["step_deg"][axis]) for v, r in zip(shuffled, turned)]))
                   if turned else None)
        a = np.array([r["angle_deg"][axis] for r in ask])
        rate = np.array([r[f"{key}_sum"] / TURN_STEPS for r in ask])
        same = (np.sign(a) == np.sign(rate)) & (np.abs(a) > 0)
        out[key] = {"teacher_asks": len(ask), "james_turned": len(turned),
                    "sign_agree": round(len(agree) / max(1, len(turned)), 3),
                    "sign_agree_shuffled_control": round(control, 3) if control is not None else None,
                    "gain_lsq": round(float((a * rate).sum() / max((a * a).sum(), 1e-9)), 3) if len(ask) else None,
                    "gain_median_ratio": round(float(np.median(rate[same] / a[same])), 3) if same.any() else None,
                    "gain_median_ratio_scope": "same-sign subset only; not a validated gain",
                    "gain_same_sign_samples": int(same.sum()),
                    "gain_median_signed_ratio": round(float(np.median(rate / a)), 3) if len(ask) else None,
                    "corr": (round(float(np.corrcoef(a, rate)[0, 1]), 3)
                             if len(ask) > 2 and a.std() > 0 and rate.std() > 0 else None)}
    out["rows"] = rows
    return out


def _thumb(frame, box, lab, s, w=480):
    import cv2
    k = w / frame.shape[1]
    img = cv2.resize(frame, (w, int(frame.shape[0] * k)))
    cx, cy = img.shape[1] // 2, img.shape[0] // 2
    cv2.rectangle(img, (int(box[0] * k), int(box[1] * k)), (int(box[2] * k), int(box[3] * k)), (0, 255, 0), 2)
    scale = 8.                                           # px per degree, for the arrows only
    cv2.arrowedLine(img, (cx, cy), (int(cx + lab.angle_deg[0] * scale), int(cy + lab.angle_deg[1] * scale)),
                    (0, 255, 0), 2, tipLength=.2)
    cv2.arrowedLine(img, (cx, cy), (int(cx + s["yaw_sum"] * scale), int(cy + s["pitch_sum"] * scale)),
                    (0, 140, 255), 2, tipLength=.2)
    cv2.putText(img, f"{s['session'][9:15]} {s['pts_s']:.1f}s", (6, 18), 0, .5, (255, 255, 255), 1)
    return img


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--run05")
    ap.add_argument("--per-session", type=int, default=40)
    ap.add_argument("--late", help="'A,B': sample only A..B s before each engagement's first hit (e.g. 0.6,0.1)")
    ap.add_argument("--tag", default="", help="suffix for the output files")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {"teacher": {"gain": T.GAIN, "focal_1280": T.FOCAL_1280, "deadband_px_1280": T.DEADBAND_PX_1280},
              "turn_steps": TURN_STEPS, "min_turn_deg": MIN_TURN_DEG}
    if a.run05:
        result["run05"] = run05(a.run05)
        print("run05", {k: v for k, v in result["run05"].items() if k != "rows"}, flush=True)
    late = tuple(float(v) for v in a.late.split(",")) if a.late else None
    result["late_window_s"] = late
    result["james"] = james(a.per_session, out / f"teacher_james_sheet{a.tag}.jpg", late=late)
    print("james", json.dumps({k: v for k, v in result["james"].items() if k != "rows"}), flush=True)
    (out / f"teacher_validation_20260930{a.tag}.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


if __name__ == "__main__":
    main()
