"""Read only explicit JSON inputs. No model or runtime imports; no replay."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = "data/l1/galacta-pilot-20260922-04-learned/"
PRIOR = "data/diagnostics/galacta-slot01-policy-20260922/report.json"
SOURCE = "data/human/skill-events/032454-request-diagnostic-v1/examples.json"
EXPECTED = {
    RUN + "meta.json": "7418db6db7aa0c7ae71fcb9012e5f322810d43070ab183dc0e5202326d2f19ca",
    RUN + "frames.jsonl": "1eadcb5efba274883e103ebfae5e5f62c4f720008c75c3ea5ec226baf9e071a6",
    PRIOR: "c98a2d4c84eb383c2c21b664189b4e4f4d1daf8f79eee0d8d16912b7e1aab666",
    SOURCE: "bd6cf4cb298379ac1a63fd226652e517ad6773ed6b4cead92dfb790abca91570",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def counts(items):
    return dict(Counter(str(x) for x in items))


def stats(items):
    xs = [float(x) for x in items if x is not None]
    return {"n": len(xs), "min": min(xs), "median": statistics.median(xs), "max": max(xs)} if xs else {"n": 0}


def features(s, target):
    # Same descriptive 13 value / known-mask fields used in slot 1.
    # None remains unknown; this is not a new policy validator or source adapter.
    f = {"hp_fraction": s["hp"] / s["max_hp"] if s["hp"] is not None and s["max_hp"] is not None else None,
         "webs": s["webs"] / 5 if s["webs"] is not None else None,
         **{a + "_ready": s["abilities"].get(a, {}).get("ready") for a in ("pull", "uppercut", "swing")},
         "on_target": s["on_target"], "detector": s["detections"] is not None,
         "target": target is not None if s["detections"] is not None else None}
    f.update({k: None for k in ("target_x", "target_y", "target_height", "target_distance", "target_tagged")})
    if target is not None:
        assert target in s["detections"]
        x1, y1, x2, y2 = target["bbox"]
        w, h = s["frame"]
        f.update(target_x=(x1+x2)/(2*w), target_y=(y1+y2)/(2*h), target_height=(y2-y1)/h,
                 target_distance=target["distance"]/40 if target["distance"] is not None else None,
                 target_tagged=target["tagged"])
    return f


def group_summary(records):
    fs = [r["features"] for r in records if r["features"] is not None]
    return {"n": len(records), "decision_ids": [r["decision_id"] for r in records],
            "p_start": stats(r["probabilities"][1] for r in records),
            "phase_age_s": stats(r["phase_age_s"] for r in records),
            "exact_feature_rows": len(fs),
            "features": {k: {"numeric": stats(f[k] for f in fs),
                             "unknown": sum(f[k] is None for f in fs)} for k in fs[0]} if fs else {}}


def main():
    before = {p: digest(ROOT / p) for p in EXPECTED}
    assert before == EXPECTED, before
    meta, prior, source = read(RUN + "meta.json"), read(PRIOR), read(SOURCE)
    rows = [json.loads(line) for line in (ROOT/(RUN+"frames.jsonl")).read_text().splitlines()]
    decisions = [(i+1, r) for i, r in enumerate(rows) if "decision_trace" in r]
    normal = [r for r in rows if "type" not in r]
    origin = meta["decision_schedule"]["origin_t"]
    records = []
    for line, row in decisions:
        tr = row["decision_trace"]
        if tr["probabilities"] is None:
            continue
        s = row["state"]
        matches = [d for d in s["detections"] if d["track"] == tr["target"]]
        records.append({"decision_id": tr["decision_id"], "jsonl_line": line,
            "state_t": s["t"], "phase_age_s": s["t"]-origin,
            "slot": row["decision_timing"]["slot"], "probabilities": tr["probabilities"],
            "proposal": tr["web_cluster_request"], "target": tr["target"],
            "resources": tr["resources"], "first_executor_reason": row.get("range_skill_trace", {}).get("reason"),
            "matching_detections": matches, "features": features(s, matches[0]) if len(matches)==1 else None})
    known = [r for r in source["rows"] if r["label_known"]]
    source_windows = [{"grid_index": r["grid_index"], "label": r["label"],
                       "actual_t": [s["state"]["t"] for s in r["history"]],
                       "available_t": [s["available_t"] for s in r["history"]],
                       "features": [features(s["state"], s["target"]) for s in r["history"]]} for r in known]
    # Independent projection matches the frozen slot-1 source comparison exactly.
    assert [r["features"] for r in source_windows] == [r["features"] for r in prior["source_train_only"]["windows"]]
    sf = [f for r in source_windows for f in r["features"]]
    pf = next(r["features"] for r in source_windows if r["label"]=="start")
    bounds = {name: [min(f[name] for f in sf if f[name] is not None),
                     max(f[name] for f in sf if f[name] is not None)]
              for name in ("webs", "target_x", "target_y", "target_height")}
    positive_bounds = {name: [min(f[name] for f in pf if f[name] is not None),
                              max(f[name] for f in pf if f[name] is not None)] for name in bounds}
    exact = [r for r in records if r["features"] is not None]
    inside = [r for r in exact if bounds["target_height"][0] <= r["features"]["target_height"] <= bounds["target_height"][1]]
    near = [r for r in exact if r["features"]["target_height"] > bounds["target_height"][1]]
    within_positive_height = [r for r in exact if positive_bounds["target_height"][0] <= r["features"]["target_height"] <= positive_bounds["target_height"][1]]
    window_ids = []
    source_height_window_ids = []
    positive_height_window_ids = []
    for i in range(4, len(records)):
        seq = records[i-4:i+1]
        if all(r["features"] is not None for r in seq) and all(
            b["decision_id"]==a["decision_id"]+1 and b["slot"]==a["slot"]+1 for a,b in zip(seq, seq[1:])) and all(
                abs(r["state_t"]-(seq[-1]["state_t"]-(4-j)*.1)) <= .025 for j,r in enumerate(seq)):
            window_ids.append(seq[-1]["decision_id"])
            if all(bounds["target_height"][0] <= r["features"]["target_height"] <= bounds["target_height"][1] for r in seq):
                source_height_window_ids.append(seq[-1]["decision_id"])
            if all(positive_bounds["target_height"][0] <= r["features"]["target_height"] <= positive_bounds["target_height"][1] for r in seq):
                positive_height_window_ids.append(seq[-1]["decision_id"])
    releases = [r for r in rows if r.get("type")=="executor_release"]
    terminal = releases[-1]
    stop_send = terminal["preceding_send_result"]
    report = {
        "scope": "Recorded numerical outputs and causal feature support only; no inference or native outcome claim",
        "meta": {k: meta[k] for k in ("stop", "seconds", "ticks", "decisions", "errors", "range_gaps")},
        "phase_origin_t": origin,
        "checkpoint_sha256": meta["range_policy"]["checkpoint_sha256"],
        "same_checkpoint_and_source_as_slot1": all(meta["range_policy"][k]==v for k,v in
            [("checkpoint_sha256",prior["checkpoint_sha256"]),("source_identity",prior["identities"]["source_identity"]) ]),
        "runtime_identities_equal": meta["range_policy"]["runtime"]==prior["identities"]["runtime"],
        "identities": {k:meta["range_policy"][k] for k in ("source_identity","runtime")},
        "decision_reasons": counts(r["decision_trace"]["reason"] for _,r in decisions),
        "model_proposals": counts(r["proposal"] for r in records),
        "p_start": stats(r["probabilities"][1] for r in records),
        "p_no_new_start": stats(r["probabilities"][0] for r in records),
        "first_executor_reasons": counts(r["first_executor_reason"] for r in records),
        "normal_send_status": counts(r.get("send_result",{}).get("status") for r in normal),
        "returned_offensive_calls": {k: sum(r.get("send_result",{}).get("status")=="returned" and r.get("pad",{}).get(k,0)>0 for r in normal) for k in ("lt","rt")},
        "proposed_offensive_ticks": {k: sum(r.get("proposed_pad",{}).get(k,0)>0 for r in rows) for k in ("lt","rt")},
        "accepted_pulse_owner_ids": sorted({r["range_skill_trace"]["decision_id"] for r in rows if r.get("range_skill_trace",{}).get("accepted")}),
        "all_model_original_resource_clocks_preserved": all(r["resources"]["observed_t"]==r["state_t"] for r in records),
        "resource_webs": counts(r["resources"]["webs"] for r in records),
        "all_model_state_hp": counts(r["state"]["hp"] for _,r in decisions if r["decision_trace"]["probabilities"] is not None),
        "target_candidates_tagged": counts(d["tagged"] for r in records for d in r["matching_detections"]),
        "ambiguous_decision_ids": [r["decision_id"] for r in records if r["features"] is None],
        "exact_anchor_summary": group_summary(exact),
        "within_source_history_height": group_summary(inside),
        "within_positive_history_height": group_summary(within_positive_height),
        "above_all_source_history_height": group_summary(near),
        "joint_positive_xyz_marginal_matches": [r["decision_id"] for r in exact if all(
            positive_bounds[k][0] <= r["features"][k] <= positive_bounds[k][1] for k in ("target_x","target_y","target_height"))],
        "fully_traceable_five_anchor_windows": window_ids,
        "five_anchor_windows_all_heights_within_source": source_height_window_ids,
        "five_anchor_windows_all_heights_within_positive": positive_height_window_ids,
        "source_train_only": {"known_examples": len(known), "unique_start_events": 1,
            "masked_unknown_rows": sum(not r["label_known"] for r in source["rows"]),
            "feature_windows": source_windows, "marginal_bounds": bounds, "positive_marginal_bounds": positive_bounds,
            "reported_fit_predictions": prior["source_train_only"]["reported_fit_predictions"],
            "validation": None},
        "slot1": {k: prior[k] for k in ("p_start","model_proposals","decision_reasons","first_executor_reasons_per_model_decision","runtime_exact_anchor_features")},
        "terminal": {"event": terminal, "normal_last_observation_t": normal[-1]["observation_t"],
            "scope_check_overrun_ms": (stop_send["checked_t"]-stop_send["scope_not_after"])*1000,
            "last_observation_phase_age_s": stop_send["observation_t"]-origin,
            "scope_deadline_phase_age_s": stop_send["scope_not_after"]-origin,
            "interpretation": "Terminal last-send check exceeded phase scope; range_lost is logged stop classification, not proof of lost range pixels. This absent normal send is separate from 1097 returned normal calls."},
        "model_decision_locators": records,
        "limitations": ["No inference, temporal retiming, selector reconstruction or feature intervention.",
            "Track-ambiguous snapshots are excluded from exact geometry/windows, not assigned fabricated targets.",
            "Source has five TRAIN labels and one start; unknown rows are not negatives. Two non-firing slots are not a population generalization rate.",
            "Unchanged checkpoint/source do not imply equal runtime receipts or scenes; no causal feature attribution."],
        "next_minimum_learning_step": "Admission owner: prepare a small natural human correction packet covering a target-agreed first web request from full-ammo, untagged Galacta approach through mid/near geometry, with resource-legal no-fresh-request controls from the same natural sequence. Keep received-RMB/cast association, original five causal snapshots, target masks and raw continuity; do not derive labels from model/scripted actions. Fit a separate candidate including original admitted rows and new reviewed support, preserving the original checkpoint. Treat first fit as TRAIN-only; reserve independent human-session evidence for quality claims. No further identical-model trial or threshold tuning is prescribed.",
    }
    assert len(decisions)==meta["decisions"] and len(normal)==meta["ticks"]
    assert len({r["decision_trace"]["decision_id"] for _,r in decisions})==len(decisions)
    assert len(records)==194 and report["model_proposals"]=={"no_new_start":194}
    assert report["p_start"]["max"]<.5 and report["p_no_new_start"]["min"]>.7
    assert report["same_checkpoint_and_source_as_slot1"]
    after = {p:digest(ROOT/p) for p in EXPECTED}
    assert before==after
    (OUT/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    receipts = {"input_sha256_before":before,"input_sha256_after":after,"all_originals_unchanged":True,
        "outputs": {p.name:digest(p) for p in [Path(__file__),OUT/"report.json"]},
        "method":"stdlib JSON/arithmetic only; no runtime imports or model inference"}
    if (OUT/"README.md").exists():
        receipts["outputs"]["README.md"]=digest(OUT/"README.md")
    (OUT/"receipts.json").write_text(json.dumps(receipts,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("p_start","first_executor_reasons","resource_webs","joint_positive_xyz_marginal_matches")},indent=2))
    for k in ("within_source_history_height","within_positive_history_height","above_all_source_history_height"):
        print(k,report[k]["n"],report[k]["p_start"])
    print("geometry",{k: report["exact_anchor_summary"]["features"][k] for k in ("target_x","target_y","target_height")})
    print("windows",len(window_ids),"terminal_overrun_ms",report["terminal"]["scope_check_overrun_ms"])


if __name__=="__main__":
    main()
