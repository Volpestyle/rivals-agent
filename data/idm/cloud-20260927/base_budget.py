"""Fixed $30 explore reservation, independent of round 3 accounting."""
import json
import math
from pathlib import Path
import time

CAP = 30.0
RATE = .000542 + 8 * .0000131 + 32 * .00000222
ARMS = (1, 4, 8)
PRIOR_CHARGE = .80  # Failed CPU-only attempt: conservative bound, not a bill.
OVERHEAD = .75 + PRIOR_CHARGE
STOP_SECONDS = 120
STARTUP_SECONDS = 300
APP_NAME = 'rivals-explore-chunks-20260927-attempt2'
INPUT_VOLUME = 'rivals-explore-chunks-20260927'
OUTPUT_VOLUME = APP_NAME + '-outputs'
IDENTITY = {'profile': 'rivals', 'workspace': 'volpestyle',
            'workspace_id': 'ac-kMLf5bJKqF5CAlSbfNhGh0'}


def reservation(*, wall=None, mono=None):
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in (wall, mono)):
        raise ValueError('Positive finite local clocks required')
    lifetime = math.floor((CAP - OVERHEAD) / (len(ARMS) * RATE))
    stop_after = lifetime - STOP_SECONDS
    return {'cap_usd': CAP, 'overhead_reserve_usd': OVERHEAD,
            'prior_attempt_charge_usd': PRIOR_CHARGE, 'new_overhead_usd': .75,
            'rate_usd_second_per_arm': RATE, 'arms': list(ARMS), 'attempts_per_arm': 1,
            'started_at_unix': wall, 'started_monotonic': mono,
            'stop_at_unix': wall + stop_after, 'stop_monotonic': mono + stop_after,
            'funded_until_unix': wall + lifetime, 'lifetime_seconds': lifetime,
            'function_timeout_seconds': stop_after - STARTUP_SECONDS,
            'startup_seconds': STARTUP_SECONDS, 'stop_seconds': STOP_SECONDS,
            'reserved_usd': OVERHEAD + lifetime * len(ARMS) * RATE,
            'app_name': APP_NAME, 'identity': IDENTITY}


def reserve_once(directory):
    """Exclusive persistent reservation precedes any image/app/function creation."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    value = reservation()
    with (directory / 'budget-reservation.json').open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return value


def spend_bound(value, *, wall=None, mono=None):
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    elapsed = max(0, wall - value['started_at_unix'], mono - value['started_monotonic'])
    return OVERHEAD + elapsed * len(ARMS) * RATE


def expired(value, *, wall=None, mono=None):
    wall = time.time() if wall is None else wall
    mono = time.monotonic() if mono is None else mono
    if not math.isfinite(wall) or not math.isfinite(mono):
        return True
    return (wall >= value['stop_at_unix'] or mono >= value['stop_monotonic']
            or spend_bound(value, wall=wall, mono=mono) + STOP_SECONDS * len(ARMS) * RATE > CAP)
