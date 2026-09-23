# Review: the cohort fit driver and Windows verifier (VUH-1346), read-only

**Reviewed** (all uncommitted in the shared checkout at `21db6c6`):
- `docs/evidence/range-request-human-fit-20260922/fit_cohort_20260923.py` (`eb6a8f10…`);
- `verify_windows_cohort_20260923.py` (`7c8aae34…`);
- the "Next fit" runbook in `docs/evidence/fit-readiness-20260923/README.md`;

against:
- the 09-22 `fit.py` (`6a3ff6b2…`) and 09-22 `verify_windows.py`;
- the manifest `james-request-cohort-ae648b33/cohort-manifest.json` (`c3f64979…`, `pending_v4_admission`) and the
  frozen members it names;
- the rehearsal output in `data/diagnostics/range-request-cohort-rehearsal-20260923/`.

**How it was run:**
- No fit was run anywhere and the Mac was not touched. Nothing in the repo was edited or committed, and nothing was
  written to Linear.
- The driver ran only in `--check` mode: on the real inputs (read-only), and on a scratch mirror of the repo for the
  tamper cases.
- My scripts and outputs are in
  `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\fit\`,
  called `fit/` below:
  - `tamper.py`: the mirror in `fit/tree/` and every tamper case;
  - `recompute.py`: the report sections and the checkpoint read;
  - `transfer.json`: the real 17 verified inputs.

## Verdict: approve with required fixes

**The mechanics are right:**
- Every data file is hash-checked before it is read, and a bad pin aborts before any row is built.
- The training call is byte-for-byte the 09-22 request fit.
- The cohort build matches the manifest's counts and identity through the real `validate()`/`cohort()`.
- The checkpoint and report carry the right provenance, and every new report section recomputes exactly.

**But the admission gate is weaker than the 09-22 fit it replaces:**
- It reads admission only from the manifest's own description of each member, not from the frozen artifact.
- A forged v4 examples packet, built from the real candidate rows, whose own status still says
  `candidate_only_not_admitted` and whose "review receipt" is another session's decision, is accepted. It builds
  the full 4,288-row cohort, equal to the manifest's joint counts.

**Three further holes:**
- every gate disappears under `python -O`;
- three imported modules escape the code check;
- the runbook runs commands taken from the manifest before checking the manifest's hash.

F1-F4 must be fixed before the real launch. All are small.

## Findings, most severe first

### F1 (high, required): admission is read from the manifest, never from the frozen artifact or its receipt

- `admitted()` (`fit_cohort_20260923.py:74-76`) tests only the member dict in the manifest: an `examples` key, no
  `candidate_rows`, and a status prefix.
- The packet checks (`:124-136`) never read the examples packet's own `status`. 09-22 `fit.py:35` did:
  `assert packet["status"] == "accepted_train_only_numerical_diagnostic"`.
- The review receipt is only a hash that rows must echo (`:135`). The driver never opens it, checks its decision, or
  ties it to this member.

**Failing inputs**, on the scratch mirror (`fit/tamper.py`, cases T4/T4b/T5):

| case | the artifact itself says | driver `--check` |
|---|---|---|
| **T4**: v4 member → `examples-FORGED.json`, built by `cohort.py`'s own recipe from the real `051828-request-timing-v4/candidate-rows.json`; packet `status` `candidate_only_not_admitted`; `review_receipt` = the **032454** session's train decision; top and member status renamed "admitted" | not admitted; receipt for another session | **exit 0: 108 + 4180 rows, 5 + 68 known, joint equals the manifest's `check`** |
| **T4b**: same, `--dry-run` on v4 alone | same | **exit 0, 4180 rows** |
| **T5**: member 0's packet `status` → `REJECTED_do_not_train`, manifest unchanged | rejected | **exit 0** |

Without `--check`, each of these would go on to fit.

**Required:**
- The packet's own `status` must begin "accepted"/"admitted" and contain no "candidate", "pending" or "reject".
- Open the (hash-verified) `review_receipt`:
  - require its `decision` to begin "accept"/"admit";
  - bind it to this artifact. For example, its `frozen_candidate` `{path, sha256}` must appear in the packet's
    `input_artifacts`. The 032454 receipt already carries `frozen_candidate`, so T4 would fail that binding.
- Refuse the all-zero placeholder review hash that `cohort.py` uses in memory.
- Also require `artifact_hashes["evidence_digest"]` (`:136` currently falls back to the packet's own value, a
  self-comparison).

### F2 (medium, required): every gate is a bare `assert`, removed under `python -O` or `PYTHONOPTIMIZE`

- In the driver, all of them are asserts: `verify()`, the manifest-hash check, admission, the code check, and the
  counts and identity checks (`:89-149`, `:195`, `:199`, `:219`).
- So are all the verifier's checks (`:28`, `:31`, `:38`, `:44-47`, `:53-69`).

**Failing inputs**, on the real inputs, read-only:
- `python -O -B fit_cohort_20260923.py --manifest <real> --manifest-sha256 000…0 --check --dry-run 20260922T032454-642Z-24328-1`
  → **exit 0, "verified_inputs 1"**. With asserts on, the same command stops at
  "cohort manifest differs from its pinned sha256".
- `PYTHONOPTIMIZE=1` with the real pending manifest and no `--dry-run` → the pending and admission checks are
  skipped. It crashed only on `KeyError: 'examples'`, because v4 has no examples artifact yet; once it has one, it
  would be admitted.

**Required:**
- Use an explicit raise. `policy.execution.require` already exists.
- Or, as the first statement of both scripts, `if sys.flags.optimize: raise SystemExit("gates need asserts")`.

### F3 (medium, required): the code check covers 4 of the 7 repo modules the driver runs, and checks them after executing them

- The driver imports policy code at `:32-36`, before any check.
- Its runtime closure on the real inputs was `agent/__init__.py`, `agent/human_demos.py` (imported by
  `policy/execution.py`), `agent/state.py`, `policy/__init__.py`, `policy/execution.py`, `policy/range_policy.py`
  and `policy/range_skill_policy.py`.
- `SNAPSHOT_CODE` (`:39-40`, checked at `:119-120`) covers four of them.

**Failing inputs** (T7, scratch mirror, one appended `print` line each):

| modified file | result |
|---|---|
| `agent/human_demos.py` | **exit 0**: accepted, and the injected code ran |
| `policy/__init__.py` | **exit 0**: accepted, and the injected code ran |
| `agent/__init__.py` | **exit 0**: accepted, and the injected code ran |
| `policy/range_policy.py` (checked) | refused ("differs from the cohort's code snapshot"), but its injected code **ran first**, at import |

In fit mode, a modified `human_demos.py` would run during training, undetected. `python -B` also does not stop
Python from reading an existing stale `__pycache__`.

**Required:**
- Verify every file in the import closure against the snapshot, which already carries blobs for all of them.
- Do it before importing the policy code: a stdlib-only preamble compares blobs, then imports.
- For example, check every `sys.modules` entry under `ROOT` after import, as a second guard.

### F4 (medium, required, runbook): step 1 executes commands from the manifest before the manifest's hash is checked

- README "Next fit", step 1 (around line 152) reads `(Get-Content $M | ConvertFrom-Json).members.freeze_check` and
  runs each string with `uv run … @a`.
- It then runs `cohort.py --check`.
- Only after both does it run the driver, which is the first thing that compares `$M` with `$MS`.
- **Failing input:** any manifest at `$M` whose `freeze_check` is, say, `python -c "<anything>"` runs that code on the
  PC before any pin is checked.

**Required:** make the first line of step 1:
`if ((Get-FileHash -Algorithm SHA256 $M).Hash.ToLower() -ne $MS) { throw 'manifest differs from $MS' }`.
Or hard-code the two freeze commands.

### F5 (low): the verifier trusts the command line for the torch pin

- `verify_windows_cohort_20260923.py:56` never checks `torch.__version__` against `mac["torch"]` (`2.14.0`).
- The pin exists only as `--with torch==2.14.0` in the runbook.
- Add `assert torch.__version__.split("+")[0] == mac["torch"]`, as a real check per F2.
- The rehearsal did run 2.14.0+cpu.

### F6 (low): one refusal is an accident, not a check

- Pointing v4's `examples` at `candidate-rows.json` (T3) is refused by `KeyError: 'files'` (`:128`), because v4's
  `artifact-hashes.json` has a different schema. It is not refused by a designed test.
- The format assertion two lines later would also catch it.
- Once F1's packet-status check exists this is moot. Still, `:128` should fail with a message.

## The downstream question the brief asked: is it the 09-22 fit?

**Yes, with no retune.** Diffed against `fit.py`:
- `CONFIG = dict(epochs=100, batch_size=2, lr=.01, device="mps", seed=7)` (`:44` vs `fit.py:56`);
- `Spec(hidden=8)`, with confidence 0.7 as the `Spec` default (`:45` vs `:57`);
- `torch.set_num_threads(4)`, MPS required with no CPU fallback;
- `train(examples, spec=SPEC, **CONFIG)` (`:204` vs `:61`), and the same `train()` signature
  (`range_skill_policy.py:493`);
- the same row constructor (`example()` `:79-83` vs `fit.py:37-41`);
- the same save, CPU reload, `names == cpu_names` and `delta < 1e-5` (`:213-219` vs `:74-79`).

**The only differences:**
- three extra metadata keys in `training_config` (manifest sha, driver sha, dry-run member);
- the added report sections;
- rows concatenated in manifest member order, which is deterministic.

Weights: the owner reports the dry-run weights bit-identical across runs. I could not check that on Windows (MPS),
and did not try.

## Items settled

**1. Hash-checked before read: confirmed for data; see F3 for code.**
- The manifest hash is checked before it is parsed (`:89`).
- For each selected member, every `{path, sha256}` in the member entry (`:109-110`) and every pin (`:111-112`) is
  verified before the snapshot and packet are read.
- Every `{path, sha256}` in each examples packet (`refs`, rows excluded) is verified (`:125-126`) before any row is
  built (`:133`).
- Conflicting pins are refused (`:94`).
- **T6**, one byte appended to `source-profile.json`, `dependencies.json` (a packet ref), the member `examples.json`
  or the snapshot manifest: each **aborts with "hash mismatch"** before any row.
- A zero manifest sha is refused.

**2. The manifest-level rule: confirmed** (it is not sufficient; see F1).

| case | result |
|---|---|
| the real pending manifest, no `--dry-run` | refused |
| status "Pending" (case) | refused |
| top status "admitted" while v4 still has `candidate_rows` | refused |
| v4 status "accepted v4" but still `candidate_rows` | refused |
| `--dry-run` naming v4 | refused ("not admitted") |

- `--dry-run` on 032454 reads exactly one member: 16 inputs; the skipped member is listed.

**3. The 09-22 fit:** see above. No retune.

**4. The code identity check.**
- The four `SNAPSHOT_CODE` blobs, compared EOL-insensitively to the pinned `manifest-ae648b33.json` (whose `commit`
  must equal `perception_commit`), refuse a modified `policy/range_policy.py`.
- Gaps: F3.

**5. The cohort build: confirmed.**
- The real `--check --dry-run 20260922T032454-642Z-24328-1` gives 108 rows, 5 known, [4, 1], evidence digest
  `e66b6fec…` (equal to the packet and its `artifact-hashes`), and a SourceIdentity equal to `check.source_identity`.
- The rows pass the real `validate()`/`cohort()`.
- T4 exercised the full joint on the real v4 rows: 4,288 rows, [39, 34], 34 unique events, equal to `check.joint`.
  So the counts gate works, but it is not an admission gate (F1).

**6. Checkpoint and report: confirmed** (`fit/recompute.py`).
- `run-1/model.pt` is `682d81f1…`, as reported.
- Its `training_config` holds the 09-22 config and spec, plus `cohort_manifest_sha256` `c3f64979…`, `driver_sha256`
  `eb6a8f10…` and `dry_run_member`.
- `code_sha256` is `d6b62274…`, `data_sha256` is `e66b6fec…`.
- The driver copy in the run directory has the same sha.
- **Every report section recomputes exactly** from the report's own probabilities and independently rebuilt rows:
  - model and CPU-reload metrics, confidence-filtered (threshold 0.7, 0 refusals), ammo and never-start baselines;
  - per-session metrics, coverage, and label reproduction (5/5);
  - the same-ammo contrast groups: one group, ammo (3,3,3,3,3), 137 no-new against 141 start. The other three known
    rows have unique histories and are correctly omitted.
- The CPU delta is 2.79e-9.
- `identity_code_check`, recomputed from the git blobs at `21db6c6`, is equal: the source identity matches the CRLF
  form.

**7. The Windows verifier: sound, apart from F2 and F5.**
- It pins `mac-report.json` by sha, then checks the driver copy (LF-normalized) against the Mac's driver sha.
- It re-hashes every input the Mac listed, and requires each recorded code file to equal the git blob at the Mac's
  commit, with a CRLF-only difference allowed for `agent/state.py` alone (the LF requirement).
- It re-runs the driver's `load()`, including the snapshot code check.
- It reloads the exact checkpoint on CPU, and requires equal predictions, delta < 1e-5 and metrics equal to the Mac
  CPU reload.
- It writes its report exclusively; failures exit 1 (with asserts enabled).
- **The rehearsal's `windows-report.json`** (`e90c8300…`) pins `f8dd25e7…` (the Mac report), ran torch 2.14.0+cpu, and
  has identical predictions, equal metrics and a 1.16e-9 delta.

**Runbook step 3.**
- `mac.ps1` prepends `set -e`, so the clean-worktree test and `merge-base --is-ancestor` do stop the script.
- The transferred files are hash-checked on the Mac before the fit.
- A failed fit leaves at least `mac-report.json` missing (the report is the last write), so the closing `shasum`
  fails the call.

## Inputs changed during this review (07:27-07:28)

The admission lane wrote a new `james-request-cohort-ae648b33/cohort-manifest.json` (`37cf57a2…`, status `admitted`),
with a v5 member and `051828-v5-admitted-examples.json`. It moved the manifest I reviewed aside, unchanged, as
`cohort-manifest-pending-v4.json` (`c3f64979…`). Everything above is against `c3f64979…` and driver `eb6a8f10…`.

- **The reviewed driver refuses the new manifest** (`--check`, read-only):
  `AssertionError: member 20260922T032454-642Z-24328-1 is not admitted`.
- **Why:** the new members carry a `files` list instead of `examples`/`artifact_hashes`. Member 0's status now
  begins "accepted labels re-measured…" but has no `examples` key, so `admitted()` fails.
- **So the driver, the manifest, or both must change before launch.** That change needs a delta review against F1-F4.
- **For F1 in particular:** the new v5 member lists `candidate-rows.json` beside the admitted examples in one
  undifferentiated `files` list. The driver must know which file is the admitted artifact, and must read that file's
  own status and receipt. It must not infer admission from the list.

## Delta

Bounded check of the fix round (`fit-runner-final-2.md`), read-only.

**Reviewed:**
- driver `3c90e9419376593c…`;
- verifier `f01efa194f7de3cd…`;
- the "Next fit" runbook (`6743be60…`);

on `main` at `4553072`, against the admitted manifest `bcaa1cf4…`.

**How it was run:**
- No fit ran, the Mac was not touched, nothing in the repo was edited, and nothing was written to Linear.
- The driver ran in `--check` mode only: on the real inputs, and on a fresh scratch mirror for tampering.
- The verifier ran on scratch copies of the rehearsal4 run directory (it resolves `--run` as `ROOT / args.run`, so an
  absolute scratch path writes nothing to the repo).
- Scripts and outputs are in `…\scratchpad\fit2\` (`tamper2.py`, `mech.py`, `transfer.json`).

### Verdict: approve with required fixes

- Everything the lead asked me to confirm holds.
- Every round-1 tamper case now refuses before any repo code runs.
- The fit is the 09-22 fit.
- The dry-run weights are bit-identical to `682d81f1…`.

**One required fix, F7, from my new attack:**
- For the v5 (`lead_admission_decision`) schema, the receipt binds the packet to the lead-admitted artifact only by
  aggregate counts, never by row content.
- A packet whose admitted rows differ from the admitted `candidate-rows.json` is accepted.
- The real v5 packet does equal that artifact row for row (checked below), so no data is wrong today. The gate is
  what fails.

### F7 (medium, required): the v5 receipt binding does not bind row content

**The gap:**
- `admission()` (`fit_cohort_20260923.py:143-161`), for the `lead_admission_decision` schema, checks three things:
  - the receipt names this session, group and split, and is train-only;
  - `admitted_artifact` equals the packet's `source_artifact`;
  - the bound file's rows are all this session's, and `counts` (starts, controls, coordinates) equal the packet's.
- Nothing compares the packet's rows with the admitted artifact's rows. The manifest's `check.per_member` for
  `bcaa1cf4…` carries no evidence digest, and the packet's and hashes file's digests are self-issued.

**Failing input:**
- Scratch mirror, `NEW-admitted-start-features-altered`.
- In the admitted v5 packet, admitted start **grid 39** (the full-ammo Luna rise) has its web-ammo history changed
  from `[5, 5, 5, 5, 5]` to `[0, 0, 0, 0, 0]`.
- Labels, counts, packet status, receipt and `source_artifact` are untouched. The packet's evidence digest and the
  hashes file are recomputed.
- The admitted `candidate-rows.json` (`bc605bf9…`) still says `[5, 5, 5, 5, 5]` for grid 39.
- **Result: exit 0, 108 + 4180 rows, joint [39, 37].** The feature the policy work turns on (full-ammo onset) would
  train on values the lead never admitted.
- Control: dropping one admitted control instead (`NEW-b`) is refused ("counts differ from the receipt's"). The
  binding catches count changes, not content changes.

**The fix is feasible, and the real data passes it.** On the real packet `ffec1633…`:
- all 412 rows of the admitted `candidate-rows.json` equal the packet's rows at the same grid index, on every
  `request_example_fields` value (except review provenance), on `history`, and on the label mapped through
  `request_example_mapping`;
- the other 3,768 rows are all unknown with empty history;
- the packet's grid equals `coverage.json`'s grid (4,180).

**Required, in stage 1 (stdlib, JSON equality):**
- Require exactly the checks above for the `lead_admission_decision` schema.
- Walk and hash-verify the receipt's own `{path, sha256}` references first. `coverage.json` (`c6e701b4…`), named
  only in the receipt's `admitted_artifact`, is not among today's 21 verified inputs.
- Make the label binding mandatory per schema: `known_labels` for `decision_receipt`, row equality for
  `lead_admission_decision`. Today both are conditional on the field's presence (`:155`, `:157`).

**Recommended, for the re-measured schema:**
- Its features differ from the original by design, so only labels are bound today.
- The packet already lists `remeasurement.unchanged_fields`. Requiring those fields to equal the `of_artifact`'s rows
  would bind everything except the re-measured features.

### (1) The round-1 tamper cases, re-run against `3c90e941…`: all refused before any repo code runs

- **Method:** fresh mirror of the code and the 21 inputs the real `--check` verified. Each case ran under
  `-X importtime`, and the column below lists every `agent`/`policy` module imported before exit.
- The accepted baselines show exactly the seven closure modules, so "none" is meaningful.

| case | result | repo code imported | injected code ran |
|---|---|---|---|
| T0a dry run 032454 / T0b full admitted | accepted: [4, 1] / + [35, 36] | the 7 closure modules | no |
| **T4** v5 packet, status `candidate_only_not_admitted`, 032454 receipt | refused: packet status | none | no |
| **T4b** same, `--dry-run` v5 | refused: packet status | none | no |
| **T4c** status `admitted_train_only`, 032454 receipt, its `input_artifacts` copied | refused: receipt's bound artifact belongs to another session | none | no |
| **T5** member 0 packet status `REJECTED_do_not_train` | refused: packet status | none | no |
| **`-O`**, manifest sha `000…0` | refused: run without -O | none | no |
| **`PYTHONOPTIMIZE=1`**, admitted manifest | refused: run without -O | none | no |
| **T7** `agent/human_demos.py`, `policy/__init__.py`, `agent/__init__.py`, `policy/range_policy.py` (each + `print`) | refused: differs from the code snapshot (each) | none | **no** (before, each ran) |
| F6 `artifact_hashes` → v5 source hashes, which do not pin the examples | refused with its message | none | no |

### (2) Stage 1, the bytecode redirect and the module checks: confirmed

**Stage 1 (`:166-212`):**
- Standard library only.
- `Inputs.json` refuses to read any file whose hash was not checked first.
- All seven `CLOSURE` modules are compared as source bytes (EOL-insensitive git blobs) with the pinned `ae648b33`
  snapshot before `import_policy` runs (`:196-197`).

**Bytecode redirect** (`:236-237`, T8):
- An unchecked-hash `.pyc` of a tampered `range_policy.py`, beside intact source, is **not executed** by the driver.
  The run is accepted and the injected line never prints.
- A plain `import policy.range_policy` in the same mirror **does** run it.

**Post-import check** (`check_loaded`, `:215-231`, T9):
- A repo module outside the closure (`agent/tracker.py`), loaded before stage 2 via `sitecustomize`, is refused:
  "loaded module agent/tracker.py is outside the verified code closure".
- The post-fit check (`:352`) is the same function after reload. It was not exercised, since no fit was run.

**Exemptions:**
- As narrow as claimed: skip only a non-absolute or non-existent `__file__`, and the main module by identity
  (`:225`), which also covers the `__mp_main__` alias as the same object.
- **Note (low):** T9b shows the relative-`__file__` exemption can hide that same non-closure module, when the code
  that loaded it also rewrote its `__file__`. That needs code already running in the interpreter, so it is not a
  practical hole.
- Suggestion: consult `module.__spec__.origin` before exempting.

### (3) The fit path and the weights: confirmed

**Training call:** unchanged from 09-22 `fit.py`:
- `CONFIG` identical;
- `P.Spec(hidden=8)`, confidence 0.7;
- `set_num_threads(4)`, MPS required;
- `P.train(examples, spec=spec, **CONFIG)`;
- the same `save_checkpoint` arguments;
- the same CPU reload with `names == cpu_names` and delta < 1e-5.

**Checkpoints:** `682d81f1…` (round-1 rehearsal) against `04bca0af…` (rehearsal4), loaded with torch 2.14.0:
- all six weight tensors are `torch.equal`;
- every other payload field is identical;
- `training_config` differs only in `cohort_manifest_sha256` (`c3f64979` → `bcaa1cf4`) and `driver_sha256`
  (`eb6a8f10` → `3c90e941`).

**Reports:** differ only in `checkpoint_sha256`, `code_closure_git_blobs` (new), `cohort_manifest`, `driver`,
`fit_seconds`, `git_commit`, `input_artifacts` and `members` (now with `admission`). Every metric block and every
known row is identical.

### (4) F4, F5, F6: confirmed

**F4.** Runbook step 1 (`:196-201`):
- It begins with `Get-FileHash $M -ne $MS → throw`.
- No command is taken from the manifest's content.
- `cohort.py --check` runs after the driver has verified its pin.
- `unzip -o` is followed by the Mac-side hash check of every transferred file.

**F5.** The verifier gates the torch version (`verify_windows_cohort_20260923.py:70`). On a scratch copy of the
rehearsal4 run with the report's torch set to `2.99.0`: "refused: torch 2.14.0+cpu is not the Mac's 2.99.0".

**The rest of the verifier**, on scratch copies:
- `-O`, `PYTHONOPTIMIZE=1` and a wrong `--mac-report-sha256` are each refused before anything is written.
- The positive run exits 0, and its `windows-report.json` is identical in every key to the rehearsal4 one.
- It executes exactly the driver bytes it hash-checked (`:43-47`).

**F6.** Refused with a message: "… does not pin …" (`fit_cohort_20260923.py:203`).

### Also confirmed

- The new driver accepts the real admitted manifest `bcaa1cf4…` in `--check`:
  - 032454: 108 rows, 5 known, [4, 1], `decision_receipt`, re-measured from the accepted `bd6cf4cb…`;
  - v5: 4,180 rows, 71 known, [35, 36], `lead_admission_decision`;
  - joint [39, 37], 37 events, 21 verified inputs.
- The lead's F1 decision (per-schema equivalents) is implemented as described (`:105-163`):
  - the re-measured status is admitted only through `remeasurement.of_artifact` (accepted, hash-pinned, same receipt);
  - v5 requires `kind`, train-only, session/group/split, and `admitted_artifact` equal to `source_artifact`;
  - both schemas refuse the placeholder receipt, require every row to carry the receipt, `reviewed_human` and the
    member identity, and require evidence digests with no fallback.
- Its binding is weaker than its intent only as F7 describes.

## Delta 2

Final bounded check of F7 (`fit-runner-final-3.md`), read-only.

**Reviewed:**
- driver `f9f158fcc9abaa8f…`;
- verifier unchanged, `f01efa194f7de3cd…`;
- runbook `7fa487010a0146af…`;

on `main` at `4553072`, against manifest `bcaa1cf4…`.

**Scope of the change:** diffed against the `3c90e941…` driver I reviewed last round, only `admission()` changed. It
adds `by_grid()` and `lead_rows_bound()`, and the `REVIEW_PROVENANCE`/`REMEASURED` constants. The training path is
untouched.

**How it was run:**
- No fit ran, the Mac was not touched, and nothing was edited in the repo or written to Linear.
- Every case ran in `--check` mode on a fresh scratch mirror under `-X importtime`.
- Scripts are in `…\scratchpad\fit3\` (`tamper3.py`, `transfer.json`, `transfer-dry.json`).

### Verdict: approve with one required fix (F8), small

- Everything the lead listed holds.
- F7's binding refuses every forgery I aimed at it, before any repo code runs.
- The real `--check` and the dry-run weights are as stated.

**My forgery against the new binding succeeded on the one field it leaves unbound:**
- the re-measured 032454 member's `history`, exempt by design;
- yet the packet pins a re-measurement report that records exactly those histories.

**On the fix:**
- The real packet already matches that report, so the fix changes nothing for the launch data.
- If the lead prefers to accept the exemption as the design, record that decision and this becomes approve.

### F8 (medium, required unless the lead accepts the exemption): re-measured features bind to nothing

**The gap:** `admission()` (`fit_cohort_20260923.py:164-170`) binds the re-measured 032454 packet to the accepted
original on every field except `REMEASURED = {source, history, anchor_target_track}` (`:49`). So nothing checks the
features the model trains on for those five labels.

**Failing input** (`X-remeasured-grid137-ammo-altered`):
- In the 032454 packet, grid 137 (no-new-start; the no-new half of the only same-ammo contrast pair, 137 against
  141) has its web-ammo history changed from `[3, 3, 3, 3, 3]` to `[0, 0, 0, 0, 0]`.
- Labels, every other field, the receipt and the re-measurement block are untouched. The packet digest and its
  `artifact-hashes` are recomputed.
- **Result: accepted, exit 0**, in the dry run (108 rows, [4, 1]) and in the full check (4,288 rows).
- The pair that lets the model tell ammo from intent would no longer share an ammo history.

**The record to bind to exists and is pinned:**
- The packet's `remeasurement.report` (`remeasure/ae648b3/report.json`, `37c813f3…`, hash-verified today) holds
  `rows[].new_history` for exactly the six rows with history: 137, 141, 144, 198, 200 and 206.
- On the real inputs:
  - all six packet `history` values equal the report's `new_history`;
  - every other row's history is `[]`, equal to the original's;
  - every row's `source` equals the report's `source_identity`.

**Required, in stage 1:**
- Each re-measured row's `history` must equal the report's `new_history`, and rows absent from the report must keep
  the original's history.
- `source` must equal the report's `source_identity`.
- `anchor_target_track` has no counterpart in the report (it records `anchor_body: same_box`). It can stay exempt,
  since it is not a model feature.

### Confirmed

**F7's cases refuse before any repo code runs.** Each ran under `-X importtime`; the "none" column is meaningful,
because the accepted baselines import exactly the seven closure modules.

| case | result | repo code imported |
|---|---|---|
| **NEW-a**: admitted start grid 39 ammo `[5,5,5,5,5]` → `[0,0,0,0,0]` (was accepted at `3c90e941…`) | refused: grid 39 differs from the lead-admitted row | none |
| **NEW-b**: admitted control grid 36 dropped, manifest counts updated | refused: grid 36 differs from the lead-admitted row | none |
| one byte appended to v5 `coverage.json` | refused: hash mismatch | none |

**The receipt's own references are hash-verified before its content is used** (`:178-180`). The receipt is read only
after its own hash is checked, and its references are verified before `decision`, `admitted_artifact` or
`known_labels` are read.

| mode | verified inputs | coverage.json | new since last round |
|---|---|---|---|
| full | **27** | included | `coverage.json`; the v1 and v4 reviews; 032454 v1 `artifact-hashes.json` and `request-evidence.json`; `skill-events/…/source-profile.json` |
| dry run | **19** | — | |

**`lead_rows_bound()` (`:113-135`) enforces every rule stated.** Each probe was refused in stage 1 with the binding's
own message and no repo code imported:

| rule | probe | refused with |
|---|---|---|
| exact key set | an extra key on admitted row 39 | "grid 39 differs from the lead-admitted row" |
| `source` equals `source_identity` | row 39's `source.cooldown_regime` changed | "grid 39 differs…" |
| every `request_example_fields` value | row 39's `anchor_t` moved 0.1 s | "grid 39 differs…" |
| the other rows are unknown with empty history | an unknown row given row 39's history | "grid 14 is not an unknown row of the admitted coverage" |
| `coverage.json`'s reason | an unknown row's `reason` edited | "grid 19 is not an unknown row…" |
| the grid equals `coverage.json`'s, in order | two unknown rows swapped | "packet grid is not the admitted coverage grid" |

- Label and `label_known` equal to `coverage.json` are enforced for every row (`:131-132`).
- The 412 admitted rows are bound on history and on the mapped label (NEW-a above).
- All of this holds on the real packet.

**`known_labels` is mandatory for `decision_receipt`** (`:186-187`).
- Probe K1: a receipt without `known_labels`, with the original and the packet consistently re-pinned to it so that
  every other gate passes.
- Result: refused, "labels differ from the receipt's known_labels", with no repo code imported.

**The re-measured packet is bound row for row to the accepted original** on every field except `source`, `history`
and `anchor_target_track`, and `changed_fields` must lie within those three.
- Probe R1: grid 137's `raw_evidence` edited.
- Result: refused, "re-measured rows differ from the accepted artifact beyond the re-measured features".
- The gap in that exemption is F8.

**Real `--check`** on `bcaa1cf4…` (pin matched):

| mode | rows | known | bins | events | evidence digest | verified inputs |
|---|---|---|---|---|---|---|
| full | 4,288 (108 + 4,180) | 76 | [39, 37] | 37 | joint `86e5894b12d9a6bf…` | 27 |
| `--dry-run 20260922T032454-642Z-24328-1` | 108 | 5 | [4, 1] | | `e66b6fec…` | 19 |

**Dry-run weights: bit-identical to `682d81f1…`.** Rehearsal5's `run-1/model.pt` (`3fea92c4…`), loaded with torch
2.14.0:
- all six weight tensors are `torch.equal`;
- every other payload field is identical;
- `training_config` differs only in `driver_sha256` (`eb6a8f10` → `f9f158fc`) and `cohort_manifest_sha256`
  (`c3f64979` → `bcaa1cf4`);
- the report differs only in metadata (`checkpoint_sha256`, `code_closure_git_blobs`, `cohort_manifest`, `driver`,
  `fit_seconds`, `git_commit`, `input_artifacts`, `members`). Every metric block and known row is identical.

**Unchanged and still sound:**
- the verifier (`f01efa19…`, confirmed in Delta 1);
- stage 1's closure check, the bytecode redirect and the post-import check;
- the runbook's hash-first step 1.

The low note on the relative-`__file__` exemption stands, optional.
