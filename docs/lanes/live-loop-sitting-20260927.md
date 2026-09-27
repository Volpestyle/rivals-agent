# Supervised sitting: camera map and CUDA FPS cost only

Owner live-loop; booking/desktop/Linear owner herdr-lead; input reviewer binds-review.
VUH-1384. Plan updated 2026-09-27; no sitting has run.

**Readiness verdict: camera + FPS only.** Remove the learned-versus-scripted
block from the earlier 55-minute proposal. Proposed reduced reservation: **40
minutes**, preserving the lead's **hard stop at minute 33 if camera work is
incomplete**. James stays present while input runs; the lead books the time.

The approved legacy fallback is interim94-s012 model_nohud seed 0, SHA256
`2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`.
On the preselected 120-second admitted TRAIN window (3,600 native frames), it
produced zero supported presses/holds and zero raw median yaw/pitch every step:
100% action-only and action-plus-camera neutral. Human comparison: 437 supported
presses (3.642/s), 28.42% action neutral and 9.92% combined neutral. Human mean
absolute yaw/pitch was 2.027/0.864 degrees per step; pitch uses the recorded
derived-equal-sensitivity calibration, not an independent measurement.

This diagnostic used raw camera median classes, independently of Cal, and
self-fed decoded outputs. It confirms the fallback's failure; it does not
promote a policy or measure live outcomes. Evidence:
`docs/evidence/live-loop-fallback-train-20260927/run/report.json`.
CM3 phase1-02 produced no A0 checkpoint; phase103 refused before AppCreate and
round3 is parked. Only a new explicit lead decision may change the candidate.
No explore-format adapter is being built. The fallback remains useful for the
actuator-free FPS workload, whose outputs are discarded.

## Agent-owned readiness

1. Camera input: a2 pre-run LAND, exact receipt
   `docs/evidence/camera-turns-20260927/camera-turns-review-v1-a2.json`
   (5c9da6f0); v1/a1 receipts are stale. Driver/pulse tests: 29 pass. Offline
   alias/uncertainty analysis: 47 owner tests, landed d1c49a4. Native video must
   still establish turn count and validity; no camera map is accepted.
2. Each pulse block requires its own ready-prime inspection/token for fixed
   +0.45 yaw / 120 ms initialization after attach settling. Directional motion
   must be observed or the block stops without retry. **Re-check the bot-free
   pose on the fresh ready-0 frame after the roughly 19-degree initialization**,
   then supply a separate measurement token. Exclude initialization frames,
   reports and video intervals from calibration. Write continue tokens
   atomically from the remote agent side, without PC keypresses.
3. Signed pitch order is +0.5, -0.5, +1, -1. Alternate signs, inspect between
   pulses and avoid clamps; no automatic return pulse exists. Initialization
   and every inspection count against the existing block/sitting deadlines.
4. FPS runner landed 22b53fc, 27 owner tests and exact fallback CPU preparation
   passed. It has no actuator and does not consume execution maps. Commands:
   `docs/lanes/live-fps-20260927.md`. It defaults to CPU preparation; CUDA and
   desktop capture require explicit flags. GPU inference permission is 4f81722.
5. Exact fallback copy/hash check, source domain/regime/vocabulary/support,
   preparation and CUDA timing are pinned in
   `docs/evidence/live-loop-fallback-20260927/RESULT.md`. Offline prediction
   p50/p95 was 25.97/28.99 ms; replay send age 47.15/62.88 ms. Real TRAIN
   prediction p50/p95 was 23.07/26.98 ms. None includes game FPS contention.
6. Before James enters the range, the lead prepares a fresh sitting output,
   native OBS video reference, fresh game PID, current source receipts and
   command sheets. Only the desktop owner executes. No repeat of the touch
   test already passed on 2026-09-26; wall work is outside this sitting.

## James's actions and time

| Clock | James does | Lead/agent does |
|---|---|---|
| 0-4 min | Leave monitor on; enter Practice Range as Spider-Man on the alt; confirm Steam Input disabled, H/V 247/124 and saved hero settings; enable visible FPS counter and start native OBS recording on cue. | Verify settings pixels, normal cooldowns and capture preflight; inspect an open, level, bot-free turn view. Keep aim assist 100 unchanged and record it. |
| 4-16 min | Hands off during each turn. Between blocks, on cue, briefly walk and attack, then restore the marked pose. | Four blocks, each <=180 s, with fresh inspected-frame token before each <=20 s segment: (+.45,-.45,+.1,-.1), (+.2,-.2,+.3,-.3), (+.6,-.6), (+.8,-.8,+1,-1). Keep >=.8 last or alone. Retain failures; no automatic retry. |
| 16-22 min | Perform six slow human-mouse far-landmark edge-to-edge sweeps, three per direction, with established input logger running. Stand still and keep camera level. Then one near-landmark sweep each way for parallax control. | Verify pinned mouse gain/settings. Count logged motion between native edge crossings, propagate endpoint uncertainty. Use far-landmark geometry; reject unstable focal rather than assume 640 px. |
| 22-28 min | Briefly walk/attack and restore pose on cue, then hands off for short-pulse blocks. | After accepted focal, pitch +.5,-.5,+1,-1 at 40/80 ms, three repeats each. Short yaw +.45,-.45,+1,-1 at 33/67 ms, three repeats. Each block has separately inspected initialization and post-init pose; stop at the time cap even with unfinished rows. |
| 28-33 min | Hands off; remain available. | Inspect native turns and report intervals, derive supported signed values and retain unknowns. If camera work is incomplete at minute 33, end the sitting under the approved hard stop. No policy launch occurs in this plan. |
| 33-36 min | Keep marked view and visible FPS overlay unchanged; hands off. | Actuator-free A/B/A: each phase 10 s warmup +30 s measurement, 120 s total. A capture/guards/evidence; B same plus CUDA inference with outputs discarded; A inference off. Same resident model and scene throughout. |
| 36-40 min | Stop OBS when the lead confirms all input is closed. | Confirm closed/neutral state, preserve artifacts and unfinished rows. Annotate retained FPS frames offline and report measured cost after annotation; do not make James wait for it. |

This is a scheduling cap, not a promise of complete calibration. Low signed
magnitudes may not complete three return intervals within 20 seconds; leave
them unknown. Full-turn rates alone do not establish short-pulse response.
Any idle banner, focus/HUD loss, keyboard stop, capture error or deadline ends
the block. Camera-only activity does not reset inactivity: the between-block
human walk/attack is required. Workers never navigate the lobby or queue blind
activity. Unknown deadzone/asymmetry values are not zero or copied old values.

## FPS measurement and later policy boundary

Use exact fallback, compact-bgr preprocessing, two CPU threads and explicit
--device cuda. Keep resolution, graphics, FPS cap, OBS, pose and capture/proof/
evidence workload identical across phases. Capture/proof target is 30 Hz and
retained native PNG evidence 1 Hz throughout; report actual rates. B permits
one in-flight prediction on a fresh frame and discards outputs. The model stays
resident across phases; this measures active-inference cost, not model residency
versus game alone. Native driver calls cannot be force-cancelled by Python.

Manually annotate the visible game FPS counter from retained frames, leaving
unreadable values blank, then run the runner's annotate command. Report counts,
sample rates, per-phase median/p10, A1/A2 drift and cap saturation. Paired loss
is 100 * (mean(A1 median,A2 median) - B median) / mean(A1 median,A2 median).
Counter samples are not frame times or 1% lows. Also retain prediction ages,
CUDA memory, native capture times and dropped evidence. FPS remains unmeasured
until this desktop test and annotation finish; James decides acceptability.

Any later learned policy run still needs an eligible, explicitly selected
checkpoint, accepted execution maps, reviewed input code and deployment
re-freeze including controller, loop, record and pad_bindings. A changed
asymmetric decoder requires its own pre-run review outside this sitting.
The existing CPU-default live CLI/explicit CUDA path remains landed d034ff1,
with receipt review-receipt-v2-a1.json (817fa8f7). The ten matched scripted/
learned pairs are deferred, not executed or counted as failures in this sitting.

## VUH-1384 current-result text for the lead

Inference code and CPU-default/explicit-CUDA CLI are landed and accepted
(7ca7e16, d034ff1). Camera input has a2 pre-run LAND (5c9da6f0), with 29 driver
and 47 offline-analysis tests; the actuator-free FPS runner landed 22b53fc
with 27 tests. Exact legacy fallback 2d5183cb is prepared and CUDA-timed, but
its fixed 120-second admitted TRAIN-native replay was 100% neutral, including
raw camera, versus 437 supported human presses. Evidence is in
`docs/evidence/live-loop-fallback-train-20260927/run/report.json`.
Readiness verdict: camera + FPS only; defer learned/scripted pairs. No A0
checkpoint exists and round3 is parked. Camera maps, live policy outcomes,
game FPS cost and FPS acceptance remain unmeasured. Lead owns booking and
publication; this paragraph is pending publication, not a claim of a Linear write.
