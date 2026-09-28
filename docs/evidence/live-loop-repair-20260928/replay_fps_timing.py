"""Replay recorded call durations with a fake worker; never inference/capture."""
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts import measure_inference_fps as current

out = Path(sys.argv[1])
events = ROOT/'data/calibration/alt-cam-20260928/inference-fps-aba/events.jsonl'
native = [json.loads(line) for line in events.read_text().splitlines()]
captures = [row for row in native if row['kind']=='startup_capture']
assert len(captures) == 6
source = subprocess.check_output(['git','show','1455a92:scripts/measure_inference_fps.py'])
assert hashlib.sha256(source).hexdigest() == '8a97a7604db9ede4cdc12835e879648cf4a11ef93f686e17031385e34b4f0b36'
baseline = importlib.util.module_from_spec(importlib.util.spec_from_loader('fps_before_repair',loader=None))
baseline.__file__ = str(ROOT/'scripts/measure_inference_fps.py')
exec(compile(source,baseline.__file__,'exec'),baseline.__dict__)
fake = runpy.run_path(str(ROOT/'tests/test_measure_inference_fps.py'))

results={}
for name,module in [('before',baseline),('after',current)]:
    clock,journal,capture,worker,guards = fake['startup_fixture'](cold=.7749)
    def row():
        return captures[capture.calls-1] if 0 < capture.calls <= len(captures) else {
            'capture_duration_s':.001,'range_duration_s':.001,'idle_duration_s':.001}
    def grab():
        capture.calls += 1
        clock.sleep(row()['capture_duration_s'])
        return fake['Frame'](capture.calls)
    capture.grab=grab
    def range_ok(frame):
        clock.sleep(row()['range_duration_s'])
        return True
    def idle(frame):
        clock.sleep(row()['idle_duration_s'])
        return False
    guards.update(in_range=range_ok,idle_warning=idle)
    result=module.warm_start(capture,worker,journal,**guards)
    results[name]={'result':result,'submissions':worker.submitted,'events':journal.events}
assert results['before']['result']['stop_reason']=='stale_proof'
assert results['after']['result']['stop_reason']=='ready'
assert results['after']['result']['discarded_stale_frames']==2
assert all(identifier not in (1,6) for _,identifier in results['after']['submissions'])
packet={'scope':'Recorded first-six capture/proof durations; synthetic fresh continuation and worker timings. No model, GPU, desktop or game FPS.',
        'source_events_sha256':hashlib.sha256(events.read_bytes()).hexdigest(),
        'before_source_sha256':hashlib.sha256(source).hexdigest(),
        'after_source_sha256':hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest(),
        'results':results}
with out.open('x') as stream:
    json.dump(packet,stream,indent=2,allow_nan=False)
print({k:v['result']['stop_reason'] for k,v in results.items()})
