"""Aim teacher (VUH-1321, aim curriculum step 2): frame + selected target -> camera correction in degrees per step.

The scripted compat aimer (agent/camera_compat.py, which passed run-05) as a label oracle. It keeps the compat aimer's
rules and converts its pixel error to the policy's camera units (vocab: degrees per 30 Hz step, yaw + right, pitch +
down):
  target     the eligible enemy outline the aimer would hold: the tracked one while it stays within TRACK_PX, else the
             one nearest the crosshair (compat acquires the nearest, then holds its track id)
  error      box centre minus frame centre, in 1280-wide px (compat's `error`)
  deadband   an axis within DEADBAND_PX_1280 of the target gets 0 (compat's 12 px deadband)
  degrees    atan(error / focal), focal = FOCAL_1280 (agent/placement.py's 930 px at 2560, from the 2.08 s full turn
             at .45 stick; the camera map's measured focal is still "missing", so magnitudes carry that assumption,
             signs do not)
  per step   GAIN of the remaining angle per step, clamped to vocab.CLAMP_DEG (compat closes in short pulses; a
             proportional step is the same direction with a smooth size, and GAIN is fitted on James's turns)

Labels are None when no eligible target is visible: the teacher has nothing to say there, and the dataset must
not read that as "don't turn".
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEADBAND_PX_1280 = 12.          # agent.camera_compat.LIMITS.deadband_px_1280
FOCAL_1280 = 465.               # agent.placement.FOCAL_PX (930) at 1280 wide
GAIN = .25                      # share of the remaining angle per 30 Hz step; provisional until fitted on James
TRACK_PX_1280 = 80.             # rl.aim.metrics.TRACK_PX (160 at 2560)


@dataclass(frozen=True)
class Label:
    box: tuple                  # target box in the frame's pixels
    err_px_1280: tuple          # (x, y) box centre minus frame centre
    angle_deg: tuple            # (yaw, pitch) to the box centre
    step_deg: tuple             # (yaw, pitch) the teacher asks for this step
    cam_class: tuple            # vocab classes of step_deg


def error_1280(box, size):
    w, h = size
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return (cx - w / 2) * 1280 / w, (cy - h / 2) * 1280 / w


def angles(err, focal=FOCAL_1280):
    return tuple(math.degrees(math.atan(e / focal)) for e in err)


def step(angle, err, gain=GAIN):
    from policy.range_bc import vocab
    out = []
    for a, e in zip(angle, err):
        out.append(0. if abs(e) <= DEADBAND_PX_1280 else max(-vocab.CLAMP_DEG, min(vocab.CLAMP_DEG, gain * a)))
    return tuple(out)


def select(boxes, size, previous=None):
    """The compat aimer's target among eligible boxes: keep the tracked one, else the one nearest the crosshair."""
    if not boxes:
        return None
    k = 1280 / size[0]
    centre = lambda b: ((b[0] + b[2]) / 2 * k, (b[1] + b[3]) / 2 * k)
    if previous is not None:
        px, py = centre(previous)
        near = min(boxes, key=lambda b: (centre(b)[0] - px) ** 2 + (centre(b)[1] - py) ** 2)
        nx, ny = centre(near)
        if (nx - px) ** 2 + (ny - py) ** 2 <= TRACK_PX_1280 ** 2:
            return near
    return min(boxes, key=lambda b: sum(e * e for e in error_1280(b, size)))


def label(box, size, gain=GAIN, focal=FOCAL_1280):
    from policy.range_bc import vocab
    err = error_1280(box, size)
    ang = angles(err, focal)
    st = step(ang, err, gain)
    return Label(tuple(box), err, ang, st, tuple(vocab.camera_class(v) for v in st))


class Teacher:
    """Stateful over one episode: frame -> Label or None. `finder(frame)` returns eligible enemy boxes."""

    def __init__(self, finder=None, gain=GAIN, focal=FOCAL_1280):
        self.finder = finder or default_finder()
        self.gain, self.focal, self.previous = gain, focal, None

    def reset(self):
        self.previous = None

    def __call__(self, frame):
        size = (frame.shape[1], frame.shape[0])
        box = select(self.finder(frame), size, self.previous)
        self.previous = box
        return None if box is None else label(box, size, self.gain, self.focal)


def default_finder():
    """The live finder's eligible enemy outlines (agent.loop.default_perception().wide + agent.range_reset.eligible),
    the same rule rl.aim.metrics and the reset use."""
    from agent import loop as L
    from agent.range_reset import eligible
    percept = L.default_perception()

    def find(frame):
        size = (frame.shape[1], frame.shape[0])
        return [tuple(d.bbox) for d in eligible(percept.wide(frame), size)]
    return find
