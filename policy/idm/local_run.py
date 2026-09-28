"""Local native-store adapter and bounded I/O timing, no cloud provisioning."""
from pathlib import Path
import json
import tempfile
import time

from policy.idm import cloud_run, local_store, refit_stages as R


def run(root, *, phase, manifest, manifest_sha256, registry, input_volume_id, output_volume_id):
    root = Path(root)
    R.E.require(root.name == phase and phase in (*R.ARTIFACTS, 'local', 'timing'), 'local stage differs')
    started = time.perf_counter()
    _, loaded, _, _ = cloud_run.load_inputs(
        manifest=manifest, manifest_sha256=manifest_sha256, registry=registry, out=str(root),
        input_volume_id=input_volume_id, output_volume_id=output_volume_id)
    preflight_seconds = time.perf_counter()-started
    R.D.require_disjoint_roles(loaded)
    R.E.require_decode_platform(loaded)
    identity = json.loads((root/'started.json').read_bytes())['identity']
    R.E.require(identity['inputs_sha256'] == manifest_sha256, 'local input identity differs')
    attempt = identity['attempt_id']
    R.E.require(Path(attempt).name == attempt and attempt not in ('.', '..'), 'invalid local attempt')
    def progress(value):
        print(json.dumps({'stage': phase, 'progress': value}), flush=True)
        R.write('idm-local-'+phase, root=root/'jobs', owner='idm-owner', host='modal',
                stage='running', evidence=str(root/'completed.json'), progress=value)
    if phase not in ('zero', 'report'):
        cache = Path(tempfile.gettempdir())/('idm-native-'+attempt)
        loaded, copied = local_store.prepare(loaded, source_root='/inputs', cache=cache,
                                             identity=identity, progress=progress)
        if phase in ('local', 'timing'):
            R.E.write_json(root/'copy.json', copied)
    if phase == 'local':
        R.E.write_json(root/'local.json', {'preflight_seconds': preflight_seconds,
                                         'source_and_destination_verified': True})
        return 0
    if phase == 'timing':
        from policy.idm.io_probe import measure, projection
        report = measure(loaded, device='cuda', progress=progress)
        report.update(preflight_seconds=preflight_seconds, local_copy=copied)
        report['projection'] = projection(
            train_rows=report['training']['full_train_examples'], dev_rows=report['dev_rows'],
            train_rate=report['training']['steady_updates_per_second'],
            inference_rate=min(v['rows_per_second'] for v in report['inference']),
            camera_seconds=report['camera_projected_seconds'], preflight_seconds=preflight_seconds,
            copy_seconds=copied['seconds'], loader_seconds=report['loader_seconds'],
            cache_verify_seconds=copied['destination_verify_seconds'])
        R.E.write_json(root/'timing.json', report)
        return 0
    # Existing training/evaluation code still re-hashes FrameStore inputs and
    # authenticates completed predecessor stages; no partial fit can resume.
    return R.compute(root, phase, loaded, device='cuda', manifest_sha256=manifest_sha256, progress=progress)
