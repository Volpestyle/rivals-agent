LAND

# Pre-run delta review v4: named guard clauses and refusal-frame retention (VUH-1384), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the delta from accepted v3 source `6e3b7b0` to live-loop's uncommitted worktree. Only
`scripts/measure_camera_turns.py` and its test changed. It is read-only. I ran no desktop, game, GPU or video decode
work, and I did not open the D: native evidence beyond hashing it and reading the test log.

**Inputs checked.**
- All 12 pins in `review-inputs.json` match the working-tree bytes (driver `4f3d770a…b0e0`, test `ce695ed7…317cea`).
- A fresh `git diff 6e3b7b0 -- <2 files>` hashes to `delta_sha256` `2be67210…` and is byte-identical to `delta.diff`.
- Compared with the v3 receipt, only the driver and its test differ. The analyzer is still `cf8f16ae…`, and the prime
  analyzer is still `465fc479…`.
- HEAD `a2a0a3a` changes no source file after `6e3b7b0`.

**Tests.** I ran both test files in a private `UV_PROJECT_ENVIRONMENT` with the perception group, CUDA hidden:
- **101 passed and 12 skipped** without `--corpus`;
- **113 passed** with `--corpus`.

The owner's 125 passed and 12 skipped also includes `test_camera_prime_response.py`: 101 + 24 = 125, per `qualify.py`.

## The lead's checks

**No guard is relaxed.**
- **The frame guard.** `check_frame_guard` (`:143`) evaluates the old boolean guard's clauses in the same order, and
  also short-circuits: focus, key, `perf_counter() < attach_end`, `in_range`, then `not idle_warning`.
- **Exceptions in the guard.** An exception from any check now returns "failed" where it used to propagate. That is
  stricter:
  - Inside `Live._commit` it now causes `release()` and `RangeLost`, where before an exception left the pad to the
    lease watchdog.
  - Before attach it now fails `require`.
- **`post_attach_proof` (`:160`).** It keeps the old `proof()` order: focus, key, `timing["failed"]`, `live.fresh()`,
  guard, then age greater than `FRESH_S` (0.1 s, `perf_counter`). It journals the frame only after every check passes.
  No limit, clock or check was removed.
- **`guarded_proof`.** Its scope check is unchanged: `reasons` or `clock() >= end`, before and after capture.
- **Exception types.**
  - Two stops change type from `ValueError` to `GuardRefused`, which subclasses `RangeLost` and `RuntimeError`: the
    report-timing failure and the block-scope stop.
  - I searched for handlers that could now catch them. Nothing reachable from this driver catches `RangeLost` and
    continues. The only `except RangeLost` handlers in the pinned files are in `agent/startup.start_pose` and
    `l4_measure.main`, and the driver calls neither.
  - Inside the driver, `ready_proof` wraps only `unchanged_pose` in its `try`, and the pulse branch catches only
    `MotionRefused` and re-raises it. Every one of these stops still ends the block.

**Prime, collect, attach and the actuator are unchanged.** My own AST comparison against `6e3b7b0` shows:
- These are identical: `collect_segment`, `initialize_pad`, `measure_pulse`, `attach_after_token`, `ready_proof`,
  `unchanged_pose`, `save_native`, `validate`, `verify_receipt`, and all module-level statements, including `FILES`.
- `run_block` differs only in its nested `guarded_proof`.
- The multiset of every `send_guarded`, `send`, `release`, `close`, `Live`, `collect_segment`, `Capture`, `attach`,
  `hold`, `keepalive`, `pulse`, `watch_pad` and `fresh` call is identical.
- There is still one `Capture("dxcam")`, and no GDI or backend change.

**Retention never resumes input.**
- Encoding happens only in `retain_pose_refusal`, and `live.close()` is its first statement. Any image write, JSON
  write or disk failure there comes after the pad is neutral and dead.
- Write errors are caught and returned as `retained: False`, and `main` re-raises the original exception.
- The passing path adds no full-frame copy. `guard_state` holds a reference, not a copy.

**Retention can delay a stop by about 2.3 ms, but never block it.** See finding 1.

**The six controller error strings the retention path maps** each appear verbatim once in `agent/controller.py`.
Anything unrecognized becomes `controller_or_capture_stop` and is not guessed at.

## Findings

1. **Low: retention delays a mid-segment stop by one full-frame copy.**
   - **Where:** `scripts/measure_camera_turns.py:140`.
   - **What happens:** `GuardRefused.__init__` copies the frame before the exception reaches
     `collect_segment`'s `finally: live.release()`. On this PC a 2560×1440×3 copy takes 2.29 ms median and 2.68 ms at
     most (30 runs, CPU).
   - **Why it's bounded:** Renewals are at most 40 ms apart and leases at most 100 ms. The actuator also refuses writes
     past `scope_not_after` on its own, and a monitor stop has already closed the pad before `guarded_proof` raises.
   - **Optional fix:** Don't copy here; keep a reference. No capture runs between a stop and `retain_pose_refusal`,
     which closes the pad first and then encodes. The failure mode is a few milliseconds of extra release latency, not
     a missed stop.
2. **Info: pre-attach guard failures are still generic and not retained.**
   - **Where:** `scripts/measure_camera_turns.py:643` and `:191`.
   - **What happens:** `capture_proof` still raises the combined `ValueError` "range/idle/freshness stop before
     attach". The controller-retention branch needs `live` to exist.
   - **Why it matters:** `guard_state` does hold the clause, but if the next refusal happens before attach, its image
     and clause won't be written. This is not a safety issue.
3. **Info: one retained frame is labelled "checked" when it isn't the failing capture.**
   - **Where:** `scripts/measure_camera_turns.py:191-207`.
   - **What happens:** For `capture delivered no frame` raised inside `Live._commit`, the retained image is the previous
     frame the guard checked, and it is labelled `checked`. It is the last checked frame, not a capture tied to the
     failure.
   - **Mitigation:** `original_error` makes the case identifiable.
4. **Info: a construction failure could skip `failure.json`.**
   - **Where:** `scripts/measure_camera_turns.py:206`.
   - **What happens:** In the controller branch, `GuardRefused(...)` is constructed outside the `try`. A failure there,
     such as a `MemoryError` during its copy, would escape `retain_pose_refusal` and skip `failure.json`.
   - **Why it's only info:** It happens after `live.close()`, so it cannot affect input.

## Receipt

`review-v4.json` uses the a4, v1, v2 and v3 format (`camera-turns-review-v1`).
- It pins the 12 driver dependencies exactly as they are on disk in this checkout.
- `verify_receipt` accepts it, and the v3 receipt now refuses as stale.
- If the landed bytes differ in any way, including line endings, the receipt fails closed. Re-run `verify_receipt` on
  the sitting checkout after integration.
