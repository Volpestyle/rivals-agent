LAND

# Pre-run re-check a3: pre-attach token and M1 startup for both modes (VUH-1384), binds-review (Opus 5.5), 2026-09-27

**Scope.** Live-input boundary only, per `2e00d3f`. Earlier reviews and receipts are preserved; `camera-turns-review-v1-a2.json` is stale.

**Inputs.**
- `HANDBACK-a3.md` is `2f38c4c4…` and `source-hashes-a3.json` is `ef55a90e…`.
- All 11 pins match the working tree. Only the driver and tests changed from a2; HEAD `6f3a7f7` holds the accepted a2 driver `54253de1…`.
- **Tests:** 40 passed, CPU only with CUDA hidden, in the durable `rivals-live-cu128` environment. Game and OBS were absent.

**Order and guards.**
1. **Before any pad exists**, a capture-only proof checks focus, keyboard, the range HUD, the idle banner, freshness (≤100 ms) and the block deadline, which now covers the gate. A `ready-attach` token follows. During the wait and again after the token, the view must be unchanged from the saved frame. The receipt is re-verified inside the attach factory. There is no pad drift during the human wait, which was the yaw-01 cause.
2. `Live(settle_s=0)` is created and the full-report watcher installed. The **first non-neutral report** is the reviewed M1 prime (`START_TURN_RX` +0.45 for `START_TURN_S` 0.3 s, from `agent/startup.py`), sent through the guarded `collect_segment`: proof per renewal, renewals every 40 ms or less, leases of 100 ms or less capped at the prime's end, `finally` release. The monitor starts with `run_block` just before the prime, and no input is sent before it.
3. **Response.** The pair comes from guard-retained native frames with their own capture timestamps, both at least 150 ms after the first send and within the prime, 40–100 ms apart. It uses the unchanged `l4.checked_shift(direction=-1)`, labelled `mid_motion_response_only`. If there is no pair, no motion, the wrong sign or an unreliable fit, the block ends with no retry, extra pulse or alternative estimator.
4. **Settle.** A full `START_SETTLE_S` (5 s) of neutral follows, with a proof about every 10 ms and a stability check over the last 0.5 s plus the post-settle frame. yaw-01 shows the Switching Devices banner does not break the range check (it failed on `MotionRefused`), so proving through the settle is compatible with it. The operator still confirms banner clearance on `ready-0`.
5. **Every `ready-N`** compares fresh scenery with its saved frame during the wait and again after the token. A bad or moving pose ends the block, with no automatic leveling or search.

The guard now also refuses on any keypress, so Live's own proof inherits the keyboard stop. The initialization is labelled `initialization_excluded`, with start and end events even on failure.

**Notes (not blocking).**
- The prime keeps up to 16 native frame copies (about 180 MB), well inside the PC memory rule.
- The pose gate (phase score ≥0.5, ≤1.5 band px, correlation ≥0.95) is conservative: animated scenery can refuse. That fails safe.
- There is a short unmonitored gap between `Live` construction and `run_block` starting its monitor. No input is sent in it, and Live's own watchdog is active.

**Receipt.** `camera-turns-review-v1-a3.json` pins the 11 a3 files, and the driver's `verify_receipt` accepts it. It covers input safety only; no rate, focal length or map is accepted.
