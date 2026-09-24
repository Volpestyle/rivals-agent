# pilot-prep: placement review fixes F1-F6 (for the reviewer's re-check). Offline, no game input, no commit

The driver is paused as asked. Only the minimum changes to `scripts/place.py` were made so it follows the new
planner contract:
- a PITCH_RESET step that live refuses while it is unmeasured;
- `pitch_ref` handling;
- replay from a pitched state.

Its dry, replay and live-gate logic is otherwise unchanged. Full detail: `docs/lanes/placement.md` section 7.

## Files

| Path | Change |
|---|---|
| `agent/placement.py` | Rewritten pose (F1), level check + PITCH_RESET (F2, F3), near gate (F4), MAX_STEPS (F5), 2-of-3 (F6) |
| `agent/placement_sim.py` | Pitch offset and reset, lane boxes on the level line, a lower-plaza fall view visible at any heading, per-box height bias |
| `tests/test_placement.py` | Rewritten: 264 cases |
| `tests/test_placement_frames.py`, `tests/test_place.py` | Updated to the contract |
| `tests/fixtures/placement/labelled.json`, `provenance.json` | New: the 81 mined labels, and both files pinned |
| `tests/fixtures/placement/build_frames.py` | No label fallback; refuses unlabelled rows |
| `docs/lanes/placement.md` | Section 7 |

## How each finding was fixed

**F1. What I found doing it: the review's fix has two gaps, and I dealt with both.**

- **Gap 1: bearings + mean-height range leave a mirror ambiguity.** +x and −x subtend the same angle. The per-box
  height ratio is the only side cue, and it is exactly what the differential bias corrupts.
  - My first version decided the side from heights with a margin. The simulator then produced falls: a 25/25 bias
    made the frame fit only the wrong side, and the planner strafed right into the drop.
- **Gap 2: the angle is poorly conditioned near the axis.** A 5 % range-scale error reads as ~0.3·d of lateral
  offset, and labelled frames of mixed pitch show scale errors up to 23 %.
- **So the pose is a feasible set.** It holds every pose consistent with:
  - the exact bearings;
  - a ±10 % scale error (UNMEASURED at the reference pitch);
  - the mean-height distance model, solved rather than approximated (they differ ~20 % at close range);
  - a height ratio within **0.51** (the review's ±25 % differential) of prediction.
- **A frame is accepted** only if its best pose fits within **0.21** (the clean labelled maximum).
- **The side:** known only when every feasible pose agrees. Own moves carry a tracked x-interval (rate 0.5-2×) that
  prunes mirror poses.
- **Moves:**
  - every move must be safe for every feasible pose;
  - drop-side margin **x ≤ 2.0 m** for predicted ends inside the drop zone, unless the move is inward;
  - backing out near the bots strafes LEFT first: facing the pair, that moves toward −x for every pose.
- **Result:** **0 falls in 1,890 closed-loop runs.**
  - The grid: 35 starts × 3 headings × 9 biases, mid and far.
  - The biases: ±15 % and ±25 % differential in both directions, 0/−20 % one-sided both ways, and ±10 % common scale.
  - The test requires 0.
- **Liveness is the honest cost.**
  - Unbiased mid starts: READY in 77/105; the rest hand back.
  - With ±25 % bias: it hands back every time, because every frame fails acceptance, which is what protects it.
  - **The post-KO start** (point blank, right of the designated bot, the most common real case) **hands back under the
    worst-bias set.** In the simulator it places if the true bias bound is ≤ 0.35. The look's known-position frames
    measure that bound.

**F2:**
- The level check is `y2 = 495.9 + 1.073·h`, fitted on 32 boxes of the low-pitch cluster.
  - **Held out:** the other 32 boxes stay within −25..+40 px. The tolerance is −40..+50.
  - The other pitch cluster sits +87..+205 px off.
- **The ×1.9 plaza pair:** +214 px, never PAIR (test).
- **Lower-plaza negatives at 10-20 m:** synthetic, at the real frame's +214 px offset. Real ones are due from the look.

**F3:**
- PITCH_RESET is the first action, and the answer to UNLEVELLED.
- Recorded frames of unknown pitch never yield a pose: replay of the pilot archives never moves.
- **Pitch-perturbation tests:** ±40-160 px before the reset, a ±30 px residual after it, a reset that never levels
  (hands back, zero moves), and the plaza under residuals down to −150 px.
- **The limit:** the level check protects only while the reset holds the pitch within ~150 px (~9°).
- **Unmeasured:** the stick durations; live refuses until they are measured.

**F4:**
- `EDGE_X_M = None` refuses near.
- With an edge: ceiling edge − 1.5 m, strafes ≤ 0.15 s each with a fresh pose, and the side must be known (tested
  with a monkeypatched 4.5 m).

**F5:** `MAX_STEPS = 150`, counted on every call. The alternating PAIR/LOST case at dt = 0 hands back within it
(test).

**F6:**
- **2 of 3 frames:** a pose needs two agreeing frames (test: one of three is LOST).
- **Labels:** `labelled.json` is committed and SHA-pinned; the builder has no `label or got`.
- **IN-SAMPLE:** marked in the module docstring and in the tests.
- **Two real pairs now rejected conservatively:** frame-cut `near-02`, and mid-combo `000007` (the old tightest
  margin).

## Checks

- **Placement tests:** `tests/test_placement.py` 264 passed (~64 s: the bias grid dominates); `tests/test_place.py`
  27 passed.
- **Suites:** SUITES_PLACEHOLDER

## What the look must now also deliver

(All listed in `placement.md` section 7.)
1. Frames at known lateral positions: localisation ground truth, and the real bias bound.
2. Real lower-plaza frames at 10-20 m, approaching the terrace wall.
3. PITCH_RESET durations, and the pitch they land on.
4. The left edge: walls and planters along its whole length?
5. Where the right rail ends.

The intake lane must tag the look's spans rejected ("placement look").

## Assumptions the reviewer should check

- The left side is not a drop (the left-strafe rule).
- The drop zone is y ≥ −10 m.
- The scale error is ≤ 10 % at the reference pitch.

All three are marked UNVERIFIED in code and doc.
