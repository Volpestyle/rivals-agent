# scoreboard-fix: IDM diagnostics, Go 1 (yaw direction) and Go 2 (edge head) (VUH-1353)

2026-09-24.
- **No retraining,** no edits to `policy/idm` or `policy/idm_eval.py`, no commits, no Linear, no game input.
- **Mac:** only inference, through `/Users/james/dev/idm-data/` (MPS, niced, about 90 s in all).
- **PC:** everything else, read-only.

## Short answers

- **Go 1: the model, specifically a training failure.** It is not a timing offset, not a per-session sign, and not
  fast turns.
  - The `loso-051828` checkpoint never learned yaw direction: 0.52 agreement held out, and **0.44 on 171533, a
    session it trained on**. Its yaw means are about 6 % of the truth, while the size of the turn goes into its
    variance.
  - The `loso-171533` checkpoint did learn yaw: 0.92 on 051828 (in its training set), 0.96 held out.
  - Pitch is learned by both.
  - **The folds' "yaw beats zero" was abstention selection.** Paired on all moving rows, raw yaw error is 1.425° for
    the model against 1.422° for zero.
- **Go 2: the edge head outputs its class prior.**
  - For every supported action but jump, pos_weight hits the clamp (100). An uninformative model's weighted optimum
    is then p* = 0.03–0.45, below 0.5, so nothing ever fires.
  - Jump is the one action under the clamp (neg/pos 76–78). Its p* is exactly 0.50, so weak signal (AUC 0.73) pushes
    about a fifth of all rows over the line.
  - **The metric hides this:** onsets on abstained rows drop out of the positives and misses, so recall and
    "decides" are computed over answered rows only.

## Go 1: per-row predictions, `loso-051828` on its held-out session 051828

**Run:** `diag_predict.py` (`8b66f33c…`), checkpoint `11d0b912…` (as in the report), MPS, 37.5 s.
- 25,100 usable rows, all with frames.
- Raw camera mean and log-variance, the predictor's own answer and every press probability, one JSON line per row.
- Output: `…\scratchpad\idm-diag\loso-051828-predictions.jsonl` (`93d0be91ec7a0ba9…`), copied back and hash-checked.
- Analysis: `analyse.py` (`0ed5569b…`).
- The rows carry what a band split needs: true degrees, counts, pointer rate and gain regime per row.
- "Moving" means |true| ≥ 0.5°. Agreement is `idm_eval`'s definition. Raw-μ agreement uses the model's mean on every
  row, which removes the abstention selection.

**Yaw by true pointer speed** (× the 915 counts/s calibration turn):

| Band | Moving rows | Abstained | Agreement, answered | Agreement, raw μ | corr(μ, true) | median \|μ\|/\|true\| |
|---|---|---|---|---|---|---|
| 1-2× | 2,309 | 0.22 | 0.568 | 0.558 | 0.14 | 0.065 |
| 2-4× | 3,589 | 0.51 | 0.533 | 0.535 | 0.12 | 0.059 |
| 4-8× | 2,830 | 0.74 | 0.510 | 0.491 | 0.02 | 0.061 |
| 8-16× | 1,284 | 0.96 | 0.500 | 0.491 | 0.07 | 0.076 |
| >16× | 298 | 1.00 | – | 0.534 | 0.12 | 0.063 |
| all | 10,310 | 0.58 | 0.543 | 0.523 | 0.06 | 0.064 |

- **By gain regime:** calibrated 1,109 rows, agreement 0.570 (raw μ); extrapolated 9,201 rows, 0.517.
- **By true degrees per interval:** 0.5–1° gives 0.542 and 1–2° gives 0.533. **The slowest turns fail too.**

**Lag check** (raw μ at row i against the truth at row i+k, inside a run):

| k | −3 | −2 | −1 | 0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| Yaw agreement | 0.515 | 0.519 | 0.522 | 0.523 | 0.522 | 0.519 | 0.518 |
| Pitch agreement | 0.808 | 0.824 | 0.831 | **0.836** | 0.835 | 0.826 | 0.814 |

- **Yaw is flat at chance at every lag, and never below 0.5.** No lag recovers it, and nothing flips.
- **By session-time quarter** it is 0.51, 0.53, 0.54 and 0.51. No segment is flipped.
- **Pitch peaks at k = 0,** so there is no timing offset.

**Pitch, briefly.**
- Agreement is 0.836, and correlation with the truth is 0.70.
- It is flat across regimes: calibrated 0.850, extrapolated 0.834.
- It holds to 4–8× (0.82) and fades above 8× (0.75 at 8–16×, 0.50 above 16×).
- It is under-scaled: median |μ|/|true| is 0.45.

**Extension, beyond the brief's one fold: in-sample checks.** Two more predict passes, read-only, no training
(`diag_predict_any.py`, `3ecfb13f…`), each checkpoint on a session **in its own training set**.

| Checkpoint → session | Held out? | Yaw agreement (raw μ) | Yaw corr | Yaw \|μ\|/\|true\| | Pitch agreement |
|---|---|---|---|---|---|
| loso-051828 → 051828 | yes | 0.523 | 0.06 | 0.064 | 0.836 |
| loso-051828 → 171533 | no (trained on it) | **0.442** | 0.08 | 0.054 | 0.829 |
| loso-171533 → 051828 | no (trained on it) | **0.923** | 0.72 | 0.674 | 0.835 |

Outputs: `loso-051828-on-171533-predictions.jsonl` (`424691d3…`) and `loso-171533-on-051828-predictions.jsonl`
(`da9c0fa1…`).

**Predicted yaw std on the same session (051828), moving rows, median / p90:**
- `loso-051828`: 1.47° / 4.81°;
- `loso-171533`: 0.79° / 3.90°.

On still rows both are about 0.12°. The failing model's variance tracks how much the camera moves, while its mean
stays near 0.

**Which explanation the numbers support.**
- **Not a timing offset:** no lag in ±3 recovers yaw, and pitch peaks at lag 0.
- **Not a per-session sign:** agreement never falls below chance in any band, quarter or lag. The failing checkpoint
  also fails on a session it trained on, which a per-session sign on 051828 cannot cause.
- **Not fast turns:** slow turns fail equally.
- **The model:** in this fit the yaw head did not learn direction even on its training data. The other fold's fit
  did, on the same code and architecture.
- **The likely mechanism** (supported, not proven): the Gaussian NLL with a learned variance lets the model explain
  yaw error through variance. The mean's gradient scales with 1/variance, so once the variance has grown, the mean
  stalls. The failing model's yaw variance is about twice the working one's and tracks motion magnitude. Pitch has
  smaller magnitudes, so its variance stays small and its mean learns.
- **What would falsify it:**
  - Refit the 051828 fold (same data, 3 epochs) with only the camera loss changed so the variance cannot starve the
    mean: β-NLL with β = 0.5, or the mean trained by MSE with the variance detached. **If yaw still stays at chance
    on its own training data, the NLL mechanism is wrong.** The next place to look would be the input or
    optimisation, for example seeds 1 and 2 unchanged, to measure how often yaw is learned at all.
  - Conversely, if unchanged seeds already learn yaw most of the time, the problem is fragility, not the loss.

## Go 2: the edge head, read-only

**Sources:** the four reports; `policy/idm/train.py` (`train_statistics`, `ABSTAIN_BAND`, `POS_WEIGHT_MAX`);
`policy/idm_eval.py` (`edge_metrics`, `THRESHOLD`); and, as supporting evidence, the Go 1 per-row probabilities
(`edges.py`, `ad20915d…`).

**1. The clamp decides who fires.**
- `pos_weight = clamp(neg/pos, 1, 100)`. At 60 Hz an onset is one interval, so every supported action except jump
  has neg/pos above 100 in every train fold. Their weight is the clamp.
- For an uninformative head, the weighted BCE optimum is p* = w·π / (w·π + 1 − π):

| Action | Train onsets (fold without 171533) | pos_weight | p* | Held-out median p, on 051828 (other rows) |
|---|---|---|---|---|
| move_left | 1,191 | 100 (clamped) | 0.43 | 0.44 |
| web_cluster | 1,274 | 100 (clamped) | 0.44 | 0.38 |
| move_forward | 971 | 100 (clamped) | 0.38 | 0.33 |
| move_right | 933 | 100 (clamped) | 0.37 | 0.32 |
| move_back | 746 | 100 (clamped) | 0.32 | 0.26 |
| spider_power | 611 | 100 (clamped) | 0.28 | 0.19 |
| web_swing | 548 | 100 (clamped) | 0.25 | 0.19 |
| amazing_combo | 354 | 100 (clamped) | 0.18 | 0.09 |
| team_up | 160 | 100 (clamped) | 0.09 | 0.05 |
| get_over_here | 152 | 100 (clamped) | 0.09 | 0.05 |
| **jump** | 2,098 | **76 (not clamped)** | **0.50** | 0.48 |

- The other folds are the same to ±0.02: jump 76–78, every other action clamped.
- **The head's outputs sit at or just under p*.** Every clamped action's p* is below 0.5, so no row reaches the 0.5
  threshold, let alone 0.65: a share of 0.000 on 051828 for all ten.
- **Jump's weight balances exactly,** so its uninformative output is 0.50, on the threshold. On 051828 its rows split
  into 20 % ≥ 0.65, 50 % inside the band and 31 % ≤ 0.35.
- **The signal is weak** (AUC 0.73), so about a fifth of all rows fire and precision is near the base rate (0.02–0.06
  across folds).

**2. There is some ranking signal, but it is weak.** AUC on 051828, onset rows against the rest:

| Action | AUC |
|---|---|
| amazing_combo | 0.80 |
| jump | 0.73 |
| team_up | 0.70 |
| web_swing | 0.63 |
| get_over_here | 0.61 |
| web_cluster | 0.60 |
| spider_power | 0.56 |
| move_forward | 0.55 |
| move_left | 0.55 |
| move_back | 0.50 |
| move_right | 0.46 |

- **The movement keys carry no onset signal;** the HUD shows nothing for them.
- The HUD-visible abilities carry a little. They are sampled only at the interval's start and end, while their HUD
  evidence lags the press by 0.1–1.9 s (replay-HUD lane).

**3. The abstention band.**
- (0.35, 0.65) is centred on 0.5, but the clamped actions' outputs sit at p* = 0.25–0.45. So actions whose p* lies
  inside the band abstain wholesale: move_left 95 %, web_cluster 57 %, move_forward 33 %. The rest answer "no" almost
  everywhere.
- For jump, the band swallows half of all rows.

**4. What the report's edge metrics hide.**
- **Positives and misses count only answered rows.** `edge_metrics` skips a row once the predictor abstains, before
  checking for a true onset (`idm_eval.py` lines 170-174), so a true onset in the band is neither a positive nor a
  miss. On 051828:
  - move_left has **183** true onsets; the report says `heldout_positives` **5**, because 178 abstained;
  - jump has 361; the report says 171;
  - web_cluster 226 → 62, and move_forward 151 → 97.

  Recall is therefore measured on the rows the model chose to answer, and the F7 "decides" flag (≥ 30 positives)
  flips with the model's own abstention. **This is an `idm_eval` correctness issue, not a model issue.** A fix would
  count positives over all known rows and report the onsets abstained on. I have not edited it (my brief says no
  edits), and it needs its own review.
- **The onset error is computed on matched pairs only.** When jump fires on about 20 % of rows, every true onset
  finds a prediction within ±2 intervals, so the median onset error of 0 reflects prediction density, not timing.
- **Threshold-only F1 hides ranking.** An F1 of 0 on an action that never fires ("precision –") reads like a "no",
  but it hides AUC 0.80 (combo).

**The smallest pre-registrable change to test next** (one change, no retraining, Mac minutes):
- **Change:** replace the fixed 0.5 threshold with a **rate-matched per-action threshold**.
  - Each action's threshold is the probability quantile, on that fold's **own train sessions**, that fires at the
    train onset rate.
  - It is computed before the held-out rows are scored. The abstention band is disabled for this test.
  - It is scored on all known rows, with the positive count fixed as above.
- **Predicted effect:**
  - F1 rises above chance-at-rate only where held-out AUC ≥ 0.7 (amazing_combo, jump, team_up);
  - **it stays ≤ 0.10 for every action,** because AUC 0.6–0.8 at a base rate of 0.1–1.4 % cannot give usable
    precision;
  - the movement keys stay at chance.
- **Judged:** per action with ≥ 30 held-out onsets over all known rows, pooled over the four folds. F1 is compared
  with chance-at-rate (a random draw at the same rate), and the pre-registered call is "signal" only if it clears
  chance by ≥ 0.05 F1 in at least 3 of 4 folds.
- **Why this one first:** it separates "wrong decision rule" from "no signal" without touching training. **If the
  prediction holds, the thresholds are not the lever: the input is.** The follow-up would then be one retraining
  change: HUD crops at t1 + 8 and + 16 video frames, which the stores already hold, instead of only t0 and t1. That
  is not proposed here.

## Files

All in `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\`.

| File | sha256 |
|---|---|
| `idm-diag\loso-051828-predictions.jsonl` | `93d0be91ec7a0ba9fd102b05d75c5496cbe14ba4c036ee565968542f36854077` |
| `idm-diag\loso-051828-on-171533-predictions.jsonl` | `424691d30895a2a171dcb703b342f9081cfd8507967d39bcb5ecb330ee7d1529` |
| `idm-diag\loso-171533-on-051828-predictions.jsonl` | `da9c0fa13e3aac4d4b593512ab62117d90156b1df77b5e4d0124ea39b3a91c54` |
| `idm-send\jobs\diag_predict.py` | `8b66f33c…` |
| `idm-send\jobs\diag_predict_any.py` | `3ecfb13f…` |
| `idm-diag\analyse.py` | `0ed5569b…` |
| `idm-diag\edges.py` | `ad20915d…` |

The Mac copies are under `/Users/james/dev/idm-data/diag/` and `/Users/james/dev/idm-data/jobs/`. Nothing is running
there.
