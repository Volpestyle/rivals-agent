# EXPLORATORY result: dropout reduces the harm, but does not fix yaw

At the fixed epoch-26 endpoint, hidden dropout p=0.5 improves the matched 4x4
residual control in every seed, but remains worse than the frozen base and zero
motion in every seed. This arm does not merit promotion on these measurements.

| Seed-mean metric | Dropout | Residual control | Frozen base |
|---|---:|---:|---:|
| Yaw MAE, degrees | 1.885650 | 1.908168 | 1.772851 |
| Left-turn MAE | 2.430783 | 2.450378 | 2.320278 |
| Right-turn MAE | 2.079991 | 2.101504 | 1.989594 |
| False turns when yaw is still | 30.1132% | 31.1866% | 24.9809% |
| False turns when both axes are still | 29.6355% | 30.7495% | 24.6523% |
| TRAIN-cutoff press F1 | 0.300688 | 0.300688 | 0.300688 |
| Predicted/human press-rate ratio | 0.934364 | 0.934364 | 0.934364 |
| Pitch MAE | 0.594146 | 0.594146 | 0.594146 |

Zero-motion yaw MAE is **1.735184**. Dropout improves mean yaw MAE **1.18%**
relative to the residual control, but worsens it **6.36%** relative to the base
and **8.67%** relative to zero. Improvements over control occur on left turns,
right turns and both still-frame false-turn measures in every seed; none of
those measures beats the base in any seed. Actions, movement and pitch are
exactly retained, including pitch logits and frozen base tensors.

The same overfitting pattern remains in every seed: TRAIN cumulative weighted
loss falls while dev camera CE rises. Dropout raises the final TRAIN loss and
lowers final dev CE relative to control in all three seeds, consistent with
regularization reducing overfitting, but its absolute yaw remains worse than the
base. The curves do not establish a unique cause. Both CE and full-run MAE
improve relative to control; this is not the opposite-direction pattern that
would particularly implicate decoding/context. No early checkpoint was selected.

| Seed | Dropout TRAIN, epoch 1 → 26 | Dropout dev camera CE, epoch 1 → 26 | Control final dev CE |
|---|---|---|---:|
| 1 | 1.401308 → 1.386075 | 2.722192 → 2.815921 | 2.836328 |
| 2 | 1.400774 → 1.385836 | 2.734262 → 2.829479 | 2.850957 |
| 3 | 1.400969 → 1.384518 | 2.745619 → 2.856131 | 2.875006 |

All 156 arm/seed/epoch rows are retained in [curves.csv](curves.csv), with the
[overlay](curves.png) and [per-seed report](report.md). TRAIN is a cumulative
weighted average, including frozen losses; dev CE includes both camera axes.
These offline predictions do not establish live turning ability.

Collection authenticated all three final checkpoints, stage artifacts, exact
run identities, input/recipe pins, and terminal teardown. The report also
verified that each base evaluation and TRAIN cutoff is byte-equivalent as a
parsed value to its matched control. Final checkpoints remain on their own
output volumes; no partial checkpoint was resumed or selected. Supplementary
fit/status.json curves were collected with stable double reads and pinned hashes.

Spend: three fits **$2.277448**, shakedown **$0.273254**, new campaign total
**$2.550702** under its $6.25 cap. All six apps are terminal, zero active holds.
Prior yaw settled $18.666509 plus this campaign gives **$21.217211** across the
yaw investigations. These are conservative lane reports, not the Modal provider
balance; do not add them again to metered usage. Unspent allowance grants no
new run or retry. The 8x8 relaunch remains cancelled.

Next: lead/steering decides the next research intervention using this negative
result and the completed intent/target audit. No further compute is authorized
or requested by this report. The lead owns VUH-1346 acceptance and publication.
