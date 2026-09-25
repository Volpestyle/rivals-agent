**Addendum: edge-input-2** (pre-registered 2026-09-25, after part B's result and before these runs; lead's go
`DECISION edge-input-2`).
- **Part B's result:** the lag arm "helped" on one seed of one fold. amazing_combo ΔF1 went from +0.030 to +0.089,
  and jump's F1 from 0.104 to 0.069. Seeds and a second fold decide whether that holds.
- **Runs:** the lag arm (`--hud-offsets 8 16`, code `b3112fc`), plain loss, 3 epochs, MPS.
  - Fold 051828: seeds 1 and 2 (seed 0 is part B's `b-lag`).
  - Fold 205528 (held out; train on 171533, 051828 and 200129): seeds 0, 1 and 2.
- **Today's arm, per fold and seed:** the existing plain runs with the same fold, seed and epochs.
  - 051828: seed 0 `loso-051828`, seed 1 `yaw-c1`, seed 2 `yaw-c2` (code `1df31e7`).
  - 205528: `a1-plain-s0`, `a1-plain-s1`, `a1-plain-s2` (code `fe5c9ca`; the plain path is identical).
  - Their press probabilities over the four sessions are computed now, from those checkpoints.
- **Judge:** part C's protocol per run, exactly as in part B.
  - The threshold is the train-session quantile at the train onset rate; the band is off; the landed `idm_eval` scores
    all known rows; chance-at-rate is the mean of 20 seeded draws.
  - "Clears" means ΔF1 = F1 − chance ≥ **0.05**, counted only where the action has ≥ 30 held-out onsets in that fold.
    On 205528 that includes Get Over Here! (35) and team_up (42).
- **"Helps" requires all three:**
  1. **amazing_combo** clears on **≥ 2 of 3 seeds in each fold** (051828: seeds 0 to 2; 205528: seeds 0 to 2);
  2. **Get Over Here! or team_up** clears on **≥ 2 of 3 seeds on 205528** (the same action on at least two seeds);
  3. **jump's** mean F1 in the lag arm, pooled over the six (fold, seed) runs, is **within 0.05 of today's pooled
     mean** (lag ≥ today − 0.05).
- **Reported only:**
  - each component separately, so a different combination of them can be read off;
  - web_swing's ΔF1 and AUC;
  - the movement keys;
  - AUC per action.
- **Budget:**
  - five lag-arm fits of about 20 min;
  - 40 probability passes (today's five checkpoints and the lag arm's five, on four sessions each);
  - about 2.3 h of Mac time after A4.

