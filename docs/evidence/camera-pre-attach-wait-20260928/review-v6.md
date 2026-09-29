LAND

# Pre-run delta review v6: bounded stale-frame discard before attach (VUH-1384), live-review (Claude Opus 5.5), 2026-09-28

**Scope.** This review covers the delta from `1af578c` to the evaluator's frozen worktree. Only
`scripts/measure_camera_turns.py` and its test changed, and only in `pre_attach_proof`. It is read-only. I ran no
desktop, game, GPU or video decode work, opened no sealed source and edited no source file. The v5 evidence is reused
for everything unchanged.

**Inputs checked.**
- All 12 pins and all 5 sitting-e evidence hashes in `review-inputs.json` match the bytes on disk (driver
  `2aac7ab9…95fb`, test `43905d11…50b6`, both CRLF).
- A fresh `git diff 1af578c -- <2 files>` hashes to `delta_sha256` `a676b438…` and is byte-identical to `delta.diff`.
- The base commit's blobs are the v5-receipted bytes (`3d27fb09…` and `92f13792…`) with CRLF normalised to LF.
- Compared with the v5 receipt, only the driver and its test differ.

**Tests.** I ran them in a private `UV_PROJECT_ENVIRONMENT` with the perception group, CUDA hidden:
- driver, ready-pose and prime tests: **143 passed, 12 skipped**, which matches the owner's run;
- driver and ready-pose tests with `--corpus`: **131 passed**.

## The change

**AST check.** Against `1af578c`, only `pre_attach_proof` changed. Every other function and class and every
module-level statement, including `FILES`, is identical. The multiset of input, capture and guard calls
(`send_guarded`, `release`, `close`, `Live`, `collect_segment`, `grab`, `guard`, `fresh`, `pulse`, `watch_pad`) is
identical.

**What changed in `pre_attach_proof`.**
- **Window:** the acquisition window grows from `FRESH_S` (100 ms) to `min(scope_end, now + 2 s)`
  (`scripts/measure_camera_turns.py:168`).
- **Stale frames:** A frame that passes every guard but is older than 100 ms is no longer an immediate stop. It is kept
  as a candidate `GuardRefused("freshness")` holding its exact pixels, and the journal records
  `pre_attach_stale_discarded`, with capture and guard time split (`:191-196`). The loop then grabs again.
- **When the window ends:**
  - if a stale frame was seen and the scope is still open, that exact stale refusal is raised (`:207`);
  - otherwise the refusal is `block_deadline` or `capture_unavailable`, as in v5.

## Safety: the readiness change preserves it

- **No pad exists on this path.** `capture_proof`'s only callers are `attach_after_token`'s reference capture (`:356`)
  and its `acquire` (`:361`), used during the token wait and the re-proof after the token. Both run before
  `factory(...)` constructs `Live`. Everything after attach still goes through `post_attach_proof`, which is
  byte-for-byte AST-identical, with its immediate 100 ms freshness stop unchanged.
- **Returned frames.** A returned frame has passed every guard on that same frame, and its age from acquisition start
  to the end of checking is at most 100 ms. A stale frame is never returned, used as the ready reference, or compared
  for pose.
- **Semantic failures are still immediate.** The guard result is tested before the age (`:184`). A stale frame that
  also fails range or idle stops at once, and so does focus, key or a capture exception before any grab.
  - The block deadline is one of the guard's own checks, and it also caps the window.
  - Every returned frame still passes through `ready_proof`, the unchanged fixed-reference pose check.
- **My randomized check.** I ran 20,000 seeded trials against `pre_attach_proof` with a fake clock and capture. They
  mixed grab durations of 1 ms to 1.3 s, guard durations of 1 ms to 300 ms, missing frames, capture errors and
  range, idle, focus and key failures. Every run passed all of these checks:
  - no stale frame and no frame that failed a check was returned;
  - no semantic failure was ever skipped for a later frame;
  - every refusal after a stale frame carried the exact frame;
  - every call ended within `min(2 s, scope)` plus one blocking call.
- **Owner tests.** They reproduce sitting e's 600.2695 ms in both the capture stage and the guard stage, and return the
  following fresh frame. They show that a semantic stop is never recovered after a stale frame, and that a persistent
  stale stall retains the exact last frame.

## Liveness: no blocking flaw

A native call that hangs still cannot be interrupted. That is the same as in v5, no pad exists meanwhile, and the
scope deadline applies when it returns. The stall's source is not established; the 60-cycle probe after the attempt
peaked at 38.3 ms.

## Findings

1. **Low: the 2 s wait is shorter inside the token wait.**
   - **Where:** `scripts/measure_camera_turns.py:292` and `:324`.
   - **What happens:** During the token wait and the re-proof after the token, each acquisition runs inside
     `ready_proof`, which has a 1 s budget per call. A stall longer than about 1 s there still ends the attempt, and it
     is labelled `ready pose recovery deadline during capture`, not `freshness`. My fake-clock run confirmed this: a
     1.2 s stale stall followed by a fresh, unchanged frame refused.
   - **Why it's only low:** It is safe, and a 600 ms stall still fits. The discarded frames are journaled, so the cause
     remains visible.
2. **Info: the final stale refusal carries an early decision time.**
   - **Where:** `scripts/measure_camera_turns.py:207`.
   - **What happens:** The `GuardRefused` raised when the window ends was built when the last stale frame was
     discarded. So `decision_t` in `guard-refusal.json` is that discard time, not the end of the window. If the window
     then ends with only missing frames, the clause still reads `freshness`.
3. **Info: each discarded stale frame is copied.**
   - **Where:** `scripts/measure_camera_turns.py:191`.
   - **What happens:** Each stale discard builds a `GuardRefused`, which copies the frame (about 2.3 ms at 2560×1440).
     There are at most about 20 such copies per window, because each stale frame already took more than 100 ms, and no
     pad exists. There is no safety effect.

The v5 findings and the v4-1, v4-3 and v4-4 findings carry over unchanged.

## Receipt

`review-v6.json` uses the same format (`camera-turns-review-v1`).
- It pins the 12 driver dependencies exactly as they are on disk in this checkout.
- `verify_receipt` accepts it, and the v5 receipt now refuses as stale.
- If the landed bytes differ in any way, including line endings, the receipt fails closed. Re-run `verify_receipt` on
  the sitting checkout after integration.
