"""Fresh dropout packets from frozen prior payload + exact committed release/science."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

SCIENCE = "51db7ea"
RUNTIME = "/Users/james/dev/range-bc-data/explore/nitrogen-yaw-dropout-20260928"
RATE = "0.0007178888888888888888888888889"


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(commit, name):
    return subprocess.check_output(["git", "show", commit+":"+name])


def assemble(original, bindings, destination, guard_commit, release_sha, mode):
    from cloud.modal_guard.holds import bootstrap
    from cloud.modal_guard.release import verify
    original, destination = Path(original), Path(destination)
    old = json.loads((original/"assembly.json").read_bytes())
    raw = (original/"source-inventory.json").read_bytes()
    assert sha(raw) == old["source_inventory_sha256"]
    sources = {}
    for name, pin in json.loads(raw).items():
        data = (original/"code"/name).read_bytes()
        assert sha(data) == pin
        if not name.startswith("cloud/modal_guard/"):
            sources[name] = data
    release_raw = git(guard_commit, "cloud/modal_guard/RELEASE.json")
    assert sha(release_raw) == release_sha
    manifest = json.loads(release_raw)
    assert manifest["version"] == "1.0.5" and manifest["sdk"] == "1.5.5"
    for name, pin in manifest["files"].items():
        raw = git(guard_commit, "cloud/modal_guard/"+name)
        assert sha(raw) == pin
        sources["cloud/modal_guard/"+name] = raw
    sources["cloud/modal_guard/RELEASE.json"] = release_raw
    payload = json.loads(sources["cloud/yaw-payload-manifest.json"])
    for filename in ("spatial_yaw.py", "spatial_yaw_train.py", "spatial_yaw_dropout_probe.py"):
        name = "policy/range_bc/"+filename
        data = git(SCIENCE, name)
        sources["cloud/yaw_payload/"+name] = data
        payload["files"][name] = sha(data)
    # Extend a new bridge copy; the old packet and accepted guard are untouched.
    sources["cloud/yaw_fit_entry.py"] += b'\n\ndef probe(root, *, payload_manifest_sha256, spec_path, spec_sha256):\n    verify_payload(payload_manifest_sha256)\n    worker = importlib.import_module("policy.range_bc.spatial_yaw_dropout_probe")\n    return worker.run_probe(root, spec_path=spec_path, spec_sha256=spec_sha256)\n'
    recipes = []
    for seed in (1, 2, 3):
        recipe = json.loads(sources[f"cloud/yaw_payload/fit-specs/yaw-fit-grid4-s{seed}-20260927-02.json"])
        assert recipe["grid"] == 4 and recipe["seed"] == seed and recipe["epochs"] == 26 and recipe["updates"] == 15288
        assert "cache_mode" not in recipe and "hidden_dropout" not in recipe
        recipe["hidden_dropout"] = .5
        name = f"dropout-specs/seed-{seed}.json"
        data = encode(recipe)
        sources["cloud/yaw_payload/"+name] = data
        payload["files"][name] = sha(data)
        recipes.append((name, sha(data)))
    sources["cloud/yaw-payload-manifest.json"] = encode(payload)
    payload_sha = sha(encode(payload))
    attempts = [f"yaw-dropout-{mode}-s{s}-20260928-01" for s in (1, 2, 3)]
    bindings = json.loads(Path(bindings).read_bytes())
    assert set(bindings) == set(attempts) and len(set(bindings.values())) == 3
    assert all(v.startswith("vo-") and "placeholder" not in v.lower() for v in bindings.values())
    probe = mode == "probe"
    envelope = dict(mode="EXPLORATORY_BOOTSTRAP", campaign_id="nitrogen-yaw-dropout-"+mode+"-20260928-01",
        workload="three-app-dropout-synthetic-shakedown" if probe else "three-26epoch-grid4-dropout-fits-and-evaluation",
        attempt_ids=attempts, concurrency=3, campaign_cap_usd="1.23" if probe else "5.02",
        startup_seconds=300, work_seconds=120 if probe else 1800, cleanup_seconds=120,
        rate_usd_second=RATE, overhead_usd="0.02" if probe else "0.05")
    hold = bootstrap(envelope)
    assert hold["reserved_usd"] == ("0.407660" if probe else "1.643714")
    assert Decimal("1.222980")+Decimal("4.931142") == Decimal("6.154122") < Decimal("6.25")
    root = RUNTIME+"/"+mode+"-01"
    output = {"code/"+name: data for name, data in sources.items()}
    output["bootstrap.json"] = encode(envelope)
    pins = []
    for seed, (attempt, (relative, digest)) in enumerate(zip(attempts, recipes), 1):
        spec = json.loads((original/f"specs/yaw-fit-grid4-s{seed}-20260927-02.json").read_bytes())
        assert spec["image_id"] == "im-FNjy4v5u4XYF29SBGvT0KD"
        assert spec["input_volume_id"] == "vo-ujapSF2Htu9GfKAXEyXH70"
        spec.update(attempt_id=attempt, app_name="rivals-"+attempt, release_sha256=release_sha,
            run_cap_usd="0.41" if probe else "1.65", hold=hold,
            bootstrap_ref={"path": root+"/bootstrap.json", "sha256": sha(output["bootstrap.json"])},
            output_volume="rivals-"+attempt+"-outputs", output_root="/outputs/"+attempt,
            stage_identity={**spec["stage_identity"], "attempt_id": attempt, "code_sha256": payload_sha,
                "recipe_sha256": digest, "output_volume_id": bindings[attempt]})
        kwargs = dict(payload_manifest_sha256=payload_sha, spec_path="/root/cloud/yaw_payload/"+relative,
                      spec_sha256=digest)
        if probe:
            spec["stages"] = [dict(name="probe", module="cloud.yaw_fit_entry", function="probe",
                                   artifacts=["probe-yaw.pt", "probe.json"], kwargs=kwargs)]
        else:
            for stage in spec["stages"]:
                stage["kwargs"] = kwargs
        name = "specs/"+attempt+".json"
        output[name] = encode(spec)
        pins.append({"path": root+"/"+name, "sha256": sha(output[name])})
    output["source-inventory.json"] = encode({k: sha(v) for k, v in sources.items()})
    assembly = dict(release_sha256=release_sha, guard_commit=guard_commit, source_commit=SCIENCE, mode=mode,
        payload_manifest_sha256=payload_sha, source_inventory_sha256=sha(output["source-inventory.json"]),
        specs=pins, per_arm_reserved_usd=hold["reserved_usd"], total_reserved_usd=str(3*Decimal(hold["reserved_usd"])),
        all_six_reserved_usd="6.154122", new_campaign_cap_usd="6.25", prior_yaw_settled_usd="18.666509",
        launch_performed=False, full_fit_p95_claim=False)
    output["assembly.json"] = encode(assembly)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in output.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify(destination/"code/cloud/modal_guard", release_sha)
    return assembly


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("original", "bindings", "destination", "guard_commit", "release_sha"):
        p.add_argument(name)
    p.add_argument("mode", choices=("probe", "fit"))
    a = p.parse_args()
    print(json.dumps(assemble(**vars(a)), indent=2))
