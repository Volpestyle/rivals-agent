# EXPLORATORY: completed 4x4 yaw residual versus frozen base

The 4x4 position-aware yaw residual worsens yaw MAE in all three seeds, on both left and right turns, and increases false turns while James is still. Actions, movement and pitch are exactly retained. This is a standalone result: the stopped, incomplete 8x8 fits neither support nor reject finer features.

Same admitted cohort and 24,556 frozen-dev frames; frozen confirmed NitroGen no-history seeds 1/2/3; 26 epochs / 15,288 updates, 96-step windows / stride 64. L40S, torch 2.14.0+cu130; both base and residual use the same new CUDA-extracted cache. Median camera decode; original CUDA TRAIN press cutoffs. Offline predictions, not a live-play result.

| Seed | Model | Yaw MAE | Zero | Left MAE | Right MAE | False >=0.6 deg, yaw still | False >=0.6 deg, both still |
|---|---|---|---|---|---|---|---|
| 1 | base | 1.774179 | 1.735184 | 2.332130 | 1.988203 | 0.244237 | 0.240854 |
| 1 | candidate | 1.893851 | 1.735184 | 2.457853 | 2.066949 | 0.299842 | 0.294839 |
| 2 | base | 1.782225 | 1.735184 | 2.336895 | 1.996026 | 0.250396 | 0.245798 |
| 2 | candidate | 1.919141 | 1.735184 | 2.465684 | 2.113611 | 0.302305 | 0.295234 |
| 3 | base | 1.762150 | 1.735184 | 2.291810 | 1.984553 | 0.254795 | 0.252917 |
| 3 | candidate | 1.911511 | 1.735184 | 2.427596 | 2.123952 | 0.333451 | 0.332411 |

Support per seed: 8,984 left, 9,889 right, 5,683 human-yaw-zero, 5,057 both-axes-zero frames. False-turn columns are fractions of their stated still-frame slice.

Seed means: {"base": {"false_turn_ge_point6_when_both_zero": 0.2465229714587041, "false_turn_ge_point6_when_yaw_zero": 0.24980937298375272, "left_mae": 2.320278046611251, "pitch_mae": 0.5941461304066947, "press_f1": 0.30068794148597805, "right_mae": 1.9895937095762841, "yaw_mae": 1.7728513125680558, "zero_yaw_mae": 1.735183864749924}, "candidate": {"false_turn_ge_point6_when_both_zero": 0.3074945619932766, "false_turn_ge_point6_when_yaw_zero": 0.3118657985805619, "left_mae": 2.4503777753833886, "pitch_mae": 0.5941461304066947, "press_f1": 0.30068794148597805, "right_mae": 2.101504023743543, "yaw_mae": 1.9081679744420474, "zero_yaw_mae": 1.735183864749924}}.

Paired candidate-minus-base yaw errors (degrees): [{"seed": 1, "all": 0.11967217975782685, "left": 0.12572301466309144, "right": 0.07874653477600901}, {"seed": 2, "all": 0.1369164436553243, "left": 0.1287891735826756, "right": 0.11758468213166484}, {"seed": 3, "all": 0.1493613622088239, "left": 0.13578699807064698, "right": 0.1393997255941033}].

| Seed | Retained TRAIN-cutoff press F1 | Predicted/human press rate | Retained pitch MAE | Fixed-0.5 F1 | Real yaw NLL | Zero-spatial yaw NLL |
|---|---|---|---|---|---|---|
| 1 | 0.284916 | 0.942229 | 0.595408 | 0.330356 | 3.165720 | 3.151653 |
| 2 | 0.313503 | 0.937347 | 0.593668 | 0.354265 | 3.187425 | 3.192745 |
| 3 | 0.303645 | 0.923515 | 0.593362 | 0.359858 | 3.217323 | 3.268750 |

Human live-action base rate: 2,458 events / 24,556 frames = 0.100097736 events/frame. Incumbent H1 reference F1: 0.101745815. All frozen base tensors, action/pitch predictions and pitch logits pass exact retention checks. The NLL ablation zeros only the residual spatial input; the frozen base continues to read pixels. It is not a trained zero-token control.

All three outputs are collected and hash-checked against accepted guard stage receipts; epoch-26 checkpoints remain on their output volumes. All apps are stopped with zero owned containers. Three 4x4 charges total $2.585487; three intentionally stopped 8x8 charges total $2.252171. Including prior campaign attempts, settled conservative total is $9.505342 before the separately approved local-disk probe. These are guard bounds/lane reports, not a provider balance.

Next: finish the authorized local-disk throughput probe, then obtain the lead decision on any fresh 8x8 fits. No grid comparison is made here.
