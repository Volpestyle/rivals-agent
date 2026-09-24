"""Synthetic producer-to-runner integration; run with the actual format-5 writer/loader."""
from dataclasses import replace
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

pytest.importorskip('mlx')
np = pytest.importorskip('numpy')
from perception import events as writer
pytestmark = pytest.mark.skipif(writer.FORMAT_VERSION != 5, reason='requires integrated format-5 source tree')
from agent.demos import Event, Segment, Mask, Skipped
from policy import b0, b0_support as support, b0_multilabel as multi


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    mapping = {n: n for n in multi.NAMES if n != 'web_cluster_fired'}
    clips = []
    visibility = tmp_path / 'visibility'
    visibility.mkdir()
    cache = tmp_path / 'cache'
    cache.mkdir()
    for name, group in b0.ALLOWED.items():
        path = tmp_path / (name + '.json')
        path.write_text('{}')
        event_path = path.with_suffix('.jsonl')
        event_path.write_text('{}\n')
        segments = [Segment(0, 0., 1.9, 'start', 'cut'), Segment(1, 2., 20., 'cut', 'end')]
        def event(lo, hi, known, segment, slot='swing', kind='ability_cast'):
            return Event(kind, lo, hi, slot=slot, slot_pos=slot, amount=1, segment=segment,
                         known_at=known, known_i=round(known * 10))
        events = [event(1.4, 1.5, 6., 0), event(6.5, 6.6, 7.3, 1),
                  event(8.2, 8.4, 9.7, 1, 'get_over_here'), event(19., 19.2, 20.5, 1)]
        clip = NS(id=name, group=group, path=path, header={'events': str(event_path)},
                  events=events, segments=segments, _mask_ts=[], masks_near=lambda *a: None,
                  _resolve=Path, segment_at=lambda t, segs=segments: next((s for s in segs if s.start_t <= t <= s.end_t), None),
                  events_meta=dict(format=5, writer='synthetic-writer', fps=10., duration_s=21.,
                                   kit={'table': writer.KIT_REFERENCE}, slot_mapping=mapping, cut_times=[]))
        rows = []
        for i in range(211):
            t = i / 10
            rows.append(dict(t=t, playing=True, aside=None, cut=False,
                             hud=dict(hp=250, bar_fill=1, webs=5,
                                      abilities={n: [True, 1] for n in mapping},
                                      cooldowns={n: max(1, math.ceil(12-t)) for n in mapping})))
        meta = dict(source=name, event_sha256=b0.digest(event_path), writer='synthetic-writer',
                    fps=10., slot_mapping=mapping)
        b0.write_json(visibility / (name + '.json'), dict(meta=meta, frames=rows))
        b0.write_json(cache / (name + '.json'), dict(id=name, dim=384, t_origin=0.))
        np.savez(cache / (name + '.npz'), emb=np.ones((211, 384), np.float32), t=np.arange(211)/10)
        clips.append(clip)
    demos = NS(_decisions=lambda c, *a: [(c.segments[1], t) for t in (7., 7.3, 8.)],
               _observe=lambda c, s, t, *a, **k: NS(truncated_context=False,
                   frames=[NS(t=round(t-5+i/10, 4), masked=None) for i in range(51)]),
               usable=lambda c: c.segments,
               skipped=[Skipped(c.id, 3.5, 'known_after_segment_end') for c in clips]
                     + [Skipped(c.id, 19.2, 'known_after_segment_end_unbridged') for c in clips])
    monkeypatch.setattr(b0, 'train_clips', lambda: (demos, clips))
    monkeypatch.setattr(support, 'train_clips', lambda: (demos, clips))
    monkeypatch.setattr(multi, 'cache_dir', lambda *a: cache)
    return clips, tmp_path


def test_real_visibility_constructor_kit_and_provenance(dataset):
    clips, root = dataset
    clip = clips[0]
    path = root / 'visibility' / (clip.id + '.json')
    vis = b0.Visibility(path, clip)
    assert vis.meta['charge_maxima'] == {'swing': 3, 'uppercut': 2}
    clip.events_meta['kit']['table'] = None
    vis = b0.Visibility(path, clip)
    assert vis.meta['charge_maxima'] == {}
    assert not b0.observed_channels(vis.rows[0], vis.meta['slot_mapping'], {})[0]['uppercut']
    clip.events_meta['writer'] = 'different'
    with pytest.raises(ValueError, match='provenance'):
        b0.Visibility(path, clip)


def test_support_producer_to_h2_builder_and_causal_proxies(dataset, monkeypatch):
    clips, root = dataset
    report = support.produce(root / 'support', root, 2.)
    assert report['horizon_s'] == 2 and report['event_format'] == 5
    assert all(s['loader_knowledge_skips'] == {'known_after_segment_end': 1,
               'known_after_segment_end_unbridged': 1} for s in report['sessions'].values())
    seen = []
    original = multi.step_row
    def row(*args, **kwargs):
        seen.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(multi, 'step_row', row)
    out = root / 'out'
    out.mkdir()
    arrays, records, result = multi.build(out, root / 'support')
    assert arrays['x'].shape == (6, 51, 386)
    assert result['loader_knowledge_skips'] == {k: v['loader_knowledge_skips'] for k, v in report['sessions'].items()}
    assert seen and all(k['state'] is None and k['events'] is None for k in seen)
    assert arrays['recent'][:3, 1].tolist() == [0, 1, 1]
    assert [r['context_event_proxy'] for r in records[:3]] == [False, True, True]
    assert [r['context_events_not_yet_known'] for r in records[:3]] == [1, 0, 0]
    assert arrays['y'][:3, 0].tolist() == [1, 1, 1]  # future occurrence, not future knowledge
    assert arrays['mask'][:, 4].all() and not arrays['y'][:, 4].any()
    # Accepted current-format headers still require their actual fingerprints.
    path = root / 'support' / 'support-diagnostic.json'
    damaged = json.loads(path.read_text())
    damaged['source_versions']['policy/b0.py'] = 'stale'
    b0.write_json(path, damaged)
    monkeypatch.setattr(multi, 'Cache', lambda *a, **k: pytest.fail('payload opened before fingerprint check'))
    with pytest.raises(ValueError, match='archived'):
        multi.build(out, root / 'support')
    damaged['source_versions'] = support.source_versions()
    b0.write_json(path, damaged)
    (root / 'support' / 'support-windows.json').write_text('[]')
    with pytest.raises(ValueError, match='fingerprint'):
        multi.build(out, root / 'support')


def test_window_event_blanks_reads_and_targets_keep_uncertainty(dataset):
    clips, _ = dataset
    clip = clips[0]
    clip.masks_near = lambda *a: Mask(('chat',), ('swing',))
    original = replace(clip.events[1], kind='ability_uncertain', amount=2, before=2, after=1)
    visible = b0.Demos.window_event(clip, original)
    assert (visible.amount, visible.before, visible.after) == (None, None, None)
    assert (visible.t_from, visible.t_to, visible.known_at) == (6.5, 6.6, 7.3)
    clip.events = [original]
    target, = b0.targets(clip)[0]
    assert not target.certain and target.evidence == ('ability_uncertain',)
    # A masked verified event must also remain an uncertainty blocker, not disappear.
    clip.events = [replace(original, kind='ability_cast')]
    target, = b0.targets(clip)[0]
    assert not target.certain


def test_reader_provenance_does_not_serialize_extra_metadata():
    meta = dict(format=5, writer='abc', fps=10, cut_times=[12], observed={'secret': 1},
                recipe={'video': 'private'}, kit={'patch': 'p', 'patch_from': 'manifest',
                'table': 'k', 'alarms': {'i': 999}, 'durations': {'secret': 2}})
    result = b0.reader_provenance(meta)
    assert result['format'] == 5 and result['writer'] == 'abc'
    assert result['kit'] == {'patch': 'p', 'patch_from': 'manifest', 'table': 'k'}
    assert not {'cut_times', 'observed', 'recipe'} & result.keys()
