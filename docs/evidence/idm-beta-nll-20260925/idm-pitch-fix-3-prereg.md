### Pitch-uncertainty fix, final round: k fitted on each bin's truly fast rows (pre-registered 2026-09-25)

Pre-registered before anything is computed; inference only on the same β-NLL per-row predictions.
**This is the last inference-only round on these judge sets.** If it fails, the pitch item waits for fresh held-out
sessions: the three newly admitted takes, once their frame stores exist. **This is not a gate result.**

**Why.**
- The previous round's band variable works: the stated yaw std puts 70–76 % truly fast rows in its top bin and ≤ 2 %
  in its lowest three. That finding was not pre-registered.
- But a k fitted over a whole bin under-covers the bin's fast rows, because the slow rows in the bin over-cover.
- The judge fails on the fast (extrapolated) band, so this round fits k on the fast rows it must cover.

**What changes from the previous round: only how k is fitted.** The bins, the application and yaw's treatment are
unchanged.
- **The bins:** five quintile bins of the row's stated total yaw std σ_y. The edges are the 20/40/60/80 % quantiles of
  σ_y over the fit set's rows with known pitch truth (all of them, as before). A value on an edge goes up.
- **The inflation, per bin:** k_b = max(1, q₀.₆₈₃(r), q₀.₉₅₄(r) / 2), with r = |μ_pitch − pitch truth| / s over the fit
  set's rows in bin b **whose true gain regime is extrapolated**, before any abstention; nearest-rank quantiles. The
  true regime is used in fitting only.
  - **If a bin has fewer than 50 truly fast fit rows,** k_b = 1: a quantile over so few rows is unstable, and those
    bins' slow rows already over-cover.
- **Applied at inference, to every row in the bin, slow or fast:** s′ = k_{bin(σ_y)} · s, and pitch is answered iff
  s′ ≤ the pre-registered bound of its predicted regime (1° / 3°). Only σ_y is used at inference, never the true regime.
  Yaw's std, answers and abstention are untouched.

**The arms, in the same order as before.**
- **A (fitted apart):** fitted on the dev fold's β-NLL seed-0 predictions (`a4-beta` on 171533, `822f22dc…`); judged
  on both folds.
- **B (cross-fitted):**
  - fitted on fold 051828 (`yaw-t0/t1/t2` on 051828, pooled), judged on fold 205528;
  - fitted on fold 205528 (`a1-beta-s0/s1/s2` on 205528, pooled), judged on fold 051828.

  No fold is judged with parameters fitted on it.

**Judge: per arm, the same as both previous rounds.**
1. **Coverage:** per fold (three seeds pooled), per **true** band, over answered pitch rows under s′. Within 1σ′ ≥
   **0.70** and within 2σ′ ≥ **0.90**, in both bands on both folds.
2. **The 1° / 3° bounds hold on every one of the six runs:** per true regime, ≥ **90 %** of answered pitch rows have
   |error| ≤ the bound of their predicted regime.
3. **Yaw identical,** row for row.

**Reading, the same as the previous round:**
- **A passes:** A is the fix, with A's dev-fold parameters.
- **A fails and B passes:** B is the fix, with its deployable parameters fitted by this rule on both fast-heavy folds
  pooled. That set is not itself judged; the cross-fit is its held-out evidence.
- **Both fail:** the pitch cost stands, fast-band replay pitch labels stay untrusted, and **the pitch item waits for
  the three new admitted takes as fresh held-out sessions.** No further round is run on these judge sets.

**Reported beside, per arm:**
- the bin edges;
- k per bin and the count of truly fast fit rows per bin;
- pitch abstention per true band before and after. Inflating every row in a bin also inflates its slow rows, so the
  cost in answered rows may be larger than last round's;
- per-run coverage;
- the fit sets' in-sample coverage.

**Budget:** PC only, from the existing prediction files; minutes. Nothing runs until the lead's OK.

