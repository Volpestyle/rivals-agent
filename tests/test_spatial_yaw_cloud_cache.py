"""Synthetic CPU extraction exercises the paid callback's shared science path."""
import json
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from policy.range_bc import fixture, steps, train
from policy.range_bc.spatial_yaw_cache import sha
from policy.range_bc.spatial_yaw_cloud_cache import extract_dual
from policy.range_bc.spatial_yaw_data import SpatialArrays


def test_one_tower_pass_both_grids_labels_and_partial_refusal(tmp_path):
    torch.set_num_threads(2)
    header, rows = fixture.session("synthetic-yaw", runs=(8,), seed=4, unknown_mouse=0)
    session = steps.Session("synthetic", "a" * 64, header, rows)
    frames = np.zeros((8, 2, 2, 3), dtype=np.uint8)
    arr = train.SessionArrays(session, (frames, frames, frames, list(range(8)), {}))
    calls = []

    def tower(pixel_values):
        calls.append(len(pixel_values))
        return SimpleNamespace(last_hidden_state=torch.arange(256).float()[None, :, None]
                               .expand(len(pixel_values), -1, 1024) / 256)

    root = tmp_path / "cache"
    result = extract_dual([arr], [], tower, root, {"device": "cpu"}, lambda _: None,
                          device="cpu", batch=4)
    assert calls == [4, 4, 4, 4]  # two batches, two views; never a second grid pass
    assert result["dataset_sha256"] == sha(root / "dataset.json")
    dataset = json.loads((root / "dataset.json").read_text())
    for grid in (4, 8):
        restored = SpatialArrays(root, dataset["sessions"][0], grid)
        assert torch.equal(restored.act, arr.act)
        assert torch.equal(restored.camera, arr.camera)
        assert restored.frames(torch.tensor([0]))[0].shape == (1, 16384 + grid * grid * 1024)
    with pytest.raises(FileExistsError):
        extract_dual([arr], [], tower, root, {"device": "cpu"}, lambda _: None, device="cpu")
    assert calls == [4, 4, 4, 4]
    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises(FileExistsError):
        extract_dual([arr], [], tower, partial, {}, lambda _: None, device="cpu")
