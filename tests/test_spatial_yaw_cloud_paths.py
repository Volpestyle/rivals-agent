"""No torch or data required: exact identity across a relocated mount root."""
from pathlib import Path

import pytest

from policy.range_bc.spatial_yaw_cloud_cache import pixel_path


def test_resolved_mount_root_and_exact_view(monkeypatch, tmp_path):
    # Model /inputs being a native mount alias without requiring Windows symlink privileges.
    actual = tmp_path / "native" / "caches"
    (actual / "admitted").mkdir(parents=True)
    for view in ("global", "crop"):
        (actual / "admitted" / (view + ".u8")).write_bytes(b"synthetic")
    alias = tmp_path / "inputs" / "caches"
    original = Path.resolve

    def resolved(path, strict=False):
        if path.is_relative_to(alias):
            return original(actual / path.relative_to(alias), strict=strict)
        return original(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolved)
    source = alias / "admitted" / "global.u8"
    assert not source.resolve().is_relative_to(alias)  # original failed comparison
    assert pixel_path(source, "admitted", "global", cache_root=alias) == actual / "admitted/global.u8"
    assert pixel_path(source.resolve(), "admitted", "global", cache_root=alias) == source.resolve()
    with pytest.raises(ValueError, match="session/view"):
        pixel_path(source, "admitted", "crop", cache_root=alias)
    outside = tmp_path / "other.u8"
    outside.write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="session/view"):
        pixel_path(outside, "admitted", "global", cache_root=alias)
