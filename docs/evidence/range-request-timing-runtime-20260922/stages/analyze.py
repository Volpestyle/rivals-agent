"""Finalized JSON and stage-clock arithmetic only; no project/runtime imports."""
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = "data/l1/range-request-timing-20260922-1/"
PREFLIGHT = "data/runtime/range-request-timing-preflight-20260922/"
INPUTS = [RUN+"meta.json", RUN+"frames.jsonl", PREFLIGHT+"actual-thread-settings.json", PREFLIGHT+"launch-result.json"]


def pin(path):
    data = (ROOT/path).read_bytes()
    return {"path":path, "sha256":hashlib.sha256(data).hexdigest(), "bytes":len(data)}


def read(path):
    return json.loads((ROOT/path).read_text())


def stats(values):
    known = sorted(v for v in values if v is not None)
    return {"known":len(known), "missing":len(values)-len(known),
            **({"min_ms":known[0], "median_ms":statistics.median(known),
                "p95_nearest_rank_ms":known[math.ceil(.95*len(known))-1], "max_ms":known[-1],
                "mean_ms":statistics.mean(known)} if known else {})}


def main():
    assert not (OUT/"report.json").exists() and not (OUT/"receipts.json").exists()
    pins = [pin(p) for p in INPUTS]
    meta, threads, launch = read(INPUTS[0]), read(INPUTS[2]), read(INPUTS[3])
    rows = [json.loads(line) for line in (ROOT/INPUTS[1]).read_text().splitlines()]
    decisions = {r["decision_trace"]["decision_id"]:r for r in rows if "decision_trace" in r}
    assert len(decisions) == 45 and len(meta["decision_timings"]) == 45
    assert set(decisions) == set(range(1,46))
    origin = meta["start"]["live_scope"]["loop_perf_origin"]
    stages = ("acquisition_to_offer", "offer_to_worker", "detection_tag", "hud_and_coasting",
              "state_assembly", "brain_call_consumer", "brain_complete_to_publication", "publication_to_consumption")
    result_rows, history, previous, warm_group, warm_counts = [], deque(maxlen=5), None, "initial", Counter()
    for timing in meta["decision_timings"]:
        n = timing["d"]
        row = decisions[n]
        assert row["decision_timing"] == timing
        assert row["state"]["t"] == timing["acquisition_t"] == row["decision_trace"]["t"]
        clocks = [origin+timing["acquisition_t"], timing["offer_perf"], timing["worker_start_perf"],
                  timing["detection_tag_complete_perf"], timing["hud_complete_perf"], timing["brain_call_start_perf"],
                  timing["brain_call_complete_perf"], timing["ready_publication_perf"], timing["first_reflex_consumption_perf"]]
        costs = {name:(b-a)*1000 if a is not None and b is not None else None
                 for name,a,b in zip(stages,clocks,clocks[1:])}
        assert all(v is None or v >= 0 for v in costs.values())
        total = (clocks[-1]-clocks[0])*1000 if clocks[-1] is not None else None
        accounting_error = sum(costs.values())-total if all(v is not None for v in costs.values()) else None
        assert accounting_error is None or abs(accounting_error)<1e-6
        acquisition = timing["acquisition_t"]
        gap = acquisition-previous if previous is not None else None
        cadence_reset = gap is not None and abs(gap-.1)>.025+1e-9
        if cadence_reset:
            history.clear(); warm_group=f"gap_before_decision_{n}"
        previous = acquisition
        history.append(acquisition)
        residuals = [(t-(acquisition-(4-i)*.1))*1000 for i,t in enumerate(history)] if len(history)==5 else []
        clock_reason = "warmup" if len(history)<5 else "invalid_history" if max(map(abs,residuals))>25+1e-6 else "usable"
        if clock_reason == "invalid_history": history.clear()
        reason = row["decision_trace"]["reason"]
        if reason == "warming_up": warm_counts[warm_group]+=1
        if reason in ("model_event","low_confidence"): assert clock_reason=="usable"
        if reason == "invalid_history": assert clock_reason=="invalid_history"
        if reason == "warming_up": assert clock_reason=="warmup"
        trace = row.get("range_skill_trace")
        execution_t = trace.get("execution_t") if trace else None
        costs["consumption_to_execution"] = (origin+execution_t-clocks[-1])*1000 if execution_t is not None and clocks[-1] is not None else None
        result_rows.append({"decision":n, "slot":timing["slot"], "acquisition_t":acquisition,
                           "phase_offset_ms":(acquisition-timing["phase_t"])*1000,
                           "observed_reason":reason, "proposal":row["decision_trace"]["web_cluster_request"],
                           "detection_count":None if row["state"]["detections"] is None else len(row["state"]["detections"]),
                           "stages_ms":costs, "acquisition_to_consumption_ms":total,
                           "accounting_error_ms":accounting_error,
                           "acquisition_to_publication_ms":(clocks[-2]-clocks[0])*1000 if clocks[-2] is not None else None,
                           "publication_state": "missing" if clocks[-2] is None else "published",
                           "consumption_state": "unconsumed" if clocks[-1] is None else "consumed",
                           "gap_ms":None if gap is None else gap*1000, "adjacent_reset":cadence_reset,
                           "clock_reason":clock_reason,"window_residual_ms":residuals,
                           "first_execution_reason":trace.get("reason") if trace else None,
                           "first_fullpress_slack_ms":(trace["valid_until"]-execution_t-.033)*1000
                              if trace and trace.get("valid_until") is not None else None})
    grouped = {}
    for name,predicate in (("all",lambda r:True), ("model_event",lambda r:r["observed_reason"]=="model_event"),
                           ("refusal",lambda r:r["observed_reason"]!="model_event"),
                           ("one_detection",lambda r:r["detection_count"]==1),
                           ("multiple_detections",lambda r:r["detection_count"] is not None and r["detection_count"]>1)):
        selected = [r for r in result_rows if predicate(r)]
        grouped[name] = {stage:stats([r["stages_ms"][stage] for r in selected]) for stage in (*stages,"consumption_to_execution")}
        grouped[name]["acquisition_to_consumption"] = stats([r["acquisition_to_consumption_ms"] for r in selected])
        grouped[name]["acquisition_to_publication"] = stats([r["acquisition_to_publication_ms"] for r in selected])
    failures = [r for r in rows if r.get("type")=="executor_send_failure"]
    assert len(failures)==1
    failure=failures[0]; send=failure["send_result"]; trace=failure["range_skill_trace"]
    assert failure["d"]==45 and trace["accepted"] and send["status"]=="failed"
    releases=[r for r in rows if r.get("type")=="executor_release"]
    assert releases==[e for e in meta["executor_events"] if e["type"]=="executor_release"] and len(releases)==2
    assert failures==[e for e in meta["executor_events"] if e["type"]=="executor_send_failure"]
    assert all(r["preceding_send_result"]==send and r["release_returned"] for r in releases)
    normal = [r for r in rows if "type" not in r]
    lt_returned = [r for r in normal if r.get("pad",{}).get("lt",0) and r.get("send_result",{}).get("status")=="returned"]
    assert not lt_returned and len(normal)==196
    failed = {"decision":45, "single_event_key":[send["observation_t"],send["attempted_t"],send["not_after"]],
              "retained_step_row":failure, "two_release_references_same_send":True,
              "initial_accept_fullpress_slack_ms":(trace["valid_until"]-trace["execution_t"]-.033)*1000,
              "send_entry_fullpress_slack_ms":(send["not_after"]-send["attempted_t"])*1000,
              "failed_return_past_fullpress_deadline_ms":(send["returned_t"]-send["not_after"])*1000,
              "send_call_ms":(send["returned_t"]-send["attempted_t"])*1000,
              "accept_to_send_entry_ms":(send["attempted_t"]-trace["execution_t"])*1000,
              "accepted_means":"controller ownership only; no returned LT or delivery claimed"}
    schedule=meta["decision_schedule"]
    assert all(0<=t["acquisition_t"]-t["phase_t"]<=.025 for t in meta["decision_timings"])
    report={"scope":"actual_recorded_stage_clocks_JSON_only_no_inference",
            "loop_perf_origin":origin,"normal_ticks":len(normal),"retained_decisions":len(decisions),
            "seconds_reported":meta["seconds"],"decision_reason_counts":dict(Counter(r["observed_reason"] for r in result_rows)),
            "proposal_counts":dict(Counter(r["proposal"] for r in result_rows if r["proposal"] is not None)),
            "actual_thread_settings":threads,"launch_result":launch,
            "distributions":grouped,"per_decision":result_rows,
            "decision_schedule":schedule,"slot_reason_counts":dict(Counter(s["reason"] for s in schedule["slots"])),
            "adjacent_resets":[{"decision":r["decision"],"slot":r["slot"],"gap_ms":r["gap_ms"]} for r in result_rows if r["adjacent_reset"]],
            "warmups_by_gap":dict(warm_counts),"published_missing":[r["decision"] for r in result_rows if r["publication_state"]=="missing"],
            "unconsumed":[r["decision"] for r in result_rows if r["consumption_state"]=="unconsumed"],
            "first_start_requests":[r for r in result_rows if r["proposal"]=="start"],
            "single_failed_send":failed,"returned_LT_calls":len(lt_returned),"returned_release_events":len(releases),
            "accounting_max_absolute_error_ms":max(abs(r["accounting_error_ms"]) for r in result_rows if r["accounting_error_ms"] is not None),
            "definitions":{"detection_tag":"worker_start through wide detection/tracker if used plus tag loop; not isolated one tag read",
                           "hud_and_coasting":"tag_complete through coasting snapshot and hud(frame)",
                           "brain_call_consumer":"entire actual consumer call including gate/history/features/model where reached; not isolated Torch",
                           "acquisition_to_offer":"actual acquisition origin through capture/guard/reflex aim/tracking before offer; components unseparated",
                           "publication_to_consumption":"readiness to first recorded reflex consumption, includes scheduling/reflex wait",
                           "statistics":"ms; median and nearest-rank p95 per stage; sums checked per-decision, not sums of percentiles"},
            "limits":["No checkpoint, inference, human data, runtime/native imports or original-run prediction/duration transfer.",
                      "Elapsed stage time includes contemporaneous scheduling/contention; per-function CPU time is not measured.",
                      "Failed step, send_failed cancellation and terminal range_lost cancellation reference one attempted send, not three attacks.",
                      "No actual visual cast/delivery inference from controller acceptance or failed send."]}
    receipts={"inputs_before_after":pins, "code_inspected":pin("agent/loop.py"),
              "analyzer":pin(str(Path(__file__).relative_to(ROOT)).replace('\\','/'))}
    assert [pin(p) for p in INPUTS]==pins
    for name,value in (("report.json",report),("receipts.json",receipts)):
        with (OUT/name).open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({"counts":report["decision_reason_counts"],"proposals":report["proposal_counts"],
                      "slots":report["slot_reason_counts"],"resets":report["adjacent_resets"],"warmups":report["warmups_by_gap"],
                      "stages_all":grouped["all"],"stage45":result_rows[-1],
                      "failed_send_margins":{k:v for k,v in failed.items() if k.endswith('_ms')}},indent=2))


if __name__=='__main__':
    main()
