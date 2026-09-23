# Review: end-to-end fit design (VUH-1359, VUH-1346)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main` `9f01247` plus the
uncommitted `docs/lanes/end-to-end-fit.md`.

- **Read:**
  - `AGENTS.md`, `docs/recording-protocol.md` and `docs/recording-log.md`;
  - `docs/learning-plan.md` (lines 1-320 and "First acceptance");
  - `docs/human-demo-schema.md` and `agent/human_demos.py`;
  - the design, `fit-design-final.md` and `review-whole-session-design.md`;
  - `docs/plan.md` (scope boundary, L0 gate) and `.agents/skills/rivals-live-game/SKILL.md`;
  - `agent/controller.py` (`Live`), `perception/hud.py` (regions) and `docs/spiderman-kit.md`.
- **Measured:** the logger `inputs.jsonl` of 032454, 033319, 051828 and 171533, on the design's own 30 Hz step.
  - The scripts and their output are next to this file: `fit-review-stepstats.py`, `fit-review-extra.py` and
    `fit-review-stepstats.json`.
  - Both scripts are stdlib only and take about 20 s each.
- **Not done:**
  - No repo edits, commits, Linear writes, Mac jobs or game input.
  - No video was decoded.
  - **053616:** none of its files were opened. One directory listing of `RivalsInput\` showed its file names and sizes,
    nothing more.
- **Seen in passing:** an uncommitted `policy/range_bc/` (files dated 14:29-14:34 today) already implements parts of
  this design. I did not review it. I cite it only where it shows that a finding is already in code.

## Verdict

**Offline fit (§0-§3, §5, §6): APPROVE WITH REQUIRED CHANGES.**

- **What is right:** the skeleton. A fixed vocabulary, a classification mouse head, a history-only twin, pre-registered
  seeds and floors, and a test opened once.
- **What must change:**
  - the headline metric can be maxed by a policy that carries no information (F2);
  - evaluation never runs the model the way it will run live (F3);
  - one half of G3 is passed by persistence (F4);
  - the primary arm cannot see or remember the resources the protocol says the decisions depend on (F5);
  - the split rules do not add up with 20-30 minute sessions (F6).

**Live path (§4): REJECT AS WRITTEN.**

- It treats SendInput acceptance as "one supervised look" before a pilot.
- The project closed the injected-mouse-button path at L0 (F1), and LMB and RMB are two of the three controls that G2
  requires one by one.
- Reopening L0 is the lead's and James's decision under the scope boundary. A lane cannot clear it as a pilot
  precondition.

## Ranked findings

### F1 (blocking for §4): the KBM executor rests on an input path the project closed at L0

**Evidence.**
- **L0 result.** `docs/plan.md:142`: injected mouse buttons (`mouse_event`, 120 ms hold, game focused, same integrity
  level) were ignored: "three clicks on two screens did nothing".
- **The ruling.** `:147-148`: "The game drops software-injected mouse clicks. Under boundary item 4 the mouse path is
  closed; nobody works around it."
- **Keyboard.** `.agents/skills/rivals-live-game/SKILL.md:19-20`:
  - Injected keyboard was accepted in menus, but "`h` did not open the hero picker".
  - Injected mouse clicks are ignored: "That path is closed; do not work around it."
- **What the design asks.** It never cites L0. Its unverified fact 7(a) (`end-to-end-fit.md:309`) asks only about
  "SendInput keys and relative mouse movement". It does not ask about the buttons that were already rejected.
- **Same path.** `mouse_event` is superseded by `SendInput`, and both inject through the same system path (the OS
  flags both as injected). A SendInput button test is a retest of the closed path.

**Consequence.**
- The executor could not fire Spider-Power (LMB) or Web Cluster (RMB). Those are 921 of the 3,767 vocabulary presses
  measured (24%), and two of the three controls G2 names individually.
- Injected keys have no positive result in gameplay, and one negative.
- Injected relative motion was never tested in game.
- **As the repo stands, no offline number can lead to a KBM pilot.** The design's "worth a live pilot" number has no
  pilot behind it.

**Required.**
- §4 states the L0 facts, and becomes conditional on an explicit decision by the lead and James to retest L0 with
  SendInput keys, buttons and relative motion in the range.
- The retest follows plan item 4: one plain, documented test. A rejection closes KBM output for good.
- §4 states what the fit is for if L0 stays closed. It becomes a study of representation, scaling and data sufficiency,
  and any live use then needs a pad-domain executor. That is out of scope here, and "a later measured experiment" in
  `learning-plan.md:241-244`.
- One line saying that hardware HID emulators, driver-level injectors, or anything that makes injected input look
  physical are out of scope (plan scope item 2, `plan.md:17-20`). Nobody should "fix" L0 that way.
- The lead settles this before a pilot is used to justify the data campaign.

### F2 (serious): echoing the teacher-forced previous action maxes the headline metric

**Evidence.**
- **The input.** It is the *true* step k−1 action (design §1; `policy/range_bc/steps.py:329-330`; the baselines read
  `record["prev"]`, `baselines.py:16-21`).
- **The metric.** Edges are scored at ±1 step with symmetric one-to-one matching (design `:241`;
  `policy/range_bc/metrics.py:18-24`).
- **The echo policy.** It predicts a press at k+1 whenever its input shows a true press at k. Every such prediction
  matches its true press within +1.
- **Measured, macro press-F1 (±1) over {LMB, RMB, E, F, Shift, Space}:** **1.000, 1.000, 1.000, 0.993** on the four
  sessions.
- **The same echo at exact step:** **0.000** (RMB 0.042 in 171533).

| Gate | Echo policy |
|---|---|
| Headline and G2 | ≈ 1.0 |
| G5 | Passes exactly: its press rate *is* the human rate |
| G4, balanced-accuracy half | Passes |
| G3 | Fails |
| G4, change-F1 half | Fails |

**Why it matters, even though exact-step BCE will not teach a network to echo.**
- A gate should not rely on the loss being unable to exploit a leak.
- Any late-by-one prediction gets full credit only because the answer is already in the input.
- The design's "number that says worth a live pilot" (`:263`) is maximised by a policy that carries no information.

**Required.**
- **Tolerance.** Under teacher forcing, a prediction at step j matches a true edge at t only if j ∈ {t−1, t}: early or
  on time, never after the edge is visible in the input.
- **Echo baseline.** Add the echo policy as a named sanity baseline. It must score near 0 on the headline.
- **Headline.** Compute it self-fed (F3). There, ±1 is safe.

### F3 (serious): evaluation never runs the model the way it runs live

**Evidence.**
- **Evaluation mode.** The design never states it.
  - The twin text says "zeros in training and evaluation", and the code pairs each record with the true `prev`.
  - Both point to teacher-forced windows.
- **Live.** The previous action is the model's own, and the LSTM runs from run start for minutes (`:93-94`). Training
  sees only 96-step windows.
- **What teacher forcing hides.** It hides the failures that previous-action input risks: copycat lock-in, press spam
  and stuck keys.
  - G4 and G5, computed teacher-forced, cannot fail for those reasons.
  - Held-key persistence is handed to the model: persistence alone already scores W/A/S/D/Shift balanced accuracy
    0.89-0.98, because held state changes on only 0.5-3.3% of steps (measured).

**Required.**
- **Self-fed evaluation.**
  - It runs over whole validation runs from the run start.
  - The model's own decoded previous action is the input; the recorded frames are unchanged.
- **Where each gate runs.**
  - G4, G5 and the headline are computed self-fed.
  - G1 stays teacher-forced, with F2's tolerance, because it asks whether frames add information beyond the true
    history.
- **Stuck-control checks.**
  - The longest predicted continuous hold per control is at most the longest human hold in train.
  - Predicted mouse drift (mean signed dx over 10 s) stays within the human range.
- **Live previous action.** Define it as what was actually sent, including lease and kill releases, not what was
  predicted.

### F4 (serious): persistence passes G3's sign test; the informative steps are onsets

**The sign half.**
- On steps with |true| ≥ 20, persistence's sign agreement is **dx 0.954-0.975 and dy 0.975-0.990**. The gate asks for
  0.70 (`:258`).
- The informative steps are onsets and reversals: |true| ≥ 20 with the previous step under 5 counts or of opposite
  sign.
  - They are 4.9% of such dx steps (745 of 15,312).
  - Persistence scores **0.23-0.35 (dx) and 0.35-0.56 (dy)** on them.

**The MAE half.**
- A two-coefficient AR(2) extrapolator reaches **0.887-0.937** of the best trivial baseline. It is fitted
  leave-one-session-out: dx_k ≈ 1.35-1.40·dx_{k−1} − 0.40-0.45·dx_{k−2}.
- So 0.8× is not trivial. But a teacher-forced LSTM that sees the true mouse history may reach it without frames, and
  it is really G1's 10% mouse margin that carries G3.

**Required.**
- Replace the 0.70 floor with sign agreement on onset and reversal steps.
- Report it against persistence, AR(2) and the history-only twin, and require a G1-style margin over the twin.
- Add AR(2) as a named mouse baseline. It needs no training.

### F5 (serious): resource state is invisible at 256x144 and cannot be learned from history in 3.2 s windows

**HUD glyph sizes** (`perception/hud.py:184-191`, at 2560 wide):

| Glyph | Native size | At 1/10 (256x144) | Legible? |
|---|---|---|---|
| Ammo count | ~20x32 px | 2x3 px | No |
| Charge badge digit | ~12x18 px | 1x2 px | No |
| Cooldown countdown | 36-52 px tall | 4-5 px tall | No |
| Ability icon box | 62 px tall (`hud.py:56`) | ~6 px tall | Colour only |

- The icon's red-versus-white "cooling" colour (`hud.py:104-110`) plausibly survives as a colour patch.
- So "is E ready" may be visible; "how many webs or charges" is not.

**Timescales** (`docs/spiderman-kit.md:78-84`):

| Resource | Timescale |
|---|---|
| Web Cluster | 5 ammo, 2 s per charge |
| Get Over Here! | 8 s |
| Amazing Combo | 2 charges, 6 s each |
| Web-Swing | 3 charges, 6 s each |
| Tracer | 3 s |

**Memory.**
- Training windows are 96 steps with 32 of burn-in (`:93-94`), so the gradient never spans more than 3.2 s.
- The LSTM cannot learn to count an 8 s cooldown from its own presses.

**Why it matters.**
- The protocol says normal-cooldown play is "where the decisions live (two webs left, wait for uppercut or commit)"
  (`recording-protocol.md:33-34`).
- The primary arm cannot represent those decisions.
- Arm C's reader outputs would bring back the reader failures that the design rightly keeps out.

**Required.** This is cheap and stays end-to-end.
- **A third pixel stream in the primary arm** (or pre-registered as arm A2 under the same gates), made of native HUD
  crops downscaled 2-3x:
  - the ability row, x ≈ 0.735-0.972 and y ≈ 0.845-0.95 of the frame (`hud.py:55-58`);
  - the M&K webs box (`hud.py:101`).

  At 1/3 the countdown is 12-17 px tall and the ammo digit 7x11. That is about 10k extra pixels, roughly +20% encoder
  cost.
- **Stratification.** Report metrics per resource state, using R12 reads for stratification only.
- **Honesty.** §1 says plainly what the primary arm cannot learn.

### F6 (serious): the split rules do not fit 20-30 minute recordings or sitting-level groups

**The arithmetic.**
- R10 asks for 70/15/15 by minutes, with ≥ 2 session groups each for validation and test (`fit-design-final.md:121-125`,
  `end-to-end-fit.md:221`).
- Protocol recordings are 20-30 min (`recording-protocol.md:22`).
- Two groups each for validation and test is 4 recordings, or 80-120 of 180 min held out. **Train is then 33-56%,
  not 70%.**

**Group unit.**
- The schema groups "all recordings from the same play session" (`human-demo-schema.md:102-105`).
- If a group is a sitting ("two hours on to one hour off", `recording-protocol.md:36-37`), 3 h may be only two or three
  groups, and the rule cannot be met at all.
- The intake review already notes that 053616 shares an evening and an OBS process with 051828.

**The plumbing fit.** At about 1 h (2-3 recordings), one recording is validation. The nested "15, 30, 45 min and the
full hour" (`:374-375`) cannot include an hour of train.

**Required.**
- The lead fixes the group unit now: recording or sitting. The campaign plan follows from that choice. For example:
  - ask James for dedicated 10-15 minute validation and test takes on separate days; or
  - accept one group each at 3 h, and say so.
- Restate the plumbing curve in actual train minutes.

### F7 (moderate): "no selection" is honest about validation, blind to overfitting, and the plumbing fit spends validation anyway

**Overfitting.**
- 20 epochs over 50%-overlap windows (`:168-176`) is about 40 passes per frame.
- At 30 Hz, neighbouring frames are near-duplicates, so the effective sample size is far below 227k.
- AdamW weight decay of 1e-4 is close to none, and there is no spatial augmentation.
- Overfitting by epoch 20 is the likely outcome, and nothing in the design would show it.

**Validation spent early.**
- The plumbing fit computes the gates and a scaling curve "against the same validation group" (`:366`, `:374-375`).
- Its result may change "the model or observation" (`:384-385`).
- If that group is also real-fit validation, validation has been used to select the design before the real fit.

**Required.**
- **Dev split.** Carve a dev split out of the train session groups (or leave one train group out) for per-epoch curves.
- **Pre-registration.** Take the real fit's epoch count and weight decay from the plumbing fit's dev curve, not from
  validation.
- **Plumbing reporting.** The plumbing fit reports on dev only. Real-fit validation groups are first read at the real
  fit.
- **Real-fit logs.** The real fit logs per-epoch train and dev loss, reported and not used for selection.
- **Augmentation.** Consider a DrQ-style random shift of ±4 px on the global stream only. Not on the crosshair crop,
  where the offset *is* the aim signal.

### F8 (moderate): the budget is an unmeasured, probably optimistic estimate, and it leaves out the twins

**Throughput.**
- My arithmetic for the §2 encoders:

  | Stream | Forward per frame |
  |---|---|
  | 256x144 global | ≈ 0.54 GFLOP |
  | Crop | ≈ 0.24 GFLOP |
  | Total, forward plus backward | ≈ 2.3 GFLOP |

- The design's 3-6k frames/s therefore means 7-14 TFLOP/s sustained.
  - That is on 16- and 32-channel convolutions, on MPS, under `use_deterministic_algorithms`.
  - Small-channel convolutions rarely get near that.
- Expect a 2-5x shortfall until measured: roughly 2-7 h per seed, not 1-1.5 h. The 192x108 fallback then becomes the
  likely path.

**Missing runs.** The 5 h cap covers "all seeds" (`:191`), but it leaves out:
- **Real fit:**
  - G1's history-only twin on three seeds;
  - the reported frames-only twin;
  - arms B and C.
- **Plumbing fit:**
  - a rerun of seed 0;
  - the lag pair;
  - four nested sizes, plus their twins if G1 is computed.

**Required.**
- **A budget table** that lists every fit.
- **A cheap twin.** Implement the history-only twin without running the encoders: a learned constant replaces the
  frame features, so it takes minutes, not hours.
- **Early measurement.** Measure throughput in the smoke fit, or with the `bench` module on synthetic frames, which needs
  no data.

### F9 (moderate, applies only if L0 is reopened): the KBM executor falls short of the pad's guard in six ways

The pad contract (`agent/controller.py:40-61`, `:123-132`) is sound where it applies: a whitelist, proof at commit, a
250 ms lease on the real clock, and neutral on every exit. The design rightly adds a separate watchdog, because a
crashed injector leaves keys down, while a closed ViGEm pad unplugs. The gaps:

1. **Focus race.**
   - Pad input to another window is "silently eaten" (`SKILL.md:32-33`).
   - KBM input goes to the foreground window and *acts* there: LMB plus relative motion outside the game is a click
     wherever the cursor lands.
   - Required: check that the foreground window is the game's HWND immediately before every SendInput batch, and
     confine the cursor (ClipCursor). A failed check means release and stop.
   - "Losing focus means stop" (`:297`) must be this per-send check, not an event handler.
2. **The kill switch can be tripped falsely, or fail silently.**
   - **Zero-effect packets.** 032454 has a second mouse handle whose packet had zero motion, buttons and wheel
     (`human-demo-schema.md:405-410`). "Any event whose device handle is a real device" (`:293-294`) would stop such a
     run at once, or turn into ad-hoc filtering. Use the importer's `_control_affecting` definition
     (`agent/human_demos.py:350-359`) with handle ≠ 0.
   - **Background registration.** A background listener needs `RIDEV_INPUTSINK`, or it hears nothing while the game has
     focus. A guard that fails silently is the worst kind, so every run needs a positive pre-run test: a physical touch
     stops a dry run.
   - **Hangs.** Run the physical-input listener in the separate watchdog process as well. A hung executor has a hung
     kill switch.
3. **The watchdog contract.**
   - The send path writes the heartbeat after each proven send, not a timer thread that outlives a hung loop.
   - The executor refuses to start, and stops, without an acknowledged live watchdog.
   - Key-ups check SendInput's return value and retry, because injection is blocked on the secure desktop (lock screen,
     UAC).
4. **The HUD proof must prove gameplay, not the banner.** The intake review left open whether a menu keeps the "PRACTICE
   RANGE" banner. Reuse `record.in_range`, which is false under the scoreboard (`SKILL.md:121`).
5. **Maximum duration** needs a number, pre-registered.
6. **Pad→KBM handoff, 7(c).**
   - The HUD layout differs between pad and M&K: the webs box is mirrored and the charge badge inverted
     (`hud.py:73-76`, `:97-101`). Every training frame is M&K.
   - After pad placement, the first KBM frames show a layout the model never saw. The game switches layout only on the
     first KBM input.
   - Required: confirm the M&K layout on a fresh frame before any model output is sent. One whitelisted non-model tap
     can trigger the switch.

### F10 (moderate): no check that training and live frames match

**The gap.**
- Training frames are NVENC video decoded by ffmpeg to `rgb24` (`policy/range_bc/cache.py:109`). Live frames are dxcam
  BGRA.
- Colour range and matrix, chroma subsampling and encoder smoothing all differ.
- I found no parity measurement in `docs/`.
- Earlier learned heads read HUD values, not raw pixels, so this is the first pixels-in policy to meet the gap.

**Required before any pilot.**
- Capture one static range scene both ways.
- Put both through the cache's exact filter graph and report the per-channel mean and maximum difference.
- If they differ by more than the ±10% jitter covers, fix the decode to match live.

### F11 (minor): the counts and statistics in §0 and §6 are off

**Key counts.**
- The "Key downs" in the measured-usage table (`:48-55`) include typematic repeats.
- True presses (down edges while not held):

  | Session | Shift presses (raw downs) |
  |---|---|
  | 051828 | **83** (472) |
  | 033319 | 189 (585) |
  | 171533 | 25 (131) |

- W, A, S and D are inflated too: D is 45 against 151 in 171533. E, F, Space, C and the mouse buttons are unaffected.
- §6's "Shift 8,000" at 3 h is about 1,500 true presses. That changes Shift's `pos_weight` and the G5 rate reference.

**Mouse statistics.** The table is at 20 ms, but the step is 33.3 ms. At 33.3 ms:
- non-zero |dx| has p50 20-40, p90 138-224, p99 431-641 and max 1,384;
- |dx| ≥ 1000 occurs on 0-0.11% of steps;
- |dy| never exceeds 362;
- 16-35% of steps have zero dx.

**032454's length.** The video itself is about 30 s: 3,609 decoded frames at 120 fps (`human-demo-schema.md:399-400`).
The recording log's "~4 min video" is wrong too.

### F12 (minor): the lag grid, and the "strictly causal" wording

- **Lag grid.** The only live latency measured so far is acquisition-to-consumption 71 ms (`learning-plan.md:90-91`),
  about 2 steps.
  - Add lag 2.
  - Or measure the KBM tick latency offline on recorded frames before the plumbing fit.
- **Wording.** With lag ≥ 1, the previous-action input is the bin *after* the frame (`steps.py:329`).
  - That is correct live, because it is the agent's own committed action.
  - But §1's "strictly causal" should read "causal with respect to the agent's committed actions".

### F13 (minor): R2 has no per-control held-known bit

- After a focus snapshot, held keys stay unknown until they are resolved (`human-demo-schema.md:42-53`).
- The design's `known` mask covers only the previous action and the mouse motion (`:90`, `:164`).
- R2 should carry `held_known` per control, and the held and release losses should be masked on it.

### F14 (minor): the scaling curve needs its own design to be informative

**Confounds.**
- Fixed 20 epochs confound data with optimiser steps: a 15 min subset gets a third of the updates of a 45 min one.
- One seed per point is mostly noise.

**Required.**
- Use a fixed number of optimiser steps, or dev-selected epochs per point (F7).
- Run ≥ 2 seeds per point.
- Plot per-head validation NLL (continuous and less noisy) and the frames-minus-twin gap (with F2's correction), not
  only thresholded F1.

**Pre-registered reading.**

| Rule | Condition | Meaning and action |
|---|---|---|
| (a) | The frames-minus-twin gap is not positive and rising from half to full plumbing train | More minutes will not make the policy use its eyes. Change the observation or encoder first (F5, or a frozen pretrained-encoder arm) |
| (b) | Dev NLL falls roughly linearly in log(minutes) | Extrapolate to the real train minutes. If the projection does not clear the G2/G3 floors with margin, 3 h is not enough. State the implied minutes rather than recording blindly toward 5 h |
| (c) | Train NLL falls while dev NLL rises within the plumbing fit | The model is memorising. Fix regularisation before adding data |

## The six questions, settled

1. **Observation and action.**
   - **30 Hz** is defensible for actions: there are 0 multi-edge steps, and only 2 taps completing inside one step, in
     3,767 presses.
   - **The 31-class head** fits the measured 33 ms distribution:
     - every dx class from ±1 to ±13 holds at least 183 steps;
     - ±14 and ±15 are sparse (2-93 steps);
     - dy uses classes beyond ±11 on only 5 steps;
     - persistence passed through the codec is only 0-6% worse in MAE than raw persistence.
   - **Decoding.** Define "median class centre". It should be the median of the predicted distribution (MAE-optimal),
     not the centre of the argmax class.
   - **Frame streams.** Global plus crop is right for movement and aim. It loses every HUD number (F5), and those are
     what the protocol's cooldown decisions need.
2. **Model and budget.**
   - The parameter count checks out: about 4.2-4.4M by my arithmetic.
   - The compute estimate is unmeasured, probably 2-5x optimistic, and leaves out the twins (F8).
   - Twenty fixed epochs with no dev split cannot see overfitting (F7). "No selection" is honest only if the plumbing
     fit stays off the validation groups.
3. **Gates.**
   - Echo maxes the headline and G2, and passes G5 and half of G4 (F2).
   - Persistence passes G3's sign test (F4).
   - Always-hold-W and plain persistence fail G2.
   - The history-only twin is the right key baseline. Add echo, AR(2) for the mouse, and a rate-matched chance level
     (about 3x the per-step press rate at ±1, so an F1 of about 1.4% for E).
   - The number that should justify a pilot is not raw F1. It is the F2-corrected G1 margin with a block-bootstrap
     95% CI (30 s blocks) whose lower bound is above 0, on seed 0 and on the mean. It comes together with the design's
     floors computed the corrected way, and F3's self-fed checks.
   - **With L0 as it is, no number justifies a KBM pilot (F1).**
4. **Live executor.**
   - It rests on a closed path (F1).
   - If that path is reopened, the gaps are listed in F9 (focus race, kill-switch definition and liveness, watchdog
     contract, gameplay-HUD proof, maximum duration, pad→KBM HUD layout) and F10 (pixel parity).
   - Nothing in the sketch sends Esc, and the whitelist-by-construction is right.
5. **Data sufficiency.**
   - The 1 h curve, as specified, is not informative (F14), and the split arithmetic must be fixed first (F6).
   - Rules (a) and (b) in F14 are what would say that 3 h is not enough.
6. **Learning-plan items.**
   - **Present:** the held-input persistence baseline, fitting-set statistics, the per-control breakdown,
     unsupported-control counts, and the sealed test opened once.
   - **Missing:**
     - step 5, "inspect transfer failures before connecting learned execution to the existing guarded loop"
       (`learning-plan.md:241-242`). Add a qualitative review of self-fed predictions over validation clips;
     - the unsupported share of human edges, stated as a ceiling. C, Alt and X1/X2 are 2.2% of 051828's edges;
     - the fit driver checking intake's sealed denylist (intake review R4) before it reads any registry.

## What is sound

- **The vocabulary comes from the bindings, not from the labels** (`:139-147`).
  - Unsupported controls are never predicted or emitted, and their steps stay in training for the supported targets.
  - This avoids both a false "nothing happens here" and an Esc-pressing policy.
- **The mouse is a classification head.** The heavy tail justifies it, and the 33 ms measurements above support the bin
  edges.
- **The history-only twin is gate G1.** It asks the right question ("does it see?"), and the design says a G1 failure is
  a finding, not a pilot.
- **The floors are pre-registered.** Seed 0 is declared as the candidate, three seeds must pass, and the test is opened
  once with nothing tuned afterwards.
- **The design is honest about MPS determinism.** It gives a measured fallback instead of promising a byte-identical
  checkpoint.
- **The R2 step table is right.** `samples()` materialises `past` per sample (`agent/human_demos.py:589`), so a
  per-anchor table is the right fix at 324k anchors.
- **R11 and the 032454 correction.** Minutes are counted from focused logged input.
- **It sees how KBM differs from the pad on a crash:** keys stay down. It releases the full vocabulary on every path and
  has no Esc path at all.
- **Scenario tags never enter the observations,** and the perception State stays out of the primary arm, so reader
  failures cannot confound the result.

## Measurement method

- **Sessions.** `inputs.jsonl` of 032454, 033319, 051828 and 171533, read-only. The script's session list asserts that
  053616 is not among them.
- **Steps.**
  - Each focused interval (a focus-active event to the next focus or pause event) is tiled from its start on the
    design's 33,333,333 ns grid, with bins (a, a+step].
  - That gives 30,702 steps, about 17.1 min.
  - No suitability cuts are applied: 033319's cut segments and any Esc spans are included. So these numbers describe
    distributions, not admitted rows.
- **Press.** A down edge of a vocabulary scan code (flags & 6 = 0) or a mouse button while it is not already held.
  Typematic repeats are not presses.
- **Echo.** A predicted press at k+1 for each true press at k within one run, matched one-to-one within the tolerance.
- **AR(2).** Coefficients chosen by grid search to minimise MAE on the other three sessions, then tested on the held-out
  one.
- **Class codec.** The design's values are taken as lower bin edges, and each class decodes to its pooled class median.
