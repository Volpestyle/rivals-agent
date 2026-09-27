# Spider-Man alt controller profile, 2026-09-26

**Offline implementation only. No alt agent run is safe until independent review,
camera calibration and a recorded touch test pass.** The old deployment freeze
is invalidated; the lead re-freezes after calibration. No new camera values have
been measured or inferred here.

The executable combat mapping lives only in `agent/pad_bindings.py`. Source:
**James's alt settings, screenshots 2026-09-26**, supplied with the pad-binds brief.
`20260926164632_1.jpg` shows Jump, primary, secondary, melee and abilities;
`20260926164635_1.jpg` shows both team-up clicks, the ultimate chord and View.
`20260926164624_1.jpg` shows the targeting bind and hero toggles.
`20260926164617_1.jpg` shows Spider-Man H/V **247/124**; the All Heroes page
`20260926164601_1.jpg` shows 265/195. Advanced is collapsed: curve, deadzones,
boost, acceleration and aim assist are unknown. The supplied gameplay HUD crop
also shows Team-Up A on R3, Get Over Here on RB, swing on A, combo on B and the
two-click ultimate.

## Semantics and menu separation

- Melee Attack is unbound. The semantic `melee` action aliases Spider-Power,
  which is Spider-Man's melee, on RT. Simultaneous `melee` and `spider_power`
  combine with OR. Neither presses R3.
- Learned-policy `ultimate`, `melee`, `team_up` and `goh_targeting` remain
  masked by an explicit pre-registration set, regardless of support counts.
  Their correct physical mappings do not authorize a sendability flip; that
  requires a separate lead-recorded change under end-to-end-fit items 5 and 7.
- `team_up` selects Team-Up A (R3/`RS`). Team-Up B uses L3/`LS`; it has no
  separate action in the current learned vocabulary. Ultimate sets LS and RS
  before one `pad.update()` and releases both in one neutral report. Never use
  a sequence of independent `LS RS` taps for an ultimate.
- Hold to Swing, Hold to Wall Crawl and Hold to Run on Walls are ON; Simple
  Swing is OFF and unbound. Wall direction is Advance Vertically Upwards;
  Targeting Sensitivity While Aloft is 100. Y is unbound.
- The scripted swing already holds for `Cal.swing_s`, then releases; its
  button changes to A. That one-second duration remains a historical guess
  until the touch test. The learned executor sustains A across consecutive
  `web_swing` held steps and releases on the first inactive step. A press-only
  prediction holds for one 1/30-second step, not an entire swing.
- Wall crawl uses sustained Jump/LB against a wall. The learned vocabulary has
  no distinct wall-crawl action: sustained `jump` supplies the hold. A jump tap
  or the scripted Disengage jump pulse cannot claim sustained wall crawling.
  `wall_crawl` and `wall_sprint` helper aliases support explicit scripted holds;
  wall sprint combines held Jump and Spider-Power. Wall-contact response and
  release behavior still need observation. No new learned action/index was added.
- Live and loop share the combat whitelist. B/X and the stick clicks now have
  combat meanings. START, BACK, Y and d-pad remain forbidden in combat sends;
  range freshness checks and the neutralizing lease are unchanged. View/BACK
  remains accessible only through the existing guarded scoreboard method;
  environmental interaction is recorded in the mapping but not enabled there.
- `scripts/reenter.py` A confirms a proven practice tile or hero, RB changes
  hero tabs, and X confirms hero selection. `scripts/l4_menu.py` A/B/START/LB/RB
  control positively identified menus. `record.switch_to_spiderman` X/RB/A/X
  is legacy hero-picker UI. These are physical UI controls, not combat aliases;
  their old screen assumptions still require current visual proof before use.
- `scripts/pad.py` raw tokens remain physical. Prefer `combat:jump:0.15`,
  `combat:web_swing:1.0`, or `combat:ultimate:0.15` for combat; `LS+RS` is an
  atomic chord. Semantic commands retain the existing dangerous-button check.
  This manual tool has no HUD guard and is not an autonomous executor. Use a
  complete checkout: standalone historical copies of pad/record now also need
  the shared `agent/pad_bindings.py` module, not another pasted mapping.

Deployment dependency list: ship `agent/pad_bindings.py` alongside
`agent/controller.py`, `agent/loop.py` and `scripts/record.py`, plus the reviewed
hand tool `scripts/pad.py`. A flat `C:\rivals-agent\pad.py` also needs
`C:\rivals-agent\agent\pad_bindings.py`. Include the new module in the next
reviewed freeze; no deployment has been performed by this offline lane.

## Stale calibration inventory

Source of the old `Cal`: `docs/lanes/l4-controller.md`, “Measurements (Linear
curve, H / V sensitivity 265 / 75, aim assist 0)”, and its immutable L4 evidence.
None of those settings establish the alt's current advanced profile.

| Constant or consumer | Historical value and provenance |
|---|---|
| `Cal.yaw_map` | stick/rate: 0/0, .1/18.5, .2/61.5, .3/110, .45/172, .6/241, .8/320, 1/415 deg/s; `l4_measure.py yawmap` |
| `Cal.pitch_map` | 0/0, .5/43, 1/99 deg/s; same measurement |
| `Cal.focal_1280` | 465 px; pinned to a 2.08 s full turn at .45 stick (~173 deg/s), not solved from image shifts alone |
| `Cal.yaw_deadzone`, `pitch_deadzone` | Both None (unmeasured); interpolation through zero is not a measured deadzone |
| `Cal.latency_s`, `press_s` | .045 s controller latency budget; .033 s press duration, based on old A jump registering 8 ms in 6/6 trials and 17–20 ms pad-to-screen latency |
| Primitive durations | strike .7 s, pull .8 s, uppercut .5 s, melee 1.3 s, swing 1 s; recheck tap/hold response |
| `Controller` Search/Disengage | .45 yaw search, full-up 1.8 s then half-down 1.8 s leveling, integral pitch budget .30 stick-seconds, 180-degree turn from the yaw map |
| `scripts/reenter.py` | .45 stick / 172 deg/s and 465 px focal for door steering |
| `agent/placement.py` | 172 deg/s and 930 px focal at 2560 wide |
| `agent/startup.py`, `scripts/padprime_m1.py` | .45 stick for .3 s, later -.45; old observed prime 52–58 degrees and device-settle timing |
| `scripts/place.py` | half-stick pitch previously 43 deg/s; pitch reset times already None; lowmap explicitly requires Linear/265/75/assist 0 and checks against the old Cal |
| `perception/camera_motion.py` | derives focal from Cal; a degrees estimate inherits its focal assumption |
| `policy/range_bc/executor.py` | feedforward, saturation/feasibility ceilings and rate bands derive from, or describe, the old maps; default ceilings 415/30 yaw and 99/30 pitch degrees/step |
| `scripts/l4_measure.py yawleft` | historical fallback focal 760 is known wrong in the L4 note; always supply a newly period-pinned `--focal` |

Focal length is geometric, not a sensitivity gain; retain 465 only if the new
measurement independently confirms it. Do not scale any rates by 247/265 or
124/75. Mouse degrees-per-count calibration in `vocab.py` belongs to recorded
M&K sessions and must not be replaced with pad sensitivity numbers.

## Next PC session: calibration procedure

This is a future supervised measurement, not authorization to run it now.
The lead owns the desktop session, follows `rivals-live-game`, records native
video and retains all attempts. Stop on a rejected input path or lost range HUD.

1. After independent review, use the intended deployed checkout and the same
   `agent.controller.Live` virtual Xbox pad as the agent. Record checkout/code
   hashes, patch, account/profile, resolution/FPS, and screenshots of Spider-Man's
   entire Advanced section (curve, deadzones, boost, latency, acceleration, aim
   assist), 247/124 and all hero toggles/binds. Do not reset James's settings.
   Human places Spider-Man on open, level ground with textured scenery and no
   bot near the crosshair. No concurrent pad/capture-control owner; hands off
   during measurements. Ensure cooldowns/readiness before press trials.
2. Run the existing calibration script inside that desktop, from the checkout.
   Use a private environment with perception plus vgamepad. For example, in
   PowerShell (replace the output directory with a new sitting identifier):

   ```powershell
   $env:UV_PROJECT_ENVIRONMENT = 'C:/Users/volpe/AppData/Local/Temp/rivals-pad-calibration'
   uv run --group perception --with vgamepad python scripts/l4_measure.py period --report-timing --out data/calibration/alt-NEW/period-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawmap --report-timing --out data/calibration/alt-NEW/yawmap-candidate-1.json
   ```

   Re-establish the same safe view before each process: each opens a new pad and
   starts with the existing bounded walk/attack keepalive, which can move the
   pose. `period` holds .45 yaw for 7 seconds, guarded and renewed. Confirm in
   the video that its reported period is **one** full turn, not two turns or a
   repeated-texture match. Repeat as `period-2.json` and `period-3.json`.
3. Pin focal length using that 360-degree rate and the raw .45-stick image
   shifts in `yawmap-candidate-1.json`. The script now retains `dx`/`dy`.
   The upper-center yaw patch is `(520,100)-(760,260)` at 1280 width;
   its center has x=0 relative to the image center.
   `angle(f, dx) = degrees(atan(0/f) - atan(dx/f))`.
   Choose positive f so the difference of the two .45-stick pulse angles
   divided by their **observed report hold-time difference** matches 360/T.
   Maps use short deadline-capped `Live.send_guarded` pulses, not `Live.hold`'s
   50 ms renewal loop. `hold_s` records the update-return interval estimate;
   rates use its difference rather than nominal duration. Retain report
   timings with `--report-timing`, which uses the existing
   `agent.startup.watch_pad` observer after construction and embeds reports in the JSON, and
   compare with native video. Observer timestamps are update-return times, not
   hardware arrival times. A noisy/multiple solution leaves focal unknown.
   `--report-timing` also records `report_timing.full_reports`: each entry has
   `t`, raw integer `buttons` (XUSB mask), signed `lx/ly/rx/ry`, and unsigned
   `lt/rt` in 0..255 (`& 0xFF` handles signed ctypes BYTE layouts too). Existing
   `[time, nonneutral]` tuples remain in `reports` for compatibility. Full state
   is copied from the outgoing pad report after update, including releases and
   close, and retained in failed output too. A non-null observer `failed` means
   the capture is incomplete; missing bits must never be interpreted as zero.
   The equal-pulse focal candidate and old `yaw` optical-flow estimate are not
   acceptance evidence: L4 previously found them ill-conditioned.
   `period` refuses without at least eight confident horizontal phase shifts
   after the first .5 s, sampled at least .04 s apart: response >=.2, shift >=1
   band pixel, horizontal shift >2x vertical, and median confident shift >=1
   in the commanded direction (negative scene dx for positive yaw). Phase
   correlation uses a Hanning window on copies, preserving the evidence arrays.
   Identical/flat images never count. This prevents stationary false periods;
   it does not disambiguate multiple turns, so the native-frame check still binds.
4. With that measured f, repeat the map three times with new outputs:

   ```powershell
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawmap --report-timing --focal <measured-pixels> --out data/calibration/alt-NEW/yawmap-pinned-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawleft --report-timing --focal <measured-pixels> --out data/calibration/alt-NEW/yawleft-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py press --report-timing --out data/calibration/alt-NEW/press-1.json
   ```

   Yawmap samples .1/.2/.3/.45/.6/.8/1 yaw and .5/1 pitch with two durations
   each; yawleft checks -.3/-.6/-1. Retain frames, match scores, report timings
   and every failure. Reject ambiguous scenery matches, pitch clamps, bot
   aim-assist interference or disagreement between repeats/directions. Measure
   negative pitch from the retained return-pulse `back` shifts too before assuming symmetry. `press` tests Web-Cluster/LT
   and current Jump/LB at 8/16/25/33/50/80/120 ms, six trials each. It observes
   hero animation, so inspect the recordings; readiness failure is not a failed
   input and animation noise is not proof of a successful press.
   Yaw durations are .04/.08 s through .45 deflection and .02/.04 s above it;
   pitch uses .04/.08 s. Equal-pulse focal candidates use two .04 s pulses at
   .45, with each forward and return checked. Every pulse has a guarded release
   deadline and a finally-neutral; a measured overrun >10 ms is refused. This
   removes the old .25 s pulse and 50 ms hold rounding. Pitch uses a separate
   right-side patch `(920,280)-(1160,440)`, centered vertically.
   At measured 161 deg/s, the longest .45 pulse plus 10 ms allowance is 14.49
   degrees. Planning bounds of 500 deg/s yaw, 150 deg/s pitch and focal 250..1000
   keep all patch edges inside the image for these durations; these bounds are
   not Cal values or measured maxima. Synthetic tests exercise partial overlap
   through +/-512 px yaw and +/-256 px pitch. Larger matches are refused.
   Every map forward/return requires template score >=.8, displacement >=2 px,
   >2x off-axis motion and the commanded scene sign (yaw opposite stick; pitch
   same sign). Phase then verifies the template at its matched location using
   a Hanning window, response >=.2 and residual <=1.5 px per axis. This avoids
   the fixed-crop overlap failure without treating zero residual as movement.
   Identical/flat patches are refused. Nonfinite audit values become JSON null.
   Static, insufficient or ambiguous evidence raises `MotionRefused`, closes
   Live, and writes a failed record with the motion audit; it is unknown, not
   a zero rate or a measured deadzone. These conservative checks need live
   validation after independent review; synthetic controls alone do not accept
   a calibration. No automatic retry or extra movement follows a refusal.
5. Measure the low end and both deadzones using the existing
   `scripts/place.py --lowmap --declaration <new-measurement.json>` procedure:
   yaw .02/.04/.05/.06/.07/.08/.09/.10 for 1 s, pitch
   .05/.1/.15/.2/.3/.4/.5 for .5 s, twice each direction, with still-frame noise
   controls. **Prerequisite:** the lead must update and independently review
   its profile contract `LOWMAP_PAD_SETTINGS` against the newly observed
   Advanced settings, plus supply the newly measured full maps/focal to its
   fit. As written, this tool correctly refuses the alt profile; never attest
   the old 265/75 settings or bypass its declaration to make it run. Its
   declaration pins the current range-entry record, process identity, valid
   authorization window and James present/recording. A reported `cal_candidate`
   is not `cal`. Use measured rates/durations and the existing direction,
   repeat, noise, monotonicity and off-axis checks; keep deadzone intervals.
6. Record one bounded touch test per semantic action, observing the expected
   jump/cast/HUD change and release. Include melee/primary alias, Team-Up A
   alone, B alone and X targeting. Capture the alt's UI binds, then check a
   bounded X hold under fresh range proof: measure whether and when it opens
   CHANGE HERO. Hold behaviour is unknown; a range-HUD loss must release input
   and stop, leaving any menu recovery to the lead. Keep goh_targeting masked
   pending that evidence and a separate pre-registration change.
   For ultimate inspect actual pad reports:
   every down report has **both** LS+RS and the release clears both. Hold swing
   across multiple ticks then release; against a safe wall compare a short
   jump tap with a sustained Jump hold, then release; test held wall sprint.
   Confirm that no team-up fires as an unintended singleton part of ultimate.
   Use `Live.send_guarded`/`Live.hold` with `combat_controls`, not sequential
   thumb-click hand-tool taps. Single-action success does not establish a
   useful learned swing or wall-crawl policy.
7. Lead integrates measured Cal, timing, startup/arrival/placement effects and
   executor feasibility results; rechecks PID settling, pitch leveling and the
   configured curve across rates/directions. Review this delta, then re-freeze
   the affected deployment and the new mapping dependency. Only then consider
   a bounded agent pilot. Old receipts and checkpoints are not silently amended.

The lowmap profile update and supervised measurements are next-session work;
this offline change does not claim to complete them.
