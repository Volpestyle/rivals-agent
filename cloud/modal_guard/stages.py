"""Durable stage boundaries and explicit complete-epoch recovery."""
from __future__ import annotations

from pathlib import Path
import os

from .common import artifact, json_bytes, name, read, require, sha256


def claim(path, value):
    """Volume-safe exclusive create; a torn receipt is partial and never resumed.

    Modal Volumes reject hard links. O_EXCL preserves no-overwrite semantics;
    the caller commits only after a complete write/fsync. Readers validate the
    entire receipt and every artifact, so a partial JSON file grants no success.
    """
    with Path(path).open("xb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def identity_check(identity):
    require(set(identity) == {"attempt_id", "code_sha256", "inputs_sha256", "recipe_sha256",
                              "output_volume_id"}, "complete stage identity required")
    name(identity["attempt_id"])
    for key in ("code_sha256", "inputs_sha256", "recipe_sha256"):
        value = identity[key]
        require(isinstance(value, str) and len(value) == 64
                and all(c in "0123456789abcdef" for c in value), "invalid stage pin")
    require(isinstance(identity["output_volume_id"], str)
            and identity["output_volume_id"].startswith("vo-"), "output volume identity required")


def load(root, stage, identity, expected):
    identity_check(identity)
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "partial stage refused")
    marker = root / "completed.json"
    require(marker.is_file() and not marker.is_symlink(), "partial stage refused: no completion")
    before = sha256(marker)
    receipt = read(marker)
    require(receipt["format"] == "modal-guard-stage-v1" and receipt["stage"] == stage
            and receipt["identity"] == identity and receipt["exit_code"] == 0, "stage identity/completion mismatch")
    require(set(receipt["artifacts"]) == set(expected) and expected, "stage artifact closure mismatch")
    for relative, info in receipt["artifacts"].items():
        path = artifact(root, relative)
        require(path.is_file() and path.stat().st_size == info["bytes"]
                and sha256(path) == info["sha256"], "stage artifact hash mismatch")
    require(sha256(marker) == before, "completion changed during read")
    return receipt


def run(root, stage, identity, expected, compute, *, commit, reload, resume=None, resume_source=False):
    """Commit STARTED before compute; commit payload before publishing completion.

    commit/reload are the output Volume methods in Modal. One writer per stage;
    max_containers=1 remains required. On any exception leave STARTED/partial bytes.
    An explicit consumer validator may resume a complete epoch checkpoint; the
    guard never interprets partial weights; native Modal timeouts own execution.
    """
    identity_check(identity)
    name(stage)
    root = Path(root)
    reload()
    state = None
    if root.exists():
        if (root / "completed.json").exists():
            return load(root, stage, identity, expected)
        require(resume is not None and not root.is_symlink(), "partial stage refused: no checkpoint validator")
        require(read(root / "started.json") == {"identity": identity, "stage": stage}, "partial stage identity mismatch")
        state = resume(root)
        require(type(state) is dict and state, "partial stage has no validated complete epoch")
    else:
        root.mkdir(parents=True, exist_ok=False)
        claim(root / "started.json", {"identity": identity, "stage": stage})
        commit()  # durable before expensive compute
        if resume is not None and resume_source:
            state = resume(root)
            require(type(state) is dict and state, "prior source has no validated complete epoch")
    code = compute(root, resume_state=state) if resume is not None else compute(root)
    require(code == 0 and type(code) is int, "stage failed; partial output retained")
    files = {}
    for relative in expected:
        require(relative not in ("completed.json", "started.json"), "reserved stage filename")
        path = artifact(root, relative)
        require(path.is_file(), "missing stage output")
        files[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    require(files, "no stage artifacts")
    commit()
    receipt = {"format": "modal-guard-stage-v1", "stage": stage, "identity": identity,
               "exit_code": 0, "artifacts": files}
    claim(root / "completed.json", receipt)
    commit()
    return load(root, stage, identity, expected)
