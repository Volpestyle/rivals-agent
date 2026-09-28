EXPLORATORY 4x4 hidden-dropout p=0.5 result: **helps the residual control, but still loses to the frozen base and zero motion in every seed.** All three seeds completed the fixed 26 epochs / 15,288 updates; no checkpoint selection.

| Seed-mean metric | Dropout | Matched control | Frozen base |
|---|---:|---:|---:|
| Yaw MAE | 1.885650 | 1.908168 | 1.772851 |
| Left / right MAE | 2.430783 / 2.079991 | 2.450378 / 2.101504 | 2.320278 / 1.989594 |
| False turns, human yaw still | 30.1132% | 31.1866% | 24.9809% |
| False turns, both axes still | 29.6355% | 30.7495% | 24.6523% |

Zero-motion yaw MAE: **1.735184**. Dropout reduces control yaw error 1.18%, but remains 6.36% worse than base and 8.67% worse than zero. Candidate-minus-control yaw differences for seeds 1/2/3: **−0.009512, −0.025719, −0.032324**; candidate-minus-base: **+0.110160, +0.111197, +0.117038**.

The overfitting pattern persists in every seed: TRAIN cumulative loss falls and dev camera CE rises. Dropout lowers final dev CE versus control in all three seeds, but does not recover base yaw quality. All 26-epoch curves are retained; no early selection. Exact action/movement/pitch retention passes: press F1 **0.300688**, press-rate ratio **0.934364**, pitch MAE **0.594146**. These are offline predictions, not live-play results.

All artifacts and terminal teardown authenticated. New campaign settled **$2.550702** including the shakedown; zero active holds. Prior yaw plus dropout is **$21.217211** in conservative lane bounds, not a provider balance.

Evidence: `docs/evidence/nitrogen-yaw-dropout-20260928/results-01/` contains report.md, INTERPRETATION.md, report.json, curves.csv/png/svg and the source manifest. Raw final stage/status receipts are in the adjacent `fit-results-01/`. Collection SHA-256: `138f624017115d906aab12058c17d3d12a4fc973c69c00d5029552b06871e65b`.

Recommendation: do not promote this residual arm. Lead/steering owns the next intervention using this result and the completed intent/target audit. No new compute; 8x8 relaunch remains cancelled.
