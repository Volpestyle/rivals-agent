"""Fresh local-disk grid8 fits, unchanged science, explicit lead cap amendment."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

RUNTIME = '/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/fullfit-local-03'


def encode(v):
    return (json.dumps(v, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def assemble(original, bindings, destination):
    from cloud.modal_guard.holds import bootstrap
    from cloud.modal_guard.release import verify
    original, destination = Path(original), Path(destination)
    inventory = json.loads((original/'source-inventory.json').read_bytes())
    old_assembly = json.loads((original/'assembly.json').read_bytes())
    assert sha((original/'source-inventory.json').read_bytes()) == old_assembly['source_inventory_sha256']
    sources = {}
    for name, digest in inventory.items():
        raw = (original/'code'/name).read_bytes()
        assert sha(raw) == digest
        sources[name] = raw
    manifest = json.loads(sources['cloud/yaw-payload-manifest.json'])
    for filename in ('spatial_yaw_train.py', 'spatial_yaw_local.py', 'spatial_yaw_io_probe.py'):
        name = 'policy/range_bc/' + filename
        raw = subprocess.check_output(['git', 'show', '4487b42:'+name])
        sources['cloud/yaw_payload/'+name] = raw
        manifest['files'][name] = sha(raw)
    bindings = json.loads(Path(bindings).read_bytes())
    attempts = [f'yaw-fit-grid8-s{s}-20260927-03' for s in (1, 2, 3)]
    assert set(bindings) == set(attempts) and len(set(bindings.values())) == 3
    science = []
    for seed, attempt in enumerate(attempts, 1):
        old = f'fit-specs/yaw-fit-grid8-s{seed}-20260927-02.json'
        recipe = json.loads(sources['cloud/yaw_payload/'+old])
        assert recipe['grid'] == 8 and recipe['seed'] == seed and recipe['epochs'] == 26 and recipe['updates'] == 15288
        recipe['cache_mode'] = 'verified-local'
        relative = 'fit-specs/'+attempt+'.json'
        raw = encode(recipe)
        sources['cloud/yaw_payload/'+relative] = raw
        manifest['files'][relative] = sha(raw)
        science.append((relative, sha(raw)))
    sources['cloud/yaw-payload-manifest.json'] = encode(manifest)
    payload_sha = sha(encode(manifest))
    envelope = dict(mode='EXPLORATORY_BOOTSTRAP', campaign_id='nitrogen-spatial-yaw-fullfit-local-03',
        workload='local-hashed-dualgrid-cache-26epoch-grid8-threefits-and-local-evaluation',
        attempt_ids=attempts, concurrency=3, campaign_cap_usd='14.63', startup_seconds=300,
        work_seconds=6300, cleanup_seconds=120, rate_usd_second='0.0007178888888888888888888888889',
        overhead_usd='0.05')
    hold = bootstrap(envelope)
    assert hold['reserved_usd'] == '4.874214'
    total = 3*Decimal(hold['reserved_usd'])
    assert Decimal('10.052912') + total == Decimal('24.675554') < Decimal('25')
    output = {'code/'+k: v for k, v in sources.items()}
    output['bootstrap.json'] = encode(envelope)
    pins = []
    for seed, (attempt, (relative, digest)) in enumerate(zip(attempts, science), 1):
        spec = json.loads((original/f'specs/yaw-fit-grid8-s{seed}-20260927-02.json').read_bytes())
        spec.update(attempt_id=attempt, app_name='rivals-'+attempt, run_cap_usd='4.88', hold=hold,
            bootstrap_ref={'path': RUNTIME+'/bootstrap.json', 'sha256': sha(encode(envelope))},
            output_volume='rivals-'+attempt+'-outputs', output_root='/outputs/'+attempt,
            stage_identity={**spec['stage_identity'], 'attempt_id': attempt, 'code_sha256': payload_sha,
                            'recipe_sha256': digest, 'output_volume_id': bindings[attempt]})
        for stage in spec['stages']:
            stage['kwargs'] = dict(payload_manifest_sha256=payload_sha,
                spec_path='/root/cloud/yaw_payload/'+relative, spec_sha256=digest)
        path = 'specs/'+attempt+'.json'
        output[path] = encode(spec)
        pins.append({'path': RUNTIME+'/'+path, 'sha256': sha(output[path])})
    output['source-inventory.json'] = encode({k: sha(v) for k, v in sources.items()})
    assembly = dict(release_sha256=spec['release_sha256'], source_commit='4487b42',
        payload_manifest_sha256=payload_sha, source_inventory_sha256=sha(output['source-inventory.json']),
        specs=pins, per_arm_reserved_usd=hold['reserved_usd'], total_reserved_usd=str(total),
        prior_settled_usd='10.052912', campaign_cap_usd='25', campaign_warn_usd='24',
        combined_usd='24.675554', full_fit_p95_claim=False, launch_performed=False)
    output['assembly.json'] = encode(assembly)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in output.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify(destination/'code/cloud/modal_guard', assembly['release_sha256'])
    return assembly


if __name__ == '__main__':
    print(json.dumps(assemble(*sys.argv[1:]), indent=2))
