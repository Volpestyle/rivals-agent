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
