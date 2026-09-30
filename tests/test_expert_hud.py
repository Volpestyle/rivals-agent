"""Offline adapter checks; native regressions use only retained private frames."""
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from perception import expert_hud, hud, replay_hud


@pytest.fixture(autouse=True)
def limited_threads():
    previous = cv2.getNumThreads()
    cv2.setNumThreads(2)
    yield
    cv2.setNumThreads(previous)


@pytest.fixture
def native_frame():
    root = Path(os.environ.get("RIVALS_HUD_REVIEW_FRAMES", (
        "D:/rivals-expert-footage/private-review/menu-action-check/hud-cast-check")))
    if "sealed" in str(root).lower():
        pytest.fail("sealed source refused")
    if not root.is_dir():
        pytest.skip("retained private DayMR/ReqMR review frames absent")
    for p in (root, *root.parents):
        if p.is_symlink() or getattr(p.stat(), "st_file_attributes", 0) & 0x400:
            pytest.fail("symlink/reparse source refused")

    def read(name):
        p = root / name
        if p.is_symlink() or getattr(p.stat(), "st_file_attributes", 0) & 0x400:
            pytest.fail("symlink/reparse frame refused")
        frame = cv2.imread(str(p))
        assert frame is not None and frame.shape[:2] == (1080, 1920)
        return frame

    return read


@pytest.mark.corpus
def test_native_joined_eight_and_all_retained_controls(native_frame):
    """One observed miss fixed; other 89 frames and every non-GOH row preserved."""
    changed = []
    for prefix, count in (("day74", 50), ("req7", 40)):
        for i in range(1, count + 1):
            name = f"{prefix}-{i:03}.png"
            frame = native_frame(name)
            old = replay_hud.read_frame(frame, i / 10, replay_hud.DAYMR_ORDER,
                                        source="first_person")
            new = expert_hud.read_frame(frame, i / 10, replay_hud.DAYMR_ORDER,
                                        source="first_person")
            if old != new:
                changed.append(name)
                before = next(r for r in old if r.ability == "get_over_here")
                after = next(r for r in new if r.ability == "get_over_here")
                assert before.state == "ready" and before.numeral is None
                assert after.state == "cooldown" and after.numeral == 8
            assert [r for r in old if r.ability != "get_over_here"] == [
                r for r in new if r.ability != "get_over_here"]
    assert changed == ["day74-050.png"]


@pytest.mark.corpus
def test_native_ammo_decrements_remain_resource_evidence(native_frame):
    for before, after, expected in (("req7-007.png", "req7-008.png", (5, 4)),
                                    ("day74-038.png", "day74-039.png", (3, 2))):
        rows = [expert_hud.read_frame(native_frame(name), i / 10,
                                     replay_hud.DAYMR_ORDER, source="first_person")
                for i, name in enumerate((before, after))]
        assert tuple(next(r.numeral for r in rs if r.ability == "web_cluster.ammo")
                     for rs in rows) == expected
        assert all(next(r.state for r in rs if r.ability == "get_over_here") == "ready"
                   for rs in rows)
        events, coverage, _ = replay_hud.cast_events(sum(rows, []))
        assert any(e.ability == "web_cluster" and e.count == 1 for e in events)
        assert not any(replay_hud.press_coverage(coverage, events).values())


@pytest.mark.parametrize("reason", ["column order unknown for this source", "no HUD drawn",
                                    "dead (hp 0)", "replay timeline up", "viewer not following B5"])
def test_whole_frame_abstentions_do_not_run_fallback(monkeypatch, reason):
    rows = replay_hud._unknown(1.0, reason)
    monkeypatch.setattr(replay_hud, "read_frame", lambda *a, **kw: rows)
    monkeypatch.setattr(expert_hud, "_recover_goh_countdown",
                        lambda *a: pytest.fail("fallback crossed a whole-frame abstention"))
    assert expert_hud.read_frame(None, 1, None) == rows


def test_preserve_existing_numeral_and_reject_disagreement(monkeypatch):
    frame = np.zeros((1080, 1920, 3), np.uint8)
    monkeypatch.setattr(hud, "_slot_occluded", lambda *a: False)
    monkeypatch.setattr(hud, "read_cooldown", lambda *a: 7)
    assert expert_hud._recover_goh_countdown(frame, hud.MK) is None
    monkeypatch.setattr(hud, "read_cooldown", lambda *a: None)
    monkeypatch.setattr(hud, "_masks", lambda *a, **kw: [np.zeros((50, 80), np.uint8)] * 2)
    # Alternating original and cleaned masks pass the edge-branch condition.
    edge = iter([True, False, True, False])
    monkeypatch.setattr(expert_hud, "_edge_joined_countdown", lambda *a: next(edge))
    votes = iter([8, 6])
    monkeypatch.setattr(hud, "_countdown_in", lambda *a: next(votes))
    assert expert_hud._recover_goh_countdown(frame, hud.MK) is None


def test_occluded_slot_abstains_before_cleaning(monkeypatch):
    monkeypatch.setattr(hud, "_slot_occluded", lambda *a: True)
    monkeypatch.setattr(hud, "read_cooldown", lambda *a: pytest.fail("read through occlusion"))
    assert expert_hud._recover_goh_countdown(None, hud.MK) is None
