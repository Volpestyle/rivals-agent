# Prime response estimator — 2026-09-27

Owner: camera-analysis. Consumer/integration owner: live-loop, VUH-1384.

[Actual saved-native replay and limitations](../evidence/camera-prime-response-20260927/RESULT.md)
reproduce yaw-01b's false refusal: the original rigid 240x160 template scored
0.689 at dx=-170, within the displacement limit. Excluding the switch banner
does not repair its confidence. Smaller perspective-tolerant correspondences
retain the original >=0.8 NCC, stationary and sign protections.

New pixel-only `perception.camera_prime_response.analyze(before, after,
direction=-1, *, before_t=None, after_t=None)` returns serializable evidence
or refusal. Exact native replay finds 14 coherent patches, dx=-175.5/dy=0 at
1280 scale, minimum NCC0.8179. Same-frame, wrong-sign and bad-time controls refuse;
the reversed pair passes only with reversed expected sign. This is image motion
evidence, never rate/focal/angle or calibration acceptance.

24 owner tests passed; perspective valid controls in both signs and explicit
false-refusal coverage included. All owned CPU test/replay processes stopped.
No video decode, game input, GPU, sealed source access or existing-file edits.
No independent review is claimed. Lead owns driver integration and any live
input-boundary review. No extra prime or duration change is needed by this fix.
