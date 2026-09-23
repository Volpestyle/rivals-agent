# Mac fit readiness for the next Web-Cluster request fit

Checked 2026-09-23 for VUH-1346. **The first cohort fit has run**; see
[First cohort fit](#first-cohort-fit-2026-09-23): checkpoint `698d8831…`, 74/76 training labels. The Mac can train
the admitted two-session `web-cluster-request-v1` cohort on MPS; the commands are in [Next fit](#next-fit). The Mac
is at `4553072`.
The manifest-driven driver and its Windows verifier carry the driver review's required fixes (F1-F4). They were
rehearsed end to end with exactly those commands, on the accepted 032454 member only: fit, Mac→PC `scp`,
Windows CPU reload. Earlier, at `0f71336`, both recorded fits re-ran on their original inputs and the request
checkpoint reproduced byte for byte.

Still open:
- F8 is implemented in driver `80c118d5…` after the fit and is not yet reviewed. Any later fit must use it.
- Training accepts one exact `SourceIdentity`, so a later perception change means re-measuring first.

No model was selected, and no game input was sent on either machine.

## Mac state

| Item | State |
|---|---|
| Host | `james`, Darwin arm64, macOS 27.0, Apple M5 Max, 128 GiB; idle when checked (no training, GPU or ML job) |
| Tools | `git`, `uv` 0.11.32, `ffmpeg`/`ffprobe` 8.1.2. System `python3` is 3.9.6 and unused; each `.venv` is Python 3.12.13 |
| `/Users/james/dev/rivals-agent` | `main`, clean. Fast-forwarded (`--ff-only`) `83c6739` → `0f71336` → `21db6c6` → `45530720c10274680afe138f06f4b2f8689f77f7` (docs only) |
| `/Users/james/dev/rivals-agent-worktrees/human-execution` | Where both previous fits and the cohort dry runs ran. Clean, detached; advanced `7feee7b` → `0f71336` → `21db6c6` → `4553072`, each checked as an ancestor first. The previous run directories and inputs under `data/` are unchanged, except that the cohort manifest and `cohort.py` were replaced in place by their admitted versions. The pre-admission copies there are the ones preserved on the PC as `cohort-manifest-pending-v4.json` and `cohort-pending-v4.py`. The dry runs added the ignored `data/diagnostics/range-request-cohort-*-20260923/` and their inputs under `data/human/` |
| `/Users/james/dev/rivals-agent-worktrees/fit-dryrun-20260923` | New disposable detached worktree at `0f71336`, holding today's dry run. Remove with `git worktree remove --force` when no longer needed |
| Other worktrees | `loaderfmt5`, `rangeproof`, `tracker`, `writerfix`: untouched |

The training code is byte-identical from the previous fit commit `7feee7b` through `21db6c6`: `git diff 7feee7b 21db6c6 -- policy/ agent/state.py pyproject.toml uv.lock` is empty (only `perception/hud.py` and `perception/outline.py` changed after `0f71336`). So the pin on `policy/range_skill_policy.py` (`d6b62274…`) still holds. At `21db6c6` the environment checks below gave the same results (tests: 235 passed in 1.44 s).

## Environment

In `human-execution` and the dry-run worktree:

```zsh
uv sync --offline --locked --group execution     # no-op, cache warm, 0 s
uv run --offline --locked --group execution python -c 'import torch; print(torch.__version__); print(torch.backends.mps.is_built(), torch.backends.mps.is_available()); x=torch.arange(4.,device="mps",requires_grad=True); x.square().sum().backward(); torch.mps.synchronize(); print(x.grad.cpu().tolist())'
# 2.14.0 / True True / [0.0, 2.0, 4.0, 6.0]
nice -n 10 uv run --offline --locked --group execution pytest -q tests/test_range_skill_policy.py tests/test_range_policy.py tests/test_execution.py
# 235 passed in 2.42 s
```

## Dry run on the previously admitted inputs (`0f71336`)

Setup:
- Inputs: Mac-local copies of the 14 admitted numerical inputs and receipts, plus the two executed drivers, copied from `human-execution` into the dry-run worktree. No source media.
- Hashes: every file matched the hash pinned in its driver: `fit.py` `6a3ff6b2…` for request and `875c5562…` for v2.
- Execution: the drivers ran unmodified in one `nohup nice -n 10` job that wrote a log and exit status. Both exited 0 with about 3 s wall time each.

| Fit | Checkpoint | Predictions and metrics | Notes |
|---|---|---|---|
| Request (`range-request-human-fit-20260922`) | `6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef`, **byte-identical** to the recorded one | All five known rows identical (137 no, 141 start, 144/200/206 no); all four metric blocks identical | `fit_seconds` 2.60 (recorded 1.90). Report differs only in `git_commit` and `fit_seconds` |
| Six-label v2 (`range-event-human-fit-v2-20260922`) | `254c92c7…`, differs from `da29a97f…` | Weights **bit-identical** (`torch.equal` on every tensor); probabilities and metrics identical | The only differing payload field is `code_sha256`. v2 was trained at `8f78ae9`, before `range_skill_policy.py` gained the request revision (`582e3f08…` → `d6b62274…`) |

Dry-run artifacts are under `fit-dryrun-20260923/data/diagnostics/`: `fit-readiness-20260923/`, which holds `job.zsh`, `exit-codes.txt` and one log per fit, and each fit's `run-1/`.

## Hand-back to Windows (`0f71336`)

**Transfer.** `scp` returned the dry-run request checkpoint to this PC's scratchpad. SHA-256 on arrival was `6ee38807…`.

**Reload.** To avoid touching the shared checkout, I ran the reload in an isolated `git clone --shared` at `0f71336`. That clone was staged with:
- the transferred checkpoint;
- the recorded `mac-report.json` (`9d763f7c…`);
- the recorded numerical inputs.

**Request verifier.** The unmodified `verify_windows.py` exited 0 with `uv run --offline --no-project --with torch==2.14.0`. Its report has identical `known_rows` and identical `train_metrics`, and its maximum delta from Mac CPU is 1.630e-9, all matching the recorded `windows-report.json`. It differs only in `git_commit` and in `code_checks`, because the clone's `agent/state.py` is LF rather than CRLF.

**v2 checkpoint (`da29a97f…`).** The recorded verifier cannot pass at any commit after `8f78ae9`. By design, it requires the Windows `range_skill_policy.py` bytes to equal the Mac commit's blob, and that file has since changed. Instead I ran a reload-only check at `0f71336` on torch 2.14.0+cpu, with the verifier's own hash, identity, prediction and metric assertions minus the code-bytes pin. Predictions were identical, and probabilities differed from the recorded Windows report by 0.0. Metrics equal the Mac CPU reload.

## Cohort driver and dry run (after the driver review)

The driver consumes the admission owner's `rivals-request-cohort-manifest-v1`. Every gate is an explicit raise, and
the driver refuses to start under `-O` or `PYTHONOPTIMIZE`.

**Stage 1** uses the standard library only. No `agent` or `policy` module is imported before it passes.
1. The manifest's bytes equal `--manifest-sha256`. Then, before each is read, the driver hash-checks:
   - every file a selected member names;
   - every pin;
   - every `{path, sha256}` reference inside each member's examples packet;
   - every `{path, sha256}` reference inside that packet's review receipt, before the receipt's content is trusted.
     This now includes v5's `coverage.json` and the reviews both receipts name.
2. It reads admission from the frozen artifacts (`admission()`), not from the manifest's description:
   - the packet's own status;
   - its hash-pinned review receipt and the receipt's decision;
   - the receipt's binding to this packet and this session;
   - a mandatory row and label binding per schema (below).

   The placeholder review hash is refused. The manifest's own statuses must also be admitted.
3. Each of the seven modules the policy import runs must equal its git blob in the pinned `ae648b33` code snapshot,
   compared as source bytes. The seven are `agent/__init__.py`, `agent/state.py`, `agent/human_demos.py`,
   `policy/__init__.py`, `policy/execution.py`, `policy/range_policy.py` and `policy/range_skill_policy.py`.

**Stage 2:**
1. Imports the policy code with bytecode caches bypassed (`sys.pycache_prefix` is a fresh empty directory). It then
   re-checks every module loaded from the checkout, and checks again after the fit.
2. Builds the rows with the accepted recipe and runs the real `validate()`/`cohort()`.
3. Requires the manifest's identity and counts, and each member's evidence digest against both its packet and its
   `artifact_hashes`. There is no self-comparison fallback.

**Fit.** The 2026-09-22 request fit, unchanged.

| File | SHA-256 |
|---|---|
| [`fit_cohort_20260923.py`](../range-request-human-fit-20260922/fit_cohort_20260923.py) (driver, current, with F8) | `80c118d5c30cd05e6d16321f4c3fa2fad6aff099fc7e6b22397e442d9d5eb917` |
| The same driver before F8: rehearsal 5 and the first cohort fit | `f9f158fcc9abaa8fefe09d48c3fde2a85d80fa6573f69b4df777a82e30a7b653` |
| [`verify_windows_cohort_20260923.py`](../range-request-human-fit-20260922/verify_windows_cohort_20260923.py) | `f01efa194f7de3cd482c8a98de11ee2b4d7d64876057e646c4c3786bec716ac8` |

**How each member's admission is read** (from the frozen files):

| | 032454 (re-measured accepted labels) | 051828 v5 (admitted) |
|---|---|---|
| Packet status | `remeasured_accepted_labels_train_only_not_a_new_admission`, admitted through its hash-pinned `remeasurement.of_artifact` (`bd6cf4cb…`, status `accepted_train_only_numerical_diagnostic`, same receipt) | `admitted_train_only` |
| Receipt | 2026-09-22 decision (`52423a3c…`): `decision` `accept_five_…`; its `frozen_candidate` is in the packet's `input_artifacts` | `admission-decision.json` (`6d9fbe2d…`): `kind` `lead_admission_decision`, train-only, this session/group/split; its `admitted_artifact` is the packet's `source_artifact` |
| Session binding | Bound candidate `032454-request-timing-v1/candidate-rows.json`: all rows this session | Bound candidate `051828-request-timing-v5/candidate-rows.json`: all rows this session |
| Row and label binding (mandatory, F7) | The receipt's `known_labels` equal the packet's. Every row equals the accepted original at its grid index on every field except the re-measured features (`source`, `history`, `anchor_target_track`). The re-measurement may declare no other `changed_fields`. Those features are bound instead (F8) to the packet's pinned `remeasurement.report` (`37c813f3…`), from the same commit. Each re-measured history equals the report's `new_history`, the other rows keep the original's history, and every `source` equals the report's `source_identity`. `anchor_target_track` stays exempt: it is not a model feature | All 412 admitted rows equal the packet rows at their grid index: every `request_example_fields` value, `history`, the label mapped through `request_example_mapping`, and `source` = the candidate's `source_identity`. The packet adds nothing but review provenance. The other 3,768 rows are unknown with empty history and coverage's reason. The grid, labels and `label_known` equal `coverage.json` (`c6e701b4…`). The receipt counts 36/35/4,180 also match |
| Evidence digest | `e66b6fec…` = packet = `artifact_hashes` | `a6f8d629…` = packet = `artifact_hashes` |

**Dry run** (a rehearsal, not a candidate):
- **Input.** The admitted manifest `james-request-cohort-ae648b33/cohort-manifest.json` (`bcaa1cf4…`), run with
  `--dry-run 20260922T032454-642Z-24328-1`. The driver read only the 032454 member (19 inputs) and skipped v5.
- **Full cohort check.** The same driver's `--check` without `--dry-run`, which does not fit, passes on the admitted
  manifest: 27 inputs, 4,288 rows, 76 known, [39, 37], 37 unique events, joint digest `86e5894b…`.

| Check | Result |
|---|---|
| Code | `4553072` (docs-only after `21db6c6`) on both machines; the seven closure blobs equal the `ae648b33` snapshot's |
| Training | torch 2.14.0 on `mps:0`, `fit_seconds` 2.03. The earlier runs took 1.03–2.02; Spotlight was indexing during some |
| Checkpoint | `3fea92c4743451145cc0da7727630bc44810d8a4b6893506192cab4a456a2955`; `run-2` byte-identical |
| Against `682d81f1…` (driver before review) | Every weight tensor bit-identical. The only differing payload fields are `training_config.driver_sha256` and `cohort_manifest_sha256`, so the checkpoint bytes necessarily differ. Every metric, prediction, identity and coverage section of the report is identical |
| Labels and baselines | Model 5/5 (141 start at 0.994; the four no-new at 0.0043 or less). Ammo-positive 1/4 no-new, 1/1 start, 3 extra starts. Never-start 4/4, 0/1 |
| Mac CPU to Windows CPU | torch 2.14.0+cpu: same predictions and metrics, max delta 1.164e-9 (`windows-report.json` `db3f51dd…`) |

### Review fixes F1-F4, F7 and F8, tamper cases

The harness copies the repo's code and every input into a scratch mirror. It then runs the driver `--check` under
`-X importtime`, which records every import. A refusal therefore shows that no `agent` or `policy` module was
imported, and that no row was built, before the driver exited. Result: 29 cases, all as expected, against driver
`80c118d5…` and the admitted manifest `bcaa1cf4…`.

| Case | Before (review) | Now |
|---|---|---|
| T4: forged 051828 packet, own status `candidate_only_not_admitted`, 032454's receipt | exit 0, full joint | refused: packet status |
| T4b: same, `--dry-run` 051828 | exit 0 | refused: packet status |
| T4c (new): forged status `admitted_train_only`, 032454's receipt and its `input_artifacts` copied | not tested | refused: labels differ from the receipt's `known_labels` |
| T4d (new): real v5 receipt, one start label flipped after admission | not tested | refused: grid 39 differs from the lead-admitted row |
| T5: member 0 packet status `REJECTED_do_not_train` | exit 0 | refused: packet status |
| T5b (new): rows carry the all-zero placeholder review hash | not tested | refused: re-measured rows differ from the accepted artifact beyond the re-measured features |
| `python -O`, manifest sha `000…0` | exit 0 | refused before any import |
| `PYTHONOPTIMIZE=1`, admitted manifest, no `--dry-run` | gates skipped | refused before any import |
| `python -OO` | not tested | refused before any import |
| T6: one byte appended to the profile, `dependencies.json`, the examples, the snapshot manifest or the receipt (5 files) | refused | refused: hash mismatch |
| T6c: manifest sha `000…0` | refused | refused |
| T7: `print` appended to `agent/human_demos.py`, `policy/__init__.py` or `agent/__init__.py` | exit 0, injected code ran | refused: differs from the code snapshot; the injected code did not run |
| T7: `print` appended to `policy/range_policy.py` | refused, but the injected code ran first | refused before import; the injected code did not run |
| T8 (new): unchecked-hash `.pyc` of a tampered `range_policy.py` beside the real source | not tested | accepted, and the `.pyc` was not executed. A plain import in the same mirror does execute it |
| **NEW-a** (delta review): admitted start grid 39 ammo history `[5,5,5,5,5]` → `[0,0,0,0,0]`; labels, counts, status, receipt and `source_artifact` untouched; digest and hashes recomputed | exit 0, [39, 37] (also with driver `3c90e941…` in this mirror) | refused: grid 39 differs from the lead-admitted row |
| **NEW-b** (delta review): admitted control grid 36 dropped to unknown, manifest counts updated | refused: counts | refused: grid 36 differs from the lead-admitted row |
| One byte appended to v5 `coverage.json` (named only by the receipt) | not an input | refused: hash mismatch |
| R1 (new): the re-measured 032454 packet edits a masked row's `reason`; digest and hashes recomputed | not tested | refused: re-measured rows differ from the accepted artifact beyond the re-measured features |
| **X** (delta review 2): re-measured 032454 grid 137 ammo history `[3,3,3,3,3]` → `[0,0,0,0,0]`; labels, receipt and re-measurement block untouched; digest and hashes recomputed. Dry run and full | exit 0: 108 rows [4, 1] and 4,288 rows [39, 37] (driver `f9f158fc…` in this mirror) | refused (both): re-measured histories differ from the pinned re-measurement report |
| X-b (new): every re-measured row's `source.cooldown_regime` `normal` → `off` | refused after import, by `cohort()` ("mixed source identity") | refused before import: re-measured source differs from the pinned report's identity |
| Verifier: `-O` / `PYTHONOPTIMIZE=1` / wrong report pin / report recording another torch (F5) | asserts | refused, each |

**F4.** Runbook step 1 now checks `$M` against `$MS` before anything reads it. It runs no command taken from the
manifest's content. The admission owner's `cohort.py --check` runs only after the driver has verified its pin.

**F6.** A member whose `artifact_hashes` does not pin its examples file is refused with a message, not a `KeyError`.

**F7 (delta check).** The v5 receipt used to bind its packet only by aggregate counts, so NEW-a trained on ammo values
the lead never admitted. Stage 1 now binds each packet to what its receipt admitted, row for row, using JSON equality
only; see the row-binding line in the admission table. The label binding is mandatory for each schema, no longer
conditional on the field being present. On the real data every binding holds: 412 admitted rows, 3,768 unknowns, and
a 4,180-coordinate grid for v5; 108 rows differing only in `history` and `source` for 032454.

**F8 (second delta check).** F7 left the re-measured 032454 features (`history`, `source`) bound to nothing. Stage 1
now binds them to the hash-pinned re-measurement report, as in the admission table. The real `--check` output is
byte-identical before and after F8 in both modes (`data/diagnostics/range-request-cohort-f8-check-20260923/`).

**Two faults from the fixes, both found only in the real round trip:**
- The post-fit module check rejected `torch.ops`, whose `__file__` is the bare string `_ops.py`.
- The verifier rejected itself, because importing torch pulls in `multiprocessing`, which registers the running
  script again as `__mp_main__`.

Both are fixed. The failed attempts are kept as evidence in `…-rehearsal2-20260923/` (fit refused after training,
no report) and `…-rehearsal3-20260923/` (the Windows verifier refused).

**Artifacts.** Ignored paths, the same repo-relative directory on both machines:
- `data/diagnostics/range-request-cohort-rehearsal5-20260923/` is the passing run of [Next fit](#next-fit) exactly as
  written, with the F7 driver, plus `run-2`.
- Earlier drivers: `…-dryrun-`, `…-rehearsal-` through `…-rehearsal4-20260923/`.
- The harness and its results are in `range-request-cohort-rehearsal5-20260923/tamper/` (`tamper3.py`, F7), and in
  `range-request-cohort-f8-check-20260923/` (`tamper4.py`, `tamper4-results.json`, and the F8 check outputs), on the
  PC only.

## First cohort fit (2026-09-23)

The lead launched this fit.
- **Commands:** the [Next fit](#next-fit) blocks, verbatim, with `$MS` = `bcaa1cf4…`, `$DRY = @()` and
  `$RUN` = `data/diagnostics/range-request-cohort-fit-20260923`.
- **Code:** commit `4553072`, driver `f9f158fc…`. The lead exempted this fit from F8.
- **Scope:** train-only. This is not validation, generalization or live clearance.

| Item | Result |
|---|---|
| Checkpoint | `698d8831a6740d1d060ed3691dc2102fc1a39987ad4c7a03ad4c96a49df9ce1b` (same on both machines) |
| Mac report / Windows report | `d67507a00a1f302311f55d63fa7e36e344d26856ae0b23c19d235ce228a8bc61` / `b38defa3c42c59cd5bc261dabdd14e8bfab1486deface43885e58a85037752b8` |
| Cohort | 4,288 rows (108 + 4,180), 76 known, [39 no-new, 37 start], 37 unique events, evidence digest `86e5894b…`. 27 inputs hash-checked; 28 transferred hashes matched on the Mac |
| Training | torch 2.14.0 on `mps:0`, `fit_seconds` 9.29; the 09-22 configuration (100 epochs, batch 2, lr 0.01, seed 7, hidden 8) |
| Model on training labels | **74/76**: starts 36/37, controls 38/39, one extra start. Missed start 051828:51 (`p_start` 0.411). Extra start 051828:591 (`p_start` 0.642). Both have ammo 4. Mean request lead 0.050 s |
| Confidence ≥ 0.7 | 70 scored, all correct (starts 33, controls 37). 6 below threshold, all 051828: 48, 51, 591, 764, 3835 and 4032. Precision 1.0, recall 0.892 |
| Ammo-positive baseline | Starts 35/37 (1374 and 1717 have unknown ammo); controls 1/39; 38 extra starts |
| Never-start baseline | Controls 39/39, starts 0/37 |
| Per session, 032454 | Model 5/5 (141 at 0.947; no-new at most 0.071). Ammo 1/4 + 1/1 with 3 extra starts. Never-start 4/4 + 0/1 |
| Per session, 051828 | Model 69/71 (starts 35/36, controls 34/35). Ammo starts 34/36 (2 unknown), controls 0/35. Never-start 35/35 + 0/36 |
| MPS to Mac CPU | Same predictions; max delta 5.96e-7 |
| Mac CPU to Windows CPU | torch 2.14.0+cpu in the shared LF checkout: same predictions and metrics, max delta 4.17e-7. Policy files byte-identical; `agent/state.py` differs by CRLF only |
| Identity check | At `4553072` the CRLF form reproduces `a30b3cae…` / `00fd672e…` (`source_identity_matches: ["crlf"]`); LF gives `75912d7f…` / `9e024bc1…` |

**Same-ammo contrast groups** (known rows with identical five-step ammo histories and both labels):

| Ammo history | No-new | Start |
|---|---|---|
| `[3,3,3,3,3]` | 032454:137; 051828: 134, 1714, 1788, 1859, 3266 | 032454:141; 051828: 137, 404, 764, 1791, 2349, 3010, 3987 |
| `[4,4,4,4,4]` | 051828: 48, 591, 1655, 1663, 1665, 3255 | 051828: 51, 126, 594, 652, 1047, 1658, 1668, 2730, 3113, 3258, 3401, 3434, 4032 |
| `[4,3,3,3,3]` | 051828: 56, 131, 599, 657, 667, 1867, 3263, 3439, 4037 | 051828: 1092, 2069 |
| `[1,1,1,1,1]` | 051828: 1184, 1514, 3832 | 051828: 1177, 1187, 1517, 3752, 3835 |
| `[5,5,5,5,5]` | 051828:36 (`p_start` 0.026) | 051828:39 (0.925), the only full-ammo pair |
| `[0,0,1,1,1]` | 032454:206 | 051828:3730 |

Both training errors fall in the largest mixed group, `[4,4,4,4,4]`. One training fit on two same-owner sessions
shows only that these labels can be fitted, not that timing generalizes.

**Artifacts.** On the PC and the Mac: `data/diagnostics/range-request-cohort-fit-20260923/`, containing
`run-1/model.pt`, `run-1/mac-report.json`, `check.json`, `transfer-manifest.json` and `transfer.zip`. The PC also
has `run-1/windows-report.json`; the Mac has `fit.log`, `exit.txt` and `run.sh`.

**Re-verifying this run later:**
- The docs verifier now sits beside the F8 driver. By design it refuses this run's report, whose driver hash is
  `f9f158fc…`.
- Use the copy of `verify_windows_cohort_20260923.py` (`f01efa19…`) kept in the run directory, beside its
  `f9f158fc…` driver.
- Run it on a copy of `run-1` without `windows-report.json`, which it writes exclusively.

## Next fit

This replaces the earlier per-packet procedure of copying `fit.py` and editing its `EXPECTED` block.

**When:** once the lead says the v5 exactness check passed and hands over the final manifest's SHA-256. The
manifest was rewritten several times while v5 was frozen, so use the hash the lead hands over, not one recorded here.

**Lead decision, 2026-09-23 (F8).** The reviewer's second delta check requires F8. F8 binds the re-measured 032454
histories to the pinned `data/human/inspection/20260922T032454-642Z-24328-1/remeasure/ae648b3/report.json`, row
for row.
- **Exempted: the first cohort fit.** That is driver `f9f158fc…`, manifest `bcaa1cf4…`, run
  `range-request-cohort-fit-20260923`. The reviewer had independently verified that the real packet's histories
  equal that pinned report.
- **Required: F8 before any later fit.** Use the driver that implements it, not `f9f158fc…`.
- **Status:** the first cohort fit ran under this exemption. F8 is now implemented in `80c118d5…`, the driver this
  section copies, and awaits review.

**Where:** PowerShell, from `C:\Users\volpe\repos\rivals-agent`, on the pushed commit the fit runs on. The
checkout's policy files must be LF: `git ls-files --eol policy/range_*.py` shows `w/lf`.

Each step stops on failure. The rehearsal ran these blocks verbatim, with `$MS`, `$RUN` and `$DRY` set to the
dry-run values.

```powershell
# 0. Set once.
$M      = 'data/human/skill-event-candidates/james-request-cohort-ae648b33/cohort-manifest.json'
$MS     = '<admitted manifest sha256, as handed over>'
$RUN    = 'data/diagnostics/range-request-cohort-fit-20260923'   # new name; must not exist on either machine
$DRY    = @()                    # rehearsal only: @('--dry-run', '20260922T032454-642Z-24328-1')
$EV     = 'docs/evidence/range-request-human-fit-20260922'
$H      = '/Users/james/dev/rivals-agent-worktrees/human-execution'
$MAC    = "$HOME/.claude/skills/mac-remote/mac.ps1"
$COMMIT = git rev-parse HEAD

# 1. Windows pre-flight. Nothing reads the manifest before its hash is checked, and no command comes from its
#    content. The driver's check verifies every pin, cohort.py included, before the admission owner's check runs.
if ((Get-FileHash -Algorithm SHA256 $M).Hash.ToLower() -ne $MS) { throw 'manifest differs from $MS' }
New-Item -ItemType Directory $RUN | Out-Null; Copy-Item "$EV/fit_cohort_20260923.py" $RUN
uv run --offline --no-project python -B "$RUN/fit_cohort_20260923.py" --manifest $M --manifest-sha256 $MS @DRY --check --transfer-manifest "$RUN/transfer-manifest.json" > "$RUN/check.json"; if ($LASTEXITCODE) { throw 'driver check failed' }
uv run --offline --no-project python -B data/human/skill-event-candidates/james-request-cohort-ae648b33/cohort.py --check; if ($LASTEXITCODE) { throw 'cohort check failed' }

# 2. Package with forward-slash member names and send.
uv run --offline --no-project python -c "import json,sys,zipfile; m=sys.argv[1]; z=zipfile.ZipFile(sys.argv[2],'x'); [z.write(p,p.replace(chr(92),'/')) for p in [*json.load(open(m)),m]]; z.close()" "$RUN/transfer-manifest.json" "$RUN/transfer.zip"; if ($LASTEXITCODE) { throw 'package failed' }
(Get-FileHash -Algorithm SHA256 "$RUN/transfer.zip").Hash.ToLower()
ssh -o BatchMode=yes mac "mkdir -p $H/$RUN"; scp -o BatchMode=yes "$RUN/transfer.zip" "mac:$H/$RUN/transfer.zip"; if ($LASTEXITCODE) { throw 'send failed' }

# 3. Mac, one call: clean worktree, advance to $COMMIT, environment, unpack, hashes, MPS probe,
#    then one niced durable fit, waiting for its exit status. Compare the printed zip hash with step 2's.
& $MAC ("RUN=$RUN; COMMIT=$COMMIT; M=$M; MS=$MS; DRY=($DRY)`n" + @'
cd /Users/james/dev/rivals-agent-worktrees/human-execution
test -z "$(git status --porcelain)" || { echo 'human-execution is dirty: stop'; exit 3; }
git fetch -q origin; git merge-base --is-ancestor HEAD $COMMIT; git checkout -q --detach $COMMIT; git rev-parse HEAD
uv sync --offline --locked --group execution
shasum -a 256 $RUN/transfer.zip; unzip -o -q $RUN/transfer.zip
uv run --offline --locked --group execution python -c 'import json,hashlib,sys; m=json.load(open(sys.argv[1])); bad=[p for p,d in m.items() if hashlib.sha256(open(p,"rb").read()).hexdigest()!=d]; print("BAD",bad) if bad else print("all",len(m),"hashes match"); sys.exit(bool(bad))' $RUN/transfer-manifest.json
uv run --offline --locked --group execution python -c 'import torch; print(torch.__version__, torch.backends.mps.is_available()); x=torch.arange(4.,device="mps",requires_grad=True); x.square().sum().backward(); torch.mps.synchronize(); print(x.grad.cpu().tolist())'
ps -Ao pid,%cpu,comm -r | head -4 || true
print -r -- "uv run --offline --locked --group execution python -B $RUN/fit_cohort_20260923.py --manifest $M --manifest-sha256 $MS ${DRY[*]} --out $RUN/run-1 >$RUN/fit.log 2>&1; echo \$? >$RUN/exit.txt" >$RUN/run.sh
nohup nice -n 10 zsh $RUN/run.sh >/dev/null 2>&1 & echo $! >$RUN/pid.txt
while kill -0 $(<$RUN/pid.txt) 2>/dev/null; do sleep 2; done
echo "exit $(<$RUN/exit.txt)"; tail -8 $RUN/fit.log; shasum -a 256 $RUN/run-1/model.pt $RUN/run-1/mac-report.json
'@)
if ($LASTEXITCODE) { throw 'Mac fit failed' }

# 4. Return, then Windows CPU reload pinned to the Mac's torch. The report hash is read from the Mac.
New-Item -ItemType Directory "$RUN/run-1" | Out-Null
scp -o BatchMode=yes "mac:$H/$RUN/run-1/model.pt" "$RUN/run-1/model.pt"; scp -o BatchMode=yes "mac:$H/$RUN/run-1/mac-report.json" "$RUN/run-1/mac-report.json"; if ($LASTEXITCODE) { throw 'return failed' }
$RS = (ssh -o BatchMode=yes mac "shasum -a 256 $H/$RUN/run-1/mac-report.json").Split(' ')[0]
uv run --offline --no-project --with torch==2.14.0 python -B "$EV/verify_windows_cohort_20260923.py" --run "$RUN/run-1" --mac-report-sha256 $RS; if ($LASTEXITCODE) { throw 'Windows reload failed' }

# 5. Hand to the lead: these hashes and summary lines, plus the run directory path.
Get-FileHash -Algorithm SHA256 "$RUN/run-1/*" | Format-Table -AutoSize Hash, @{n='File'; e={Split-Path $_.Path -Leaf}}
uv run --offline --no-project python -c "import json,sys; r=json.load(open(sys.argv[1])); print(json.dumps({k: r[k] for k in ('scope','git_commit','checkpoint_sha256','evidence_digest','label_reproduction','fit_seconds')})); print(r['coverage']['grid_rows'], 'rows', r['coverage']['bin_support'], 'support', r['coverage']['unique_events'], 'events'); [print(k, r[k]['confusion'], 'extra starts', r[k]['false_positive']) for k in ('model_train_metrics','ammo_baseline_train_metrics','never_start_train_metrics')]" "$RUN/run-1/mac-report.json"
```

Report the result from `exit.txt`, `fit.log` and `run-1/mac-report.json`, not from the launch. The report also has
per-session metrics, confidence-filtered metrics, same-ammo contrast groups and every known row's probabilities.
Rehearsal faults already fixed in the text above:
- `set -o pipefail` stopped step 3 at `ps | head`, which exits early by design;
- `mac.ps1` output cannot be captured into a variable, so step 4 reads the report hash with plain `ssh`;
- In Windows PowerShell, `>` writes `check.json` as UTF-8 with a BOM, so read it with `utf-8-sig`. It is a record
  only and is not transferred;
- `unzip -n` kept a stale copy of a pinned file that the admission owner had rewritten at the same path, and the
  hash check stopped step 3. `unzip -o` writes the pinned bytes, and the hash check after it still proves them.

### What the manifest must carry

"Admitted status" below means a status that begins with "accepted" or "admitted" and contains none of "candidate",
"pending" or "reject".

**Manifest fields:** `format` `rivals-request-cohort-manifest-v1`, `head`, `semantic_revision`, `feature_revision`
and `perception_commit`, and an admitted top-level `status`.

**Each member:**
- `session`, `group`, and `split` `train`.
- An admitted `status`.
- `examples` `{path, sha256}`.
- `artifact_hashes` `{path, sha256}`, whose `files` pins that examples path and whose `evidence_digest` equals it.
- No `candidate_rows`.

**Each examples artifact:**
- `format`, `head` and revisions as above.
- An admitted `status`. A re-measurement may instead be `remeasured_accepted…` with a pinned
  `remeasurement.of_artifact` that is itself admitted and has the same receipt.
- `evidence_digest` and `policy_schema_sha256`.
- Rows in the accepted constructor recipe, all carrying this member's session, group and split, `reviewed_human`,
  and the receipt's hash.
- A `review_receipt` `{path, sha256}`, never the placeholder. Every file the receipt names must be present with
  its hash. It takes one of two forms:
  - **Decision receipt.** `decision` begins with accept or admit, and its `frozen_candidate` is among the packet's
    `input_artifacts`. Its `known_labels` (required) equal the packet's.
  - **Lead admission decision.** `kind` `lead_admission_decision`, `train_only` true, and this
    session/group/split. Its `admitted_artifact` path and hash equal the packet's `source_artifact`, and it names a
    `coverage` file. The packet equals that artifact and coverage row for row, as in the admission table.
- The receipt's bound candidate holds only this session's rows. `counts`, where present, equal the packet's.
- A re-measured packet may declare only `source`, `history` and `anchor_target_track` as changed. Every other row
  field equals its accepted original's.

**`pins`:** exactly one `…/code-snapshot/manifest-<commit>.json`, whose `commit` is `perception_commit`, with blobs
for all seven closure modules.

**`check`:** `source_identity`, `per_member` in member order, and `joint` `{rows, bin_support, unique_events}`.
`joint_evidence_digest` and per-member `evidence_digest` are checked when present.

The admitted manifest `bcaa1cf4…` meets all of these.

### What the binding needs

The fit is train-only, and the binding is a separate reviewed act. The live loader (`agent/loop.py --brain
range-skill`) reads three operator JSON files, and `load_checkpoint` refuses a live load without all of them:

- **`--range-identity`:** exactly `check.source_identity`: patch `1.1.3870120/build25364676`, regime `normal`, profile
  `c5528cf7…`, perception `a30b3cae…`, selector `00fd672e…`, `web-cluster-request-v1`,
  `masked-state-grid-causal-v1`. Its digest, which the receipt's `source_identity_sha256` must equal, is
  `fff3cab14b4e7c15e788938bce5246312b9965e72719fd92a32c6f4b7b85d16a`.
- **`--range-runtime` (`SkillRuntimeIdentity`):**
  - The code requires these three to equal the source: `patch` `1.1.3870120/build25364676`, `cooldown_regime`
    `normal`, `selector_sha256` `00fd672e…`.
  - `perception_sha256` is only required to be *a* hash. For a like-for-like binding, set it to `a30b3cae…` and run
    perception code equal to `ae648b33`'s `hud.py`/`outline.py`/`loop.py` (unchanged at `21db6c6`).
  - Also required: `runtime_settings_sha256` (the virtual-pad settings manifest, which must differ from the source
    profile `c5528cf7…`), `calibration_sha256`, `controller_code_sha256` and `semantic_review_sha256`;
    `input_domain` `virtual_pad`; and the source's semantic and feature revisions.
- **`--range-deployment`:** the checkpoint SHA-256, the `source_identity_sha256` above, that runtime verbatim, and
  the deployment review's SHA-256.
- **The build and flags:** the game must still report 1.1.3870120 / build 25364676. Run with
  `--cooldowns normal` and `--decision-hz 10`.

**The identity hashes are over CRLF bytes.** `perception_sha256` and `selector_sha256` are
`digest({path: sha256(bytes)})` over the bytes `git archive` wrote on this PC, where `core.autocrlf=true` makes
them CRLF. Other byte forms of the same files give other values:

| Bytes hashed at `21db6c6` | Perception | Selector |
|---|---|---|
| CRLF (`git archive` on this PC; the identity) | `a30b3cae…` | `00fd672e…` |
| LF (git blobs; the Mac checkout) | `75912d7f…` | `9e024bc1…` |
| This PC's shared working tree (mixed endings) | `fb5ce333…` | `ea2b9fb5…` |

In the shared working tree, `hud.py`, `outline.py` and `brain.py` are CRLF, while `loop.py` and `tracker.py`
are LF.

A runtime check that hashes files must hash git blobs converted to CRLF, never working-tree bytes. The driver's
`identity_code_check` does exactly that and reports `source_identity_matches: ["crlf"]` at `21db6c6`. The only
alternative is to normalize the recipe and re-issue every identity.

## Expected runtime

**Measured (5 known rows):**
- Windows pre-flight (step 1): about 3.5 s.
- Transfer: seconds; the dry-run zip was 1.1 MB. The full cohort adds the 9.5 MB admitted v5 examples.
- Mac block: under a minute, not timed separately; the fit itself was `fit_seconds` 1.03–2.02.
- Windows verifier: about 4 s.

**Next fit (76 known rows: 5 + 71).** Training runs ⌈K/2⌉ × 100 optimizer steps for K known rows, here 3,800.
At the measured 3.4–9 ms per step, the fit takes about 13–34 s. Masked rows only count toward coverage.

## Not ready or at risk

- **F8 is applied after the fit and is unreviewed.**
  - F1-F4 and F7 are reviewed and approved.
  - The second delta check approved with F8 required before any later fit. The lead exempted the first fit.
  - F8 is implemented in `80c118d5…` and tested above: 29 tamper cases, and the real check unchanged.
  - Its review is the lead's call.
- **F1 reads two receipt schemas.** The lead accepted the per-schema equivalents on 2026-09-23, and the artifacts
  are unchanged.
- **The manifest changes under a fixed path.** It was rewritten several times on 2026-09-23. Step 1 refuses
  anything but the handed-over hash, and the Mac overwrites stale copies with the pinned bytes.
- **Unpinned Windows torch drifts.** On 2026-09-23, `uv run --offline --no-project --with torch` resolved
  **torch 2.6.0+cu124** from this PC's uv cache instead of the recorded 2.14.0+cpu. The verifier still passed:
  predictions were identical and probabilities within 1.4e-9. Pin `--with torch==2.14.0`, which is now cached,
  for a like-for-like report.
- **A fresh Windows checkout fails the verifier's code pin.** `core.autocrlf=true` in the system gitconfig writes
  `policy/*.py` as CRLF, and the verifier allows CRLF only for `agent/state.py`. The shared checkout has LF
  `range_policy.py` and `range_skill_policy.py`. For an isolated checkout, use `git -c core.autocrlf=false`.
- **Training accepts exactly one `SourceIdentity`.** Every training row must share patch, regime, source-profile
  hash, perception hash and selector hash, and `cohort()` refuses anything else before training starts.
  - Any later change to `perception/hud.py`, `perception/outline.py` or `agent/loop.py` changes the perception
    hash, and a change to `agent/brain.py` or `agent/tracker.py` changes the selector hash. Either way, re-measure
    and re-freeze before a fit.
  - `evaluate()` tolerates a different source profile across sessions but still requires the same patch, regime,
    perception and selector hashes.
  - No human train+validation driver has been executed yet, so an evaluation in the same job would be new driver
    code needing review.
- **A newer `$COMMIT` is checked, not trusted.** The driver refuses to fit if the policy code's git blobs differ
  from the cohort's pinned code snapshot. A later policy change therefore needs re-validation of the cohort,
  not a silent refit. The Mac block refuses a dirty worktree, and `merge-base --is-ancestor` refuses to move it
  backwards or sideways.

## Range BC (end-to-end fit): plumbing runbook

Owner: the end-to-end fit lane (`docs/lanes/end-to-end-fit.md`). No real data has been fitted.

**What was rehearsed on 2026-09-23 with the calibration take** (`2026-09-23 15-47-07.mkv`, not a training session):
- steps 1-2: transfer with hash checks;
- step 4: the cache build on the Mac;
- the Windows and Mac decode agreement.

The script is `range_bc_rehearsal.py` in this folder. Steps 3 and 5-9 have run only on synthetic data, in
`tests/test_range_bc*.py`.

**Rules:**
- Caches are built **on the Mac only**, with the pinned Homebrew **ffmpeg 8.1.2_1**; the builder refuses other
  platforms.
- The sealed denylist (`data/human/sealed-denylist.json`, pin `57cfe01f…`) is loaded by every CLI.
- 053616 is never transferred.

```powershell
# 0. Set once. $W is a clean Mac worktree at $COMMIT (create it once: git -C /Users/james/dev/rivals-agent worktree
#    add --detach $W $COMMIT); $D is the Mac data root, outside every checkout.
$MAC    = "$HOME/.claude/skills/mac-remote/mac.ps1"
$W      = '/Users/james/dev/rivals-agent-worktrees/range-bc'
$D      = '/Users/james/dev/range-bc-data'
$COMMIT = git rev-parse HEAD                      # the landed package; --scope fit refuses uncommitted code (K5)
$UV     = 'uv run --offline --locked --group execution'

# 1. Windows, per admitted recording $ID (never 053616): hash the originals, video first, then the logger files.
$ID = '<logger session id>'; $V = '<C:\Users\volpe\Videos\... .mkv, from metadata.json video_path>'
$L = "C:\Users\volpe\Videos\RivalsInput\$ID"
Get-FileHash -Algorithm SHA256 $V, "$L\metadata.json", "$L\inputs.jsonl", "$L\frames.csv" |
    ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content -Encoding ascii "$ID.sha256"

# 2. Send, keeping the video's own base name (the cache resolves videos by it), then verify on the Mac.
ssh -o BatchMode=yes mac "mkdir -p '$D/originals/$ID' '$D/steps' '$D/caches' '$D/runs'"
scp -o BatchMode=yes "$L\metadata.json" "$L\inputs.jsonl" "$L\frames.csv" "$ID.sha256" "mac:$D/originals/$ID/"
scp -o BatchMode=yes "$V" "mac:'$D/originals/'"              # a name with spaces: check the result in step 2b
& $MAC ("D=$D; ID=$ID`n" + @'
cd "$D/originals"
while read -r want name; do
  f="$ID/$name"; [[ -e "$f" ]] || f="$name"
  got=$(shasum -a 256 "$f" | cut -c1-64); [[ $got == $want ]] || { echo "BAD $name"; exit 2; }; echo "ok $name"
done < "$ID/$ID.sha256"
'@)
if ($LASTEXITCODE) { throw 'transfer hash mismatch' }

# 3. The step table: intake writes it on the Mac (agent.human_intake.write_steps, the admission lane's procedure) to
#    $D/steps/$ID.jsonl. Check it loads under the fit's reader and the pinned denylist before anything else reads it.
& $MAC ("cd $W; ID=$ID; D=$D`n" + @'
uv run --offline --locked --group execution python -c 'import sys; from policy.range_bc import steps; s=steps.load(sys.argv[1], denylist=steps.load_denylist()); print(s.session_id, s.split, len(s.rows), s.sha256)' "$D/steps/$ID.jsonl"
'@)

# 4. Cache, on the Mac only (rehearsed: 2 min of HEVC took 20 s). Refuses a changed video, wrong colour tagging,
#    another timebase or a pts that differs from the step table.
& $MAC ("cd $W; ID=$ID; D=$D`n" + @'
nice -n 10 uv run --offline --locked --group execution python -m policy.range_bc.cache "$D/steps/$ID.jsonl" "$D/caches/$ID" --video-root "$D/originals"
'@)
if ($LASTEXITCODE) { throw 'cache build failed' }

# 5. Dev carve-out, before the first fit: the lead names whole train recordings as dev (the group unit is one
#    recording). Record the list and never change it between the plumbing and the real fit. It is never validation.
#    $DEV = @('<id>', ...);  $TRAIN = the other train-split recordings;  $VAL = the two dedicated validation takes.

# 6-8. Fits: one durable niced job each, on the Mac, waiting for its exit status (the pattern of "Next fit" step 3).
#    smoke:     --scope smoke    --train <train steps> --dev <dev steps> --epochs 1 --seeds 0
#    plumbing:  --scope plumbing --train ... --dev ... --epochs 20 --seeds 0            (dev curve; no --val)
#               the same again into a second --out (the repeatability check: compare the two checkpoints' sha256)
#               --lag 1 and --lag 2 runs; the scaling curve with --max-steps on nested recording subsets, 2 seeds each
#    then write $D/preregistration.json: {"epochs": <argmin of the seed-0 dev total loss in epochs_log>,
#               "weight_decay": 1e-4, "stride": 48 or 64, "hud_parity_sha256": <sha256 of the parity file>,
#               "source": "<plumbing report path and sha256>"}
#    real:      --scope fit --train ... --dev ... --val ... --preregistration $D/preregistration.json
#               --hud-parity <parity file> --epochs <as registered> --weight-decay <as registered> --stride <as registered>
$FIT = "$UV python -m policy.range_bc.train --cache-root $D/caches --device mps --out $D/runs/<name> <arguments above>"
& $MAC ("cd $W`n" + "print -r -- '$FIT >$D/runs/<name>.log 2>&1; echo `$? >$D/runs/<name>.exit' > $D/runs/<name>.sh`n" + @'
nohup nice -n 10 zsh $D/runs/<name>.sh >/dev/null 2>&1 & echo $! > $D/runs/<name>.pid
'@)
#    Report the result from <name>.exit, <name>.log and runs/<name>/report.json, never from the launch.

# 9. Return and verify on Windows CPU. Copy back the run directory, the validation step tables and their caches
#    (about 9 GB for two 12-minute takes: 43k anchors x 208 kB), then verify against the report hash read from the Mac.
$RS = (ssh -o BatchMode=yes mac "shasum -a 256 $D/runs/<name>/report.json").Split(' ')[0]
uv run --offline --locked --group execution python -m policy.range_bc.verify --run <local run dir> --set val `
    --steps <local val step tables> --cache-root <local caches> --report-sha256 $RS --out <local run dir>\windows-report.json
if ($LASTEXITCODE) { throw 'Windows verification failed' }
```

**Rehearsal notes:**
- **Login shell.** A non-login SSH shell on the Mac has no Homebrew `PATH` (`ffmpeg: command not found`). `mac.ps1`
  runs `zsh -l`, and so did the rehearsal (ssh with the script on stdin, from Git Bash).
- **Word splitting.** zsh does not word-split `$UV`, so `$UV python …` inside a zsh script fails. Use a function, or
  `uv run …` written out, as the blocks above do.
- **The video name** must keep its original base name, spaces included. The rehearsal renamed after `scp` and
  verified the hash; step 2's glob copy keeps the name, but check it.
- **Timing** for the 2 min, 940 MB HEVC take:

  | Operation | Machine | Time |
  |---|---|---|
  | Transfer | | 33 s |
  | Full-decode probe | Mac | 121 s |
  | Full-decode probe | Windows, under load | 327 s |
  | Cache build | Mac | 20 s |
