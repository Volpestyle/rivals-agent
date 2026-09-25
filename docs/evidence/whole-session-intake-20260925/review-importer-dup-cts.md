# Review: the importer's duplicated-composition-time tolerance (`importer-dup-cts.md`), with E1

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only: no session folder was written, and
nothing was committed.

**Bytes reviewed (LF, the git blobs):**

- `agent/human_demos.py` `bf8697d1`
- `tests/test_human_demos.py` `5abcdaef`
- `agent/human_intake.py` `6d43048d`
- `data/human/sessions/intake_session.py` `a7dc71c4`
- `tests/test_human_intake.py` `c63e154b`
- `archive_code_snapshot.py` `5016dd9b`

**The snapshot:** `code-snapshot-dfbb4dd-98e52781`, manifest `6bc89834`.

- All 104 manifest entries verify against their files.
- Its `human_demos.py` and `human_intake.py` equal the repo's LF bytes. The owner's `836b4b79` is the snapshot's CRLF
  bytes of the same file.

**Tests:** `tests/test_human_demos.py`, `tests/test_human_intake.py --corpus` and `tests/test_human_intake_edges.py`, in
my own cv2 environment: **157 passed, 1 skipped** (an absent blank-OBS timing fixture).

## Verdict: approve. The two new takes may be imported, and all three assemblies may proceed

Every point of the brief holds, on my own evidence. The owner's real decode proofs cover `probe_video`. My check re-runs
the only changed function, `match_frames`, old against new, with independent inputs: the logger's `frames.csv`, the
container's own packet list (`ffprobe -show_entries packet=pts`, one full read of each original), each review's
`pts_anchor`, and the accepted spans from the admitted `review.json` files or my own verdict records
(`dupcts.py`, `dupcts2.py`).

| Brief point | Result |
|---|---|
| **The four admitted sessions import identically, and their audits are identical old vs new** | **Holds**, for all four including 200129 (see below) |
| **025230 and 232304: exactly one audited unknown each (distance 1 and 5); the old importer refuses both** | **Holds** (see below) |
| **Distance 9 refused** | **Holds**: my synthetic refs give 5 and 8 excused, 9 refused with "9 packets apart; at most 8" |
| **A duplicate inside an accepted span refused** | **Holds**, on both real takes: an added accepted span over the slot is refused |
| **The slot bound is exclusive** | **Holds** (see below) |
| **The other refusals: no review, a second duplicate, a step back without a duplicate** | **Hold**: each refuses, on the real takes (no review; a second duplicate) and on 205528's packets (a step back without a duplicate) |

**The four admitted sessions.**

| Session | Refs, old vs new | Audit, old vs new | `unknown_composition` |
|---|---|---|---|
| 051828 | field-equal, 50,602 | equal | none |
| 171533 | field-equal, 20,396 | equal | none |
| 200129 | field-equal, 193,155 | equal | none |
| 205528 | field-equal, 80,036 | equal | none |

- With no reversal, the new code takes the old path. The audit's `decoded_frames` and `unwritten_tail_packets` now
  count `pts`, which equals the old refs count whenever nothing is dropped.
- The owner's real re-imports (all four, including 200129 `e8c4fde7`) equal the stored `imported-demo.jsonl`, and
  their old/new audit hashes are equal.

**The two new takes.**

| | 025230 | 232304 |
|---|---|---|
| Old importer | refuses ("composition times go backwards") | refuses (same) |
| Dropped packet | 118 (file pts 1021, frame 120) | 38775 (file pts 323138, frame 38774) |
| Its twin (distance) | 119 (distance **1**) | 38770 (distance **5**) |
| Frames kept | **26,996 of 26,997** | **63,665 of 63,666** |
| Where the slot lies | before focus | inside rejected seg-004 |

- In both, the dropped frame is absent from the refs, and every other frame keeps its decoded `frame_index`, so
  exact-PTS decodes still address the right frames.
- Presentation order is monotone after the drop.
- The audit record carries every field the hand-back lists.

**The slot bound.** Tested on synthetic refs, since the real takes can't be moved:

| Accepted span | Result |
|---|---|
| starts on the next real frame | excused |
| starts 1 ns earlier | refused |
| ends at the previous real frame + 1 (so its last frame is that frame) | excused |
| ends 1 ns later | refused |

This is exactly the fix for the inclusive-bound bug the owner found: 232304's seg-005 starts on the next real frame.

**E1 (from my edge-rule review): fixed.**

- `require_edge_rule` refuses a snapshot whose `human_intake` lacks `EDGE_PROOF`.
- `require_proven_edges` runs right after `propose_segments`, before any review frame or evidence is written. It
  requires a native read with `proof` True at every gameplay edge frame (`start_ns` and `end_ns − 1`). This check
  doesn't depend on which proposer ran.
- The owner reports 021320's scheduled run on the old snapshot was refused by it. The evidence I'm reviewing for 021320
  names `code-snapshot-dfbb4dd-98e52781`.

## Notes (not blocking)

**N1: a span over only the twin is excused.** The rule tests the dropped frame's slot against the accepted spans, not
its twin.

- **Why it holds today:** the drop is chosen by monotonicity with a unique candidate, and in both real takes the twin's
  logged time is its own. For example, 025230's twin, pts 118, logs 0.9833 s = 118/120. Both twins also lie outside
  accepted spans (025230 frame 118; 232304 frame 38772).
- **The suggestion:** refusing a twin inside an accepted span would be a cheap extra guard for a future shape.

**N2: a refused re-emission can leave no current evidence.** With `--supersedes`, the evidence step renames the old
`segments-evidence.json` and `review-frames/` to `.vN` before `require_proven_edges` runs. A refusal would leave the
folder with no current evidence file. Move the rename after the checks, just before writing.

**N3: 8 packets is a stated bound, not a measured one.** `DUP_CTS_MAX_PACKET_DISTANCE = 8` is justified as the reorder
window for 3 B-frames. It fits both observed shapes (1 and 5). The audit records the distance, and anything beyond it
refuses.
