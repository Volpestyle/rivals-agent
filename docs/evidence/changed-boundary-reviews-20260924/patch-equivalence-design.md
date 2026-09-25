# Lead decision: game builds are grouped into cohorts by kit version, not by raw build (2026-09-24, PC 22:15)

**Fact.** Steam auto-updated Marvel Rivals at 06:15 today to `1.1.3892207/build25501035`. Every admitted session is
`1.1.3870120/build25364676`. `policy/range_bc/steps.py:load_cohort` refuses a cohort whose `patch` differs;
`data/human/sessions/assemble_session.py` hard-codes `PATCH` to the old build; `policy/idm_targets.py` IDENTITY includes
`patch`. Tonight's four takes are on the new build.

**Evidence that the kit is unchanged.** Version 20260924 patch notes (https://www.marvelrivals.com/gameupdate/20260923/41548_1314808.html,
https://marvelrivals.gg/marvel-rivals-version-20260924-patch-notes): a new Domination map (God Quarry), Galacta's Gift
Vol.3, three store bundles, one bug fix (Devil Dinosaur KO-feed icon). No hero balance, no HUD, no practice-range change.
`docs/spiderman-kit.md`'s "Patch reflected: Season 10, Version 20260911" therefore still holds; that line is not edited.

**Design (minimal, no re-emission of admitted tables):**
1. A pinned data file `data/human/patch-equivalence.json`: `{"format": "rivals-patch-equivalence-v1", "kit_versions":
   {"Season 10, Version 20260911": {"builds": ["1.1.3870120/build25364676", "1.1.3892207/build25501035"], "evidence":
   [<the two URLs>, "docs/spiderman-kit.md Patch reflected line"], "decided_by": "lead", "decided_on": "2026-09-24"}}}`.
   Adding a build to a kit version is a lead decision with evidence, recorded in this file and the recording log.
2. `steps.load_cohort` (fit lane): the `patch` key compares the **kit version** each session's `patch` maps to under
   this file (loaded like the sealed denylist, pinned by sha256 in the report), and refuses a build the file does not
   name. The step-table header keeps `patch` = the real build (truthful provenance); no admitted table is re-emitted.
   The report records the equivalence file's sha256 and every build in the cohort.
3. `assemble_session.py` (admission lane): replace the constant with the build read at intake from Steam's
   `appmanifest` / content log for the recording's date (the same source the constant cites), with that evidence in
   `provenance.game_patch`; refuse to assemble if it cannot be read. Keep the header contract unchanged.
4. `idm_targets` (IDM lane): IDENTITY compares the kit version through the same file; targets keep the real build.

**Review.** Items 2 and 4 decide what enters a training set: independent review by fit-review before landing. Item 3 is
the admission lane's file with its own tests; admission-review checks it with the first new session.
