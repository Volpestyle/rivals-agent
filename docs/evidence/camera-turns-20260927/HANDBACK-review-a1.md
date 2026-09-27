LAND

# Pre-run re-check a1: camera-turn driver input boundary (VUH-1384), binds-review (Opus 5.5), 2026-09-27

**Scope.** Only the live-input boundary is reviewed, per `2e00d3f`. `HANDBACK-review.md` and `camera-turns-review-v1.json` are preserved unchanged; the latter is now stale, because the driver's hash changed.

**Inputs.**
- `HANDBACK-a1.md` is `9faafcee…`.
- All 11 entries of `source-hashes-a1.json` match the working tree: driver `a5710a99…`, tests `776b6c8f…`, and 9 dependencies unchanged.
- The committed driver in `87291cd` equals the previously reviewed `96752b7f…`.
- **Tests:** 26 passed, CUDA hidden.

**Turn segments.**
- Every new `Live.fresh` frame is retained, which addresses advisory C.
- Pad renewals happen at most every 40 ms, each after a full guarded proof in the same loop iteration.
- Leases are unchanged at 100 ms or less, capped at the segment end with `scope_not_after` at the block end, and released in `finally`.
- If capture stalls, the lease simply lapses to neutral.

**Short pulses (`--pulse-axis`).**
- They reuse the accepted `l4.pulse` (at most 80 ms, released in `finally`, over 10 ms overrun refused) and `l4.checked_shift`.
- A proxy routes `fresh` through the full guarded proof (focus, key, range HUD, idle banner, freshness, block not ended) and refuses any send whose deadlines cross the block end.
- Only the chosen axis is non-zero, with no buttons.
- Yaw uses the signed set; pitch is limited to ±0.5 and ±1.0; durations are 20, 33, 40, 67 or 80 ms.
- A fresh lead token precedes each pulse.
- Neutral 0.35 s stills are taken before and after each pulse.
- There is no automatic return pulse, so alternate signs (as in the example) to stay away from the pitch clamps.
- Any shift refusal or overrun stops the block.

**Offline analysis.**
- `perception/camera_turn_analysis.py` (`5ee47a5f…`, recorded in the manifest) imports only `math`, `re`, `cv2` and `numpy`, and never receives `Live`.
- It runs while the pad is neutral, and it can only **stop** the block (no candidate → `MotionRefused`), never add input.
- So leaving it out of the receipt does not widen the input space.

**The focal receipt is analysis input, not a guard.** It is self-declared (`acceptance`, `evidence`, `focal_px_1280`) and hashed into the manifest. It only orders the sitting: pulses come after focal acceptance.

**Receipt.** `camera-turns-review-v1-a1.json` pins the 11 a1 files, and the driver's `verify_receipt` accepts it. It covers input safety only; no rate, focal length or map is accepted.
