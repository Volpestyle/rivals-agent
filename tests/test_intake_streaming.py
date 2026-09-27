"""Bounded intake storage preserves ordered pixel data and vote results."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_decode_yields_bounded_windows_with_identical_pixels(monkeypatch):
    intake = load('streaming_intake', ROOT / 'data/human/sessions/intake_session.py')
    monkeypatch.setattr(intake, 'W', 2)
    monkeypatch.setattr(intake, 'H', 1)
    monkeypatch.setattr(intake, 'check_before_decode', lambda: None)
    calls = []
    expected = list(range(21, 201, 10))

    def run(cmd, **kwargs):
        count = int(cmd[cmd.index('-frames:v') + 1])
        assert count <= 8
        assert cmd[cmd.index('-threads') + 1] == '2'
        start = sum(calls)
        calls.append(count)
        return SimpleNamespace(stdout=b''.join(bytes([ms]) * 6 for ms in expected[start:start+count]))

    monkeypatch.setattr(intake.subprocess, 'run', run)
    decoded = intake._decode(SimpleNamespace(video='synthetic-only.mkv'), expected)
    assert calls == []  # creating the iterator must not decode or retain the whole request
    for ms, frame in decoded:
        assert frame.shape == (1, 2, 3)
        assert np.all(frame == ms)
    assert calls == [8, 8, 2]


def test_vote_spool_preserves_native_fixtures_and_replay_order(tmp_path):
    scan = load('bounded_scan', ROOT / 'data/human/sessions/code-snapshot-f8fd92c-bounded-20260927'
                / 'data/human/inspection/20260922T033319-205Z-24328-2/regime-scan/scan.py')
    frames = [cv2.imread(str(ROOT / 'tests/fixtures/intake_match' / name)) for name in
              ('052001-own-webs3.jpg', '052001-own-webs0.jpg', '052001-spectate.jpg')] * 3
    assert all(f is not None for f in frames)
    spool = scan.DiskFrames(tmp_path / 'votes')
    for frame in frames:
        spool.append(frame)
    assert all(isinstance(p, Path) for p in spool.paths)
    for _ in range(2):
        assert all(np.array_equal(a, b) for a, b in zip(frames, spool))
    assert scan.hud.slot_mapping(frames, scan.hud.MK) == scan.hud.slot_mapping(spool, scan.hud.MK)
    spool.close()
    assert not (tmp_path / 'votes').exists()
