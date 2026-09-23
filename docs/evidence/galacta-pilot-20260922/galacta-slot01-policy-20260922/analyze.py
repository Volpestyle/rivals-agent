"""Bounded, stdlib-only accounting; no policy/runtime imports or inference.

Run from repo root: uv run --offline --no-project python -B
data/diagnostics/galacta-slot01-policy-20260922/analyze.py
"""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = "data/l1/galacta-pilot-20260922-01-learned/"
PREFLIGHT = "data/runtime/galacta-pilot-20260922-01-preflight/"
EXAMPLES = "data/human/skill-events/032454-request-diagnostic-v1/examples.json"
FIT = "data/diagnostics/range-request-human-fit-20260922/run-1/windows-report.json"
INPUTS = [RUN + "meta.json", RUN + "frames.jsonl", EXAMPLES, FIT,
          PREFLIGHT + "loader-preflight.json", PREFLIGHT + "effective-setup.json",
          "policy/range_policy.py"]
EXPECTED = {
    RUN + "meta.json": "48c60301dbfc2c6a21f9963dd21a29075030e8ebec12313c0cb41bf8d9468cdf",
    RUN + "frames.jsonl": "cef90ac2c2f1e36ad87d57d74e87331f4efb7ca585be7efd68dba88b602f1284",
    EXAMPLES: "bd6cf4cb298379ac1a63fd226652e517ad6773ed6b4cead92dfb790abca91570",
}
FIELDS = ("hp_fraction", "webs", "pull_ready", "uppercut_ready", "swing_ready",
          "on_target", "detector", "target", "target_x", "target_y",
          "target_height", "target_distance", "target_tagged")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def stats(values):
    values = [float(x) for x in values if x is not None]
    return {"n": len(values), "min": min(values), "median": statistics.median(values),
            "max": max(values)} if values else {"n": 0}


def counts(values):
    return dict(Counter(str(x) for x in values))


def features(state, target):
    # Arithmetic transcription of the read, hashed feature_row implementation.
    # This is descriptive JSON projection, not a validator/adapter or model call.
    assert target is None or target in state["detections"]
    hp, maximum = state["hp"], state["max_hp"]
    values = [hp / maximum if hp is not None and maximum is not None else None,
              state["webs"] / 5 if state["webs"] is not None else None]
    values += [state["abilities"].get(a, {}).get("ready") for a in ("pull", "uppercut", "swing")]
    values += [state["on_target"], state["detections"] is not None,
               target is not None if state["detections"] is not None else None]
    if target is None:
        values += [None] * 5
    else:
        x1, y1, x2, y2 = target["bbox"]
        w, h = state["frame"]
        values += [(x1 + x2) / (2 * w), (y1 + y2) / (2 * h), (y2 - y1) / h,
                   target["distance"] / 40 if target["distance"] is not None else None,
                   target["tagged"]]
    return dict(zip(FIELDS, values))


def summary(rows):
    return {key: {"known": sum(r[key] is not None for r in rows),
                  "unknown": sum(r[key] is None for r in rows),
                  "values": counts(r[key] for r in rows) if key not in
                  ("target_x", "target_y", "target_height", "target_distance") else None,
                  "numeric": stats(r[key] for r in rows)} for key in FIELDS}


def main():
    before = {p: sha(ROOT / p) for p in INPUTS}
    for p, digest in EXPECTED.items():
        assert before[p] == digest, p
    meta, packet, fit = read(RUN + "meta.json"), read(EXAMPLES), read(FIT)
    rows = [json.loads(x) for x in (ROOT / (RUN + "frames.jsonl")).read_text().splitlines()]
    normal = [r for r in rows if "type" not in r]
    decisions = [r for r in rows if "decision_trace" in r]
    assert len({r["decision_trace"]["decision_id"] for r in decisions}) == len(decisions)
    models = [r for r in decisions if r["decision_trace"]["reason"] == "model_event"]
    source = [r for r in packet["rows"] if r["label_known"]]
    assert len(source) == 5 and sum(r["label"] == "start" for r in source) == 1
    anchors, ambiguous, records = [], [], []
    for r in models:
        state, trace = r["state"], r["decision_trace"]
        matches = [d for d in state["detections"] if d["track"] == trace["target"]]
        rec = {"decision_id": trace["decision_id"], "state_t": state["t"],
               "jsonl_line": rows.index(r) + 1, "slot": r["decision_timing"]["slot"],
               "probabilities": trace["probabilities"], "proposal": trace["web_cluster_request"],
               "selected_track": trace["target"], "matching_detection_count": len(matches),
               "matching_bboxes": [d["bbox"] for d in matches],
               "resources": trace["resources"],
               "first_executor_reason": r.get("range_skill_trace", {}).get("reason"),
               "first_execution_t": r.get("range_skill_trace", {}).get("execution_t")}
        if len(matches) == 1:
            rec["features"] = features(state, matches[0])
            anchors.append(rec["features"])
        else:
            rec["features"] = None
            ambiguous.append(rec["decision_id"])
        records.append(rec)
    source_records = []
    for r in source:
        hist = [features(s["state"], s["target"]) for s in r["history"]]
        source_records.append({"grid_index": r["grid_index"], "label": r["label"],
                               "anchor_t": r["anchor_t"],
                               "actual_t": [s["state"]["t"] for s in r["history"]],
                               "available_t": [s["available_t"] for s in r["history"]],
                               "features": hist})
    source_features = [f for r in source_records for f in r["features"]]
    positive = next(r for r in source_records if r["label"] == "start")
    bounds = {}
    for name in ("webs", "target_x", "target_y", "target_height"):
        vals = [f[name] for f in source_features if f[name] is not None]
        pv = [f[name] for f in positive["features"] if f[name] is not None]
        bounds[name] = {"source_all_min_max": [min(vals), max(vals)],
                        "positive_min_max": [min(pv), max(pv)],
                        "runtime_exact_anchors_below_source": sum(f[name] < min(vals) for f in anchors),
                        "runtime_exact_anchors_above_source": sum(f[name] > max(vals) for f in anchors),
                        "runtime_exact_anchors_outside_positive": sum(not min(pv) <= f[name] <= max(pv) for f in anchors)}
    # Only already recorded unambiguous model anchors, consecutive IDs and slots.
    # Do not reconstruct selector outputs for warmup or ambiguous track IDs.
    windows = []
    for i in range(4, len(records)):
        seq = records[i-4:i+1]
        if not all(r["features"] is not None for r in seq):
            continue
        if any(b["slot"] != a["slot"] + 1 or b["decision_id"] != a["decision_id"] + 1
               for a, b in zip(seq, seq[1:])):
            continue
        if not all(abs(r["state_t"] - (seq[-1]["state_t"] - (4-j)*.1)) <= .025
                   for j, r in enumerate(seq)):
            continue
        windows.append(seq[-1]["decision_id"])
    report = {
        "scope": "Recorded-output and feature support diagnosis; no inference, labels, or outcome audit",
        "meta": {k: meta[k] for k in ("stop", "seconds", "ticks", "decisions", "errors", "range_gaps")},
        "checkpoint_sha256": meta["range_policy"]["checkpoint_sha256"],
        "loader": read(PREFLIGHT + "loader-preflight.json"),
        "identities": {k: meta["range_policy"][k] for k in ("source_identity", "runtime")},
        "decision_reasons": counts(r["decision_trace"]["reason"] for r in decisions),
        "model_proposals": counts(r["decision_trace"]["web_cluster_request"] for r in models),
        "p_start": stats(r["decision_trace"]["probabilities"][1] for r in models),
        "confidence_no_new_start": stats(r["decision_trace"]["probabilities"][0] for r in models),
        "first_executor_reasons_per_model_decision": counts(r["first_executor_reason"] for r in records),
        "executor_reasons_normal_ticks": counts(r.get("range_skill_trace", {}).get("reason") for r in normal),
        "normal_send_status": counts(r.get("send_result", {}).get("status") for r in normal),
        "returned_offensive_calls": {key: sum(r.get("send_result", {}).get("status") == "returned"
                                             and r.get("pad", {}).get(key, 0) > 0 for r in normal)
                                      for key in ("lt", "rt")},
        "accepted_executor_ticks": sum(r.get("range_skill_trace", {}).get("accepted", False) for r in normal),
        "model_selected_tracks": counts(r["selected_track"] for r in records),
        "model_state_webs": counts(r["state"]["webs"] for r in models),
        "model_state_hp": counts(r["state"]["hp"] for r in models),
        "model_resources_match_original_clock": all(r["decision_trace"]["resources"] ==
            {"webs": r["state"]["webs"], "observed_t": r["state"]["t"]} for r in models),
        "all_matching_selected_candidates_tagged": counts(d["tagged"] for r in models
            for d in r["state"]["detections"] if d["track"] == r["decision_trace"]["target"]),
        "exact_selected_anchor_count": len(anchors), "ambiguous_anchor_ids": ambiguous,
        "runtime_exact_anchor_features": summary(anchors),
        "source_train_only": {"known_examples": 5, "bin_support_no_new_start_start": [4, 1],
            "unknown_unscored_rows": sum(not r["label_known"] for r in packet["rows"]),
            "unique_events": 1, "feature_snapshot_occurrences": len(source_features),
            "unique_actual_snapshot_times": len({t for r in source_records for t in r["actual_t"]}),
            "features": summary(source_features), "positive": positive,
            "windows": source_records, "reported_fit_predictions": fit["known_rows"],
            "validation": fit["validation"], "limitations": packet["limitations"]},
        "marginal_support_comparison_not_causal_attribution": bounds,
        "fully_traceable_five_anchor_windows": {"count": len(windows), "ending_decision_ids": windows,
            "all_have_target_present_full_hp_webs5_untagged": all(
                f["target"] and f["hp_fraction"] == 1 and f["webs"] == 1 and f["target_tagged"] is False
                for f in anchors),
            "limit": "No exact box reconstruction for 12 ambiguous anchors or unreported warmup selection; no model replay."},
        "model_decision_locators": records,
        "findings": [
            "Zero starts originated upstream: all 194 model decisions chose no_new_start; maximum p_start below 0.5. Confidence threshold 0.7 did not suppress a start.",
            "182 first executor consumptions processed no-new normally; 12 refused ambiguous current track. No start was proposed for either group. Expiry on later reflex ticks cannot explain missing start proposals.",
            "Runtime full-ammo feature is outside all admitted training histories; untagged/full-HP selected history differs from the sole positive. Geometry comparison is limited to unique track matches.",
            "These are observed covariate/support differences, not identified causal model feature effects or a one-run generalization estimate. TRAIN fit on one onset cannot establish a firing rule.",
        ],
        "next_minimal_control": "Use root's already planned fixed mid pair: compare recorded normalized box geometry, masks, webs/tag/readiness and unchanged head probabilities against these exact anchors. Keep unchanged model/threshold. If full-ammo/untagged mid observations produce starts, those values are not an absolute learned veto; if they do not, geometry alone remains unproven. Do not replace unknowns or mutate features to force firing.",
    }
    assert len(decisions) == meta["decisions"] and len(normal) == meta["ticks"]
    assert fit["checkpoint_sha256"] == report["checkpoint_sha256"]
    after = {p: sha(ROOT / p) for p in INPUTS}
    assert before == after, "input changed during analysis"
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    receipts = {"inputs_before": before, "inputs_after": after, "unchanged": before == after,
                "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT / "report.json"),
                "readme_sha256": sha(OUT / "README.md"),
                "method": "stdlib JSON/arithmetic only; no project imports, checkpoint reads, inference or media decode"}
    (OUT / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("decision_reasons", "model_proposals", "p_start",
          "first_executor_reasons_per_model_decision", "returned_offensive_calls",
          "marginal_support_comparison_not_causal_attribution")}, indent=2))
    print("Exact anchor geometry:", json.dumps({k: report["runtime_exact_anchor_features"][k]["numeric"]
          for k in ("target_x", "target_y", "target_height")}))
    print("Traceable windows:", len(windows))


if __name__ == "__main__":
    main()
