"""Offline fallback boundary tests; no corpus, Modal import or cloud call."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'docs/evidence/nitrogen-nohistory-confirm-20260927/launch'
NEW = ROOT / 'docs/evidence/nitrogen-spatial-yaw-20260927/fallback-launch'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_guard_functions_and_transport_unchanged():
    def functions(path):
        return [ast.dump(x, include_attributes=False) for x in ast.parse(path.read_text()).body
                if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    assert functions(OLD / 'encoder_budget.py') == functions(NEW / 'encoder_budget.py')
    for name in ('encoder_lifecycle.py', 'appcreate_gate.py', 'lifecycle.py', 'explore_mounts.py'):
        assert (OLD / name).read_text() == (NEW / name).read_text()


def test_cap_and_positive_runtime(tmp_path, monkeypatch):
    # Execute only the guard source with a synthetic sibling config, no imports of Modal.
    target = tmp_path / 'encoder_budget.py'
    target.write_text((NEW / 'encoder_budget.py').read_text())
    (tmp_path / 'run-config.json').write_text(json.dumps({
        'arm': 'nitrogen', 'app_name': 'synthetic-yaw', 'input_volume': 'synthetic-input'}))
    guard = module('yaw_fallback_test_budget', target)
    r = guard.reservation(wall=1000, mono=1000)
    assert r['reserved_usd'] <= 2.50
    assert r['function_timeout_seconds'] > 1800
    assert 6 * guard.CAP == 15
    assert guard.expired(r, wall=r['stop_at_unix'], mono=1000)


@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setitem(sys.modules, 'explore_mounts', module('fallback_test_mounts', NEW / 'explore_mounts.py'))
    return module('fallback_test_worker', NEW / 'encoder_worker.py')


def test_completed_fit_resumes_evaluation_without_refit(tmp_path, worker):
    from cloud.modal_guard.stages import run
    identity = {'attempt_id': 'synthetic-yaw', 'code_sha256': 'a' * 64,
                'inputs_sha256': 'b' * 64, 'recipe_sha256': 'c' * 64,
                'output_volume_id': 'vo-test', 'deadline_unix': 9999999999}
    calls = []
    def fit(root, **kwargs):
        calls.append('fit')
        (root / 'epoch-26.pt').write_bytes(b'finished synthetic epoch26')
        (root / 'fit.json').write_text('{}')
        return 0
    def evaluate(root, **kwargs):
        calls.append('evaluate')
        (root / 'evaluation.json').write_text('{}')
        return 0
    volume = SimpleNamespace(commit=lambda: None, reload=lambda: None)
    run(tmp_path / 'fit', 'fit', identity, ['epoch-26.pt', 'fit.json'],
        lambda root: fit(root), commit=volume.commit, reload=volume.reload)
    callbacks = SimpleNamespace(fit=fit, evaluate=evaluate)
    worker.execute(tmp_path, {}, identity, volume, callbacks, run)
    assert calls == ['fit', 'evaluate']
    worker.execute(tmp_path, {}, identity, volume, callbacks, run)
    assert calls == ['fit', 'evaluate']  # complete report replay also skips computation
    (tmp_path / 'fit/epoch-26.pt').write_bytes(b'corrupt')
    with pytest.raises(RuntimeError, match='hash mismatch'):
        worker.execute(tmp_path, {}, identity, volume, callbacks, run)


def test_partial_fit_never_recomputed(tmp_path, worker):
    from cloud.modal_guard.stages import run
    identity = {'attempt_id': 'synthetic-yaw', 'code_sha256': 'a' * 64,
                'inputs_sha256': 'b' * 64, 'recipe_sha256': 'c' * 64,
                'output_volume_id': 'vo-test', 'deadline_unix': 9999999999}
    (tmp_path / 'fit').mkdir()
    (tmp_path / 'fit/epoch-26.pt').write_bytes(b'incomplete without receipt')
    def no_compute(*args, **kwargs):
        pytest.fail('partial fit was recomputed')
    with pytest.raises(RuntimeError, match='partial stage'):
        worker.execute(tmp_path, {}, identity,
                       SimpleNamespace(commit=lambda: None, reload=lambda: None),
                       SimpleNamespace(fit=no_compute, evaluate=no_compute), run)
