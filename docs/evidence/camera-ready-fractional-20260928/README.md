# Fractional patch confidence: ready for independent delta review

**Implemented but uncommitted, unstaged and not approved for live use.**
Only `perception/camera_ready_pose.py` and `tests/test_camera_ready_pose.py`
change from approved base `adfe13f6a1516d5987424acbda9cfbe1211929d2`.
`delta.diff` and `review-inputs.json` pin the exact change and all 12 driver
dependencies plus analyzer tests. The v2 receipt is stale on this checkout.
The lead dispatches live-review; owner has not issued a replacement receipt.

## Cause and bounded change

The guard estimated a fractional displacement but scored correspondence at the
integer-grid template peak. This penalized a valid subpixel alignment before
the whole-band residual could be evaluated. Now each 96x60 current patch is
sampled with `getRectSubPix` at its already-estimated fractional location and
that correlation is compared to the same NCC >=.95 threshold. The audit keeps
both `integer_ncc` and the new aligned `ncc`.

No offset is changed or optimized again. Peak selection, parabolic offset,
integer-surface uniqueness >=.02, reference texture, patch count and coverage,
spread <=.75, raw displacement <=1.5 band pixels, phase >=.5, and registered
whole-band correlation >=.95 remain unchanged. Uniqueness deliberately still
uses the original integer score surface; no confidence boost changes its margin.
Nonfinite aligned correlation refuses. Driver, retention, prime, send/lease,
token and deadline code are untouched. Edited files retain CRLF without a BOM.

## Evidence and tests

**95 tests passed in 12.10 s** (`final-tests.txt`), CPU at BelowNormal with two
OpenCV/BLAS threads and CUDA hidden. Ruff and scoped whitespace checks pass.
`native-replay.json` records **51** hash-checked native/control cases:

- All **42 prior outcomes are identical**, including all 30 earlier ready
  poses, journal 150 passing, journal 148 refusing, centre noise/flat refusing,
  true translations refusing and yaw-01b prime motion refusing as a ready pose.
- Sitting c yaw-01r's exact **analyzed** reference/current pair now passes with
  all six patches. Original integer NCC .9184–.9407 becomes aligned
  .9639–.9771. Offset median stays (-.19614, -.63731) band pixels, spread .17825;
  whole-band residual is .978315. Tests compare every offset, original peak and
  uniqueness to the saved failed audit. This is a bounded-pose result, not proof
  of exactly zero physical movement.
- Synthetic half-band-pixel translations of this native reference pass in
  both axes/signs. The requested −.5 vertical control has residual .984103.
  All ±2-band-pixel controls still return `changed`. At native 2560 width,
  half a band pixel is two native pixels; two band pixels are eight native
  pixels. The original bound remains 1.5 band pixels.

Only saved calibration PNGs were read. No native-video decode, GPU, inference,
desktop capture, game input, cloud use or live attempt. All owner jobs exited.

## Prime-response check: no production change

The saved yaw-01s pair was inspected and replayed. The original prime analyzer
finds 7 correspondences but only 5 coherent ones and refuses
`incoherent_displacement`. Of 48 patches, 17 are low-texture, 22 weak/ambiguous,
2 fail reverse correspondence, and 7 pass local checks.

An isolated, **offline-process-only diagnostic** rescored `_locate` confidence
at fractional peaks while leaving integer coordinates and all downstream
reverse, phase and coherence checks unchanged. One match rose from .78791 to
.80555 (margin .12657), yielding 8 correspondences / 6 coherent. It **still
refuses**: 6/8 = .75 is below the unchanged .80 coherence requirement. The
diagnostic does not establish a safe general prime fix; it is not a candidate
implementation. See `prime-diagnostic.json` and `check_prime.py`.

Thus integer sampling affects one prime match, but it does not explain away
this refusal. Poor texture and inconsistent scene displacement remain. Unlike
the pose guard, the original prime pipeline retains integer positions and
checks their fractional phase residual separately. Production prime source
remains exactly `465fc479…`, unchanged. No threshold, coverage or scene-selection
change is bundled into the pose repair.

## Limits and next step

Interpolation changes confidence behavior; these are the demonstrated cases,
not calibrated universal error bounds. The earlier row-support/content limits
remain. No yaw rate, focal or complete camera map has been accepted, and no
scripted baseline has been rebound. Send this two-file delta to live-review;
after LAND, the lead can authorize integration and a new exact-byte receipt.
