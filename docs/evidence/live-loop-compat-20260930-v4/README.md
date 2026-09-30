# Compatibility v4: pitch convergence and duplicate-frame retention

Owner live-loop, VUH-1319. Produced offline for delta-only independent live-review
through lead w2:p1J. Uncommitted; no LAND/RUN authority. v1/v2/v3 and run-02 remain
immutable. Only agent/camera_compat.py and tests/test_camera_compat.py change.

## Run-02 diagnosis

run-02/result.json records insufficient_response_budget, 26 pulses, 1.3 s reserved
input, completed_sides=[], safety.stop_reason=null and close_returned=true.
The stop followed the final fresh observation at t=15.038733 s; post-perception
age was 27.78 ms. It was the full remaining-response-window reservation in pulse(),
not a scope guard or stale frame refusal. The old stage label post_perception_scope
described the last observation, not the clause raising the stop. v4 labels the
subsequent reservation stage pulse_response_budget.

**There was one yaw pulse and 25 pitch pulses.** The first fresh pulse proof had
target-2 error (-30.5,-163.25) at 1280 scale. Yaw immediately reached -10.25 px,
inside the 12 px deadband. The final native box was (1195,558,1337,699): centre
(1266,628.5), hence error (-7,-45.75) at 1280 scale. Horizontal alignment alone
does not complete a side; pitch still had 45.75 px to correct.

Pitch responses to |ry|=0.1/50 ms were **2.75-6.75 px**, median **4.75 px**.
Mean response delay was 200.67 ms, mean pulse cycle 555.98 ms. The median
response-to-next-proof gap was 319.58 ms. The per-pulse trace and hash comparison
are in trace-summary.json. All **26 response PNGs equal the following before PNG
byte for byte**, including pulse-25-response and pulse-26-before (which never sent).

Inspected stop.png shows both intended Galacta bots and the range HUD; the left
bot is above the crosshair. These pixels agree with the trace's remaining pitch
error. The task's approximate wall-clock time is not used to infer a video offset.
No OBS video decode was needed or performed: the retained trace and native PNGs
resolve this failure, so the corrected/repeated decode releases did not trigger work.

## Small bounded control change

The command is always selected again from the **fresh post-retention observation**:

| Axis/error at 1280 scale | Command magnitude | Scheduled hold |
| --- | ---: | ---: |
| yaw, abs(error) > 96 px | 0.3, exact measured signed knot | 50 ms |
| yaw, 48 < abs(error) <= 96 | 0.2, exact measured signed knot | 50 ms |
| yaw, 12 < abs(error) <= 48 | 0.1, exact measured signed knot | 50 ms |
| pitch, abs(error) > 39 px | 0.2, direction from existing sign contract | 100 ms |
| pitch, 12 < abs(error) <= 39 | 0.1, existing fine command | 50 ms |

The **39 px pitch threshold** is 12 px deadband + 4 * the largest measured fine
response (6.75 px). This means the run-02 failure at 45.75 px uses coarse pitch.
The multiplier is a counterfactual proportional-gain assumption, **not** an
accepted pitch-rate measurement: strength doubles and duration doubles. Below
39 px we use the already observed fine pulse. Overshoot or opposite/no response
continues to stop under the existing response rule.

**Explicit changed individual-pulse bounds:** yaw strength expands from 0.1 to
at most 0.3; pitch strength from 0.1 to 0.2; coarse pitch duration from 50 to
100 ms. The coarse pitch command fits the lead-authorized calibration envelope
(|ry| <= 1, 0.1-0.5 s; agent/camera_calibration.schedule). Fine 50 ms pitch reuses
the existing compatibility authorization, rather than pretending it is inside
that separate calibration-duration range. No pitch degrees/rates or interpolation
are claimed and no map or acceptance pin changes.

**Unchanged:** 100 ms freshness, 2 s total reserved input, 40 pulses, 60 s live
scope, 15 s side convergence, 10 s acquisition, 100 ms neutral wait and 750 ms
response window. The full selected duration is reserved before sending; a coarse
pulse that cannot fit the total cap refuses. Native release_at, the independent
response watchdog, continuous range/idle/focus/takeover monitoring and guaranteed
release remain unchanged. No neutral wait shortening is needed in this proposal.

## Retention removes repeat encoding, keeps fresh proof

NativeRetention writes the original native PNG exactly as before. Only when the
immediately preceding retained observation has **both the same timestamp and
the identical frame object** does retain() hard-link the new before filename to
the already-written PNG. File names and native bytes remain available; there is
one immutable inode for the same frame. Another stamp or frame object writes a
new PNG. A missing source/link error propagates, stops, releases and retains the
exception; there is no hidden fallback or asynchronous frame writer.

Saving/aliasing still happens while neutral. The runner always calls observe(),
re-matches target identity, recomputes axis/sign/strength/duration and checks the
fresh proof before send. A retained frame or hard link never authorizes input.
Retention events now record name, stamp, alias source and elapsed time so the
next attempt measures the remaining overhead instead of leaving it ambiguous.

Fifty actual NTFS hard links on the sitting's C: volume measured **p50 0.150 ms,
p95 0.266 ms**, max 14.21 ms (alias-timing.json), with samefile checks. The default
PNG path on D: measured p50 209.80 ms in ten writes; compression-off was worse,
p50 684.71 ms, and is rejected (retention-timing.json). These are different-volume
offline checks; they are not a live measurement of total saving cost. The original
run's trace supplies the observed ~320 ms repeated-image/proof gap. One original
response PNG per pulse still incurs encoding/IO, and freshness is still rechecked.

## Replay from recorded response numbers

replay_responses.py uses run-02's actual sequence of 25 fine pitch pixel responses,
initial fresh errors for both target ids, the one observed yaw response and
signed measured yaw-knot rate ratios. It applies both-axis camera shifts to both
targets and keeps total reservations. It assumes the hard-link path removes half
of measured per-cycle overhead, adds the extra 50 ms coarse hold and allows
120 ms for three final confirmation observations. These are declared timing
assumptions, not a replay of unperformed game actions.

| Counterfactual coarse pitch response | Side | Pulses | Side elapsed s | Reserved input s |
| --- | --- | ---: | ---: | ---: |
| 4 * recorded fine response | left | 12 | 5.04 | 0.95 |
| same | right | 4 | 1.64 | 0.20 |
| 2 * recorded fine response | left | 20 | 8.38 | 1.65 |
| same | right | 4 | 1.64 | 0.20 |

Totals: **16 pulses/1.15 s** or **24 pulses/1.85 s**, respectively. Both sides
are within their individual 15 s convergence windows and the unchanged shared
caps. Starting from the failure's (-7,-45.75) error instead, the 4x case completes
left in 6 pulses/2.45 s/0.35 s input. response-replay.json has every assumed
pulse, before/after error, and limitations. The baseline model stops on the
response reservation after 25 pulses, close to the observed 26; it is a model,
not an exact reconstruction of wall-clock scheduling.

model_run.py additionally executes the actual CompatibilityCheck with synthetic
capture, pixel detections of native-sized bots, tracker, reservation checks,
150 ms writes/0.2 ms aliases and a sign-correct plant. v3 refuses with no side
completed; v4 passes both sides in the nominal plant in 6.90 s/14 pulses/1.05 s
input, and at half nominal pitch gain in 12.09 s/26 pulses/1.95 s input. The
half-gain model also reduces the fine-pulse gain, making it a separate sensitivity
case from the recorded-response replay. Coarse pitch gain remains unmeasured;
slower response can still hit the total cap safely. Neither model accepts a live
compatibility result or predicts physical pad/display latency.

## Verification and next consumer

152 compatibility/live-safety tests pass. New tests cover threshold boundaries,
both coarse/fine durations, actual-duration reservation at the 2 s cap, two-side
large-pitch convergence with slow writes, hardlink byte/inode identity and missing
source failure, same-frame/different-stamp refusal to alias, and a new fresh proof
after alias. Existing scope, takeover, late response, invalid detection, admission,
watchdog and real-Live/fake-capture tests remain passing. Ruff passes.

v4 review-inputs.json pins runtime/dependencies, exact before/after/delta, supporting
scripts/results and run-02 native evidence. Generated bytecode is excluded from
pins and the packet. Prior packets are untouched. No live input, capture, commit,
push, training or ongoing job was started. Lead owns delta review and VUH-1319
reconciliation: produced v4 is not LAND, and any retry needs separate authority
plus all current placement/hash/settings preflights. The 1440p-only warm-up and
single-frame placement limitations from v3 remain.
