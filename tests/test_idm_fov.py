"""Synthetic source sampling controls; never opens footage or a checkpoint."""
import json

import numpy as np
import pytest

pytest.importorskip("torch")
from policy.idm import fov


def test_empty_estimate_is_explicit_unknown():
    result = fov.summarise(np.zeros(0))
    assert result["frames"] == 0 and result["camera_scale"] is None
    assert result["z_median"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("per_video,selected", [(24, [0, 1, 2]), (2, [0, 2]), (1, [0])])
def test_clip_sources_sample_the_full_timeline_and_correct_paths(tmp_path, monkeypatch, per_video, selected):
    path = tmp_path / "spans.jsonl"
    rows = [{"video_id": "v", "span_id": f"v:{i}", "start_s": i * 10, "end_s": i * 10 + 6,
             "local_path": f"/clips/v/{i}.mkv", "source_path": "D:/footage/creator/v.mp4"} for i in range(3)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    reads = []

    def frames(video, windows):
        reads.append((video, windows))
        return np.ones((2, 1, 1), np.uint8)

    monkeypatch.setattr(fov, "frames_at", frames)
    monkeypatch.setattr(fov, "predict_z", lambda model, grey, **kw: np.ones(len(grey)))
    result = fov.sources(None, path, per_video=per_video)
    assert [v for v, _ in reads] == [rows[i]["local_path"] for i in selected]
    assert [w for _, w in reads] == [[(i * 10 + 1.5, i * 10 + 4.5, [])] for i in selected]
    assert result["videos"]["v"]["creator"] == "creator"
    assert result["creators"]["creator"]["camera_scale"] == 1.0
    assert len(result["videos"]["v"]["sampled_windows"]) == len(selected)


@pytest.mark.parametrize("per_video,window", [(0, 3), (-1, 3), (1, 0), (1, -1)])
def test_invalid_sampling_refused_before_opening_source_list(per_video, window):
    with pytest.raises(ValueError, match="positive"):
        fov.sources(None, "must-not-open", per_video=per_video, window=window)
