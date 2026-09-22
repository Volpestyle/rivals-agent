"""Offline, deterministic range encounter scoring. No capture, perception or input imports.

Evidence records are assertions made by an audited pixel reader or a human reviewing
native recordings. A track ID, a vanished box and a kill-feed *presence* bit are
not such an assertion. See docs/lanes/range-benchmark.md for the wire contract.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import math
from typing import Iterable

HORIZON_S = 20.0


@dataclass(frozen=True)
class EpisodeSpec:
    episode_id: str
    run_id: str
    policy: str                    # frozen revision/checkpoint; 'human:<reference id>' for James
    scenario: str                  # predeclared location/view/distance/resource bin
    epoch: str                     # scoreboard/reset epoch, never silently reused
    target: str                    # visual bot incarnation, not its common display name
    track: int
    patch: str | None = None
    patch_evidence: str | None = None
    cooldowns: str | None = None
    settings_evidence: str | None = None
    settings: dict = field(default_factory=dict)  # bot health/movement, bindings, swing
    display_grace_s: float = 2.0    # observation only; does not extend gameplay

    def __post_init__(self):
        for name in ('episode_id', 'run_id', 'policy', 'scenario', 'epoch', 'target'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f'{name} must be nonempty')
        if type(self.track) is not int or self.track < 0:
            raise ValueError('track must be a nonnegative integer')
        if not math.isfinite(self.display_grace_s) or not 0 <= self.display_grace_s <= 5:
            raise ValueError('display grace must be between 0 and 5 seconds')


@dataclass(frozen=True)
class Observation:
    t: float                      # same monotonic clock as frames.jsonl
    kind: str                     # ready, board, kill, coverage, range, reset
    evidence: str                 # native frame/recording interval and audit identity
    epoch: str
    target: str | None = None
    track: int | None = None
    range_ok: bool | None = None
    identity: bool | None = None
    full_health: bool | None = None
    resources_ready: bool | None = None
    kos: int | None = None         # ONLY read_scoreboard's open=True result
    event_id: str | None = None    # persistent event ID, not per-frame feed visibility
    lo: float | None = None       # occurrence interval for kill; audited interval for coverage
    hi: float | None = None
    association: str | None = None # reviewed visual continuity target -> kill feed
    capture_clock: str | None = None  # board acquisition interval, never game-event time

    def __post_init__(self):
        if self.kind not in {'ready', 'board', 'kill', 'coverage', 'range', 'reset'}:
            raise ValueError(f'unknown observation kind: {self.kind}')
        if not math.isfinite(self.t) or not self.evidence or not self.epoch:
            raise ValueError('observations need finite timestamps, epoch and evidence')
        if self.kos is not None and (type(self.kos) is not int or self.kos < 0):
            raise ValueError('KO counter must be a nonnegative integer or None')
        if self.kind in {'kill', 'coverage'}:
            if (self.lo is None or self.hi is None or not math.isfinite(self.lo)
                    or not math.isfinite(self.hi) or not self.lo <= self.hi <= self.t):
                raise ValueError('invalid observation interval')
        if self.kind == 'board' and (self.lo is not None or self.hi is not None or self.capture_clock is not None):
            if (self.lo is None or self.hi is None or not math.isfinite(self.lo)
                    or not math.isfinite(self.hi) or not self.lo <= self.hi == self.t
                    or self.capture_clock != 'grab_start_to_return_loop_seconds'):
                raise ValueError('board needs a valid grab interval ending at captured_t')


@dataclass(frozen=True)
class Stop:
    t: float
    reason: str
    evidence: str

    def __post_init__(self):
        if not math.isfinite(self.t) or not self.reason or not self.evidence:
            raise ValueError('stop needs finite timestamp, reason and evidence')


@dataclass(frozen=True)
class EpisodeResult:
    spec: EpisodeSpec
    outcome: str                   # completed, timeout, interrupted, lost_range, unknown, setup_failure
    reason: str
    start_t: float | None
    end_t: float | None
    elapsed_s: float | None
    reward: float | None
    components: dict
    evidence: tuple[str, ...]
    event_id: str | None = None
    counter_credit: int | None = None
    completion_interval_s: tuple[float, float] | None = None

    @property
    def valid(self):
        return self.outcome in {'completed', 'timeout'}

    def to_dict(self):
        return {**asdict(self), 'valid': self.valid}


def score_episode(spec: EpisodeSpec, observations: Iterable[Observation], *,
                  stop: Stop | None = None,
                  prior_observations: Iterable[Observation] = (),
                  used_events: frozenset[tuple] = frozenset(),
                  used_counters: frozenset[tuple] = frozenset()) -> EpisodeResult:
    """Score one encounter, without mutating observations or credit registries.

    Timeout needs audited continuous coverage of [ready, deadline], confirming no
    designated completion. A loop max_time alone never proves that fact. Delayed
    kill display can be credited only with an occurrence interval wholly inside
    the encounter, corroborating counter and no intervening reset/interruption.
    """
    obs = list(observations)
    if any(a.t > b.t for a, b in zip(obs, obs[1:])):
        raise ValueError('observations must be ordered by display timestamp')
    ready = next((o for o in obs if o.kind == 'ready'), None)
    start = ready.t if ready else None
    # Readiness belongs to this trial; earlier run observations constrain its
    # history but must never substitute an earlier trial's ready assertion.
    history = list(prior_observations)
    if start is not None and any(o.t >= start for o in history):
        raise ValueError('prior run observations overlap trial readiness')
    obs = sorted(dict.fromkeys(history + obs), key=lambda o: o.t)

    def result(outcome, reason, end=None, evidence=(), kill=None, counter=None):
        elapsed = None if start is None or end is None else min(HORIZON_S, max(0, end - start))
        valid = outcome in {'completed', 'timeout'}
        event_reward = 1.0 if outcome == 'completed' else -0.25 if outcome == 'timeout' else None
        time_reward = -0.20 * elapsed / HORIZON_S if valid else None
        return EpisodeResult(spec, outcome, reason, start, end, elapsed,
                             round(event_reward + time_reward, 9) if valid else None,
                             {'event': event_reward, 'time': time_reward, 'damage': None,
                              'valid': valid, 'source': 'audited_pixels' if valid else None},
                             tuple(evidence), kill.event_id if kill else None, counter,
                             (kill.lo - start, kill.hi - start) if kill else None)

    missing = [name for name in ('patch', 'patch_evidence', 'settings_evidence')
               if not getattr(spec, name) or getattr(spec, name) == 'unknown']
    missing += [f'settings.{k}' for k in ('bot_health', 'bot_movement', 'bindings', 'swing')
                if spec.settings.get(k) in (None, '', 'unknown')]
    if spec.cooldowns != 'normal':
        missing.append('normal_cooldowns')
    if missing:
        return result('setup_failure', 'unverified_context:' + ','.join(missing))
    if (ready is None or ready.epoch != spec.epoch or ready.target != spec.target
            or ready.track != spec.track or any(x is not True for x in
                (ready.range_ok, ready.identity, ready.full_health, ready.resources_ready))):
        return result('setup_failure', 'readiness_unverified', evidence=(ready.evidence,) if ready else ())
    if stop and stop.t < start:
        return result('setup_failure', 'stopped_before_ready', evidence=(stop.evidence,))
    # A reset starts a new counter epoch. Validate the history *before* readiness,
    # too: a fresh ready assertion cannot rehabilitate a pre-reset baseline.
    seen_epochs = set()
    seen_resets = set()
    reset_epochs = {}
    boundary = -math.inf
    last_reset = None
    for o in obs:
        if o.t >= start:
            break
        if o.kind == 'reset':
            reset_key = (o.t, o.epoch)
            if reset_key in seen_resets:
                continue  # the same run boundary may be cited by multiple trials
            seen_resets.add(reset_key)
            if o.t in reset_epochs and reset_epochs[o.t] != o.epoch:
                return result('setup_failure', 'conflicting_reset_epochs', evidence=(o.evidence, ready.evidence))
            reset_epochs[o.t] = o.epoch
            if o.epoch in seen_epochs:
                return result('setup_failure', 'reset_reused_epoch', evidence=(o.evidence, ready.evidence))
            last_reset = o
            boundary = o.t
        elif o.epoch != spec.epoch:
            boundary = o.t
        seen_epochs.add(o.epoch)
    if last_reset is not None and last_reset.epoch != spec.epoch:
        return result('setup_failure', 'readiness_epoch_precedes_reset',
                      evidence=(last_reset.evidence, ready.evidence))
    deadline = start + HORIZON_S
    # Faults bound evidence, including the observation-only display grace period.
    faults = [(o.t, 'lost_range' if o.range_ok is False and o.kind == 'range' else 'interrupted',
               'reset' if o.kind == 'reset' or o.epoch != spec.epoch else 'range_unknown', o.evidence)
              for o in obs if o.t >= start and (o.kind == 'reset' or o.epoch != spec.epoch
                                               or (o.kind == 'range' and o.range_ok is not True))]
    # Range is a state, not a one-tick pulse. Only an explicit recovery clears a
    # pre-ready failure; the ready assertion itself cannot erase a logged gap.
    range_at_start = max((o for o in obs if o.kind == 'range' and o.t <= start
                          and o.epoch == spec.epoch), default=None,
                         key=lambda o: (o.t, o.range_ok is not True, o.range_ok is False))
    if range_at_start is not None and range_at_start.range_ok is not True:
        faults.append((start, 'lost_range' if range_at_start.range_ok is False else 'interrupted',
                       'range_gap_active_at_ready', range_at_start.evidence))
    if stop and stop.reason not in {'max_time', 'episode_deadline', 'episode_complete', 'end_of_log'}:
        faults.append((stop.t, 'interrupted', stop.reason, stop.evidence))
    fault = min(faults, default=None, key=lambda x: x[0])
    cutoff = min(deadline + spec.display_grace_s, fault[0] if fault else math.inf,
                 stop.t if stop and stop.t < deadline and stop.reason != 'episode_complete' else math.inf)
    # Unknown outcomes have observed duration only; reaching a configured horizon
    # in arithmetic is not evidence that any frame or stop occurred there.
    observed_end = min(deadline, cutoff, max([start, *(o.t for o in obs if start <= o.t <= cutoff),
                                             *([stop.t] if stop and start <= stop.t <= cutoff else [])]))
    boards = [o for o in obs if o.kind == 'board' and o.epoch == spec.epoch and o.kos is not None
              and boundary < (o.lo if o.lo is not None else o.t) and o.t <= cutoff]
    baseline = next((o for o in reversed(boards) if o.t <= start), None)
    # Never turn a decrease (reset, OCR error) into a new positive delta.
    counter_bad = any(b.kos < a.kos for a, b in zip(boards, boards[1:]) if b.t >= start)
    uncertain = []
    kills = [o for o in obs if o.kind == 'kill' and start <= o.t <= cutoff
             and o.epoch == spec.epoch and o.target == spec.target]
    for kill in kills:
        if kill.hi < start or kill.lo > deadline:
            continue
        if kill.lo < start or kill.hi > deadline:
            uncertain.append('kill_interval_crosses_boundary')
            continue
        if stop and kill.hi > stop.t:
            uncertain.append('kill_after_runtime_stop')
            continue
        if not kill.event_id or kill.track != spec.track or kill.identity is not True or not kill.association:
            uncertain.append('target_association_unverified')
            continue
        if (spec.run_id, spec.epoch, kill.event_id) in used_events:
            uncertain.append('event_already_credited')
            continue
        # Grab return is not an exact observation/event time. The entire grab
        # interval must follow the audited kill bound, and a baseline's entire
        # interval must end before readiness. Rendering age remains an audit duty.
        after = next((b for b in boards if (b.lo if b.lo is not None else b.t) >= kill.hi
                      and baseline and b.kos == baseline.kos + 1), None)
        if counter_bad or baseline is None or after is None:
            uncertain.append('counter_corroboration_unverified')
            continue
        if (spec.run_id, spec.epoch, after.kos) in used_counters:
            uncertain.append('counter_already_credited')
            continue
        if fault and (kill.hi >= fault[0] or kill.t >= fault[0] or after.t >= fault[0]):
            continue
        return result('completed', 'designated_bot_confirmed', kill.hi,
                      (ready.evidence, baseline.evidence, kill.evidence, kill.association, after.evidence),
                      kill, after.kos)
    if fault and fault[0] <= deadline:
        return result(fault[1], fault[2], fault[0], (ready.evidence, fault[3]))
    if stop and stop.t < deadline:
        return result('interrupted', stop.reason, stop.t, (ready.evidence, stop.evidence))
    if counter_bad:
        uncertain.append('counter_decreased')
    if uncertain:
        return result('unknown', ','.join(sorted(set(uncertain))), observed_end,
                      (ready.evidence, *(o.evidence for o in kills)))
    # Coverage is a reviewed no-completion interval, NOT 'no detection this tick'.
    through = start
    coverage = []
    for o in sorted((o for o in obs if o.kind == 'coverage' and o.t <= cutoff
                     and o.epoch == spec.epoch and o.target == spec.target and o.track == spec.track
                     and o.identity is True and o.association), key=lambda o: o.lo):
        if o.lo <= through:
            through = max(through, o.hi)
            coverage.extend((o.evidence, o.association))
    if through >= deadline:
        return result('timeout', 'audited_no_completion_by_deadline', deadline, (ready.evidence, *coverage))
    return result('unknown', 'outcome_coverage_missing', observed_end, (ready.evidence,))


def score_batch(trials):
    """Chronological trials; observations and credits persist within each run."""
    results, events, counters, ids, boundaries = [], set(), set(), set(), {}
    histories = {}
    for spec, observations, stop in trials:
        if spec.episode_id in ids:
            raise ValueError('duplicate episode_id')
        ids.add(spec.episode_id)
        observations = list(observations)
        ready = next((o.t for o in observations if o.kind == 'ready'), None)
        if ready is not None and ready <= boundaries.get(spec.run_id, -math.inf):
            raise ValueError('episodes overlap or are out of order within run')
        scored = score_episode(spec, observations, stop=stop,
                               prior_observations=histories.get(spec.run_id, ()),
                               used_events=frozenset(events), used_counters=frozenset(counters))
        results.append(scored)
        histories[spec.run_id] = sorted(dict.fromkeys(histories.get(spec.run_id, []) + observations), key=lambda o: o.t)
        if observations or stop:
            # Attribution must finish before another target/reset begins.
            boundaries[spec.run_id] = max([boundaries.get(spec.run_id, -math.inf), *(o.t for o in observations),
                                          *([stop.t] if stop else [])])
        if scored.event_id is not None:
            events.add((spec.run_id, spec.epoch, scored.event_id))
            counters.add((spec.run_id, spec.epoch, scored.counter_credit))
    return results


def distribution(values):
    xs = sorted(v for v in values if v is not None and math.isfinite(v) and v >= 0)
    if not xs:
        return {'n': 0, 'p50': None, 'p95': None, 'max': None}
    return {'n': len(xs), 'p50': xs[math.ceil(len(xs) * .5) - 1],
            'p95': xs[math.ceil(len(xs) * .95) - 1], 'max': xs[-1]}


def wilson(successes, total):
    """Descriptive 95% binomial interval; repeated bot trials need not be independent."""
    if not total:
        return None
    p, z = successes / total, 1.959963984540054
    den = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / den
    return [max(0, centre - half), min(1, centre + half)]


def summarise(results, *, wall_seconds=None, reset_seconds=(), respawn_seconds=(), latency=None,
              scope_audited_trials=0, scope_breaches=None, matched_baseline=None):
    results = list(results)
    counts = Counter(r.outcome for r in results)
    attempts = len(results) - counts['setup_failure']
    valid = sum(r.valid for r in results)
    successes = counts['completed']
    gate = None
    if scope_breaches or len(results) != 10 or successes < 8 or matched_baseline is False:
        gate = False
    elif scope_audited_trials == 10 and scope_breaches == 0 and matched_baseline is True:
        gate = True
    return {
        'scheduled_trials': len(results), 'attempted_episodes': attempts,
        'setup_failures': counts['setup_failure'], 'valid_episodes': valid,
        'outcomes': dict(sorted(counts.items())), 'successes': successes,
        'success_per_attempt': successes / attempts if attempts else None,
        'success_per_scheduled_trial': successes / len(results) if results else None,
        'success_per_valid_episode': successes / valid if valid else None,
        'primary_metric': 'success_per_scheduled_trial',
        'scheduled_success_wilson95': wilson(successes, len(results)),
        'attempted_success_wilson95': wilson(successes, attempts),
        'uncertainty_note': 'Small, possibly correlated trial sample; feasibility only, not human parity.',
        'invalid_attempt_fraction': (attempts - valid) / attempts if attempts else None,
        'restricted_completion_s': (sum(r.elapsed_s if r.outcome == 'completed' else HORIZON_S
                                        for r in results if r.outcome != 'setup_failure') / attempts
                                    if attempts else None),
        'wall_seconds': wall_seconds,
        'valid_episodes_per_hour': valid * 3600 / wall_seconds if wall_seconds and wall_seconds > 0 else None,
        'reset_seconds': distribution(reset_seconds), 'respawn_seconds': distribution(respawn_seconds),
        'latency_ms': {k: distribution(v) for k, v in (latency or {}).items()},
        'failures': [{'episode_id': r.spec.episode_id, 'policy': r.spec.policy, 'scenario': r.spec.scenario,
                      'outcome': r.outcome, 'reason': r.reason, 'elapsed_s': r.elapsed_s,
                      'evidence': list(r.evidence)}
                     for r in results if r.outcome != 'completed'],
        'feasibility_gate': {'scheduled_trials_required': 10, 'minimum_successes': 8,
                             'scope_audited_trials': scope_audited_trials, 'scope_breaches': scope_breaches,
                             'matched_baseline': matched_baseline, 'passed': gate,
                             'meaning': 'feasibility, not pro-level parity'},
    }


def board_observation(t, epoch, evidence, parsed, *, capture_interval=None, capture_clock=None):
    """Adapt a board with explicit audited time or a preserved grab interval.

    A grab interval describes acquisition, not when the rendered pixels or kill
    occurred. Its end is t; audit must account for any earlier rendered frame.
    """
    if capture_interval is not None and len(capture_interval) != 2:
        raise ValueError('capture_interval requires [grab_start, grab_return]')
    return Observation(t, 'board', evidence, epoch,
                       kos=parsed.get('kos') if parsed and parsed.get('open') is True else None,
                       lo=capture_interval[0] if capture_interval is not None else None,
                       hi=capture_interval[1] if capture_interval is not None else None,
                       capture_clock=capture_clock)
