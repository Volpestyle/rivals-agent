"""Synthetic feature-contract checks; no corpus or optional torch dependency."""
import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")

from policy.bc2 import target_features as T


def frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def ring(f, x, y, w, h):
    cv2.rectangle(f, (x, y), (x + w, y + h), (83, 199, 92), 3)


def test_unknown_distinct_from_centred_target_and_expert_never_reads_pixels(monkeypatch):
    unknown = T.extract(frame())
    assert unknown.shape == (10,) and unknown.dtype == np.float32
    assert (unknown == 0).all()
    centred = T.from_boxes([(620, 330, 660, 390)])
    assert centred[0] == 1 and tuple(centred[1:4]) == (1, 0, 0)
    assert np.array_equal(centred[1:5], centred[5:9])
    monkeypatch.setattr(T, "detect_boxes", lambda _: pytest.fail("expert pixels read"))
    monkeypatch.setattr(T.teacher, "green_share", lambda _: pytest.fail("expert guard read pixels"))
    assert np.array_equal(T.extract(None, source_kind="expert"), unknown)
    assert T.extract_with_reason(None, source_kind="expert")[1] == "expert_unqualified"


def test_nearest_uses_pixels_largest_uses_area_and_ties_are_stable():
    # Horizontal offset 100px vs vertical 90px: unit-square distance would choose wrong.
    boxes = [(730, 350, 750, 370), (630, 440, 650, 460), (800, 100, 1000, 300)]
    a = T.from_boxes(boxes)
    assert a[1:5] == pytest.approx([1, 0, 90 / 720, 20 / 720])
    assert a[5:9] == pytest.approx([1, 260 / 1280, -160 / 720, 200 / 720])
    assert a[-1] == pytest.approx(np.log1p(3))
    assert np.array_equal(a, T.from_boxes(reversed(boxes)))
    tied = [(540, 350, 560, 370), (720, 350, 740, 370)]
    assert np.array_equal(T.from_boxes(tied), T.from_boxes(reversed(tied)))


def test_small_target_kept_hero_mark_dropped_and_red_not_used():
    f = frame()
    ring(f, 850, 300, 24, 40)  # <8% of height, outside hero zone
    ring(f, 450, 400, 24, 40)  # same small mark in measured hero zone
    f[200:210, 600:690] = (0, 0, 255)  # red fallback must stay off
    boxes = T.detect_boxes(f)
    assert len(boxes) == 1 and boxes[0][0] > 800
    assert T.extract(f)[-1] == pytest.approx(np.log1p(1))


def test_resolution_parity_and_single_shared_path():
    f = frame()
    ring(f, 840, 280, 50, 110)
    native = cv2.resize(f, (2560, 1440), interpolation=cv2.INTER_NEAREST)
    assert np.array_equal(T.extract(native), T.extract(f))
    assert np.array_equal(T.extract(native), T.from_boxes(T.detect_boxes(native)))


@pytest.mark.parametrize("bad", [None, np.zeros((720, 1280)), np.zeros((50, 50, 3), np.uint8)])
def test_invalid_or_cropped_input_refused(bad):
    with pytest.raises(ValueError):
        T.extract(bad)


@pytest.mark.parametrize("box", [(1, 2, 1, 4), (-1, 0, 5, 5), (0, 0, 1281, 5), (0, 0, float("nan"), 5)])
def test_invalid_boxes_refused(box):
    with pytest.raises(ValueError):
        T.from_boxes([box])


def test_unsupported_source_refused():
    with pytest.raises(ValueError):
        T.extract(None, source_kind="replay")


def test_door_abstention_shares_teacher_function_threshold_and_strict_boundary(monkeypatch):
    # Changing the teacher constant here catches an accidentally copied numeric veto.
    monkeypatch.setattr(T.teacher, "DOOR_GREEN_SHARE", .125)
    f = frame()
    boxes = [(800, 300, 840, 360)]
    monkeypatch.setattr(T, "detect_boxes", lambda _: boxes)
    monkeypatch.setattr(T.teacher, "green_share", lambda _: .125)
    assert np.array_equal(T.extract(f), T.from_boxes(boxes))
    monkeypatch.setattr(T.teacher, "green_share", lambda _: .126)
    monkeypatch.setattr(T, "detect_boxes", lambda _: pytest.fail("finder ran after abstention"))
    assert not T.extract(f).any()
    assert T.extract_with_reason(f)[1] == "teacher_door_abstention"


def test_saturated_green_scene_abstains_with_same_native_frame_as_teacher(monkeypatch):
    f = frame()
    ring(f, 840, 280, 50, 110)
    native = cv2.resize(f, (2560, 1440), interpolation=cv2.INTER_NEAREST)
    native[100:400, 200:500] = (83, 199, 92)
    assert T.teacher.green_share(native) > T.teacher.DOOR_GREEN_SHARE
    assert not T.extract(native).any()
    seen = []
    real_share = T.teacher.green_share

    def share(image):
        seen.append(image)
        return real_share(image)

    monkeypatch.setattr(T.teacher, "green_share", share)
    assert not T.extract(native).any()
    assert seen[0] is native  # no preceding resize changes the teacher's decision


def test_known_and_unknown_reasons():
    f = frame()
    assert T.extract_with_reason(f)[1] == "no_green_detection"
    ring(f, 840, 280, 50, 110)
    values, reason = T.extract_with_reason(f)
    assert values[0] == 1 and reason == "detected_not_verified"
