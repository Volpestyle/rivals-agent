"""Real filesystem namespace checks, without a corpus, GPU or Modal account."""
import os
from pathlib import Path

import pytest

from policy.range_bc import explore_mounts as mounts


@pytest.fixture
def aliases(tmp_path, monkeypatch):
    if os.name == "nt":
        readlink = Path.readlink
        monkeypatch.setattr(Path, "readlink", lambda p: Path(str(readlink(p)).removeprefix("\\\\?\\")))
    physical = tmp_path / "volumes"
    physical.mkdir()
    pins = {}
    for name in ("inputs", "outputs"):
        target = physical / ("vo-" + name)
        target.mkdir()
        alias = tmp_path / name
        alias.symlink_to(target, target_is_directory=True)
        pins[str(alias)] = target.name
    monkeypatch.setattr(mounts, "MOUNT_ROOTS", tuple(pins))
    monkeypatch.setattr(mounts, "MODAL_VOLUMES", physical)
    return tmp_path, physical, pins


def test_authenticated_alias_preserved_for_read_and_new_output(aliases):
    root, _, pins = aliases
    targets = mounts.check_mounts(pins)
    source = root / "inputs" / "file"
    source.write_text("payload")
    assert mounts.logical_path(source, targets) == source
    assert source.resolve() != source
    assert mounts.logical_path(source, targets).read_text() == "payload"
    output = root / "outputs" / "fresh" / "result.json"
    assert mounts.logical_path(output, targets) == output


@pytest.mark.parametrize("mutation", ["wrong-volume", "missing-pin", "duplicate", "bad-id",
                                      "directory", "relative-alias", "target-symlink"])
def test_mount_authentication_refuses_invalid_aliases(aliases, mutation):
    root, physical, pins = aliases
    output = root / "outputs"
    if mutation == "wrong-volume":
        pins[str(output)] = "vo-other"
    elif mutation == "missing-pin":
        pins.pop(str(output))
    elif mutation == "duplicate":
        pins[str(output)] = "vo-inputs"
    elif mutation == "bad-id":
        pins[str(output)] = "vo-../escape"
    elif mutation == "target-symlink":
        (physical / "vo-outputs").rmdir()
        (physical / "vo-outputs").symlink_to(physical / "vo-inputs", target_is_directory=True)
    else:
        output.unlink()
        if mutation == "directory":
            output.mkdir()
        else:
            output.symlink_to(Path("volumes") / "vo-outputs", target_is_directory=True)
    with pytest.raises(ValueError):
        mounts.check_mounts(pins)


@pytest.mark.parametrize("mutation", ["traversal", "physical", "relative", "child-symlink"])
def test_logical_path_refuses_escape_before_payload_io(aliases, mutation):
    root, physical, pins = aliases
    targets = mounts.check_mounts(pins)
    if mutation == "traversal":
        path = root / "outputs" / ".." / "escape"
    elif mutation == "physical":
        path = physical / "vo-outputs" / "file"
    elif mutation == "relative":
        path = Path("outputs/file")
    else:
        (root / "outputs" / "child").symlink_to(physical / "vo-outputs", target_is_directory=True)
        path = root / "outputs" / "child" / "file"
    with pytest.raises(ValueError):
        mounts.logical_path(path, targets)
