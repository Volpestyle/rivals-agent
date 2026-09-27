"""Measured campaign accounting; callers authenticate every JSON reference.

No writes, launches, refunds or approval authority. USD is a conservative clock
and approved-rate estimate, never represented as a provider invoice.
"""
from decimal import Decimal, ROUND_CEILING
import math
from pathlib import Path, PurePosixPath
import re

CAP_SECONDS = 57600
CAP_USD = Decimal('50')
BASIS_SECONDS = 12159
BASIS_USD = Decimal('6.18374656')
IDENTITY = {'profile': 'rivals', 'workspace': 'volpestyle',
            'workspace_id': 'ac-kMLf5bJKqF5CAlSbfNhGh0'}
# Older diagnostic drivers omitted format/attempt_id. Only these exact historical
# result bytes have the reviewed serial driver-through-cleanup clock contract.
LEGACY_SERIAL = {
    'capture-03': '2408b72a85f32e32bd0052e4c6fc6e50cc39b822443b75e57db870b2b75fe188',
    'mount-probe-01': 'e1439f5178525d3798c830d08b0d12f298e75fdd7027f4b5f242a88b1b6831f1',
    'runtime-probe-01': '0523b0303fcd62a2efc1544f3382dd7a20d5da48bead9942fefd93ee78c17931',
    'runtime-probe-03': '4ff8c02eaf2ef83e4c3bb80588ebb62f7477bd8b4daa264ac256dd73e1c5599d',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, name, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), 'invalid ' + name)
    return Decimal(str(value))


def usd_up(value):
    return value.quantize(Decimal('0.000001'), rounding=ROUND_CEILING)



def relative_ref(ref):
    """Validate one root-relative evidence reference without changing its bytes."""
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'canonical evidence reference required')
    name = ref['path']
    require(isinstance(name, str) and name and ':' not in name and '\\' not in name,
            'invalid canonical evidence path')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and '..' not in path.parts and str(path) == name,
            'noncanonical/traversal evidence path')
    require(isinstance(ref['sha256'], str) and re.fullmatch('[0-9a-f]{64}', ref['sha256']) is not None,
            'invalid canonical evidence digest')
    return dict(ref)



def reservation_ref(attempt, digest):
    require(isinstance(attempt, str) and re.fullmatch('[a-zA-Z0-9_.-]+', attempt) is not None
            and attempt not in ('.', '..'), 'invalid reservation attempt')
    return relative_ref({'path': 'reservations/' + attempt + '.json', 'sha256': digest})


def output_ref(ref):
    """Only immutable owner /outputs refs have a fixed canonical namespace alias."""
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'owner reference required')
    name = ref['path']
    require(isinstance(name, str), 'invalid owner reference path')
    if name.startswith('/outputs/'):
        name = name[1:]
    result = relative_ref({'path': name, 'sha256': ref['sha256']})
    require(result['path'].startswith('outputs/'), 'owner evidence outside outputs namespace')
    return result


def bundle_document(reference, document, *, local_path=Path):
    """Bind relative evidence to the externally authenticated ledger's directory.

    document remains the caller's hash-checking reader. local_path maps logical
    mounts to the physical filesystem only for containment checks (Writer.local).
    No caller-supplied mapping is serialized into the canonical ledger.
    """
    external = Path(reference['path'])
    if not external.is_absolute():
        external = PurePosixPath(reference['path'])
    root = external.parent
    require(root.is_absolute(), 'absolute external ledger reference required')
    physical_root = Path(local_path(str(root))).resolve(strict=True)
    require(physical_root.is_dir(), 'ledger evidence root missing')
    def read(ref):
        ref = relative_ref(ref)
        target = root.joinpath(*PurePosixPath(ref['path']).parts)
        physical = Path(local_path(str(target))).resolve(strict=True)
        require(physical.is_relative_to(physical_root) and physical.is_file(),
                'evidence escaped ledger root')
        return document({'path': str(target), 'sha256': ref['sha256']})
    return read


def settle(row, document):
    """Verify one completed attempt, including failed scientific executions."""
    reservation, result = document(row['reservation']), document(row['result'])
    attempt = row['attempt_id']
    legacy = LEGACY_SERIAL.get(attempt) == row['result']['sha256']
    require(reservation.get('attempt_id', reservation.get('run_id')) == attempt
            and (result.get('attempt_id', result.get('run_id')) == attempt or legacy), 'attempt binding')
    require(result['status'] in ('PASS', 'INCOMPLETE', 'COMPLETE'), 'unfinished attempt')
    teardown = result['teardown']
    require(teardown['status'] == 'TERMINAL' and teardown['identity'] == IDENTITY,
            'terminal cleanup required')
    apps = teardown['apps']
    require(apps and len(apps) == len(set(apps)), 'app inventory missing/duplicate')
    require(any(event.get('containers') == 0 and set(event.get('terminal_apps', [])) == set(apps)
                for event in teardown['events']), 'terminal app/container evidence missing')
    number(teardown['checked_at_unix'], 'cleanup clock', True)
    spend = result.get('spend', result)
    seconds = number(spend.get('seconds_through_cleanup', result.get('elapsed_seconds')),
                     'driver-through-cleanup seconds', True)
    bounds = reservation.get('bounds')
    if bounds is None:
        pricing = document(row['pricing'])
        expected = reservation.get('proposal_sha256', reservation.get('approved_receipt_sha256'))
        require(expected == row['pricing']['sha256'], 'pricing not reservation-bound')
        bounds = pricing['budget']
    rate = number(bounds['rate_usd_second'], 'resource rate', True)
    overhead = number(bounds['overhead_usd'], 'noncompute overhead')
    slots = reservation.get('concurrent_slots', 1)
    require(type(slots) is int and slots in (1, 5, 8), 'unregistered concurrency')
    if slots != 1:
        require(result['format'] == 'cm3-fanout-wrapper-result-v2'
                and len(reservation['tasks']) == slots and len(set(reservation['tasks'])) == slots,
                'fanout concurrency evidence')
        require(set(reservation['tasks']) == ({'A-0', 'A-1', 'A-2', 'H-0', 'H-repeat-0'} if slots == 5
                else {'H-1', 'H-2', 'I-0', 'I-1', 'I-2', 'W-0', 'W-1', 'W-2'}), 'fanout task set')
        require(set(result['owner_results']).issubset(set(reservation['tasks'])), 'unexpected fanout result')
        owner_results = list(result['owner_results'].values())
    else:
        require(legacy or result.get('format') in ('cm3-bootstrap-result-v1', 'cm3-inputs-wrapper-result-v1',
                'cm3-mount-probe-result-v1', 'cm3-runtime-probe-result-v1',
                'cm3-runtime-capture-result-v1'), 'unknown serial clock semantics')
        owner_results = [result['owner_result']] if result.get('owner_result') is not None else []
    # Whole driver lifetime per allocated slot is conservative even when workers overlap.
    charged_seconds = math.ceil(seconds * slots)
    calculated = overhead + seconds * slots * rate
    reported = number(spend['estimated_conservative_usd'], 'reported estimate')
    require(abs(reported - calculated) <= Decimal('0.000000001'), 'cost/clock/rate mismatch')
    charged_usd = usd_up(overhead + Decimal(charged_seconds) * rate)
    number(reservation['reserved_compute_seconds'], 'reserved seconds', True)
    number(reservation['reserved_usd'], 'reserved dollars', True)
    return {'attempt_id': attempt, 'seconds': charged_seconds, 'usd': float(charged_usd),
            'owner_results': owner_results, 'reservation': row['reservation']}


def ledger(reference, document, *, required_results=(), inventory=None, local_path=Path):
    """The external pin binds the complete reservation inventory and every settlement.

The launching wrapper MUST also compare against its on-disk campaign inventory
under its existing lock, before creating a new hold. Missing results refuse.
"""
    data = document(reference)
    canonical = data['format'] == 'cm3-measured-accounting-v2'
    require(data['format'] in ('cm3-measured-accounting-v1', 'cm3-measured-accounting-v2') and data['approved_by'] == 'herdr-lead'
            and data['campaign_id'] == 'r3-20260926-l40s', 'accounting authority/campaign')
    require(data['basis_seconds'] == BASIS_SECONDS and Decimal(str(data['basis_usd'])) == BASIS_USD,
            'pre-campaign basis changed')
    if canonical:
        relative_ref(data['inventory'])
        for row in data['settlements']:
            for key in ('reservation', 'result', 'pricing'):
                if key in row:
                    relative_ref(row[key])
        for ref in data.get('completed_phase1', {}).values():
            require(relative_ref(ref) == output_ref(ref), 'noncanonical phase1 output')
        required_results = [output_ref(ref) for ref in required_results]
        document = bundle_document(reference, document, local_path=local_path)
    reservations = document(data['inventory'])
    require(reservations['format'] == ('cm3-reservation-inventory-v2' if canonical else 'cm3-reservation-inventory-v1')
            and reservations['campaign_id'] == data['campaign_id'], 'inventory campaign')
    expected = reservations['reservations']
    require(isinstance(expected, dict) and expected, 'empty reservation inventory')
    if canonical:
        for attempt, ref in expected.items():
            require(relative_ref(ref) == reservation_ref(attempt, ref['sha256']),
                    'noncanonical reservation location')
    if inventory is not None:
        require(expected == inventory, 'campaign reservation inventory changed')
    rows, ids, measured, owners = data['settlements'], set(), [], []
    for row in rows:
        attempt = row['attempt_id']
        require(attempt not in ids and expected.get(attempt) == row['reservation'],
                'duplicate/unregistered settlement')
        ids.add(attempt)
        item = settle(row, document)
        if canonical:
            item['owner_results'] = [output_ref(ref) for ref in item['owner_results']]
        measured.append(item)
        elapsed = Decimal(0)
        for ref in item['owner_results']:
            require(ref not in owners, 'duplicate owner result')
            owner = document(ref)
            elapsed += number(owner['elapsed_stage_seconds'], 'owner elapsed')
            owners.append(ref)
        require(elapsed <= item['seconds'], 'owner compute exceeds wrapper clock')
    require(ids == set(expected), 'missing measured attempt record; hold not released')
    require(all(ref in owners for ref in required_results), 'predecessor absent from accounting')
    seconds = BASIS_SECONDS + sum(row['seconds'] for row in measured)
    dollars = BASIS_USD + sum((Decimal(str(row['usd'])) for row in measured), Decimal(0))
    require(seconds <= CAP_SECONDS and dollars <= CAP_USD, 'measured campaign cap exhausted')
    return {'spent_seconds': seconds, 'spent_usd': float(dollars), 'settlements': measured,
            'inventory': expected}


def allocation(budget, document, *, required_results=(), local_path=Path):
    require(document(budget['accounting'])['format'] == 'cm3-measured-accounting-v2',
            'canonical v2 ledger required for new allocations')
    totals = ledger(budget['accounting'], document, required_results=required_results, local_path=local_path)
    require(budget['spent_seconds'] == totals['spent_seconds']
            and Decimal(str(budget['spent_usd'])) == Decimal(str(totals['spent_usd'])), 'spent differs from measured ledger')
    cap = number(budget['cap_seconds'], 'compute cap', True)
    usd_cap = number(budget['cloud_cap_usd'], 'dollar cap', True)
    stage = number(budget['stage_seconds'], 'stage seconds', True)
    hold_seconds = number(budget['hold_seconds'], 'hold seconds', True)
    hold_usd = number(budget['hold_usd'], 'hold dollars', True)
    rate = number(budget['hourly_usd'], 'hourly rate', True) / 3600
    overhead = number(budget['stage_overhead_usd'], 'stage overhead')
    require(cap <= CAP_SECONDS and usd_cap <= CAP_USD and stage <= hold_seconds
            and totals['spent_seconds'] + hold_seconds <= cap, 'compute reservation exhausted')
    require(hold_usd >= usd_up(hold_seconds * rate + overhead)
            and Decimal(str(totals['spent_usd'])) + hold_usd <= usd_cap, 'dollar reservation exhausted')
    return totals
