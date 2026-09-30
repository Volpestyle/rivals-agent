"""Synthetic replay alignment controls; no media, corpus or model weights."""
import copy
import json

import numpy as np
import pytest

from policy.idm import labels
from policy.range_bc import vocab


def fixture():
    t = np.arange(121) / 60
    n = len(t)
    z = {"t": t, "cam": np.zeros((n, 2)), "prob": np.zeros((n, vocab.N)),
         "held": np.zeros((n, vocab.N)), "yaw_ans": np.ones(n), "pitch_ans": np.ones(n) * 2,
         "yaw_std": np.ones(n) * .1, "pitch_std": np.ones(n) * .2,
         "meta": np.array(json.dumps({"actions": list(vocab.NAMES)}))}
    kw = dict(video_path="synthetic.mp4", index_pts=t, tb=[1, 60], run_id="v:0-2", i0=0)
    old = labels.step_rows(z, {"jump": .5}, **kw)
    return z, kw, old


def test_original_grid_uses_new_answers_and_exact_frames():
    z, kw, old = fixture()
    newer = {k: v[3:-3] if getattr(v, "ndim", 0) else v for k, v in z.items()}
    newer["yaw_ans"] = newer["yaw_ans"] * 3
    rows = labels.step_rows(newer, {"jump": .5}, **kw, anchor_rows=old)
    assert len(rows) > 32
    refs = {r["anchor_ns"]: r for r in old}
    for i, r in enumerate(rows):
        ref = refs[r["anchor_ns"]]
        assert r["i"] == i and r["run"] == ref["run"] and r["frame"] == ref["frame"]
        assert r["yaw_deg"] == ref["yaw_deg"] * 3
    assert rows[0]["anchor_ns"] > old[0]["anchor_ns"]
    assert rows[-1]["anchor_ns"] < old[-1]["anchor_ns"]


@pytest.mark.parametrize("key,value", [("frame_index", 999), ("pts", 999), ("timebase", [1, 1000])])
def test_wrong_frame_identity_refused(key, value):
    z, kw, old = fixture()
    old = copy.deepcopy(old)
    old[0]["frame"][key] = value
    with pytest.raises(ValueError, match="source-frame mismatch"):
        labels.step_rows(z, {}, **kw, anchor_rows=old)


def test_missing_intervals_not_bridged_and_unknown_answers_stay_unknown():
    z, kw, old = fixture()
    z["yaw_ans"][10] = np.nan
    z["held"][20:, 0] = 1
    keep = np.ones(len(z["t"]), bool)
    keep[15:20] = False
    newer = {k: v[keep] if getattr(v, "ndim", 0) else v for k, v in z.items()}
    rows = labels.step_rows(newer, {}, **kw, anchor_rows=old)
    assert any(r["yaw_deg"] is None for r in rows)
    assert not any(.24 <= r["anchor_ns"] / 1e9 < .33 for r in rows)
    after_gap = next(r for r in rows if r["anchor_ns"] / 1e9 > .34)
    assert after_gap["held_start"][0] == 1


def test_no_reference_rows_means_no_invented_grid():
    z, kw, _ = fixture()
    assert labels.step_rows(z, {}, **kw, anchor_rows=[]) == []


def test_partial_final_step_is_omitted():
    z, kw, old = fixture()
    shortened = {k: v[:-2] if getattr(v, "ndim", 0) else v for k, v in z.items()}
    rows = labels.step_rows(shortened, {}, **kw, anchor_rows=old)
    assert all(r["anchor_ns"] / 1e9 + labels.STEP_NS / 1e9 <= shortened["t"][-1] + 1e-9 for r in rows)


def test_export_preserves_reference_and_refuses_overwrite_or_wrong_media(tmp_path, monkeypatch):
    z, kw, _ = fixture()
    media = tmp_path / "creator" / "v.mp4"
    media.parent.mkdir()
    media.write_bytes(b"synthetic media identity; never decoded")
    work = tmp_path / "work"
    (work / "new").mkdir(parents=True)
    span = {"video_id": "v", "span_id": kw["run_id"], "local_path": str(media),
            "start_s": 0, "end_s": 2, "width": 1920, "height": 1080}
    spans = tmp_path / "spans.jsonl"
    spans.write_text(json.dumps(span) + "\n")
    np.savez(labels.span_file(work, "new", span), **z)
    monkeypatch.setattr(labels.vod, "load_any", lambda *a: (None, None, {"jump": .5}))
    monkeypatch.setattr(labels, "_video_index", lambda *a: (kw["index_pts"], kw["tb"]))
    labels.export("synthetic", spans, work, tmp_path / "old", model="new")
    ref_dir = tmp_path / "old" / "new"
    ref = ref_dir / "expert-v.steps.jsonl"
    before = ref.read_bytes()
    outputs = labels.export("synthetic", spans, work, tmp_path / "aligned", model="new", anchor_dir=ref_dir)
    assert next(iter(outputs.values())) > 32
    assert ref.read_bytes() == before
    with pytest.raises(FileExistsError):
        labels.export("synthetic", spans, work, tmp_path / "aligned", model="new", anchor_dir=ref_dir)
    lines = ref.read_text().splitlines()
    h = json.loads(lines[0])
    h["media_sha256"] = "f" * 64
    ref.write_text(json.dumps(h) + "\n" + "\n".join(lines[1:]) + "\n")
    with pytest.raises(ValueError, match="different source"):
        labels.export("synthetic", spans, work, tmp_path / "wrong", model="new", anchor_dir=ref_dir)
