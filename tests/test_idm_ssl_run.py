import hashlib
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("torch")
from policy.idm import ssl_run as R


def test_fixed_mask_leaves_world_pixels_and_does_not_mutate_input():
    source = np.zeros((2, 144, 256, 3), np.uint8)
    result = R.masked(source)
    assert not source.any()
    assert (result[:, 40, 120] == 0).all()
    for x0, y0, x1, y1 in R.MASK:
        assert (result[:, y0:y1, x0:x1] == (124, 116, 104)).all()


def test_packet_refuses_uninspected_and_nonadmitted_before_frame_read(tmp_path, monkeypatch):
    monkeypatch.setattr(R.ssl_sample, "admitted", lambda *args: [
        {"source_family": "admitted", "media_sha256": "1" * 64}])
    clip = {"source_family": "admitted", "media_sha256": "1" * 64,
            "eligibility": "pending_inspection", "frames": [{"path": "missing"}]}
    doc = {"schema": "rivals-ssl-inspected-clips-v1", "semantic_labels": False,
           "admission_sha256": "2" * 64, "inspector": "synthetic", "clips": [clip]}
    path = tmp_path / "packet.json"
    def call():
        path.write_text(json.dumps(doc))
        return R.packet(path, hashlib.sha256(path.read_bytes()).hexdigest(), "metadata-only", "2" * 64)
    with pytest.raises(ValueError, match="inspection"):
        call()
    clip["source_family"] = "not-admitted"
    with pytest.raises(ValueError, match="not admitted"):
        call()
