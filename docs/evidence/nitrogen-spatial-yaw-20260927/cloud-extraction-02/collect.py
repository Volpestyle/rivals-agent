"""Read-only collection after guard completion; no compute, retry or volume writes."""
import hashlib
import json
from pathlib import Path
import sys
import time


def collect(packet, destination):
    packet, destination = Path(packet), Path(destination)
    sys.path.insert(0, str(packet / "code"))
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.provider import connect
    import modal
    spec = json.loads((packet / "spec.json").read_bytes())
    local = DEFAULT_ROOT / "attempts" / spec["attempt_id"]
    result = json.loads((local / "result.json").read_bytes())
    assert result["status"] == "COMPLETE" and result["accounting"]["state"] == "TERMINAL"
    assert result["accounting"]["proof"]["kind"] == "TERMINAL"
    stage, = result["result"]["stages"]
    assert stage["exit_code"] == 0 and stage["stage"] == "extraction"
    assert set(stage["artifacts"]) == set(spec["stages"][0]["artifacts"])
    assert len(stage["artifacts"]) == 75
    client = connect()
    volume = modal.Volume.from_name(spec["output_volume"], create_if_missing=False)
    volume.hydrate(client=client)
    assert volume.object_id == spec["stage_identity"]["output_volume_id"]
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("result.json", "teardown.json", "rates.json", "call.json", "watchdog.log"):
        (destination / name).write_bytes((local / name).read_bytes())
    remote = spec["output_root"].removeprefix("/outputs") + "/extraction/"
    pins = {}
    for relative, pin in stage["artifacts"].items():
        if not relative.endswith(".json"):
            continue  # 99 GiB payload was streaming-hashed by guard before/after commit.
        raw = b"".join(volume.read_file(remote + relative))
        assert len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"]
        dest = destination / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        pins[relative] = pin
    cache = destination / "dual-grid-cache"
    complete = json.loads((cache / "complete.json").read_bytes())
    dataset_sha = hashlib.sha256((cache / "dataset.json").read_bytes()).hexdigest()
    assert complete["exit"] == 0 and complete["dataset_sha256"] == dataset_sha
    assert complete["identity"]["graph"]["device"] == "cuda"
    assert complete["identity"]["graph"]["grids"] == [4, 8]
    assert sum(v["count"] for v in complete["sessions"].values()) == 325004
    value = {"status": "PASS", "attempt_id": spec["attempt_id"], "app_id": result["accounting"]["app_id"],
             "output_volume_id": volume.object_id, "dataset_sha256": dataset_sha,
             "guard_verified_artifacts": len(stage["artifacts"]),
             "guard_verified_bytes": sum(v["bytes"] for v in stage["artifacts"].values()),
             "collected_metadata_pins": pins, "conservative_charge_usd": result["accounting"]["bound_usd"],
             "active_hold_usd": "0", "device": "cuda", "precision": "bf16 tower / fp16 features",
             "full_payload_verification": "accepted worker stage hashes before and after volume commit",
             "collected_at": time.time()}
    (destination / "collection.json").write_text(json.dumps(value, indent=2) + "\n")
    return value


if __name__ == "__main__":
    print(json.dumps(collect(sys.argv[1], sys.argv[2]), indent=2))
