# Live-loop: camera rebind preparation, 2026-09-29

Owner: live-loop. Consumer: [VUH-1319](https://linear.app/vuhlp/issue/VUH-1319),
after [VUH-1384](https://linear.app/vuhlp/issue/VUH-1384). This is offline
preparation for the narrowed compatibility check, not a ten-encounter campaign.
The lead supplied the current Linear description/comments at 01:05 CDT.

## Delivered boundary

`agent/camera_map.py` and `agent/camera_maps/{legacy-265-75,alt-247-124}.json`
provide the data contract. The controller/startup/camera-selection changes remain an **unapplied patch**.
The safety follow-up changes only the active `agent/loop.py` and owned tests;
its current delta-review packet is `docs/evidence/live-loop-safety-rebind-20260929-v2/`.
The v1 packet and its FIX review are preserved unchanged.
The initial `live-loop-rebind-20260929/` packet is preserved as historical evidence.

The lead explicitly prohibited edits to controller/startup tonight: their bytes
are pinned by `camera-schedule-20260929-v2/review-inputs.json`. The pending patch
must be applied only after calibration acceptance, independently reviewed by
live-review and included in a new deployment freeze. Its camera-selection hunks also change loop.py and remain deferred. The refreshed
patch uses the final safety-loop bytes as its preimage.

## Profile contract

The loader accepts a built-in profile name or an explicit JSON path. Every
measurement has value, status (`accepted`, `candidate`, `missing`), sitting,
receipt and uncertainty. Unknown numeric uncertainty is explicit, never zero.
The file SHA-256 identifies the exact profile; receipt paths are recorded but
never opened by the loader. Loading a map performs no capture, input or corpus IO.

Yaw positive/negative and pitch positive/negative have independent knots, with
nonnegative rate magnitudes. No unmeasured direction is mirrored. Missing knots
are holes: interpolation cannot skip them. In-between rates require an explicit
piecewise-linear model record. Measured zero-rate knots can represent a deadzone;
the historic linear-to-origin assumption is recorded explicitly in the old map.
There is no extrapolation above a measured endpoint; inverse requests saturate
at full stick. A complete controller map needs all four directions through full
stick, focal, effective latency and the interpolation record, plus nonzero
responses at the timed-turn deflections.

`load_camera_map(..., live=True)` refuses candidate/missing measurements when
queried; `.require_controller()` checks the whole controller requirement before
any hardware can be opened. Offline queries can inspect the single candidate
point without pretending the rest of the map exists. Offline full-controller
replay also needs a complete map, but its measurements may be candidates.

The legacy file preserves the deployed floats exactly: notably 18.5 and 61.5
deg/s, where the L4 prose rounds to 18 and 61. Its accepted entries mean the
historical model is retained for that profile, **not** a new acceptance of alt
settings. Effective latency and pitch symmetry are marked as historical model
assumptions, with no invented measurement precision.

The alt skeleton has only **RX +0.45 = 154 deg/s, candidate**. All other
measurements are missing. The initial return-period interpretation has now been
checked by the evaluator: seven native full turns give 153.893 deg/s and
conservative timing bounds 151.397–156.473; the 77 deg/s alias is ruled out.
The rounded point retains those asymmetric bounds and links the native-count
record. The lead will accept the map as a unit after the remaining points exist;
this delivery grants no single-point acceptance.

Live admission in the deferred v2 patch additionally requires an explicit map,
an operator settings-match declaration, and a whole-map acceptance record whose
SHA-256 is in the code-reviewed `REVIEWED_ACCEPTANCES` registry. The registry is
empty: neither the legacy nor alt map has live acceptance in this delivery.
The record pins map bytes, settings and evidence bytes; status strings alone
cannot authorize live input. All timed turns are checked before attach and
locally bounded to four times the legacy duration, and recorded in metadata.

To consume an accepted revision, fill a versioned JSON using the same schema
and select its explicit path with the pending `--camera-map` argument. No new
controller code is needed for different rates, focal, latency or directional
asymmetry. New interpolation model families would require code and review.
The candidate skeleton can remain as a historical file when a new accepted
revision is supplied. Game settings/profile identity still need verification at
the sitting; a JSON label does not prove which settings the game is using.

## Constants and consumers found

| Location | Current dependency | Pending treatment |
|---|---|---|
| `agent/controller.py:Cal` | Focal 465 px at width 1280; yaw `(0,0),(.1,18.5),(.2,61.5),(.3,110),(.45,172),(.6,241),(.8,320),(1,415)`; pitch `(0,0),(.5,43),(1,99)`; effective latency .045 s; unknown yaw/pitch deadzones | Load legacy defaults from data; `Cal.from_profile` validates selected data. Preserve direct `Cal` overrides for old offline consumers. |
| `controller._interp`, `stick_for`, `_advance`, `_aim` | Piecewise-linear inverse, full-stick saturation, symmetric sign reflection, camera integral and feedforward aiming | Selected profiles use independent signed tables. Default legacy behavior remains equivalent. |
| `controller._follow` and `_aim` | `focal * width/1280`, `atan2` pixel-to-bearing, `tan` projection, latency compensation | Consume the selected focal/latency through `Cal`; projection formula stays the same. |
| `controller.step(Search)` | +.45 yaw for .3 s per .5 s; upper-clamp pitch +1 for 1.8 s, then -.5 for 1.8 s; 12 s reset cycle; half-stick residual unwind | Preserve yaw stop/look and nominal pitch sweeps (178.2 and 77.4 degrees); divide each pitch sweep by the selected signed rate. Keep residual unwind policy. |
| `controller.step(Disengage)` | 180 degrees divided by positive full-stick yaw rate | Use selected positive full-stick rate. |
| `controller` aim policy | KP 20, KI 2, done .4 degrees, max integral 5, pitch budget .30 stick-seconds, residual threshold .03 | Policy limits, not measured camera curves; retained, to be observed in the compatibility check. |
| `agent/startup.py` | Prime +.45 and search -.45, each .3 s; legacy prime about 52–58 degrees; 5 s settle and .15 s inter-turn wait | Loop-supplied calibration preserves nominal 51.6-degree turns using independent signed durations. Other direct callers keep their original .3 s pulses. Existing time/turn budgets stay. |
| `agent/loop.py:_camera` and `agent/tracker.py:reproject` | Controller yaw/pitch history at `t-latency`, focal scaled to actual frame width; tracker projection uses supplied focal | Pass the selected controller through the loop. Add profile/hash/settings to summary and start metadata, including pose-only. |
| `agent/placement.py:33,92`; `docs/lanes/reentry.md:263` | `FOCAL_PX=930` at 2560; `YAW_DEG_PER_S=172` at .45; bearing and turn-time calculations | Pinned by the range-benchmark freeze. Needs re-measurement and re-freeze after map acceptance; no hand edits tonight. |
| `agent/placement_sim.py` | Uses placement's focal and turn model | Historical placement simulator, unchanged. |
| `scripts/place.py` | TURN_STICK .45, low-map settings Linear 265/75 assist 0, default `Cal`, placement pitch-reset timings | Outside scope; do not use it as an alt-calibrated placement tool. |
| `scripts/reenter.py` | YAW_STICK .45, YAW_DEG_S 172, FOCAL 465 for arrival geometry | Outside scope; menu/arrival ownership remains with lead. |
| `scripts/l4_trial.py`, `l4_measure.py`, `padprime_m1.py` | L4 trials use `Cal` plus .45 offset turns; measurements/prime schedule use fixed experimental deflections | Historical or separately reviewed measurement tools; untouched. |
| `agent/live_range_bc.py`, `policy/range_bc/executor.py` | Separate learned executor calibrations use `Cal` and positive tables/deadzones | Outside this scripted-loop integration. No claim that the learned executor now supports signed profile files. |
| `scripts/replay_steps.py` | Historical per-step caps 415/30 yaw and 99/30 pitch | Offline labels, outside scope; not silently rebound. |

The pending patch does not change bindings, primitive press/strike/pull/uppercut/
melee/swing durations, tracker selection, range guards, or frozen learned-policy
identity. Editing controller/startup/loop later also requires reconciling the
older `698d8831` deployment freeze before that checkpoint can run again.

## Brief live compatibility check plan

1. Evaluator completes signed yaw/pitch coverage, focal and timing/model evidence;
   lead accepts the map as a unit on VUH-1384. Apply the pending patch only then,
   rerun its synthetic checks, obtain live-review's exact-byte approval and
   re-freeze all changed runtime inputs plus the selected map. Keep the existing
   accepted binding/touch-test evidence for unchanged controls.
2. Lead owns desktop entry and verifies the current profile, range HUD, focus,
   normal cooldowns and no idle warning on fresh pixels. Use one pad session,
   native recording and retained timestamped commanded inputs. Confirm the
   approved wrapper continuously enforces focus, HUD, idle warning, any-key or
   mouse-button takeover, hard deadline and guaranteed release.
3. One short run, at most 20 seconds of controller activity after bounded startup:
   inspect startup turn direction/displacement; a small measured target offset
   each side and above/below; Search re-level; a bounded Disengage turn if safe.
   If one run cannot expose a case, record it as unexercised rather than starting
   a campaign or repeating encounters. Target placement is lead-supervised.
4. Offline, compare retained native frames with the map's predicted signed turn
   and focal-based aim errors. Record wrong-sign motion, sustained oscillation,
   pitch-clamp/re-level errors, command-vs-frame timing and safety stop/release.
   Report compatibility or a named failure per exercised behavior, with unknowns
   intact. This is not a KO benchmark or a learned-policy result.

**Safety follow-up produced:** every live CLI mode now requires the explicit game
PID and uses the existing read-only focus guard and calibration tool's all-key/
mouse-button takeover reader. A latched monitor checks focus, takeover and the
hard startup-plus-run deadline independently of capture; pixel proofs check HUD
and idle throughout startup, controller sends and scoreboard transitions. Every
CLI exit closes the pad and monitor. Bare `LiveIO()` refuses before hardware;
callers must provide an explicitly guarded `Live`. The bridge owner must update
`agent/session.py` before enabling VUH-1316. No bridge file was edited.

This is offline preparation. The lead routes the frozen safety delta and updated
controller/startup patch to live-review `w2:p3E` before landing or running it.
Calibration completeness, independent review, application of the deferred patch
and a new deployment freeze remain required for the VUH-1319 live check.

## Verification and handoff

The packet records final test outputs, patch preimages and runtime-freeze checks.
Its `verify_patch.py` applies the patch only to disposable named copies, then
runs synthetic controller/startup/loop tests and compares 1,500 exact pad reports
and camera states with the pinned pre-patch controller. No real pad, desktop,
GPU, paid compute, held-out recordings or sealed data were used.

The initial packet records **296 passed**. The safety follow-up has **331 passed**
targeted tests and **521 passed** with the deferred camera patch applied only to
disposable copies. Its receipt records nine matching current calibration pins.
The packet README holds the broad-suite failure reconciliation and remaining
limitations. No account connector was substituted for unavailable direct
workspace Linear tools. The lead owns VUH-1319 publication/readback, review
routing and acceptance; this remains preparation produced, not calibration
accepted or behavior demonstrated live. VUH-1384 remains the calibration
prerequisite.

Final isolated full stdlib run (no exclusion, after 657020d): 2690 passed,
138 skipped, 28 failed and 12 errors. All bad node IDs reproduce without this
lane runtime on the 8331c45 baseline; perception adds five distinct bad IDs,
also baseline-reproduced. Exact names and CRLF attribution are in the packet
`baseline-failures.md`. No lane-caused failure remains. The safety delta stays
uncommitted and frozen for the lead-routed independent live-input review.

## Safety review v2 follow-up

V1 review required a scoreboard fix: negative HUD proof during the native
RETURN_S fade wait incorrectly latched range loss. V2 opens a bounded
scoreboard-only latch exemption and closes it in finally. A false proof stays
false; focus, all-key/mouse takeover, deadline, idle and reader failures still
close immediately. Real Live plus fake pad/capture tests cover return, timeout
and each hard stop. Scripted/Jev/learned now stop on the first missing HUD frame;
the former 0.25 s live grace is intentionally removed under AGENTS.md, confirmed
by the lead. Ordinary offline replay grace remains.

Known caller gap: scripts/range_cast_probe.py:324-347 must gain takeover and an
independent scope monitor before its next live use (owner: range-cast probe).
Bridge owner (VUH-1316): agent/session.py must pass an explicitly guarded Live
before enabling the bridge. Neither caller was edited.

The v2 README and review-inputs.json carry the frozen bytes, tests and next
consumer. Only agent/loop.py and tests/test_loop_safety.py change from the v1
active safety delta; controller/startup and all nine calibration pins remain
untouched. V2 is produced, pending independent delta review, not live approval.
