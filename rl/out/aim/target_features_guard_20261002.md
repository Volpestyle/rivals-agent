# Shared door abstention, 2026-10-02 — VUH-1346

**Bounded check passed:** the existing teacher rule suppresses both false-known door boxes on the
same fourteen pilot controls; all eleven non-door vectors remain exactly unchanged. This is conservative
input masking for a future model experiment, not general detector qualification or an aiming improvement.
Mix399 is unchanged. Cost **$0**; no fit, GPU, cloud, live input/integration, video decode, or corpus write.

[Paired native-pixel examples](target_features_guard_20261002.jpg) ·
[all fourteen paired rows and timing](target_features_guard_20261002.json) ·
[reproduction script](target_features_guard_20261002.py) ·
[historical raw pilot](target_features_pilot_20261002.md).

The paired image shows raw boxes on the left and boxes retained by the mask on the right, for the centred
control, all three door views and the wall control. The owner visually inspected it at native detail.
It reuses the original pilot's inspected identities; no new frames or annotations were selected.

## Change

`policy.bc2.target_features.extract()` now calls the existing
`rl.aim.teacher.green_share(original_frame) > teacher.DOOR_GREEN_SHARE` before the finder. The function
and threshold are read from the teacher module itself; no numeric veto is copied or tuned. As in `Teacher`,
the share function receives the original full frame, then performs its existing 640×360 resize internally.
The teacher/core detector were not edited. The guarded feature path still uses the same 1280×720 green finder
and the same ten-value schema from the pilot.

`extract_with_reason()` returns the same vector plus one of `teacher_door_abstention`,
`no_green_detection`, `expert_unqualified`, or `detected_not_verified`. Expert rows return masked zeros
before accessing pixels or calling the rule. Raw `detect_boxes()`/`from_boxes()` remain available for
diagnostics; future model consumers must call the guarded extraction API, not compose the raw helpers.
Unknown coordinates and count remain placeholders, never centred-target or enemy-absence claims.

## Exact paired controls

The historical JSON supplies the exact fourteen paths and visual observations. The check verifies the
current raw boxes **and every raw vector** against that saved result before comparing the mask. Denylist
identities and takeover exclusions were rechecked, and source paths are restricted to the same retained
range-development sittings. No new TRAIN/DEV/VAL or expert pixels, sealed source, or split role was involved.

| Pilot ID | Scene | Green share | Raw → guarded boxes | Raw → guarded known | Result |
|---|---|---:|---:|---:|---|
| 00 | Near-centred bots | .003494 | 2 → 2 | 1 → 1 | Exact vector preserved |
| 01 | Left/up and right bots | .004562 | 2 → 2 | 1 → 1 | Exact vector preserved |
| 02 | Distant bots | .003398 | 1 → 1 | 1 → 1 | Exact vector preserved |
| 03 | Door glass | .057517 | 1 → 0 | 1 → 0 | False-known scenery suppressed |
| 04 | Small bots | .004253 | 1 → 1 | 1 → 1 | Exact vector preserved |
| 05 | Open bots | .005239 | 2 → 2 | 1 → 1 | Exact vector preserved |
| 06 | Open bots | .005256 | 2 → 2 | 1 → 1 | Exact vector preserved |
| 07 | Distant bots | .003529 | 1 → 1 | 1 → 1 | Exact vector preserved |
| 08 | Distant bots | .003702 | 1 → 1 | 1 → 1 | Exact vector preserved |
| 09 | Door glass | .044115 | 0 → 0 | 0 → 0 | Already unknown; reason now door abstention |
| 10 | Door glass | .074093 | 1 → 0 | 1 → 0 | False-known scenery suppressed |
| 11 | Multiple bots | .003885 | 2 → 2 | 1 → 1 | Exact vector preserved |
| 12 | Hero/wall | .001732 | 0 → 0 | 0 → 0 | Unknown preserved |
| 13 | Hero/foliage | .002630 | 0 → 0 | 0 → 0 | Unknown preserved |

The observed shared threshold is .0065, using strict `>`. Known frames fall **11 → 9** and false-known
frames **2 → 0**, using the original manual observations. Nine open-bot vectors and two empty-control
vectors are bit-exact. Raw partial boxes and missed left bots remain unchanged; this rule does not repair them.

**Tradeoff:** all three door views visibly contain real enemies through the glass. The mask discards any
chance to expose those positions. In these particular controls the raw finder already missed those enemies,
so **zero enemy-overlapping raw boxes were removed**; it would be misleading to claim newly measured loss
of correct detections. Real enemies remain unknown in all three views, and future valid detections in other
green-heavy scenes could be suppressed. This selected sample establishes neither general precision/recall
nor the rate of that false-unknown tradeoff. The threshold was not re-estimated.

## Timing and checks

One CPU pass per path on the same fourteen JPEGs, BelowNormal, OpenCV/OMP/MKL two threads; first frame
excluded from aggregates, JPEG reads excluded. Shared rule alone: **2.85 ms p50 / 3.13 ms p95**.
Raw finder/vector: **6.43 / 7.90 ms**. Guarded extraction: **8.98 / 10.51 ms**. The mask can avoid the
finder on door frames. These short, ordered, warm-cache timings are not a live runtime guarantee.

- Feature, outline and teacher-validation tests: **60 passed, 4 corpus tests skipped**.
  Tests check shared function/constant use, strict threshold boundary, native-frame input parity, finder
  bypass on abstention, reason metadata, expert no-read, centred/unknown separation and prior feature behavior.
- Literal isolated environment without numpy/cv2/torch: clean collection, **55 passed / 10 skipped** with
  the existing camera-calibration tests; the feature test file skips cleanly.
- Scoped Ruff passed. Paired script exited **0**, job status `done`; no job or hardware reservation remains.

The original pilot report, JSON and images are unchanged. Its claim of public-function/raw parity describes
**commit `f439918`**, before this mask. Its reproduction script now explicitly uses the raw helper path to
keep that historical baseline reproducible; it was not rerun over historical outputs. Run the new script
for the current paired check:

```powershell
& C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe rl/out/aim/target_features_guard_20261002.py
```

Lead owns publication and the next consumer. This delivered change is suitable for a deliberately masked
exploratory input path; full-corpus extraction, model integration/adoption and live testing remain separate,
unauthorized work. No additional review gate was introduced.
