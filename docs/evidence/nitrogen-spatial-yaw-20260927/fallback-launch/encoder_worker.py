"""Yaw-only fallback worker; verified completed stages replay, partial fits refuse."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import time

from explore_mounts import check_mounts, logical_path

RELEASE = "732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce"
CALLBACK = "policy.range_bc.spatial_yaw_train"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_run_config(path, expected_sha, arm):
    assert digest(path) == expected_sha, "Run config hash mismatch"
    config = json.loads(Path(path).read_text())
    assert arm == config["arm"] == "nitrogen" and config["history"] == "disabled"
    assert config["seed"] in (1, 2, 3) and config["grid"] in (4, 8)
    assert config["epochs"] == 26 and config["updates"] == 15288
    assert config["job_name"] == config["app_name"] == (
        f"rivals-yaw-fallback-g{config['grid']}-s{config['seed']}-20260927-01")
    assert config["callback"] == CALLBACK
    for key in ("input_manifest_sha256", "checkpoint_sha256", "cutoff_sha256"):
        value = config[key]
        assert len(value) == 64 and all(c in "0123456789abcdef" for c in value), key
    return config


def execute(out, config, identity, volume, callback, run_stage):
    """A fit completes only after epoch-26 + receipt persist; evaluation is separate."""
    receipts = []
    for stage, artifacts in (("fit", ["epoch-26.pt", "fit.json"]),
                             ("evaluate", ["evaluation.json"])):
        receipts.append(run_stage(
            Path(out) / stage, stage, identity, artifacts,
            lambda root, stage=stage: getattr(callback, stage)(
                root, config=config, fit_root=Path(out) / "fit",
                deadline=identity["deadline_unix"]),
            commit=volume.commit, reload=volume.reload))
    return receipts


def run_encoder(arm, deadline, pins, bundle_sha, output_volume, config_sha):
    import modal
    targets = check_mounts(pins)
    assert time.time() < deadline
    config = load_run_config(logical_path('/outputs/run-config.json', targets), config_sha, arm)
    assert pins == {"/inputs": config["input_volume_id"], "/outputs": config["output_volume_id"]}
    manifest = logical_path('/inputs/dual-grid-inputs.json', targets)
    assert digest(manifest) == config["input_manifest_sha256"]
    bundle = logical_path('/outputs/code.tar', targets)
    assert digest(bundle) == bundle_sha
    volume = modal.Volume.from_name(output_volume)
    volume.hydrate()
    assert volume.object_id == pins['/outputs']
    out = logical_path('/outputs/run', targets)
    identity = {"attempt_id": config["job_name"], "code_sha256": bundle_sha,
                "inputs_sha256": config["input_manifest_sha256"], "recipe_sha256": config_sha,
                "output_volume_id": pins['/outputs'], "deadline_unix": deadline}
    volume.reload()
    if out.exists():
        assert json.loads((out / 'started.json').read_text())['identity'] == identity
    else:
        out.mkdir(exist_ok=False)
        (out / 'started.json').write_text(json.dumps({'identity': identity}) + '\n')
        volume.commit()
    with tempfile.TemporaryDirectory(prefix='yaw-fallback-code-') as temp:
        code = Path(temp)
        with tarfile.open(bundle) as archive:
            archive.extractall(code, filter='data')
        sys.path.insert(0, str(code))
        # Only stage durability helpers are reused here, never the shared paid runner.
        from cloud.modal_guard import release
        from cloud.modal_guard.stages import run
        release.verify(code / 'cloud/modal_guard', RELEASE)
        callback = importlib.import_module(config['callback'])
        receipts = execute(out, config, identity, volume, callback, run)
        result = {'tag': 'EXPLORATORY', 'exit': 0, 'identity': identity,
                  'completed_at': time.time(), 'stages': receipts, 'files': {}}
        for path in out.rglob('*'):
            if path.is_file() and path.name != 'result.json':
                result['files'][path.relative_to(out).as_posix()] = {
                    'bytes': path.stat().st_size, 'sha256': digest(path)}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        volume.commit()
        return result
