# Independent delta re-review v2: bounded pixel compatibility mode, VUH-1319, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, the v1 reviewer, outside the live-loop lane). Read-only; no desktop
input, game, pad, capture or GPU. Scope: the delta since [review v1](../live-loop-compat-20260929/review-v1.md)
(receipt `56c88402…36c1`) and its findings.

Reviewed against `review-inputs.json` sha256 `44a07067981d8a89c1c213e5e271a6b8b487d463665545704fd8f8f216914b27`.
- All `files` and `support_files` match the working tree.
- Relative to the v1 freeze, only `agent/camera_compat.py` (`b37e5617…`) and `tests/test_camera_compat.py` changed.
- The `before/` snapshots equal the v1 pins.
- I diffed `before/` against the working tree myself. The only runtime change is inside `CompatibilityCheck.pulse()`
  (`camera_compat.py:112-147`).

## Verdict: **LAND**

### C1 (was blocking): fixed

- **New order.** `pulse()` now runs in this order:
  1. check the pulse budget and validate the requested command;
  2. save the frame while the pad is neutral;
  3. take a **fresh** `observe()`, which re-applies the range/idle proof, the frame-age and monotonicity checks and
     detection;
  4. re-match the locked target, stopping if it is lost or ambiguous;
  5. recompute the errors, returning with no input if the target is already inside the deadband;
  6. recompute the axis and sign, and re-check yaw against the pinned knots;
  7. set `sent_at = check_time()`, with `release_at = sent_at + 50 ms` and `response_until = sent_at + 750 ms`;
  8. refuse if the fresh proof is more than 100 ms old at `sent_at`, or if there is not enough response budget;
  9. send.

  No disk I/O lies between the fresh proof and the send. `before` comes from the fresh observation. The saved frame and
  the caller's earlier error cannot authorize input.
- **Recomputed commands stay inside the declared set.** Yaw goes through `yaw_command` again. Pitch is
  `copysign(0.1, …)`, which is ±0.1 by construction. The pulse and budget caps, `send_guarded` limits, the lease, the
  response watchdog and `finally: release()` are unchanged from v1.
- **Independent reproduction.** My v1 script uses the owner's fakes with a `save` that costs real `imwrite` time:

  | save cost | v1 | v2 |
  |---|---|---|
  | 0 / 30 ms | passed | passed, 10 pulses |
  | 45 ms | `no_observed_response` | passed, 10 pulses |
  | 75 / 86 ms (measured 1440p) | `stale_before_input`, 0 pulses | passed, 10 pulses |
  | 120 ms | not run | passed, 10 pulses |
  | 200 ms | not run | `target_lost_or_ambiguous`, 0 pulses (fails closed) |

  - Pulse count no longer depends on save cost.
  - A scratch assertion confirms that every send has exactly a 50 ms `release_at − t` window.
  - Every proof is at most 100 ms old at send, and later than the frame that was saved.
- **Margin.** A 200 ms save fails closed before any input. That is about 2.2× the 73–89 ms I measured without the game
  running.
- **Tests.** The owner added 90, 100 and 120 ms save regressions that converge, a direction change during retention,
  and scope loss, stale capture, target loss and deadline refusals after the save. The eight affected suites in the live
  venv (`--no-project`, read-only) give **494 passed**.

### C2 (was a note): addressed

The README adds an on-PC preflight that must run before any live invocation: `preflight_hashes.py` runs the real
`load_yaw_compatibility`. That call raises on any map, record or evidence mismatch, and the README treats the failure as
a STOP with no repinning. I ran it read-only here: it confirmed map `0e062286…` and record `a5597978…`, with exit 0.

### C3 (was a note): kept

Stale or late frames still cannot authorize a pulse. The fresh observation carries the age check, and the
response-phase logic is unchanged.

## Unchanged from v1 (evidence reused)

All of the following are byte-identical to the v1 pins, so the v1 verification still applies:
- the input set and caps;
- the `LiveSafety` guards and `ResponseWatch`;
- the acceptance pinning and the complete-map refusal;
- the legacy 1,500-step trace;
- the parser.

## Conditions

This receipt covers code only. The live run still needs:
- the lead's grant;
- a passing hash preflight on the PC immediately before the sitting;
- an explicit profile and settings declaration;
- the v1 plan's hands-off operation.

Everything used fakes. The physical pixel response and the device latency are unmeasured.
