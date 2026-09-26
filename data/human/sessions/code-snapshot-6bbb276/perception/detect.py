"""Run the fine-tuned detector on one frame.

Usage: uv run --no-project --with ultralytics python perception/detect.py <weights.pt> <image> [annotated-out.jpg]

Library use (what the agent loop imports):
    det = Detector("data/runs/range/weights/best.pt")
    state_detections = det(frame_bgr)   # list[agent.state.Detection]

Returns agent.state.Detection directly, so there is one definition of the shape.
`distance` and `tagged` are left None: this detector estimates neither, and under
state.py's rule None means "not read", never a guess. bbox is in pixels of the
frame that was passed in -- feed it the same frame size the agent puts in
State.frame.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `agent`

from agent.state import ANCHOR, ENEMY, TARGET, Detection  # noqa: E402

CLASSES = [ENEMY, TARGET, ANCHOR]
_COLOURS = {ENEMY: (0, 255, 0), TARGET: (0, 200, 255), ANCHOR: (255, 160, 0)}


def pick_device():
    import torch
    if torch.cuda.is_available():
        return 0
    return "mps" if torch.backends.mps.is_available() else "cpu"


class Detector:
    def __init__(self, weights, imgsz=1280, conf=0.25, device=None):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        device = pick_device() if device is None else device
        self.kw = dict(imgsz=imgsz, conf=conf, device=device, verbose=False)
        if device == 0:
            self.kw["half"] = True  # fp16 on CUDA only; passing it at all warns on this ultralytics

    def __call__(self, frame_bgr):
        r = self.model.predict(frame_bgr, **self.kw)[0]
        return [Detection(cls=r.names[int(c)], bbox=tuple(round(v, 1) for v in box), conf=round(float(p), 3))
                for box, c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist())]


def draw(frame_bgr, dets):
    import cv2
    for d in dets:
        x1, y1, x2, y2 = map(int, d.bbox)
        colour = _COLOURS.get(d.cls, (200, 200, 200))
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(frame_bgr, f"{d.cls} {d.conf:.2f}", (x1, max(y1 - 6, 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    return frame_bgr


if __name__ == "__main__":
    import cv2
    frame = cv2.imread(sys.argv[2])
    assert frame is not None, f"cannot read {sys.argv[2]}"
    dets = Detector(sys.argv[1])(frame)
    for d in dets:
        print(d)
    if len(sys.argv) > 3:
        cv2.imwrite(sys.argv[3], draw(frame, dets))
