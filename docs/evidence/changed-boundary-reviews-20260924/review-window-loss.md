# Review: the replay window-level loss, changed-boundary review (VUH-1359, VUH-1346, VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-24. Read-only: no edits to the reviewed files, no commits, no Linear,
no game, no Mac.

**Reviewed:** hud-review's uncommitted change on `main` at `c2b8a25`, as described in `fit-window-loss.md` and
pre-registered in `docs/lanes/end-to-end-fit.md`, "Replay window-level loss". Every byte matches the hand-back's table.
The hashes are at the end.

**How I checked (own evidence throughout):**
- **Two private trees.** I exported `c2b8a25` twice with `git archive` into my scratchpad (`wl/base`, `wl/changed`) and
  overlaid `wl/changed` with the seven changed files, copied from the shared tree as they are.
  - `diff -rq` shows exactly those seven files differ.
  - Nothing under `policy/` or `tests/` changes between `abda588` (the hand-back's "before") and `c2b8a25`.
  - The shared tree and its `.git` were never written to.
- **My own environments,** built from `uv.lock` with `UV_PROJECT_ENVIRONMENT` pointing into my scratchpad. The shared
  `.venv` was never touched, so no `uv sync` was needed.
  - `venv-stdlib`: the dev group only (pytest; numpy, cv2 and torch absent).
  - `venv-perc`: dev plus perception (cv2 5.0.0, numpy 2.4.6; torch absent).
  - `venv-rangebc`: perception plus execution (torch 2.14.0+cpu), for the torch suite and the fits.
- All runs were at below-normal priority, with the game and OBS not running.

## Verdict: land

- Human cohorts are byte-identical, reproduced independently.
- The term, masks, placement and refusals are what W1-W3 pre-registered.
- The KeyError fix leaves every human path unchanged.
- No test regresses in any environment.
- The findings below are minor or notes. None blocks landing.

## 1. Are human cohorts unchanged? Yes, byte for byte

**What I ran** (`wl/id/gen.py`, `run.py`, `compare.py`):
- **Inputs, generated once** with the base tree's fixture code:
  - three human fixture tables: `t` (train), `d` (train, used as dev) and `v` (val);
  - `runs=(150, 120)`, seeds 0/2/1;
  - fake caches from the torch suite's `fake_cache`.
- **The fit,** in each tree in a fresh process: `train.main` with `--scope smoke --epochs 2 --batch 4 --seeds 0
  --model-config TINY`, all arms, CPU. Each process imported the tree's own `policy/range_bc/train.py` (checked).

**Every output file is identical:**

| File | sha256 (both trees) |
|---|---|
| `model-seed0.pt` | `18e2dc51c777…` |
| `model_nohud-seed0.pt` | `230828b09b48…` |
| `history_only-seed0.pt` | `f8954ce491c6…` |
| `dev-cpu-probs.f32`, `val-cpu-probs.f32` | `92292cae669d…`, `d709ee941ead…` |
| `dev-/val-cpu-tf-decisions.bin`, `-sf-decisions.bin`, `-cpu-reference.json` | identical |

**`report.json`, compared key by key:** 22 differences, none of them results.
- **Wall-clock only:** `budget/*/seconds`, `sequence_frames_per_second`, `epochs_log/*/seconds` and `fit_seconds/*`.
- **`code_closure`** for the three changed modules (`steps.py`, `train.py`, `metrics.py`), as expected.
- **Equal:** every loss in `epochs_log`, `train_statistics`, `ar2`, the teacher-forced and self-fed metrics, gates,
  `cpu_reference` and `windows`.

These are the same three checkpoint hashes the hand-back reports, reproduced independently.

**In-suite:** `test_human_batches_and_the_human_loss_are_untouched` passes. Human batches have exactly today's keys, and
the press term is `torch.equal` to today's expression.

## 2. Is the term what was pre-registered? Yes

**The noisy-OR form.**
- `window_nll = -log(-expm1(-max(Σ softplus(z), 1e-12)))`, that is `-log(1 − Π(1 − σ(z)))`.
- It joins `terms["press"]` as `num + Σ pw[c]·NLL_w` over `den + #windows`, with `pw` the press row of `pos_weight`.
- There is no release term and no new weight: `LOSS_WEIGHTS` is unchanged.
- **W3.** `train_statistics(..., windows=placed)` adds one press positive and one known press entry per placed train
  window. `run_fit` places them with the same `lag`, `regimes` and `stride` as `Batches`, so the statistics and the
  batches count the same windows.

**W1.**
- Exact duplicates are refused: the key is (action, `lo_ns`, `hi_ns`, `evidence_s`).
- Overlapping windows are allowed and scored independently.

**W2.**
- Each counted window lands in the first base tile that scores it whole, else in its own window-only sequence (shared
  when placed alike).
- My probe (`wl/probe/term.py`, fixture, lag 0 and 1, stride 64 and 48) finds every counted window scored **exactly
  once** across an epoch in all four cases.

**Can a window be both a positive and a step 0?** No.
- The reader refuses any non-null press of the window's action on any row the window overlaps. That covers flagged
  and partial windows too, which is stricter than pre-registered.
- `check_replay_row` ties `press_known` to `press is not None`.
- My probe counted, over every sequence and position whose target row lies inside a complete window, the positions
  where that action's press is a known step: **0**, at both lags and both strides.
- On DayMR's real table (read only, through the changed reader), complete-window rows with a non-null press or
  `press_known` for their action number **0**. There is **no** `press = 1` anywhere in the table.

**Are partial windows excluded and flagged?** Yes.
- `cast` false becomes `flagged`; not whole becomes `partial`; more than 64 rows becomes `too_long`. All three are
  excluded from `counted` and reported per action.
- Fixture: web_cluster 1 partial, get_over_here 1 flagged, amazing_combo 1 too long.
- **DayMR, reproduced exactly as the hand-back reports:**
  - 439 records: 430 cast, 9 flagged;
  - 426 complete, 4 partial, 7 too long, 419 counted;
  - web_cluster: 65 overlap pairs, largest group 4;
  - placement: stride 64 gives 274 base and 145 window-only; stride 48 gives 329 and 90; 0 unplaced at either.
- The ult cast my replay-HUD review flagged (P2, 617 s) now has window 616.55–619.63 s over its whole transition,
  with its rows null. At 93 rows it is too long: excluded from the term, but kept for recall.

**Are the window-only sequences free of step and camera gradient?** Yes.
- Leaf logits run through `loss_terms` and `total_loss`, then `backward`. On the window-only sequence the gradient is
  non-zero on **exactly** the 16 press-channel steps of its own window, for its action. It is exactly zero on every
  other position, action and channel (hold and release included), and on the whole camera output.
- This holds at lag 0 and 1 (`wl/probe/lag1.py`).
- `batch()` clears both `act_mask[i]` and `camera_mask[i]` for those sequences.

## 3. Refusals

All of these were produced with the changed reader on the fixture (`wl/probe/term.py`):

| Case | Result |
|---|---|
| Exact duplicate record | refused: "an exact duplicate of an earlier window" |
| A row inside a window with press 0 (and, separately, 1) for its action | refused: "a row inside the window has a non-null … press (never both a window and a step)" |
| `rows` off by one | refused, with the reader's own rows given |
| `complete` flag wrong | refused: "complete is False, the table gives True" |
| `lo_ns` > `hi_ns` | refused |
| Unknown action | refused |
| `step_ns` differs | refused |
| A windows file beside a human table | refused: "a press-windows file its step table does not pin (human tables carry none)" |
| Same span, different `evidence_s` | **accepted**, as W1 allows (see N3) |

**The CLI on a replay cohort:**
- `--scope smoke` and `--scope plumbing` are refused by the loader: "a replay-split recording is never train, val or
  test".
- `--scope fit` is refused earlier, before loading: "the real fit needs validation and dev recordings".
- Structurally, no call in `train.py` passes `allow_replay`, so `load_cohort` refuses the replay split in every scope.
- The in-suite tests for these refusals pass.

## 4. Does the KeyError fix change a human path? No

- `_pitch_known(s)` is `steps.is_replay(s.header) or s.calibration["pitch_deg_per_count"] is not None`.
- `is_replay` is false for every human header (`source_kind` absent or "human"), so a human table evaluates exactly
  the old expression.
- The identity run exercised `predict_teacher` and `predict_self` on human dev and val: the CPU reference probabilities
  and decisions are byte-identical.

## 5. Tests, in both trees and all three environments

| Environment | `c2b8a25` | Changed tree |
|---|---|---|
| stdlib (whole repo) | 1,895 passed, 75 skipped, 1 failed | **1,911 passed** (+16), 75 skipped, 1 failed (the same) |
| perception (whole repo) | 2,849 passed, 232 skipped, 7 failed, 29 errors | **2,865 passed** (+16), 232 skipped, 7 failed, 29 errors (**identical failure and error set**) |
| torch (`tests/test_range_bc_torch.py`) | 25 passed | **30 passed** (+5) |

- **Every failure is environmental and occurs identically before and after the change.** The exports lack
  git-ignored `data/` and `.git`:
  - `test_range_skill_loop` (stdlib and perception): a report under `data/`;
  - `test_policy::test_third_party_derived_data_stays_out_of_git`: "not a git repository";
  - `test_hud_countdown_performance` (29 setup errors): `data/diagnostics/…/measure.py`;
  - `test_hud_accuracy` in the exports: "145/145 labelled frames are not on disk".
- **The hand-back's five, checked in the shared checkout itself** (read-only: `PYTHONDONTWRITEBYTECODE`, no cache
  plugin, `git status` unchanged):
  - `test_replay_states` (3): `FileNotFoundError data/run1/frames.jsonl`;
  - `test_scoreboard::test_a_frame_without_a_scoreboard_reads_nothing`: `IndexError`, no local frames;
  - `test_hud_accuracy`: **passes** alone, which matches the hand-back's latency-under-load explanation.
  - None of these tests' code, nor `perception/` or `agent/`, differs between `c2b8a25` and the working tree, so they
    are the same failures at `c2b8a25`.
- No existing test was removed or weakened. The test diffs are additions only, plus one added assert that human
  reports carry no window keys.

## Findings (minor; none blocks)

- **N1. The pre-registered section was edited after its pin.**
  - The section cites its pre-registration as `75c530a7…`, but it now also holds the status block, the "Implemented"
    subsection and, **inside W2**, a table headed "For DayMR the implementation measures" (274/145, 329/90).
  - Its text therefore cannot be checked against the pin. I found no copy of the pinned bytes in hud-review's
    scratchpad.
  - At landing, keep the pinned bytes somewhere checkable (the DECISION text, or an evidence copy), and keep post-code
    numbers under "Implemented" only.
- **N2. The window term's gradient saturates to exactly 0 in float32 once a window is satisfied.**
  - With Σ softplus above about 17 (P(no press) under about 4e-8), `expm1(-S)` rounds to −1. Its backward,
    `grad·(result + 1)`, is then exactly 0.
  - Probe: logits around +1 over 16 steps give NLL 0 and gradient 0; logits around 0 give gradient 6.6e-6.
  - This is harmless: a satisfied window should not push. But the pre-registration's "every step in the window gets
    gradient" holds only below saturation.
  - Under a future bf16 or fp16 autocast, saturation would come at a P(no press) of about 4e-3 and silence windows
    early. Compute `window_nll` in float32 or float64 explicitly if autocast is ever enabled.
- **N3. Two records with the same action and span but different `evidence_s` are both accepted and both scored.** That
  is the same interval with twice the weight. This is consistent with W1 (distinct events), and DayMR has none (0
  same-span or same-rows groups). Noted only.
- **N4. The evaluation `windows` block lacks the counts the pre-registration lists.** It says the block reports "the
  flagged, partial and unscorable window counts". `metrics.window_block` reports windows, evaluated, hits, presses,
  zero rows, recall and macro recall.
  - The counts exist only in the train report (`windows.press_windows`) and the reader's `PressWindows.report`.
  - Add each evaluation set's `press_windows.report` to its block. The names also differ from the pre-registration's
    `recall_tf`/`recall_sf` (they are `tf`/`sf` → `recall`); cosmetic.
- **N5. Cost, for the plan:** window-only sequences add **+32 %** sequences per epoch at stride 64 (145 on 455 base)
  and +15 % at stride 48 (90 on 594). Each is a full forward pass carrying one window's loss.
- **N6. Pre-existing, not from this change:** `run_fit` creates `--out` before the loader's replay refusal, leaving an
  empty directory behind (`--scope smoke`/`plumbing`). This is the same at `c2b8a25`.

## Bytes reviewed (sha256)

| File | Raw (working tree) | LF-normalised |
|---|---|---|
| `policy/range_bc/steps.py` | `0a7ccb2b2ac1eab4fdd8abf15d38059651573afd7904411890bfc3d2bf3e31e5` | `bceab645b5cade09cdb9928c1af968013db11808a7d9c97ce8ff9678d4aa1e63` |
| `policy/range_bc/train.py` | `d90a960ec3cc26847889bc0dce4477050eff20c21f6dc1fc920442601032cabc` | same |
| `policy/range_bc/metrics.py` | `187b748e1ab9a8c2473c577a00a1e6e8386da6022bfcbf15612d2e0a9ed1c8b2` | same |
| `policy/range_bc/fixture.py` | `6067bc8ca1beccc76ed901cbbb45e6e999bce6edb246bc52a7d2111e5357c8fe` | same |
| `tests/test_range_bc.py` | `474f56ba3f8a4262e9dcfcafb4e8313e94c8eba8ef72dd6787cdbdfdca9b2bb5` | `65da3e91e35a04a381f8d3ed78fe34ad80afb9801ee18c5e0ed3deb6279703ea` |
| `tests/test_range_bc_torch.py` | `83af81decacb3eae3890a22dde3c568030b35d8b75385551aff4d196361f826e` | `6b4910e9e9453c04792e135fb29db310a25261cddfd8f9763d212fc9a3e811f4` |
| `docs/lanes/end-to-end-fit.md` | `2bb576bf239cac01573f07b040a53d8dcd6c026d350ed1db7e023ff3daa90afd` | same |
| `handoff/fit-window-loss.md` | `292fd479549ddd5c481cdd590e3e06cda01e8ae0d4e913cfeffde24001b9982b` | |
| `handoff/brief-fit-review-window-loss.md` | `5aa370d21a51ac907b1c1dce4ce2125807694be97a11fda97b4cc720401b7ba9` | |
| `handoff/brief-hud-review-window-loss.md` | `2bb310a65e6b8f6fc42fa918a808ea854b2f0eeab5d7afa028c3d856ade00aa6` | |
| DayMR table (read only) | `3e1acef80a08c5e5946df35fa4529b1a95a1aaad67d3b1cfcf336f3aa8290b35` | |
| DayMR `press-windows.json` (read only) | `91df5010f592f016bbc031f753a797769cb3b6bfc57ed2190f631b74f40eda3d` | |

The base blobs at `c2b8a25`, LF: `steps.py` `82cca65d…`, `train.py` `05145829…`, `tests/test_range_bc.py` `50c06d44…`.

My scripts and logs are in my scratchpad under `wl/`: `id/`, `probe/`, `t-*.log` and `tests-summary.txt`.
