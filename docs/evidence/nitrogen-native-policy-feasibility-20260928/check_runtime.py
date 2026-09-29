"""Recompute receipt arithmetic and the declared native timing example; CPU only."""
import hashlib
import json
import math
from pathlib import Path

root = Path(__file__).parent
r = json.loads((root/'gpu-01/runtime-gpu-01.json').read_text())
s = json.loads((root/'gpu-01/runtime-gpu-01.sampler.json').read_text())
assert r['sampler'] == s['sampler']
assert r['benchmark_sha256'] == hashlib.sha256((root/'benchmark_gpu_release.py').read_bytes()).hexdigest()
assert r['contract_sha256'] == hashlib.sha256((root/'gpu-01/contract-cpu-executed.json').read_bytes()).hexdigest()
assert (r['checkpoint_config']['model_cfg']['action_dim'],
        r['checkpoint_config']['model_cfg']['action_horizon'],
        r['checkpoint_config']['model_cfg']['num_inference_timesteps']) == (25,18,16)
samples = sorted(r['sampler']['ms'])
assert len(samples) == 30 and all(math.isfinite(x) and x > 0 for x in samples)
def quantile(q):
    i = (len(samples)-1)*q
    lo = math.floor(i)
    return samples[lo]+(samples[math.ceil(i)]-samples[lo])*(i-lo)
assert math.isclose(quantile(.5), r['sampler']['p50_ms'])
assert math.isclose(quantile(.95), r['sampler']['p95_ms'])
t = r['synthetic_training']
assert len(t['seconds']) == t['measured_updates'] == 10
assert math.isclose(10/sum(t['seconds']), t['updates_s'])
assert r['trainable_parameters'] == 468440089
assert r['parameters'] == 493631513
assert r['forbidden_imports_absent']
# This is an explicit native 30 Hz interpretation, NOT established pretraining
# cadence or an implemented execution scheduler. Never add shift to sampler age.
shift, hz, horizon = 3, 30, 18
intervals = [(i/hz, (i+1)/hz) for i in range(shift,shift+horizon)]
arrival = quantile(.95)/1000
expired = [i for i,(a,b) in enumerate(intervals) if b <= arrival]
underway = [i for i,(a,b) in enumerate(intervals) if a <= arrival < b]
assert expired == list(range(8)) and underway == [8]
assert intervals[0][0] == .1 and intervals[-1][1] == .7
assert all(x > 250 for x in samples)
assert arrival > .250  # Current observation-age gate refuses the entire chunk.
# One held edge crossing adjacent chunk boundaries is never re-created.
states = [0]*17+[1]*3+[0]*16
edges = [int(v and not (states[i-1] if i else 0)) for i,v in enumerate(states)]
assert sum(edges) == 1 and edges[17] == 1 and edges[18] == 0
print(json.dumps(dict(receipt_checks='PASS', native_timeline_example='PASS',
                     expired_intervals_at_p95=len(expired), ongoing_zero_based_chunk_row=underway[0],
                     all_samples_exceed_250ms=True)))
