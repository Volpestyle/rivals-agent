LAND

# Pre-run review v1: ready-pose and FPS startup repair (alt-cam-20260928), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the live-input boundary only. It is read-only. I ran no game, pad, capture, video decode
or GPU work. The only images I read were saved calibration PNGs, on the CPU. The review covers two repairs: the
ready-pose guard in `measure_camera_turns` and the cold-start stale proof in `measure_inference_fps`. It accepts no
rate, focal length, camera map or FPS cost. The a4 receipt is stale for this driver.

**Inputs.**
- `review-inputs.json` `617f7a5d…`, `driver-delta.patch` `5583128f…`, `input-ast.json` `9acab168…` and `RESULT.md`
  `3a67228d…`.
- The lane note `live-loop-diagnosis-20260928.md` is `a7a167f5…`, the sitting's `SITTING.md` is `59871fa2…` and the a4
  receipt is `1be5e514…`.
- All 12 pins and the 3 additional pins match the working-tree bytes.
- The packet's base is `bf782b6`. HEAD has since moved to `4567659`, which only adds IDM reader files and touches no
  pinned file.
- Rebuilt with `git diff`, `driver-delta.patch` is identical apart from its headers. The camera driver's HEAD blob is
  `fbc442d6…`, which is the driver a4 accepted. The FPS driver's HEAD blob is `8a97a760…`.
- The owner's claimed unchanged files (controller, startup, l4_measure, record, pad_bindings, loop, run_range_bc_live,
  live_range_bc, capture) have no working-tree changes.

**Tests.** I ran the three named modules myself, in a private uv environment with `--group perception --corpus`, CUDA
hidden and two threads: **128 passed in 11.96 s**, which matches the owner's `tests-review.txt`.

## The five questions

1. **Can the ready-pose analyzer authorize input it shouldn't?**
   - **Camera motion beyond the bound: no.** `unchanged` requires all of the following:
     - phase score ≥0.5;
     - a global shift ≤1.5 band px;
     - at least 3 patches with NCC ≥0.95 and uniqueness margin ≥0.02, covering both rows and both columns;
     - patch spread ≤0.75;
     - every patch offset ≤1.5 against the fixed original reference.
   - I probed a real native frame (`yaw-01/ready-attach.png`, 2560×1440) and nothing I tried returned `unchanged`:
     - yaw and pitch shifts of 3.0–200 px at 1280, and a 530 px phase wrap;
     - zoom 1.01 and 1.02, and roll 0.5°;
     - blur plus a 10 px shift, noise plus a 4 px shift;
     - the saved yaw-01b true-motion pair.
   - Sub-bound cases do pass: shifts of 2.6 and 2.9 px, zoom 1.005 and roll 0.2°. This matches the original 3 px bound.
   - Unprovable evidence never passes. `ready_proof` returns only from the `else` branch after a proven frame, and it
     never updates the reference.
   - **Scene content: yes, in part.** The whole-band correlation gate is gone (finding 1).
   - The owner's thresholds are supported for the translation bound: native translations of 2 px pass and 4 px or more
     refuse. They are not calibrated error bounds, which the owner says.
2. **Does neutral recovery stay bounded, and does it stay neutral?** Yes.
   - The deadline is `min(end, clock()+1)` per call, and each capture is re-checked against it.
   - `ready_proof` sends nothing. Its only acquisition is the caller's proof: `guarded_proof`→`Live.fresh()` or the
     pre-attach `capture_proof`, and neither writes the pad.
   - Every call site runs after a `release()` or a `finally: release()`: the `run_block` loop head, `initialize_pad`
     after `collect_segment`, and pulses via `l4.pulse`. The attach site runs before any pad exists.
   - Leases are still ≤100 ms. Guard failures (RangeLost, block ended) propagate unwrapped, because proof runs outside
     the `try`.
3. **FPS re-prime.** Stale frames are never submitted.
   - An over-age proof is discarded before the copy or submit (`measure_inference_fps.py:206`), and submission
     re-checks age immediately before `submit` (`:220`).
   - Re-priming needs two consecutive fresh proofs. Each recovery has 3 s, counted from the moment freshness was lost,
     and the whole startup has 10 s.
   - The constants are unchanged: `FRESH_S` 0.1, `PREDICTION_LIMIT_S` 0.25, cold 5 s. `run()` and every phase function
     are AST-identical to HEAD.
   - There is one `Capture("dxcam")` (`:657`) and no GDI path or fallback. The runner has no input import or actuator.
4. **Refusal-frame retention.**
   - In the camera driver, encoding happens only in `main`'s `except`, and `retain_pose_refusal` calls `live.close()`
     (neutral, then dead) before any encoding. `run_block`'s `finally` has already closed the pad and stopped the
     monitor. A pre-attach refusal is encoded with no pad in existence.
   - An IO failure is caught and recorded, and the bare `raise` preserves the original exception. Nothing in that path
     can reach `send_guarded`.
   - In the FPS runner, the sink runs after the loop exits and after `worker.close()` has been asked to stop the worker,
     and its exceptions are caught.
5. **Unchanged input code.** I confirmed this with my own AST walk rather than by reusing `input-ast.json`.
   - `collect_segment` and `measure_pulse` are identical.
   - Every `send_guarded`, `release`, `Live(...)` and `collect_segment` call is unchanged.
   - The only relocated call is `live.close()`, which moved from `main`'s `except` into `retain_pose_refusal`. It runs
     first there (`scripts/measure_camera_turns.py:136`), so ordering is preserved. See finding 6 for why the packet's
     check can't show this.

## Findings

1. **Medium: measurement validity, not input safety.**
   - **Where:** `perception/camera_ready_pose.py:39`, `:48-49` and `:68`.
   - **What changed:** The old `correlation >= .95` gate is still computed and logged, but no longer gated. On the
     native scene only 3 patches ever contribute, because patch (1,1) scores uniqueness 0.016 < 0.02 even on identical
     frames. About 57% of the band is therefore checked only by the global phase: the centre gap at band x 112–152, the
     borders and the lower-right quadrant.
   - **Probe:** I replaced the centre strip (80×300 px at 1280) with noise, and separately with a flat colour. Both
     returned `unchanged`, at correlation 0.816 and 0.910. HEAD refuses both.
   - **Scenario:** A bot or effect enters that strip between the lead's ready-N inspection and the post-token proof. The
     segment then runs on a view the lead did not approve.
   - **Why it doesn't block:** The pad, lease and guards are untouched, and the camera pose is still proven within 1.5
     band px.
   - **Disclosure:** `RESULT.md` lists what was kept but never says the correlation gate was removed.
   - **Next revision:** Cover the gap, for example with a centre patch column, or add a residual or correlation floor
     after the shift bound, justified on the retained frames. The tail frames sit at 0.990–0.991. The 0.944 failure
     frame is unidentified.
2. **Low: motion reported as quality.**
   - **Where:** `perception/camera_ready_pose.py:74-77`, and the docstring at `scripts/measure_camera_turns.py:155`.
   - **What happens:** `phase < .5` returns `unprovable` before the absolute patch-offset test runs. Agreeing patches
     that show motion beyond the bound are therefore not reported as `changed` when blur lowers the phase score.
   - **Probe:** A 31 px horizontal blur plus a 10 px shift gives patches agreeing at about 5 band px and a phase score of
     0.459, and returns `unprovable`. The saved yaw-01b true-motion pair is also `unprovable`.
   - **Effect:** Refusal can wait up to 1 s of neutral recovery, and the journal logs `pose_quality_wait` instead of
     motion. It never passes, so this is not unsafe.
   - **Accuracy:** It contradicts "Movement refuses immediately" and RESULT's "Actual motion … still stop".
   - **Fix:** With 3 or more agreeing patches, a spread ≤0.75 and a maximum offset >1.5, return `changed` whatever the
     phase score.
3. **Low: liveness.**
   - **Where:** `perception/camera_ready_pose.py:14` and `:68`.
   - **What it means:** Native support has zero redundancy: exactly 3 of the 4 patches, with tail-frame margins of
     0.029–0.035 against the 0.02 floor. Disturb one patch and the result is `unprovable`, then refusal after 1 s.
   - **Direction:** The failure is safe. The retry may still refuse, and the new retention should capture the exact
     pair.
   - **Don't:** Lower thresholds without a new review.
4. **Low: FPS liveness.**
   - **Where:** `scripts/measure_inference_fps.py:215`.
   - **What happens:** Every fresh startup frame is fully copied (about 11 MB at 2560×1440) for refusal evidence before
     the submit-freshness re-check. That adds milliseconds during the cold forward, which is the interval where the
     104 ms capture happened.
   - **Effect:** It can make a frame miss submission. It cannot submit a stale one.
   - **Optional fix:** Copy into a preallocated buffer (`np.copyto`) outside the freshness-critical span.
5. **Info: the receipt semantics.**
   - **Where:** `scripts/measure_camera_turns.py:37-43`.
   - **What it checks:** `verify_receipt` checks only `format` and the 12 file hashes. It ignores verdict and findings,
     so this file authorizes the run by itself. It is issued only because the verdict is LAND.
   - **Line endings:** The files are LF in the working tree and `core.autocrlf` would write CRLF on a fresh checkout. The
     receipt then fails closed, so re-verify it on the sitting checkout after commit.
6. **Info: the packet's AST check.**
   - **Where:** `input-ast.json`.
   - **The limit:** `input_call_expressions_identical` compares a sorted multiset of calls, so it cannot see a relocated
     call. I checked the one relocation myself (question 5).

## Receipt and use

- **Receipt:** `review-v1.json`, in the a4 format (`camera-turns-review-v1`). It carries the 12 driver pins, plus the
  verdict, findings, reviewer, reviewed inputs and the three additional FPS and test pins.
- **Limits:** Its scope is input safety only. It accepts no rate, focal length, map or FPS cost, and it does not
  qualify the missing 0.944 failure frame.
- **Lead:** Arrive via `reenter.py`, inspect the ready image, and treat a refusal as the result. Findings 1 and 2 are
  for the owner's next revision and are not needed before this retry.
