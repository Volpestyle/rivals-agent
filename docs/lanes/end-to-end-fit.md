# End-to-end range fit: frames and executed-action history in, semantic Spider-Man actions and camera degrees out (VUH-1359, VUH-1346)

**Status (2026-09-23):**
- The design is revised after the independent review (`review-fit-design.md` in the lead's handoff folder) and the
  lead's decisions F1-F8.
- The code is in `policy/range_bc/`, uncommitted, and tested on Windows CPU and Mac CPU.
- There is one synthetic bench on the Mac (MPS). The throughput and determinism numbers in §2 come from it.
- The second code review (`review-fit-code.md`), the lead's decisions K1-K9, the Team-Up correction, the pitch and
  pad-setting decisions and the HUD parity result are folded in: see "Review round 2" and "Pilot pre-registration" at
  the end.
- Round 3 (`review-fit-code-2.md`), the calibration take's facts, the vocabulary decisions (`team_up`,
  `goh_targeting`, Mouse 5 on melee) and the Mac cache rehearsal are folded in: see "Round 3" at the end. **Where the
  sections above disagree with "Round 3", "Round 3" wins.**
- There has been no fit, no session data and no game input.

**Goal.** The design lets whole-session intake (`docs/lanes/human-admission.md`) produce what the first fit needs. It
fixes the pass/fail rule before anyone sees a validation number.

**James's direction** (`docs/recording-protocol.md`): about 3-5 h of logged practice-range play, then one causal
policy trained on all of it, taking frames plus input history.

**Ownership.** This lane owns the fit, its gates and the contract the live executor must meet. Intake owns the rows,
and the executor's live wiring belongs to the loop.

**The action space changed after the review.**
- The policy outputs **semantic Spider-Man actions**, mapped from James's keys through his per-session binding table,
  and **camera rotation in degrees per step**, mapped from mouse counts through the 360° calibration take.
- The live executor is **the existing guarded pad**.
- There is no SendInput path (§4).
- This matches the inverse-dynamics lane (`docs/lanes/inverse-dynamics.md`), which already predicts degrees and
  semantic actions.

## Lead decisions and where they landed

| # | Decision | Where |
|---|---|---|
| F1 | No SendInput path: L0 stays closed. Hardware and driver injectors are out of scope. Outputs are semantic actions plus camera degrees, and the executor is the guarded pad with a calibrated stick→deg/s curve. Its tracking error is measured before any pilot | §1, §4; `vocab.py`, `executor.py` |
| F2 | Teacher-forced edge match window {t−1, t}. An echo baseline must score near 0 on it. The headline is self-fed | §3; `metrics.py` (`TEACHER`, `SELF`), `baselines.echo`, gate G0 |
| F3 | Self-fed evaluation over whole validation runs for G4, G5 and the headline, with G1 teacher-forced. Stuck-control and drift checks. The live previous action is what was actually sent | §3; `train.predict_self`, `metrics.sanity`, G5 |
| F4 | Onset/reversal sign agreement against persistence, AR(2) and the twin, with a G1-style margin. AR(2) is a named baseline | §3; `metrics.py`, `baselines.ar2`, G3 |
| F5 | A third pixel stream of native HUD crops at 1/3 in the primary arm, plus per-resource-state stratification. State what the arm cannot learn | §1; `cache.py`, `model.py`, `metrics.stratified` |
| F6 | The group unit is one recording, with a sitting tag for stratification. Validation and test come from dedicated 10-15 min takes at the start of two later sittings. The plumbing curve is restated in real train minutes | §3, §5, §6; `steps.py` |
| F7 | A dev split from train recordings. Epochs and weight decay are pre-registered from the plumbing dev curve. Per-epoch logs. DrQ shift on the global stream only | §2, §6; `train.fit`, `train.drq_shift` |
| F8 | A budget table for every fit, a cheap constant-feature twin, and throughput measured by the bench | §2; `model.py` (`frames=False`), `bench.py` |

The review's other findings are handled as follows:
- **F9** (KBM executor gaps) is moot with no KBM path, except its HUD-layout point, which applies in reverse (§4).
- **F10** (frame parity) is a pre-pilot measurement (§4).
- **F11** (counts) is corrected in §0.
- **F12**: lag 2 is added and the causality wording is fixed (§1).
- **F13**: `held_known` is now required (§5).
- **F14**: the scaling curve now has its own design (§6).

## 0. What exists, and measured input usage

`policy/execution.py` (the paired-execution baseline) keeps its role. This fit reuses its conventions but not its
data path, which does not scale:
- it keeps at most 20k frames in RAM;
- it re-encodes on every epoch;
- it has no past-input features;
- it regresses the mouse.

**Measured from the logger `inputs.jsonl` of the non-sealed sessions**, where a press is a down while not already held
(autorepeat excluded):

| Session | Focused logged span | Key presses | Mouse downs | Status |
|---|---|---|---|---|
| 032454 | **29 s**. The video itself is about 30 s (3,609 frames); both "~4 min" entries in the recording log are wrong | Space 16, A 10, Shift 8, W 6, S 6, E 5, Esc 3, D 2, F 1, Alt 1 | L 10, R 13 | admitted |
| 033319 | 6.9 min | Shift 189 (review's count); others not counted here | | verified, seg2/seg4 cut |
| 051828 | 7.0 min | Space 361, A 183, D 156, W 151, S 132, Shift 83, E 60, F 27, **C 24**, Alt 1 | R 226, L 110, X2 6, X1 3 | admitted |
| 053616 | 2.1 min | **not read (sealed)** | | sealed test |
| 053929 | 1.2 min | calibration | | inspected |
| 171533 | 2.6 min | Space 88, A 53, D 45, S 32, W 26, Shift 25, E 14, **C 8**, F 7, Alt 2, Esc 1 | R 48, L 24, X1 1 | pending |

- **Never pressed:** ultimate (Q) and melee (V).
- **Camera at the 33.3 ms step** (the review's measurement over 17 min):
  - non-zero \|dx\| has p50 20-40, p90 138-224, p99 431-641 and max 1,384 counts;
  - 16-35% of steps have zero dx;
  - \|dy\| never exceeds 362.
- **C is Team-Up, and it fires in the solo range** (lead correction; James's HUD labels the team-up slot C). It is an
  action (`team_up`), not an unsupported control.
- **Unsupported ceiling:** Alt, Esc and X1/X2 remain. The review's 2.2% of 051828's edges included C, so the ceiling
  is now lower. The fit reports it on every evaluation set (`unsupported_share`).
- **Trainable today:** at most 17 min before suitability cuts.

## 1. Inputs and outputs

### Rate and alignment

- **Anchors: 30 Hz**, stride `33_333_333` ns, inside each accepted segment ∩ focus interval.
  - Each anchor's frame is the last one with CTS ≤ anchor.
  - The frame's age is recorded per row and must be within 2 frame periods.
- **Action step:** the bin `(anchor_k + lag·step, anchor_k + (lag+1)·step]`.
  - `lag` ∈ {0, 1, 2}. The default is 0; the plumbing fit also runs 1 and 2.
  - The only measured live latency, acquisition to consumption, is 71 ms, about 2 steps.
- **Causality.** With lag ≥ 1, the previous-action input is the step after the frame. That is causal *with respect to
  the agent's committed actions*, which is what it has live, but not with respect to the frame.

### Observation at step k

| Stream | Content | Why |
|---|---|---|
| Global | Full frame area-downscaled to **256x144 RGB** | Scene, bots, terrace edges, swing anchors |
| Crosshair crop | Native 256x256 at screen centre → **128x128** | Aim. A far Galacta is a few pixels at 256x144 |
| **HUD (F5)** | Native M&K HUD crops at 1/3, stacked into **80x200**: the ability row (x 0.734-0.972, y 0.844-0.950; 608x152 → 200x50) over the M&K webs box (x 0.234-0.281, y 0.889-0.951; 120x90 → 40x30) | At 1/3, a cooldown countdown is 12-17 px tall and an ammo digit 7x11. At 1/10 in the global stream both are 1-5 px and illegible |
| Previous executed action | The step k−1 action: hold/press/release bits for 12 actions, one-hot camera classes, and a known bit | Causal input history. In training it is the recorded human step; self-fed and live it is **what the executor sent** (F3) |
| Regime bit | No-cooldown = 1 | Arm B only |

**Memory.** The LSTM carries history. Training sequences are 96 steps (3.2 s) with 32 steps of burn-in. Evaluation and
live runs keep the state from the start of each run.

**Excluded inputs.** Perception State (reader outputs) is not a model input, and neither are scenario tags. HUD
reader outputs (R12), when intake supplies them, are used only for stratification.

**What the primary arm cannot learn, and why:**
- **Resources the HUD does not draw.** The Get Over Here! tracer state (3 s, `docs/spiderman-kit.md`) is the known
  one. Cooldowns and charges *are* drawn, and the HUD stream now makes them legible.
- **Dependencies longer than about 3 s** that the screen does not show, such as "I pulled 6 s ago". The gradient never
  spans more than 96 steps. The state can carry them in principle but is never trained to.
- **Anything off-screen or behind the hero.** The hero's own region hides bots (`HERO_BOX`).
- **Bot hit points and KOs.** They are not in the crops, and the scoreboard is not shown during play.
- **Ultimate and melee:** no examples so far, and the pad cannot send them (below).
- **Anything specific to the pad HUD layout.** Every training frame is M&K, and the live pad shows a different layout
  (§4).

### Action at step k: semantic actions and camera degrees (F1)

| Action | James's default binding (per-session table in the header) | Pad control | Pad-sendable through `Live` today |
|---|---|---|---|
| move_forward / left / back / right | W / A / S / D | left stick (±1 per axis, normalised on diagonals) | yes |
| jump | Space | A | yes |
| web_swing | LShift | LB | yes |
| get_over_here | **F** (his HUD; the kit's PC column says E) | RB | yes |
| amazing_combo | **E** (his HUD; the kit says F) | X | yes |
| spider_power | LMB | RT (1.0) | yes |
| web_cluster | RMB | LT (1.0) | yes |
| ultimate | Q | LS+RS click | **no**: stick clicks are outside `Live`'s whitelist (`ALLOWED = {A, X, LB, RB}`) |
| melee | V | RS click | **no**, for the same reason |
| **team_up** | C | Y | **no**: Y is outside `Live`'s whitelist. Trained and scored normally (24 + 8 presses so far) |
| **goh_targeting** | X1 | none | **no**: no pad control. Trained and scored |
| **simple_swing** | Caps Lock | none yet | **no**, until the pilot pad profile binds Simple Swing to a button and `Live.ALLOWED` includes it (Pilot pre-registration item 7). Trained and scored with its positives (13 in 200129) |

**Per action and step:**
- held at the step's end, plus press and release (at least one edge in the step).
- **Taps:** a tap inside a step is press = release = 1 with held = 0.
- **Multi-edge steps** keep press = 1 and are counted.
- **Unknown holds:** holds unknown after a focus snapshot (`held_known`) mask all three channels.

**Camera:**
- **Axes:** yaw and pitch, each `counts × deg_per_count` from the calibration take (R8). Yaw is positive to the right
  and pitch positive downward, as the mouse's +dy.
- **Classes:** 31 foveated classes per axis: 0, then ±{0.05, 0.1, 0.2, 0.35, 0.6, 1, 1.6, 2.5, 4, 6, 9, 13, 19, 28, 40}
  degrees per step. Rotation under 0.025° counts as zero.
- **Pre-registration.** These are fixed before the calibration take exists, and the report gives the clamp rate
  (\|deg\| > 40) once real degrees are known.
- **Decoding** is the median of the predicted class distribution, which is MAE-optimal, not the argmax.
- **Masking:** a step with any absolute mouse packet masks the camera loss.

**What the executor emits.** An action is emitted only if it is pad-sendable **and** has ≥ 50 presses in the train
split (`vocab.live_mask`). Everything is trained and scored either way.

**Unsupported controls** are physical controls bound to no action: Alt, Esc, Tab, X1/X2, MMB, T, F1, B and the wheel.
Ultimate and melee are actions with no positives yet.
- They are never predicted and never sent.
- Their presses are counted per row.
- Their steps stay in training for the supported targets.

## 2. Model and budget

Parameter counts are counted from `policy/range_bc/model.py`.

| Part | Choice | Parameters |
|---|---|---|
| Global encoder | IMPALA CNN (16/32/32; conv, maxpool/2, 2 residual blocks each) → 32×18×32 → 1×1 conv to 8 → linear 256 | 1,277,768 |
| Crop encoder | The same, 128x128 → linear 256 | 622,408 |
| HUD encoder | The same, 80x200 → linear 128 | 353,992 |
| Previous-action embedding | Linear (102 → 64) + ReLU | 6,592 |
| Core | LSTM, hidden 512, input 704 | 2,494,464 |
| Heads | 39 action logits (hold/press/release × 13) + 2×31 camera logits | 51,813 |
| **Total** | | **4,807,037** |
| No-HUD arm (K7) | The same without the HUD encoder; trained in every fit | 4,190,901 |
| History-only twin (G1) | No encoders; a learned 640-d constant replaces the frame features. It trains in minutes | 2,553,509 |

**Loss:**
- BCE on holds.
- BCE on press and release, with `pos_weight` = the train negative/positive ratio, capped at 20.
- CE on camera classes.
- Weights 1 : 1 : 1 : 0.5, masked by `held_known`, the step's validity, burn-in and camera-known.

**Optimisation:**
- AdamW, lr 3e-4, cosine with 500 warm-up steps, clip 1.0.
- **Batch 8 × 96 steps** (measured: batch 32 needs about 97 GB of MPS memory; see below).
- Windows with stride 48; runs shorter than 48 steps are dropped and counted.
- **Augmentation:**
  - ±10% brightness/contrast on all streams, per sequence;
  - **a DrQ random shift of ±4 px on the global stream only**. The crop's offset is the aim signal, and the HUD crop
    is a fixed region;
  - previous-action dropout of 0.2, per step.
- **Epochs and weight decay are pre-registered from the plumbing fit's dev curve (F7), not from validation.**
  - Until then, the code's defaults (20 epochs, 1e-4) are placeholders.
  - The real fit logs train loss and per-head dev loss each epoch (`epochs_log`). These are reported and never used
    to select a checkpoint. The final checkpoint is the candidate.
- **Seeds:** 0, 1 and 2; seed 0 is the pre-declared candidate.

**Throughput and determinism, measured on synthetic tensors** (`policy/range_bc/bench.py`, Mac M5 Max, MPS,
torch 2.14.0, niced):

| Run (20 steps, 3 warm-up) | Batch × window | Mean s/step | Frames/s | MPS driver memory | Checkpoint sha256 (prefix) |
|---|---|---|---|---|---|
| Model, deterministic, run 1 / run 2 | 8 × 96 | 0.827 / 0.826 | 929 / 930 | 23.3 / 24.9 GB | `061a4f7c` / `061a4f7c` |
| Model, deterministic | 16 × 96 | 1.677 | 916 | 50.0 GB | `d3cb79ff` |
| Model, deterministic, run 1 / run 2 | 32 × 96 | 14.27 / 6.96 (steps 5.97-16.05) | 215 / 441 | 97.0 GB | `b768914b` / `b768914b` |
| Model, `use_deterministic_algorithms(False)`, run 1 / run 2 | 32 × 96 | 3.95 / 3.94 | 778 / 780 | 97.8 GB | `b768914b` / `b768914b` |
| History-only twin (constant features) | 32 × 96 | 0.026 | 118,023 | 2.4 GB | `5090dbd9` |

- **Batch 32 is not viable,** because it needs about 97 GB of MPS memory next to a 52 GB frame cache. Its
  deterministic runs slowed 2-4x, but the flag-off runs at the same 97.8 GB ran flat at 3.94 s/step, so the slowdown
  was system memory pressure at the time (22% free), not a property of batch 32 itself (review K8).
- **Batch 8 and batch 16 give the same ~930 frames/s.** **The fit's default batch is now 8 × 96**, which leaves room
  for the cache. The learning rate stays 3e-4.
- **Throughput against the estimate.** The measured 930 frames/s is 3-6x below this doc's first estimate (3-6k) and
  inside the review's predicted 2-5x shortfall.
- **What the bench leaves out:** the memmap gather, the DrQ loop and host transfer of real batches. The smoke fit
  measures those.
- **Runs and scripts:** the bench ran niced, from a scratch copy of `HEAD` `c0892ab` plus this uncommitted package, in
  a fresh `.venv` synced offline from `uv.lock`. The same copy passed all 70 `range_bc` tests on the Mac CPU.

**Budget for every fit** (F8). The first three columns of runs come from the bench. The frame-cache build is timed in
the smoke fit.

Assumptions, all from the bench:
- **Encoder model:** 930 frames/s at batch 8.
- **Twin:** about 118k frames/s, so each twin fit takes minutes.
- **Frame passes per epoch:** 2 × train steps (stride 48 over 96-step windows); the 32 burn-in steps are also run
  forward.
- **Not included, and unmeasured (review K8):**
  - the memmap gather and host transfer of real batches;
  - the per-epoch dev-loss pass;
  - the self-fed evaluation, a per-step Python loop over every evaluation run, for each model arm and the twin;
  - the no-HUD arm's own throughput (no HUD encoder; assumed close to the HUD arm's);
  - the frame-cache build, and at `--scope fit` a full sha256 pass over about 52 GB of cache.

  "3.2 h per seed" is the encoder cost only. The smoke fit measures the rest.

| Fit | Train steps (30 Hz) | Runs | Encoder-model hours | Notes |
|---|---|---|---|---|
| Smoke | ≤ 27k (≤ 15 min) | model and twin × 3 seeds × 1 epoch | ≈ 0.05 | Plus the cache build, which is untimed; the smoke fit times it |
| Plumbing: dev curve | 81k (45 min) | seed 0 × 20 epochs, with per-epoch dev loss | ≈ 1.0 | Sets the pre-registered epochs and weight decay |
| Plumbing: repeatability | 81k | seed 0 rerun | ≈ 1.0 | The byte comparison on real data |
| Plumbing: lag 1 and lag 2 | 81k | 2 × seed 0 × 20 epochs | ≈ 2.0 | Can drop to the dev-curve epoch count |
| Plumbing: scaling curve | ¼ to all of 81k | 4 points × 2 seeds, fixed steps = 10 full epochs | ≈ 3.9 | Twins add minutes |
| **Plumbing total** | | | **≈ 8 h** | **Two evenings.** The lead can trim the lag pair or the curve's seeds |
| Real, per seed and model arm | 270k (2.5 h) | 20 epochs | ≈ 3.2 (encoder only) | 9.7 min per epoch |
| **Real: 2 model arms × 3 seeds + 3 twins** (K7) | | | **≈ 19 h at 20 epochs; ≈ 9.7 h at 10** | Encoder-only. **Lead decision:** epochs and weight decay come from the plumbing dev curve; if that does not bring epochs to ≤ 10, **stride 64 first** (every step scored once, −25%), **then two evenings**. The global stream stays 256x144. The Mac is free for long jobs |
| Real, frames-only twin | 270k | 1 seed (ungated) | ≈ 3.2 × epochs/20 | Optional |
| Evaluation | 2 validation takes + dev | tf for every arm; sf for both model arms and the twin | unmeasured | The self-fed loop is one LSTM step per 33 ms step |

### Reproduction rule

- **Target: a byte-identical checkpoint** on a rerun of seed 0 with the same code, cohort and configuration.
  - Seeded python and torch.
  - All randomness drawn from CPU generators.
  - No loader workers.
  - `use_deterministic_algorithms(True)`.
- **Measured on MPS with synthetic tensors (above).** Reruns in separate processes gave byte-identical checkpoints at
  batch 8 (2 runs) and batch 32 (4 runs, two of them with the deterministic flag off). The flag changed neither bytes
  nor loss here, and the precedent from the 09-22 and 09-23 fits now extends to a 4.8M-parameter conv + LSTM.
- **Still to confirm on real data.** The plumbing fit reruns seed 0 on real data, because the loader, DrQ and
  prediction paths are not in the bench.
- **If that rerun differs,** the lane reports it. The fallback for the lead: identical thresholded decisions and camera
  classes on the whole evaluation set, metrics within 1e-6, and a byte-identical CPU rerun of a 1-epoch configuration.

- **The report records:**
  - git commit, the cohort (with each step table's sha256 and its role), frame-cache hashes;
  - configuration, the permutation rule, per-run seconds and optimiser steps;
  - checkpoint sha256, the per-epoch log, train minutes and the sealed denylist used.
- **Cross-machine check:** a Windows CPU reload must give identical thresholded decisions on the whole evaluation set,
  and a maximum probability delta ≤ 1e-4.

## 3. Evaluation before any live run

### Splits (F6)

- **Group unit.** The group unit is **one recording**: `session_group` must equal `session_id`, and the reader refuses
  anything else. Every header also carries a `sitting` tag, used for stratification.
- **Validation and test** come from **dedicated 10-15 min takes that James records at the start of two later
  sittings**. The test is 053616 plus one of those takes; it is sealed at registration, and the fit refuses it before
  reading any row (the header check and intake's sealed denylist, `--sealed-denylist`).
- **Dev** is one or more train-split recordings held out of fitting. It gives the per-epoch curves and the plumbing
  fit's numbers.
- **The plumbing fit reads no validation**: the driver refuses `--val` under `--scope plumbing`. Validation is first
  read by the real fit.

### Two evaluation modes (F2, F3)

- **Teacher-forced (tf).**
  - The true previous action is the input.
  - Edges match one-to-one within **[t−1, t]**: a prediction after a true edge is not credited, because by then the
    edge is visible in the input.
  - The echo baseline scores ≈ 1.0 on a symmetric ±1 window and ≈ 0 on this one (tested).
- **Self-fed (sf).**
  - Each validation run is replayed from its start over the recorded frames. The previous-action input is what the
    executor would have sent: decoded, live-masked holds and edges consistent with the hold state, and the camera
    saturated at the pad's maximum rate.
  - Edges match within [t−1, t+1].
  - The state carries through the whole run.

### Baselines

All are teacher-forced.

| Baseline | Prediction |
|---|---|
| Persistence | Holds stay, no edges, the camera repeats the previous step |
| Zero-motion | The camera does not move (reported for the camera only) |
| Train prior | Train marginal frequencies; the camera is the train median class |
| **Echo** (sanity, F2) | Repeats the previous step's edges. It must stay under 0.05 macro press-F1 in tf, or the gates are invalid |
| **AR(2)** (F4) | Camera x_k ≈ a₁x_{k−1} + a₂x_{k−2}, least squares on train, per axis |
| History-only twin | The constant-feature twin, same seeds |
| Frames-only twin | Previous action zeroed; reported, not gated |

### Metrics

- **Scope:** per action and per channel, over all steps and stratified by tag, regime, sitting and resource state.
  Resource state comes from R12 reads, for stratification only.
- **Holds:** balanced accuracy, plus F1 on change steps.
- **Edges:** F1 at the exact step and within the mode's window, plus PR-AUC.
- **Camera:**
  - MAE in degrees;
  - class accuracy and clamp rate;
  - sign agreement where \|true\| ≥ 0.3°;
  - **onset/reversal sign agreement**, on steps with \|true\| ≥ 0.3° whose previous true step was < 0.075° or of the
    opposite sign.

  The two thresholds are pre-registered in degrees. At a typical 0.013°/count they are close to the review's 20 and
  5 counts.
- **Self-fed sanity:** the longest predicted hold per action, and the range of mean signed rotation over 10 s windows.
- **Other:** press rates, the unsupported share, and multi-edge counts.

### Gates

All are on validation and pre-registered in `policy/range_bc/gates.py`.

| Gate | Mode | Condition |
|---|---|---|
| **G0 leak check** | tf | Echo macro press-F1 ≤ 0.05, or every gate is void |
| **G1 frames matter** | tf | For seed 0 **and** the 3-seed mean, the model beats the history-only twin by ≥ 0.05 macro press-F1 and has ≤ 0.9× its camera MAE |
| **G2 edges** | **sf** | Macro press-F1 over {spider_power, web_cluster, get_over_here, amazing_combo, web_swing, jump} ≥ 0.30, and spider_power, web_cluster and get_over_here each ≥ 0.20 |
| **G3 camera** | tf | Per axis: MAE ≤ 0.8 × the best of persistence, zero-motion and AR(2); **and** onset/reversal sign agreement ≥ the best of persistence, AR(2) and the twin **+ 0.05** |
| **G4 holds** | **sf** | Against the **self-fed history-only twin** (K4): move and swing balanced accuracy ≥ the twin's − 0.01, and mean change-F1 > the twin's. In self-fed mode a predicted change is counted from the model's own previous executed hold |
| **G5 sanity** | **sf** | Live actions' press rates within [0.5, 2]× the human rate; no predicted hold longer than the longest human hold; the 10 s mean rotation inside the human range. "Human" is train plus the evaluation set's own recordings, because a check the human fails is not a check |
| **G6 seeds** | both | G2 (sf) and G3 (tf) hold on all three seeds |

- **The headline:** seed 0's **self-fed** macro press-F1. It counts only when G0-G6 all hold.
- **Status of the thresholds:** they have no precedent. They are floors fixed before any validation number exists,
  and changing them afterwards voids the gate.
- **Also before a pilot:**
  - (learning plan, step 5) a qualitative review of self-fed predictions over validation clips, looking for transfer
    failures;
  - opening the test split once. If G2 or G3 fails there, there is no pilot.
- **Passing the gates is necessary, not sufficient.** §4's executor measurements must also be reported.

## 4. Live path (F1)

**Closed paths.** L0 stays closed. The game drops software-injected mouse clicks (`docs/plan.md` L0, "the mouse path is
closed; nobody works around it"). This lane has no SendInput or other injected keyboard/mouse path, and none is
planned. Hardware HID emulators, driver-level injectors, and anything else that makes injected input look physical
are **out of scope** under the scope boundary. Nobody works around L0 that way.

**The executor is the existing guarded pad.**
- **Where it runs.** `policy/range_bc/executor.py` computes each step's pad state offline and stdlib-only, and hands it
  to `agent.controller.Live.send_guarded`. `Live` remains the only door to the pad, with its whitelist, fresh-HUD proof
  at commit, 250 ms lease, scope deadline and scoreboard transitions. The loop's rules hold: HUD confirmed on a fresh
  frame, stop when it disappears, one agent on the desktop, desktop session only.
- **Actions → pad**, as in the §1 table:
  - Movement is the left stick.
  - A tap is held for the whole 33 ms step: `Cal.press_s` shows 33 ms registers.
  - Ultimate and melee are never sent.
- **Camera → right stick.**
  - Requested degrees per step become deg/s, then a deflection through the measured maps (`agent.controller.Cal`):
    yaw 18.5-415°/s over 0.1-1.0 deflection (172°/s at 0.45, as the placement lane measured), and pitch 43 and
    99°/s at 0.5 and 1.0.
  - The maps were measured at pad sensitivity H/V 265/75, a Linear curve and aim assist 0. **The pilot must run with
    those settings.**
  - The pad can deliver at most **13.8° yaw and 3.3° pitch per step**. Requests beyond that saturate, and the self-fed
    evaluation already feeds back the saturated value.
- **Closing the loop.** `Tracker` adds a correction in deg/s proportional to the accumulated difference between
  requested and measured rotation. It uses the frame-based rotation estimate, and skips steps without a measurement.
  The gain is 0 (feedforward only) unless the measured tracking error says otherwise.
- **The live previous action is what was actually sent** (F3). Lease releases, kill releases and saturation all feed
  back as sent, not as predicted.

**Measured before any pilot, and reported beside the gates:**
1. **Executor tracking error** (`executor.tracking_error`): per axis MAE, bias, RMS, saturated share, and MAE on
   unsaturated steps.
   - Method: a scripted pad replay of requested-rotation profiles, drawn from validation human steps converted to
     degrees, in the range, with rotation measured from frames.
   - This number is measured, not assumed.
2. **Human feasibility** (`executor.human_feasibility`): the share of human camera steps above the pad's cap, once the
   calibration take gives degrees. A large share means the pad cannot reproduce James's flicks, whatever the policy
   learns.
3. **Frame parity** (review F10): one static range scene captured both ways, live dxcam and OBS/NVENC through the
   cache's exact filter graph, with the per-channel mean and maximum difference per stream. A gap beyond the ±10%
   jitter means fixing the decode to match live.
4. **HUD layout** (review F9.6, reversed): training frames all show the M&K HUD, but live play on the pad shows the pad
   layout.
   - In the pad layout the webs box is mirrored and the charge badge is inverted (`perception/hud.py` `Layout`).
   - What to measure: whether the game keeps the M&K layout under pad input, or how far the pad-layout HUD stream sits
     from anything in training.
   - If they differ, the live HUD stream must be built from the pad layout's webs box, which is not trained. That is
     then a known transfer gap, reported as one.
5. **Control mismatch.** James steers with digital WASD and the policy's movement is digital too, but the pad's
   swing and aim assist may behave differently from M&K. The pilot's first trials are read qualitatively for this.

**Scope.** Practice range only, under the existing per-entry binding. The maximum trial duration is pre-registered in
the pilot design, and placement uses the placement lane's pad homing, all on the same pad.

**Out of scope for the first fit:**
- KBM output of any kind;
- real matches and lobbies;
- ultimate and melee;
- wheel, menus and hero select;
- DAgger or fine-tuning on agent-run data;
- RL;
- reader outputs as inputs;
- inverse dynamics on replays (VUH-1353), whose semantic and degree outputs this action space was aligned with.

## 5. What intake must provide

The contract is in the `policy/range_bc/steps.py` docstring and is enforced by `steps.load`.

| # | Requirement |
|---|---|
| R1 | 30 Hz anchors with an exact frame reference (video, ordinal, pts, timebase, composition time) and its age |
| R2 | A **per-anchor step table** in the semantic action order, with holds, presses, releases, relative counts and unsupported presses. It replaces per-sample past events |
| R3 | Contiguous-run ids. A gap, focus loss, pause or segment boundary starts a new run, and a gap-free flag is set per row |
| R4 | Per row: segment suitability, regime, scenario tags with their source, and optional HUD reads (R12). Per header: session, group = session, **sitting**, split, patch, settings hash |
| R5 | Regime per row, so a declared mixed cohort (arm B) is possible |
| R6 | Single keyboard-and-mouse device scope, with injected (device 0) events asserted to be zero |
| R7 | **The binding table in every header**, mapping each action (13, including `team_up` on C) to a physical id, with ids distinct. The cohort must share one table. James's HUD shows E = Amazing Combo and F = Get Over Here!; confirm on his settings screen |
| R8 | **The calibration in every header**: yaw and pitch deg/count and their source. Yaw comes from the 360° take; pitch needs its own take, such as horizon to straight down (90°), or an explicit statement that it equals yaw |
| R9 | Exact decode ordinals, checked by the cache against pts |
| R10 | Validation and test from the dedicated takes, sealed at registration, with the sealed denylist handed to the fit |
| R11 | The tally counts focused, accepted, gap-free minutes in runs of at least 1.6 s (`steps.train_minutes`), not video length |
| R13 | `held_known` per action is **required** (review F13) |
| R14 | `hud_layout: "mk"` in every header, because the HUD crop regions are the M&K layout's |
| R15 | `media_sha256` of the original recording in every header (K1), and `swing_mode` from the settings look (K6) |
| R16 | Intake's `FIT_ACTIONS` includes `team_up` (appended last), so its default header equals the fit vocabulary (done 2026-09-23) |

## 6. Data sufficiency (F6, F14)

**Today:** at most 17 trainable minutes, with no validation or test take recorded yet.

| Fit | When | Train / dev / val | Purpose | Reads |
|---|---|---|---|---|
| **Smoke** | When Mac jobs are allowed, on today's recordings | All available minus one recording as dev | The code path: step table → cache → fit → report → Windows reload. It also times the cache build and measures real-data throughput | dev |
| **Plumbing** | At about 1 h admitted | About 40-50 train min (1 h minus one or two dev recordings) | Pre-register the epochs and weight decay from the dev curve. Measure lag 0/1/2, MPS repeatability on real data, and the scaling curve | **dev only** |
| **Real** | At ≥ 3 h admitted, with both dedicated validation takes recorded | About 2.5 h train, one or two dev recordings, 2 validation takes | The §3 gates | dev, then validation; test once at the end |

**The scaling curve, in actual train minutes:**
- **Points:** nested subsets at ¼, ½, ¾ and all of the plumbing fit's train minutes, each reported in minutes.
- **Training:** a fixed number of optimiser steps per point (`--max-steps`) and 2 seeds per point.
- **Plotted against dev:**
  - per-head dev NLL;
  - the frames-minus-twin gap in teacher-forced macro press-F1 on the [t−1, t] window;
  - dev camera MAE.

**Pre-registered reading:**

| Rule | Condition | Meaning and action |
|---|---|---|
| (a) | The frames-minus-twin gap is not positive and rising from ½ to all | More minutes will not make the policy use its eyes. Change the observation or encoder first |
| (b) | Dev NLL falls roughly linearly in log(minutes) | Extrapolate to 2.5 h of train. If the projection does not clear the G2/G3 floors with margin, 3 h is not enough, and the report states the implied minutes |
| (c) | Train NLL falls while dev NLL rises | The model is memorising. Fix regularisation (weight decay, epochs, augmentation) before adding data |

## Code

The code is `policy/range_bc/`, uncommitted, and the lane is its only writer.

**Modules:**

| Module | Holds | Needs |
|---|---|---|
| `vocab` | Actions, pad mapping and camera classes | stdlib |
| `steps` | The contract reader, the sealed denylist, runs and windows, targets, the previous-action encoding, train statistics and train minutes | stdlib |
| `fixture` | Synthetic recordings and FFV1 videos | stdlib + ffmpeg |
| `cache` | The three-stream frame cache, with pts-checked ordinals | stdlib + ffmpeg |
| `baselines` | Persistence, zero-motion, prior, echo, AR(2) | stdlib |
| `metrics` | Both match windows, onsets, sanity, stratification | stdlib |
| `gates` | G0-G6 | stdlib |
| `executor` | Pad mapping, saturation, tracking error, feasibility | stdlib; imports `agent.controller` |
| `report` | The fit report | stdlib |
| `hudmap` | The fixed pad → M&K HUD transform and the live HUD stream crop | numpy (+ cv2 for the crop) |
| `hudparity` | The pre-registered parity test on paired stills | perception group |
| `verify` | The Mac CPU reference (written by the fit) and the Windows CPU reload verifier | torch |
| `model` | The network | torch |
| `train` | Loader, DrQ, loss, fit with dev logs, tf/sf prediction, checkpoint (`rivals-range-bc-v2`, domain `semantic_pad`), the fit CLI | torch |
| `bench` | The synthetic MPS bench | torch |

**Tests:**
- `tests/test_range_bc.py`: stdlib, with the cache tests skipped without ffmpeg.
- `tests/test_range_bc_torch.py`: skipped without torch; run it with `uv run --group execution`.
- `tests/test_range_bc_contract.py`: intake → fit, end to end (stdlib).
- `tests/test_range_bc_hudmap.py`: the transform (perception group), plus a `corpus`-marked parity regression.

## Review round 2: the code review and the lead's decisions (2026-09-23)

| # | Decision | Where it landed |
|---|---|---|
| K1 | The sealed denylist is parsed by intake's own reader (`human_intake.load_denylist`) with a sha256 pin, and is mandatory in the fit, cache and verifier CLIs, defaulting to `data/human/sealed-denylist.json` (pin `57cfe01f…`). The step-table header carries `media_sha256`, and a header naming a sealed id or media hash is refused before any row. Matching is exact everywhere: a file named exactly for a sealed id is refused before opening, and a substring is not a match | `steps.load_denylist`, `check_sealed`, `load`; `cache.main`; `verify.main`; tests on the real file |
| K2 | Intake owns the writer (`agent.human_intake.write_steps`, already written by the admission lane) with every header field plus `media_sha256`, `session_group` = the recording, and the gap rule on intake's side (a stale-frame anchor is never emitted; the run ends). The fit lane owns the end-to-end contract test | `tests/test_range_bc_contract.py`: intake fixtures → `write_steps` → `steps.load`, plain and capture-gap sessions, the denylist and a pending yaw gain. Intake's default `FIT_ACTIONS` now includes `team_up`, and a test pins that it equals the fit vocabulary |
| K3 | `Cal` stores a measured deadzone per axis (None today), and `stick_for` moves its zero-rate point there. The minimum rotation per step with measured support is reported (yaw 0.62°, pitch 1.43°). Tracking error is reported per requested-rate band, and replay profiles come from train or dev recordings only. **The low-end map (yaw 0-0.1, pitch 0-0.5) and the deadzone are a live pad job for James's next PC window** (the lead schedules it with the placement look) | `agent/controller.py` (`Cal.yaw_deadzone`, `pitch_deadzone`, `stick_for(…, deadzone)`, backward compatible); `executor.min_step_degrees`, `tracking_error` bands, `replay_profiles`, `human_feasibility` |
| K4 | G4 is self-fed against the self-fed twin, with change measured from the model's own previous executed hold | `metrics.evaluate(self_fed=…)`, `gates.g4` |
| K5 | The report carries the code closure: the sha256 of every repo module the fit imported. `--scope fit` refuses untracked or uncommitted code, and verifies every cache byte | `train.code_closure`, `require_committed`; `verify` checks the closure |
| K6 | A `swing_mode` header field. The live mask drops `web_swing` unless it equals the pad's (Automatic Swing OFF, Hold to Swing ON) | `steps`, `vocab.PAD_SWING_MODE`, `vocab.live_mask` |
| K7 | Every fit trains the `hud=False` arm beside the HUD arm. The HUD arm is the pilot candidate only if the pad-HUD parity passed; otherwise the no-HUD arm is, pre-registered | `train.MODEL_ARMS`, `candidate_arm`, `--hud-parity` (required at `--scope fit`); gates per arm |
| K8 | The unmeasured costs are named; "3.2 h per seed" is encoder-only | §2 budget |
| K9 | The YUV → RGB conversion is pinned (tv range, BT.709, `accurate_rnd+bitexact+full_chroma_int`) and every scale is bitexact. Differently tagged video is refused, the stream timebase is checked beside pts, a same-named-video collision is refused, and the video must hash to the header's `media_sha256`. **Caches are built on the Mac only** | `cache.GRAPH`, `check_colour`, `build(any_platform=False)` |
| K10 (reviewer, not a lead item) | `--model-config` is refused at `--scope fit`; `--scope fit` requires a pre-registration file (epochs, weight decay, stride) and matches the CLI to it; G5's use of the evaluation set's own recordings is stated in the report; a test pins that self-fed output never reads the true previous action | `train.preregistered`; tests |

**Other lead decisions of this round:**
- **Pitch:** a pitch calibration take (horizon → straight down → horizon) is requested alongside the 360° yaw take.
  Until it exists, no pitch gain is assumed: the header's `pitch_deg_per_count` is null, pitch labels are masked
  everywhere (loss, metrics, G1/G3/G5 use yaw only), and the verdict carries `pitch_gain_known: false` and is never
  pilot-worthy. A pending *yaw* gain is refused outright, so no fit runs before the yaw take.
- **Team-Up:** `team_up` (C, pad Y) is the 13th action, appended so the first twelve keep intake's order. It is
  trained normally and live-masked only because Y is not pad-sendable. Ultimate and melee stay unsupported, with no
  positives. The kit's "only with a partner hero" line is corrected in `docs/spiderman-kit.md`.
- **James's E and F:** his M&K HUD labels E over the Amazing Combo fist and F over the Get Over Here! arrow, the
  reverse of the kit's PC column. The vocab defaults follow his HUD; each recording's binding table (R7) remains the
  authority.

## Pilot pre-registration

These are fixed before any pilot. Changing one is a new pre-registration.

1. **Pad settings:** H/V sensitivity **265/75**, **Linear** response curve, **aim assist 0**, Automatic Swing OFF and
   Hold to Swing ON. These are the conditions `Cal`'s maps and the swing mode were measured under.
2. **The candidate** (round 3; lead decision) is seed 0 of the **no-HUD arm**. The HUD arm takes over only if a P2′
   parity run on fresh frames passes **and** the HUD arm beats the no-HUD arm on validation by **+0.05 self-fed macro
   press-F1** (`train.choose_candidate`). Parity run 1 (P2) failed and stays failed on record.
3. **The HUD transform and its parity** (lead decision; `policy/range_bc/hudmap.py`, `hudparity.py`).
   - **The transform:**
     - it swaps ability slots 3 and 4 (pad: Get Over Here! then the combo fist; James's M&K: the reverse, measured
       with the repo's icon templates on 603 pad stills and 47 M&K frames);
     - it moves the web count +241 px (measured digit right edges 444.7 → 685.5 at 2560x1440);
     - it inverts the charge badges.
   - **Parity run 1** (`hud-parity-1.json`, sha256 `158649e6…`), 603 pad stills from the pilot archives against 47 of
     James's frames from 051828 and 171533:

     | Check | Result | Detail |
     |---|---|---|
     | P1 slot identity | **pass** | The same ability at every position |
     | P3 web digit position | **pass** | 603/603 inside James's range (median 685.5 against 682.5-686.5) |
     | P2 reader parity | **fail as pre-registered, on one quantity** | Webs 603/603, swing and combo charges 99-100%, cooldowns, HP and ult all agree, with **zero contradictions anywhere**. The failure is Get Over Here!'s ready flag at M&K slot 4: 347/603 agree and 256 are lost (the M&K reader returns unknown) |

   - **Why slot 4 is lost:** the M&K reader's occlusion guard abstains there on **64% of James's own genuine M&K
     frames** (30/47), because of the ult diamond's glow, against 46% on the transformed frames.
   - **Untransformed baseline:** webs and combo charges agree 0%.
   - **As pre-registered, the fallback applies: the no-HUD arm is the pilot candidate** unless the lead amends P2. An
     amended rule could be "losses no higher than the M&K reader's native abstention at that position, and zero
     contradictions"; on it this run would pass. The lane does not change the rule itself.
   - **Not covered by the parity test:**
     - the swapped and moved regions carry their scene background, so visible seams appear at their edges
       (`hud-transform-sheet.png`);
     - the pad stills are almost all at full resources (webs 4-5, full charges, few cooldowns), so parity is shown
       mostly on those states.
4. **Before any pilot, measured and reported beside the gates:**
   - the low-end yaw/pitch map and deadzone (K3, the live pad job);
   - the executor's tracking error per requested-rate band, on replay profiles from train or dev recordings;
   - human feasibility (steps above the pad's cap, and moving steps below the smallest measured rotation);
   - frame parity (dxcam against the cache graph);
   - the qualitative self-fed review.
5. **Never sent:** ultimate, melee and team-up (outside `Live`'s whitelist), `goh_targeting` and `simple_swing` (no
   pad control), and web-swing unless the recording's swing mode equals the pad's.
6. **Not yet fixed here:** the maximum trial duration, and placement between trials. Both belong to the pilot design
   and the placement lane.
7. **Pre-registered settings change: Simple Swing on the pad** (James's decision, 2026-09-23). `simple_swing`
   (Caps Lock) is trained and scored today and masked live. It becomes sendable only when **both** of these are true,
   and together they are one new pre-registration of the pad settings in item 1:
   - the pilot pad profile binds Simple Swing to a pad button, recorded here with the button;
   - `Live.ALLOWED` includes that button (`agent/controller.py`, the controller lane's change).

   Then `vocab.ACTIONS` gets that pad control and `PAD_SENDABLE` true, `executor.BUTTON` maps it, and the executor still
   emits it only with at least 50 train presses (`vocab.live_mask`). Until then no checkpoint can send it, whatever its
   count.

## Round 3 (2026-09-23): review, calibration take, vocabulary, cache rehearsal

### HUD parity: P2 stays failed, and P2′ is pre-registered

- **The amendment is withdrawn** (the lead, following the round-3 review). Run 1 stays **FAIL** on record, and the
  no-HUD arm is the pre-registered candidate.
- **P2′** is pre-registered before any new data (`policy/range_bc/hudparity.py`, `--rule p2prime`), exactly as the
  review worded it:
  - ready flags are scored only where the M&K reader's occlusion guard is not firing at that slot;
  - agreement ≥ 0.95 on ≥ `MIN_KNOWN` frames per quantity;
  - zero contradictions on every quantity;
  - a **power check**: the untransformed baseline must fail P2′;
  - a **coverage floor**: ≥ 20 frames each with webs ≤ 2, a spent swing charge, a spent combo charge, and a running
    cooldown on each ability slot;
  - **fresh frames only**. The CLI refuses any source that run 1 used (by sha256) and 053616.
- **Exercising the code on run 1's frames** is not a parity result, because P2′ refuses them.
  - Agreement and zero-contradiction would pass, and the power check works: the untransformed baseline has 17
    contradictions.
  - The **coverage floor fails**: those stills have no low-web or spent-charge frame at all.
  - So P2′ needs new pad stills from the placement or pilot runs, and M&K frames from the campaign takes.
- **The HUD arm** becomes the candidate only if P2′ passes and it beats the no-HUD arm by +0.05 self-fed macro
  press-F1 on validation (seed 0).
- **L6:** a parity file must be a real `hudparity` result, and its sha256 is pinned in the pre-registration at
  `--scope fit`.

### The live contract (L1, L2)

- **`hudmap.live_streams(frame)`** applies `pad_to_mk` **once, to the native frame**, and builds all three streams from
  it. The global stream also shows the HUD at 1/10, so it sees the M&K layout too; the crosshair crop is unaffected.
- **Cost:** the transform now copies only the bottom HUD band and uses cv2 connected components and flood fill. Measured
  on 40 pilot stills:

  | Step | Median | p90 | Max |
  |---|---|---|---|
  | `pad_to_mk`, in place | **0.86 ms** | | 1.2 ms |
  | `live_streams`, all three streams | **3.2 ms** | 3.9 ms | |

  The review had measured 8-14 ms for the previous version. Parity run 1, rerun with the new code, reproduces every
  number exactly.
- **This cost belongs in the measured frame-to-send latency.**

### Other round-3 items

- **L3:** tracking error is banded per axis. Pitch uses 0-9, 9-43 and 43-99 °/s, then saturated.
- **L5:** a non-default denylist or pin is flagged in the report and refused at `--scope fit`. The verifier fails a
  report whose denylist was not the pinned default.
- **L7:** the verifier requires `--report-sha256` (recorded out of band) and re-hashes cache bytes by default. At a
  self-fed divergence it reports the step's decision margin: its distance from 0.5 or from the camera median boundary.
- **L4 (the L4 owner's decision):** the executor uses `Cal.*_deadzone` once it is measured. The scripted `Live._aim`
  does not.
- **Budget (the lead's call):** the HUD arm cannot be the candidate without P2′. The reviewer suggests training it on
  one seed, as a reported comparison, to save about half of the ≈ 19 h.

### Calibration (the lead's decisions from the calibration take)

- **Yaw:** 0.0330738 °/count from the slow 360° turn. This equals exactly 0.0175 × sensitivity 1.89.
  - James has mouse acceleration and smoothing **on**, but the settings show factor 1.00 with threshold 1. Acceleration
    is most likely a no-op and the gain linear.
  - That linearity is **unverified above slow speed**. It is pre-registered as a caveat (`vocab.DEGREE_CAVEAT`), which
    every degree target and every saturation, tracking and feasibility number carries.
  - The header records `accel_on` and `calibration.kind: "slow_turn_constant"`. The kind `"speed_curve"` is refused
    until it is implemented.
- **Proposed for James's next session: a multi-speed calibration take.** Three full 360° turns each at slow, medium and
  fast wrist speed, on a fixed landmark, logged. It confirms linearity, or gives the speed curve.
- **Pitch** could not be measured: the third-person orbit camera and the pitch clamps prevent it.
  - It is derived: pitch = yaw = 0.0330738 °/count, from equal sensitivities and the exact 0.0175 × sensitivity match.
  - The header records `calibration.pitch.kind: "derived_equal_sensitivity"`. Pitch labels are usable with that flag,
    and the verdict carries `pitch_gain_kind`.

### Vocabulary: 14 actions (15 since `simple_swing`; see "Plumbing pre-registration")

- `team_up` is on C.
- **`goh_targeting`** (Get Over Here Targeting) is on X1. It is trained and never sent.
- **melee** is on V *and* Mouse 5. A binding value may be a list of ids; the action is held while any of them is held,
  and presses and releases are the changes of that combined hold. Intake's writer implements this through `aliases`.
- **Caps Lock** (Simple Swing) was bound to no action until it occurred. It first occurs in 200129 (VK 20, 13
  presses), and James decided it is the 15th action, `simple_swing` (next section). This had been noted as a toggle
  of the swing mode itself: if it is one, the header's `swing_mode` describes the session's start, and `web_swing`'s
  live mask (K6) still compares that start state with the pad's.
- **Which actions have positives is counted, never assumed.** Melee may now have positives, through Mouse 5.
- **Parameters:**

  | Arm | Parameters |
  |---|---|
  | Model | 4,808,768 (15 actions: 4,810,499) |
  | No-HUD arm | 4,192,632 (4,194,363) |
  | History-only twin | 2,555,240 (2,556,971) |

- **The cache is about 208 kB per anchor** (110.6 global + 49.2 crop + 48.0 HUD), so **about 67 GB at 3 h**, not
  52 GB. The 52 GB figure predates the HUD stream.

### Mac cache rehearsal

- **Input:** the 2026-09-23 15-47-07 calibration take (HEVC, NVENC, 2560x1440 at 120, yuv420p, tv range, BT.709). It
  is not a training session.
- **Transfer:** the take went to a Mac scratch folder with its logger files, and all four hashes were checked against
  the Windows receipt.
- **Decode agreement:** Windows ffmpeg **8.0.1** (gyan full build) and Mac ffmpeg **8.1.2** (Homebrew `8.1.2_1`,
  native `hevc` decoder) decode the same frames:
  - 14,242 frames;
  - the same pts list (`bfb95427…`);
  - the importer's `match_frames` gives identical refs on both machines, with a fitted muxer offset of exactly
    **21/1000 s**, equal to the independent +21 ms anchor, and residual 1/3000 s.
- **Cache build:** the Mac's cache builder, run through the CLI, was fed a step table built on Windows from Windows's
  refs. Every selected frame's pts and the stream timebase matched on all 3,560 anchors, the media hash was verified,
  and it took 20 s.
- **Pinned for caches: Homebrew ffmpeg 8.1.2_1 on the Mac.** Any other build is a new pin.
- **Script:** `docs/evidence/fit-readiness-20260923/range_bc_rehearsal.py`. The runbook is in that folder's README,
  section "Range BC".

## Smoke fit on real data (2026-09-23)

This is a plumbing check only. No gate is claimed and no validation exists or was read.
- **Code:** `git archive` of `2052b45`, byte-identical in the fit's files to the landed `ebba342`.
- **Data:** train on 051828 (6.97 counted min), dev on 171533 (2.57 min, a train-split recording used only for
  per-epoch dev loss).
- **Run:** `--scope smoke --epochs 1 --seeds 0 --device mps`, twice, on the Mac, niced.

| Measure | Result |
|---|---|
| Transfer (runbook steps 1-2) | 9.2 GB of originals in 5 min, every hash verified on the Mac |
| Cache, 051828 (6.9 GB H.264, 7 min) | 81 s, 2.4 GB, 12,558 frames, all pts and timebase checks passed |
| Cache, 171533 (2.3 GB) | 30 s, 976 MB, 4,800 frames |
| Determinism on real data | Runs A and B gave **byte-identical checkpoints for all three arms**, and identical CPU-reference decisions |
| MPS vs Mac CPU | Teacher-forced decisions equal; max probability delta 2.1e-7 |
| Windows CPU verifier (runbook step 9, clean worktree at `2052b45`) | **All 14 checks pass**: identical tf and sf decisions on 4,800 dev rows, max delta 3.6e-7, full cache re-hash, code closure equal |
| Throughput with the real loader | HUD model **802 frames/s**, no-HUD **1,056**, twin 52k |
| Evaluation (every arm tf and sf, the baselines) | 22 s for 4,800 dev rows |

- **About the throughput:** each run was one epoch of 33 steps, so the numbers include the per-epoch dev pass and
  first-step warm-up.
- **What it means for the budget:** the HUD arm's 802 frames/s is about 14% under the synthetic bench's 930, so plan
  about 11 min per epoch at 2.5 h of train.
- **The candidate is the no-HUD arm,** as pre-registered: there is no P2′ parity yet.
- **The runbook was corrected during the smoke:**
  - a quoted scp remote path fails in SFTP mode;
  - two zsh traps (`path` clobbers `PATH`; `nice` cannot run a function).

## Replay labels: how expert replays enter `rivals-range-steps-v1` (design, 2026-09-23)

**Purpose.** Expert replay footage, once labelled, becomes a step table the fit can read. Two lanes label it:
- **inverse-dynamics** (`docs/lanes/inverse-dynamics.md`): camera yaw and pitch in true degrees, locomotion holds,
  holds for primary, swing and crawl, and action onsets. Every head can abstain.
- **replay-hud** (in progress; its lane doc is not in this checkout yet): per-frame ability states, and cast events
  with abstentions.

**What is built.** The contract is in `policy/range_bc/steps.py` (docstring "REPLAY source"), with a fixture
(`fixture.replay_session`) and tests. There has been no fit.

**The one rule that matters:** an unknown channel is masked out of the loss and the metrics per channel and per
action, and is never read as "no". A test shows that a replay row with unknown movement contributes exactly zero
gradient to the movement heads, and that changing the values behind an unknown label does not change the loss.

### Header (`source_kind: "replay"`)

| Field | Replay value | Human value it replaces |
|---|---|---|
| `calibration` | `{kind: "replay_degrees", source, label_sources: {camera, movement, edges}}`. Degrees come direct, with no counts→degrees gain; each label source names a model or reader and its version | `slow_turn_constant` with gains |
| `expert_context` | `{player, match_id, viewer_fov_assumption, replay_source}`. The FOV assumption matters because whether the replay renders at the viewer's FOV or the target's decides what the IDM's degrees mean (IDM doc) | `settings_hash`, `bindings`, `accel_on` (absent, refused if present) |
| `swing_mode` | From the expert's `control_context` (IDM doc, F4); null = unknown, so the live mask drops `web_swing` | James's settings |
| `media_sha256` | The replay *capture* video (OBS recording of the replay viewer) | The original recording |
| Absent, refused if present | `bindings`, `device_scope`, `injected_events`, `settings_hash`, `accel_on`, `media_relocation` | |

- **Unchanged:** `session_id` (the capture), `session_group` = `session_id`, `sitting`, `split`, `step_ns`,
  `frame_period_ns`, `actions` (the same 14 semantic actions), `hud_layout` (must be `mk`: a pad-HUD replay is out of
  scope), `video_size`, `patch`.
- **The sealed denylist is irrelevant** (no human take is a replay). The reader still runs it, and it cannot match.
- **No media relocation:** the cache refuses one for a replay.

### Rows

| Field | Replay form |
|---|---|
| `held_start`, `held_end`, `press`, `release` | 14 × (0 \| 1 \| null). Press and release are onset flags, never counts |
| `held_known`, `press_known`, `release_known` | 14 × bool each, **equal to "the value is not null"** (`held_known` covers start and end). The reader refuses any disagreement |
| `yaw_deg`, `pitch_deg` | float or null: degrees this step, direct |
| `beyond_pad_envelope` | bool: the IDM's flag. The label is saturated, never silently clipped (IDM doc) |
| Absent, refused if present | `mouse_dx`, `mouse_dy`, `relative_known`, `wheel_v`, `wheel_h`, `unsupported` |
| `hud` (optional) | replay-hud's per-frame ability states, for stratification only, never a model input |

**The framing fields are unchanged:** `i`, `run`, `anchor_ns`, `frame`, `gap_free`, `segment`, `suitability`,
`regime`, `tags`. Anchors are 30 Hz on the capture's composition clock, exactly as for James.

**Edge conservation** (`press − release = held_end − held_start`) is checked only where all four values are known.
**Hold continuity** is checked only where both neighbouring holds are known.

### From the labellers' 60 Hz intervals to one 33.3 ms step

The labelling lanes' writer applies these rules:
- **Camera:** the sum of the two intervals' degrees. The step is unknown if either interval is unknown, and flagged
  beyond the envelope if either interval is.
- **Holds:** `held_end` is the state in the step's last interval, and `held_start` is the previous step's `held_end`
  (the state before the first interval). Each is unknown where its interval abstains.
- **Onsets:** `press` is 1 if either interval has an onset, 0 only if both say "no" (a "no" needs support, IDM F2),
  and null otherwise.
- **Release:** `release` is derived only where both holds are known (a fall), and is null otherwise. Cast-only actions
  (Get Over Here!, Amazing Combo, Web Cluster from replay-hud) therefore have `release` null.
- **Unlabelled actions:** actions no labeller emits (ultimate, melee, `team_up` and `goh_targeting`, until a head
  supports them) are all null. That keeps them out of the loss and the metrics entirely.

### What the fit does with it

- **Targets** carry per-channel masks: `known` (hold), `press_known` and `release_known`. Human rows set all three
  from `held_known`, so their behaviour is unchanged (all human tests pass).
- **The loss** uses a `[B, T, 3, 14]` mask, so each channel's term averages only over its known entries.
- **Metrics** gate every channel separately, and press rates divide by press-known steps.
- **The previous-action encoding** sets no bit for an unknown channel.
- **Statistics** count per channel (`press_known`, `release_known` denominators). The prior and `pos_weight` use them.
- **Cohorts hold one source kind.** Mixing replay and human recordings (replay pretraining, then a James fine-tune)
  needs its own design: gates, splits, and how the expert's context meets James's. It is future work, and the reader
  refuses it today.

### Tests

- **`tests/test_range_bc.py`:** a replay recording loads, with unknowns exactly where the fixture put them.
  - Refused: every human-only field; a wrong calibration kind; a missing label source or expert-context field;
    known-mask and value disagreements; out-of-range values; a conservation break; mouse fields in a row.
  - A mixed cohort is refused, and so is a relocation for a replay.
  - Unknown channels are never scored, and never fed back as previous-action bits.
- **`tests/test_range_bc_torch.py`:** a replay window with unknown movement has no mask on any movement channel, gets
  zero gradient there and non-zero gradient where movement is known, and its loss is invariant to the values behind
  an unknown label.

## Plumbing pre-registration (2026-09-23, before either new session is admitted)

Fixed in `docs/evidence/fit-readiness-20260923/range_bc_plumbing_prereg.json`. The driver `range_bc_plumbing.py` in
the same folder turns it into the exact command sequence, and later derives the real fit's `--preregistration` file
from the plumbing reports. No plumbing fit has run.

**Vocabulary: 15 actions.** `simple_swing` (Caps Lock, `key:58:0`; James's decision) is appended 15th, so the other
indices are unchanged. It is trained and scored with its positives, and masked live until Pilot pre-registration item
7 is met. Consequences:
- **Intake** appends `simple_swing` to `FIT_ACTIONS`, binds Caps Lock in the reviewed binding tables and re-emits all
  four step tables with 15 actions: 051828 and 171533 as well, which have zero presses but must carry the 15th column
  with its own `held_known`. The fit refuses the 14-action tables (`actions differ from the fit vocabulary`).
- **The contract tests** (`tests/test_range_bc_contract.py`) pass against intake's working-tree change, which
  appends `simple_swing` to `FIT_ACTIONS` and binds `key:58:0` in its fixtures. The fit's vocabulary change and that
  change must land together: either one alone fails them.
- **The caches** of 051828 and 171533 are rebuilt, because the cache binds the step table's sha256. That takes about
  2 min on the Mac.
- **The parameters** grow by 1,731 per arm (the table above).
- **Class balance:** 13 positives give the press channel a large `pos_weight`, capped at 20 (`steps.pos_weight`).

**Cohort, fixed before admission.** Validation: none.

| Role | Recordings |
|---|---|
| Train | 051828 and 200129 |
| Dev | 171533 and 205528 |

The dev rule is "171533 plus the later-recorded new session", which does not look at content. It also keeps 200129's
`simple_swing` presses in train. The dev list stays frozen through the real fit.

**Runs** (one niced durable queue on the Mac; every run `--scope plumbing`, batch 8, lr 3e-4, `normal` regime, dev
only):

| Run | Arms × seeds | Settings | Purpose |
|---|---|---|---|
| p1-curve | all three × 0 | 20 epochs, wd 1e-4, stride 48, lag 0 | The dev curve (per-epoch dev loss) |
| p2-repeat | no-HUD + twin × 0 | as p1 | Byte repeatability against p1 on real data |
| p3-wd | no-HUD × 0 | wd 1e-3 | The weight-decay alternative |
| p4-lag1, p4-lag2 | no-HUD × 0 | lag 1, lag 2 | Reported only |
| p5-scale-{¼, ½, ¾, 1} | no-HUD + twin × 0, 1 | `--train-fraction` f, `--max-steps` = 10 full epochs at f = 1 | The scaling curve (§6) |

**New options, used only by these runs.** `--scope fit` refuses both:
- `--arms` trains a subset of arms. If the pre-registered candidate arm is not trained, the report's CPU reference
  uses the first trained model arm and says so.
- `--train-fraction` keeps the nested time-prefix of each train recording that holds that fraction of its eligible,
  gap-free steps (`steps.truncate`). The file and its sha256 are unchanged. Each point reports its real minutes.

**Derivation** (`range_bc_plumbing.py derive`), on the pre-registered candidate arm (no-HUD). The HUD arm's curve is
reported and selects nothing.
- **Weight decay:** 1e-3 only if p3's minimum dev total loss is strictly lower than p1's; otherwise 1e-4.
- **Epochs E\*:** 1 + the argmin epoch of the chosen curve; ties go to fewer epochs.
- **Stride:** 48 if E\* ≤ 10, else 64 (the lead's first fallback).
- **Lag** stays 0 until the frame-to-send latency is measured.
- **Seeds** for the real fit: 0, 1, 2.
- **`hud_parity_sha256`:** the parity file passed to derive. That is a P2′ result if one exists by then, else run 1,
  which keeps the no-HUD candidate.
- **derive refuses** if:
  - p1 and p2 checkpoints of the same name differ;
  - a report is missing, not plumbing-scope, or off-plan: another cohort, another step-table sha256, or other
    arguments.
- **Scaling reading:** derive computes rule (a) (the frames-minus-twin gap positive and rising from ½) and tabulates
  what rules (b) and (c) need, for the lead to read.

**Budget.** About 7.9 h at most. That assumes every recorded minute counts (33.8 train and 13.7 dev minutes); the
driver re-estimates from the admitted tables. p1 is about 1.7 h. Transfer of the two new videos (35.6 GB) is about
20 min, and the caches about 10 min.
