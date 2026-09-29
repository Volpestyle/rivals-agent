"""Read only checks of this candidate and its explicit holes; no corpus or pad."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.camera_map import CameraMapError, load_camera_map


def refuses(call, word):
    try:
        call()
    except CameraMapError as exc:
        assert word in str(exc), str(exc)
    else:
        raise AssertionError('operation unexpectedly allowed')


def main():
    here = Path(__file__).parent
    camera = load_camera_map('alt-247-124')
    live = load_camera_map('alt-247-124', live=True)
    yaw = json.loads((here / 'yaw-results-final.json').read_text())
    checks = []
    for result in yaw:
        stick = result['stick']
        rate = result['rate_magnitude_deg_s']
        assert result['turns'] >= 1
        assert abs(rate * result['elapsed_s'] - result['turns'] * 360) < 1e-8
        low, high = result['conservative_endpoint_bounds_deg_s']
        assert 0 < low <= rate <= high
        assert camera.rate('yaw', stick) == (rate if stick > 0 else -rate)
        refuses(lambda: live.rate('yaw', stick), 'candidate')
        checks.append(f'yaw {stick:+g}: measured knot, bounds, turn arithmetic, live refusal')
    assert camera.rate('yaw', .45) == 154  # prior separately pinned source retained
    refuses(lambda: live.rate('yaw', .45), 'candidate')
    assert len([m for rows in camera.axes['yaw'].values() for _, m in rows if m.value is not None]) == 14
    for sign in (-1, 1):
        for stick in (.1, .2, .3, .45, .6, .8, 1.):
            refuses(lambda: camera.rate('pitch', sign * stick), 'missing')
    for scalar in ('focal', 'latency', 'interpolation'):
        refuses(lambda: camera.scalar(scalar), 'missing')
    refuses(camera.require_controller, 'missing')
    refuses(live.require_controller, 'missing')
    refuses(lambda: camera.rate('yaw', .15), 'missing')
    refuses(lambda: camera.stick('yaw', 80), 'missing')
    checks.append('14 missing pitch knots; missing scalars, interpolation, inverse and controller fail closed')
    pitch = json.loads((here / 'pitch-results.json').read_text())
    assert len(pitch) == 14
    for row in pitch:
        assert row['scene_pixel_rate_median_1280'] * row['segment']['stick'] > 0
        assert row['late_motion_pairs'] == row['late_pair_count'] == 4
        assert row['degrees_rate'] is None
    checks.append('pitch sign and all late-motion checks agree; no fabricated degree rate')
    attempts = json.loads((here / 'focal-counts-attempts.json').read_text())
    assert len(attempts) == 2
    for attempt in attempts:
        assert attempt['result']['status'] == 'refused'
        assert attempt['result']['focal_candidate'] is None
        assert len(attempt['rows']) == 6
        for row in attempt['rows']:
            gain = ROOT / row['gain_evidence']['ref']
            assert hashlib.sha256(gain.read_bytes()).hexdigest() == row['gain_evidence']['sha256']
    checks.append('both focal attempts refused; current gain-provenance pins match')
    print(json.dumps({'status': 'pass', 'candidate_sha256': camera.sha256, 'checks': checks}, indent=2))


if __name__ == '__main__':
    main()
