# Review: cohorts by kit version (patch equivalence), fit and IDM lanes, with the intake boundary (VUH-1359, VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-24. Read-only: no edits, no commits, no Linear, no game, no Mac. The
shared tree was only read, and the shared `.venv` was not used.

**Reviewed:** the uncommitted change in the shared tree on main `7add7f8`:
- `fit-patch-equivalence.md`: the data file, `steps`, `train`, `verify`, the fixture, the tests and the
  pre-registration note;
- `idm-patch-equivalence.md`: `idm_targets.check_cohort`, `idm/train.run_fit`, the `idm_eval` baselines CLI and the
  tests;
- `intake-patch.md`, only where it meets these two.

The design is `patch-equivalence-design.md`. Every file matches its hand-back hash; the table is at the end.

**How I checked:**
- **Two private trees:** `git archive 7add7f8` twice into my scratchpad (`pe/base`, `pe/changed`), with `pe/changed`
  overlaid with all 16 modified files, the untracked note and the gitignored data file. `diff -rq` shows exactly those.
- **My own environments** from `uv.lock` (unchanged since `c2b8a25`):
  - `venv-stdlib` (dev only);
  - `venv-exec` (dev plus execution);
  - `venv-rangebc` (perception plus execution, torch 2.14.0+cpu).
- Every run was at below-normal priority.

## Verdict: land, with two conditions for the landing commit

1. **Force-add the data file with the code** (`git add -f data/human/patch-equivalence.json`), as the denylist was.
   - Untracked, every CLI in both lanes refuses on a clean checkout, in CI and on the Mac (`git archive`).
   - Worse, the mapping behind a landed cohort would exist only as a pin in code, with no bytes in history to match
     it.
   - Both hand-backs flag this. I make it a condition.
2. **Land the fit and IDM changes together.** `idm_targets` imports `steps.load_patch_equivalence`, `kit_version` and the
   pin, so the IDM change cannot land alone.

Every settle item holds on my own evidence. The findings below are minor.

## Refusals (own probes: `pe/probe/refuse.py`, `pe/id/refusals_torch.py`)

| Case | Fit lane (`steps`/`train`) | IDM (`check_cohort`/`run_fit`) |
|---|---|---|
| Old and new build, pinned file | **one cohort**, "Season 10, Version 20260911" | **one cohort**; builds recorded as the real ones |
| Old and new build, no file (the pre-change behaviour) | refused: "patch differs" | (the IDM requires the file) |
| **Unnamed build** `1.1.3999999/build29999999`, cohort of one | **refused**, naming the build and file | **refused** (alone and beside the old build) |
| Tampered file (one digit), default pin | **refused** by the pin | **refused** (the same loader) |
| Pin `None` | refused | refused: "must be pinned" |
| CRLF copy, LF pin | loads (LF-normalised pin), as designed | the same loader |
| Missing file | `FileNotFoundError` (refused) | the same |
| Malformed file: a build under two kits, empty builds, no evidence, a bad date, the wrong format | each **refused** | the same loader |
| Two kit versions in one cohort (self-pinned two-kit file) | **refused**, naming both | **refused** ("a cohort is one kit version") |
| **Two kit versions across train, dev and val** (val on the new build under a two-kit file, smoke) | **refused before training**, naming both kits and builds; **no output written** | `check_cohort` runs over train and held-out together |
| **`--scope fit` with a non-default file** (a byte-identical copy at another path, with the right pin, plus a valid pre-registration and parity) | **refused**: "uses the pinned default patch-equivalence file only". The default file passes to the next guard (committed code) | no fit scope exists; see M3 |
| An IDM fit on an unnamed build | | **refused before any frame store opens** (a `FrameStore` spy counted 0) |

**Intake boundary.**
- `recorded_build` writes `patch` as `"<version>/build<buildid>"`, exactly the file's string form.
- It refuses when the Steam evidence doesn't settle the build.
- So tonight's sessions will carry `1.1.3892207/build25501035`, which the file names. A future unnamed build is
  refused at the fit and at the IDM cohort. It **fails closed**, never silently.

## The four admitted tables, and the human smoke identity

- **Byte-unchanged:** 051828 `d49224e3`, 171533 `dc28b0c1`, 200129 `fcc9b044`, 205528 `941950f1`. These equal the
  admitted pins, read from the shared tree only.
- They cohort **with the pinned file** (kit "Season 10, Version 20260911", all on `1.1.3870120/build25364676`) and
  **without it** (four sessions).
- **Human smoke fit, with the file present** (`pe/id/`):
  - Inputs were generated once with the changed fixture; the header `patch` is now the admitted build.
  - `train.main --scope smoke`, 2 epochs, TINY, seed 0, all arms, in `7add7f8` and in the changed tree.
  - **Every file is identical except `report.json`:** checkpoints `18e2dc51` (model), `230828b0` (no-HUD) and
    `f8954ce4` (twin), the same three as in my window-loss review, plus the CPU probabilities and decisions.
  - The report differs only in `code_closure` (the four changed modules), the new `patch_equivalence` and timings. The
    losses, statistics and metrics are equal.

## What reports record

- **The fit's report records `patch_equivalence`:** `path` "data/human/patch-equivalence.json", `sha256_pin`
  `4df869f3…`, `default` true, `kit_version` "Season 10, Version 20260911", and `builds` (both, for a fit across the two
  builds). Each cohort entry keeps its real build.
- **The verifier's `main`** loads the same pinned file (defaults to the fit's path and pin) and passes it to
  `load_cohort`.
- **The IDM's report `cohort` and its checkpoint meta `cohort`** are equal: the file's path and sha256, the kit
  version, and each session's real build.
- **One rule, not two.** `idm_targets.load_patch_equivalence` and `kit_version` wrap the fit's functions, and the IDM
  pin *is* `steps.PATCH_EQUIVALENCE_SHA256` (asserted). `COHORT_KEYS` are the fit's human keys minus `video_size`,
  which a target header does not have.

## Tests (own environments, both trees)

| Suite | `7add7f8` | Changed |
|---|---|---|
| stdlib, whole repo | 1,918 passed, 75 skipped, 1 failed | **1,947 passed**, 76 skipped, 1 failed (the same) |
| torch: `tests/test_range_bc_torch.py` | 30 passed | **31 passed** |
| execution: `test_idm_eval`, `test_idm_model`, `test_idm_targets`, `test_idm_decode`, `test_replay_camera` | 79 passed | **84 passed** |

- The one failure is the export-only `test_range_skill_loop`: it reads a git-ignored report. The extra skip is the new
  `--corpus` test, whose claims I reproduced read-only above.
- The IDM lane's one-off `test_training_is_byte_reproducible_on_cpu_and_learns` failure did **not** recur.

## Findings (minor; none blocks, given the two conditions)

- **M1. A caller that omits the file still gets the old behaviour.** `load_cohort(equivalence=None)`, and with it
  `load_arrays(...)` and `verify(...)` by default, falls back to exact comparison.
  - That **accepts a cohort made entirely of an unnamed build.** Probe: two tables on `1.1.3999999/build29999999`
    cohort with no refusal.
  - No CLI takes this path today; `run_fit` and `verify.main` always pass the file.
  - But the next caller can. For human cohorts, either make the argument required, or default it to loading the pinned
    file.
  - The keyboard/mouse baseline, `policy/execution.py`'s own `load_cohort`, compares `patch` exactly and has the same
    property. It is outside this boundary; noted only.
- **M2. The verifier doesn't bind the run's recorded file.**
  - `verify.main` loads whatever file and pin it is given (default: the code's current pin), but never compares them
    with the report's `patch_equivalence.sha256_pin`.
  - After a future pin change (a new build added), an old run is re-verified under a different mapping without notice.
  - Require the loaded pin to equal the report's, when the report has the record. The author lists this as a
    follow-up.
- **M3. The IDM is asymmetric with the fit.**
  - The IDM accepts a non-default file (with its pin) at every scope, `gate1-dev` included.
  - Its `cohort` record has no `default` flag, and its `path` is absolute (machine-specific) where the fit records the
    argument.
  - Record `default`, and refuse a non-default file at any gate scope, as `--scope fit` does.
- **M4. The pre-registration's order can't be checked.** The note's title says "before any code". The brief says the
  code for items 1-5 predated the note's first version; the hand-back says the note was registered first, at
  `d7965977…`.
  - The note is untracked, so neither order can be checked.
  - The rule is the one in the lead's design (`patch-equivalence-design.md`, 22:14), which does predate the code.
  - Let the lead settle the title's wording when landing.
- **Note: the file's integrity rests on the pin living in code.**
  - An edit without a new pin is refused everywhere (probed). An edit with one is a code commit, visible in review.
  - With the file force-added (condition 1), every landed cohort's mapping stays recoverable by its recorded pin.

## Bytes reviewed (sha256)

| File | Raw (working tree) | LF |
|---|---|---|
| `data/human/patch-equivalence.json` | `4df869f31178898cc9d93c6c1108698fa0cc3321524aae0fa10b33b889c6bba4` | `4df869f31178898cc9d93c6c1108698fa0cc3321524aae0fa10b33b889c6bba4` |
| `docs/lanes/end-to-end-fit-patch-equivalence.md` | `01c8d7054610a57163a6875c097683336db3f0c669cd56e003487bbfda04ab17` | same |
| `policy/range_bc/steps.py` | `396633fbaebe2d25889bb572e366701fbe1d175d88b023c04c2cad7cb89ca75e` | `b79d5a49242df77b4de0dae7947e9870624fc8fd2a1dfff64a68d74272e3521b` |
| `policy/range_bc/train.py` | `c1e73469051eea04acb26ca24cf3f5c88b0263fda5b67be1e9559b87b487e662` | same |
| `policy/range_bc/verify.py` | `ead3dea861f633f8510c75581e192f2ed6501dd551ff65cc26f216aa898b2415` | same |
| `policy/range_bc/fixture.py` | `071012c25fdb004291b0dd114c5ee153f03dedb077da79b794c8d6b6b4e7528b` | same |
| `tests/test_range_bc.py` | `3bc4db9c70970b527e01c18a36cdcbb3238a16142b89781995877ecfcdc9cd63` | `914144d532968bc3cb6e913fcf8a1d1dacfbd4ae033f4c9e51f49505070bc35c` |
| `tests/test_range_bc_torch.py` | `404108251c1898c45b17da85c98e005f60acc4bcff7c1e1d552fe6e97d0a3fc0` | `fb521e1715bd3215dd7a28d8423d428a7c24e56b3811a9811b1931017fabd21f` |
| `policy/idm_targets.py` | `18b3f800519c56416a85e8aa9d0ceeaefdaf63ab6c66918e6992f9c4185fa135` | `ffd54c7ebfb71b1ed9fe2531ee31744544ff2446181574c0f9fb9879339e179a` |
| `policy/idm_eval.py` | `a74e04aa70029cabfbe96087470a6778b5c9d8b784e287524f86d9b84cef437f` | `d32c341a102d212e7d15c0f178976d3bc012f252986af146479d000c5c2e4153` |
| `policy/idm/train.py` | `2e450c92443017661f11e403ab429ed6bbb7be03c0f66c8c2b00229ff26dbbc5` | `72a2f2482d3ef60d72fd002282b1045cdb5c7d42c24aba3f6a51a7f53e2c8394` |
| `tests/test_idm_targets.py` | `8ca8aea4e0230bdd1a890cb29176e656137908712d421e1cfc2cfa7f09587fdd` | `e0a0fd4d9fc2798a932b9c7eba7abb49537e744cd118621253f7ce93b494c087` |
| `tests/test_idm_eval.py` | `28d2b894f755f2254830bd7812481f33342efda4d071ad9d101f6fabeda1b2bd` | `ae460db57dfd0b15709b844240cc9e2f00d369b6f2a102e8f1865a9da05d2f3b` |
| `tests/test_idm_model.py` | `5ceb2a891f76f2edeb3dfbdcf3eff226024e7cfb76fb94b9bc36ba94f80a2748` | `867d337fd1c7e65d3010afcb77758b39a91c33f219eff1b1c1c4d3de6f38afd6` |
| `handoff/patch-equivalence-design.md` | `b1e95a326006f8604b261c1cca37f391f5613cbbc72149f6b0aa84fc89eb6c59` | |
| `handoff/fit-patch-equivalence.md` | `48f1169f1b1dc8cbf7ed42918fa4487f1df74892346c265d0d48416a07885fd6` | |
| `handoff/idm-patch-equivalence.md` | `a80df9a7d186f21d0fc574f86cd7f6c011e4efa76584d0ef100ec05480eb35be` | |
| `handoff/intake-patch.md` | `f6d5c2fbe46e03bc19ddd625bcfaf725e0896e29b70879275c0dff09c37f1ff5` | |
| `handoff/brief-fit-review-patch-equivalence.md` | `4a800b02c7c462633c9401e973f5403c56d21db614120e797021a04b80ad8d68` | |

The intake files (`agent/human_intake.py`, `assemble_session.py`, `intake_session.py`, `tests/test_human_intake.py`)
were read only at the boundary above; admission-review owns them.

My scripts and logs are in my scratchpad under `pe/`: `probe/`, `id/`, `idm/`, `t-*.log` and `tests-summary.txt`.
