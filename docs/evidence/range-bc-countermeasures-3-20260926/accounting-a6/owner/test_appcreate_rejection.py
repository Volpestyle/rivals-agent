import copy
import hashlib
import json
from pathlib import Path

import pytest

import cm3_accounting as a
import make_accounting_bundle as maker


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(maker.encoded(value))
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def doc(ref):
    data = Path(ref['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != ref['sha256']:
        raise ValueError('hash mismatch')
    return json.loads(data)


def values():
    reservation = {'format': 'cm3-task-reservation-v1', 'attempt_id': 'test-H-0',
        'campaign_id': 'r3-20260926-l40s', 'concurrent_slots': 1,
        'reserved_compute_seconds': 1020, 'reserved_usd': .732197,
        'bounds': {'started_at_unix': 100, 'rate_usd_second': .00071784, 'overhead_usd': 0, 'hold': {'startup_seconds': 300}}}
    result = {'format': 'cm3-inputs-wrapper-result-v1', 'attempt_id': 'test-H-0',
        'status': 'INCOMPLETE', 'creation_started': True, 'owner_result': None,
        'reason': 'App create rate limit exceeded. Please wait and retry.',
        'teardown': {'identity': a.IDENTITY, 'status': 'INCOMPLETE_CLEANUP', 'apps': [],
                     'events': [], 'checked_at_unix': 110},
        'spend': {'seconds_through_cleanup': 10, 'estimated_conservative_usd': .0071784}}
    owned = {'format': 'cm3-owned-inventory-v1', 'attempt_id': 'test-H-0',
        'identity': a.IDENTITY, 'app_name': 'rivals-cm3-test-H-0',
        'creation_started': True, 'creation_finished': False, 'apps': [], 'calls': {}}
    evidence = {'format': 'cm3-appcreate-rejection-v2', 'attempt_id': 'test-H-0',
        'identity': a.IDENTITY, 'app_name': owned['app_name'],
        'creation_started': True, 'creation_finished': False, 'creator_terminated': True,
        'rpc_method': 'AppCreate', 'rpc_status': 'RESOURCE_EXHAUSTED', 'rpc_outcome': 'REJECTED',
        'rejected_at_unix': 109, 'creator_terminated_at_unix': 111,
        'request_started_at_unix': 101, 'request_clock_source': 'rpc_started',
        'startup_seconds': 300, 'logical_request_id': 'key-test-H-0',
        'capture_started_at_unix': 402, 'capture_finished_at_unix': 464,
        'inventory_snapshots': [{'status': 'READ_OK', 'complete': True, 'identity': a.IDENTITY,
            'checked_at_unix': clock, 'apps': [], 'owned_containers': []} for clock in (403, 463)]}
    for snapshot in evidence['inventory_snapshots']:
        snapshot['raw_outputs'] = {}
        for key, value in [('identity', a.IDENTITY), ('apps', []), ('containers', [])]:
            text = json.dumps(value)
            snapshot['raw_outputs'][key] = {'stdout': text,
                'sha256': hashlib.sha256(text.encode()).hexdigest(), 'returncode': 0, 'elapsed_seconds': .1}
    return copy.deepcopy([reservation, result, owned, evidence])


def source(root, data=None):
    reservation, result, owned, evidence = data or values()
    rr = write(root, 'reservation.json', reservation)
    re = write(root, 'result.json', result)
    owned['reservation'] = rr
    oi = write(root, 'owned.json', owned)
    evidence.update(reservation_sha256=rr['sha256'], result_sha256=re['sha256'],
                    owned_inventory_sha256=oi['sha256'])
    row = {'attempt_id': 'test-H-0', 'reservation': rr, 'result': re,
           'owned_inventory': oi, 'appcreate_rejection': write(root, 'rejection.json', evidence)}
    inv = write(root, 'inventory.json', {'format': 'cm3-reservation-inventory-v1',
        'campaign_id': 'r3-20260926-l40s', 'reservations': {'test-H-0': rr}})
    ref = write(root, 'ledger.json', {'format': 'cm3-measured-accounting-v1',
        'approved_by': 'herdr-lead', 'campaign_id': 'r3-20260926-l40s',
        'basis_seconds': 12159, 'basis_usd': 6.18374656, 'inventory': inv, 'settlements': [row]})
    return row, ref


def test_full_hold_no_refund_or_scientific_result(tmp_path):
    row, ref = source(tmp_path)
    assert a.settle(row, doc) == {'attempt_id': 'test-H-0', 'seconds': 1020,
        'usd': .732197, 'owner_results': [], 'reservation': row['reservation'],
        'absent_app': {'app_name': 'rivals-cm3-test-H-0', 'logical_request_id': 'key-test-H-0',
                       'identity': a.IDENTITY, 'rpc_outcome': 'REJECTED'}}
    totals = a.ledger(ref, doc)
    assert totals['spent_seconds'] == 13179
    assert totals['spent_usd'] == 6.91594356


def test_portable_bundle_keeps_new_evidence_and_full_charge(tmp_path):
    row, old = source(tmp_path / 'source')
    host = maker.build(old, tmp_path / 'host', tmp_path / 'unused')
    remote = maker.build(old, tmp_path / 'container', tmp_path / 'unused')
    assert host['sha256'] == remote['sha256']
    assert a.ledger(host, doc) == a.ledger(remote, doc)
    entry = doc(host)['settlements'][0]
    assert set(entry) == set(row)
    for key in ('appcreate_rejection', 'owned_inventory'):
        assert a.relative_ref(entry[key]) == entry[key]
    target = Path(remote['path']).parent / entry['appcreate_rejection']['path']
    target.write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'):
        a.ledger(remote, doc)


@pytest.mark.parametrize('group,key,value', [
    (0, 'concurrent_slots', 5), (0, 'reserved_compute_seconds', True),
    (0, 'reserved_compute_seconds', 0), (0, 'reserved_usd', .01),
    (0, 'reserved_usd', float('nan')), (0, 'campaign_id', 'other'),
    (1, 'attempt_id', 'other'), (1, 'creation_started', False),
    (1, 'status', 'PASS'), (1, 'over_hold', True),
    (1, 'spend', {'seconds_through_cleanup': 1021}), (1, 'owner_result', {'path': 'result'}),
    (2, 'creation_finished', True), (2, 'creation_started', False),
    (2, 'apps', ['ap-x']), (2, 'calls', {'H-0': 'fc-x'}),
    (2, 'identity', {}), (2, 'attempt_id', 'other'),
    (3, 'rpc_outcome', 'UNKNOWN'), (3, 'rpc_outcome', 'PENDING'),
    (3, 'rpc_status', 'UNAVAILABLE'), (3, 'rpc_method', 'FunctionCreate'),
    (3, 'app_name', 'other'), (3, 'creator_terminated', False),
    (3, 'creator_terminated_at_unix', 99), (3, 'rejected_at_unix', 175),
    (3, 'inventory_snapshots', []), (3, 'creation_started', 1),
])
def test_guard_refusals(tmp_path, group, key, value):
    data = values()
    data[group][key] = value
    if isinstance(value, float) and value != value:
        with pytest.raises(ValueError):
            source(tmp_path, data)
        return
    row, _ = source(tmp_path, data)
    with pytest.raises((ValueError, KeyError)):
        a.settle(row, doc)


@pytest.mark.parametrize('key,value', [
    ('status', 'READ_FAILED'), ('complete', False), ('identity', {}),
    ('checked_at_unix', 110), ('checked_at_unix', 115),
    ('apps', None), ('apps', [{}]), ('owned_containers', ['ta-x']),
    ('apps', [{'app_id': 'ap-x', 'description': 'rivals-cm3-test-H-0', 'state': 'stopped'}]),
    ('apps', [{'app_id': 'ap-x', 'description': 'other'}] * 2),
])
def test_failed_stale_or_matching_inventory_refuses(tmp_path, key, value):
    data = values()
    data[3]['inventory_snapshots'][1][key] = value
    if key == 'apps':
        raw = data[3]['inventory_snapshots'][1]['raw_outputs']['apps']
        raw['stdout'] = json.dumps(value)
        raw['sha256'] = hashlib.sha256(raw['stdout'].encode()).hexdigest()
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError):
        a.settle(row, doc)


@pytest.mark.parametrize('key', ['reservation_sha256', 'result_sha256', 'owned_inventory_sha256'])
def test_cross_attempt_binding_refuses(tmp_path, key):
    row, _ = source(tmp_path)
    evidence = doc(row['appcreate_rejection'])
    evidence[key] = '0' * 64
    row['appcreate_rejection'] = write(tmp_path, 'bad.json', evidence)
    with pytest.raises(ValueError, match='binding'):
        a.settle(row, doc)


@pytest.mark.parametrize('missing', ['appcreate_rejection', 'owned_inventory'])
def test_missing_evidence_refuses(tmp_path, missing):
    row, _ = source(tmp_path)
    row.pop(missing)
    with pytest.raises(KeyError):
        a.settle(row, doc)


def test_unreadable_evidence_refuses(tmp_path):
    row, _ = source(tmp_path)
    Path(row['appcreate_rejection']['path']).unlink()
    with pytest.raises(FileNotFoundError):
        a.settle(row, doc)


def test_existing_terminal_path_unchanged_and_unknown_still_refused(tmp_path):
    row, _ = source(tmp_path)
    row.pop('appcreate_rejection')
    row.pop('owned_inventory')
    with pytest.raises(ValueError, match='terminal cleanup'):
        a.settle(row, doc)
    result = doc(row['result'])
    result['teardown'].update(status='TERMINAL', apps=['ap-x'],
        events=[{'terminal_apps': ['ap-x'], 'containers': 0}])
    row['result'] = write(tmp_path, 'terminal.json', result)
    settled = a.settle(row, doc)
    assert settled['seconds'] == 10 and settled['usd'] == .007179


@pytest.mark.parametrize('key,value', [('returncode', 1), ('elapsed_seconds', 10.01),
    ('sha256', '0' * 64), ('stdout', 'not-json')])
def test_raw_inventory_command_refuses(tmp_path, key, value):
    data = values()
    data[3]['inventory_snapshots'][1]['raw_outputs']['apps'][key] = value
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError):
        a.settle(row, doc)


@pytest.mark.parametrize('field,value', [('capture_started_at_unix', 111),
    ('capture_finished_at_unix', 493), ('capture_finished_at_unix', 460)])
def test_capture_bounds_refuse(tmp_path, field, value):
    data = values()
    data[3][field] = value
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError):
        a.settle(row, doc)


def test_presence_in_first_snapshot_also_refuses(tmp_path):
    data = values()
    snapshot = data[3]['inventory_snapshots'][0]
    snapshot['apps'] = [{'app_id': 'ap-x', 'description': data[2]['app_name'], 'state': 'stopped'}]
    raw = snapshot['raw_outputs']['apps']
    raw['stdout'] = json.dumps(snapshot['apps'])
    raw['sha256'] = hashlib.sha256(raw['stdout'].encode()).hexdigest()
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError, match='name exists'):
        a.settle(row, doc)


@pytest.mark.parametrize('key', ['key-test-H-0', None])
def test_typed_unknown_charges_full_hold_after_startup(tmp_path, key):
    data = values()
    data[3].update(rpc_outcome='UNKNOWN', rpc_status=None, rejected_at_unix=None,
                   logical_request_id=key)
    row, _ = source(tmp_path, data)
    settled = a.settle(row, doc)
    assert settled['seconds'] == 1020 and settled['usd'] == .732197
    assert settled['owner_results'] == []
    assert settled['absent_app']['rpc_outcome'] == 'UNKNOWN'


@pytest.mark.parametrize('clock', [400, 401])
@pytest.mark.parametrize('outcome', ['REJECTED', 'UNKNOWN'])
def test_full_startup_deadline_is_strict_for_both_outcomes(tmp_path, clock, outcome):
    data = values()
    data[3]['capture_started_at_unix'] = clock
    if outcome == 'UNKNOWN':
        data[3].update(rpc_outcome=outcome, rpc_status=None, rejected_at_unix=None)
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError, match='bound'):
        a.settle(row, doc)


def test_historical_unknown_uses_cleanup_clock_as_conservative_request_upper_bound(tmp_path):
    data = values()
    data[3].update(rpc_outcome='UNKNOWN', rpc_status=None, rejected_at_unix=None,
        request_clock_source='failed_cleanup_upper_bound', request_started_at_unix=110,
        capture_started_at_unix=411, capture_finished_at_unix=473, logical_request_id=None)
    for snapshot, clock in zip(data[3]['inventory_snapshots'], (412, 472)):
        snapshot['checked_at_unix'] = clock
    row, _ = source(tmp_path, data)
    assert a.settle(row, doc)['seconds'] == 1020
    data[3]['request_started_at_unix'] = 100
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError, match='upper bound'):
        a.settle(row, doc)


@pytest.mark.parametrize('field', ['logical_request_id', 'idempotency_key'])
def test_key_match_refuses_even_with_different_app_name(tmp_path, field):
    data = values()
    snap = data[3]['inventory_snapshots'][1]
    snap['apps'] = [{'app_id': 'ap-x', 'description': 'other', field: 'key-test-H-0'}]
    raw = snap['raw_outputs']['apps']
    raw['stdout'] = json.dumps(snap['apps'])
    raw['sha256'] = hashlib.sha256(raw['stdout'].encode()).hexdigest()
    row, _ = source(tmp_path, data)
    with pytest.raises(ValueError, match='key exists'):
        a.settle(row, doc)
