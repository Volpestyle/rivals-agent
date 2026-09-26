# admission-reader-validation-20260926: two match recordings move to reader_validation (VUH-1353; quick review)

This is on top of cf03945. Nothing is committed.

## The change

In `data/human/session-splits.corpus.json` → `evaluation_sessions`, two rows move from `match_dev` to `reader_validation`.
In each, `kind` and `session_group` both change (the existing `reader_validation` rows use `reader_validation` for
both), and the `note` is replaced with the role note:

| Session | Video | Role note (new `note`) |
|---|---|---|
| `20260926T021321-378Z-63684-9` | `2026-09-25 21-13-21.mkv` (God Quarry, last ~3 min) | moved from match_dev to reader_validation (lead 2026-09-26, VUH-1353): a fresh validation source for the Gate 2 readers' one re-validation; no lane has decoded it. Evaluation-only: never a split, never trained on |
| `20260926T034805-307Z-63684-13` | `2026-09-25 22-48-05.mkv` (Lower Manhattan competitive, main account) | the same, plus "(the admission lane read only its logger metadata and input log on 2026-09-25, to say it was a match)" |

- **The disclosure in the second note:** my arrivals-0925-late check read 22-48-05's logger metadata and input log on
  2026-09-25 (Tab ×56, Enter ×8). No frame of it was ever decoded.
- **Everything else is byte-identical:** `sessions`, `calibration_sessions`, the other 7 evaluation rows and the
  top-level fields, checked by structural comparison against HEAD. Key order within the two rows is unchanged. The
  diff is those 6 lines.

## Result

| File | LF sha256 |
|---|---|
| **`data/human/session-splits.corpus.json`** | **`e8a1d0606bfc62fe304e73c78d94f4f62e90d9ef6468a09c486a8f5218ce7e29`** (25,510 B; was `4b615b7b…`) |
| `data/human/sessions/tally.json` (regenerated: only its `registry.sha256` line changed) | `e94e401d38f0323b68102c6ebf2e80ee772a66c6e4eee57570fc8a0dfdc323e3` |
| `docs/evidence/corpus-tally.md` | unchanged, `8b7dde1a…` |

- **The registry validates with denylist v2** (`check_registry`, the pinned `steps.load_denylist()`): 20 split rows,
  12 train, 1 val, 4 gate2, 3 test. The B1 disjointness and sealed-identity checks pass.
- **The tally,** regenerated with the default `code-snapshot-e7f5045`: **train 180.57 (180.569…, 10 sessions), val
  15.58**, unchanged. The two sessions keep their `not_range` tally rows; their reason text is already generic
  ("reader_validation, reader_development or match_dev"), so `tally.py` is unchanged.

## Tests

- `tests/test_sealed_denylist_v2.py`, `test_human_demos.py`, `test_human_intake.py` and `test_gate2_split.py`:
  **313 passed, 3 skipped**.
- `tests/test_tally_default.py --corpus`: **2 passed** (the default reproduces the regenerated `tally.json` and
  `corpus-tally.md` byte for byte).

No commits, no Linear, no game input, nothing on the Mac.
