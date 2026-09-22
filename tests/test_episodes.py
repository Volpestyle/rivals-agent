"""Synthetic contract regressions and committed evidence; never opens the corpus."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from agent.episodes import (EpisodeSpec, Observation, Stop, board_observation,
                            score_episode, score_batch, summarise)
from scripts.range_benchmark import inspect_log, score_manifest, main


def spec(**changes):
    values = dict(episode_id='e1', run_id='r1', policy='scripted:77d5032', scenario='near',
                  epoch='spawn1', target='left-bot-life1', track=7, patch='observed-build',
                  patch_evidence='build.png#audit', cooldowns='normal', settings_evidence='settings.png#audit',
                  settings={'bot_health': 'full', 'bot_movement': 'standing',
                            'bindings': 'pad-default', 'swing': 'hold'})
    return EpisodeSpec(**(values | changes))


def ready(t=10, **changes):
    return Observation(**(dict(t=t, kind='ready', evidence='ready.png#audit', epoch='spawn1',
                               target='left-bot-life1', track=7, range_ok=True, identity=True,
                               full_health=True, resources_ready=True) | changes))


def board(t=9, kos=0):
    return board_observation(t, 'spawn1', f'board-{t}.png', {'open': True, 'kos': kos})


def kill(t=15, lo=14.9, hi=15, **changes):
    return Observation(**(dict(t=t, kind='kill', evidence=f'feed-{t}.png#audit', epoch='spawn1',
                               target='left-bot-life1', track=7, identity=True, event_id='ko1', lo=lo, hi=hi,
                               association='native.mp4#14.9-15:reviewer') | changes))


def coverage(lo=10, hi=30, **changes):
    return Observation(**(dict(t=hi, kind='coverage', evidence='native.mp4#10-30:audit', epoch='spawn1',
                               target='left-bot-life1', track=7, identity=True, lo=lo, hi=hi,
                               association='target continuity; no designated completion') | changes))


def success():
    return [board(), ready(), kill(), board(16, 1)]


def test_success_reward_once_and_conservative_occurrence_time():
    observations = success() + [kill(16.5), board(17, 1)]
    result = score_episode(spec(), observations)
    assert result.outcome == 'completed'
    assert result.reward == .95
    assert result.elapsed_s == 5
    assert result.completion_interval_s == pytest.approx((4.9, 5))
    assert result.components['damage'] is None


@pytest.mark.parametrize('change', [{'identity': None}, {'full_health': None}, {'resources_ready': None},
                                    {'range_ok': None}, {'target': 'door'}, {'track': 8}])
def test_readiness_never_inferred_from_detection(change):
    assert score_episode(spec(), [ready(**change)]).outcome == 'setup_failure'


@pytest.mark.parametrize('change', [{'patch': None}, {'patch_evidence': None}, {'cooldowns': 'off'},
                                    {'settings_evidence': None}, {'settings': {}}])
def test_unverified_context_fails_setup(change):
    assert score_episode(spec(**change), success()).outcome == 'setup_failure'


def test_bare_aggregate_increment_is_unknown():
    result = score_episode(spec(), [board(), ready(), board(30, 1)])
    assert result.outcome == 'unknown' and result.reward is None


@pytest.mark.parametrize('change', [{'target': 'right-bot'}, {'track': 8}, {'identity': None},
                                    {'association': None}, {'event_id': None}])
def test_feed_presence_or_wrong_bot_cannot_win(change):
    assert score_episode(spec(), [board(), ready(), kill(**change), board(16, 1)]).outcome != 'completed'


def test_timeout_is_real_failure_with_continuous_audited_coverage():
    result = score_episode(spec(), [ready(), coverage(10, 18), coverage(18, 30)])
    assert result.outcome == 'timeout' and result.reward == -.45


def test_missing_coverage_is_unknown_not_timeout():
    result = score_episode(spec(), [ready(), coverage(10, 18), coverage(19, 30)],
                           stop=Stop(30, 'max_time', 'meta'))
    assert result.outcome == 'unknown' and result.reward is None


@pytest.mark.parametrize('reason', ['capture_loss', 'guard_stop', 'operator_stop', 'error'])
def test_interruption_never_receives_timeout_penalty(reason):
    result = score_episode(spec(), [ready()], stop=Stop(13, reason, 'meta'))
    assert result.outcome == 'interrupted' and result.reward is None


def test_lost_range_is_not_death():
    result = score_episode(spec(), [ready(), Observation(12, 'range', 'frame.png', 'spawn1', range_ok=False)])
    assert result.outcome == 'lost_range' and not result.valid


def test_success_at_deadline_wins_and_delayed_display_is_attributed():
    result = score_episode(spec(), [board(), ready(), kill(t=31, lo=29.9, hi=30), board(31.5, 1)],
                           stop=Stop(30, 'episode_deadline', 'stop.json'))
    assert result.outcome == 'completed' and result.reward == .8


def test_display_after_grace_is_unknown():
    assert score_episode(spec(), [board(), ready(), kill(33, 29, 30), board(34, 1)]).outcome == 'unknown'


def test_boundary_straddling_kill_cannot_be_backdated_or_timeout():
    result = score_episode(spec(), [board(), ready(), coverage(), kill(t=31, lo=29.9, hi=30.1), board(31.5, 1)])
    assert result.outcome == 'unknown' and result.reward is None


def test_reset_and_counter_decrease_cannot_generate_reward():
    result = score_episode(spec(), [board(kos=4), ready(), board(11, 0), kill(), board(16, 5)])
    assert result.outcome == 'unknown'
    result = score_episode(spec(), [board(), ready(), Observation(12, 'reset', 'reset.mp4', 'spawn2'),
                                    kill(), board(16, 1)])
    assert result.outcome == 'interrupted'


def test_unknown_counter_is_not_zero():
    assert score_episode(spec(), [board(kos=None), ready(), kill(), board(16, 1)]).outcome == 'unknown'


def test_multi_ko_jump_is_not_attributed():
    assert score_episode(spec(), [board(), ready(), kill(), board(16, 2)]).outcome == 'unknown'


def test_duplicate_credit_across_episodes_is_rejected():
    second = [board(39, 0), ready(40), kill(45, 44.9, 45), board(46, 1)]
    results = score_batch([(spec(), success(), None), (spec(episode_id='e2'), second, None)])
    assert [r.outcome for r in results] == ['completed', 'unknown']
    assert 'event_already_credited' in results[1].reason
    second[2] = replace(second[2], event_id='invented-fresh-id')
    assert 'counter_already_credited' in score_batch([(spec(), success(), None),
                                                    (spec(episode_id='e2'), second, None)])[1].reason


def test_no_reward_from_hp_decay_healing_or_ult():
    # None of these signals is a scoring input. Existing loop summaries cannot synthesize reward.
    meta = {'stop': 'max_time', 'seconds': 20, 'hp': 250, 'ult_charge': 1, 'damage': 100}
    report = inspect_log(meta, [{'t': 0, 'state': {'hp': 500}}, {'t': 20, 'state': {'hp': 250}}])
    assert report['gameplay_benchmark'] is False
    assert score_episode(spec(), [ready()]).reward is None


def test_attempted_denominators_include_every_interruption_and_unknown():
    results = [score_episode(spec(), success()), score_episode(spec(), [ready(), coverage()]),
               score_episode(spec(), [ready()], stop=Stop(12, 'operator_stop', 'meta')),
               score_episode(spec(), [ready()]), score_episode(spec(), [])]
    summary = summarise(results, wall_seconds=1800, reset_seconds=[1, None, 3])
    assert summary['scheduled_trials'] == 5 and summary['attempted_episodes'] == 4
    assert summary['valid_episodes'] == 2 and summary['success_per_attempt'] == .25
    assert summary['success_per_valid_episode'] == .5
    assert summary['restricted_completion_s'] == 16.25
    assert summary['valid_episodes_per_hour'] == 4
    assert summary['feasibility_gate']['passed'] is False
    assert len(summary['failures']) == 4


def test_invalid_timestamps_and_duplicate_episode_ids_fail_loudly():
    with pytest.raises(ValueError):
        ready(float('nan'))
    with pytest.raises(ValueError):
        kill(lo=16)
    with pytest.raises(ValueError):
        score_episode(spec(), [ready(), board()])
    with pytest.raises(ValueError):
        score_batch([(spec(), success(), None)] * 2)
    with pytest.raises(ValueError):
        score_batch([(spec(), success(), None), (spec(episode_id='e2'), success(), None)])


def manifest():
    return {'schema': 'range-benchmark-v1', 'scripted_baseline': 'scripted:77d5032',
            'scenarios': {'near': 'plaza front/near/full resources', 'mid': 'plaza left/mid/full resources'},
            'trials': [{'spec': asdict(spec()), 'observations': [asdict(o) for o in success()]},
                       {'spec': asdict(spec(episode_id='e2', run_id='r2', scenario='mid'))}]}


def test_unrun_schedule_slots_are_preserved_not_dropped():
    report = score_manifest(manifest())
    assert report['summary']['scheduled_trials'] == 2
    assert report['summary']['setup_failures'] == 1
    assert report['human_reference']['comparison'] == 'not_established'
    assert report['promotion'] is None


def test_native_log_read_is_descriptive_and_patch_not_invented():
    path = Path(__file__).resolve().parents[1] / 'docs/evidence/l4/plaza30-meta.json'
    report = inspect_log(json.loads(path.read_text()), [])
    assert report['scoreboards'][0]['parsed']['kos'] == 2
    assert report['observed_patch'] is None
    assert report['gameplay_benchmark'] is False


def test_cli_scores_explicit_manifest_without_live_imports(tmp_path, capsys):
    path = tmp_path / 'benchmark.json'
    path.write_text(json.dumps(manifest()))
    assert main(['score', str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['summary']['successes'] == 1


def test_log_adapter_preserves_range_gaps(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'stop': 'max_time', 'range_gaps': [[12, None]]}))
    (run / 'frames.jsonl').write_text(json.dumps({'t': 30, 'ms': 4}) + '\n')
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[9, 32])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == 'lost_range'


def test_accepted_gate_primary_denominator_and_scope_evidence():
    win = score_episode(spec(), success())
    setup = score_episode(spec(), [])
    results = [win] * 8 + [setup] * 2
    report = summarise(results, scope_audited_trials=10, scope_breaches=0, matched_baseline=True)
    assert report['success_per_scheduled_trial'] == .8
    assert report['success_per_attempt'] == 1
    assert report['feasibility_gate']['passed'] is True
    assert report['scheduled_success_wilson95'] == pytest.approx([.49016, .94332], abs=1e-5)
    assert summarise(results)['feasibility_gate']['passed'] is None
    assert summarise(results, scope_audited_trials=10, scope_breaches=1,
                     matched_baseline=True)['feasibility_gate']['passed'] is False
    assert summarise(results, scope_audited_trials=10, scope_breaches=0,
                     matched_baseline=False)['feasibility_gate']['passed'] is False


def test_baseline_settings_mismatch_blocks_comparison():
    m = manifest()
    m['trials'] += [dict(slot, spec=slot['spec'] | {'episode_id': 'candidate-' + slot['spec']['episode_id'],
                                                   'run_id': 'candidate-' + slot['spec']['run_id'],
                                                   'policy': 'candidate:abc', 'patch': 'different-build'})
                    for slot in list(m['trials'])]
    assert score_manifest(m)['comparable_schedule'] is False


@pytest.mark.parametrize('relative,size,kos,feed', [
    ('scoreboard-back-native.jpg', [2560, 1440], 3, False),
    ('scoreboard-back-720.jpg', [1280, 720], None, False),
    ('scoreboard/killfeed-a.jpg', [2560, 1440], None, True),
    ('plaza30-start-confirm-2-native.jpg', [2560, 1440], None, False),
])
def test_inspected_pixel_sample(relative, size, kos, feed):
    pytest.importorskip('cv2')
    from scripts.range_benchmark import read_pixels
    path = Path(__file__).resolve().parents[1] / 'docs/evidence/l4' / relative
    report = read_pixels(path)
    assert report['native'] == size
    assert report['scoreboard']['kos'] == kos
    assert report['killfeed_present'] is feed
    assert report['designated_target_completion'] is None
    assert report['full_target_health'] is None


def pilot_manifest():
    m = manifest()
    m['trials'] = []
    for policy in ('scripted:77d5032', 'candidate:abc'):
        for i in range(10):
            ident = f'{policy}-{i}'
            s = spec(episode_id=ident, run_id=ident, policy=policy, scenario='near' if i < 5 else 'mid')
            m['trials'].append({'spec': asdict(s), 'observations': [asdict(o) for o in success()],
                                'scope_audit': {'breach': False, 'evidence': f'{ident}/scope-audit'}})
    return m


def test_r1_pre_ready_reset_invalidates_old_baseline():
    obs = [board(), Observation(9.5, 'reset', 'reset.mp4', 'spawn1'), ready(), kill(), board(16, 1)]
    r = score_episode(spec(), obs)
    assert r.outcome != 'completed' and r.reward is None


def test_r1_new_epoch_and_fresh_post_reset_baseline_is_valid():
    obs = [Observation(8, 'reset', 'reset.mp4', 'spawn2')]
    obs += [replace(o, epoch='spawn2') for o in success()]
    r = score_episode(spec(epoch='spawn2'), obs)
    assert r.outcome == 'completed' and r.reward == .95


@pytest.mark.parametrize('gap,outcome', [([8, None], 'lost_range'), ([8, 9], 'completed'),
                                       ([12, None], 'lost_range'), ([8, 11], 'lost_range')])
def test_r2_log_gap_state_at_readiness(tmp_path, gap, outcome):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'stop': 'max_time', 'range_gaps': [gap]}))
    (run / 'frames.jsonl').write_text(json.dumps({'t': 30}) + '\n')
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == outcome


def test_r3_unexecuted_baseline_cannot_pass_candidate_gate():
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = []
    report = score_manifest(m)
    assert report['comparable_schedule'] is True
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False
    assert report['by_policy']['scripted:77d5032']['setup_failures'] == 10


def test_r3_executed_audited_timeout_baseline_is_valid_comparison():
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(o) for o in (ready(), coverage())]
    report = score_manifest(m)
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is True
    assert report['by_policy']['scripted:77d5032']['outcomes'] == {'timeout': 10}


def test_r4_joint_context_multiplicity_must_match():
    m = pilot_manifest()
    for i, slot in enumerate(m['trials']):
        moving = i % 5 == 4 if i < 10 else i % 5 != 4
        slot['spec']['settings']['bot_movement'] = 'moving' if moving else 'standing'
    report = score_manifest(m)
    assert report['comparable_schedule'] is False
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False


def test_r4_matching_multiplicity_valid_control():
    m = pilot_manifest()
    for i, slot in enumerate(m['trials']):
        slot['spec']['settings']['bot_movement'] = 'moving' if i % 5 == 4 else 'standing'
    report = score_manifest(m)
    assert report['comparable_schedule'] is True
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is True


def test_r4_unused_declared_scenario_blocks_gate():
    m = pilot_manifest()
    for slot in m['trials']:
        slot['spec']['scenario'] = 'near'
    report = score_manifest(m)
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False


@pytest.mark.parametrize('captured_t,outcome', [(None, 'unknown'), (16, 'completed'), (33, 'unknown')])
def test_legacy_board_timestamp_is_never_an_acquisition_bound(tmp_path, captured_t, outcome):
    run = tmp_path / 'run'
    run.mkdir()
    b = {'t': 16, 'file': 'board.png', 'parsed': {'open': True, 'kos': 1}}
    if captured_t is not None:
        b['captured_t'] = captured_t
        b['capture_interval'] = [captured_t - .1, captured_t]
        b['capture_clock'] = 'grab_start_to_return_loop_seconds'
    (run / 'meta.json').write_text(json.dumps({'stop': 'max_time', 'scoreboards': [b]}))
    (run / 'frames.jsonl').write_text(json.dumps({'t': 30}) + '\n')
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32],
                          observations=[asdict(o) for o in (board(), ready(), kill())])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == outcome


def test_r1_fresh_board_cannot_rehabilitate_reused_reset_epoch():
    obs = [board(7), Observation(8, 'reset', 'reset.mp4', 'spawn1'), *success()]
    r = score_episode(spec(), obs)
    assert r.outcome == 'setup_failure' and r.reason == 'reset_reused_epoch'


def test_r1_wrong_ready_epoch_after_reset_is_rejected():
    obs = [Observation(8, 'reset', 'reset.mp4', 'spawn2'), *success()]
    assert score_episode(spec(), obs).reason == 'readiness_epoch_precedes_reset'


@pytest.mark.parametrize('recovery,outcome', [(None, 'lost_range'), (9, 'completed')])
def test_r2_pure_scorer_preserves_range_state(recovery, outcome):
    obs = [Observation(8, 'range', 'lost.png', 'spawn1', range_ok=False)]
    if recovery is not None:
        obs.append(Observation(recovery, 'range', 'recovered.png', 'spawn1', range_ok=True))
    obs += success()
    assert score_episode(spec(), sorted(obs, key=lambda o: o.t)).outcome == outcome


def test_r2_overlapping_gap_recovery_does_not_clear_active_loss(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'range_gaps': [[7, 9], [8, None]]}))
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == 'lost_range'


def test_r3_readiness_alone_does_not_prove_baseline_execution():
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(ready())]
    report = score_manifest(m)
    assert report['execution_evidence']['scripted:77d5032']['auditable_executed_slots'] == 0
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False


def test_r3_audited_baseline_setup_failure_is_retained_with_supported_bins():
    m = pilot_manifest()
    m['trials'][0]['observations'] = [asdict(ready(full_health=False))]
    report = score_manifest(m)
    assert report['by_policy']['scripted:77d5032']['setup_failures'] == 1
    assert report['execution_evidence']['scripted:77d5032']['auditable_executed_slots'] == 10
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is True


def test_r4_declared_bin_without_started_baseline_encounter_is_not_support():
    m = pilot_manifest()
    for slot in m['trials'][5:10]:
        slot['observations'] = [asdict(ready(full_health=False))]
    report = score_manifest(m)
    assert report['comparable_schedule'] is True
    assert report['execution_evidence']['scripted:77d5032']['started_by_scenario']['mid'] == 0
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False


def test_legacy_board_can_be_supplied_as_explicit_audited_observation(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'scoreboards': [
        {'t': 2, 'file': 'board.png', 'parsed': {'open': True, 'kos': 1}}]}))
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == 'completed'


def acquired_board(lo, hi, kos):
    return board_observation(hi, 'spawn1', 'native-board.png', {'open': True, 'kos': kos},
                             capture_interval=[lo, hi], capture_clock='grab_start_to_return_loop_seconds')


@pytest.mark.parametrize('baseline_interval,after_interval,outcome', [
    ((8.9, 9), (15.9, 16), 'completed'),
    ((9.9, 10.1), (15.9, 16), 'unknown'),
    ((8.9, 9), (14.9, 16), 'unknown'),
])
def test_grab_intervals_cannot_straddle_ready_or_kill_boundary(baseline_interval, after_interval, outcome):
    obs = [acquired_board(*baseline_interval, 0), ready(), kill(), acquired_board(*after_interval, 1)]
    r = score_episode(spec(), sorted(obs, key=lambda o: o.t))
    assert r.outcome == outcome
    b = acquired_board(*after_interval, 1)
    assert (b.lo, b.hi) == after_interval
    assert asdict(b)['capture_clock'] == 'grab_start_to_return_loop_seconds'


def test_grab_interval_cannot_cross_reset_even_when_return_is_after_reset():
    obs = [Observation(8, 'reset', 'reset.mp4', 'spawn2'),
           replace(acquired_board(7.9, 9, 0), epoch='spawn2')]
    obs += [replace(o, epoch='spawn2') for o in (ready(), kill(), board(16, 1))]
    assert score_episode(spec(epoch='spawn2'), obs).outcome == 'unknown'


def test_automatic_board_without_grab_interval_is_not_upgraded(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'scoreboards': [
        {'t': 14, 'captured_t': 16, 'file': 'board.png', 'parsed': {'open': True, 'kos': 1}}]}))
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32],
                          observations=[asdict(o) for o in (board(), ready(), kill())])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == 'unknown'


def test_adapter_preserves_ambiguous_grab_interval(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    b = {'t': 14, 'captured_t': 16, 'capture_interval': [14.9, 16],
         'capture_clock': 'grab_start_to_return_loop_seconds',
         'file': 'board.png', 'parsed': {'open': True, 'kos': 1}}
    (run / 'meta.json').write_text(json.dumps({'scoreboards': [b]}))
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32],
                          observations=[asdict(o) for o in (board(), ready(), kill())])
    report = score_manifest(m, tmp_path)
    assert report['results'][0]['outcome'] == 'unknown'
    assert report['logs']['e1']['scoreboards'][0]['capture_interval'] == [14.9, 16]
    assert report['logs']['e1']['scoreboards'][0]['capture_clock'] == b['capture_clock']


def test_r1b_reset_history_survives_trial_boundary():
    first = success() + [board(19, 1), Observation(20, 'reset', 'reset.mp4', 'spawn2')]
    second = [board(19, 1), ready(30), kill(35, 34.9, 35, event_id='ko2'), board(36, 2)]
    results = score_batch([(spec(), first, None), (spec(episode_id='e2'), second, None)])
    assert results[0].outcome == 'completed'
    assert results[1].outcome != 'completed' and results[1].reward is None


def test_r1b_fresh_epoch_baseline_after_prior_trial_reset_passes():
    first = success() + [board(19, 1), Observation(20, 'reset', 'reset.mp4', 'spawn2')]
    second = [replace(o, epoch='spawn2') for o in
              (board(29, 0), ready(30), kill(35, 34.9, 35, event_id='ko2'), board(36, 1))]
    results = score_batch([(spec(), first, None), (spec(episode_id='e2', epoch='spawn2'), second, None)])
    assert [r.outcome for r in results] == ['completed', 'completed']
    assert [r.counter_credit for r in results] == [1, 1]


@pytest.mark.parametrize('recovery,outcome', [(9.999, 'completed'), (10, 'completed'), (10.001, 'lost_range')])
def test_r2b_recovery_at_ready_uses_half_open_gap(tmp_path, recovery, outcome):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'meta.json').write_text(json.dumps({'range_gaps': [[8, recovery]]}))
    m = manifest()
    m['trials'][0].update(run_dir='run', log_interval=[8, 32])
    assert score_manifest(m, tmp_path)['results'][0]['outcome'] == outcome


@pytest.mark.parametrize('reverse', [False, True])
def test_r2b_tied_loss_and_recovery_remain_conservative(reverse):
    tied = [Observation(10, 'range', 'loss.png', 'spawn1', range_ok=False),
            Observation(10, 'range', 'recovered.png', 'spawn1', range_ok=True)]
    if reverse:
        tied.reverse()
    obs = sorted(success() + tied, key=lambda o: o.t)
    assert score_episode(spec(), obs).outcome == 'lost_range'


def test_r3b_same_ready_frame_is_not_post_ready_execution():
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(ready()), asdict(Observation(
            10, 'range', 'same-ready-frame.png', 'spawn1', range_ok=True))]
    report = score_manifest(m)
    evidence = report['execution_evidence']['scripted:77d5032']
    assert evidence['auditable_executed_slots'] == 0
    assert evidence['started_by_scenario'] == {'near': 0, 'mid': 0}
    assert evidence['comparison_ready'] is False
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False
    assert report['by_policy']['scripted:77d5032']['scheduled_trials'] == 10


def test_r1b_reciting_same_reset_in_next_trial_is_idempotent():
    reset = Observation(20, 'reset', 'reset.mp4', 'spawn2')
    first = success() + [reset]
    second = [replace(reset, evidence='second-audit-of-same-reset')]
    second += [replace(o, epoch='spawn2') for o in (board(29), ready(30), kill(35, 34.9, 35), board(36, 1))]
    results = score_batch([(spec(), first, None), (spec(episode_id='e2', epoch='spawn2'), second, None)])
    assert [r.outcome for r in results] == ['completed', 'completed']


def test_r1b_reset_history_is_scoped_to_run():
    first = success() + [Observation(20, 'reset', 'reset.mp4', 'spawn2')]
    results = score_batch([(spec(), first, None), (spec(episode_id='other', run_id='other'), success(), None)])
    assert [r.outcome for r in results] == ['completed', 'completed']


def test_r1b_reset_seen_on_setup_failure_still_constrains_next_trial():
    first = [ready(full_health=False), Observation(20, 'reset', 'reset.mp4', 'spawn2')]
    second = [board(29), ready(30), kill(35, 34.9, 35), board(36, 1)]
    results = score_batch([(spec(), first, None), (spec(episode_id='e2'), second, None)])
    assert [r.outcome for r in results] == ['setup_failure', 'setup_failure']
    assert results[1].reason == 'readiness_epoch_precedes_reset'


def test_r1b_same_time_conflicting_reset_epochs_cannot_rewrite_history():
    first = success() + [Observation(20, 'reset', 'reset.mp4', 'spawn2')]
    second = [Observation(20, 'reset', 'contradictory-reset.mp4', 'spawn3')]
    second += [replace(o, epoch='spawn3') for o in (board(29), ready(30), kill(35, 34.9, 35), board(36, 1))]
    results = score_batch([(spec(), first, None), (spec(episode_id='e2', epoch='spawn3'), second, None)])
    assert results[1].outcome == 'setup_failure'
    assert results[1].reason == 'conflicting_reset_epochs'


@pytest.mark.parametrize('reverse', [False, True])
def test_r2b_conflicting_pre_ready_state_does_not_depend_on_row_order(reverse):
    tied = [Observation(9, 'range', 'loss.png', 'spawn1', range_ok=False),
            Observation(9, 'range', 'recovered.png', 'spawn1', range_ok=True)]
    if reverse:
        tied.reverse()
    assert score_episode(spec(), sorted(tied + success(), key=lambda o: o.t)).outcome == 'lost_range'


@pytest.mark.parametrize('stop_t,supported', [(10, False), (10.001, True)])
def test_r3b_stop_must_follow_ready_to_supply_started_support(stop_t, supported):
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(ready())]
        slot['stop'] = asdict(Stop(stop_t, 'operator_stop', 'operator-stop.json'))
    report = score_manifest(m)
    evidence = report['execution_evidence']['scripted:77d5032']
    assert evidence['auditable_executed_slots'] == 10  # even immediate recorded interruptions stay
    assert evidence['comparison_ready'] is supported
    assert evidence['started_by_scenario'] == {'near': 5 if supported else 0, 'mid': 5 if supported else 0}
    assert report['by_policy']['scripted:77d5032']['outcomes'] == {'interrupted': 10}


def test_r3b_unknown_duration_stops_at_actual_last_observation():
    assert score_episode(spec(), [ready()]).end_t == 10
    assert score_episode(spec(), [ready()]).elapsed_s == 0
    obs = [ready(), Observation(12, 'range', 'later-frame.png', 'spawn1', range_ok=True)]
    result = score_episode(spec(), obs)
    assert result.outcome == 'unknown' and result.end_t == 12 and result.elapsed_s == 2
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(o) for o in obs]
    report = score_manifest(m)
    assert report['execution_evidence']['scripted:77d5032']['comparison_ready'] is True
    assert report['by_policy']['scripted:77d5032']['outcomes'] == {'unknown': 10}


def test_r3b_post_stop_frames_do_not_establish_started_encounter():
    m = pilot_manifest()
    for slot in m['trials'][:10]:
        slot['observations'] = [asdict(ready()), asdict(Observation(
            12, 'range', 'after-stop.png', 'spawn1', range_ok=True))]
        slot['stop'] = asdict(Stop(10, 'operator_stop', 'operator-stop.json'))
    report = score_manifest(m)
    assert report['execution_evidence']['scripted:77d5032']['started_by_scenario'] == {'near': 0, 'mid': 0}
    assert report['by_policy']['candidate:abc']['feasibility_gate']['passed'] is False
