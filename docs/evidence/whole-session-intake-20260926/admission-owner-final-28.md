# admission-owner final 28: the landing list for 212646 (val), 203745 (train) and 045729 (train)

This replaces final-24's list; final-24's per-session detail stands. All three sessions are admitted, with freeze checks
clean just before this list was written.
- **The tally,** regenerated from the final registry: normal, train **150.4168 counted min** (150.4078 trainable), **9
  sessions**, 29.58 of 180 to go. Normal, val **15.5846** (1 session), beside the headline.
- **The fit reader** (`steps.load_cohort` with the patch-equivalence file) loads all **10 step tables** as one cohort:
  9 train, 1 val.

## Sessions

| Session | Split | Counted min | Runs | Freeze (`artifact-hashes.json`) | Assembled from | Independent record | Hand-back |
|---|---|---|---|---|---|---|---|
| `20260925T212646-322Z-49728-6` | val | 15.5846 | 6 | `415b1b8b…` | `code-snapshot-b7d4592` | `7c47d6af…` | final-21, final-22 |
| `20260925T203745-207Z-49728-2` | train | 45.9781 | 6 | `e9860472…` | `code-snapshot-3936f94-4c9638d1` | `916ea4bf…` | final-23, final-24 |
| `20260926T045729-166Z-79780-1` | train | 10.2599 | 3 | `596883a2…` | `code-snapshot-3936f94-4c9638d1` | `e80c10ca…` | final-26 (below) |

**045729** was assembled on 2026-09-26 at 03:42. It was reviewed in review-session-045729.md (`903bc324…`), which
matches the owner verdicts on all 15 segments.
- **Accepted:** seg-002, seg-007 and seg-012 (87.967 / 464.367 / 63.258 s).
- **Step table:** 18,603 rows, 18,465 accepted and gap-free.
- **Import:** 75,321 frames; no `unknown_composition`.
- **Header:** patch `1.1.3892207/build25501035`, settings `a8dea3ba…`, sitting 2026-09-25-late.
- **Motor source:** its own `MOTOR_STATEMENTS["2026-09-25"]["sessions"]` entry (`3936f94`).
- **Intake steps** ran from `code-snapshot-3936f94`.

| 045729 file (all LF) | Bytes | sha256 |
|---|---|---|
| `20260926T045729-166Z-79780-1.steps.jsonl` | 12,620,530 | `92ba60cf62f413a87adf3cd8d8b04647c4d004b79c9f2f4bde7647b808baae38` |
| `artifact-hashes.json` | 4,859 | `596883a2bbe7e81f25c694684ea6a6ae1eff62f85fef982def4b10cf4febad5a` |
| `settings.json` | 5,075 | `d2243ac14c55515ca10dd8d121673f8a9f220952c6959672ef9faec2c4b1c7aa` |
| `review.json` | 15,752 | `c32992e8816275ef152c21e4175d50218ef594c5fc992bfc5772a9ffc00075be` |
| `sampling.json` | 639 | `7d5e359b3e83c2e4201d5e46d7cc8b78e5ab516c296477594129e25716240966` |
| `minutes.json` | 941 | `bc100413d39fd4d1ec6affcb0c96e9b3b63c398c019fc390e8d790085f34bb5e` |
| `independent-review.verdicts.json` | 152,744 | `e80c10ca5bd747a6700e29e406c48ab32c5bf09d3d83e7a1e3a3509ef9d8353e` |
| `independent-review.md` | 11,416 | `903bc324de163f7bdb8ec011ef5387b70576f45d69a37c8f1d96e90d7c399114` |
| `recording-log.7ad63e5.md` | 11,179 | `a03fe99a5437a8b18c9f127dc6169ca97f1e8a503ebbea10e1985a1e55cc1b92` |
| `registry.26d55f3d1bba.json` | 20,304 | `26d55f3d1bba686eaea1af82e5e02fa6fc6b93ef57737c5c9fff168a24d8da71` |
| intake files | | as in final-26 |

**Files to land per session folder**, the same set as every admitted session:
- `artifact-hashes.json`, `candidates-pass1.json`, `independent-review.md`, `independent-review.verdicts.json`;
- `input-profile.json`, `minutes.json`, `motor-settings.json`, `owner-verdicts.json`, `provenance.json`;
- `recorder-verification.json`, `recording-log.<commit>.md`, `regime-timeline.json`, `registry.<hash>.json`;
- `review.json`, `sampling.json`, `segments-evidence.json`, `settings.json`, `slot-mapping.json`.

For 203745 also: `timed-practice.json`, `candidates-pass1.v1.json` and `segments-evidence.v1.json`.

The step tables, imports, HUD samples and review frames (and 203745's `review-frames.v1/`) stay out, pinned by each
freeze, as before.

## Code and tests: the reviewed final-27 bytes

These are approved in review-intake-0926-2.md (`c26426fc…`) at final-27's pins. They are **unchanged since**, except
`tally.py`, as noted.

| File | LF sha256 | Status |
|---|---|---|
| `agent/human_intake.py` (CRLF) | `8ecf85e48181568f9af9fd81de0227b0c0e54cb3ad613a6a870d19dbdecf53e0` | = final-27 |
| `agent/human_demos.py` (CRLF) | `614042e5cb8eb45164a4b7d3b49249180048dd9c530ae14c540484fb8e72dd38` | = final-27 |
| `data/human/sessions/intake_session.py` (CRLF) | `80830341b1d68f8263fb5dccba37cbddfacdc9f85cce9ed51f52092a66d8e3f5` | = final-27 |
| `data/human/sessions/assemble_session.py` (LF) | `a11fd5d1d87516b80f4b0e09545eb9631ef2ae91c1b81cdfe5ff39381cacb97c` | = final-27 |
| `data/human/sessions/tally.py` (CRLF) | `6cc97d6a717ecc3831a05de82658f4def42019382fe769ef1a23d3e98d1269d9` | **changed since the reviewed pin:** the session lists only (045729 moved from `pending` to `ADMITTED`) |
| `tests/test_human_intake.py` | `fc81c28e77684c0a15987f415f5821730fb240270d8124c126340619baaa1c96` | = final-27 |
| `tests/test_human_demos.py` (CRLF) | `d952b428ab1b9574fe8d6db8ab5687ff829ff635f2beea8937ce471695d85c4b` | = final-27 |
| `tests/test_gate2_split.py` (new) | `41a1898bb0389b9cba1789bb71a4d636fde006ac430e3e7236bf4425af93cca8` | = final-27 |
| `tests/test_human_intake_timed.py` (new) | `3fa13741e75f35d475657851fed5badbb75af42124618ddd01e39b2a4d924a78` | = final-27 |
| `tests/fixtures/intake_timed/` (new) | README LF `70790c2a…`; PNG raw `1857860c…`, `71a80b2f…` | unchanged |

**The late take's `MOTOR_STATEMENTS` entry rides in this landing.** `assemble_session.py` carries
`MOTOR_STATEMENTS["2026-09-25"]["sessions"]["20260926T035932-508Z-63684-14"]`, which quotes `83c05f1` and `7ad63e5` and
names the calibration.
- **Inert:** it is used only when that session's motor step or assembly runs, and it resolves for no other session.
- **Reviewed:** the lookup logic (`applies_to`, `sessions`) was reviewed. The entry's wording and evidence are the late
  take's own session review's.

## Data and docs

- **`data/human/session-splits.corpus.json`:** `26d55f3d1bba686eaea1af82e5e02fa6fc6b93ef57737c5c9fff168a24d8da71`
  (LF, unchanged since the review; B1 validates it). It holds:
  - 16 split rows, including the late take (train, noted as pending review) and the `gate2` pair;
  - 3 `calibration_sessions` rows;
  - 8 `evaluation_sessions` rows.
- **`data/human/sessions/tally.json`:** `1e53def57c1e8692c0891d678681f726789b68fd7ddf956757a2905e012398c7`, regenerated
  from that registry (N1).
- **`docs/evidence/corpus-tally.md`:** `24ff1282e770d23a199fc86a358b37107e357ab2ea6b8faf8ead68822b12c0ab`.
- **`docs/lanes/human-admission.md`:** LF `2e7a5353b65f369a5b4726b4654ff5c0fb271856db03feab1fb306f765000381`. This batch
  adds three sections and the 2026-09-26 additions.
- **Snapshot manifests:**

  | Snapshot | sha256 | Role |
  |---|---|---|
  | `code-snapshot-fbe6693` | `b5bdb3b3…` | 203745's timed, propose and evidence steps |
  | `code-snapshot-3936f94` | `da606ea9…` | 045729's intake steps |
  | `code-snapshot-3936f94-4c9638d1` | `bc5e786e…` | the 203745 and 045729 assemblies |

**Reviews to copy into the evidence folder** (suggested: `docs/evidence/whole-session-intake-20260926/`, beside
`…-20260925/`):

| File (handoff folder) | sha256 |
|---|---|
| `review-session-212646.md` | `fcc7197343571ce0a28916d26513dc6d4e5b4148860df0594496f8e0832d3012` |
| `review-session-212646.verdicts.json` | `7c47d6afac6c439298ff64ff755877ce2ebfccabef52021bdae84d12e34fb9bf` |
| `review-session-203745.md` | `a5cc09c2fc5bb52ed0eedf7ff1486aa6a208ab90be4568c73fddd1f0627f029a` |
| `review-session-203745.verdicts.json` | `916ea4bf20cba89b56c711e75b05c0d4c453e4e20c8dd9d0d8ab643146b4c74e` |
| `review-session-045729.md` | `903bc324de163f7bdb8ec011ef5387b70576f45d69a37c8f1d96e90d7c399114` |
| `review-session-045729.verdicts.json` | `e80c10ca5bd747a6700e29e406c48ab32c5bf09d3d83e7a1e3a3509ef9d8353e` |
| `review-intake-0926.md` (+ `review-intake-0926-work/`) | `af85359c898730380761ae960c17a2af882f68b22c460d3cdf16e0f00025b03b` |
| `review-intake-0926-2.md` (+ `review-intake-0926-2-work/`) | `c26426fcd75d6d2fa63ac549b13de69bacf4d16fe98a0431829d5d541f8058a3` |
| my hand-backs `admission-owner-final-21` … `-28`, `arrivals-0925.md`, `arrivals-0925-late.md` | as written |

## Not in this landing

- **The late take (22:59)** lands after its own session review. It keeps these:
  - its session folder and `code-snapshot-83c05f1` (`070a2882…`);
  - the main-account calibration folder `data/human/calibration/20260926T060921-977Z-60612-1/`.

  It also has a new finding: a ~9 s Timed Practice round at about 491–500 s inside a gameplay span. That is the next
  step, not this landing.
- **Other lanes' work in the tree:**
  - `docs/lanes/inverse-dynamics.md` and `docs/lanes/idm-gate2-anchors.md`;
  - `perception/cooldown_anchors.py`, `killfeed.py`, `match_timer.py`, `match_timer_glyphs.json`, `replay_cuts.py`;
  - `tests/test_cooldown_anchors.py`, `test_gate2_readers.py`, `test_replay_cuts.py` and `tests/fixtures/gate2_readers/`.

No commits, no Linear, nothing on the Mac.

## Addendum (2026-09-26 04:57): 1 fps native banner sweep, clean on all three sessions

As the lead asked, each original was swept at 1 fps before landing.
- **Method** (`…/arrivals-0925/sweep/banner_sweep.py`, `89afa2dd…`):
  - CPU decode, 4 threads, below-normal priority, about 131 MB per ffmpeg; it checks every 300 frames that the game and
    OBS are not running.
  - Only the top-left banner crop is kept (the `timed` step's `BANNER_BOX`), matched against the same pinned references
    with the same rule.
  - Every TIMED PRACTICE frame is located against the session's accepted segments in `review.json`.

| Session | Frames (1 fps) | PRACTICE RANGE | TIMED PRACTICE | Neither | Max TIMED score | TIMED in accepted | Result |
|---|---|---|---|---|---|---|---|
| 212646 (val) | 953 | 950 | 0 | 3 | 0.4714 | 0 | `sweep-…212646….json` `2ad41593…` |
| 203745 (train) | 2,879 | 2,782 | 91 | 6 | 0.9996 | **0** | `sweep-…203745….json` `dd98b67a…` |
| 045729 (train) | 628 | 623 | 0 | 5 | 0.4704 | 0 | `sweep-…045729….json` `38a8be40…` |

- **203745's 91 TIMED PRACTICE frames** are one contiguous run, 2,229.08–2,319.08 s: the known round, entirely inside its
  `timed_practice` cut (2,228.59–2,319.87 s).
- **Nothing unexpected:** no other round in any of the three, and no TIMED PRACTICE frame inside accepted footage.
- **The "neither" frames** (3–6 per session) are hero select, focus transitions and death cards, as in the earlier
  review-frame check.
- **The sweep's resolution:** a round shorter than about 1 s could fall between samples. The shortest seen so far (the
  late take's, aborted) lasted 8.7 s.

The seven previously admitted sessions are next, as a report-only follow-up.
