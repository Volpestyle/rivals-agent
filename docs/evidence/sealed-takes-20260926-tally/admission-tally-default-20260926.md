# admission-tally-default-20260926: tally.py's default snapshot, and today's recording-log intake cells (quick review)

This is a follow-up to bcf5495, fix-forward, for admission-review's quick review. Nothing is committed.

## 1. `tally.py` defaults to a snapshot that validates the live registry

**`data/human/sessions/tally.py`** (LF `90bab987677106023d9926e5c41dc3f1af5d645cf6bf95bee74e90bf3a71207f`):
- **The default** is `DEFAULT_SNAPSHOT = "code-snapshot-e7f5045"`, previously `code-snapshot-86a1912`. That snapshot is
  committed in bcf5495 (manifest `ccefa568…`) and carries the reviewed `check_registry`, which knows `allowed_split` and
  checks every list.
- **Why the old default fails:** `code-snapshot-86a1912` refuses the live registry against the pinned v2 with
  "20260926T002109-428Z-63684-2: denylisted session outside test" (reproduced just now).
- **The work moved into `build(snapshot)`,** which returns (tally doc, markdown), so a test can compare without writing.
  `main()` writes the same two files as before, and prints the markdown.

**`tests/test_tally_default.py`** (new, LF `8c80fccf102f5a38636f182d95c6b6eb5127e994ebd4ae47587b5b214714917a`). Both
tests run in a fresh interpreter, as the command line does, so the snapshot's own `agent.human_intake` is the one
imported.
- **`test_the_default_snapshot_is_committed_and_validates_the_live_registry`** (not corpus):
  - the imported module is the snapshot's;
  - `check_registry` with the pinned v2 accepts the live registry (splits {gate2, test, train, val});
  - the snapshot's manifest is tracked in git.
- **`test_the_default_reproduces_the_committed_tally_byte_for_byte`** (`@pytest.mark.corpus`: it hashes every admitted
  freeze): `build()` with the default equals the committed `tally.json` (`0be5b59c…`) and `corpus-tally.md`
  (`8b7dde1a…`), byte for byte.
- **Results:** `pytest tests/test_tally_default.py` gives 1 passed, 1 skipped. With `--corpus`: **2 passed** (2 min 41 s).

## 2. `docs/recording-log.md`: today's four intake-status cells

`docs/recording-log.md` (LF `eaba5c923f4f3d553a4bcdf96d01049d11db248bd754cf2728ca74f27e40c384`; it equalled HEAD
before the edit). **Only the last cell of each of the four rows changed**, checked by comparing every row against
`git show HEAD` with the last cell stripped: 4 lines changed, and each is identical up to its last cell.

| Row | New intake status (summary) |
|---|---|
| 2026-09-26 10-38-35.mkv | sealed test, in denylist v2 (allowed_split test, `58ddc1de…`). The held 153812 (its deleted 11 s video, hashed from the Recycle Bin, `1dcf54c0…`) is sealed with it; both registered test; landed bcf5495 |
| 2026-09-26 10-57-37.mkv | gate2 replay half of pair 2, `gate2-20260925-hall-of-djalia-1949`, with the whole of 19-28-51 as its live half; sealed by split and in denylist v2 (`29f1a48f…`); never opened; landed bcf5495 |
| 2026-09-26 11-10-08.mkv | evaluation-only `reader_development`, paired with 20-06-20, never trained (`4c74f388…`); landed bcf5495 |
| 2026-09-26 11-26-48.mkv | calibration, never a split; leftward gain +0.001 / −0.006 / +0.039 % (mean +0.011 %, all within ±0.08 %): direction-symmetric. 162623 is an Alt+Tab false start, not registered; landed bcf5495 |

**Unchanged:** `tally.json`, `corpus-tally.md`, the registry, the denylist and every other file of bcf5495.

No commits, no Linear, no game input, nothing on the Mac.
