"""Focused B0 guards; synthetic payloads never open the demonstration corpus."""
from dataclasses import replace
from types import SimpleNamespace
import json
import pytest

pytest.importorskip('mlx')
np = pytest.importorskip('numpy')
from policy import b0
from agent.demos import Event


def target(cls=0, lo=5.2, hi=5.3):
    return b0.Target(cls, lo, hi, 0, ('ability_cast',))


def test_intervals_crossing_boundaries_and_ambiguous_order_are_not_negatives():
    assert b0.next_target([target(lo=4.9, hi=5.1)], 5)[1] == 'interval_crosses_decision'
    assert b0.next_target([target(lo=5.9, hi=6.1)], 5)[1] == 'interval_crosses_horizon'
    assert b0.next_target([target(), target(1, 5.25, 5.4)], 5)[1] == 'ambiguous_first_event'
    label, reason = b0.next_target([target()], 5)
    assert reason is None and label[:3] == pytest.approx((0, .2, .3))
    assert b0.next_target([], 5)[0][0] == b0.NONE
    assert b0.interval_error(.25, .2, .3) == 0
    assert b0.interval_error(.4, .2, .3) == pytest.approx(.1)


def test_most_recent_is_confirmed_past_not_previous_future_target():
    assert b0.most_recent([target()], 5) == b0.NONE
    assert b0.most_recent([target()], 5.3) == 0
    assert b0.most_recent([target(), target(1, 5.25, 5.4)], 5.5) == b0.NONE


def test_cast_charge_dedup_preserves_union_and_same_kind_ambiguity(monkeypatch):
    cast = Event('ability_cast', 5.2, 5.3, slot='swing', amount=4, segment=0, slot_pos='swing')
    charge = replace(cast, kind='charges_spent', t_from=5.1, t_to=5.4, amount=1)
    clip = SimpleNamespace(events=[cast, charge], events_meta={'slot_mapping': {'swing': 'swing'}})
    monkeypatch.setattr(b0.Demos, '_readable', lambda c, e: True)
    events, counts = b0.targets(clip)
    assert len(events) == 1 and (events[0].lo, events[0].hi) == (5.1, 5.4)
    assert counts['corroborating_charge_merged'] == 1
    clip.events = [cast, replace(cast, t_to=5.35)]
    assert len(b0.targets(clip)[0]) == 2
    clip.events = [replace(cast, slot=None)]
    assert not b0.targets(clip)[0]


def raw_row(t):
    return dict(t=t, playing=True, aside=None, cut=False,
                hud=dict(hp=250, bar_fill=1, webs=5,
                         abilities={k: [True, None] for k in ('get_over_here', 'swing', 'uppercut', 'teamup')},
                         cooldowns={k: None for k in ('get_over_here', 'swing', 'uppercut', 'teamup')}))


def visibility():
    vis = b0.Visibility.__new__(b0.Visibility)
    vis.rows = [raw_row(round(4.9 + i / 10, 3)) for i in range(14)]
    vis.times = np.array([r['t'] for r in vis.rows])
    vis.meta = {'slot_mapping': {k: k for k in ('get_over_here', 'swing', 'uppercut', 'teamup')}}
    return vis


def test_unknowns_missing_frames_margin_and_raw_changes_censor_no_event():
    seg = SimpleNamespace(start_t=0, end_t=20)
    vis = visibility()
    assert vis.covers(5, 6, seg, []) == (True, None)
    vis.rows[5]['hud']['abilities']['teamup'] = [False, None]
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
    assert not b0.observed_channels(row, mapping)[0]['swing']
    row['hud']['abilities']['swing'][1] = 1
    assert b0.observed_channels(row, mapping)[0]['swing']
    row['hud']['abilities']['swing'][0] = None
    assert not b0.observed_channels(row, mapping)[0]['swing']
    mapping.pop('teamup')
    assert not b0.observed_channels(row, mapping)[0]['teamup']


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
    assert occurrence([], 0, 5, vis, seg)[:2] == ('negative', None)
    assert occurrence([], 4, 5, vis, seg)[0] == 'unknown'
    assert occurrence([target(4)], 4, 5, vis, seg)[:2] == ('positive', None)
    crossing = target(4, 4.9, 5.1)
    assert occurrence([crossing], 4, 5, vis, seg)[0] == 'unknown'
    assert occurrence([crossing, target(4)], 4, 5, vis, seg)[:2] == ('positive', 'interval_crosses_decision')
    assert occurrence([target(4), target(4, 5.25, 5.4)], 4, 5, vis, seg)[:2] == ('positive', 'ambiguous_first_event')
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
    assert multi.nonoverlap([0,.2,.4,1.,1.2,2.]) == 3


def test_resource_baseline_is_prefix_causal_and_fits_only_given_mask():
    from policy import b0_multilabel as multi
    vis=visibility()
    clip=SimpleNamespace(segment_at=lambda t:SimpleNamespace(n=0))
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
