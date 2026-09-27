# a3 draft 1: repair fresh-pad startup for both camera modes

Owner live-loop; VUH-1384; input-boundary reviewer binds-review. **NOT READY TO
RUN OR LAND.** Exact draft pins are source-hashes-a3-draft1.json. Only driver and
tests differ from a2. Python AST parsing passed; execution of owner tests and
native-still regression is held while James plays/records. No new desktop,
input, decode or GPU work. This packet supports static review now; final test
evidence and any revised pins must precede pre-run LAND.

## Demonstrated failure

Lead stopped data/calibration/alt-cam-20260927/yaw-01 after a 39-second token
wait following pad attach. Its ready-0 image showed the initial view; guard-39
showed the camera pitched down to the floor. The subsequent +.45 segment
refused motion and Switching Devices appeared. The native partial recording
is C:/Users/volpe/Videos/2026-09-27 14-27-37.mkv. No rate was accepted. Existing
evidence is preserved; neither this draft nor the prior a2 review erases it.

## Input change

Both modes now capture ready-attach BEFORE constructing Live. The operator
approves continue-attach.json by atomic rename. Fresh capture checks range,
idle, focus, keyboard and deadline throughout this wait. Live is constructed
only after approval and another proof, with settle_s=0. Source receipt is
checked again immediately before construction. The <=180-second block budget
starts before the first token wait, not after it.

With the independent monitor active, the first guarded input is the reviewed
M1 START_TURN_RX=.45 / START_TURN_S=.3 constant from agent/startup.py. It uses
collect_segment unchanged: proof per renewal, <=40ms renewal interval, <=100ms
leases capped to prime end, and neutral in finally. There is no post-attach
human gate or PNG encoding before that first non-neutral command. Native frame
copies for response evidence happen in memory during proof.

The whole approximately 50-degree M1 turn can exceed l4.checked_shift's
displacement envelope. This draft therefore checks a retained **40-100ms pair
within that same prime**, with negative scene direction in YAW_BOX. It does
not send a second pulse or weaken checked_shift. No suitable pair, no motion,
wrong direction or unreliable match stops without retry. Retain first native
frame, pair natives/timestamps, full-rate bands and actual report times. This
is observed response, not USB acknowledgement or proof of a calibrated rate.

After response verification, five full seconds neutral use START_SETTLE_S.
Fresh guards continue throughout; the last half-second must have stable scene
registration. The subsequent NEW ready-0 requires a separate token. Operator
must see range, no idle/device banner, level and bot-free view. Banner clearance
is explicitly an operator check; five seconds alone is not a banner detector.
Bad pose ends the block. No auto-leveling, search or new input type exists.

All ready waits now compare the current scenery with the saved approved frame:
finite phase score >=.5, correlation >=.95, shift <=1.5 band pixels per axis.
Ambiguous or changed views refuse, including immediately after token arrival.
This is conservative and may refuse animation or weak texture; native duplicate
and failed-yaw drift checks are still pending. It never authorizes a new input.

Initialization start/end events, manifest, initialization.json, full reports and
success/failure references label initialization_excluded. Prime/neutral times
stay outside measurement segments. A failure before the detail file exists
still has exclusion events. Measurement leases, pulse signs, allowed durations,
focal requirement and no-retry behavior remain unchanged.

## Pending verification and operation

Synthetic tests cover both-mode ordering, 39-second pre-attach wait without a
pad, refused/stale tokens, yaw/pitch pose changes, observed/refused prime motion,
five-second neutral delay and refusal closing both modes without measurement.
Existing guard/lease/blocked-capture tests remain. These new tests have not run.

After play closes, run CPU-only tests and a saved-native ready-0/guard-39 drift
regression with a duplicate-ready control. Do not decode the partial OBS just
for this regression. Then provide final bytes/evidence to binds-review.

Operator sheet now starts with HOLD, uses the durable Python path and requires
keep-alive before the first block. Lead owns reenter.py, desktop probes, input,
tokens and keep-alives. Old a2 receipt is stale for the changed source. No focal,
camera map, game FPS cost or live policy acceptance is claimed.
