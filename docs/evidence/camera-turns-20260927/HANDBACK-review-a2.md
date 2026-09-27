LAND

# Pre-run re-check a2: pulse-block pad initialization (VUH-1384), binds-review (Opus 5.5), 2026-09-27

**Scope.** Live-input delta only, per `2e00d3f`. The earlier reviews and receipts are preserved; `camera-turns-review-v1-a1.json` is now stale.

**Inputs.**
- `HANDBACK-a2.md` is `d4dc3bb7…` and `source-hashes-a2.json` is `b87dda62…`.
- All 11 pins match the working tree, and the file set is unchanged. Only the driver and its tests changed.
- HEAD (`8580cea`) holds the accepted a1 driver `a5710a99…`.
- **Tests:** 29 passed, CUDA hidden.

**The delta** is one `initialize_pulse_pad` step, in pulse mode only; full-turn mode is unchanged.
- It is the first non-neutral input after the 3 s settle.
- It is gated by its own `ready-prime`/`continue-prime` token, and the pad stays neutral during the wait.
- It sends constant +0.45 `rx` for 120 ms (`PRIME_D`/`PRIME_S`, with no CLI knob) through the already-accepted guarded `collect_segment`:
  - full proof before each renewal;
  - renewals at most every 40 ms;
  - leases of 100 ms or less, capped at the initialization's end and the block end;
  - `finally` release;
  - the independent monitor active.
- Neutral native stills are taken 0.35 s before and after.
- The accepted `l4.checked_shift` must observe negative horizontal scene motion in `YAW_BOX` (about 19°, which is inside the 512 px envelope). Otherwise `MotionRefused` propagates, Live closes and the failure is recorded, with **no retry**.
- Then a fresh `ready-0` frame and a **new** token are required before any measurement pulse.
- The manifest, `initialization.json`, results and failure record label it `initialization_excluded`, and its on/off times mark the excluded report and video interval.

**Notes (not blocking).**
- A swallowed *first* report still passes if later renewals move the camera. That is the intended absorption, and the motion check proves response, not delivery timing.
- The 0.35 s settles use the real `time.sleep`, not the injected clock. That is harmless live.
- Re-check that the pose is bot-free after the roughly 19° initialization, as the hand-back says.

**Receipt.** `camera-turns-review-v1-a2.json` pins the 11 a2 files, and the driver's `verify_receipt` accepts it. It covers input safety only; no rate, focal length or map is accepted.
