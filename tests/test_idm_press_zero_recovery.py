"""Synthetic recovery checks; never reads the recorded corpus."""
from types import SimpleNamespace
import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
from policy.idm import press_zero_recovery as R, press_diagnostic as D
from policy.idm.model import Config, IDM


def test_zero_inputs_match_original_ablation_with_tail_batch():
    torch.set_num_threads(2)
    config = Config(window=1, height=16, width=16, channels=(2,), embed=3,
                    hud_channels=(2,), hud_embed=3, hidden=4, test_scale=True)
    model = IDM(config)
    class Original(R.ZeroInputs):
        def inputs(self, indices):
            return tuple(x + 0.75 for x in super().inputs(indices))
    original = D.infer(model, Original(35, config), device='cpu', zero=True)
    recovered = D.infer(model, R.ZeroInputs(35, config), device='cpu', zero=True)
    assert np.array_equal(original, recovered)


def test_exact_row_order_and_refusals(monkeypatch):
    targets = [SimpleNamespace(session_id=sid, rows=[{'i': 2}, {'i': 5}]) for sid in R.HELDOUT]
    monkeypatch.setattr(R.T, 'training_rows', lambda target: iter(target.rows))
    ids = [[R.HELDOUT[1], 5], [R.HELDOUT[0], 2]]
    e = R.select_rows(targets, ids)
    assert [[t.session_id, row['i']] for t, _, row, _ in e.items] == ids
    with pytest.raises(ValueError, match='duplicate'):
        R.select_rows(targets, ids * 2)
    with pytest.raises(ValueError, match='missing or ineligible'):
        R.select_rows(targets, [[R.HELDOUT[0], 99]])
    with pytest.raises(ValueError, match='exact frozen'):
        R.select_rows(targets[:1], ids)


def test_bad_origin_refused_before_model_or_targets(tmp_path, monkeypatch):
    artifact = tmp_path/'stage-identity.json'
    artifact.write_text('{}')
    def forbidden(*args, **kwargs):
        raise AssertionError('model/targets must not open')
    monkeypatch.setattr(R.TR, 'load_checkpoint', forbidden)
    monkeypatch.setattr(R.T, 'load', forbidden)
    with pytest.raises(ValueError, match='artifact pin'):
        R.run(tmp_path, {'artifacts': {'stage-identity.json': '0'*64}},
              tmp_path/'inputs', tmp_path/'out', {}, device='cpu')
