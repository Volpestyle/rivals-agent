"""Metadata-only inventory gate. Requires a separately reviewed hash-once witness."""
import hashlib
import json
import os
import pathlib
import stat

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def inventory(root):
    root=pathlib.Path(root)
    rows=[]
    def walk(directory,prefix):
        with os.scandir(directory) as scan:
            entries=sorted(scan,key=lambda e:e.name)
        for entry in entries:
            if entry.name in (".","..") or "/" in entry.name or "\\" in entry.name:
                raise ValueError("unsafe entry")
            relative=prefix+entry.name
            info=entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                rows.append({"path":relative,"type":"directory"})
                walk(entry.path,relative+"/")
            elif stat.S_ISREG(info.st_mode):
                rows.append({"path":relative,"type":"file","bytes":info.st_size,"mtime_ns":info.st_mtime_ns})
            else:
                raise ValueError("symlink or special entry: "+relative)
    walk(root,"")
    return sorted(rows,key=lambda r:r["path"])

def verify_metadata(root,witness_bytes,expected_sha,expected_volume_id,expected_version):
    if hashlib.sha256(witness_bytes).hexdigest()!=expected_sha:
        raise ValueError("witness pin differs")
    witness=json.loads(witness_bytes)
    if (witness.get("format")!="cm3-volume-version-witness-v1" or witness.get("status")!="PASS"
        or witness.get("scheme")!="manifest+exclusive-writer-generation"
        or witness.get("provider_commit_id") is not None):
        raise ValueError("unrecognized witness")
    if witness.get("volume_id")!=expected_volume_id or witness.get("version_id")!=expected_version:
        raise ValueError("volume generation differs")
    root=pathlib.Path(root);target=pathlib.Path("/__modal/volumes")/expected_volume_id
    if str(root)!="/inputs" or not root.is_symlink() or root.readlink()!=target or root.resolve(strict=True)!=target:
        raise ValueError("mount identity differs")
    if target.is_symlink() or not target.is_dir():
        raise ValueError("invalid volume target")
    actual=inventory(root)
    if actual!=witness["inventory"]:
        raise ValueError("mounted size/mtime inventory differs; no automatic rehash")
    return {"status":"PASS","volume_id":expected_volume_id,"version_id":expected_version,
            "witness_sha256":expected_sha,"inventory_sha256":hashlib.sha256(canonical(actual)).hexdigest(),
            "payload_bytes_read":0}
