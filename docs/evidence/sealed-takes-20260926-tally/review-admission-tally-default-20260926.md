**Verdict: LAND. The new default reproduces the committed tally JSON and Markdown byte for byte; reverting the default to 86a1912 makes both tests fail; only the four requested recording-log intake cells changed. No blocking findings.**

Independent admission-review (Codex), VUH-1359, 2026-09-26T17:51:15.359445+00:00. Hand-back `admission-tally-default-20260926.md`, SHA256 `047abb1cb27b15757b5c5d809b1042d8be0f176b366840459a657a8b241a6b50`.

- **Default and output:** `DEFAULT_SNAPSHOT` is `code-snapshot-e7f5045`, used by both `build()` and the CLI argument default. Extracting `build()` preserves the calculation and rendering; it returns data without writing the production artifacts. Both new tests passed with `--corpus` in fresh interpreters, including the real admitted-freeze checks. Generated JSON matches **0be5b59c2082e71e2fe097f9f6e88cd77bcb7bebe467b5cafe5baffda8775120**, and generated Markdown matches **8b7dde1a15a4d8a5493efcbd9dbb652b10558e638f278a303fb3ea76b1055c32**. The test normalizes comparison-file line endings; I additionally verified the current files are already exact committed LF bytes, so this is a literal byte match, not merely normalized equivalence.
- **Regression sensitivity:** an in-memory copy of tally.py was loaded with only the default literal changed back to `code-snapshot-86a1912`. Both tests fail with **denylisted session outside test** for the first gate2 identity. The mutant stops at registry validation before the expensive corpus hashes. No production source or snapshot was modified.
- **Recording log:** exact line/cell comparison against HEAD found four changed lines and no additions/removals. Each row is identical through its first five data cells; only its final intake-status cell changes. The four rows are **10-38-35, 10-57-37, 11-10-08 and 11-26-48 on 2026-09-26**. Their sealed test, paired gate2, reader-development and calibration statuses agree with the previously reviewed evidence.
- **Scope:** all three owner file pins match. The registry, denylist, numerical calibration and previously accepted admission decisions were not reopened. The tally remains **180.57 train / 15.58 val** minutes.

Verification ran sequentially. Python workers installed the **hard Windows job per-process commit limit of 2 GiB**, inherited by fresh-interpreter test children. The hash-check worker was observed at about **21 MiB private memory**. Hashing used chunked reads; no full video/NPZ allocation, video decode, protected logger access or game input. An OBS/Marvel process guard surrounded subprocess launches and monitored the active hash worker. No production files edited, no commits; only review scratch and this report were written.

Evidence beside this report in `review-tally-default-work/`:

| Artifact | SHA256 |
|---|---|
| audit.json | `a22796139eb99fc83297919c6266b7d0f2402377660522ad441cae8ffc0ee8a1` |
| tests.txt | `5ded97de0e7cc61f5e2462897aafea62d35beaafdfde5f38a3df8388d13c2eb7` |
| mutation.txt | `e16f7bc76d29b53ca6475f7b088f3defddcf2a14c66a63df2e71eb2066a9fc7f` |
| run_tests.py | `2fadbb6428443116de44b9179f3fcfbd19a00b99805bed7b85b08610d20b8efd` |
| mutation.py | `ad1b7a94f80eeb04f4160607114cb49230ec4cd58866714526106f54fd34159e` |
| cap.py | `dfb6c3475cfa41b55e86c5876da37df58872bbdf2b4bd546dcde9b41636000bc` |
| live_guard.py | `377510729bb74badc78465d43b6c689e88b37ed4084bd6882ae0eb16076c515c` |

Production LF pins:

- `data/human/sessions/tally.py`: `90bab987677106023d9926e5c41dc3f1af5d645cf6bf95bee74e90bf3a71207f`
- `tests/test_tally_default.py`: `8c80fccf102f5a38636f182d95c6b6eb5127e994ebd4ae47587b5b214714917a`
- `docs/recording-log.md`: `eaba5c923f4f3d553a4bcdf96d01049d11db248bd754cf2728ca74f27e40c384`
