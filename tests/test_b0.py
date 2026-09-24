"""Focused B0 guards; synthetic payloads never open the demonstration corpus."""
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


def test_visibility_coverage_uses_only_the_requested_time_slice():
    vis = visibility()
    vis.rows = [raw_row(i/10) for i in range(101)]
    vis.times = np.array([row['t'] for row in vis.rows])
    seg = SimpleNamespace(start_t=0, end_t=20)
    for horizon in (1., 2.):
        assert vis.covers(5, 5+horizon, seg, []) == (True, None)
