"""Recover independently verified output artifacts without host/billing gates.

No stop, launch, deletion or scientific acceptance. Failed artifacts retain their
partial download and do not prevent collection of other valid artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import uuid


def relative(value):
    part = PurePosixPath(value)
    if (not value or part.is_absolute() or ".." in part.parts or "\\" in value
            or ":" in value or str(part) != value):
        raise ValueError("unsafe output path")
    return value


def collect(volume, *, volume_id, attempt, identity, destination):
    if volume.object_id != volume_id or identity["attempt_id"] != attempt:
        raise ValueError("output volume/attempt identity mismatch")
    relative(attempt)
    if "/" in attempt:
        raise ValueError("invalid attempt name")
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    if out.is_symlink():
        raise ValueError("collection destination symlink")
    inventory = volume.listdir(attempt, recursive=True)
    results = {}
    def destination_path(name):
        path = out / relative(name)
        if path.is_symlink() or not path.resolve().is_relative_to(out.resolve()):
            raise ValueError("collection path escape")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    for entry in inventory:
        path = entry.path.lstrip("/")
        if not path.startswith(attempt + "/"):
            continue
        name = path[len(attempt)+1:]
        if not (name.endswith("/completed.json") or name.endswith(".complete.json")):
            continue
        try:
            relative(name)
            chunks, size = [], 0
            for chunk in volume.read_file(path):
                size += len(chunk)
                if size > 4 * 1024 * 1024:
                    raise ValueError("completion receipt too large")
                chunks.append(chunk)
            raw = b"".join(chunks)
            receipt = json.loads(raw)
            if receipt.get("format") == "idm-complete-epoch-v1":
                scientific = {k: identity[k] for k in ("inputs_sha256", "recipe_sha256", "code_sha256")}
                if receipt["contract"]["identity"] != scientific:
                    raise ValueError("epoch scientific identity mismatch")
                artifacts = {receipt["artifact"]["path"]: receipt["artifact"]}
            else:
                if (receipt.get("format") != "modal-guard-stage-v1" or receipt["identity"] != identity
                        or receipt["exit_code"] != 0):
                    raise ValueError("stage identity mismatch")
                artifacts = receipt["artifacts"]
            destination_path(name).write_bytes(raw)
            results[name] = {"status": "receipt", "sha256": hashlib.sha256(raw).hexdigest()}
        except Exception as exc:
            results[name] = {"status": "rejected", "error": repr(exc)}
            continue
        parent = str(PurePosixPath(name).parent)
        for artifact, pin in artifacts.items():
            key = parent + "/" + artifact
            try:
                relative(artifact)
                target = destination_path(key)
                temporary = target.with_name(target.name + ".partial-" + uuid.uuid4().hex)
                digest, size = hashlib.sha256(), 0
                with temporary.open("xb") as stream:
                    for chunk in volume.read_file(attempt + "/" + key):
                        size += len(chunk)
                        if size > pin["bytes"]:
                            raise ValueError("artifact oversized")
                        digest.update(chunk)
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                if size != pin["bytes"] or digest.hexdigest() != pin["sha256"]:
                    raise ValueError("artifact hash/size mismatch")
                # Independently verify the local copy before publishing it.
                with temporary.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != pin["sha256"]:
                        raise ValueError("local artifact hash mismatch")
                os.replace(temporary, target)
                results[key] = {"status": "hash_verified", "bytes": size, "sha256": pin["sha256"]}
            except Exception as exc:
                results[key] = {"status": "rejected", "error": repr(exc)}
    report = {"volume_id": volume_id, "attempt": attempt, "artifacts": results,
              "execution_status": "not inferred", "accounting_status": "not queried",
              "scientific_acceptance": "not inferred from byte collection"}
    # Preserve separate collection receipts on repeated recovery attempts.
    (out / ("collection-" + uuid.uuid4().hex + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("volume-name", "volume-id", "identity", "identity-sha256", "destination"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    raw = Path(args.identity).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.identity_sha256:
        raise ValueError("collection identity pin mismatch")
    identity = json.loads(raw)
    from cloud.modal_guard.provider import connect
    import modal
    volume = modal.Volume.from_name(args.volume_name, create_if_missing=False)
    volume.hydrate(client=connect())
    report = collect(volume, volume_id=args.volume_id, attempt=identity["attempt_id"],
                     identity=identity, destination=args.destination)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
