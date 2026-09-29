"""Pin an unlanded diagnostics delta, not an approval receipt; no media access."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
BASE = '6e3b7b0622478ab39c4af4263044821245b7c086'
PATHS = ['scripts/measure_camera_turns.py', 'tests/test_measure_camera_turns.py']
EXTERNAL = Path('D:/rivals-diagnostics/live-loop-guard-20260928')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def write(name, data):
    with (OUT/name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.write('\n')


prior = ROOT/'docs/evidence/camera-ready-fractional-20260928/review-v3.json'
receipt = json.loads(prior.read_text())
pins = {p:sha(ROOT/p) for p in receipt['files']}
assert set(p for p in pins if pins[p] != receipt['files'][p]) == set(PATHS)
old = ast.parse(git('show',BASE+':'+PATHS[0]).decode())
new = ast.parse((ROOT/PATHS[0]).read_text())
functions = ['collect_segment','initialize_pad','measure_pulse','attach_after_token','ready_proof','validate','verify_receipt']
for name in functions:
    a = next(n for n in old.body if getattr(n,'name',None)==name)
    b = next(n for n in new.body if getattr(n,'name',None)==name)
    assert ast.dump(a) == ast.dump(b), name
def actuator_calls(tree):
    return sorted(ast.dump(n) for n in ast.walk(tree) if isinstance(n,ast.Call) and (
        isinstance(n.func,ast.Attribute) and n.func.attr in ('send','send_guarded','hold','release','close')
        or isinstance(n.func,ast.Name) and n.func.id == 'Live'))
assert actuator_calls(old) == actuator_calls(new)
patch = OUT/'delta.diff'
assert not patch.exists()
git('diff','--binary','--no-ext-diff','--output='+str(patch),BASE,'--',*PATHS)
external = [EXTERNAL/'diagnose_native.py',EXTERNAL/'diagnose_native_attempt2.py',EXTERNAL/'qualify.py',
    EXTERNAL/'native-279-289/ABORT.json',EXTERNAL/'native-279-289-attempt2/result.json',
    EXTERNAL/'native-279-289-attempt2/frames.json',EXTERNAL/'qualification-02/result.json',
    EXTERNAL/'qualification-02/pytest.txt']
write('review-inputs.json', {'format':'camera-guard-refusal-review-inputs-v1',
    'status':'unreviewed_uncommitted_no_live_use','base_commit':BASE,
    'head_at_packet':git('rev-parse','HEAD').decode().strip(),'files':pins,
    'prior_receipt':{'path':str(prior.relative_to(ROOT)),'sha256':sha(prior)},
    'delta_sha256':sha(patch),'ast_unchanged_functions':functions,'actuator_call_ast_unchanged':True,
    'prime_analyzer_sha256':sha(ROOT/'perception/camera_prime_response.py'),
    'external_evidence':{str(p):sha(p) for p in external},
    'checks':'125 passed, 12 corpus skipped; Ruff pass; 2 native-image retention controls',
    'original_failure_clause':'unknown; failing DXCAM frame not retained'})
write('files.sha256.json',{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()})
print('Pinned exact two-file delta; no staging, commit or owner approval receipt.')
