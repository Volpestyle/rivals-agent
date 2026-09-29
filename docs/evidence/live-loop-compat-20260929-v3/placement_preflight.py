"""Read-only screenshot placement check; never opens a pad or sends input."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def placement(detections, size):
    from agent.state import ENEMY
    w, h = size
    left, right = [], []
    for d in detections:
        if d.cls != ENEMY:
            continue
        x, y = d.center
        if x < w / 2 - 48 * w / 2560 and (x < .27 * w or y < .39 * h):
            left.append(d.bbox)
        elif x > w / 2 + 48 * w / 2560:
            right.append(d.bbox)
    return {"left": left, "right": right, "pass": bool(left and right)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--frame', type=Path, help='offline validation only')
    source.add_argument('--live-screenshot', action='store_true')
    ap.add_argument('--game-pid', type=int)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    import cv2
    from agent.loop import default_perception, foreground_pid_guard
    percept = default_perception()
    if a.live_screenshot:
        if not a.game_pid:
            ap.error('--game-pid required for live screenshot')
        focused = foreground_pid_guard(a.game_pid)
        if focused() is not True:
            raise SystemExit('game not focused; refuse launch')
        from scripts.capture import Capture
        cap = Capture('dxcam')
        try:
            frame = None
            until = time.perf_counter() + 2
            while frame is None and time.perf_counter() < until:
                frame = cap.grab()
        finally:
            cap.cam.release()
        if focused() is not True:
            raise SystemExit('focus changed; refuse launch')
    else:
        frame = cv2.imread(str(a.frame))
    if frame is None:
        raise SystemExit('no screenshot; refuse launch')
    a.out.mkdir(parents=True, exist_ok=False)
    if not cv2.imwrite(str(a.out / 'placement.png'), frame):
        raise OSError('screenshot retention failed; refuse launch')
    result = placement(percept.wide(frame), percept.size(frame))
    result['range'] = bool(percept.in_range(frame))
    result['idle'] = bool(percept.idle(frame))
    result['pass'] = result['pass'] and result['range'] and not result['idle']
    result['mode'] = 'live_screenshot' if a.live_screenshot else 'offline_only'
    (a.out / 'placement.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
