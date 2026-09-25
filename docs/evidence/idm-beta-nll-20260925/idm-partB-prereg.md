### The edge head's input: HUD crops after the interval (pre-registered 2026-09-25)

Pre-registered before any code or run; the reading was fixed by the lead's brief. **This is not a gate result.**

**Why.**
- `idm-diag` and part C found that the edge head outputs its class prior, and that thresholds rescue only jump.
- The HUD-visible abilities' evidence lags the press by 0.1–1.9 s, while the head sees the HUD only at the interval's
  start and end frames.
- The stores already hold the HUD crop of every stored frame, including t1 + 8 and t1 + 16 video frames (+67 ms and
  +133 ms) for every row whose motion window is complete. **No rebuild is needed.**

**The arms** (fold 051828 held out; train on 171533, 205528 and 200129; plain loss, seed 0, 3 epochs, MPS):

| Arm | HUD input | Run |
|---|---|---|
| **Today** | the t0 and t1 crops (6 channels) | the existing `loso-051828` (checkpoint `11d0b912…`, code `1df31e7`; the plain loss path is unchanged at `fe5c9ca`). Its part-C probabilities are reused |
| **Lag** | the t0 and t1 crops **plus t1 + 8 and t1 + 16** (12 channels) | new. Code: one commit on branch `idm/edge-hud-lag-20260925` from `fe5c9ca`, adding the extra crops behind a config option that defaults to today's input, with a default checkpoint's bytes unchanged |

**Judge** (part C's protocol, exactly):
- **Threshold,** per action: the quantile on the arm's own train sessions at which it fires at the train onset rate.
- **Scoring:** abstention band off; scored with the landed `idm_eval` on all known rows. Chance-at-rate is the mean
  F1 of 20 seeded random draws at the arm's held-out fire rate.
- **Only actions with ≥ 30 held-out onsets decide.**
  - On 051828 that is **amazing_combo (60)**.
  - Get Over Here! (27) and team_up (24) are below 30 there and **cannot decide**; they are reported only.
- **The lag arm "helps"** if amazing_combo, get_over_here or team_up (in practice amazing_combo) clears chance-at-rate
  by **≥ 0.05 F1 where today's input does not**, and **jump's F1 does not fall by more than 0.05**.
  - Today's input on 051828: amazing_combo ΔF1 **+0.030** (does not clear); jump F1 **0.104**.
  - So "helps" means amazing_combo ΔF1 ≥ 0.05 and jump F1 ≥ 0.054.
- **The movement keys are expected unchanged:** there is no HUD evidence for them. They are reported, not judged.
- **Reported beside:** held-out AUC per action for both arms.

**Budget:** one fit of about 21 min, and four probability passes (the lag arm on its three train sessions and its
held-out session), after A1.

