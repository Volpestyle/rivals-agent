"""CPU-only scheduling fixtures: compile the stdlib guard functions, never import torch."""
import argparse
import ast
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from types import SimpleNamespace, ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'rl/world_model/tokenizer.py'
DRIVER = ROOT / 'rl/world_model/pc_tokenizer.sh'


@pytest.fixture
def guard():
    tree = ast.parse(SOURCE.read_text())
    names = {'competing_process', 'busy_reason', 'checkpoint_and_yield', 'main'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = dict(Path=Path, re=re, shlex=shlex, json=json, subprocess=subprocess,
              os=SimpleNamespace(name='nt'), MANUAL_HOLD=None, PS_GPU_JOBS='fixture-query',
              argparse=argparse, sys=sys, below_normal=lambda: None,
              torch=SimpleNamespace(set_num_threads=lambda n: None))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


@pytest.mark.parametrize('cmd', [
    r'"D:\rivals-policy\.venv\Scripts\python.exe" D:\rivals-policy\intake\20260930T193113-731Z-163680-1\run-local-features.py',
    r'python.exe D:/rivals-policy/intake/20260930T193113-731Z-163680-1/run-local-features.py --worker',
    r'python.exe "D:/rivals-policy/runs/still-start-193113-s0/encode_val.py"',
    r'python.exe -u D:/rivals-policy/runs/still-start-193113-s0/local_checks.py',
    r'"C:\Program Files\Python\python.exe" -X utf8 -m policy.bc2.features --out x',
    'python.exe -m policy.idm.label', 'python.exe -m policy.bc2',
    'python.exe -m agent.loop', 'python.exe -m agent.server', 'python.exe -m agent.learned_runner',
])
def test_actual_launch_forms_and_module_controls(guard, cmd):
    assert guard['competing_process']('python.exe', cmd)


@pytest.mark.parametrize('name', ['obs64.exe', 'OBS32.EXE', 'Marvel-Win64-Shipping.exe'])
def test_recording_and_game_names(guard, name):
    assert guard['competing_process'](name, None)


@pytest.mark.parametrize('cmd', [
    'python.exe -c "print(\'-m policy.bc2\')"',
    'python.exe report.py --text "-m agent.loop"',
    'python.exe -m policy.bc2_notes', 'python.exe -m http.server',
    'python.exe D:/unrelated/encode_val.py',
    'python.exe D:/rivals-policy/runs/a/report.py --input D:/rivals-policy/runs/a/local_checks.py',
    'python.exe D:/rivals-policy-backup/runs/a/encode_val.py',
    'python.exe D:/rivals-policy/runs/a/local_checks.py.bak',
    'python.exe D:/other/run-local-features.py',
    'python.exe -m rl.world_model.tokenizer --out D:/rivals-agent-local/rl-wm/runs/tok-pc',
    'python.exe unrelated.py --note obs64.exe', None,
])
def test_unrelated_python_and_argument_mentions_do_not_block(guard, cmd):
    assert guard['competing_process']('python.exe', cmd) is None


def test_hold_is_persistent_and_precedes_process_query(guard, tmp_path, monkeypatch):
    hold = tmp_path / 'manual.hold'
    hold.write_text('root reservation')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('hold must short circuit'))
    assert 'manual hold' in guard['busy_reason'](hold)
    assert 'manual hold' in guard['busy_reason'](hold)
    assert hold.read_text() == 'root reservation'


@pytest.mark.parametrize('payload', [
    {'Name': 'obs64.exe', 'CommandLine': None},
    [{'Name': 'python.exe', 'CommandLine': 'python.exe -m policy.idm.label'}],
    [{'Name': 'python.exe', 'CommandLine': 'python.exe D:/rivals-policy/runs/still-start-193113-s0/encode_val.py'}],
])
def test_busy_reason_consumes_process_snapshot(guard, monkeypatch, payload):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(payload)))
    assert guard['busy_reason'](None)


def test_idle_snapshot_and_query_failure(guard, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='[]'))
    assert guard['busy_reason'](None) is None
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='invalid json'))
    assert guard['busy_reason'](None) == 'GPU ownership query failed'


def test_checkpoint_precedes_yield_and_retains_completed_step(guard, tmp_path):
    ckpt = tmp_path / 'checkpoint.json'
    events = []
    def save():
        ckpt.write_text(json.dumps({'step': 8751, 'optimizer': 'fixture'}))
        events.append('saved')
    def log(reason):
        assert json.loads(ckpt.read_text())['step'] == 8751
        events.append(reason)
    with pytest.raises(SystemExit) as exc:
        guard['checkpoint_and_yield']('manual hold', save, log)
    assert exc.value.code == 3 and events == ['saved', 'manual hold']
    guard['checkpoint_and_yield'](None, lambda: pytest.fail('no save'), lambda _: pytest.fail('no yield'))


def test_failed_checkpoint_never_reports_successful_yield(guard):
    def fail():
        raise OSError('disk failure')
    with pytest.raises(OSError):
        guard['checkpoint_and_yield']('OBS running', fail, lambda _: pytest.fail('no success log'))


def test_trainer_hold_exits_before_device_or_data_and_preserves_checkpoint(guard, tmp_path, monkeypatch):
    import rl.world_model
    v2 = ModuleType('rl.world_model.v2')
    logs = []
    v2.log = lambda *a, **kw: logs.append(kw)
    monkeypatch.setitem(sys.modules, 'rl.world_model.v2', v2)
    monkeypatch.setattr(rl.world_model, 'v2', v2, raising=False)
    hold = tmp_path / 'manual.hold'
    hold.write_text('root reservation')
    ckpt = tmp_path / 'ckpt.pt'
    ckpt.write_bytes(b'unchanged completed checkpoint')
    with pytest.raises(SystemExit) as exc:
        guard['main'](['--out', str(tmp_path), '--yield-check', '--hold-file', str(hold)])
    assert exc.value.code == 3
    assert ckpt.read_bytes() == b'unchanged completed checkpoint'
    assert logs[-1]['phase'] == 'before_device_init'


def test_driver_hold_short_circuits_python_and_gpu_queries(tmp_path):
    bash = shutil.which('bash')
    if sys.platform == 'win32':
        bash = 'C:/Program Files/Git/bin/bash.exe'
    if not bash or not Path(bash).exists():
        pytest.skip('bash unavailable')
    hold = tmp_path / 'manual.hold'
    hold.write_text('root reservation')
    script = DRIVER.read_text()
    busy = script[script.index('busy() {'):script.index('\nstep_now()')]
    result = subprocess.run([bash, '-c', 'HOLD="$1"; PY=/must-not-run; ' + busy + '\nbusy',
                             'fixture', hold.as_posix()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.strip() == 'manual hold: ' + hold.as_posix()
    assert not result.stderr and hold.exists()
