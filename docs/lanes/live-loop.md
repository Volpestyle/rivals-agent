# Live-loop: camera rebind preparation, 2026-09-29

Owner: live-loop. Consumer: [VUH-1319](https://linear.app/vuhlp/issue/VUH-1319),
after [VUH-1384](https://linear.app/vuhlp/issue/VUH-1384). This is offline
preparation for the narrowed compatibility check, not a ten-encounter campaign.
The lead supplied the current Linear description/comments at 01:05 CDT.

## Delivered boundary

`agent/camera_map.py` and `agent/camera_maps/{legacy-265-75,alt-247-124}.json`
provide the data contract. The controller, startup and loop changes are an
**unapplied patch**, with tests, in
`docs/evidence/live-loop-rebind-20260929/`. No active live-input path was changed.

The lead explicitly prohibited edits to controller/startup tonight: their bytes
are pinned by `camera-schedule-20260929-v2/review-inputs.json`. The pending patch
must be applied only after calibration acceptance, independently reviewed by
live-review and included in a new deployment freeze. It also changes loop.py;
shipping that part early would leave an inconsistent runtime.

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
| `agent/placement.py` | `FOCAL_PX=930` at 2560; `YAW_DEG_PER_S=172` at .45; bearing and turn-time calculations | Known separate caller, outside the lead-approved rebind scope. |
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

**Follow-up authorized by the lead:** bare `agent.loop` has no human-takeover monitor, and
its focus composition is limited to range-skill/episode-collection mode. This
patch preserves that boundary. After this data/patch delivery, live-loop owns the
fix in `agent/loop.py`, reusing the existing all-key/mouse takeover helper and
focus composition without editing pinned implementations. Tests must cover all
stop paths. The lead will route the frozen fix and the rebinding patch together
to live-review before any run. A bare-loop command is not authorized by this
plan; calibration completeness alone does not remove this operational gap.

## Verification and handoff

The packet records final test outputs, patch preimages and runtime-freeze checks.
Its `verify_patch.py` applies the patch only to disposable named copies, then
runs synthetic controller/startup/loop tests and compares 1,500 exact pad reports
and camera states with the pinned pre-patch controller. No real pad, desktop,
GPU, paid compute, held-out recordings or sealed data were used.

The initial packet records **296 passed** targeted checks. Full stdlib and
perception checks are still being reconciled against unmodified runtime HEAD;
the perception group already has an unrelated missing-torch collection failure.
The safety follow-up will carry the final broad-suite results and failure lists,
separately from the pending-patch checks. The lead owns Linear publication and
acceptance; no account connector was substituted for unavailable direct workspace
tools. Pending VUH-1319 correction: record the standalone loader/maps and unapplied
patch as produced, retain calibration acceptance, independent delta review,
deployment freeze and brief compatibility check as remaining work, and name the
human-takeover/focus wrapper gap. VUH-1384 remains the calibration prerequisite.
