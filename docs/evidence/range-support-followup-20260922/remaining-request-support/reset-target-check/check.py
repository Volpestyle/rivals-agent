"""Exactly two five-frame saved-image reset checks; no model, decoder, or input."""
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
SURVEY = ROOT / 'data/human/skill-event-candidates/032454-support-v2/continuous-survey.json'
OLD = ROOT / 'data/human/skill-event-candidates/20260922T032454-642Z-24328-1/measurement-receipt.json'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


paths = ['agent/loop.py', 'agent/brain.py', 'agent/tracker.py', 'agent/state.py',
         'perception/hud.py', 'perception/outline.py', 'scripts/record.py']
pins = {p: sha(ROOT / p) for p in paths}
assert pins['agent/brain.py'] == '0deaafb77cae4fa4a15fc8c8abe6d49c09821de7a1ab5810b096788117b30c00'
assert pins['agent/tracker.py'] == '56fa3012391b22a0c4a3dbe3f5414f275faba4e038bfebdbe6b8f579bc72c892'
assert pins['perception/outline.py'] == '369994b22c895c0248b8089a1ca37c9a30f3e5dd9cb653ad2cc3e59bfb17dd55'
assert pins['perception/hud.py'] == 'b5c15cfe8e8d3b11003cd74d2d69c76f34d37591894124f5dfd70e5b32249acc'
import cv2
from agent import brain
from agent.loop import default_perception, aim_window
from agent.state import State, ENEMY
from agent.tracker import Tracker
from perception import hud

cv2.setNumThreads(4)
percept = default_perception()
layout = replace(hud.MK, slot_cx={'swing': .795, 'uppercut': .8348, 'get_over_here': .8723})
assert json.loads(json.dumps(asdict(layout))) == json.loads(OLD.read_text())['layout']
survey = {r['grid_n']: r for r in json.loads(SURVEY.read_text())}
results = []
for n in (154, 211):
    tracker, memory, history = Tracker(), brain.Memory(), []
    for k in range(n - 4, n + 1):
        previous = survey[k]
        frame = previous['frame']
        path = ROOT / frame['image']
        assert sha(path) == frame['image_sha256']
        pixels = cv2.imread(str(path))
        assert pixels.shape[:2] == (1440, 2560)
        t = frame['composition_t']
        assert t == previous['state']['t'] == previous['available_t']
        assert (frame['composition_ns'] - 115370505348149) / 1e9 == t
        assert t <= k / 10 and abs(t - k / 10) <= .025
        size = percept.size(pixels)
        aim = tracker.update(percept.aim(pixels), t, size, clip=aim_window(size))
        dets = aim or tracker.update(percept.wide(pixels), t, size)
        dets = [replace(d, tagged=percept.tag(pixels, d.bbox)) if d.cls == ENEMY else d for d in dets]
        state = State(t=t, frame=size, detections=dets, coasting=tuple(tracker.coasting),
                      **hud.read(pixels, layout).state_kwargs())
        early, target = brain.gate(state, memory)
        history.append({'grid_index': k, 'grid_tick_t': k / 10, 'frame': frame,
                        'state': state.to_dict(), 'available_t': t,
                        'selected_target': asdict(target) if target is not None else None,
                        'gate': type(early).__name__ if early is not None else None,
                        'in_range': bool(percept.in_range(pixels))})
    results.append({'grid_index': n, 'anchor_t': n / 10, 'history': history,
                    'final_selected_target': history[-1]['selected_target'],
                    'prior_continuous_selected_target': survey[n]['target'],
                    'label': None, 'status': 'target_check_only_not_label_or_admission'})
assert pins == {p: sha(ROOT / p) for p in paths}, 'Source changed during bounded check'
report = {'status': 'two_saved_reset_windows_measured', 'bins': [154, 211],
          'actual_frames_processed': 10, 'cv2_threads': 4, 'code_sha256': pins,
          'survey_sha256': sha(SURVEY), 'source_layout': asdict(layout),
          'method': 'Fresh Tracker/Memory per window, actual saved composition times, default aim then wide fallback, mapped source HUD, brain.gate only. No policy/model call, controller, pad, decode or future frame.',
          'hud_note': 'Current accepted HUD bytes include landed mask/countdown optimizations; original source-owned mapped MK geometry retained. No old feature/source identity rewritten.',
          'results': results}
(OUT / 'measurements.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
for r in results:
    print(r['grid_index'], 'earlier_targets', [h['selected_target'] for h in r['history']],
          'final', r['final_selected_target'])
