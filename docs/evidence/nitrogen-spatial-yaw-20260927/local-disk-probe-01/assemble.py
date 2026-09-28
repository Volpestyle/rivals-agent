"""Offline closure for the lead-approved $1.50 local-copy timing probe."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ATTEMPT = 'yaw-local-disk-probe-20260927-01'
RUNTIME = '/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/local-disk-probe-01'


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def assemble(original, destination, volume_id):
    from cloud.modal_guard.holds import bootstrap
    original, destination = Path(original), Path(destination)
    inventory = json.loads((original/'source-inventory.json').read_bytes())
    sources = {}
    for name, digest in inventory.items():
        raw = (original/'code'/name).read_bytes()
        assert sha(raw) == digest
        sources[name] = raw
    manifest = json.loads(sources['cloud/yaw-payload-manifest.json'])
    name = 'policy/range_bc/spatial_yaw_io_probe.py'
    raw = subprocess.check_output(['git', 'show', '5acb203:'+name])
    sources['cloud/yaw_payload/'+name] = raw
    manifest['files'][name] = sha(raw)
    spec = json.loads((original/'specs/yaw-fit-grid8-s1-20260927-02.json').read_bytes())
    science_path = 'fit-specs/yaw-fit-grid8-s1-20260927-02.json'
    science = json.loads(sources['cloud/yaw_payload/'+science_path])
    science['timed_updates'] = 716
    raw = encode(science)
    sources['cloud/yaw_payload/io-probe-spec.json'] = raw
    manifest['files']['io-probe-spec.json'] = sha(raw)
    science_sha = sha(raw)
    sources['cloud/yaw-payload-manifest.json'] = encode(manifest)
    payload_sha = sha(encode(manifest))
    sources['cloud/yaw_io_entry.py'] = b'''from .yaw_fit_entry import verify_payload
import importlib
def run(root, *, payload_manifest_sha256, spec_path, spec_sha256):
    verify_payload(payload_manifest_sha256)
    return importlib.import_module("policy.range_bc.spatial_yaw_io_probe").run(
        root, spec_path=spec_path, spec_sha256=spec_sha256)
'''
    envelope = dict(mode='EXPLORATORY_BOOTSTRAP', campaign_id='nitrogen-spatial-yaw-local-disk-probe-01',
        workload='full-cache-local-copy-hash-one-shuffled-epoch-plus128-and-evaluator-timing',
        attempt_ids=[ATTEMPT], concurrency=1, campaign_cap_usd='1.5', startup_seconds=300,
        work_seconds=1600, cleanup_seconds=120, rate_usd_second='0.0007178888888888888888888888889',
        overhead_usd='0.04')
    hold = bootstrap(envelope)
    spec.update(attempt_id=ATTEMPT, app_name='rivals-'+ATTEMPT, run_cap_usd='1.5', hold=hold,
        bootstrap_ref={'path': RUNTIME+'/bootstrap.json', 'sha256': sha(encode(envelope))},
        output_volume='rivals-'+ATTEMPT+'-outputs', output_root='/outputs/'+ATTEMPT,
        stage_identity={**spec['stage_identity'], 'attempt_id': ATTEMPT, 'code_sha256': payload_sha,
                        'recipe_sha256': science_sha, 'output_volume_id': volume_id},
        stages=[dict(name='probe', module='cloud.yaw_io_entry', function='run', artifacts=['copy.json', 'probe.json'],
                     kwargs=dict(payload_manifest_sha256=payload_sha,
                                 spec_path='/root/cloud/yaw_payload/io-probe-spec.json', spec_sha256=science_sha))])
    # validate_spec resolves the absolute Mac bootstrap_ref; native proof does
    # that after transfer, before launch. This assembler runs offline on the PC.
    output = {'code/'+k: v for k, v in sources.items()}
    output.update({'spec.json': encode(spec), 'bootstrap.json': encode(envelope),
                   'source-inventory.json': encode({k: sha(v) for k, v in sources.items()})})
    assembly = dict(release_sha256=spec['release_sha256'], payload_manifest_sha256=payload_sha,
                    source_inventory_sha256=sha(output['source-inventory.json']),
                    specs=[dict(path=RUNTIME+'/spec.json', sha256=sha(output['spec.json']))],
                    total_reserved_usd=hold['reserved_usd'], campaign_cap_usd='24', probe_cap_usd='1.5')
    output['assembly.json'] = encode(assembly)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in output.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return assembly


if __name__ == '__main__':
    print(json.dumps(assemble(*sys.argv[1:]), indent=2))
