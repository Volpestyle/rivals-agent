# Camera ready-pose and FPS startup repair candidate

Owner: live-loop. CPU only, $0. No desktop, input, native-video decode, model
execution or GPU work. **Independent live-input review pending; a4 is stale.**

## Behavior

`perception/camera_ready_pose.py` compares the fixed original ready image with
each fresh image. It keeps the existing right-of-hero 265x150 scenery band,
phase-confidence floor 0.5 and absolute displacement bound 1.5 band pixels
(3 px at width 1280). It does not update the reference or hide motion by
registering images before measuring displacement.

Four 96x60 patches cover two separated columns and two rows. At least three
must match at NCC >=0.95, with a peak margin >=0.02 outside a 5x5 neighborhood,
and both rows/columns represented. Subpixel quadratic peak offsets must agree
within 0.75 band px of their componentwise median; every accepted patch and
the global phase displacement must stay inside the original 1.5 px bound.
Unknown, ambiguous or inconsistent evidence cannot pass. A confident global
shift beyond the bound refuses immediately.

The first 64x48 six-patch probe lost uniqueness on the distorted tail frames.
Larger 96x60 patches recovered spatial support without lowering NCC or peak
uniqueness requirements (final NCC is stricter than probe 1's 0.90). Probe 1/2
outputs are retained as exploratory threshold-selection evidence, not final
qualification. Native support is narrow: one ready scene and one moving prime
pair, plus synthetic controls. These thresholds are engineering gates, not
calibrated probabilistic error bounds.

The driver allows at most one second of neutral quality recovery per proof,
capped by the existing block deadline. A quality failure requires two
consecutive proven frames before returning. Actual motion and focus/key/range/
idle/freshness failures still stop; no token, attach or segment starts on
unknown quality. The independent monitor, prime, durations, leases and commands
remain unchanged. The analyzer is newly included in the exact-byte receipt
because this guard can authorize input. The old a4 receipt cannot verify.

On a ready-pose refusal, the exact reference/current arrays and their capture
and decision timestamps are held in memory. They are encoded only after the
top-level exit closes the pad, or records that no pad was ever attached. The
refusal bypasses the lossy frame queue. Encoding failure is recorded without
replacing the original stop reason. FPS startup similarly retains its last
fresh frame and current refusal frame after the actuator-free startup loop
stops and its worker is asked to stop; missing frames are explicitly marked.
No synchronous refusal-image encoding runs inside a proof or input loop.

FPS startup discards stale frames and re-primes throughout cold warm-up, within
three seconds per continuous recovery and ten seconds total. No stale pixels
are submitted. The same worker retains the one-time five-second cold allowance
and 250 ms warm limit. Two consecutive fresh proofs are needed to re-prime;
phase execution retains the existing 100/250 ms limits. Events now record
acquisition/proof completion and inference overlap. No GDI or capture-backend
change was made: DXCAM remains the fixed backend across A/B/A.

## Verification

- `tests-review.txt`: **128 passed in 15.63 s**, CUDA hidden, CPU/BelowNormal,
  two OpenCV threads. Only the three explicitly named test modules were run;
  `--corpus` enabled their two fixed, authorized calibration-PNG tests.
- `pose-final.json`: all 30 retained yaw-01 frames pass; native translated
  controls beyond the original bound refuse. The Sep27 yaw-01b moving pair
  refuses as a ready pose; its original prime-response analyzer still accepts
  that direction of motion. Source PNG hashes are pinned in the replay result.
- Synthetic controls cover bounded jitter, yaw/pitch motion, accumulated drift
  against the original reference, blank/repetitive/blurred/unrelated scenes,
  one-patch evidence, hero-only animation and changed geometry. Driver controls
  exercise recovery, consecutive proofs, deadlines, no attach/send after
  refusal, propagation of the existing full guards, copied refusal arrays,
  encode-after-close ordering, timestamp round-trip, and encoding failure.
- `fps-timing-final.json`: the six recorded capture/reader durations reproduce
  `stale_proof` with source 8a97a760, while the repaired runner reaches `ready`.
  Frames 1 and 6 are discarded and never submitted. The continuation and worker
  are explicitly synthetic; this is not another CUDA or game-FPS measurement.
  The source event log and both runner versions are hashed. Fake tests include
  persistent missing/slow frames, guard failures during recovery, prediction
  deadlines and unchanged strict measured-phase behavior.

The first camera test attempt was stopped after a fake clock never advanced
during an unknown-quality case. The test now advances its injected clock; the
production recovery clock always advances. The retained diagnostic traceback
is `camera-tests-01.txt`. Only our own test processes were stopped.

### Limits and next consumer

The exact yaw-01 failure image is absent or unidentified: 86 frames were dropped,
30 saved; final saved raw correlation is .9897 rather than failure.json's
.9438. This fixes retained neighboring distortion and tests the recovery
contract, but does not establish an exact failed-frame pass. No video was
decoded while Marvel remained active, and no fresh capture was attempted.

Lead routes `review-inputs.json`, `driver-delta.patch`, `input-ast.json`, source,
tests and this record for independent pre-run review before the retry. No owner
receipt is issued. Arrival is via `reenter.py`; no hand-posing. Lead must inspect
the actual ready image after arrival: unprovable scenery or a non-level/bot view
ends the attempt rather than prompting automatic camera search. After review,
verify the reviewer-issued receipt on the committed checkout before use.
Focal, camera map, GPU FPS cost and learned-policy acceptance remain unknown.
