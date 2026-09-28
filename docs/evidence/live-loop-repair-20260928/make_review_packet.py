"""Static exact-byte review inputs, never an owner-issued review receipt."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
driver=ROOT/'scripts/measure_camera_turns.py'
base=subprocess.check_output(['git','show','HEAD:scripts/measure_camera_turns.py'])
assert hashlib.sha256(base).hexdigest()=='fbc442d602bab060ad541c22d00520cc66dc101d5bb594e6c3c924d701c2ecde'
new=driver.read_bytes()
old_tree,new_tree=ast.parse(base),ast.parse(new)
pins=next(ast.literal_eval(n.value) for n in new_tree.body if isinstance(n,ast.Assign)
          and any(isinstance(t,ast.Name) and t.id=='FILES' for t in n.targets))
sha=lambda path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def emit(name,data):
    with (OUT/name).open('x',encoding='utf8',newline='\n') as stream:
        json.dump(data,stream,indent=2,allow_nan=False)
        stream.write('\n')
emit('review-inputs.json',{'format':'camera-turns-review-inputs-v1','acceptance':'NOT_A_REVIEW_RECEIPT',
    'base_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'files':{p:sha(p) for p in pins},
    'additional_test_and_fps_files':{p:sha(p) for p in ('tests/test_camera_ready_pose.py',
        'scripts/measure_inference_fps.py','tests/test_measure_inference_fps.py')}})
def functions(tree):
    return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
old_f,new_f=functions(old_tree),functions(new_tree)
def sends(tree):
    return sorted(ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call)
        and ((isinstance(n.func,ast.Attribute) and n.func.attr in ('send_guarded','send','release','close'))
             or (isinstance(n.func,ast.Name) and n.func.id in ('Live','collect_segment'))))
assert old_f['collect_segment']==new_f['collect_segment']
assert old_f['measure_pulse']==new_f['measure_pulse']
assert sends(old_tree)==sends(new_tree)
emit('input-ast.json',{'base_driver_sha256':hashlib.sha256(base).hexdigest(),
    'candidate_driver_sha256':hashlib.sha256(new).hexdigest(),
    'collect_segment_ast_identical':True,'measure_pulse_ast_identical':True,
    'input_call_expressions_identical':True,'calls':sends(new_tree),
    'limit':'Call expressions and two input functions unchanged; pose authorization/recovery and deferred refusal handling changed and require independent review.'})
with (OUT/'driver-delta.patch').open('x',encoding='utf8',newline='\n') as stream:
    stream.writelines(difflib.unified_diff(base.decode().splitlines(True),new.decode().splitlines(True),
                                         fromfile='a/scripts/measure_camera_turns.py',tofile='b/scripts/measure_camera_turns.py'))
print('12 runtime/driver-test pins and independent review inputs written')
