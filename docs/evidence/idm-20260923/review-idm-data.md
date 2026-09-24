# Review: the inverse-dynamics data step (VUH-1353): `policy/idm_targets.py` and `scripts/replay_camera.py`

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**The target moved twice during the review.**
- The builder went from `20c2a440` (the hand-back) to `3043d55d` (20:30), which declared goh_targeting unsupported,
  and then to **`b0a5ea48`** (about 20:35), which follows your corrected decisions. The four target files were rebuilt
  both times.
- The build logic (`split_row`, `build`, `header_from`, `load`) is the same in all three versions. Only the support
  declarations and their test changed.
- **I reviewed the final bytes and checked the final rebuild.**

| File | sha256 |
|---|---|
| `policy/idm_targets.py` | `b0a5ea48…` |
| `tests/test_idm_targets.py` | `ada07279…` |
| `scripts/replay_camera.py` | `1d822a11…` (as handed back) |
| `tests/test_replay_camera.py` | `389f1784…` (as handed back) |
| `docs/lanes/inverse-dynamics.md` | `ba81fb46…` (the data-step entry now records both decisions) |
| Targets: 051828, 171533, 200129, 205528 | `b203de7c`, `1f2aa5f1`, `65745238`, `e8236d6e`, all built by `b0a5ea48` |

**Ran** (in my own environment built from the lockfile, below-normal priority, 16.9 GB free):
- **Tests.** `tests/test_idm_targets.py` and `tests/test_replay_camera.py`: **16 passed**, on the final bytes and on
  `3043d55d`.
- **An independent join of every built interval against its admitted step table** (`idm_verify.py` in my scratchpad):
  - the file loads through `idm_targets.load`;
  - every parent row is joined;
  - checked per parent: times, copied fields, sums, holds, mouse counts, the frame and the known flags;
  - checked per file: calibration and identity against the step header, the source hashes against the files on disk, the
    denylist against its pin (`57cfe01f`).
- **A speed profile** of the camera targets against the calibration turn.

**Not done:**
- no decode, and no estimator replay run;
- `replay_camera` was not run on the capture;
- no edits;
- 053616 not read. Its absence was checked by folder name only.

## Verdict

**`idm_targets`: land, after one fix (S1).**
- Five of the six questions are settled on the built files. The sixth, excluding the sealed take before any read,
  holds today only by accident.
- The acceleration caveat is carried in the header, but it covers most of the camera signal, and target consumers do
  not see it (S3).

**`replay_camera`: sound, and land it after its dependencies.** It needs `scripts/replay_steps.py` (untracked) and the
uncommitted `policy/range_bc/steps.py` change: `REPLAY_SPLIT`, which `replay_steps.header()` uses and HEAD lacks.

## The six questions

**1. Does every interval's parent row match exactly? Yes, on all four rebuilt files.**
- **85,488 parents, 170,976 intervals, two per parent** (no stale-frame drops), and no interval without a parent.
- Zero mismatches in any of these:
  - `t0`/`t1` equal to `(a, a + step // 2]` and `(a + step // 2, a + step]`;
  - run, segment, suitability, regime and gap_free equal to the parent's;
  - the presses and releases of the two halves sum to the parent's;
  - `held_start` of half 0, `held_end` of half 1, and the two halves meet at the midpoint;
  - mouse counts sum to the parent's wherever `relative_known`;
  - half 0's `frame0` is the parent's frame;
  - `held_known` equals the parent's on every action, never more known and never less.
- The step table and imported demo hashes in each header equal the files today.
- The binning is `write_steps`'s, line for line:
  - the id groups are the header's bindings, which already include aliases, as `reviewed_identity` builds them;
  - a press needs a known state before the rise;
  - events fall in `(t0, t1]`.

**2. Does any interval span a run boundary or a withheld span? No.**
- Each interval is half of exactly one parent, and `write_steps` emits a parent only inside one review segment ∩ focus
  interval, strictly before its end, and inside one run. A capture gap ends the run, and a step touching a gap is not
  `gap_free`.
- **Non-accepted spans are in the file, labelled.** 472 parents (944 intervals) are `rejected` or `unresolved`.
  `usable()` excludes them, and so does `supported_actions`, but `target()` does not check (S2).

**3. Do the degree targets use the pinned calibration, with pitch flagged and the acceleration caveat carried? Yes in
the header; the caveat does not reach `target()`.**
- The header copies the step table's calibration exactly: `slow_turn_constant`, yaw 0.0330738°/count from the 360°
  closure, pitch `derived_equal_sensitivity`, `accel_on: true`, source `calibration.json (v2)`, which is `baa49158` on
  disk.
- `accel_on` is also an identity field.
- The reader recomputes every degree from counts × gain.
- **S3, the extent of the caveat.** The gain was measured on one turn at about 915 counts/s (30°/s), and its speed
  dependence is recorded as "open", with in-game Mouse Acceleration and Smoothing on. Of the 170,032 usable intervals:

  | Faster than the calibration turn | Intervals | Share of all yaw counts |
  |---|---|---|
  | 1× (> 30°/s) | 39.3 % | **91.7 %** |
  | 2× | 25.8 % | 80.9 % |
  | 4× | 14.0 % | 62.5 % |
  | 8× | 4.9 % | 34.8 % |

  - So the caveat covers most of the camera signal.
  - `beyond_pad_envelope` (5.3 %) is computed on the slow-turn degrees. If acceleration raises the gain at speed, it
    undercounts.
  - `target()` returns `pitch_known: True` on every row, with no sign that pitch is derived.
- **Required:**
  - `target()` (or `load`) passes through `degrees_kind` = `calibration.kind` and `pitch_derived`, so a trainer or
    `idm_eval` can stratify;
  - Gate 1's camera error is reported by speed band (≤ 1×, 1–4×, > 4× the calibration rate) until a fast-turn
    calibration exists.

**4. Do edges ever cross the importer's segment boundaries? No.** Parents lie strictly inside `segment ∩ interval`
(`anchor + step < hi`), halves inherit the parent's segment (zero mismatches), and events are taken from `(t0, t1]`
inside the parent.

**5. Is the sealed take excluded by the denylist before any read? Not by construction (S1, required).**
- `build()` never loads the denylist.
- It reads the whole step table and hashes the whole imported demo **before** the first sealed check. That check is
  `hd._placement` on the registry, which lists 053616 as `test`, followed by `header_from`'s split check.
- It skips `load_dataset`'s header-first sealed check and intake's denylist-first `check_registry`.
- Today no sealed byte can be read, but only because 053616 has no folder under `data/human/sessions` (checked by
  name).
- `load()` refuses a `test` header before rows, but does not check the denylist either.
- **Required:**
  - at the top of `build()`, load the pinned denylist (`steps.load_denylist`, `57cfe01f`) and run `assert_not_sealed`
    on the session id before forming any path;
  - read only the step table's header line first, then check its `media_sha256` against the denylist and its split;
  - place the session through `hi.check_registry(REGISTRY, denylist=…)` before opening the demo;
  - apply the same id and media check in `load()`;
  - add a test showing that a denylisted id is refused with no file opened.

**6. Can replay camera rows reach the human targets? No; there are four independent barriers.**
- `build()` reads only `data/human/sessions/<id>/`, requires the id in the corpus registry and an imported demo that
  hashes to the step table's pin.
- `header_from` refuses a `source_kind` other than human, and a split outside train/val. Replay tables now carry split
  `replay` (the uncommitted `steps.py`).
- `load()` recomputes every degree from mouse counts × gain, so an estimator degree cannot pass.
- `idm_targets` imports neither replay script.
- `replay_camera` writes only a new `<table>.camera.jsonl` (exclusive create), and `load_cohort` refuses the replay
  split without `allow_replay`.
- **Minor.** `source_kind` defaults to "human" when absent, because human tables do not write it. The split check is the
  real barrier.

## `replay_camera`

**Settled.**
- **Source is honoured.** The default is `("main",)`, enforced inside `fill_camera`.
  - The landed estimator flags its outlier-refit rotations `source="centre"` too, so the default excludes both kinds of
    imprecise rotation.
- **The per-row why-unknown note mirrors `fill_camera`'s walk:**
  - gap, withheld (with the estimator's reason), source not accepted, no fit, no pair;
  - it is written only on unknown rows and is never a model input.
  - Where two reasons apply, its check order differs slightly from `fill_camera`'s (source before a missing fit). That
    changes only which reason is named.
- `check_camera_run` requires the meta line, `spectator_mask: true` and `t_offset` 0. It checks the output with
  `check_replay_header` and `check_replay_row`, and never modifies the input table.

**Suggested:**
- `check_camera_run` matches the capture by basename only. Also compare the run's full path, or have the run record
  the media sha256 and compare it with the table's `media_sha256`.
- Add the run's `focal` and "viewer FOV unverified (M2 refused)" to `source.camera`: replay degrees use the live
  calibrated focal.
- The known residual still applies: on live turns about 2 % of large moves report a main-source zero.

**Landing order:**
1. the `steps.py` replay-split change;
2. `replay_steps.py`, whose own 3 table tests fail here, and whose press-coverage issues are in
   `review-replay-hud-2.md`;
3. `replay_camera.py`.

## Lead decisions, as corrected, against the final bytes

- **team_up supported.** It is not declared unsupported, and 168 ≥ 50. The comment gives your reason (the range HUD
  effect) and the match caveat.
- **goh_targeting supported by the floor,** 51 ≥ 50. `DECLARED_UNSUPPORTED` is empty. The test's declaration is now a
  synthetic `declared={…}` argument, not a real one.
- **melee unsupported** (23), along with ultimate (9) and simple_swing (16), by count.
- My reproduced train press counts equal the hand-back's for all 15 actions.
- **For you to know:** goh_targeting is 1 press over the floor. When F1 allocates the held-out split, moving any
  session out of train re-counts support, and goh_targeting can flip to unsupported automatically. That is the
  pre-registered rule working, but it will change the action set.

## Smaller findings

- **S2.** `target()` does not refuse non-usable rows. Either make `target()` require `usable(r)`, or give the reader a
  `training_rows()` so a trainer cannot pick up the 944 rejected or unresolved intervals.
- **S4.** No test pins the decisions on the real configuration. `DECLARED_UNSUPPORTED == {}` and team_up counting by
  its presses are asserted nowhere. One line each.
- **Sound:**
  - the refuse-on-mismatch design, a finer view of the admitted table and never a second reading;
  - exact halves;
  - the envelope is flagged, never clipped;
  - the test split is refused before any row;
  - F2 counts only usable, known train rows, and val never counts;
  - an unsupported action is unknown, never "no".
