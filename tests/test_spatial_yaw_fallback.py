"""Offline fallback boundary tests; no corpus, Modal import or cloud call."""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / 'docs/evidence/nitrogen-spatial-yaw-20260927/fallback-launch'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


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
