"""CI only: tests that read recordings a fresh clone does not have are xfail(strict=False) there.

Loaded by .github/workflows/tests.yml as `pytest -p missing_data` with PYTHONPATH=.github/ci. A developer run
never loads it. Each entry names the gitignored data it reads, and the mark applies only while that path is
absent, so a machine that has the data still runs these tests and still has to pass them.
"""
import pytest

NEEDS = {   # node id, or file for a whole module: the untracked path it reads (measured on a fresh clone, 2026-09-23)
    "tests/test_replay_states.py": "data/run1",
    "tests/test_scoreboard.py::test_a_frame_without_a_scoreboard_reads_nothing": "data/run1",
    "tests/test_hud.py::test_hud_accuracy": "data/l2",       # also the 12 ms median latency gate: runner-load sensitive
    "tests/test_hud_countdown_performance.py": "data/diagnostics/range-hud-countdown-performance-20260922",
    "tests/test_range_skill_loop.py::test_recorded_first_phase_acquisitions_match_82_4_62_without_retiming":
        "data/diagnostics/range-request-runtime-timing-20260922",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        for prefix, data in NEEDS.items():
            if (item.nodeid == prefix or item.nodeid.startswith(prefix + "::")) and not (config.rootpath / data).exists():
                item.add_marker(pytest.mark.xfail(strict=False, reason=f"reads {data}, which is gitignored and not in CI"))
