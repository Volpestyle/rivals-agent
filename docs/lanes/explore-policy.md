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

The driver reserves the complete remaining $30 allowance
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


### EXPLORATORY first cloud attempt and mount correction

The upload completed: 126 files, 69,446,072,111 bytes, 2,561.86 s (42.70 min)
for upload and 2,605.77 s (43.43 min) including source hashing, about 27.11 MB/s.
The first paid attempt failed during CPU-only input verification, before any
GPU arm started. App `ap-Zqtoz75RPrbhQ5z8Amjv7a` ended with driver/launcher exit 1,
`results={}`, and verified **zero owned containers**. There are no full-cohort
Modal six-decode metrics from this attempt. The stop command's nonzero result
meant the app was already stopped; the subsequent app/container observation,
not that command result, establishes teardown.

The verifier resolved `/inputs` through Modal's legitimate volume symlink and
then incorrectly tested containment against the logical alias. The output
adapter had the same latent mistake. The lead authorized the reviewed `770d000`
namespace pattern: authenticate both aliases against exact SDK-resolved volume
IDs, preserve logical paths, and reject traversal, physical paths and child
symlinks. Synthetic tests cover the valid alias and these refusal cases.
This changes launch plumbing only; cohort, model, loss and metrics are unchanged.

The failed reservation-to-zero interval was 14.539 s. Its conservative bound is
$0.75 overhead plus that interval charged at all three L40S resource rates,
rounded up to **$0.80**. This is a booked bound, not an actual billing receipt.
The replacement reserves that charge plus $0.75 new overhead inside the same
$30 hard cap, shortening the funded lifetime. Failed receipts remain under
`explore/modal15/`; the replacement uses `explore/modal30-attempt2/`, a fresh
`rivals-explore-chunks-20260927-attempt2` app/output volume and a versioned
small code overlay on the existing input volume. The 69.446 GB payload is reused.
Results remain provisional pending the post-run plumbing review.

## EXPLORATORY pretrained encoder comparison (2026-09-27, launched)

Lead brief `brief-explore-encoder.md`, VUH-1346, authorizes **$25 hard total** from
James's $150 weekend budget, warning at $20. No further history/decode/horizon
variants. Code **9665876** adds frozen stock SigLIP versus NitroGen vision weights
into the existing H1 recurrent heads. Nineteen synthetic tests passed; targeted
Ruff passed. Results remain provisional pending independent post-landing review.

A bounded HTTP-range read plus `pickletools` (no unpickle) established that the
released NitroGen checkpoint's actual tower is **google/siglip2-large-patch16-256**,
1024-wide, 24 layers. Stock revision `787800c8990e6f058423089178e718139608408c`,
weight SHA256 `fa34f822f016dbb167d8d0e3a8af99b5e199aa28573360d4295252b9ec418e2a`;
NitroGen revision `584c8dded734d032f07a4bcc0ccb330e703298c4`, source SHA256
`a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81`. Workers use
`weights_only=True` for NitroGen and retain only vision tensors; no NitroGen
package, game environment, live harness, VL mixer or action head is imported.

Both arms use the same eight TRAIN plus two frozen-dev sessions, normal regime,
lag0, seed0, H1, batch8, stride64, history dropout0.2, LR3e-4, unchanged weighted
BCE/camera CE and the final epoch26 of the same cosine schedule. Epoch13 is retained.
Frozen encoders see the existing global and crosshair RGB views resized to256x256;
last-layer patch features pool to a spatial4x4 grid, then independent trainable
projections emit256 features per view into the existing512-wide LSTM. Shared
recurrent/head initialization is exactly preserved. **Compared with incumbent H1,
pixel jitter/DrQ is removed because features are cached.** The two new arms match
each other; the incumbent comparison therefore does not isolate initialization
alone. Encoder inference is bf16, caches float16, trainable head arithmetic unchanged.

Every arm evaluates all six fixed0.5/TRAIN-chosen thresholds by median/mode/expectation
camera decodes and recomputes zero/persistence/TRAIN-AR2 references. The required
real-versus-zero diagnostic now reports per-axis camera/moving-sign NLL and per-action
press NLL (including positive-only NLL), with teacher action history fixed. It remains
an out-of-distribution sensitivity test, not a separately trained history-only control.

Mac launch/collection root: `/Users/james/dev/range-bc-data/explore/encoder-20260927/`,
subdirectories `siglip/` and `nitrogen/`. Separate new apps/output volumes, one L40S,
8CPU/32GiB per arm, retries0, single-use/max1 containers. Existing explore input volume
is read-only; CM3 apps/volumes are untouched. Base image `im-tE3Y0YrWYZ0po0yAA0JQT8`,
derived image `im-FNjy4v5u4XYF29SBGvT0KD` pins transformers4.57.1,
safetensors0.6.2/huggingface-hub0.35.3. Resource rate $0.00071784/s, rechecked against
Modal pricing. Each arm reserves at most$12.50 (including$0.75 overhead), so both
remain inside$25. The original guard's dual-clock deadline and120s teardown reserve
are retained. Large derived feature arrays stay on worker scratch; hashes/source
receipts, weights, checkpoints and reports persist. This is not invoice accounting.

Reviewed a6 `AppCreateGate` transport is reused unchanged, with lane-specific inventory
adapter:15s spacing/RPC limit, stable idempotency key for typed ResourceExhausted only,
no retry for uncertain creation or fit failure. Separate campaign parents do not share
its lock; actual creation times were coordinated with modal-port and idm-owner via
Herdr. SigLIP `ap-UuznXHyCEqJ5zipZ4EFz5p` created16:54:23.994UTC; NitroGen
`ap-sKEKpIXEeauhlWzxAk5vxQ` created16:55:56.742UTC; one RPC each. One earlier local
shell launcher failed on CRLF before any Modal call/reservation and was fixed to LF;
its log is retained. At16:56UTC both workers are verifying input bytes, with no fit
or result yet. Owner retains responsibility for outcomes, cost and terminal proof.


**Independent review accepted to continue (17:10UTC):** frame-review (Claude Opus5.5)
reviewed9665876 and the live launch: **LAND WITH FIXES, no blocker**; lead directed
both runs to continue with running inputs unchanged. Receipt
`C:/Users/volpe/AppData/Local/Temp/claude/C--Users-volpe/7e6e33ed-20c0-4115-b6e2-59dc2d360929/scratchpad/handoff/post-land-reviews-20260927/review-9665876-encoder-comparison.md`,
SHA256 `1589f2a93234c01630eac48c313e06989d10e0d1468e1cc8883510a61c95bf9d`
independently matched. Budget functions are AST-identical to the reviewed guard;
each maximum reservation is$12.49960512. All running manifest hashes verified.

Non-blocking findings and disposition:
- F1: the$150 weekend aggregate is the lead's ledger responsibility, not a shared
  code-enforced cap. These arms add at most$25 to previous runs; owner reports their
  running conservative allocation and final resource-time estimate to the lead.
- F2: the driver's status-only `scripts.job_status` import comes from the existing
  Mac `code-full-aca82b4` snapshot and is not pinned by this runner manifest. This
  limitation is retained for these runs; pin/vendor that helper before a future run.
- F3: the code archive includes `agent/physical_input.py`, which is never imported.
  The encoder transitively imports `agent.controller` via `vocab`/`executor`, matching
  the existing offline fits; on these Linux containers it sends no live input.
  No NitroGen code is downloaded/imported; only its hash-checked weight file is used.
- F4: the copied PRIOR_CHARGE=0 comment still says failed CPU-only attempt. Its actual
  booked prior charge is zero. Correct the comment in future launcher copies, not
  these hash-pinned running inputs.

The new trainable heads contain10,683,307 parameters versus4,194,363 for incumbent
H1, excluding the frozen tower. This capacity difference also qualifies the
incumbent comparison; the new encoder pair remains matched. Runtime asset receipts
agree on architecture/preprocessing config SHA256
`172e39dbf0143b8fe22d2f08921730eb8c397967e58cb37d133161e28aa34104`.
Extracted vision weights differ: SigLIP
`38e5bf7f597c42369ceaac06499bf9e63e67e97818d3dcae549e65bb8f11b7be`, NitroGen
`2fceee7b828e737e459b39aa5d11e01362ce38210033f6f885b9974d7a0d6e79`.

## Encoder result and closure (2026-09-27, 17:29 UTC; EXPLORATORY)

**Both pretrained encoders improve the real-versus-zero visual NLL diagnostic, but neither resolves self-fed collapse.** Both completed the fixed epoch-26 endpoint and all six decodes on the same 300,448 TRAIN / 24,556 frozen-dev frames. This is one seed, not a confirm result or authorization to deploy. NitroGen has a larger ablation gap, but the two real-input NLLs are close and it is not a decisive winner.

### Visual conditioning, teacher history held fixed

Lower NLL is better. Values are real visuals / zeroed visual features. Press NLL pools all known action-frame pairs; positive-only pools observed press positives. Per-action results are mixed and remain in each full evaluation. This is an out-of-distribution ablation, not proof that pixels alone suffice.

| Arm | Yaw NLL | Pitch NLL | Moving yaw sign NLL | Moving pitch sign NLL | Press NLL | Positive press NLL |
|---|---:|---:|---:|---:|---:|---:|
| siglip | 1.488341 / 1.530940 | 1.338252 / 1.387199 | 0.158956 / 0.164642 | 0.147473 / 0.155685 | 0.079501 / 0.085908 | 1.576067 / 2.366025 |
| nitrogen | 1.496561 / 1.540679 | 1.337642 / 1.401752 | 0.160815 / 0.165816 | 0.152024 / 0.162761 | 0.078520 / 0.101509 | 1.567919 / 2.213433 |

The previous matched L40S H1 did not show this camera NLL benefit (yaw real/zero 1.58918/1.54218; pitch 1.42897/1.42255). The new heads have more parameters and omit per-epoch pixel augmentation, so this comparison does not isolate pretrained initialization alone. The two new arms match architecture, recipe and preprocessing.

### All six self-fed decodes

F is the same executed press F1 used by the chunk sweep; camera error is mean yaw/pitch MAE in degrees. Frozen-dev reference MAE is **zero 1.224645, persistence 0.418271, TRAIN-refit AR2 0.379687**, identical across both arms and incumbent. These are camera references, not press predictors.

| Decode | SigLIP F | SigLIP camera MAE | NitroGen F | NitroGen camera MAE | H1 F | H1 camera MAE |
|---|---:|---:|---:|---:|---:|---:|
| fixed_0.5/median | 0.024214 | 1.233146 | 0.041297 | 1.311368 | 0.069158 | 1.408948 |
| fixed_0.5/mode | 0.019348 | 1.224645 | 0.051046 | 1.566926 | 0.072289 | 1.750884 |
| fixed_0.5/expectation | 0.070692 | 1.897432 | 0.086649 | 1.849111 | 0.101746 | 1.823276 |
| train_chosen/median | 0.000861 | 1.411876 | 0.000576 | 1.329099 | 0.006204 | 1.377091 |
| train_chosen/mode | 0.000000 | 1.256158 | 0.000576 | 1.224652 | 0.009209 | 1.687592 |
| train_chosen/expectation | 0.004278 | 1.952423 | 0.001709 | 1.729218 | 0.007291 | 1.755161 |

No new self-fed camera beats zero; SigLIP fixed-mode equals zero exactly. Every self-fed camera fails persistence and AR2. Best press F1 is stock 0.070692 and NitroGen 0.086649, below incumbent H1 0.101746. TRAIN-chosen thresholds remain collapsed (F <= 0.004279, always some action held). At fixed-expectation, predicted press counts are only 293/2458 (stock) and 318/2458 (NitroGen). Better visual sensitivity therefore does not establish an autonomous-policy improvement.

Teacher-forced F at fixed 0.5 / TRAIN-chosen thresholds is stock 0.126952 / 0.038675 and NitroGen 0.115361 / 0.035951. Best teacher camera MAE is stock 0.403704 and NitroGen 0.405622 (expectation): slightly better than persistence but still worse than AR2. No endpoint was selected using dev results.

### Runtime, cost, retained artifacts

Both environment receipts confirm **NVIDIA L40S, Torch 2.14.0+cu130, CUDA 13.0**. Stock training/evaluation took 512.627/239.378 seconds; NitroGen 505.647/237.825 seconds. Encoder extraction and asset setup are additional and included in the conservative budget duration.

Both workers and drivers exited 0. All worker artifact hashes matched the Mac collector; the PC additionally verified all 88 files in the result packet. Large weight/checkpoint files remain on the Mac and separate owned output volumes. Teardown receipts plus a fresh authenticated inventory at 17:28:46 UTC prove both apps stopped, tasks 0, and no owned containers. No further encoder AppCreate or compute is planned.

Cost is **$2.125502 stock + $2.090313 NitroGen = $4.215816**, conservatively charging reservation start through terminal proof at $0.00071784/s plus $0.75 setup reserve per arm. This is a resource-time estimate, not an invoice; storage remains retained. Maximum reserved liability was $24.999210, under this brief's $25 hard cap. The lead received this total for the separate $150 weekend ledger. The $20 notification threshold was not reached.

Authoritative Mac root: `/Users/james/dev/range-bc-data/explore/encoder-20260927/`. Each arm has `final.json`, `teardown.json`, `runner-manifest.json`, and `collected/{evaluation.json,epoch-26.pt,environment.json,assets/assets.json}`. Combined `summary.json`, `terminal-proof.json`, `result-packet-manifest.json` and `result-packet.zip` are at the root. PC copy: `C:/Users/volpe/AppData/Local/Temp/explore-encoder/results/`; packet at its parent. Runtime source/guard/adapter copies are included in the packet.

| Artifact | SHA256 |
|---|---|
| siglip evaluation.json | `0d55f44b7b9eed688ff738f85b2446349254e07bd6e99e2c639d0a640f98e42f` |
| siglip epoch-26.pt | `09163e8fa5b28376911d8058483583ac046dbf26e8f48fd736ba8345536e9677` |
| nitrogen evaluation.json | `87f434a84e9be7ba54d3bb24a1b7a5415956ad5553cd82dc9659e8e9efb3e99b` |
| nitrogen epoch-26.pt | `b8429830f0c5f15dc8c869e4a2531b9677306696b0639098af8895422df6ef2a` |
| summary.json | `2d1fda94bc10a12639390de6678eeb974d2d02d6d9425c183aed72df0ddd217b` |
| terminal-proof.json | `2b3249430780dd362f8876cb06560ca2ec728352099a31e723118e899cb784d1` |
| result-packet-manifest.json | `f63256f598c96700d12445ff411c3491548e16103baa3935b99efba9278f7238` |
| result-packet.zip | `2223f9f04cbd757b9c848e76d2419f1b481833c847c0f1c40684de99a2dcbfcb` |

Independent implementation/launch review remains LAND WITH FIXES, with the four documented non-blocking limitations above. The lead owns acceptance and the VUH-1346 result record; direct workspace Linear was unavailable to this lane. **Parked after this result; no extra seeds, variants or fit retries.**

## No-history encoder follow-up (2026-09-27, 17:38 UTC; launched)

Lead authorized a new **$12 hard-cap EXPLORATORY round** after accepting/posting the encoder result on VUH-1346. Amended mandatory arms remove previous-action input completely on both stock SigLIP and NitroGen, everything else matched. Implementation `1a9bcaf` uses the existing `Config(history=False)` in training and evaluation. The previous-action projection receives a constant zero vector (its learned bias remains); the LSTM retains visual recurrent memory. This directly removes the feedback shortcut without selecting a dropout rate. Default history-enabled behavior is unchanged.

Seed 0, 26 epochs, full cohort/frozen dev, H1 heads, loss, optimizer/schedule, cached frozen visual features and the six decodes per encoder remain matched to the prior encoder pair. The added test proves both chunk-training and recurrent one-step outputs/states are invariant to arbitrary prior-action values, with nonzero gradients into both visual projections and zero history-weight gradient. Focused suite: 20 passed; lint passed.

New Mac root `/Users/james/dev/range-bc-data/explore/encoder-historyoff-20260927/{siglip,nitrogen}`; local launch copies at `C:/Users/volpe/AppData/Local/Temp/explore-encoder-historyoff/`. Each new app owns a separate new output volume. Existing explore inputs remain read-only; no prior or CM3 app/volume is changed. Reused image `im-FNjy4v5u4XYF29SBGvT0KD`, L40S/8 CPU/32 GiB, $0.00071784/s. Each arm reserves at most $5.99956392 including $0.75 setup: combined $11.99912784. Function timeout 6893 s, startup 300 s, teardown reserve 120 s. Guard functions and a6 gate are unchanged. The status helper is now vendored and hash-pinned (prior review F2); the stale prior-charge comment is corrected (F4).

AppCreate coordinated with IDM and CM3, one RPC each: stock `ap-bOm7PMDWI8dnoLASru9vUg` at 17:37:11.779 UTC; NitroGen `ap-RUfsHpFc94fSt7Qid64QAz` at 17:38:30.821 UTC, 79.04 seconds apart. Post-land independent review requested from frame-review. These are running attempts, not completed outcomes.

The evaluator stops summarizing further conditions and emits a STOP receipt on the first observed self-fed camera MAE below freshly recomputed persistence. Owner must report immediately and stop other work; no extra seed or experiment follows a breakthrough. Otherwise complete the 12 conditions and visual NLLs, settle/prove teardown, then use remaining dollars under the SAME $12 cap for at most one partial-history robustness variant on the stronger encoder. Alert the lead at $10 round allocation; weekend $150 aggregate remains the lead's ledger responsibility.

## No-history result and closure (2026-09-27; EXPLORATORY)

**NitroGen without previous-action input is a promising press candidate for confirmation.** All 12 decodes completed; **none skipped**, no persistence stop. Removing history makes model inputs independent of teacher/self-fed action history by construction, so gap closure is not a result. The absolute comparisons below use the same six-action macro tolerant self-fed press F1 as incumbent H1 (0.101745815). Teacher-executed and self-fed press metrics also have different tolerance windows; they must not be interpreted as an input-conditioning comparison.

Frozen dev has 24,556 eligible frames and 2,458 human presses across the ten supported live actions: **0.100098 events/frame (100.098 per 1,000)**, allowing simultaneous actions. The six primary F1 actions contain 1,437 human presses: **0.058519 events/frame**. Neither quantity is the binary probability of any press on a frame.

| Arm | Threshold / camera | Press F1 | Predicted presses / human | Predicted / human rate | Camera MAE (degrees) |
|---|---|---:|---:|---:|---:|
| siglip | fixed_0.5/median | 0.303451 | 3111 / 2458 | 1.265663 | 1.200213 |
| siglip | fixed_0.5/mode | 0.303451 | 3111 / 2458 | 1.265663 | 1.358474 |
| siglip | fixed_0.5/expectation | 0.303451 | 3111 / 2458 | 1.265663 | 1.269364 |
| siglip | train_chosen/median | 0.268441 | 2267 / 2458 | 0.922295 | 1.200213 |
| siglip | train_chosen/mode | 0.268441 | 2267 / 2458 | 0.922295 | 1.358474 |
| siglip | train_chosen/expectation | 0.268441 | 2267 / 2458 | 0.922295 | 1.269364 |
| nitrogen | fixed_0.5/median | 0.371920 | 3134 / 2458 | 1.275020 | 1.185917 |
| nitrogen | fixed_0.5/mode | 0.371920 | 3134 / 2458 | 1.275020 | 1.364083 |
| nitrogen | fixed_0.5/expectation | 0.371920 | 3134 / 2458 | 1.275020 | 1.249360 |
| nitrogen | train_chosen/median | 0.308382 | 2259 / 2458 | 0.919040 | 1.185917 |
| nitrogen | train_chosen/mode | 0.308382 | 2259 / 2458 | 0.919040 | 1.364083 |
| nitrogen | train_chosen/expectation | 0.308382 | 2259 / 2458 | 0.919040 | 1.249360 |

**Primary camera baseline: zero motion, MAE 1.224645.** Median improves the mean by 2.00% (stock) and 3.16% (NitroGen); mode and expectation do not beat zero. The gain is **pitch-driven**: stock yaw/pitch 1.800071/0.600355, NitroGen 1.782815/0.589019, versus zero 1.735184/0.714106. Both yaw errors are worse than zero. Persistence 0.418271 and AR2 0.379687 use **true human history unavailable to these no-history models**; show them as history-privileged references, not an equal-information baseline. Neither arm beats them.

At TRAIN-calibrated cutoffs, NitroGen F1 0.308382 still exceeds incumbent H1 0.101746 while pressing at 0.91904 times the human rate. This supports confirmation without relying on the fixed-0.5 over-pressing. Remaining limits: one seed; small aggregate camera gain; yaw still weak; fixed-cutoff hold-onset recall only 0.1541 and any-hold share 0.5150 versus human 0.6993. No live-control success is claimed.

### Required real/zero visual check

Lower is better; values are real / zeroed visual features. History remains disabled in both cases. The ablation is out-of-distribution; per-action results are retained and mixed.

| Arm | Yaw NLL | Pitch NLL | Moving yaw sign NLL | Moving pitch sign NLL | Pooled press NLL | Positive-only press NLL |
|---|---:|---:|---:|---:|---:|---:|
| siglip | 2.943649 / 3.430420 | 2.531853 / 3.482835 | 0.693818 / 0.693592 | 0.520461 / 0.748415 | 0.090900 / 0.154280 | 1.791490 / 1.997478 |
| nitrogen | 2.900587 / 3.797517 | 2.493271 / 3.283924 | 0.681921 / 1.115805 | 0.518019 / 0.696238 | 0.093921 / 0.175099 | 1.693605 / 1.693639 |

Camera and pooled press NLL improve with real features. Stock moving-yaw sign is essentially unchanged, and NitroGen positive-only press NLL is essentially unchanged; do not describe every submetric as improved.

### Closure, review and next consumer

Both worker/driver exits are 0, all collector hashes match, and the PC verified 90 packet files. Fresh authenticated inventory at 18:11:14 UTC: both apps stopped, tasks 0, zero owned containers. L40S / Torch 2.14.0+cu130 / CUDA 13.0, same immutable image. Stock train/eval 499.054/240.859 seconds; NitroGen 507.462/239.487 seconds. All weights and final checkpoints remain on the Mac and owned output volumes.

Conservative resource-time cost including $0.75 setup per arm: **$2.11944192 + $2.08138654 = $4.20082846**. No $10 alert; below the $12 cap. Prior encoder pair $4.21581554 plus earlier chunk sweep $26.732 gives cumulative explore compute **about $35.148644**, using the earlier rounded conservative figure. Not an invoice; other lanes and retained storage excluded.

Independent review of 1a9bcaf/live launch: **LAND WITH FIXES**, receipt SHA256 `88314b57bac5a7dc233d930eea9d6a93f0f6f0bcec01444166157a66a93c1c7f`. The missing stop test landed as a23a0c3 (23 passing). F1-F3 landed as **19d0060**, 26 tests passing: authenticated run-config drives history, skipped decodes are reported, and the next manifest includes image/package pins. New copies are under `docs/evidence/explore-encoder-20260927/launch-fixes/`; completed inputs remain unchanged, no rerun.

Authoritative run root: `/Users/james/dev/range-bc-data/explore/encoder-historyoff-20260927/`; local metadata copy `C:/Users/volpe/AppData/Local/Temp/explore-encoder-historyoff/results/`. Summary, terminal proof, packet manifest, per-arm final receipt and evaluation hashes are retained.

| Artifact | SHA256 |
|---|---|
| siglip evaluation | `2576d336817b06fbaefabf63a02faaf9c3a99a3a6f39c38258a909149448c31a` |
| siglip epoch-26.pt | `e16bb4f2fc9b10913f399a4b7eebe4a10732cf579279c21d609cc84cfbef5071` |
| nitrogen evaluation | `4ca4745b9d24aa77403d5805edf2e8e7934e5bbaf1d479659607075695aacd37` |
| nitrogen epoch-26.pt | `70d279f6186a6be8597f17046d7b586784e450941f837b28372ab5f939500bb6` |
| result-packet.zip | `0f0bbf1bc835595e1873c6617072fee3d0084d445f42cf115b932bb76931be24` |

**Lead decision:** no third exploratory arm. Prepare a pre-registered CONFIRM comparison of exact NitroGen no-history versus matched NitroGen history-enabled (dropout 0.2), seeds 1/2/3, $20 hard cap. Lead must approve committed pre-registration and pinned synthetic-tested judge before any confirm launch. Seed 0 is design evidence only, not confirmation.

## NitroGen no-history CONFIRM launched ? 2026-09-27 18:45 UTC

Lead approved the matched candidate/control seeds 1, 2 and 3 (seed 0 excluded),
26 epochs, frozen full cohort/dev, L40S, $20 hard cap. No third explore arm.
Pre-registration `c28d039` at `docs/evidence/nitrogen-nohistory-confirm-20260927/preregistration.md`
SHA256 `825c3852d82ac0eb3e994bb64bf995e3babb7b14017da9d86cb8f564a9294295`;
pre-result review-timing amendment `07c73ec`, `preregistration-a1.md`,
SHA256 `7950bd9fce5cd57cde3bc218275999afec1cbfdb40f5ae47c142c5d03472f8a1`.
Both pushed. Source `5673de101a398fa661be581e3c1dd041391e2a61`.
Judge `6f2187dd974befedbaf656470d7b153f3a5ca7be0a62a3954a67670ab726aa32` cleared
by frame-review, LAND WITH FIXES, receipt `review-confirm-judge-5673de1.md`
SHA256 `cf8724b53bb29dc2829fbf844a1c53ea3e3f37e5123fe43dc10c4519f1f6b34a`.
Do not edit judge. Publication must compare output source_manifest to the pinned judge,
metrics `ff8ec1788700392a2490d39d19ecc623cea85094adbd23873aefb30420e2a2e5` and
vocab `9f57c02a977921cc0f8fef003a19eb647136ff51af34a7913f76fb22ec811f3e`;
report yaw/pitch and three paired differences separately. Future-test findings do not block this run.

Mac parent `/Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927`.
Six exclusive app/output-volume pairs; read-only prior explore input volume. All use image
`im-FNjy4v5u4XYF29SBGvT0KD`; runner manifests pin image/package versions/config/source/helpers.
Source archive `8ae54d75dcbeb0f1fb5758d7df2c93cf12b21aa4eec7a3b540d058c52bce766a`
contains source and explicit registry/tally/denylist/equivalence metadata, no demonstration payloads;
every archived member verified byte-equal to git source. Windows `git archive` applied CRLF
conversion on the first local attempt; prelaunch SHA check rejected it. Recreated with
`-c core.autocrlf=false`, verified and prepared; no paid attempt used the rejected archive.

| Arm | App ID | AppCreate UTC |
|---|---|---|
| Candidate seed 1 | ap-qG9re2Po0qwnHKEg4LWmwk | 18:44:02.380057 |
| Control seed 1 | ap-qan0bFQU52xnosEkv8MKMz | 18:44:28.164320 |
| Candidate seed 3 | ap-qoYesaN6NxbjwDVkuvRpVJ | 18:44:43.402331 |
| Control seed 3 | ap-i85U45O1VaoGB1FeD35JEs | 18:44:58.623262 |
| Candidate seed 2 | ap-PR5gZ1baNAJ6JV6G5fXUy6 | 18:45:13.803248 |
| Control seed 2 | ap-McTxozLZtgSIkoF8rx5Kkb | 18:45:28.979106 |

CM3 explicitly released its reserved window after zero AppCreate RPCs; its phase1-03 was parked.
This burst respected global >15-second spacing and was released to IDM at 18:45:43.979106 UTC.
No further encoder creation is authorized/planned. All six containers started and authenticated
A1, seed and history mode; first cohort-loading heartbeats at 18:47 UTC. No scientific result yet.
Six disjoint $3.33 guards reserve $19.97950176, immutable guard-function AST unchanged.
Completed explore allocation before confirmation remains approximately $35.148644 (rounded chunk
cost component; excludes other lanes/storage). Lead owns James's combined $150 weekend ledger.


## Confirmation interruption and approved Mac recovery (2026-09-27, 19:46 UTC)

All six original fits reached epoch 26, but their evaluations were interrupted and contain no completed decode summaries. Five re-entries refused existing output directories during a shared Modal rescheduling window also observed by IDM; the sixth ended via its original lifetime guard. All six apps are independently proven stopped/tasks zero/no containers. There is no statistical confirmation verdict yet. Original allocation is $13.8781933744; cumulative lane allocation approximately $49.0268373703, not an invoice and excluding other lanes/storage.

All six complete checkpoints and original CUDA TRAIN cutoff receipts persisted. Two independent volume reads match; safe loads show finite epoch-26 tensors identical to latest.pt. No pre-failure checkpoint digest was produced; recovered-byte stability is the evidence available. The [incident record](../evidence/nitrogen-nohistory-confirm-20260927/modal-incident.md), raw receipts and six-input pins landed in 2975583.

Lead-approved [A2](../evidence/nitrogen-nohistory-confirm-20260927/preregistration-a2.md), commit 535be13, SHA256 6f7eedfb6e0f1cf4407a2fde9b9dc83c895b780350a549d7dd37ff35dfd33c1d, moves all six evaluations to one $0 Mac MPS stack. It keeps exact checkpoints and original TRAIN cutoffs, frozen judge 6f2187dd and unchanged decision rules. Recovery source a5cb931 verifies complete identities and step/cache receipts and has no fit path. 64 synthetic tests pass on PC/Mac; the actual tower passes a synthetic bf16 MPS check.

Mac evaluation launched 19:45:58 UTC, PID 93960, observed nice 15 (requested nice -n 10). All-six input manifest SHA256 14347004b5d12ed44a89d69961fcb2df7be8f1a34444460f145fee3c5797cf21 was committed before inference. Root /Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/mac-evaluation-a2. Per-seed metrics are withheld until all six outputs exist; persistence STOP still reports immediately. No additional cloud spend or AppCreate. Replay follows the result and lead decision; release the Mac slot explicitly to lead/IDM afterwards.


## NitroGen no-history confirmation delivered (2026-09-27, 20:31 UTC)

**CONFIRMED** under the pre-registered seed rules. All six Mac A2b evaluations completed, process exit 0, all 36 decodes, none skipped. Candidate mean TRAIN-calibrated press F1 0.302564 versus matched history control 0.004060 and incumbent H1 0.101746; rate 0.932194x human, random-presser floor 0.027553. Each paired seed favors candidate. Camera mean MAE 1.183091 versus control 1.327261 and zero 1.224645; each seed beats both. Yaw remains worse than zero: 1.771697 versus 1.735184; pitch 0.594485 versus zero 0.714106. This is offline confirmation, not playable horizontal target turning.

A2 initially failed before inference on Path JSON serialization. Fix and completed-feature reuse receipt landed 88b231d; 65 tests PC and changed-path tests Mac passed. A2b reused streaming-verified caches, same six checkpoints, original CUDA TRAIN cutoffs and MPS stack, with no refit/re-extraction. The historical judge refused a 65-character manifest pin. Lead-authorized pre-result A3 c13820c corrects only its extra final d in a NEW judge (66830ce6); historical 6f2187dd remains byte-intact. Actual manifest, all six checkpoint prefixes and upload receipt agree. Frame-review independently cleared the exact one-constant delta (receipt cd1e9526) before any numerical metric was inspected. New judge, metrics ff8ec178, vocab 9f57c02a and A3 inclusion were explicitly checked in source_manifest.

[Full confirmation report](../evidence/nitrogen-nohistory-confirm-20260927/confirmation-report.md) includes per-axis values, three paired differences, all decodes, real-vs-zero NLL, human base rates and chance floors. Raw result packet SHA c8fada8aadb2d9ed377cb3ef4a7521021a53f36fa0f64c1f89c48a69beb04baf. Original Modal allocation $13.878193; recovery $0; cumulative lane approximately $49.026837, not invoice/other-lane spend. Lead-requested EXPLORATORY cold-onset audit is running on the niced Mac; pinned 30 s offline replay follows. Mac slot remains owned until both finish.


## Follow-ups delivered; Mac slot released (2026-09-27, 20:54 UTC)

[Delivery index](../evidence/nitrogen-nohistory-confirm-20260927/delivery-index.md) joins confirmation, both exploratory onset audits, replay and accounting. The strict joint cold split is **uninformative** for initiation: only 5 press targets at 0.5 s, none at 1 s. It is not reassuring evidence. The lead-requested per-action split allows other activity: 977/577 onset targets at 1 s/2 s; candidate macro F1 0.134030/0.122656 vs control 0.003740/0.005151, but candidate macro recall only 0.091084/0.081857. Boundary-permitting recall rises to 0.280487/0.274203 and can credit one-frame late visual echoes. Basic spider_power onset recall remains 0.0044/0.0028. These post-result diagnostics do not change the confirmed verdict or establish autonomous initiation. Every diagnostic rerun exactly reproduces the original aggregate F1/MAE.

The parameterised offline renderer/spec landed ec3a44f; [30 s video/report](../evidence/nitrogen-nohistory-confirm-20260927/offline-replay-report.md) landed 0f018dd. 900 frames, 30.000 s, 1536x800; same James-recorded policy-view frames across James/H1/NitroGen panels. Labelled offline predictions, not model gameplay. TRAIN cutoffs on this pre-pinned clip: H1 1 press/F1 0.022222, NitroGen 65/F1 0.370400, human 77 presses. Original full-cohort metrics remain authoritative.

All Mac follow-ups ended with exit 0; slot explicitly released to lead and idm-owner after the per-action audit. No further compute queued. Exact unrounded cumulative lane REPORT is $49.026403877872901, cloud holds $0 (0d9e206); this replaces the previous approximate figure based on rounded chunk cost and is not a verified balance/invoice. Existing cloud launchers unchanged. No sealed data or live input used. Paid yaw work still awaits a new lead-approved brief.

## Native-label full-policy feasibility, 2026-09-28 (CPU interim)

Lead resumed VUH-1346 under the accepted IDM-to-policy priority note; IDM label
qualification is no longer a prerequisite for sizing on existing native labels.
The [feasibility note](../research/nitrogen/native-policy-feasibility-20260928.md)
records the actual authenticated full NitroGen checkpoint: 25 coordinates,
18 actions, 16 sampling iterations, tokenizer buttons-first, action_shift=3,
pretraining FPS unspecified. Seven synthetic CPU contract groups passed; unknown
coordinates require replacing upstream's all-known mask, and semantic aliases,
opposite movement and within-bin taps prevent a globally lossless round trip.
493,631,513 checkpoint elements; 468,440,089 trainable under released freeze rules;
7.074 GiB is only the FP32 AdamW-state arithmetic floor, not measured peak VRAM.

The live camera/FPS sitting took exclusive PC GPU ownership before any sampler
started. Whole-sampler latency/memory and synthetic-update throughput remain
PENDING explicit lead release. Prepared bounded benchmark is not launched. No
Modal creates, dataset/sealed reads, live input, fit or paid proposal. Current
camera calibration remains a target-validity prerequisite, not an IDM dependency.

## Native full-policy feasibility complete, 2026-09-28 18:54 CDT

The [final note](../research/nitrogen/native-policy-feasibility-20260928.md) recommends
NO extensive integration or paid native-label adaptation with the unchanged sampler.
Authenticated actual 25D/18-action/16-iteration policy measured 341.623 ms p50 /
387.553 ms p95 on RTX 4080 SUPER, FP32 weights/BF16 autocast, 30 calls after 3 warmups.
Every sample exceeds 250 ms before capture/preprocessing/pad. Inference allocated 1.871 GiB;
full released-scope synthetic batch-1 AdamW 3.863 updates/s, allocated 7.132 GiB/reserved 7.514 GiB;
host peak 2.561 GiB. All 493,631,513 parameters loaded strictly; 468,440,089 trainable.
No actual fit/model quality result; no claim against action-pretraining transfer.

The declared 30 Hz shift-3 timeline puts row 0 at 100 ms; at p95 387.6 ms eight target
intervals are over, ninth underway, and existing freshness rejects the whole chunk.
Timestamp/edge and receipt arithmetic checks pass. No automatic offset copying,
extra 100 ms wait, shortened sampler, long pad lease or partial integration proposed.
GPU released directly to herdr-lead after process exit; game absent, idle OBS
explicitly allowed only after recording stop was verified. $0/no Modal/no sealed
or dataset reads/no model checkpoint. Raw runtime receipt SHA256
0c8e7d93125c60fc5328aac910f6dbcc202af977478c5cdcc3e37b4b55c02dba.
Lead owns any new runtime-optimization dispatch and VUH-1346 reconciliation.
