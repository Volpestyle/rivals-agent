LAND

# Pre-run delta review v5: pre-attach named refusals and 1 Hz routine trace (VUH-1384), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the change from the v4-accepted bytes to the evaluator's frozen worktree. Only
`scripts/measure_camera_turns.py` and its test changed. It is read-only. I ran no desktop, game, GPU or video decode
work. The v4 packet is untouched.

**Inputs checked.**
- All 12 pins in `review-inputs.json` match the working-tree bytes (driver `3d27fb09…9f7dff`, test `92f13792…374b68`).
- `delta-from-v3.diff` equals a fresh `git diff 6e3b7b0 -- <2 files>`, and its hash matches the packet's. The
  `owner-tests.txt` hash also matches.
- Compared with the v4 receipt (`d4291a50…`), only the driver and its test differ.
- **Baseline.** The v4 bytes are uncommitted, so I rebuilt them by applying the v4 `delta.diff` to `6e3b7b0`. The result
  hashes to exactly `4f3d770a…` and `ce695ed7…`. Everything below compares against those bytes.

**Tests.** I ran them in a private `UV_PROJECT_ENVIRONMENT` with the perception group, CUDA hidden:
- the owner's three files: **136 passed, 12 skipped**, which matches `owner-tests.txt`;
- with `--corpus`, the driver and analyzer tests: **124 passed**.

The 11 new cases are:
- a named refusal before attach, with the exact pixels and no pad;
- capture and reader errors;
- absent captures;
- a disk-full failure;
- 105 acquisitions, all checked, with 2 routine snapshots.

## The change, compared with v4

`capture_proof`'s body moves into a new `pre_attach_proof` (`scripts/measure_camera_turns.py:160-190`). The only line
left in the adapter is the call at `:669`.

**AST check.** Apart from that body, everything is identical:
- `main`, every other function and class, and all module-level statements, including `FILES`;
- attach, prime, `collect_segment`, pulse, the ready-pose code, `post_attach_proof`, and retention.

The input and capture call multiset is unchanged. The only relocation is `cap.grab()` becoming `capture.grab()`, on the
same `Capture("dxcam")` object.

**The guard checks are the same, on every capture.**

| Check | v4 `capture_proof` | v5 `pre_attach_proof` |
|---|---|---|
| Window | `min(attach_end, now + FRESH_S)` | same |
| Before each grab | `require(focused() and not key)` | focus, then key; either raises `GuardRefused`, with no image |
| After each grab | full `guard(frame)`, then age ≤ `FRESH_S` | same order and limit; failure raises `GuardRefused` with the actual frame |
| No frame | `sleep(.001)` and retry | same |
| Window expires | `RangeLost` | `GuardRefused("block_deadline" or "capture_unavailable")`, no image |
| Capture raises | raw exception | `GuardRefused("capture_error")`, chained with `from` |

Only the routine `journal.frame(..., "before-attach")` is throttled (`:184-186`). It is written at most once per
`journal.guard_period` (1 s), keyed on capture time, and runs only after the frame has passed. The throttle does not
change:
- capture frequency;
- the guard and freshness checks;
- the `ready-attach` image, which `attach_after_token`'s `save_native` still writes;
- any refusal image.

It also removes the per-acquisition `frame.copy()` that `Journal.frame` made inside the proof loop.

**Nothing is relaxed, and the stops still hold.**
- Every refusal before attach still raises, and the exception now subclasses `RangeLost`. As v4 established, nothing
  reachable from this driver catches `RangeLost` and continues.
- Inside `ready_proof` the acquisition runs outside its `try`, so a refusal during the token wait or the re-proof after
  the token propagates as a stop.
- No pad exists on this path, and `Live` is never constructed after a refusal.

**Retention.**
- `main`'s `except` calls `retain_pose_refusal` with `live is None`. That skips `close` and the controller branch and
  writes `guard-refusal.png` and its JSON with `written_after: no_pad_attached`.
- A disk failure there is returned as `retained: False`, and the original exception is re-raised.
- The copy of the refused frame happens with no pad attached, so it cannot delay any release.

**v4 findings.**
- v4-2, pre-attach failures being generic and unretained: **resolved**.
- v4-1, the post-attach copy delaying release by about 2.3 ms: unchanged and still open, and still bounded.
- v4-3 and v4-4: unchanged.

## Findings

1. **Info: a throwing focus or key check before attach is still unnamed.**
   - **Where:** `scripts/measure_camera_turns.py:165-167`.
   - **What happens:** An exception raised by `focused()` or `key_pressed()` propagates raw, as in v4, rather than as a
     named `GuardRefused`. It still stops the attempt, but no clause is recorded.
   - **Contrast:** A throwing capture is named (`capture_error`), as is a throwing range or idle reader, through
     `check_frame_guard`.
2. **Info: the routine before-attach trace is now sparse.**
   - **Where:** `scripts/measure_camera_turns.py:184`.
   - **What happens:** The routine trace drops to 1 Hz. The earlier saved-frame replays of ready poses used the dense
     before-attach frames.
   - **Why it's only info:** A refusal still keeps its exact frame, and the lead's ready image is unaffected, but future
     offline pose replays will have fewer neighbouring frames. This is intended and not a safety issue.

## Receipt

`review-v5.json` uses the same format (`camera-turns-review-v1`).
- It pins the 12 driver dependencies exactly as they are on disk in this checkout.
- `verify_receipt` accepts it, and the v4 receipt now refuses as stale.
- If the landed bytes differ in any way, including line endings, the receipt fails closed. Re-run `verify_receipt` on
  the sitting checkout after integration.
