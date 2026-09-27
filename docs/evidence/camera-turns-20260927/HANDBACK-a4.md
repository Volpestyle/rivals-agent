# a4: replace only the post-release prime response measurement

VUH-1384; owner live-loop; exact-byte input delta reviewer binds-review.
Only driver/tests differ from a3. Pins: source-hashes-a4.json. Driver diff:
a4-driver.diff. Input AST comparison: a4-ast-comparison.json.

The actual yaw-01b prime moved the view. Its retained 89.11ms native pair found
dx=-170 at1280, within the512px envelope, but the rigid240x160 template scored
.6893 against the unchanged .8 gate. The patch touches the Switching Devices
banner and spans perspective-deformed scenery. This was a measurement refusal,
not evidence that the pad failed to turn. Original sitting files are untouched.

The only driver change replaces l4.checked_shift AFTER collect_segment has
released with actuator-free perception.camera_prime_response.analyze. It gets
the same pair pixels/timestamps and direction -1, returns response audit, and
has no Live/pad/capture access. A refusal becomes the same l4.MotionRefused; no
retry, alternate input or fallback estimator is added. Successful dx/dy/score
remain response-only; no angle, focal or rate is inferred. Record the entire
audit and analyzer SHA in initialization.json. The module is outside the input
receipt, as the existing offline camera-turn analysis is.

AST evidence: every other top-level function is identical to accepted a3
(91b6d9b), including main, verify_receipt, collect_segment, attach_after_token,
run_block, measure_pulse and unchanged_pose. Replacing precisely the six new
post-release analysis statements with the prior one call makes the WHOLE MODULE
AST identical. Prime amount/duration, lease/freshness guards, token order,
5-second neutral settle, deadline, no-retry and all live calls are unchanged.

Owner checks: **42 passed in5.58s**, CPU/CUDA hidden, PCGuard, durable env;
Ruff passed. Existing fixed yaw-01 drift still refuses, duplicate still passes.
Records: a4-checks-run1/pytest.txt and checks.json. Reproducer reused unchanged
a3-owner-checks.py with a new output directory. New integration tests prove
analysis runs only after prime release and preserve the exact refusal audit,
with no settle/measurement continuation on refusal.

Analyzer owner independently replays the actual yaw-01b pair and adversarial
controls. Its attempt-02 native record reports14 coherent32x32 patches,
dx=-175.5/dy0, minimum NCC .8179; every patch retains >=.8 NCC plus peak uniqueness,
reverse correspondence and phase-residual checks. Same-frame, wrong-sign,
reversed-pair under original sign and duplicate timestamps refuse. Evidence:
docs/evidence/camera-prime-response-20260927/attempt-02/result.json.
Analyzer owner finishes its synthetic geometry suite/packet separately; no
independent exploratory-analysis review is requested. Input review covers this
bounded call-site change, and only binds-review issues the replacement receipt.

No input, desktop capture, video decode or GPU was used by live-loop for these
checks. Camera rates, focal, game FPS cost and acceptance remain unmeasured.
