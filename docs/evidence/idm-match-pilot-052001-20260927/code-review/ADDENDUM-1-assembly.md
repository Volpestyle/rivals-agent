# Addendum 1 to the match-mode packet: motor statements, assembly of -5, pending receipt (admission-owner)

Written 2026-09-27 ~10:57 CDT. This delta follows the lead's `32007db` (James's motor statements, recorded verbatim in
`docs/recording-log.md`). Uncommitted.

**Code (`assemble_session.py`, now in `matchmode.diff`):**
- `MOTOR_STATEMENTS["2026-09-27"]` quotes the 09-27 night line verbatim. It adds `no_pad` ("Keyboard/mouse only"), and
  `applies_to` covers the eight night idm_train Quick Matches only (V-C/V-Q are never assembled).
- `MATCHES_0925`: per-session overrides under `"2026-09-25"` for the six 09-25 evening alt matches, quoting that line
  verbatim with its own `no_pad`. 22-48-05 is not covered, so it stays motor-pending (and `training_pending` in the
  registry).
- Checked: -5 resolves to 2026-09-27 with `no_pad`; 005304 to its override; the range take 203745 is unchanged (no
  `no_pad`, so the 2026-09-23 wording is kept).

**-5 run** (snapshot `code-snapshot-f8fd92c-6046514b`):
- **motor:** `motor-settings.json` `f5d3aa1a…`, settings identity `a8dea3ba…`, the same as the admitted range sessions.
- **assembly:** `--independent-verdicts` is frame-review's v2 record, copied beside the evidence as
  `independent-review.verdicts.json` (`49842f90…`).
  - Import: 63,757 frames decoded, PTS alignment verified.
  - Steps: 15,853 rows, 10,348 accepted, all gap-free.
  - Counted: 5.7515 min over 6 runs; trainable 5.7489 min.
  - Freeze `artifact-hashes.json` `f2f843f6…`: 24 files, 9 external.
- **receipt (PENDING):** `match-admission-052001.pending.json`, sha256 `26095f9a…` (in this folder).
  - `match_targets.Admission.check` passes on it as a dry run.
  - The step header's identity digest equals its `identity_sha256`.
  - The independent reviewer writes the accepted copy (`decision` "accepted", `reviewer` named); the run pins that
    copy's hash.

| Path | sha256 |
|---|---|
| data/human/sessions/assemble_session.py | 9447cbe165ca9d790a35484fda70efd78ff877daa10b9ae8cadf9fcda51d5815 (LF) |
| data/human/sessions/20260927T052001-827Z-150600-5/motor-settings.json | f5d3aa1aecbeaaaa6ca36cdb28d7567f863e9439ebda43fd57c4e6430dfd9f56 (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/independent-review.verdicts.json | 49842f90b8f13c288baa698317c392a90e3cac56551a338bb02f651bd5868999 (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/settings.json | a1d07db38190005486a7f4ffdc9a9c285d07eb058d932305bca49d31430e0cd1 (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/review.json | 15844f604db7d589002208fa701f80410e54c65582f1090ab18e732739d67872 (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/imported-demo.jsonl | 1e016eda97dd663442f77161ec57d1e8fba554f607bb23cf7d6af5c832b1e62c (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/20260927T052001-827Z-150600-5.steps.jsonl | 55a2623aecaaeb6289848d930aa01bd9bc7077896a147c78bbf25feefa4e812c (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/minutes.json | d624e0a586df2ff6b991e19c1a6d1a06960de005c707b104ba78e2623f5bf0d5 (raw) |
| data/human/sessions/20260927T052001-827Z-150600-5/artifact-hashes.json | f2f843f6d1dcbd5bd5038b0c55c833bb5217349141f2fb4f5ff78bf5e16390b4 (raw) |
| handoff/matchmode-0927/match-admission-052001.pending.json | 26095f9abc0853ba7af19fd3c44fd981ed6e4feaf2912c3f7b5aa2110963938e (raw) |

**Known limitation.** Round-start splash overlays have no rule yet (seg-026, rejected whole). The lead asks for that rule
before scaling to the other seven. It will come as its own small delta.
