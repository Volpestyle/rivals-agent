import pytest

torch = pytest.importorskip("torch")

from policy.range_bc.spatial_yaw_probe import exercise, verify_input_blocks


def test_probe_cpu_exercises_both_grids_and_records_overlap_interval():
    state, report = exercise("cpu", batch=1, window=2, seconds=0, updates_min=2)
    assert set(state) == {"4", "8"}
    assert report["work_finished_at"] >= report["work_started_at"]
    assert report["updates_per_grid"] == 2
    assert all(len(times) == 2 for times in report["synthetic_batch_seconds"].values())
    assert report["retention"].startswith("exact action/pitch")


def test_probe_refuses_another_source_before_file_access():
    with pytest.raises(ValueError, match="source differs"):
        verify_input_blocks({"session": "not-authorized", "frame_ids": [7, 8]})


def test_six_way_overlap_requires_all_six_successful_intervals():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parents[1] / "docs/evidence/nitrogen-spatial-yaw-20260927/collect_probe.py"
    spec = importlib.util.spec_from_file_location("yaw_probe_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reports = [{"slot": i + 1, "work_started_at": i * 15, "work_finished_at": i * 15 + 110}
               for i in range(6)]
    assert module.overlap(reports)["seconds"] == 35
    assert not module.overlap(reports[:-1])["six_way_overlap"]
    reports[-1]["work_started_at"] = 111
    assert not module.overlap(reports)["six_way_overlap"]
