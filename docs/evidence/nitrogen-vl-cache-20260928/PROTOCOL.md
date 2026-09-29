# One VL-cache attempt, fixed before execution

Owner start: 2026-09-28 19:12:46 CDT; owner deadline 19:57:46 CDT.
Lead authorizes $0 local GPU measurement, at most five minutes GPU occupancy.
Game absent; idle OBS allowed, recording forbidden. No cloud APIs or paid work.

Keep the authenticated checkpoint, FP32 parameters/BF16 autocast, image processing,
25 dimensions, 18 actions, CFG=1 and all 16 Euler iterations unchanged. Install
only a call-local wrapper on the loaded VL mixer's forward method. Its first
invocation computes the original forward; the next 15 return that tensor. A new
wrapper/cache is created for each get_action call and removed in finally. No
vendored source or checkpoint changes, training, compiler, step or horizon sweep.

Before any timing, run uncached raw-action inference three times for each of three
retained fixtures at seeds 0, 1 and 2. Reset the same seed immediately before each
call. Let R be the greatest absolute raw-coordinate difference among repeats.
Fix absolute tolerance T = max(1e-6, 5*R), relative tolerance zero. Refuse if T
exceeds 1e-5, any raw value is nonfinite, or baseline decoded button decisions or
stick signs vary. The 1e-6 floor is a predeclared FP32 rounding allowance, not a
tolerance fitted to cached outputs. Save/fsync repeatability.json before parity.

Compare cached versus the saved uncached reference for all nine fixture/seed
pairs, plus image sequence A/B/A with fixed seed, using that fixed tolerance.
Require unchanged decoded buttons and both stick signs. In these parity calls,
check exact equality of every VL input within the call and count 16 wrapper
calls/one true mixer evaluation. A/B must have distinct mixer-input hashes and
the second A must recreate its first output; no cross-observation cache reuse.
Stop before timing if any check fails.

After parity, profile mixer GPU time within one uncached sampler call. Then run
three warmups and 30 standalone calls for uncached and cached paths, cycling the
same three fixture tensors. Same two CPU threads, BelowNormal, private runtime
as a24a475. Timing ends with CPU-readable decoded outputs; capture, preprocessing,
host-to-device input transfer and actual pad delivery excluded. Expensive
within-call equality checks are parity-only; cache lifetime is identical in timing.

Stop and park the full actor if parity fails, owner/GPU time expires, or cached
p95 is greater than 150 ms. No second optimization or retiming after a near miss.
Passing permits only a bounded native-label adaptation proposal, never a fit.
The 150 ms investment cutoff does not alter the 250 ms live freshness gate.
