"""Independent CPU-only arithmetic and retained raw-action comparison."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np

root = Path(__file__).parent
r = json.loads((root/'results/result.json').read_text())
repeat = json.loads((root/'results/result.repeatability.json').read_text())
parity = json.loads((root/'results/result.parity.json').read_text())
completion = json.loads((root/'results/completion.json').read_text())
assert repeat == r['repeatability'] and parity == r['parity']
for filename,key in [('PROTOCOL.md','protocol_sha256'),('run_probe.py','script_sha256'),('cache_wrapper.py','wrapper_sha256')]:
    assert hashlib.sha256((root/filename).read_bytes()).hexdigest() == repeat[key]
assert repeat['max_abs'] == 0 and repeat['absolute_tolerance'] == 1e-6
assert parity['max_abs'] == 0 and parity['pass_'] and parity['aba_cache_reset']
assert all(row['calls'] == 16 and row['computes'] == 1 for row in parity['rows'])
with np.load(root/'results/result.raw-actions.npz', allow_pickle=False) as raw:
    assert len(raw.files) == 18
    for fixture in range(3):
        for seed in range(3):
            a,b = (raw[f'{kind}_{fixture}_{seed}'] for kind in ('baseline','cached'))
            assert a.shape == b.shape == (1,18,25)
            assert np.isfinite(a).all() and np.array_equal(a,b)
            assert np.array_equal(a[:,:,:21] > .5,b[:,:,:21] > .5)
            assert np.array_equal(np.sign(a[:,:,21:]*2-1),np.sign(b[:,:,21:]*2-1))
for path in ('baseline','cached'):
    a = r[path]
    assert len(a['ms']) == a['calls'] == 30
    assert math.isclose(np.percentile(a['ms'],50),a['p50_ms'])
    assert math.isclose(np.percentile(a['ms'],95),a['p95_ms'])
assert r['cached']['p95_ms'] > 150
assert r['verdict'] == 'PARK: cached p95 above 150 ms'
assert r['elapsed_s'] < 300
t = completion['phase_written_ns']
assert t['result.repeatability.json'] < t['result.parity.json'] < t['result.json']
print('PASS: source pins, fixed tolerance before parity/timing, 9 raw-output pairs, decoded decisions, quantiles, cutoff and time budget')
