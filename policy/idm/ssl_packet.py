"""Small exact-PTS SSL candidate packet; inspection must accept clips separately.

No labels, no automatic gameplay admission. Reuses the Windows PC exception
guards and opens only sources in the pinned whole-file SSL admission.
"""
from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import re

from policy.idm import ssl_sample as S
from policy import idm_targets as T
from scripts.job_status import write


def selected_pts(log, count, stride):
    text = Path(log).read_text(encoding="utf-8")
    bases = re.findall(r"config in time_base: (\d+)/(\d+)", text)
    if not bases or len(set(bases)) != 1:
        raise ValueError("one exact source timebase required")
    tb = tuple(map(int, bases[0]))
    pts = [int(v) for v in re.findall(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:", text)][:count]
    if len(pts) != count or len(set(pts)) != count:
        raise ValueError("missing or duplicate PTS")
    # Integer-millisecond media may alternate 16/17 or 8/9 ms; no invented CFR times.
    for left, right in zip(pts, pts[1:]):
        if abs((right - left) * tb[0] / tb[1] - stride / 120) > tb[0] / tb[1] + 1e-9:
            raise ValueError("source gap or wrong sample stride")
    return tb, pts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("admission", "admission-sha256", "plan", "plan-sha256", "out", "job"):
        parser.add_argument("--" + name, required=True)
    a = parser.parse_args(argv)
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), S.BELOW_NORMAL)
    sources = S.admitted(a.admission, a.admission_sha256)
    if T.sha256(a.plan) != a.plan_sha256:
        raise ValueError("candidate plan pin mismatch")
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8-sig"))
    if plan["admission_sha256"] != a.admission_sha256 or plan["purpose"] != "inspection_candidates_only":
        raise ValueError("candidate plan context mismatch")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    write(a.job, owner="idm-owner", host="pc", stage="running", evidence=str(out / "packet.json"))
    clips = []
    try:
        for n, item in enumerate(plan["clips"]):
            source = next(s for s in sources if s["source_family"] == item["source_family"])
            stride, start = item["stride"], item["start_seconds"]
            if stride not in (2, 15) or not 0 <= start < source["duration_seconds"] - 2:
                raise ValueError("invalid candidate sampling window")
            S.guard()
            S.source_unchanged(source)
            root = out / f"clip-{n:04d}"
            root.mkdir()
            log = root / "decode.log"
            command = ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "2", "-hwaccel", "none",
                       "-ss", str(start), "-copyts", "-i", source["path"], "-an", "-sn", "-dn",
                       "-filter_threads", "2", "-vf",
                       "scdet=threshold=10,metadata=print:key=lavfi.scd.score,"
                       f"select=not(mod(n\\,{stride})),showinfo,scale=256:144:flags=area",
                       "-frames:v", "16", "-fps_mode", "passthrough", "-threads", "2", str(root / "%02d.png")]
            S.bounded_ffmpeg(command, log)
            S.source_unchanged(source)
            files = sorted(root.glob("*.png"))
            if len(files) != 16:
                raise ValueError("exactly 16 frames required")
            tb, pts = selected_pts(log, 16, stride)
            scores = [float(v) for v in re.findall(r"lavfi.scd.score=(\d+(?:\.\d+)?)", log.read_text())]
            if not scores:
                raise ValueError("dense scene-change evidence missing")
            clips.append({**item, "clip_id": root.name, "media_sha256": source["media_sha256"],
                          "timebase": tb, "pts": pts, "eligibility": "pending_inspection",
                          "scene_check": {"method": "ffmpeg scdet on every decoded native frame before selection",
                                          "threshold": 10, "max_score": max(scores),
                                          "dense_frames_checked": len(scores), "pass": max(scores) < 10,
                                          "limit": "cut detector plus human sample inspection; not a proof of no edit"},
                          "frames": [{"path": p.relative_to(out).as_posix(), "sha256": T.sha256(p)} for p in files]})
            write(a.job, progress={"n": n + 1, "total": len(plan["clips"])})
            (out / "progress.json").write_text(json.dumps(clips, indent=2) + "\n")
        (out / "packet.json").write_text(json.dumps({"schema": "rivals-ssl-candidates-v1",
            "admission_sha256": a.admission_sha256, "plan_sha256": a.plan_sha256,
            "semantic_labels": False, "clips": clips}, indent=2) + "\n")
        write(a.job, stage="done")
    except BaseException:
        write(a.job, stage="failed")
        raise


if __name__ == "__main__":
    main()
