# Hand-back: the seven logged matches released to idm_train (James's call), for admission-review (admission-owner)

Written 2026-09-26 21:08 CDT, revised 21:12 CDT (PC clock) for 11-10-08 and the 22-48-05 flag (lead, 21:09), and again 21:31 CDT for review F1 (admission-review, LAND WITH FIXES, `e56381a0…`). **Frozen at the hashes below.** The version admission-review read is kept as `admission-release-idm-train-20260926.reviewed-dd73a5e0.md`. Uncommitted. The lead lands the commit. The full record is in
`docs/lanes/human-admission.md`, section "2026-09-26 (evening): the seven logged matches released to idm_train"; the
allocation idm-reader-validation-20260927T030000Z is recorded just above it.

**Credit:** James's call ("we should use those, I thought that's what I recorded them for"). idm-owner set the
retain-exposure and no-take-back conditions and designed the allocation.

## Files (LF sha256)

| Path | LF sha256 | Change |
|---|---|---|
| agent/human_demos.py | fe6b60d4216e1c12cb9b5c6181011accefcbe2739a246c6863a81bb315025160 | `IDM_TRAIN_SPLIT` added to `SPLITS`; unsealed |
| agent/human_intake.py | 4c3cea861183ba8014d2b750c107d24fb45e3a93728d3cc958d13fcaef594f6d | `assign_split(..., kind="match")` returns idm_train; F1: a new range group's targets and totals count train/val/test only |
| tests/test_gate2_split.py | 839f54f89a248297b26a3b5c02b0f36b499a3ee3d0291e3ba7723f96ba38ade0 | +2 tests: registry accepts idm_train, range_bc refuses it, the default for matches; F1 regression (admission-review's reproduction, plus gate2 and a large idm_train group) |
| data/human/session-splits.corpus.json | 5b3a592d0ba8b638614ef2d5db1886495d5b0763d18c91e51de4d1f89717a74c (was e8a1d060…) | the 7 rows move from evaluation_sessions into sessions, split idm_train; 11-10-08 joins 20-06-20's group as idm_train; 22-48-05 gains `training_pending`; evaluation_sessions is now empty. Diff: admission-release-idm-train-registry.diff |
| data/human/sessions/code-snapshot-107970b-3c8a3b7e/ (NEW, 118 files) | manifest d40333b555b7474f1e3b0121d515d898dc88fc80a426909f13e104d83d6123a3 | HEAD 107970b plus this batch's human_demos/human_intake, with F1. Replaces code-snapshot-107970b (manifest 6f3efef7…, pre-F1), which was never landed and is removed. The two differ only in agent/human_intake.py and the manifest |
| data/human/sessions/tally.py | f4bc8b92191958fba00a42a8ca9edc0d22bb302d6ed37ea229bc7a2f99be34c7 | DEFAULT_SNAPSHOT is code-snapshot-107970b-3c8a3b7e; reason text for the 7 rows and 11-10-08 |
| tests/test_tally_default.py | 44220ed0c96c63d6522a76fea222e3f221b2f3c9eed8042b217bccee636dee60 | expects idm_train; the tracked check follows DEFAULT_SNAPSHOT |
| data/human/sessions/tally.json | 8440ac3b10cbde433512f59d873a6a0f474dd7b4ea67f9dbde5122013f9bd132 | regenerated |
| docs/evidence/corpus-tally.md | 9c614b85540f0aaa2f200053ed58b4d53af623e9191eb82bafad447f47318701 | regenerated |
| docs/lanes/human-admission.md | 333b872bd49d1b6fea9a91e85401b7c6d1cecd836506fe68ea62eb3906e0918d | the allocation section and the release section |

## The seven live rows (plus 11-10-08, the replay paired with 20-06-20)

Each carries `expected_media_sha256`, `prior_exposure` (its history, plus "the reader results measured on this file
stand as historical and are not re-scored as fresh evidence"), `released_at` and James's quote as `split_basis`.
Each is its own `session_group`.

| Session | Video | Media sha256 |
|---|---|---|
| 20260926T005304-628Z-63684-4 | 19-53-04 | c2a280321a4fa39e9d0a6f990ccbd668e2aaf26b4a51f7c75ad0f79768e59dc1 |
| 20260926T010620-721Z-63684-5 | 20-06-20 | b286939f3a503a52bffa0c0a29873e8c71aac7d89dfb1b726f4818176e2efc87 |
| 20260926T012552-291Z-63684-6 | 20-25-52 | 9e96ac695acab0ec98e8ba8c4e753f7157481dbdd3c3f7a61913cd60cb0e824c |
| 20260926T013711-125Z-63684-7 | 20-37-11 | 2a82d16853bb3b4040552e0ceeaec23fdbdacc5312730401f313f18e0cb2813d |
| 20260926T015610-960Z-63684-8 | 20-56-10 | 9602ce5b47fc3e2bedc84eceb28af1fdd80ae8088e00c9e67068324cbf21b6af |
| 20260926T021321-378Z-63684-9 | 21-13-21 | 7ec600407c2267accba23983f8a093b35bfb4ab7b19c7f8d04414316433fe887 |
| 20260926T034805-307Z-63684-13 | 22-48-05 | cb9c7ad74873a3e802bae332aca7b19065162009b5bfd1c30439cbdbc71fdda2 |

- **Hashing:** bytes only, streamed in 4 MiB blocks at below-normal priority, with obs64 and Marvel* checked absent
  before and after. No frame was opened.
- **Unchanged:** both Gate 2 pairs, the test take, denylist v2 (`439c80df…`; v1 `57cfe01f…`) and the calibration rows.
- **Validation:** the registry validates with denylist v2: 28 split rows (train 12, idm_train 8, gate2 4, test 3, val 1).

## Tally check

- **Headline unchanged:** normal train 180.57 admitted / 180.56 trainable over 10 sessions; val 15.58.
- **Regenerated diff versus the previous tally.json/md:** only the seven rows and 11-10-08 (reason, group, split: null → idm_train; 11-10-08's group is 20-06-20's),
  the registry sha256 and the snapshot name change.
- **Why the snapshot changed:** e7f5045 refuses idm_train. The new default must be committed together with the registry.

## Review F1 fix (21:31 CDT)

- **The defect:** `assign_split` summed every group's minutes into the 70/15/15 denominator but only train/val/test into
  the per-split totals. An `idm_train` or `gate2` group could change the next range take's split. admission-review
  reproduced it: `{g1: train 10, sealed: test 2.1}` plus 3 min gives val; adding `match: idm_train 20` gave train.
- **The fix:** `have` comes from `SPLIT_TARGETS`, and `total = sum(have) + minutes`. The existing-group rule and the
  match default are unchanged.
- **The old code** in the pre-F1 snapshot still gives `val train` for admission-review's two calls. The new code gives
  val for all four cases in the regression.
- **Gate2 groups** are also excluded from the denominator now. They inflated it in the same way before idm_train existed.
- **Tally:** only the snapshot name in tally.json changes. corpus-tally.md is byte-identical, and the headline is still
  180.57 / 15.58.

## Tests (private uv environment, from this checkout)

- **Registry suite:** `pytest tests/test_sealed_denylist_v2.py test_human_demos test_human_intake test_gate2_split
  test_range_bc test_idm_targets test_tally_default` gives **470 passed, 5 skipped, 1 failed (after F1)**.
  - The one failure is `test_the_default_snapshot_is_committed…` at its final `git ls-files` guard:
    code-snapshot-107970b-3c8a3b7e is untracked until landed.
  - Its registry-validation assertion, splits == [gate2, idm_train, test, train, val], passed before that guard.
- **Corpus run:** `pytest --corpus tests/test_tally_default.py` gives **1 passed (byte-for-byte tally reproduction)**
  and the same 1 expected failure.
- **Expected after landing:** both pass. Please re-run after the commit.

## Limitations and open items

- `idm_targets.FIT_SPLITS` does not name idm_train yet. It is idm-owner's, and idm_train is inert until the reviewed
  match target path exists.
- **22-48-05** is the main account. It stays idm_train, flagged `training_pending`: it needs its own motor statement,
  identity and calibration before it trains. The lead is asking James for the motor statement.
- **11-10-08** (20260926T161008-331Z-116800-2), the Heart of Heaven replay of 20-06-20, is released to idm_train, as the
  lead confirmed at 21:09 CDT.
  - It is in 20-06-20's session_group, as the replay-of-self pair for true-input replay-transfer training.
  - Its labels come only from the live half. Its viewer inputs are never a target.
  - Its pinned media hash is carried over unchanged, `4c74f388be47e44c53002005edb548cd41aa7308ecf50ac39a34625862817e7e`.
    It was not re-hashed; the file is unchanged since registration (4,555,570,015 B, mtime 11:22).
- **Allocation idm-reader-validation-20260927T030000Z** is recorded, with V-C and V-Q open. No logger session started
  at or after 20260926T233007 as of 21:08 CDT.

**Review asked:** admission-review, read-only, of the code delta, the registry diff and the tally.
