# Pose guard delta for independent pre-run review

**Implemented, uncommitted, not approved for live use.** The lead dispatches
live-review for this delta. No staging, landing, new freeze or sitting by owner.

Compare approved base `e91a2d4f6bf03da8c624967a1c578e7da3f3c0c1` to the working
tree for exactly these four files (also captured in `delta.diff`):

- `perception/camera_ready_pose.py`
- `scripts/measure_camera_turns.py`
- `tests/test_camera_ready_pose.py`
- `tests/test_measure_camera_turns.py`

`review-inputs.json` pins the 12 driver dependencies and the additional analyzer
test file. It is an owner input manifest, **not a review receipt**. The previous
v1 receipt fails closed on the edited checkout. Re-verify any independently
issued replacement on the actual sitting checkout after integration; raw byte
pins include line endings. The four edited files use CRLF without a BOM.

## Changed boundary

The analyzer adds a centre column (six patches total), retaining NCC >=.95,
uniqueness >=.02, at least three agreeing patches, two rows, two columns and
spread <=.75. Agreeing offsets beyond the original 1.5-band-pixel limit become
`changed` before the phase-confidence test. After the geometry passes, bounded
alignment must give whole-band residual correlation >=.95; this checks scene
content without treating an out-of-bound shift as acceptable.

The driver retains the last analyzed image and its capture/analysis timestamps
separately from a later terminal capture that was never classified. On capture
deadline refusal, `refusal-current.png` belongs to the audit;
`refusal-terminal-unanalyzed.png` belongs to the refusal trigger. Both roles
are explicit in `pose-refusal.json` and in `failure.json.refusal_evidence`.
If analysis threw instead of classifying, terminal status is `failed`; if it
never ran, it is `not_run`. Without any prior analysis the audit is null.

One bounded image copy before the next recovery capture protects against
reused capture buffers; no copy was added to the successful return's freshness
span. Refusal snapshots remain arrays until the pad is closed, then encoding
occurs. A late frame still refuses, even when its pose independently passes.
Prime, segment, lease, token, deadline, GDI and FPS code remain unchanged.
`ast-delta.json` shows only `analyze`, `ready_proof`, and `retain_pose_refusal`
changed among production function/class definitions.

## Verification

- **86 tests passed in 9.16 s**, final CRLF bytes, saved-PNG and synthetic CPU
  checks; `final-tests.txt` is the full output. Initial semantic checks also
  passed 86 tests in 9.53 s. Ruff and scoped `git diff --check` pass.
- **42 fixed native/control cases** matched expected outcomes in
  `native-replay.json`, with every native source SHA checked against the earlier
  evidence. All 30 earlier ready poses pass. The terminal frame and journal
  frame 150 pass; frame 148 still safely refuses inconsistent motion.
- Native centre noise and flat replacements refuse (registered correlation
  .939497 / .925691). Real yaw-01b prime motion and all six beyond-bound native
  translation controls refuse. Synthetic tests additionally force low phase
  confidence: agreeing patch motion is `changed`, stationary low-phase evidence
  remains `unprovable`.
- Retention regressions cover a reused buffer, capture deadline before any
  analysis, analysis exceptions after an earlier audit, and a genuinely passing
  image arriving after a failing image but after the deadline. Encoding is
  checked to occur after close, including when no pad had attached.

CPU at BelowNormal, OpenCV/BLAS limited to two threads; no GPU, native-video
decode, desktop, capture or input. The two owner jobs exited. A preliminary
inline shell launcher failed Python quoting before importing or running tests;
the retained file-based runner avoids that problem.

## Sitting record correction and limits

The 2026-09-28b refusal was **deadline during capture**. The saved terminal frame
passes v1; the old attached audit described the preceding analyzed frame, which
was not retained. Journal frame 150 reproduces the earlier two-patch failure,
but is not the exact last audit frame. Original sitting evidence is unchanged.

Thresholds have narrow native support, not calibrated error bounds. Sparse
1 Hz journal samples do not establish that a continuous recovery would finish
within its deadline. This is no yaw-rate, focal, map or learned-policy result.
After independent review and re-freeze, the planned lead-operated retry uses
`reenter.py` arrival and yaw-01 without hand-posing.
