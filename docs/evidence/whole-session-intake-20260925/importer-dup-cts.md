# importer-dup-cts: one recorder-duplicated composition time, excused narrowly (option A, distance 8), plus E1

**For admission-review, before 025230 or 232304 is assembled.**

## The change (`agent/human_demos.py`)

**Where.** `match_frames` gains `accepted=` (the review's accepted spans), and `_build` passes them. Only the importer's
own review path can excuse anything. Every other caller (transcode verification, replay tools) passes nothing and
still refuses.

**When a composition time steps back in presentation order,** `_unknown_composition` excuses it only if all of these
hold:
1. there is **exactly one** reversal in presentation order;
2. the file holds **exactly one** composition value shared by two frames;
3. the two are at most **`DUP_CTS_MAX_PACKET_DISTANCE` = 8** packets apart in packet order. The rationale is in the code
   and in every audit record: this stream's reorder window, NVENC HEVC with 3 B-frames per anchor;
4. dropping exactly one of the two frames at the reversal makes presentation order monotonic;
5. that frame has a real neighbour on both sides (never the first or last frame);
6. **no accepted span covers its slot.** Its true time lies strictly between its neighbours' times, and a span may
   start on the next real frame.

**The frame then leaves the frame references.**
- Its time is unknown and never interpolated.
- `decoded_frames` still counts it.
- The audit gains `unknown_composition`: `[{packet_index, file_pts, frame_index, logged_composition_ns,
  duplicate_of_packet_index, twin_file_pts, packet_distance, max_packet_distance, distance_rationale, slot_ns, reason}]`.

**Anything else still refuses** with "composition times go backwards in presentation order": two duplicates, a step
back without a duplicate, a twin 9 or more packets away, or a slot inside an accepted segment.

**A bug I found and fixed before this hand-back.** My first version bounded the slot inclusively by the neighbours'
times. The 232304 rehearsal was then refused, because its accepted seg-005 starts exactly on the next real frame. The
slot is now exclusive, and a test covers both sides of that boundary. The archived snapshot `code-snapshot-dfbb4dd`
carries the buggy version; nothing recorded uses it.

## The proofs

**1. The four admitted sessions re-import byte-identical**, with the new importer from `code-snapshot-dfbb4dd-98e52781`
(`human_demos.py` sha256 `836b4b79…`; a real `import_session` with an ffprobe decode of every frame, into scratch):

| Session | Re-import sha256 = stored `imported-demo.jsonl` | Frames |
|---|---|---|
| 051828 | `ed98a5c1…` = `ed98a5c1…` | 50,602 |
| 171533 | `6b498977…` = `6b498977…` | 20,396 |
| 205528 | `0906e7e0…` = `0906e7e0…` | 80,036 |
| 200129 | `e8c4fde7…` = `e8c4fde7…` | 193,155 |

All four are byte-identical, none has an `unknown_composition` record, and the stored imports are untouched (each
re-import went to scratch).

**2. Same audit bytes.** The audit isn't stored in `imported-demo.jsonl`, whose payload is the raw data; it is
recomputed on every load. So I loaded each stored import with the **old** importer (`code-snapshot-2ad0992`) and with
the **new** one, in separate processes.

| Session | Old audit sha256 | New audit sha256 | Equal |
|---|---|---|---|
| 051828 | `5813be85…` | `5813be85…` | yes |
| 171533 | `5670ad6e…` | `5670ad6e…` | yes |
| 200129 | `efa281b7…` | `efa281b7…` | yes |
| 205528 | `76e3d7f6…` | `76e3d7f6…` | yes |

**3. Each defective take imports with exactly one audited unknown:**

| Session | Old importer | New importer: unknown packet → its twin (distance) | Frames |
|---|---|---|---|
| 025230 | refused | packet 118 (file pts 1021) → 119 (1004), **distance 1**; slot 1.081–1.098 s (logger time), inside rejected seg-000, the focus transition (corrected 2026-09-25: I first wrote "0.99 s, before focus", measured from the first frame) | 26,996 of 26,997 |
| 232304 | refused | packet 38775 (file pts 323138) → 38770 (323121), **distance 5**; slot 323.243–323.260 s (logger time), inside rejected seg-004 | 63,665 of 63,666 |

- **025230** is from a real `import_session` (sha256 `9d354343…`), with the review from its stopped assembly.
- **232304** is from a **full rehearsal assembly in scratch** (`--sessions-dir`), with the reviewer's v2 verdicts
  (`8a504cbd…`):
  - import, step table (`f60f7f75…`, patch `1.1.3892207/build25501035`, settings `a8dea3ba…`), minutes and freeze
    (`68d1ffaa…`) all completed;
  - **8.7654 counted minutes** (2 runs).

**4. Tests (`tests/test_human_demos.py`, +9):**

| Case | Result |
|---|---|
| distance 1 (025230's shape) | excused, full audit record checked |
| distance 5 (232304's shape) | excused |
| distance 9 | refused, "9 packets apart; at most 8" |
| a duplicate inside an accepted segment | refused |
| an accepted span starting on the next real frame | allowed |
| … starting 1 ns earlier | refused |
| two duplicates | refused |
| a step back without a duplicate | refused |
| a caller without a review | refused |

- **Importer and intake suites: 154 passed, 2 skipped** (the corpus test and one perception test).
- **Full stdlib suite: 1971 passed, 71 skipped.**

## E1 (review of the edge rule): the evidence step runs only the new proposer

- **`human_intake.EDGE_PROOF = 1`** marks a proposer with the edge rule.
- **`intake_session.require_edge_rule`** refuses a snapshot without it.
- **`require_proven_edges`**, after proposing, requires every gameplay edge frame (`start_ns`, `end_ns − 1`) to have a
  native read with proof True. Otherwise nothing is written.
- **Tested:** a pre-rule proposer is refused; an inward edge left on an unproven frame is refused; an unread edge is
  refused.
- **In practice:** 021320's scheduled evidence step on the old snapshot **was refused by it**. It then ran on the
  refreshed snapshot (final-17).

**Refreshed snapshot:** `code-snapshot-dfbb4dd-98e52781`, manifest `6bc89834…`. The archiver's lane list now includes
the importer and its tests.

## Bytes

| File | Bytes | sha256 of the blob git stores |
|---|---|---|
| `agent/human_demos.py` | 41,452 | LF `bf8697d1ec7264981dd8d71428c82b7519269e039f8d090ddb060473d9556404` |
| `tests/test_human_demos.py` | 46,886 | LF `5abcdaefb4899659a922ebb7d0aa2a95f551a10ff99f4ef0b0ffb26511d40271` |
| `agent/human_intake.py` | 81,204 | LF `6d43048d9553e7de1c070fb117aca381c0faa4a1fedb28e3e7dc0e49a8b8714d` |
| `data/human/sessions/intake_session.py` | 39,760 | LF `a7dc71c43be506dc192d338a760fea3f037e4df5e7d0acdebf1f0a16b9226b54` |
| `tests/test_human_intake.py` | 58,631 | LF `c63e154bab9ce85047695dd954b647f8f8fdc7e211f6cf86895302f6618b7a84` |
| `data/human/sessions/archive_code_snapshot.py` | 5,238 | LF `5016dd9b14aec3491633d30e64230d8535b9ee8794f50cd8be3bd442a5969730` |
| `docs/lanes/human-admission.md` (importer, E1 and wheel entries) | 91,055 | LF `b546a5a3200003bd9b21a745879190ef3a55892c25a0265031dde45bb15bad64` |
| `code-snapshot-dfbb4dd-98e52781/manifest.json` | | `6bc898348290afc9e359229bfc0eb60fefd687cc2308524989a94793dd3f5947` |

**Scratchpad (`…/scratchpad/edge/`):**

| File | sha256 |
|---|---|
| `proof_import.py` | `f1782fe4…` |
| `audit_under.py` | `e4dcdf86…` |
| `audit-old.json` | `d7d59bcd…` |
| `audit-new.json` | `02eda92d…` |

The `proof2/*.result.json` files and the `rehearsal2/` folder are there too.

**Next, after admission-review:**
- assemble 025230 and 232304 (train), with step tables and tally rows;
- 021320 waits for its independent review.

No commits, no Linear, nothing on the Mac.
