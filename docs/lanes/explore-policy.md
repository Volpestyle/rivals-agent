# EXPLORATORY — short action chunks (2026-09-26)

Owner: explore-policy. VUH-1346, Policy team, EXPLORE track. **Full caches complete; Mac H=1 running; Modal H=1/H=4/H=8 upload in progress.**
The dated 2026-09-27 lead authorization grants a separate $30 hard Modal explore cap for device-matched H=1/H=4/H=8, with a warning before projections reach about $28. Mac H=1 continues as a cross-device check; round 3 retains its own budget and resources.
Lead authorized an explore-only commit on 2026-09-27 once the full-run code is final.
No validation, test, Gate 2 or sealed payloads are used.

The comparison is H=1/4/8, trained on all valid future offsets, executing only
offset zero and replanning each step. Existing no-HUD encoder/LSTM, lr 3e-4,
batch 8, stride 64, lag 0, previous-action dropout 0.2, weighted BCE and camera CE.
Future targets cannot cross an eligible run; padding, burn-in, invalid rows and
per-channel unknowns mask their losses. H=1 retains the original initialization.

**Cohort:** corpus registry TRAIN rows intersected with admitted, positive
`trainable_min` rows in `data/human/sessions/tally.json`, minus frozen dev
171533 and 205528. This is eight training sessions: **166.9261 admitted minutes,
166.9156 trainable minutes**. Both 09-22 sessions are held, not training data.
The missing Mac steps/cache preparation concerns 203745, 035932 and 045729.
Preparation uses the existing pipeline under `range-bc-data/explore/`.
Admission-owner confirmed the three originals, logger triples and frozen step
tables exist only on the PC: **78,055,082,413 bytes of original video**, no
transcodes or relocation receipts. Transfer started 20:50 CDT (PC PID 111404),
with 1 MiB buffers, streaming source hashes against freezes, and a fresh Mac
file hash before each partial is renamed. **All 33 files completed and were
verified at both ends by 23:24 CDT**; originals and frozen step tables are ready. The first GiB took 492.6 s; native SCP/AES-GCM
probes did not improve it. PC priority Idle, Mac nice 15, peak driver RAM
19.3 MB. Transfer finished; cache build: queued after interim H=1 evaluation.
Lead approved dropping interim H=4/H=8 and proceeding to fresh full-cohort arms.

**Epochs:** the lead approved 26 matched epochs, seed 0 first. The 13-epoch recipe
was chosen on 33.59 minutes, and earlier curves often still fell at its cap
([assumption audit](../research/assumption-audit.md), findings 1 and 3). Keep
per-head, step-one dev curves and epoch-13 snapshots. An epoch-13 snapshot belongs
to the **26-epoch cosine schedule**, not a replication of the old 13-epoch fit.
Use the final epoch for the sweep; report convergence limits. Add seeds 1–2 only
if a chunk arm improves self-fed checks.

| Arm, seed 0 | Epochs | S1 onset / S2 pooled + per-action press ratios | S3 camera / S4 any hold | T / F | Wall time |
|---|---:|---|---|---|---|
| H=1 (interim) | 26 complete | See six-decode table below | Worse than zero motion | See below | 155.78 min fit + 2.68 min eval |
| H=4 (full, Modal L40S) | 26 planned | Not run | Not run | Not run | Upload in progress |
| H=8 (full, Modal L40S) | 26 planned | Not run | Not run | Not run | Upload in progress |
| H=1 (full, Mac MPS) | 26 planned | Not evaluated | Not evaluated | Not evaluated | Training |
| H=1 (full, Modal L40S) | 26 planned | Not run | Not run | Not run | Upload in progress |

Each arm will have **fixed 0.5** and **TRAIN-chosen per-action threshold** rows,
each under **median, mode and expectation** camera decoding.
Calibration now matches the audited exact binary64 interval search over [0,1]
for TRAIN executed press counts (hold rises plus taps), including zero-positive
actions; ties prefer the threshold closest to 0.5, then the lower threshold. Each condition carries its own executed feedback. Existing
`metrics.EXECUTED_TEACHER`, `metrics.SELF` and `selffed_checks` provide T/F and
S1–S4, including per-action ratios; camera references are persistence 0.418°,
AR2 0.376°, and frozen-dev zero-motion 1.2246° are historical dev references.
Recompute TRAIN/dev zero-motion, persistence and train-fitted AR2 for each cohort.
No new judge. The completed decoder audit (`handoff/research/decoder/RESULTS.md`)
found 0/9 train-calibrated checkpoint decodes passed S2/S3, and none of the camera
decoders recovered motion. These decoder interventions were insufficient; the
result does not by itself isolate the cause of the rollout collapse. Both
threshold conditions remain in this sweep for comparability. The implementation
adapts r3-sidecar's `button_audit.py` exact interval helper, replacing the draft grid.

**H=1 camera pre-step:** camera and moving-sign NLL with real versus zeroed visual
features, keeping teacher action history fixed. Credit
[research-methods](../research/camera-targets/analysis.md): zero is a minority
label but the marginal mode/median; full-cohort continuity is weaker. This
ablation is an out-of-distribution sensitivity diagnostic, not proof the encoder
lacks direction. Cumulative-trajectory loss remains a separate candidate; this
H comparison retains matched CE/BCE.

**Implemented and synthetic-tested:** `policy/range_bc/explore_chunks.py`,
`explore_chunks_train.py`, `explore_chunks_eval.py`, `explore_camera.py`,
`explore_thresholds.py`, and tests in
`tests/test_range_bc_explore_chunks.py`. Tests cover H=1 output/loss/gradient
parity, all-head learning with step-one-only execution, target masks, resumed
optimizer/RNG state, cohort rejection before payload access, and threshold
decoding, legacy median-rollout parity, independent decoder histories, and masked
conditioning NLL. **16 CPU tests passed in 9.36 s** using an isolated environment
on the PC (lead-authorized); targeted Ruff checks pass. The default environment
lacked PyTorch and skipped this module, so that first attempt was not a test pass.
Review request withdrawn on the lead's direction: fit-review stays on round 3.
Before withdrawal, two findings were observed and fixed: float32-cutoff decisions
now match the executor exactly, and resume binds actual target tensors and the
complete window schedule. Their regression tests are included. Exact threshold search is additionally
checked against exhaustive boundary candidates, including 0/1, unknown rows,
run resets, taps and zero-positive actions.

**Mac compute queue:** r3-sidecar released at 21:42 CDT; idm-lab explicitly
released at 22:01 CDT after exit 0. Explore took the slot and launched the
sequential interim sweep at 22:06 CDT, nice 15, shell PID 42194. Modal upload finished; transfer was authorized meanwhile. The lead
also authorized using existing interim data while originals land: `--cohort interim`
means five train (**80.5317 trainable minutes**) plus two frozen dev sessions,
reported separately. Full-cohort
runs use their own fixed inputs; resume refuses a cohort switch. No new cache
job has run. The running code snapshot is `explore/code-107970b4/`, with two
verified overlays; its native Python 3.12 environment uses locked torch 2.14.0.
The MPS operation/backward probe passed; all 16 synthetic Mac tests passed in
4.42 s. First setup failed on a fractional status timestamp before environment
creation; callers now use whole seconds and the successful retry is recorded.
The trainer saves an epoch checkpoint and can yield at the next update through
a stop file, preserving its resume state. These are heavily reused-dev
diagnostics; any candidate needs a registered CONFIRM run before a real fit or
pilot. More presses alone would not establish learned timing or gameplay skill.

**Dashboard receipts:** existing transfer publishes via `scripts/job_status.py`
to `C:/Users/volpe/jobs/explore-originals-transfer.status.json`. Its receipt-only
monitor reads progress/exit files without restarting transfer or reading video.
Train/eval CLIs require `--job-name` and absolute `--log`, publish start/progress
and done/failed to Mac `~/dev/jobs/`; checkpointed yields return to queued.
The native venv belongs to this code snapshot. Sweep outputs/logs/PID/exit files
are under `explore/interim-chunks26-seed0/`; `STOP` there yields at the next
training update and prevents later arms. Jobs run H=1 train/eval, H=4 train/eval,
H=8 train/eval were the original interim queue. On 2026-09-27 the lead dropped
interim H=4/H=8. A successor STOP was set only after H=1 training exited 0 and
its evaluator started at 00:43 CDT; that evaluator finishes normally, then the
wrapper exits before H=4. Full preparation waits for that exit. No automatic retry.
Dashboard parent
`explore-interim-chunks26-seed0`, with per-arm `explore-interim-h1-train` etc.

**First real checkpoint verified (22:16 CDT):** H=1 completed epoch 1, 284
updates, train chunk loss 2.78589 and step-one dev total 2.39721. The 50,426,571-byte
`latest.pt` existed; epoch 2 then began. This verifies training/dev-loss/saving,
not self-fed improvement. Snapshot of the first status is in
`handoff/explore/interim-h1-first-checkpoint-status.json`. The process launched
with nice 15 reports effective niceness 20 on the Mac; RSS was about 20.2 GiB.

## EXPLORATORY camera-history diagnostic (completed 2026-09-27)

**All six teacher-forced heads beat the TRAIN marginal and their distributions
track previous camera direction strongly.** This rejects the description of an
always-uninformative teacher-forced head. It does not establish causal use of
history rather than correlated vision, nor explain the whole self-fed failure.
Credit: the steering lead's [target-bearing probe](../research/target-bearing/result.md).
Its next-four-step raw-degree R-squared is a different target from this head's
one-step categorical loss.

Existing A (`interim94-s012`) and E (`cm2-e-s012`), seeds 0-2; 24,556 known rows
per axis/checkpoint from frozen dev 171533/205528. No weights were changed.
TRAIN histograms from the checkpoint reports define the marginal. Empirical
prior NLL is **2.964614 yaw / 2.743950 pitch** for every checkpoint; no scored
class is unseen in TRAIN. Jeffreys +0.5 smoothing changes either reference by
less than 0.00003 nats. No dev-fitted prior or checkpoint selection was used.

| Checkpoint | Yaw NLL | Pitch NLL | Median-zero yaw / pitch | Camera share of weighted TF dev loss |
|---|---:|---:|---:|---:|
| A-seed0 | 1.800870 | 1.606428 | 28.23% / 30.66% | 64.81% |
| A-seed1 | 1.787789 | 1.592138 | 27.87% / 29.89% | 64.25% |
| A-seed2 | 1.786697 | 1.598625 | 28.25% / 30.18% | 64.61% |
| E-seed0 | 1.987763 | 1.787963 | 28.15% / 30.10% | 64.00% |
| E-seed1 | 1.992309 | 1.800967 | 29.06% / 29.70% | 63.50% |
| E-seed2 | 1.977307 | 1.782404 | 29.26% / 29.70% | 64.12% |

The full per-previous-class bins are in `handoff/explore/camera-history-class-bins.csv`.
The compact table below pools negative, zero and positive previous classes;
values are means across the three seeds. Class indices run 0-30; zero is 15
(the indices are not degrees). Each seed has yaw bin counts 8,982 / 5,683 /
9,889 and pitch counts 9,127 / 6,089 / 9,338; two run-start rows per axis have
unknown previous class and are kept separate. Same-direction probabilities
include zero mass in the denominator; zero/unknown previous has no direction.

| Arm / axis | Mean predicted class: previous negative / zero / positive | P(same direction): previous negative / positive | Median-zero after previous zero |
|---|---|---|---:|
| A / yaw | 10.01 / 14.92 / 19.94 | 82.92% / 84.14% | 97.52% |
| A / pitch | 10.96 / 14.92 / 19.18 | 82.61% / 85.29% | 96.67% |
| E / yaw | 10.66 / 14.87 / 19.29 | 75.88% / 77.38% | 95.58% |
| E / pitch | 11.38 / 14.82 / 18.80 | 76.60% / 79.69% | 92.70% |

The global mean class near 15 hides this conditioning: left and right predictions
cancel when pooled. A zero previous class does produce a zero median on about
93-98% of rows, consistent with a possible sticky-zero feedback mechanism;
this is an observational diagnostic, not an intervention proving that mechanism.
Under teacher forcing, median decoding retains motion on roughly 69-72% of rows.
The earlier decoder audit instead found A's **self-fed** mean P(zero) about
85% and NLL 4.64/4.85, versus teacher-forced NLL 1.792/1.599 (reproduced here
to reported precision). Keep that feedback distinction: these results neither
justify a universal uninformed-head claim nor show that changing the decoder
alone repairs self-fed rollout.

**Loss audit:** `held_mean + press_mean + release_mean + 0.5*camera_mean`.
Each button term averages known entries across all 15 actions; camera CE averages
known yaw/pitch entries. With all labels known, each action/channel has coefficient
1/15 and each camera axis 0.25, before press/release positive weighting and actual
loss magnitudes. Both report configurations match the source constant. On these
TF dev rows, weighted camera loss is 0.845-0.948 versus 0.463-0.545 for all three
button terms combined: 63.5-64.8% of total scalar loss. This is not a gradient-share
measurement or proof that optimization weighting is correct; it does rule out
simple dilution by 15 summed button losses. Training augmentation, burn-in and
history corruption are not reproduced by these diagnostic dev components.

**Execution and evidence:** six cases completed with exit 0 in 70.2 minutes of
inference, one CPU thread, requested nice 19, no MPS. The fit advanced 3,488
updates over 70.4 minutes (0.826 updates/s). Completed epoch intervals during the
full diagnostic were 285-409 s (median 344 s) versus 319-427 s (median 385 s)
for pre-probe epochs 2-11. No sustained slowdown outside prior variation was
observed; this is not a controlled contention experiment. The running sweep's
code and checkpoints were untouched by the diagnostic. Three synthetic tests
passed on PC and Mac; targeted lint passed; all bin counts and weighted NLL
reconstructions were checked after download.

Raw result: `handoff/explore/camera-history-full.json`, SHA256
`897554469bacd5d1896dca662e31d93c13f232cf6b2bdadcab880137775b0ceb`.
The raw JSON includes checkpoint/source hashes, exact configurations, priors,
all class bins, dev loss components and throughput observations. Mac receipt
`explore-camera-history-six` is done. This is heavily reused-dev EXPLORATORY
evidence, with no causal history ablation, training intervention or gameplay claim.

## Full-cohort transition (lead approved 2026-09-27)

Finish and evaluate interim H=1; interim H=4/H=8 are dropped. Build caches for
203745, 035932 and 045729 from the verified originals and byte-identical frozen
step tables, using the existing Mac cache pipeline under `explore/caches/`.
Then run fresh full H=1/H=4/H=8, seed 0, 26 matched epochs; no interim checkpoint
is resumed on the larger cohort. Mac only, niced, serial heavy work, $0 cloud.
The full runtime will retain the interim legacy-code/lock/data snapshot and
layer the finalized explore modules from the authorized commit, preserving the
matched recipe while changing the declared cohort. It gets its own native venv.

Interim H=1's dev loss rose after its earlier minimum while training loss kept
falling. This is recorded as convergence/overfitting evidence, not a reason to
silently change the approved full-sweep epoch cap or choose a dev-best model.
Epoch-13 snapshots remain snapshots of the 26-epoch cosine schedule.

## EXPLORATORY interim H=1 result (26 epochs, seed 0)

This is the five-session, 80.5317-trainable-minute stopgap control, separate from
the upcoming full cohort. Training/evaluation exited 0; the successor wrapper
exited 75 after evaluation, as requested. Interim H=4/H=8 were not launched.

| Threshold / camera decode | S1 onset recall | S2 pooled press ratio | S3 camera MAE | S4 any-hold share | T | F |
|---|---:|---:|---:|---:|---:|---:|
| fixed_0.5/median | 0.0538 | 0.1037 | 1.4017 | 0.2944 | 0.0859 | 0.0439 |
| fixed_0.5/mode | 0.0685 | 0.1306 | 1.8278 | 0.3239 | 0.0859 | 0.0605 |
| fixed_0.5/expectation | 0.0876 | 0.1664 | 1.9944 | 0.4342 | 0.0859 | 0.0593 |
| train_chosen/median | 0.0037 | 0.0167 | 1.3523 | 0.0153 | 0.0333 | 0.0090 |
| train_chosen/mode | 0.0053 | 0.0252 | 1.7036 | 0.0320 | 0.0333 | 0.0143 |
| train_chosen/expectation | 0.0094 | 0.0285 | 1.8919 | 0.0340 | 0.0333 | 0.0176 |

All six camera MAEs are worse than frozen-dev zero motion (1.224645 degrees),
persistence (0.418271) and TRAIN-refitted AR2 (0.376227). TRAIN calibration does
not rescue rollout here. Per-action onset recall, press ratios and raw counts
are in `handoff/explore/interim-h1-per-action-checks.csv`; complete existing-metric
outputs are in `interim-h1-evaluation.json`. No new judge or pass rule was added.
Training took 155.78 min; evaluation 2.68 min.
Step-one dev total reached 1.250403 at epoch 11, then rose to
1.408418 at epoch 26. Epoch 26 remains the declared endpoint; the
epoch-13 snapshot is from this 26-epoch cosine schedule.

**H=1 visual conditioning pre-step:** real versus zero visual features, keeping
true previous actions fixed, gave camera NLL yaw 1.744729 vs 1.662288 and pitch
1.562909 vs 1.502069. Moving-sign conditional NLL was 0.217642 vs 0.197773 yaw,
0.205489 vs 0.201742 pitch. Zeroing features improved these reused-dev metrics;
this is an out-of-distribution ablation, not proof that visual features contain
no direction or that a trained history-only policy would be better.

**Full transition:** code commit `aca82b4` contains only explore paths; unrelated
shared changes were preserved. Verified runtime `explore/code-full-aca82b4/`
retains legacy base `107970b4` and its lock/metadata, overlays the committed
explore modules, and has its own native venv. MPS backward verification passed.
Pipeline PID 20950 is building 203745, 035932 and 045729 serially with the existing
cache CLI, then runs fresh full H=1/H=4/H=8 train/eval jobs, each 26 epochs.
Logs, stage PIDs/exits and STOP are under `explore/full-chunks26-seed0/`;
dashboard parent `explore-full-chunks26-seed0`. No automatic retry or cohort switch.

## EXPLORATORY Modal exception and queue update (2026-09-27)

All three new cache builds exited 0: 203745 15.76 min, 035932 9.51 min,
045729 3.25 min; 28.52 min total. Their cache sizes are 17.838, 11.430 and
3.865 GB respectively. The ten-session train/frozen-dev cache set is 69.218 GB.
The frozen eight-session training roster and two TRAIN-dev sessions are unchanged.

The one-night PC CUDA option was declined on feasibility: a streamed,
hash-verified SCP sample measured 9.97 MB/s, projecting 115.7 min to transfer the
complete set before verification, beyond the one-hour cutoff. No PC fit ran.
The 16 GB RTX 4080 SUPER versus documented roughly 21 GB fit memory is an
additional untested capacity concern, not a measured OOM.

James first authorized a separate $15 Modal explore budget, then raised it to
a **$30 hard cap** to preserve comparison quality. The final scope on thread
`explore-modal-15` is **H=1, H=4 and H=8**, parallel L40S,
8 CPU cores/32 GiB, seed 0, 26 epochs, execute offset zero and replan.
Mac H=1 continues as a **cross-device MPS versus CUDA check**; the primary
chunk comparison uses the device-matched Modal H=1. Once the cloud
arms are confirmed live, the Mac successor queue will stop after H=1 evaluation,
preserving H=1 and preventing duplicate H=4/H=8 runs.

All cloud arms keep the same model/loss/targets/recipe and per-epoch
dev curves, with final fixed-0.5/train-chosen thresholds crossed with camera
median/mode/expectation. `explore_cloud_run.py` calls the existing fit function;
evaluation now accepts an explicit device with MPS still the default. No AMP,
batch, precision, seed, data selection or loss change is introduced.

At the measured L40S benchmark and published resource rate $2.584224/hour,
the 588 versus 284 updates per epoch project to about 119 min/$5.12 per arm
including epoch-dev checks. Three arms plus setup/final evaluation project to
roughly $16-18; the lead accepts about $21 plus setup/eval, with the
**strict $30 guard** binding even if incomplete and notification at a $27.50
projection or conservative spend bound, ahead of the roughly $28 warning point.
These are extrapolations, not measured chunk-run costs. The original three-arm
estimate exceeded $15 before final evaluation; James then funded device matching
instead of retaining a cheaper cross-device primary comparison.

The Mac upload contains 69.446 GB including steps and pinned source/metadata;
the prior 36.658 GB/3654.7 s upload implies about 115 min plus verification.
Its own input volume is `rivals-explore-chunks-20260927`, output volume has
the `-outputs` suffix, and the app uses the input-volume name. Profile `rivals`
and authenticated workspace `volpestyle` were verified. Round-3 volumes/apps
are never mounted or modified. The first upload failed on the file-descriptor
limit; the documented 8192 limit was applied and the isolated upload restarted.
Dashboard `explore-modal-upload`; Mac artifacts under `explore/modal15/`.

Paid work is not yet launched. The driver reserves the complete $30 allowance
before app creation, uses retries=0 and bounded function lifetimes, and starts
an independent driver-death/deadline watchdog. The budget calculation reserves
$0.75 non-GPU overhead and 120 seconds for teardown. Collection must prove
zero owned containers; an API/identity failure is reported as unproven cleanup.
Tests: 19 existing synthetic checks, one explicit CPU evaluation-routing check,
and 11 reservation/clock/identity/owned-teardown checks passed; targeted lint passed.
Runner artifacts and detailed estimates are in `handoff/explore/modal_*.py` and
`pc-cuda-feasibility.md`. Cloud results must retain their actual CUDA/GPU/software
identity and the cross-device limitation; this remains EXPLORATORY evidence.
If a chunk arm clearly beats H=1, the next proposal is a multi-seed confirmation,
not additional single-seed variants. The Mac H=1 is never interrupted by the
successor-stop helper; its STOP is written only after training exits normally
and its evaluator has started. The initial $15 waiting launcher was stopped
before any paid driver existed, then replaced for the new three-arm authorization.
