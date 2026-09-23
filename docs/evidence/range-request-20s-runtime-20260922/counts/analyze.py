"""Finalized JSON locators/counts only; no runtime/model/native imports."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = 'data/l1/range-request-20s-20260922-1/'
PRE = 'data/runtime/range-request-20s-preflight-20260922/'
INPUTS = [RUN+'meta.json',RUN+'frames.jsonl'] + [PRE+n+'.json' for n in (
    'launch-result','actual-thread-settings','loader-preflight','binding-consumed','deployment-check')]
EXPECTED = ['4d005fe44444d7701f2c54d2beb93bcfb01398f1f33d345e91ba0dd2efaf8a9f',
            '46002b2e42cff7e1a93dce161bd8f3d2cde77f5a7a606e5ff65f627fa36943ac']


def pin(path):
    raw = (ROOT/path).read_bytes()
    return dict(path=path,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))


def main():
    assert not (OUT/'report.json').exists() and not (OUT/'receipts.json').exists()
    pins = [pin(p) for p in INPUTS]
    assert [p['sha256'] for p in pins[:2]]==EXPECTED
    meta = json.loads((ROOT/INPUTS[0]).read_text())
    rows = [json.loads(s) for s in (ROOT/INPUTS[1]).read_text().splitlines()]
    phase0 = meta['decision_schedule']['origin_t']
    scope = meta['start']['live_scope']
    phase_end = phase0+scope['phase_max_s']
    hard_end = min(phase_end,scope['not_after_t'])
    lines = {id(r):i+1 for i,r in enumerate(rows)}

    def locator(row):
        t = row.get('observation_t',row['t'])
        return dict(jsonl_line=lines[id(row)],decision=row.get('d'),loop_observation_t=t,
            phase_observation_s=t-phase0,frame_reference=row.get('file'),frame_index=row.get('i'))

    first = {r['d']:r for r in rows if 'decision_trace' in r}
    assert len(first)==sum('decision_trace' in r for r in rows)==meta['decisions']==196
    assert set(first)==set(range(1,197))
    for timing in meta['decision_timings']:
        r = first[timing['d']]
        assert timing==r['decision_timing']
        assert timing['acquisition_t']==r['state']['t']==r['decision_trace']['t']
        assert timing['reflex_acquisition_t']==r['observation_t']
    normal = [r for r in rows if 'type' not in r]
    failures = [r for r in rows if r.get('type')=='executor_send_failure']
    releases = [r for r in rows if r.get('type')=='executor_release']
    assert len(normal)+len(failures)==meta['ticks']==836
    assert releases==[r for r in meta['executor_events'] if r['type']=='executor_release']
    mirrors = [r for r in meta['executor_events'] if r['type']=='executor_send_failure']
    assert len(mirrors)==len(failures)==1
    assert {k:v for k,v in failures[0].items() if k not in ('file','i')}==mirrors[0]
    steps = [r for r in rows if r.get('range_skill_trace',{}).get('event')=='step']
    accepted = [r for r in steps if r['range_skill_trace']['accepted']]
    lt = [r for r in normal if r['pad']['lt']]
    assert len(accepted)==len({r['d'] for r in accepted})==13 and len(lt)==25
    pulses = []
    for r in accepted:
        tr = r['range_skill_trace']
        owner,A,E,D = tr['pulse_decision_id'],tr['pulse_accepted_t'],tr['pulse_press_until'],tr['pulse_valid_until']
        assert owner==r['d'] and A<D and abs(E-A-.033)<1e-9
        original = first[owner]
        resource = original['decision_trace']['resources']
        assert resource==tr['resources'] and resource['observed_t']==original['state']['t']
        assert 1<=resource['webs']<=5 and 0<=A-resource['observed_t']<=.1
        owned = [x for x in rows if x.get('range_skill_trace',{}).get('pulse_decision_id')==owner]
        for x in owned:
            xtr=x['range_skill_trace']
            assert (xtr['pulse_accepted_t'],xtr['pulse_press_until'],xtr['pulse_valid_until'])==(A,E,D)
        sends = [x for x in owned if x.get('proposed_pad',{}).get('lt')]
        send_rows=[]
        for x in sends:
            s,xtr=x['send_result'],x['range_skill_trace']
            H=min(E,hard_end)
            expected=min(H,D,resource['observed_t']+.1) if xtr['press_edge'] else H
            assert abs(s['not_after']-expected)<1e-9 and abs(s['release_at']-H)<1e-9
            assert s['scope_not_after']==hard_end
            send_rows.append(dict(**locator(x),first=xtr['press_edge'],accepted=xtr['accepted'],
                send=s,request_slack_at_entry_ms=(D-s['attempted_t'])*1000,
                pulse_slack_at_entry_ms=(E-s['attempted_t'])*1000,
                applicable_slack_at_return_ms=(expected-s['returned_t'])*1000,
                after_D_entry=s['attempted_t']>=D))
        endings=[x for x in owned if x['range_skill_trace']['ended_pulse_decision_id']==owner]
        assert len(endings)==1
        end=endings[0]
        pulses.append(dict(owner=owner,target_id=tr['pulse_target_id'],anchor_t=original['state']['t'],
            first_state_line=lines[id(original)],accepted_locator=locator(r),A=A,E=E,D=D,
            phase_A_s=A-phase0,resources=resource,resource_age_at_A_ms=(A-resource['observed_t'])*1000,
            sends=send_rows,returned_LT_calls=sum(x['send_result']['status']=='returned' for x in sends),
            failed_calls=sum(x['send_result']['status']=='failed' for x in sends),
            ended_locator=locator(end),ended_execution_t=end['range_skill_trace']['execution_t'],
            outcome=end['range_skill_trace']['pulse_outcome']))
    failed=failures[0]
    owner=failed['range_skill_trace']['pulse_decision_id']
    assert owner==62 and not failed['range_skill_trace']['press_edge'] and 'pad' not in failed
    release=next(r for r in releases if r['reason']=='send_failed')
    assert release['preceding_send_result']==failed['send_result'] and release['release_returned']
    assert lines[id(release)]<lines[id(failed)]
    later=rows[lines[id(failed)]:]
    assert not any(r.get('pad',{}).get('lt') and r['range_skill_trace']['pulse_decision_id']==owner for r in later)
    assert not any(r.get('range_skill_trace',{}).get('accepted') and r['d']==owner for r in later)
    recovery=dict(failed_locator=locator(failed),failure=failed,release_locator=locator(release),release=release,
        original_decision_locator=locator(first[owner]),original_state=first[owner]['state'],
        later_decisions=sum('decision_trace' in r for r in later),
        later_accepted_owners=[r['d'] for r in later if r.get('range_skill_trace',{}).get('accepted')],
        same_ID_reaccepted_or_LT=False)
    disengage=[r for r in normal if r.get('note')=='disengage']
    assert len(disengage)==5 and {r['d'] for r in disengage}=={173}
    hp=first[173]
    assert hp['decision_trace']['reason']=='scripted_low_hp_retreat' and hp['decision_trace']['probabilities'] is None
    disengage_detail=dict(original_decision_locator=locator(hp),original_state=hp['state'],
        original_decision_trace=hp['decision_trace'],
        ticks=[dict(**locator(r),send=r['send_result'],pad=r['pad'],ids=r['ids'],coasting=r['coasting']) for r in disengage],
        neighbors=[dict(decision=d,**{k:first[d]['state'][k] for k in ('t','hp','max_hp')},
            reason=first[d]['decision_trace']['reason'],locator=locator(first[d])) for d in (171,172,174,175)])
    loss=[r for r in steps if r['range_skill_trace']['reason'] in ('target_coasting','target_missing_or_ambiguous')]
    loss_rows=[dict(**locator(r),reason=r['range_skill_trace']['reason'],ids=r['ids'],coasting=r['coasting'],
        proposed_target=r['range_skill_trace']['target_id'],send=r['send_result']) for r in loss]
    unobserved=[r for r in first.values() if r['decision_trace']['reason']=='target_unobserved']
    unobserved_rows=[dict(**locator(r),anchor_t=r['state']['t'],phase_anchor_s=r['state']['t']-phase0,
        detection_ids=[x['track'] for x in r['state']['detections']] if r['state']['detections'] is not None else None,
        coasting=r['state']['coasting']) for r in unobserved]
    selections=[]
    previous=None
    for r in first.values():
        target=r['decision_trace']['target']
        if target is not None and target!=previous:
            selections.append(dict(**locator(r),anchor_t=r['state']['t'],phase_anchor_s=r['state']['t']-phase0,
                from_last_nonnull=previous,to_target=target))
            previous=target
    terminal=releases[-1]
    duration=dict(phase0=phase0,phase_end=phase_end,absolute_session_end=scope['not_after_t'],
        startup_budget_s=scope['startup_max_s'],phase_budget_s=scope['phase_max_s'],combined_budget_s=scope['combined_max_s'],
        reported_seconds=meta['seconds'],terminal_observation_t=terminal['observation_t'],
        terminal_observation_age_s=terminal['observation_t']-phase0,
        release_call_age_s=terminal['t']-phase0,
        release_return_age_s=terminal['release_attempts'][-1]['returned_t']-phase0,
        last_processed_observation_age_s=normal[-1]['observation_t']-phase0,
        last_send_return_age_s=normal[-1]['send_result']['returned_t']-phase0)
    model=[r for r in first.values() if r['decision_trace']['reason']=='model_event']
    support={}
    for proposal in ('start','no_new_start'):
        selected=[r for r in model if r['decision_trace']['web_cluster_request']==proposal]
        support[proposal]=dict(unique_decisions=len(selected),ids=[r['d'] for r in selected],
            first_controller_reasons=dict(Counter(r.get('range_skill_trace',{}).get('reason') for r in selected)))
    report=dict(scope='20s finalized JSON counts/locators; no native outcome adjudication',
        checkpoint_sha256_recorded=meta['range_policy']['checkpoint_sha256'],execution_interpretation='request-start-owned-pulse-v1',
        stop=meta['stop'],duration=duration,normal_rows=len(normal),failed_send_rows=len(failures),meta_ticks=meta['ticks'],
        retained_unique_decisions=len(first),decision_reasons=dict(Counter(r['decision_trace']['reason'] for r in first.values())),
        probability_vectors_recorded=sum(r['decision_trace']['probabilities'] is not None for r in first.values()),
        proposal_support=support,accepted_owners=[p['owner'] for p in pulses],returned_LT_calls=len(lt),
        first_LT_returns=sum(r['range_skill_trace']['press_edge'] for r in lt),
        continued_LT_returns=sum(not r['range_skill_trace']['press_edge'] for r in lt),
        pulse_outcomes=dict(Counter(p['outcome'] for p in pulses)),pulses=pulses,recovery=recovery,
        after_D_LT_returns=[dict(owner=p['owner'],**s) for p in pulses for s in p['sends'] if s['after_D_entry'] and s['send']['status']=='returned'],
        returned_release_events=sum(r['release_returned'] for r in releases),disengage=disengage_detail,
        selected_target_transitions=selections,model_target_counts=dict(Counter(str(r['decision_trace']['target']) for r in model)),
        accepted_target_counts=dict(Counter(str(p['target_id']) for p in pulses)),target_loss_locators=loss_rows,
        target_unobserved_locators=unobserved_rows,range_gaps=meta['range_gaps'],errors=meta['errors'],
        schedule_counts=dict(Counter(s['reason'] for s in meta['decision_schedule']['slots'])),
        late_slots=[s for s in meta['decision_schedule']['slots'] if s['reason']!='offered'],
        worker_queue_misses=meta['missed_decisions'],exact_first_consumption_links=len(first),
        unconsumed_decisions=[t['d'] for t in meta['decision_timings'] if t['first_reflex_consumption_perf'] is None],
        preflight={Path(p).stem:json.loads((ROOT/p).read_text()) for p in INPUTS[2:]},
        limits=['All targets are local tracker IDs, not named bot/kill identities.',
            'Log HP is an upstream observation, not independently verified damage/healing.',
            'Locators use loop seconds and phase age, not independently synchronized video PTS.',
            'Request/pulse/send timestamps are recorded software clocks, not physical delivery.',
            'No old 67ms gate, counterfactual scheduler, broad stage campaign or new inference.'])
    assert [pin(p) for p in INPUTS]==pins
    receipts=dict(inputs_before_after=pins,analyzer=pin(Path(__file__).relative_to(ROOT).as_posix()))
    for name,value in [('report.json',report),('receipts.json',receipts)]:
        with (OUT/name).open('x',encoding='utf8',newline='\n') as f:
            json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({k:report[k] for k in ('duration','normal_rows','failed_send_rows','decision_reasons','proposal_support',
        'accepted_owners','returned_LT_calls','first_LT_returns','continued_LT_returns','pulse_outcomes',
        'selected_target_transitions','schedule_counts','unconsumed_decisions')},indent=2))


if __name__=='__main__':
    main()
