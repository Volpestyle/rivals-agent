LAND

# Pre-run delta review v2: ready-pose revision (VUH-1384), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the delta from `e91a2d4` to live-loop's uncommitted worktree, and whether v1 findings 1–3
are resolved. It is read-only. I ran no GPU work, video decode or game input; the only images I read were saved
calibration PNGs, on the CPU. It covers input safety only. It accepts no rate, focal length, map or learned-policy
result.

**Inputs checked.**
- All 13 pins in `review-inputs.json` match the working-tree bytes. The four edited files are CRLF, and the other nine
  match their v1 values.
- A fresh `git diff e91a2d4 -- <4 files>` hashes to `1be69ca9…`, as `diff_sha256` records, and is byte-identical to
  `delta.diff`.
- The base blobs at `e91a2d4` for the driver (`6c0bb35d…`) and the analyzer (`2ff123e0…`) are exactly the bytes v1
  reviewed. The delta is therefore the whole change since v1.

**Tests.** I ran both test files myself in a private `UV_PROJECT_ENVIRONMENT` with `--group perception --corpus`, CUDA
hidden: **86 passed in 9.12 s**. This matches `final-tests.txt`.

## The lead's checks

**(a) Can motion beyond the bound become "ready"?** No. **Can it become a recoverable quality wait?** Only when the
motion can't be measured, and then it's safe.
- **Measurable motion is now `changed`, which refuses immediately.**
  - A confident phase shift beyond 1.5 band px refuses first, as before.
  - New: agreeing patches beyond 1.5 band px are now tested before the phase-confidence check
    (`perception/camera_ready_pose.py:76-79`). My v1 case, a 31 px blur plus a 10 px shift at phase 0.459, now
    returns `changed`. So do the blur-31 cases with 6 and 20 px shifts, and the blur-15 cases up to 30 px.
  - Zoom of 1.015 or more, shear plus a 4 px shift, and every translation of 3.0 px or more at 1280 also return
    `changed`.
- **Motion the analyzer can't measure is still `unprovable`.** That covers:
  - blur 61 with any shift;
  - blur 31 with a 30 px shift;
  - shifts of 200 px or more;
  - the real yaw-01b prime pair (raw correlation 0.036, phase 0.098).
- **Why that wait is safe.** It is bounded at 1 s while neutral. It can end in "ready" only if two consecutive later
  frames prove to be within 1.5 band px of the fixed original reference, that is, only if the view is actually back
  where the lead approved it. See finding 2.
- **Nothing beyond the bound returned `unchanged`.** That includes all 42 of the owner's native cases and all of mine.

**(b) Registration can't hide a real displacement.**
- The warp runs only after these have passed:
  - `max(|phase dx|, |phase dy|, |every accepted patch offset|) ≤ 1.5`;
  - a spread of 0.75 or less;
  - a phase score of 0.5 or more.
- It shifts by the patch median, which is itself within 1.5 band px, so registration can remove at most the displacement
  the bound already allows. It is used only for the content residual and never feeds back into the displacement
  decision.
- The sign is correct. Sub-bound yaw shifts of 1.0, 2.0 and 2.8 px give residuals of 0.9990, 1.0000 and 0.9987.
  Registering the wrong way would have lowered them, which could only cause a refusal.

**(c) Retention and deadlines.**
- `record_analysis` pairs `audit` with exactly the frame and capture time it classified
  (`scripts/measure_camera_turns.py:165-168`).
- A frame captured after the deadline is refused before analysis (`:191-192`). It appears only as
  `terminal-unanalyzed`, with status `not_run`, beside the earlier audited `current` frame.
- An analysis exception yields `terminal-unanalyzed` with status `failed`. The earlier audit stays with its own frame.
- With no prior analysis, the audit and `current` are null.
- `ReadyPoseRefused` and a deadline hit after analysis both attach the audit to the frame that was just analysed.
- A late frame that would pass still refuses: the capture-deadline check runs before analysis, and the deadline is
  re-checked after a passing analysis (`:207-208`).
- The copy at `:216` is reached only on the recovery path. It runs before the next `proof()`, and so it does not age the
  next frame, whose clock starts at its own capture.
- Encoding still happens only in `retain_pose_refusal`, after `live.close()`.

**(d) Nothing outside the pose code changed.**
- My own AST comparison against `e91a2d4` shows only these changes: `analyze`, `ready_proof` with its nested
  `record_analysis` and `refuse`, and `retain_pose_refusal`.
- Module-level statements, including `FILES`, are identical in both files. The multiset of every `send_guarded`,
  `release`, `close`, `Live`, `collect_segment`, `acknowledge`, `watch_pad`, `verify_receipt`, `Capture` and `sleep`
  call is identical.
- `git diff e91a2d4` is empty for `measure_inference_fps.py`, `agent/`, `capture.py` and `l4_measure.py`.
- Prime, segment, lease, token, deadline, GDI and FPS code are unchanged.

## The v1 findings

- **v1-1, the centre strip: resolved to about pre-v1 parity.** The registered whole-band residual must be 0.95 or more.
  - My v1 probes now all refuse: the full centre strip in noise and in flat colour, bot-sized 40×70 and 40×100 boxes in
    the strip in noise and in flat colour, and the right third.
  - Low-contrast or edge changes can still pass. See finding 3.
- **v1-2, blur and phase: resolved for motion the patches can measure.** Unmeasurable motion is covered in (a) above
  and in finding 2.
- **v1-3, redundancy: partly resolved.** Row 0 now has three supporting patches. Row 1 still has one. See finding 1.

## Findings

1. **Low: liveness, the rest of v1-3.**
   - **Where:** `perception/camera_ready_pose.py:49` and `:68`.
   - **What happens:** On the native reference, the new lower patches (1,1) and (1,2) fail the uniqueness check even on
     identical frames (0.010 and 0.016, below the 0.02 floor). Row 1, and with it the two-row rule, therefore rests on
     patch (1,0) alone, whose margin is 0.042–0.050.
   - **Scenario:** A sub-bound vertical shift of 1.0 or 2.8 px at 1280 drops (1,0) to 0.014–0.015, and the result is
     `unprovable` rather than `unchanged`. This is the safe direction: the attempt refuses after 1 s. All retained
     native ready frames still pass, and frame 29 passes with exactly 3 patches.
   - **For the lead:** A new arrival scene may have more or less support, and a refusal is a valid outcome. Don't lower
     the thresholds without a new review.
2. **Low: motion that can't be measured is still treated as quality.**
   - **Where:** `perception/camera_ready_pose.py:68-69`, and the docstring at `scripts/measure_camera_turns.py:157`.
   - **What happens:** The cases listed under (a) take the bounded 1 s neutral wait instead of refusing immediately. The
     journal logs `pose_quality_wait`.
   - **Why it's safe:** They can never pass unless the view is proven back at the reference.
   - **Accuracy:** "Movement refuses immediately" still over-claims for this class.
   - **Optional:** A low raw-correlation floor, for example refusing when the phase score is below 0.5 and the raw
     correlation is below 0.5 (yaw-01b is at 0.036), would refuse these at once. The distortion cases the repair
     targets sit at about 0.944.
3. **Info: the limits of the content residual.**
   - **Where:** `perception/camera_ready_pose.py:84-87`.
   - **What still passes:**
     - a flat fill of the top half of the centre strip (residual 0.980);
     - a flat 30×60 box in the lower right (0.954);
     - noise across the bottom 16-px band strip (0.981), a region no patch covers (band y 134–150);
     - a flat 17 px strip on the right edge (0.977).
   - **Why it's only info:** A whole-band correlation floor can't see small or low-contrast local changes. This is
     roughly what the pre-v1 raw 0.95 gate saw, and the guard's contract is camera pose. The lead's ready-image
     inspection remains the check for bots.
4. **Info: a new receipt is needed.**
   - The v1 receipt fails closed on these bytes, correctly. No v2 receipt was requested, so none is issued here.
   - A replacement must pin the actual sitting-checkout bytes. The four edited files are CRLF now, and a fresh checkout
     with `core.autocrlf` would produce different hashes.
   - The pins reviewed are those in `review-inputs.json` (driver `bfc51b55…`, analyzer `f4ee95f3…`, driver test
     `a174681f…`, analyzer test `d5b6d36c…`, plus the eight unchanged v1 pins).
