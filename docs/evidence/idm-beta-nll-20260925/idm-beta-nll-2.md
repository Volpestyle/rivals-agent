# scoreboard-fix: toward β-NLL default-on, A1-A3 (A4 pending) (VUH-1353)

2026-09-25.
- **Pre-registration:** lane doc "### Toward β-NLL default-on: second fold, pitch, calibration, Gate 1
  (pre-registered 2026-09-25)", LF sha256 `42beb90e34d321e9391e2ad90f80b239e5b3a66d21f3cca2315cc8763280f098`. It was
  sent before any run and is unchanged.
- **Runs:** code `fe5c9ca` (clean worktree), MPS, niced. The A1 queue exited 0 after 130 min.
- **A4 (Gate 1 with `--beta-nll`) is pending.** It is queued behind B on the Mac, and will come as a second file,
  `idm-beta-nll-2-a4.md`.
- **Not done:** no commits, no Linear, no game input.

## A1: the second fold (205528 held out), three seeds, both losses

The judge is raw-μ yaw agreement on moving rows ≥ 0.85, both held out (205528) and in-sample (171533). The 051828 fold
rows come from `idm-yaw-test.md` / `-2.md`.

| Fold | Seed | Loss | Yaw held out | Yaw in-sample | **Learned** | Yaw corr | \|μ\|/\|true\| | Pitch held out |
|---|---|---|---|---|---|---|---|---|
| **205528** | 0 | β-NLL | 0.937 | 0.956 | **yes** | 0.882 | 0.809 | 0.641 |
| **205528** | 1 | β-NLL | 0.968 | 0.986 | **yes** | 0.913 | 0.936 | 0.830 |
| **205528** | 2 | β-NLL | 0.971 | 0.986 | **yes** | 0.919 | 0.850 | 0.787 |
| 205528 | 0 | plain | 0.480 | 0.460 | no | 0.177 | 0.022 | 0.799 |
| 205528 | 1 | plain | 0.899 | 0.922 | yes | 0.569 | 0.559 | 0.621 |
| 205528 | 2 | plain | 0.493 | 0.493 | no | 0.171 | 0.039 | 0.847 |
| 051828 | 0 / 1 / 2 | β-NLL | 0.976 / 0.946 / 0.973 | 0.988 / 0.968 / 0.991 | yes / yes / yes | | | 0.814 / 0.783 / 0.798 |
| 051828 | 0 / 1 / 2 | plain | 0.523 / 0.567 / 0.920 | 0.442 / 0.569 / 0.954 | no / no / yes | | | 0.836 / 0.829 / 0.823 |

**Reading:** β-NLL learns yaw on 3 of 3 seeds on 205528, so **the fold dependence is closed.**
- Across both folds, β-NLL learns 6 of 6 and the plain loss 2 of 6.
- The failing plain seeds show the same signature again: yaw means 2–4 % of the truth.

**Repeatability across commits, reported:**
- Plain seed 0 at `fe5c9ca` has **weights bit-identical** to `loso-205528` (seed 0 at `1df31e7`): every tensor
  equal, and the same config.
- The checkpoint files differ only because `fe5c9ca` adds the `cohort` meta key. The epoch losses match to the last
  digit (0.4066043700384203).

## A2: pitch non-inferiority (margin 0.05), pooled over both folds and seeds

| Fold | Seed | Plain | β-NLL | β − plain |
|---|---|---|---|---|
| 051828 | 0 | 0.836 | 0.814 | −0.022 |
| 051828 | 1 | 0.829 | 0.783 | −0.046 |
| 051828 | 2 | 0.823 | 0.798 | −0.025 |
| 205528 | 0 | 0.799 | 0.641 | **−0.157** |
| 205528 | 1 | 0.621 | 0.830 | **+0.209** |
| 205528 | 2 | 0.847 | 0.787 | −0.060 |

- Plain mean **0.7925**, β-NLL mean **0.7757**; the difference is **−0.017**, and the mean paired difference is also
  −0.017.

**Reading:** **non-inferior** (within 0.05), so this condition does not keep β-NLL behind the flag.

**My note on it:** the margin is met on the mean, but the pairs are wide (−0.157 to +0.209).
- On the 205528 fold, pitch itself is seed-fragile under **both** losses: plain seed 1 gives 0.621 and β-NLL seed 0
  gives 0.641, against 0.79–0.85 for the rest.
- So pitch has a fragility of its own that β-NLL neither causes nor cures. On 051828, β-NLL is consistently about
  0.02–0.05 below plain.
- This is worth carrying into A4's pitch figures, and into any later pitch-specific test.

## A3: the stated yaw std, per true gain regime (answered rows, held-out session)

| Fold | Seed | Loss | Calibrated: abstain / within 1σ / within 2σ / within bound | Extrapolated: abstain / within 1σ / within 2σ / within bound | Bounds hold |
|---|---|---|---|---|---|
| 051828 | 0 | β | 0.002 / 0.636 / 0.927 / 0.999 | 0.008 / 0.598 / 0.864 / 0.946 | yes |
| 051828 | 1 | β | 0.006 / 0.789 / 0.975 / 0.999 | 0.042 / 0.708 / 0.922 / 0.936 | yes |
| 051828 | 2 | β | 0.003 / 0.778 / 0.966 / 0.999 | 0.014 / 0.657 / 0.901 / 0.942 | yes |
| 205528 | 0 | β | 0.017 / 0.811 / 0.979 / 0.998 | 0.039 / 0.685 / 0.914 / 0.929 | yes |
| 205528 | 1 | β | 0.008 / 0.791 / 0.970 / 0.998 | 0.027 / 0.676 / 0.924 / 0.954 | yes |
| 205528 | 2 | β | 0.006 / 0.670 / 0.958 / 0.998 | 0.015 / 0.636 / 0.890 / 0.953 | yes |
| 051828 | 0 | plain | 0.051 / 0.783 / 0.951 / 1.000 | 0.553 / 0.480 / 0.883 / 0.814 | no |
| 051828 | 1 | plain | 0.035 / 0.789 / 0.965 / 1.000 | 0.520 / 0.362 / 0.837 / 0.765 | no |
| 051828 | 2 | plain | 0.005 / 0.729 / 0.941 / 0.999 | 0.110 / 0.615 / 0.866 / 0.910 | yes |
| 205528 | 0 | plain | 0.113 / 0.877 / 0.981 / 1.000 | 0.776 / 0.608 / 0.947 / 0.837 | no |
| 205528 | 1 | plain | 0.038 / 0.811 / 0.966 / 0.999 | 0.273 / 0.713 / 0.917 / 0.933 | yes |
| 205528 | 2 | plain | 0.042 / 0.743 / 0.921 / 1.000 | 0.500 / 0.339 / 0.808 / 0.694 | no |

**Pooled per loss (six runs each)**, with distance from nominal = |cov₁σ − 0.683| + |cov₂σ − 0.954|:

| Loss | Calibrated: within 1σ / 2σ (distance) | Extrapolated: within 1σ / 2σ (distance) |
|---|---|---|
| plain | 0.792 / 0.954 (0.109) | 0.544 / 0.874 (0.219) |
| β-NLL | 0.748 / 0.964 (0.075) | 0.661 / 0.904 (0.073) |

**Readings:**
- **The extrapolated band improved:** its distance falls from 0.219 to **0.073**.
- **The calibrated band did not worsen by more than 0.05.** It also improved, from 0.109 to 0.075.
- **The 1° / 3° abstention bounds hold on 6 of 6 β-NLL runs** (≥ 90 % of answered rows within the bound of their
  predicted regime, in both regimes), against 2 of 6 plain runs.
- β-NLL also abstains far less in the extrapolated band: 1–4 % of rows, against 11–78 % for plain.

**My call on A1-A3:** all three pre-registered readings favour β-NLL.
- the fold dependence is closed;
- pitch is non-inferior, with the fragility noted above;
- the calibration improves in both bands and the bounds hold.

The default-on decision waits on A4.

## Hashes (all checked across the wire)

**A1 runs** (`C:\Users\volpe\repos\rivals-agent\data\idm\runs\a1-*`, gitignored, with `a1.log` / `a1.exit`):

| Run | Checkpoint sha256 | report.json sha256 |
|---|---|---|
| a1-plain-s0 | `429eec1555d2a267615d0f7637adfcc7a6c3a70f354b628d46dda27d0190efb6` | `856ea2a1cb4487165c82b00c5e765b3ca2211ad78d43bac111c14f459f2733f3` |
| a1-plain-s1 | `48355ec265a48dca0f612945be65edce3dfde41b13e1d724162e919530213192` | `2e8cb3fddb64d640d6c4aa963d799ae49690b1599d1b3813563e5ffbb358b233` |
| a1-plain-s2 | `e38372845b43fbbc58d0caa4a586d9b369f15351ad43ca8b4ec9226af14e8836` | `1373efa8ab1875ee3bfff914fa329210317654b8b604d7d68d758f87fcb9dfe1` |
| a1-beta-s0 | `74727eaab01de29f95d131c252434858345d162587119871abd02e1efc24ab80` | `769d87e82f634388fe5492436006d509db4ca0367c7c2014cde08b65f30769df` |
| a1-beta-s1 | `6ba7738376e7ce864b3ced6cfadd612375d3a1efdd1481621975acad50fe7ba7` | `1682f25dbdf43f1d732b7ae69424f63e66c213e96fab753bee5ef960028c9374` |
| a1-beta-s2 | `0e2fd63da907045d8c9f93b357d79a9a4df0e9b84651cf37a48dbdb94ed3e662` | `cf87ffa7dfd06c259e9e845e9520ed05be66f42cdd09a8697bf778fb24385af4` |

**Per-row predictions** (`scratchpad\idm-diag\a1-<loss>-s<seed>-on-<session>-predictions.jsonl`):

| Run | on 205528 | on 171533 |
|---|---|---|
| plain s0 | `810cc6b1…` | `7bc50d43…` |
| plain s1 | `9a524ff6…` | `b9e31173…` |
| plain s2 | `186d1f13…` | `f7f3a946…` |
| β s0 | `5c561fd7…` | `970668ad…` |
| β s1 | `3fd23a87…` | `ee6f1264…` |
| β s2 | `c5f4d23f…` | `6f43b904…` |

The full hashes are in `data\idm\runs\a1.log`.

**Scripts:**

| File | sha256 |
|---|---|
| `judge_a.py` | `51621699d5bfe57f4547d86f44e7fb5d6857d91a35763563f313d025b7d05a26` |
| `judge_a-out.md` (the full output above) | `a7116c6b4e3387f57219ba1fb3cc598cd9d9e900ab01be135686b2b8e6a726e0` |
| Mac queue `a1.zsh` | `1370b105cd18a0f80d6aa30d2adb2c87be3051ee2e2004aba7676776b3724d5e` |
| `diag_predict_ckpt.py` | `ea8343300c415e1289c07162c4205ffddd530ee59f5051c2785c9a1203eb4d2a` |

## Still running

- **B (the edge-input lag arm):** on the Mac now.
- **A4:** chained behind it.

Their hand-backs will be `idm-edge-input.md` and `idm-beta-nll-2-a4.md`.
