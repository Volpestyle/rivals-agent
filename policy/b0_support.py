"""Support diagnostic ONLY for a proposed independent-occurrence B0 task.

No model fit, no new reader pass, no change to the original global-task artifacts.
"""
import argparse
from collections import Counter
from pathlib import Path
import json
import time

import numpy as np


from .b0 import (CLASSES, CONFIG, OUT, Visibility, digest, next_target, observed_channels,
                 targets, train_clips, write_json, no_reset, window_reason)

SEMANTICS = 'format5-expiry-consistent-occurrence-v3'
SUPPORT_OUT = OUT / 'support-h2'


def source_versions():
    return {p: digest(p) for p in ('policy/b0_support.py', 'policy/b0.py', 'policy/train.py', 'agent/demos.py', 'perception/events.py')}


def positive_support(evidence):
    """Distinct-use lower bound: never add different witnesses for potentially the same use.

    Within each segment and evidence kind choose disjoint occurrence intervals; take the largest
    count among kinds. This deliberately undercounts uses split across witness kinds.
    """
    records = {(r['segment'], r['lo'], r['hi'], tuple(r['evidence'])) for r in evidence}
    total, ambiguous = 0, 0
    for segment in {r[0] for r in records}:
        local = [r for r in records if r[0] == segment]
        counts = []
        for kind in {k for r in local for k in r[3]}:
            end, count = -float('inf'), 0
            for _, lo, hi, _ in sorted((r for r in local if kind in r[3]), key=lambda r: r[2]):
                if lo > end + 1e-8:
                    count += 1
                    end = hi
            counts.append(count)
        total += max(counts, default=0)
        if any('ability_cast' in r[3] for r in local):
            ambiguous += sum(r[3] == ('charges_spent',) for r in local)
    return dict(distinct_positive_lower_bound=total, reported_intervals=len(records),
                ambiguous_charge_pairings=ambiguous)


def negative_channel(vis, name, t, end, seg):
    """Exactly the HUD negative contract, applied only to this channel."""
    start, stop = t - .1, end + .2
    if start < seg.start_t + .6 - 1e-8 or stop > seg.end_t - .6 + 1e-8:
        return False, 'visibility_segment_margin'
    lo, hi = np.searchsorted(vis.times, [start - 1e-7, stop + 1e-7])
    rows = vis.rows[lo:hi]
    count = round((stop - start) * 10) + 1
    if len(rows) != count or not np.allclose(vis.times[lo:hi], start + np.arange(count) / 10, atol=.002):
        return False, 'missing_visibility_frame'
    values = []
    for row in rows:
        hud = row['hud']
        if (hud.get('hp') is None and hud.get('bar_fill') is None) or hud.get('hp') == 0:
            return False, 'unobserved_hud_or_death'
        if row.get('cut') or row.get('aside') or row.get('playing') is False:
            return False, 'raw_cut_banner_or_other_hero'
        known, raw = observed_channels(row, vis.meta['slot_mapping'], vis.meta['charge_maxima'])
        if not known[name]:
            return False, 'unreadable_channel'
        values.append(raw[name])
    if not no_reset(name, vis.times[lo:hi], values):
        return False, 'unconfirmed_or_negative_raw_change'
    return True, None


def occurrence(events, cls, t, vis, seg, horizon):
    """Positive proves occurrence, without claiming a uniquely timed first event."""
    local = [e for e in events if e.cls == cls and e.segment == seg.n]
    end = t + horizon
    if t < seg.start_t or end > seg.end_t + 1e-8:
        return 'unknown', 'horizon_segment_end', []
    certain = [e for e in local if e.certain]
    uncertain = [e for e in local if not e.certain and e.hi >= t - .1 and e.lo <= end + .2]
    contained = [e for e in certain if e.lo > t + 1e-8 and e.hi <= end + 1e-8]
    overlapping = [e for e in certain if e.hi > t + 1e-8 and e.lo <= end + 1e-8]
    if contained:
        # next_target rejects boundary-crossing or ambiguous earliest intervals.
        _, reason = next_target(certain, t, horizon)
        first_hi = min(e.hi for e in contained)
        if any(e.hi > t and e.lo <= first_hi for e in uncertain):
            reason = 'uncertain_first_event'
        if any(e.evidence == ('charges_spent',) for e in contained) and any('ability_cast' in e.evidence for e in contained):
            reason = reason or 'ambiguous_charge_pairing'
        return 'positive', reason, contained
    if overlapping:
        return 'unknown', 'boundary_crossing_interval', []
    if uncertain:
        return 'unknown', 'uncertain_event', []
    if any(t < e.hi <= end + .2 + 1e-8 for e in certain):
        return 'unknown', 'confirmation_margin_event', []
    observed, reason = negative_channel(vis, CLASSES[cls], t, end, seg)
    return ('negative' if observed else 'unknown'), reason, []


def produce(out, visibility_root=OUT, horizon=CONFIG['horizon_s']):
    if horizon not in (1.0, CONFIG['horizon_s']):
        raise ValueError('only H1 diagnostic and predeclared H2 are supported')
    out = Path(out)
    target = out / 'support-diagnostic.json'
    if target.exists() or (out / 'support-windows.json').exists():
        raise ValueError('support artifacts already exist; use a fresh directory')
    started = time.perf_counter()
    demos, clips = train_clips()
    sessions, rows = {}, []
    for clip in clips:
        events, _ = targets(clip)
        vis_path = Path(visibility_root) / 'visibility' / (clip.id + '.json')
        vis = Visibility(vis_path, clip)
        channels = {name: dict(positive_windows=0, negative_windows=0, unknown_windows=0,
                              timing_supported_positives=0, unknown_reasons=Counter(),
                              timing_exclusions=Counter()) for name in CLASSES[:-1]}
        unique = {name: [] for name in channels}
        shared_exclusions, eligible = Counter(), 0
        decisions = demos._decisions(clip, 'grid', 5)
        for seg, t in decisions:
            obs = demos._observe(clip, seg, t, 5, 10, across=True)
            reason = window_reason(clip, seg, t, obs, horizon)
            if reason:
                shared_exclusions[reason] += 1
                continue
            eligible += 1
            result = dict(session=clip.id, t=t, segment=seg.n, channels={})
            for cls, name in enumerate(CLASSES[:-1]):
                outcome, why, positive = occurrence(events, cls, t, vis, seg, horizon)
                evidence = [dict(lo=e.lo, hi=e.hi, segment=e.segment, evidence=list(e.evidence)) for e in positive]
                counts = channels[name]
                counts[outcome + '_windows'] += 1
                if outcome == 'positive':
                    unique[name].extend(evidence)
                    counts['timing_supported_positives'] += why is None
                    if why:
                        counts['timing_exclusions'][why] += 1
                elif outcome == 'unknown':
                    counts['unknown_reasons'][why] += 1
                result['channels'][name] = dict(outcome=outcome, reason=why,
                                               intervals=[[e.lo, e.hi] for e in positive], evidence=evidence)
            rows.append(result)
        for name, counts in channels.items():
            counts.update(positive_support(unique[name]))
            assert sum(counts[k + '_windows'] for k in ('positive', 'negative', 'unknown')) == eligible
        sessions[clip.id] = dict(group=clip.group, decision_windows=len(decisions),
                                 structural_eligible_windows=eligible, structural_grid_seconds=eligible / 5,
                                 shared_exclusions=dict(shared_exclusions), channels=channels,
                                 visibility=str(vis_path.resolve()), visibility_sha256=digest(vis_path),
                                 manifest_sha256=digest(clip.path),
                                 event_sha256=digest(clip._resolve(clip.header['events'])),
                                 loader_knowledge_skips=dict(Counter(s.reason for s in demos.skipped
                                     if s.clip == clip.id and s.reason in ('known_after_segment_end',
                                                                         'known_after_segment_end_unbridged'))),
                                 reader_writer=clip.events_meta['writer'])
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / 'support-windows.json', rows)
    report = dict(task='Independent per-ability occurrence forecasts; SUPPORT DIAGNOSTIC ONLY',
                  command='nice -n 10 uv run --no-sync --group policy --group perception python -m policy.b0_support',
                  event_format=5, policy_semantics=SEMANTICS, source_versions=source_versions(),
                  windows_sha256=digest(out / 'support-windows.json'),
                  history_s=5, steps=51, frame_hz=10, decision_hz=5, horizon_s=horizon,
                  sessions=sessions, elapsed_seconds=time.perf_counter() - started,
                  semantics=['positive: at least one accepted same-channel interval wholly inside the horizon',
                             'other-channel unknowns do not censor a positive or this channel negative',
                             'negative: observed over prior .1s and following .2s; one consistent expiry, no countdown reset, stable charges/ammo; .6s segment margins',
                             'boundary-crossing intervals unknown unless contained positive proves occurrence',
                             'timing requires no boundary-crossing interval and unambiguous earliest same-channel event',
                             'counts use common structurally eligible windows; shared context/segment exclusions are separate',
                             'no fitting, model selection, new footage, sealed payloads, or task promotion'],
                  limitations=['10Hz sampled observability; intersample gaps not established',
                               'Day icon-overlay contamination count unknown; frozen reader has no per-frame identity test',
                               'two development sessions, correlated overlapping windows; distinct-use support is a conservative lower bound'])
    write_json(target, report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=SUPPORT_OUT)
    ap.add_argument('--visibility-root', type=Path, default=OUT)
    ap.add_argument('--horizon', type=float, choices=(1., CONFIG['horizon_s']), default=CONFIG['horizon_s'])
    args = ap.parse_args()
    report = produce(args.out, args.visibility_root, args.horizon)
    print(json.dumps(report['sessions'], indent=2))


if __name__ == '__main__':
    main()
