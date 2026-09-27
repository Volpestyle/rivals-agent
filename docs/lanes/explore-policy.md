# EXPLORATORY — short action chunks (2026-09-26)

Owner: explore-policy. VUH-1346, Policy team, EXPLORE track. **No fit result yet.**
Mac-only, $0 cloud; round 3, the decoder audit, and the Modal upload have priority.
No commits. No validation, test, Gate 2 or sealed payloads are used.

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
file hash before each partial is renamed. First logger triple verified;
originals remain in progress. The first GiB took 492.6 s; native SCP/AES-GCM
probes did not improve it. PC priority BelowNormal, Mac nice 15, peak driver RAM
19.3 MB. Transfer time: running; cache build: not run.

**Epochs:** the lead approved 26 matched epochs, seed 0 first. The 13-epoch recipe
was chosen on 33.59 minutes, and earlier curves often still fell at its cap
([assumption audit](../research/assumption-audit.md), findings 1 and 3). Keep
per-head, step-one dev curves and epoch-13 snapshots. An epoch-13 snapshot belongs
to the **26-epoch cosine schedule**, not a replication of the old 13-epoch fit.
Use the final epoch for the sweep; report convergence limits. Add seeds 1–2 only
if a chunk arm improves self-fed checks.

| Arm, seed 0 | Epochs | S1 onset / S2 pooled + per-action press ratios | S3 camera / S4 any hold | T / F | Wall time |
|---|---:|---|---|---|---|
| H=1 | 26 planned | Not run | Not run | Not run | Not run |
| H=4 | 26 planned | Not run | Not run | Not run | Not run |
| H=8 | 26 planned | Not run | Not run | Not run | Not run |

Each arm will have **fixed 0.5** and **TRAIN-chosen per-action threshold** rows,
each under **median, mode and expectation** camera decoding.
The proposed calibration matches TRAIN executed press counts (hold rises plus
taps); ties prefer 0.5. Each condition carries its own executed feedback. Existing
`metrics.EXECUTED_TEACHER`, `metrics.SELF` and `selffed_checks` provide T/F and
S1–S4, including per-action ratios; camera references are persistence 0.418°,
AR2 0.376°, and frozen-dev zero-motion 1.2246° are historical dev references.
Recompute TRAIN/dev zero-motion, persistence and train-fitted AR2 for each cohort.
No new judge. The decoder audit's
final threshold procedure/results must be read before this evaluation runs.

**H=1 camera pre-step:** camera and moving-sign NLL with real versus zeroed visual
features, keeping teacher action history fixed. Credit
[research-methods](../research/camera-targets/analysis.md): zero is a minority
label but the marginal mode/median; full-cohort continuity is weaker. This
ablation is an out-of-distribution sensitivity diagnostic, not proof the encoder
lacks direction. Cumulative-trajectory loss remains a separate candidate; this
H comparison retains matched CE/BCE.

**Implemented and synthetic-tested:** `policy/range_bc/explore_chunks.py`,
`explore_chunks_train.py`, `explore_chunks_eval.py`, `explore_camera.py`, and tests in
`tests/test_range_bc_explore_chunks.py`. Tests cover H=1 output/loss/gradient
parity, all-head learning with step-one-only execution, target masks, resumed
optimizer/RNG state, cohort rejection before payload access, and threshold
decoding, legacy median-rollout parity, independent decoder histories, and masked
conditioning NLL. **15 CPU tests passed in 8.69 s** using an isolated environment
on the PC (lead-authorized); targeted Ruff checks pass. The default environment
lacked PyTorch and skipped this module, so that first attempt was not a test pass.
Review request withdrawn on the lead's direction: fit-review stays on round 3.
Before withdrawal, two findings were observed and fixed: float32-cutoff decisions
now match the executor exactly, and resume binds actual target tensors and the
complete window schedule. Their regression tests are included in the 15.

**Mac compute queue:** decoder release, then idm-lab's capped 30-minute slot,
then explore. Modal upload finished; transfer was authorized meanwhile. The lead
also authorized using existing interim data while originals land: `--cohort interim`
means five train plus two frozen dev sessions, reported separately. Full-cohort
runs use their own fixed inputs; resume refuses a cohort switch. No model/cache
job has run. A verified code snapshot is staged at `explore/code-107970b4/`.
The trainer saves an epoch checkpoint and can yield at the next update through
a stop file, preserving its resume state. These are heavily reused-dev
diagnostics; any candidate needs a registered CONFIRM run before a real fit or
pilot. More presses alone would not establish learned timing or gameplay skill.
