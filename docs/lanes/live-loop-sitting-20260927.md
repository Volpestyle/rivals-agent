# One supervised sitting: camera map, CUDA cost, scripted comparison

Owner live-loop; scheduling/desktop/Linear owner herdr-lead; reviewer binds-review.
VUH-1384. Proposed 2026-09-27; this is a plan, not a run record.

Reserve **55 minutes**, with a **33-minute camera-only stop point**. James stays
present while input runs. Agent preparation below happens before that reservation;
do not ask James to idle in the range while code, models or reviews are pending.
No repeat touch test: the 2026-09-26 sitting already passed it. Wall work is
outside this sitting. GPU inference approval is already recorded in 4f81722.

The lead's latest checkpoint decision selects the **legacy interim94-s012
model_nohud seed 0**, SHA256
`2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`.
CM3 phase-1 `r3p1-A-0-02` produced no checkpoint. A later A-0 replaces this
fallback only on an explicit lead decision and fresh preparation/timing.
Do not silently switch weights mid-comparison. The fallback failed self-fed
decode offline; its new 120-second admitted-TRAIN replay is a pre-booking check.
If it is effectively neutral there, the lead will book camera + FPS only and
wait for another checkpoint. The exploratory H1/encoder adapter is deferred until
the NitroGen no-history confirmation decision. These are exploratory failure
observations, not a declaration of policy competence or promotion.

## Before inviting James: agent-owned readiness

1. Binds-review approved the exact camera driver/pulse bytes; use
   `docs/evidence/camera-turns-20260927/camera-turns-review-v1-a1.json`
   (3c438067). The old v1 receipt is stale. Offline alias/uncertainty fixes have
   47 owner tests; native video still establishes turn count and validity.
   The CPU-default, explicit-CUDA CLI is landed at d034ff1, with a1 receipt
   `docs/evidence/live-loop-profile-20260927/cli-review/review-receipt-v2-a1.json`.
   Driver packet: `docs/evidence/camera-turns-20260927/HANDBACK.md`.
2. The fallback is copied/hash-checked and its own domain, vocabulary, normal
   regime and train support are pinned. Prepare-only CUDA passed; its measured
   full prediction p50/p95 is 25.97/28.99 ms and replay send age 47.15/62.88 ms.
   `docs/evidence/live-loop-fallback-20260927/RESULT.md` holds the scope and
   explicit camera-disabled offline preparation. Complete the real TRAIN replay
   check before booking; fixture replay alone cannot decide gameplay usefulness.
3. Prepare a new sitting directory, native OBS video reference, visible game
   FPS counter, fresh game PID, desktop capture preflight, reviewed deployment
   receipt and command sheets. Only the lead operates the desktop. Predeclare
   ten matched scenario pairs: four near, three mid, three far, with the same
   target type, pose/readiness and normal cooldowns within each pair. Alternate
   learned-first/scripted-first order. Freeze the scripted brain revision and
   controller settings; prepare the existing benchmark manifest/audit fields.
4. Signed pulses are implemented in the reviewed driver's `--pulse-axis` mode,
   reusing l4 pulse/motion guards with per-sign report intervals. Use
   `--deflections .5 -.5 1 -1` for pitch: **alternate signs**, inspect between
   pulses and stay away from clamps; no automatic return pulse exists.
   Capture-only A/B/A is landed at 22b53fc, 27 owner tests and real fallback
   CPU preparation pass. Command sheet: `docs/lanes/live-fps-20260927.md`.
   It has no actuator and does not consume execution maps, so its preparation
   does not depend on the map being measured during this sitting.
5. Bind the exact runtime/dependency hashes to the deployment. The post-map
   re-freeze must include controller, loop, record and pad_bindings and changed
   live dependencies. If the accepted map needs a new asymmetric decoder,
   complete that code and review outside the sitting; do not rush it into the
   five-minute review slot below.

## James's actions and booked time

| Clock | James does | Lead/agent does |
|---|---|---|
| 0–4 min | Turn on/leave on the monitor; enter Practice Range as Spider-Man on the alt; confirm Steam Input disabled, H/V 247/124 and the saved per-hero settings; enable the game's visible FPS counter and start native OBS recording when prompted. | Verify settings pixels, normal cooldowns and the already-passed bindings; capture preflight; inspect an open, level, bot-free view for the whole turn. Keep aim assist 100 unchanged and record it. |
| 4–16 min | Leave controls alone while each approved turn runs. Between the four blocks, on the lead's cue, briefly walk and attack, then restore the marked pose. Do not move during a segment. | Four blocks, each <=180 s, with a fresh inspected-frame token before every <=20 s segment. Suggested groups: (+.45,-.45,+.1,-.1), (+.2,-.2,+.3,-.3), (+.6,-.6), (+.8,-.8,+1,-1). Keep >=.8 last or alone. Retain failed and incomplete segments; no automatic retry. Maximum commanded yaw is 280 s. |
| 16–22 min | On cue, perform six slow **human-mouse** edge-to-edge sweeps of the selected far landmark, three each direction, with the established input logger running. Keep the hero still and camera level. Then perform one sweep each way of the near landmark as a parallax control. | Verify the established mouse gain and unchanged sensitivity from its receipt; count logged motion between native edge crossings, not ruler distance or estimated hand speed. Use the focal review's far-landmark method. A pad sweep is an alternative only if its independently accepted yaw rate and timing precision pass the new offline focal checks. Accept 640 px only if far FOV is 90° ±1°; otherwise require a consistent measured value. |
| 22–28 min | Briefly walk/attack and restore the pose on cue, then keep hands off for the guarded short-pulse blocks. | With accepted focal, run pitch in alternating order +.5,-.5,+1,-1 at 40 ms, then the same at 80 ms; repeat each block three times, inspecting between pulses and staying away from clamps. Check sign, drift, duration and <=10 ms release overrun. Short yaw uses +.45,-.45,+1,-1 at 33/67 ms, three repeats each. Keep unknown low-end/deadzone values unknown; no guessed zero or copied old map. |
| 28–33 min | Hands off; remain available. | Inspect raw video/report evidence, derive the supported executor map, obtain required acceptance, verify symmetry assumptions and re-freeze. **If a complete supported map, review or re-freeze is missing at minute 33, end the sitting here.** Retain the partial result; no policy launch. |
| 33–36 min | Keep the marked range view and FPS overlay unchanged. After the FPS sequence, say whether the measured impact is acceptable for proceeding. | Capture-only A/B/A: 10 s warmup + 30 s measurement per phase (120 s total), plus setup/readout. A: capture/guards/evidence, no inference; B: same plus explicit CUDA predictor, discard outputs; final A: inference off again. No pad in this sequence. |
| 36–51 min | For each pair, restore the lead's designated near/mid/far pose and full-health target incarnation; release controls during each 20 s episode. Follow the lead's reset cue between episodes. Press a keyboard key immediately if a run should stop. | Ten learned and ten scripted allocations, alternating order. Total episode budget 6m40s; the remaining 8m20s covers readiness, native board/target evidence and resets. If resets take longer, end at minute 51 and retain unexecuted/refused slots in the planned denominator. Do not compress proof or extend the reservation. |
| 51–55 min | Stop OBS when the lead confirms all input is closed. | Verify neutral/closed state, preserve artifacts, note unfinished slots and give James the measured FPS change and observed failures. Offline annotation/review follows without requiring James to remain. |

The 55 minutes is a scheduling cap, not a promise that a map will converge or
that all twenty episodes will execute. Camera-only activity does not reset
inactivity. Keep blocks below three minutes, and inspect a new pose after each
human activity refresh or pad attach. Any idle warning, HUD/focus loss, keyboard
stop, capture failure or deadline refusal ends that block immediately. Workers
never navigate the lobby or queue blind movement to keep the client alive.

Full-turn rates alone do not establish the 33 ms executor response. The reviewed
l4 pulse helper caps pulses at 80 ms; the earlier lane proposal's 100 ms check
is not an available reviewed command and is excluded here. The 33/67 ms wrapper
is covered by the a1 receipt above. Low signed
deflections may not complete three steady return intervals in 20 seconds. Those
rows remain unknown; infer no deadzone from a refusal. An incomplete map may
require another sitting, which the lead decides from this evidence.

## Measurement and comparison contract

The capture-only FPS test uses the exact checkpoint, compact-bgr preprocessing,
two CPU threads and explicit `--device cuda` intended for the policy run.
CPU remains the CLI default. Keep resolution, graphics, FPS cap, OBS settings,
capture/proof/evidence workload and pose identical across A/B/A; log actual
capture and inference cadence. Start a prediction only on a newly captured
frame; one inference at a time, outputs discarded. Keep the GPU model allocated
across the phases to isolate active inference; report resident GPU memory
separately, and label the result as active-inference cost. A game-only reference
would be a different comparison. Restart/abandon if another workload changes.

Read timestamped samples of the game's visible FPS counter, manually audited
if OCR is uncertain. Report each phase's sample count/rate, median and p10;
paired loss = 100 × (mean(A1 median,A2 median) − B median) /
mean(A1 median,A2 median). Report A1/A2 drift and cap saturation: a capped counter
can bound visible FPS loss but cannot show unused rendering headroom. Counter
samples are not frame times or 1% lows. Also report native capture duration,
full preprocessing/encoder/head prediction age p50/p95/p99, CUDA memory and
dropped evidence. FPS cost remains **unmeasured** until this desktop test runs.

Launch the learned CLI with the pinned checkpoint/support/settings/receipt,
`--duration 20 --device cuda --preprocessor compact-bgr --cpu-threads 2`, fixed
decoder and the unchanged 250 ms age cap and 33 ms action leases. No camera-
disabled substitute for missing calibration. The matched scripted baseline
uses the existing `agent.loop` scripted brain, bounded `--max-s 20`, normal
cooldowns and the same accepted camera/controller deployment. Its normal
startup/pose procedure must be retained and timed outside the verified ready
boundary; model preparation/settling is also excluded and reported.

Score designated-bot completion/time only from audited target/incarnation and
reset evidence. Retain all scheduled failures/unknowns, actual command versus
visually observed casts, duty/neutral gaps, prediction ages, FPS samples,
camera behavior, stalls/falls, human interventions/reset seconds and stop
reason. Feed appearances alone are not exact KO counts. Preserve native video,
source/checkpoint/deployment hashes and excluded intervals. Apply the existing
ten-trial >=8/10 completion and zero-scope-breach gate only if evidence supports
it; this small sample cannot establish expert parity.

## VUH-1384 current-result text for the lead

CPU/CUDA inference code is landed and independently accepted (7ca7e16); the
CPU-default, explicit-CUDA live CLI and device-count skip fix are landed at
d034ff1 with pre-run a1 receipt 817fa8f7. Trained-model offline timings remain
in `docs/evidence/live-loop-profile-20260927/RESULT.md`; they include real
preprocessing/encoder/head costs, not capture or game FPS. The multi-deflection
yaw driver and signed-pulse wrapper are accepted for input under a1 receipt 3c438067 in
`docs/evidence/camera-turns-20260927/`; signed pulses and full-rate capture have
26 passing offline tests, and the separate offline analysis has 47 owner tests.
No camera calibration, live policy result, GPU FPS cost or acceptance is claimed.
The actuator-free FPS tool is landed at 22b53fc with 27 owner tests. The named
legacy fallback is copied, prepared and CUDA-timed; A-0 produced no checkpoint.
Next: finish the 120-second admitted-TRAIN replay usefulness check, then the
lead books camera + FPS, adding scripted/learned comparison only if justified.
Alt policy input remains behind accepted maps and re-freeze. H1/explore-format
adaptation is deferred by the lead's checkpoint decision.
