# Target-feature pilot, 2026-10-02 — VUH-1346

**Result: working feature interface, visibly noisy target geometry; no data adoption or aiming claim.**
Fourteen explicitly selected retained development frames show that the unchanged green finder can supply
useful left/right/near-centred positions, including bots below the reset-only 8% height cutoff. It also
returns door scenery as a known target and misses or fragments real bots. Those errors matter more than
the inexpensive extraction. Mix399 remains unchanged. No fit, model/live integration, cloud, GPU work,
video decode or corpus writes were performed. Cost **$0**.

[Overview](target_features_pilot_20261002.overview.jpg) ·
[native full-frame sheet, 5120×10640](target_features_pilot_20261002.native.jpg) ·
native-pixel zooms [00–03](target_features_pilot_20261002.detail-1.jpg),
[04–07](target_features_pilot_20261002.detail-2.jpg),
[08–11](target_features_pilot_20261002.detail-3.jpg),
[12–13](target_features_pilot_20261002.detail-4.jpg) ·
[raw output and manual observations](target_features_pilot_20261002.json).

Yellow boxes are raw detector output, **not verified enemy boxes**. Cyan N and magenta L mark the selected
nearest/largest centres; they can coincide. The table and JSON explicitly distinguish boxes that overlap
an enemy from false-known scenery. Source paths and native dimensions are in each JSON row and sheet caption.
The owner inspected the full-frame overview and all fourteen native-pixel detail views, including original
full-resolution door, distant-bot, wall and foliage controls. No intended target, calibrated angle, or
precise human-drawn box ground truth is available.

## Feature contract

`policy.bc2.target_features.extract(frame_bgr, source_kind="range")` returns float32:

`[known, nearest_visible, nearest_dx, nearest_dy, nearest_h, largest_visible, largest_dx, largest_dy, largest_h, log1p_count]`

- Full 16:9 uint8 BGR image → `INTER_AREA` resize to 1280×720 → unchanged
  `perception.outline.find_enemies(..., scale=1.0)`. Hero/HUD exclusions are inherited.
- `dx=(cx-640)/1280`, `dy=(cy-360)/720`, `h=box_height/720`; positive right/down.
  Nearest is Euclidean distance to the image centre in **pixels**; largest is box area. Ties are deterministic.
- Both slots may describe the same detection. `known=1` means the finder returned a box, **not that it is a true enemy**.
- No detections → all zeros with `known=0`, `visible=0`. Geometry/count values are masked placeholders,
  never evidence of a centred target or zero enemies. A real centred detection has `known=visible=1`, `dx=dy=0`.
- `source_kind="expert"` unconditionally returns unknown without accessing the supplied frame.
  Other source kinds are refused. No expert frames were opened or admitted.
- No reset eligibility filter, temporal tracking, teacher door veto, focal length, gain, red fallback or detector tuning.
  No feature rows were attached to a corpus. Future consumers must use this same function and obey its mask.

This follows p3S's original design after the lead corrected its initial x/y/w/h shorthand in Swarm thread
`vuh-1346-target-pilot`. The actual design was read in its original `policy-target-design-1a/1b` messages.
Model embedding/dropout, full extraction and model comparison remain outside this pilot.

## Inspected controls

Fourteen unique frames, all retained range-development data: compat learned-01-a and sittings 01, 04 and 07.
The first twelve were explicit start/middle/end and previously inspected controls; two additional explicit
wall/foliage frames completed the empty controls. No statistical sampling claim. Current denylist identities
and takeover exclusions were checked before reading; excluded episodes 07-008/012/015 were not opened.
No TRAIN/DEV/VAL session media or sealed match payload was needed; no split role changed.

| ID | Raw count / known | Raw boxes visibly on enemies | Native visual observation |
|---|---:|---|---|
| 00 | 2 / 1 | 0, 1 | Near-centred right bot mostly boxed; left box captures only its right-side fragment. |
| 01 | 2 / 1 | 0, 1 | Nearest left/up bot misses left arm/side; largest right bot mostly boxed. |
| 02 | 1 / 1 | 0 | Right distant bot retained at height 46/720 (6.4%); visible left bot entirely missed. |
| 03 | 1 / 1 | **none** | **False known:** door/ceiling scenery selected; visible enemies through glass missed. |
| 04 | 1 / 1 | 0 | Right small bot's head omitted, detected height 32/720 (4.4%); left bot missed. |
| 05 | 2 / 1 | 0, 1 | Nearest left bot partially boxed; largest right bot mostly boxed. |
| 06 | 2 / 1 | 0, 1 | Both bots mostly boxed; nearest left, largest right. |
| 07 | 1 / 1 | 0 | Right distant bot boxed, visible left mate missed. |
| 08 | 1 / 1 | 0 | Right distant bot boxed, visible left mate missed. |
| 09 | 0 / 0 | none | Unknown despite visible enemies through door glass. |
| 10 | 1 / 1 | **none** | **False known:** a different door/ceiling patch selected, enemies missed. |
| 11 | 2 / 1 | 0, 1 | Nearest uses only left bot's left limb fragment; largest right bot mostly boxed. |
| 12 | 0 / 0 | none | Hero against wall; no visible enemy, correctly unknown. |
| 13 | 0 / 0 | none | Hero and foliage; no visible enemy, correctly unknown. |

11/14 frames are raw known; 9 of those contain an enemy-overlapping selected box and 2 are false-known
door scenery. This is descriptive accounting of hand-selected controls, **not precision/recall**. Partial
boxes are counted as overlapping an enemy, not accurate full-body boxes. Several missed left bots lie
in the existing hero-exclusion region; that is a plausible cause, not an isolated causal measurement.
The hero exclusion itself is unchanged and synthetic coverage checks that it remains active.
Object-versus-scenery calls here are high confidence; precise extents and intended-target identity remain unknown.

## Runtime and verification

Final 14-frame CPU run: **6.46 ms p50 / 7.24 ms p95**, excluding first call (**13.94 ms**) and JPEG loading.
Times include resize, finder and vector construction. PC BelowNormal, OpenCV/OMP/MKL at two threads;
frames streamed individually, contact sheets under the 3 GB cap. Earlier development passes on the same
small cohort measured roughly 8–9 ms median; this is a short warm-cache sample, not a live latency guarantee.
All 14 outputs exactly match the public extraction entry point. That proves same-function replay on these
bytes; it does not establish live integration or equivalence to independently decoded recordings.

- `tests/test_bc2_target_features.py` + `tests/test_outline.py`: **53 passed, 4 skipped** (corpus opt-ins).
  The new file contributes 12 tests: masking/centred distinction, expert no-read, coordinate scaling,
  pixel-distance selection, deterministic ties, area selection, small-target retention, hero exclusion,
  no red fallback, 1440p/720p parity, and invalid-input refusal.
- Literal isolated pytest environment verified numpy/cv2/torch absent; new test file plus existing
  `test_camera_calibration_schedule.py`: **55 passed, 10 skipped**, clean collection.
- Scoped Ruff passed; standalone pilot process returned exit 0 and job status `done`.

Reproduce with the existing perception-capable Python environment:

```powershell
& C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe rl/out/aim/target_features_pilot_20261002.py
```

The script only reads its fourteen explicit JPEGs plus denylist/exclusion metadata and writes this pilot's
outputs and its job-board status. Manual observations are embedded in the script for reproducibility.

## Recommendation and handback

Keep the extractor as an exploratory interface. Do not call raw-known rows reliable targeting data or start
bulk extraction merely because tests and latency pass. The immediate limitation is false-known scenery and
partial/missing geometry. A future owner could assess sharing the **existing** `Teacher` door abstention
across offline/live preprocessing rather than inventing a second veto. It trades false-known suppression
for false-unknowns: the inspected door views also visibly contain real enemies, so abstaining discards their
positions as well. That rule was neither applied nor tuned here; its existing numeric threshold is not validated
by this pilot. Any masking policy needs explicit shared semantics before model use.

Lead owns the next bounded task and any adoption/publication. The lead clarified that current lean-mode rules
add no cross-family review gate for this offline pilot; owner tests and inspected evidence complete this scope.
No full extraction, fit, live sitting, or extra benchmark was launched. No GPU/queue reservation remains.
