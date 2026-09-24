# fit-window-counts (VUH-1346, VUH-1353): review note N4, the window counts in the evaluation block

**Each replay evaluation block now carries the set's window counts, per action.** Human output is byte-identical. The
change is uncommitted, in the shared tree. No commit, no Linear write, no game input, no Mac.

## What changed

**`train.window_counts(arrays, *, stride)`** (new): for a replay set, per action:

| Count | Meaning |
|---|---|
| `windows` | all records |
| `complete` | complete cast windows |
| `partial_or_flagged` | partial plus flagged |
| `too_long` | complete but over 64 rows |
| `scored_base` | how training at `stride` would score them (the same `steps.place_windows` as `Batches`) |
| `scored_window_only` | |
| `unplaced` | |

Two identities hold, and the test checks them:
- `windows = complete + partial_or_flagged`;
- `complete = too_long + scored_base + scored_window_only + unplaced`.

**`evaluate_set(..., stride=steps.STRIDE)`** computes the counts once per replay set and passes them into every
`tf` and `sf` block. `run_fit` passes the fit's `--stride`. For human sets nothing is computed and no block exists, as
before.

**`metrics.window_block(..., counts=None)`** adds `"counts"` only when given counts.

**Not changed:**
- The pre-registration's key names `recall_tf` / `recall_sf` (N4's cosmetic point). They are still `tf` / `sf` →
  `recall`.
- The lane doc. The review's bytes table pins `docs/lanes/end-to-end-fit.md` at `2bb576bf…`, so it is a frozen review
  packet under AGENTS.md.

## Tests

**Torch, `test_replay_evaluation_reports_window_recall_and_the_cli_still_refuses_replay`** (extended). Both the `tf`
and `sf` blocks carry these counts at the default stride 48, the same in each:

| Action | windows | complete | partial_or_flagged | too_long | scored_base | scored_window_only | unplaced |
|---|---|---|---|---|---|---|---|
| web_cluster | 4 | 3 | 1 | 0 | 3 | 0 | 0 |
| get_over_here | 3 | 2 | 1 | 0 | 2 | 0 | 0 |
| amazing_combo | 2 | 2 | 0 | 1 | 1 | 0 | 0 |

At stride 64, `get_over_here` moves to 1 base and 1 window-only. Both identities hold for every action.

**Stdlib, `test_window_recall_counts_a_window_once_whatever_its_presses`** (extended). The block has no `counts` key
unless given counts, and carries them unchanged when given.

**Human byte-identity, rerun.** The smoke fixture (human, tiny config, CPU, seed 0, 2 epochs, all three arms), run at
`94120df` before the edit and on the changed tree in my own environment, gives **byte-identical** output `9d74453f…`:
checkpoints, per-epoch losses, press statistics and dev teacher-forced metrics. It is the same value as the previous
hand-back's, so nothing human moved.

## Test counts

All runs used my own environment: `UV_PROJECT_ENVIRONMENT=C:\Users\volpe\.uv-envs\hud-review`. The shared `.venv`
was not touched.

| Environment | Result |
|---|---|
| Torch (`--group execution`, `tests/test_range_bc_torch.py`) | **30 passed** |
| Stdlib, whole repo (environment exact-synced to default) | **1,925 passed, 69 skipped, 0 failed** |
| Perception, whole repo (default + perception, no torch) | **2,977 passed, 158 skipped, 5 failed**, the same 5 as last hand-back and none of them `range_bc` |
| `ruff check` on the four files | All checks passed |

The 5 perception failures: `test_replay_states` ×3 (local `data/run1/frames.jsonl` missing); `test_scoreboard` ×1 (no
local frames); `test_hud_accuracy` (median latency 19 ms > 12 ms under load).

**Something I found, pre-existing, not from this change: the verifier's `no_live_io` check fails whole-repo runs that
have torch.**
- **What:** three `range_bc` torch tests fail in a single-process whole-repo run where torch is installed:
  - `test_the_cpu_reference_verifies_and_every_tamper_fails`;
  - `test_the_verifier_cli_writes_its_report_once`;
  - `test_a_failed_parity_makes_the_no_hud_arm_the_candidate_with_stride_and_unknown_pitch`.

  The failing check is `no_live_io` (`verify.py:184`). It fails when `vgamepad`, `dxcam` or `agent.loop` is already
  in `sys.modules`, and earlier test files, e.g. `tests/test_loop.py`, import `agent.loop`.
- **Why it wasn't seen before:** whole-repo runs happened in the torch-less shared `.venv`, where these tests skip. It
  showed up now because my own environment kept torch from the execution-group run.
- **Proof it predates this change:** `pytest tests/test_loop.py <that verifier test>` fails with `['no_live_io']` on
  the changed tree **and on a clean `94120df` worktree** (created at a short path outside the repo, then removed). All
  three pass alone and in the full torch file.
- **Options, for the lead** (I changed nothing): run the verifier tests in their own process, or have them clear or
  guard those modules. The check itself is right for a real verifier process.

## Bytes (sha256; working tree; raw, then LF-normalised where the file is CRLF)

| File | sha256 raw | LF-normalised |
|---|---|---|
| `policy/range_bc/train.py` | `9769ce5fdb84864d52b1c9b5b9e298760994faf085e4670739d9cdd19d39195c` | same |
| `policy/range_bc/metrics.py` | `e6d07cb8b2d34fdf085648637a20ac042b5bbeb63a649b65fe7f671509533a79` | same |
| `tests/test_range_bc.py` (CRLF) | `97f598b2a2fec58d2c0f2af2d0be436cce13018023c8efd003d2d23e98489db4` | `d847a5c1647f052d07722cef75de5173f2eeaf4476c641ad33aaad44003aeab0` |
| `tests/test_range_bc_torch.py` (CRLF) | `7ead7e96d05bed938b373a12f74e8675fde42b0bbfab864d600a31ea47fb14c7` | `289db6ada4bb6f5369dd97845ee8e6a826d075723c789bd5c1c7784ede3ca558` |

The diff against `94120df` is 4 files, +53 −8.

**In the scratchpad**
(`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\`):
- `human-identity-before-n4.json` and `human-identity-after-n4.json`, both `9d74453f…`;
- `full-torch-run.log`, the whole-repo run with torch showing `no_live_io`;
- `n4-suites.log`.

Parking after this hand-back, as briefed.
