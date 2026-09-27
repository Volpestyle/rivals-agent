"""Small tensors only: future leakage, teacher detachment and copy baseline."""
import pytest

torch = pytest.importorskip("torch")
from policy.idm import ssl


@pytest.fixture(autouse=True)
def threads():
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(before)


def test_encoder_causal_across_multiple_blocks():
    torch.manual_seed(1)
    config = ssl.Config(cells=3, feature_width=8, width=12, heads=3, feedforward=24)
    model = ssl.TemporalEncoder(config).eval()
    x = torch.randn(2, 5, 3, 8)
    t = torch.arange(5).float()[None].repeat(2, 1) / 60
    y = model(x, t)
    changed = x.clone()
    changed[:, 3:] += torch.randn_like(changed[:, 3:]) * 100
    assert torch.equal(y[:, :3], model(changed, t)[:, :3])


def test_predictor_never_reads_future_feature_values():
    config = ssl.Config(cells=3, feature_width=8, width=12, heads=3, feedforward=24)
    model = ssl.PredictiveSSL(config).eval()
    x = torch.randn(2, 16, 3, 8, requires_grad=True)
    t = torch.arange(16).float()[None].repeat(2, 1) / 8
    pred = model(x, t)
    changed = x.detach().clone()
    changed[:, 8:] *= 100
    assert torch.equal(pred, model(changed, t))
    loss, _ = ssl.objective(pred, x)
    loss.backward()
    assert x.grad is None
    assert model.encoder.project.weight.grad.abs().sum() > 0


def test_static_copy_has_zero_loss_and_time_reversal_refuses():
    x = torch.randn(2, 1, 17, 384).expand(-1, 16, -1, -1)
    loss, diagnostics = ssl.objective(x[:, 8:], x)
    assert loss == 0 and diagnostics['copy_last_error'] == 0
    model = ssl.TemporalEncoder()
    with pytest.raises(ValueError, match="increasing"):
        model(x[:, :2], torch.zeros(2, 2))


def test_downstream_branch_initially_preserves_camera_and_press():
    from policy.idm.model import Config, IDM
    from policy.idm.ssl_camera import TemporalCamera
    c = Config(window=1, height=16, width=16, channels=(4,), embed=8,
               hud_channels=(4,), hud_embed=4, hidden=8, test_scale=True)
    base = IDM(c).eval()
    temporal = TemporalCamera(c, ssl.Config(cells=3, feature_width=8, width=12, heads=3, feedforward=24),
                              base_state=base.state_dict()).eval()
    motion, hud = torch.randn(2, 2, 16, 16), torch.randn(2, 6, 16, 16)
    feature = torch.randn(2, 16, 3, 8)
    times = torch.arange(16).float()[None].repeat(2, 1) / 60
    before = base(motion, hud)
    after = temporal(motion, hud, feature, times)
    assert torch.equal(before[0], after[0])
    torch.testing.assert_close(before[1], after[1], rtol=1e-6, atol=1e-7)
