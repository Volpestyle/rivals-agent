# Review: VUH-1314 fragment-contract repair (tracker → loop → controller, `range_skill_mode`)

Reviewer: `tracker-review` (Claude, read-only; the code's author was a Codex worker). Target: the uncommitted working tree at HEAD `83c6739`.
`git diff` matches `vuh1314-fragment-repair.patch` byte for byte, and `tests/test_tracked_body_execution.py` matches its copy, so there is no drift.
No repo file was edited. Scratch scripts: `scratchpad/review/scenarios.py`, `scenarios2.py`. Run them with
`uv run --offline --no-project python -B <script>` from the repo root.

## Verdict: **approve with required fixes**

The snapshot plumbing is sound: it is detached under the lock, touches nothing outside range mode, leaves policy inputs unchanged and costs almost nothing.
It fixes the native d53 failure. The controller still has no live-effective rule that rejects genuine identity conflicts, though. On the tracker's documented
stacked-pair hole it now presses LT with the crosshair on a *non-target* bot and past the reach cap, where HEAD refused. That is the
"arbitrary same-ID union" the spec excludes. It must not drive live input until F1–F3 are fixed and the delta is re-reviewed.

## Findings (most severe first)

### F1 (High, blocking): no live-effective identity-conflict rejection. Offense is authorized on any same-ID group, including two bodies

- **Where:** `agent/controller.py:681-743` (`_range_body_measurement`) and `agent/tracker.py:312-319` (snapshot construction).
- **Why nothing rejects a conflict live:**
  - *Class consensus* (`controller.py:719,732`) can never fire. The tracker only ever gives an id to boxes of the track's own class (`tracker.py:170,182,206,254`).
  - *Distance consensus* (`controller.py:736`) does nothing live. The reflex finder never sets `distance`: `perception/outline.py:396` builds `Detection(cls, bbox, conf, plate)`, and the only
    `distance=` producer in `agent/ perception/ scripts/` is a probe fixture (`scripts/range_cast_probe.py:385`). Every member is `None == None`.
    The new test hides this because its fixture carries `distance=13` (`tests/test_tracked_body_execution.py:12`).
  - *The "body witness" is an id group-by.* `TrackedBody` is built after association by grouping `raw` on `track` (`tracker.py:314-318`).
    It does not carry the tracker's real association: the `_bodies` stacked-split groups, the direct match, and the `_body_of` pieces (`tracker.py:251-269`).
    The controller's partition checks (`controller.py:713-729`) re-derive that same group-by from `raw`, so they are tautological.
    The witness adds no information beyond `state.detections`. The docstring "An ID alone is not a body witness" (`controller.py:685`) describes a
    property the code doesn't have. S7: a hand-built witness whose two same-id members are 1180 px apart is accepted, with union `(20,100,1260,700)`.
- **Concrete failing scenarios** (real `Tracker` → `State` → `Controller`, warmed `ARM_FRAMES` on the target alone, live-like `distance=None`, 1280×720, crosshair at (640,360)):
  - **S3b (wrong body):** the target is a near bot `(600,380,680,580)`, id 1. A smaller bot `(610,270,660,375)` stands just above its head, which is the
    tracker's `_bodies` stacked rule (`tracker.py:98-108`; `_bodies` groups `[[1,0]]`), so both get id 1.
    HEAD: `target_missing_or_ambiguous`, LT 0. Patch: **`accepted`, LT 1.0**, union `(600,270,680,580)`. The crosshair lies on the *other* bot and not on the target.
    `aligned` passes because `_aim` accepts ±half the union (`controller.py:1054`): ey = 65 ≤ 155.
  - **S5c (reach cap bypass):** two stacked boxes `(630,350,640,370)` (20 px) and `(631,332,639,348)` (16 px). Alone, the 20 px box is refused
    `outside_reach` (S5; 23.4 px is `reach_h` at 720). HEAD refuses the pair as ambiguous. Patch: **`accepted`, LT 1.0, ly 1.0**, union 38 px.
    With `distance=None`, `beyond_reach` falls back to the union's height (`controller.py:347-352, 837-839`). The code comment at `:734-735` guards against exactly
    this outcome through the distance path, which is never populated live.
  - **S4:** the tracker lane's own documented hole (`docs/lanes/tracker.md:51-53`, two 250×200 boxes 10 px apart at 1440p) now gets
    walk authority (ly 1.0) on a 410 px union. HEAD refused it.
- **What is fine:** the lane residual "smaller bot inside a confirmed near bot" (`tracker.md:66-68`; S2, 1440p) does *not* move the measurement.
  The union equals the near bot's own box `(1000,400,1250,1000)`, because a `_body_of` piece must lie ≥70% inside the padded body. The
  conflict risk comes from multi-box `_bodies` groups, not from pieces.
- **Useful discriminator, measured:** the demonstrated native failure is joined *only* by `_body_of` pieces. `Tracker._bodies` on the d53 reflex
  fragments gives `[[0],[1],[2],[3]]` and on the context fragments `[[0],…,[4]]`: no stacked groups. S3b, S5c and S4 are all multi-box `_bodies` groups.
- **Required fix (the owner chooses the rule; each option must meet the tests in F3):**
  1. Export per-member association provenance from `_update`: the direct-match group, `_bodies` multi-box groups, `_body_of` pieces and `_entering` slivers.
     Do not group raw by id after the fact. In the controller, re-check the relation geometrically, for example each piece ≥ `PIECE_INSIDE` inside the direct body's padded box,
     so a hand-built witness cannot bypass it (S7).
  2. Union only a direct body plus its pieces. Keep refusing any target id whose members include a multi-box `_bodies` group, which is the status quo for that
     geometry, until native evidence separates split-in-two from two-stacked-bodies. This keeps the d53 repair. It also re-refuses the new test's synthetic
     two-piece stack `(600,260,680,350)+(600,355,680,460)`, which is a `_bodies` group and not the demonstrated native failure.
  3. Optional extra signal, unverified: two members that both carry `plate=True` have two nameplates, so they are two bodies. d53 has exactly one `plate=True`
     member (report.json). Measure on native fragments before relying on it. Today `consensus("plate")` silently erases this evidence into `None`.

### F2 (Medium): a routine "target not in the crop" now reports `invalid_tracking_observation`, which breaks the reason taxonomy and the probe's latch classification

- **Where:** `controller.py:743` returns `None` when no body carries the target id, and `:814-816` maps that to `invalid_tracking_observation`.
- **Scenario (S6):** warm on a bot, then at t=3.0 (target expired, `coasting=()`) the crop holds only another bot. HEAD reports `target_missing_or_ambiguous`; the patch reports
  `invalid_tracking_observation`. That one string now means both a malformed witness and an absent target.
- **Consumers affected:** `scripts/range_cast_probe.py:27-28,74` latches only `TARGET_REFUSALS | HARD_REFUSALS` and ignores the new reason.
  This is not demonstrated to misfire today, because a confirmed target always coasts first and `target_coasting` latches before expiry. Diagnostics that count
  `target_missing_or_ambiguous` (e.g. `data/diagnostics/range-request-20s-counts-20260922/analyze.py:118`) would undercount.
- **Required fix:** when the observation is well formed but the target id has no body, fall through to the existing `target_missing_or_ambiguous`.
  Reserve `invalid_tracking_observation` for malformed or mismatched witnesses, and add it to the probe's `HARD_REFUSALS` so it latches.

### F3 (Medium): the tests cover one synthetic positive and its negative. They lack the native failure and every conflict control

The 4 tests (2 × parametrized) check that the raw split still refuses and that the observed split equals the whole-body outcome. Missing, per AGENTS.md "Validate measurements early":
- **Native positive:** the d53 reflex fragments (report.json) with `distance=None`. S1: HEAD refuses; the patch accepts, union `(1140,610,1521,1091)`, 4 members.
- **Genuine-conflict negatives:** S3b (crosshair on a stacked non-target bot), S5c (two stacked beyond-reach boxes), and the lane hole S4 must refuse. The lane residual S2 should document that the union equals the body box.
- **Distance disagreement:** the one conflict rule that is implemented is untested.
- **Absent target reason** (F2 / S6).
- **Malformed witness table:** t, frame or coasting mismatch; `raw != state.detections`; forged `bbox`, members, duplicate or cross-class members; a hand-built far-apart witness (S7).
  About 25 conditions in `_range_body_measurement` have no direct test.
- **Loop plumbing:** `range_skill_mode` passes `tracking_observation` and logs `body_observation` and `origin.coasting`; `NoTracker` in range mode falls back to
  `source: raw_single`; non-range mode never passes it.
- **Equivalence and detachment:** a single-member body with an observation gives the same pad/reason as the raw rule (S0 holds, untested), and a later `update()` leaves a taken snapshot unchanged (S8 holds, untested).

### F4 (Low): a defect in any non-target detection now vetoes the target (possible, unobserved stall)

- **Where:** `controller.py:698-709` validates *every* raw detection, and one failure refuses the target and cancels arming and any pulse (`_range_cancel`).
- **Live finder (verified by reading the code):** bboxes are tuples of Python floats rounded to 0.1 and inside the crop (`outline.py:374-385,396`, `loop.py:129`). conf is 0.9 or ≥0.5,
  `plate` is bool or None, and `tagged`/`distance` are None, so ordinary frames pass.
- **One theoretical path (code-read, not reproduced through pixels):** a bar-projected body box clipped at the crop's bottom edge. `top` can
  sit within 0.05 px of `ih`: the `box[3] > box[1]` filter at `outline.py:385` runs before `round(v, 1)` at `:396`. Then y1 == y2, which fails `:704`.
  That needs, for example, a bar 138 px wide (0.42·w ends in .96) whose bottom sits 58 px above the crop's edge.
- **Recommended:** validate the target body's members plus the partition, and do not let an unrelated box's geometry veto the target.

### F5 (Info): log semantics

- `origin["coasting"]` (`loop.py:772`) overwrites `row["coasting"]` through `row.update(origin)` (`loop.py:1006,1016`). The shape is unchanged (a list of ints), and
  consumers read it as a list (`analyze.py:115,119`), so nothing breaks. In range-mode rows it now means the reflex snapshot's coasting, which is what the controller used,
  instead of a later read of the shared `self.coasting`. That is an improvement; note it in `docs/lanes/loop.md`.
- `body_observation` is added to every range trace (None on refusals and cancels). No consumer reads a strict key set; the stdlib suite passes.
  Nit: `_range_body` is set at `controller.py:831`, before a possible `refuse("invalid_press_calibration")` at `:868`, so that refused trace carries a body.

## Checked and sound (no re-review needed)

- **Concurrency (Q1):** `observe()` runs inside the same `with lock` as every `update()` (`loop.py:548-556`). The snapshot is frozen dataclasses of tuples,
  detached before the lock is released. The reflex `State` is built from the snapshot's own `raw` and `coasting` (`loop.py:745,765`), so a worker `update()` between
  observe and `step()` cannot invalidate it (S8: unchanged after two later updates). The controller's `t`/`frame`/`coasting`/`raw ==` checks are therefore
  tautological in the loop: they catch mismatched non-loop callers, not races. The patch also *fixes* a HEAD race: range-mode `State.coasting` used to be read after
  the lock was released, and the worker could have rewritten it.
- **Equality (Q2):** in the loop, `state.detections` *is* `snapshot.raw`, so `==` holds. The live finder already gives tuple bboxes of Python floats, and
  `1 == 1.0` compares equal. A list/tuple mismatch arises only for non-loop callers that pair an `update()` result with a separate snapshot.
- **Refuse instead of fall back (Q4):** refusing is the right direction. Falling back to the raw rule would reopen partial-fragment aiming. No new stall appears on healthy live frames,
  apart from F4's theoretical path.
- **Measurement fields (Q5):** nothing in `_range_step` / `_follow` / `_measure` / `_aim` reads `conf`, `tagged` or `plate` beyond validation, and every member must already pass
  `conf ≥ .4`. `distance` reaches `beyond_reach` through `track.distance` (always None live). Behavior changes only through the union bbox: `track.h/w/ex/ey` → `near`,
  `far` (height fallback), `aligned` tolerance, `PLAUSIBLE`, `_fits`. That is where F1's effects come from.
- **Scope (Q6):** `update()` runs the same logic through `_update(observation=False)`. `track()` defaults to the old return, and Decider calls are unchanged.
  Outside range mode, the only change is that `reflex_coasting` is captured before `decider.offer` (`loop.py:747-748`), and no legacy `Controller.step` path reads
  `state.coasting` (only `controller.py:809`, inside `_range_step`), so the pad is unchanged. Policy inputs are unchanged: decision `dets` are `list(snapshot.raw)`, equal in value and
  type to the old `update()` output. No checkpoint, threshold, tolerance or deadline changes.
- **Single body:** S0 gives the same `accepted` / LT / ly with and without the observation.
- **Latency (Q7), measured here:** snapshot build takes 4.5 / 14 / 24 µs and controller validation 9 / 22 / 36 µs for 1 / 5 / 10 detections. That totals at most about 60 µs per reflex tick,
  under 0.3% of the ~22.9 ms HUD/coasting median and negligible against ~71 ms acquisition-to-consumption. The extra lock hold is a few µs.
- **Suites:** `uv run pytest`: 1217 passed, 61 skipped. The perception suite ran in an isolated scratch venv (`UV_PROJECT_ENVIRONMENT`), leaving the shared
  `.venv` untouched: 2015 passed, 5 failed. The 5 failures (`test_hud_accuracy`, 3× `test_replay_states` with missing `data/run1/frames.jsonl`,
  `test_scoreboard::…reads_nothing`) are missing data or fixtures. None of those tests reference tracker, controller or loop, and the same 5 fail on a clean HEAD export.
