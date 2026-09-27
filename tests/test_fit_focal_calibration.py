"""Synthetic controls; never open a recording or logger directory."""
import pytest

from scripts import fit_focal_calibration as m


def test_unknown_source_cannot_expand_authority():
    with pytest.raises(ValueError, match="authorized"):
        m.proposal("another_session")


def test_accounts_and_unknown_focal_stay_separate():
    assert m.proposal("alt_left")["source"]["account"] == "alt"
    assert m.proposal("main_right")["source"]["account"] == "main"
    assert m.proposal("rightward_unassigned")["source"]["account"] is None
    for name in m.SOURCES:
        p = m.proposal(name)
        assert p["candidate_focal_px_1280"] is None
        assert not p["automatic_probe_queued"]
        assert p["requires_explicit_lead_game_closed_release"]


def test_proposal_copy_does_not_mutate_fixed_windows():
    p = m.proposal("alt_left")
    p["source"]["track_windows_logger_s"][0][0] = 100
    assert m.proposal("alt_left")["source"]["track_windows_logger_s"][0] == [6., 6.8]


def test_packet_selection_uses_composition_clock_not_callback_order():
    start = m.SOURCES["alt_left"]["start_ns"]
    rows = [dict(track=0, composition_ns=start+int(t*1e9), pts=pts, timebase_num=1, timebase_den=120)
            for t, pts in ((6.025, 803), (6., 800), (5.99, 799), (6.8, 896))]
    selected = m.proposed_packets("alt_left", [6., 6.8], rows)
    assert [r["pts"] for r in selected] == [800, 803]
    with pytest.raises(ValueError, match="fixed"):
        m.proposed_packets("alt_left", [0., 48.], rows)


def test_static_loader_reads_only_named_small_json(monkeypatch):
    expected = m.SOURCES["alt_left"]
    import json
    reads = []
    def read(path, **kwargs):
        reads.append(path)
        if path.name == "calibration.json":
            return json.dumps({"session": expected["session"], "media": {
                "path": expected["video_path"], "sha256": expected["expected_media_sha256"]}})
        assert path.name == "metadata.json"
        return json.dumps({"session_id": expected["session"], "video_path": expected["video_path"],
                           "start_ns": expected["start_ns"]})
    monkeypatch.setattr(m.Path, "read_text", read)
    result = m.load_static_metadata("alt_left")
    assert len(reads) == 2
    assert not result["video_verified_this_task"]


def test_selected_packets_have_native_pts_and_exclude_endpoint(tmp_path, monkeypatch):
    import csv
    monkeypatch.setattr(m, "RAW", tmp_path)
    source = m.SOURCES["alt_left"]
    folder = tmp_path / source["session"]
    folder.mkdir()
    path = folder / "frames.csv"
    with path.open("w", newline="") as stream:
        fields = ["track", "composition_ns", "pts", "timebase_num", "timebase_den"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for t, pts in [(6.025, 803), (6., 800), (6.8, 896)]:
            writer.writerow(dict(track=0, composition_ns=source["start_ns"]+int(t*1e9),
                                 pts=pts, timebase_num=1, timebase_den=120))
    rows, sha = m.selected_packets("alt_left", "window", 0)
    assert [r["expected_mkv_pts"] for r in rows] == [6688, 6713]
    assert sha == m.digest(path)


def test_evidence_write_never_overwrites(tmp_path):
    path = tmp_path / "result.json"
    m.write(path, {"candidate": None})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        m.write(path, {"candidate": 640})
    assert path.read_bytes() == original
