"""One offline observational pass over D's exact decision States. No actuation."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / "data/diagnostics/range-event-human-fit-v2-20260922/run-1/model.pt"
LOG = ROOT / "data/l1/range-cast-probe-20260922-d/frames.jsonl"
MAC_REPORT = ROOT / "docs/evidence/range-human-fit-v2-20260922/mac-report.json"
MODEL_SHA = "da29a97f0542210e6c69bc7dfa488afec97c33668a27deea98e3177919834987"
LOG_SHA = "7ec2d278e57878220ef0615db7a2f4bdb5d0fbf7e9d1ec4209d15a798b04c690"
OUTPUT = Path(__file__).with_name("report.json")


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def summary(values):
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "min": None, "median": None, "p95_nearest_rank": None, "max": None}
    import math
    return {"n": len(values), "min": ordered[0], "median": statistics.median(ordered),
            "p95_nearest_rank": ordered[math.ceil(.95 * len(ordered)) - 1], "max": ordered[-1]}


def main():
    if OUTPUT.exists():
        raise SystemExit("report.json already exists; frozen replay will not be repeated or overwritten")
    before = {"model": fingerprint(MODEL), "frames_jsonl": fingerprint(LOG)}
    assert before == {"model": MODEL_SHA, "frames_jsonl": LOG_SHA}
    metadata = json.loads(MAC_REPORT.read_text())
    config_path, meta_path, probe_path = (LOG.parent / name for name in
                                         ("probe-config.json", "meta.json", "probe-report.json"))
    config, live_meta, probe = (json.loads(path.read_text()) for path in (config_path, meta_path, probe_path))
    assert metadata["checkpoint_sha256"] == MODEL_SHA
    logged_rows = [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]
    decisions, seen = [], {}
    for line, row in enumerate(logged_rows, 1):
        if "state" not in row:
            continue
        original = row["state"]
        if original["t"] in seen:
            assert original == seen[original["t"]], "conflicting States at one timestamp"
            continue
        assert not decisions or original["t"] > decisions[-1][1]["state"]["t"], "out-of-order States"
        assert original["t"] == row["decision_trace"]["t"], "decision clock disagreement"
        seen[original["t"]] = original
        decisions.append((line, row))
    assert len(decisions) == 52 == live_meta["decisions"]

    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from agent.brain import Memory
    from agent.intents import RangeSkill
    from agent.learned_range_skill import LearnedRangeSkillBrain
    from agent.state import State
    from policy.range_skill_policy import OUTCOMES, SourceIdentity

    load_start = time.perf_counter()
    consumer = LearnedRangeSkillBrain.from_checkpoint(MODEL, expected_sha256=MODEL_SHA,
        expected_identity=SourceIdentity(**metadata["source_identity"]), device="cpu", offline=True)
    load_ms = (time.perf_counter() - load_start) * 1000
    assert consumer.policy.data_sha256 == metadata["evidence_digest"]
    assert asdict(consumer.policy.spec) == metadata["spec"]
    assert consumer.policy.origin == "reviewed_human"
    memory = Memory()
    inference = []
    original_probabilities = consumer.policy.probabilities

    def timed_probabilities(history, anchor_t, *, sampling):
        started = time.perf_counter()
        probabilities = original_probabilities(history, anchor_t, sampling=sampling)
        elapsed = (time.perf_counter() - started) * 1000
        inference.append({"anchor_t": anchor_t, "ms": elapsed, "probabilities": list(probabilities),
                          "history": [{"t": s.state.t, "available_t": s.available_t,
                                       "target_id": s.target.track if s.target else None} for s in history]})
        return probabilities

    # Timing wrapper delegates once to the unchanged real policy method.
    consumer.policy.probabilities = timed_probabilities
    results, intervals = [], []
    previous_t = None
    for line, row in decisions:
        original = row["state"]
        state = State.from_dict(deepcopy(original))
        assert canonical(state.to_dict()) == canonical(original), "State values changed during construction"
        dt = None if previous_t is None else state.t - previous_t
        cadence_reset = dt is not None and abs(dt - consumer.policy.spec.period_s) > consumer.policy.spec.tolerance_s + 1e-9
        if dt is not None:
            intervals.append(dt * 1000)
        previous_t = state.t
        prior_inferences = len(inference)
        history_before = len(consumer.history)
        started = time.perf_counter()
        intent = consumer(state, memory)  # exactly one pass, no warmup calls or retries
        consumer_ms = (time.perf_counter() - started) * 1000
        assert canonical(state.to_dict()) == canonical(original), "consumer changed recorded State"
        selected = memory.target if memory.target_t == state.t else None
        probabilities = consumer.last["probabilities"]
        results.append({"log_line": line, "recorded_decision_id": row["d"], "state_t": state.t,
            "state_sha256": hashlib.sha256(canonical(original).encode()).hexdigest(),
            "dt_s": dt, "cadence_reset": cadence_reset, "history_before": history_before,
            "history_after": len(consumer.history), "inference_called": len(inference) > prior_inferences,
            "inference_ms": inference[-1]["ms"] if len(inference) > prior_inferences else None,
            "consumer_ms": consumer_ms, "trace": deepcopy(consumer.last),
            "argmax_prediction": OUTCOMES[max(range(len(OUTCOMES)), key=probabilities.__getitem__)] if probabilities else None,
            "confidence": max(probabilities) if probabilities else None,
            "observed_resources": {"webs": state.webs, "observed_t": state.t},
            "emitted_resources": asdict(intent.resources) if isinstance(intent, RangeSkill) else None,
            "selected_target": asdict(selected) if selected else None,
            "recorded_detection_ids": None if state.detections is None else [d.track for d in state.detections],
            "recorded_scripted_target_id_context_only": row["decision_trace"].get("target_id"),
            "recorded_live_decide_ms_context_only": row.get("ms_decide")})

    after = {"model": fingerprint(MODEL), "frames_jsonl": fingerprint(LOG)}
    assert before == after, "input artifact changed during replay"
    forbidden = [name for name in sys.modules if name in ("agent.controller", "agent.loop", "agent.live")
                 or name.startswith("perception") or "cast_probe" in name or name in ("vgamepad", "cv2")]
    assert not forbidden, forbidden
    refusal = Counter(r["trace"]["reason"] for r in results if r["trace"]["source"] == "range_skill_refusal")
    emitted = Counter(r["trace"]["web_cluster_request"] for r in results if r["trace"]["web_cluster_request"])
    report = {"scope": "offline_off_policy_posthoc_observational_support_dispatch_only",
        "created_utc": datetime.now(timezone.utc).isoformat(), "replay_passes": 1,
        "checkpoint": {"path": str(MODEL.relative_to(ROOT)), "before_after_sha256": [before["model"], after["model"]],
                       "original_source_identity": asdict(consumer.policy.identity), "original_evidence_digest": consumer.policy.data_sha256,
                       "spec": asdict(consumer.policy.spec), "support": list(consumer.policy.support), "origin": consumer.policy.origin,
                       "load_mode": "offline=True", "runtime_identity": None, "deployment_binding": None},
        "recorded_input": {"path": str(LOG.relative_to(ROOT)), "before_after_sha256": [before["frames_jsonl"], after["frames_jsonl"]],
                           "log_rows": len(logged_rows), "state_rows": sum("state" in r for r in logged_rows),
                           "unique_decision_states": len(results), "first_t": results[0]["state_t"], "last_t": results[-1]["state_t"],
                           "timestamps_values_unchanged": True, "selection": "chronological recorded States, fresh actual consumer/Memory, no scripted-intent injection"},
        "counts": {"inference_calls": len(inference), "refusals": sum(refusal.values()), "refusal_reasons": dict(refusal),
                   "emitted_requests": {name: emitted[name] for name in OUTCOMES},
                   "argmax_predictions": dict(Counter(r["argmax_prediction"] for r in results if r["argmax_prediction"])),
                   "sources": dict(Counter(r["trace"]["source"] for r in results)),
                   "cadence_reset_intervals": sum(r["cadence_reset"] for r in results),
                   "selected_target_ids": dict(Counter(str(r["selected_target"]["track"]) for r in results if r["selected_target"])),
                   "original_webs": dict(Counter(str(r["observed_resources"]["webs"]) for r in results))},
        "timing": {"cpu_only": True, "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
                   "torch_version": torch.__version__, "platform": platform.platform(), "checkpoint_load_ms": load_ms,
                   "actual_decision_interval_ms": summary(intervals), "offline_probability_call_ms": summary([r["ms"] for r in inference]),
                   "offline_consumer_call_ms": summary([r["consumer_ms"] for r in results]),
                   "first_probability_call_ms": inference[0]["ms"] if inference else None,
                   "later_probability_call_ms": summary([r["ms"] for r in inference[1:]]),
                   "confidence": summary([r["confidence"] for r in results if r["confidence"] is not None]),
                   "cost_boundary": "Local perf_counter wall time on CPU, not hardware CPU-cycle measurement; no capture/perception/scheduling/input. First inference includes cold-call overhead."},
        "recorded_live_context_not_remeasured": {"mode": probe["mode"], "source": probe["source"],
            "patch": live_meta["patch"], "cooldowns": live_meta["cooldowns"], "clock_evidence": config["clock_evidence"],
            "normal_cooldowns_note": config["normal_cooldowns_note"], "setup_note": config["setup_note"],
            "decide_ms": live_meta["decide_ms"], "decision_lag_ms": live_meta["decision_lag_ms"],
            "tick_ms": live_meta["tick_ms"], "aim_ms": live_meta["aim_ms"]},
        "input_metadata_hashes": {str(path.relative_to(ROOT)): fingerprint(path) for path in (MAC_REPORT, config_path, meta_path, probe_path)},
        "code_hashes": {name: fingerprint(ROOT / name) for name in ("agent/learned_range_skill.py", "agent/brain.py", "agent/state.py",
                       "policy/range_skill_policy.py", "policy/range_policy.py")},
        "replay_script_sha256": fingerprint(Path(__file__)), "forbidden_imports": forbidden,
        "limits": ["D is scripted calibration, not independent human validation; scripted decisions are not truth labels.",
                   "No scoring, admission, runtime binding, live approval, counterfactual kills or pulse-success claim.",
                   "Different learned actions would alter later scenes; later D observations remain off-policy.",
                   "Human checkpoint provenance remains original; D patch is unverified and its runtime/perception equivalence is unapproved.",
                   "Training used window-reset tracking; this replay uses continuous recorded detections and fresh continuous consumer Memory.",
                   "Recorded States already contain perceived fields. No source media, native frames, perception, Controller or Loop was imported or executed.",
                   "No retiming, interpolation, padding, threshold/model change, fitting, repeated replay or input occurred.",
                   "Recorded observation clock is grab START; render time is unknown. Offline CPU timings cannot substitute for live pipeline latency."],
        "decisions": results, "inferences": inference}
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"report": str(OUTPUT.relative_to(ROOT)), "counts": report["counts"], "timing": report["timing"]}, indent=2))


if __name__ == "__main__":
    main()
