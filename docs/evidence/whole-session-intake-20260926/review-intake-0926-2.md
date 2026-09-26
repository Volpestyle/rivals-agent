**Verdict: approve the B1/F2 delta. B1 is closed; F2 is closed. No remaining blocking or fix-forward finding in this delta.**

Independent reviewer: admission-review (Codex), 2026-09-26. Re-review of `admission-owner-final-27.md`, SHA256 `9845788a9f5060c05c583ad42657541641d287c5d58fe3d8bd5b6b234cd15536`. This supplements `review-intake-0926.md` (`af85359c`); its other accepted checks and the unchanged session verdicts stand. Only B1/F2 were reconsidered.

## B1 — closed

`human_demos.read_splits` calls `_check_excluded` before returning placements; `human_intake.check_registry` reaches that same check after its denylist validation. Calibration/evaluation rows must be disjoint from split rows and from other excluded rows by session ID, resolved media path and supplied `expected_media_sha256`. Neither excluded category can carry `split` or `sealed`; evaluation `kind` cannot name train, val, test or gate2. The reader returns split rows only.

I reran the original **byte-identical** `audit.py` from a new scratch directory so the prior review evidence stays unchanged. Its formerly accepted calibration-as-train reproduction now refuses:

> calibration_sessions row 20260923T204707-487Z-45572-2 shares its session id with a split row or another excluded row

The current registry still validates: **16 split placements, 3 calibration entries, 8 evaluation entries**. No excluded entry resolves to a placement. Fifty independent synthetic checks across both public registry readers covered valid controls, ID/path/hash collisions, relative path normalization, within-list duplicates, cross-list collisions, forbidden split/sealed fields, and all four split-named evaluation kinds. Every expected refusal and valid control passed.

## F2 — closed

`load_dataset_relocated` now checks `hd.SEALED_SPLITS` against both the artifact header and the resolved registry placement. It also requires an exact Boolean sealed flag consistent with that placement, before reading the body.

The original **byte-identical** `relocation_repro.py` now returns **`SealedError: gate2 artifact is sealed`**, replacing the prior payload checksum error. Additional guarded-stream checks make any second `readline()` fail: each of the four cases below refused after exactly one header read, without reading the body.

| Header / access | Refusal |
|---|---|
| gate2, sealed=False, ordinary access | gate2 artifact is sealed |
| train, sealed=False, registry placement gate2 | gate2 session is sealed |
| gate2, sealed=False, unseal=True | sealed header mismatch |
| gate2, sealed flag absent, unseal=True | sealed header mismatch |

The positive relocated-load regression also passed in the targeted suite.

## Validation and scope

- **15 tests passed, 159 deselected:** isolated admission-review Python, `-B -m pytest -q -p no:cacheprovider tests/test_human_demos.py tests/test_human_intake.py -k "excluded or calibration_and_evaluation or relocated"`. No corpus tests requested.
- Original audit and relocation scripts were copied byte-for-byte to `review-intake-0926-2-work/` and executed there. Prior scripts, reports and outputs were preserved. `delta_checks.py` adds the 50 registry checks and four body-read guards.
- All four code/test hashes match final-27's LF pins and were checked again before writing this report. No decode, media content inspection, checkout/session edit, commit, Linear write or Mac action.
- The owner's existing `code-snapshot-3936f94-4c9638d1` predates these fixes. This receipt approves the current code bytes below; it does not assert that the old snapshot contains them. Existing session verdicts stand for their unchanged bytes. Tally regeneration at landing and the separate late-take evidence review remain outside this delta.

## Reviewed pins

| Path | LF SHA256 |
|---|---|
| `agent/human_demos.py` | `614042e5cb8eb45164a4b7d3b49249180048dd9c530ae14c540484fb8e72dd38` |
| `agent/human_intake.py` | `8ecf85e48181568f9af9fd81de0227b0c0e54cb3ad613a6a870d19dbdecf53e0` |
| `tests/test_human_demos.py` | `d952b428ab1b9574fe8d6db8ab5687ff829ff635f2beea8937ce471695d85c4b` |
| `tests/test_human_intake.py` | `fc81c28e77684c0a15987f415f5821730fb240270d8124c126340619baaa1c96` |

Evidence hashes (raw SHA256):

| Scratch file | SHA256 |
|---|---|
| `review-intake-0926-2-work/audit.py` | `ae7d2febd49cdd85d4b2abbceca457ae6d7e8ba54f5dbff6da4e6676cab62553` |
| `review-intake-0926-2-work/audit.json` | `c16b1bd00ee16594e1cc7580cf4e21e3478b7d86a9a11d543562cf314c292b6d` |
| `review-intake-0926-2-work/audit-run.txt` | `1d345429642158cc73efd4bae384864ecaf3a7df78ec98a0a2c960224f167ffb` |
| `review-intake-0926-2-work/relocation_repro.py` | `0d4b61c05db9f68397547b88cd26ddd30752c9b52ce4272ccb924fc7c885f4d7` |
| `review-intake-0926-2-work/relocation-run.txt` | `c3149561b0207e9647916debb7298b0540562d0ea4b49a2607512c58bdc2b7da` |
| `review-intake-0926-2-work/delta_checks.py` | `70d37ff01e6a9e6a69e08da824e1797de87a57163d917e7ce2a66caae868b9f4` |
| `review-intake-0926-2-work/delta-checks.json` | `1bce44c1906755c4fad9b0502d62f85487663edbc3ef1077fea29d83ad7ca327` |
