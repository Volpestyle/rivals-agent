"""SDK 1.5.5 source-mount inspection only: no App.run, build or cloud RPC."""
import argparse
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys


def verify(packet):
    packet = Path(packet).resolve()
    code = packet / "code"
    sys.path.insert(0, str(code))
    import modal
    from modal._utils.function_utils import FunctionSourceInfo
    from cloud.modal_guard import release
    from cloud.modal_guard.runner import execute_stages
    from cloud import yaw_entry
    import scripts.job_status
    assert modal.__version__ == "1.5.5"
    assembly = json.loads((packet / "assembly.json").read_bytes())
    inventory = json.loads((packet / "source-inventory.json").read_bytes())
    assert hashlib.sha256((packet / "source-inventory.json").read_bytes()).hexdigest() == assembly["source_inventory_sha256"]
    assert Path(inspect.getfile(execute_stages)).resolve() == code / "cloud/modal_guard/runner.py"
    assert Path(inspect.getfile(scripts.job_status)).resolve() == code / "scripts/job_status.py"
    release.verify(code / "cloud/modal_guard", assembly["release_sha256"])
    from cloud.modal_guard.common import DEFAULT_ROOT
    release.reviewed(DEFAULT_ROOT, assembly["release_sha256"])
    mounts = FunctionSourceInfo(execute_stages).get_entrypoint_mount()
    assert set(mounts) == {"cloud"}
    observed = {}
    for entry in mounts["cloud"].entries:
        for local, remote in entry.get_files_to_upload():
            relative = Path(remote).relative_to("/root").as_posix()
            assert Path(local).resolve() == code / relative
            observed[relative] = hashlib.sha256(Path(local).read_bytes()).hexdigest()
    expected = {p: sha for p, sha in inventory.items() if p.startswith("cloud/")}
    assert observed == expected
    assert observed["cloud/modal_guard/RELEASE.json"] == assembly["release_sha256"]
    yaw_entry.verify_payload(assembly["payload_manifest_sha256"])
    worker = importlib.import_module("policy.range_bc.spatial_yaw_cloud_cache")
    assert str(inspect.signature(worker.run)) == "(root, *, spec_path, spec_sha256)"
    from cloud.modal_guard.holds import validate_spec
    for pin in assembly["specs"]:
        raw = Path(pin["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
        validate_spec(json.loads(raw))
    return {"status": "PASS", "sdk": modal.__version__, "appcreates": 0, "image_builds": 0,
            "source_inventory_sha256": assembly["source_inventory_sha256"],
            "cloud_file_count": len(observed), "host_only_files": ["scripts/job_status.py"],
            "entrypoint": "cloud.modal_guard.runner.execute_stages",
            "stage": "cloud.yaw_entry.run", "worker": "policy.range_bc.spatial_yaw_cloud_cache.run",
            "files": observed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("packet")
    args = parser.parse_args()
    print(json.dumps(verify(args.packet), indent=2))
