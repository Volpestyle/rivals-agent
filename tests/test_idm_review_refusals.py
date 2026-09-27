"""Synthetic regressions for the post-land admission and decoder review."""
import hashlib
import json

import pytest

from policy.idm import match_targets as A


@pytest.mark.parametrize("change", [{"decision": "pending"}, {"reviewer": None}])
def test_unaccepted_receipt_refused_before_registry_payload(tmp_path, change):
    doc = {"format": A.FORMAT, "scope": "EXPLORATORY", "decision": "accepted",
           "reviewer": "independent", "sessions": {}, **change}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="not independently accepted"):
        A.load(path, hashlib.sha256(path.read_bytes()).hexdigest(),
               registry=tmp_path / "must-not-open", denylist={"sessions": []})


@pytest.mark.parametrize("row", [{"split": "reader_validation"},
                                  {"split": "idm_train", "sealed": True},
                                  {"split": "idm_train", "training_pending": True}])
def test_forbidden_registry_role_refused(row):
    with pytest.raises(ValueError):
        A.Admission({}, {"synthetic": row}, "0" * 64).check("synthetic")


def test_mixed_and_unknown_decode_platform_refused_before_payload(tmp_path):
    pytest.importorskip("torch")
    from policy.idm import explore as E
    loaded = []
    for i, platform in enumerate(("Darwin arm64", "Linux x86_64")):
        root = tmp_path / str(i)
        root.mkdir()
        path = root / "frames.json"
        path.write_text(json.dumps({"decode": {"platform": platform}}))
        loaded.append(({"store": str(root), "frames_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, None))
    assert E.require_decode_platform(loaded[:1]) == "Darwin arm64"
    with pytest.raises(ValueError, match="mixed decode platforms"):
        E.require_decode_platform(loaded)
    path.write_text(json.dumps({"decode": {}}))
    loaded[-1][0]["frames_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="decode platform missing"):
        E.require_decode_platform(loaded[-1:])
