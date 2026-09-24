"""Focused B0 guards; synthetic payloads never open the demonstration corpus."""
from dataclasses import replace
from types import SimpleNamespace
import json
import math
import pytest

pytest.importorskip('mlx')
np = pytest.importorskip('numpy')
from policy import b0


def target(cls=0, lo=5.2, hi=5.3):
    return b0.Target(cls, lo, hi, 0, ('ability_cast',), hi)


def test_intervals_crossing_boundaries_and_ambiguous_order_are_not_negatives():
    assert b0.next_target([target(lo=4.9, hi=5.1)], 5, horizon=1)[1] == 'interval_crosses_decision'
    assert b0.next_target([target(lo=5.9, hi=6.1)], 5, horizon=1)[1] == 'interval_crosses_horizon'
    assert b0.next_target([target(), target(1, 5.25, 5.4)], 5, horizon=1)[1] == 'ambiguous_first_event'
    label, reason = b0.next_target([target()], 5, horizon=1)
    assert reason is None and label[:3] == pytest.approx((0, .2, .3))
    assert b0.next_target([], 5, horizon=1)[0][0] == b0.NONE
    assert b0.interval_error(.25, .2, .3) == 0
    assert b0.interval_error(.4, .2, .3) == pytest.approx(.1)


def test_most_recent_is_confirmed_past_not_previous_future_target():
    assert b0.most_recent([target()], 5) == b0.NONE
    assert b0.most_recent([target()], 5.3) == 0
    assert b0.most_recent([target(), target(1, 5.25, 5.4)], 5.5) == b0.NONE


def test_cast_charge_dedup_preserves_union_and_same_kind_ambiguity(monkeypatch):
    cast = SimpleNamespace(kind='ability_cast', t_from=5.2, t_to=5.3, known_at=6.6,
                           slot='swing', amount=4, segment=0, slot_pos='swing')
    charge = SimpleNamespace(**(vars(cast) | dict(kind='charges_spent', t_from=5.1, t_to=5.4, amount=1, known_at=7.0)))
    clip = SimpleNamespace(events=[cast, charge], events_meta={'slot_mapping': {'swing': 'swing'}})
    monkeypatch.setattr(b0.Demos, 'window_event', lambda c, e: e, raising=False)
    events, counts = b0.targets(clip)
    assert len(events) == 1 and (events[0].lo, events[0].hi) == (5.1, 5.4)
    assert counts['corroborating_charge_merged'] == 1
    clip.events = [cast, SimpleNamespace(**(vars(cast) | dict(t_to=5.35)))]
    assert len(b0.targets(clip)[0]) == 2
    clip.events = [SimpleNamespace(**(vars(cast) | dict(slot=None)))]
    unknown = b0.targets(clip)[0]
    assert len(unknown) == 4 and all(not e.certain for e in unknown)


def raw_row(t):
    return dict(t=t, playing=True, aside=None, cut=False,
                hud=dict(hp=250, bar_fill=1, webs=5,
                         abilities={k: [True, 1] for k in ('get_over_here', 'swing', 'uppercut', 'teamup')},
                         cooldowns={k: math.ceil(10-t) for k in ('get_over_here', 'swing', 'uppercut', 'teamup')}))


def visibility():
    vis = b0.Visibility.__new__(b0.Visibility)
    vis.rows = [raw_row(round(4.9 + i / 10, 3)) for i in range(14)]
    vis.times = np.array([r['t'] for r in vis.rows])
    vis.meta = {'slot_mapping': {k: k for k in ('get_over_here', 'swing', 'uppercut', 'teamup')},
                'charge_maxima': {'swing': 3, 'uppercut': 2}}
    return vis


def test_unknowns_missing_frames_margin_and_raw_changes_censor_no_event():
    seg = SimpleNamespace(start_t=0, end_t=20)
    vis = visibility()
    assert vis.covers(5, 6, seg, []) == (True, None)
    vis.rows[5]['hud']['abilities']['teamup'] = [False, None]
    vis.rows[5]['hud']['cooldowns']['teamup'] = None
    assert vis.covers(5, 6, seg, [target()])[1] == 'unreadable:teamup'
    vis = visibility()
    vis.rows[5]['hud']['webs'] = 4
    assert 'raw_change' in vis.covers(5, 6, seg, [])[1]
    vis = visibility()
    vis.rows.pop(5)
    vis.times = np.array([r['t'] for r in vis.rows])
    assert vis.covers(5, 6, seg, [])[1] == 'missing_visibility_frame'
    assert visibility().covers(5, 6, SimpleNamespace(start_t=0, end_t=6.5), [])[1] == 'visibility_segment_margin'


def test_channel_observability_requires_readable_charges_and_mapping():
    row = raw_row(0)
    mapping = {k: k for k in row['hud']['abilities']}
    row['hud']['abilities']['swing'] = [False, None]
    row['hud']['cooldowns']['swing'] = 3
    assert not b0.observed_channels(row, mapping, {'swing': 3, 'uppercut': 2})[0]['swing']
    row['hud']['abilities']['swing'][1] = 1
    assert b0.observed_channels(row, mapping, {'swing': 3, 'uppercut': 2})[0]['swing']
    row['hud']['abilities']['swing'][0] = None
    assert not b0.observed_channels(row, mapping, {'swing': 3, 'uppercut': 2})[0]['swing']
    mapping.pop('teamup')
    assert not b0.observed_channels(row, mapping, {'swing': 3, 'uppercut': 2})[0]['teamup']


def test_train_side_identity_gate_precedes_payload_access(monkeypatch):
    calls = []
    def clips_in(side):
        calls.append(side)
        return [SimpleNamespace(id='sealed', group='twitch:2877719252')]
    monkeypatch.setattr(b0.Demos, 'load_split', lambda name: SimpleNamespace(clips_in=clips_in))
    monkeypatch.setattr(b0, 'Cache', lambda *a, **kw: pytest.fail('opened cache before identity gate'))
    with pytest.raises(ValueError, match='exactly'):
        b0.build()
    assert calls == ['train']


def test_selective_cache_never_opens_other_arrays_and_clock_is_causal(tmp_path, monkeypatch):
    from policy.train import Cache
    for name, origin in [('allowed', .027), ('sealed', 0)]:
        (tmp_path / f'{name}.json').write_text(json.dumps({'id': name, 'dim': 2, 't_origin': origin}))
    np.savez(tmp_path / 'allowed.npz', emb=np.ones((3, 2)), t=np.array([.027, .127, .227]))
    # Sealed NPZ deliberately absent: opening it would fail.
    with pytest.raises(TypeError):
        Cache(tmp_path)
    cache = Cache(tmp_path, ids={'allowed'})
    assert set(cache.by_clip) == {'allowed'}
    assert cache.index_at('allowed', .15) == 1
    assert cache.by_clip['allowed'][0][1] <= .15
    assert cache.index_at('allowed', -.01) is None
    assert cache.index_at('allowed', .5) is None


def test_fold_statistics_use_only_fit_rows_and_missing_classes_stay_unsupported():
    fit = [dict(target=0, lo=.1, hi=.3), dict(target=0, lo=.3, hi=.5), dict(target=b0.NONE, lo=0, hi=0)]
    stats = b0.fitted_stats(fit)
    assert stats['majority'] == 0
    assert stats['medians'][0] == pytest.approx(.3)
    assert stats['medians'][1] is None and stats['class_weights'][1] == 0
    result = b0.metrics(fit, np.array([0, 0, b0.NONE]), np.zeros((3, 5)))
    assert result['per_class']['teamup']['support'] == 0
    assert result['macro_f1'] == pytest.approx(2 / 6)


def test_saved_gru_reproduces_predictions_with_frames_only_layout(tmp_path, monkeypatch):
    monkeypatch.setitem(b0.CONFIG, 'epochs', 1)
    x = np.random.default_rng(0).normal(size=(4, 51, 386)).astype(np.float32)
    records = [dict(session='day' if i < 2 else 'req', target=0 if i % 2 == 0 else b0.NONE,
                    lo=.2 if i % 2 == 0 else 0, hi=.3 if i % 2 == 0 else 0, recent=b0.NONE)
               for i in range(4)]
    records[2]['target'] = 1  # unseen on fit side: model timing has support, median does not
    report = b0.fit_fold(x, records, 'req', tmp_path)
    assert report['train_windows'] == report['dev_windows'] == 2
    model = b0.Head(386, 11)
    model.load_weights(report['checkpoint'])
    actual = np.asarray(model(b0.mx.array(x[2:])))[:, :6]
    saved = np.load(tmp_path / 'day-to-req' / 'predictions.npz')
    np.testing.assert_allclose(actual, saved['logits'], atol=1e-6)
    assert report['fitted_stats']['counts'] == [1, 0, 0, 0, 0, 1]

    assert report['model']['timing']['scored'] == 1
    assert report['baselines']['train_majority']['timing']['scored'] == 0
    assert report['timing_comparison_common_support']['windows'] == 0


def test_occurrence_diagnostic_masks_channels_independently_without_revising_global_task():
    from policy.b0_support import occurrence
    seg = SimpleNamespace(n=0, start_t=0, end_t=20)
    vis = visibility()
    for row in vis.rows:
        row['hud']['abilities']['teamup'] = [None, None]
    assert occurrence([], 0, 5, vis, seg, horizon=1)[:2] == ('negative', None)
    assert occurrence([], 4, 5, vis, seg, horizon=1)[0] == 'unknown'
    assert occurrence([target(4)], 4, 5, vis, seg, horizon=1)[:2] == ('positive', None)
    crossing = target(4, 4.9, 5.1)
    assert occurrence([crossing], 4, 5, vis, seg, horizon=1)[0] == 'unknown'
    assert occurrence([crossing, target(4)], 4, 5, vis, seg, horizon=1)[:2] == ('positive', 'interval_crosses_decision')
    assert occurrence([target(4), target(4, 5.25, 5.4)], 4, 5, vis, seg, horizon=1)[:2] == ('positive', 'ambiguous_first_event')
    assert vis.covers(5, 6, seg, [target(4)])[1] == 'unreadable:teamup'


def test_multilabel_unknown_loss_and_unsupported_fit_channels_are_masked():
    from policy import b0_multilabel as multi
    mx = multi.mx
    y = np.zeros((2,5),np.float32); y[0,0]=1
    mask = np.zeros((2,5),bool); mask[:,0]=True
    timing = np.zeros((2,5),bool); timing[0,0]=True
    bounds = np.zeros((2,5,2),np.float32); bounds[0,0]=[.4,.6]
    stats = multi.fit_stats(y,mask,timing,bounds)
    assert stats['supported'] == [True,False,False,False,False]
    model = lambda x: mx.zeros((2,10))
    args = [mx.zeros((2,51,386)),mx.array(y),mx.array(mask),mx.array(timing),mx.array(bounds),mx.array(stats['weights'])]
    loss = float(multi.masked_loss(model,*args))
    y[:,1:]=1; bounds[:,1:]=100
    args[1],args[4]=mx.array(y),mx.array(bounds)
    assert float(multi.masked_loss(model,*args)) == pytest.approx(loss)
    assert multi.nonoverlap([0,.2,.4,1.,1.2,2.], horizon=1) == 3
    assert multi.nonoverlap([0,.2,.4,1.,1.2,2.], horizon=2) == 2


def test_resource_baseline_is_prefix_causal_and_fits_only_given_mask():
    from policy import b0_multilabel as multi
    vis=visibility()
    clip=SimpleNamespace(segment_at=lambda t:SimpleNamespace(n=0), events=[])
    before=multi.resource_keys(clip,vis)
    vis.rows[-1]['hud']['cooldowns']['swing']=99
    after=multi.resource_keys(clip,vis)
    assert before[:-1]==after[:-1]
    keys=np.array([['a']*5,['a']*5,['b']*5])
    y=np.array([[1]*5,[0]*5,[1]*5]);mask=np.array([[True]*5,[True]*5,[False]*5])
    tables=multi.resource_fit(keys,y,mask,np.full(5,.5))
    assert tables[0]=={'a':{'positive':1,'observed':2,'probability':.5}}
    assert multi.resource_predict(tables,np.array([['b']*5]),[.2]*5).tolist()==[[.2]*5]


def test_multilabel_checkpoint_and_common_timing_support(tmp_path,monkeypatch):
    from policy import b0_multilabel as multi
    monkeypatch.setitem(multi.SPEC,'epochs',1)
    data=dict(x=np.random.default_rng(0).normal(size=(4,51,386)).astype(np.float32),
              y=np.array([[1]*5,[0]*5,[1]*5,[0]*5],np.float32),mask=np.ones((4,5),bool),
              timing=np.array([[True]*5,[False]*5,[True]*5,[False]*5]),
              bounds=np.tile([.2,.3],(4,5,1)).astype(np.float32),recent=np.zeros((4,5)),
              resources=np.array([['unknown|unknown|unknown']*5]*4))
    records=[dict(session='day' if i<2 else 'req') for i in range(4)]
    held_support={name:{'held_support_gate':False} for name in multi.NAMES}
    report=multi.fit_fold(data,records,'req',tmp_path,{'support':{'req':{'channels':held_support}}})
    assert all(v['status']=='inconclusive' for v in report['claim_screen'].values())
    assert report['timing_common_support']['common_support_rows']==5
    model=multi.Head(386,10);model.load_weights(report['checkpoint'])
    actual=np.asarray(model(multi.mx.array(data['x'][2:])))[:,:5]
    saved=np.load(tmp_path/'day-to-req'/'predictions.npz')
    np.testing.assert_allclose(actual,saved['logits'],atol=1e-6)


def test_existing_final_checkpoint_refuses_before_any_dataset_artifact_write(tmp_path,monkeypatch):
    from policy import b0_multilabel as multi
    folder=tmp_path/'day-to-req';folder.mkdir()
    checkpoint=folder/'model.safetensors';checkpoint.write_text('retained')
    monkeypatch.setattr(multi.sys,'argv',['b0_multilabel','--fit','--out',str(tmp_path)])
    monkeypatch.setattr(multi,'build',lambda out:pytest.fail('build must not run beside accepted checkpoints'))
    with pytest.raises(ValueError,match='refusing to rebuild'):
        multi.main()
    assert checkpoint.read_text()=='retained'
    assert not (tmp_path/'run-spec.json').exists()


def test_uncertain_intervals_mask_only_their_channel_and_never_prove_occurrence():
    from policy.b0_support import occurrence
    seg = SimpleNamespace(n=0, start_t=0, end_t=20)
    uncertain = replace(target(lo=4.8, hi=5.2), certain=False, evidence=('ability_uncertain',))
    assert occurrence([uncertain], 0, 5, visibility(), seg, horizon=1)[:2] == ('unknown', 'uncertain_event')
    assert occurrence([uncertain], 1, 5, visibility(), seg, horizon=1)[:2] == ('negative', None)
    result = occurrence([uncertain, target()], 0, 5, visibility(), seg, horizon=1)
    assert result[:2] == ('positive', 'uncertain_first_event')
    assert result[2] == [target()]
    margin = replace(uncertain, lo=6.1, hi=6.2)
    assert occurrence([margin], 0, 5, visibility(), seg, horizon=1)[0] == 'unknown'
    assert occurrence([margin, target()], 0, 5, visibility(), seg, horizon=1)[:2] == ('positive', None)
    contained_unknown = replace(uncertain, lo=5.2, hi=5.3)
    assert b0.next_target([contained_unknown], 5, horizon=1)[1] == 'uncertain_event'
    assert visibility().covers(5, 6, seg, [contained_unknown])[1] == 'uncertain_event'


def test_targets_preserve_uncertainty_and_filter_before_corroboration(monkeypatch):
    monkeypatch.setattr(b0.Demos, 'window_event', lambda c, e: e, raising=False)
    cast = SimpleNamespace(kind='ability_cast', t_from=5.2, t_to=5.3, known_at=6.6,
                           slot='swing', slot_pos='swing', amount=6, segment=0)
    charge = SimpleNamespace(**(vars(cast) | dict(kind='charges_spent', t_from=5.1, t_to=5.4, known_at=7.0)))
    clip = SimpleNamespace(events=[cast], events_meta={'slot_mapping': {'swing': 'swing'}})
    before = b0.targets(clip, known_by=6.6)[0]
    clip.events.append(charge)
    assert b0.targets(clip, known_by=6.6)[0] == before
    assert b0.targets(clip, known_by=6.5)[0] == []
    merged, = b0.targets(clip)[0]
    assert (merged.lo, merged.hi, merged.known_at) == (5.1, 5.4, 7.0)
    uncertain = SimpleNamespace(**(vars(cast) | dict(kind='ability_uncertain', amount=8)))
    clip.events = [uncertain]
    unknown, = b0.targets(clip)[0]
    assert not unknown.certain
    assert b0.most_recent([unknown], 8) == b0.NONE


def test_format5_event_features_use_availability_and_health_cause():
    from policy.train import EventEvidenceError, _event_features, EVENT_KINDS
    damage = SimpleNamespace(kind='hp_lost', t_from=4, t_to=5, known_at=6.3, cause='damage')
    assert not _event_features([damage], 5.5)[0].any()
    assert _event_features([damage], 6.3)[0][EVENT_KINDS.index('damage_taken')] == 1
    for cause in ('unknown', 'shield_decay', None):
        other = SimpleNamespace(**(vars(damage) | dict(cause=cause)))
        assert not _event_features([other], 6.3)[0].any()
    for kind in ('icon_dimmed', 'icon_lit'):
        icon = SimpleNamespace(**(vars(damage) | dict(kind=kind)))
        assert _event_features([icon], 6.3)[0][EVENT_KINDS.index(kind)] == 1
    for known in (None, float('nan'), float('inf'), 4.9):
        invalid = SimpleNamespace(**(vars(damage) | dict(known_at=known)))
        with pytest.raises(EventEvidenceError):
            _event_features([invalid], 6.3)
    legacy = SimpleNamespace(kind='hp_lost', t_to=5, cause='damage')
    with pytest.raises(EventEvidenceError):
        _event_features([legacy], 6.3)


def test_lit_icons_and_timer_ends_do_not_certify_readiness():
    from policy.b0_multilabel import resource_keys
    vis = visibility()
    for row in vis.rows:
        row['hud']['cooldowns'] = {}
    assert not b0.observed_channels(vis.rows[0], vis.meta['slot_mapping'], vis.meta['charge_maxima'])[0]['get_over_here']
    end = SimpleNamespace(kind='cooldown_ended', t_to=4.0, known_at=5.5, slot='get_over_here', segment=0)
    clip = SimpleNamespace(events=[end], segment_at=lambda t: SimpleNamespace(n=0))
    keys = resource_keys(clip, vis)
    assert keys[0][0] == 'unknown|unknown|unknown'
    assert keys[6][0] == 'unknown|unknown|<1s'
    prefix = SimpleNamespace(events=[], segment_at=clip.segment_at)
    assert resource_keys(prefix, vis)[:6] == keys[:6]


def test_two_second_occurrence_uses_occurrence_bounds_and_full_visibility_horizon():
    from policy.b0_support import occurrence
    seg = SimpleNamespace(n=0, start_t=0, end_t=20)
    vis = visibility()
    vis.rows = [raw_row(round(4.9 + i / 10, 3)) for i in range(24)]
    vis.times = np.array([r['t'] for r in vis.rows])
    event = replace(target(lo=6.1, hi=6.9), known_at=8.2)
    assert occurrence([event], 0, 5, vis, seg, horizon=2)[:2] == ('positive', None)
    assert occurrence([], 0, 5, vis, seg, horizon=2)[:2] == ('negative', None)
    vis.rows.pop()
    vis.times = np.array([r['t'] for r in vis.rows])
    assert occurrence([], 0, 5, vis, seg, horizon=2)[:2] == ('unknown', 'missing_visibility_frame')


def test_archived_support_refuses_before_cache_access(tmp_path, monkeypatch):
    from policy import b0_multilabel as multi
    monkeypatch.setattr(b0, 'train_clips', lambda: (None, []))
    monkeypatch.setattr(b0, 'OUT', tmp_path)
    (tmp_path / 'support-diagnostic.json').write_text(json.dumps({'horizon_s': 1}))
    monkeypatch.setattr(multi, 'Cache', lambda *a, **kw: pytest.fail('opened cache for old labels'))
    with pytest.raises(ValueError, match='archived support'):
        multi.build(tmp_path, tmp_path)


def test_pending_confirmation_and_invalid_badges_cannot_certify_labels(monkeypatch):
    from policy.train import EventEvidenceError
    monkeypatch.setattr(b0.Demos, 'window_event', lambda c, e: e, raising=False)
    event = SimpleNamespace(kind='ability_cast', t_from=5.2, t_to=5.3, known_at=6.6,
                            slot='swing', slot_pos='swing', amount=6, segment=0)
    clip = SimpleNamespace(events=[event], events_meta={'slot_mapping': {'swing': 'swing'}, 'duration_s': 6.5})
    pending, = b0.targets(clip)[0]
    assert not pending.certain
    event.known_at = None
    with pytest.raises(EventEvidenceError):
        b0.targets(clip)
    row = raw_row(5)
    mapping = {k: k for k in row['hud']['abilities']}
    row['hud']['abilities']['uppercut'] = [True, 7]
    assert not b0.observed_channels(row, mapping, {'uppercut': 2})[0]['uppercut']
    assert row['hud']['abilities']['uppercut'][1] == 7
    row['hud']['abilities']['uppercut'][1] = 1
    assert not b0.observed_channels(row, mapping, {})[0]['uppercut']
    assert b0.observed_channels(row, mapping, {'uppercut': 2})[0]['uppercut']


def test_countdown_ticks_certify_negatives_at_every_phase_but_resets_do_not():
    import math
    from policy.b0_support import negative_channel
    seg = SimpleNamespace(n=0, start_t=0, end_t=30)
    for horizon in (1., 2.):
        for phase in range(100):
            t = 5 + phase / 100
            vis = visibility()
            vis.rows = [raw_row(t-.1+i/10) for i in range(round(horizon*10)+4)]
            vis.times = np.array([r['t'] for r in vis.rows])
            for row in vis.rows:
                row['hud']['cooldowns'] = {name: math.ceil(15-row['t']) for name in vis.meta['slot_mapping']}
            for name in vis.meta['slot_mapping']:
                assert negative_channel(vis, name, t, t+horizon, seg) == (True, None)
            assert vis.covers(t, t+horizon, seg, []) == (True, None)
        vis.rows[8]['hud']['cooldowns']['get_over_here'] += 3
        assert not negative_channel(vis, 'get_over_here', t, t+horizon, seg)[0]
        vis.rows[8]['hud']['abilities']['swing'][1] = 0
        assert not negative_channel(vis, 'swing', t, t+horizon, seg)[0]
        for value in (None, 0):
            vis.rows[8]['hud']['cooldowns']['teamup'] = value
            assert not negative_channel(vis, 'teamup', t, t+horizon, seg)[0]


def test_two_second_structural_gates_cover_segment_cut_and_annotation():
    seg = SimpleNamespace(n=0, start_t=0, end_t=20)
    obs = SimpleNamespace(truncated_context=False, frames=[SimpleNamespace(t=i/10) for i in range(51)])
    clip = SimpleNamespace(events_meta={'cut_times': []}, _mask_ts=[])
    assert b0.window_reason(clip, seg, 5, obs, 2) is None
    assert b0.window_reason(clip, SimpleNamespace(start_t=0, end_t=6.5), 5, obs, 2) == 'horizon_segment_end'
    clip.events_meta['cut_times'] = [6.5]
    assert b0.window_reason(clip, seg, 5, obs, 2) == 'cut_in_context_or_horizon'
    clip.events_meta['cut_times'] = []
    clip._mask_ts = [7.15]
    assert b0.window_reason(clip, seg, 5, obs, 2) == 'annotation_mask'


def test_distinct_support_never_adds_cast_and_charge_witnesses():
    from policy.b0_support import positive_support, occurrence
    from policy.b0_multilabel import support, NAMES
    evidence = [dict(segment=0, lo=i+.1, hi=i+.2, evidence=[kind])
                for i in range(10) for kind in ('ability_cast', 'charges_spent')]
    result = positive_support(evidence)
    assert result['distinct_positive_lower_bound'] == 10
    assert result['ambiguous_charge_pairings'] == 10
    # Non-overlapping cross-kind bounds also cannot be counted as independent uses.
    for r in evidence[1::2]:
        r['lo'] += .4; r['hi'] += .4
    assert positive_support(evidence)['distinct_positive_lower_bound'] == 10
    cast = target(1)
    charge = replace(target(1, 5.55, 5.65), evidence=('charges_spent',))
    seg = SimpleNamespace(n=0, start_t=0, end_t=20)
    assert occurrence([cast, charge], 1, 5, visibility(), seg, horizon=1)[:2] == ('positive', 'ambiguous_charge_pairing')
    session = next(iter(b0.ALLOWED))
    records = [dict(session=session, t=i*2, context_event_proxy=False,
                    channels={name: {'evidence': evidence if i==0 else []} for name in NAMES}) for i in range(21)]
    y = np.zeros((21,5)); y[0] = 1
    report = support(records, y, np.ones((21,5), bool), np.zeros((21,5), bool))
    assert not report[session]['channels']['swing']['held_support_gate']


def test_slot_mapping_disagreement_fails_loudly():
    from policy.train import EventEvidenceError
    event = SimpleNamespace(kind='ability_cast', t_from=5.2, t_to=5.3, known_at=6.6,
                            slot='swing', slot_pos='uppercut', amount=6, segment=0)
    clip = SimpleNamespace(events=[event], events_meta={'slot_mapping': {'uppercut': 'uppercut'}})
    with pytest.raises(EventEvidenceError, match='slot_mapping'):
        b0.targets(clip)


def test_raw_sidecars_preserve_eighth_and_ninth_fields():
    from policy.b0_reads import serialize_reads
    from perception.hud import Hud
    read = (1, .1, Hud(hp=250), True, None, False, False, .41)
    assert serialize_reads([read])[0]['hero_score'] == .41
    glyphs = {'swing': 'glyph_displayed'}
    assert serialize_reads([read+(glyphs,)])[0]['glyph_evidence'] == glyphs
    with pytest.raises(ValueError, match='8 fields'):
        serialize_reads([read[:7]])


def test_expiry_intersection_rejects_stalls_and_impossible_jumps_without_losing_ticks():
    from policy.b0_support import negative_channel
    from perception.events import ROUND_S, TIMER_EPS
    seg = SimpleNamespace(n=0, start_t=0, end_t=30)
    for horizon in (1., 2.):
        for decision_phase in range(100):
            times = 5 + decision_phase/100 - .1 + np.arange(round(horizon*10)+4)/10
            for timer_phase in (0, .01, .2, .49, .8, .99):
                cds = [math.ceil(15+timer_phase-t) for t in times]
                assert b0.no_reset('get_over_here', times, cds)
                assert b0.no_reset('swing', times, [(c, 2) for c in cds])
        for offset in (0., .01, 1000.):
            times = offset + np.arange(round(horizon*10)+4)/10
            for name in ('get_over_here', 'teamup', 'swing', 'uppercut'):
                values = [(5, 2)]*len(times) if name in ('swing', 'uppercut') else [5]*len(times)
                assert not b0.no_reset(name, times, values)
        vis = visibility()
        vis.rows = [raw_row(4.9+i/10) for i in range(round(horizon*10)+4)]
        vis.times = np.array([r['t'] for r in vis.rows])
        for row in vis.rows:
            row['hud']['cooldowns'] = {n: 5 for n in vis.meta['slot_mapping']}
        assert all(not negative_channel(vis, n, 5, 5+horizon, seg)[0] for n in vis.meta['slot_mapping'])
        assert not vis.covers(5, 5+horizon, seg, [])[0]
    assert not b0.no_reset('get_over_here', [0, .1], [9, 7])
    # The writer's slack admits this small upward step geometrically; no-reset still rejects it.
    times = np.arange(14)/10
    cds = [5]*9 + [4, 5, 4, 4, 4]
    lo = max(t+v-ROUND_S-TIMER_EPS for t,v in zip(times,cds))
    hi = min(t+v+TIMER_EPS for t,v in zip(times,cds))
    assert hi-lo > 1e-6
    assert not b0.no_reset('get_over_here', times, cds)
    assert b0.no_reset('web_cluster_fired', times, [5]*14)
    assert not b0.no_reset('web_cluster_fired', times, [5]*13+[4])


def test_visibility_coverage_uses_only_the_requested_time_slice():
    vis = visibility()
    vis.rows = [raw_row(i/10) for i in range(101)]
    vis.times = np.array([row['t'] for row in vis.rows])
    seg = SimpleNamespace(start_t=0, end_t=20)
    for horizon in (1., 2.):
        assert vis.covers(5, 5+horizon, seg, []) == (True, None)
