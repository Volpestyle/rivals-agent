"""Local SDK source-mount and installed acceptance proof; no app/build RPC."""
import hashlib
import inspect
import json
from pathlib import Path
import sys


def verify(packet):
    packet = Path(packet).resolve()
    code = packet/"code"
    sys.path.insert(0, str(code))
    import modal
    from modal._utils.function_utils import FunctionSourceInfo
    from cloud.modal_guard import release
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.runner import execute_stages
    from cloud.modal_guard.holds import validate_spec
    from cloud import yaw_fit_entry
    import scripts.job_status
    assert modal.__version__ == "1.5.5"
    assembly = json.loads((packet/"assembly.json").read_bytes())
    inventory = json.loads((packet/"source-inventory.json").read_bytes())
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert digest(packet/"source-inventory.json") == assembly["source_inventory_sha256"]
    assert Path(inspect.getfile(execute_stages)).resolve() == code/"cloud/modal_guard/runner.py"
    assert Path(inspect.getfile(scripts.job_status)).resolve() == code/"scripts/job_status.py"
    release.verify(code/"cloud/modal_guard", assembly["release_sha256"])
    release.reviewed(DEFAULT_ROOT, assembly["release_sha256"])
    mounts = FunctionSourceInfo(execute_stages).get_entrypoint_mount()
    assert set(mounts) == {"cloud"}
    observed = {}
    for entry in mounts["cloud"].entries:
        for local, remote in entry.get_files_to_upload():
            name = Path(remote).relative_to("/root").as_posix()
            assert Path(local).resolve() == code/name
            observed[name] = digest(local)
    assert observed == {p: pin for p, pin in inventory.items() if p.startswith("cloud/")}
    assert observed["cloud/modal_guard/RELEASE.json"] == assembly["release_sha256"]
    for name, pin in inventory.items():
        assert digest(code/name) == pin
    assert digest(code/"cloud/yaw-payload-manifest.json") == assembly["payload_manifest_sha256"]
    payload = json.loads((code/"cloud/yaw-payload-manifest.json").read_bytes())
    for name, pin in payload["files"].items():
        assert digest(code/"cloud/yaw_payload"/name) == pin
    for function in (yaw_fit_entry.fit, yaw_fit_entry.evaluate, yaw_fit_entry.probe):
        assert str(inspect.signature(function)) == "(root, *, payload_manifest_sha256, spec_path, spec_sha256)"
    for pin in assembly["specs"]:
        assert digest(pin["path"]) == pin["sha256"]
        validate_spec(json.loads(Path(pin["path"]).read_bytes()))
    return dict(status="PASS", sdk=modal.__version__, appcreates=0, image_builds=0,
        source_inventory_sha256=assembly["source_inventory_sha256"], cloud_file_count=len(observed),
        release_sha256=assembly["release_sha256"], files=observed)


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1]), indent=2))
