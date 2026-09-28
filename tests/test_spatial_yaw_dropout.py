"""Approved one-factor dropout arm: CPU synthetic inputs only."""
import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("numpy")

from policy.range_bc import steps
from policy.range_bc.explore_encoder import EncoderPolicy
from policy.range_bc.model import Config
from policy.range_bc.spatial_yaw import SpatialYawReadout
from policy.range_bc.spatial_yaw_cache import sha
from policy.range_bc.spatial_yaw_train import BASE_PINS, SpatialYawPolicy, checked_spec


@pytest.fixture(autouse=True)
def cpu_threads():
    torch.set_num_threads(2)


def test_no_capacity_or_state_dict_change_and_zero_initial_residual():
    torch.manual_seed(7)
    control = SpatialYawReadout(4)
    torch.manual_seed(7)
    candidate = SpatialYawReadout(4, hidden_dropout=.5)
    assert sum(p.numel() for p in candidate.parameters()) == 201187
    assert control.state_dict().keys() == candidate.state_dict().keys()
    assert all(torch.equal(v, candidate.state_dict()[k]) for k, v in control.state_dict().items())
    x, h = torch.randn(1, 4, 16384), torch.randn(1, 4, 512)
    assert torch.count_nonzero(candidate(x, x, h)) == 0


def test_dropout_only_in_training_and_evaluation_equals_legacy_operations():
    model = SpatialYawReadout(4, hidden_dropout=.5)
    with torch.no_grad():
        model.out.weight.normal_()
    x, h = torch.randn(1, 8, 16384), torch.randn(1, 8, 512)
    model.train()
    assert not torch.equal(model(x, x, h), model(x, x, h))
    model.eval()
    actual = model(x, x, h)
    joined = torch.cat((model.view(x), model.view(x), h.detach()), -1)
    assert torch.equal(actual, model.out(torch.relu(model.hidden(joined))))
    assert torch.equal(actual, model(x, x, h))


def test_train_eval_switches_keep_base_and_action_pitch_exact(tmp_path):
    base = EncoderPolicy(Config(history=False, hud=False))
    model = SpatialYawPolicy(base, 4, hidden_dropout=.5)
    before = {k: v.clone() for k, v in base.state_dict().items()}
    x = torch.randn(1, 4, 32768)
    prev = torch.randn(1, 4, steps.PREV_DIM)
    model.train()
    with torch.no_grad():
        expected = base(x[..., :16384].contiguous(), x[..., :16384].contiguous(), None, prev)
    opt = torch.optim.AdamW(model.yaw.parameters(), lr=.001, weight_decay=.0001)
    for _ in range(3):
        opt.zero_grad()
        a, c, _ = model(x, x, None, prev)
        assert torch.equal(a, expected[0]) and torch.equal(c[:, :, 1], expected[1][:, :, 1])
        torch.nn.functional.cross_entropy(c[:, :, 0].flatten(0, 1), torch.zeros(4, dtype=torch.long)).backward()
        opt.step()
    assert not base.training and all(p.grad is None for p in base.parameters())
    assert all(torch.equal(v, before[k]) for k, v in base.state_dict().items())
    model.eval()
    actual = model(x, x, None, prev)
    assert torch.equal(actual[0], expected[0]) and torch.equal(actual[1][:, :, 1], expected[1][:, :, 1])
    assert not torch.equal(actual[1][:, :, 0], expected[1][:, :, 0])
    saved = tmp_path / "model.pt"
    torch.save(model.state_dict(), saved)
    restored = SpatialYawPolicy(base, 4, hidden_dropout=.5).eval()
    restored.load_state_dict(torch.load(saved, weights_only=True), strict=True)
    assert torch.equal(actual[1], restored(x, x, None, prev)[1])
    model.train()
    assert model.yaw.hidden_dropout.training and not model.base.training


@pytest.mark.parametrize("grid,dropout,allowed", [(4, .5, True), (4, 0., True), (8, 0., True),
                                                (8, .5, False), (4, .2, False), (4, True, False)])
def test_spec_pin_and_approved_recipe_only(tmp_path, grid, dropout, allowed):
    spec = dict(grid=grid, hidden_dropout=dropout, seed=1, epochs=26, updates=15288,
                base_sha256=BASE_PINS[1][0], cutoff_sha256=BASE_PINS[1][1])
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    if allowed:
        assert checked_spec(path, sha(path)) == spec
    else:
        with pytest.raises(ValueError, match="unapproved hidden dropout"):
            checked_spec(path, sha(path))
    with pytest.raises(ValueError, match="bytes differ"):
        checked_spec(path, "0"*64)


def test_shakedown_runs_actual_dropout_optimizer_and_retention_on_cpu():
    from policy.range_bc.spatial_yaw_dropout_probe import exercise
    base = EncoderPolicy(Config(history=False, hud=False))
    state, report = exercise(base, device="cpu", seed=1, seconds=0, batch=1, window=3)
    assert report["updates"] == 3 and report["evaluation_dropout_disabled"]
    assert state["out.weight"].abs().sum() > 0
    assert len(state) == len(SpatialYawReadout(4).state_dict())
