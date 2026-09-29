LAND

# Pre-run delta review v3: fractional patch NCC (VUH-1384), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the delta from `adfe13f` to live-loop's uncommitted worktree. It is read-only. I ran no
GPU work, video decode or game input; the only images I read were saved calibration PNGs, on the CPU. It covers input
safety only. It accepts no rate, focal length, map or prime-analyzer change.

**Inputs checked.**
- All 13 pins in `review-inputs.json` match the working-tree bytes.
- A fresh `git diff adfe13f -- <2 files>` matches `diff_sha256` `8746711d…` and is byte-identical to `delta.diff`.
- `scripts/measure_camera_turns.py` and its test have no diff from `adfe13f`. They are the v2-receipted bytes.
- `perception/camera_prime_response.py` is still `465fc479…`. The prime diagnostic is packet-only.
- Nothing in `agent/`, `capture.py`, `l4_measure.py`, `record.py` or `run_range_bc_live.py` changed between `adfe13f`
  and HEAD `7707f38`.

**Tests.** I ran both test files myself in a private `UV_PROJECT_ENVIRONMENT` with `--group perception --corpus`, CUDA
hidden: **95 passed in 11.33 s**. This matches `final-tests.txt`.

## The change

This is one hunk in `analyze` (`perception/camera_ready_pose.py:65-72`). Each accepted patch's NCC is now computed with
`getRectSubPix` at the offset already estimated from the integer peak and its parabolic refinement. That is the same
`(px, py)` the displacement checks use. The raw peak is kept as `integer_ncc`.
- Nothing else in `analyze` changed: the peak choice, the offsets, uniqueness on the integer score surface, the texture
  floor, the patch grid, the row and column rules, spread, the bounds, phase and the residual.
- A nonfinite aligned NCC rejects the patch.
- The sampling centre `(x+47.5+px, y+29.5+py)` is the patch centre shifted by the estimated offset, which is correct
  for a 96×60 patch. Sub-bound shifts now reach aligned NCC of 0.96 or more. Sampling in the wrong direction would have
  lowered it.
- Nothing in the driver reads `ncc`. `camera_prime_response.py` has its own separate `ncc`.

## The lead's checks

**(a) Bounds and thresholds are unchanged.**
- `SHIFT_LIMIT` 1.5, `PATCH_NCC` 0.95, `PATCH_MARGIN` 0.02, `SEARCH` 12, the texture floor of 2, spread 0.75, phase
  0.5 and residual 0.95 all sit outside the hunk.
- The raw displacement test still uses the global phase shift and the unmodified patch offsets.

**(b) Fractional sampling can't raise confidence for a real move.**
- It changes only whether a patch counts, never the offset that patch reports. Any accepted patch whose offset is
  beyond 1.5 band px makes the result `changed`. `unchanged` also still needs a phase score of 0.5 or more with a
  global shift of 1.5 or less, and a registered residual of 0.95 or more.
- **The differential probe.** I ran the `adfe13f` analyzer and the new one on the same 468 images. The references were
  the yaw-01 reference and the sitting-c yaw-01r reference, plus synthetic scenes. The cases were:
  - shifts of 0–20 band px along 6 directions;
  - Gaussian blur of the current frame, or of both frames, at σ 1–8;
  - JPEG quality 30 and 10, noise, and half resolution, each combined with shifts of 0–3 band px;
  - six occlusions, in noise and in flat colour;
  - an unrelated scene, a blank frame and a mirrored frame;
  - periodic stripes, including shifts of exactly one period;
  - smooth low-texture fields.
- **Result.** No case with a true displacement beyond 1.5 band px returned `unchanged` under either analyzer. Every ±2
  band px control is still `changed` or `unprovable`.
- **Only 8 statuses changed, all on the sitting-c reference:**
  - Four sub-bound shifts, ±0.5 vertical and the ±0.53 diagonals, went from `unprovable` to `unchanged`. This is the
    intended fix.
  - Four shifts at the bound, −1.5 horizontal, +1.5 vertical and the ±1.41 diagonals, went from `unchanged` or
    `unprovable` to `changed`. With more patches accepted, one estimated offset just over 1.5 now counts. That makes
    the guard stricter at the boundary.
- On the yaw-01 reference nothing changed.

**(c) Interpolation can't fabricate a match on low-texture or ambiguous patches.**
- Low-texture patches (standard deviation below 2) are still skipped before any sampling.
- Uniqueness is still measured on the integer `matchTemplate` surface, and the interpolated score never touches it. An
  ambiguous patch with a margin below 0.02 is rejected however high its aligned NCC is.
- The edge-peak check is unchanged.
- No status changed on the stripe scenes, including their one-period aliases, on the smooth fields, on blur of σ up to
  8, or on the unrelated or blank frames.

**(d) Nothing else changed, and the v2 findings still stand.**
- **v2-1 (row-1 support):** unchanged on the yaw-01 reference, because uniqueness, not NCC, is what limits it. On the
  sitting-c reference all six patches now pass for the exact analysed pair.
- **v2-2 (motion it can't measure takes the 1 s quality wait):** unchanged.
- **v2-3 (the content residual misses small or faint changes):** unchanged. My occlusion probes returned the same
  statuses under both analyzers.
- **v2-4:** a new receipt is needed. It is issued as `review-v3.json`.

## Findings

1. **Info: boundary behaviour.**
   - **What happens:** Shifts at or just under 1.5 band px can now come back `changed` where the base analyzer returned
     `unchanged` or `unprovable`. The cause is estimation noise on the extra patches that now count.
   - **Why it's only info:** It is conservative, and it only affects shifts that are already at the edge of the bound.
2. **Info: the limit of the evidence.**
   - **What was shown:** The fix is demonstrated on one analysed native pair, the sitting-c yaw-01r pair, where every
     patch goes from an integer NCC of 0.918–0.941 to an aligned NCC of 0.964–0.977.
   - **What wasn't:** No other native refusal has been replayed. As the owner says, these are engineering gates, not
     calibrated error bounds.

## Receipt

`review-v3.json` uses the a4, v1 and v2 format (`camera-turns-review-v1`).
- It pins the 12 driver dependencies exactly as they are on disk in this checkout, including CRLF, plus the analyzer
  test.
- `verify_receipt` accepts it, and the v2 receipt is now stale and refuses.
- If the landed bytes differ in any way, including line endings, the receipt fails closed. Re-run `verify_receipt` on
  the sitting checkout after integration.
