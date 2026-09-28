"""Six original matched arms, assembled only from completed extraction evidence."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

RUNTIME = "/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/fullfit-02"
RELEASE = "5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd"


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def assemble(extraction_packet, collected, bindings, destination):
    from cloud.modal_guard.holds import bootstrap
    from cloud.modal_guard.release import verify
    from policy.range_bc.spatial_yaw_train import BASE_PINS
    extraction_packet, collected = Path(extraction_packet), Path(collected)
    collection = json.loads((collected / "collection.json").read_bytes())
    final = json.loads((collected / "result.json").read_bytes())
    assert collection["status"] == "PASS" and final["status"] == "COMPLETE"
    assert final["accounting"]["state"] == "TERMINAL" and collection["active_hold_usd"] == "0"
    assert final["accounting"]["stage_identity"]["output_volume_id"] == collection["output_volume_id"]
    assert final["accounting"]["release_sha256"] == RELEASE
    assert Decimal(collection["conservative_charge_usd"]) + Decimal("0.187193") <= Decimal("3")
    extraction_spec = json.loads((extraction_packet / "spec.json").read_bytes())
    assert final["accounting"]["attempt_id"] == extraction_spec["attempt_id"] == collection["attempt_id"]
    stage, = final["result"]["stages"]
    assert stage["exit_code"] == 0 and stage["stage"] == "extraction"
    assert stage["identity"] == {**extraction_spec["stage_identity"], "deadline_unix": final["accounting"]["stop_at"]}
    assert set(stage["artifacts"]) == set(extraction_spec["stages"][0]["artifacts"]) and len(stage["artifacts"]) == 75
    for relative in ("dual-grid-cache/complete.json", "dual-grid-cache/dataset.json", "dual-grid-cache/identity.json"):
        assert digest((collected / relative).read_bytes()) == stage["artifacts"][relative]["sha256"]
    complete = json.loads((collected / "dual-grid-cache/complete.json").read_bytes())
    dataset_sha = digest((collected / "dual-grid-cache/dataset.json").read_bytes())
    assert dataset_sha == complete["dataset_sha256"] == collection["dataset_sha256"]
    assert complete["identity"]["graph"]["device"] == "cuda"
    assert complete["identity"]["torch"] == "2.14.0+cu130"
    inventory = json.loads((extraction_packet / "source-inventory.json").read_bytes())
    source_assembly = json.loads((extraction_packet / "assembly.json").read_bytes())
    assert digest((extraction_packet / "source-inventory.json").read_bytes()) == source_assembly["source_inventory_sha256"]
    sources = {}
    for path, pin in inventory.items():
        raw = (extraction_packet / "code" / path).read_bytes()
        assert digest(raw) == pin
        sources[path] = raw
    manifest = json.loads(sources["cloud/yaw-payload-manifest.json"])
    fixed = Path(__file__).with_name("spatial_yaw_train.py").read_bytes()
    assert b"SpatialBatches(arrays, stride=64), SpatialBatches(dev, stride=64)" in fixed
    sources["cloud/yaw_payload/policy/range_bc/spatial_yaw_train.py"] = fixed
    manifest["files"]["policy/range_bc/spatial_yaw_train.py"] = digest(fixed)
    prior = json.loads(Path(__file__).with_name("failed-original").joinpath("summary.json").read_bytes())
    assert prior["old_active_holds_usd"] == "0"
    assert all(x["state"] == "TERMINAL" for x in prior["attempts"])
    assert Decimal(prior["total_prior_conservative_usd"]) + Decimal("14.971080") <= Decimal("24")
    bridge = Path(__file__).with_name("yaw_fit_entry.py").read_bytes()
    sources["cloud/yaw_fit_entry.py"] = bridge
    bindings = json.loads(Path(bindings).read_bytes())
    attempts = [f"yaw-fit-grid{grid}-s{seed}-20260927-02" for grid in (4, 8) for seed in (1, 2, 3)]
    assert set(bindings) == set(attempts) and len(set(bindings.values())) == 6
    assert all(v.startswith("vo-") for v in bindings.values())
    specs = []
    for grid in (4, 8):
        for seed, (base_sha, cutoff_sha) in BASE_PINS.items():
            attempt = f"yaw-fit-grid{grid}-s{seed}-20260927-02"
            science = {"tag": "EXPLORATORY", "grid": grid, "seed": seed, "epochs": 26, "updates": 15288,
                       "dataset_root": "/inputs/yaw-extract-20260927-02/extraction/dual-grid-cache",
                       "dataset_sha256": dataset_sha,
                       "base_checkpoint": f"/inputs/assets/candidate-s{seed}/epoch-26.pt", "base_sha256": base_sha,
                       "cutoff_receipt": f"/inputs/assets/candidate-s{seed}/evaluation.json", "cutoff_sha256": cutoff_sha}
            relative = "fit-specs/" + attempt + ".json"
            raw = encode(science)
            sources["cloud/yaw_payload/" + relative] = raw
            manifest["files"][relative] = digest(raw)
            specs.append((attempt, relative, digest(raw)))
    sources["cloud/yaw-payload-manifest.json"] = encode(manifest)
    payload_sha = digest(encode(manifest))
    envelope = {"mode": "EXPLORATORY_BOOTSTRAP", "campaign_id": "nitrogen-spatial-yaw-fullfit-02",
                "workload": "26epoch-frozenbase-dualgrid-yaw-sixfits-and-evaluation", "attempt_ids": attempts,
                "concurrency": 6, "campaign_cap_usd": "15", "startup_seconds": 300, "work_seconds": 3000,
                "cleanup_seconds": 120, "rate_usd_second": "0.0007178888888888888888888888889",
                "overhead_usd": "0.04"}
    hold = bootstrap(envelope)
    output = {"code/" + p: raw for p, raw in sources.items()}
    output["bootstrap.json"] = encode(envelope)
    pins = []
    for attempt, relative, spec_sha in specs:
        kwargs = {"payload_manifest_sha256": payload_sha, "spec_path": "/root/cloud/yaw_payload/" + relative,
                  "spec_sha256": spec_sha}
        spec = {"attempt_id": attempt, "app_name": "rivals-" + attempt, "lane": "explore-policy",
                "release_sha256": RELEASE, "run_cap_usd": "2.5", "hold": hold,
                "bootstrap_ref": {"path": RUNTIME + "/bootstrap.json", "sha256": digest(encode(envelope))},
                "image_id": final["accounting"]["image_id"],
                "input_volume": final["accounting"]["output_volume"], "input_volume_id": collection["output_volume_id"],
                "output_volume": "rivals-" + attempt + "-outputs", "output_root": "/outputs/" + attempt,
                "stage_identity": {"attempt_id": attempt, "code_sha256": payload_sha,
                                   "inputs_sha256": dataset_sha, "recipe_sha256": spec_sha,
                                   "output_volume_id": bindings[attempt]},
                "stages": [{"name": name, "module": "cloud.yaw_fit_entry", "function": function,
                            "artifacts": artifacts, "kwargs": kwargs}
                           for name, function, artifacts in (("fit", "fit", ["epoch-26.pt", "fit.json"]),
                                                              ("evaluation", "evaluate", ["evaluation.json"]))]}
        path = "specs/" + attempt + ".json"
        output[path] = encode(spec)
        pins.append({"path": RUNTIME + "/" + path, "sha256": digest(encode(spec))})
    output["source-inventory.json"] = encode({p: digest(raw) for p, raw in sources.items()})
    assembly = {"release_sha256": RELEASE, "payload_manifest_sha256": payload_sha,
                "source_inventory_sha256": digest(output["source-inventory.json"]),
                "source_extraction_inventory_sha256": digest((extraction_packet / "source-inventory.json").read_bytes()),
                "dataset_sha256": dataset_sha, "collection_sha256": digest((collected / "collection.json").read_bytes()),
                "specs": pins, "per_arm_reserved_usd": hold["reserved_usd"],
                "total_reserved_usd": str(6 * Decimal(hold["reserved_usd"])), "fits_cap_usd": "15",
                "campaign_cap_usd": "24", "full_fit_p95_claim": False, "launch_performed": False}
    output["assembly.json"] = encode(assembly)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    for relative, raw in output.items():
        path = dest / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    verify(dest / "code/cloud/modal_guard", RELEASE)
    return assembly


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("extraction_packet", "collected", "bindings", "destination"):
        p.add_argument(name)
    a = p.parse_args()
    print(json.dumps(assemble(**vars(a)), indent=2))
