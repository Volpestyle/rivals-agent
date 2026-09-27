from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from policy.range_bc import steps, vocab
from policy.range_bc.explore_encoder import EncoderPolicy, pool_tokens
from policy.range_bc.model import Config
from policy.range_bc.spatial_yaw import FrozenBaseYaw, SpatialYawReadout, pool_grid
from policy.range_bc.spatial_yaw_cache import compact_indices, extract_session, frame_ids, verify_stage


@pytest.fixture(autouse=True)
def cpu_threads():
    torch.set_num_threads(2)


def test_grid_pooling_preserves_row_major_geometry_and_legacy_four():
    yy, xx = torch.meshgrid(torch.arange(16), torch.arange(16), indexing="ij")
    pixels = (100 * yy + xx).float().reshape(1, 256, 1).expand(2, -1, 1024).clone()
    assert torch.equal(pool_grid(pixels, 4), pool_tokens(pixels))
    for grid in (4, 8):
        got = pool_grid(pixels, grid).reshape(2, grid, grid, 1024)
        cell = 16 // grid
        for y in range(grid):
            for x in range(grid):
                expected = 100 * (y * cell + (cell - 1) / 2) + x * cell + (cell - 1) / 2
                assert torch.all(got[:, y, x] == expected)
    with pytest.raises(ValueError):
        pool_grid(pixels, 16)


@pytest.mark.parametrize("grid", (4, 8))
def test_readout_capacity_positions_and_initial_residual(grid):
    readout = SpatialYawReadout(grid)
    assert sum(p.numel() for p in readout.parameters()) == 201187
    assert readout.positions[0, 0] < readout.positions[1, 0]
    assert readout.positions[0, 1] == readout.positions[1, 1]
    assert readout.positions[grid, 1] > readout.positions[0, 1]
    x = torch.randn(1, 2, grid * grid * 1024)
    hidden = torch.randn(1, 2, 512, requires_grad=True)
    value = readout(x, x, hidden)
    assert value.shape == (1, 2, vocab.CAMERA_CLASSES) and torch.count_nonzero(value) == 0
    value.sum().backward()
    assert hidden.grad is None


def test_yaw_updates_leave_actions_pitch_frozen_tensors_and_causality_unchanged():
    torch.manual_seed(1)
    base = EncoderPolicy(Config(history=False, hud=False))
    model = FrozenBaseYaw(base, 8).train()
    assert not model.base.training
    original = {k: v.clone() for k, v in base.state_dict().items()}
    g, c = torch.randn(1, 3, 16384), torch.randn(1, 3, 16384)
    sg, sc = torch.randn(1, 3, 65536), torch.randn(1, 3, 65536)
    prev = torch.randn(1, 3, steps.PREV_DIM)
    with torch.no_grad():
        expected_a, expected_c, _ = base(g, c, None, prev)
    actions, camera, _ = model(g, c, sg, sc, prev)
    assert torch.equal(actions, expected_a) and torch.equal(camera, expected_c)
    opt = torch.optim.AdamW(model.yaw.parameters(), lr=.01)
    for _ in range(2):
        opt.zero_grad()
        _, camera, _ = model(g, c, sg, sc, prev)
        torch.nn.functional.cross_entropy(camera[:, :, 0].flatten(0, 1), torch.zeros(3, dtype=torch.long)).backward()
        opt.step()
    actions, camera, _ = model(g, c, sg, sc, prev)
    assert torch.equal(actions, expected_a)
    assert torch.equal(camera[:, :, 1], expected_c[:, :, 1])
    assert not torch.equal(camera[:, :, 0], expected_c[:, :, 0])
    assert all(p.grad is None for p in base.parameters())
    assert all(torch.equal(v, original[k]) for k, v in base.state_dict().items())
    _, prefix, _ = model(g[:, :2], c[:, :2], sg[:, :2], sc[:, :2], prev[:, :2])
    assert torch.allclose(prefix, camera[:, :2], atol=1e-6)


def test_compact_lookup_preserves_duplicates_order_and_refuses_missing():
    assert compact_indices([2, 5, 9], [9, 2, 5, 2]).tolist() == [2, 0, 1, 0]
    for ids in ([1], [4], [10]):
        with pytest.raises(ValueError, match="absent"):
            compact_indices([2, 5, 9], ids)
    with pytest.raises(ValueError, match="invalid"):
        compact_indices([5, 2], [2])


def synthetic_array():
    return SimpleNamespace(session=SimpleNamespace(session_id="synthetic"), runs=[(0, 3)],
                           row_frame=torch.tensor([3, 1, 3]),
                           global_frames=np.zeros((5, 4, 4, 3), dtype=np.uint8),
                           crop_frames=np.zeros((5, 4, 4, 3), dtype=np.uint8))


def test_completed_stage_replays_without_tower_and_refuses_corruption(tmp_path):
    import hashlib
    arr = synthetic_array()
    ids = frame_ids(arr)
    identity = {"count": 2, "frame_ids_sha256": hashlib.sha256(ids.tobytes()).hexdigest()}
    calls = []

    def tower(pixel_values):
        calls.append(len(pixel_values))
        return SimpleNamespace(last_hidden_state=torch.ones(len(pixel_values), 256, 1024))

    root = tmp_path / "cache"
    result = extract_session(arr, tower, root, identity, lambda _: None, device="cpu", batch=2)
    assert calls == [2, 2] and result["exit"] == 0
    assert extract_session(arr, None, root, identity, lambda _: None, device="cpu") == result
    with (root / "global-8.npy").open("r+b") as stream:
        stream.seek(-2, 2)
        stream.write(b"\x01\x00")
    with pytest.raises(ValueError, match="bytes differ"):
        verify_stage(root, identity)


def test_partial_or_changed_identity_never_extracts_again(tmp_path):
    root = tmp_path / "partial"
    root.mkdir()
    (root / "started.json").write_text("{}")
    with pytest.raises(ValueError, match="partial"):
        extract_session(synthetic_array(), None, root, {}, lambda _: None, device="cpu")


def test_stop_before_tower_leaves_partial_receipt(tmp_path):
    stop = tmp_path / "STOP"
    stop.touch()
    root = tmp_path / "stopped"
    with pytest.raises(ValueError, match="STOP"):
        extract_session(synthetic_array(), None, root, {}, lambda _: None, device="cpu", stop=stop)
    assert (root / "started.json").exists() and not (root / "completed.json").exists()
