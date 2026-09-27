"""Offline episode benchmark; never launches a loop, capture source or virtual pad.

  uv run --no-sync python -m scripts.range_benchmark inspect-log path/to/run
  uv run --no-sync python -m scripts.range_benchmark score benchmark.json
  uv run --no-sync python -m scripts.range_benchmark read-pixels native.png

The last command needs an already-provisioned perception environment. Schema and
the bounded prospective protocol are in docs/lanes/range-benchmark.md.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from agent.episodes import (EpisodeSpec, Observation, Stop, board_observation,
                            distribution, score_batch, summarise)


def read_log(run_dir):
    """Read a completed, explicitly named loop log. No recursive corpus discovery."""
    root = Path(run_dir)
    meta = json.loads((root / 'meta.json').read_text(encoding='utf-8'))
    rows = []
    index = root / 'frames.jsonl'
    if index.exists():
        rows = [json.loads(line) for line in index.read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(a['t'] > b['t'] for a, b in zip(rows, rows[1:])):
        raise ValueError('loop rows are out of order')
    return meta, rows


def inspect_log(meta, rows):
    """Existing observations, explicitly separate from a scored episode."""
    return {
        'stage': 'log_inspection_only', 'gameplay_benchmark': False,
        'stop': meta.get('stop'), 'cooldowns': meta.get('cooldowns'),
        'declared_patch': meta.get('patch'), 'observed_patch': None,
        'rows': len(rows), 'native': meta.get('native'),
        'saved_frames': sum(bool(r.get('file')) for r in rows),
        'track_rows': sum('ids' in r for r in rows),
        'scoreboards': meta.get('scoreboards', []), 'range_gaps': meta.get('range_gaps', []),
        'latency_ms': {'tick_compute': distribution(r.get('ms') for r in rows),
                       'decision_compute': distribution(r.get('ms_decide') for r in rows),
                       'capture_to_input': distribution(())},
        'run_latency_summary': {k: meta.get(k) for k in ('tick_ms', 'decide_ms', 'decision_lag_ms', 'period_ms')},
        'missing_for_scoring': ['verified_target_readiness', 'observed_patch_and_settings',
                                'target_associated_kill_or_audited_timeout', 'reset_epoch_and_counter_baseline'],
    }


def read_pixels(path):
    """Use the existing pixel outcome reader; presence never becomes target identity."""
    import cv2
    from perception.scoreboard import is_killfeed, read_scoreboard

    frame = cv2.imread(str(path))
    if frame is None:
        raise ValueError(f'unreadable image: {path}')
    return {'file': str(path), 'native': [frame.shape[1], frame.shape[0]],
            'scoreboard': read_scoreboard(frame), 'killfeed_present': is_killfeed(frame),
            'designated_target_completion': None, 'full_target_health': None}


def range_observations(gaps, bounds, epoch, evidence):
    """Merge overlapping [loss, recovery) intervals; retain state at interval start."""
    merged = []
    for lo, hi in sorted(gaps, key=lambda gap: gap[0]):
        end = math.inf if hi is None else hi
        if not math.isfinite(lo) or (hi is not None and not math.isfinite(hi)) or end < lo:
            raise ValueError('invalid range gap')
        if end == lo:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([lo, end])
    for lo, hi in merged:
        if lo > bounds[1] or hi <= bounds[0]:
            continue
        yield Observation(max(lo, bounds[0]), 'range', evidence, epoch, range_ok=False)
        if hi <= bounds[1]:
            yield Observation(hi, 'range', evidence, epoch, range_ok=True)


def score_manifest(manifest, base=Path('.')):
    """Every scheduled slot produces a result, even when its observation list is empty.

    Manifest is a predeclared schedule, not a filtered list of successful logs.
    Retain it unchanged for the reviewer; fill observations after collection.
    """
    if manifest.get('schema') != 'range-benchmark-v1':
        raise ValueError('expected schema range-benchmark-v1')
    baseline = manifest.get('scripted_baseline')
    if not isinstance(baseline, str) or not baseline.strip():
        raise ValueError('a frozen scripted_baseline revision is required')
    scenarios = manifest.get('scenarios', {})
    if len(scenarios) < 2 or any(not v for v in scenarios.values()):
        raise ValueError('declare at least two start scenarios with location/view/distance/resources')
    slots = manifest.get('trials', [])
    if not slots:
        raise ValueError('predeclare the trial schedule')
    trials, latencies, log_reports, safety, log_intervals = [], {}, {}, {}, {}
    for slot in slots:
        spec = EpisodeSpec(**slot['spec'])
        audit = slot.get('scope_audit', {})
        if audit.get('breach') is not None and type(audit['breach']) is not bool:
            raise ValueError('scope_audit.breach must be true, false or null')
        safety[spec.episode_id] = audit
        if spec.scenario not in scenarios:
            raise ValueError('trial uses undeclared scenario')
        obs = [Observation(**o) for o in slot.get('observations', [])]
        stop = Stop(**slot['stop']) if slot.get('stop') else None
        if slot.get('run_dir'):
            meta, rows = read_log(base / slot['run_dir'])
            log_reports[spec.episode_id] = inspect_log(meta, rows)
            # Restrict timing samples to this slot. Repeated rows across different slots
            # must not silently multiply the latency denominator.
            bounds = slot.get('log_interval')
            if not bounds or len(bounds) != 2 or not bounds[0] <= bounds[1]:
                raise ValueError('run_dir requires explicit log_interval [start, end]')
            log_key = str((base / slot['run_dir']).resolve())
            for lo, hi in log_intervals.get(log_key, []):
                if max(lo, bounds[0]) < min(hi, bounds[1]):
                    raise ValueError('log intervals overlap; latency samples would be counted twice')
            log_intervals.setdefault(log_key, []).append(bounds)
            for row in rows:
                if bounds[0] <= row['t'] < bounds[1]:
                    samples = latencies.setdefault(spec.policy, {'tick_compute': [], 'decision_compute': [], 'capture_to_input': []})
                    samples['tick_compute'].append(row.get('ms'))
                    samples['decision_compute'].append(row.get('ms_decide'))
            # Legacy t precedes the guarded hold. Never upgrade it into a frame
            # acquisition timestamp. Such rows remain visible in log inspection.
            for b in meta.get('scoreboards', []):
                captured_t = b.get('captured_t')
                if captured_t is None:
                    continue
                if type(captured_t) not in (int, float) or not math.isfinite(captured_t):
                    raise ValueError('scoreboard captured_t must be a finite acquisition timestamp')
                if b.get('capture_interval') is None:
                    continue  # grab return alone supplies no conservative acquisition bound
                if b.get('file') and bounds[0] <= captured_t <= bounds[1]:
                    obs.append(board_observation(captured_t, spec.epoch,
                                                 f"{slot['run_dir']}/{b['file']}", b.get('parsed'),
                                                 capture_interval=b['capture_interval'],
                                                 capture_clock=b.get('capture_clock')))
            # Preserve actual runtime failures even if an audit sidecar omits them.
            obs.extend(range_observations(meta.get('range_gaps', []), bounds, spec.epoch,
                                          f"{slot['run_dir']}/meta.json:range_gaps"))
            last_t = rows[-1]['t'] if rows else None
            if meta.get('errors'):
                # The summary has no error timestamps. Fail closed from the start
                # of this interval, retaining the attempted trial in the report.
                obs.append(Observation(bounds[0], 'range', f"{slot['run_dir']}/meta.json:errors",
                                       spec.epoch, range_ok=None))
                stop = Stop(bounds[0], 'runtime_errors_unlocated', f"{slot['run_dir']}/meta.json:errors")
            if last_t is not None and bounds[0] <= last_t <= bounds[1] and meta.get('stop'):
                runtime_stop = Stop(last_t, meta['stop'], f"{slot['run_dir']}/meta.json:stop")
                if stop is None or runtime_stop.t < stop.t:
                    stop = runtime_stop
        trials.append((spec, sorted(obs, key=lambda o: o.t), stop))
    by_policy = {}
    for spec, _, _ in trials:
        by_policy[spec.policy] = by_policy.get(spec.policy, 0) + 1
    if baseline not in by_policy or any(n > 20 for n in by_policy.values()):
        raise ValueError('include baseline; bounded evaluation allows at most 20 scheduled slots per policy')
    results = score_batch(trials)
    schedule_counts = {p: {s: sum(r.spec.policy == p and r.spec.scenario == s for r in results)
                           for s in scenarios} for p in by_policy}
    # Joint counts preserve multiplicity: 4 standing + 1 moving is not 1 + 4.
    contexts = {p: Counter((r.spec.scenario, r.spec.patch, r.spec.cooldowns,
                            json.dumps(r.spec.settings, sort_keys=True))
                           for r in results if r.spec.policy == p) for p in by_policy}
    planned_matching = {p: contexts[p] == contexts[baseline] for p in by_policy}
    # An empty scheduled slot is not an executed baseline. Keep failed attempts,
    # including audited failed readiness, but require evidence and a scope audit
    # for every slot. Each declared bin also needs an actual started encounter.
    executed, observed_after_ready = {}, {}
    for r, (_, observations, stop) in zip(results, trials):
        audit = safety[r.spec.episode_id]
        readiness = next((o for o in observations if o.kind == 'ready'), None)
        observed_after_ready[r.spec.episode_id] = (readiness is not None and (
            (stop is not None and stop.t > readiness.t)
            or any(o.kind in {'range', 'reset', 'kill', 'coverage'} and o.t > readiness.t for o in observations)))
        encounter_evidence = (r.valid or r.outcome == 'setup_failure'
                              or (stop is not None and readiness is not None and stop.t >= readiness.t)
                              or observed_after_ready[r.spec.episode_id])
        executed[r.spec.episode_id] = (readiness is not None and encounter_evidence
                                       and bool(r.evidence)
                                       and type(audit.get('breach')) is bool and bool(audit.get('evidence')))
    execution = {}
    for p in by_policy:
        selected = [r for r in results if r.spec.policy == p]
        support = {s: sum(executed[r.spec.episode_id] and r.outcome != 'setup_failure'
                          and observed_after_ready[r.spec.episode_id]
                          and r.start_t is not None and r.end_t is not None and r.end_t > r.start_t
                          for r in selected if r.spec.scenario == s) for s in scenarios}
        audited = sum(executed[r.spec.episode_id] for r in selected)
        execution[p] = {'auditable_executed_slots': audited, 'started_by_scenario': support,
                        'comparison_ready': audited == len(selected) and all(support.values())}
    matching = {p: planned_matching[p] and execution[p]['comparison_ready']
                and execution[baseline]['comparison_ready'] for p in by_policy}
    summaries = {}
    for policy in by_policy:
        selected = [r for r in results if r.spec.policy == policy]
        audits = [safety[r.spec.episode_id] for r in selected]
        audited = sum(type(a.get('breach')) is bool and bool(a.get('evidence')) for a in audits)
        breaches = sum(a.get('breach') is True for a in audits)
        summaries[policy] = summarise(selected, latency=latencies.get(policy),
                                     scope_audited_trials=audited,
                                     scope_breaches=breaches if audited == len(selected) or breaches else None,
                                     matched_baseline=matching[policy])
        summaries[policy]['by_scenario'] = {
            scenario: summarise([r for r in selected if r.spec.scenario == scenario])
            for scenario in scenarios}
    if any(a.get('breach') is True for a in safety.values()):
        for summary in summaries.values():
            summary['feasibility_gate']['passed'] = False
    exposure = manifest.get('wall_seconds')
    if exposure is not None and (not math.isfinite(exposure) or exposure <= 0):
        raise ValueError('wall_seconds must include all setup/reset time and be positive')
    human = manifest.get('human_reference')
    human_policies = [p for p in by_policy if p.startswith('human:')]
    return {
        'schema': 'range-benchmark-result-v1', 'stage': 'offline_scoring_requires_independent_audit',
        'summary': summarise(results, wall_seconds=exposure,
                             reset_seconds=manifest.get('reset_seconds', []),
                             respawn_seconds=manifest.get('respawn_seconds', [])),
        'by_policy': summaries, 'schedule_counts': schedule_counts,
        'comparable_schedule': all(planned_matching.values()),
        'execution_evidence': execution,
        'matched_baseline_comparison': matching,
        'human_reference': {'declared': human, 'scored_policies': human_policies,
                            'comparison': 'matched_metrics_available' if human and human_policies
                                          and all(matching[p] and summaries[p]['valid_episodes'] for p in human_policies)
                                          and summaries[baseline]['valid_episodes']
                                          else 'not_established'},
        'scope_audits': safety,
        'experiment_stop_required': any(a.get('breach') is True for a in safety.values()),
        'promotion': None, 'results': [r.to_dict() for r in results], 'logs': log_reports,
        'capture_timing_requirement': ('Grab intervals are acquisition bounds, not render or game-event times. '
                                       'Auditors must bound any render age in native evidence; '
                                       'kill occurrence intervals never come from scoreboard captured_t.'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('inspect-log').add_argument('run_dir', type=Path)
    sub.add_parser('score').add_argument('manifest', type=Path)
    sub.add_parser('read-pixels').add_argument('frames', nargs='+', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'inspect-log':
        report = inspect_log(*read_log(args.run_dir))
    elif args.command == 'score':
        report = score_manifest(json.loads(args.manifest.read_text(encoding='utf-8')), args.manifest.parent)
    else:
        report = [read_pixels(p) for p in args.frames]
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
