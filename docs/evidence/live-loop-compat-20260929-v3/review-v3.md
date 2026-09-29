# Independent delta re-review v3: compatibility-mode warm-up, stop diagnostics and placement preflight, VUH-1319, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, reviewer of v1 and v2, outside the live-loop lane). Read-only. I ran
no desktop input, game, pad, capture or GPU, and opened no external run-01 evidence (data, video or `D:` frames).
Scope: the delta since the v2 LAND (receipt `6873541e…4b02`, landed as `6f59736`).

Reviewed against `review-inputs.json` sha256 `d4f3d22dcc344460cf762e1bc84b34764174b2530ca202b7603b60c1a6da7999`, base
`b1f2351`.
- All pins match. Only `agent/camera_compat.py` and `tests/test_camera_compat.py` differ from the v2 freeze.
- I diffed HEAD against the working tree myself, after line-ending normalization.
- `Limits`, `pulse()`, `ResponseWatch`, the parser, `camera_acceptance.py`, the record, the maps and `agent/loop.py`
  are unchanged.

## Verdict: **LAND**

### (a) The warm-up sends no input and cannot hold the pad

- **When it runs.** `warm_perception` runs inside the preflight `try`, after the first focus/takeover check and before
  the second. That is before `LiveSafety` exists, before `_open_live_io` and before any pad is created
  (`camera_compat.py` `main`).
- **What it touches.** Three iterations of `idle`, `in_range`, `size` and `wide` on a synthetic `np.zeros((1440, 2560,
  3))` frame, and a fresh throwaway `Tracker`. It has no `io`, `Live`, capture or pad references, and its result is
  metadata only.
- **No carry-over.** `perception/outline.py` has no module-level mutable state, `default_perception().wide` is a
  stateless crop-and-find, and the check's own `Tracker` is created separately. So priming cannot leak into real
  observations. A failure here raises before hardware.
- **Test.** `test_warmup_uses_only_synthetic_readers` asserts that only the synthetic frame reaches the readers.

### (b) Named stop clause and retention after release

- **Instrumentation.** `observe()` gains stage labels and timings, which add only extra `check_time()` deadline checks.
- **Split clause.** The old `stale_perception_or_scope` becomes `stale_after_perception`, then
  `scope_lost_after_perception`. The order and conditions are the same, the age check still short-circuits before the
  second guard call, and the owner's test asserts that.
- **Retention off the input path.** `record_stop` runs in `run()`'s `finally` after `io.release()`, and again,
  idempotently, in `main`'s `finally` after `source.close()` and `safety.close()`. The check loop has exited by then, so
  no input can follow. A retention error is recorded, never raised into control.
- **Exceptions.** The new `except Exception` paths in `run()` and `main()` only label the result and re-raise, so
  cleanup order is unchanged.
- **Test.** `test_stop_retains_failing_frame_after_release_and_names_clause` asserts at save time that the pad is empty
  and at least two releases have happened, for the age, scope, reader-error and save-error cases.

### (c) `placement_preflight.py` is read-only

- It never imports a pad library. It uses `foreground_pid_guard` before and after a single dxcam `grab()`, then
  releases the camera.
- It runs `percept.wide`, `in_range` and `idle` on that screenshot, and writes only `placement.png` and
  `placement.json` into a new `--out` directory (`exist_ok=False`).
- It requires a left target and a right target at least 48 px (2560-scaled; 24 px at 1280, matching the runner's
  acquisition offset) from center, plus the range HUD and no idle warning.
- Its left rule rejects any left target centred at x ∈ [0.27w, 0.5w) with y ≥ 0.39h. That is **stricter** than
  `PLAYER_ZONE` (x ∈ [0.27, 0.47], y ∈ [0.39, 0.90], small boxes only), so the preflight cannot pass a left bot that the
  finder's hero-zone rule would drop.
- `test_screenshot_preflight_requires_detected_targets_outside_left_hero_zone` covers this.

### Guards and caps from v2: unchanged

- `Limits` is byte-identical, so the 100 ms frame age, 50 ms pulse, 100 ms neutral, 750 ms response, 2 s / 40 pulses,
  10 s / 15 s phases and 12 px / 2 px thresholds are all as before.
- `pulse()` is unchanged. It still saves while neutral, takes a fresh proof and computes its windows from send time.
- `ResponseWatch`, `LiveSafety` and `_open_live_io`, the acceptance pins and the parser bounds are unchanged.
- My v2 retention-cost reproduction still behaves the same: saves of 0–120 ms converge with 10 full pulses, and 200 ms
  fails closed with 0 pulses.

### Tests

The eight affected suites in the live venv (`--no-project`, read-only) give **500 passed**. The new stops each have a
test: the named post-perception clauses, a reader exception at the `target_finder` stage, save failure during stop
retention, the warm-up, and the preflight.

## Notes (not blocking)

- **N1 (packet hygiene).** `support_files` pins three generated `__pycache__/*.pyc` files. They are Python-version
  specific and get regenerated whenever the packet's scripts run, which invalidates the pin. Drop them from the pins and
  from the commit.
- **N2.** The preflight is necessary but not sufficient. It judges one frame, while the runner needs a confirmed
  tracker identity on two successive fresh observations. A pass de-risks placement but does not guarantee acquisition.
- **N3.** The warm-up frame is fixed at 2560×1440. If the desktop runs at another resolution the priming still happens,
  just at a different size. The measured cold-start timing applies only to 1440p.

## Conditions

This receipt covers code only. The live run still needs the lead's grant and the v2 on-PC hash preflight immediately
before the sitting. The placement preflight must pass on a fresh screenshot before launch, and the run needs an
explicit profile and settings declaration and hands-off operation. Everything used fakes, and the physical response is
unmeasured.
