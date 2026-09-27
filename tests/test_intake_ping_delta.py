"""Delta admission preserves unrelated accepted evidence, including older rule versions."""
import copy
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "intake_ping_delta", Path(__file__).resolve().parents[1] / "data/human/sessions/intake_session.py")
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


def segment(sid, start, end, gameplay=True):
    row = dict(segment_id=sid, start_ns=start, end_ns=end,
               machine_reason="range_hud_present" if gameplay else "ui_key",
               review_frames=[dict(image="old.jpg", decoded_bgr_sha256="a" * 64)], seen="old inspection")
    if gameplay:
        row["edges"] = {"start": {"sample_ns": start}, "end": {"sample_ns": end - 1}}
    return row


def test_delta_keeps_unrelated_segments_and_clips_to_the_old_accepted_bounds():
    old = [segment("seg-000", 0, 100), segment("seg-001", 100, 200), segment("seg-002", 200, 300)]
    before = copy.deepcopy(old)
    # A changed proposer also changes unrelated intervals. None of that may leak into this revision.
    proposed = [segment("new-0", 0, 70), segment("new-1", 70, 130),
                segment("new-2", 130, 160, False), segment("new-3", 160, 240), segment("new-4", 240, 300)]
    result = intake.splice_ping_delta(old, proposed, {"seg-001"})
    assert old == before
    assert result[0] == old[0] and result[-1] == old[-1]
    assert [(r["start_ns"], r["end_ns"]) for r in result[1:-1]] == [(100, 130), (130, 160), (160, 200)]
    assert result[1]["edges"]["start"] == old[1]["edges"]["start"]
    assert result[-2]["edges"]["end"] == old[1]["edges"]["end"]
    assert all(r["parent_segment"] == "seg-001" for r in result[1:-1])
    assert len({r["segment_id"] for r in result}) == len(result)


@pytest.mark.parametrize("proposed", [[], [segment("x", 101, 200)],
                                    [segment("x", 100, 130), segment("y", 140, 200)],
                                    [segment("x", 100, 160), segment("y", 140, 200)]])
def test_delta_refuses_missing_or_overlapping_coverage(proposed):
    with pytest.raises(intake.Refused, match="tile"):
        intake.splice_ping_delta([segment("old", 100, 200)], proposed, {"old"})


def test_delta_refuses_unknown_old_segment():
    with pytest.raises(intake.Refused, match="missing affected"):
        intake.splice_ping_delta([segment("old", 100, 200)], [], {"other"})
