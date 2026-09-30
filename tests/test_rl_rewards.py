"""rl.rewards on synthetic frames: the hit strokes, the KO ring against a red arm, and the event tracker."""
import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from rl.rewards import RewardTracker, hit_marker, ko_marker  # noqa: E402


def blank(h=1440, w=2560):
    return np.full((h, w, 3), (110, 90, 100), np.uint8)


def strokes(frame, r0=20, r1=60, arms=4):
    h, w = frame.shape[:2]
    s = h / 1440
    cx, cy = w // 2, h // 2
    for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1))[:arms]:
        a = (int(cx + dx * r0 * s / 2 ** .5), int(cy + dy * r0 * s / 2 ** .5))
        b = (int(cx + dx * r1 * s / 2 ** .5), int(cy + dy * r1 * s / 2 ** .5))
        cv2.line(frame, a, b, (245, 245, 245), max(1, int(5 * s)))
    return frame


def ring(frame, r=54):
    h, w = frame.shape[:2]
    s = h / 1440
    cv2.circle(frame, (w // 2, h // 2), int(r * s), (60, 60, 230), max(1, int(3 * s)))
    return frame


def test_hit_marker_fires_on_four_strokes_at_native_and_720p():
    assert hit_marker(strokes(blank())) is True
    assert hit_marker(strokes(blank(720, 1280))) is True


def test_hit_marker_quiet_on_plain_frame_and_one_stroke():
    assert hit_marker(blank()) is False
    assert hit_marker(strokes(blank(), arms=1)) is False


def test_ko_ring_fires_but_a_red_blob_does_not():
    assert ko_marker(ring(blank())) is True
    arm = blank()
    cv2.circle(arm, (1280, 720), 90, (40, 40, 220), -1)   # red at every radius, like the suit
    assert ko_marker(arm) is False


def test_tracker_counts_rising_edges_and_confirms_hp():
    tr = RewardTracker()
    steps = [tr.update(t / 10, hit, ko, hp, 250 if hp is not None else None) for t, (hit, ko, hp) in enumerate([
        (False, False, 250), (True, False, 250), (True, False, 250), (False, False, 250),
        (True, False, 180),                        # one-frame hp read: not yet confirmed
        (False, True, 180), (False, True, 180),    # KO ring held over two frames counts once
        (False, None, None), (False, False, 0), (False, False, 0),
    ])]
    assert [s.hit for s in steps] == [False, True, False, False, True, False, False, False, False, False]
    assert sum(s.ko for s in steps) == 1
    assert [s.hp_lost for s in steps if s.hp_lost] == [70, 180]
    assert sum(s.death for s in steps) == 1
    assert steps[7].hp == 180          # an unread frame keeps the last confirmed hp, not zero


def test_bonus_health_decay_is_not_damage():
    tr = RewardTracker()
    reads = [(300, 300)] * 2 + [(298, 298)] * 2 + [(296, 296)] * 2 + [(290, None)] * 2 + [(250, 250)] * 2
    assert not any(tr.update(i / 10, False, False, hp, mx).hp_lost for i, (hp, mx) in enumerate(reads))


def test_tracker_ko_refractory():
    tr = RewardTracker()
    kos = [tr.update(t, False, k, None).ko for t, k in [(0.0, True), (0.1, False), (0.5, True), (1.2, False), (1.3, True)]]
    assert kos == [True, False, False, False, True]


def test_reads_after_death_are_ignored_until_respawn_at_full_hp():
    tr = RewardTracker()
    reads = ([(40, 250, True)] * 2 + [(0, 250, True)] * 2          # death
             + [(257, 275, False)] * 2 + [(125, 325, False)] * 2   # spectating teammates
             + [(200, 250, True)] * 2                               # the scoreboard's Spider-Man row, not full
             + [(250, 250, True)] * 2 + [(200, 250, True)] * 2)    # respawn, then real damage
    steps = [tr.update(i / 10, False, False, hp, mx, own) for i, (hp, mx, own) in enumerate(reads)]
    assert sum(s.death for s in steps) == 1
    assert [s.hp_lost for s in steps if s.hp_lost] == [40, 50]   # the killing blow, then post-respawn damage
