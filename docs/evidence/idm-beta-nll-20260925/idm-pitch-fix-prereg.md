### Pitch-uncertainty fix: a yaw-std band, fitted apart and cross-fitted (pre-registered 2026-09-25)

Pre-registered before anything is computed. It follows the lead's brief `brief-idm-pitch-fix` and is inference only,
on the existing β-NLL checkpoints. There is no retraining and no model code change: a passing fix would become a
reviewed change to the predictor's stated pitch std later. **This is not a gate result. It is a Gate 2 precondition
for replay pitch labels in the fast band.**

**Why.** The per-predicted-band scalar failed for two reasons:
- 16–27 % of truly fast rows are predicted slow, so they keep k = 1;
- the dev fold under-corrects.

Arm A targets the first reason, and arm B adds the second.

**What both arms change.** Only the stated pitch std s, the predictor's total: model variance plus the label sigma of
the predicted value in its predicted regime.
- **The band variable:** the stated total **yaw** std σ_y of the same row, known at inference. β-NLL's yaw variance
  tracks motion magnitude (moving about 0.40°, still about 0.14° median, `idm-yaw-test.md`), so it can flag a fast row
  whose predicted mean is small. Yaw itself is only read, never changed.
- **The bins:** five quintile bins of σ_y. The edges are the 20/40/60/80 % quantiles of σ_y over the fit set's rows
  with known pitch truth. A value on an edge goes to the upper bin; values beyond the outer edges go to the end bins.
- **The inflation, per bin:** k_b = max(1, q₀.₆₈₃(r), q₀.₉₅₄(r) / 2), with r = |μ_pitch − pitch truth| / s over the fit
  set's rows in bin b with known pitch truth, before any abstention; nearest-rank quantiles. This is the smallest
  inflation that meets both nominal coverages on the fit set, and never a deflation.
- **Applied:** s′ = k_{bin(σ_y)} · s, and pitch is answered iff s′ ≤ the pre-registered bound of its predicted regime
  (1° calibrated, 3° extrapolated). Yaw's std, answers and abstention are untouched.

**The arms, in order.**
- **A (fitted apart):** the fit set is the dev fold's β-NLL seed-0 predictions (`a4-beta` on 171533, `822f22dc…`),
  the only β prediction set that is not judged. One set of 5 edges and 5 k values is judged on both folds.
- **B (cross-fitted on the fast-heavy folds):** the fit set is one fold's held-out predictions, pooled over its three
  seeds. It is judged on the other fold:
  - fit on fold 051828 (`yaw-t0/t1/t2` on 051828), judge fold 205528;
  - fit on fold 205528 (`a1-beta-s0/s1/s2` on 205528), judge fold 051828.

  **No fold is judged with parameters fitted on it.**

**Judge sets:**
- fold 051828: `yaw-t0`, `yaw-t1`, `yaw-t2` on 051828;
- fold 205528: `a1-beta-s0`, `-s1`, `-s2` on 205528.

All of these are existing per-row predictions.

**Judge: per arm, all of these must hold** (the same judge as the failed calibration).
1. **Coverage:** per fold (rows pooled over its three seeds), per **true** gain regime band, over the answered pitch
   rows under s′. Within 1σ′ ≥ **0.70** and within 2σ′ ≥ **0.90**, in **both bands on both folds**.
2. **The 1° / 3° bounds hold on every one of the six runs:** per true regime, ≥ **90 %** of answered pitch rows have
   |error| ≤ the bound of their predicted regime.
3. **Yaw untouched:** the yaw answers, std and mean are identical before and after, row for row.

**Reading** (the arms are ordered; an arm passes only if all three components hold):
- **A passes:** A is the fix, whatever B does. Its deployable parameters are A's dev-fold fit, one set. A is preferred
  because it is fitted once, on data never judged.
- **A fails and B passes:** B is the fix. Its deployable parameters are then fitted by the same rule on **both**
  fast-heavy folds pooled (six runs). That set is not itself judged; the cross-fit is its held-out evidence. The
  parameters are reported.
- **Both fail:** the pitch cost stands, fast-band replay pitch labels stay untrusted, and the failing components are
  named.

**Reported beside, per arm:**
- the bin edges and k values;
- pitch abstention per true band, before and after (the cost in answered rows);
- the per-run coverage;
- the fit set's own in-sample coverage.

**Budget:** PC only, from existing prediction files; minutes. Nothing runs until the lead's OK.

