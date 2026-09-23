"""Setup reference for one native range screenshot: range HUD, resources, enemy boxes and their height bins. Offline.

    uv run --offline --no-project --python 3.11 --with opencv-python-headless --with numpy python -B scout.py <native.png> [--live DIR]

Runs the loop's own readers (agent.loop.default_perception) from the live tree on a saved frame and classifies each box
with agent.brain.range_of: near h >= .325, mid .065 < h < .325, h = (y2 - y1) / frame height. Sends nothing. The operator
uses it to place Spider-Man for the planned bin; the trial's bin is the one measured on its own first-phase frame.
"""
import argparse
import json
import sys
from pathlib import Path

LIVE = Path("C:/Users/volpe/repos/rivals-agent-live")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frame", type=Path)
    ap.add_argument("--live", type=Path, default=LIVE)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(a.live.resolve()))
    import cv2
    from agent.brain import range_of
    from agent.loop import default_perception
    from agent.state import State
    frame = cv2.imread(str(a.frame))
    if frame is None:
        raise SystemExit(f"unreadable frame {a.frame}")
    p = default_perception()
    w, h = p.size(frame)
    if (w, h) != (2560, 1440):
        print(f"warning: frame is {w}x{h}, not native 2560x1440", file=sys.stderr)
    hud = p.hud(frame)
    state = State(t=0.0, frame=(w, h), **hud)
    boxes = [("aim", d) for d in p.aim(frame)] + [("wide", d) for d in p.wide(frame)]
    print(json.dumps({
        "frame": str(a.frame), "size": [w, h], "in_range": bool(p.in_range(frame)), "idle_banner": bool(p.idle(frame)),
        "hp": hud.get("hp"), "max_hp": hud.get("max_hp"), "webs": hud.get("webs"),
        "abilities": {k: v for k, v in (hud.get("abilities") or {}).items()},
        "boxes": [{"finder": src, "bbox": [round(v) for v in d.bbox], "plate": d.plate,
                   "h": round((d.bbox[3] - d.bbox[1]) / h, 4), "bin": range_of(d, state)} for src, d in boxes],
        "note": "setup reference only; readiness, identity and full health are the operator's native audit",
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
