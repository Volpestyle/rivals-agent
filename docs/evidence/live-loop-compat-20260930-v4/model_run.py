"""Deterministic sensitivity model, not a claim of unmeasured pitch gain."""
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_camera_compat import setup
from agent import camera_compat as current
from agent.state import Detection, ENEMY

PACKET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('agent.compat_v3_before', PACKET / 'before/camera_compat.py')
prior = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prior
spec.loader.exec_module(prior)


def run(module, scale=1.):
    check, io = setup()
    io.positions = [[609.5,196.75],[920.,196.75]]
    def advance(dt):
        active = max(0., min(io.t + dt, io.until) - io.t)
        rx, ry = io.pad.get('rx',0.), io.pad.get('ry',0.)
        gain = {0.:0., .1:405., .2:1215., .3:2025.}.get(abs(rx),0.)
        for xy in io.positions:
            xy[0] -= math.copysign(gain,rx) * active if rx else 0
            xy[1] += ry * 1000 * scale * active
        io.t += dt
    io.advance = advance
    def finder(frame):
        io.advance(.025)
        return [Detection(ENEMY,(x-38,y-38,x+38,y+38),1.) for x,y in frame]
    check.percept.wide = finder
    class Save:
        def __call__(self,name,frame):
            io.advance(.1 if name.startswith('acquire') else .15)
        def alias(self,*args):
            io.advance(.0002)
    check = module.CompatibilityCheck(io,check.percept,check.guard,check.admission,
                                      60.,sleep=io.advance,save=Save())
    result = check.run()
    return {'result':result['result'], 'completed_sides':result['completed_sides'],
            'pulses':result['pulses'], 'input_s':result['reserved_input_s'],
            'elapsed_s':io.t, 'events':result['events']}


if __name__ == '__main__':
    rows = {'baseline_v3':run(prior), 'v4_pitch_gain_half':run(current,.5),
            'v4_pitch_gain_nominal':run(current), 'v4_pitch_gain_double':run(current,2)}
    (PACKET / 'modeled-comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
    print({name:{k:v for k,v in row.items() if k!='events'} for name,row in rows.items()})
