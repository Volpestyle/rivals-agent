# Review: uncommitted `perception/camera_motion.py` change (+212/−9) and `tests/test_camera_motion.py` (+148)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main` `9e0fbfb` plus the working-tree
diff described in `idm-decisions-applied.md`.

- **Read:**
  - the full diff;
  - the unchanged `compare()`, `run_proxy` and `run_video`;
  - the l2 probe section of `docs/lanes/l2-hud.md` (lines 2090-2260);
  - the request-fit driver's code closure;
  - the intake's snapshot use;
  - every file under `data/human/` that names `camera_motion.py`.
- **Ran:**
  - **Tests.** `tests/test_camera_motion.py` with system Python and caches off: **26 passed** in 44 s. Nothing was
    written to the checkout, and the shared `.venv` was not re-synced.
  - **The new estimator on the l2 probe's own range proxies** (`C:/rivals-agent/data/l1/baseline1..4`, ~9.3 Hz, 720p).
    - It ran single-threaded at below-normal priority, about 4 CPU-minutes.
    - **The game was running and OBS was recording**, so I kept the run small and streamed. Available memory stayed
      above 5 GB.
    - Script and output: `camera-review-regress.py` and `.out`.
  - **Three frame composites**, inspected by eye: `camera-review-*.png`.
  - **Two small synthetic probes**, reproduced inline below.
- **Not done:** no repo edits, commits or Linear writes, no game input, and no replay decode.

## Verdict: APPROVE WITH REQUIRED CHANGES. Do not commit the per-pair rule as it stands

**Sound:**
- the intent: an overlay-won zero becomes unknown, not 0;
- the `abstain` reason on every withheld pair;
- the symmetric spectator mask;
- the focal-fit refusal gate.

**Not yet right:**
- the per-pair rule's "world changed" test also fires on real still-camera pairs whenever something moves in the frame
  (C1);
- `run_video` applies the window verdict to the whole requested span (C2);
- the still-camera test cannot fail (C3).

**Pinned artefacts:** none changes (C6). But the l2 lane's published probe numbers stop being what the working tree
reproduces.

## Findings

### C1 (serious): the "world changed" test withholds true still-camera pairs on real range footage

**The rule.** `pair_abstain` withholds a zero-flow pair when the mean grey change over the centre side strips exceeds 4
levels (`PAIR_WORLD_DIFF`). The strips are x 0.20-0.36 and 0.64-0.80, y 0.25-0.75, via `_centre_world`.

**The flaw.** That number rises for anything that changes in those strips:
- ability and attack VFX;
- a bot moving;
- the character's limbs during a combo;
- translation while the camera does not rotate.

None of these is a camera rotation.

**Measured on the l2 proxies.** Up to 60 sampled pairs per stratum per run, seed 0, run through the new `Estimator.step`.

| Run | Still pairs with world diff > 4 | Still, withheld (of sampled) | Attack, withheld (of sampled) | Ability | Turn |
|---|---|---|---|---|---|
| baseline1 | 16.6% (of 806) | **6 / 60** | **7 / 60** (7 of its 9 zero-flow pairs) | 2 / 60 | 1 / 60 |
| baseline2 (still run) | 0% (of 2,775) | 0 / 60 | 0 / 16 | – | – |
| baseline3 | 14.8% (of 789) | **3 / 60** | **10 / 60** (all 10 of its zero-flow pairs) | 4 / 60 | 1 / 60 |
| baseline4 (spin) | 0.3% (of 346) | 0 / 60 | 1 / 14 | – | 0 / 60 |

- **Rules.** Every withheld pair was withheld by the world-change rule. The border rule never fired on about 700 real
  range pairs.
- **Still-pair world diff.** p50 0.8-1.8, p90 2.3-7.7.
- **Coverage.** Extrapolated by stratum size, baseline1 falls from 0.84 to about 0.76 and baseline3 from 0.79 to about
  0.73. The still and spin runs barely change. These are sample estimates.

**What the frames show.**

| Composite | What happened | Verdict |
|---|---|---|
| `camera-review-still-1398.png` | Neutral stick, 722 inliers, border share 0.56. The whole difference image is black except one glowing effect blob left of centre | A true still camera, withheld because of one effect. **This is a regression** |
| `camera-review-still-97.png` | The character jumps; the camera translates with him; the zero-flow fit has 158 inliers, 91% in the border strips | Withholding is right here: the rule also catches real failures on range footage |
| `camera-review-attack-1324.png` | A web impact and a melee pose in a static room | Most likely a camera held still by combat, now withheld |

**Synthetic confirmation.** A still camera, with one filled circle changed in the left centre strip:

| Circle diameter at 1280x720 | World diff | Result |
|---|---|---|
| 40 px | 1.27 | Kept |
| 60 px | 2.62 | Kept |
| 80 px | 4.56 | **Withheld** |
| 100 px | 7.02 | **Withheld** |

An 80 px change is about one mid-range bot or one ability effect.

**Why the attack stratum matters.**
- The l2 probe's own finding is that "combat holds the camera... here the video is right and the map is wrong"
  (`l2-hud.md`, "What breaks it").
- The rule withholds most of exactly those zero readings (17 of 19 in baseline1 and baseline3).
- So the attack stratum loses its disagreeing zeros, and its estimated-versus-map agreement (reported r 0.62-0.80) will
  *rise* for a reason that is not accuracy.

**Required.** Decide a zero from the world's own matches, not from mean pixel change. The ratio-tested matches are
already in `compare()`:
- **keep** a zero only when enough matches in the centre strips (for example ≥ 20, body excluded) themselves have
  median displacement ≤ `ZERO_FLOW_PX`;
- **withhold** it when the centre has too few matches, or when they show displacement.

The same three synthetic cases through that test:

| Case | Centre matches | Centre median displacement | Decision |
|---|---|---|---|
| Still camera plus 100 px blob | 585 | 0.0 px | Kept (correct) |
| The replay failure (soft world turns 4°, sharp UI) | 0 | – | Withheld (correct) |
| Sharp world turns 4° | 264 | 44.8 px | The fit's own non-zero flow stands |

- Keep `world_diff` as a diagnostic column.
- Validate on the M1 rerun's live windows with known mouse counts, as already planned. Report kept and withheld still
  pairs, not only withheld moving ones.

### C2 (serious): `run_video` invalidates the whole requested span with one verdict

**The behaviour.**
- `run_video` now ends with `steps, verdict = checked(steps)` over *everything it decoded*.
- A span where more than half of the fitted pairs have zero flow has **every** rotation withheld, including its turns.
- The verdict's own comment accepts this: "A camera that really held still is withheld too".

**Where it hurts.**
- For 3 s replay windows (the way `measure2.py` calls it), that is the intended behaviour.
- For the l2 CLI on a whole 60 fps range recording (`python -m perception.camera_motion video clip.mp4 out.jsonl --hz
  60`), one mostly-still recording loses all its rotations.
- The zero-flow share of still pairs I measured was 28-59 of 60 per run, even at 9.3 Hz.
- `loop30g`, the l2 lane's slow-aim result (r 0.80, direction 100%), was called "too still to say anything" about lag.
  It is the run most at risk.

**Required.**
- Apply the verdict over fixed sub-windows (for example 3 s) inside `run_video`, or make it opt-in with the spectator
  mask.
- Count only zero-flow pairs that C1's centre test could not confirm as still.

### C3 (moderate): the tests prove the failure path, not the still-camera path

1. **`test_a_camera_that_really_held_still_keeps_its_zero`** compares a frame with an exact copy of itself.
   - `world_diff` is 0.0 by construction, so the test cannot fail.
   - Real still pairs are never identical: p50 0.8-1.8 grey levels, and some exceed 4.
   - Required: a still camera with an animated patch in a centre strip, like C1's blob, expected **kept**. As written the
     current rule fails it.
2. **The replay-failure tests are an honest mechanism reproduction, not a reproduction of the replay.**
   - They build the conditions under which the UI wins: the world is blurred (σ 3) and its contrast halved (`_soft`),
     under a sharp pasted UI, then one 4° step.
   - That matches the real mechanism: ORB's 1,500-feature budget goes to sharp UI text.
   - It does not show that the replay's world is soft, or that the masks fix M1. Only the masked rerun can.
   - Say so in the docstrings. "The replay failure" overclaims.
3. **The border rule is tested only on hand-made `Step` objects.** It never fired on real range footage, so neither its
   firing nor its restraint is exercised on images.
   - Its comment "a uniform scene gives about 0.7" does not match what the file's own `texture()` scenes give (0.57-0.58).
     Real range pairs span 0.16-0.98.
4. **The focal tests use ideal correspondences:** whole-frame points, ±6° rotations, 0.3 px noise.
   - They check the code, and the tiny-turn refusal is a good test.
   - But they are not evidence that M2 is conditioned on footage: real fits were 590-860. Label them as code checks.
5. **Missing:** a test that a mostly-still whole-span `run_video` does not null its turns (C2).

### C4 (minor, a bug): `Estimator.last_matches` goes stale on early returns

- `compare()` returns before setting `self.last_matches` in two places: no descriptors, and fewer than `MIN_INLIERS`
  ratio-tested matches.
- The previous pair's matches then remain. A caller that collects `last_matches` after each step for `focal_fit` would
  add the previous pair twice and attribute it to the wrong interval.
- Fix: set `self.last_matches = None` at the top of `compare()`.

### C5 (minor): the threshold depends on frame rate and on bots

- `PAIR_WORLD_DIFF` is a per-pair pixel change, so the same animation scores several times higher at 9.3 Hz than at
  60/120 fps.
  - One constant cannot serve both the proxy path (`run_proxy`) and the 120 fps replay path.
  - The C1 test removes this dependence.
- `world_diff` also counts logged enemy boxes (moving bots) that `mask_for` already excludes from features.
- If the rule stays, scale the threshold by `dt`, and mask the dets out of `_centre_world`.

### C6 (information): pinned identities and evidence

**Nothing pinned changes bytes.**
- **Code snapshots.** Every snapshot copy is a separate file with sha256 `9d1cb99a…`, git blob `6bb2c55`: under
  `data/human/sessions/code-snapshot-c0892ab/` and `data/human/inspection/…/code-snapshot/{git-archive-0f71336,
  git-archive-ae648b33, worktree-copy-0f71336}/`. The live edit does not touch them.
- **Artifact hashes.** The request-timing v3-v5 `artifact-hashes.json` files pin those *copies*, not the live path.
- **Request-fit driver.** Its closure (`docs/evidence/range-request-human-fit-20260922/fit_cohort_20260923.py:40-44`)
  checks `agent/*`, `policy/*`, `perception/hud.py`, `outline.py`, `loop.py`, `brain.py` and `tracker.py`. It does not
  check `camera_motion.py`.
- **Whole-session intake.** It imports from the archived snapshot (`data/human/sessions/intake_session.py:18, 76-77`),
  so it never loads the live file.
- **The PC runtime copy** (`C:/rivals-agent/perception/camera_motion.py`, 27,186 bytes, 09-21) is separate.
- **The flag rename** (`replay` → `spectator_mask`) never reached a commit and has no callers.

**What does change.**
1. **l2's published results.**
   - `docs/lanes/l2-hud.md` publishes the coverage table (0.84 / 0.79 / 0.59 / 1.00), the stratum claims and the 60 fps
     results.
   - The working tree now produces different numbers: C1 on `run_proxy`, C2 on `run_video`.
   - `camera_motion.py` is the l2 lane's probe (`l2-hud.md:503, 2092`). The l2 owner should state which commit produced
     its tables (`2920ceb`), or the new rules should stay off the pad-logged proxy path until validated.
2. **The CLI summary.** "coverage" now excludes withheld pairs, so it changes meaning.
3. **Future code snapshots.** `human-admission.md:509-511` says "git diff 72eee24..c0892ab is empty for … perception".
   Once this lands, no later snapshot may reuse that sentence.

## The three questions, settled

1. **Coverage regression.** Yes, the rule withholds true still-camera pairs on real range footage.
   - Frame evidence: pair 1398. Synthetic threshold: about an 80 px change.
   - In the two combat-heavy l2 runs, about 5-10% of still pairs and most zero-flow attack pairs are withheld. Coverage
     falls by roughly 6-8 points; the still and spin runs barely change.
   - It also biases the attack stratum toward agreeing with the map (C1).
2. **Are the synthetic tests honest?**
   - As mechanism checks, yes: sharp UI, soft world, one step.
   - As a reproduction of the replay failure, no. The softness is manufactured, and only the masked rerun can confirm it.
   - The still-camera test is trivially true and hides C1 (C3).
3. **Pinned identities.** None changes (C6). The l2 lane's published probe numbers are no longer reproduced by the
   working tree, and that needs recording.

## What is sound

- **Withheld, not zero.** Rotation fields are nulled with `replace`, and the reason (`abstain`) and the diagnostics
  (`world_diff`, `border_frac`, flow) are kept. `Step` and `read()` stay compatible through defaults.
- **The spectator mask.** It is applied identically to replay and live, and documented that way (F3). The new
  `window_overlay` learns from the window's own sparse sample.
- **The window verdict,** for short replay windows: invalid windows are reported with a reason and their flow is kept.
- **`replay_focal`.** It refuses to fit the replay unless the same fit first recovers the calibrated focal on live
  footage, with a sharp basin. Tiny turns are refused on basin width even when their best value happens to be 465.
- **Thresholds marked provisional,** with a stated validation plan: live windows with known mouse counts.
