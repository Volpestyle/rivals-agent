# Sizing only: one regularized 4x4 yaw residual candidate

**Pick: dropout p=0.5 on the residual head's 128-unit hidden activation,
immediately after ReLU and before its final yaw-logit projection.** Active only
while fitting the residual, disabled for validation/evaluation. The control
is the completed no-dropout 4x4 residual in `grid4-results-02`, matched seeds
1/2/3. One regularization intervention; parameter count stays 201,187.
Do not change width, weight decay (1e-4), learning rate (3e-4), losses, decoder,
data or targets at the same time. No intent labels enter this experiment.

Why: every completed 4x4 control and partial 8x8 seed fits TRAIN increasingly
while dev camera CE worsens. Hidden-activation dropout tests whether the residual
relies on fragile combinations of frozen visual features and memory. It preserves
the zero-initialized residual and exact frozen action/movement/pitch paths. It
may simply underfit; this is a hypothesis, not a promised remedy. The intent
audit shows mixed contexts but does not establish their contribution to model
error. Do not claim dropout fixes target selection or self-fed visual feedback.

Reuse existing 4x4 CUDA caches, matched frozen base checkpoints and TRAIN cutoffs.
No new extraction, uploads or 8x8 files. Keep 26 epochs, 15,288 updates, 96-row
windows, stride 64, batch 8, cohort and frozen dev; seed-matched order is already
generated independently of torch dropout RNG. Same L40S / pinned CUDA stack.
Three fresh fits; no partial resume or fresh control fits. Load only the fixed
epoch-26 endpoint, never choose a checkpoint by dev loss.

Report the pre-stated yaw MAE against zero, frozen base and completed 4x4 residual
control; left/right separately, false turns while still, exact action/pitch
retention, all seeds and mean. Retain full curves. `train_chunk_loss` is the
trainer's cumulative running average through each epoch; dev CE is recomputed
at that epoch. Neither is a checkpoint-selection rule. These remain exploratory
measurements on repeatedly used frozen dev.

## Cost envelope proposed for approval

Existing 4x4 accepted receipts have settled bounds $0.890870 / $0.822238 /
$0.872379, total **$2.585487**. Reservation-to-fence time was approximately
1,176 / 1,085 / 1,153 seconds, including setup/verification/evaluation; three
observations are not p95. With the same cache path and a small dropout operation,
expect roughly **$2.6-3.4 for three fits**, plus cheap launch validation.
Throughput is an estimate until observed.

Propose **$6.25 additional hard cap** including setup/shakedown and fits;
new lead approval is required. At the existing fixed-class rate
$0.0007178888888888888888888888889/s, rounded upward to one microdollar:

| Slots | Startup / work / cleanup seconds | Per-slot overhead | Per-slot hold | Total holds |
|---|---|---:|---:|---:|
| 3 concurrent shakedowns | 300 / 60 / 120 | $0.02 | $0.364587 | $1.093761 |
| 3 fits plus evaluation | 300 / 1800 / 120 | $0.05 | $1.643714 | $4.931142 |
| Combined | | | | **$6.024903** |

The remaining $0.225097 is unallocated margin, not permission to retry. Full
work has >50% margin over the slowest old reservation-to-fence observation,
with startup and cleanup separately funded. Do not borrow margin for unbounded
setup or alter live guards. Verify the accepted guard's exact rounding before
launch, bind finite named attempts and honor stricter reviewed minimums. If a
required allowance exceeds $6.25, stop for a decision.

Guard v1.0.5 was only a review candidate when this sizing was written. Launch
requires LAND/lead acceptance (or another explicitly approved accepted release),
a real bounded shakedown and globally paced AppCreate. No app, volume, launcher
packet or paid resource was created here.

Current yaw conservative settled amount is $18.666509, zero active holds. Adding
the proposed cap gives $24.916509; this does not authorize cancelled 8x8 fits.
The lead reconciles workspace/weekend totals and the $150 tell-James gate. Lane
bounds must not be added to overlapping metered usage as separate bills.
