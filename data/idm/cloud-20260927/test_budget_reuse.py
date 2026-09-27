"""Bounded offline checks: enforcement is byte-for-byte AST-equivalent to source."""
import ast
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load():
    spec = importlib.util.spec_from_file_location('idm_budget_test', ROOT / 'modal_budget.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unchanged_enforcement():
    assert hashlib.sha256((ROOT / 'base_budget.py').read_bytes()).hexdigest() == (
        'dc540a101ed6070b8d70a78e39ceab9b3100a3b1faa658ab4b2019c0ea32fb34')
    def functions(path):
        return [ast.dump(n) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)]
    assert functions(ROOT / 'base_budget.py') == functions(ROOT / 'modal_budget.py')


def test_four_dollar_bound_and_both_clock_stops():
    b = load()
    v = b.reservation(wall=1000, mono=1000)
    assert v['reserved_usd'] <= 4 and v['arms'] == [1] and v['attempts_per_arm'] == 1
    assert v['stop_seconds'] == 120 and v['startup_seconds'] == 300
    assert not b.expired(v, wall=1001, mono=1001)
    assert b.expired(v, wall=v['stop_at_unix'], mono=1001)
    assert b.expired(v, wall=1001, mono=v['stop_monotonic'])
    assert b.expired(v, wall=float('nan'), mono=1001)
    assert b.spend_bound(v, wall=v['funded_until_unix'], mono=1001) <= 4


def test_exclusive_reservation_cannot_restart(tmp_path):
    b = load()
    b.reserve_once(tmp_path)
    import pytest
    with pytest.raises(FileExistsError):
        b.reserve_once(tmp_path)
