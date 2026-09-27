"""Synthetic calibration leakage, rate ties, and actual visual ablation checks."""
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")
from policy.idm import press_diagnostic as D
from policy.range_bc import vocab


def sample():
    t = SimpleNamespace(session_id="synthetic", header={"split": "train"})
    return SimpleNamespace(actions=("amazing_combo",), items=[(t, None, {}, None)] * 4,
                           y=torch.tensor([[0.], [1.], [0.], [0.]]),
                           mask=torch.ones(4, 1, dtype=torch.bool))


def test_overlap_is_refused_before_checkpoint_or_store_payload(tmp_path):
    same = SimpleNamespace(session_id="same-source")
    loaded = [({"role": "train"}, same), ({"role": "heldout"}, same)]
    with pytest.raises(ValueError, match="separate explicit"):
        D.run(loaded, tmp_path / "must-not-open", "0" * 64, tmp_path, device="cpu")
    D.require_disjoint_roles([({"role": "train"}, same),
                             ({"role": "heldout"}, SimpleNamespace(session_id="another-source"))])


def test_calibration_uses_training_rate_and_reports_ties():
    e = sample()
    report = D.thresholds(e, np.array([[.1], [.9], [.9], [.2]]), role="train")
    assert report["thresholds"]["amazing_combo"] == .9
    assert report["rates"]["amazing_combo"] == {"target": .25, "achieved": .5}
    with pytest.raises(ValueError, match="explicit train"):
        D.thresholds(e, np.ones((4, 1)), role="heldout")


def test_no_positives_emits_no_event_and_nonfinite_refuses():
    e = sample()
    e.y.zero_()
    assert D.thresholds(e, np.ones((4, 1)), role="train")["thresholds"]["amazing_combo"] > 1
    with pytest.raises(ValueError, match="finite"):
        D.thresholds(e, np.full((4, 1), np.nan), role="train")


def test_zero_control_zeroes_both_visual_streams_with_identical_rows():
    class Examples:
        def __len__(self):
            return 3

        def inputs(self, indices):
            return torch.ones(len(indices), 2), torch.ones(len(indices), 6)

    class Model:
        def eval(self):
            return self

        def __call__(self, motion, hud):
            z = motion.sum(1) + hud.sum(1)
            return z[:, None].expand(-1, vocab.N), None

    real = D.infer(Model(), Examples(), device="cpu", batch=2)
    zero = D.infer(Model(), Examples(), device="cpu", zero=True, batch=2)
    assert real.shape == zero.shape == (3, 3)
    assert (real > .99).all() and (zero == .5).all()
