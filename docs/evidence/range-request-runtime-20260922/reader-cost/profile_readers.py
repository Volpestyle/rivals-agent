"""Bounded CPU profile of unchanged readers on three saved runtime images."""
import hashlib
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import cv2
from perception import hud

RUN = ROOT / 'data/l1/range-request-diagnostic-20260922-1'
NAMES = ('000066.jpg', '000069.jpg', '000071.jpg')
rows = [json.loads(line) for line in (RUN / 'frames.jsonl').read_text().splitlines()]
selected = {r['file']: r for r in rows if r.get('file') in NAMES}
original = {n: getattr(hud, n) for n in ('read_hp', 'read_bar_fill', 'read_ult', 'read_cooldown',
    'read_damage_segment', 'read_webs', '_read_ability')}
times = defaultdict(list)


def wrapped(name, function):
    def call(*args, **kwargs):
        start = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            times[name].append((time.perf_counter() - start) * 1000)
    return call


for name, function in original.items():
    setattr(hud, name, wrapped(name, function))
result = []
for name in NAMES:
    path = RUN / name
    frame = cv2.imread(str(path))
    assert frame.shape == (1440, 2560, 3)
    boxes = selected[name]['dets']
    # Warm templates once; all following calls reuse these exact pixels/boxes.
    hud.read(frame)
    [hud.read_tagged(frame, box) for box in boxes]
    times.clear()
    totals, tags = [], []
    for _ in range(8):
        start = time.perf_counter(); value = hud.read(frame)
        totals.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter(); tag_values = [hud.read_tagged(frame, box) for box in boxes]
        tags.append((time.perf_counter() - start) * 1000)
    result.append({'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'observation_t': selected[name]['send_result']['observation_t'], 'boxes_from_saved_reflex_row': boxes,
        'hud_total_ms': totals, 'tag_total_ms': tags, 'hud_median_ms': statistics.median(totals),
        'tag_median_ms': statistics.median(tags), 'subreader_total_ms_per_call': dict(times),
        'decoded_jpeg_hud': {'hp': value.hp, 'max_hp': value.max_hp, 'webs': value.webs,
                            'abilities': value.abilities, 'cooldowns': value.cooldowns},
        'decoded_jpeg_tags': tag_values})
for name, function in original.items():
    setattr(hud, name, function)
assert not any(m in sys.modules for m in ('torch', 'agent.controller', 'agent.loop', 'dxcam', 'vgamepad'))
report = {'scope': 'saved_JPEG_CPU_reader_cost_not_original_live_stage_measurement',
    'cv2': cv2.__version__, 'opencv_threads': cv2.getNumThreads(), 'iterations_per_frame': 8,
    'hud_source_sha256': hashlib.sha256((ROOT / 'perception/hud.py').read_bytes()).hexdigest(),
    'results': result, 'limits': ['JPEG pixels and reflex-row boxes differ from original decision inputs.',
        'No model, capture, input or GPU work; no inferred live worker/queue/dispatch timing.',
        'Offline sequential reader costs do not reproduce concurrent live contention.']}
out = Path(__file__).with_name('report.json')
with out.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps([{'file': r['file'], 'hud_median_ms': r['hud_median_ms'], 'tag_median_ms': r['tag_median_ms']} for r in result]))
