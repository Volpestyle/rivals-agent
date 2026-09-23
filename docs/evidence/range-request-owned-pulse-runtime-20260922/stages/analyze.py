"""Finalized recorded clocks/counts only. No project, native or model imports."""
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = 'data/l1/range-request-owned-pulse-20260922-1/'
PRE = 'data/runtime/range-request-owned-pulse-preflight-20260922/'
INPUTS = [RUN+'meta.json', RUN+'frames.jsonl', PRE+'actual-thread-settings.json', PRE+'launch-result.json',
          'data/diagnostics/range-request-efficiency-stage-20260922/report.json']
EXPECTED = ['547045f0609c4e9545f7b294de28a2418f3b359ccdd78edb632dfcf161d31cff',
            'de55f50c202f0a5fe875669aa04dac0051e492a0b679727d3aa6c5f2ce378bde']
STAGES = ('acquisition_to_offer','offer_to_worker','detection_tag','hud_and_coasting',
          'state_assembly','brain_call_consumer','brain_complete_to_publication','publication_to_consumption')


def pin(path):
    raw = (ROOT/path).read_bytes()
    return dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def read(path):
    return json.loads((ROOT/path).read_text())


def stats(values):
    xs = sorted(x for x in values if x is not None)
    return dict(known=len(xs),missing=len(values)-len(xs),**(dict(min_ms=xs[0],
        median_ms=statistics.median(xs),p95_nearest_rank_ms=xs[math.ceil(.95*len(xs))-1],
        max_ms=xs[-1],mean_ms=statistics.mean(xs)) if xs else {}))


def main():
    assert not (OUT/'report.json').exists() and not (OUT/'receipts.json').exists()
    pins = [pin(p) for p in INPUTS]
    assert [p['sha256'] for p in pins[:2]] == EXPECTED
    meta,threads,launch,prior = [read(INPUTS[i]) for i in (0,2,3,4)]
    rows = [json.loads(s) for s in (ROOT/INPUTS[1]).read_text().splitlines()]
    first = {r['d']:r for r in rows if 'decision_trace' in r}
    assert len(first)==sum('decision_trace' in r for r in rows)==meta['decisions']==95
    assert set(first)==set(range(1,96)) and len(meta['decision_timings'])==95
    origin = meta['start']['live_scope']['loop_perf_origin']
    schedule = meta['decision_schedule']
    phase0 = schedule['origin_t']
    phase_end = phase0+meta['start']['live_scope']['phase_max_s']
    scope_end = min(phase_end,meta['start']['live_scope']['not_after_t'])
    details, warmups, history, previous, group = [],Counter(),deque(maxlen=5),None,'initial'
    for timing in meta['decision_timings']:
        row = first[timing['d']]
        dt = row['decision_trace']
        assert row['decision_timing']==timing
        assert row['state']['t']==dt['t']==timing['acquisition_t']
        assert row['observation_t']==timing['reflex_acquisition_t']
        assert not any(r.get('d')==row['d'] for r in rows[:rows.index(row)])
        clocks = [origin+timing['acquisition_t']] + [timing[k] for k in (
            'offer_perf','worker_start_perf','detection_tag_complete_perf','hud_complete_perf',
            'brain_call_start_perf','brain_call_complete_perf','ready_publication_perf','first_reflex_consumption_perf')]
        costs = {k:None if a is None or b is None else (b-a)*1000 for k,a,b in zip(STAGES,clocks,clocks[1:])}
        assert all(x is None or x>=0 for x in costs.values())
        total = (clocks[-1]-clocks[0])*1000 if clocks[-1] is not None else None
        error = None if any(x is None for x in costs.values()) else sum(costs.values())-total
        assert error is None or abs(error)<1e-6
        a = timing['acquisition_t']
        gap = a-previous if previous is not None else None
        reset = gap is not None and abs(gap-.1)>.025+1e-9
        if reset:
            history.clear()
            group = f'gap_before_decision_{row["d"]}'
        previous = a
        history.append(a)
        residuals = [(t-(a-(4-i)*.1))*1000 for i,t in enumerate(history)] if len(history)==5 else []
        clock_reason = 'warmup' if len(history)<5 else 'invalid_history' if max(map(abs,residuals))>25+1e-6 else 'usable'
        if dt['reason']=='warming_up':
            assert clock_reason=='warmup'
            warmups[group]+=1
        if dt['reason'] in ('model_event','low_confidence'): assert clock_reason=='usable'
        if clock_reason=='invalid_history': history.clear()
        tr = row.get('range_skill_trace',{})
        execution = tr.get('execution_t')
        costs['consumption_to_execution'] = (origin+execution-clocks[-1])*1000 if execution is not None and clocks[-1] is not None else None
        resource = dt.get('resources')
        ammo_age = execution-resource['observed_t'] if resource is not None and execution is not None else None
        details.append(dict(decision=row['d'],timing=timing,reason=dt['reason'],proposal=dt['web_cluster_request'],
            target_id=dt['target'],resources=resource,first_execution_reason=tr.get('reason'),
            resource_legal_at_first_execution=(resource is not None and type(resource['webs']) is int and
                1<=resource['webs']<=5 and ammo_age is not None and 0<=ammo_age<=.1),
            resource_age_at_first_execution_ms=ammo_age*1000 if ammo_age is not None else None,
            first_LT=bool(row.get('pad',{}).get('lt')),stages_ms=costs,
            acquisition_to_consumption_ms=total,
            acquisition_to_publication_ms=(clocks[-2]-clocks[0])*1000 if clocks[-2] is not None else None,
            accounting_error_ms=error,gap_ms=gap*1000 if gap is not None else None,adjacent_reset=reset,
            clock_reason=clock_reason,window_residual_ms=residuals))
    dist = {}
    for name,predicate in [('all',lambda d:True),('model_event',lambda d:d['reason']=='model_event'),
                           ('refusal',lambda d:d['reason']!='model_event')]:
        ds = [d for d in details if predicate(d)]
        dist[name] = {k:stats([d['stages_ms'][k] for d in ds]) for k in (*STAGES,'consumption_to_execution')}
        for k in ('acquisition_to_consumption','acquisition_to_publication'):
            dist[name][k] = stats([d[k+'_ms'] for d in ds])
    normal = [r for r in rows if 'type' not in r]
    failures = [r for r in rows if r.get('type')=='executor_send_failure']
    releases = [r for r in rows if r.get('type')=='executor_release']
    assert not failures and releases==meta['executor_events']
    assert len(normal)==meta['ticks']==406
    steps = [r for r in normal if 'range_skill_trace' in r]
    assert all(r['range_skill_trace']['execution_interpretation']=='request-start-owned-pulse-v1' for r in steps)
    accepted = [r for r in steps if r['range_skill_trace']['accepted']]
    lt = [r for r in normal if r['pad']['lt']]
    assert len(accepted)==10 and len({r['d'] for r in accepted})==10 and len(lt)==20
    assert all(r['send_result']['status']=='returned' for r in normal)
    pulses = []
    for row in accepted:
        tr,send = row['range_skill_trace'],row['send_result']
        owner,A,E,D = tr['pulse_decision_id'],tr['pulse_accepted_t'],tr['pulse_press_until'],tr['pulse_valid_until']
        assert owner==row['d'] and tr['press_edge'] and A==tr['execution_t']
        assert A<D and abs(E-A-.033)<1e-9 and E<D+.033
        resource = first[owner]['decision_trace']['resources']
        assert tr['resources']==resource and resource['observed_t']==first[owner]['state']['t']
        assert 1<=resource['webs']<=5 and 0<=A-resource['observed_t']<=.1
        owned = [r for r in steps if r['range_skill_trace']['pulse_decision_id']==owner]
        sends = [r for r in lt if r['range_skill_trace']['pulse_decision_id']==owner]
        assert len(sends)==2
        for r in owned:
            trace = r['range_skill_trace']
            assert (trace['pulse_accepted_t'],trace['pulse_press_until'],trace['pulse_valid_until'])==(A,E,D)
        sent_rows = []
        for r in sends:
            trace,s = r['range_skill_trace'],r['send_result']
            is_first = trace['press_edge']
            H = min(E,scope_end)
            limit = min(H,D,resource['observed_t']+.1) if is_first else H
            assert abs(s['not_after']-limit)<1e-9 and abs(s['release_at']-H)<1e-9
            assert s['scope_not_after']==scope_end
            assert s['attempted_t']<s['returned_t']<s['not_after']
            assert trace['execution_t']<H
            sent_rows.append(dict(decision=r['d'],first=is_first,execution_t=trace['execution_t'],
                send=s,request_slack_at_entry_ms=(D-s['attempted_t'])*1000,
                request_slack_at_return_ms=(D-s['returned_t'])*1000,
                applicable_limit_slack_at_entry_ms=(limit-s['attempted_t'])*1000,
                applicable_limit_slack_at_return_ms=(limit-s['returned_t'])*1000,
                send_ms=(s['returned_t']-s['attempted_t'])*1000,
                ammo_age_at_entry_ms=(s['attempted_t']-resource['observed_t'])*1000,
                after_request_deadline_at_entry=s['attempted_t']>=D,
                after_request_deadline_at_return=s['returned_t']>=D))
        edges = [r for r in owned if r['range_skill_trace']['release_edge']]
        ended = [r for r in owned if r['range_skill_trace']['ended_pulse_decision_id']==owner]
        assert len(edges)==len(ended)==1 and not edges[0]['pad']['lt']
        edge,end = edges[0],ended[0]
        pulses.append(dict(owner=owner,A=A,E=E,D=D,resources=resource,
            acceptance_age_from_anchor_ms=(A-first[owner]['state']['t'])*1000,
            request_slack_at_acceptance_ms=(D-A)*1000,nominal_end_after_D_ms=(E-D)*1000,
            sends=sent_rows,release_edge_execution_t=edge['range_skill_trace']['execution_t'],
            first_observed_nonLT_send=edge['send_result'],
            nonLT_send_return_minus_E_ms=(edge['send_result']['returned_t']-E)*1000,
            ended_at_execution_t=end['range_skill_trace']['execution_t'],outcome=end['range_skill_trace']['pulse_outcome'],
            outcome_is='controller schedule bookkeeping; not physical pulse/cast confirmation'))
    model = [d for d in details if d['reason']=='model_event']
    support = {}
    for proposal in ('start','no_new_start'):
        ds = [d for d in model if d['proposal']==proposal]
        support[proposal] = dict(unique_decisions=len(ds),ids=[d['decision'] for d in ds],
            first_controller_reasons=dict(Counter(d['first_execution_reason'] for d in ds)),
            resource_legal_at_first_execution_ids=[d['decision'] for d in ds if d['resource_legal_at_first_execution']],
            snapshot_ammo_counts=dict(Counter(str(d['resources']['webs']) for d in ds)),
            first_LT_count=sum(d['first_LT'] for d in ds))
    terminal = releases[-1]
    duration = dict(requested_s=meta['start']['live_scope']['phase_max_s'],phase0=phase0,phase_end=phase_end,
        session_end_t=meta['start']['live_scope']['not_after_t'],effective_scope_t=scope_end,
        metadata_seconds=meta['seconds'],stop_acquisition_span_s=terminal['observation_t']-phase0,
        last_processed_span_s=normal[-1]['observation_t']-phase0,
        last_send_return_span_s=normal[-1]['send_result']['returned_t']-phase0,
        terminal_release_return_span_s=terminal['release_attempts'][-1]['returned_t']-phase0)
    report = dict(scope='recorded observed support/counts/clocks; no performance quality or native outcome claim',
        interpretation='request-start-owned-pulse-v1',stop=meta['stop'],duration=duration,
        normal_rows=len(normal),failed_send_rows=len(failures),retained_decisions=len(first),
        accepted_owners=[p['owner'] for p in pulses],LT_returns=len(lt),pulse_outcomes=dict(Counter(p['outcome'] for p in pulses)),
        releases=releases,send_statuses=dict(Counter(r['send_result']['status'] for r in normal)),
        decision_reasons=dict(Counter(d['reason'] for d in details)),proposal_support=support,
        logged_probability_vectors=sum(first[d['decision']]['decision_trace']['probabilities'] is not None for d in details),
        interpretation_trace_counts=dict(Counter(r['range_skill_trace']['execution_interpretation'] for r in steps)),
        pulses=pulses,after_D_continuations=[dict(owner=p['owner'],**s) for p in pulses for s in p['sends'] if s['after_request_deadline_at_entry']],
        slot_reasons=dict(Counter(s['reason'] for s in schedule['slots'])),
        skipped_slots=[s for s in schedule['slots'] if s['reason']!='offered'],
        warmups_by_gap=dict(warmups),worker_queue_misses=meta['missed_decisions'],
        clock_reason_counts=dict(Counter(d['clock_reason'] for d in details)),
        adjacent_resets=[dict(decision=d['decision'],gap_ms=d['gap_ms']) for d in details if d['adjacent_reset']],
        missing_publication=[d['decision'] for d in details if d['timing']['ready_publication_perf'] is None],
        unconsumed=[d['decision'] for d in details if d['timing']['first_reflex_consumption_perf'] is None],
        exact_first_consumption_links=len(details),accounting_max_error_ms=max(abs(d['accounting_error_ms']) for d in details),
        per_decision=details,distributions=dist,
        stage_comparison={k:dict(prior=prior['distributions']['all'][k],current=v) for k,v in dist['all'].items()},
        prior_summary={k:prior[k] for k in ('normal_rows','failed_step_rows','metadata_tick_count','retained_decisions',
            'decision_reasons','proposals','first_start_execution_reasons','slot_reasons','duration','returned_LT_calls')},
        current_thread_settings=threads,prior_thread_settings=prior['actual_thread_settings'] if 'actual_thread_settings' in prior else prior['current_thread_settings'],
        launch_result=launch,current_meta_summaries={k:meta[k] for k in ('period_ms','tick_ms','aim_ms','decide_ms','decision_lag_ms','errors')},
        definitions=prior['definitions'],limits=['No old 67ms gate applied; no counterfactual replay or prediction transfer.',
            'No causal attribution across different scenes/HUD filter/execution interpretation.',
            'No native decode/inference/training; returned send and completed schedule do not establish cast, hit or physical duration.',
            'No actuator check timestamp exists here; entry/return bound a call, not exact game receipt.',
            'Watchdog may neutralize before the next recorded nonLT send; do not infer actual held duration from that row.',
            'Current-label controls mean observed model-head/consumer/executor behavior, not human labels or TP/KO.'])
    assert [pin(p) for p in INPUTS]==pins
    receipts = dict(inputs_before_after=pins,analyzer=pin(Path(__file__).relative_to(ROOT).as_posix()))
    for name,value in [('report.json',report),('receipts.json',receipts)]:
        with (OUT/name).open('x',encoding='utf8',newline='\n') as f:
            json.dump(value,f,indent=2); f.write('\n')
    print(json.dumps({k:report[k] for k in ('duration','decision_reasons','proposal_support','slot_reasons',
        'warmups_by_gap','clock_reason_counts','adjacent_resets','after_D_continuations','distributions')},indent=2))


if __name__=='__main__':
    main()
