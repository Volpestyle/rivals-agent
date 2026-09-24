# replay-steps-3: the window press contract applied; table rebuilt

Lane pilot-prep. No commits, no Linear writes, nothing sent to admission-review. Details are in
`docs/lanes/replay-hud.md` §9.

## Contract (lead decision), as built
- Every step overlapping a cast's feasible press window [t_lo − Lmax, t_hi − Lmin] is null for that action: never 0,
  never a single-step 1. The table holds no 1 for any action.
- Negatives remain only outside every window, and only within max-count press-time coverage. That rule is unchanged
  from replay-steps-2.
- New file `steps/20260923T054325-507Z-33696-4.press-windows.json` (format `rivals-replay-press-windows-v1`). It is
  hash-pinned in the table header (`source.press_windows`) and in `build.json`. Each record carries:
  - `action`, `ability`, `basis`, `count`;
  - `cast`: false for the 9 flagged team-up stretches;
  - `lag_measured`;
  - `lo_s`/`hi_s` (capture file seconds) and `lo_ns`/`hi_ns` (the table's anchor clock);
  - `evidence_s` [t_lo, t_hi];
  - `rows` [first, last];
  - `complete`: the overlapped rows are one run's consecutive steps covering the whole window.
- The window-level arm ("at least one press in the window") should use only records with `cast` and `complete` both
  true. That is a recommendation, stated in the file's `contract` field. How the loss is applied is the fit lane's
  pre-registration.

## Rebuilt table: 29,121 rows, 24 runs
| action | windows (casts) | complete | 1 | 0 | null |
|---|---|---|---|---|---|
| team_up | 22 (+9 flagged) | 22 | 0 | 17,819 | 11,302 |
| get_over_here | 60 | 60 | 0 | 17,431 | 11,690 |
| amazing_combo | 76 | 74 | 0 | 15,458 | 13,663 |
| web_cluster | 263 (267 casts; 4 two-count) | 262 | 0 | 7,912 | 21,209 |
| ultimate | 9 | 8 | 0 | 24,892 | 4,229 |

What changed from replay-steps-2: the single team-up 1 is now null (team_up null 11,301 → 11,302), and rows no
longer carry a `hud.casts` note. The rows, deaths, coverage and negatives are unchanged.

## Code
- `scripts/replay_steps.py`:
  - `press_windows` returns `Window(lo, hi, count, lag_measured, basis, t_lo, t_hi)`;
  - `label_rows` returns press only and places no 1;
  - new `window_records`;
  - `build` writes and pins the windows file, and reports windows, complete, complete-with-measured-lag and flagged
    windows per action;
  - the docstring states the contract.
- `tests/test_replay_steps.py`. New tests:
  - `test_even_a_window_inside_one_step_is_null_never_a_1`;
  - `test_a_window_record_is_complete_only_over_one_runs_consecutive_rows` (a missing row, a run break, a late start,
    no rows);
  - `test_the_press_windows_file_names_every_cast_and_its_rows_are_unknown` (real table: hash pins, recomputed row
    spans, nulls, completeness).

  `test_known_casts_are_the_ones_counted` now asserts no 1 anywhere and one window per cast.
- Tests: `uv run --group execution --group perception pytest tests/test_replay_steps.py tests/test_replay_hud.py
  tests/test_range_bc.py tests/test_range_bc_torch.py tests/test_replay_camera.py` → **201 passed**.
- Not edited (not mine): `docs/lanes/end-to-end-fit.md` "Replay labels", which should mention the windows file.

## Transcode
Unchanged: the tool refused because obs64.exe is running (game closed). The lead is asking James to close OBS.

## Bytes (sha256)
| file | sha256 |
|---|---|
| scripts/replay_steps.py | f1b0f7bccce4f14ed95670f0e4419d0d1a2c4df0826d8d9347d1ab9f129e9265 |
| tests/test_replay_steps.py | ad534d9a346d0d0421b88c370f09c31fa7ef8b45403a4c6a79ee4540cfa260a2 |
| docs/lanes/replay-hud.md | f76dc6abd6375e3cbbac21de645b363886ac9af772d055b824292b12cc2a1f92 |
| policy/range_bc/steps.py (unchanged since -2) | aa17bbcd55407f173c28f63a5e7ce3b6cc9e25e5e06765fa3a1a77c9ec4de7d2 |
| policy/range_bc/fixture.py (unchanged) | b66720be4beb59a0bdf02225bc596868f93484361f221edb8d765aa690192c44 |
| tests/test_range_bc.py (unchanged) | 9f50f8b88ad4b2818e1b3fca396a414988d6eca93fd41f6cf8149484a1e5b46f |
| tests/test_range_bc_torch.py (unchanged) | 7d1b0f27488c81e1a3fa9b82f172e3a53d3bf960f28555fa81a424d1fc9b509e |
| perception/replay_hud.py (unchanged) | 40d4f9680eb1e765b07d953f59e3926703c8914077e1f2168375ef4fab49b999 |
| tests/test_replay_hud.py (unchanged) | b89053421e9b3659dca4f0aa8356c35e9a5c2ec9ca5152a568a625dcdf58910e |
| scripts/replay_hud_full.py (unchanged) | d5859a779f89b76dd3c3ee4396dcb3bbbbc8d7cf9e6fcbcbd5840c762d67736f |
| scripts/replay_hud_validate.py (unchanged) | c946abde0f6e8444c6ea55d044ce46e2c0c49f75574539c25a3e6c56b0e6f926 |
| hud/events.json (unchanged) | 629490f1018e859f99d144bac525892622c8079490c4204f378609923688d6b2 |
| hud/manifest.json (unchanged) | da6ace58622ac43b745f757e884c6d3a0fd5932f5d8f57a3e62d5a264c790897 |
| steps/20260923T054325-507Z-33696-4.jsonl | 3e1acef80a08c5e5946df35fa4529b1a95a1aaad67d3b1cfcf336f3aa8290b35 |
| steps/20260923T054325-507Z-33696-4.press-windows.json | 91df5010f592f016bbc031f753a797769cb3b6bfc57ed2190f631b74f40eda3d |
| steps/build.json | ec182861a43ac7eaa5138d4f5b2a9e43a7acad6ac8700fce7c5579b82c1fa9bd |

The data lives under `data/demos/replays/daymr-20260923-004325/` and is not committed.
