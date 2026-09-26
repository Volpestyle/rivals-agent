# Intake delta review — 2026-09-26

**Verdict: changes require one registry guard before unconditional approval (B1).** The current registry excludes all eleven calibration/evaluation entries from splits, the current fit paths refuse gate2, F1 is fixed, and the existing 212646/203745 session verdicts stand. One additional fix-forward concerns relocated gate2 artifacts (F2). No session verdict changes follow from either finding.

Independent reviewer: admission-review (Codex). Read-only checkout; synthetic fixtures and reports only in the handoff folder. No video decode or sealed contents opened for this code review. Owner hand-back final-24 re-hashed as `5c64d041dd01b5a7546b8164a46e66e8263da07ad36be38bbfe6b00d6e3f030c`.

## Findings

**B1 — blocking the requested “never enter a split” invariant: category exclusions are not validated.** `agent/human_intake.py:534` (`check_registry`) and `agent/human_demos.py:188` (`read_splits`) inspect only `sessions`. Neither validates its separation from `evaluation_sessions` or `calibration_sessions`. In `review-intake-0926-work/audit.py`, adding an existing calibration session ID and video path to `sessions` as train passes `check_registry`; no media is opened. The same path ignores reader_validation, reader_development and match_dev metadata. This is an actual validator acceptance, not evidence that the present registry contains contamination: all 3 calibration and 8 evaluation rows are currently disjoint from its 16 split rows. Enforce disjoint identities and media paths (and available media hashes) at the shared registry boundary; test each category. Until then the exclusion is maintained by the current data and reviewer, not by the reader.

**F2 — fix-forward: relocation does not share the gate2 sealed check.** `agent/human_intake.py:1291` tests `split == "test"`, unlike the updated ordinary loader; it also never checks the header's sealed flag against the placement. A synthetic gate2 registry row marked sealed plus a matching artifact header with `sealed=False` reaches the payload checksum without `unseal=True`. Reproduction `review-intake-0926-work/relocation_repro.py` returns `DemoError: artifact checksum mismatch`, where a sealed refusal must happen before reading the body. Use `hd.SEALED_SPLITS` for both placement/header checks and validate the sealed header. Correctly emitted gate2 headers currently have sealed=True and do refuse; the tested fit readers still refuse gate2. This is not a demonstrated training leak.

**N1 — moving checkout.** Core intake/importer/driver and test bytes match final-24's LF pins. The current assembly module, tally script and registry have advanced since that hand-back (pins below). Assembly's new late-take wording additionally cites 7ad63e5, turncal 4ab87a55 and bindings-equivalence 9f2adb9b; tally's late-take status is now pending. I reviewed the per-session lookup logic and 045729 statement, not the new late-take calibration/binding evidence. That evidence needs its own session review. tally.json remains final-24's `6544941c` and therefore describes its earlier registry pin; regenerate it from the selected final registry when landing.

## Accepted checks

- **gate2:** SEALED_SPLITS includes test and gate2; registry validation rejects an explicit false sealed flag; ordinary import placement refuses before session access; ordinary load refuses before payload; sample generation for training refuses even after explicit unsealing. Headers emitted by import/export mark gate2 sealed. Intake's context rejects it before opening the raw session. Range-BC's split allow-list rejects gate2 even with allow_test; IDM's normal reader rejects it before rows, and target generation plus IDM training require train/val or train as appropriate. Execution, range_policy, range_skill_policy and range-BC fitting enforce train-only training; explicit allow_test in the IDM reader is evaluation access, not a fit permission.
- **F1:** original range→timed→range end-bracket reproduction now raises “end bracket: the banner flickers back”. Leading-range and later-timed regressions are covered. Re-evaluating all pinned 203745 banner reads produces exactly the stored cut. The helper's caller enumerates only declared spans; no automatic whole-video cut was introduced. Prior independent native verification of that unchanged span remains valid.
- **settings_change:** starts at recording start, ends two seconds after the declared Nth Esc up→down transition; auto-repeat does not add a press. It removes Esc events inside that explicit span from R3, cuts the span, and preserves R3 for a later Esc. Other UI cuts remain. E1 still checks every resulting gameplay edge before evidence is emitted. This review approves the mechanism, not the late session's lead-conditional settings equivalence.
- **MOTOR_STATEMENTS:** the 09-25 date-level statement is restricted to 203745 and 212646. Named session overrides replace the statement; a different session that day refuses. Chicago date resolves the 045729 UTC session to 09-25; its own 3936f94 quote is selected. Existing earlier-date behavior is preserved.
- **tally:** independently recomputing `hi.tally(tally.json.rows)` is identical. Normal train has 8 admitted sessions, 140.1569 counted / 140.1494 trainable minutes; normal val has 1 session, 15.5846 minutes, separately. Four false starts are not_range. Evaluation/gate2 rows add no minutes. The current calibration/evaluation entries do not resolve to any split placement. No calibration or match media was read.

## Validation and pins

Focused tests: **164 passed, 3 skipped** (`test_human_intake`, `test_human_demos`, `test_gate2_split`, `test_human_intake_timed`), isolated admission-review Python with -B and pytest cache disabled. Skips are the intentionally unrequested corpus tests. Additional reader/edge/execution results are recorded below. Synthetic reproductions and full tally output are in `review-intake-0926-work/audit.json`.

Current reviewed hashes (LF-normalized for code; raw hashes also retained in audit.json):

| Path | SHA256 (LF) |
|---|---|
| `agent/human_intake.py` | `e753e6ec1aedf87c636fa7ab22479626d7c9964fe12ebabd4ec531cdc38c8a2a` |
| `agent/human_demos.py` | `8c71f6ae1857b581a0599c401dd2f57f25f1d65d6f0f0978938ff0662517e206` |
| `data/human/sessions/intake_session.py` | `80830341b1d68f8263fb5dccba37cbddfacdc9f85cce9ed51f52092a66d8e3f5` |
| `data/human/sessions/assemble_session.py` | `a11fd5d1d87516b80f4b0e09545eb9631ef2ae91c1b81cdfe5ff39381cacb97c` |
| `data/human/sessions/tally.py` | `28958e664d61609eb2961f732f3eec354ed85809fa9bacebc2af978997eee2a7` |
| `tests/test_human_intake.py` | `98133b824283620178638ba5fae80247f71ce677316bc2460ab8ae3a96813a9c` |
| `tests/test_human_demos.py` | `01e9fdcde8de20d85298aa6bbaee7a1d37ff5373f7892c44adc06014d48c19a3` |
| `tests/test_gate2_split.py` | `41a1898bb0389b9cba1789bb71a4d636fde006ac430e3e7236bf4425af93cca8` |
| `tests/test_human_intake_timed.py` | `3fa13741e75f35d475657851fed5badbb75af42124618ddd01e39b2a4d924a78` |
| `data/human/session-splits.corpus.json` | `26d55f3d1bba686eaea1af82e5e02fa6fc6b93ef57737c5c9fff168a24d8da71` |
| `data/human/sessions/tally.json` | `6544941c243b8eb63f2a6a9ee29786642288a879522560cbca2021c032a72a54` |
`test_human_intake_edges`, `test_idm_targets`, `test_execution`, `test_range_bc`: **157 passed, 2 skipped**. No corpus or sealed files opened. An initial command named a nonexistent test file and collected nothing; the corrected command produced this result.
