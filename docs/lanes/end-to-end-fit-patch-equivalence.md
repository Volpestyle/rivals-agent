# End-to-end fit: cohort patch equivalence (pre-registration, 2026-09-24, before any code)

**Why this note is separate.** It continues `end-to-end-fit.md`. That note's current bytes (`2bb576bf…`) are pinned by
`docs/evidence/changed-boundary-reviews-20260924/review-window-loss.md`, so it is a frozen review packet (AGENTS.md).
This note holds the fit lane's sections from 2026-09-24 on.

**The decision** (the lead's, `patch-equivalence-design.md`, 2026-09-24). Steam updated Marvel Rivals to
`1.1.3892207/build25501035`, while every admitted session is on `1.1.3870120/build25364676`. The version 20260924 patch
notes change no hero, HUD or practice range. So builds are grouped into cohorts **by kit version, not by raw build**.
`docs/spiderman-kit.md`'s "Patch reflected: Season 10, Version 20260911" still holds and is not edited.

## The rule

1. **The data file** `data/human/patch-equivalence.json`, format `rivals-patch-equivalence-v1`:
   `{"kit_versions": {"<kit version>": {"builds": [...], "evidence": [...], "decided_by", "decided_on"}}}`.
   - Adding a build to a kit version is a lead decision with evidence, recorded in this file and the recording log.
   - The fit pins it like the sealed denylist: `steps.PATCH_EQUIVALENCE` and `steps.PATCH_EQUIVALENCE_SHA256`, the
     sha256 over LF-normalised bytes.
2. **In `steps.load_cohort(..., equivalence=)`,** for human cohorts, the `patch` key compares **the kit version each
   session's build maps to**, not the build string. Every session's build must be named by the file, even in a cohort
   of one. The other identity keys are compared exactly, as before.
   - Every step-table header keeps `patch` = the real build (truthful provenance). No admitted table is re-emitted.
   - Without `equivalence` (library callers, synthetic tests), the comparison stays today's exact one.
3. **Every CLI that builds a cohort loads the pinned file and passes it:** the fit (`train.run_fit` → `load_arrays`)
   and the verifier (`verify.main` → `verify.verify`). Like the denylist, `--scope fit` accepts only the pinned default
   path and pin. `--patch-equivalence` and `--patch-equivalence-sha256` exist for smoke and plumbing runs and for tests.
4. **Replay cohorts are unchanged:** their `patch` is the replay's free-text client note, compared exactly. The CLI
   refuses replay cohorts anyway.
5. **Each `load_cohort` call is one split's cohort,** as today: the fit loads train, dev and val with separate calls.
6. **Amendment (the lead's DECISION, 2026-09-24, added before its code): one kit version across the whole fit.**
   After loading train, dev and val, `train.main` (`run_fit`) requires every loaded human session to map to **one** kit
   version under the same file, and refuses otherwise before anything is trained. The refusal names every kit version
   found and the builds under each. Before this, nothing compared builds across splits.

## What it refuses

- **A file whose LF-normalised sha256 differs from the pin:** "patch equivalence refused: … differs from its pinned
  sha256".
- **A malformed file:**
  - the wrong format, or no kit version;
  - an entry without a non-empty `builds` list, a non-empty `evidence` list, `decided_by`, or a `YYYY-MM-DD`
    `decided_on`;
  - an empty or non-string build;
  - **one build listed under two kit versions**.
- **A human session whose build the file does not name.** The message names the build and the file, and says that
  adding it is a lead decision with evidence.
- **A cohort whose sessions map to different kit versions.** The message names both kit versions and the build.
- **A fit whose train, dev and val sessions together map to more than one kit version** (amendment, item 6).

## What the fit's report records

`patch_equivalence`:
- `path` and `sha256_pin`;
- `default` (pinned path and pin);
- `kit_version`: the one kit version of the whole fit (amendment);
- `builds`: every build among the loaded train, dev and val sessions, sorted.

The per-session `cohort` entries keep their real `patch`.

## Acceptance tests (with the code)

1. **Two builds under one kit version cohort together.** The two real builds, through the real pinned file, and two
   synthetic builds through a test file.
2. **A build the file does not name is refused,** with a message naming it. Two kit versions in one cohort are
   refused.
3. **A tampered file is refused by its pin.** Malformed files are refused, including a build under two kit versions.
4. **The four admitted tables** (051828, 171533, 200129, 205528) load and cohort as before, with and without the file,
   and are byte-unchanged (their sha256 equal the admitted pins). This is a `corpus`-marked test, run with `--corpus`.
5. **Replay cohorts are unaffected.** Every existing test passes, in the stdlib and perception environments.
6. **One kit version across splits** (amendment): a fit whose val session's build maps to another kit version is
   refused before training, naming both kit versions and their builds. A fit across the two real builds records
   `kit_version` and both builds.
7. **The human fixture** now records the admitted build, so every fit and verifier CLI test runs through the real
   pinned file. Human training output stays byte-identical: the smoke-fixture identity check `9d74453f…`.
