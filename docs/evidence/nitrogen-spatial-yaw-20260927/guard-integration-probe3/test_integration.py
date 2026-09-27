"""Offline assembly/closure checks; no imports of the CUDA workload or Modal calls."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
module_spec = importlib.util.spec_from_file_location("yaw_assembler", HERE / "assemble.py")
assembler = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(assembler)
RUNTIME = "/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-test"


def test_draft_has_no_launch_and_preserves_exact_git_pins(tmp_path):
    result = assembler.assemble(ROOT, tmp_path / "draft", RUNTIME)
    assert result["status"].startswith("DRAFT") and not result["launch_performed"]
    assert result["probe_reserved_usd"] == "2.884404" and result["new_image_builds"] == 0
    assert result["cumulative_probe_allocation_usd"] == "5.861882"
    envelope = json.loads((tmp_path / "draft/bootstrap.json").read_bytes())
    assert envelope["campaign_cap_usd"] == "3.022522"
    assert envelope["startup_seconds"] == 300
    assert all("probe3" in x for x in envelope["attempt_ids"])
    code = tmp_path / "draft/code"
    payload = code / "cloud/yaw_payload"
    assert assembler.digest((payload / assembler.INPUT_SPEC).read_bytes()) == assembler.INPUT_SHA
    assert assembler.digest((payload / "policy/range_bc/spatial_yaw_probe.py").read_bytes()) == assembler.PROBE_SHA
    assert (code / "cloud/modal_guard/RELEASE.json").is_file()
    assert (code / "scripts/job_status.py").is_file()  # host-only import dependency
    for pin in result["specs"]:
        spec = json.loads((tmp_path / "draft/specs" / Path(pin["path"]).name).read_bytes())
        assert spec["stage_identity"]["output_volume_id"] is None
        assert spec["stages"][0]["module"] == "cloud.yaw_entry"
        assert spec["stages"][0]["artifacts"] == ["probe.json", "probe-yaw.pt"]
        assert spec["hold"]["work_seconds"] == 180


def test_concrete_bindings_and_corruption_refusal(tmp_path):
    metadata = tmp_path / "image.json"
    metadata.write_bytes(assembler.encode({"image_id": assembler.BASE_IMAGE}))
    binding = {"image_id": assembler.BASE_IMAGE, "release_sha256": assembler.RELEASE,
               "image_metadata_ref": {"path": str(metadata), "sha256": assembler.digest(metadata.read_bytes())},
               "outputs": [{"name": "rivals-yaw-probe3-20260927-" + str(i).zfill(2) + "-outputs",
                            "id": "vo-test" + str(i)} for i in range(1, 7)]}
    path = tmp_path / "bindings.json"
    path.write_bytes(assembler.encode(binding))
    ref = {"path": str(path), "sha256": assembler.digest(path.read_bytes())}
    result = assembler.assemble(ROOT, tmp_path / "final", RUNTIME, bindings_ref=ref)
    assert result["status"] == "ASSEMBLED" and len(result["specs"]) == 6
    spec_refs = result["specs"]
    assert len({p["sha256"] for p in spec_refs}) == 6
    with pytest.raises(FileExistsError):
        assembler.assemble(ROOT, tmp_path / "final", RUNTIME, bindings_ref=ref)
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="bytes differ"):
        assembler.assemble(ROOT, tmp_path / "bad", RUNTIME, bindings_ref=ref)
    assert not (tmp_path / "bad").exists()


def test_payload_bridge_detects_changed_code_before_import(tmp_path):
    result = assembler.assemble(ROOT, tmp_path / "packet", RUNTIME)
    cloud = tmp_path / "packet/code/cloud"
    spec = importlib.util.spec_from_file_location("test_yaw_bridge", cloud / "yaw_entry.py")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    (cloud / "yaw_payload/policy/range_bc/spatial_yaw_probe.py").write_text("raise RuntimeError('must not import')")
    with pytest.raises(ValueError, match="payload bytes differ"):
        bridge.verify_payload(result["payload_manifest_sha256"])
