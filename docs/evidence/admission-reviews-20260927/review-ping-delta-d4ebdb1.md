# Independent admission-delta review: d4ebdb1

Verdict: LAND. Reviewer: fit-review (Codex), 2026-09-27. Scope: `intake_session.py --ping-delta` and its admission tests. Wrapper plumbing excluded under James's current review rule. No findings in the changed boundary.

## Preservation and coverage

The path is restricted to superseding evidence for -4/-5 and the exact hardcoded affected IDs: -4 seg-015/030/043; -5 seg-030. It authenticates the previous owner/evidence binding, requires those old segments to have been accepted, and checks raw-input and accepted-review hashes against the audit. The splice deep-copies all other segment JSON values without changing bounds, reasons, inspection text, edge descriptors, native/JPEG hashes or frame references. Replacements are intersections with the old affected bounds and must tile those bounds exactly; empty, missing, overlapping or gapped coverage refuses.

Metadata-only invocation on the real previous evidence and current proposals preserved every unrelated segment for both sessions. These are coarse splice checks, not newly emitted or accepted evidence. Actual previous owner/evidence/review bindings and every inherited JPEG hash were independently verified. No raw video or decoder was opened.

## Edge proof and acceptance

Existing outer bounds inherit their old edge descriptors and native reads. New internal edges use the ping-aware proposer's normal native refinement. The unchanged E1 check then requires a true native read at each emitted gameplay start and end-minus-one; inheriting a descriptor alone cannot satisfy it. Independent missing/false-proof controls refuse, and a valid true-proof control passes.

A full `step_evidence` synthetic run, with decoder and image operations stubbed, verified exact unaffected segment objects, copied JPEG pins, retained native-read records, clipped/tiled replacements, and preservation of the previous evidence file. It correctly retained a rejected `unsampled_edge` piece between a sampled gameplay edge and the UI cut. A separate false-edge experiment moved gameplay inward to the next proven frame and retained the unproven region as rejected, matching the existing conservative refinement rule. The inherited-JPEG hash guard refuses tampering before publication.

New child IDs are tied to their old parent and do not inherit old acceptance or inspection text. Their proposal remains unresolved/rejected and `seen` is cleared. Old verdict IDs therefore cannot automatically accept the new pieces. Independent changed-boundary verdicts and the ordinary assembly gates remain required.

## Verification and limits

`tests/test_intake_ping_delta.py` plus `tests/test_intake_match_mode.py`: 34 passed, four unchanged OpenCV image-fixture cases skipped in the private reviewer environment. The owner's 38-pass report is inherited evidence for those unchanged cases. Tested admission code matches d4ebdb1. This commit changes no frozen snapshot.

The full-step probes were synthetic and performed no decode or media inspection. This accepts the admission code, not replacement frame verdicts, assemblies or accepted-a1 receipts. The lead/admission owner retains the requested sequence: -6 completion, affected -4/-5 boundaries, then -7. Lead owns VUH-1353 acceptance/status reconciliation.
