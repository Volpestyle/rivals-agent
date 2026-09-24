# Inverse dynamics — inferring inputs from frames (VUH-1353)

Lane owner and single writer: `scoreboard-fix` (2026-09-23). This file holds design and measured facts. Status and
acceptance go on VUH-1353. Nothing here sends input to the game.

The design was reviewed by `fit-review` (`review-idm-design.md`, 2026-09-23): approve with required changes F1–F11,
all adopted by the lead. Each change is folded in below and tagged with its finding.

## Why

The in-client replay of a selected expert (`data/demos/replays/daymr-20260923-004325/`, VUH-1328) shows his own camera
and his full M&K HUD at native 2560×1440 and 120 fps. It carries no inputs. The recording is 34 min; the operator's cut
is ≈27 min, ≈19.5 min of that is on his POV, and ≈15.1 min is alive in-round play.

An inverse-dynamics model (IDM) is trained on James's own sessions, where frames and keyboard/mouse inputs are both
logged. It then labels the replay's frames with the inputs that most likely produced them, and the labelled replay
becomes imitation data.

This follows the VPT pattern. The IDM is non-causal: it may look at frames after the action. Any policy trained from its
labels stays causal (`docs/learning-plan.md`, "Camera motion and inverse dynamics"). VPT is a precedent, not a
guarantee: it used thousands of hours of contractor data, and we have 14.4 focused training minutes (below).

## What the IDM predicts

**The label unit** is one 60 Hz interval between frame *t* and *t+1*. The recordings are 120 fps, so every other frame
is used. The existing camera probe found that 10 Hz loses fast turns (34 % of intervals fit), and 60 Hz is where it
held (97–99 % direction agreement).

**The window is set from measurement, not assumed (F8).**
- Visible evidence can lag a press by more than the ±133 ms first proposed:
  - a HUD cooldown starts when a cast completes;
  - Get Over Here! travels 250 ms to 20 m, and Web Cluster up to 250 ms to 30 m;
  - the replay reflects server state a tick or two late.
- Before training, the delay from press to first visible evidence is measured per action on James's data, in-world
  and on the HUD (HUD readers).
- The window is set from that, likely asymmetric (for example −8/+30 frames).

**Outputs are semantic actions, not physical keys.** James's key codes are mapped to actions through his pinned bindings
(Shift = Web-Swing, E = Get Over Here!, F = Amazing Combo, LMB = Spider-Power, RMB = Web Cluster, Space = jump/flip,
Q = ultimate, V = melee, C = team-up, WASD = move; `docs/spiderman-kit.md`).

The expert's own bindings are printed on his replay HUD's ability row (keyframe k0414, 843 s): C (team-up), LSHIFT
(swing), **R** (Get Over Here!), F (Amazing Combo), Q (ultimate). His pull is R where James's is E, so a key-level label
would be wrong for the same action. This is the direct evidence for semantic outputs. The ability row shows only those
five; his movement, jump, fire and melee keys are unread.

| Head | Target per interval | Form | Model input (F3) |
|---|---|---|---|
| Camera | Yaw and pitch change, **in true degrees** (F4) | Discretised, μ-law bins plus an abstain bin | Stacked frame differences over the window at ≥ 448 wide through a small trainable conv. The geometric estimator's rotation runs as a separate arm. **No pooled DINO vectors for rotation**: a 384-d pooled 224² vector cannot carry sub-degree rotation |
| Locomotion | Held state of forward/back/left/right, relative to the camera | 4 × {held, not held, unknown} | Same motion input. The weakest head: momentum, air control and swing physics hide the keys |
| Action edges | Press onset of each **supported** action (F2) | Per action: onset / no / unknown | The native HUD crops (ability row, ammo, ult) plus the motion input. The HUD is **not** painted over, unlike `policy/frames.py`'s `GAME_CHROME` |
| Holds | Held state of primary (LMB), swing (Shift), crawl (Space) | Held / not / unknown | As for edges. Hold duration is a separate target from the press. A swing hold or tap label is used only where swing modes match (F4) |

**One spectator-UI rect set (F3).** `perception.camera_motion.REPLAY_UI_MASK` (rosters, FPS/kill-feed row, "Current
Player" box) is applied **identically to replay and live frames**, so both domains lose the same pixels. DayMR's Twitch
overlay rects in `policy/frames.py` belong to his stream, not the replay, and are not used here.

**Structurally unsupported actions (F2).**
- An action with fewer than **50 training positives** (pre-registered) always emits **unknown**, never "no".
- Today that is:
  - ult (Q): 0;
  - melee (V): 0;
  - team-up (C): 24, and pressed with no teammate, so no visible effect.
- A range-trained head that has never seen an action does not abstain; it learns "never", confidently. That would stamp
  "no ult" on every expert ult.
- On the pad side, ult (LS+RS) and team-up (Y) are also unexecutable: `ALLOWED = {A, X, LB, RB}`
  (`agent/controller.py`).

**A "no" needs support (F2).** A "no" label (no press, no hold) is emitted only where an out-of-distribution score says
the interval resembles training. Otherwise the head says unknown.

Every head can abstain. An unknown label is dropped from imitation, and never read as "no input".

Not predicted: menu, chat, ping and scoreboard keys, which are masked out of training. Also not predicted: anything
about targets or enemies. The IDM is target-agnostic on purpose, so it does not inherit the replay finder's failure
(below).

## Degrees, the gain and the pad's envelope (F4)

- **The gain's ground truth is the shared 360° calibration take.** It gives counts per 360° from a video-verified full
  turn, and James has been asked for it; the end-to-end fit's R8 asks for the same take. James's counts × that gain are
  the camera labels.
  - The geometric estimator is *checked against* the take, never used to fit the gain. Its degrees rest on a focal
    pinned by a pad 360° turn, so fitting the gain to it would pass any focal error into the labels and then cancel it
    in Gate 1.
- **The pad's reachable envelope** (`agent.controller.Cal`, measured at Linear curve, aim assist 0, H/V sensitivity
  265/75):
  - yaw up to **415°/s** at full stick, 6.9° per 60 Hz interval;
  - pitch up to **99°/s**, 1.65° per interval.
  - Low rates are coarse. Yaw is measured from 0.1 stick (18.5°/s, 0.31° per interval) upward; below that the map
    interpolates to 0.
  - Pitch has only two measured points (43°/s at 0.5, 99°/s at 1.0), so pitch below 0.5 stick is interpolation, not
    measurement.
- **Out-of-envelope labels are flagged, never silently clipped.**
  - A label beyond either cap carries `beyond_pad_envelope` and is saturated to the maximum rate in its direction, with
    the flag kept.
  - The training consumer decides whether to use it.
  - Every expert-label report gives the exceedance share. On James's own 33.3 ms steps it is **0.27 % to 12.07 %**,
    depending on the true gain (review F4 table, pitch dominating). These are the flicks imitation most wants, and the
    expert's are presumably faster.
- **`control_context` per device.** Each label source carries its device's swing mode (Simple Swing, Hold to Swing) and
  aim assist, beside the pad's own:
  - pad: Simple Swing OFF, Hold to Swing ON, aim assist 0;
  - James's KBM mode: pinned from the settings-screen look (recording protocol step 2). The report values so far are
    sensitivity 1.89/1.89, and hold swing and Easy Swing off.
  - Aim assist on the pad adds rotation nobody commanded, so it stays 0 wherever labels are compared.

## How the replay camera differs from live play

Rivals is third-person in both cases. The replay's "PLAYER POV" reproduces the target's over-shoulder camera and HUD.
It is not a first-person view, and it is not the pixels he saw. What differs, and what each difference does to transfer:

1. **The camera is reconstructed, not captured.**
   - The replay re-renders from recorded game state. The view rotation is plausibly replicated control rotation,
     updated at a replication rate and interpolated between updates. Mouse micro-motion may arrive smoothed, quantised
     or delayed differently.
   - **M1 looks for this on the replay itself** (F6), with signatures that do not depend on the player:
     - periodic kinks in angular velocity at a fixed period (a replication rate);
     - quantised pitch. As a hypothesis to test, not a Rivals fact: Unreal's stock replicated view pitch for other
       players' pawns is one byte, 360/256 = 1.40625° per step. The estimator resolves about 0.12° per pixel, so a
       lattice in cumulative pitch would show.
   - A spectral comparison against James's range play is **not** used: player, content and parallax all differ.
   - Only replay-of-self (Gate 2) isolates the effect with true inputs.
2. **Spectator rendering.**
   - Colours are fixed by side, not by POV. For a Team B target his own team is green, which is the colour our range
     perception reads as "enemy".
   - Enemies are outlined through walls he could not see live. That shifts the image distribution, and an outline seen
     through a wall can be read as the reason for a turn.
   - Use colour-jitter augmentation and hue-agnostic inputs, and mask outline pixels where they can be isolated.
3. **Follow switching and cuts (VUH-1328).**
   - The viewer resets its follow to Team A slot 1 at every round setup and after a cross-round seek. 202 s show
     another player and 200 s show no POV. Two setup stretches appear twice.
   - A follow change is a camera cut, and an IDM would read it as an impossible flick.
   - Every window is gated on the roster follow bar (`route-map/followed_player.json`) and on a cut detector. A window
     containing a cut, pause, rewind or speed change is not labelled.
4. **Viewer UI and clock.**
   - The timeline overlay (toggle N) covers the HUD for ≈110 s, and HUD reads there are confidently wrong.
   - Pauses, rewinds and reloads break the link between file time and match time.
   - James's viewer inputs (`logger_timeline.json`) are operator inputs, **never labels**; they only mark excluded
     intervals.
5. **HUD.**
   - Both players use the M&K HUD. Scale, crosshair and colour settings may still differ.
   - The HUD readers' replay failures (team-up digit on a light tile, locked uppercut icon, portrait hero gate) are
     masked before HUD events are used.
6. **Field of view (M2).**
   - Whether the replay renders at the viewer's FOV or the target's decides whether degrees on the expert are known.
   - It is settled by the **viewer-FOV re-record** (Gate 2, F5), not by self-calibration, which is ill-conditioned
     (the controller lane got 590–860 from shifts alone).
   - The coded focal fit (`camera_motion.replay_focal`) runs only after it recovers the known 465 px on James's live
     windows, and is second evidence at most.
7. **Networking.**
   - The replay reflects server-side state; the live view reflects client prediction.
   - Onsets can shift by a tick or two. This is measured in Gate 2, never assumed.

**Consequences of VUH-1354 (side-aware finder).**
- On the replay the range enemy finder scores P 0.053 / R 0.053. Its green band marks the target's own team, and
  recolouring alone reaches only P 0.32 / R 0.37.
- The IDM needs no enemy boxes, so this does not block motor labels.
- It blocks target-relative labels, which wait on VUH-1354. The first replay product is **motor labels only**.

## Training data

All of it is courtyard range, the Galacta pair, normal cooldowns and one map. Minutes are **focused logged input** (F7):

| Session | Focused min | Use |
|---|---|---|
| 20260922T032454 | 0.48 | train (group A, with 033319: same evening, OBS process 24328) |
| 20260922T033319 | 6.93 | train (group A) |
| 20260923T051828 | ≈7.0 | train (group B) |
| 20260923T171533 | 2.67 | **dev only** (F1) |
| 20260923T053616 | 2 | **not used by the IDM** (F1): the end-to-end fit's sealed take (VUH-1347), and the same evening and process as 051828 |
| 20260923T053929 | 1 | calibration only, if suitable |

**Sealed test (F1).** The IDM names no sealed session. Its sealed sessions are allocated by the lead from the campaign
at registration (the R10 mechanism). Until then its only held-out data is `171533`, and it is dev, not sealed.

**Scale.** Training is 14.4 min, about 52 k intervals at 60 Hz, in **two** independent groups.

**Tally (F11):** true presses (down edges), whole focused spans, no suitability cuts:

| Action | 032454 | 033319 | 051828 | 171533 (dev) | Train | Supported (≥ 50) |
|---|---|---|---|---|---|---|
| Swing (Shift) | 8 | 189 | 83 | 25 | 280 | yes |
| Pull (E) | 5 | 104 | 60 | 14 | 169 | yes |
| Combo (F) | 1 | 38 | 27 | 7 | 66 | yes (thinnest) |
| Spider-Power (LMB) | 10 | 112 | 110 | 24 | 232 | yes |
| Web Cluster (RMB) | 13 | 378 | 226 | 48 | 617 | yes |
| Jump (Space) | 16 | 375 | 361 | 88 | 752 | yes |
| Ult (Q), melee (V) | 0 | 0 | 0 | 0 | 0 | **no** |
| Team-up (C) | 0 | 0 | 24 | 8 | 24 | **no** |

**At the 3-hour mark:** about 8–10 sessions, leave-one-session-out with a real spread. Swings, falls, recoveries and
web-empty states should be covered, since the protocol asks for them.

**The domain gap that more range time does not close:** the replay is a Competitive Convoy match, with different maps
and lighting, human enemies, team fights, ults, deaths and spectator rendering. Real matches close it, and they are the
only source of Gate 2.

**Auxiliary:** the scripted pad recordings (≈67 k ticks) can pretrain the camera head through the turn map. That map is
a calibration model, not truth, so it is used for pretraining only, never for evaluation.

## The trust test, before any replay label is used

Two gates in order, then a downstream check. Every threshold below is registered on VUH-1353 before its numbers are
looked at.

### Gate 1: in-domain, on James's held-out sessions

- **Split by whole session.** Uncertainty is by session, not by correlated frames. Today the only held-out session is
  `171533` (dev).
- **Today's Gate 1 is a plumbing draft (F7).** The stop rules decide nothing below **30 held-out positives per action**
  (pre-registered). In `171533`, pull (14) and combo (7) are below it. Their 95 % intervals on recall at 0.5 are about
  ±0.26 and ±0.37.
- **Camera:**
  - per-interval yaw/pitch error in degrees against the logged counts × **the 360° take's gain**;
  - direction agreement;
  - error integrated over 0.25 s and 1 s;
  - the pad-envelope exceedance share.
  - Baselines: zero motion and the geometric estimator. The IDM must beat the estimator where it fails (fast turns,
    swings, ability-driven camera) and match it elsewhere.
- **Edges:** precision and recall at ±2 intervals (±33 ms) per supported action, plus the onset-error distribution.
  Baseline: HUD-reader cast events.
- **Holds and locomotion:** per-class F1 against the majority class and a last-value-held baseline.
- **Every head:**
  - a confidence threshold set before looking, with precision reported at the coverage it gives: the risk-coverage
    curve (F9);
  - calibration;
  - results by stratum: standing, walking, airborne, swinging, combo animation, ability-driven camera, death, chat or
    menu. Missing strata are reported as missing.

### Gate 2: replay transfer

**Two sources, each settling a different thing:**

- **Viewer-FOV re-record (F5, decisive for M2).** James re-records 10–20 s of the *same* DayMR replay segment at two
  viewer FOV settings.
  - If the image scale changes, the replay renders at the viewer's FOV, which is known, and M2 is settled.
  - If it does not, degrees on the expert need loop-closure calibration from his own footage.
  - The first-party outline-toggle evidence (`replay-research.md` §4) leans toward the viewer's settings.
- **Replay-of-self.** James records a real match with the logger on, then its replay from his own POV.
  - That gives replay-rendered frames with **true inputs**, the only direct measurement of camera smoothing (M1), lag
    and spectator rendering.
  - **Alignment uses independent anchors only:** the HUD round timer, kill-feed events and cooldown starts. **Never
    rotation**: cross-correlating the rotation series would absorb the lag the gate exists to measure.
  - Plan for **two matches on different maps**. One match is one unit, and a narrow pass on one match does not clear a
    head.

**Pass margins per head** (pre-registered, replay-of-self against the same session's live numbers):

| Head | Metric | Margin to clear |
|---|---|---|
| Camera | Median absolute yaw and pitch error on moving intervals (\|true\| ≥ 0.5°); direction agreement | Replay median error ≤ 1.25 × live, and direction agreement ≥ live − 5 points |
| Edges | F1 at ±2 intervals, per supported action | ≥ live − 0.10 per action; median onset shift ≤ 1 interval after anchor alignment |
| Holds | F1 per hold | ≥ live − 0.10 |
| Locomotion | Macro F1 | ≥ live − 0.10, and above the last-value baseline |

**The support gate (F5, promoted from a label-free check).** An expert interval is labelled only if it lies inside the
training support:
- estimated rotation rate within James's p99.5;
- an out-of-distribution feature score within James's dev p99.

The withheld share is reported per stratum. A head that fails any Gate 2 part does not label the expert's replay. Heads
pass or fail separately.

**Still open:** whether Practice vs. AI matches get replays (research §1). Quick Match and Competitive do.

### Gate 2 protocol: replay-of-self (2026-09-23)

This makes the Gate 2 outline above concrete for the model as built (`policy/idm/`). **Where the two differ, this
section holds.** Every number below is pre-registered here, before any replay-of-self recording exists. Nothing in
this section is code yet.

**What James records** (the paragraph in `docs/recording-protocol.md` is the version he reads):

1. **The live match.**
   - One real match as Spider-Man, recorded like a range session: the same OBS profile (2560×1440, 120 fps, MKV), the
     logger on, the same DPI, sensitivity, bindings and M&K HUD, and a Controls-screen look in the same sitting.
   - The mode is Quick Match, or Practice vs. AI if that match shows up in History with a replay (`replay-research.md`
     §1 leaves this open).
   - He notes the map and the time, so the History entry is unambiguous.
2. **The replay of it, the same day** (replays can break at a patch).
   - In the replay viewer, he follows **himself** in PLAYER POV, with the viewer at **his own settings**: the same FOV,
     HUD on, M&K HUD.
   - He records the whole match at **1× speed**, from the start to the end screen, with the logger on and the same
     OBS profile. His viewer inputs only mark excluded stretches; they are never labels.
   - No pause, seek, rewind, speed change or POV switch, and the timeline overlay stays hidden.
   - If the follow drops, for example at a round setup, he re-selects himself and says so. The stretch until then is
     excluded as a cut.
3. **The two-FOV re-record, on the same replay.**
   - He picks a 10–20 s stretch with plenty of turning and notes the in-game timer where it starts.
   - He records it at his FOV, changes only the viewer's FOV to a clearly different value, scrubs back to the same
     timer value, and records it again.
   - He reports both FOV values, then restores his FOV.
   - On his own match the true turn is known from his mouse counts and the gain, so this measures the FOV scale
     directly (M2). The DayMR re-record ask stays open for the expert's replay.
4. **Two matches on different maps.**
   - A match is one unit: each match's live and replay recordings are one session group.
   - The pair is **registered before anyone looks at it**, as its own `gate2` split. Every fit path refuses it, as it
     refuses test. It is opened once per frozen checkpoint, to score that checkpoint (a decision for the lead).

**Aligning the two recordings without rotation.**
- **Principle.** The live recording has the logger's clock, and the replay recording has its own. The map between
  them is fitted **only** from events both recordings show as HUD pixels, driven by server time rather than by the
  camera:
  - the **HUD match or round timer**: each displayed-second change is an anchor, one per second;
  - **kill-feed entries**: the frame an entry first appears;
  - **cooldown starts** (team-up, Get Over Here!): the replay-HUD lane's countdown reader, about ±0.015 s at full rate
    (`replay-hud.md` §6).
- **Never used:** rotation, optical flow, or any image correlation of the game view. Any of them carries the camera
  lag and smoothing this gate exists to measure.
- **Fit:**
  - The replay recording is cut into **playback spans** at every pause, seek, speed change, follow change or cut. The
    viewer logger and a cut detector mark these.
  - Per span: offset = the median of the (replay time − live time) differences over the timer anchors, with the slope
    fixed at 1.
  - The free-slope fit is reported as a check: a span with |slope − 1| > 0.001 is not used, because playback was not
    1×.
  - Kill-feed and cooldown-start anchors are checked against the timer fit, not fitted.
- **Span acceptance** (pre-registered):
  - at least 30 timer anchors;
  - the p90 |residual| of all anchors is at most 2 recorded frames (17 ms);
  - every kill-feed and cooldown anchor lies within 2 frames of the fit.

  A span that fails is excluded and counted.
- **Readers.** No timer or kill-feed reader exists yet. Both come before any Gate 2 number. Each is validated first on
  a small, inspected native-frame sample of James's live recording, where the logger clock checks it.
- **What the alignment leaves in.** The live frame shows the client's prediction; the replay shows server state. Any
  residual onset shift or camera lag after the anchor fit is **the effect being measured**. It is reported, never
  fitted away.

**What the IDM must reproduce.**
- **Truth** is the live logger's inputs for the match: its `rivals-idm-targets-v1` file, with 60 Hz intervals, press
  onsets, and camera degrees from the counts × the 360° gain (pitch derived, per row gain regime).
- **Frames.** The live frames are the live recording's own. The replay frames are the replay recording's frames at
  each interval's aligned times, chosen the way the live ones are: the last frame whose aligned time is at or before
  t0 and t1, with the same ±8-interval window.
- **One frozen checkpoint** from the real fit, trained on James's train sessions only (neither match, nor any range
  session recorded after the checkpoint), is run on both frame sets with its own support set and abstention bounds.
- **The paired set.** Scoring uses only intervals that are usable in the live targets **and** whose replay window
  lies wholly inside an accepted span, with James followed in PLAYER POV. The same intervals score both sides, so the
  only difference is the rendering.
- **The replay must reproduce the true inputs,** not the live predictions. The live numbers are the bar; the true
  inputs are the target.
- **Heads.** The heads the model has today are camera (yaw and pitch) and press edges per supported action. Holds and
  locomotion get their rows below once those heads exist; until then they are "no head", not a pass.

**Per-head metric and pre-registered margin** (`policy.idm_eval` names, replay against live on the paired set).

| Head | Metric | Clears when |
|---|---|---|
| Camera, per axis | `abs_error_moving_deg` median (\|true\| ≥ 0.5°); `direction_agreement_moving` | Replay median ≤ 1.25 × live median, and replay direction agreement ≥ live − 5 points |
| Camera confidence | `model_std_coverage` within 1σ; answered share | Replay 1σ coverage ≥ live − 10 points, and replay answered share ≥ live − 10 points |
| Edges, per supported action | F1 at ±2 intervals (`edge_metrics`); median onset error | Replay F1 ≥ live − 0.10, and \|replay − live\| median onset ≤ 1 interval. Only actions with ≥ 30 true onsets in the match's paired set decide; below that the action is "undecided" |
| Holds, locomotion (when the heads exist) | F1 per hold; macro F1 | Replay ≥ live − 0.10, and locomotion above the last-value baseline |

- **Matches.** A head clears only if **each** match meets its margin on its own. A pass pooled over both matches, with
  one match failing, does not clear. A match with fewer than **6,000** paired, scored intervals (100 s) is undecided
  for every head.
- **Reported, not gated:**
  - the camera error by true gain regime and speed band;
  - the 0.25 s and 1 s summed error;
  - the lag, in intervals, that minimises replay yaw error. This measures M1's smoothing and delay; it is never used
    to align;
  - the replay M1 signatures (kink period, pitch lattice) against the live ones;
  - pitch, which is scored against derived pitch and labelled so.
- **What passing means.** A head that clears may label the expert's replay, still behind the support gate. A head
  that fails labels nothing. Heads pass or fail separately.

**The withheld-share report.** Every 60 Hz interval of each replay recording falls in exactly **one** bucket, first
match wins, in this order:
1. **no alignment:** outside every accepted span, or in a rejected span;
2. **not his POV:** follow lost, a cut, the timeline overlay, a menu;
3. **not usable live:** focus loss, gaps, chat or menu, or not accepted in the live targets;
4. **outside support:** the support gate. The estimated rotation rate is above James's train p99.5, or the frozen
   out-of-distribution score is above James's dev p99;
5. **scored.**

Within "scored", the IDM's own abstention is reported **per head and per action**.
- **Units:** counts and shares per match, and per stratum where the stratum is known (standing, walking, airborne,
  swinging, combo animation, ability-driven camera, death or spawn, menu). A stratum that is missing is reported as
  missing.
- **The live recording's buckets** are reported beside them, so the paired set's size and the cost of each exclusion
  are visible.
- **The support gate's two thresholds** are computed from James's train and dev sessions and frozen with the
  checkpoint, before Gate 2 is opened.

### Downstream check (F9)

- **Relabel test.** At 3 h, relabel James's held-out sessions with the IDM, and train the same BC policy on IDM labels
  and on true labels. The metric gap is the cost of using IDM labels.
- **Abstention is not neutral.** Report coverage per action and stratum on the expert replay, and name the behaviours
  the replay cannot teach because the IDM abstains on them (swings, flicks, unsupported actions).

**Label-free checks on the expert replay** (supporting evidence, not gates):
- inferred edges against the HUD event stream;
- the abstention rate per stratum;
- camera rotation against the geometric estimator;
- no labels inside cuts or follow gaps.

## Failure modes

- **Follow switching and cuts:** fake flicks. Gate on the follow bar plus the cut detector.
- **Spectator colours and x-ray:** colour augmentation and outline masking; Gate 2 measures what remains.
- **Spectator UI out-voting the world:** the shared `REPLAY_UI_MASK`, a per-window `window_overlay`, and two estimator
  rules:
  - **per pair,** zero inlier flow while the centre of the world changed, or with inliers only in the border strips, is
    withheld;
  - **per window,** zero flow on more than half the pairs is invalid.
  - Withheld rotations are unknown, never 0.
- **Replay timeline overlay, pause, rewind, speed change:** masked from the operator events and a template detector.
- **Replay camera smoothing or quantisation:** M1 on the replay's own signatures, then Gate 2. If present, the camera
  head predicts the replay's rotation and says so.
- **Unsupported actions:** always unknown (F2).
- **Out-of-envelope rotation:** flagged and saturated, with the share reported (F4).
- **HUD differences:** mask the known bad reader cases.
- **Patch drift:** every source carries its build (VUH-1324). Train and label within one build family, or report the
  difference. The replay is build 25364676 / 1.1.3870120.
- **Ability-driven camera** (pull, combo launch): the camera moves with no mouse input. Tested as its own stratum and
  never relabelled as input.
- **Momentum and air control:** WASD often has no visible effect. Abstain.
- **Chat typing:** chat-open intervals are excluded from training.
- **Different bindings or swing mode:** semantic outputs absorb bindings. Swing labels are used only where modes match.
- **Overfitting to one map and two bots:** Gate 2 on two real matches.
- **Label leakage:** windows never straddle the split, and sessions never straddle it.

## Measured

**2026-09-23: first M1 attempt, invalid as a rotation measurement.**
- **Method:** 8 windows of 3 s, on target, timeline hidden, alive (file t 597, 702, 843, 1119, 1272, 1428, 1729,
  1955 s). Decoded at 120 fps to 1280×720 grey, through `perception/camera_motion.py` without the replay masks.
- **Result:** every window fits zero motion: `flow_px` 0 on 99–100 % of pairs, 700–1,200 inliers out of 1,500 features,
  while the median frame difference is 6–13 grey levels.
- **Leading hypothesis (F6), not yet shown.** Static spectator UI outside the pad-HUD masks, feature-rich and still, wins
  every fit:
  - team rosters down to y ≈ 0.20 (the mask stops at 0.12);
  - FPS readout and kill-feed row, y ≈ 0.19–0.24;
  - "Current Player" box, x ≈ 0.9–1.0, y ≈ 0.58–0.69.
- These rects come from **one keyframe** (k0414). The hypothesis stands only when the masked rerun shows non-zero flow on
  the same eight windows. Each window's own UI is also checked, because kill-feed rows grow and the ping box may move.
- **Valid from the same run:**
  - near-identical consecutive frames are only 1.7–4.5 % of pairs, so the replay renders fresh images at about 96 % of
    120 fps;
  - the client's FPS readout shows 193 at 843 s.
  - This is render cadence, not camera-angle cadence.
- **The expert's bindings** are on his HUD: C, LSHIFT, R, F, Q (above).

**2026-09-23: estimator changes for the rerun** (`perception/camera_motion.py`, tests in `tests/test_camera_motion.py`,
all synthetic):
- `REPLAY_UI_MASK` (`--spectator-mask`), used on replay and live alike.
- `window_overlay`: `static_mask` learned from a window's own frames.
- The per-pair rule, `pair_abstain`:
  - zero flow with the centre changing by more than 4 grey levels, or with ≥ 95 % of inliers in the border strips, is
    withheld;
  - **both thresholds are provisional** until validated on James's live fast turns with known mouse counts;
  - `Estimator.step` applies it, so the range probe (`run_proxy`) now withholds such pairs too.
- The window rule, `checked`: more than half of the fitted pairs at zero flow withholds the whole window.
- The gated focal fit, `focal_fit` / `replay_focal`.
- **Superseded by review C1/C2** (`review-camera-motion.md`, below). The world-change rule withheld true stills on range
  footage.

**2026-09-23: review C1–C6 applied** (not committed; the reviewer re-checks before landing):
- **C1, the zero is decided by the world's own matches.**
  - A zero-flow pair is kept only if at least 20 ratio-tested matches lie in the centre strips (STATIC_CENTRE minus the
    body's columns) and their median displacement is ≤ `ZERO_FLOW_PX`.
  - It is withheld if there are too few such matches, or if they moved.
  - The border rule (≥ 95 % of inliers in the border strips) is checked first.
  - `world_diff` is a diagnostic column only.
- **C2, sub-window verdicts.** The window verdict runs over fixed 3 s sub-windows (`checked_windows`) in `run_video`, and
  counts only zeros that C1 could not confirm.
- **C4:** `last_matches` is reset at the top of `compare()`.
- **C3:** tests on images, 34 passing, including:
  - a still camera with a moving 100 or 160 px patch, kept;
  - the overlay-won pair, withheld by the border rule, and by the centre test alone;
  - the review's two real baseline1 pairs, hash-pinned and corpus-marked: 1398 kept, 97 withheld;
  - sub-window and end-to-end `run_video` tests where a mostly-still clip keeps its turns;
  - focal tests labelled as code checks;
  - a C4 test.
  Docstrings now call the spectator-UI cases mechanism reproductions.
- **C5:** moot, because `world_diff` no longer decides anything.
- **C6:** the CLI summary now reports `reported` and `withheld` separately. The l2 lane's published probe tables were
  produced at `2920ceb`; with these rules the working tree yields different coverage.
- **Regression bound (lead: the still stratum on baseline1/3 loses ≤ 2 points against HEAD).** Measured with the
  reviewer's method: proxies, lag 30 ms, 60 sampled pairs per stratum with seed 0, a fresh estimator per pair, the
  proxy's static mask, plus the full still stratum.

  | Still stratum | HEAD | Fixed | Points lost |
  |---|---|---|---|
  | baseline1, all 806 | 0.994 | 0.948 | **4.59, fails** |
  | baseline3, all 789 | 0.996 | 0.977 | 1.90, passes |
  | baseline1, sampled 60 | 1.000 | 0.933 | 6.67 |
  | baseline3, sampled 60 | 1.000 | 0.983 | 1.67 |

  - Baseline1's 37 withheld stills: 32 "contradicted by the centre's own matches", 5 border-only.
  - Other sampled strata lose 0–8.3 points.
- **Diagnosis** (baseline1 still stratum, from saved frames without the proxy overlay, so its counts differ):
  - **Keypoint quantisation.** Most "contradicted" pairs have centre matches moving 0.2–1.7 px, with a centre-only
    rotation of 0.01–0.25° and 80–100 % rotation-consistent. That is the ORB keypoint grid (1 px ≈ 0.12° at 465 px),
    well above the 0.05 px bar.
  - **Real motion.** A second group moved 2–7 px (0.2–0.8° per interval), a rotation-consistent 2–7°/s under no
    command, plus clear failures of 17–28 px (pairs 97, 99, 103, 1377). HEAD's zeros there were probably wrong.
  - The l2 "still" stratum means no command, not a still camera.

**2026-09-23: lead decision on the C1 bar, option (c)** (history; superseded by option (i) below, and the
`CENTRE_CONSISTENT` constant it describes no longer exists).
- A zero-flow pair is kept only when all of these hold:
  - at least 20 centre matches;
  - a rotation fitted to the centre matches alone is **< 0.25°** (`CENTRE_STILL_DEG`);
  - that rotation explains **≥ 80 %** of them (`CENTRE_CONSISTENT`).
- A larger centre rotation, an inconsistent fit or no fit withholds the pair as "contradicted". The border rule and the
  20-match minimum stay.
- This separates ORB keypoint quantisation (about 1 px, 0.12°) from real motion. Synthetic centre shifts: 1–2 px kept,
  5 px withheld. On the review pairs, 1398 is kept (0.011°, 90 %) and 97 withheld (no consistent fit).
- The centre fit uses its own seeded random generator, so the main fit's sequence is unchanged.
- **HEAD's l2 "still" stratum is "no command", not "still camera".** HEAD's coverage there counted zeros the world did
  not confirm, so it overstates correct zeros. The 2-point bound was first re-scoped to the pairs the centre fit calls
  still. That subset is defined by the rule under test, so it is circular (review re-check B1). It is replaced by a
  by-eye audit bound (below).

**2026-09-23: option (c) measured** (`camera_motion.py` sha256 `a45fe129…`, 37 tests passing).

**Regression**, the reviewer's method; HEAD against fixed, coverage in points lost:

| Still stratum | All "no command" pairs | Pairs the centre fit calls still (bound ≤ 2) |
|---|---|---|
| baseline1 | 0.994 → 0.948, **4.59** (806) | 0.994 → 0.987, **0.65, passes** (774) |
| baseline3 | 0.996 → 0.973, **2.28** (789) | 0.996 → 0.996, **0.00, passes** (771) |

- By construction the subset drops the "contradicted" zeros, so its loss is border and too-few withholds only.
- **Attack stratum (sampled):** zeros kept are baseline1 **2 of 9** and baseline3 **1 of 10**.
  - That is fewer than the strict bar (4/9, 6/10), and back near the rejected world-change rule (2/9, 0/10).
  - Combat pairs with effects and bots in the centre fail the 80 % consistency test, even when the static majority
    fits zero rotation.
  - The review's attack-stratum bias therefore recurs under (c). **Decided below: option (i).**

**2026-09-23: lead decision, option (i).**
- A zero-flow pair is kept when the centre-only rotation is **< 0.25°** and it explains **≥ 20 centre matches**
  (`Step.centre_inliers`).
- The explained share (`centre_consistency`) is a diagnostic column only. In combat, moving effects and bots lower the
  share while the static majority still fits zero.
- Test: a still camera with 45 % of the centre moving 15 px has a 0.73 share and a 0.002° rotation, and is **kept**.
- The border rule and the 20-match minimum stay. 38 tests pass.

**M1 on option (c)'s bytes** (`a45fe129…`; history) (12 windows, same as before; 36 s of video; 530 s wall, 479 s Python CPU; ≥ 12.6 GB free,
paused whenever another decoder ran):
- **All 8 replay windows are valid.** Unconfirmed zeros are 0–4.6 %, except window 597 at 21.7 %.
- **Window 597** is a slow, nearly still stretch (median 12°/s, p95 61°/s). Its zeros are mostly confirmed now, which
  weakens the KO-banner hypothesis.
- Rates in the other windows are unchanged from the pre-C1 rerun.
- **No replication signature:** the kink autocorrelation is unchanged. The pitch-lattice p-values carry the same
  autocorrelation caveat, and the random-period control from the pre-C1 run applies.
- **Live, against mouse counts** (moved = ≥ 20 counts, still = 0 counts, x and y, at the fitted lag):
  - of 87 moved pairs with zero flow, **75 withheld (86 %)**;
  - of 276 still pairs, **231 reported and 45 withheld**, 44 of them in window 347 (42 "contradicted").
  - In window 347, zero mouse input with the centre moving could be ability-driven camera or failed stills; it is not
    yet separated.
- **M2:** the live gate refuses again (515 px, basin 427–637 px).

**2026-09-23: M1 rerun with the masks.**
- **Setup:** the same 8 replay windows plus 4 live windows (051828 t 39, 117, 245, 347), with `REPLAY_UI_MASK` and a
  per-window `window_overlay` on both, and the per-pair and window rules. Uncommitted post-review `camera_motion.py`
  (sha256 `aa2fd71c…`); its code review was still pending.
- **The UI hypothesis holds.** Seven of eight replay windows are now valid:
  - zero-flow pairs are 2.6–12.1 % (99–100 % before);
  - median rotation is 29–68°/s, and p95 198–389°/s.
- **Window 597 stays invalid** (59 % zero flow, 200 pairs withheld). Its keyframe at 598.4 s shows a "KO" elimination
  banner at x ≈ 0.78–1.0, y ≈ 0.43–0.53, outside the mask. That is a candidate cause, not shown; the rule withheld the
  window as unknown.
- **Replication signatures on the replay: none detected.**
  - The autocorrelation of |Δ angular velocity| decays without a peak at lags 1–12 frames, so there is no periodicity
    between 10 and 120 Hz. Slower rates are not tested by 3 s windows.
  - For the 1.40625° pitch lattice, raw Rayleigh p-values reached 1e-5 on two windows. But against 200 random control
    periods the lattice period ranks between the 3rd and 98th percentile, and other periods score higher, so those
    p-values are autocorrelation artifacts.
  - Integrated pitch also carries estimator drift, so this test is weak: not detected, not ruled out. Replay-of-self
    stays the test.
- **The per-pair rule on live, against logged mouse counts** (moved = |dx| ≥ 20 counts per 1/120 s at the fitted lag;
  yaw only):
  - of 85 moved pairs with zero flow, **76 were withheld (89 %)**; 9 were missed;
  - of 771 still pairs, **114 were withheld (15 %)**, 93 of them in window 347.
  - That is conservative in the intended direction: unknowns, not zeros.
  - The thresholds stay provisional. Two live windows still had 20 % and 42 % zero-flow pairs under the masks, which
    means static content in range frames that is not yet identified.
- **Mouse against estimated yaw on live:** correlation 0.79–0.88. The best lag is 1–5 frames (8–42 ms at 120 fps) and
  varies by window. This is an estimator-side number, not ground truth: the gain waits on the 360° take.
- **Render cadence:** replay 95.5–98.3 % fresh frames, live 98.9 %.
- **M2: the gated focal fit refused, as designed.** On 268 live pairs the fit gives 515 px with a basin of 427–637 px
  (41 % wide), so it misses the calibrated 465 px and cannot tell focal lengths apart. The replay focal was not fitted.
  This matches the controller lane's ill-conditioning; the viewer-FOV re-record is the M2 test.

**2026-09-23: review re-check applied, measured on the landing bytes** (`camera_motion.py` sha256 `3220a4db…`;
`review-camera-motion-2.md`; scripts and results in `docs/evidence/idm-camera-m1-20260923/`):
- **B3.** A zero-flow pair whose centre-only fit is strongly supported (≥ 50 inliers, ≥ 80 % consistent) and rotated
  ≥ 0.25° reports that rotation, flagged `source="centre"`.
  - Synthetic tests are exact: 0.8° reports 0.801°, and 2.0° reports 2.000°.
  - The audited moving range pairs 721, 1329 and 2396 are pinned by hash.
- **B2.** When the border rule would fire, ≥ 10 centre matches with median ≤ 1 px keep the zero (synthetic test).
  - It does **not** recover the audited still 2510. The floor gives no features, and its only centre matches are the
    bot's name plate and the character's leg, which move.
  - It is pinned as a strict expected failure: the known false withhold.
- **Tests:** 45 pass, plus 1 strict expected failure.
- **B1, the audit bound**, replacing the circular subset.
  - Every withheld no-command zero (baseline1 9, baseline3 8; the whole population) was labelled by eye, with frame
    hashes.
  - baseline1: 3 still (2510-2512); baseline3: 1 still (853).
  - False withholds: **0.37 and 0.13 points** (Wilson 95 % upper bound 0.72 and 0.48) against the 2-point bound:
    **passes**.
  - Every other withheld pair shows scene edges across the frame, meaning the camera moved.
- **Regression, full no-command stratum** (HEAD → landing):
  - baseline1 0.994 → 0.983 (1.12 points), with 13 zeros now reported from the centre;
  - baseline3 0.996 → 0.986 (1.01 points), with 5 centre-sourced.
  - Attack zeros (sampled): baseline1 kept 3, centre-sourced 2, withheld 4 of 9; baseline3 kept 4, centre-sourced 2,
    withheld 4 of 10.
- **M1 replay:**
  - all 8 windows are valid; window 597 has 22 centre-sourced pairs;
  - no kink peak;
  - no pitch lattice: with the random-period control on these bytes, 1.40625° ranks at the 0th–98th percentile.
- **M2:** refused again (515 px, basin 427–640 px).
- **Live, against mouse counts: the finding that matters.**
  - Zeros reported while the mouse moved ≥ 20 counts in the interval: **36** on the landing bytes, against **12** under
    (c).
  - At ≥ 60 counts (about 1.3–1.7°): **12** against **3**.
  - Ten of those 12 are real turns whose zero (i) keeps. Their centre fit is < 0.25° with 54–275 inliers, but only
    49–83 % consistent. On live turns the zero consensus comes from content fixed to the screen or the character while
    the world rotates; (c)'s 80 % share withheld 9 of those 10.
  - The other two are fully consistent zeros during 155–168-count moves, probably repeated capture frames. (c) reported
    them too.
  - Still pairs withheld: 21 of 276, against 45 under (c).
- **B3 against the mouse:** only 10 centre-sourced live pairs.
  - They agree in direction (correlation 0.88–0.91, 75–83 % sign agreement), but they are imprecise: median error
    0.35–0.46° against median magnitudes of 0.48–0.75°.
- **Open for the lead before landing** (decided below as (a)):
  - On the range proxies, (i) fixes combat zeros. On live turns it keeps wrong zeros that (c) withheld.

**2026-09-23: lead decision (a), measured; these are the landing bytes** (`camera_motion.py` sha256 `4b5714b8…`;
tests: 50 passing plus 1 strict expected failure):
- **The outlier refit.**
  - After the centre fit's zero consensus, a rotation is fitted to its outliers.
  - If that rotation is ≥ 0.25° with ≥ 20 inliers, including ≥ 5 on each side of the frame, the world turned and the
    zero is contradicted.
  - With ≥ 50 inliers the rotation is reported (`source="centre"`); otherwise the pair is withheld.
  - Combat content on one side keeps its zero (tested on both sides).
  - **Known limitation, pinned by a test:** one rigid object spanning both side strips reads as a world rotation.
- **Repeated frames are withheld.**
  - OBS re-encoded repeats differ by only ~0.07 grey levels on average, but so does a small animation, so the mean
    cannot decide.
  - The largest 16×16-block mean change decides (≤ 8 is a repeat): re-encode noise ≤ 4.5, a 12 px dot appearing 17.
  - Live: 17 pairs withheld in 12 s, almost all while the mouse moved, so they are true repeats.
- **Live mouse truth** (zeros reported while the mouse moved, at each window's fitted lag):

  | Mouse counts in the interval | (c) | (i) | **(a), landing** |
  |---|---|---|---|
  | ≥ 20 (722 moved pairs) | 12 | 36 | **13 of 722** (1.8 %) |
  | ≥ 60 (319 moved pairs; about 1.3–1.7°) | 3 | 12 | **7 of 319** (2.2 %) |

  - **(a) does not reach (c) at ≥ 60 counts: 7 against 3.** It lands with that cost recorded (lead decision).
  - The 7 have 54–184 centre inliers at 49–72 % consistency. Their outliers form no single rotation on both sides,
    likely world parallax while the character moves and turns, which a rotation-only refit cannot model.
  - Still pairs (0 counts): **253 of 276 reported; 23 not reported (22 withheld + 1 unfitted)**. Under (c): 231
    reported; 45 not reported (44 withheld + 1 unfitted).
- **B3 against the mouse:** 24 centre-sourced live pairs, including the outlier-refit rotations. Sign agreement
  78–93 %, correlation 0.62–0.80, median error about 0.5° against median magnitudes of 1.1–1.3°. Directional,
  imprecise; not validated on replay, which has no mouse truth.
- **Audit bound (B1)** on these bytes: withheld no-command zeros are baseline1 10 and baseline3 9, the whole
  population, labelled by eye.
  - Still (false withholds): baseline1 4 (2510–2512, plus 1476 from the new refit); baseline3 2 (853, plus 1915 from
    the new refit).
  - **0.50 and 0.25 points** (Wilson 95 % upper bound 0.85 and 0.62), against the 2-point bound: **passes**.
  - The refit's own false positives (1476, 1915) are moving bots on both sides and an animated glow, the limitation
    above.
- **Regression, full no-command stratum** (HEAD → landing): baseline1 0.994 → 0.981 (1.24 points), baseline3 0.996 →
  0.985 (1.14 points). Attack zeros are unchanged from (i).
- **Replay:** the 8 windows were not rerun for (a) (lead decision). Their results on the (i) bytes stand:
  `m1-replay-results-option-i.json`.

**2026-09-23: the data step, as code** (no model yet):
- **Replay camera labels:** `scripts/replay_camera.py`.
  - It fills the replay step table's yaw and pitch from the estimator's replay run (`video --spectator-mask`) through
    `scripts/replay_steps.py` `fill_camera`, unchanged.
  - Default sources are "main" only; "centre" pairs are opt-in.
  - Every row gets a `camera` note: the source where filled; where unknown, why (no pair, a gap, a withheld pair with
    the estimator's own reason, a source not accepted).
  - The header records the run and the estimator's sha256. The output is checked with the step-table contract and
    written as a new file.
  - Tests: `tests/test_replay_camera.py`, 6.
  - **Not run on the capture yet:** the replay run over the whole capture is a decode.
- **Human IDM targets:** `policy/idm_targets.py`, format `rivals-idm-targets-v1`, spec in the module docstring.
  - Every admitted 30 Hz step row is split into two 60 Hz intervals, binned with the intake's own rules from the
    session's imported demo. The halves must add up exactly to the admitted row (presses, releases, holds, mouse
    counts), or the build refuses. The video is not opened.
  - Camera degrees use the table's calibration: yaw 0.0330738°/count from the 360° take, pitch derived equal,
    `accel_on` true. `beyond_pad_envelope` is flagged per interval, never clipped.
  - The reader refuses a test split before any row, and checks masks, hold arithmetic and degrees.
  - `supported_actions` applies F2 over train rows; `target()` makes unsupported actions unknown.
  - Tests: `tests/test_idm_targets.py`, 10.
- **Built for the four admitted sessions** (051828, 171533, 200129, 205528; all train), `data/idm/targets/`
  (gitignored):
  - **170,976 intervals, 170,032 usable** (accepted, gap-free, normal); every one of the 85,488 parent rows matched
    exactly.
  - Camera known on every usable interval. 8,999 are beyond the pad envelope (5.3 %).
  - Training presses:

    | Action | Presses |
    |---|---|
    | move_forward | 997 |
    | move_left | 1,244 |
    | move_back | 778 |
    | move_right | 977 |
    | jump | 2,186 |
    | web_swing | 573 |
    | get_over_here | 159 |
    | amazing_combo | 368 |
    | spider_power | 635 |
    | web_cluster | 1,322 |
    | goh_targeting | 51 |
    | team_up | 168 |
    | ultimate | 9 |
    | melee | 23 |
    | simple_swing | 16 |

  - **Unsupported:** ultimate, melee and simple_swing by count (floor 50, pre-registered in the spec).
  - **Lead decisions, 2026-09-23:**
    - team_up is **supported**: 168 presses, and a visible range effect (the icon turns gold, hp 250 → 300, a 10 s
      cooldown); the replay HUD reads 22 team-up events on DayMR. Its match-time effect differs.
    - goh_targeting is **supported** by the floor: 51 train presses; the earlier declaration is dropped. melee (23)
      stays unsupported.

**2026-09-23: data review fixes** (`review-idm-data.md`: the join and the calibration confirmed):
- **S1, sealed before any read.** `build()` loads the pinned denylist (`57cfe01f`) and refuses a denylisted id before
  forming any path. It then reads only the step header line (media hash and split), and runs the intake's
  `check_registry` (denylist first) before opening the demo. `load()` refuses a denylisted id or media. Tested with a
  fake sealed folder: nothing under it is opened.
- **S3, the acceleration caveat per row.** Each interval carries `mouse_rate_cps` and `gain_regime`: "calibrated" up to
  1,400 counts/s (the top of the calibration turn's measured speeds), "extrapolated" above.
  - `target()` gives a per-row camera sigma: half a count, plus 20 % of the degrees when extrapolated (the calibration
    record's slow-to-fast drop, provisional until a fast-turn calibration). It also gives `degrees_kind` and
    `pitch_derived`.
  - Gate 1 reports camera error by regime and by speed band (≤ 1×, 1–4×, > 4× the turn's 915 counts/s).
  - Over the four sessions, **40.1 % of usable intervals are extrapolated, carrying 90.2 % of all yaw counts**.
- **S2:** `target()` refuses a non-usable row, and `training_rows()` gives the usable ones.
- **S4:** tests pin `DECLARED_UNSUPPORTED == {}`, the floor of 50, and team_up and goh_targeting counting by presses.

**2026-09-23: Gate 1 evaluation harness** (`policy/idm_eval.py`, no model; tests `tests/test_idm_eval.py`, 14):
- **Inputs:** held-out target files and a predictor (per row: yaw, pitch, and a press probability per action; None =
  abstain). Results per session and pooled.
- **Camera, per axis:**
  - error against the calibration truth: median, mean and p90, all and split moving (≥ 0.5°) / still;
  - direction agreement on moving rows;
  - summed error over 15- and 60-interval windows (0.25 s and 1 s);
  - abstention rate and envelope share.
- **Edges, per supported action:**
  - one-to-one matching inside a run within ±2 intervals (the label-precision window);
  - precision, recall, F1, onset error and abstention rate;
  - held-out positives, and "decides" only at ≥ 30 (F7).
- **Baselines:**
  - zero;
  - persistence. For camera it uses the previous interval's true rotation: a strong smoothness reference built from
    labels, not a floor. For edges a persisting hold has no onset. Repeating the previous press would leak the label
    through the ±2 window (F1 = 1), and a test pins that it does not.
- **Plumbing run** (171533 as a stand-in held-out against the other three; it is train in the corpus, so this is not
  a gate result). Yaw on moving intervals:
  - zero: median error 1.22°, 1 s summed error 12.6°;
  - persistence: 0.20°, 99.3 % direction agreement, 1 s summed error 0.36°.
  - Edges: both baselines have F1 0. Five actions have ≥ 30 held-out positives there (move_left, move_back,
    move_right, jump, web_cluster).

**2026-09-23: the IDM model as code** (`policy/idm/`, no real training; tests `tests/test_idm_model.py`, 10,
synthetic fixtures only):
- **Frame store** (`frames.py`, "rivals-idm-frames-v1"): per session, grey frames at the motion width and the native
  80×200 HUD crops, keyed by video frame index, as uint8 arrays with sha256s in a manifest (`verify=True` checks them).
  Filling it from the video is a decode job and is not written yet.
- **Model** (`model.py`, F3): the motion input is the 2W = 16 differences of the grey frames at the interval's end
  frame ±8 intervals (±16 video frames), 448×252, through a small trainable conv (4 stride-2 layers, GroupNorm).
  The native HUD crops at the start and end frames go through a second small conv that feeds the edge head only.
  - **Heads:** a press-onset logit per action; camera yaw and pitch means in degrees, plus a log-variance each.
  - About 420 k parameters. A width under 448 is refused unless the config is marked test-scale, and the fit CLI
    refuses test-scale.
- **Loss:** masked BCE on press onsets. The mask is `held_known` AND supported, so an unsupported action contributes
  neither loss nor gradient (tested). Camera loss is a Gaussian NLL whose variance is the model's own plus the
  target's sigma² (`idm_targets.camera_sigma`), so an extrapolated row weighs less. It trains on `training_rows` only.
- **Trainer** (`train.py`), with range_bc's reproduction discipline:
  - seeded `random` and torch, deterministic algorithms, the permutation `Random(seed*1000003+epoch)`, AdamW, clip 1;
  - train files only; checkpoints written once;
  - a byte-identical checkpoint test on CPU (same seed gives the same sha, another seed differs);
  - a write-once canonical report carrying the target and frame-store shas, git commit and history, which refuses
    `test_opened`.
- **Abstention** (pre-registered here):
  - unsupported actions are always None;
  - a press probability inside (0.35, 0.65) is None;
  - a camera axis whose **total** std exceeds its predicted regime's bound is None: 1° when calibrated, 3° when
    extrapolated (see the review fixes below);
  - a row lacking any frame of its window is fully abstained.
- **Evaluation:** `gate1()` runs `idm_eval.evaluate` for the model, zero and persistence on the held-out files, which
  includes the camera error by gain regime and speed band.

**2026-09-23: model review fixes** (`review-idm-model.md`: land as dev code after K1 and K2; tests 16):
- **K1, provenance in the checkpoint.** The checkpoint meta and the report carry:
  - the support set with the train press counts;
  - the code closure (range_bc's `code_closure`: the LF sha256 of every imported repo module);
  - each target file's sha256, taken as it is loaded, with its calibration and `media_sha256`;
  - the frame stores' array hashes, and the seed.

  `checkpoint_bytes` refuses a meta that lacks any of these, or whose support set differs from the model's. The
  predictor and `gate1` take the support set from the model (fit or checkpoint) and refuse a caller's that differs.
  `run_fit` calls `require_committed` on the closure before reading anything: `git_commit` ignores untracked files,
  so an uncommitted package would otherwise look clean.
- **K2, pixels bound to the targets.** A frame store records each frame's pts. `bind()` refuses the whole file when:
  - the store's `media_sha256` differs from the target header's;
  - any frame both name carries a different pts;
  - the header's frame period is not the 120 fps the offsets assume.

  Opening a store refuses a denylisted session id or media. The decode job, when written, must check the denylist
  before it decodes.
- **Masked-loss guard.** Masked camera targets and sigmas are zeroed before the NLL. A NaN or inf in a masked slot
  otherwise left the loss finite but made every parameter gradient NaN (`torch.where`'s backward is 0 × NaN). Tested:
  the gradients are finite and equal to a clean batch's.
- **Camera uncertainty used at prediction.** Each axis reports its **total** std, sqrt(model variance + the label
  sigma of the predicted value in its predicted gain regime), plus that regime, which comes from the predicted counts'
  rate.
  - The abstention bound is per regime, pre-registered: 1° calibrated, 3° extrapolated. Extrapolated labels are known
    to about 20 %, so 3° admits up to ~15° per interval with a sure model.
  - Gate 1 adds, per true regime and axis, the abstention rate and the stated std's coverage (share of |error| within
    1 and 2 std).
  - `pitch_truth` labels pitch as scored against derived equal-sensitivity degrees.

**2026-09-23: the frame-store decoder** (`policy/idm/decode.py`; tests `tests/test_idm_decode.py`, 10, on range_bc's
synthetic FFV1 fixture):
- **Inputs, all pinned before any decode:**
  - the target file (read by `idm_targets.load`, which refuses sealed sessions and the test split);
  - the admitted step table and the imported demo, whose sha256 must equal the targets' `source` pins;
  - the original, whose bytes must equal `media_sha256` (or be a pinned relocation, through intake's `check_media`).
- **pts:** the imported demo's decoded frame table gives every frame's pts, not only the rows'. Each decoded frame's
  showinfo pts, each target row's frame and each step-table anchor must all agree with it, and so must the timebase.
- **What it decodes:** each usable row's ±8-interval window (every 2nd video frame) and its start and end frames. As
  range_bc's cache does, it pins the YUV → RGB conversion and uses area+bitexact scaling to 448×252, then an integer
  luma in numpy. The HUD crop is byte-identical to the range cache's (tested).
- **Rules:** stores are built on the Mac only. They are streamed and hashed as written, and the manifest is written
  last. `inspect` writes a few frames as PNG images (stdlib only) for a person to check before the other stores are built.
- **Checked on the real inputs, with no decode:** all four sessions pass the pre-decode checks. The stores hold
  25,116 / 9,276 / 95,852 / 39,868 frames (051828 / 171533 / 200129 / 205528), **27.4 GB** in all. Each session's
  frames form one arithmetic run, so the select expression is a single term.
- **C1 fixed** (review of `d402c74`): `train.py` imports `agent.human_intake` and `agent.human_demos` before its first
  closure is taken. An end-to-end `run_fit` test (full-scale config, smoke) asserts that the committed closure holds
  both, that the checkpoint and report are written, and that their closures agree.
  - `store_entry` adds the manifest's sha256.
  - `Examples` refuses a store whose size differs from the config's.
  - `--max-examples` is allowed for `--scope smoke` only.

**2026-09-23: decoder re-check follow-ups** (`review-idm-model-3.md`; the decoder landed in `057a843`):
- **The denylist:** the store CLI refuses any sealed denylist path or pin but the pinned default, and the manifest
  records the denylist used.
- **The demo** is read once, and parsed only after its bytes match the targets' pin. The step table is pin-checked
  before it is parsed, and again after.
- **The video's** size and mtime must not change between hashing and the end of the decode.
- **The e2e `run_fit` test runs in a fresh interpreter.** Negative control: with the module-level `agent` import
  removed it fails with "the code closure changed during the fit".
- **The HUD identity with range_bc's cache** is now also tested on textured frames (`testsrc2`), which a crop offset
  would break.

**2026-09-24: first IDM plumbing run on the Mac** (`gate1-dev` scope, not a gate result; code `1df31e7`, clean).
- **Stores:** 170,112 frames, 26 GB, built in about 33 min (niced, 4 threads) from the originals read in place.
  All four re-verify and bind to their targets. The inspected dev frames look right.
- **MPS:** runs under deterministic algorithms. Two 512-example smoke fits gave byte-identical checkpoints
  (`2b97875d`).
- **Leave-one-session-out:** 3 epochs, seed 0, four folds in 81 min (0.0029 s/example). Train loss falls in every
  fold. The held-out sessions are train-split recordings.
- **Camera beats zero in every fold, and is far short of persistence.** Persistence uses the true previous rotation,
  so it is a ceiling built from labels, not a floor.

  | Held out | Yaw error, moving, median: model / zero / persistence | Yaw direction agreement | Pitch error, moving, median: model / zero | Extrapolated share |
  |---|---|---|---|---|
  | 171533 | 0.35° / 1.22° / 0.20° | 0.96 | 0.51° / 0.89° | 23 % |
  | 051828 | 0.85° / 1.42° / 0.20° | 0.54 | 0.56° / 0.93° | 43 % |
  | 205528 | 0.74° / 1.46° / 0.20° | 0.47 | 0.68° / 0.93° | 40 % |
  | 200129 | 0.85° / 1.39° / 0.20° | 0.51 | 0.82° / 0.93° | 41 % |

  - **Open, not explained:** yaw direction agreement is at chance on the three fast-heavy folds. The aggregates
    cannot split it by speed.
  - **A hypothesis to test** with per-row predictions: turns faster than the conv's receptive field per interval
    leave the direction ambiguous to a small conv with global pooling.
  - The stated yaw std under-covers above the calibrated band: 29–73 % of errors within 1σ, where about 68 % is
    expected.
- **The edge head has no usable skill yet.** It predicts almost no onsets. The exception is jump, which fires
  constantly (precision 0.02–0.06, recall 0.59–0.94, F1 0.05–0.11). Every other deciding action has F1 0.
- **Runs, reports and store manifests** are in `data/idm/runs/` on the PC (gitignored); the hashes are in the
  hand-back.

### Yaw falsification test (2026-09-24)

Pre-registered before any code or run, after `idm-diag`. In the plumbing fit that held out 051828, yaw direction was
never learned, even on its own training data, while the fit that held out 171533 did learn it. The diagnosed mechanism
is that the Gaussian NLL's learned variance starves the mean. This test separates that mechanism from seed fragility.
**Nothing here is a gate result.**

**Fixed across all three runs.**
- **Fold:** 051828 held out; train on 171533, 205528 and 200129.
- **Data:** the same target files and stores as `loso-051828`.
  - Targets: 171533 `42732841`, 205528 `5d51f240`, 200129 `a32a7380`, held-out 051828 `2e89adf3`.
  - Store manifests: `8780ea7c`, `14190df6`, `a111ba07`, `457637aa`.
- **Fit:** `run_fit` defaults: 3 epochs, batch 16, AdamW lr 1e-3, weight decay 1e-4, clip 1.0, full-scale `Config()`,
  MPS, niced, scope `gate1-dev`.

**The runs.**

| Run | Seed | Camera loss | Code |
|---|---|---|---|
| **C1** (control) | 1 | Unchanged (Gaussian NLL, variance = model + label σ²) | `1df31e7` |
| **C2** (control) | 2 | Unchanged | `1df31e7` |
| **T** (treatment) | 0 | **β-NLL, β = 0.5:** each camera element's NLL is multiplied by stop-gradient(var^β), with var the same total variance the NLL uses. The mean's gradient then scales with 1/σ instead of 1/σ². Both axes, nothing else changed | Branch `idm/yaw-test-20260924`: one commit adding this behind a flag that defaults to today's loss |

T at seed 0 is otherwise identical to `loso-051828`, whose checkpoint is `11d0b912`.

**Judge, per run.**
- **Per-row raw μ** of the run's checkpoint, as in `idm-diag`, on:
  - the held-out session **051828**;
  - the in-sample session **171533**.
- **Metric:** raw-μ yaw direction agreement on moving rows (|true yaw| ≥ 0.5°), by `analyse.py`'s definition
  (`0ed5569b`). There is no abstention, so no selection.
- **"Learned":** agreement ≥ **0.85 on both** sessions. Anything else is "not learned".
- **Reported beside it, not judged:**
  - yaw correlation, median |μ|/|true|, and the median predicted yaw std on still and moving rows;
  - pitch agreement, as a guard that the treatment broke nothing else.

**Pre-registered readings.**

| C1, C2 | T | Reading |
|---|---|---|
| Both learn | Either | **Seed fragility.** Seed 0 was unlucky and the loss stays; T's result is reported, not decisive |
| Exactly one learns | Either | **The current loss learns yaw only sometimes:** fragility is established. One treatment seed cannot show that β-NLL removes it; the next step is seeds, not a loss change |
| Both fail | Learns | **The mechanism holds.** β-NLL becomes the candidate change, to be reviewed before it is relied on |
| Both fail | Fails | **The mechanism is wrong.** The next place is the input or the optimiser |

**The lane's own expectation,** stated before the runs and not part of the judge: at least one control fails (one of
four seed-0 fits learned yaw), and T learns.

**Budget.**
- Three fits of about 21 min each (`loso-051828` took 1,273 s), one after another in one niced queue.
- Six predict passes of under 1 min each.
- About 1.2 h of Mac time.

## Measurements owed

- **The 7 large live zeros (a) still keeps:** parallax during combined movement and turning.
- **Window 347's** still-input pairs withheld as contradicted.
- **M2:** the viewer-FOV re-record (asked of James). Self-calibration refused on live (above).
- **The window-597 cause,** and the live range frames' remaining zero-flow content.
- **The per-pair thresholds,** re-validated once the 360° gain gives true degrees.
- **Press-to-evidence delay** per action on James's data (F8), which sets the window.
- **The 360° calibration take** (asked of James), which is the gain.

## One-day prototype on the Mac (plan)

**Scope:** a Gate 1 **plumbing draft** on today's data, for the camera and edge heads. Nothing it finds stops the lane
below the per-action minimum counts. It ends with a dry run on 5 minutes of the expert replay, with no labels exported.

**Budget (F10):**
- **Geometric features:** 0.106 CPU-s per 1280×720 pair (M1 run), so the ≈75 k frames at 60 Hz cost about 2.2 CPU-hours.
  Run on the Mac after transfer, parallelised, not inside the export slot.
- **Frames:** 75 k frames at 448×252×3 is ≈ 25 GB raw. Export streamed and compressed (for example H.264 at 448 wide,
  or `npz` chunks). Never hold a session in memory.
- **PC memory:** the export honours the > 5 GB free / no-other-decoder gate that stopped the first M1 run.

| Hours | Step | Output |
|---|---|---|
| 0–1.5 | **Export on the PC**, niced, 4 threads, streamed: 60 fps at 448 wide, the native HUD crops, the spectator mask applied alike. Align inputs through `frames.csv` composition timestamps and the intake's muxer-offset anchor. Label per interval: semantic edges, holds, mouse counts; unsupported actions marked unknown. Exclude focus loss, gaps and chat | Compressed chunks; per-session tally |
| 1.5–2.5 | **Gain and envelope.** The 360° take's counts-per-turn is the gain, if the take has arrived; otherwise the camera numbers stay in counts and are marked uncalibrated. Check the estimator against the take. Flag out-of-envelope intervals | Gain, estimator check, exceedance share |
| 2.5–3.5 | **Press-to-evidence delay** per action (F8), then **baselines** on dev: zero, geometric estimator, HUD cast events | Window choice, baseline table |
| 3.5–6 | **Train** on the Mac: stacked frame differences through a small conv (camera), native HUD crops plus motion (edges), 3 seeds, niced. A second arm uses the geometric features only and is reported as that | Checkpoints, training log |
| 6–7 | **Evaluate on `171533` (dev):** metrics by stratum, risk-coverage, calibration. Per action, say whether it clears the 30-positive minimum | Gate 1 plumbing draft |
| 7–8 | **Replay dry run** on 5 min of alive target POV: the support gate, label-free checks, coverage per action | Transfer note, no labels written |

**Stop rules** apply only where an action clears its minimum count:
- if the camera head does not beat the geometric estimator on its failure strata, keep the estimator;
- if the edge head does not beat HUD cast events, keep the HUD events.

Otherwise the result is "undecided at this data size". Results go on VUH-1353 with the numbers.

**Asks for James** (routed by the lead):
- the shared 360° calibration take;
- 10–20 s of the same DayMR replay segment at two viewer FOV settings;
- two logged real matches on different maps, each with its replay recorded from his own POV;
- the Controls-screen look that pins sensitivity, DPI, bindings and swing settings.
