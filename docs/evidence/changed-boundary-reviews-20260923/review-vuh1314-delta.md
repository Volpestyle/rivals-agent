# Delta re-review: VUH-1314 owner-final (tracker → loop → controller, `range_skill_mode`)

Reviewer: `tracker-review`, read-only; no repo file was edited.

**Drift check.**
- `vuh1314-owner-final.patch` (sha256 `95a2c103…`) applied cleanly to a `git archive 83c6739` export. All 14 changed and new files equal the working tree once CR is stripped.
- `summary.json`'s LF hashes of tracker, controller, loop, state, intents, brain, the probe and the three evidence scripts equal the tree. The evidence therefore describes this tree.

**Scratch scripts** (in `scratchpad/review/`, run with `uv run --offline --no-project python -B <script>` from the repo root):
- `scenarios.py`, `scenarios2.py`: the original scenarios.
- `delta_scenarios.py [seeds]`: S7 family, T1 and the tracker fuzz.
- `delta_chain.py`, `delta_chain2.py`: T3.
- `mutate.py`: runs on a scratch copy only.

## Verdict: **approve with required fixes**

The delta closes F1–F4 as specified: every scenario from the first review now lands where required. One new genuine-conflict path remains. A bot absorbed once as a piece becomes part of the reference for the next update. The union then follows that bot out of the target's footprint, and LT is authorized with the crosshair on it; HEAD authorizes nothing there. The lead accepted this residual on my first review's single-tick claim ("the union equals the near bot's own box"). That claim is wrong across updates, and D1 corrects it.

## (a) F1–F4 closure, rerun against the tree

`scenarios.py` and `scenarios2.py` were run on the working tree. The raw rule (no witness) is HEAD's result everywhere.

| Scenario | HEAD / raw rule | Tree with witness | Required | |
|---|---|---|---|---|
| S0 single whole | accepted, LT 1, ly 1 | identical | same | ✓ |
| S1 d53 reflex fragments | missing | **accepted, LT 1, ly 0**, 4 members, union (1140,610,1521,1091) | accept, ly 0 | ✓ |
| S1b d53 context fragments | missing | accepted, ly 0, 5 members | accept | ✓ |
| S0b old synthetic stacked split | missing | missing | refuse | ✓ |
| S3 / S3b stacked second bot (crosshair on it) | missing | missing | refuse | ✓ |
| S4 lane hole 250×200 pair | missing | missing | refuse | ✓ |
| S5b / S5c stacked beyond-reach pair | missing | missing | refuse | ✓ |
| S5 far single (control) | outside_reach | outside_reach | same | ✓ |
| S6 target gone, other bot present | missing | **missing** (F2) | missing | ✓ |
| S7a hand-built piece 1180 px away (ref = own) | n/a | invalid | refuse | ✓ |
| S7b forged spanning reference | n/a | missing | refuse | ✓ |
| S7c both boxes as one own group | n/a | missing | refuse | ✓ |

- **F3:** the owner's mutation claims hold. I mutated each rule in a scratch copy with the patch applied and ran the 94 new and probe tests:
  - stacked-group rule removed: 6 failed
  - approach withheld removed: 1 failed
  - piece recomputation removed: 1 failed
  - size bound removed: 1 failed
  - absent target routed to invalid: 1 failed
  - body-clear on refuse removed: 1 failed
  - **centre bound removed: 0 failed** (D2)
- **F4:** only the target's members get `_range_detection` (`controller.py:726-727`). Other bodies are checked for structure and partition only, and every one of those checks is a tracker invariant, so a live frame cannot trip it.
- **F2:** the probe latch is closed as well (`scripts/range_cast_probe.py:33`, and the new row in `tests/test_range_cast_probe.py`).

## Findings

### D1 (High, required): an absorbed piece chains across updates, so offense follows a second bot out of the target

**Where.**
- The tracker writes a body's pieces into the track box (`agent/tracker.py:298,318`).
- The next update exports that box as `reference` (`tracker.py:278,344`), and `_body_of` tests new pieces against it.
- The controller recomputes that test faithfully (`agent/controller.py:749-754`), so it passes.
- The result: "a piece never vouches for the next box" holds within one update only.

**Failing inputs** (real `Tracker.observe` → `State` → `Controller`, 60 Hz, `distance=None`, a start proposed every tick):

**T3b** (`delta_chain2.py`):
- Setup, 2560×1440:
  - target `(950,420,1200,1020)`, whole for 6 ticks
  - a smaller bot `(1100,650,1195,950)` appears inside the target's box and walks right at 4 px/tick (240 px/s)
- HEAD/raw: **0 accepted starts**.
- Tree: **2 accepted LT starts, both with the crosshair (1280,720) on the second bot and not on the target.**
  - tick 22: union `(950,420,1283,1020)`
  - tick 43: union `(950,420,1367,1020)`
- `ids` stay `[1, 1]` throughout.

**T3a** (`delta_chain.py`):
- Setup: target `(1150,420,1400,1020)`.
- At tick 59 the second bot is at x 1536–1631, entirely outside the target, and still has id 1.
- The union is 481 px wide against the target's 250.
- The step at tick 40 is `accepted` with LT 1.

**Bounds.**
- Approach stays withheld (ly 0).
- The union is capped only by `CLOSE_RATIO` × own size (`controller.py:746`), which is 2700 px at this size.
- The chain breaks when the second bot is missed for one tick. I verified this: at k=30 its id goes `[1,1]` → `[1]` → `[1,2]`.
- The entry condition is the lane residual: a new bot first appears ≥70% inside the confirmed target's box with no track of its own. The lane doc says this has not been seen live.
- HEAD's tracker already gave both bots id 1. The new part is that the range controller now authorizes offense on it.

**Required fix: a multi-member union must not grow past the target's own body across updates.** Two candidate directions; the owner picks.
1. **Controller:** refuse (`target_missing_or_ambiguous`) a union whose width or height exceeds the held id's last *single-member* measurement by more than `PIECE_PAD` × its size. That measurement must be recent, for example within the current fragment burst.
2. **Tracker:** export as `reference` the track's last box from an update without pieces, and test pieces against it.
   - The tracker's own absorption still uses the union, so a failure of this stricter test must route to `missing`, not `invalid`.
   - Otherwise it would trip the probe's hard latch on legitimate tracker output.

**Acceptance.**
- T3a and T3b refuse once the union leaves the target's box plus the piece pad. Add both as tests.
- S1, S1b and S2 still pass.
- Re-run `run.py` and report whether the 48 repaired slot-4 ticks survive.
  - Heights look safe: unions are 416–503 px against 525–536 px whole neighbours (tracker.md).
  - Widths are not in `summary.json`; `run.py` needs to record union width for this check.

**Correct the premise in:**
- `docs/lanes/tracker.md:455` ("It adds no area: the union is the near bot's own box")
- the docstring of `test_smaller_bot_inside_a_near_bot_is_a_piece_that_does_not_move_the_union` (`tests/test_tracked_body_execution.py:112-113`)

Both repeat my single-tick S2 result. Also related, not a fix: T1 (`delta_scenarios.py`) shows that when the target's own match is a fragment, even a single-tick piece moves the union centre by ~(78, 95) px, while staying inside the target's previous box.

### D2 (Low, required test): the centre bound does unique work but no test pins it

- **Where:** `controller.py:742-743`.
- **Failing input** (only the centre bound rejects it):
  - own `(100,300,160,450)`, one piece `(1000,300,1060,450)`, and `reference` = that piece's box, 900 px from own.
  - The size ratio is 1, and the piece recomputation passes because the piece sits inside its own reference.
  - Tree: `invalid_tracking_observation`. With the bound removed it would be measured as a 960 px union, and all 94 tests still pass.
- **Fix:** add this case to `test_a_hand_built_witness_cannot_unite_distant_boxes`.

### D3 (Info): what the bounds prove about a forged witness

- A forged reference inside both bounds still unites two separate boxes (S7d):
  - own `(600,300,660,450)`, other `(780,330,840,470)`
  - ref `(590,250,860,520)`: centre 96 < 652, size ratio 1.8
  - Result: measured union `(600,300,840,470)`.
- This matters only for non-loop callers, since live witnesses come only from `Tracker.observe` under the lock.
- The lane doc's "So a hand-built grouping by id cannot pass" is true, but it could be misread as "a forged witness cannot pass".
- Suggested wording: the checks limit a forged witness to associations the tracker could plausibly have made; they do not prove provenance.

## (b) Reference bounds and routing: sound

**Centre bound** (< (1+√2)·span → otherwise `invalid`). It is a real tracker invariant:
- the prediction moves the reference by at most max(size, 1) (`tracker.py` `_predicted`);
- the cost gate allows ≤ GATE·span, and the IoU path allows < √2·span because the boxes overlap;
- the total is < (1+√2)·span, with `span` the same max as `_cost`'s `size`.

A fuzz confirms it: `delta_scenarios.py 1500` ran 1500 seeds × 400 ticks with camera turns, aim-crop clipping, 2–5 fragment bodies, dropouts, velocity changes and strays. It produced 1.33M body evaluations and 94,535 multi-member measurements, with **0 tracker-produced witnesses routed `invalid`**. So neither the centre bound nor the piece recomputation (formulas identical to `_body_of`, same inputs) can falsely latch the probe.

**Size bound** (≤ `CLOSE_RATIO` → otherwise `missing`). It is correctly treated as a refusal, not a fault, since `_cost` may match through a remembered height. It only narrows the repair and never adds exposure.

**Routing table.** Every check in `controller.py:700-757` matches the owner's table:
- `invalid` for:
  - a witness that is not this State's
  - a broken partition or structure
  - a forged target bbox (`:730-731`)
  - a non-finite reference
  - the centre bound
  - a failed piece recomputation
- `missing` for:
  - no target body or a class mismatch
  - a target member failing `_range_detection`
  - a stacked group
  - the size bound
  - distance disagreement

## (c) `_update` bookkeeping: sound

- `reference` is captured as `tr.box` after camera turning and before `_body_of` (`tracker.py:278`). This is exactly the box `_body_of` uses, and it is stored as a tuple.
- `pieces` holds exactly the `_body_of` groups (`:283`).
- **One own group per id holds:**
  - direct matches use `used`;
  - `_entering` only takes tracks not in `used` and adds them to it;
  - `_body_of` only attaches to direct tracks;
  - a new id belongs to one group.
- A piece iterated before its own group is filled in afterwards (`:334-344`).
- A violation would fail the partition check as `invalid`. None occurred in the fuzz, whose structural assertions also held: `own` non-empty, pieces only on `matched`.
- `update()` output is unchanged. The owner's replay matches HEAD on 1068 steps, and the no-witness tree matches HEAD.

## (d) Approach withheld: sound

- `withheld = len(members) > 1` (`controller.py:854`) gates only `ly` (`:864`), the sole forward command in `_range_step`.
- Aim, arming, request accounting and pulses are unchanged. S1 and S1b give ly 0, and single-member ticks are unchanged (S0).
- `far` still uses the union height, which errs toward refusal because unions measure short.

## (e) Regressions in the 8 files: none found

- **`loop.py`:** the legacy path passes `self.coasting` at the same point HEAD evaluated it. Range mode is unchanged from the first review, which found it sound.
- **Tracker update path:** `reference` and `pieces` are read-only bookkeeping.
- **Controller non-range path:** only `_range_body = None` and a `None` trace key.
- **Probe:** one frozenset entry. Its test row and new `failure` assertion match `range_cast_probe.py:79`.
- **Docs:** `loop.md` and `range-skill-controller.md` are accurate. `tracker.md:455` needs the D1 correction.
- **Suites**, both run in isolated scratch venvs so the shared `.venv` was untouched:
  - `uv run pytest`: **1253 passed, 61 skipped**.
  - `uv run --group perception pytest`: **2051 passed, 125 skipped, 5 failed**. These are the 5 pre-existing missing-data failures (`test_hud_accuracy`, 3× `test_replay_states`, `test_scoreboard::…reads_nothing`), the same as on clean HEAD.
- The new tests embed the d53 boxes from `report.json` as literals (`tests/test_tracked_body_execution.py:25`) and open no files, so no corpus marker is needed.

## D1 round

Scope: `vuh1314-owner-d1-delta.patch`, this round's changes only. Read-only; no repo file edited.

**Drift check.**
- `vuh1314-owner-final.patch` (sha256 `f5024c88…`) applied cleanly to a `git archive 83c6739` export. All 15 changed and new files equal the working tree once CR is stripped.
- `vuh1314-owner-final-v1.patch` still hashes to `95a2c103…`, the version reviewed above.
- The v1 → tree code diff is the D1 patch:
  - `tracker.py`: `_Track.solo`, `TrackedBody.whole`, and the `whole()` projection.
  - `controller.py`: the `whole` structure checks and the cap.
  - `test_range_cast_probe.py`: the one constructor argument.
  - `loop.py` and the probe script are unchanged.

### Verdict: **approve**

D1 is closed. The trailing second bot now refuses with 0 starts, the native repair is unchanged, and no tracker-produced witness routes to `invalid`. D2 and D3 are closed. Only the two non-blocking nits at the end remain.

### (a) T3 closed; S1/S1b/S2 unchanged (rerun against this tree)

- **`delta_chain2.py`, T3b** (target left of the crosshair, second bot walking out at 240 px/s):
  - accepted starts: 0 with the raw rule and **0 with the witness** (v1: 2, both with the crosshair on the second bot).
- **`delta_chain.py`, T3a/b/c:**
  - The union grows only inside the target's box plus the pad: at most `(1150,420,1455,1020)` against target `(1150,420,1400,1020)` + 60.
  - Every tick from about +17/+20 on is `target_missing_or_ambiguous` with LT 0.
  - That holds on all ticks where the crosshair is on the second bot (T3b +25…+45).
- **`scenarios.py`, `scenarios2.py`:** results equal the table above.
  - S0 accepted, identical.
  - S1: accepted, LT 1, ly 0, 4 members, union (1140,610,1521,1091).
  - S1b: accepted, 5 members.
  - S2: `unaligned_target`, union = the near bot's box.
  - Refused: S0b, S3, S3b, S4, S5b, S5c, S6. S5 stays `outside_reach`.

### (b) `solo` / `whole` bookkeeping and projection: sound

**Where `solo` is set** (`tracker.py`, new track and update branches):
- only when the group is one box, and, for an existing track, only when `parts[tr.id] == [gi]`, meaning no pieces this update;
- `box` is then exactly that single box;
- the older-measurement branch (`t < tr.seen_t`, the worker's late whole-frame result) `continue`s first, so it never sets `solo`.

**A union can never become `whole`:**
- a `_bodies` pair (`len(g) > 1`) cannot;
- an update with pieces cannot;
- a one-box update refreshes it; an `_entering` sliver or a lone fragment can become `whole`, which only tightens the cap (refusal).

**Pairing and export:**
- `solo` stores the box with the `tr.cam` written in the same update, the pair convention the tracker uses for `tr.box`.
- `whole()` is computed after association, from the track itself. With pieces, `solo` necessarily predates this update.
- It projects with the same `_turned(box, was, cam, frame)` the tracker applies to every held box, into this frame's camera. With no camera on either side it is left unturned, which is also the tracker's rule.
- It is None past `HIST_S`, and exported only with pieces.
- The loop always passes a camera for reflex frames (`_note_cam` precedes `track`).

**What the cap does:**
- A union must stay inside the body's last one-box box plus `PIECE_PAD` × its size. Chaining can no longer grow a body past that box, because `whole` does not move while pieces are present.
- `T1` (a second bot inside the cap, pulling the centre by ~100 px) remains, correctly recorded as a residual in `tracker.md`.

### (c) The cap never routes a tracker-produced witness to `invalid`: confirmed

**Routing:**
- Missing `whole`, or a failed cap → `missing`.
- `invalid` only for a structurally bad `whole`, a non-finite `whole`, or a `whole` without pieces.
- The tracker never produces any of those: `_turned` clamps its angle and so is finite, the box is a 4-tuple, and `whole` is exported only with pieces.

**Fuzz** (`delta_scenarios_v3.py 1500`, the same generator and seeds as before, plus an assertion that `whole` appears only with pieces):
- 1500 seeds × 400 ticks, 1.33M body evaluations.
- **0 witnesses routed `invalid`.**
- Multi-member measured: **39,032**, exactly the owner's figure (down from 94,535; the cap refuses the rest).

**Hand-built witnesses:**
- S7a → invalid; S7b → missing; S7c → missing.
- S7d (the forged reference inside both bounds) → now **missing**: it has no `whole`.
- S7f (non-finite `whole`) → invalid. S7g (`whole` without pieces) → invalid.
- S7e (S7d plus a forged `whole` = the forged reference) → measured.
  - That is the stated limit: the checks hold a witness to plausible associations and cannot prove provenance.
  - Live witnesses come only from `Tracker.observe`.

### (d) The replay fix is sound and the 48 ticks stand: reproduced

**Why the fix is right:**
- The tracker's camera now comes from a second `Controller` stepped with the recorded boxes, ids and coasting.
- It reads the camera before its own step on each row, the same order as `Loop._tick` (`_note_cam`, then `ctrl.step`).
- It runs the tree's code, which matches HEAD with no witness (0 reason and 0 pad changes).
- It reproduces every recorded pad; `run.py` asserts this (`tree_observe_camera_pads_differing_from_recording: 0`).
- So the camera is the recording's, and the replayed controller's own aim no longer feeds back into the boxes.

**Rerun:** I ran the owner's `run.py`, `replay.py` and `scenarios.py` from a scratch copy, with the repo root as cwd, so `summary.json` was written to scratch, not the repo.
- The result is **identical to the committed `summary.json` in every key.**
- Fidelity: 1068 steps, 0 mismatches.
- The 64 former refusals now land as 23 `decision_expired`, 9 `no_new_start`, 16 `duplicate_no_new_start` and 16 still refused. That is **48 measured**, with `ly` 0 on all 64.
- Union widths are 379–470 px, at most 0.99 of the last one-box width.
- 9 of the 12 decisions are repaired.
- Starts 0 → 0, LT 0 → 0, forward ticks 76 → 76, 484 aim-only ticks. The log hash was unchanged before and after.

### (e) D2, D3 closed; regressions: none

**D2 closed.** I mutated each rule in a scratch copy with the full patch applied and ran the new and probe tests (99 tests):

| Mutation | Tests failed |
|---|---|
| centre bound removed | **1** (was 0 in v1) |
| `whole` cap | 2 |
| no `whole` → missing | 1 |
| stray `whole` without pieces | 1 |

**D3 closed:**
- `tracker.md` says the checks hold witnesses to plausible associations, not provenance.
- The single-tick premise is corrected there, and in the S2 test docstring (`tests/test_tracked_body_execution.py:113-115`).
- `range-skill-controller.md` states the capped rule.

**Suites**, run in scratch venvs:
- `uv run pytest`: **1258 passed, 61 skipped**.
- `uv run --group perception pytest`: **2056 passed, 125 skipped, 5 failed**. These are the same 5 pre-existing missing-data failures.

### Non-blocking nits

1. **Two `whole` checks are unpinned.**
   - Removing `non-finite whole → invalid` passes all 99 tests: a NaN `whole` would fall to `missing` through the cap comparison instead.
   - Removing the `whole` structure check (`tuple`, length 4) also passes all 99. Verified on a scratch copy with the check removed: a 3-tuple `whole` raises `IndexError` inside `_range_body_measurement` instead of routing to `invalid`. The tree returns `invalid`.
   - Add both to the malformed-witness table.
2. **`tracker.md` wording.** The sentence "A reference forged inside both bounds can still unite two separate boxes (review S7d)" comes before the `whole` cap. S7d alone now refuses (`missing`); it needs a forged `whole` as well (S7e). Suggest: "…inside both bounds, together with a forged `whole` around both, …".
