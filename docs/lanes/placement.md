# Placement: from any post-trial state back to a verified start, with no human (VUH-1359, VUH-1299)

2026-09-23, design only; no code, no game input. The Galacta pilot 2 stopped at 3 of 20 slots because placement
between slots needed James three times (`docs/evidence/galacta-pilot-20260923/README.md`): the operator walked blind on
timed presses, fell off the courtyard terrace twice and entered the Timed Practice hall once. This lane owns the fix;
it is the start state for the live range pilot the recording protocol ends in (`docs/recording-protocol.md`).

**Recommendation: do not reset. Home on the Galacta pair.** No in-range reset exists in the evidence, and re-entry costs
a lobby round trip and a new binding per trial. The two courtyard bots are a landmark the existing finder already
measures on every frame, with a geometric signature that off-lane views break. Placement becomes closed-loop: camera
sweeps (no displacement) to reacquire the pair, then short walk pulses along the pair's axis with a fresh check after
every pulse, stopping on the planned bin. Re-entry plus a recorded spawn path is kept only as the last-resort recovery.

## 1. Reset mechanisms we could use

| Mechanism | Screens and input | What goes wrong | Evidence held | Needs a supervised look |
|---|---|---|---|---|
| **Range reset/respawn from a menu** | Pause (`START`): Resume, Practice Settings, Settings, Leave Game, Exit. Practice Settings has four rows: No Ability Cooldown, its Always On sub-row, Friendly Fire, Controller Operation | **None exists.** No row resets position or respawns the hero; the HUD's own prompt list (Practice Settings, Change Hero, View Destructible Objects, Hero Profile) has none either | `.agents/skills/rivals-live-game/SKILL.md` "Practice Settings (pause menu) has four rows and no bot options"; pages read fresh twice on 2026-09-23 (`data/benchmarks/galacta-setup-20260923/practice-settings{,-entry2}/ps-0.jpg`) | No |
| **Change hero** (hold `X`) | Hero select in the range | **Does not respawn the player** (skill: "Re-picking a hero does not respawn the player"; `docs/lanes/reentry.md` arrival notes). Also `X` is a dangerous button on the lobby | Skill, reentry lane | No |
| **Re-enter the range** | Leave Game (pause), or the idle drop, to the PLAY lobby; `scripts/reenter.py`: PRACTICE tab, PRACTICE RANGE tile, Spider-Man, arrival out of the spawn room | `l4_menu` deliberately has **no confirmable LEAVE GAME** (VUH-1325 allow-list), so the only agent path to the lobby is the idle drop: **~10 min of idle per reset**. Arrival exited 1 in 2 of 3 trials of one session (`docs/lanes/l4-controller.md`). Every entry re-enables No Ability Cooldown (Always On), so `cooldowns-off` + page read each time, and **each entry needs a new binding** (scope = PID + range entry). The lobby is where `X` starts Quick Match. At 17 slots that is ~3 h of drops alone | reentry lane; pilot 2 (drop 13:20, binding 2) | No, already characterised |
| **Suicide / respawn** | Would need self-damage or a kill plane | Range bots never attack, Friendly Fire is off, no self-damage ability. Whether the water under the courtyard or a map edge kills and respawns is **unknown**. A respawn lands in the spawn room, so it still needs the spawn-to-courtyard path | Skill ("range bots never attack") | **Yes**: one look at whether falling into the courtyard water respawns, and where |
| **Fixed recorded path from the spawn** | After re-entry or a respawn: the spawn room's lime door, the plaza facing the Luna Snow bot (`reenter.py` arrival end pose), then plaza to courtyard | Timed presses drift: the camera turns on every pad attach (~25°/s until the first non-neutral report, skill), a settings-menu pad turned it ~180° on 2026-09-23, and 2.5 s of blind walk from a diagonal heading dropped off the terrace. A path is only as good as its first heading | `C:\desk\out\galacta-courtyard-00..06.png` (first pilot's route, screenshots only, no recorded tokens); arrival end pose documented; James's sessions now log keys and mouse (`recording-protocol.md`) | **Yes, but offline-derivable**: one James session that walks spawn → courtyard gives the path with exact inputs from the input logger |
| **Home on the pair (recommended)** | None; in-range, camera and stick only | Finder flicker at 25 m (one of two boxes missing on one frame); point-blank states show one bot only; the lane's unrailed right side (bridge side) | The measurements below, 17 inspected frames from pilot 2 | No |

## 2. Pixel check: "on the lane facing the pair"

Inputs, all from existing readers on one fresh native frame (`agent.loop.default_perception`): `in_range`, HUD `hp` and
`webs`, and the whole-frame finder's enemy boxes (`p.wide`). A **Galacta box** is an enemy box with aspect
`w/h ∈ [0.80, 1.30]` (Galacta at far/mid measures 1.00-1.12; the stray lane box in `e2-pos1` is 0.23).

**PAIR** passes when all hold:

1. `in_range` is true and HUD `hp` = `max_hp`.
2. Exactly two Galacta boxes A (left) and B (right, the designated bot).
3. Same floor and size: `|y1_A − y1_B| ≤ 12 px` and `|h_A − h_B| / max(h) ≤ 0.12`.
4. **Signature:** `(cx_B − cx_A) / h_px ∈ [3.3, 4.3]`, where `h_px` is the mean box height in pixels. Measured on-lane
   3.6-4.0 at every distance from 25 m to mid; this is what a view from below the terrace, from the side, or of other
   bots does not reproduce.
5. **Level:** `y1 ∈ [440, 620]` at 1440 p for far/mid (on-lane values 475-545). Seen from below the terrace, the box
   top sits at 975.
6. **Heading:** midpoint `(cx_A + cx_B) / 2 ∈ [1130, 1430]` (screen centre 1280 ± 150).

Distance is read from `h` (fraction of frame height, the `agent.brain.RANGES` measure): **25 m end ≈ .038-.039**,
15 m ≈ .055, mid bin .065-.325 (placement target .09-.10), near ≥ .325. **AT_25M** = PAIR with both `h ∈ [.033, .047]`.

**NEAR_ONE** (point blank, one bot fills the view) is a separate state: one Galacta box with `h ≥ .30`, `y1 ∈ [640, 700]`
and `cx ∈ [1000, 1560]`. It is where every trial ends, and it is only ever exited by the back-away procedure below.

A decision uses up to **3 fresh frames** 150 ms apart, and passes if any frame passes (finder flicker: `scene-03`).

**Worked on the frames we have** (finder output, 2560x1440):

| Frame | Boxes (bbox, h, cx) | Result |
|---|---|---|
| `p0923-e2-pos2-a` (lane, ~25 m, entry 2) | A `1176,476,1231,531` .038 1204; B `1377,475,1431,531` .039 1404 | **AT_25M pass**: Δy1 1, Δh 2 %, sep/h 200/55 = 3.64, y1 476, midpoint 1304 |
| `p0923-scene-03` (James's park at the 25M marking) | one box, B `1333,567,1387,623` .039 | **PAIR fail** (one box: left bot missed by the finder on this frame). Retry frames or a small pitch/turn; a human sees both |
| `p0923-scene-01` (James's park, 15 m) | A `988,518,1071,597` .055; B `1282,518,1359,598` .056 | PAIR pass (sep/h 290/79.5 = 3.65), AT_25M fail (too close: .055) |
| `galacta-0923-ready-e2` (slot 3 start) | A `729,510,884,649` .097; B `1264,508,1392,641` .092 | PAIR pass, sep/h 522/136 = 3.84; B mid bin: **slot-ready mid** |
| `p0923-pos-01-a` (slot 1 approach) | A .097; B .100 | PAIR pass, sep/h 557/139 = 4.0 |
| `p0923-cdcheck-d` (slot 1 start) | one box `1055,663,1475,1155` .342 | NEAR_ONE: **slot-ready near** |
| `p0923-pos04-a` (after the back-walk, below the terrace) | one box `1159,975,1354,1193` .151 | fail: y1 975, one box |
| `p0923-restart-look`, `p0923-pl-up-a` (under the terrace) | none (bots shown only as through-wall icons) | fail |
| `p0923-e2-pos1-a` (other lane, moving bots) | `951,511,972,601` (w/h .23) and a sliver at the frame top | fail: not Galacta boxes |

## 3. Procedure

Movement numbers are measured, not guessed:

| Quantity | Value | Source |
|---|---|---|
| Yaw at right stick 0.45 | 172°/s: **0.35 s ≈ 60°, 1.05 s ≈ 180°** | `Cal.yaw_map`; six 0.35 s turns returned to the starting view twice (`nav-04`, `pan04`) |
| Walk, 25 m end → mid | h .038 → .062 in 2.5 s → .09 in +1.2 s (**~3.7 s**) | entry 2, `e2-pos2-a/b`, `e2-pos3-a` |
| Walk, 15 m → near | .055 → .10 in 2.0 s → .33 in +1.6 s → .34 in +0.3 s | entry 1, `scene-01`, `pos-01/02/03` |
| Web Cluster refill | 2 s per charge (5 → 4 → 5 in 2.6 s) | `cdcheck`, `e2-cd` |
| Respawn after KO | ≤ ~4 s, full bar | `reset02-c..e`, slot 3 → `pre04-look` |

Pulses are **0.4 s walks (≤ ~2.5 m), then a fresh 3-frame check**. No blind leg is longer than one pulse, and every
pulse is re-planned from the check. One pad is held for the whole placement (attach drift), with the first report
non-neutral.

**P0. Classify** the fresh frame: slot-ready (target bin met under PAIR or NEAR_ONE, designated bot full), PAIR,
NEAR_ONE, or LOST.

**P1. Reacquire (LOST).** Camera only, no displacement: six 60° turns; at each, the check. Stop on PAIR or NEAR_ONE and
turn by the pixel error of the pair midpoint (degrees = atan((x − 1280) / focal), focal 930 px at 2560 wide). Nothing
found after 360°: pitch ±15° and one more sweep, then **hand back** (no walking while lost: both terrace falls came
from walking while the pair was out of view).

**P2. Back away from NEAR_ONE** (every trial end). Turn so B's `cx` is within ±80 px of 1280, then back up in 0.4 s
pulses **keeping B centred** (correct the heading after each pulse by its `cx` error). After every pulse B's `h` must
fall and its `y1` must stay in `[440, 700]`; the moment A appears, switch to PAIR centring (midpoint). Any pulse where
`h` rises, `y1` leaves the band, or B is lost: stop, P1. This replaces the failed blind 2.5 s back-walk, which started
facing the pavilion off-axis.

**P3. Distance servo in PAIR.** Keep the midpoint centred. Too close for the planned bin: back-pulse. Too far: forward
pulse. Stop when B's `h` is inside the target band: **far start `.033-.047`** (AT_25M), **mid `.085-.11`**,
**near `.33-.37`** (near switches to B-centring once A leaves the view). Budget 20 pulses (~8 s of motion).

**P4. Readiness.** Designated bot full (name plate only, or a full green bar after a respawn), HP 250, webs 5,
swing 3, uppercut 2 (HUD), then the slot's own first-phase frame measures the bin as before.

**Retry and hand-back:** P1-P3 once; if slot-ready is not reached in 90 s or 40 pulses, one full retry from P1;
still not ready: stop with no further input, archive the frames, hand back. The slot is not consumed (placement is
before `allocation-consumed.json`).

**KO-ending vs timeout-ending slots:**

- **KO ending** (scripted combos, stop on feed): Spider-Man ends at point blank, often past the bot or airborne,
  camera anywhere. Wait 5 s for the respawn and landing, then P0 (usually NEAR_ONE or LOST), P2, P3. The respawned
  bot has a full bar. Resources: wait for swing 3 (6 s per charge) before P4.
- **Timeout ending** (learned trials so far): Spider-Man near the bot, **the bot damaged**. First the accepted KO reset
  (Web Cluster taps on B from NEAR_ONE, the reset recorded with timed screenshots), then 5 s, then as above. Webs refill
  2 s per charge before P4.
- **Setup failure before the phase** (slot 2's refusal): no displacement happened; P0 only.

The inactivity timer is fed by the pulses themselves. Placement between trials takes well under the ~10 min drop, and a
paused pilot must use a verified real move (a 0.15 s nudge was not enough on 2026-09-23).

## 4. What needs James once, and what is offline

**Offline, now, on held frames:**
- the PAIR/NEAR_ONE rules above, as a pure function over finder output, tested on the 17 inspected pilot-2 frames
  (these are the positives and negatives in section 2) plus the first pilot's `galacta-setup-20260922*` scouts;
- the pulse planner against a simulated lane (yaw map, walk rate, the drop edge), including P2 from `cdcheck-d` and
  `pre04-look` states;
- from James's logged whole-session recordings (`recording-protocol.md`): his real approaches to the pair give many
  more PAIR frames at every distance, and the input log gives true walk rates and the spawn-to-courtyard path.

**Needs one supervised look (James present, or his next recording):**
1. Whether falling into the courtyard water, or off the terrace, respawns the hero, and where. It decides whether
   "suicide" is a reset.
2. One run of P1-P3 live from the three failure states: NEAR_ONE after a KO, the under-terrace nook (`restart-look`),
   the lower plaza (`pl-stair3-c`). The rules are offline-verified; the pulse rates on this geometry are not.
3. The spawn-to-courtyard route, walked once in a logged session, only if re-entry is ever used as the last-resort
   reset.

**Not needed:** a supervised look at a reset menu. There is none (section 1).

## 5. Implementation (2026-09-23, offline, no game input)

`agent/placement.py`, pure and stdlib, in `agent/` beside the brain and controller it will feed: it is decision logic
on reader output, not a device tool. A later `scripts/` driver owns capture, the pad and its range proof, as
`scripts/reenter.py` does for the menus. It adds no file to the checkpoint identity (perception: hud/outline/loop;
selector: brain/tracker).

**One change from the design above, found by the simulated lane before any live run.** From slot 3's end pose (point
blank, right of the designated bot, facing it off-axis), backing straight away from the bot, even centred and in
0.4 s pulses, still walks off the unrailed right side: the back direction points off the lane. So:
- The planner **localises**. Two bots' bearings (box centres) and ranges (`0.96 / h` m) give Spider-Man's position
  and heading relative to the pair (`localise`).
- **Consistency check:** the localised bot-to-bot distance must be 0.72-1.30 × **5.17 m** (fitted: the median over 60
  labelled pairs; p10-p90 4.67-5.57 m).
- **On-lane check:** the pose must fall within the lane (`|x| ≤ 3.5 m`, 1-30 m out). Off-lane false pairs localise
  15-20 m to the side and fail it.
- **Moves are made only with a pose:** first **strafe onto the axis**, then walk the distance, and every pulse's
  predicted end must stay on the lane.
- **From point blank** it turns the camera until both bots are in view. It never backs up blind.

**Classifier** (`classify`, `decide`), on 84 held frames (`tests/fixtures/placement/frames.json`, hash-pinned):

| Set | Frames | Content |
|---|---|---|
| Pilot 2 | 18 | the frames in section 2, plus the post-KO `pre04-look` |
| First pilot's setup scouts | 7 | two are finder misses on the lane (hero occlusion; no box at all), correctly LOST |
| Mined | 59 | 49 on-lane pairs and 10 false pairs from 1,014 already-extracted stills (`data/l1` pilot runs, their start/phase stills, the setup scouts, `C:\desk\out`, `data/human/inspection`), each labelled by eye on contact sheets. No video was decoded |

- **Widened signature:** separation/height **3.3-4.7** (on-lane 3.38-4.64). Box top in 440-560 when far (h < .06),
  470-740 otherwise. |Δy1| ≤ 40 px and |Δh| ≤ 25 %.
- **The false pairs** are point-blank fragments, another room's bots, the lower plaza, the far bridge rail, a building
  interior and the moving-bot lane. They fail the band or, via the pose, the lane.
- **Tightest margin:** one mid-combo frame of the first pilot (`000007`): separation/height 4.64, Δy1 35, Δh 0.22.
- **Hero occlusion** (a pilot-1 scout: the left bot hidden behind Spider-Man) is answered by a ±15° camera jitter
  before any 60° sweep.

**Planner** (`plan`): TURN, STRAFE, WALK (≤ 0.4 s), READY or HAND_BACK. Its limits:
- 40 moves and 90 s per attempt, one retry;
- two moves that land away from their prediction, or four that lose the pair;
- a full camera turn with no pair.

**Tests:**
- `tests/test_placement.py` (stdlib, 100 cases): the frame table, the design examples, the 3-frame decision, and the
  simulated lane.
  - The lane reproduces both real falls: the 2.5 s blind back-walk from slot 3's end, and a walk and jump off the
    side.
  - From the same pose the planner strafes left, away from the drop, and reaches READY.
  - Once fallen, it only turns and hands back, with zero moves.
  - It also covers: 25 m end to far, mid and near; point blank facing away (camera first); a finder that drops 30 %
    of boxes; a stuck character (hands back inside the budget); and a move the lane forbids.
- `tests/test_placement_frames.py` (perception): re-derives every row's finder boxes and range proof from its pixels.
  - All 84 re-derive on the PC.
  - Rows whose image is absent (the Mac, the gitignored run folders) or whose bytes differ skip with that reason.

**Unmeasured, marked `UNVERIFIED`/`UNMEASURED` in the module:**
- the strafe rate (assumed equal to walking);
- the lane's half-width, and where the right-side rail stops.

The supervised look measures both.

## 6. Supervised look: five minutes in James's next recorded session

James plays and records as usual (`docs/recording-protocol.md`, input logger on). No agent input. Say "placement look"
in chat with the video path afterwards. Everything below is recovered offline from the video and the input log.

1. **Lane edge (1 min).** Walk to the lane's 25 m end, facing the Galacta pair. Walk slowly along the **right** edge
   (the bridge side) toward the bots, hugging it, until the rail ends or you reach the bots. Then the same along the
   left edge. This gives the lane's width and where the drop begins.
2. **Strafe rate (20 s).** At the 25 m end, facing the pair: hold strafe right for about 1 s, then left for about 1 s.
3. **Water / drop respawn (1 min).** From beside the bots, step off the unrailed right side. If you land in water, wait
   10 s. Does Spider-Man respawn, and where (spawn room, lane, same spot)? If not, climb back however you like.
4. **The three failure states (2 min).** For each:
   - get there, stop for 2 s, then turn the camera slowly through a full circle **without moving**;
   - then walk back to the 25 m end.

   The three states:
   - **point blank after a KO:** KO the right bot with a combo and stay where the combo ends;
   - **the nook under the terrace:** the rocks under the bridge, below the lane's right side;
   - **the lower plaza** by the wooden stair.

   The camera circles are exactly what the planner's camera-only search sees; they replay offline through `classify`.
   The walks back show the route a pose-based planner must find.

A live P1-P3 run by the agent needs the live driver (capture + one pad + range proof around `plan`), which is not
built. It is the next step. Its first live window should start from these same three states with James at the
keyboard as the kill switch, and take about 5 minutes.

## 7. Review fixes (2026-09-23): F1-F6 of `review-placement.md`

The review approved with required fixes. The lead's decisions are all applied. **Still offline logic only:** live
input stays gated on F4, F6's held-out check, the pitch reset, and the look's measurements.

**F1: the pose is a feasible set, not a point.**
- **The problem:** the lateral offset comes from the two exact bearings, the known 5.17 m spacing and one range from
  the mean box height. That leaves a mirror ambiguity (+x and −x subtend the same angle). It is also poorly
  conditioned near the axis: a 5 % range-scale error reads as ~0.3·d of offset, and labelled frames of mixed pitch
  show scale errors up to 23 %.
- **The feasible set:** `localise` keeps every pose consistent with:
  - the bearings;
  - a scale error within ±10 % (`RANGE_SCALE_ERR`; UNMEASURED at the reference pitch);
  - the distance solved from the mean-height model, not the mean height directly (they differ at close range);
  - a per-box height ratio within 0.51 of its prediction (`BIAS_LOG_MAX`, the review's ±25 % differential).
- **Rejection:** a frame whose best pose misses the ratio by more than 0.21 (`RANGE_LOG_BOUND`, clean labelled
  maximum) is rejected.
- **The side is known only when every feasible pose agrees.** Own moves carry an x-interval (rate 0.5-2×) that prunes
  mirror poses.
- **Every move must be safe for every feasible pose.** Inside the drop zone (y ≥ −10 m, UNVERIFIED) no predicted end
  may lie beyond x = 2.0 m unless it is closer to the axis than its start.
- **Backing out near the bots** strafes LEFT until every pose is left of the axis. Facing the pair, a left strafe moves
  toward −x for every pose. This relies on the left side not being a drop (UNVERIFIED; the look checks).
- **Result on the review's grid:** 35 starts × 3 headings × 9 biases (±15-25 % differential both ways, one-sided, and
  ±10 % common), mid and far: **0 falls in 1,890 runs**.
- **Liveness:** READY in 77/105 unbiased mid starts. With ±25 % bias it hands back every time, because every frame
  fails the acceptance bound.
- **The post-KO start** (point blank, right of the designated bot) hands back under the worst-bias set. It reaches
  READY in the simulator if the real bias bound is ≤ 0.35: the look's known-position frames measure that.

**F2: level, independent of the y1 band.**
- At a fixed pitch, a box's bottom row on one level is linear in its height: `y2 = 495.9 + 1.073·h`, fitted on 32
  boxes of the low-pitch cluster.
- **Held out:** the cluster's other 32 boxes stay within −25..+40 px.
- **The level band is −40..+50 px.** Everything else sits well outside it:

  | Views | Offset from the lane level |
  |---|---|
  | Lower-plaza views of the pair | ~+200 px |
  | The review's ×1.9 plaza pair | +214 px |
  | The other pitch cluster | +87..+205 px |

- **Tests:**
  - the ×1.9 pair is never PAIR, at any pitch flag;
  - synthetic lower-plaza views at 10-20 m are never PAIR. Real 10-20 m plaza frames are due from the look.

**F3: PITCH_RESET.**
- **The action:** the planner's first action, and its answer to any UNLEVELLED view. It holds the right stick fully
  down to the pitch clamp, then up for a measured time.
- **Only after it do frames count as at the reference pitch.** Recorded frames of unknown pitch can never yield a
  pose, so they can never yield a move.
- **The durations are UNMEASURED.** `scripts/place.py` refuses PITCH_RESET live until they are measured.
- **Tests:** pitch errors of ±40-160 px before the reset, a ±30 px residual after it, a reset that never levels
  (hands back with zero moves), and the plaza under residuals up to −150 px.
- **The requirement for live:** the reset must hold the pitch within ~150 px (~9°).

**F4:** `EDGE_X_M = None` refuses near placement.
- With a measured edge, the stand ceiling is edge − 1.5 m.
- Approach strafes are ≤ 0.15 s, each with a fresh pose.
- The side must be known.

**F5:** `MAX_STEPS = 150`, counted on every call. The alternating PAIR/LOST case at dt = 0 now hands back within it.

**F6:**
- **2 of 3 frames:** a pose counts only when two frames agree.
- **Labels committed:** `labelled.json` is committed and pinned in `provenance.json`.
- **No fallback:** the builder refuses an unlabelled frame.
- **IN-SAMPLE:** the thresholds are marked so, in the module and in the tests.
- **Two real on-lane pairs are now conservatively rejected:** the frame-cut `near-02` and the mid-combo `000007`,
  which had the tightest margin.
- **Before gating live input:** a held-out check on the look frames and James's next sessions.

**Section 6 look, additions** (the review's list and these fixes):
1. **Frames at known lateral positions:** along both edges, facing the pair. They are the localisation ground truth,
   and they measure the real bias bound that decides post-KO liveness.
2. **A lower-plaza approach to the terrace wall,** facing the pair: real 10-20 m F2 negatives.
3. **The pitch-clamp and reference durations for PITCH_RESET,** and the pitch it lands on.
4. **The left edge:** whether it is walls and planters all along, which the left-strafe rule assumes.
5. **Where the right-side rail ends,** which gives the drop zone.

**Tell the intake lane:** the look's spans are deliberate falls, edge-hugging and strafe tests. Tag them rejected for
whole-session training, with the reason "placement look".
