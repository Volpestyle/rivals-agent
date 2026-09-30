"""Container packet metadata must not corrupt IDM span presentation times."""
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")

from policy.idm import vod  # noqa: E402


def test_span_pts_side_data_order_and_boundaries(monkeypatch):
    packets = [
        {"pts_time": "213.583000", "side_data_list": [{"side_data_type": "MPEGTS Stream ID", "id": 224}]},
        {"pts_time": "213.516000", "side_data_list": [{}]},
        {"pts_time": "213.549000"},
        {"pts_time": "212.000000"},
        {"pts_time": "215.000000"},
        {"pts_time": "N/A"},
        {"side_data_list": [{}]},
    ]

    def probe(command, **kwargs):
        assert command[command.index("-show_entries") + 1] == "packet=pts_time"
        assert command[command.index("-of") + 1] == "json"
        return SimpleNamespace(stdout=json.dumps({"packets": packets}))

    monkeypatch.setattr(vod.subprocess, "run", probe)
    assert vod.span_pts("vod.mp4", 213.516, 213.583) == [213.516, 213.549, 213.583]


def test_span_pts_empty(monkeypatch):
    monkeypatch.setattr(vod.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout='{"packets": []}'))
    assert vod.span_pts("vod.mp4", 1, 2) == []


def test_span_pts_malformed_timestamp_still_fails(monkeypatch):
    monkeypatch.setattr(vod.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout='{"packets": [{"pts_time": "broken"}]}'))
    with pytest.raises(ValueError):
        vod.span_pts("vod.mp4", 1, 2)
