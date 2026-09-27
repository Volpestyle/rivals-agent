"""Offline-only packet assembly. No Modal imports, API writes or launch action."""
import argparse
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

GUARD_COMMIT = "c6004073f2bcefce006f28422b42170442ca8b60"
APP_COMMIT = "3902167"
RELEASE = "732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce"
BASE_IMAGE = "im-FNjy4v5u4XYF29SBGvT0KD"
INPUT_VOLUME = "rivals-explore-chunks-20260927"
INPUT_VOLUME_ID = "vo-K5FeMtunP9vFG2mx8HVn0p"
INPUT_SPEC = "docs/evidence/nitrogen-spatial-yaw-20260927/probe-inputs.json"
INPUT_SHA = "c7061ddbe65a4d13dbb1cec6876b7df4fc6e20c84ced4bb5ea7d724c8025fe2d"
PROBE_SHA = "21d6a8f258a28ac8f27e4953765d7167b220f7f87d1de196c57acb5d6018eb84"
RATE = "0.0007178888888888888888888888889"


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(repo, commit, path):
    return subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + path])


def put(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def pinned(ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("concrete pinned reference required")
    raw = Path(ref["path"]).read_bytes()
    if digest(raw) != ref["sha256"]:
        raise ValueError("reference bytes differ")
    return json.loads(raw)


def assemble(repo, destination, runtime_root, *, bindings_ref=None):
    from cloud.modal_guard.holds import bootstrap
    from cloud.modal_guard.release import verify
    repo, destination = Path(repo).resolve(), Path(destination).resolve()
    runtime_root = PurePosixPath(runtime_root)
    if not str(runtime_root).startswith("/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/"):
        raise ValueError("wrong Mac campaign runtime root")
    binding = pinned(bindings_ref) if bindings_ref else None
    if binding:
        if binding["image_id"] != BASE_IMAGE or binding["release_sha256"] != RELEASE:
            raise ValueError("image/release binding differs")
        metadata = pinned(binding["image_metadata_ref"])
        if metadata["image_id"] != BASE_IMAGE:
            raise ValueError("image metadata differs")
        if len(binding["outputs"]) != 6 or len({x["id"] for x in binding["outputs"]}) != 6:
            raise ValueError("six distinct output volumes required")
        for slot, output in enumerate(binding["outputs"], 1):
            if output["name"] != "rivals-yaw-probe-20260927-" + str(slot).zfill(2) + "-outputs" or not output["id"].startswith("vo-"):
                raise ValueError("wrong output volume binding")
    # Validate all frozen inputs before creating even a draft destination.
    release_bytes = blob(repo, GUARD_COMMIT, "cloud/modal_guard/RELEASE.json")
    if digest(release_bytes) != RELEASE:
        raise ValueError("guard release differs")
    release = json.loads(release_bytes)
    sources = {"cloud/modal_guard/RELEASE.json": release_bytes}
    for file, sha in release["files"].items():
        raw = blob(repo, GUARD_COMMIT, "cloud/modal_guard/" + file)
        if digest(raw) != sha:
            raise ValueError("guard source differs")
        sources["cloud/modal_guard/" + file] = raw
    app_commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", APP_COMMIT], text=True).strip()
    app_paths = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", app_commit,
                                         "policy/range_bc", "agent"], text=True).splitlines()
    app_paths = sorted([p for p in app_paths if p.endswith(".py")] + ["policy/__init__.py", INPUT_SPEC])
    archive = subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(repo), "archive", "--format=tar", app_commit, "--", *app_paths])
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        payload = {member.name: stream.extractfile(member).read() for member in stream.getmembers()
                   if member.isfile() and member.name in app_paths}
    if set(payload) != set(app_paths):
        raise ValueError("git archive source closure incomplete")
    if digest(payload[INPUT_SPEC]) != INPUT_SHA or digest(payload["policy/range_bc/spatial_yaw_probe.py"]) != PROBE_SHA:
        raise ValueError("worker/input spec differs")
    if payload["policy/range_bc/spatial_yaw.py"] != blob(repo, "b2010fd", "policy/range_bc/spatial_yaw.py"):
        raise ValueError("FrozenBaseYaw differs from owner's b2010fd")
    for path, raw in payload.items():
        sources["cloud/yaw_payload/" + path] = raw
    payload_manifest = {"app_commit": app_commit, "input_spec": INPUT_SPEC,
                        "files": {p: digest(raw) for p, raw in payload.items()}}
    sources["cloud/yaw-payload-manifest.json"] = encode(payload_manifest)
    payload_sha = digest(sources["cloud/yaw-payload-manifest.json"])
    sources["cloud/yaw_entry.py"] = Path(__file__).with_name("yaw_entry.py").read_bytes()
    sources["scripts/job_status.py"] = blob(repo, GUARD_COMMIT, "scripts/job_status.py")
    attempts = ["yaw-probe-20260927-" + str(i).zfill(2) for i in range(1, 7)]
    envelope = {"mode": "EXPLORATORY_BOOTSTRAP", "campaign_id": "nitrogen-spatial-yaw-probe-20260927-01",
                "workload": "yaw-launch-probe-not-fullfit", "attempt_ids": attempts, "concurrency": 6,
                "campaign_cap_usd": "3", "startup_seconds": 300, "work_seconds": 180,
                "cleanup_seconds": 120, "rate_usd_second": RATE, "overhead_usd": "0.05"}
    hold = bootstrap(envelope)
    destination.mkdir(parents=True, exist_ok=False)
    for path, raw in sources.items():
        put(destination, "code/" + path, raw)
    verify(destination / "code/cloud/modal_guard", RELEASE)
    inventory = {path: digest(raw) for path, raw in sources.items()}
    put(destination, "source-inventory.json", encode(inventory))
    put(destination, "bootstrap.json", encode(envelope))
    recipe_sha = digest(encode({"envelope": envelope, "seconds": 110, "artifacts": ["probe.json", "probe-yaw.pt"]}))
    spec_pins = []
    for slot, attempt in enumerate(attempts, 1):
        output = binding["outputs"][slot - 1] if binding else {"name": "rivals-yaw-probe-20260927-" + str(slot).zfill(2) + "-outputs", "id": None}
        spec = {"attempt_id": attempt, "app_name": "rivals-" + attempt, "lane": "explore-policy",
                "release_sha256": RELEASE, "run_cap_usd": "0.5", "hold": hold,
                "bootstrap_ref": {"path": str(runtime_root / "bootstrap.json"), "sha256": digest(encode(envelope))},
                "image_id": BASE_IMAGE, "input_volume": INPUT_VOLUME, "input_volume_id": INPUT_VOLUME_ID,
                "output_volume": output["name"], "output_root": "/outputs/" + attempt,
                "stage_identity": {"attempt_id": attempt, "code_sha256": payload_sha,
                                   "inputs_sha256": INPUT_SHA, "recipe_sha256": recipe_sha, "output_volume_id": output["id"]},
                "stages": [{"name": "probe", "module": "cloud.yaw_entry", "function": "run",
                            "artifacts": ["probe.json", "probe-yaw.pt"],
                            "kwargs": {"payload_manifest_sha256": payload_sha, "slot": slot}}]}
        relative = "specs/" + attempt + ".json"
        put(destination, relative, encode(spec))
        spec_pins.append({"path": str(runtime_root / relative), "sha256": digest(encode(spec))})
    result = {"status": "ASSEMBLED" if binding else "DRAFT_UNRESOLVED_OUTPUTS_AND_IMAGE_EVIDENCE",
              "runtime_root": str(runtime_root), "code_root": str(runtime_root / "code"), "release_sha256": RELEASE,
              "image_id": BASE_IMAGE, "image_route": "existing image plus SDK immutable entrypoint source mount",
              "new_image_builds": 0, "setup_compute_usd": "0", "probe_reserved_usd": str(6 * Decimal(hold["reserved_usd"])),
              "campaign_cap_usd": "24", "workspace_cap_usd": "100", "bindings_ref": bindings_ref,
              "payload_manifest_sha256": payload_sha, "source_inventory_sha256": digest(encode(inventory)),
              "specs": spec_pins, "launch_performed": False}
    put(destination, "assembly.json", encode(result))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--runtime-root", required=True)
    p.add_argument("--bindings")
    p.add_argument("--bindings-sha256")
    args = p.parse_args()
    ref = {"path": args.bindings, "sha256": args.bindings_sha256} if args.bindings else None
    print(json.dumps(assemble(args.repo, args.destination, args.runtime_root, bindings_ref=ref), indent=2))
