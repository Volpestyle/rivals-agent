"""Synthetic-only tests for the exploratory history/NLL diagnostic."""
import math

import pytest

torch = pytest.importorskip("torch")

from policy.range_bc import fixture, steps, train, vocab
from policy.range_bc.explore_history_diagnostic import CameraMeter, diagnose
from policy.range_bc.model import Config, Policy


def test_camera_prior_and_direction_bins_keep_zero_and_unknown_separate():
    counts = [1] * vocab.CAMERA_CLASSES
    meter = CameraMeter(counts)
    probabilities = torch.zeros(4, vocab.CAMERA_CLASSES, dtype=torch.float64)
    probabilities[:, vocab.ZERO_CLASS - 1] = .2
    probabilities[:, vocab.ZERO_CLASS] = .5
    probabilities[:, vocab.ZERO_CLASS + 1] = .3
    meter.add(probabilities.log(), torch.full((4,), vocab.ZERO_CLASS),
              torch.tensor([vocab.ZERO_CLASS - 1, vocab.ZERO_CLASS, vocab.ZERO_CLASS + 1, -1]),
              torch.tensor([True, True, True, True]))
    result = meter.result()
    assert result["all"]["nll"] == pytest.approx(-math.log(.5))
    assert result["all"]["prior_nll"] == pytest.approx(math.log(vocab.CAMERA_CLASSES))
    assert result["all"]["predicted_class"] == pytest.approx(vocab.ZERO_CLASS + .1)
    bins = result["by_previous_class"]
    assert bins[str(vocab.ZERO_CLASS - 1)]["p_same_direction"] == pytest.approx(.2)
    assert bins[str(vocab.ZERO_CLASS + 1)]["p_same_direction_given_moving"] == pytest.approx(.6)
    assert bins[str(vocab.ZERO_CLASS)]["p_same_direction"] is None
    assert bins["-1"]["p_same_direction"] is None


def test_empirical_unseen_class_is_not_silently_finite_and_unknown_target_is_masked():
    counts = [0] * vocab.CAMERA_CLASSES
    counts[vocab.ZERO_CLASS] = 10
    meter = CameraMeter(counts)
    logits = torch.zeros(3, vocab.CAMERA_CLASSES)
    meter.add(logits.log_softmax(-1), torch.tensor([0, 1, vocab.ZERO_CLASS]),
              torch.tensor([0, 0, 0]), torch.tensor([True, False, True]))
    result = meter.result()["all"]
    assert result["n"] == 2 and result["prior_unseen"] == 1
    assert result["prior_nll"] is None
    assert math.isfinite(result["smoothed_prior_nll"])


def test_diagnostic_preserves_recurrence_across_chunks_and_masks_targets():
    import numpy as np
    torch.set_num_threads(2)
    header, rows = fixture.session("history-diagnostic-synthetic", runs=(12, 10), seed=4)
    session = steps.Session("synthetic", "synthetic", header, rows)
    frames = tuple(np.zeros((len(rows), 2, 2, 3), dtype=np.uint8) for _ in range(3))
    arr = train.SessionArrays(session, (*frames, list(range(len(rows))), {}))
    arr.camera_known[3, 1] = False
    model = Policy(Config(frames=False, hud=False, embed=4, history_embed=3, hidden=5))
    statistics = steps.train_statistics([session])
    a = diagnose(model, [arr], statistics, chunk=3)
    b = diagnose(model, [arr], statistics, chunk=19)
    for axis in ("yaw", "pitch"):
        assert a["axes"][axis]["all"]["nll"] == pytest.approx(b["axes"][axis]["all"]["nll"], abs=1e-7)
        assert a["axes"][axis]["all"]["n"] == b["axes"][axis]["all"]["n"]
    assert a["axes"]["pitch"]["all"]["n"] == a["axes"]["yaw"]["all"]["n"] - 1
    for name in train.LOSS_WEIGHTS:
        assert a["teacher_dev_loss_components"][name]["mean"] == pytest.approx(
            b["teacher_dev_loss_components"][name]["mean"], abs=1e-7)
