"""The reusable renderer must not silently span an ineligible gap."""
import pytest

pytest.importorskip('torch')
from policy.range_bc.offline_replay import selected_interval
from policy.range_bc.train import FitError


def test_interval_keeps_explicit_warmup_and_accepts_other_clip_lengths():
    interval = {'display_start_row': 55, 'display_stop_row_exclusive': 655,
                'warmup_start_row': 23, 'frames': 600}
    assert selected_interval(interval, [(20, 700)]) == (23, 55, 655)


def test_interval_cannot_bridge_two_runs_or_disagree_with_frame_count():
    interval = {'display_start_row': 55, 'display_stop_row_exclusive': 655,
                'warmup_start_row': 23, 'frames': 600}
    with pytest.raises(FitError, match='boundary'):
        selected_interval(interval, [(20, 300), (320, 700)])
    with pytest.raises(FitError, match='count'):
        selected_interval({**interval, 'frames': 900}, [(20, 700)])
