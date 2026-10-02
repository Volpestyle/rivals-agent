"""Pixel-derived range target positions; no target identity or camera calibration.

Contract: [known, nearest_visible, nearest_dx, nearest_dy, nearest_h,
largest_visible, largest_dx, largest_dy, largest_h, log1p_count], float32.
Offsets are (cx-640)/1280 and (cy-360)/720, positive right/down; height is h/720.
Nearest uses Euclidean distance in 1280x720 pixels, not stretched unit coordinates.
Both slots may describe the same detection. Unknown is all-zero WITH known=0:
its coordinates/count are placeholders, never a centred target or absence of enemies.
Consumers must respect known. Expert rows always remain unknown, without reading pixels.

The unchanged green finder supplies hero/HUD exclusion and may still box scenery or
project a body from a lone nameplate. Known means detected, not verified correct.
Extraction shares the teacher's door abstention; raw detect_boxes/from_boxes do not.
No reset eligibility, tracking, focal length or gain is used.
Both offline and any future live consumer must call this same full-frame path.
"""
import cv2
import numpy as np

from perception.outline import find_enemies
from rl.aim import teacher

SIZE = (1280, 720)
FIELDS = ("known", "nearest_visible", "nearest_dx", "nearest_dy", "nearest_h",
          "largest_visible", "largest_dx", "largest_dy", "largest_h", "log1p_count")


def _check_frame(frame_bgr):
    if (not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8
            or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3):
        raise ValueError("expected a uint8 full-frame BGR image")
    h, w = frame_bgr.shape[:2]
    if h == 0 or w == 0 or w * 9 != h * 16:
        raise ValueError("expected a nonempty 16:9 full frame; do not stretch a crop")


def detect_boxes(frame_bgr):
    """Raw, unguarded green xyxy boxes in 1280x720 pixels; diagnostics only."""
    _check_frame(frame_bgr)
    frame = cv2.resize(frame_bgr, SIZE, interpolation=cv2.INTER_AREA)
    return tuple(tuple(d.bbox) for d in find_enemies(frame, scale=1.0))


def from_boxes(boxes):
    """Summarise finder xyxy boxes in 1280x720 pixels. Ties use lexicographic xyxy."""
    out = np.zeros(len(FIELDS), dtype=np.float32)
    boxes = sorted(tuple(map(float, b)) for b in boxes)
    if not boxes:
        return out
    for b in boxes:
        if (len(b) != 4 or not all(np.isfinite(b))
                or not (0 <= b[0] < b[2] <= SIZE[0] and 0 <= b[1] < b[3] <= SIZE[1])):
            raise ValueError("boxes must be finite, positive-area xyxy inside 1280x720")
    nearest = min(boxes, key=lambda b: ((b[0] + b[2]) / 2 - SIZE[0] / 2) ** 2
                  + ((b[1] + b[3]) / 2 - SIZE[1] / 2) ** 2)
    largest = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    out[0], out[-1] = 1, np.log1p(len(boxes))
    for start, b in ((1, nearest), (5, largest)):
        out[start:start + 4] = (1, (b[0] + b[2]) / (2 * SIZE[0]) - .5,
                              (b[1] + b[3]) / (2 * SIZE[1]) - .5, (b[3] - b[1]) / SIZE[1])
    return out


def extract(frame_bgr, *, source_kind="range"):
    """Ten guarded values; experts are unknown without pixel access (frame may be None)."""
    return extract_with_reason(frame_bgr, source_kind=source_kind)[0]


def extract_with_reason(frame_bgr, *, source_kind="range"):
    """Return (ten values, reason) so unknowns retain their provenance.

    The teacher's green-share rule sees the original full frame, exactly as Teacher
    does. Abstention can suppress real enemies behind glass or other green scenes.
    """
    if source_kind == "expert":
        return from_boxes(()), "expert_unqualified"
    if source_kind != "range":
        raise ValueError("source_kind must explicitly be range or expert")
    _check_frame(frame_bgr)
    if teacher.green_share(frame_bgr) > teacher.DOOR_GREEN_SHARE:
        return from_boxes(()), "teacher_door_abstention"
    boxes = detect_boxes(frame_bgr)
    return from_boxes(boxes), "detected_not_verified" if boxes else "no_green_detection"
