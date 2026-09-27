"""Fill the replay step table's camera degrees from the camera estimator's replay run (VUH-1353).

    uv run python scripts/replay_camera.py CAMERA_RUN.jsonl [--sources main] [--table T.jsonl] [--out O.jsonl]

Input: the table scripts/replay_steps.py builds (yaw_deg / pitch_deg null everywhere) and one run of
perception/camera_motion.py over the same capture (`video ... --spectator-mask`, no clock offset), as its read()
returns. The degrees go through replay_steps.fill_camera, unchanged: a step gets them only when accepted,
non-withheld pairs tile it, pitch flips to positive-down, beyond_pad_envelope flags the executor's caps.

What this adds:
- `sources`: which estimator pair sources count. Default ("main",): "centre" pairs (the centre-only fits, directional
  but imprecise, ~0.5 deg median error on 1.1-1.3 deg moves, n = 24) leave their step unknown unless opted in.
- A per-row `camera` note: {"source": ...} where the degrees were filled, {"why": ...} where they stay unknown -- the
  first reason the step could not be tiled: no estimator pair, a gap between pairs, a withheld pair (with the
  estimator's own abstain reason: repeated frame, zero flow unconfirmed, window invalid, ...), a source not accepted,
  or a pair without a fit. The mask itself stays the table's (null degrees = unknown); the note is for audit and
  stratification only, never a model input.
- The header records the estimator run (file sha256, camera_motion.py sha256) and the accepted sources in
  calibration.label_sources.camera and source.camera; the output is checked with the step-table contract.
The input table is never modified; the filled table is a new file.
"""
import argparse
import bisect
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import replay_steps as S  # noqa: E402
from perception import camera_motion as cm  # noqa: E402
from policy.range_bc import steps  # noqa: E402

ESTIMATOR = ROOT / "perception" / "camera_motion.py"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def why_unknown(row, pairs, starts, sources):
    """The first reason a step could not be tiled by accepted pairs, mirroring fill_camera's walk; None if it can."""
    a, b = row["anchor_ns"], row["anchor_ns"] + S.STEP_NS
    j = max(0, bisect.bisect_right(starts, a) - 1)
    edge, seen = a, False
    while j < len(pairs) and pairs[j][0] < b:
        c0, c1, s = pairs[j]
        j += 1
        if c1 <= a:
            continue
        seen = True
        if c0 - edge > S.PERIOD_NS:
            return "gap between estimator pairs"
        if s.get("abstain"):
            return f"withheld: {s['abstain']}"
        if s.get("source", "main") not in sources:
            return f"source {s.get('source')!r} not accepted"
        if s.get("yaw_deg") is None or s.get("pitch_deg") is None:
            return "estimator pair without a fit"
        edge = c1
    if not seen:
        return "no estimator pair"
    if b - edge > S.PERIOD_NS or edge <= a:
        return "gap between estimator pairs"
    return None


def fill(header, rows, camera, to_comp, *, capture_video, sources=S.CAMERA_STEP_SOURCES, camera_sha256, estimator_sha256):
    """Fill `rows` in place through replay_steps.fill_camera, add the per-row notes and the header provenance.
    Returns a report {filled, unknown, why}."""
    meta, camera_steps = camera
    records = [s if isinstance(s, dict) else vars(s) for s in camera_steps]
    filled = S.fill_camera(rows, (meta, records), to_comp, capture_video=capture_video, sources=tuple(sources))
    pairs = sorted((to_comp(s["t0"]), to_comp(s["t1"]), s) for s in records)
    starts = [p[0] for p in pairs]
    why = {}
    for r in rows:
        if r["yaw_deg"] is not None:
            srcs = sorted({p[2].get("source", "main") for p in pairs
                           if p[1] > r["anchor_ns"] and p[0] < r["anchor_ns"] + S.STEP_NS})
            r["camera"] = {"source": "+".join(srcs)}
        else:
            reason = why_unknown(r, pairs, starts, sources) or "not tiled"
            r["camera"] = {"why": reason}
            why[reason] = why.get(reason, 0) + 1
    label = (f"perception/camera_motion.py@{estimator_sha256[:12]} replay run over this capture "
             f"({Path(str(meta.get('video'))).name}, spectator mask); pairs from sources {list(sources)} only; "
             "withheld or unaccepted pairs leave a step unknown; filled by scripts/replay_camera.py through "
             "scripts/replay_steps.py fill_camera")
    header["calibration"]["label_sources"]["camera"] = label
    header.setdefault("source", {})["camera"] = {
        "run_sha256": camera_sha256, "estimator_sha256": estimator_sha256, "sources": list(sources),
        "builder": {"path": "scripts/replay_camera.py", "sha256": sha256(__file__)}}
    return {"rows": len(rows), "filled": filled, "unknown": len(rows) - filled, "why": why, "sources": list(sources)}


def check(header, rows):
    steps.check_replay_header(header)
    for k, r in enumerate(rows):
        steps.check_replay_row(r, header, k)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("camera_run")
    ap.add_argument("--table", default=str(S.OUT / f"{S.CAPTURE}.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--sources", nargs="+", default=list(S.CAMERA_STEP_SOURCES))
    a = ap.parse_args(argv)
    table = Path(a.table)
    lines = table.read_text(encoding="utf-8").splitlines()
    header, rows = json.loads(lines[0]), [json.loads(x) for x in lines[1:]]
    meta, camera_steps = cm.read(a.camera_run)
    clock = S.capture_clock()
    to_comp = S.FileToComposition([(v[2] / 1000, v[0]) for v in clock.values()])
    capture_video = rows[0]["frame"]["video_path"] if rows else ""
    report = fill(header, rows, (meta, camera_steps), to_comp, capture_video=capture_video, sources=a.sources,
                  camera_sha256=sha256(a.camera_run), estimator_sha256=sha256(ESTIMATOR))
    check(header, rows)
    out = Path(a.out) if a.out else table.with_name(table.stem + ".camera.jsonl")
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(header) + "\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    report["out"] = {"path": str(out), "sha256": sha256(out)}
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
