# fit-window-loss (VUH-1359, VUH-1346, VUH-1353): the replay window-level loss, pre-registered then implemented

**The window term is implemented, tested, and uncommitted; no replay fit has run.** The pre-registration came first
(DECISION `window-loss-prereg`, section sha256 `75c530a7…`). The lead's go accepted W1-W3 as written. The code follows
it: a noisy-OR "at least one press in the window" term over complete cast windows.
- **Human cohorts are byte-identical:** checkpoints, losses, statistics and metrics.
- **`--scope fit` and every CLI path still refuse replay cohorts.**
- No commit, no Linear write, no game input, no Mac, nothing under `docs/evidence/`.

## The pre-registered section (in `docs/lanes/end-to-end-fit.md`, "Replay window-level loss")

**The term.** Per counted window `w` of action `c` over rows `f..l`:

```
NLL_w = -log(1 - exp(-max(sum softplus(z_t), 1e-12)))      z_t = the press logit of c at step t
```

It joins the press term as one positive observation weighted by `pw_c`: the numerator gains `pw_c · NLL_w` and the
denominator gains one per window. There is no release term and no new weight.

**Counted windows:** `cast` and `complete`, and at most 64 rows (one sequence's scored span). Partial, flagged and
longer windows are flagged and excluded.

**W1:** overlapping windows of one action are allowed and scored independently. Only exact duplicates are refused.
**W2:** each counted window is scored exactly once per epoch, in the first base sequence that scores it whole, else in
its own window-only sequence with every step and camera term masked. **W3:** a window counts as a press positive in
replay statistics, so `pw_c` is the action's own, as for a labelled press.

**Reader refusals:**
- a sha256 other than the header's pin;
- a format, session or `step_ns` other than the table's;
- a missing or mistyped field, or an unknown action;
- `lo_ns` > `hi_ns`;
- `rows` or `complete` differing from the table's own anchors;
- **any non-null press of the window's action on a row it overlaps;**
- exact duplicates;
- a windows file beside a human table, or not pinned by its replay table.

**Metrics:** replay evaluation sets only, and no gate reads them. Per action: window recall (teacher-forced and
self-fed), presses per window, and the decoded-press rate on press = 0 rows.

**The rationale numbers are in the section,** from DayMR's real table, read only:
- 65 overlapping web_cluster pairs (119 of 262 windows; largest group 4);
- at stride 64 the base tiling scores only 131 of 262 web_cluster windows whole.

**What the implementation measures on DayMR:**

| Stride | Base sequences score | Window-only sequences | Unplaced |
|---|---|---|---|
| 64 | 274 windows | 145 | 0 |
| 48 | 329 windows | 90 | 0 |

Counted windows are 419 of 426 complete cast windows; the 7 not counted are longer than 64 rows.

**The section also records** the status (pre-registered, go, implemented) and an "Implemented" subsection with these
numbers.

## What changed

| File | Change |
|---|---|
| `policy/range_bc/steps.py` | `WINDOWS_FORMAT`, `MAX_WINDOW_ROWS`, `PressWindows`, `windows_path`, `load_windows` (the reader), `place_windows` (W2, lag-aware), `train_statistics(..., windows=)` (W3) |
| `policy/range_bc/train.py` | `SessionArrays(press_windows=)`; `Batches` placement, window-only sequences, `window_report` and `win_index` (replay only); `window_nll`; the press term in `loss_terms`; the `windows` block in `evaluate_set` (replay sets only); `load_arrays` loads windows (refuses one beside a human table); `run_fit` feeds placed windows to the statistics; `_pitch_known` (below) |
| `policy/range_bc/metrics.py` | `window_block` |
| `policy/range_bc/fixture.py` | `WINDOW_SPECS`, `replay_windows_session`, `write_replay_windows` |
| `tests/test_range_bc.py` | 16 new test items |
| `tests/test_range_bc_torch.py` | 5 new tests, and one assert added to the CLI end-to-end test: human reports carry no window keys |
| `docs/lanes/end-to-end-fit.md` | The section |

**Found and fixed on the way (please review).** `predict_teacher` and `predict_self` read
`calibration["pitch_deg_per_count"]`, and a replay calibration has no such field. So replay evaluation raised
`KeyError` before this change. The new `_pitch_known(session)` returns true for replay tables (degrees come direct),
the same rule `train_statistics` already uses. For a human table it evaluates exactly the old expression.

## Acceptance tests

| Test (from the pre-registration) | Where | Result |
|---|---|---|
| **1. Reader, fixture with complete, partial, flagged, overlapping, over-length and stride-64-uncovered windows.** Complete windows enter the term; partial, flagged and 70-row ones are excluded with counts; no step inside any window is a 0 or 1 for its action; a refusal test each | `test_press_windows_load_with_…`, `test_malformed_press_windows_are_refused` (11 cases), `test_a_windows_file_must_be_the_pinned_one_…` | pass |
| **2. The term.** Loss < 1e-6 with one certain press; equal to the float64 closed form within 1e-6; capped at −log 1e-12; gradient non-zero on every window step, exactly zero outside it, on other actions and on hold and release; weighted by the action's `pw` | `test_the_window_term_is_zero_at_its_optimum_…`, `test_the_window_term_has_gradient_only_inside_…` | pass |
| **3. Assignment.** Every counted window scored exactly once across an epoch at strides 64 and 48 and with lag 1; the window-only sequence has no step or camera mask; placement is scored-whole after burn-in | `test_each_counted_window_is_placed_…` (stdlib), `test_each_window_is_scored_once_per_epoch_…` (torch) | pass |
| **4. Human byte-identity.** Smoke fixture (human, tiny config, CPU, seed 0, 2 epochs, all three arms), run at `abda588` and on the changed tree, same machine | `human_identity.py` (scratchpad) | **byte-identical** output `9d74453f…`: checkpoints `18e2dc51…` (model), `230828b0…` (no-HUD), `f8954ce4…` (twin), per-epoch losses, press statistics and dev teacher-forced metrics. In-suite, `test_human_batches_and_the_human_loss_are_untouched`: human batches have exactly today's keys, and the press term equals today's expression, `torch.equal` |
| **5. The replay refusal stays.** `train.main` on a replay table raises the loader's replay-split refusal. The existing `load_cohort` refusal tests pass unchanged | `test_replay_evaluation_reports_window_recall_and_the_cli_still_refuses_replay` | pass |
| Also: windows count as press positives in replay statistics, via a relabelled copy as the existing replay test does; window recall counts a window once, and a press-everywhere model shows `zero_row_press_rate` 1.0; `evaluate_set` on a replay set returns the tf and sf window blocks | stdlib + torch | pass |

## Test counts (Windows)

| Environment | Result |
|---|---|
| Stdlib, whole repo (`uv run pytest -q`) | **1,918 passed, 69 skipped** |
| Torch (`uv run --group execution pytest tests/test_range_bc_torch.py`) | **30 passed**, 5 of them new |
| Perception, whole repo (`uv run --group perception pytest -q`) | **2,970 passed, 158 skipped, 5 failed**, then `uv sync` restored stdlib-only (cv2 and torch absent) |
| `ruff check` on the six changed Python files | All checks passed |

**The 5 perception failures were run twice, with the same 5 names both times.** None of these files imports
`range_bc`. I did not run them at `abda588`.

| Test | Failure |
|---|---|
| `test_replay_states.py` (3 tests) | `FileNotFoundError: data/run1/frames.jsonl`: local data this checkout lacks |
| `test_scoreboard.py::test_a_frame_without_a_scoreboard_reads_nothing` | `IndexError`: it globs local frames and finds none |
| `test_hud.py::test_hud_accuracy` | "median latency 19.10 ms > 12.0 ms" under full-suite load; it passed when rerun alone |

## What I did not do

- **No replay fit, and no training on DayMR.** The CLI refuses replay cohorts and I kept that. `fit()` also accepts
  train-split sessions only.
- **No gate on the window metrics,** and no change to the gates.
- **I did not change `scripts/replay_steps.py` or its outputs.** The DayMR table and windows file were only read.
- **Not built: a "≥ k distinct presses" term** for overlapping windows or `count` 2 events. Each such window is scored
  as "at least one" (W1).
- **The swarm message carrying the lead's go never reached my inbox.** `fetch` returned nothing; sync showed one
  message leased and two dead-lettered. I acted on the lead's pasted summary and did not ack.

## Bytes (sha256; working tree; raw, then LF-normalised where the file is CRLF)

| File | sha256 raw | LF-normalised |
|---|---|---|
| `policy/range_bc/steps.py` (CRLF) | `0a7ccb2b2ac1eab4fdd8abf15d38059651573afd7904411890bfc3d2bf3e31e5` | `bceab645b5cade09cdb9928c1af968013db11808a7d9c97ce8ff9678d4aa1e63` |
| `policy/range_bc/train.py` | `d90a960ec3cc26847889bc0dce4477050eff20c21f6dc1fc920442601032cabc` | same |
| `policy/range_bc/metrics.py` | `187b748e1ab9a8c2473c577a00a1e6e8386da6022bfcbf15612d2e0a9ed1c8b2` | same |
| `policy/range_bc/fixture.py` | `6067bc8ca1beccc76ed901cbbb45e6e999bce6edb246bc52a7d2111e5357c8fe` | same |
| `tests/test_range_bc.py` (CRLF) | `474f56ba3f8a4262e9dcfcafb4e8313e94c8eba8ef72dd6787cdbdfdca9b2bb5` | `65da3e91e35a04a381f8d3ed78fe34ad80afb9801ee18c5e0ed3deb6279703ea` |
| `tests/test_range_bc_torch.py` (CRLF) | `83af81decacb3eae3890a22dde3c568030b35d8b75385551aff4d196361f826e` | `6b4910e9e9453c04792e135fb29db310a25261cddfd8f9763d212fc9a3e811f4` |
| `docs/lanes/end-to-end-fit.md` | `2bb576bf239cac01573f07b040a53d8dcd6c026d350ed1db7e023ff3daa90afd` | same |

**Also in the scratchpad**
(`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\`):
- `human_identity.py`;
- `human-identity-before.json` and `human-identity-after.json` (both `9d74453f…`);
- `perception-full-2.log`.
