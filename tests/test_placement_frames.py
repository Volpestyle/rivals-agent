"""The placement frame table against pixels: the finder's boxes on each held image equal the recorded ones.

Needs opencv and numpy (`uv run --group perception pytest tests/test_placement_frames.py`). Each row of
tests/fixtures/placement/frames.json names an image by path and SHA-256. The images live in gitignored run folders,
the committed pilot evidence, or the operator's C:\\desk\\out on the PC; a row whose image is absent or whose bytes
differ is skipped with that reason, never re-labelled. tests/fixtures/placement/build_frames.py wrote the table.
"""
import hashlib
import json
from pathlib import Path

import cv2
import pytest

from agent import placement as P
from agent.loop import default_perception

ROOT = Path(__file__).resolve().parent.parent
FRAMES = json.loads((ROOT / "tests/fixtures/placement/frames.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def perception():
    return default_perception()


def _image(row):
    path = Path(row["path"]) if Path(row["path"]).is_absolute() else ROOT / row["path"]
    if not path.exists():
        pytest.skip(f"image absent on this machine: {row['path']}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        pytest.skip(f"image bytes differ from the pinned hash: {row['path']}")
    return cv2.imread(str(path))


@pytest.mark.parametrize("row", FRAMES, ids=[f"{r['set']}:{Path(r['path']).name}" for r in FRAMES])
def test_finder_output_and_class_from_pixels(row, perception):
    frame = _image(row)
    assert [frame.shape[1], frame.shape[0]] == row["size"]
    assert bool(perception.in_range(frame)) == row["in_range"]
    boxes = [[round(v, 1) for v in d.bbox] for d in perception.wide(frame)]
    assert boxes == row["boxes"]
    got = P.classify((frame.shape[1], frame.shape[0]), boxes, row["in_range"], False)
    assert got.pose is None                                  # a frame of unknown pitch never yields a pose
    if row["label"] == "NOT_PAIR":
        assert got.kind == "LOST"
    elif row["label"] == "PAIR":
        assert got.kind in ("UNLEVELLED", "LOST")            # LOST only for the two conservative rejections
    else:
        assert got.kind == row["label"]
