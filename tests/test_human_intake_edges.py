"""The intake's edge proof on real frames: 232304's spawn edge (lead decision 2026-09-25). Needs cv2 (perception group)."""
import importlib.util
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")   # perception group; the stdlib suite skips this module

from agent import human_intake as hi

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/intake_edge"
# composition ns of 232304's frames 308-310 (frames.csv, presentation order)
F308, F309, F310 = 360061738644248, 360061746977581, 360061755310914
PERIOD = 8_333_333


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HudAlwaysPresent:
    """The intake scan's reading of these three frames: HUD present on all of them."""

    @staticmethod
    def read_sample(img, layout, mapping):
        return {"hud_present": True}


def frames():
    return {t: cv2.imread(str(FIX / f"232304-f{i}.jpg")) for t, i in ((F308, 308), (F309, 309), (F310, 310))}


def test_the_live_guard_rejects_the_two_spawn_in_frames_and_proves_the_next():
    guard = module("record_under_test", ROOT / "scripts/record.py").in_range
    got = {t: guard(img) for t, img in frames().items()}
    assert got == {F308: False, F309: False, F310: True}


def test_the_seg_002_opening_moves_from_f308_to_f310():
    guard = module("record_under_test", ROOT / "scripts/record.py").in_range
    intake = module("intake_session_under_test", ROOT / "data/human/sessions/intake_session.py")
    proofs = {t: intake.edge_proof(img, HudAlwaysPresent, None, None, guard) for t, img in frames().items()}
    assert [p["hud_present"] for p in proofs.values()] == [True, True, True]   # the scan alone would open at f308
    assert [proofs[t]["proof"] for t in (F308, F309, F310)] == [False, False, True]
    # the proposer, with the first HUD-present sample two frames after f310 and the frames before it proven
    sample = F310 + 2 * PERIOD
    native = {("start", sample): [(F308, False), (F309, False), (F310, True), (F310 + PERIOD, True), (sample, True)]}
    focus = [(F308 - 20 * PERIOD, sample + 600 * PERIOD)]
    hud = [(F308 - 18 * PERIOD, False)] + [(sample + k * 24 * PERIOD, True) for k in range(25)]
    segs, _ = hi.propose_segments(focus, hud, native=native, focus_settle_ns=0)
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert play[0]["start_ns"] == F310
    native_scan_only = {("start", sample): [(F308, True), (F309, True), (F310, True), (F310 + PERIOD, True), (sample, True)]}
    segs, _ = hi.propose_segments(focus, hud, native=native_scan_only, focus_settle_ns=0)
    assert [s for s in segs if s["machine_reason"] == hi.GAMEPLAY][0]["start_ns"] == F308   # what the scan alone did
