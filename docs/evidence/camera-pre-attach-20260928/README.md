# Camera repair: pre-attach failures and diagnostic trace load

James transferred the VUH-1384 repair to the evaluator on September 28 while
herdr-lead handles disk cleanup. Live-loop handed over its existing patch and
parked. Independent v4 review accepted that patch; this is the small follow-up.

## Observed problem

Sitting d's yaw-01b still has no established failure cause or accepted camera
measurement. V4 fixes post-attach evidence loss. Its reviewer identified the
same generic-error/evidence gap before attachment.

The same attempt's frame-retention.json records 96 written before-attach PNGs,
300 dropped before-attach snapshots, and one dropped passing guard frame. Those
routine snapshots were being attempted on every acquisition during an operator
token wait. This is unnecessary CPU/disk work. It is not proven to have caused
the post-attach stop.

## Delta from v4

- Extract the existing capture_proof body into pre_attach_proof. Keep focus,
  keyboard, scope, range, idle and 100 ms freshness checks on every acquisition.
- Reuse GuardRefused to retain the actual failed capture and name the condition
  before attachment too. No pad exists on this path. Missing/erroring capture,
  focus/key refusal before capture, and scope expiry do not fabricate an image.
- Attempt routine before-attach PNG snapshots at most once per existing
  Journal.guard_period (1 second), instead of on every acquisition. This does
  not throttle capture, checks, ready images, refusal images or measurement data.
- All changes are in scripts/measure_camera_turns.py and its test. The attach,
  prime, collect, pulse, ready-pose, controller, capture backend and thresholds
  are unchanged from v4. No new input, retry, bypass or calibration acceptance.

Tests exercise each pre-attach failure, exact retained pixels without a pad,
capture/reader exceptions, disk-full reporting, and 105 successive captures:
all 105 are checked, only two routine snapshots are retained, and a failure
between snapshots stops immediately. Existing v4/native controls remain valid
for unchanged image readers and post-attach code. Test output and source pins
accompany this note. Independent review is required before live use.

Next: verify the reviewed source on the sitting checkout, coordinate exclusive
desktop ownership, and try one bounded block with the named-failure repair.
Any accepted camera rates still need observed turns; the lost sitting-d frame
cannot be reconstructed from OBS or from the new diagnostics.
