### Post-hoc pitch-std calibration (pre-registered 2026-09-25)

Pre-registered before anything is computed; the judge was fixed by the lead's `beta-default` decision. It is
inference only, on existing β-NLL checkpoints, with no retraining. **This is not a gate result.**

**Why.** Under the default β-NLL, the stated pitch std is too tight at speed: at Gate 1 the extrapolated band's 1σ
coverage is 0.604. This test asks whether one scalar per band fixes that without touching yaw.

**The calibration.**
- The stated pitch std s is the predictor's total std: model variance plus the label sigma of the predicted value in
  its predicted regime.
- It is scaled by one scalar per **predicted** gain regime band, the band known at inference and the one the
  abstention uses: s′ = k_band · s.
- **Fit set:** the dev fold's β-NLL seed-0 checkpoint (`a4-beta`, 171533 held out), its per-row predictions on
  171533. These are computed now, by inference only.
- **k_band** = max(1, the 0.683 quantile of |pitch error| / s) over that band's rows with known pitch truth, before
  any abstention. It is an inflation only: a band that already over-covers keeps k = 1.
- **Applied:** pitch is answered iff s′ ≤ the pre-registered bound of its predicted regime (1° / 3°).
- **Yaw:** its std, answers and abstention are left exactly as they are.

**Judge sets:** the β-NLL runs of both folds, all seeds, on their held-out sessions:
- fold 051828: T, T1 and T2 (`yaw-t0`, `yaw-t1`, `yaw-t2`);
- fold 205528: `a1-beta-s0`, `-s1` and `-s2`.

Their per-row predictions already exist.

**Judge: all of these must hold.**
1. **Coverage:** per fold (rows pooled over its three seeds), per **true** gain regime band, over the answered pitch
   rows under s′. Within 1σ′ ≥ **0.70** and within 2σ′ ≥ **0.90**, in **both bands on both folds**.
2. **The abstention bounds still hold:** on every one of the six runs, per true regime, ≥ **90 %** of answered pitch
   rows have |error| ≤ the bound of their predicted regime (A3's definition, applied to pitch).
3. **Yaw untouched:** the yaw answers, std and coverage are identical before and after, checked row for row.

**Reported beside:**
- k per band;
- pitch abstention per band before and after (the inflation's cost in answered rows);
- the per-run coverage;
- the dev fold's own in-sample coverage.

**Reading:**
- **Pass:** the calibration is the candidate fix for the pitch cost, as a change to the predictor's stated std, to be
  reviewed before it lands.
- **Fail:** the pitch cost stands as recorded, and the failing component is named.

