LAND

Independent read-only review, VUH-1353, 2026-09-26. Reviewed the uncommitted delta against HEAD cf0394556506d674ee096d47e93bd9f49436c941. No blocking findings.

- Verified hand-back LF SHA-256 `81d8ec39f0a9fe8306b46985b2f4d0b9cb3d02d4775975e3da971b4a80d03339`.
- Registry changes are exactly six replaced lines: `kind`, `session_group`, and `note` in evaluation rows `20260926T021321-378Z-63684-9` and `20260926T034805-307Z-63684-13`. Both kinds and groups now say `reader_validation`. Their existing `role` fields, identity/path fields and key order are unchanged; all other rows and fields are unchanged. The matching session-group update is explicitly included in the hand-back.
- Executed current `human_intake.check_registry` with independently hash-pinned denylist v2 `439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20`: passes, 20 split rows (12 train, 1 val, 4 gate2, 3 test). Each target occurs only in `evaluation_sessions`, is absent from the returned split map, and has no denylist match by the registry identity/path/hash fields. Neither is sealed or assigned another registry purpose.
- `tally.json` differs from HEAD only by substitution of `registry.sha256`, verified both structurally and byte-for-byte after LF normalization. Recomputed the pure tally from its saved rows with v2: train **180.56902055553334** minutes (180.57), val **15.58458271005** (15.58), with every recomputed field equal. Both targets remain `not_range`, split null, admitted/trainable minutes null. `docs/evidence/corpus-tally.md` is unchanged. No corpus/media regeneration was run for this metadata-only delta; the prior accepted default-build check is reused.
- Searched `.py`, `.md`, and `.json` references under docs, agent, policy, scripts, tests and data, including ignored files, by both full IDs and recording timestamps. No recorded prior training or reader use was found. Historical frozen registry copies and synthetic review fixtures keep both targets in `evaluation_sessions`, with no split; these copies do not admit their footage. The original source list in `docs/lanes/inverse-dynamics.md:430` explicitly held both in reserve; its new addendum at line 591 onward authorizes this one re-validation after registration. The older inventory (`docs/evidence/whole-session-intake-20260926/arrivals-0925-late.md:103`) records only metadata/input-log inspection of 22-48-05 and explicitly no frames, consistent with the new disclosure. It does not establish any prior visual/model use.

Scope limits: absence of prior use is supported by the repository records and reference search, not proof about unrecorded activity outside this checkout. No media bytes, logger folders or frames were opened, and media identity hashes were not recomputed. The historical grouped recording-log row still describes these sources as match_dev; the explicit dated reclassification in the registry and lane addendum supersedes it. Frozen records were left untouched.

Reviewed LF SHA-256 pins:

| File | SHA-256 |
|---|---|
| data/human/session-splits.corpus.json | e8a1d0606bfc62fe304e73c78d94f4f62e90d9ef6468a09c486a8f5218ce7e29 |
| data/human/sessions/tally.json | e94e401d38f0323b68102c6ebf2e80ee772a66c6e4eee57570fc8a0dfdc323e3 |
| docs/evidence/corpus-tally.md | 8b7dde1a15a4d8a5493efcbd9dbb652b10558e638f278a303fb3ea76b1055c32 |

Reproduction evidence: adjacent `review-reader-validation-work/audit.py`, `audit.json`, `check_references.py`, and `references.txt`. Both audit processes completed successfully, sequentially, with an enforced Windows Job process-memory limit of 2 GiB. Hashing was chunked; bounded text reads were limited to metadata/source files. No repository edits or commits; only this report and scratch audit artifacts were written.
