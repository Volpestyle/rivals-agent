import copy
import importlib.util
import json
from pathlib import Path

import pytest
import cm3_accounting as accounting
import make_receipt
from policy.range_bc import cm3_run as run

spec = importlib.util.spec_from_file_location('runner_fixtures', Path.cwd()/'tests/test_range_bc_cm3_run.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
packet = fixtures.packet


@pytest.mark.parametrize('cap,accepted', [(62742, True), (69120, True), (69121, False)])
def test_real_runner_receipt_cap(packet, cap, accepted):
    _, make, _ = packet
    ref, _ = make(budget={'cap_seconds': cap, 'spent_seconds': 0, 'stage_seconds': 100,
                          'approved_by': 'herdr-lead'})
    if accepted:
        run.authenticate('inputs', ref, runtime=False)
    else:
        with pytest.raises(ValueError, match='budget exhausted'):
            run.authenticate('inputs', ref, runtime=False)


@pytest.mark.parametrize('seconds,dollars,accepted', [(69120, 60, True), (69121, 60, False), (69120, 60.01, False)])
def test_writer_cap_boundary(seconds, dollars, accepted):
    state = {'allocation': {'approved_by': 'herdr-lead', 'cap_seconds': seconds,
        'spent_seconds': 0, 'stage_seconds': 1, 'cloud_instance': 'cuda:SYNTHETIC',
        'hourly_usd': 1, 'cloud_cap_usd': dollars}}
    writer = make_receipt.Writer({'amendment': 3, 'device': 'cuda',
        'hardware': {'class': 'cuda:SYNTHETIC'}}, state, {'approvals': []})
    if accepted:
        assert writer.budget('inputs', {})['cap_seconds'] == seconds
    else:
        with pytest.raises(ValueError):
            writer.budget('inputs', {})


@pytest.mark.parametrize('seconds,dollars,accepted', [(69120, 60, True), (69121, 60, False), (69120, 60.000001, False)])
def test_real_ledger_aggregate_cap(monkeypatch, seconds, dollars, accepted):
    row = {'attempt_id': 'synthetic', 'reservation': {'path': 'r', 'sha256': 'a'*64}}
    docs = {'ledger': {'format': 'cm3-measured-accounting-v1', 'approved_by': 'herdr-lead',
        'campaign_id': 'r3-20260926-l40s', 'basis_seconds': accounting.BASIS_SECONDS,
        'basis_usd': float(accounting.BASIS_USD), 'inventory': {'path': 'inventory'},
        'settlements': [row]}, 'inventory': {'format': 'cm3-reservation-inventory-v1',
        'campaign_id': 'r3-20260926-l40s', 'reservations': {'synthetic': row['reservation']}}}
    monkeypatch.setattr(accounting, 'settle', lambda *args: dict(attempt_id='synthetic',
        seconds=seconds-accounting.BASIS_SECONDS,
        usd=float(accounting.Decimal(str(dollars))-accounting.BASIS_USD), owner_results=[]))
    if accepted:
        result = accounting.ledger({'path': 'ledger'}, lambda ref: docs[ref['path']])
        assert result['spent_seconds'] == seconds and result['spent_usd'] == dollars
    else:
        with pytest.raises(ValueError, match='campaign cap exhausted'):
            accounting.ledger({'path': 'ledger'}, lambda ref: docs[ref['path']])


@pytest.mark.parametrize('field,value', [('cap_seconds', 69121), ('cloud_cap_usd', 60.01),
    ('hold_seconds', 60000), ('hold_usd', 60)])
def test_allocation_caps_still_refuse(monkeypatch, field, value):
    monkeypatch.setattr(accounting, 'ledger', lambda *a, **k: {'spent_seconds': 10000, 'spent_usd': 10})
    budget = dict(accounting={}, spent_seconds=10000, spent_usd=10, cap_seconds=69120,
        cloud_cap_usd=60, stage_seconds=1, hold_seconds=10, hold_usd=1,
        hourly_usd=2.584224, stage_overhead_usd=0)
    budget[field] = value
    with pytest.raises(ValueError):
        accounting.allocation(budget, lambda _: {'format': 'cm3-measured-accounting-v2'})


@pytest.mark.parametrize('variant', ['old', 'new', 'seconds_over', 'dollars_over'])
def test_budget03_exact_forecast_and_over_cap_stop(monkeypatch, variant):
    fixture = json.loads((Path(__file__).with_name('budget03-numbers.json')).read_bytes())
    state = {'allocation': fixture['allocation'], 'projection': fixture['projection'], 'stage_results': {}}
    allocation = state['allocation']
    if variant != 'old':
        allocation.update(cap_seconds=69120, cloud_cap_usd=60)
    if variant == 'seconds_over':
        state['projection']['startup_shutdown_seconds'] += 6000
    if variant == 'dollars_over':
        state['projection']['non_compute_usd'] += 10
    # Isolate unchanged real forecast arithmetic from historical approvals/payloads.
    # Cap enforcement itself runs through real Writer.budget/accounting.allocation.
    monkeypatch.setattr(accounting, 'ledger', lambda *a, **k: {
        'spent_seconds': allocation['spent_seconds'], 'spent_usd': allocation['spent_usd']})
    writer = make_receipt.Writer({'amendment': 3, 'device': 'cuda',
        'hardware': {'class': allocation['cloud_instance']}}, state, {'approvals': []})
    monkeypatch.setattr(writer, 'chain', lambda _: ({}, {'smoke': {
        'artifacts': {'details': 'smoke'}, 'elapsed_total_seconds': allocation['spent_seconds']}}))
    state['stage_results']['smoke'] = 'synthetic-predecessor'
    monkeypatch.setattr(writer, 'doc', lambda ref: fixture['smoke'] if ref == 'smoke'
                        else {'format': 'cm3-measured-accounting-v2'})
    result = writer.forecast()
    assert result['status'] == ('ELIGIBLE' if variant == 'new' else 'STOP')
    if variant in ('old', 'new'):
        # Python 3.11/3.12 summation differs by about 7e-12 seconds here.
        assert result['forecast_total_seconds'] == pytest.approx(
            fixture['expected']['forecast_total_seconds'], rel=0, abs=1e-8)
        assert result['projected_modal_usd'] == fixture['expected']['projected_modal_usd']
