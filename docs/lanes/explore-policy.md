# EXPLORATORY — short action chunks (2026-09-26)

Owner: explore-policy. VUH-1346, Policy team, EXPLORE track. **Interim H=1 trained; evaluation running. Full sweep queued.**
Mac-only, $0 cloud; round 3, the decoder audit, and the Modal upload have priority.
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
| H=1 (interim) | 26 complete | Evaluating | Evaluating | Evaluating | Fit complete; evaluation running |
| H=4 (full) | 26 planned | Not run | Not run | Not run | Not run |
| H=8 (full) | 26 planned | Not run | Not run | Not run | Not run |
| H=1 (full) | 26 planned | Not run | Not run | Not run | Not run |

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
