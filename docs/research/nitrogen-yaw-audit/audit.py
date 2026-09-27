"""Bounded causal native-frame audit. Fixed admitted TRAIN sources; CPU only."""
import argparse
import ctypes
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
SOURCES = {
    "20260923T200129-346Z-33696-6": (
        "b06621fe4d6de489ac1c78b9557f57cdc4e8f8e641cbe1b35912510c60336f30",
        "C:/Users/volpe/Videos/2026-09-23 15-01-29.mkv", [7469, 11401]),
    "20260925T203745-207Z-49728-2": (
        "666c626d4c285e20b3444081b9a1813d743aec8ab6cb538f134c5b61a265125c",
        "C:/Users/volpe/Videos/2026-09-25 15-37-45.mkv", [40584]),
    "20260926T035932-508Z-63684-14": (
        "7ab6b6083ac9aa38ad5b3ccde866ccb684d79332be42696ab36c2c7030f22494",
        "C:/Users/volpe/Videos/2026-09-25 22-59-32.mkv", [1676]),
}


def limits():
    assert sys.platform == "win32"
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = k32.GetCurrentProcess()
    k32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    assert k32.SetPriorityClass(handle, 0x4000)  # BelowNormal

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ("peak", "working", "qpp", "qp", "qnp", "qn", "pf", "ppf")]

    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = (ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong)

    def peak():
        value = Counters()
        assert fn(handle, ctypes.byref(value), ctypes.sizeof(value))
        assert value.peak < 2.8 * 1024 ** 3, "memory bound exceeded"
        return value.peak

    return peak


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    out = p.parse_args().out
    peak = limits()
    import av
    import cv2
    import numpy as np
    from agent.tracker import Tracker
    from perception.outline import detect, find_enemies
    from policy.range_bc import steps
    from scripts.job_status import write

    cv2.setNumThreads(2)
    out.mkdir(parents=True, exist_ok=False)
    job = "nitrogen-yaw-native-causal-audit"
    write(job, owner="explore-policy", host="pc", stage="running", evidence=str(out / "summary.json"))
    denylist = steps.load_denylist()
    registry = json.loads((ROOT / "data/human/session-splits.corpus.json").read_text(encoding="utf-8"))
    placements = {r["session_id"]: r for r in registry["sessions"]}
    tally = json.loads((ROOT / "data/human/sessions/tally.json").read_text(encoding="utf-8"))
    admitted = {r["session"] for r in tally["rows"] if r.get("status") == "admitted" and r.get("split") == "train"}
    summaries = []
    started = time.monotonic()
    for sid, (media_sha, video, centers) in SOURCES.items():
        assert sid in admitted and placements[sid]["split"] == "train"
        assert placements[sid]["expected_media_sha256"] == media_sha
        steps.check_sealed(sid, media_sha, denylist)
        path = ROOT / "data/human/sessions" / sid / (sid + ".steps.jsonl")
        selected = {}
        wanted = {i for c in centers for i in range(c - 45, c + 45)}
        with path.open(encoding="utf-8") as f:
            head = json.loads(next(f))
            assert head["session_id"] == sid and head["split"] == "train" and head["media_sha256"] == media_sha
            for line in f:
                row = json.loads(line)
                if row["i"] in wanted:
                    assert row["suitability"] == "accepted" and row["regime"] == "normal"
                    assert row["gap_free"] and row["relative_known"]
                    assert Path(row["frame"]["video_path"]).resolve() == Path(video).resolve()
                    selected[row["i"]] = row
        assert set(selected) == wanted
        for center in centers:
            name = sid[:15] + "-i" + str(center)
            dest = out / name
            dest.mkdir()
            rows = [selected[i] for i in range(center - 45, center + 45)]
            assert len({r["run"] for r in rows}) == 1
            assert all(b["anchor_ns"] - a["anchor_ns"] == head["step_ns"] for a, b in zip(rows, rows[1:]))
            tracker = Tracker()
            reader = av.open(video)
            stream = reader.streams.video[0]
            stream.thread_count = 2
            reader.seek(rows[0]["frame"]["pts"], stream=stream, backward=True, any_frame=False)
            frames = reader.decode(stream)
            current = None
            receipts, panels = [], []
            picks = (0, 18, 36, 54, 72, 89)
            for n, row in enumerate(rows):
                pts = row["frame"]["pts"]
                while current is None or current.pts < pts:
                    current = next(frames)
                assert current.pts == pts and [stream.time_base.numerator, stream.time_base.denominator] == row["frame"]["timebase"]
                frame = current.to_ndarray(format="bgr24")
                h, w = frame.shape[:2]
                assert [w, h] == head["video_size"]
                green = find_enemies(frame)
                dets = green if green else detect(frame, mode="red")  # exactly auto fallback
                observation = tracker.observe(dets, float(current.pts * stream.time_base), (w, h), cam=None)
                receipts.append({"i": row["i"], "pts": pts, "decoded_pts": current.pts,
                                 "anchor_ns": row["anchor_ns"], "frame_composition_ns": row["frame"]["composition_ns"],
                                 "human_yaw_label_deg": row["mouse_dx"] * head["calibration"]["yaw_deg_per_count"],
                                 "detector_path": "green" if green else "red-fallback",
                                 "observation": asdict(observation)})
                assert row["frame"]["composition_ns"] <= row["anchor_ns"]
                if n in picks:
                    cv2.imwrite(str(dest / f"{n:03d}-native.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    drawn = frame.copy()
                    for d in observation.raw:
                        x1, y1, x2, y2 = map(int, d.bbox)
                        color = ((int(d.track) * 83) % 180 + 75, 255, 255)
                        cv2.rectangle(drawn, (x1, y1), (x2, y2), color, 3)
                        cv2.putText(drawn, f"ID{d.track}", (x1, max(25, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    panel = cv2.resize(drawn, (960, 540))
                    cv2.rectangle(panel, (0, 0), (960, 35), (0, 0, 0), -1)
                    cv2.putText(panel, f"{name} row{row['i']} +{n/30:.2f}s coast{list(observation.coasting)}",
                                (5, 24), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)
                    panels.append(panel)
                peak()
            reader.close()
            (dest / "tracks.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
            sheet = np.vstack([np.hstack(panels[i:i + 2]) for i in range(0, 6, 2)])
            cv2.imwrite(str(dest / "contact.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 95])
            summary = {"name": name, "session": sid, "center": center, "n": len(rows),
                       "start_i": rows[0]["i"], "end_i": rows[-1]["i"], "video": video,
                       "media_sha256_from_admission": media_sha, "video_rehashed_this_audit": False,
                       "video_bytes": Path(video).stat().st_size, "video_mtime_ns": Path(video).stat().st_mtime_ns,
                       "detection_count": sum(len(r["observation"]["raw"]) for r in receipts),
                       "no_detection_frames": sum(not r["observation"]["raw"] for r in receipts),
                       "unique_track_ids": sorted({d["track"] for r in receipts for d in r["observation"]["raw"]}),
                       "coasting_frames": sum(bool(r["observation"]["coasting"]) for r in receipts),
                       "green_frames": sum(r["detector_path"] == "green" for r in receipts)}
            summaries.append(summary)
            write(job, progress=f"{len(summaries)}/4 causal sequences complete")
            print(json.dumps(summary), flush=True)
    result = {"tag": "EXPLORATORY", "sequences": summaries, "seconds": time.monotonic() - started,
              "peak_working_set_bytes": peak(), "priority": "BelowNormal", "decode_threads": 2,
              "opencv_threads": 2, "device": "CPU", "cam_argument": None,
              "causal": "only current and past detections; no human camera commands or future frames to tracker",
              "selection": "four fixed challenge sequences around already inspected TRAIN anchors; not a random population sample",
              "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
                  "docs/research/nitrogen-yaw-audit/audit.py", "perception/outline.py", "agent/tracker.py", "agent/state.py")}}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write(job, stage="done", progress="4/4 sequences; native visual inspection pending")
    print(json.dumps({"seconds": result["seconds"], "peak_working_set_bytes": result["peak_working_set_bytes"]}))


if __name__ == "__main__":
    main()
