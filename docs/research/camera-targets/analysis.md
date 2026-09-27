# Why the camera head decodes to zero: interim versus full admitted train

2026-09-26 · research-methods · VUH-1346 · revised under James's full-cohort addendum.

**Result:** zero is only **17.86% / 18.73%** of interim yaw/pitch labels and **18.80% / 19.69%** of full-cohort labels. Nevertheless, zero is the modal class and signed median on both axes in both populations. A calibrated but uninformed head can therefore decode to zero every step without assigning most probability to zero. The targets do not describe mostly stationary play.

**No qualitative conclusion or candidate-ranking reversal.** Coarser targets reduce zero frequency in both populations but still have zero signed medians. Temporal dependence remains strong, though its magnitude declines with the full cohort. The complete scalar and histogram tables below recompute every statistic on each cohort rather than carrying over the earlier assumptions.

The supplied decoder audit is attributed to the steering lead, not reproduced here. No checkpoint was opened. Only this report was written; no training, game input, Mac/cloud job, Linear write or commit.

## Populations and authorised scope

James's addendum explicitly requests the **full admitted 180.6-minute registry-train cohort**. That includes 171533 and 205528, reserved as frozen dev for rounds 1–3. Their admitted step labels were read for this descriptive comparison under the addendum; **their experimental role is unchanged**. No validation, test, gate2 or sealed-session payload was opened.

Membership comes from the [corpus registry](../../../data/human/session-splits.corpus.json), [v2 denylist](../../../data/human/sealed-denylist.v2.json), [admission tally](../../../data/human/sessions/tally.json), [admission note](../../lanes/human-admission.md) and [interim queue manifest](../../evidence/range-bc-countermeasures-2-20260926/queue.zsh).

| Population | Sessions | Accepted normal-regime steps | Continuous runs | Step minutes |
|---|---:|---:|---:|---:|
| Interim train, rounds 1–3 | 5 | 144,957 | 12 | 80.5317 |
| Full admitted registry-train | 10 | 325,004 | 31 | 180.5578 |

The tally records 180.5690 accepted minutes and 180.5578 trainable step minutes; both round to 180.6. The latter is used here, from exact 33,333,333 ns steps. The earlier eight-session 166.92-minute analysis excluded the two frozen-dev identities; it is superseded as the requested full-cohort comparison. No separate full-cohort launch manifest is claimed.

Old candidate-registry sessions 032454 and 033319 are held/unadmitted and were skipped. Non-train placements, evaluation-only and calibration recordings were skipped. The dedicated validation take 212646 was never opened. No unclear-split file was used.

Before reading step rows, all ten current step files matched their assembled artifact manifests by SHA-256. Header identity, train placement, media hash and sealed flag were checked against the registry and denylist. No images, video, caches, raw input logs or calibration-session payloads were read. Calibration comes from the admitted step headers.

Statistics use accepted normal-regime, gap-free, camera-known rows in continuous runs of at least 48 steps. Continuity additionally checks consecutive row indices and exact anchor spacing. No window or pair crosses a boundary. There were no short eligible runs or unknown camera labels in either population. Rows are counted once unless a statistic explicitly describes overlapping windows or training exposure. The original interim statistics exactly reproduce the earlier computation.

## What changes with the full cohort?

| Finding | Interim 80.53 minutes | Full 180.56 minutes | Interpretation |
|---|---:|---:|---|
| Yaw / pitch zero frequency | 17.86% / 18.73% | 18.80% / 19.69% | About +0.95 percentage points each; still minority zero labels |
| Modal class / signed median | Zero, both axes | Zero, both axes | Marginal-head explanation unchanged |
| Absolute yaw motion mass above 1 degree | 91.94% | 91.90% | Large turns still dominate rotation |
| Lag-one / lag-four yaw correlation | 0.9290 / 0.5229 | 0.9145 / 0.4682 | **Weaker continuity**; the old effect size must not be reused |
| Mean-axis zero MAE | 1.3660 degrees | 1.3591 degrees | Slightly lower |
| Mean-axis raw human-history persistence MAE | 0.4460 degrees | 0.4748 degrees | **6.44% worse**, while still much better than zero |
| Leave-session-out yaw transition NLL | 1.7216 nats | 1.7621 nats | Past camera class remains predictive, with increased difficulty |
| H=8 yaw / pitch net-zero frequency | 4.24% / 4.70% | 4.54% / 5.00% | Coarse targets reduce exact zeros in both |
| H=4/H=8 signed displacement medians | Zero, both axes | Zero, both axes | Coarsening alone still cannot create directional information |

No directional or ranking conclusion reverses. The weaker correlations strengthen the caution against long open-loop commitments. These are descriptive differences, not significance tests on independent frames.

## Label definition and main numbers

[Target construction](../../../policy/range_bc/steps.py) multiplies each step's net relative mouse counts by its header gain. All ten selected headers use 0.0330738 degrees/count for both axes; pitch is explicitly **derived_equal_sensitivity**. These are requested input rotations, not observed screen rotation.

[The vocabulary](../../../policy/range_bc/vocab.py) uses signed representatives `0.05, 0.1, 0.2, 0.35, 0.6, 1, 1.6, 2.5, 4, 6, 9, 13, 19, 28, 40` degrees with geometric-mean boundaries. Class 15 covers |rotation| <0.025 degrees. At this integer-count gain, **class 15 means zero net counts**; one-count movements are not silently quantised to zero. Opposing raw packets could cancel within the bin, which these step labels cannot resolve.

| Statistic | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|
| Zero class share | 17.86% | 18.73% | 18.80% | 19.69% |
| Negative share | 40.30% | 39.06% | 39.29% | 38.46% |
| Positive share | 41.84% | 42.20% | 41.90% | 41.85% |
| Absolute angle quantile 0.25 (degrees) | 0.0661 | 0.0661 | 0.0661 | 0.0661 |
| Absolute angle quantile 0.5 (degrees) | 0.6615 | 0.3969 | 0.6284 | 0.3969 |
| Absolute angle quantile 0.75 (degrees) | 2.2821 | 1.1576 | 2.1829 | 1.1245 |
| Absolute angle quantile 0.9 (degrees) | 5.3910 | 2.2159 | 5.2918 | 2.2490 |
| Absolute angle quantile 0.95 (degrees) | 8.0700 | 3.0759 | 8.1692 | 3.1089 |
| Absolute angle quantile 0.99 (degrees) | 15.7762 | 5.0934 | 16.6361 | 5.1264 |
| Absolute angle quantile 0.999 (degrees) | 27.3190 | 8.1376 | 29.8987 | 8.3015 |
| Absolute angle quantile 1 (degrees) | 66.1145 | 15.7101 | 66.1145 | 16.2723 |
| Steps above 1 degree absolute | 41.47% | 28.26% | 40.43% | 28.00% |
| Absolute motion mass above 1 degree | 91.94% | 75.42% | 91.90% | 75.80% |
| Mean signed angle (degrees) | -0.003209 | 0.001078 | -0.010077 | 0.001917 |
| Median signed angle | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Zero-predictor MAE (degrees) | 1.9079 | 0.8240 | 1.8980 | 0.8202 |
| Quantise/dequantise MAE (degrees) | 0.2038 | 0.0976 | 0.2031 | 0.0975 |
| Step moving: |angle| >0.5 degrees | 54.33% | 45.02% | 53.21% | 44.34% |
| Complete nine-step window centers | 144861 | 144861 | 324756 | 324756 |
| Moving on same window centers | 54.35% | 45.04% | 53.23% | 44.37% |
| Any movement within ±4 steps | 82.63% | 72.98% | 82.54% | 72.98% |

Motion mass is sum(|angle|). Above-1-degree yaw steps occupy 40.43% of the full cohort but carry 91.90% of absolute yaw rotation. CE gives each known step one categorical observation, regardless of rotation magnitude. Nonzero directions/magnitudes occupy 30 bins, while zero occupies one; zero can therefore be the mode without being the majority behavior.

The symmetric ±4-step activity window has nine bins (about 300 ms of support). Its central-step comparator uses the same complete-window centers. It is retrospective analysis, not an allowed future visual input. A trailing nine-step window has the same pooled any-movement share because it enumerates the same windows under a shifted anchor; that is not equal predictive information at their respective anchors.

### Autocorrelation, lags 1–16

Pearson correlation of raw signed displacement over within-run pairs, with separate pair means/variances per lag. At fixed 30 Hz, degrees/step and degrees/second have the same correlation. These are temporal dependencies, not proof of visual observability or autonomous skill.

| Lag | Time (ms) | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|---:|
| 1 | 33.3 | 0.9290 | 0.9401 | 0.9145 | 0.9354 |
| 2 | 66.7 | 0.8012 | 0.8333 | 0.7648 | 0.8198 |
| 3 | 100.0 | 0.6558 | 0.7002 | 0.6047 | 0.6787 |
| 4 | 133.3 | 0.5229 | 0.5628 | 0.4682 | 0.5351 |
| 5 | 166.7 | 0.4166 | 0.4340 | 0.3655 | 0.4028 |
| 6 | 200.0 | 0.3390 | 0.3227 | 0.2936 | 0.2904 |
| 7 | 233.3 | 0.2804 | 0.2260 | 0.2410 | 0.1959 |
| 8 | 266.7 | 0.2399 | 0.1499 | 0.2059 | 0.1236 |
| 9 | 300.0 | 0.2103 | 0.0902 | 0.1812 | 0.0689 |
| 10 | 333.3 | 0.1875 | 0.0449 | 0.1632 | 0.0288 |
| 11 | 366.7 | 0.1691 | 0.0120 | 0.1498 | 0.0004 |
| 12 | 400.0 | 0.1542 | -0.0113 | 0.1396 | -0.0199 |
| 13 | 433.3 | 0.1414 | -0.0286 | 0.1299 | -0.0350 |
| 14 | 466.7 | 0.1310 | -0.0419 | 0.1206 | -0.0467 |
| 15 | 500.0 | 0.1214 | -0.0530 | 0.1106 | -0.0562 |
| 16 | 533.3 | 0.1109 | -0.0625 | 0.1001 | -0.0642 |

## CE-optimal constants and persistence references

For class C without useful conditioning, the CE-optimal distribution is the full marginal q(c)=P(C=c), with risk H(C). It is **not** a hard all-zero distribution: putting probability 1 on zero gives infinite unsmoothed CE when a nonzero label occurs. Median/mode decoding of the marginal nevertheless returns zero on both populations. The MAE-optimal signed constant is exactly zero; the MSE-optimal constant is the signed mean, close to zero.

Hard class persistence is also infinite-CE on any class change. Two finite probabilistic references clarify the question:

- **Sticky family:** probability s on the previous class and (1−s)/30 elsewhere, with s equal to empirical class-stay frequency. Its optimal NLL within that family is −s log(s)−(1−s)log((1−s)/30).
- **Previous-class transition distribution:** empirical q(c_t|c_(t−1)). Its in-sample optimum is empirical conditional entropy, not a proven population Bayes risk. A leave-one-training-session-out count calculation uses other sessions and add-one smoothing in every cell. This checks how much of the in-sample gain survives without scoring counts on their own session.

The latter is an analytical count-based baseline, not a trained policy. Every leave-session-out calculation stays inside its respective cohort; the full-cohort calculation intentionally includes the two frozen-dev registry-train sessions under James's instruction. All CE/NLL values are nats per known axis-step. Raw persistence MAE repeats the previous **human** angle, distinct from class persistence.

| Baseline statistic | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|
| Uniform 31-class CE | 3.4340 | 3.4340 | 3.4340 | 3.4340 |
| Marginal CE / empirical constant optimum | 3.0481 | 2.8210 | 3.0368 | 2.8116 |
| Mode / median class | 15 / 15 | 15 / 15 | 15 / 15 | 15 / 15 |
| Class-persistence accuracy | 43.17% | 46.91% | 42.19% | 46.26% |
| Optimal sticky-family CE | 2.6166 | 2.4969 | 2.6473 | 2.5181 |
| Empirical transition CE | 1.7128 | 1.5653 | 1.7579 | 1.5941 |
| Raw persistence MAE (degrees) | 0.6274 | 0.2646 | 0.6758 | 0.2737 |
| Zero MAE on same pair targets | 1.9081 | 0.8240 | 1.8981 | 0.8202 |
| Pair count | 144945 | 144945 | 324973 | 324973 |
| Leave-session-out marginal CE | 3.0497 | 2.8224 | 3.0378 | 2.8123 |
| Leave-session-out transition CE | 1.7216 | 1.5722 | 1.7621 | 1.5973 |

Human past camera class contains substantial predictive information in both datasets; target unpredictability alone cannot explain collapse. This is also the known shortcut risk: live execution has its own commands, not the human's next trajectory. Neither empirical transitions nor raw persistence are proposed as autonomous controllers.

These train MAEs do not reproduce the brief's dev zero/persistence figures (1.2246/0.418 degrees); those are different populations. Inclusion of dev identities in the full descriptive aggregate does not make that aggregate the original dev evaluation.

### Training-window exposure

Native `steps.tile` and `loss_mask_start` were applied at window=96, stride=64, burn-in=32, lag=0. This counts scored elements across windows, not exact per-minibatch normalisation, augmentation or round-3 idle weights.

| Population | Scored occurrences per axis | Yaw zero | Pitch zero | Yaw marginal CE | Pitch marginal CE |
|---|---:|---:|---:|---:|---:|
| Interim | 145408 | 17.87% | 18.74% | 3.0480 | 2.8213 |
| Full admitted | 326112 | 18.82% | 19.70% | 3.0365 | 2.8116 |

Window exposure shifts zero share by no more than 0.020 percentage points in either cohort. It does not create a majority-zero loss target.

## Coarser displacement targets

For each within-run H-step window, sum signed raw degrees. Zero uses the same <0.025-degree deadband for diagnosis only. Retained displacement = sum(|sum_H angle|) / sum(sum_H |angle|), measuring cancellation. It does not measure prediction quality.

| Horizon statistic | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|
| H=4: Complete windows | 144921 | 144921 | 324911 | 324911 |
| H=4: Zero net share | 9.03% | 9.74% | 9.51% | 10.23% |
| H=4: Signed median (degrees) | 0 | 0 | 0 | 0 |
| H=4: Median absolute sum | 2.8113 | 1.6868 | 2.6790 | 1.6206 |
| H=4: p95 absolute sum | 31.1555 | 11.7081 | 31.5524 | 11.7743 |
| H=4: Retained displacement | 98.46% | 97.69% | 98.32% | 97.45% |
| H=8: Complete windows | 144873 | 144873 | 324787 | 324787 |
| H=8: Zero net share | 4.24% | 4.70% | 4.54% | 5.00% |
| H=8: Signed median (degrees) | 0 | 0 | 0 | 0 |
| H=8: Median absolute sum | 6.1848 | 3.4397 | 6.0194 | 3.3405 |
| H=8: p95 absolute sum | 58.6068 | 21.0680 | 59.0037 | 21.1011 |
| H=8: Retained displacement | 95.52% | 92.29% | 95.27% | 91.71% |

**Important unchanged conclusion:** fewer exactly zero labels do not remove signed cancellation across alternative directions. The unconditional median remains zero at H=4 and H=8 on both axes. Full-cohort yaw p95 displacement is 31.55 degrees at H=4 and 59.00 at H=8. These targets need horizon-aware units/bins; sending a summed displacement through the existing single-step cap or issuing it all at once would be wrong.

## Ranked target options for Policy explore

These rankings and costs are engineering inferences from the measured statistics. No architecture has been trained or compared here. The [steering charter](../../steering/charter-20260926.md) permits bounded explore sweeps without confirm-stage pre-registration; mandatory independent review of admission/input boundaries remains unchanged.

| Rank | Option and mechanism | Cost | Metric that would support it | Principal risk |
|---|---|---|---|---|
| 1 | H=4 trajectory plus auxiliary cumulative displacement, replan every step; H=8 follow-up | Medium head/target work; modest extra outputs, benchmark runtime | Better conditional NLL and fixed-horizon signed displacement MAE versus matched H=1; onset/reversal sign and live camera response improve | A trajectory of marginal means/medians still collapses; visual information may be absent |
| 2 | Moving → sign → magnitude, with explicit zero event | Low–medium; no new data | Moving calibration/PR, conditional sign accuracy and signed MAE improve without false-motion inflation | Exact likelihood reparameterisation has no statistical advantage by itself; changed decoding may merely force motion |
| 3 | Coarser H=4 or H=8 displacement as the primary camera target | Low–medium targets/head; additional execution design for live use | Same-horizon zero/persistence-relative displacement error and timing-sensitive aim measures improve | Unconditional median stays zero; smearing turns loses within-window timing |
| 4 | Better conditioning check: short causal visual motion context with existing targets | Medium encoder/context change; more frames/features | Same 31-class CE beats marginal, with correct moving sign and visual ablation sensitivity | Context may still reveal human trajectory rather than actionable target error; latency |
| 5 | Likelihood-trained joint trajectory mixture; diffusion later | Medium for small mixture, high for diffusion | Held-out conditional likelihood and coherent-turn error improve, not merely activity | Component means/median decoding can still cancel; ungrounded sampled directions |
| 6 | Discretised-log magnitude / bin redesign alone | Low–medium, checkpoint format changes | Lower quantisation floor plus improved conditional likelihood/aim | Already approximately logarithmic; no evidence binning is the dominant failure |

**1 — Trajectory with cumulative supervision.** In `policy/range_bc/model.py`, make the camera head emit H future bins from the current causal recurrent state; in `train.py`, build within-run future targets and optionally an auxiliary signed cumulative-displacement term. An independent CE at each horizon is a multi-step baseline, not automatically a coherent joint mode. Compare it to a shared trajectory latent or temporally coupled head only if marginal collapse persists. Keep observation time fixed, labels in the future, unknown/boundary masks and semantic button outputs unchanged. Replan at 30 Hz and initially execute only horizon 0 through existing saturation; a later coherent sampler must log its mode and executed history. Track both displacement and sign so a zero prediction cannot look successful just by exploiting symmetry. ACT demonstrates action-sequence imitation in robot manipulation, and Diffusion Policy demonstrates multimodal trajectory modeling with receding-horizon execution; neither establishes Rivals gains. [ACT](https://arxiv.org/abs/2304.13705), [Diffusion Policy](https://arxiv.org/abs/2303.04137).

**2 — Factored moving/sign/magnitude.** First use the existing zero definition, not a newly tuned 0.5-degree “moving” deadband: P(nonzero) is already about 81% on both axes. In `model.py`, expose a binary movement probability, sign conditional on movement, and positive log-spaced magnitude conditional on movement/sign; `train.py` masks conditional losses on zeros while retaining all steps for the movement loss. Their likelihood factors can represent exactly the same 31-class distribution, so correctly weighted summed log-loss is a reparameterisation, not a cure. Reconstructing the joint distribution then taking its original median/argmax still returns zero for the marginal baseline. Sequentially thresholding “moving” and then selecting sign changes the decision rule and can produce motion without skill; report this explicitly. Check moving precision/calibration, signed error and false turns during actual zero labels. `vocab.py` and checkpoint metadata must identify the factorisation; any live decode change needs input-path review. This proposal is a mathematical decomposition plus local evidence, not an asserted published result.

**3 — Coarser primary displacement.** In `train.py`, derive D_H=sum of future H raw degree labels without deleting time or rows. `model.py` predicts that signed sum (or its rate D_H/H); `vocab.py` needs horizon-aware units/bins if categorical. Prefer an auxiliary forecast first, because a net sum leaves execution within the window unspecified. Broadcasting D_H/H across future steps is a new low-pass control policy and may erase reversals, so measure it separately before live use. Compare to zero, H times the preceding human velocity, and any fixed-horizon baseline on identical target windows; do not compare a sum MAE directly with a one-step MAE. The rationale is measured activity and low four-step cancellation, not a literature guarantee. Constant zero remains the MAE-optimal uninformed sum predictor.

**4 — Check conditioning before adding expressivity.** The train transition baseline demonstrates accessible *action-history* information, not necessarily accessible *visual* information. A bounded `model.py`/feature path comparison using a short causal stack or frame-feature differences, with the current `train.py` camera labels unchanged, could test whether visual motion and target-relative direction are lost by frozen single-frame features or the recurrent core. Compare original conditioning, no-action-history visual conditioning and a declared teacher-history diagnostic; never grant future frames to the policy. Keep onset/reversal strata to expose a persistence-only solution. This is a local inference from 0.914 lag-one yaw correlation, not evidence that optical flow or a longer context will solve aim. Retain the capture/input alignment assumptions; no new lag may be justified merely by choosing the best train correlation.

**5 — Mixture or diffusion.** A small joint distribution over signed yaw/pitch trajectories can separate alternative coherent turns, trained by likelihood rather than MSE of a single mean. Modify the camera head and `train.py` loss, with versioned output metadata and explicit mode/sampling behavior; don't take the mixture expectation and assume multimodality survived execution. A mixture needs identifiable conditional modes; the present histograms only establish marginal symmetry, not multiple valid modes at the same observed state. Compare to the same-horizon categorical head before introducing expensive denoising. [Bishop's primary mixture-density report](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bishop-ncrg-94-004.pdf) explains conditional distributions and the failure of averaging multiple valid continuous targets; [Diffusion Policy](https://arxiv.org/abs/2303.04137) supplies trajectory-modeling evidence in robots. No result here shows a mixture is needed.

**6 — Log magnitude / quantisation alone.** The current representatives already grow roughly geometrically, with 0.025-degree zero deadband below one mouse count. Thus “discretise the camera” and “use log-spaced magnitudes” are largely already done. A within-bin residual or revised nonzero spacing in `vocab.py` plus the camera head could reduce the measured 0.2031-degree yaw / 0.0975-degree pitch quantisation floor, but it does not explain a 1.3591-degree mean-axis zero predictor. Benchmark a perfect class-label quantise/dequantise oracle before spending on bin redesign; retain the same units and horizon. VPT uses discretised camera actions as an established alternative to direct continuous regression, but its scale and result do not prove our existing bins optimal. [VPT, action-space appendix](https://arxiv.org/html/2206.11795v1).


## Measured versus inferred

Measured: all label statistics and analytical baselines in the tables, exact session membership, file-hash equality, and memory. The main computation peaked at **112.51 MiB**; the supplemental computation at **62.94 MiB**. Both stream JSONL with standard-library Python.

Inferred: a marginal-like head suffices to explain deterministic zero outputs, and short-horizon supervision is a reasonable explore candidate. The decoder audit alone cannot prove that learned probabilities equal the marginal; many distributions have the same median/mode. Compare conditional NLL and conditioning sensitivity before claiming the mechanism verified.

Unknown: checkpoint calibration, target intent observability, pixel/input timing adequacy, actual game-camera rotation, and live aim. Correlation does not prove current visual features contain the needed directional signal. Fixed human-video self-feeding has no visual consequences of the agent's actions. No statistic here establishes a successful treatment. The [steering charter](../../steering/charter-20260926.md) still places live evidence in the guarded execution work.

## Exact histograms

Counts sum to 144,957 per interim axis and 325,004 per full axis. Representatives are class outputs, not exact values of all members in a bin.

| Class | Representative degrees | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|---:|
| 0 | -40 | 34 | 0 | 133 | 0 |
| 1 | -28 | 198 | 0 | 617 | 0 |
| 2 | -19 | 656 | 0 | 1600 | 0 |
| 3 | -13 | 1250 | 18 | 2863 | 38 |
| 4 | -9 | 2217 | 136 | 4841 | 315 |
| 5 | -6 | 3750 | 717 | 7807 | 1723 |
| 6 | -4 | 5247 | 2695 | 11105 | 6078 |
| 7 | -2.5 | 6195 | 5380 | 13179 | 12087 |
| 8 | -1.6 | 6491 | 7463 | 13956 | 16289 |
| 9 | -1 | 7101 | 8691 | 15373 | 19213 |
| 10 | -0.6 | 6919 | 8999 | 15242 | 19277 |
| 11 | -0.35 | 6028 | 7668 | 13267 | 16694 |
| 12 | -0.2 | 3955 | 4898 | 8799 | 10760 |
| 13 | -0.1 | 3301 | 3995 | 7499 | 9037 |
| 14 | -0.05 | 5075 | 5964 | 11421 | 13480 |
| 15 | 0 | 25887 | 27157 | 61115 | 63983 |
| 16 | 0.05 | 5294 | 6315 | 11907 | 14333 |
| 17 | 0.1 | 3345 | 4676 | 7659 | 10386 |
| 18 | 0.2 | 4004 | 5645 | 9161 | 12670 |
| 19 | 0.35 | 6123 | 8971 | 13845 | 19950 |
| 20 | 0.6 | 7302 | 10113 | 16689 | 22213 |
| 21 | 1 | 7490 | 9461 | 17102 | 20850 |
| 22 | 1.6 | 6702 | 7490 | 15280 | 16569 |
| 23 | 2.5 | 6425 | 5325 | 14264 | 11685 |
| 24 | 4 | 5624 | 2373 | 12283 | 5573 |
| 25 | 6 | 4119 | 699 | 8547 | 1515 |
| 26 | 9 | 2412 | 103 | 5280 | 263 |
| 27 | 13 | 1235 | 5 | 2713 | 22 |
| 28 | 19 | 475 | 0 | 1138 | 1 |
| 29 | 28 | 94 | 0 | 283 | 0 |
| 30 | 40 | 9 | 0 | 36 | 0 |

| Class | Interim yaw scored occurrences | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|
| 0 | 34 | 0 | 133 | 0 |
| 1 | 200 | 0 | 620 | 0 |
| 2 | 660 | 0 | 1612 | 0 |
| 3 | 1256 | 18 | 2880 | 38 |
| 4 | 2225 | 141 | 4856 | 320 |
| 5 | 3763 | 728 | 7835 | 1737 |
| 6 | 5271 | 2714 | 11150 | 6116 |
| 7 | 6218 | 5403 | 13224 | 12137 |
| 8 | 6521 | 7487 | 14005 | 16339 |
| 9 | 7117 | 8718 | 15418 | 19271 |
| 10 | 6932 | 9020 | 15285 | 19328 |
| 11 | 6039 | 7702 | 13295 | 16768 |
| 12 | 3965 | 4916 | 8826 | 10811 |
| 13 | 3310 | 4010 | 7530 | 9078 |
| 14 | 5090 | 5986 | 11469 | 13536 |
| 15 | 25980 | 27255 | 61388 | 64250 |
| 16 | 5312 | 6339 | 11956 | 14380 |
| 17 | 3353 | 4692 | 7683 | 10435 |
| 18 | 4018 | 5649 | 9190 | 12708 |
| 19 | 6141 | 8988 | 13894 | 20019 |
| 20 | 7321 | 10141 | 16737 | 22275 |
| 21 | 7511 | 9472 | 17157 | 20877 |
| 22 | 6732 | 7499 | 15330 | 16589 |
| 23 | 6439 | 5338 | 14299 | 11709 |
| 24 | 5638 | 2385 | 12305 | 5589 |
| 25 | 4128 | 699 | 8564 | 1516 |
| 26 | 2417 | 103 | 5289 | 263 |
| 27 | 1238 | 5 | 2724 | 22 |
| 28 | 476 | 0 | 1139 | 1 |
| 29 | 94 | 0 | 283 | 0 |
| 30 | 9 | 0 | 36 | 0 |

## Every computed scalar, side by side

This table includes all quantiles, horizon/window quantities and ancillary baseline scalars emitted by the calculation, even when not repeated in the headline. Fractions are not percentages here. Names match the reproduction source. Degrees are raw unless identified as classes; likelihoods/entropies use natural logs. Per-session membership statistics follow separately.

| Statistic | Interim yaw | Interim pitch | Full yaw | Full pitch |
|---|---:|---:|---:|---:|
| `n` | 144957 | 144957 | 325004 | 325004 |
| `zero` | 0.178584 | 0.187345 | 0.188044 | 0.196868 |
| `negative` | 0.402995 | 0.390626 | 0.392924 | 0.384583 |
| `positive` | 0.418421 | 0.422029 | 0.419032 | 0.418549 |
| `abs_quantiles.1` | 66.114526 | 15.710055 | 66.114526 | 16.272310 |
| `abs_quantiles.0.1` | 0 | 0 | 0 | 0 |
| `abs_quantiles.0.25` | 0.066148 | 0.066148 | 0.066148 | 0.066148 |
| `abs_quantiles.0.5` | 0.661476 | 0.396886 | 0.628402 | 0.396886 |
| `abs_quantiles.0.75` | 2.282092 | 1.157583 | 2.182871 | 1.124509 |
| `abs_quantiles.0.9` | 5.391029 | 2.215945 | 5.291808 | 2.249018 |
| `abs_quantiles.0.95` | 8.070007 | 3.075863 | 8.169229 | 3.108937 |
| `abs_quantiles.0.99` | 15.776203 | 5.093365 | 16.636121 | 5.126439 |
| `abs_quantiles.0.999` | 27.318959 | 8.137610 | 29.898715 | 8.301524 |
| `signed_mean` | -0.003209 | 0.001078 | -0.010077 | 0.001917 |
| `signed_median` | 0 | 0 | 0 | 0 |
| `zero_mae` | 1.907944 | 0.823969 | 1.897978 | 0.820171 |
| `above_one_share` | 0.414695 | 0.282615 | 0.404318 | 0.279963 |
| `above_one_mass` | 0.919360 | 0.754214 | 0.919020 | 0.757971 |
| `above_half` | 0.543313 | 0.450161 | 0.532147 | 0.443435 |
| `window.n` | 144861 | 144861 | 324756 | 324756 |
| `window.step` | 0.543528 | 0.450397 | 0.532329 | 0.443681 |
| `window.any` | 0.826337 | 0.729831 | 0.825395 | 0.729843 |
| `window.past_any` | 0.826337 | 0.729831 | 0.825395 | 0.729843 |
| `entropy` | 3.048056 | 2.821002 | 3.036815 | 2.811620 |
| `mode` | 15 | 15 | 15 | 15 |
| `median_class` | 15 | 15 | 15 | 15 |
| `median_degrees` | 0 | 0 | 0 | 0 |
| `median_mae` | 1.907944 | 0.823969 | 1.897978 | 0.820171 |
| `quantization_mae` | 0.203778 | 0.097586 | 0.203082 | 0.097459 |
| `pair_n` | 144945 | 144945 | 324973 | 324973 |
| `persistence_mae` | 0.627429 | 0.264615 | 0.675807 | 0.273696 |
| `pair_zero_mae` | 1.908067 | 0.824024 | 1.898113 | 0.820228 |
| `class_persistence_accuracy` | 0.431736 | 0.469109 | 0.421857 | 0.462617 |
| `sticky_nll` | 2.616576 | 2.496903 | 2.647264 | 2.518096 |
| `transition_nll` | 1.712799 | 1.565294 | 1.757870 | 1.594057 |
| `pair_marginal_entropy` | 3.048108 | 2.821051 | 3.036866 | 2.811668 |
| `lag1_mutual_information` | 1.335309 | 1.255757 | 1.278996 | 1.217611 |
| `autocorr.1` | 0.928961 | 0.940107 | 0.914459 | 0.935386 |
| `autocorr.2` | 0.801232 | 0.833330 | 0.764783 | 0.819839 |
| `autocorr.3` | 0.655774 | 0.700247 | 0.604659 | 0.678703 |
| `autocorr.4` | 0.522892 | 0.562770 | 0.468191 | 0.535109 |
| `autocorr.5` | 0.416648 | 0.433957 | 0.365509 | 0.402803 |
| `autocorr.6` | 0.338962 | 0.322743 | 0.293561 | 0.290435 |
| `autocorr.7` | 0.280369 | 0.226035 | 0.241048 | 0.195909 |
| `autocorr.8` | 0.239892 | 0.149902 | 0.205894 | 0.123606 |
| `autocorr.9` | 0.210312 | 0.090178 | 0.181216 | 0.068881 |
| `autocorr.10` | 0.187477 | 0.044891 | 0.163188 | 0.028828 |
| `autocorr.11` | 0.169061 | 0.012019 | 0.149757 | 0.000369 |
| `autocorr.12` | 0.154154 | -0.011306 | 0.139592 | -0.019918 |
| `autocorr.13` | 0.141377 | -0.028604 | 0.129881 | -0.034995 |
| `autocorr.14` | 0.130957 | -0.041941 | 0.120596 | -0.046696 |
| `autocorr.15` | 0.121400 | -0.053002 | 0.110614 | -0.056204 |
| `autocorr.16` | 0.110926 | -0.062464 | 0.100095 | -0.064173 |
| `horizons.4.n` | 144921 | 144921 | 324911 | 324911 |
| `horizons.4.zero_class` | 0.090325 | 0.097412 | 0.095078 | 0.102311 |
| `horizons.4.above_half` | 0.759421 | 0.712568 | 0.754151 | 0.704599 |
| `horizons.4.any_step_above_half` | 0.690286 | 0.589411 | 0.686148 | 0.586533 |
| `horizons.4.abs_quantiles.1` | 182.038195 | 51.065947 | 187.627667 | 51.065947 |
| `horizons.4.abs_quantiles.0.1` | 0.033074 | 0.033074 | 0.033074 | 0 |
| `horizons.4.abs_quantiles.0.25` | 0.562255 | 0.363812 | 0.529181 | 0.363812 |
| `horizons.4.abs_quantiles.0.5` | 2.811273 | 1.686764 | 2.678978 | 1.620616 |
| `horizons.4.abs_quantiles.0.75` | 9.161443 | 4.498037 | 8.830705 | 4.431889 |
| `horizons.4.abs_quantiles.0.9` | 21.134158 | 8.533040 | 20.869568 | 8.566114 |
| `horizons.4.abs_quantiles.0.95` | 31.155520 | 11.708125 | 31.552405 | 11.774273 |
| `horizons.4.abs_quantiles.0.99` | 57.806388 | 18.852066 | 60.194316 | 19.017435 |
| `horizons.4.abs_quantiles.0.999` | 93.686169 | 29.567977 | 99.621262 | 29.835544 |
| `horizons.4.retained_displacement` | 0.984562 | 0.976881 | 0.983216 | 0.974507 |
| `horizons.4.mean_abs_per_step` | 1.878843 | 0.805078 | 1.866505 | 0.799430 |
| `horizons.4.signed_median` | 0 | 0 | 0 | 0 |
| `horizons.8.n` | 144873 | 144873 | 324787 | 324787 |
| `horizons.8.zero_class` | 0.042444 | 0.047014 | 0.045414 | 0.049984 |
| `horizons.8.above_half` | 0.863984 | 0.823238 | 0.861857 | 0.819556 |
| `horizons.8.any_step_above_half` | 0.806044 | 0.707219 | 0.804875 | 0.706906 |
| `horizons.8.abs_quantiles.1` | 215.343512 | 75.375190 | 236.808408 | 79.178677 |
| `horizons.8.abs_quantiles.0.1` | 0.264590 | 0.165369 | 0.264590 | 0.165369 |
| `horizons.8.abs_quantiles.0.25` | 1.587542 | 0.959140 | 1.554469 | 0.926066 |
| `horizons.8.abs_quantiles.0.5` | 6.184801 | 3.439675 | 6.019432 | 3.340454 |
| `horizons.8.abs_quantiles.0.75` | 18.620549 | 8.566114 | 18.190590 | 8.433819 |
| `horizons.8.abs_quantiles.0.9` | 40.912291 | 15.743129 | 40.614626 | 15.710055 |
| `horizons.8.abs_quantiles.0.95` | 58.606774 | 21.068011 | 59.003659 | 21.101084 |
| `horizons.8.abs_quantiles.0.99` | 98.238447 | 32.974579 | 100.643573 | 32.908431 |
| `horizons.8.abs_quantiles.0.999` | 143.610673 | 48.957691 | 147.946185 | 49.180741 |
| `horizons.8.retained_displacement` | 0.955201 | 0.922862 | 0.952739 | 0.917139 |
| `horizons.8.mean_abs_per_step` | 1.823260 | 0.760752 | 1.809115 | 0.752574 |
| `horizons.8.signed_median` | 0 | 0 | 0 | 0 |
| `exposure_loso.scored_mass` | 145408 | 145408 | 326112 | 326112 |
| `exposure_loso.scored_zero` | 0.178670 | 0.187438 | 0.188242 | 0.197018 |
| `exposure_loso.scored_entropy` | 3.047974 | 2.821282 | 3.036545 | 2.811620 |
| `exposure_loso.loso_pairs` | 144945 | 144945 | 324973 | 324973 |
| `exposure_loso.loso_constant_nll` | 3.049674 | 2.822408 | 3.037781 | 2.812293 |
| `exposure_loso.loso_transition_nll` | 1.721582 | 1.572187 | 1.762068 | 1.597283 |

## Session support and reproducibility

Only these ten step payloads were opened. Membership in the historical interim set remains fixed. The two frozen-dev members enter only the full descriptive population under the addendum.

| Session | Membership | Steps | Minutes | Yaw zero | Pitch zero | Yaw zero MAE | Pitch zero MAE | Yaw moving >0.5 degrees | Pitch moving >0.5 degrees |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20260923T051828-422Z-33696-1 | Interim + full | 12550 | 6.9722 | 17.66% | 17.82% | 1.9896 | 0.8930 | 55.55% | 48.96% |
| 20260923T171533-187Z-33696-5 | Full only | 4630 | 2.5722 | 32.74% | 36.31% | 1.2080 | 0.3914 | 37.04% | 21.75% |
| 20260923T200129-346Z-33696-6 | Interim + full | 47910 | 26.6167 | 18.65% | 19.74% | 1.8423 | 0.8092 | 53.67% | 44.60% |
| 20260923T205528-900Z-45572-3 | Full only | 19926 | 11.0700 | 20.91% | 22.12% | 1.8577 | 0.7891 | 52.52% | 42.56% |
| 20260924T232304-170Z-12024-1 | Interim + full | 15777 | 8.7650 | 16.87% | 17.23% | 1.9646 | 0.9338 | 55.02% | 48.73% |
| 20260925T021320-371Z-7804-1 | Interim + full | 62126 | 34.5144 | 17.44% | 18.41% | 1.9306 | 0.7990 | 54.75% | 43.87% |
| 20260925T025230-605Z-7804-2 | Interim + full | 6594 | 3.6633 | 18.74% | 19.79% | 1.8809 | 0.7716 | 51.24% | 42.49% |
| 20260925T203745-207Z-49728-2 | Full only | 82756 | 45.9756 | 19.40% | 20.27% | 1.9116 | 0.8112 | 51.85% | 43.34% |
| 20260926T035932-508Z-63684-14 | Full only | 54270 | 30.1500 | 18.61% | 19.36% | 1.9385 | 0.8448 | 53.21% | 45.20% |
| 20260926T045729-166Z-79780-1 | Full only | 18465 | 10.2583 | 18.39% | 18.73% | 1.8558 | 0.8991 | 55.39% | 48.63% |

Adjacent steps are not independent samples; no frame-level confidence interval or population-generalisation claim is made. Statistics are pooled by step, not equally weighted by recording. Exact hashes below record the inputs, not a new confirm-stage freeze.

| Input | Raw-byte SHA-256 |
|---|---|
| `data/human/session-splits.corpus.json` | `e8a1d0606bfc62fe304e73c78d94f4f62e90d9ef6468a09c486a8f5218ce7e29` |
| `data/human/sealed-denylist.v2.json` | `439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20` |
| `data/human/sessions/tally.json` | `e94e401d38f0323b68102c6ebf2e80ee772a66c6e4eee57570fc8a0dfdc323e3` |
| `policy/range_bc/vocab.py` | `9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e` |
| `policy/range_bc/steps.py` | `3117bf3acbfc2c81bb116d5bbe06feb17b240adf69ef21498c63399e3353b1f1` |

| Train session | Step-file SHA-256 | Assembled manifest SHA-256 |
|---|---|---|
| 20260923T051828-422Z-33696-1 | `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb` | `f428cc64d9efd5e894d79dd6a29f146be323e780919d9332e6a60a11b99590cf` |
| 20260923T171533-187Z-33696-5 | `dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e` | `eb61a5ac010ed82dc20d72b152bfbb4efc129068252df871a7a6ac4576d8f0b4` |
| 20260923T200129-346Z-33696-6 | `fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e` | `93e2452130b267ba39e59b39c3ef3b0f7c7bcbe7307bdc337a58a1eb7850f48f` |
| 20260923T205528-900Z-45572-3 | `941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98` | `c0687e0fe8e9ed1e05a49ebb98757dbf3321ea40f26be291f4eaad82fd9aba53` |
| 20260924T232304-170Z-12024-1 | `8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1` | `ccdf62482e72739dffa373371ceb3ba9a5c382c340bf07129b5613647d1a1fb6` |
| 20260925T021320-371Z-7804-1 | `841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537` | `16fabb73285dde1c0b00acfd57e68fbcf18e8c9e13c2a25787bfb21b81fecf43` |
| 20260925T025230-605Z-7804-2 | `84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288` | `5617d968ac8f0e76fbd5459bc9a0b233e308a74f365309760f0d23166c014ab6` |
| 20260925T203745-207Z-49728-2 | `1fcfffb8fa67bcd1b48684611cfe07cafe6455670f82840eb72e99aa4d9e8373` | `e9860472efd7e0f1cc48544e26d33629de18509e4437fc84f60e379b1ed10673` |
| 20260926T035932-508Z-63684-14 | `1a98150a122f316b9bd975e82ef8453d714466454a25a2d186c341b8baf2bdc2` | `2184320220d387095a6237209d80167d93a50339589ed9fe946f7c7f0a4b8f2d` |
| 20260926T045729-166Z-79780-1 | `92ba60cf62f413a87adf3cd8d8b04647c4d004b79c9f2f4bde7647b808baae38` | `596883a2bbe7e81f25c694684ea6a6ae1eff62f85fef982def4b10cf4febad5a` |

### Reproduction source

Run inline through `uv run --no-project python -B -` from the repository root. The code writes nothing and emits main and supplementary JSON. All ten selected step hashes match their assembled manifests. Inclusion of 171533/205528 is deliberate under the full-cohort addendum; no role or source file is edited.

Quantiles interpolate at (n−1)p. Correlation pools pair moments separately per lag. Horizon statistics enumerate complete overlapping windows. Code and data identities above should be compared before interpreting any future rerun.

<details>
<summary>Read-only standard-library calculation</summary>

```python
import json, math, hashlib, statistics, ctypes
from pathlib import Path
from array import array
from collections import Counter
from policy.range_bc import vocab
ROOT=Path.cwd()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def lfsha(p): return hashlib.sha256(Path(p).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
reg=read('data/human/session-splits.corpus.json'); deny=read('data/human/sealed-denylist.v2.json'); tally=read('data/human/sessions/tally.json')
dev={'20260923T171533-187Z-33696-5','20260923T205528-900Z-45572-3'}
interim={'20260923T051828-422Z-33696-1','20260923T200129-346Z-33696-6','20260924T232304-170Z-12024-1','20260925T021320-371Z-7804-1','20260925T025230-605Z-7804-2'}
denids={r['session_id'] for r in deny['sessions']}; denhash={r['media_sha256'] for r in deny['sessions']}
norm=lambda s:s.replace('\\','/').lower()
denpaths={norm(r['media_path']) for r in deny['sessions']}
placements={r['session_id']:r for r in reg['sessions']}
selected=[]
for r in tally['rows']:
 sid=r['session']
 if r.get('status')!='admitted' or r.get('split')!='train':continue
 p=placements[sid]
 assert p['split']=='train' and not p.get('sealed',False) and sid not in denids and p['expected_media_sha256'] not in denhash
 assert all(norm(p.get(k,'')) not in denpaths for k in ('video_path','recorded_video_path'))
 selected.append(sid)
assert len(selected)==10 and interim<=set(selected)
sessions={}; provenance=[]; total_unknown=0
for sid in selected:
 base=Path('data/human/sessions')/sid
 art=read(base/'artifact-hashes.json')
 assert art['session']==sid and art['status']=='assembled' and art['split']=='train'
 path=base/(sid+'.steps.jsonl'); expected=art['files'][path.as_posix()]
 actual=sha(path); assert actual==expected, (sid,actual,expected)
 runs=[]; run=[]; prev=None; counts=Counter()
 with path.open(encoding='utf-8-sig') as f:
  header=json.loads(next(f))
  assert header['session_id']==sid and header['split']=='train' and not header.get('sealed',False)
  assert header['media_sha256']==placements[sid]['expected_media_sha256'] and header['media_sha256'] not in denhash
  cal=header['calibration']; assert header['step_ns']==33333333
  for line in f:
   r=json.loads(line); counts['rows']+=1
   eligible=r['suitability']=='accepted' and r['regime']=='normal'
   contiguous=prev is None or (r['run']==prev[0] and r['i']==prev[1]+1 and r['anchor_ns']-prev[2]==header['step_ns'])
   if run and (not eligible or not contiguous):
    runs.append(run);run=[]
   if eligible:
    counts['eligible']+=1
    valid=r['gap_free'] and r['relative_known']
    y=r['mouse_dx']*cal['yaw_deg_per_count'] if valid else None
    p=r['mouse_dy']*cal['pitch_deg_per_count'] if valid and cal['pitch_deg_per_count'] is not None else None
    run.append((y,p))
    counts['unknown_yaw']+=y is None;counts['unknown_pitch']+=p is None
   prev=(r['run'],r['i'],r['anchor_ns'])
  if run:runs.append(run)
 kept=[r for r in runs if len(r)>=48]
 counts['short_run_rows']=sum(len(r) for r in runs if len(r)<48)
 counts['kept_rows']=sum(map(len,kept));counts['kept_runs']=len(kept)
 sessions[sid]=kept
 provenance.append(dict(sid=sid,step_sha256=actual,artifact_sha256=sha(base/'artifact-hashes.json'),counts=dict(counts),calibration=cal,interim=sid in interim))
def quant(a,ps=(.1,.25,.5,.75,.9,.95,.99,.999,1)):
 a=sorted(a);n=len(a)
 def q(p):
  x=(n-1)*p;l=int(x);return a[l]+(a[min(l+1,n-1)]-a[l])*(x-l)
 return {str(p):q(p) for p in ps}
def entropy(hist):
 n=sum(hist);return -sum(c/n*math.log(c/n) for c in hist if c)
def stats(ids,axis):
 runs=[]
 for sid in ids:
  for rr in sessions[sid]:
   part=[]
   for row in rr:
    if row[axis] is None:
     if part:runs.append(part);part=[]
    else:part.append(row[axis])
   if part:runs.append(part)
 vals=[v for r in runs for v in r]; n=len(vals); av=[abs(v) for v in vals];hist=[0]*31
 classes=[]
 for r in runs:
  cs=[vocab.camera_class(v) for v in r];classes.append(cs)
  for c in cs:hist[c]+=1
 pairs=[[0]*31 for _ in range(31)];persist_mae=0;pair_n=0; pair_zero=0
 for r,cs in zip(runs,classes):
  for i in range(1,len(r)):
   pairs[cs[i-1]][cs[i]]+=1;pair_n+=1
   persist_mae+=abs(r[i]-r[i-1]);pair_zero+=abs(r[i])
 cond=sum(sum(row)*entropy(row) for row in pairs)/pair_n
 current=[sum(row[c] for row in pairs) for c in range(31)]
 stay=sum(pairs[i][i] for i in range(31))/pair_n
 sticky=-(stay*math.log(stay)+(1-stay)*math.log((1-stay)/30))
 mode=max(range(31),key=lambda c:hist[c]);median=vocab.median_class([c/n for c in hist])
 window_n=window_step=window_any=window_past=0
 for r in runs:
  move=[int(abs(v)>.5) for v in r];pref=[0]
  for m in move:pref.append(pref[-1]+m)
  for i in range(4,len(r)-4):
   window_n+=1;window_step+=move[i];window_any+=pref[i+5]-pref[i-4]>0
  for i in range(8,len(r)):
   window_past+=pref[i+1]-pref[i-8]>0
 past_n=sum(max(0,len(r)-8) for r in runs)
 ac=[]
 for lag in range(1,17):
  N=0;sx=sy=sxx=syy=sxy=0.
  for r in runs:
   for i in range(lag,len(r)):
    x=r[i-lag];y=r[i];N+=1;sx+=x;sy+=y;sxx+=x*x;syy+=y*y;sxy+=x*y
  cov=sxy-sx*sy/N
  ac.append(cov/math.sqrt((sxx-sx*sx/N)*(syy-sy*sy/N)))
 horizons={}
 for H in (4,8):
  sums=[];totabs=0.;coherent=0;anymoves=0
  for r in runs:
   for i in range(len(r)-H+1):
    seq=r[i:i+H];s=sum(seq);sums.append(s);totabs+=sum(abs(x) for x in seq);anymoves+=any(abs(x)>.5 for x in seq)
  N=len(sums);hh=Counter(vocab.camera_class(s) for s in sums)
  horizons[H]=dict(n=N,zero_class=hh[15]/N,above_half=sum(abs(s)>.5 for s in sums)/N,any_step_above_half=anymoves/N,
   abs_quantiles=quant([abs(s) for s in sums]),retained_displacement=sum(abs(s) for s in sums)/totabs,
   mean_abs_per_step=sum(abs(s) for s in sums)/N/H, signed_median=statistics.median(sums))
 # Rounded-class reconstruction vs raw target
 qmae=sum(abs(v-vocab.class_degrees(vocab.camera_class(v))) for v in vals)/n
 return dict(n=n,hist=hist,zero=hist[15]/n,negative=sum(v<0 for v in vals)/n,positive=sum(v>0 for v in vals)/n,
  abs_quantiles=quant(av),signed_mean=sum(vals)/n,signed_median=statistics.median(vals),zero_mae=sum(av)/n,
  above_one_share=sum(x>1 for x in av)/n,above_one_mass=sum(x for x in av if x>1)/sum(av),
  above_half=sum(x>.5 for x in av)/n,window=dict(n=window_n,step=window_step/window_n,any=window_any/window_n,past_any=window_past/past_n),
  entropy=entropy(hist),mode=mode,median_class=median,median_degrees=vocab.class_degrees(median),
  median_mae=sum(abs(v-vocab.class_degrees(median)) for v in vals)/n,quantization_mae=qmae,
  pair_n=pair_n,persistence_mae=persist_mae/pair_n,pair_zero_mae=pair_zero/pair_n,class_persistence_accuracy=stay,
  sticky_nll=sticky,transition_nll=cond,pair_marginal_entropy=entropy(current),lag1_mutual_information=entropy(current)-cond,
  autocorr=ac,horizons=horizons)
result={'selection':provenance,'metadata':{p:sha(p) for p in ('data/human/session-splits.corpus.json','data/human/sealed-denylist.v2.json','data/human/sessions/tally.json','policy/range_bc/vocab.py','policy/range_bc/steps.py')},'stats':{}}
for name,ids in [('interim',sorted(interim)),('full_admitted',selected)]:
 result['stats'][name]={axis:stats(ids,i) for i,axis in enumerate(('yaw','pitch'))}
result['session_summary']=[]
for sid in selected:
 rr=sessions[sid]; row={'sid':sid,'n':sum(map(len,rr))}
 for axis,i in [('yaw',0),('pitch',1)]:
  vals=[r[i] for run in rr for r in run if r[i] is not None]
  row[axis]={'zero':sum(vocab.camera_class(v)==15 for v in vals)/len(vals),'zero_mae':sum(abs(v) for v in vals)/len(vals),'move_half':sum(abs(v)>.5 for v in vals)/len(vals)}
 result['session_summary'].append(row)
class PMC(ctypes.Structure):
 _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
pm=PMC();pm.cb=ctypes.sizeof(pm)
kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(PMC),ctypes.c_ulong]
psapi.GetProcessMemoryInfo.restype=ctypes.c_int
assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(pm),pm.cb)
result['peak_working_set_bytes']=pm.PeakWorkingSetSize
print(json.dumps(result))

from policy.range_bc import steps
def entropy(hist):
 n=sum(hist);return -sum(c/n*math.log(c/n) for c in hist if c)
summary={}
for cohort,ids in [('interim',sorted(interim)),('full_admitted',selected)]:
 out={}
 for a,axis in enumerate(('yaw','pitch')):
  hist=[0]*31;ss={};n=0
  for sid in ids:
   sh=[0]*31;mat=[[0]*31 for _ in range(31)]
   for run in sessions[sid]:
    cs=[vocab.camera_class(r[a]) for r in run]
    for c in cs:sh[c]+=1
    for i in range(1,len(cs)):mat[cs[i-1]][cs[i]]+=1
    for st,L in steps.tile(0,len(run),window=96,stride=64,min_run=48):
     for i in range(st+steps.loss_mask_start(st,0,32),st+L):
      hist[cs[i]]+=1;n+=1
   ss[sid]=(sh,mat)
  totalh=[sum(ss[s][0][c] for s in ids) for c in range(31)]
  totalm=[[sum(ss[s][1][p][c] for s in ids) for c in range(31)] for p in range(31)]
  lconst=ltrans=0.;pn=0
  for sid in ids:
   h,m=ss[sid]; nh=[totalh[c]-h[c] for c in range(31)];N=sum(nh)
   for p in range(31):
    nr=[totalm[p][c]-m[p][c] for c in range(31)];nrn=sum(nr)
    for c in range(31):
     count=m[p][c];pn+=count
     lconst-=count*math.log((nh[c]+1)/(N+31))
     ltrans-=count*math.log((nr[c]+1)/(nrn+31))
  out[axis]={'scored_mass':n,'scored_zero':hist[15]/n,'scored_hist':hist,'scored_entropy':entropy(hist),
    'loso_pairs':pn,'loso_constant_nll':lconst/pn,'loso_transition_nll':ltrans/pn}
 summary[cohort]=out
# Memory accounting for actual bounded streaming computation
class PMC(ctypes.Structure):
 _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(PMC),ctypes.c_ulong]
psapi.GetProcessMemoryInfo.restype=ctypes.c_int
pm=PMC();pm.cb=ctypes.sizeof(pm)
assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(pm),pm.cb)
print(json.dumps({'extra':summary,'peak_working_set_bytes':pm.PeakWorkingSetSize}))

```

</details>
