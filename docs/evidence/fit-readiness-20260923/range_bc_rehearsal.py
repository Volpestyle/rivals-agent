"""Range BC cache rehearsal (fit-impl-3): does the Mac's ffmpeg select the same decoded ordinals as the importer's view?

Not admission and not training data: the input is the 2026-09-23 15-47-07 calibration take (HEVC, NVENC), and the
step table it writes is a rehearsal artifact with zero actions and a placeholder calibration.

    probe  --video V --frames-csv F --out probe.json
        The importer's own `probe_video` (ffprobe -show_frames) and `match_frames` in inspection mode (no admission
        anchor: the offset is fitted, which the importer allows only for timing inspection). Records the ffmpeg and
        ffprobe versions, the decoded pts list's sha256, the fitted muxer offset and the residual, per machine.
    steps  --probe probe.json --out steps.jsonl
        A rehearsal `rivals-range-steps-v1` table: 30 Hz anchors on the composition clock, each anchor's frame the
        last composition time <= anchor, FrameRefs exactly as the importer builds them (ordinal, decoded pts).
    compare A.json B.json
        Exit 0 only when both machines decoded the same pts list and matched frames.csv with the same offset.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent import human_demos as hd  # noqa: E402
from policy.range_bc import fixture, steps, vocab  # noqa: E402

STEP_NS = 33_333_333


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def packets(frames_csv):
    with open(frames_csv, newline="", encoding="utf-8") as f:
        return [{k: int(v) for k, v in row.items()} for row in csv.DictReader(f)]


def version(tool):
    return subprocess.run([tool, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]


def probe(a):
    decoded = hd.probe_video(a.video)
    refs, info = hd.match_frames(packets(a.frames_csv), decoded, a.video, inspection_only=True)
    out = {"machine": __import__("platform").platform(), "ffmpeg": version("ffmpeg"), "ffprobe": version("ffprobe"),
           "video": str(a.video), "video_sha256": sha256(a.video), "frames_csv_sha256": sha256(a.frames_csv),
           "timebase": [decoded["timebase_num"], decoded["timebase_den"]], "decoded_frames": len(decoded["pts"]),
           "pts_sha256": hashlib.sha256(json.dumps(decoded["pts"]).encode()).hexdigest(),
           "match": {k: v for k, v in info.items()},
           "refs": [[r.frame_index, r.pts, r.composition_ns] for r in refs]}
    Path(a.out).write_text(json.dumps(out), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("ffmpeg", "decoded_frames", "pts_sha256")} | {"match": out["match"]}))


def build_steps(a):
    p = json.loads(Path(a.probe).read_text(encoding="utf-8"))
    refs = p["refs"]
    comp = [c for _, _, c in refs]
    period = 1_000_000_000 // 120
    header = fixture.header_for("rehearsal-calibration-204707", split="train", sitting="rehearsal")
    header.update(media_sha256=p["video_sha256"], video_size=[2560, 1440], settings_hash="rehearsal",
                  patch="rehearsal", source={"rehearsal": True, "probe_pts_sha256": p["pts_sha256"]})
    rows, run, anchor, j, broken = [], 0, comp[0], 0, False
    zero = [0] * vocab.N
    while anchor + STEP_NS < comp[-1]:
        while j + 1 < len(comp) and comp[j + 1] <= anchor:
            j += 1
        if anchor - comp[j] > 2 * period:          # a stale frame: no row, and the run ends (intake's gap rule)
            broken, anchor = True, anchor + STEP_NS
            continue
        if broken and rows:
            run, broken = run + 1, False
        ordinal, pts, c = refs[j]
        rows.append({"i": len(rows), "run": f"r{run}", "anchor_ns": anchor,
                     "frame": {"video_path": p["video"].replace("\\", "/"), "frame_index": ordinal, "pts": pts,
                               "timebase": p["timebase"], "composition_ns": c},
                     "gap_free": True, "segment": "rehearsal", "suitability": "accepted", "regime": "normal",
                     "tags": [], "tag_source": "untagged", "held_start": zero, "held_end": zero,
                     "held_known": [True] * vocab.N, "press": zero, "release": zero, "mouse_dx": 0,
                     "mouse_dy": 0, "relative_known": True, "wheel_v": 0, "wheel_h": 0, "unsupported": {}})
        anchor += STEP_NS
    path = fixture.write(a.out, header, rows)
    s = steps.load(path, denylist=steps.load_denylist())
    print(json.dumps({"rows": len(s.rows), "runs": len({r["run"] for r in s.rows}), "sha256": s.sha256}))


def compare(a):
    x, y = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (a.a, a.b))
    same = {k: x[k] == y[k] for k in ("video_sha256", "frames_csv_sha256", "timebase", "decoded_frames", "pts_sha256")}
    same["fitted_offset"] = (x["match"]["muxer_offset_num"], x["match"]["muxer_offset_den"]) == \
        (y["match"]["muxer_offset_num"], y["match"]["muxer_offset_den"])
    same["refs"] = x["refs"] == y["refs"]
    print(json.dumps({"same": same, "a": x["ffmpeg"], "b": y["ffmpeg"]}))
    sys.exit(0 if all(same.values()) else 1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("probe")
    q.add_argument("--video", required=True)
    q.add_argument("--frames-csv", required=True)
    q.add_argument("--out", required=True)
    q = sub.add_parser("steps")
    q.add_argument("--probe", required=True)
    q.add_argument("--out", required=True)
    q = sub.add_parser("compare")
    q.add_argument("a")
    q.add_argument("b")
    a = p.parse_args()
    {"probe": probe, "steps": build_steps, "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    main()
