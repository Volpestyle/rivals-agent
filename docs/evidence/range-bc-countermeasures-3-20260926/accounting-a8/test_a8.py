"""Metadata-only regression of the real, unchanged Writer forecast and hold guard."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / 'accounting-a7' / 'owner'


@pytest.fixture
def modules(monkeypatch):
    # Load exact evidence modules independently of any checkout/runtime imports.
    loaded = {}
    for name, path in (
        ('cm3_timeouts', PREVIOUS / 'cm3_timeouts.py'),
        ('cm3_accounting', PREVIOUS / 'cm3_accounting.py'),
        ('cm3_budget_plan', HERE / 'owner/cm3_budget_plan.py'),
        ('make_receipt', PREVIOUS / 'make_receipt.py'),
    ):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


def measured_writer(modules, monkeypatch):
    fixture = json.loads((HERE / 'budget04-numbers.json').read_bytes())
    allocation = fixture['allocation']
    state = dict(allocation=allocation, projection=fixture['projection'],
                 stage_results={'smoke': 'metadata-only-predecessor'})
    writer = modules['make_receipt'].Writer(
        {'amendment': 3, 'device': 'cuda', 'hardware': {'class': 'cuda:L40S'}},
        state, {'approvals': []})
    # Historical authentication/ledger is outside this arithmetic regression.
    # Real Writer.budget, allocation, forecast and hold guard still execute.
    monkeypatch.setattr(modules['cm3_accounting'], 'ledger', lambda *a, **k: {
        'spent_seconds': allocation['spent_seconds'], 'spent_usd': allocation['spent_usd']})
    monkeypatch.setattr(writer, 'chain', lambda _: ({}, {'smoke': {
        'artifacts': {'details': 'smoke'}, 'elapsed_total_seconds': allocation['spent_seconds']}}))
    monkeypatch.setattr(writer, 'doc', lambda ref: fixture['smoke'] if ref == 'smoke'
                        else {'format': 'cm3-measured-accounting-v2'})
    return writer, fixture


@pytest.mark.parametrize('variant', ['measured', 'seconds_over', 'dollars_over'])
def test_full_forecast_and_caps(modules, monkeypatch, variant):
    writer, fixture = measured_writer(modules, monkeypatch)
    if variant == 'seconds_over':
        writer.state['projection']['startup_shutdown_seconds'] += 5000
    if variant == 'dollars_over':
        writer.state['projection']['non_compute_usd'] += 8
    result = writer.forecast()
    assert result['extraction_hold_seconds'] == 2320
    if variant == 'measured':
        assert result['status'] == 'ELIGIBLE'
        assert result['forecast_total_seconds'] == pytest.approx(64004.017956114025, abs=1e-8, rel=0)
        assert result['projected_modal_usd'] == 52.913912
        assert result['forecast_total_seconds'] < 69120
        assert result['projected_modal_usd'] < 60
        assert result['measured_fit_seconds'] == fixture['expected']['measured_fit_seconds']
        required = 1.25 * (result['extraction_and_rehash_seconds'] + 172) + 300 + 120
        assert 2220 < required < 2320
        assert 2320 - 300 - 120 == 1900
    else:
        assert result['status'] == 'STOP'
        assert ('aggregate compute exceeds cap' if variant == 'seconds_over'
                else 'gross dollar estimate exceeds cap') in result['stop_reasons']


def test_original_hold_refuses_same_forecast(modules, monkeypatch):
    writer, _ = measured_writer(modules, monkeypatch)
    monkeypatch.setattr(modules['cm3_budget_plan'], 'EXTRACTION_HOLD_SECONDS', 2220)
    with pytest.raises(ValueError, match='extraction hold below measured work and allowances'):
        writer.forecast()


def test_only_delta_is_hold_and_copies_match():
    old = (PREVIOUS / 'cm3_budget_plan.py').read_bytes()
    new = (HERE / 'owner/cm3_budget_plan.py').read_bytes()
    assert new == old.replace(b'EXTRACTION_HOLD_SECONDS = 2220',
                              b'EXTRACTION_HOLD_SECONDS = 2320')
    assert new == (HERE / 'fanout/cm3_budget_plan.py').read_bytes()
