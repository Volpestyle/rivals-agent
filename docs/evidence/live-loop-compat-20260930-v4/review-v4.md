# Independent delta re-review v4: compatibility-mode coarse/fine pulses and hard-link retention, VUH-1319, 2026-09-30

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, reviewer of compat v1–v3, outside the live-loop lane). Read-only; no
game, pad, capture or run-02 data opened. The filesystem check below used a scratch directory only.

Reviewed against `review-inputs.json` sha256 `f19b5ad860c95dae2a0c12114934eae34548c538748878e24db2484493f512ae`.
- All 33 `files` and 18 `support_files` match, and no `__pycache__` pins remain (v3's N1 is resolved).
- Only `agent/camera_compat.py` and `tests/test_camera_compat.py` differ from the v3 freeze. HEAD's `camera_compat.py`
  equals the v3 LAND bytes, and I diffed against HEAD myself.

## Verdict: **FIX** (one evidence-integrity defect; the input side passes)

### E1 (blocking; evidence only, no input effect): writing through a hard link overwrites earlier evidence

- **What happens.** `retain()` hard-links `pulse-{n}-before.png` to the previous `pulse-{n-1}-response.png` when the
  stamp and frame object are the same (`camera_compat.py:147-162`). `NativeRetention.__call__` writes with
  `cv2.imwrite`, which truncates and rewrites an existing file **in place**, so it keeps the same inode.
- **When it happens.** If `pulse()` returns early because the fresh post-retention observation is already inside the
  deadband (`:219-220`), `self.pulses` does not advance. The next `pulse()` then retains `pulse-{n}-before` **again**,
  with a new frame (`:213`), which writes through the shared inode.
- **Result.** `pulse-{n-1}-response.png` silently becomes the later frame.
- **Reproduced with the real `NativeRetention`** in a scratch directory:
  1. write `pulse-0-response`;
  2. alias it as `pulse-1-before`;
  3. retain `pulse-1-before` again with a different frame.

  Both names now hash to the new frame, and the response PNG shows the later pixels.
- **Why it matters.** The README's "one immutable inode" is not true. The early return is reachable whenever the camera
  is still settling after the response frame; run-02 recorded a mean response delay of about 200 ms, which is when
  this happens. Run-02's own diagnosis relied on exactly these response PNGs.
- **Fix, any one of these:**
  - write to a temporary name and `os.replace` it over the target, which swaps the directory entry and leaves the
    linked inode intact;
  - `unlink` an existing target before writing;
  - give every retained name a unique suffix and refuse an existing name.

  Add a test: alias, then re-retain the same name with a new frame, and assert the earlier file is unchanged.

### Verified: the input set and caps

- **Pulse selection is always recomputed from the fresh observation after retention.** `command()`
  (`camera_compat.py:164-175`):
  - yaw 0.1, 0.2 or 0.3 at thresholds of more than 48 px and more than 96 px (1280-scale), always passed through
    `yaw_command`'s exact-knot check, and 0.1, 0.2 and 0.3 are measured signed knots;
  - pitch 0.1 for 50 ms, or 0.2 for 100 ms above 39 px, with the direction taken from the existing sign contract;
  - one axis per pulse;
  - pitch values are ±0.1 or ±0.2 by construction.
- **Every possible pulse is within the declared set.**
  - Yaw: |rx| ≤ 0.3 for 50 ms, all measured knots.
  - Coarse pitch: 0.2 for 100 ms, inside the reviewed calibration envelope (|ry| ≤ 1, 0.1–0.5 s).
  - Fine pitch: 0.1 for 50 ms, the existing compat authorization, which the README correctly says sits outside that
    envelope's duration range.
- **Timing.** `release_at = sent_at + duration`, so `Live`'s lease and `not_after` bound the hold to the selected
  duration, and the hold loop keeps observing.
- **Caps.**
  - The pre-retention checks (40 pulses, and `used_s + 0.05`) are unchanged.
  - A new check, `used_s + duration ≤ 2.0`, runs after the command is selected and before any input, so reserved input
    can never exceed 2 s even for coarse pulses. The owner's test refuses at 1.95 s plus 0.1 s with no call sent.
  - The 100 ms freshness, 750 ms response window, 10/15/60 s phase bounds and the parser are unchanged.
- **The coarse gains are hypotheses.** The 2× and 4× coarse-pitch gains, and the 39 px threshold derived from run-02's
  largest fine response, are declared counterfactuals, not measurements. I treated them as such, and the existing
  opposite-response and no-response stops still bound them.

### Verified: guards and stops unchanged from v2/v3

`observe()`, `LiveSafety` and `_open_live_io`, `ResponseWatch`, the `run()` and `main()` cleanup, `record_stop`,
warm-up, the acceptance and admission code, and the maps have no diff. The only other runtime change is the stage
label `pulse_response_budget`.

### Verified: aliasing cannot authorize input, and retention cannot block release

- Aliasing happens only for the identical `(stamp, frame object)` pair.
- It happens while the pad is neutral, and it is always followed by a fresh `observe()`, a target re-match, command
  recomputation and the 100 ms age check at `sent_at`. The owner's test asserts `proof_t > retained + save time`.
- A link or write error propagates out of `pulse()`. `run()` still releases in `finally` and records the stop, and
  `main()` still closes the source and safety.

### Tests

- The owner's new tests cover both sides of each threshold (96/97 and 48/49 for yaw, 39/40 for pitch), coarse-pitch
  cap exhaustion, alias semantics, a fresh proof after an alias, and large-error convergence using both pitch sizes.
- The 40-pulse cap is covered by the existing `count` case.
- The eight affected suites in the live venv give **512 passed**.
- My v2 retention-cost reproduction still converges from 0 to 120 ms of save cost, now in 8 pulses, and fails closed at
  200 ms.

## Re-review scope

Re-review only E1: the `NativeRetention` write semantics or retained-name uniqueness, plus its test. Everything else
reuses this review.
