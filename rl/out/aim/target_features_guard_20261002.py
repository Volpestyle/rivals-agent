"""Paired CPU check of the exact 14 historical raw-pilot frames; no new sample or fit."""
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
from rl.aim import teacher
from scripts import job_status

STEM = Path(__file__).with_suffix("")
BASELINE = Path("rl/out/aim/target_features_pilot_20261002.json")
ALLOWED = {"compat-check-20260929", "rl-sitting-20260930-01",
           "rl-sitting-20260930-04", "rl-sitting-20260930-07"}
DISPLAY = [0, 3, 9, 10, 12]


def main():
    cv2.setNumThreads(2)
    job = "target-features-guard-20261002"
    job_status.write(job, owner="explore-policy", stage="running", host="pc", evidence=str(STEM) + ".json")
    baseline = json.loads(BASELINE.read_text())
    assert len(baseline["rows"]) == 14
    deny = json.loads(Path("data/human/sealed-denylist.v2.json").read_text())
    denied = {r["session_id"] for r in deny["sessions"]}
    excluded = json.loads(Path("rl/aim/exclusions.json").read_text())["episodes"]
    rows = []
    sheet = Image.new("RGB", (2560, len(DISPLAY) * 820), "#121822")
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 25)
    for old in baseline["rows"]:
        path = Path(old["image"])
        assert path.parts[:2] == ("data", "calibration") and path.parts[2] in ALLOWED
        assert "sealed" not in path.as_posix().lower() and ".." not in path.parts
        assert not any(sid in path.as_posix() for sid in denied)
        assert path.parent.as_posix() not in excluded
        frame = cv2.imread(str(path))
        assert frame is not None and frame.shape == (1440, 2560, 3)
        start = time.perf_counter()
        share = teacher.green_share(frame)
        share_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        boxes = T.detect_boxes(frame)
        raw = T.from_boxes(boxes)
        raw_ms = (time.perf_counter() - start) * 1000
        assert np.array_equal(raw, np.asarray(old["values"], dtype=np.float32))
        assert np.array_equal(np.asarray(boxes), np.asarray(old["boxes_720"]))
        start = time.perf_counter()
        gated, reason = T.extract_with_reason(frame)
        gated_ms = (time.perf_counter() - start) * 1000
        veto = share > teacher.DOOR_GREEN_SHARE
        assert np.array_equal(gated, np.zeros(10, np.float32) if veto else raw)
        assert np.array_equal(gated, T.extract(frame))
        row = dict(id=old["id"], image=old["image"], green_share=share, abstained=veto,
                   reason=reason, raw_count=len(boxes), gated_count=0 if veto else len(boxes),
                   raw_known=int(raw[0]), gated_known=int(gated[0]), raw_values=raw.tolist(),
                   gated_values=gated.tolist(), unchanged=bool(np.array_equal(raw, gated)),
                   baseline_exact=True, inspection=old["inspection"],
                   timing_ms=dict(shared_rule=share_ms, raw=raw_ms, gated=gated_ms))
        rows.append(row)
        if old["id"] in DISPLAY:
            y = DISPLAY.index(old["id"]) * 820
            for side, kept in enumerate((boxes, () if veto else boxes)):
                canvas = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(canvas)
                for b in kept:
                    draw.rectangle(tuple(v * 2 for v in b), outline="#ffd04d", width=4)
                # Same native-pixel scene crop as prior detailed inspection; no resizing.
                sheet.paste(canvas.crop((640, 100, 1920, 880)), (side * 1280, y + 40))
                caption = (f"{old['id']:02} RAW known={int(raw[0])}, boxes={len(boxes)}" if side == 0
                           else f"GUARDED known={int(gated[0])}: {reason}")
                ImageDraw.Draw(sheet).text((side * 1280 + 8, y + 5), caption, fill="white", font=font)
    def timing(key):
        values = [r["timing_ms"][key] for r in rows[1:]]
        return dict(p50=float(np.median(values)), p95=float(np.percentile(values, 95)))
    result = dict(baseline=BASELINE.as_posix(), baseline_commit="f439918", cost_usd=0,
                  schema=T.FIELDS, rule="rl.aim.teacher.green_share(original_frame) > teacher.DOOR_GREEN_SHARE",
                  threshold_observed=teacher.DOOR_GREEN_SHARE, device="CPU BelowNormal, OpenCV 2 threads",
                  samples=len(rows), abstained_ids=[r["id"] for r in rows if r["abstained"]],
                  raw_known=sum(r["raw_known"] for r in rows), gated_known=sum(r["gated_known"] for r in rows),
                  raw_false_known=sum(r["inspection"]["false_known"] and r["raw_known"] for r in rows),
                  gated_false_known=sum(r["inspection"]["false_known"] and r["gated_known"] for r in rows),
                  all_non_abstained_unchanged=all(r["unchanged"] for r in rows if not r["abstained"]),
                  true_enemy_overlapping_raw_boxes_removed=sum(len(r["inspection"]["enemy_overlapping_raw_box_ids"])
                                                              for r in rows if r["abstained"]),
                  timing_ms={key: timing(key) for key in ("shared_rule", "raw", "gated")},
                  timing_note="one pass per path per frame, JPEG excluded, first frame excluded from aggregates; not live latency",
                  rows=rows)
    STEM.with_suffix(".json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    sheet.save(STEM.with_suffix(".jpg"), quality=92)
    job_status.write(job, stage="done", progress={"n": 14, "total": 14})
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
