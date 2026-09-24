# fit-prereg (VUH-1359, VUH-1346): the plumbing fit's pre-registration and command sequence, with `simple_swing` folded in

**The pre-registration is drafted and the command sequence is generated from it.** The plumbing fit can start as soon as
200129 and 205528 are admitted. No fit ran, no commit, no Linear write, no game input. 053616 was not touched.

## What exists

| File | What it is |
|---|---|
| `docs/evidence/fit-readiness-20260923/range_bc_plumbing_prereg.json` | **The pre-registration:** vocabulary, cohort, fixed settings, 9 runs, the derivation rules, the scaling reading, the budget rule |
| `docs/evidence/fit-readiness-20260923/range_bc_plumbing.py` | **The driver** (stdlib). `commands` refuses until the tables are admitted, then writes the exact scripts; `derive` turns the plumbing reports into the real fit's `--preregistration` file |
| `policy/range_bc/train.py`, `steps.py` | `--arms` and `--train-fraction` (plumbing and smoke only, and `--scope fit` refuses both), `steps.truncate`, a reference-arm fallback, and `parser()` split out of `main` |
| `policy/range_bc/vocab.py` | **`simple_swing`, the 15th action** |
| Lane doc | Sections "Plumbing pre-registration" and "Pilot pre-registration" item 7, the action table, and the vocabulary notes |

## The pre-registration

**Cohort, fixed now.** Validation: none, and nothing reads a validation or test take.

| Role | Recordings |
|---|---|
| Train | 051828 and 200129 |
| Dev | 171533 and 205528 |

The rule: dev = 171533 plus the later-recorded new session. It does not look at content, and it keeps 200129's 13
Simple Swing presses in train. The driver refuses if the rule is broken, if a table is not train-split, or if a table
lacks the 15 actions.

**Runs** (`--scope plumbing`, MPS, batch 8, lr 3e-4, `normal` regime):

| Run | Arms × seeds | Settings |
|---|---|---|
| p1-curve | model, model_nohud, history_only × 0 | 20 epochs (the epochs grid is 1 to 20, from the per-epoch dev log), wd 1e-4, stride 48, lag 0 |
| p2-repeat | model_nohud, history_only × 0 | as p1; checkpoints must be byte-identical to p1's |
| p3-wd | model_nohud × 0 | wd 1e-3 |
| p4-lag1, p4-lag2 | model_nohud × 0 | lag 1, lag 2; reported only |
| p5-scale-¼, ½, ¾, 1 | model_nohud, history_only × 0, 1 | `--train-fraction` (a nested time-prefix; same file and sha256), `--max-steps` = 10 full epochs at f = 1 |

**Derivation** (on the pre-registered candidate, the no-HUD arm; the HUD arm's curve is reported and selects nothing):
- **Weight decay:** 1e-3 only if p3's minimum dev total loss is strictly lower than p1's; otherwise 1e-4.
- **Epochs E\*:** 1 + the argmin epoch of the chosen curve; ties go to fewer epochs.
- **Stride:** 48 if E\* ≤ 10, else 64.
- **Lag:** 0.
- **Seeds:** 0, 1, 2.
- **`hud_parity_sha256`:** the parity file handed to derive (P2′ if it exists, else run 1, which keeps the no-HUD
  candidate).
- **derive refuses:**
  - p1 and p2 bytes that differ;
  - a report that is missing, not plumbing-scope, or off-plan (cohort, step-table sha256, arguments).
- **Scaling reading:** derive computes rule (a) and tabulates what rules (b) and (c) need, for the lead to read.

**Budget.** About 7.9 h at most. That assumes every recorded minute counts: 33.8 train and 13.7 dev minutes, from 26.8
and 11.1 raw minutes. p1 is about 1.7 h. Add about 20 min to transfer the 35.6 GB of new video and about 10 min for the
four caches. Once the tables exist, `commands` re-estimates from them.

## The exact command sequence (Windows PowerShell, repo root, after admission and landing)

```powershell
$COMMIT = git rev-parse HEAD            # the landed commit carrying these bytes
$PLAN = "$env:TEMP\range-bc-plumb-$($COMMIT.Substring(0,7))"
uv run --offline --locked --group execution python docs\evidence\fit-readiness-20260923\range_bc_plumbing.py `
    commands --commit $COMMIT --out-dir $PLAN            # exit 2 "NOT READY: ..." until all four 15-action tables load
& "$PLAN\transfer.ps1"      # hashes and sends 200129 and 205528's originals (media sha256 = the header's), the 4 tables, the code archive and the Mac scripts
& "$PLAN\launch.ps1"        # Mac: mac-prepare.zsh in the foreground, then mac-queue.zsh as one niced durable job
#                           prepare: verify the hashes, unpack git archive to $D/code-<sha7>, uv sync, load every table
#                           under the pinned denylist, build 4 caches into $D/caches15 (051828 and 171533 are rebuilt)
#                           queue: p1 → p2 → p3 → p4-lag1 → p4-lag2 → p5 ×4, one .log and .exit each, stop at the first failure
# status: ssh mac 'cat /Users/james/dev/range-bc-data/runs/plumb-queue.status'
& "$PLAN\collect.ps1"       # after DONE: the 9 reports back, then derive, which writes $PLAN\preregistration.json (set $PARITY first)
```

**Where things go.** Everything goes under `/Users/james/dev/range-bc-data`, outside every checkout. No Mac checkout is
touched. On Windows, the outputs (hash files, code tar) stay in `$PLAN`.

**If intake relocates a video to a transcode,** `transfer.ps1` stops at the media-hash check. The cache step then
needs the runbook's `--media-relocation`, and I would add it.

## `simple_swing`: James's decision, folded in

- **Vocabulary:** `simple_swing` is 15th (Caps Lock, `key:58:0`), appended, so the other 14 indices are unchanged.
  `PAD_SENDABLE` is false, so it is masked live whatever its count.
- **Pilot pre-registration item 7:** it becomes sendable only when **both** hold:
  - the pilot pad profile binds Simple Swing to a pad button;
  - `Live.ALLOWED` includes that button.

  Together these are a new pre-registration of the pad settings. Then the vocabulary gets its pad control, the
  executor maps it, and the 50-press live floor still applies.
- **Intake's side is already in its working tree:** `FIT_ACTIONS` has `simple_swing`, and the fixture binds
  `key:58:0`. **The two land together:** the contract tests fail with either one alone.
- **All four step tables must be re-emitted with 15 actions,** 051828 and 171533 included (zero presses, but their
  own `held_known` column). The fit refuses 14-action tables, so the current `5a186224…` and `f89dcbc4…` are
  superseded. Their Mac caches are rebuilt by prepare, because the cache binds the table's sha256.
- **Model:** +1,731 parameters per arm (4,810,499 / 4,194,363 / 2,556,971). 13 positives put its `pos_weight` at the
  cap of 20.
- **Recorded, not decided:** Caps Lock had been noted as a toggle of the swing mode. If it is one, the header's
  `swing_mode` describes the session's start, and `web_swing`'s live mask still compares that start state with the
  pad's.

## Checks (Windows, joint tree with intake's working-tree `human_intake.py` and fixtures)

| Suites | Result |
|---|---|
| `test_range_bc.py`, `_contract.py`, `_hudmap.py`, `_plumbing.py` (new, 8 tests) | 119 passed, 1 skipped (corpus) |
| `test_range_bc_torch.py` (22, 2 new) and `test_human_intake.py` (36) | 58 passed |

**New tests:**
- `truncate` gives nested prefixes, never touches the file, and refuses a bad fraction;
- the pre-registration's cohort, dev rule and runs;
- `commands` refuses before admission, on a broken dev rule and on a validation table; its scripts are LF-only, name
  no 053616, and hold the table and media hashes;
- `derive` applies the rules, takes wd 1e-3 only when strictly lower, falls back to stride 64, writes once, and
  refuses unrepeatable, off-cohort and off-argument runs;
- every pre-registered run parses under the fit CLI;
- a plumbing run with `--arms` and `--train-fraction` end to end: reference fallback, same sha256, fewer minutes, dev
  untouched;
- `--scope fit` refuses both new options.

**Updated pins:** the parameter counts and the 15-action vocabulary test.

## Bytes (every file of mine differing from `b30eac5`)

```
41f49e006b55554ef6752dcc3095c0157c4941c9f57b36d2503fc44c1e08a8af  policy/range_bc/vocab.py
494d7e3b70d493f6d1a02f59aad044bb1f6ad0d92849c42b31497cfe62e171a4  policy/range_bc/steps.py
05145829f623619dff34e703a98a76801ad37679e9ca399abc2ded9ac4f3bb90  policy/range_bc/train.py
2aeec370c9812da33b14cf78b823e64a1807103583d69848b5770d53d16443b7  policy/range_bc/fixture.py
6ef3b8eba7b46f06cf28fbceb783be614124807eb54a7939f160d90978a2697f  tests/test_range_bc.py
a5ba0fffc406d7c33c9c295d97106d903e832e8e6e0651252afab58556fef354  tests/test_range_bc_contract.py
4369fd2fe8ceb1e2a4a3ece34b3840fd4523bd8e1d10682424106b9ecaa76c1e  tests/test_range_bc_torch.py
029fdcf7328eff43b5a00a612c96f0c26bf2c62a06810fba6262cfca9497e78a  tests/test_range_bc_plumbing.py                  (new)
11b7d050974bf068c56f4522dafc49a6712941e00859edde79f7f3796a840b77  docs/lanes/end-to-end-fit.md
9c1c025eac076ef6d0a3095d2f003cf28cda8b53ad835043663ef4d40a1a315b  docs/evidence/fit-readiness-20260923/README.md
79a76e580981596235a4eadeafed5f088acae5c38b35106e9106a5b3ec5b07ef  docs/evidence/fit-readiness-20260923/range_bc_plumbing.py        (new)
b0ce04dfe089f814528cc56bb6fc144ea7e9714e923ad269cebf879a724bc465  docs/evidence/fit-readiness-20260923/range_bc_plumbing_prereg.json (new)
```

**Required alongside, intake's and not mine** (the versions tested above):
```
83a18a42a00a14500fade79d9a079bca940571f50eef34b47a5022285f8996ff  agent/human_intake.py
f30458dd6763e44ee791fd172b9a120d1c484a062d81dc5c0ed237cad219d351  tests/human_intake_fixtures.py
```

## For the lead

1. **Admission must emit 15-action tables for all four recordings.** `commands` names whatever still fails to load.
2. **The dev rule** (the later-recorded new session is dev) is my proposal. Swapping it now, before admission, is
   free; after the first plumbing run it is not.
3. **Git archive and the data folder.** The code on the Mac is a `git archive` of the landed commit, so `data/` files
   tracked at that commit ride along. The fit reads only the denylist from it.
