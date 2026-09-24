# Review: the IDM β-NLL camera loss behind `--beta-nll` (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-24. Read-only: no edits, no commits, no Linear, no game, no Mac. The
shared tree and the shared `.venv` were never used.

**Reviewed:**
- commit **`4e7f005`** on `idm/yaw-test-20260924`, parent `1df31e7`: `policy/idm/train.py` and
  `tests/test_idm_model.py`;
- the evidence: `idm-diag.md`, `idm-yaw-test.md` and `idm-yaw-test-2.md` on main;
- the pre-registered section "Yaw falsification test (2026-09-24)", which still hashes to its pin **`21e17dd95008ecf9`**
  up to the addendum.

**How I checked:**
- **Four private trees**, from `git archive` into my scratchpad, not a checkout:
  - `bn/base` = `1df31e7`;
  - `bn/changed` = `4e7f005`;
  - `bn/onmain` = main `580a32e` with `4e7f005`'s two files overlaid. Those files are unchanged on main since `1df31e7`,
    so this is exactly the rebased commit.
- **My own environments** from `uv.lock` (unchanged since `c2b8a25`), with `UV_PROJECT_ENVIRONMENT` in my scratchpad:
  - `venv-exec`: dev plus execution, torch 2.14.0+cpu;
  - `venv-stdlib`.
- Every run was at below-normal priority.
- **The commit was already in the local object store,** so no fetch was needed.

## Verdict: land behind the flag (default off)

- **Flag off:** the model is untouched. That covers the weights, every loss and every metric.
- **The term** is what the section pre-registers.
- **The evidence** reproduces independently, run for run.
- **Before the default flips:** the pitch cost (F2) and the calibration shift (F4) must be judged, not just reported.
  Nothing blocks landing behind the flag.

## 1. Flag off is a no-op for the model. The files carry two expected differences

**What I ran** (`bn/id/`), in each tree and in a fresh process, on identical synthetic inputs generated once from the
base tree's test helpers:
- **(a)** A real `run_fit` through `main` on full-scale stores: `--scope smoke --max-examples 16 --epochs 2 --seed 0`.
  `require_committed` was stubbed, because the exports are not git repositories.
- **(b)** `fit()` on the TINY fixture: 6 epochs, seed 3, batch 8.

| Check | `1df31e7` vs `4e7f005`, flag off |
|---|---|
| (b) trained `state_dict` sha256 | **identical** `272b6617…` |
| (b) per-epoch losses | **identical**: 1.0735 → −0.3738 |
| (a) checkpoint tensors | **identical**, every tensor `torch.equal` |
| (a) checkpoint `format`, `actions`, `config` and meta except `code_closure` | **identical** |
| (a) `gate1` block and `history` losses | **identical** |
| (a) checkpoint **file** sha256 | differs: `4ef1ff8d…` vs `afcf61e6…` |
| (a) `report.json` | differs in only 6 keys: timings, `checkpoint_sha256`, `code_closure["policy/idm/train.py"]` (`48a736aa` → `7de8a9e8`), and a new `camera_loss` |

- **The file difference is the closure, not the model.** The checkpoint embeds the code closure (review K1), so its bytes
  change whenever `train.py` changes.
  - The commit message's "a default checkpoint keeps today's bytes" is therefore inexact; the model's bytes are what it
    keeps (F1).
- **The report always gains `camera_loss`,** `{"kind": "gaussian_nll", "beta": null}` when off.
- **Flag on (sanity):** the loss and the checkpoint differ, the meta carries `camera_beta_nll: 0.5`, and the report
  carries `{"kind": "beta_nll", "beta": 0.5}`.

## 2. The term, and what it does to the gradients

**The change is the pre-registered one.**
- `nll = nll * var.detach() ** beta`, applied after the NLL is formed and before masking, on both axes.
- `var` is the same total variance the NLL uses: the model's `exp(logvar)` plus the label σ².
- β is refused outside (0, 1]. The lane runs use 0.5.

**Nothing else changed:**
- the diff touches only `loss_terms` (the new argument), `fit` (passing it through, plus the range check), `run_fit`
  (the meta key, only when set, and the report's `camera_loss`) and the CLI flag;
- masks, the NaN guard, abstention, `predict`, the edge head and every other report field are untouched;
- **the masked-NaN guard still holds with the flag on,** probed with a NaN target and a NaN σ in a masked slot: the
  loss and all gradients stay finite, and the masked axis gets exactly 0.

**The gradients, probed numerically against the plain loss** (error 1, σ 0.02, one known axis):

| logvar | v | ∂L/∂μ plain | ∂L/∂μ β-NLL | Ratio (= √v) | ∂L/∂logvar plain | ∂L/∂logvar β-NLL |
|---|---|---|---|---|---|---|
| −6 | 0.0029 | 347.4 | 18.6 | 0.054 | −149.1 | −8.0 |
| −2 | 0.136 | 7.37 | 2.71 | 0.368 | −3.17 | −1.17 |
| 0 | 1 | 1.000 | 1.000 | 1 | ~0 | ~0 |
| 2 | 7.39 | 0.135 | 0.368 | 2.72 | 0.432 | 1.175 |
| 8 (clamp) | 2,981 | 0.00034 | 0.0183 | 54.6 | 0.500 | 27.3 |

- **On the mean,** ∂L/∂μ goes from (μ − y)/v to v^(β−1)(μ − y) = (μ − y)/√v.
- **On the log-variance,** the gradient is only multiplied by √v; nothing flows through the weight.
  - Its stationary point is unchanged, v = E[(y − μ)²]: bisection finds exp(logvar) = 2.2500 against err² = 2.25 in
    both losses.
  - The variance still converges to the same place. Its effective step is √v times smaller where v < 1.
- **Can the variance still starve the mean?** Less, but yes.
  - The mean's gradient still falls as the variance grows, as 1/√v instead of 1/v.
  - At the logvar clamp (8), the mean keeps 1/55 of its gradient instead of 1/2,981. Only β = 1 would remove the
    coupling.
  - β = 0.5 was what the evidence tested, and it was enough on this fold (below).
- **The flip side:** β-NLL *shrinks* the mean's gradient where v < 1, by √v relative to the plain loss (×0.054 at
  logvar −6). It shifts weight from low-variance rows to high-variance ones.
  - The label-σ down-weighting of extrapolated rows (review S3) is square-rooted with it: the ratio between rows goes
    from v₂/v₁ to √(v₂/v₁).
  - This is the likely mechanism of the pitch cost in section 4.

## 3. The evidence reproduces, and the judge was applied as pre-registered

**Hashes.** Every file in the evidence tables matches, in full:

| Run | Checkpoint | `report.json` |
|---|---|---|
| C1 | `3799fe46…d9` | `fba0d320…f2` |
| C2 | `855885bf…4b` | `73728862…ad` |
| T | `17e2eee8…fc` | `78100f7f…24` |
| T1 | `bc82a2a4…32` | `e7dcfd85…2f` |
| T2 | `a85a1530…d9` | `92dfeef4…20` |
| `loso-051828` | `11d0b912…0c` (the pre-registered checkpoint) | `7249186c…` (the landed evidence copy) |

- `analyse.py` `0ed5569b…`, `judge_yaw.py` `adab45be…` and `judge_yaw2.py` `d63d4427…` match, and so do all ten
  per-row prediction files.

**Settings.** All six reports have:
- 3 epochs, scope `gate1-dev`, MPS, 144,932 train examples;
- the pre-registered target files (`2e89adf3`, `42732841`, `a32a7380`, `5d51f240`) and store manifests (`457637aa`,
  `8780ea7c`, `a111ba07`, `14190df6`).

What differs between them:
- **Seeds:** as registered.
- **Code closure:** the plain runs have `train.py` `48a736aa` (`1df31e7`); the β runs have `7de8a9e8` (`4e7f005`).
- **`camera_loss`:** `beta_nll 0.5` on T, T1 and T2. The plain runs have **no** `camera_loss` key; `idm-yaw-test.md`
  says "null", which is cosmetic.

**The judge, recomputed independently** (`bn/judge/judge.py`):
- Truth comes from the target files, joined by row. There are **0** truth mismatches against the prediction files in
  every file.
- Raw-μ sign agreement is computed on moving rows (|true yaw| ≥ 0.5°; a zero prediction counts as disagreement),
  exactly `analyse.py`'s definition.

| Run | Loss | Seed | Held out (051828) | In-sample (171533) | Learned (≥ 0.85 both) |
|---|---|---|---|---|---|
| `loso-051828` | plain | 0 | 0.523 | 0.442 | no |
| C1 | plain | 1 | 0.567 | 0.569 | no |
| C2 | plain | 2 | 0.920 | 0.954 | yes |
| T | β 0.5 | 0 | 0.976 | 0.988 | yes |
| T1 | β 0.5 | 1 | 0.946 | 0.968 | yes |
| T2 | β 0.5 | 2 | 0.973 | 0.991 | yes |

- Every figure equals the evidence, each over 10,310 moving rows held out.
- **The held-out prediction files are tied to their runs.** Recomputing `idm_eval.camera_metrics` from each file's
  answered values reproduces that run's `gate1` camera block exactly (abstention, error stats, direction agreement),
  for all six runs.
- The in-sample (171533) files cannot be tied that way, because the reports carry no in-sample metrics. I could not
  regenerate predictions: the stores are on the Mac.
- **The readings applied are the pre-registered ones:** row 2 after C1/C2/T, then the addendum's fixed reading after
  T1/T2 ("all three β seeds learn → candidate, behind the flag").

## 4. The pitch cost is small but consistent held out, and the stated std calibration did shift

**Pitch agreement** (raw μ, moving rows, derived pitch truth):

| | Plain (seeds 0, 1, 2) | β-NLL (seeds 0, 1, 2) | Rank test |
|---|---|---|---|
| Held out (051828) | 0.836, 0.829, 0.823 (mean 0.829) | 0.814, 0.783, 0.798 (mean **0.798**) | every β seed below every plain seed: exact one-sided p = 1/20 = 0.05 |
| In-sample (171533) | 0.829, 0.870, 0.807 (mean 0.835) | 0.846, 0.779, 0.778 (mean 0.801) | overlapping: p = 4/20 |

- **This is not clearly seed noise.** The held-out gap (−0.031) is more than twice the plain seeds' own spread
  (0.013), and the ordering is complete. With three seeds a side it is suggestive, not established.
- The mechanism in section 2 predicts a cost of this sign.
- The pitch truth is itself derived (equal sensitivity), so this is agreement with a derived label.

**Stated std calibration** (each report's `model_std_coverage` on 051828; a calibrated std covers about 68 % within 1σ
and 95 % within 2σ):

| Axis, regime | Plain: within 1σ / 2σ, abstention | β-NLL: within 1σ / 2σ, abstention |
|---|---|---|
| Yaw, calibrated | 0.73–0.79 / 0.94–0.96, 0.005–0.051 | 0.64–0.79 / 0.93–0.98, 0.002–0.006 |
| Yaw, extrapolated | **0.36–0.62 / 0.84–0.88, 0.11–0.55** | **0.60–0.71 / 0.86–0.92, 0.008–0.042** |
| Pitch, calibrated | 0.70–0.79 / 0.91–0.96, ≤ 0.001 | 0.77–0.82 / 0.96–0.98, ≤ 0.003 |
| Pitch, extrapolated | 0.52–0.61 / 0.82–0.88, 0.004–0.082 | 0.56–0.63 / 0.86–0.90, 0.002–0.009 |

- **The calibration changed, mostly for the better.**
  - Extrapolated yaw moves from over-confident toward calibrated.
  - Its abstention collapses from up to 55 % to under 5 %. The failing plain seeds carried the motion in the variance,
    so they abstained; β-NLL answers.
  - Pitch's std becomes a little wide (within 2σ 0.96–0.98).
- **Nothing shows β-NLL over-confident.** But the 1°/3° abstention bounds were chosen under the plain loss, and coverage
  under β is now near complete. That matters for how Gate 1 reads.

## 5. What must happen before the flag defaults on

The lead's plan, a Gate 1 re-run with the flag on at scope, is necessary. I would add these, pre-registered with it:
- **(a) More than one fold with seeds.** β-NLL's 3 of 3 is on one fold (051828 held out). The plain loss learned yaw
  on 1 of 4 folds at seed 0 and 1 of 3 seeds here.
  - The re-run should cover all four folds.
  - It should also give at least one other fold several seeds, so "β removes the fragility" is not a one-fold claim.
- **(b) A judged pitch guard.** Set a non-inferiority margin (for example, held-out pitch agreement no more than 0.03
  below the plain loss, pooled over folds), judged rather than reported. Section 4 is borderline on exactly that.
- **(c) A calibration check per regime.** Judge within 1σ and 2σ for each axis and regime (for example, within 2σ ≥ 0.90).
  Re-confirm or re-register `CAMERA_ABSTAIN_STD` (1°/3°) under β, because coverage changed.
- **(d) β stays 0.5, as registered.** A per-axis β (say, sparing pitch) would be a new pre-registration, not a tweak.
- **(e) Losses stay separate.** β-NLL's train loss is on a weighted scale (T's 1.556 → 0.882 against the plain loss's
  0.68 → 0.31), so no loss-based selection or comparison may mix the two. `camera_loss` in the report makes the kind
  visible.

## Findings

- **F1 (minor, wording).** The commit message says "a default checkpoint keeps today's bytes". Its file bytes differ,
  because the embedded code closure changes; its weights and every other meta field are identical. Also,
  `idm-yaw-test.md` says the controls' reports record `camera_loss: null`, but the key is absent. Neither affects any
  result.
- **F2 (moderate, for the default-on decision only).** The held-out pitch cost of about −0.03 is consistent across
  seeds (section 4), and the mechanism is plausible (section 2). Judge it in the Gate 1 re-run (5b).
- **F3 (note).** β = 0.5 reduces the variance's hold on the mean from 1/v to 1/√v; it does not remove it (section 2).
- **F4 (note).** The stated std calibration and the abstention coverage changed under β (section 4). Re-check
  `CAMERA_ABSTAIN_STD` before relying on abstentions (5c).

## Tests (my environments)

| Suite | `1df31e7` | `4e7f005` | main `580a32e` + `4e7f005` |
|---|---|---|---|
| execution: `test_idm_model`, `test_idm_decode`, `test_idm_targets`, `test_idm_eval`, `test_replay_camera` | 71 passed | **72 passed** (+1, the β test) | **79 passed** (main's newer `idm_eval` tests included) |
| stdlib, whole repo | | | 1,918 passed, 75 skipped, 1 failed |

The one stdlib failure (`test_range_skill_loop`) is export-only: it reads a report under git-ignored `data/`. The commit
applies cleanly to main and passes there.

## Bytes reviewed (sha256)

| File | sha256 |
|---|---|
| `policy/idm/train.py` at `4e7f005` (blob) | `7de8a9e8aa89c02b08655f9a17203628e77c2cdab118f26eb9fdc79b05b142fd` |
| `tests/test_idm_model.py` at `4e7f005` (blob) | `7369fdee7272ab564dc0033edc5d90baf342c9e642e6e6c8b35d60fe710b05d0` |
| `policy/idm/train.py` at `1df31e7` (= main) | `48a736aace8c8753edef4af05ad331892e7fd1216ab764459215ae19a030bec0` |
| `tests/test_idm_model.py` at `1df31e7` (= main) | `80e80bce40c23033b95510b67b808c439144693a3fb6f039c92fd602f0accc5e` |
| `idm-yaw-test.md` (main) | `5304ad9280d20ddabb90ca4d223eac83e9d952b06834babdbf4e09f47fd07a99` |
| `idm-yaw-test-2.md` (main) | `5891b95c1167267366372a63baac7cbe5844fe739752e1819e5cf736b45d7539` |
| `idm-diag.md` (main) | `af4d2aaa91e5296ea46019706c5b3b4d178e9fbb436c3675b283f46fa76f60bf` |
| `docs/lanes/inverse-dynamics.md` (main) | `f1de4fd8bb6525206b2b2c273d20e77d607f0158f9843b1acdf15d711244e83a`; yaw section to the addendum `21e17dd95008ecf9…` (its pin) |
| `handoff/brief-fit-review-beta-nll.md` | `4d4bc875a1f53083202d58fe08ac310b9986d11ca2188ff4fd2ee77f6a7dcd09` |

The runs' and predictions' hashes are in section 3. My scripts and logs are in my scratchpad under `bn/`: `id/`,
`judge/`, `t-*.log` and `tests-summary.txt`.
