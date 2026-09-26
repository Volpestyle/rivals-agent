# admission-owner final 24: 203745 admitted; the tally is 140.16 train min; the first landing list

## 203745 admitted (train, 45.98 counted min)

**Assembly.** `20260925T203745-207Z-49728-2` was assembled on 2026-09-26 at 02:56 from
**`code-snapshot-3936f94-4c9638d1`** (manifest `bc5e786e…`: the timed cut with F1, the `gate2` importer).
- **Independent record:** `916ea4bf…` (review-session-203745.md `a5cc09c2…`), equal to the owner verdicts on all 20
  segments.
- **Freeze:** `check_freeze` is clean; 23 folder files, 9 external.
- **Superseded records pinned** alongside their successors: `candidates-pass1.v1.json`, `segments-evidence.v1.json`.
- **A first assembly run was stopped** at 01:07 under the lead's hold (the game restarted, with 1 GB free). Its four
  partial outputs were moved aside (scratch `aside-203745-0107/`), and the rerun's `settings.json` (`d8d3043e…`) and
  `review.json` (`0ff54499…`) have exactly the hashes of those copies.

**What it holds.**
- **Accepted:** six segments (810.567 / 650.992 / 180.592 / 429.392 / 133.083 / 554.058 s); **45.9781 counted min**
  (6 runs).
- **Trainable:** 45.9756 min.
- **Step table:** 85,861 rows, 82,756 accepted and gap-free.
- **Header:** `split: train`, patch `1.1.3892207/build25501035`, settings `a8dea3ba…`, sitting 2026-09-25-afternoon.
- **Import:** 345,522 decoded = referenced frames; 1 unwritten tail packet; no `unknown_composition`.
- **The motor statement** is the date-level 2026-09-25 line (`fbe6693`), which `applies_to` names this session.

**The review's fix-forwards.**
- **F1 (fixed before assembly):** `timed_practice_span` now refuses a range→timed→range flicker in an end bracket. The
  reviewer's reproduction is a regression test, and 203745's pinned reads give the same cut.
- **F2 (narrative):** the 1,477.9 s death shows SPECTATING (f177379–f177415) before the black fade. My final-23 said no
  card. It is corrected in the lane doc; the pinned owner verdicts are unchanged.

| File (`data/human/sessions/20260925T203745-207Z-49728-2/`, all LF) | sha256 |
|---|---|
| `20260925T203745-207Z-49728-2.steps.jsonl` | (in the freeze) |
| `artifact-hashes.json` | `e9860472efd7e0f1cc48544e26d33629de18509e4437fc84f60e379b1ed10673` |
| `settings.json` | `d8d3043e712cdf5e30d5a676217e9f071800084176b7bfe7e94c7bf8415347ca` |
| `review.json` | `0ff544994d5b1ad5a89bf18ba58379a6a817aa44962e1107b9286296ef75034f` |
| `sampling.json` | `3e65d8f52313abab7eff8c1f4dde62cc735cd8ac63f3b76ac596cf9c3a5f6fae` |
| `minutes.json` | `980b0ff788c7a771c7b00eef097df83f2078165f51143aaa3a92dc2de8e42412` |
| `independent-review.verdicts.json` | `916ea4bf20cba89b56c711e75b05c0d4c453e4e20c8dd9d0d8ab643146b4c74e` |
| `independent-review.md` | `a5cc09c2fc5bb52ed0eedf7ff1486aa6a208ab90be4568c73fddd1f0627f029a` |
| `recording-log.3936f94.md`, `registry.c6bc9fa4292a.json` | pinned in the freeze |
| intake files | as in final-23 (`segments-evidence.json` v2 `b730d89a…`, `owner-verdicts.json` `0e1144bf…`, `timed-practice.json` `2df5ebaf…`) |

## The tally: 140.16 counted minutes

- **Normal, train:** **140.1569 admitted** (140.1494 trainable), **8 sessions**; 39.84 of 180 to go.
- **Normal, val:** 15.5846 (212646), beside the headline.
- **The fit's reader** (`steps.load_cohort` with the patch-equivalence file) loads all 9 step tables as one cohort: 8
  train, 1 val. A train-only fit must pass `splits=("train",)`.
- **Other rows:** the late take (22:59) is `held`; the 23:57 take is `pending` (review-ready, final-26). The gate2 pair and
  the eight evaluation-only matches are `not_range`. Four logger folders without video are `pending`.

## First landing list

Everything below is uncommitted in the shared tree. `data/` is gitignored and needs `git add -f`, as before. LF sha256
is given for text files; the CRLF files are as the tree holds them.

**For admission-review's delta review before landing** (lead: `gate2` and F1). These files also carry the second
landing's code, so the delta review must cover it too, or the first landing waits:
- the `settings_change` cut;
- the per-session `MOTOR_STATEMENTS` (`applies_to`, `sessions`), used by the late take and the 23:57 take.

| File | LF sha256 | What changed this batch |
|---|---|---|
| `agent/human_intake.py` (CRLF) | `e753e6ec1aedf87c636fa7ab22479626d7c9964fe12ebabd4ec531cdc38c8a2a` | `timed_practice_span` (+F1), the `timed_practice` cut, `settings_change_span` and the `settings_change` cut, `CUT_ORDER` |
| `agent/human_demos.py` (CRLF) | `8c71f6ae1857b581a0599c401dd2f57f25f1d65d6f0f0978938ff0662517e206` | `SEALED_SPLITS = ("test", "gate2")` in validation, placement, the training refusal and headers |
| `data/human/sessions/intake_session.py` (CRLF) | `80830341b1d68f8263fb5dccba37cbddfacdc9f85cce9ed51f52092a66d8e3f5` | the `timed` step (banner reader, pinned references), the `settings` step, `propose --supersedes`, the sealed-split refusal |
| `data/human/sessions/assemble_session.py` (LF) | `161ee5425dc5bbbf80b355e4da87145ad1cf80719ee022d1830ff4f9106eb6dd` | `MOTOR_STATEMENTS["2026-09-25"]` (`fbe6693`; `applies_to`; `sessions` for the late take `83c05f1` and 23:57 `3936f94`), per-session lookup in `motor_statement` |
| `data/human/sessions/tally.py` (CRLF) | `d6f979a25670af22c6d2c313b2c2a1936619d71e95a9c53ea0bee321a62b1969` | 212646 and 203745 admitted; the 09-25/26 rows |
| `tests/test_human_intake.py` | `98133b824283620178638ba5fae80247f71ce677316bc2460ab8ae3a96813a9c` | timed cut and span (+F1), settings change, per-session motor statements |
| `tests/test_human_demos.py` (CRLF) | `01e9fdcde8de20d85298aa6bbaee7a1d37ff5373f7892c44adc06014d48c19a3` | `test_gate2_is_sealed_like_test` |
| `tests/test_human_intake_timed.py` (new) | `3fa13741e75f35d475657851fed5badbb75af42124618ddd01e39b2a4d924a78` | banner reader (perception group) |
| `tests/test_gate2_split.py` (new) | `41a1898bb0389b9cba1789bb71a4d636fde006ac430e3e7236bf4425af93cca8` | both fit readers refuse `gate2` |
| `tests/fixtures/intake_timed/` (new) | README LF `70790c2a…`; PNG raw `1857860c…`, `71a80b2f…` | banner references |

- **Tests:** intake, timed, edges, importer and gate2: **166 passed, 3 skipped**.
- **The whole repo** (my private environment, before F1 and `gate2`): **3,021 passed, 169 skipped**. The affected suites
  plus range_bc and idm_targets after `gate2`: **316 passed, 4 skipped**.

**Data:**
- `data/human/session-splits.corpus.json`: `ea12dd296416d972de8695619e66661aebbf92b64262f7b15ee838e7bd008b51` (LF). It
  holds:
  - 13 split rows, the `gate2` pair among them;
  - `calibration_sessions`: 030045, plus the main-account turn take `20260926T060921-977Z-60612-1`;
  - `evaluation_sessions`: the eight matches, as `reader_validation`, `reader_development` or `match_dev`.
- `data/human/sessions/tally.json`: `6544941c…`; `docs/evidence/corpus-tally.md`: `b3b98acd…`.
- **Session folders**, the same file set as the admitted sessions (step tables, imports, HUD samples and review frames
  stay out, pinned by each freeze):
  - `20260925T212646-322Z-49728-6/` (val; freeze `415b1b8b`; final-22);
  - `20260925T203745-207Z-49728-2/` (train; freeze `e9860472`; plus `timed-practice.json` and the `.v1` candidates and
    evidence).
- **Snapshot manifests:**

  | Snapshot | `manifest.json` sha256 | Role |
  |---|---|---|
  | `code-snapshot-fbe6693` | `b5bdb3b3…` | 203745's timed, propose and evidence steps |
  | `code-snapshot-3936f94-4c9638d1` | `bc5e786e…` | 203745's assembly |
  | `code-snapshot-b7d4592` | `1927686c…` (landed) | 212646's steps and assembly, and 203745's earlier steps |

**Docs:** `docs/lanes/human-admission.md` (LF `dae9ce6c…`), with this batch's two new sections.

**Second landing** (after its review): the 23:57 take (final-26) and its snapshot `code-snapshot-3936f94` (`da606ea9…`).
The late take stays held (final-25) unless the main-account gain decision reopens it. Its `code-snapshot-83c05f1`
(`070a2882…`) and partial folder land only if it is revisited.

**Not mine** (other lanes' work in the tree):
- `docs/lanes/inverse-dynamics.md` and `docs/lanes/idm-gate2-anchors.md`;
- `perception/cooldown_anchors.py`, `killfeed.py`, `match_timer.py`, `match_timer_glyphs.json`, `replay_cuts.py`;
- `tests/test_cooldown_anchors.py`, `test_gate2_readers.py`, `test_replay_cuts.py` and `tests/fixtures/gate2_readers/`.

No commits, no Linear, nothing on the Mac.
