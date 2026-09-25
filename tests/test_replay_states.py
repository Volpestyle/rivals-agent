"""Checks for perception.replay_states: the shape of what it hands the brain.

    uv run --no-project --with opencv-python-headless --with numpy \
        python -m tests.test_replay_states

The accuracy of the readers themselves is tests/test_hud.py's job. This one is
about the seam: that a recorded run becomes States agent.replay can load, that
the finder really is a plain function, and that a frame the recording lists but
does not have is skipped rather than silently becoming an empty State.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.replay import load, run  # noqa: E402
from agent.state import ENEMY, Detection, State  # noqa: E402
from perception.replay_states import unknown_fractions, walk  # noqa: E402

RUN = ROOT / "tests" / "fixtures" / "range"


def _staged(frames, tmp):
    """A miniature run directory built from real recorded frames."""
    rows = []
    for i, name in enumerate(frames):
        (tmp / name).write_bytes((RUN / name).read_bytes())
        rows.append({"i": i, "t": round(i * 0.1, 3), "file": name})
    (tmp / "frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp


def _frames(n=6):
    return ["pos-fight-017.jpg", "pos-fight-060.jpg", "pos-fight-101.jpg"][:n]


def test_walk_makes_loadable_states():
    from perception.outline import detect

    names = _frames()
    with tempfile.TemporaryDirectory() as d:
        tmp = _staged(names, Path(d))
        states, stats = walk(tmp, detect)
        assert stats["read"] == len(names), stats
        assert stats["missing"] == 0, stats

        out = Path(d) / "states.jsonl"
        out.write_text("".join(json.dumps(s.to_dict()) + "\n" for s in states))
        again = load(out)               # agent.replay must accept what we wrote
        assert len(again) == len(states)
        assert run(again, hz=10.0), "the brain produced no decisions"

    for s in states:
        assert isinstance(s, State)
        frame = cv2.imread(str(RUN / names[0]))
        assert s.frame == (frame.shape[1], frame.shape[0]), s.frame
        assert s.detections is not None, "outline ran, so detections is a list, not None"
        for d in s.detections:
            assert isinstance(d, Detection)
            if d.cls == ENEMY:
                assert d.tagged in (True, False, None)


def test_finder_is_a_plain_function():
    """No registry, no plugin lookup: anything callable does."""
    names = _frames(3)
    box = Detection(cls=ENEMY, bbox=(600.0, 300.0, 660.0, 420.0), conf=0.5)
    with tempfile.TemporaryDirectory() as d:
        tmp = _staged(names, Path(d))
        states, _ = walk(tmp, lambda frame: [box])
        assert all(len(s.detections) == 1 for s in states)
        # the finder left tagged unset; this lane fills it in
        assert all(s.detections[0].tagged in (True, False, None) for s in states)

        none_states, _ = walk(tmp, None)
        assert all(s.detections is None for s in none_states), \
            "no finder must mean 'did not run', not 'ran and saw nothing'"


def test_missing_frame_is_skipped_not_faked():
    names = _frames(3)
    with tempfile.TemporaryDirectory() as d:
        tmp = _staged(names, Path(d))
        (tmp / names[1]).unlink()
        states, stats = walk(tmp, None)
        assert stats["missing"] == 1 and stats["read"] == len(names) - 1, stats
        assert len(states) == len(names) - 1


def test_unknown_fractions_shape():
    s = State(t=0.0, frame=(1280, 720), hp=None, detections=None)
    u = unknown_fractions([s])
    assert u["hp"] == 1.0 and u["detections"] == 1.0
    assert u["on_target"] == 1.0
    assert unknown_fractions([]) == {}


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
