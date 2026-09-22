"""One finalized-JSON comparison. Standard library only; no runtime/model imports."""
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = 'data/l1/range-request-efficiency-20260922-1/'
PRE = 'data/runtime/range-request-efficiency-preflight-20260922/'
INPUTS = [RUN+'meta.json', RUN+'frames.jsonl', PRE+'actual-thread-settings.json',
          PRE+'launch-result.json', 'data/diagnostics/range-request-stage-cost-20260922/report.json']
EXPECTED = ['f186a7890e5efbe783988c3ceee4e4bde22e8029dba1c522d2fcf9f0e1138356',
            'da7fae8c4eb3ff69f368d6bea502f328a043f4c95aeb4d04dc74914fc17dc2a1']
STAGES = ('acquisition_to_offer', 'offer_to_worker', 'detection_tag', 'hud_and_coasting',
          'state_assembly', 'brain_call_consumer', 'brain_complete_to_publication',
          'publication_to_consumption')


def pin(path):
    raw = (ROOT/path).read_bytes()
    return dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def read(path):
    return json.loads((ROOT/path).read_text())


def stats(values):
    xs = sorted(x for x in values if x is not None)
    return dict(known=len(xs), missing=len(values)-len(xs), **(dict(
        min_ms=xs[0], median_ms=statistics.median(xs), p95_nearest_rank_ms=xs[math.ceil(.95*len(xs))-1],
        max_ms=xs[-1], mean_ms=statistics.mean(xs)) if xs else {}))


def main():
    assert not (OUT/'report.json').exists() and not (OUT/'receipts.json').exists()
    pins = [pin(p) for p in INPUTS]
    assert [p['sha256'] for p in pins[:2]] == EXPECTED
    meta, threads, launch, prior = [read(INPUTS[i]) for i in (0,2,3,4)]
    rows = [json.loads(line) for line in (ROOT/INPUTS[1]).read_text().splitlines()]
    first = [r for r in rows if 'decision_trace' in r]
    decisions = {r['d']:r for r in first}
    assert len(first) == len(decisions) == len(meta['decision_timings']) == meta['decisions'] == 90
    assert set(decisions) == set(range(1,91))
    origin = meta['start']['live_scope']['loop_perf_origin']
    previous, history, group = None, deque(maxlen=5), 'initial'
    warmups, details = Counter(), []
    for timing in meta['decision_timings']:
        row = decisions[timing['d']]
        assert row['decision_timing'] == timing
        assert row['state']['t'] == row['decision_trace']['t'] == timing['acquisition_t']
        # Exact first-consumption linkage, without using rounded row.t.
        assert row['observation_t'] == timing['reflex_acquisition_t']
        earlier = rows[:rows.index(row)]
        assert not any(r.get('d') == row['d'] and r.get('type') != 'executor_release' for r in earlier)
        ts = [origin+timing['acquisition_t']] + [timing[k] for k in (
            'offer_perf','worker_start_perf','detection_tag_complete_perf','hud_complete_perf',
            'brain_call_start_perf','brain_call_complete_perf','ready_publication_perf','first_reflex_consumption_perf')]
        costs = {k:None if a is None or b is None else (b-a)*1000 for k,a,b in zip(STAGES,ts,ts[1:])}
        assert all(x is None or x >= 0 for x in costs.values())
        total = None if ts[-1] is None else (ts[-1]-ts[0])*1000
        error = None if any(v is None for v in costs.values()) else sum(costs.values())-total
        assert error is None or abs(error)<1e-6
        a = timing['acquisition_t']
        gap = None if previous is None else a-previous
        reset = gap is not None and abs(gap-.1)>.025+1e-9
        if reset:
            history.clear()
            group = f'gap_before_decision_{row["d"]}'
        previous = a
        history.append(a)
        residuals = [(t-(a-(4-i)*.1))*1000 for i,t in enumerate(history)] if len(history)==5 else []
        clock = 'warmup' if len(history)<5 else 'invalid_history' if max(map(abs,residuals))>25+1e-6 else 'usable'
        reason = row['decision_trace']['reason']
        if reason == 'warming_up':
            assert clock == 'warmup'
            warmups[group] += 1
        if reason in ('model_event','low_confidence'): assert clock == 'usable'
        if clock == 'invalid_history': history.clear()
        trace = row.get('range_skill_trace')
        execution = trace.get('execution_t') if trace else None
        costs['consumption_to_execution'] = (origin+execution-ts[-1])*1000 if execution is not None and ts[-1] is not None else None
        details.append(dict(decision=row['d'], timing=timing, reason=reason,
            proposal=row['decision_trace']['web_cluster_request'], stages_ms=costs,
            acquisition_to_consumption_ms=total, acquisition_to_publication_ms=(ts[-2]-ts[0])*1000 if ts[-2] is not None else None,
            accounting_error_ms=error, clock_reason=clock, adjacent_reset=reset,
            gap_ms=gap*1000 if gap is not None else None, window_residual_ms=residuals,
            first_execution_reason=trace.get('reason') if trace else None,
            first_fullpress_slack_ms=(trace['valid_until']-execution-.033)*1000 if trace and trace.get('valid_until') is not None else None))
    distributions = {}
    for name,predicate in [('all',lambda r:True), ('model_event',lambda r:r['reason']=='model_event'),
                           ('refusal',lambda r:r['reason']!='model_event')]:
        selected = [d for d in details if predicate(d)]
        distributions[name] = {k:stats([d['stages_ms'][k] for d in selected]) for k in (*STAGES,'consumption_to_execution')}
        for k in ('acquisition_to_consumption','acquisition_to_publication'):
            distributions[name][k] = stats([d[k+'_ms'] for d in selected])
    normal = [r for r in rows if 'type' not in r]
    failures = [r for r in rows if r.get('type') == 'executor_send_failure']
    releases = [r for r in rows if r.get('type') == 'executor_release']
    mirrors = [r for r in meta['executor_events'] if r['type']=='executor_send_failure']
    assert len(failures) == len(mirrors)
    for row,mirror in zip(failures,mirrors):
        # RunLog may append frame filename/index after the immutable event mirror.
        assert {k:v for k,v in row.items() if k not in ('file','i')} == mirror
    assert releases == [r for r in meta['executor_events'] if r['type']=='executor_release']
    steps = [r for r in rows if r.get('range_skill_trace',{}).get('event')=='step']
    accepts = [r for r in steps if r['range_skill_trace']['accepted']]
    returns = [r for r in normal if r.get('pad',{}).get('lt') and r['send_result']['status']=='returned']
    outcomes = []
    for row in accepts:
        tr, send = row['range_skill_trace'], row['send_result']
        owner = tr['pulse_decision_id']
        owned_returns = [r for r in returns if r['range_skill_trace']['pulse_decision_id']==owner]
        owned_failures = [r for r in failures if r['range_skill_trace']['pulse_decision_id']==owner]
        outcomes.append(dict(owner=owner, decision=row['d'], execution_t=tr['execution_t'],
            pulse_press_until=tr['pulse_press_until'], valid_until=tr['valid_until'],
            accept_fullpress_slack_ms=(tr['valid_until']-tr['execution_t']-.033)*1000,
            send_entry_slack_ms=(send['not_after']-send['attempted_t'])*1000,
            send_return_slack_ms=(send['not_after']-send['returned_t'])*1000,
            send_call_ms=(send['returned_t']-send['attempted_t'])*1000,
            accept_to_send_entry_ms=(send['attempted_t']-tr['execution_t'])*1000,
            returned_LT_calls=len(owned_returns), failed_calls=len(owned_failures), first_send=send,
            retained_LT_sends=[dict(d=r['d'], trace=r['range_skill_trace'], send=r['send_result']) for r in owned_returns]))
    recovery = []
    for failed in failures:
        owner = failed['range_skill_trace']['pulse_decision_id']
        assert 'pad' not in failed and failed['proposed_pad']['lt']
        release = [r for r in releases if r['reason']=='send_failed' and r['preceding_send_result']==failed['send_result']]
        assert len(release)==1 and release[0]['release_returned'] and rows.index(release[0])<rows.index(failed)
        later = rows[rows.index(failed)+1:]
        assert not any(r.get('pad',{}).get('lt') and r.get('range_skill_trace',{}).get('pulse_decision_id')==owner for r in later)
        assert not any(r.get('range_skill_trace',{}).get('accepted') and r['range_skill_trace']['decision_id']==owner for r in later)
        later_decisions = [r['d'] for r in later if 'decision_trace' in r]
        recovery.append(dict(cancelled_owner=owner, failed_step=failed, release=release[0],
            later_decisions=len(later_decisions), next_decision=later_decisions[0] if later_decisions else None,
            later_accepted_ids=[r['range_skill_trace']['decision_id'] for r in later if r.get('range_skill_trace',{}).get('accepted')],
            same_ID_reaccept_or_LT=False))
    schedule = meta['decision_schedule']
    phase0 = schedule['origin_t']
    terminal = releases[-1]
    assert terminal['reason']==meta['stop']=='max_time'
    end_observation = terminal['observation_t']
    duration = dict(phase_origin_t=phase0, requested_s=meta['start']['live_scope']['phase_max_s'],
        reported_seconds=meta['seconds'], stop_observation_t=end_observation,
        acquisition_span_s=end_observation-phase0,
        last_processed_observation_t=normal[-1]['observation_t'],
        last_processed_span_s=normal[-1]['observation_t']-phase0,
        last_normal_send_return_span_s=normal[-1]['send_result']['returned_t']-phase0,
        terminal_release_return_span_s=terminal['release_attempts'][-1]['returned_t']-phase0,
        definition='max_time checked on actual acquisition before tick processing; terminal cleanup has separate actual clocks')
    comparison = {k:dict(prior=prior['distributions']['all'][k], current=v)
                  for k,v in distributions['all'].items()}
    report = dict(scope='finalized JSON only; recorded clocks, no inference/native outcome audit',
        loop_perf_origin=origin, stop=meta['stop'], duration=duration,
        normal_rows=len(normal), failed_step_rows=len(failures), metadata_tick_count=meta['ticks'],
        returned_LT_calls=len(returns), releases_returned=sum(r['release_returned'] for r in releases),
        failed_mirror_frame_metadata_extras=[dict(decision=r['d'], **{k:r[k] for k in ('file','i') if k in r}) for r in failures],
        retained_decisions=len(first), decision_reasons=dict(Counter(d['reason'] for d in details)),
        proposals=dict(Counter(d['proposal'] for d in details if d['proposal'] is not None)),
        first_start_execution_reasons=dict(Counter(d['first_execution_reason'] for d in details if d['proposal']=='start')),
        slot_reasons=dict(Counter(s['reason'] for s in schedule['slots'])),
        skipped_slots=[s for s in schedule['slots'] if s['reason']!='offered'],
        worker_queue_misses=meta['missed_decisions'], warmups_by_gap=dict(warmups),
        clock_reason_counts=dict(Counter(d['clock_reason'] for d in details)),
        adjacent_resets=[dict(decision=d['decision'],gap_ms=d['gap_ms']) for d in details if d['adjacent_reset']],
        missing_publication=[d['decision'] for d in details if d['timing']['ready_publication_perf'] is None],
        unconsumed=[d['decision'] for d in details if d['timing']['first_reflex_consumption_perf'] is None],
        accounting_max_error_ms=max(abs(d['accounting_error_ms']) for d in details if d['accounting_error_ms'] is not None),
        exact_first_consumption_links=len(details), per_decision=details, distributions=distributions,
        stage_comparison=comparison, pulse_outcomes=outcomes, recoveries=recovery,
        prior_summary={k:prior[k] for k in ('normal_ticks','retained_decisions','seconds_reported','decision_reason_counts',
            'proposal_counts','slot_reason_counts','warmups_by_gap','returned_LT_calls','single_failed_send')},
        current_thread_settings=threads, prior_thread_settings=prior['actual_thread_settings'], launch_result=launch,
        current_meta_summaries={k:meta[k] for k in ('period_ms','tick_ms','aim_ms','decide_ms','decision_lag_ms','errors')},
        definitions=prior['definitions'],
        limits=['Different scenes/durations; observed stage differences do not establish causal optimization speedup.',
                'All stage values are elapsed time; brain stage is full consumer, not isolated Torch.',
                'Pulse ownership, returned writes and truncated cancellation are not native cast/delivery claims.',
                'No sum of medians; accounting asserted separately for every recorded decision.'])
    assert [pin(p) for p in INPUTS] == pins
    receipts = dict(inputs_before_after=pins, inspected_source=pin('agent/loop.py'),
                    analyzer=pin(Path(__file__).relative_to(ROOT).as_posix()))
    for name,value in [('report.json',report),('receipts.json',receipts)]:
        with (OUT/name).open('x',encoding='utf8',newline='\n') as f:
            json.dump(value,f,indent=2); f.write('\n')
    print(json.dumps({k:report[k] for k in ('duration','normal_rows','failed_step_rows','metadata_tick_count',
        'decision_reasons','proposals','first_start_execution_reasons','slot_reasons','warmups_by_gap',
        'clock_reason_counts','adjacent_resets','missing_publication','unconsumed','distributions','pulse_outcomes')},indent=2))


if __name__ == '__main__':
    main()
