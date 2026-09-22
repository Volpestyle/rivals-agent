"""Recorded-clock/window diagnosis only; no model/controller/loop/media imports."""
from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent import brain
from agent.human_demos import DemoError
from agent.intents import Idle, RangeSkill, RangeSkillResources
from agent.state import State
from policy.range_skill_policy import Snapshot, Spec, event_window, feature_row

RUN = ROOT / "data/l1/range-request-diagnostic-20260922-1"
OUT = Path(__file__).resolve().parent
EXPECTED = {"meta.json": "4d50f241fd42c653e39b8aad4c72a9bb8eb6669160495f5aecb22795ec58b613",
            "frames.jsonl": "f735585c44b1657569da4a4a2447c3b5605f12411728cc122f1618287ace47ec"}


def hashes():
    return {name: hashlib.sha256((RUN / name).read_bytes()).hexdigest() for name in EXPECTED}


def main():
    assert hashes() == EXPECTED
    meta = json.loads((RUN / "meta.json").read_text())
    rows = [json.loads(line) for line in (RUN / "frames.jsonl").read_text().splitlines()]
    release_rows = [r for r in rows if r.get("type") == "executor_release"]
    assert release_rows == meta["executor_events"]
    rows = [r for r in rows if r.get("type") != "executor_release"]
    decisions = [row for row in rows if "decision_trace" in row]
    assert [r["decision_trace"]["decision_id"] for r in decisions] == list(range(1, 84))
    spec, memory, history = Spec(hidden=8), brain.Memory(), deque(maxlen=5)
    last_t, group = None, "initial"
    diagnostics, resets, mismatches, warming = [], [], [], Counter()
    for row in decisions:
        trace, state = row["decision_trace"], State.from_dict(row["state"])
        n, t = trace["decision_id"], state.t
        assert t == trace["t"] and state.detections is not None
        dt = t - last_t if last_t is not None else None
        if dt is not None and abs(dt - spec.period_s) > spec.tolerance_s + 1e-9:
            resets.append({"decision": n, "kind": "adjacent_cadence", "t": t, "gap_ms": dt * 1000})
            history.clear()
            group = f"adjacent_reset_{n}"
        last_t = t
        feature_row(Snapshot(state, None, t))  # same consumer state-validity check
        early, target = brain.gate(state, memory)
        current = target is not None and target in state.detections and type(target.track) is int and target.track not in state.coasting
        history.append(deepcopy(Snapshot(state, target, t)))
        clocks = [s.state.t for s in history]
        offsets = [(s.state.t - (t - (4 - i) * .1)) * 1000 for i, s in enumerate(history)] if len(history) == 5 else []
        error = None
        if not current:
            reason = "target_unobserved"
        elif len(history) < 5:
            reason = "warming_up"
        else:
            try:
                event_window(tuple(history), t, spec, sampling="live")
            except DemoError as exc:
                error, reason = str(exc), "invalid_history"
            else:
                reason = trace["reason"]  # model/low-confidence result observed, never recomputed
                assert reason in ("model_event", "low_confidence")
        record = {"decision": n, "anchor_t": t, "adjacent_ms": dt * 1000 if dt is not None else None,
                  "reason_recorded": trace["reason"], "reason_from_gate_window": reason,
                  "selected_track_from_gate": getattr(target, "track", None), "target_recorded_on_intent": trace["target"],
                  "history_t": clocks, "grid_residual_ms": offsets, "window_error": error,
                  "ms_decide_rounded": row["ms_decide"],
                  "first_dispatch_observation_age_ms": (row["send_result"]["observation_t"] - t) * 1000}
        diagnostics.append(record)
        if reason != trace["reason"]:
            mismatches.append(record)
        if reason == "invalid_history":
            resets.append({**record, "kind": "window_geometry"})
            history.clear()
            group = f"invalid_reset_{n}"
        if reason == "warming_up":
            warming[group] += 1
        if trace["reason"] == "model_event":
            assert current and target.track == trace["target"]
            resources = RangeSkillResources(**trace["resources"])
            intent = RangeSkill(deepcopy(target), trace["web_cluster_request"], n, trace["valid_until"], resources)
            brain.track_mode(state, memory, target)
        else:
            intent = Idle()
        brain.commit(memory, intent)
    assert not mismatches, mismatches

    # Replay only offer eligibility on ACTUAL reflex acquisition timestamps.
    # This does not create State/feature rows or evaluate alternate model inputs.
    reflex_t = [r["send_result"]["observation_t"] for r in rows]
    offers, previous = [], -float("inf")
    for t in reflex_t:
        if t - previous >= .9 / 10:
            offers.append(t)
            previous = t
    actual_t = [r["state"]["t"] for r in decisions]
    assert offers[:83] == actual_t

    # Each first fresh execution trace's deadline slack; separate repeated reflex
    # observations from new decision requests.
    first, all_traces, movement = {}, [], Counter()
    for row in rows:
        trace = row.get("range_skill_trace")
        if trace is None:
            continue
        all_traces.append(trace)
        n = trace["decision_id"]
        if n is not None:
            first.setdefault(n, (row, trace))
        if trace["reason"] == "decision_expired" or trace["proposal"] == "no_new_start":
            moving = any(row["pad"][axis] != 0 for axis in ("lx", "ly"))
            movement[(trace["reason"], trace["proposal"], moving, bool(row["pad"]["lt"]))] += 1
    starts = []
    for row in decisions:
        d = row["decision_trace"]
        if d["web_cluster_request"] != "start":
            continue
        pair = first.get(d["decision_id"])
        if pair is None:
            starts.append({"decision": d["decision_id"], "first_execution_trace": None})
            continue
        r, x = pair
        starts.append({"decision": d["decision_id"], "anchor_t": d["t"], "reason": x["reason"],
                       "execution_t": x["execution_t"], "valid_until": x["valid_until"],
                       "acquisition_to_execution_ms": (x["execution_t"] - d["t"]) * 1000,
                       "full_33ms_press_slack_ms": (x["valid_until"] - x["execution_t"] - .033) * 1000,
                       "ms_decide_rounded": r.get("ms_decide"),
                       "acquisition_to_dispatch_observation_ms": (x["observation_t"] - d["t"]) * 1000})
    lt_rows = [{"decision": r.get("d"), "trace": r["range_skill_trace"], "send": r["send_result"]}
               for r in rows if r["pad"]["lt"]]
    for item in lt_rows:
        x, send = item["trace"], item["send"]
        item["attempt_not_after_slack_ms"] = (send["not_after"] - send["attempted_t"]) * 1000
        item["return_not_after_slack_ms"] = (send["not_after"] - send["returned_t"]) * 1000
        item["call_ms"] = (send["returned_t"] - send["attempted_t"]) * 1000
    terminal = meta["executor_events"][0]
    send, pulse = terminal["preceding_send_result"], terminal["range_skill_trace"]
    terminal_margins = {"observed_terminal_event": terminal,
        "decision_trace_or_probability_available": False,
        "implied_anchor_t_from_deadline_minus_frozen_period": pulse["pulse_valid_until"] - .1,
        "implied_accept_execution_t_from_press_until_minus_nominal_press": pulse["pulse_press_until"] - .033,
        "full_press_slack_at_implied_accept_ms": (pulse["pulse_valid_until"] - pulse["pulse_press_until"]) * 1000,
        "send_entry_full_press_slack_ms": (send["not_after"] - send["attempted_t"]) * 1000,
        "send_failed_return_after_deadline_ms": (send["returned_t"] - send["not_after"]) * 1000,
        "send_call_ms": (send["returned_t"] - send["attempted_t"]) * 1000}
    assert hashes() == EXPECTED
    forbidden = [m for m in sys.modules if m in ("torch", "agent.controller", "agent.loop", "agent.learned_range_skill") or m.startswith(("cv2", "vgamepad", "dxcam", "perception"))]
    assert not forbidden, forbidden
    result = {"scope": "recorded_state_pure_gate_and_window_clock_diagnosis_no_inference",
        "inputs_before_after_sha256": EXPECTED, "spec": {"steps": 5, "period_s": .1, "tolerance_s": .025},
        "persisted_decisions": len(decisions), "meta_decisions": meta["decisions"],
        "reason_counts": dict(Counter(r["decision_trace"]["reason"] for r in decisions)),
        "pure_gate_window_reason_mismatches": mismatches, "resets": resets,
        "warmup_by_reset": dict(warming), "decision_diagnostics": diagnostics,
        "offer_clock_reconstruction": {"rule": "first recorded reflex acquisition at least90ms after previous accepted offer",
             "matches_all83_persisted_anchors_exactly": True, "offered_times": offers,
             "meta_missed_decisions": meta["missed_decisions"],
             "limits": "Clock eligibility only; no worker timing, new observations or counterfactual model inference. Final unlogged decision State absent."},
        "first_start_execution": starts, "returned_LT_rows": lt_rows, "terminal_84": terminal_margins,
        "movement_by_reason_proposal": [{"reason": key[0], "proposal": key[1], "translation_nonzero": key[2],
                                         "lt_nonzero": key[3], "rows": count} for key, count in movement.items()],
        "execution_reason_counts": dict(Counter(x["reason"] for x in all_traces)),
        "code_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                        ("policy/range_skill_policy.py", "policy/range_policy.py", "agent/brain.py", "agent/state.py", "agent/learned_range_skill.py", "agent/loop.py", "agent/controller.py")},
        "forbidden_modules_imported": forbidden,
        "limits": ["No model execution, inference, training, fabricated States or native visual audit.",
                   "Recorded request outcomes only seed pure gate Memory; no counterfactual requests are generated.",
                   "Refusal traces omit intermediate gate target; it is reconstructed, with resulting reasons checked exactly.",
                   "Final decision84 has no persisted probability/State; only terminal pulse/send evidence is used."]}
    with (OUT / "report.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("reason_counts", "warmup_by_reset", "resets", "first_start_execution", "terminal_84", "movement_by_reason_proposal")}, indent=2))


if __name__ == "__main__":
    main()
