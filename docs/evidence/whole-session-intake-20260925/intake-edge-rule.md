# intake-edge-rule: edges sit only on frames the live range guard proves; 232304 re-emitted (seg-002 opens on f310)

**Result.**
- The rule is coded in the proposer and the evidence step, and tested on the two real frames.
- 232304's segments were re-emitted under it, with v1 kept and superseded deliberately:
  - **only seg-002's opening moved**, from f308 to f310 (+16.7 ms), and seg-001 grew by the same two frames;
  - every other bound is byte-equal;
  - counted minutes are **8.77** (8.76569 → 8.76542).
- **232304 is not assembled.** Two things stop it:
  - the reviewer's re-check of this re-emission. The existing record `3cfeeace` has seg-002 at f308, and the assembly
    requires the verdict bounds to equal the evidence;
  - **the importer block in final-16**: 232304 has the duplicated composition time at 323.108 s, and
    `match_frames` refuses it.

## The rule and the code

**The rule.** A gameplay edge sits only on a native frame where both proofs hold:
- the intake scan's `hud_present`;
- the live range guard, `in_range` from the snapshot's `scripts/record.py` (the pad loop's own proof).

**`agent/human_intake.py`, `propose_segments`** (the native reads now carry that combined proof):
- **from a proven sample frame:** the edge moves outward over contiguous proven frames, as before. This is 232304's
  case: the walk from the sample stops at f309, so the edge lands on f310.
- **from an unproven sample frame:** the start moves inward to the first proven frame, and the end to the last one. This
  covers a sample landing on a spawn frame, or on an HP bar under the guard's half-health test.
- **no proven frame in the reads:** refused, with "no frame in the native reads passes the edge proof". The edge is never
  left on an unproven frame.

**`data/human/sessions/intake_session.py`:**
- **`edge_proof(img, scan, layout, mapping, guard)`** returns `hud_present`, `in_range` and `proof`, and `Ctx.range_guard()`
  loads the guard from the snapshot.
- **The evidence step** reads every edge bracket with both proofs. It reads up to `EDGE_INWARD_NS` (2 s) inward only when
  the sample frame fails.
- **It records** per-frame `hud_present`, `in_range` and `proof` in `native_edge_reads`, `in_range` on every review frame,
  and the rule, the inward window and the guard's sha256 in `parameters`.
- **`--supersedes REASON`** now also serves the evidence step: the old `segments-evidence.json` and `review-frames/` are
  kept as `.vN` and named in the new file's `supersedes`.

**No 1 s spawn settle**, as decided.

## 232304's re-emission

| | v1 (kept) | v2 (current) |
|---|---|---|
| `segments-evidence` | `.v1.json` `504e11fa…` | `939c3a5154cebb453bcb480b7089e4967f909f3c93b48b67d18bd9f07315d48d` |
| review frames | `review-frames.v1/` (68) | `review-frames/` (68) |
| `owner-verdicts` | `.v1.json` `452c4381…` | `a9ec8cb3c2e85c73ab91f0d0179d606bed6ddaf62fe1f2aadf230bbead391eab` (verdicts unchanged; seg-001/002 wording updated; names v1) |
| seg-001 end = seg-002 start | 360061738644248 (f308) | **360061755310914 (f310)** |
| the evidence's motor pointer | `14334d6b…` = `motor-settings.v1.json` | **`46e82b4f…` = the current `motor-settings.json`** |

- **The motor pointer the reviewer flagged now resolves** for 232304; v1 keeps its old pointer.
- **The edge reads:** f308 and f309 are `hud_present` True and `in_range` False; f310 onward are proven.
- **Coverage:** all four gameplay edges were read, none needed inward frames, and every review frame of seg-002 and
  seg-005 passes `in_range`.

## Tests

- **`tests/test_human_intake.py`: 60 passed, 1 skipped (the corpus test).**
  - New: outward stop at the first unproven frame, inward start, inward end, and refusal when no frame is proven.
- **`tests/test_human_intake_edges.py`, new, perception group (cv2): 2 passed.** Run in my scratch venv, so the shared
  environment isn't re-synced. Built from the frames themselves:
  - 720p JPEGs of f308, f309 and f310 (`tests/fixtures/intake_edge/`; `in_range` gives the same answer as on the native
    frames);
  - the repo's `in_range` gives False, False, True;
  - `edge_proof` with the scan's reading (HUD present on all three) gives proof False, False, True;
  - the proposer places the start on f310, and on f308 with the scan's reading alone.
- **Full stdlib suite: 1962 passed, 71 skipped.**

## Bytes

| File | Bytes (working tree) | sha256 of the blob git stores |
|---|---|---|
| `agent/human_intake.py` | 80,953 | LF `77140564e2a9faa1a0ae43f92080bbc3683d11a9cd4b3b6ef15ff94883a751bd` |
| `data/human/sessions/intake_session.py` | 38,682 | LF `3690834c72c83c410e3c5030defcc797b93c954d6faf87f1385036318879677` |
| `tests/test_human_intake.py` | 57,294 | LF `d51f82d13fba9a1dba42a0e566b12cc00f0e4641fd11ef0a04bf305dfbb1608d` |
| `tests/test_human_intake_edges.py` (new) | 2,737 | `b1c8d104bf053009a67665ec36f9d1135133039bd1379dd963882e3d5073bd16` |
| `tests/fixtures/intake_edge/README.md` (new) | 1,000 | `4dc3f2bb7e562d20cc168667bb0932835cf0decc2b9007f4c6927dccfc513e6a` |
| `tests/fixtures/intake_edge/232304-f308.jpg` (new, binary) | 246,850 | `57736dc957d3096b501a2641dd7a263717f2dab7a16cc5e41209852a09426d74` |
| `tests/fixtures/intake_edge/232304-f309.jpg` (new, binary) | 246,764 | `6c58e6a86ffa0a875cff0e7fb7a48393e7505ee3e37c82f00b8460244dfa74d7` |
| `tests/fixtures/intake_edge/232304-f310.jpg` (new, binary) | 257,447 | `88ac3d9b72367552cf51276b95a5c8882c370ef42cc313391d9860f9e8aa9409` |
| `docs/lanes/human-admission.md` (rule section appended) | 88,716 | LF `334e7b269a038ba91789e6eaccb0c2dc43620a144b248bb58831f1e99608c7df` |

- **Snapshot:** the `code-snapshot-2ad0992` archive still holds the pre-rule `human_intake.py`.
  - The re-emission is unaffected, because the rule's effect enters through the native reads, which the driver builds.
  - With a proven sample frame, the old and new proposers give the same placement: the outward walk is unchanged.
  - The next archive, after landing, carries the new proposer.
- **Also uncommitted, from earlier hand-backs:** `assemble_session.py`, the registry, and the motor-fix test and driver
  changes.

No commits, no Linear, nothing on the Mac.
