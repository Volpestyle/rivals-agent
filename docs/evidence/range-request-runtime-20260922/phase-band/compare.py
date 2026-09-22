"""Bounded clock-only scheduler comparison. No States, targets or model imports."""
from bisect import bisect_left, bisect_right
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
LOG = ROOT / "data/l1/range-request-diagnostic-20260922-1/frames.jsonl"
EXPECTED = "f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec"
PERIOD, TOL, EPS = .1, .025, 1e-9  # same history arithmetic epsilon as event_window


def choose(clocks, mode):
    origin = clocks[0]
    slots = list(range(math.floor((clocks[-1] - origin) / PERIOD) + 1))
    chosen, skipped = [], []
    if mode == "current_relative90":
        previous = -float("inf")
        for i, t in enumerate(clocks):
            if t - previous >= .09:
                chosen.append({"clock_index": i, "t": t, "offer_t": t, "slot": None})
                previous = t
        return chosen, None, slots
    used = set()
    for slot in slots:
        phase = origin + slot * PERIOD
        if mode in ("naive_after", "band_after"):
            i = bisect_left(clocks, phase)
            if i == len(clocks) or clocks[i] >= phase + PERIOD:
                skipped.append({"slot": slot, "reason": "no_acquisition_in_slot"})
                continue
            t, offer = clocks[i], clocks[i]
            if mode == "band_after" and t > phase + TOL:
                skipped.append({"slot": slot, "reason": "first_acquisition_late", "t": t, "offset_ms": (t-phase)*1000})
                continue
        else:
            i = bisect_right(clocks, phase) - 1
            t = clocks[i]
            if t < phase - TOL:
                skipped.append({"slot": slot, "reason": "latest_acquisition_too_old", "t": t, "offset_ms": (t-phase)*1000})
                continue
            offer = phase if mode == "band_before_timer" else clocks[bisect_left(clocks, phase)]
        assert i not in used  # one actual acquisition cannot fill multiple slots
        used.add(i)
        chosen.append({"clock_index": i, "t": t, "offer_t": offer, "slot": slot,
                       "phase_t": phase, "phase_residual_ms": (t-phase)*1000})
    return chosen, skipped, slots


def history_counts(selected):
    """Consumer clock rules only: adjacent reset before append; failed window clears."""
    history, previous, counts = deque(maxlen=5), None, Counter()
    checks, reset_slots = [], []
    for index, row in enumerate(selected):
        t = row["t"]
        gap = t - previous if previous is not None else None
        if gap is not None and abs(gap - PERIOD) > TOL + EPS:
            history.clear()
            counts["adjacent_resets"] += 1
            reset_slots.append(row["slot"])
        previous = t
        history.append(t)
        residuals = [(s - (t - (4-i)*PERIOD))*1000 for i, s in enumerate(history)] if len(history) == 5 else []
        if len(history) < 5:
            reason = "clock_warmup"
        elif any(abs(v) > TOL*1000 + EPS*1000 for v in residuals):
            reason = "clock_invalid_history"
            history.clear()
        else:
            assert all(a < b and abs(b-a-PERIOD) <= TOL+EPS for a,b in zip(history, list(history)[1:]))
            reason = "clock_usable"
        counts[reason] += 1
        checks.append({"selected_index_1based": index+1, "slot": row["slot"], "t": t,
                       "reason": reason, "gap_ms": gap*1000 if gap is not None else None,
                       "residual_ms": residuals})
    return {"counts": dict(counts), "reset_slots": reset_slots, "checks": checks}


def summarize(values):
    ordered = sorted(values)
    return {"min": min(values), "median": statistics.median(values),
            "p95_nearest_rank": ordered[math.ceil(.95*len(ordered))-1], "max": max(values)}


def controls():
    # Exact band endpoint is admitted; just beyond it is skipped, with no catchup.
    clocks = [i*PERIOD + (TOL if i in (1,3) else TOL+1e-7 if i == 2 else 0.) for i in range(9)]
    selected, missed, _ = choose(clocks, "band_after")
    assert 1 in [r["slot"] for r in selected] and [r["slot"] for r in missed] == [2]
    result = history_counts(selected)
    assert result["counts"].get("clock_invalid_history", 0) == 0
    assert result["counts"]["adjacent_resets"] == 1
    assert next(r["slot"] for r in result["checks"] if r["reason"] == "clock_usable") == 7
    # Arbitrary long stall: slots1..4 are missed; .531 is too late for slot5.
    selected, missed, _ = choose([0., .531, *(i*PERIOD for i in range(6,11))], "band_after")
    assert [r["slot"] for r in missed] == [1,2,3,4,5]
    assert selected[1]["t"] == 6*PERIOD and history_counts(selected)["counts"]["adjacent_resets"] == 1
    # Legal adjacent intervals alone are insufficient for five-step geometry.
    unbounded = [{"t": t, "slot": i} for i,t in enumerate([0., .11, .22, .33, .44])]
    assert history_counts(unbounded)["counts"]["clock_invalid_history"] == 1
    # Consecutive retained slot offsets at BOTH band endpoints satisfy geometry.
    endpoints = [{"t": i*.1 + (TOL if i%2 else 0.), "slot": i} for i in range(9)]
    assert history_counts(endpoints)["counts"] == {"clock_warmup": 4, "clock_usable": 5}
    # The causal-before clock can precede the phase; it cannot use a future frame.
    selected, _, _ = choose([0., .08, .101, .18, .205], "band_before_timer")
    assert selected[1]["t"] == .08 and selected[1]["offer_t"] == .1
    return {"exact25ms_included_25ms_plus100ns_skipped": True,
            "missing_slots_reset_without_catchup": True, "arbitrary_stall_skips_old_slots": True,
            "legal_pair_gaps_can_fail_geometry": True, "consecutive_width25ms_offsets_pass": True,
            "before_phase_never_chooses_future": True}


def main():
    data = LOG.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED
    rows = [json.loads(line) for line in data.splitlines()]
    clocks = [r["send_result"]["observation_t"] for r in rows if "send_result" in r]
    assert len(clocks) == 369 and all(a < b for a,b in zip(clocks, clocks[1:]))
    results = {}
    for mode in ("current_relative90", "naive_after", "band_after", "band_before_timer", "band_before_reflex"):
        selected, missed, slots = choose(clocks, mode)
        timing = history_counts(selected)
        ages = [(r["offer_t"]-r["t"])*1000 for r in selected]
        results[mode] = {"eligible_acquisitions": len(selected), "nominal_phase_slots": len(slots),
                        "missed_slots": missed, "clock_history": timing,
                        "observation_age_at_hypothetical_offer_ms": summarize(ages),
                        "remaining_67ms_prepress_budget_at_offer_ms": summarize([67-v for v in ages]),
                        "selected": selected}
    actual = [r["state"]["t"] for r in rows if "decision_trace" in r]
    assert [s["t"] for s in results["current_relative90"]["selected"]][:83] == actual
    naive_prior = json.loads((OUT.parent / "schedule-clocks.json").read_text())
    assert [s["t"] for s in results["naive_after"]["selected"]] == naive_prior["selected_actual_clocks"]
    assert results["band_after"]["clock_history"]["counts"].get("clock_invalid_history",0) == 0
    result = {"scope": "recorded369_acquisition_clocks_only_no_States_or_model_or_actuation",
              "input_sha256": EXPECTED, "period_s": PERIOD, "tolerance_s": TOL,
              "phase_origin_t": clocks[0], "end_t": clocks[-1], "controls": controls(),
              "variants": results,
              "limits": ["Clock usability is an upper bound on consumer opportunity, not actual model calls or accepted starts.",
                         "Current variant includes84 eligible offers; only83 decisions persisted; last feature/target/probability absent.",
                         "Clock warmup includes initial first observation; actual first target refusal takes precedence.",
                         "No future frame selection, retimed timestamp, alternate State/target or feature fabricated.",
                         "Before_timer assumes an independent phase timer/buffer; before_reflex adds actual next-reflex offer delay.",
                         "Worker availability/perception/model/dispatch and changed gameplay are not simulated; all costs occur after these lower-bound ages."]}
    assert hashlib.sha256(LOG.read_bytes()).hexdigest() == EXPECTED
    with (OUT / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({mode: {"eligible":v["eligible_acquisitions"], "missed":None if v["missed_slots"] is None else len(v["missed_slots"]),
                            "counts":v["clock_history"]["counts"], "age_ms":v["observation_age_at_hypothetical_offer_ms"]}
                      for mode,v in results.items()}, indent=2))


if __name__ == "__main__":
    main()
