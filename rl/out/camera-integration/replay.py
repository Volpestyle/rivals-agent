"""CPU-only log counterfactual; never opens frames, a policy, capture or pad."""
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from agent.learned_runner import CameraPulses, STEP_S, camera_request  # noqa: E402

OUT = Path(__file__).resolve().parent
AXES = ('yaw', 'pitch')


def replay(path):
    rows = [json.loads(line) for line in (path/'frames.jsonl').read_text().splitlines() if line.strip()]
    result = json.loads((path/'result.json').read_text())
    decisions = [r for r in rows if r.get('event') == 'decision']
    cameras = {'after': CameraPulses()}
    records = []
    discarded = {r['tick'] for r in rows if r.get('event') == 'discard'}
    prev = None
    for row in decisions:
        dt = 1/result['decision_hz'] if prev is None else row['t']-prev
        prev = row['t']
        assert dt > 0
        request = camera_request(row['yaw_deg'], row['pitch_deg'], dt, row['yaw_scale'])
        record = {'tick': row['tick'], 't': row['t'], 'interval_s': dt,
                  'ready': row['disposition'] == 'ready', **request,
                  'interval_clamped': not STEP_S <= dt <= 3*STEP_S}
        for axis in AXES:
            perstep = row[f'{axis}_deg'] * (row['yaw_scale'] if axis == 'yaw' else 1.)
            record[f'{axis}_rate_requested'] = perstep/STEP_S
            record[f'{axis}_rate_before_request'] = perstep/dt
            record[f'{axis}_rate_after_request'] = request[f'requested_{axis}_deg']/dt
            # Baseline allocations are retained facts, not a reconstructed
            # residual clock (age_s is logged before the final HUD proof).
            old = [p for p in row['pulses'] if p['axis'] == axis] if record['ready'] else []
            record[f'{axis}_before_deg'] = sum(p['estimated_deg'] for p in old)
            record[f'{axis}_before_cap'] = any(p['clamped'] for p in old)
        for mode, camera in cameras.items():
            if not record['ready']:
                camera.reset()
                for axis in AXES:
                    record[f'{axis}_{mode}_deg'] = 0.
                    record[f'{axis}_{mode}_cap'] = False
                continue
            camera.begin(row['t'], row['t']+row['age_s'])
            pulses = []
            for axis in AXES:
                degrees = request[f'requested_{axis}_deg']
                pulse = camera.pulse(axis, degrees)
                if pulse:
                    pulses.append(pulse)
                record[f'{axis}_{mode}_deg'] = pulse['estimated_deg'] if pulse else 0.
                record[f'{axis}_{mode}_cap'] = bool(pulse and pulse['clamped'])
            if pulses:
                camera.reset()  # runner releases after every camera pulse
            if row['tick'] in discarded:
                camera.reset()
        records.append(record)
    return {'source': path.relative_to(ROOT).as_posix(), 'records': records}


def summarize(runs):
    records = [r for run in runs for r in run['records']]
    ready = [r for r in records if r['ready']]
    elapsed = sum(r['interval_s'] for r in records)
    stats = {'decisions': len(records), 'ready': len(ready), 'interval_sum_s': elapsed,
             'interval_median_s': statistics.median(r['interval_s'] for r in records),
             'interval_clamped': sum(r['interval_clamped'] for r in records),
             'ready_interval_clamped': sum(r['interval_clamped'] for r in ready)}
    for axis in AXES:
        stats[axis] = {
            'requested_abs_deg_s': sum(abs(r[f'{axis}_rate_requested'])*r['interval_s'] for r in records)/elapsed,
            'before_request_abs_deg_s': sum(abs(r[f'{axis}_rate_before_request'])*r['interval_s'] for r in records)/elapsed,
            'after_request_abs_deg_s': sum(abs(r[f'{axis}_rate_after_request'])*r['interval_s'] for r in records)/elapsed,
            'before_capped_abs_deg_s': sum(abs(r[f'{axis}_before_deg']) for r in records)/elapsed,
            'after_capped_abs_deg_s': sum(abs(r[f'{axis}_after_deg']) for r in records)/elapsed,
            'before_cap_decisions': sum(r[f'{axis}_before_cap'] for r in ready),
            'after_cap_decisions': sum(r[f'{axis}_after_cap'] for r in ready),
            'nonzero_ready_requests': sum(r[f'requested_{axis}_deg'] != 0 for r in ready),
        }
    return stats


def plot(stats):
    """Standard raster chart with identical rate scale within each panel."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGB', (1350, 830), '#111a26')
    draw = ImageDraw.Draw(im)
    font = lambda size: ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', size)
    draw.text((30, 18), 'Camera integration at the recorded decision cadence', font=font(30), fill='white')
    draw.text((30, 61), 'Offline log counterfactual | 2026-10-02 | VUH-1321 | no live input', font=font(19), fill='#a6b7c9')
    colors = ['#ffffff', '#e5a956', '#69ccd0', '#ac8468', '#559b9e']
    fields = ['requested_abs_deg_s', 'before_request_abs_deg_s', 'after_request_abs_deg_s',
              'before_capped_abs_deg_s', 'after_capped_abs_deg_s']
    labels = ['Policy requested', 'Before request', 'Integrated request', 'Before pulses', 'Integrated pulses']
    for j, (group, s) in enumerate(stats.items()):
        x, y = 30 + (j % 2)*670, 112 + (j//2)*327
        draw.text((x, y), f'{group}: yaw | n={s["decisions"]}, ready={s["ready"]}', font=font(22), fill='white')
        top = max(s['yaw'][f] for f in fields) or 1.
        for k, (field, label, color) in enumerate(zip(fields, labels, colors)):
            yy = y+42+k*36
            value = s['yaw'][field]
            draw.text((x, yy), label, font=font(17), fill='#c9d5e2')
            draw.rectangle((x+177, yy+3, x+177+max(1, 270*value/top), yy+22), fill=color)
            draw.text((x+455, yy), f'{value:.3f} deg/s', font=font(17), fill=color)
        count = s['yaw']['after_cap_decisions']
        draw.text((x, y+231), f'Integrated yaw capped: {count}/{s["ready"]} ready decisions', font=font(18), fill='#a6b7c9')
    draw.text((30, 778), 'Absolute rates over all decision intervals; pulses honor historical ready status and unchanged caps/floors.', font=font(18), fill='#a6b7c9')
    draw.text((30, 803), 'Counterfactual pulse scheduling may incur further live freshness drops. Command estimates are not measured rotation.', font=font(17), fill='#a6b7c9')
    im.save(OUT/'rates.png')


def main():
    a = replay(ROOT/'data/calibration/compat-check-20260929/learned-01-a')
    sitting = [replay(p) for p in sorted((ROOT/'data/calibration/rl-sitting-20260930-07').glob('ep-*')) if p.is_dir()]
    groups = {'Learned-01 A': [a], 'Sitting-07 BC': [r for r in sitting if r['source'].endswith('-bc')],
              'Sitting-07 RL': [r for r in sitting if r['source'].endswith('-rl')], 'Sitting-07 all': sitting}
    stats = {name: summarize(runs) for name, runs in groups.items()}
    (OUT/'results.json').write_text(json.dumps(stats, indent=2)+'\n')
    with (OUT/'replay.jsonl').open('w') as f:
        for run in [a, *sitting]:
            for r in run['records']:
                f.write(json.dumps({'source': run['source'], **r})+'\n')
    plot(stats)
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
