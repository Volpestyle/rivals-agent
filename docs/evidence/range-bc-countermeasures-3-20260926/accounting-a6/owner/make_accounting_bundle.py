"""Build an unapproved canonical v2 bundle from pinned historical metadata only."""
import argparse
import hashlib
import json
from pathlib import Path
import cm3_accounting as accounting


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def build(source_reference, destination, outputs_root):
    destination, outputs_root = Path(destination), Path(outputs_root)
    if destination.exists():
        raise ValueError('bundle destination already exists')
    def source_bytes(ref):
        path = Path(ref['path'])
        if ref['path'].startswith('/outputs/'):
            logical = accounting.output_ref(ref)['path'].removeprefix('outputs/')
            root = outputs_root.resolve(strict=True)
            path = (root / logical).resolve(strict=True)
            accounting.require(path.is_relative_to(root), 'source outputs escape')
        accounting.require(path.is_absolute() and path.stat().st_size <= 32*1024*1024, 'metadata path/size')
        data = path.read_bytes()
        accounting.require(hashlib.sha256(data).hexdigest() == ref['sha256'], 'source metadata hash mismatch')
        return data
    def source_doc(ref):
        return json.loads(source_bytes(ref))
    source = source_doc(source_reference)
    accounting.require(source['format'] == 'cm3-measured-accounting-v1', 'pinned source v1 metadata required')
    original = accounting.ledger(source_reference, source_doc)
    payloads = {}
    def add(name, data):
        ref = accounting.relative_ref({'path': name, 'sha256': hashlib.sha256(data).hexdigest()})
        accounting.require(name not in payloads or payloads[name] == data, 'canonical path collision')
        payloads[name] = data
        return ref
    rows, reservations = [], {}
    for row, settled in zip(source['settlements'], original['settlements']):
        attempt = row['attempt_id']
        reservation = accounting.reservation_ref(attempt, row['reservation']['sha256'])
        add(reservation['path'], source_bytes(row['reservation']))
        item = {'attempt_id': attempt, 'reservation': reservation,
                'result': add('results/'+attempt+'.json', source_bytes(row['result']))}
        if 'pricing' in row:
            item['pricing'] = add('pricing/'+attempt+'.json', source_bytes(row['pricing']))
        for key in ('appcreate_rejection', 'owned_inventory'):
            if key in row:
                item[key] = add(key+'/'+attempt+'.json', source_bytes(row[key]))
        for owner in settled['owner_results']:
            add(accounting.output_ref(owner)['path'], source_bytes(owner))
        rows.append(item)
        reservations[attempt] = reservation
    inventory = add('inventory.json', encoded({'format': 'cm3-reservation-inventory-v2',
        'campaign_id': source['campaign_id'], 'reservations': reservations}))
    data = {key: source[key] for key in ('approved_by','campaign_id','basis_seconds','basis_usd')}
    data.update(format='cm3-measured-accounting-v2', inventory=inventory, settlements=rows)
    if 'completed_phase1' in source:
        data['completed_phase1'] = {}
        for key, ref in source['completed_phase1'].items():
            logical = accounting.output_ref(ref)
            add(logical['path'], source_bytes(ref))
            data['completed_phase1'][key] = logical
    add('ledger.json', encoded(data))
    # Authentication/collection above is read-only; output is a fresh metadata bundle.
    destination.mkdir(parents=True)
    for name, content in payloads.items():
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(content)
    reference = {'path': str((destination/'ledger.json').resolve()),
                 'sha256': hashlib.sha256(payloads['ledger.json']).hexdigest()}
    def copied_doc(ref):
        content = Path(ref['path']).read_bytes()
        accounting.require(hashlib.sha256(content).hexdigest() == ref['sha256'], 'copied evidence hash mismatch')
        return json.loads(content)
    totals = accounting.ledger(reference, copied_doc)
    accounting.require((totals['spent_seconds'],totals['spent_usd']) ==
        (original['spent_seconds'],original['spent_usd']), 'transport changed accounting')
    return reference


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-ledger', required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--outputs-root', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    print(json.dumps(build({'path':args.source_ledger,'sha256':args.sha256},args.output,args.outputs_root),indent=2))
