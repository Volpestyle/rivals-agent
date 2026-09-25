# admission-owner final 20: 021320 admitted; the tally is 94.1789 counted minutes; the landing list

## 021320 admitted (train, 34.52 counted min)

**Assembly.** `20260925T021320-371Z-7804-1` was assembled from `code-snapshot-b7d4592`, with the independent record
`6acb158f…` (equal to the owner verdicts on all 19 segments; the f760 edge is valid, with no hero-drawn condition).
- **Freeze:** checks clean; 20 folder files, 9 external.
- **Import:** 263,435 decoded = referenced frames; no `unknown_composition`.

**What it holds.**
- **Accepted:** five segments (361.94 / 850.23 / 127.57 / 451.73 / 279.53 s); **34.5164 counted min** (5 runs).
- **Trainable:** 34.5144 min.
- **Step table:** 65,702 rows, 62,126 accepted and gap-free.
- **Header:** patch `1.1.3892207/build25501035`, settings `a8dea3ba…`, sitting 2026-09-24-late-evening.

| File | Bytes | sha256 |
|---|---|---|
| `20260925T021320-371Z-7804-1.steps.jsonl` | 44,677,348 | `841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537` |
| `artifact-hashes.json` | 4,823 | `16fabb73285dde1c0b00acfd57e68fbcf18e8c9e13c2a25787bfb21b81fecf43` |
| `review.json` | 16,403 | `b7767864174368cf88fb9f4692c0996688e266d9d677083009b5bed66956c187` |
| `settings.json` | 5,063 | `cdf47dfd00b88c37434609029c1a0eac011fbada1b35987829cc91c15ebdc9e1` |
| `imported-demo.jsonl` | 135,813,088 | `0a584b1a24464b5f40c43d6f64fe0dfee6c58bb7f707d97a0e9d76cd796c31c1` |
| `sampling.json` | 637 | `28de2b71de87b2131c6f9d46a63baebacad20b0a4540906f3bc1357291901385` |
| `minutes.json` | 990 | `9c5bd28a4801f85f5d2ff29820f171a8fdbc165bc09a003130f2c335b9491470` |
| `recording-log.dfbb4dd.md` | 7,747 | `25c9f622155726df96d5ab33bd021288630a74656b6a18d3dbf9748d41f4b799` |
| `registry.f36e9e3b5650.json` | 8,492 | `f36e9e3b565041cbd719d3d4c6b80033d66a685a599f3b6607e67bab3ee574fb` |
| `independent-review.verdicts.json` | 112,943 | `6acb158f802786a0414554ade8547d6b3a0377c41a553383fc2fc71427cf63b5` |
| `independent-review.md` | 6,222 | `03256d2110e98b7c9b89877b480b4c02d4f1618ac04a7cdca0257dc663047272` |
| `segments-evidence.json` | 136,712 | `75e34751156ff813cfcbf69613eda598433c02d387ea0f0ac5feca49ddcdcf34` |
| `owner-verdicts.json` | 51,179 | `e492b2c443e7a8e94d557353fb33b03126b57fdd41323d980c4aeae4f1ea6bd4` |
| `motor-settings.json` | 5,799 | `dbf5245551ee4af7a7d206ce66f7dfb30648cd07280c828bb4f69f13be550fe3` |
| `provenance.json` | 48,972 | `9caa9ef22344ae4494d26c31bd1a9235f3c545491af9eda690b94718f954be94` |
| `recorder-verification.json` | 1,212 | `bd0e65cd4ffac8d8c2c942d2f7f44ab4ec0a9840b2ff85ae115859e5393bc986` |
| `input-profile.json` | 1,802 | `b52b17d180226f7a96ebefe18fbd95c7bcc0f0ab2dc9643edb6b1a7f78590033` |
| `slot-mapping.json` | 259 | `1a4677df7972e94e94ae500d6e15a617655213f54fd52f33d5bd0d3f5ce3587d` |
| `hud-scan-samples.jsonl` | 8,322,129 | `461f8ac174816770ca4b4942601530ba686d57fae5e9ed799917d88c98c551a1` |
| `regime-timeline.json` | 96,496 | `058265e2362162d1f3fd5aeca0b38484530f68f97d6f1690923e43f6b8577c01` |
| `candidates-pass1.json` | 4,765 | `7c921d594ae7491192660a3148cc31830ba99fcaa1a2dedda775093cc1b21daa` |

## The tally: **94.1789 counted minutes**

- **Normal regime, train:** **94.17888512 admitted min**, 94.17388795 trainable, across **7 sessions**. That leaves
  85.8211 of the 180 target.
- **Per session:** 051828 6.97, 171533 2.57, 200129 26.62, 205528 11.07, 232304 8.77, 025230 3.66, 021320 34.52.
- **The fit's reader** (`steps.load_cohort` with the patch-equivalence file) loads all seven tables as one cohort:
  **169,513 accepted rows**.

| File | Bytes | sha256 |
|---|---|---|
| `data/human/sessions/tally.json` | | `1e2f8c62eb3d8d1912fe31238c600077575edb4038d1e1fa2c70972e396c253b` |
| `docs/evidence/corpus-tally.md` | | `4ea082a3e6463d9b26f275074c28c18caf212331c469cb98a97c2b8480d4b8bf` |
| `data/human/sessions/tally.py` | 6,877 | LF `7bb1a8b419d38887b3c01eb83a2e9bdd0ef3ae9b1f8d60d01d40c21014afe386` |

`tally.py` now:
- names the three new admitted sessions and the 030045 calibration take;
- takes each admitted row's date from the recording, via `chicago_date`, instead of hard-coding 2026-09-23.

## Also done

- **`docs/recording-log.md`:** the intake status of the four 2026-09-24 rows is filled in (admitted with minutes and
  freeze; 030045's per-band result). 8,273 B LF, sha256 `facda8e1f00625927ffdf77b795c55408c438c4cba8c0ca99f4ada15fa272556`.
  I edited it only after all three assemblies, which require the log to equal its last commit.
- **The lane doc:** a new 2026-09-25 section covers the admissions, N1–N3, and the slot-location correction (025230's
  duplicated timestamp is 82 ms after focus gain, inside rejected seg-000, not "before focus"). LF sha256
  `8cd1d1a3b786dd594fe439f8bc46da437fa9559432f673c77c6b792a6c4ccd86`.
- **Tests:** full stdlib suite **1972 passed, 71 skipped**; importer and intake 155 passed; the perception edge test
  2 passed.

## Landing list (every file is uncommitted in the shared tree; `data/` is gitignored and needs `git add -f`)

**Code and tests:**

| File | LF sha256 |
|---|---|
| `agent/human_demos.py` | `48aa9d0e6bf21bbc72e7247ee3eb696fdc99933d04b0913aee37464826307d3b` |
| `tests/test_human_demos.py` | `498bdfe02c2acce3352ea37767debbe659740a2dbb6ef5c5f0acd2652f847031` |
| `agent/human_intake.py` | `6d43048d9553e7de1c070fb117aca381c0faa4a1fedb28e3e7dc0e49a8b8714d` |
| `data/human/sessions/intake_session.py` | `38389b9d223b282b1068375146fc30481f50101bfe1b711786ad0db637b7a137` |
| `data/human/sessions/tally.py` | `7bb1a8b419d38887b3c01eb83a2e9bdd0ef3ae9b1f8d60d01d40c21014afe386` |

- **`data/human/sessions/assemble_session.py`:** LF `1edf1302…` plus the motor-statement lookup, unchanged since
  intake-motor-2 except the call site.
- **`data/human/sessions/archive_code_snapshot.py`:** LF `5016dd9b…`.
- **`tests/test_human_intake.py`:** the latest bytes, via `git diff`.
- **New files:** `tests/test_human_intake_edges.py` and `tests/fixtures/intake_edge/` (three JPEGs and a README; hashes
  in intake-edge-rule.md).

**Data:**
- **`data/human/session-splits.corpus.json`:** `f36e9e3b…`.
- **The three session folders**, the same file set as the admitted sessions:
  - `artifact-hashes.json`, `candidates-pass1.json`, `independent-review.md`, `independent-review.verdicts.json`,
    `input-profile.json`, `minutes.json`, `motor-settings.json`, `provenance.json`, `recorder-verification.json`,
    `recording-log.dfbb4dd.md`, `regime-timeline.json`, `registry.f36e9e3b5650.json`, `review.json`, `sampling.json`,
    `segments-evidence.json`, `settings.json`, `slot-mapping.json`;
  - plus the pinned `.v1` files: 025230's `motor-settings.v1.json`; 232304's `motor-settings.v1.json`,
    `segments-evidence.v1.json` and `owner-verdicts.v1.json`.
  - As before, the step tables, imports, HUD samples and review frames stay out of git. Their hashes are in each freeze.
- **`data/human/calibration/20260925T030045-211Z-7804-3/`:** all files except `pairs.jsonl` (3.5 MB) and
  `rest-features.npz` (1.2 MB). Those two are pinned by the freeze and could stay out like the step tables; your call.
- **Snapshot manifests** pinned by the freezes and evidence:

  | Snapshot | `manifest.json` sha256 | Role |
  |---|---|---|
  | `code-snapshot-2ad0992` | `a17ecf84…` | earlier intake steps |
  | `code-snapshot-dfbb4dd-98e52781` | `6bc89834…` | 021320's evidence |
  | `code-snapshot-b7d4592` | `1927686c…` | the three assemblies |

  **`code-snapshot-dfbb4dd`** (the buggy slot check) is referenced by nothing: don't land it.

**Docs:** `docs/recording-log.md`, `docs/lanes/human-admission.md`, `data/human/sessions/tally.json`,
`docs/evidence/corpus-tally.md`.

**Not mine** (other lanes' uncommitted work in the tree): `docs/lanes/inverse-dynamics.md`, `policy/idm/train.py`,
`tests/test_idm_model.py`.

No commits, no Linear, nothing on the Mac.
