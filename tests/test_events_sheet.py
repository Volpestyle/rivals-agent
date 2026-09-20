"""Render the before/after crops for a sample of events, for hand-checking.

    uv run --group perception python -m tests.test_events_sheet \\
        data/run1 data/l6/run1-events.jsonl docs/evidence/l2/events-verified

Not a test in the assert sense -- it makes the contact sheet a human reads to
decide whether each event is real, which is the only way to put a precision
number on an extractor whose ground truth is "what the screen showed". Two crops
per event: the frame proving the old value and the frame proving the new one.

Never point this at the demo VODs: those frames are local-only and must not end
up in docs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.hud import HP_BAR, HP_TEXT, SLOT_CX, ULT, WEBS, _badge_box, _icon_box, crop  # noqa: E402

TILE = (150, 150)


def region_for(event):
    """The part of the HUD that proves this event."""
    kind, slot = event["kind"], event.get("slot")
    if kind.startswith("ability_") and slot:
        return _icon_box(SLOT_CX[slot]), f"{slot} icon"
    if kind.startswith("charges_") and slot:
        return _badge_box(SLOT_CX[slot]), f"{slot} badge"
    if kind.startswith("ult"):
        return ULT, "ult"
    if kind.startswith("web_cluster"):
        return WEBS, "ammo"
    if kind.startswith("shield") or kind.startswith("hp_") or kind in ("death", "respawn"):
        return HP_TEXT, "hp"
    if kind == "max_hp_changed":
        return HP_TEXT, "hp"
    return HP_BAR, "bar"


def tile(run_dir, index, box, label):
    path = Path(run_dir) / f"{index:06d}.jpg"
    frame = cv2.imread(str(path))
    if frame is None:
        return np.zeros((*TILE, 3), np.uint8)
    img = cv2.resize(crop(frame, box), TILE, interpolation=cv2.INTER_CUBIC)
    cv2.putText(img, label, (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3)
    cv2.putText(img, label, (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 230, 255), 1)
    return img


def sheet(run_dir, events, out_stem, per_sheet=6):
    rows = []
    for n, e in enumerate(events):
        box, what = region_for(e)
        before = tile(run_dir, e["i_from"], box, f"{e['i_from']} {e['before']}")
        after = tile(run_dir, e["i_to"], box, f"{e['i_to']} {e['after']}")
        caption = np.zeros((TILE[1], 330, 3), np.uint8)
        text = f"{n}  {e['kind']}" + (f":{e['slot']}" if e.get("slot") else "")
        cv2.putText(caption, text, (6, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 230, 255), 1)
        cv2.putText(caption, f"{what}  t {e['t_from']:.1f}-{e['t_to']:.1f}s",
                    (6, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (190, 190, 190), 1)
        if e.get("amount") is not None:
            cv2.putText(caption, f"amount {e['amount']}", (6, 104),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (190, 190, 190), 1)
        rows.append(np.hstack([caption, before, after]))
    written = []
    for s in range(0, len(rows), per_sheet):
        img = np.vstack([np.pad(r, ((0, 4), (0, 0), (0, 0))) for r in rows[s:s + per_sheet]])
        path = f"{out_stem}-{s // per_sheet}.png"
        cv2.imwrite(path, img)
        written.append(path)
    return written


def pick(events, per_kind=4, seed=5):
    """A spread across kinds rather than a flat sample: the rare kinds matter."""
    import random

    by_kind = {}
    for e in events:
        by_kind.setdefault(e["kind"] + (f":{e['slot']}" if e.get("slot") else ""), []).append(e)
    rng = random.Random(seed)
    out = []
    for kind in sorted(by_kind):
        out += rng.sample(by_kind[kind], min(per_kind, len(by_kind[kind])))
    return sorted(out, key=lambda e: e["i_to"])


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 3:
        sys.exit(__doc__)
    run_dir, events_path, out_stem = argv[:3]
    per_kind = int(argv[3]) if len(argv) > 3 else 4
    events = [json.loads(line) for line in Path(events_path).read_text().splitlines() if line.strip()]
    chosen = pick(events, per_kind)
    written = sheet(run_dir, chosen, out_stem)
    print(json.dumps({"events_total": len(events), "sampled": len(chosen),
                      "sheets": written,
                      "kinds": sorted({e["kind"] + (f":{e['slot']}" if e.get("slot") else "")
                                       for e in chosen})}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
