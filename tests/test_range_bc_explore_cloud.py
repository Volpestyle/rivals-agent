"""Synthetic device-routing regression; no corpus or GPU access."""
from types import SimpleNamespace

import pytest

pytest.importorskip("torch")

from policy.range_bc import explore_chunks_eval as evaluation
from policy.range_bc import steps


def test_explicit_cpu_evaluation_routes_every_inference_call(tmp_path, monkeypatch):
    seen = []
    class Model:
        horizon = 1
        def to(self, device):
            seen.append(("model", device))
            return self
        def load_state_dict(self, value):
            pass
    recipe = {"config": {}, "horizon": 1, "cohort": "full"}
    monkeypatch.setattr(evaluation.torch, "load", lambda *a, **k: {
        "format": evaluation.FORMAT, "recipe": recipe, "model": {}, "epoch": 26, "seconds": 1})
    monkeypatch.setattr(evaluation, "ChunkPolicy", lambda *args: Model())
    monkeypatch.setattr(evaluation, "load_manifest", lambda *a, **k: ([], []))
    monkeypatch.setattr(steps, "train_statistics", lambda a: {"live_mask": [True] * 15})
    def teacher(*args, device):
        seen.append(("teacher", device))
        return []
    def condition(*args, device):
        seen.append(("condition", device))
        return {"synthetic": True}
    def suite(*args, device, progress):
        seen.append(("suite", device))
        return {}
    monkeypatch.setattr(evaluation.train, "predict_teacher", teacher)
    monkeypatch.setattr(evaluation, "conditioning_nll", condition)
    monkeypatch.setattr(evaluation, "predict_suite", suite)
    monkeypatch.setattr(evaluation, "choose_thresholds", lambda *a: {"thresholds": [.5] * 15})
    monkeypatch.setattr(evaluation, "recompute_references", lambda *a: {})
    args = SimpleNamespace(out=str(tmp_path / "result.json"), checkpoint="synthetic",
                           manifest="synthetic", registry="synthetic", tally="synthetic")
    evaluation.evaluate(args, lambda text: None, device="cpu")
    assert seen == [("model", "cpu"), ("teacher", "cpu"), ("condition", "cpu"), ("suite", "cpu")]
