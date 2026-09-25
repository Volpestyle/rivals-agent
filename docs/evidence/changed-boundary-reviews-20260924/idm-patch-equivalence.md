# scoreboard-fix: IDM cohort identity by kit version (item 4 of patch-equivalence-design.md) (VUH-1353)

2026-09-24.
- **Scope:** a working-tree edit in the shared checkout on HEAD `7add7f8`, uncommitted, for fit-review together with
  hud-review's change.
- **Not touched:** no data, no commits, no Linear. hud-review's files were read (to share their loader), never edited.

## What I found first

- **Nothing in the IDM compared identity across sessions.** `IDENTITY` in `policy/idm_targets.py` was only copied
  into each target header and required present (`check_header`).
- `run_fit` (train + held-out) and the `idm_eval baselines` CLI combined files without comparing `patch`,
  `settings_hash` or any other identity key.
- So item 4 is new code, not a changed comparison. The IDM now has a cohort check where it had none.

## What changed

- **`policy/idm_targets.py`:**
  - **`check_cohort(targets, equivalence)`**, which requires:
    - each session and each recording media once;
    - the **`COHORT_KEYS`** equal: `settings_hash`, `bindings`, `swing_mode`, `accel_on`, `parent_step_ns`,
      `frame_period_ns`, `calibration`. These are `steps.load_cohort`'s human-source keys; a target header has no
      `video_size`.
    - **`patch` compared by the kit version** its build maps to, with a build the file does not name refused, and
      one kit version per cohort.

    It returns what a report records: `{patch_equivalence: {path, sha256}, kit_version, builds: {session: real
    build}}`.
  - **Headers are unchanged:** a target file keeps `patch` = the real build.
  - **One loader and one pin, the fit lane's.**
    - `load_patch_equivalence` and `kit_version` are thin wrappers over hud-review's
      `policy.range_bc.steps.load_patch_equivalence` / `kit_version`, which do the LF sha256 pin and the schema
      validation. A `StepError` becomes a `TargetError`, and the wrapper refuses an unpinned call.
    - `PATCH_EQUIVALENCE`, `PATCH_EQUIVALENCE_FORMAT` and `PATCH_EQUIVALENCE_SHA256` are steps' own (pin
      `4df869f3…`).
    - I first wrote a separate loader from the design. When hud-review's appeared in the tree with slightly stricter
      checks (`decided_on` as YYYY-MM-DD, evidence entries as non-empty strings), I replaced mine with theirs, so the
      lanes cannot drift.
    - **This means my change depends on theirs landing with it.**
  - The header docstring notes that `patch` is the real build, compared by kit version.
- **`policy/idm/train.py`:**
  - `run_fit` loads the pinned file and runs `check_cohort` over train + held-out **right after loading the target
    files, before any store is opened**.
  - New CLI flags `--patch-equivalence` and `--patch-equivalence-sha256`, defaulting to steps' path and pin.
  - The result goes into the checkpoint meta (`cohort`, an extra key, not in `PROVENANCE_REQUIRED`, so older
    checkpoints still load) and into the report (`cohort`, now in `REPORT_REQUIRED`).
- **`policy/idm_eval.py`:** the `baselines` CLI takes the same two flags, runs `check_cohort` over train + held-out,
  and prints `cohort` in its report.
- **Not changed:**
  - `policy/idm/decode.py`: one session per store, no cross-session comparison; stores keep the real build.
  - `idm_targets.build`: it copies the real build from the step table, as before.

## Bytes (working tree on `7add7f8`; +208 / −6 over six files)

| File | sha256 (working tree, CRLF) | sha256 (LF) |
|---|---|---|
| `policy/idm_targets.py` | `18b3f800519c56416a85e8aa9d0ceeaefdaf63ab6c66918e6992f9c4185fa135` | `ffd54c7ebfb71b1ed9fe2531ee31744544ff2446181574c0f9fb9879339e179a` |
| `policy/idm_eval.py` | `a74e04aa70029cabfbe96087470a6778b5c9d8b784e287524f86d9b84cef437f` | `d32c341a102d212e7d15c0f178976d3bc012f252986af146479d000c5c2e4153` |
| `policy/idm/train.py` | `2e450c92443017661f11e403ab429ed6bbb7be03c0f66c8c2b00229ff26dbbc5` | `72a2f2482d3ef60d72fd002282b1045cdb5c7d42c24aba3f6a51a7f53e2c8394` |
| `tests/test_idm_targets.py` | `8ca8aea4e0230bdd1a890cb29176e656137908712d421e1cfc2cfa7f09587fdd` | `e0a0fd4d9fc2798a932b9c7eba7abb49537e744cd118621253f7ce93b494c087` |
| `tests/test_idm_eval.py` | `28d2b894f755f2254830bd7812481f33342efda4d071ad9d101f6fabeda1b2bd` | `ae460db57dfd0b15709b844240cc9e2f00d369b6f2a102e8f1865a9da05d2f3b` |
| `tests/test_idm_model.py` | `5ceb2a891f76f2edeb3dfbdcf3eff226024e7cfb76fb94b9bc36ba94f80a2748` | `867d337fd1c7e65d3010afcb77758b39a91c33f219eff1b1c1c4d3de6f38afd6` |

## Tests

These use a private `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.cache/rivals-idm-venv`, and hud-review's `steps.py` in
the working tree.

| Environment | Suites | Result |
|---|---|---|
| Stdlib | `test_idm_targets.py` + `test_idm_eval.py` | **44 passed** (targets 21, up from 18; eval 23, up from 22) |
| Execution | `test_idm_eval` + `test_idm_model` + `test_idm_targets` + `test_idm_decode` + `test_replay_camera` | **84 passed**, up from 78 |
| Lint | `uvx ruff check` on the six files | clean |

**New tests:**
- `test_the_equivalence_file_is_pinned_and_validated`, through the IDM wrapper:
  - the right pin loads, a CRLF copy loads under the LF pin;
  - no pin, a wrong pin, one build under two kits, missing evidence and no kit version are each refused;
  - the IDM pin is steps' pin.
- `test_a_cohort_compares_builds_by_kit_version_and_keeps_the_real_builds`: the old and new builds together form one
  cohort and record their real builds; an unnamed build is refused.
- `test_a_cohort_is_one_kit_version_and_one_identity`: refused for two kit versions; each of `settings_hash`,
  `bindings`, `swing_mode`, `accel_on`, `frame_period_ns` and `calibration` differing; a duplicate session; a shared
  media.
- The fresh-subprocess `run_fit` test now passes an equivalence file and asserts `cohort` in the report and the
  checkpoint meta, with the real builds.
- `test_a_fit_refuses_a_build_the_equivalence_file_does_not_name_before_opening_a_store`: `FrameStore` is patched to
  fail if called. It also covers an unpinned default.
- `test_the_baselines_cli_scores_one_cohort_by_kit_version`: old-build train + new-build held-out is one cohort in the
  report; an unnamed build is refused.

**On the real data, read-only:** with the real pinned file (`4df869f3…`), the four admitted target files form one
cohort ("Season 10, Version 20260911"), with all builds `1.1.3870120/build25364676`. The new build
`1.1.3892207/build25501035` maps to the same kit version.

## For the lead and fit-review

- **`data/human/patch-equivalence.json` is gitignored (`data/`) and untracked.**
  - Its pin is in `steps.py`, but on a fresh checkout such as the Mac worktrees the file will not exist, and every
    CLI (both lanes) will refuse.
  - It needs a force-add, as `sealed-denylist.json` has, when it lands.
- **Flaky-looking test, reported not dismissed:** in the first full run of `test_idm_model.py` in the private venv,
  `test_training_is_byte_reproducible_on_cpu_and_learns` failed once at `shas[0] == shas[1]`, two CPU fits in one
  process giving different checkpoint bytes.
  - It then passed 3 of 3 full-suite reruns, 10 of 10 alone, and in the 84-pass run above: one failure in 15 runs.
  - This change does not touch `fit`, the loss or the checkpoint. The earlier landings never showed it.
  - I cannot say more without a repro. If fit-review sees it, it is worth a look at CPU thread scheduling under load.
