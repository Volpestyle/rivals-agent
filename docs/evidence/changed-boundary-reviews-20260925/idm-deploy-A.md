# Deploying pitch fix A in the IDM predictor, 2026-09-25 (VUH-1353)

Owner: the inverse-dynamics lane (scoreboard-fix). Reviewer: fit-review. Next consumer: gate 2 (replay pitch labels),
then the replay-label export. Brief: `brief-idm-deploy-A.md` (`d7021471…`).

- **What it does:** by default, `policy.idm.train._camera` now multiplies each row's total pitch std by A's k for the
  row's stated total yaw std, before the 1° / 3° pitch abstention bound. Every prediction, and the fit report, records
  `"pitch_std_calibration": "A-6f8dba7b"`.
- **What else changed in behaviour:** nothing.
- **State:** uncommitted in the PC checkout, on top of `aafd800`. No Linear, no game input, no Mac job: the Mac's
  queue2 is running, so nothing ran there.

## The change

**`policy/idm/train.py`:**
- **The constants:** `PITCH_STD_CALIBRATION = "A-6f8dba7b"`, `PITCH_STD_EDGES` (4 floats) and `PITCH_STD_K` (5 floats).
  The comment gives the params file's path and its sha256 `6f8dba7b04336c3fd4ce5dcd2acaa8b5a6e4578678643dedb7d942b1549bcff3`.
- **`pitch_std_k(yaw_std)`:** `PITCH_STD_K[bisect.bisect_right(PITCH_STD_EDGES, yaw_std)]`, so a value on an edge goes
  to the upper bin, as in `pitch_fix3.apply`.
- **`_camera`:** the pitch axis's total std becomes `std * pitch_std_k(out["yaw_std_deg"])`, and the unchanged bound
  check follows it. The yaw axis is computed first and is untouched. `out` gains the marker.
- **`_abstain_all` and `_camera`'s no-gain early return** also carry the marker, so every prediction dict has it and an
  abstained row stays equal to `_abstain_all()`.
- **`run_fit`:** the report's `abstention` gains `"pitch_std_calibration": {"name", "yaw_std_edges", "k"}`.
  `REPORT_REQUIRED` is unchanged.
- **The module docstring's predictor paragraph** says this.

**`tests/test_idm_model.py`** (the IDM execution-group file), four new tests and one new assertion:
- **`test_pitch_fix_a_is_pinned_to_the_landed_parameters_not_re_derived`:** the landed
  `docs/evidence/idm-beta-nll-20260925/pitch_fix3-params.json` hashes to `6f8dba7b…`, since its bytes are `-text` in
  git and identical on every checkout. Its key "A" equals `PITCH_STD_EDGES` and `PITCH_STD_K` exactly; the marker is
  `"A-" + sha[:8]`; and `CAMERA_ABSTAIN_STD` is still the bounds A was judged on.
- **`test_pitch_std_k_bins_by_the_stated_yaw_std_and_a_value_on_an_edge_goes_up`:** each edge maps to the upper bin,
  and the float just below it to the lower bin.
- **`test_the_camera_answer_applies_pitch_fix_a_exactly_as_confirmed`,** the equality on a small fixture:
  - it runs a grid of 14,760 (mu_yaw, mu_pitch, logvar_yaw, logvar_pitch) that reaches all five yaw-std bins, both
    predicted regimes, and pitch answers that A turns into abstentions in both regimes;
  - `_camera` equals a verbatim copy of `pitch_fix3.apply` over the pre-A answer (`PITCH_STD_K` monkeypatched to ones),
    bit for bit;
  - yaw, yaw std and the regime are unchanged; A never un-abstains a row.
- **`test_every_prediction_is_marked_and_pitch_fix_a_leaves_yaw_press_and_the_regime_alone`:**
  - through `predict()` with a frameless row, every prediction carries the marker, including `_abstain_all` rows;
  - every key except the two pitch keys (`yaw_deg`, `yaw_std_deg`, `gain_regime`, `press`) is identical with A on and
    off;
  - pitch std equals the pre-A std times `pitch_std_k(yaw std)`, and at least one pitch answer becomes an abstention.
- **The existing end-to-end `run_fit` test** now also asserts the report's `abstention.pitch_std_calibration`.

**`docs/lanes/inverse-dynamics.md`:** a "**Deployed (2026-09-25, pending fit-review)**" paragraph, inserted after the
confirmation's Result and before "### The edge head's input".

`git diff --stat`: 3 files, 132 insertions, 7 deletions. The 7 deletions are all in `train.py`: the docstring line,
the `_camera` docstring, and the `_abstain_all`, early-return, `out =` and `abstention=` lines, each changed in place.
The lane doc is a pure insertion (0 deletions). The full diff is `handoff\idm-deploy-A\idm-deploy-A.diff`.

## Acceptance 1–2: equality with what was confirmed, and everything else unchanged

**How it was shown:** from the stored values. No inference was re-run, because hud-review's queue2 has the Mac.
- **The inputs:** the stored raw `mu_yaw`, `mu_pitch`, `logvar_yaw` and `logvar_pitch` of **all 21** confirmation
  prediction files (`handoff\idm-pitch-confirm-state\`, hashes as landed in `aafd800`).
- **Also read:** each row's `t0_ns` / `t1_ns`, and each session's calibration from its target file.
- **The harness** is `handoff\idm-deploy-A\deploy_equality.py`. It ran on the PC in a private `UV_PROJECT_ENVIRONMENT`
  (execution group) and calls the deployed `TR._camera` exactly as `predict()` and `diag_predict_ckpt.py` do.

| Check, over 1,182,958 rows (21 files) | Result |
|---|---|
| Deployed `pitch_std_deg` = `pitch_fix3.apply(pre-A rows)["std_pitch"]` | **0 mismatches** |
| Deployed `pitch_deg` (answer or abstention) = `pitch_fix3.apply(...)["ans_pitch"]` | **0 mismatches** |
| `yaw_deg` and `yaw_std_deg` identical with A on and off | **0 mismatches** |
| `gain_regime` identical with A on and off | **0 mismatches** |
| Marker `A-6f8dba7b` on every row | **0 missing** |
| Deployed pitch answer or abstention = `pitch_fix3.apply` on the **stored Mac values** | **0 mismatches** |

- **What "pre-A rows" means:** `_camera` with A switched off (`PITCH_STD_K` = ones), on the same platform. The harness
  compares with `apply` both on that and on the stored values.
- **The platform caveat,** stated because it is not zero:
  - the PC's pre-A recomputation matches the Mac's stored stds exactly on 99.48 % of rows;
  - **6,096 rows (0.52 %) differ by at most 2 ulp** (for example, 31 of 13,188 rows in one 025230 file, each by 1 ulp);
  - every answer, abstention and regime still matches the stored values (0 differences);
  - **the cause** is `math.exp` rounding differently in the Mac's arm64 libm and Windows' libm. A probe showed that
    `math.e ** x` fixes a quarter of the yaw-std differences, which fits exp, not the rule.
  - So the code equals `apply` exactly. Byte equality against the Mac's stored stds needs the harness run on the Mac,
    which is a CPU-only minute once queue2 ends, if fit-review wants it.
- **Press:** press probabilities and their abstentions are not in the stored files at full precision (`prob` is
  rounded to 6 digits). So press is shown unchanged by the test through `predict()` (identical with A on and off) and
  by the diff, which touches no press code.

**Mutation check:** with `pitch_std_k` forced to 1.0 through a pytest plugin (`handoff\idm-deploy-A\mutate_a_off.py`),
the three behaviour tests fail. The pin test still passes, as it should: it tests the constants.

## Acceptance 3–4: pins and the marker

- **Pins:** the constants are literal in the code, not read from or refitted on data. The pin test asserts them equal
  to the landed JSON's key "A" and the file's sha256.
- **The marker:**
  - `"pitch_std_calibration": "A-6f8dba7b"` is on every prediction dict: answered, abstained, frameless or without gain;
  - the fit report's `abstention` carries the name, the edges and the k.
- **No replay-label export exists today.**
  - `policy/range_bc/steps.py` defines only the reader contract for `source_kind: "replay"`;
  - `policy/range_bc/fixture.py` builds a synthetic replay source;
  - `scripts/replay_camera.py` fills camera from camera-motion, not the IDM;
  - nothing turns IDM predictions into replay steps (checked with `git grep`).
  - So nothing was changed there. The lane doc's Deployed paragraph and the docstring say that a future export must
    refuse IDM pitch without the marker, as fit-review's N3 asks.

## Acceptance 5: tests

| Run | Environment | Result |
|---|---|---|
| IDM files: `tests/test_idm_model.py`, `test_idm_decode.py`, `test_idm_eval.py`, `test_idm_targets.py` | `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/scoreboard-fix`, `uv run --offline --locked --group execution pytest …` | **83 passed**, exit 0 |
| The four new tests alone | same | 4 passed |
| stdlib suite | `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/scoreboard-fix-stdlib`, after `uv sync --offline --locked` (exact), `uv run --offline --locked pytest -q` | **1971 passed, 73 skipped**, exit 0 (5 min 10 s) |
| Lint | `uvx ruff@0.14.0 check policy/idm/train.py tests/test_idm_model.py` (the pre-commit pin) | All checks passed |

## Acceptance 6: the lane doc

- **New LF sha256:** **`a430f8fa9d34e734cd2eb950ff84eda1c2d8e444ec58d9575e154e1f28d78e99`**. It was `e326e2fa…`, as
  landed in `aafd800`.
- **What was added:** 12 lines, the "Deployed" paragraph at lines 1392–1402, plus its blank line.
- **Pins:** each occurs verbatim exactly once in the LF doc:
  - the confirmation section `a967962a`;
  - part A `42beb90e`;
  - calibration `e6b5d526`;
  - round 2 `5f94a529`;
  - round 3 `f1385679`.

## Acceptance 7: the freeze check

- **What the freeze holds:** `data/runtime/galacta-pilot-20260923-preflight/controller-deployed.json` and
  `perception-deployed.json` name 16 code files, plus one `code-receipt.json` reference: `agent/{brain, controller,
  intents, learned_range_skill, loop, startup, state, tracker}.py`, `perception/{hud, outline, scoreboard}.py`,
  `policy/{execution, range_policy, range_skill_policy}.py` and `scripts/{capture, record}.py`.
- **Result:** none of the three edited files is among them.

## Files

| File | Working-tree sha256 | LF sha256 |
|---|---|---|
| `policy/idm/train.py` | `b8415f819cad3c5fa5e3527196995cb6475c7dcbd6ef26f7d72da56f7f8c6ed5` | `b6e6fa44b5f8acb936e47a36d63a2509f4745b7fecfd547b88ec2646f2a7c080` |
| `tests/test_idm_model.py` | `273a044b7679a745e32ac1e3399272504170d8803060a786a9b0d38f8abf9c1c` | `273a044b7679a745e32ac1e3399272504170d8803060a786a9b0d38f8abf9c1c` (the working copy is LF; git warns it will write CRLF on the next checkout, and the blob is LF either way) |
| `docs/lanes/inverse-dynamics.md` | `cbcd7051cad3de59b002dba7d6b25e197fc4a01c62102031209c6239375c8085` | `a430f8fa9d34e734cd2eb950ff84eda1c2d8e444ec58d9575e154e1f28d78e99` |

**Supporting files** (`handoff\idm-deploy-A\`):

| File | sha256 |
|---|---|
| `deploy_equality.py` | `f5b7159b07aad13b429dfda04d344cbef4fa79185950bc96cea81665faf333ee` |
| `deploy_equality-out.txt` (per file and total) | `14f260c4fd7eb401964804d8808a858c2809aaae77ed74c0f876582780bb8080` |
| `mutate_a_off.py` (the mutation plugin) | `b36246a8db598e89e1369f7d965016dea2abde55d2a2fe932b12e062351ceb4c` |
| `idm-deploy-A.diff` (`git diff` at hand-back) | `16f6bd909a84e48c98883fa8932579bce511ce827b4a111c6032297884a77d74` |

**The inputs read** are the 21 prediction files (hashes in `docs/evidence/idm-beta-nll-20260925/idm-pitch-confirm.md`)
and the target files `data/idm/targets/` 232304 `8b00217a…`, 021320 `ec367594…` and 025230 `5c815469…`, each only
for its header's calibration.

## Limitations

- **Equality was shown on the PC.** Against the Mac-made stored values, 0.52 % of rows differ by at most 2 ulp in the
  stds, from platform libm `exp`. No answer, abstention or regime differs.
- **What changes for downstream code:**
  - `gate1()`'s `model_std_coverage` for pitch, and every new Gate 1 report, now state A's std and abstention (the
    intent);
  - existing checkpoints' reports are unchanged, and re-scoring one with this code gives A's pitch figures;
  - `code_closure` hashes change for any new fit, because `train.py` changed.
- **The yaw-std bins use the total yaw std** (model plus label sigma), exactly as `apply` read `std_yaw` from
  `_camera`'s output. That is by construction, not a new choice.
