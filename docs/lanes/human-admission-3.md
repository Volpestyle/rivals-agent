# Human admission: admission-codex, from 2026-09-27

**Status (2026-09-29): CURRENT.** The admission owner's note. Its "Work in progress" items are history: the night batches are complete ([night set](human-admission-night-complete-20260927.md)). Status is on Linear.

Continues `human-admission-2.md` and the accepted ownership handoff
`human-admission-handoff-20260927.md`. Earlier snapshots and evidence remain intact.

## Delivered

- `c4c8b2d` landed the predecessor's exact five handoff paths; their supplied hashes
  matched. Inherited verification: 368 passed, 4 skipped, reused for unchanged bytes.
- `5c20c8d` fixes independent review F1: the PTS-anchor fallback requires exactly
  one explicit accepted outcome bound to the session. Rejection, item-only,
  wrong/missing session and conflicting decisions refuse. Focused suite: 28 passed.
  The lead reports fit-review LAND; -12's actual basis wording remains unchanged.
- `f641ef3` delivers four whole-file S6.5 SSL sources: 90,920,475,225 bytes and
  26,767.174 seconds. `docs/evidence/ssl-s65-admission-20260927/admission.json`
  is pinned in that packet's README. Label-free world features only; no semantic
  labels or eligible intervals. idm-owner owns native sampling and the cut-free
  sampled-clip manifest. Independent post-landing review is pending.

## Memory boundary before resuming decode

The inherited 60-second vote retained 300 native 2560x1440 BGR frames (3.32 GB
before overhead). Evidence also retained every review frame. The lead authorized
bounded storage without changing selected frames, readers, votes or labels.

- `intake_session._decode` now yields at most eight native frames per exact-PTS
  decode window, with two decoder threads. Edge proofs and review-frame writes
  consume the iterator without retaining all native arrays.
- New snapshot `code-snapshot-f8fd92c-bounded-20260927` copies all 140 predecessor
  files after hash verification. Only its scan file changes: vote arrays spool
  losslessly to individual NPY files, read one at a time on both existing voting
  passes, and are removed after success. Scan decoder threads fall from four to
  two. The reader, frame sampling, mapping and majority rule are unchanged.
- New tests verify bounded lazy decoding and ordered pixel equality, plus exact
  spool round trips and equal mapping votes on existing authorized native fixtures.
  `test_intake_streaming.py` + `test_intake_match_mode.py`: 30 passed.
- Native decode parity and remaining-session resource peaks are not yet measured.
  Results remain provisional until the post-landing delta review.

## Work in progress

- -4 owner inspected all supplied gameplay contact sheets: eight candidate
  accepts, 303.633321196 seconds. Other segments rejected by machine rule without
  claiming visual inspection. Owner record explicitly distinguishes thumbnail
  inspection from inherited native hashes. frame-review owns the additional
  decoder slot for native independent verdicts.
- -6 now has regime, motor and proposal after the inherited scan. Evidence next.
- -7/-8/-10/-11/-12 remain through batch 1. Check chat/change-hero in -7 and emote
  handling in -11/-12. -12 assembly uses the reviewed session-bound anchor gate.
- Accepted -5 relocation remains admission-owner's active work. No duplicate
  transfer was started. idm-owner was told to reuse that destination.

The lead permits one additional decode beside its compression batch while
Marvel/OBS are absent: BelowNormal, less than 3 GB per process, check RAM before
each decode and stop below 2 GB free or when game/OBS starts. Admission and
frame-review coordinate that slot explicitly.
