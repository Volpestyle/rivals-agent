# fit-patch-equivalence (VUH-1359, VUH-1346): cohorts by kit version (design items 1 and 2, with the lead's amendment)

**Human cohorts now compare the kit version their builds map to, not the raw build.**
- The mapping is `data/human/patch-equivalence.json`, pinned like the sealed denylist.
- The fit also refuses a train, dev and val set that spans two kit versions.
- Headers keep the real build. No admitted table was re-emitted: all four are byte-unchanged.
- Uncommitted, in the shared tree. fit-review reviews; the lead lands.
- No commit, no Linear write, no game input, no Mac.

## Land with care: the data file is gitignored

`data/human/patch-equivalence.json` falls under `.gitignore`'s `data/`, so it needs **`git add -f`**, like
`data/human/sealed-denylist.json`.
- **If it is not tracked,** the stdlib and torch tests that load it fail on a clean checkout (CI).
- **A `git archive` for the Mac fit** would also lack it, and the fit would refuse to start ("patch equivalence
  refused", file missing).

## Pre-registration

**Where:** `docs/lanes/end-to-end-fit-patch-equivalence.md`, per the lead's DECISION (a new note, because
`end-to-end-fit.md` is a frozen review packet).
- **Registered first** at `d7965977…`, before any code.
- **The lead's amendment** was added before its own code: one kit version across train, dev and val, recorded in the
  report. The note is now `01c8d705…`.
- **Order, honestly:** the code for the original rule (items 1-5) was already written when the amendment arrived.
  Only the cross-split check was written after it.

**The rule:**
1. `load_cohort(..., equivalence=)` compares human sessions' kit versions and refuses a build the file does not name,
   even in a cohort of one. Without the argument, today's exact comparison stays. Replay cohorts always compare their
   free-text `patch` exactly.
2. Every CLI that builds a cohort loads the pinned file and passes it: the fit, and the verifier's `main`. `--scope
   fit` accepts only the pinned default path and pin, as for the denylist.
3. `run_fit` refuses, before training, loaded train, dev and val sessions that map to more than one kit version. The
   message names each kit version with its builds.
4. The report records `patch_equivalence` = {`path`, `sha256_pin`, `default`, `kit_version`, `builds`}.

**What it refuses:**
- a file whose LF-normalised sha256 differs from the pin;
- a malformed file:
  - the wrong format, or no kit version;
  - an entry lacking non-empty builds or evidence, `decided_by`, or a `YYYY-MM-DD` `decided_on`;
  - an empty build;
  - a build under two kit versions;
- an unnamed build, with a message naming it;
- two kit versions in one cohort, or across splits.

## The data file, exactly as designed

`data/human/patch-equivalence.json`, format `rivals-patch-equivalence-v1`, one kit version:
- `"Season 10, Version 20260911"`, matching `docs/spiderman-kit.md`'s "Patch reflected" line, which was not edited;
- `builds`: `1.1.3870120/build25364676` and `1.1.3892207/build25501035`;
- `evidence`: the two patch-note URLs and "docs/spiderman-kit.md Patch reflected line";
- `decided_by` "lead", `decided_on` "2026-09-24".

It is LF, indent 1. Pin: `steps.PATCH_EQUIVALENCE_SHA256 = 4df869f3…`.

## What changed in code

| File | Change |
|---|---|
| `policy/range_bc/steps.py` | `PATCH_EQUIVALENCE`, `PATCH_EQUIVALENCE_SHA256`, `PATCH_EQUIVALENCE_FORMAT`; `PatchEquivalence`; `load_patch_equivalence(path, sha256_pin)` (the pin and structure checks); `kit_version(build, equivalence)`; `load_cohort(..., equivalence=None)` |
| `policy/range_bc/train.py` | `--patch-equivalence` and `--patch-equivalence-sha256` (defaults: the pinned file and pin); `--scope fit` refuses a non-default one; `load_arrays(..., equivalence=)`; the cross-split kit-version check (amendment); the report's `patch_equivalence` |
| `policy/range_bc/verify.py` | `verify(..., equivalence=None)` passes it to `load_cohort`; `main` loads the pinned file (`--patch-equivalence` and `--patch-equivalence-sha256` default to the fit's) |
| `policy/range_bc/fixture.py` | `PATCH = "1.1.3870120/build25364676"`: human fixture sessions record the admitted build, so every fit and verifier CLI test runs through the real pinned file. The replay fixture keeps `synthetic-patch` |

**Not done here:**
- **The verifier does not compare the report's `patch_equivalence` record** (no new verifier check; old reports lack
  the field). Possible follow-up.
- **The IDM lane's `idm_targets`** (design item 4) can use `steps.load_patch_equivalence` and `steps.kit_version`.
  Their working-tree changes are theirs; I did not read or touch them.

## Tests

**`tests/test_range_bc.py`: 13 new items.**
- **Two builds under one kit version cohort together:** the two real builds through the real pinned file, and two
  synthetic builds through a test file. Without the file, the old exact refusal remains.
- **A build the file does not name is refused** with a message naming it, including a cohort of one. Two kit versions
  in one cohort are refused with both named.
- **Malformed files are refused,** 8 parametrized cases, including a build under two kit versions.
- **A tampered file is refused by its pin.** A CRLF copy still loads (LF-normalised pin). No pin means no file.
- **Replay cohorts are unaffected.**
- **The four admitted tables** (`corpus`, run with `--corpus`: **1 passed**) load and cohort with and without the file,
  their sha256 equal the admitted pins (`d49224e3…`, `dc28b0c1…`, `fcc9b044…`, `941950f1…`), and their build is the old
  one.

**`tests/test_range_bc_torch.py`:**
- **New, `test_train_dev_and_val_must_map_to_one_kit_version`:**
  - a val session on `1.1.3892207/build25501035`, under a test file that puts it in another kit version, is refused
    before training, naming both kit versions and builds, and no report is written;
  - with the pinned file, the same fit runs, recording `kit_version` "Season 10, Version 20260911", both builds, and
    the real build in each cohort entry.
- **The CLI end-to-end test** asserts the report's `patch_equivalence` record.
- **`test_scope_fit_refuses_what_the_review_asked`** gains a non-default patch-equivalence case.

**Human byte-identity** (the fixture's header `patch` changed): the smoke fixture's checkpoints, losses, statistics and
dev metrics are **byte-identical**, `9d74453f…`, after both rounds of change.

**Counts** (my own environment, `UV_PROJECT_ENVIRONMENT=C:\Users\volpe\.uv-envs\hud-review`; the shared `.venv` was
not touched):

| Run | Result |
|---|---|
| Whole repo with torch | **3,122 passed, 111 skipped, 5 failed** |
| Corpus: the four admitted tables | **1 passed** |
| Stdlib, whole repo (exact sync) | **1,954 passed, 70 skipped, 0 failed** |
| Perception, whole repo | **3,006 passed, 159 skipped, 5 failed** |
| `ruff check policy/range_bc/ tests/test_range_bc.py tests/test_range_bc_torch.py` | All checks passed |

- **The 5 failures** are the same unrelated ones as in the last three hand-backs, none of them `range_bc`:
  `test_replay_states` ×3 and `test_scoreboard` ×1 lack local data; `test_hud_accuracy` misses its latency limit
  under load.
- **The counts include other lanes' working-tree changes** in the shared tree (IDM files and `tests/test_human_intake.py`
  are modified, not by me). All of theirs passed too.
- **A run was stopped:** the first full-suite run was on the pre-amendment code. I stopped it to add the cross-split
  check (and killed its leftover processes); the counts above are the rerun.

## Bytes (sha256; working tree; raw, then LF-normalised where the file is CRLF)

| File | sha256 raw | LF-normalised |
|---|---|---|
| `data/human/patch-equivalence.json` (new, gitignored: `git add -f`) | `4df869f31178898cc9d93c6c1108698fa0cc3321524aae0fa10b33b889c6bba4` | same (the pin) |
| `docs/lanes/end-to-end-fit-patch-equivalence.md` (new) | `01c8d7054610a57163a6875c097683336db3f0c669cd56e003487bbfda04ab17` | same |
| `policy/range_bc/steps.py` (CRLF) | `396633fbaebe2d25889bb572e366701fbe1d175d88b023c04c2cad7cb89ca75e` | `b79d5a49242df77b4de0dae7947e9870624fc8fd2a1dfff64a68d74272e3521b` |
| `policy/range_bc/train.py` | `c1e73469051eea04acb26ca24cf3f5c88b0263fda5b67be1e9559b87b487e662` | same |
| `policy/range_bc/verify.py` | `ead3dea861f633f8510c75581e192f2ed6501dd551ff65cc26f216aa898b2415` | same |
| `policy/range_bc/fixture.py` | `071012c25fdb004291b0dd114c5ee153f03dedb077da79b794c8d6b6b4e7528b` | same |
| `tests/test_range_bc.py` (CRLF) | `3bc4db9c70970b527e01c18a36cdcbb3238a16142b89781995877ecfcdc9cd63` | `914144d532968bc3cb6e913fcf8a1d1dacfbd4ae033f4c9e51f49505070bc35c` |
| `tests/test_range_bc_torch.py` (CRLF) | `404108251c1898c45b17da85c98e005f60acc4bcff7c1e1d552fe6e97d0a3fc0` | `fb521e1715bd3215dd7a28d8423d428a7c24e56b3811a9811b1931017fabd21f` |

**Suite log:**
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\patch-suites-2.log`.
