"""Lead-run, neutral-only takeover verification: three touches within 60 seconds.

python -m agent.verify_takeover --game-pid PID --out NEW_DIR
Keep the range focused. Follow the printed KEY, CLICK, MOVE prompts, then release
and keep hands off for the next prompt. No attacks, motion or attach opener are
sent. A wrong touch, missing raw receipt, >100 ms receipt-to-close, or guard stop
fails the check; this script never resumes gameplay.
"""
import argparse
import json
import math
from pathlib import Path
import time

from . import loop as L
from .controller import FRESH_S, NEUTRAL, RangeLost


def touch_kind(trip):
    if not trip:
        return None
    if trip.get('kind') == 'key':
        return 'key'
    if trip.get('kind') == 'mouse':
        if trip.get('button_flags', 0) & 0x155:  # button DOWNs, not wheel/release
            return 'click'
        if trip.get('dx') or trip.get('dy') or trip.get('flags', 0) & 1:
            return 'move'
    return None


def trial(kind, focus, percept, deadline, *, takeover_factory=L.human_takeover_guard,
          opener=L._open_live_io, clock=time.perf_counter, sleep=time.sleep, prompt=print):
    takeover = source = safety = None
    result = {'requested': kind, 'passed': False, 'neutral_only': True}
    try:
        if clock() >= deadline:
            raise RangeLost('verification deadline')
        takeover = takeover_factory()
        safety = L.LiveSafety(focus, takeover, deadline, clock=clock)
        # Deliberately no attach_opener: construction cannot send the tiny walk.
        source = opener(safety, percept, lambda f: False, lambda f: False)
        source.release()
        result['attached_t'] = clock()
        guard = safety.proof(percept.in_range, percept.idle, range_required=True)
        prompt(f'{kind.upper()} NOW: one {kind}, then hands off.', flush=True)
        while safety.check():
            frame, stamp = source.next()
            if not guard(frame):
                break
            until = min(stamp + FRESH_S, deadline - source.t0)
            source.send_guarded(dict(NEUTRAL), not_after=until, release_at=until,
                                scope_not_after=deadline - source.t0)
            sleep(.005)
    except Exception as exc:
        result['exception'] = repr(exc)
    finally:
        try:
            if safety is not None:
                # Pad close precedes waiting for receipt evidence or file writes.
                safety._close_live()
            if source is not None:
                source.close()
            if takeover is not None:
                # The legacy poll can release before the pipe delivers TRIP.
                end = min(deadline, clock() + .15)
                while not takeover.raw.trip and clock() < end:
                    sleep(.005)
                result['takeover'] = takeover.snapshot()
            if safety is not None:
                result['safety'] = dict(safety.status)
                trip = result.get('takeover', {}).get('raw_trip')
                received = (trip or {}).get('received_perf_s')
                closed = safety.status.get('close_returned_t')
                if isinstance(received, (int, float)) and isinstance(closed, (int, float)):
                    result['receipt_to_close_s'] = closed - received
                    result['passed'] = (safety.status['stop_reason'] == 'human_takeover'
                                        and touch_kind(trip) == kind and received >= result.get('attached_t', math.inf)
                                        and math.isfinite(closed - received) and 0 <= closed - received <= .1
                                        and safety.status['close_returned'])
        finally:
            if safety is not None:
                safety.close()
            elif takeover is not None:
                takeover.close()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-pid', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('output exists; preserve the previous verification')
    if not 0 < args.game_pid <= 0xffffffff:
        parser.error('positive game PID required')
    from .learned_runner import limit_cpu_threads
    limit_cpu_threads(False)
    percept, focus = L.default_perception(), L.foreground_pid_guard(args.game_pid)
    args.out.mkdir(parents=True)
    started = time.perf_counter()
    end, rows = started + 60., []
    try:
        for kind in ('key', 'click', 'move'):
            if rows:
                print('Released. Hands off; next prompt in two seconds.', flush=True)
                time.sleep(min(2., max(0., end-time.perf_counter())))
            row = trial(kind, focus, percept, min(end, time.perf_counter()+18.))
            rows.append(row)
            (args.out / f'{kind}.json').write_text(json.dumps(row, indent=2)+'\n')
            print(f'{kind}: {"PASS" if row["passed"] else "FAIL"}', flush=True)
            if not row['passed']:
                break
    finally:
        result = {'passed': len(rows) == 3 and all(r['passed'] for r in rows), 'trials': rows,
                  'elapsed_s': time.perf_counter()-started, 'neutral_only': True,
                  'timing': 'raw WM_INPUT receipt to pad close return; not hardware latency'}
        (args.out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
