"""scripts/replay_camera.py: the replay step table's camera degrees from the estimator's replay run.

    uv run pytest tests/test_replay_camera.py

A synthetic run over a synthetic replay table. Needs scripts/replay_steps.py, whose fill_camera does the filling,
and numpy (scripts/replay_camera.py imports perception.camera_motion); skipped where either is absent.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
if not (ROOT / "scripts" / "replay_steps.py").is_file():
    pytest.skip("scripts/replay_steps.py (the replay step table) is not in this checkout", allow_module_level=True)
pytest.importorskip("numpy")  # scripts/replay_camera.py imports perception.camera_motion; the stdlib suite skips
import replay_camera as C  # noqa: E402
import replay_steps as S  # noqa: E402
from policy.range_bc import vocab  # noqa: E402

STEP, PERIOD = S.STEP_NS, S.PERIOD_NS
VIDEO = "C:/Users/volpe/Videos/2026-09-23 00-43-25.mkv"
META = {"type": "meta", "video": VIDEO, "spectator_mask": True, "t_offset": 0.0, "hz": 120}
T0 = 10.0                                   # file seconds of the first anchor


class Identity:
    """File seconds == composition seconds."""

    def __call__(self, t):
        return round(t * 1e9)


def table(n=6):
    header = S.header("0" * 64, {"reader": {"sha256": "1" * 64}})
    none = [None] * vocab.N
    rows = []
    for i in range(n):
        a = round(T0 * 1e9) + i * STEP
        rows.append({"i": i, "run": "b5-000", "anchor_ns": a,
                     "frame": {"video_path": VIDEO, "frame_index": 1200 + 4 * i, "pts": 0, "timebase": [1, 1000],
                               "composition_ns": a - PERIOD // 2},
                     "gap_free": True, "segment": "b5-000", "suitability": "accepted", "regime": "normal", "tags": [],
                     "tag_source": "untagged", "held_start": list(none), "held_end": list(none),
                     "held_known": [False] * vocab.N, "press": list(none), "release": list(none),
                     "press_known": [False] * vocab.N, "release_known": [False] * vocab.N, "yaw_deg": None,
                     "pitch_deg": None, "beyond_pad_envelope": False})
    return header, rows


def pair(k, yaw=0.5, pitch=0.25, source="main", abstain=None):
    """The k-th 120 fps estimator pair from T0 (four per 30 Hz step)."""
    return {"t0": T0 + k / 120, "t1": T0 + (k + 1) / 120, "yaw_deg": yaw, "pitch_deg": pitch, "abstain": abstain,
            "source": source}


def run(pairs, sources=("main",), n=6):
    header, rows = table(n)
    report = C.fill(header, rows, (META, pairs), Identity(), capture_video=VIDEO, sources=sources,
                    camera_sha256="2" * 64, estimator_sha256="3" * 64)
    return header, rows, report


def test_tiled_main_pairs_fill_the_step_through_fill_camera_and_the_table_stays_valid():
    pairs = [pair(k) for k in range(24)]
    header, rows, report = run(pairs)
    assert report["filled"] == 6 and report["unknown"] == 0
    assert rows[0]["yaw_deg"] == pytest.approx(2.0) and rows[0]["pitch_deg"] == pytest.approx(-1.0)   # down positive
    assert rows[0]["camera"] == {"source": "main"}
    reference = table()[1]
    S.fill_camera(reference, (META, copy.deepcopy(pairs)), Identity(), capture_video=VIDEO)
    assert [r["yaw_deg"] for r in rows] == [r["yaw_deg"] for r in reference]    # the degrees are fill_camera's
    assert "3" * 12 in header["calibration"]["label_sources"]["camera"]
    assert header["source"]["camera"]["sources"] == ["main"]
    C.check(header, rows)                                                      # the step-table contract


def test_a_withheld_pair_leaves_its_step_unknown_with_the_estimators_reason():
    pairs = [pair(k) for k in range(24)]
    pairs[5] = pair(5, yaw=None, pitch=None, abstain="repeated frame")
    _, rows, report = run(pairs)
    assert rows[1]["yaw_deg"] is None and rows[1]["camera"] == {"why": "withheld: repeated frame"}
    assert rows[0]["yaw_deg"] is not None and rows[2]["yaw_deg"] is not None
    assert report["why"] == {"withheld: repeated frame": 1}


def test_centre_pairs_are_unknown_unless_opted_in():
    pairs = [pair(k) for k in range(24)]
    pairs[9] = pair(9, source="centre")
    _, rows, report = run(pairs)
    assert rows[2]["yaw_deg"] is None and rows[2]["camera"] == {"why": "source 'centre' not accepted"}
    _, rows, report = run(pairs, sources=("main", "centre"))
    assert rows[2]["yaw_deg"] is not None and rows[2]["camera"] == {"source": "centre+main"}
    assert report["unknown"] == 0


def test_a_gap_and_a_missing_run_are_named():
    pairs = [pair(k) for k in range(24) if k not in (13, 14)]        # a two-frame hole inside step 3
    _, rows, report = run(pairs, n=8)
    assert rows[3]["camera"] == {"why": "gap between estimator pairs"}
    # The run ends at step 6's anchor: nanosecond rounding leaves its last pair 2 ns into step 6, so that step reads
    # as a gap (fill_camera sees the same); step 7 has no pair at all.
    assert rows[6]["camera"] == {"why": "gap between estimator pairs"}
    assert rows[7]["camera"] == {"why": "no estimator pair"}
    assert report["filled"] == 5


def test_a_fast_step_is_flagged_beyond_the_pad_envelope_and_kept():
    pairs = [pair(k, yaw=4.0) for k in range(24)]                     # 16 deg per step, over 415/30
    _, rows, _ = run(pairs)
    assert rows[0]["beyond_pad_envelope"] is True and rows[0]["yaw_deg"] == pytest.approx(16.0)


def test_only_the_estimators_replay_run_over_this_capture_is_taken():
    header, rows = table()
    with pytest.raises(ValueError, match="spectator_mask"):
        C.fill(header, rows, ({**META, "spectator_mask": False}, [pair(0)]), Identity(), capture_video=VIDEO,
               camera_sha256="2" * 64, estimator_sha256="3" * 64)
    with pytest.raises(ValueError, match="not this session's capture"):
        C.fill(header, rows, ({**META, "video": "other.mkv"}, [pair(0)]), Identity(), capture_video=VIDEO,
               camera_sha256="2" * 64, estimator_sha256="3" * 64)
