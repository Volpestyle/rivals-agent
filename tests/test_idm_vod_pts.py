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


def test_export_index_packet_metadata_and_timebase(monkeypatch, tmp_path):
    from policy.idm import labels

    def probe(command, **kwargs):
        entries = command[command.index("-show_entries") + 1]
        if entries == "stream=time_base":
            return SimpleNamespace(stdout="1/90000\n")
        assert entries == "packet=pts"
        assert command[command.index("-of") + 1] == "json"
        return SimpleNamespace(stdout=json.dumps({"packets": [
            {"pts": 90000, "side_data_list": [{"id": 224}]},
            {"pts": 3000, "side_data_list": [{}]},
            {"pts": 6000}, {"pts": "N/A"}, {},
        ]}))

    monkeypatch.setattr(vod.subprocess, "run", probe)
    pts, tb = labels._video_index("vod.mp4", tmp_path)
    assert pts.tolist() == [3000 / 90000, 6000 / 90000, 1.0]
    assert tb == [1, 90000]

    def no_reprobe(*args, **kwargs):
        pytest.fail("the completed index should be reused")

    monkeypatch.setattr(vod.subprocess, "run", no_reprobe)
    cached, cached_tb = labels._video_index("vod.mp4", tmp_path)
    assert cached.tolist() == pts.tolist()
    assert cached_tb == tb
