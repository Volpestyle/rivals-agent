import pytest

from policy.idm.ssl_packet import selected_pts


def test_integer_pts_rounding_preserved_and_gap_refused(tmp_path):
    path = tmp_path / "log"
    pts = [round(i * 1000 / 60) for i in range(16)]
    def log(values):
        path.write_text("config in time_base: 1/1000\n" + "\n".join(
            f"n: {i} pts: {p} pts_time: {p/1000}" for i, p in enumerate(values)))
    log(pts)
    assert selected_pts(path, 16, 2) == ((1, 1000), pts)
    log(pts[:8] + [p + 50 for p in pts[8:]])
    with pytest.raises(ValueError, match="gap"):
        selected_pts(path, 16, 2)
    log(pts[:8] + pts[7:15])
    with pytest.raises(ValueError, match="duplicate"):
        selected_pts(path, 16, 2)
