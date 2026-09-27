LAND

# Pre-run re-check a4: prime-response analyzer swap (VUH-1384), binds-review (Opus 5.5), 2026-09-27

**Scope.** Input boundary only, per `2e00d3f`. Earlier reviews and receipts are preserved; the a3 receipt is stale.

**Inputs.**
- `HANDBACK-a4.md` is `04fead5c…`, `source-hashes-a4.json` is `58c171c7…`, `a4-driver.diff` is `ae3c20e7…` and `a4-ast-comparison.json` is `0fa04ba8…`.
- All 11 pins match. Only the driver (`fbc442d6…`) and its tests changed.
- HEAD `91b6d9b` holds the accepted a3 driver `29216007…`.

**The delta.** In `initialize_pad`, the single post-release call `l4.checked_shift(before_gray, after_gray, YAW_BOX, direction=-1)` is replaced by `perception.camera_prime_response.analyze(...)`. The analyzer's SHA and full result are recorded, and anything but `motion_present` raises `MotionRefused`, which ends the block with no retry. Any other analyzer exception also ends the block.

Nothing else changed: sends, leases, tokens, pre-attach gate, prime timing, settle, guards and order are all as in a3. The pair still comes from within the prime, 40–100 ms apart, after the pad has been released.

**The analyzer is outside the pins, and that is acceptable.**
- `perception/camera_prime_response.py` (`465fc479…`, recorded in `initialization.json`) imports only `math`, `cv2` and `numpy`, never receives `Live`, and neither sleeps nor sends.
- A pass only lets the block reach the next token-gated, pose-locked `ready-0`. Every later input keeps its own guards, so a false pass could make data invalid but not input unsafe.

**False-pass probes (mine, on a real native frame).**

| Case | Result |
|---|---|
| Saved yaw-01b pair (old rigid template scored 0.689) | **passes**, dx −175.5 on 14 patches |
| True −60 px shift | passes |
| Identical frames | refused |
| Static plus ±3 noise | refused (stationary) |
| 1 px shift | refused |
| +60 px wrong direction | refused |
| Saved pair with direction reversed | refused |
| Unrelated scene | refused (1 correspondence) |

**Tests.** Driver plus analyzer suites pass, CPU only in `rivals-live-cu128`.

**Receipt.** `camera-turns-review-v1-a4.json` pins the 11 a4 files, and the driver's `verify_receipt` accepts it. It covers input safety only; no rate, focal length or map is accepted. After commit, re-verify on the sitting checkout, since line-ending conversion would change the hashes.
