"""perception/autolabel.py and eval.py: a re-run cannot overwrite the committed contact sheets in docs/evidence/l3/."""
import argparse
import sys
from pathlib import Path

import cv2  # noqa: F401  (autolabel needs it; tests/conftest.py collects this module only in the perception group)
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "perception"))

import autolabel  # noqa: E402
import eval as l3eval  # noqa: E402


def test_defaults_write_outside_the_evidence():
    for default in (autolabel.SHEET, l3eval.EVAL_SHEET):
        assert default.startswith("data/l3/")


@pytest.mark.parametrize("name", ["autolabel-sheet.jpg", "eval-sheet.jpg"])
def test_an_existing_evidence_sheet_is_refused_before_any_work(name):
    committed = ROOT / "docs/evidence/l3" / name
    assert committed.is_file()
    before = committed.read_bytes()
    with pytest.raises(argparse.ArgumentTypeError, match="refusing to overwrite committed evidence"):
        autolabel.sheet_path(str(committed))
    assert committed.read_bytes() == before


def test_a_new_path_is_allowed_and_its_folder_made(tmp_path):
    out = tmp_path / "l3" / "sheet.jpg"
    assert autolabel.sheet_path(str(out)) == out and out.parent.is_dir() and not out.exists()
