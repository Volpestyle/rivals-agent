"""Offline closure for one capped dual-grid CUDA extraction; no cloud calls."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

RELEASE = "5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd"
GUARD = "80d944bd8732103f2de1ad67dd83c4009b6bb7f2"
ATTEMPT = "yaw-extract-20260927-01"
RUNTIME = "/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/extract-01"
BASE = "im-FNjy4v5u4XYF29SBGvT0KD"


def encode(v):
    return (json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def assemble(destination, commit, volume_id):
    from cloud.modal_guard.holds import bootstrap
    from cloud.modal_guard.release import verify
    assert volume_id.startswith("vo-")
    here = Path(__file__).parent
    def blob(rev, path):
        return subprocess.check_output(["git", "show", rev + ":" + path])
    release = blob(GUARD, "cloud/modal_guard/RELEASE.json")
    assert sha(release) == RELEASE
    sources = {"cloud/modal_guard/RELEASE.json": release}
    for name, pin in json.loads(release)["files"].items():
        raw = blob(GUARD, "cloud/modal_guard/" + name)
        assert sha(raw) == pin
        sources["cloud/modal_guard/" + name] = raw
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit,
                                     "policy/range_bc", "agent"], text=True).splitlines()
    paths = [p for p in paths if p.endswith(".py")] + ["policy/__init__.py",
        "data/human/sealed-denylist.v2.json", "data/human/patch-equivalence.json",
        "docs/evidence/nitrogen-nohistory-confirm-20260927/recovery-inputs.json"]
    archive = subprocess.check_output(["git", "archive", "--format=tar", commit, "--", *paths])
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        payload = {m.name: stream.extractfile(m).read() for m in stream.getmembers() if m.isfile()}
    assert set(payload) == set(paths)
    metadata = {"registry.json": (here / "session-splits.corpus.json").read_bytes(),
                "tally.json": (here / "tally.json").read_bytes()}
    assert sha(metadata["registry.json"]) == "1c9e2c671b14e9d1ea8bcefd4703668a039ecac946d2f5ece768746e67118a13"
    assert sha(metadata["tally.json"]) == "2ef89830984dcbbb48d7d2274d5549e541c7129353c0b06c39b0228919119602"
    payload.update(metadata)
    prefix = "/root/cloud/yaw_payload/"
    inputs = "docs/evidence/nitrogen-nohistory-confirm-20260927/recovery-inputs.json"
    payload[inputs] = (here / "recovery-inputs.runtime.json").read_bytes()
    assert sha(payload[inputs]) == "14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21"
    recipe = {"tag": "EXPLORATORY", "device": "cuda", "grids": [4, 8], "batch": 32,
              "manifest": "/inputs/manifest-modal.json", "inputs": prefix + inputs,
              "registry": prefix + "registry.json", "registry_sha256": sha(metadata["registry.json"]),
              "tally": prefix + "tally.json", "tally_sha256": sha(metadata["tally.json"]),
              "vision": "/outputs/assets/vision.safetensors", "vision_config": "/outputs/assets/config.json"}
    payload["extraction-spec.json"] = encode(recipe)
    manifest = {"app_commit": commit, "input_spec": "extraction-spec.json",
                "files": {p: sha(raw) for p, raw in payload.items()}}
    sources.update({"cloud/yaw_payload/" + p: raw for p, raw in payload.items()})
    sources["cloud/yaw-payload-manifest.json"] = encode(manifest)
    sources["cloud/yaw_entry.py"] = (here / "yaw_entry.py").read_bytes()
    sources["scripts/job_status.py"] = blob(GUARD, "scripts/job_status.py")
    payload_sha = sha(encode(manifest))
    envelope = {"mode": "EXPLORATORY_BOOTSTRAP", "campaign_id": "nitrogen-spatial-yaw-extraction-01",
                "workload": "full-cohort-dual-grid-cuda-extraction", "attempt_ids": [ATTEMPT], "concurrency": 1,
                "campaign_cap_usd": "2", "startup_seconds": 300, "work_seconds": 2200,
                "cleanup_seconds": 120, "rate_usd_second": "0.0007178888888888888888888888889",
                "overhead_usd": "0.10"}
    hold = bootstrap(envelope)
    artifacts = ["pixels-verified.json", "extraction.json", "dual-grid-cache/identity.json",
                 "dual-grid-cache/dataset.json", "dual-grid-cache/complete.json"]
    for sid in sorted(json.loads(payload[inputs])["cohort"]):
        for name in ["frame_ids.npy", "global-4.npy", "crop-4.npy", "global-8.npy", "crop-8.npy",
                     "labels.pt", "completed.json"]:
            artifacts.append("dual-grid-cache/" + sid + "/" + name)
    spec = {"attempt_id": ATTEMPT, "app_name": "rivals-" + ATTEMPT, "lane": "explore-policy",
            "release_sha256": RELEASE, "run_cap_usd": "2", "hold": hold,
            "bootstrap_ref": {"path": RUNTIME + "/bootstrap.json", "sha256": sha(encode(envelope))},
            "image_id": BASE, "input_volume": "rivals-explore-chunks-20260927",
            "input_volume_id": "vo-K5FeMtunP9vFG2mx8HVn0p", "output_volume": "rivals-" + ATTEMPT + "-outputs",
            "output_root": "/outputs/" + ATTEMPT,
            "stage_identity": {"attempt_id": ATTEMPT, "code_sha256": payload_sha,
                               "inputs_sha256": sha(payload[inputs]), "recipe_sha256": sha(encode(recipe)),
                               "output_volume_id": volume_id},
            "stages": [{"name": "extraction", "module": "cloud.yaw_entry", "function": "run",
                        "artifacts": artifacts, "kwargs": {"payload_manifest_sha256": payload_sha}}]}
    inventory = {p: sha(raw) for p, raw in sources.items()}
    output = {"code/" + p: raw for p, raw in sources.items()}
    output.update({"source-inventory.json": encode(inventory), "bootstrap.json": encode(envelope),
                   "spec.json": encode(spec), "verify_native_mount.py": (here / "verify_native_mount.py").read_bytes()})
    assembly = {"release_sha256": RELEASE, "image_id": BASE, "app_commit": commit,
                "payload_manifest_sha256": payload_sha, "source_inventory_sha256": sha(encode(inventory)),
                "specs": [{"path": RUNTIME + "/spec.json", "sha256": sha(encode(spec))}],
                "reserved_usd": hold["reserved_usd"], "campaign_cap_usd": "24", "fits_allocation_usd": "18",
                "allocation": {"extraction": "2", "six_fits": "15", "setup_storage_margin": "1"},
                "image_route": "existing pinned CUDA image plus immutable native SDK source mount",
                "full_fit_p95_claim": False, "new_image_builds": 0}
    output["assembly.json"] = encode(assembly)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    for path, raw in output.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    verify(dest / "code/cloud/modal_guard", RELEASE)
    return assembly


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("destination")
    p.add_argument("commit")
    p.add_argument("volume_id")
    a = p.parse_args()
    print(json.dumps(assemble(a.destination, a.commit, a.volume_id), indent=2))
