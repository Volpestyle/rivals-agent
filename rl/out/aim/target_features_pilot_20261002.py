"""Fourteen explicit retained development frames, CPU only; no videos, fits or corpus writes.

Run from the repository: python rl/out/aim/target_features_pilot_20261002.py
Historical RAW-detector baseline: deliberately bypasses the later guarded extract().
Writes same-stem JSON, a full-resolution annotated sheet and a compact overview.
Do not rerun over the preserved historical artifacts to check the later guard.
"""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
if os.name == "nt":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from policy.bc2 import target_features as T
from scripts import job_status

STEM = Path(__file__).with_suffix("")
SAMPLES = [
    ("centred control", "compat-check-20260929/learned-01-a/000000.jpg"),
    ("open left/up", "rl-sitting-20260930-04/ep-000-bc/000027.jpg"),
    ("multiple/distant", "rl-sitting-20260930-01/ep-000-bc/000000.jpg"),
    ("door glass", "rl-sitting-20260930-07/ep-004-bc/000056.jpg"),
    ("04 start", "rl-sitting-20260930-04/ep-000-bc/000000.jpg"),
    ("04 later", "rl-sitting-20260930-04/ep-000-bc/000100.jpg"),
    ("04 end", "rl-sitting-20260930-04/ep-000-bc/000150.jpg"),
    ("01 middle", "rl-sitting-20260930-01/ep-000-bc/000070.jpg"),
    ("01 end", "rl-sitting-20260930-01/ep-000-bc/000115.jpg"),
    ("07-004 start", "rl-sitting-20260930-07/ep-004-bc/000000.jpg"),
    ("07-004 end", "rl-sitting-20260930-07/ep-004-bc/000117.jpg"),
    ("multiple targets", "rl-sitting-20260930-07/ep-000-bc/000055.jpg"),
    ("hero-only wall", "rl-sitting-20260930-07/ep-006-bc/000050.jpg"),
    ("empty foliage", "rl-sitting-20260930-07/ep-001-rl/000070.jpg"),
]
# Manual visual observations after native-pixel inspection, not a ground-truth dataset.
# Tuple: raw box ids visibly overlapping enemies; observation. Partial boxes count as
# overlapping an enemy here, NOT as correct full-body localisation.
INSPECTION = [
    ([0, 1], "Right/centred bot mostly boxed; left bot only right-side fragment."),
    ([0, 1], "Nearest left bot partially boxed (left arm/side missing); largest right bot mostly boxed."),
    ([0], "Right distant bot boxed (46/720 height); visible left bot entirely missed."),
    ([], "FALSE KNOWN: lone box is door/ceiling scenery; visible enemies through glass missed."),
    ([0], "Right small bot partial body, head omitted (32/720 height); left bot missed."),
    ([0, 1], "Nearest left bot partial body; largest right bot mostly boxed."),
    ([0, 1], "Both bots mostly boxed; nearest left, largest right."),
    ([0], "Right distant bot boxed; visible left bot missed."),
    ([0], "Right distant bot boxed; visible left bot missed."),
    ([], "Unknown despite visible enemies through door glass; no raw detections."),
    ([], "FALSE KNOWN: lone box is door/ceiling scenery; visible enemies through glass missed."),
    ([0, 1], "Nearest is only the left bot's left limb fragment; largest right bot mostly boxed."),
    ([], "Hero and wall only; no visible enemy, correctly unknown."),
    ([], "Hero and foliage only; no visible enemy, correctly unknown."),
]


def annotation(i):
    ids, note = INSPECTION[i]
    return dict(enemy_overlapping_raw_box_ids=ids, observation=note,
                false_known=i in (3, 10), confidence="high for object-vs-scenery; full-body extents not labelled")


def main():
    cv2.setNumThreads(2)
    job = "target-features-pilot-20261002"
    job_status.write(job, owner="explore-policy", stage="running", host="pc", evidence=str(STEM) + ".json")
    deny = json.loads(Path("data/human/sealed-denylist.v2.json").read_text())
    denied_ids = {r["session_id"] for r in deny["sessions"]}
    excluded = json.loads(Path("rl/aim/exclusions.json").read_text())["episodes"]
    rows, latency = [], []
    # Source frames are 2560x1440: keep native pixels in the large sheet.
    native = Image.new("RGB", (5120, 7 * 1520), "#121822")
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
    for i, (purpose, suffix) in enumerate(SAMPLES):
        path = Path("data/calibration") / suffix
        assert "sealed" not in path.as_posix().lower()
        assert not any(sid in path.as_posix() for sid in denied_ids)
        assert path.parent.as_posix() not in excluded
        frame = cv2.imread(str(path))
        assert frame is not None and frame.shape == (1440, 2560, 3)
        start = time.perf_counter()
        boxes = T.detect_boxes(frame)
        values = T.from_boxes(boxes)
        elapsed = (time.perf_counter() - start) * 1000
        latency.append(elapsed)
        # Preserve the raw baseline after extract() gained the shared teacher veto.
        assert np.array_equal(values, T.from_boxes(T.detect_boxes(frame)))
        canvas = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(canvas)
        for j, b in enumerate(boxes):
            native_box = tuple(v * 2 for v in b)
            draw.rectangle(native_box, outline="#ffd04d", width=4)
            draw.text((native_box[0], max(0, native_box[1] - 32)), str(j), fill="#ffd04d", font=font)
        # Crosshair and selected centres. N cyan, L magenta, no geometric label for unknown.
        for offset, colour, label in ((2, "#00ffff", "N"), (6, "#ff55ff", "L")):
            if values[0]:
                x, y = (float(values[offset]) + .5) * 2560, (float(values[offset + 1]) + .5) * 1440
                draw.ellipse((x - 8, y - 8, x + 8, y + 8), outline=colour, width=3)
                draw.text((x + 10, y), label, fill=colour, font=font)
        x, y = (i % 2) * 2560, (i // 2) * 1520
        native.paste(canvas, (x, y + 80))
        label = f"{i:02}: {purpose} | known={int(values[0])}, count={len(boxes)} | {elapsed:.1f}ms"
        ImageDraw.Draw(native).text((x + 10, y + 6), label + "\n" + suffix, fill="white", font=font)
        rows.append(dict(id=i, purpose=purpose, image=path.as_posix(), native_size=[2560, 1440],
                         boxes_720=boxes, values=values.tolist(), latency_ms=elapsed,
                         reason="detected_not_verified" if values[0] else "no_green_detection",
                         inspection=annotation(i)))
    native.save(str(STEM) + ".native.jpg", quality=92)
    native.resize((1600, 3325)).save(str(STEM) + ".overview.jpg", quality=92)
    # Four pages of native-pixel zooms for visual inspection, no resampling.
    for page in range(4):
        details = Image.new("RGB", (1280, min(4, len(rows) - page * 4) * 820), "#121822")
        for slot in range(4):
            i = page * 4 + slot
            if i >= len(rows):
                break
            x, y = (i % 2) * 2560, (i // 2) * 1520
            # Fixed central scene region includes the measured bots and door false positives.
            details.paste(native.crop((x + 640, y + 180, x + 1920, y + 960)), (0, slot * 820 + 40))
            ImageDraw.Draw(details).text((8, slot * 820 + 4), f"{i:02}: {rows[i]['purpose']} (native pixels)",
                                         fill="white", font=font)
        details.save(str(STEM) + f".detail-{page + 1}.jpg", quality=92)
    result = dict(cost_usd=0, device="CPU BelowNormal, OpenCV 2 threads", samples=len(rows),
                  fields=T.FIELDS, unknown="all-zero with known=0; geometry and count are placeholders",
                  expert="unconditionally unknown; no expert pixels opened", raw_path_parity=True,
                  extraction_mode="historical raw detector; guarded extract intentionally bypassed",
                  latency_ms=dict(first=latency[0], p50=float(np.median(latency[1:])),
                                  p95=float(np.percentile(latency[1:], 95)), max=max(latency)),
                  latency_scope="resize + green finder + vector; excludes JPEG read; first sample excluded from p50/p95",
                  rows=rows)
    STEM.with_suffix(".json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    job_status.write(job, stage="done", progress={"n": len(rows), "total": len(rows)})
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
