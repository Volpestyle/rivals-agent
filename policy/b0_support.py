"""Support diagnostic ONLY for a proposed independent-occurrence B0 task.

No model fit, no new reader pass, no change to the original global-task artifacts.
"""
from collections import Counter
import json
import time

import numpy as np

from .b0 import (CLASSES, OUT, Visibility, digest, next_target, observed_channels,
                 targets, train_clips, write_json)


def negative_channel(vis, name, t, end, seg):
    """Exactly the HUD negative contract, applied only to this channel."""
    start, stop = t - .1, end + .2
    if start < seg.start_t + .6 - 1e-8 or stop > seg.end_t - .6 + 1e-8:
        return False, 'visibility_segment_margin'
    lo, hi = np.searchsorted(vis.times, [start - 1e-7, stop + 1e-7])
    rows = vis.rows[lo:hi]
    if len(rows) != 14 or not np.allclose(vis.times[lo:hi], start + np.arange(14) / 10, atol=.002):
        return False, 'missing_visibility_frame'
    values = []
    for row in rows:
        hud = row['hud']
        if (hud.get('hp') is None and hud.get('bar_fill') is None) or hud.get('hp') == 0:
            return False, 'unobserved_hud_or_death'
        if row.get('cut') or row.get('aside') or row.get('playing') is False:
            return False, 'raw_cut_banner_or_other_hero'
        known, raw = observed_channels(row, vis.meta['slot_mapping'])
        if not known[name]:
            return False, 'unreadable_channel'
        values.append(raw[name])
    if any(v != values[0] for v in values[1:]):
        return False, 'unconfirmed_or_negative_raw_change'
    return True, None


def occurrence(events, cls, t, vis, seg):
    """Positive proves occurrence, without claiming a uniquely timed first event."""
    local = [e for e in events if e.cls == cls and e.segment == seg.n]
    contained = [e for e in local if e.lo > t + 1e-8 and e.hi <= t + 1 + 1e-8]
    overlapping = [e for e in local if e.hi > t + 1e-8 and e.lo <= t + 1 + 1e-8]
    if contained:
        # next_target rejects boundary-crossing or ambiguous earliest intervals.
        _, reason = next_target(local, t)
        return 'positive', reason, contained
    if overlapping:
        return 'unknown', 'boundary_crossing_interval', []
    if any(t < e.hi <= t + 1.2 + 1e-8 for e in local):
        return 'unknown', 'confirmation_margin_event', []
    observed, reason = negative_channel(vis, CLASSES[cls], t, t + 1, seg)
    return ('negative' if observed else 'unknown'), reason, []


def main():
    target = OUT / 'support-diagnostic.json'
    if target.exists():
        raise ValueError('support diagnostic exists; preserve it before another diagnostic revision')
    started = time.perf_counter()
    demos, clips = train_clips()
    sessions, rows = {}, []
    for clip in clips:
        events, _ = targets(clip)
        vis_path = OUT / 'visibility' / (clip.id + '.json')
        vis = Visibility(vis_path, clip)
        channels = {name: dict(positive_windows=0, negative_windows=0, unknown_windows=0,
                              timing_supported_positives=0, unknown_reasons=Counter(),
                              timing_exclusions=Counter()) for name in CLASSES[:-1]}
        unique = {name: set() for name in channels}
        shared_exclusions, eligible = Counter(), 0
        decisions = demos._decisions(clip, 'grid', 5)
        for seg, t in decisions:
            obs = demos._observe(clip, seg, t, 5, 10, across=True)
            reason = None
            if obs.truncated_context or len(obs.frames) != 51 or abs(obs.frames[0].t - (t - 5)) > .002:
                reason = 'short_history'
            elif t + 1 > seg.end_t + 1e-8:
                reason = 'horizon_segment_end'
            elif any(t - 5 < cut <= t + 1 for cut in clip.events_meta['cut_times']):
                reason = 'cut_in_context_or_horizon'
            elif any(t - .1 <= tm <= t + 1.2 for tm in clip._mask_ts):
                reason = 'annotation_mask'
            if reason:
                shared_exclusions[reason] += 1
                continue
            eligible += 1
            result = dict(session=clip.id, t=t, segment=seg.n, channels={})
            for cls, name in enumerate(CLASSES[:-1]):
                outcome, why, positive = occurrence(events, cls, t, vis, seg)
                counts = channels[name]
                counts[outcome + '_windows'] += 1
                if outcome == 'positive':
                    unique[name].update((e.lo, e.hi, e.segment) for e in positive)
                    counts['timing_supported_positives'] += why is None
                    if why:
                        counts['timing_exclusions'][why] += 1
                elif outcome == 'unknown':
                    counts['unknown_reasons'][why] += 1
                result['channels'][name] = dict(outcome=outcome, reason=why,
                                               intervals=[[e.lo, e.hi] for e in positive])
            rows.append(result)
        for name, counts in channels.items():
            counts['unique_positive_events'] = len(unique[name])
            assert sum(counts[k + '_windows'] for k in ('positive', 'negative', 'unknown')) == eligible
        sessions[clip.id] = dict(group=clip.group, decision_windows=len(decisions),
                                 structural_eligible_windows=eligible, structural_grid_seconds=eligible / 5,
                                 shared_exclusions=dict(shared_exclusions), channels=channels,
                                 visibility_sha256=digest(vis_path), reader_writer=clip.events_meta['writer'])
    report = dict(task='PROPOSED independent per-ability occurrence forecasts; SUPPORT DIAGNOSTIC ONLY',
                  command='nice -n 10 uv run --no-sync --group policy --group perception python -m policy.b0_support',
                  original_global_build_sha256=digest(OUT / 'build.json'),
                  original_global_blocked_sha256=digest(OUT / 'blocked.json'),
                  source_versions={p: digest(p) for p in ('policy/b0_support.py', 'policy/b0.py', 'agent/demos.py')},
                  history_s=5, steps=51, frame_hz=10, decision_hz=5, horizon_s=1,
                  sessions=sessions, elapsed_seconds=time.perf_counter() - started,
                  semantics=['positive: at least one accepted same-channel interval wholly inside (t,t+1]',
                             'other-channel unknowns do not censor a positive or this channel negative',
                             'negative: this channel observed/stable over t-.1 to t+1.2 with .6s segment margins and no confirmed event',
                             'boundary-crossing intervals unknown unless contained positive proves occurrence',
                             'timing requires no boundary-crossing interval and unambiguous earliest same-channel event',
                             'counts use common structurally eligible windows; shared context/segment exclusions are separate',
                             'no fitting, model selection, new footage, sealed payloads, or task promotion'],
                  limitations=['10Hz sampled observability; intersample gaps not established',
                               'Day icon-overlay contamination count unknown; frozen reader has no per-frame identity test',
                               'two development sessions, correlated overlapping windows; unique events counted separately'])
    write_json(OUT / 'support-windows.json', rows)
    write_json(target, report)
    print(json.dumps(sessions, indent=2))


if __name__ == '__main__':
    main()
