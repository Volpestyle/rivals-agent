"""Read the followed player's HUD off a replay's extracted frames and write the output contract.

    uv run --group perception python scripts/replay_hud_run.py [--replay data/demos/replays/daymr-20260923-004325]
        [--follow B5] [--teamup-s 15] [--out data/replay-hud/<replay name>]

Frames and their file times come from the replay folder's classify.json (one row per extracted keyframe). The column
order is identified from the frames (perception.replay_hud.identify_order) or the run stops. Writes, under --out
(data/: derived from third-party footage):
- rows.jsonl: the per-frame table, one JSON row per (t, ability): t, ability, state, numeral, confidence, reason;
- events.json: {"events": [{t, t_lo, t_hi, precision, ability, count, basis}], "coverage": {ability: [[a, b]]},
  "flags": [...], "order": ..., "summary": ...}.
Unknown rows are kept: they are the abstentions, and "no event" means "no cast" only inside `coverage`.
"""
import argparse
import collections
import dataclasses
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from perception import replay_hud as rh  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--replay", default=str(ROOT / "data" / "demos" / "replays" / "daymr-20260923-004325"))
    ap.add_argument("--follow", default="B5")
    ap.add_argument("--teamup-s", type=float, default=rh.TEAMUP_S["symbiote_bond"],
                    help="the source's team-up cooldown (DayMR shows Symbiote Bond: 15 s)")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    replay = Path(a.replay)
    out = Path(a.out) if a.out else ROOT / "data" / "replay-hud" / replay.name
    rows_in = json.loads((replay / "classify.json").read_text(encoding="utf-8"))
    # every other keyframe; the module itself keeps only frames following a.follow with the timeline down
    ident = rh.identify_order((cv2.imread(str(replay / r["file"])) for r in rows_in[::2]), source="replay",
                              follow=a.follow)
    if ident["order"] is None:
        print(f"REFUSED: column order not identified: {ident['why']}")
        return 2
    rows = []
    for r in rows_in:
        rows += rh.read_frame(cv2.imread(str(replay / r["file"])), r["t"], ident["order"], source="replay",
                              follow=a.follow)
    events, coverage, flags = rh.cast_events(rows, cooldowns={"teamup": a.teamup_s}, min_run=1)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "rows.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(dataclasses.asdict(r)) + "\n")
    reasons = collections.Counter(r.reason for r in rows if r.ability == "teamup" and r.state == "unknown")
    summary = {
        "frames": len(rows_in), "frames_read": sum(1 for r in rows if r.ability == "ult" and r.state != "unknown"),
        "abstained_by_reason": dict(reasons),
        "events_by_ability_basis": {f"{k[0]}/{k[1]}": v for k, v in
                                    collections.Counter((e.ability, e.basis) for e in events).items()},
        "casts_by_ability": dict(collections.Counter({e.ability: 0 for e in events}) +
                                 collections.Counter({})) or {},
        "coverage_s": {k: round(sum(b - a_ for a_, b in v), 1) for k, v in coverage.items()},
        "median_precision_s": {ab: round(sorted(e.precision for e in events if e.ability == ab)[
            len([e for e in events if e.ability == ab]) // 2], 3) for ab in {e.ability for e in events}},
    }
    casts = collections.Counter()
    for e in events:
        casts[e.ability] += e.count
    summary["casts_by_ability"] = dict(casts)
    doc = {"replay": str(replay), "follow": a.follow, "order": ident, "teamup_s": a.teamup_s,
           "events": [{"t": round(e.t, 3), "t_lo": round(e.t_lo, 3), "t_hi": round(e.t_hi, 3),
                       "precision": round(e.precision, 3), "ability": e.ability, "count": e.count, "basis": e.basis}
                      for e in events],
           "coverage": {k: [[round(x, 3), round(y, 3)] for x, y in v] for k, v in coverage.items()},
           "flags": flags, "summary": summary}
    (out / "events.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
