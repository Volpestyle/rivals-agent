"""VUH-1314 fragment-boundary accounting for one learned trial's run directory; stdlib only, read-only.

    uv run --offline --no-project python data/benchmarks/galacta-pilot-20260923/fragment_accounting.py <run_dir> [--out <json>]

Reads <run_dir>/frames.jsonl and meta.json as agent/loop.py wrote them. Counts what the tracker -> controller boundary
did on every range step (docs/lanes/tracker.md "The body witness (range mode)") and flags the anomalies after which the
operator stops the pilot and hands back. It infers nothing from pixels: the multi-member ticks it lists are for native
inspection before a verdict is published. Exit 0 = counted, no anomaly; 3 = counted, anomaly (stop); 2 = unreadable log.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

TARGET_REFUSALS = {"unknown_detector", "target_coasting", "target_missing_or_ambiguous", "target_not_measured",
                   "invalid_target"}                       # scripts/range_cast_probe.py TARGET_REFUSALS
STORM_RUN = 5          # consecutive first-consumed decisions refused for a target reason (slot 4 pre-repair: 6, 6)
STORM_SHARE = .25      # or this share of first-consumed decisions refused for a target reason
STALL_S = .5           # a gap this long between logged range steps inside the phase


def kind(trace):
    """A step's body: the witness source, None on a refusal, or no field at all before 0f71336."""
    if "body_observation" not in trace:
        return "no_witness_field"
    body = trace["body_observation"]
    return body.get("source") if body else "none_refused"


def account(run_dir):
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in (run_dir / "frames.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    steps = [(i, r) for i, r in enumerate(rows) if (r.get("range_skill_trace") or {}).get("event") == "step"]
    traces = [r["range_skill_trace"] for _, r in steps]
    witnessed = sum("body_observation" in t for t in traces)
    bodies = [t.get("body_observation") for t in traces]
    measured = [b for b in bodies if b]
    multi = [(i, r) for (i, r), b in zip(steps, bodies) if b and b.get("member_count", 1) > 1]
    saved = [(i, r["t"], r["file"]) for i, r in enumerate(rows) if "file" in r]

    def nearest_file(t):
        return min(saved, key=lambda s: abs(s[1] - t))[2] if saved else None

    firsts, seen = [], set()
    for t in traces:
        d = t.get("decision_id")
        if d is not None and d not in seen:
            seen.add(d)
            firsts.append(t)
    refused_first = [t for t in firsts if not t.get("body_observation") and t.get("reason") in TARGET_REFUSALS]
    run, longest = 0, 0
    for t in firsts:
        run = run + 1 if t in refused_first else 0
        longest = max(longest, run)
    times = [r["t"] for _, r in steps]
    gaps = [round(b - a, 4) for a, b in zip(times, times[1:]) if b - a > STALL_S]
    reasons = Counter(t.get("reason") for t in traces)

    anomalies = []
    if reasons.get("invalid_tracking_observation"):
        anomalies.append(f"invalid_tracking_observation on {reasons['invalid_tracking_observation']} steps")
    if longest >= STORM_RUN or (firsts and len(refused_first) / len(firsts) > STORM_SHARE):
        anomalies.append(f"refusal storm: {len(refused_first)}/{len(firsts)} first-consumed decisions refused for a "
                         f"target reason, longest run {longest}")
    if gaps:
        anomalies.append(f"stall: {len(gaps)} gaps > {STALL_S}s between range steps, max {max(gaps)}s")
    if meta.get("stop") not in ("max_time", "candidate_feed", "range_lost"):   # range_lost is audited per trial (slot 4's was the deadline)
        anomalies.append(f"stop reason {meta.get('stop')!r}")
    if meta.get("errors"):
        anomalies.append(f"{len(meta['errors'])} logged errors")
    if traces and not witnessed:
        verdict = "NOT EXERCISED: this log has no body_observation (runtime before 0f71336)"
    elif multi:
        verdict = "EXERCISED pending native inspection: live steps measured multi-member bodies"
    else:
        verdict = "NOT EXERCISED: no step measured a body with member_count > 1"
    return {
        "kind": "vuh1314_fragment_boundary_accounting", "run_dir": str(run_dir), "stop": meta.get("stop"),
        "range_steps": len(traces), "steps_with_witness_field": witnessed,
        "body_source": dict(Counter(kind(t) for t in traces).most_common()),
        "member_count": dict(sorted(Counter(b.get("member_count") for b in measured).items())),
        "approach_withheld_steps": sum(bool(b.get("approach_withheld")) for b in measured),
        "plate_count": dict(sorted(Counter(b.get("plate_count") for b in measured).items())),
        "reasons": dict(reasons.most_common()),
        "decisions": {"first_consumed": len(firsts),
                      "measured": sum(t.get("body_observation") is not None for t in firsts),
                      "not_measured_by_reason": dict(Counter(t.get("reason") if "body_observation" in t else "no_witness_field"
                                                             for t in firsts if not t.get("body_observation")).most_common())},
        "multi_member_steps": len(multi),
        "inspect": [{"row": i, "t": r["t"], "decision_id": r["range_skill_trace"].get("decision_id"),
                     "bbox": r["range_skill_trace"]["body_observation"]["bbox"],
                     "member_count": r["range_skill_trace"]["body_observation"]["member_count"],
                     "nearest_saved_frame": nearest_file(r["t"])} for i, r in multi[:: max(1, len(multi) // 6)][:6]],
        "boundary_anomalies": anomalies,
        "verdict": verdict,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--out", help="write the report here (refuses to overwrite)")
    a = ap.parse_args(argv)
    try:
        report = account(a.run_dir)
    except (OSError, ValueError, KeyError) as e:
        print(f"unreadable run log: {e!r}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2)
    if a.out:
        with open(a.out, "x", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    print(text)
    return 3 if report["boundary_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
