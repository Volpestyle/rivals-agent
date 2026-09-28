"""Fixed-source, CPU-only turn audit. Select metadata, then decode separate passes."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
PRIOR = runpy.run_path(str(ROOT / "docs/research/nitrogen-yaw-audit/audit.py"))
SOURCES = PRIOR["SOURCES"]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def candidates(rows, period, scale):
    half = round(0.5e9 / period)
    second = 2 * half
    window = deque(maxlen=3 * second + 1)
    found = []
    for row in rows:
        window.append(row)
        if len(window) != window.maxlen:
            continue
        w = list(window)
        if not all(r["suitability"] == "accepted" and r["regime"] == "normal"
                   and r["gap_free"] and r["relative_known"] for r in w):
            continue
        if any(b["anchor_ns"] - a["anchor_ns"] != period or b["run"] != a["run"]
               or b["i"] != a["i"] + 1 for a, b in zip(w, w[1:])):
            continue
        before = sum(abs(r["mouse_dx"] * scale) for r in w[second-half:second])
        yaw = [r["mouse_dx"] * scale for r in w[second:second+half]]
        net, total = sum(yaw), sum(map(abs, yaw))
        if before > 2 or abs(net) < 10 or abs(net) < .8 * total:
            continue
        found.append({"center": w[second]["i"], "direction": "left" if net < 0 else "right",
                      "yaw_next_half_s": net, "absolute_yaw_next_half_s": total,
                      "absolute_yaw_previous_half_s": before,
                      "frames": [{"offset_rows": j-second, **w[j]} for j in
                                 (0, half, second, second+half, 2*second, 3*second)]})
    return found


def choose(found, period):
    selected = []
    # First then last in each direction; all accepted events stay >=10 seconds apart.
    for direction in ("left", "right"):
        pool = [e for e in found if e["direction"] == direction]
        for sequence in (pool, list(reversed(pool))):
            item = next((e for e in sequence if all(
                abs(e["center"] - a["center"]) * period >= 10e9 for a in selected)), None)
            if item is not None:
                selected.append(item)
    return sorted(selected, key=lambda e: e["center"])


def select():
    from policy.range_bc import steps
    from scripts.job_status import write
    peak = PRIOR["limits"]()
    write("intent-target-audit-20260928", owner="explore-policy", host="pc", stage="running",
          progress="metadata selection", evidence=str(HERE / "selection.json"))
    registry_path = ROOT / "data/human/session-splits.corpus.json"
    tally_path = ROOT / "data/human/sessions/tally.json"
    registry = {r["session_id"]: r for r in json.loads(registry_path.read_text())["sessions"]}
    admitted = {r["session"] for r in json.loads(tally_path.read_text())["rows"]
                if r.get("status") == "admitted" and r.get("split") == "train"}
    denylist = steps.load_denylist()
    result = {"tag": "EXPLORATORY", "plan_sha256": digest(HERE / "plan.md"),
              "script_sha256": digest(__file__), "created_unix": time.time(),
              "registry_sha256": digest(registry_path), "tally_sha256": digest(tally_path),
              "steps_source_sha256": digest(ROOT / "policy/range_bc/steps.py"), "sessions": []}
    for sid, (media_sha, video, _) in SOURCES.items():
        assert sid in admitted and registry[sid]["split"] == "train"
        assert registry[sid]["expected_media_sha256"] == media_sha
        steps.check_sealed(sid, media_sha, denylist)
        path = ROOT / "data/human/sessions" / sid / (sid + ".steps.jsonl")
        with path.open(encoding="utf-8") as stream:
            head = json.loads(next(stream))
            assert (head["session_id"], head["split"], head["media_sha256"]) == (sid, "train", media_sha)
            found = candidates((json.loads(line) for line in stream), head["step_ns"],
                               head["calibration"]["yaw_deg_per_count"])
        picked = choose(found, head["step_ns"])
        for event in picked:
            event["id"] = "E%02d" % (1 + sum(len(s["events"]) for s in result["sessions"]) + picked.index(event))
            for row in event["frames"]:
                assert Path(row["frame"]["video_path"]).resolve() == Path(video).resolve()
                assert row["frame"]["composition_ns"] <= row["anchor_ns"]
        info = Path(video).stat()
        result["sessions"].append({"session": sid, "media_sha256_from_admission": media_sha,
            "media_rehashed": False, "video": video, "video_bytes": info.st_size,
            "video_mtime_ns": info.st_mtime_ns, "header": head, "steps_sha256": digest(path),
            "candidate_windows": {d: sum(e["direction"] == d for e in found) for d in ("left", "right")},
            "events": picked})
        print(json.dumps({"session": sid, "events": len(picked)}), flush=True)
        peak()
    result["peak_working_set_bytes"] = peak()
    save(HERE / "selection.json", result)
    write("intent-target-audit-20260928", stage="done", progress="selection pinned; no pixels read")


def decode(phase):
    import av
    import cv2
    import numpy as np
    from policy.range_bc import steps
    from scripts.job_status import write
    peak = PRIOR["limits"]()
    cv2.setNumThreads(2)
    selection = json.loads((HERE / "selection.json").read_text())
    assert digest(HERE / "plan.md") == selection["plan_sha256"]
    if phase == "oracle":
        assert (HERE / "causal-annotations.json").is_file()
        assert (HERE / "causal-freeze.json").is_file()
        freeze = json.loads((HERE / "causal-freeze.json").read_text())
        assert digest(HERE / "causal-annotations.json") == freeze["sha256"]
    destination = HERE / phase
    destination.mkdir(exist_ok=False)
    write("intent-target-audit-20260928-" + phase, owner="explore-policy", host="pc",
          stage="running", evidence=str(destination / "receipt.json"), progress="bounded native seeks")
    receipts = []
    started = time.monotonic()
    denylist = steps.load_denylist()
    for session in selection["sessions"]:
        sid = session["session"]
        media_sha, video, _ = SOURCES[sid]
        assert video == session["video"] and media_sha == session["media_sha256_from_admission"]
        steps.check_sealed(sid, media_sha, denylist)
        info = Path(video).stat()
        assert (info.st_size, info.st_mtime_ns) == (session["video_bytes"], session["video_mtime_ns"])
        for event in session["events"]:
            panels = []
            rows = [r for r in event["frames"] if (r["offset_rows"] <= 0) == (phase == "causal")]
            with av.open(video) as reader:
                stream = reader.streams.video[0]
                stream.thread_count = 2
                reader.seek(rows[0]["frame"]["pts"], stream=stream, backward=True, any_frame=False)
                frames = reader.decode(stream)
                current = None
                for n, row in enumerate(rows):
                    pts = row["frame"]["pts"]
                    while current is None or current.pts < pts:
                        current = next(frames)
                    assert current.pts == pts
                    assert [stream.time_base.numerator, stream.time_base.denominator] == row["frame"]["timebase"]
                    native = current.to_ndarray(format="bgr24")
                    assert [native.shape[1], native.shape[0]] == session["header"]["video_size"]
                    path = destination / (event["id"] + f"-{n}.jpg")
                    assert cv2.imwrite(str(path), native, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    offset = row["offset_rows"] * session["header"]["step_ns"] / 1e9
                    panel = cv2.resize(native, (960, 540))
                    cv2.rectangle(panel, (0, 0), (960, 32), (0, 0, 0), -1)
                    cv2.putText(panel, f"{event['id']} {phase.upper()} t={offset:+.2f}s", (8, 24),
                                cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 1)
                    panels.append(panel)
                    receipts.append({"event": event["id"], "path": path.relative_to(HERE).as_posix(),
                        "sha256": digest(path), "row": row["i"], "pts": pts, "decoded_pts": current.pts,
                        "timebase": row["frame"]["timebase"], "offset_s": offset,
                        "composition_ns": row["frame"]["composition_ns"], "anchor_ns": row["anchor_ns"]})
                    peak()
            contact = destination / (event["id"] + "-contact.jpg")
            assert cv2.imwrite(str(contact), np.vstack(panels), [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(event["id"], phase, flush=True)
    save(destination / "receipt.json", {"frames": receipts, "selection_sha256": digest(HERE / "selection.json"),
        "script_sha256": digest(__file__), "seconds": time.monotonic()-started,
        "peak_working_set_bytes": peak(), "priority": "BelowNormal", "device": "CPU", "decoder_threads": 2})
    write("intent-target-audit-20260928-" + phase, stage="done", progress="frames ready for inspection")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("select", "causal", "oracle"))
    args = parser.parse_args()
    select() if args.stage == "select" else decode(args.stage)
