# Review: placement classifier and planner (VUH-1359, VUH-1299)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only: no repo edits, commits,
game input or Linear writes. All experiments ran on the modules' own pure functions, the fixture and
`agent/placement_sim.py`.

**Reviewed bytes.** The owner edited `agent/placement.py` twice while I worked, from `c4d58f35` to
`713925ef` (current). Every result below was re-run on `713925ef`:

- `agent/placement_sim.py` `f00d8bfa`
- `tests/test_placement.py` `00c586dd`
- `tests/test_placement_frames.py` `79c672f5`
- `tests/fixtures/placement/frames.json` `a3dc4478`
- `build_frames.py` `4e30dd48`
- `docs/lanes/placement.md` `52421f92`

`placement_sim.py` is imported by the tests but was not named in the brief. I reviewed it too.

## Verdict: APPROVE WITH REQUIRED FIXES

This may land as offline logic. **It must not drive live input until F1 and F2 are fixed.**

**Sound:**

- The architecture: pure logic, camera-only search, and a move only with a pose.
- The two real falls are reproduced.
- Walk and strafe rate errors are safe by construction.

**The dangerous gap.** The pose itself is not trustworthy at the metre scale the lane needs. The checks meant
to guard it do not detect its main error, and one real off-lane view already classifies as an on-lane PAIR.

## Ranked findings

### F1 (blocking): differential box-height error sends the planner off the drop, and the spacing check can't see it

**Where it breaks.** `localise` takes each bot's range from its own box height
(`_range_bearing`, `agent/placement.py:122-123`). The pair's consistency check is the localised spacing
(`SPACING_RATIO` 0.72-1.30, `:47`).

**Why the check misses it.** A differential error (one box too tall, the other too short) leaves the
localised spacing about right and moves the pose sideways.

**Measured on exact simulated boxes** (the sim's own renderer, pose facing the pair's midpoint), with
one box's height perturbed by ±15-25%:

- **The lateral estimate moves by up to 7.7 m while the spacing ratio stays at 1.01.** Example: true
  (4.4, −8.0), estimated (−3.3, −9.2), PAIR.
- **True x ≥ 4.0 localises inside the 0.8 m lateral tolerance in 5 cases.** So the planner does not even
  strafe.

**Closed loop** (`sim.run`, 35 starts from x −3 to 3.5, y −4 to −20; script
`scratchpad/placebias.py`):

| Bias: left, right height | mid falls | far falls | near falls |
|---|---|---|---|
| 0, 0 | 0/35 | 0/35 | 0/35 |
| +10%, −10% | 0 | 0 | **5** |
| +15%, −15% | **13** | **11** | **6** |
| +25%, −25% | **9** | **9** | **5** |
| 0, −20% (right short) | 0 | 0 | **4** |
| −15%, +15% | 0 | 0 | 0 |

Falls take one or two moves, and they start from true poses the planner accepts: for example (3.0, −6.0),
bias +15/−25, falls in 2 moves.

**Can this error occur?** Yes. The fixture's labelled on-lane pairs have Δh up to 0.22
(`PAIR_MAX_DH` note, `:35`). The owner's own figures show real localised spacing ratios of 0.69-1.36.
The error sources are real:

- the right bot partly behind the hero, or cut by the frame edge;
- a fragment box;
- an outline merged with the name bar.

**The safety nets are too loose to help.**

- The bad-move check allows 1.5·|v|·walk + 1 m (3.25 m for a 0.4 s pulse, `:292`).
- The lane check is in the same biased frame.

**Required fix.**

- **Stop taking the lateral position from per-box heights.**
  - Triangulate from the **two bearings (pixel-exact) and one range from the mean height**. The subtended
    angle plus the known spacing fixes the position, and a common scale error then only moves it along
    the range.
  - Reject a frame when the two per-box ranges disagree with that geometry by more than a measured bound.
- **Add a drop-side margin.** No action whose predicted end has x > 2.0 m, except the near stand (F4).
- **Add a sim test** with ±15-25% differential height bias over the start grid, and require 0 falls.

### F2 (blocking): the pair seen from the lower plaza classifies as an on-lane PAIR

**The frame.** `galacta-manual-second-02.png` is the fixture's "pair seen from the lower plaza", i.e. the
courtyard pair from below the terrace. Its signature is near-perfect:

- sep/h 3.58, Δy1 0, Δh 0.02;
- it localises **on the lane**, at (3.3, −28.8), spacing ratio 1.02.

It fails only because its box top of 715 lies outside the *far* band (440-560). The far band applies while
h < 0.06 (`PAIR_FAR_H`/`PAIR_Y1_FAR`, `:36-37`).

**The adversarial pair.** The same two boxes scaled ×1.9 about their midpoint, at the same y1 = 715:
`[[1156.7,715,1244.1,804.3],[1477.8,715,1569.0,806.2]]`, h 0.062.

- This passes the near band (470-740, `:38`).
- **`classify` returns PAIR with pose (0.93, −15.07)**, and `plan` answers with STRAFE moves.

**Can it occur?** Yes. Walking from the lower plaza toward the terrace wall with the pair above makes the
boxes grow, and from below the bots stay in the 700-740 region. That is the plaza where pilot 2 ended up.

**The whole defence against another level is the y1 band.** The band is pitch-dependent (F3), and the sim
never exercises it: its fall model always puts y1 at 975, straight ahead only (`placement_sim.py:25,30`).
So "after a fall the planner never moves" (`tests/test_placement.py:113-120`) holds for the sim's fall,
not for this real view.

**Required fix.**

- **A level check that doesn't rest on the band.** For example, the vertical relation between each box's
  top and bottom and the horizon at a normalised pitch (F3), or a measured y1-versus-h curve for the lane
  with a tight tolerance.
- **Fixture negatives** from the lower plaza at 10-20 m.
- **A test** that the ×1.9 plaza pair above is not PAIR.

### F3 (serious): camera pitch is uncontrolled but the band depends on it

**The problem.**

- **No pitch action exists.** The action vocabulary has only yaw turns (`:201`). The design's P1 "pitch
  ±15° and one more sweep" (`placement.md:86`) was dropped.
- **The band depends on pitch.** Post-trial pitch is whatever the aim controller left.

**Measured:** shifting every fixture box by Δy (≈ 930·tanθ):

| Pitch shift | On-lane PAIRs kept (of 60) |
|---|---|
| −40 px (−2.5°) | 38 |
| −60 px (−3.7°) | 31 |

**Why that is both unsafe and unlive.**

- Search is yaw only, so such a view never recovers. It sweeps to HAND_BACK: a liveness failure.
- In the other direction, a −155 px shift admits the lower-plaza far pair above with an on-lane pose:
  a safety failure.

**Required.** Normalise pitch before classifying: a PITCH action to a reference, set by a measured procedure
(e.g. recentre, or look at the horizon), plus a pitch-perturbation test.

### F4 (serious): the near stand is the one move made toward the unrailed side

**How it works.** `goal('near')` stands at x = +2.585 m, in front of the designated right bot (`:228-234`).
The strafe/walk logic otherwise always moves toward the target line (`:331-341`).

**Tested.** Walk or strafe rate wrong by 0.5×/1.5×/2× gave **0 falls for every bin** in the sim. Rates
are self-correcting.

**Where it is still exposed.** The near stand is exposed to two things:

- the unverified edge: the sim puts the drop at 4.5 m, a guess (`placement_sim.py:3-5`), and
  `LANE_X_M = 3.5` is UNVERIFIED (`:49`);
- pose bias: near falls at only ±10% bias, the worst row in F1.

**Required.**

- Near placement only after the edge is measured.
- Approach the stand in short strafes (≤ 0.15 s) toward +x, with a fresh pose each time.
- A hard x ceiling of the measured edge minus 1.5 m.

### F5 (serious): the step budget depends on the driver passing `dt`

**The problem.**

- **`elapsed` only grows by the caller's `dt`,** which defaults to 0.0 (`plan(..., dt=0.0)`, `:275-277`).
- **`moves` counts only WALK and STRAFE.**
- **`sweep_deg` and `jitter` reset whenever a pose is seen** (`:326`).

**Constructed:** alternating one PAIR-with-pose view (heading off, so it answers TURN) with LOST, at
dt = 0. **5,000 steps of TURN, no HAND_BACK.**

**Required.** An internal `MAX_STEPS` cap counted on every call, plus a test.

### F6: other gaps the tests don't cover

- **The thresholds are in-sample.** They were widened on the same 60 positives that now "all pass". The
  tightest margin is 000007 at 4.64 against a 4.7 bound. No held-out set exists.
  - Required before gating a pilot: a held-out check on the placement-look frames and James's new
    sessions.
- **One frame out of three is enough.** `decide` accepts a PAIR-with-pose on any one of 3 frames
  (`:185-195`), which roughly triples a per-frame false-positive rate. Require 2 of 3 once F1/F2 exist.
- **The fixture's provenance is incomplete.** The 59 mined labels come from a `labelled.json`
  (`build_frames.py:29`) that is not in the repo or pinned. `label or got` would fall back to the
  classifier's own output (`:49`). Commit or hash the labels, and drop the fallback.
- **The sim can't reveal the errors that matter.** It uses the planner's own constants (walk and strafe
  rate, focal length, 0.96 m·h, spacing), so localisation is exact. Add rate, height and pitch
  perturbation to the sim, as above.

## Checks run

- **`uv run pytest tests/test_placement.py`:** 100 passed, on both `c4d58f35` and `713925ef`.
- **Perception.** `tests/test_placement_frames.py` with cv2, at below-normal priority: **84 passed**.
  Every row's boxes, range proof and class re-derive from its hash-pinned image at the current checkout.
  Rows skip with a reason when absent (verified in code, `:27-34`).
- **Whitespace:** `git diff --check` is clean, and no trailing whitespace in the reviewed files.
- **Not run:** the full stdlib and perception suites. The owner reports 1382/60 and 2319/5 with known
  failures. I ran only the placement tests to keep CPU modest while the game runs.

## Question-by-question

1. **Can an off-lane view pass as PAIR?**
   - **Yes:** the lower-plaza view of the pair (F2), constructed from a real fixture frame. It can occur.
   - The other fixture negatives fail on the band or the pose, but several have near-perfect signatures
     (sep 3.41-3.58, Δy1 0-4, Δh ≤ 3%). They fail only on y1 795/722/792, which is pitch-dependent.
2. **Localisation:**
   - A differential height error of ±15-25% moves the lateral estimate by up to 7.7 m while
     spacing/5.17 stays at about 1.0.
   - The 0.72-1.30 tolerance is not the weakness; the check measures the wrong thing.
   - True poses at x 4.0-4.4 localise inside ±0.8 m (F1).
3. **The planner:**
   - **Both falls reproduce** (`test_placement.py:89-110`).
   - **No move without a pose.** In `713925ef`, NEAR_ONE only turns or goes READY, and moves require a
     PAIR/TWO pose. (The version before `c4d58f35` walked from a stale pose. It is fixed.)
   - **From a fallen pose:** in the sim it never moves. In reality, the plaza view moves it (F2).
   - **Retry and budget:** one retry, then hand back. That cannot loop on moves, but it loops on TURNs
     when dt = 0 (F5).
4. **Constants:**
   - Walk and strafe rate errors of 0.5-2× are safe by construction (0 falls in the grid), because every
     move heads to the target line.
   - `LANE_X_M` matters only as an acceptance bound.
   - **The near stand is the exposed move** (F4).
   - **The safe direction is toward the lane axis**, which is left from the bots' right side. The left
     side's extent is also unverified.
5. **Tests:**
   - Hash-pinned images with skip reasons: good.
   - Missing: labels provenance, held-out data, and sim perturbations (F6).
6. **Supervised look** (`placement.md` §6).
   - **Safe for James**, if he keeps a clean start.
   - **Its spans must be excluded from whole-session training.** The deliberate fall, edge-hugging and
     strafe tests would otherwise be admitted as "play with mistakes". Tell the intake lane to tag
     "placement look" spans as rejected with that reason.
   - **It measures the edge and the strafe rate.** Add:
     - frames at *known* lateral positions (the edge walk, facing the pair), as localisation ground truth
       for F1;
     - a lower-plaza approach to the terrace wall facing the pair, as F2 negatives;
     - the camera pitch during the look, and a way to set it (F3);
     - the left edge.

## What is sound

- **Pure logic.** Stdlib only and no input. Every constant is named and sourced, and the unverified ones
  are marked.
- **Behaviour.** A move only with a pose, camera-only search, and no jumps.
- **The simulator** reproduces both real falls. Lateral-first strafing then walking along the line is
  correct in the pair frame.
- **Budgets and hand-back.** One retry and a HAND_BACK that leaves the slot unconsumed. NOT_IN_RANGE wins
  every decision.
- **The frame fixture** is real finder output with image hashes, and re-derives from pixels at HEAD.
