"""The pilot archiver never hashes a file the recorder is still writing.

    uv run pytest tests/test_archive_slot.py

On 2026-09-23 all three archived slots hashed an unfinished video (audit-slot3.md). Stdlib only; synthetic folders.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "data/runtime/galacta-pilot-20260923-preflight/operator/archive_slot.py"
if not SCRIPT.exists():
    pytest.skip("the pilot's operator folder is not on this machine", allow_module_level=True)
spec = importlib.util.spec_from_file_location("archive_slot", SCRIPT)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

SUMMARY = b"[out#0/mp4 @ 0] video:304095KiB audio:0KiB muxing overhead: 0.015356%\nframe= 3555 Lsize= 304142KiB\n"


class Clock:
    """Fake time: sleep advances it, and an optional hook runs on each sleep."""

    def __init__(self, on_sleep=None):
        self.t, self.on_sleep = 0.0, on_sleep

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s
        if self.on_sleep:
            self.on_sleep(self.t)


def _slot(tmp_path, log=b"frame=  17 fps=0.0 time=00:00:00.26\n"):
    slot = tmp_path / "slots" / "03-scripted"
    slot.mkdir(parents=True)
    (slot / "scripted-recorder.json").write_text('{"record_pid": 1}')
    (slot / "scripted-record.log").write_bytes(log)
    (slot / "scripted-native.mp4").write_bytes(b"\0" * 64)
    return slot


def test_a_recorder_without_its_done_marker_is_refused(tmp_path):
    slot = _slot(tmp_path)
    clock = Clock()
    with pytest.raises(archive.Refused, match="recorder not finished"):
        archive.wait_until_settled(slot, [slot], wait_s=5, clock=clock, sleep=clock.sleep)


def test_a_finished_and_still_folder_is_hashed(tmp_path):
    slot = _slot(tmp_path, SUMMARY)
    clock = Clock()
    settled = archive.wait_until_settled(slot, [slot], wait_s=5, clock=clock, sleep=clock.sleep)
    slot_files, _ = archive.hashed(slot, tmp_path / "no-run-dir", settled)
    assert set(slot_files) == {"scripted-recorder.json", "scripted-record.log", "scripted-native.mp4"}


def test_a_file_still_growing_after_the_marker_is_refused(tmp_path):
    """Slot 1's case: the size was final but ffmpeg was still writing the header."""
    slot = _slot(tmp_path, SUMMARY)
    video = slot / "scripted-native.mp4"

    def grow(t):
        with video.open("ab") as f:
            f.write(b"x")

    clock = Clock(on_sleep=grow)
    with pytest.raises(archive.Refused, match="still changing"):
        archive.wait_until_settled(slot, [slot], wait_s=5, clock=clock, sleep=clock.sleep)


def test_a_change_during_hashing_is_refused(tmp_path):
    slot = _slot(tmp_path, SUMMARY)
    clock = Clock()
    settled = archive.wait_until_settled(slot, [slot], wait_s=5, clock=clock, sleep=clock.sleep)
    (slot / "scripted-native.mp4").write_bytes(b"\1" * 65)
    with pytest.raises(archive.Refused, match="while it was being hashed"):
        archive.hashed(slot, tmp_path / "no-run-dir", settled)
