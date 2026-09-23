"""scripts/place.py --replay on real recorded frames, from pixels: the pilot slot archives and the placement stills.

Needs opencv and numpy (`uv run --group perception pytest tests/test_place_frames.py`). The run folders are gitignored
and the stills live in the operator's C:\\desk\\out on the PC; an absent source skips with that reason.
"""
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import place  # noqa: E402
from agent.loop import default_perception  # noqa: E402

RUNS = ["data/l1/galacta-pilot-20260923-01-learned", "data/l1/galacta-pilot-20260923-03-scripted",
        "data/l1/galacta-pilot-20260922-04-learned", "data/l1/galacta-pilot-20260922-03-scripted"]
STILLS = [f"C:/desk/out/p0923-{n}" for n in ("restart-look.png", "pl-up-a.jpg", "pl-wall-a.jpg", "pl-along-a.jpg",
          "pl-along-b.jpg", "pl-along-c.jpg", "pl-stair-a.jpg", "pl-stair-b.jpg", "pl-stair-c.jpg",
          "pl-stair2-a.jpg", "pl-stair2-b.jpg", "pl-stair2-c.jpg", "pl-stair3-a.jpg", "pl-stair3-b.jpg",
          "pl-stair3-c.jpg")]


@pytest.fixture(scope="module")
def perception():
    return default_perception()


@pytest.mark.parametrize("run", RUNS)
def test_slot_archive_replays_without_a_move_lacking_a_pose(run, perception):
    folder = ROOT / run
    if not folder.is_dir():
        pytest.skip(f"run folder absent on this machine: {run}")
    report = place.replay(place.records_from_images(place.image_paths([folder]), perception, cv2.imread), "mid",
                          allow_none=True)
    # frames of unknown pitch: never a pose, so never a move and nothing to compare (review D2: said, not implied)
    assert report["decisions"] > 0 and report["ok"] and report["compared"] == 0, report["mismatches"][:3]


def test_placement_stills_are_lost_and_never_move(perception):
    present = [p for p in STILLS if Path(p).is_file()]
    if not present:
        pytest.skip("the operator's placement stills are absent on this machine")
    report = place.replay(place.records_from_images(present, perception, cv2.imread), "mid", allow_none=True)
    # stills of unknown pitch: the planner's only answer is to level the camera first (review F3), never a move
    assert report["ok"] and set(report["kinds"]) == {"LOST"} and set(report["actions"]) == {"PITCH_RESET"}
