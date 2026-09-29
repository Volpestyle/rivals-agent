# Native-label NitroGen policy feasibility

2026-09-28, explore-policy, VUH-1346. **Decision: do not integrate or fund an
adaptation arm with the unchanged released sampler.** Offline fine-tuning fits
in memory, but the full sampler exceeds our current observation-age limit before
capture, preprocessing or pad delivery. This is a runtime decision, not a finding
that pretrained actions cannot transfer. $0 spent; GPU released to the lead.

This completes the [CPU interim](../../evidence/nitrogen-native-policy-feasibility-20260928/contract-cpu.json)
from `b65e9d6` and supersedes the earlier memo's IDM-qualification prerequisite:
existing native labels suffice for sizing. Frozen IDM full03 and custom-head
scientific results are unchanged. No dataset/sealed source, live input or Modal
API was used; no trained checkpoint was produced.

## Whole-policy measurement

The complete public `ng.pt` was authenticated before inspection and again before
execution: 1,974,723,762 bytes, SHA-256
`a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81`, HF revision
`584c8dded734d032f07a4bcc0ccb330e703298c4`. Strict state loading passed.
The actual configuration is **25 action dimensions, horizon 18, 16 Euler
iterations**, CFG=1, one image/256 visual tokens, no game-ID mapping or action
interleaving. We did not substitute tokenizer/model defaults or shorten sampling.

[Raw result](../../evidence/nitrogen-native-policy-feasibility-20260928/gpu-01/runtime-gpu-01.json),
SHA-256 `0c8e7d93125c60fc5328aac910f6dbcc202af977478c5cdcc3e37b4b55c02dba`:

| Measured boundary | Result |
|---|---:|
| Whole sampler, CPU-readable decoded output, p50 / p95 | **341.623 / 387.553 ms** |
| Inference peak CUDA allocated / reserved | **1.871 / 1.885 GiB** |
| Full released-scope AdamW, synthetic batch 1 | **3.863 updates/s** |
| Training peak CUDA allocated / reserved | **7.132 / 7.514 GiB** |
| Process peak host working set | **2.561 GiB** |

RTX 4080 SUPER, torch 2.11.0+cu128, torchvision 0.26.0+cu128,
transformers 4.57.1, diffusers 0.35.1; complete package versions are retained.
FP32 parameters/BF16 autocast, eager execution, two torch threads, BelowNormal.
Three warmups then 30 sampler calls cycle three tracked range fixtures. Input
resize/normalization and upload occur outside timing; the tower, all 16 mixing/
flow passes and decoded CPU outputs are inside. Twelve synthetic AdamW updates
include two warmups and ten measured updates; lr=1e-4, weight decay=.001,
`foreach=False`. These establish neither real-data training quality nor sustained
throughput. The complete probe took 24.2 seconds, including authentication/loading.

The game was absent. Preflight caught OBS still recording despite the initial
idle report; CUDA waited until its 18:52:17 recording-stop entry and mux exit.
OBS remained open and idle with explicit permission. There was no capture or pad
worker, and no game-FPS claim. The benchmark process exited and GPU memory
returned to roughly 1.06 GiB of background usage. Inference memory alone is not a
coexistence test alongside the game.

**All 30 samples exceeded 250 ms**, as well as the 33 ms policy step. For context,
our earlier encoder/custom-head profile was 40.5/44.8 ms; that separate two-view
measurement is not a matched architecture experiment. Consuming an 18-action
chunk cannot make its observation fresher or justify extending a pad lease.

## Action, masks and one explicit timeline

Seven CPU contract groups passed using the pinned tokenizer method bodies.
Executable `old_layout=False` is **21 named buttons, then left x/y, right x/y**;
its field-description comment reverses that order. All 21 one-hot buttons and
both sticks at -1/-0.5/0/0.5/1 round-trip exactly. Axes encode into [0,1] with
neutral 0.5; buttons decode strictly above 0.5.

| Native semantic | Released channel / pad |
|---|---|
| jump / get_over_here | LEFT_SHOULDER / LB; RIGHT_SHOULDER / RB |
| web_cluster / spider_power | LEFT_TRIGGER / LT; RIGHT_TRIGGER / RT |
| web_swing / amazing_combo | SOUTH / A; EAST / B |
| Four movement directions | Left stick, diagonal normalization and opposite cancellation |
| Camera degrees | Calibrated right-stick targets; pitch sign flips for up-positive ry |

Menu/guide/D-pad, unsupported actions and unresolved RIGHT_* aliases remain masked.
The tokenizer marks every supplied column known, so the native adapter must
replace its mask. Unknown camera calibration means unknown stick targets, not
neutral supervision. RT aliases lose semantic identity; 16 digital movement
combinations collapse to nine stick states; states cannot distinguish within-bin
repeated taps from holds. Cross-chunk edge tests preserve one onset across a hold.
Thus packing is exact, but a globally lossless semantic/physical round trip is
**not** established. Direct masked-loss gradients are zero; unknown-coordinate
conditioning through noisy actions still needs an explicit training convention.

The checkpoint records **action_shift=3**, but no pretraining FPS. Its config
describes actions skipped after the observation, not a measured actuator delay.
Here is the tested **hypothetical native 30 Hz interpretation**, not a loader choice:

- Observation timestamp: t=0; output row j targets [(3+j)/30, (4+j)/30) seconds.
- Row 0 targets [100,133.3) ms; row 17 targets [666.7,700) ms.
- At measured p95 arrival 387.6 ms, eight target intervals have ended and the
  ninth is underway. The existing 250 ms age gate refuses the whole chunk.
- Starting row 0 at arrival would execute a stale target in the wrong interval.
  Adding another 100 ms wait is equally unsupported. Dropping elapsed rows still
  leaves an over-age observation; neither operation repairs the current boundary.

[Receipt/timeline checks](../../evidence/nitrogen-native-policy-feasibility-20260928/check_runtime.py)
pass. Before any adaptation, observation timestamps, target offsets, interval
lengths and execution age must agree in loader, evaluation and eventual scheduler.
Do not silently inherit the three-row offset or infer physical cadence from 18 rows.
Current accepted camera calibration remains necessary for valid stick supervision;
this probe neither requests a repeat sitting nor qualifies its physical response.

## Scope, throughput, cost and next decision

Actual model construction confirms **493,631,513 parameters**, **468,440,089
trainable**. The released implementation freezes vision layer 11 and its pooling
head; otherwise vision, mixing, flow, action encoder/decoder and positions train.
This is full released-policy scope, not a frozen-tower custom head.

At measured synthetic batch-1 speed, 10,000 optimizer updates alone would take
about **43.1 minutes**. Separately, 24,556 serial fresh-context dev sampler calls
would take about **2.36 hours** at the measured mean. These are arithmetic PC
projections, not L40S quotes or full-run estimates: loading, masks, preprocessing,
real pixel I/O, checkpointing and evaluation design are excluded. Coarser chunk
sampling changes observation cadence and cannot silently replace frame-wise
comparison. Larger batches and compiled/optimized execution were not measured.

Offline integration was sized at roughly **1–2 engineer-days** for target/mask/
alignment handling, a trainer and a state/edge evaluator, before any guarded live
adapter. Runtime fails first, so that work and a paid arm are not recommended now.
A separately authorized, narrow sampler optimization with output-parity and
retiming checks could reopen this decision; no such change was tried here.

If that boundary is resolved, size **one** native-label adaptation recipe against
the completed custom-head baseline and zero on the same frozen dev sessions
`20260923T171533-187Z-33696-5` and `20260923T205528-900Z-45572-3`. Set its endpoint
before fitting; report yaw overall/moving/left/right, false turns on exact
zero-yaw-input intervals (both axes zero separately), pitch and button/onset
retention. Claiming action-pretraining benefit additionally requires the same
vision start, architecture, data, scope, seed and endpoint with freshly initialized
action/mixing/flow weights. A custom-head comparison alone cannot establish that.

Sources remain pinned to [upstream 32608444](https://github.com/MineDojo/NitroGen/tree/32608444660950ffda95e1e57c79632ad65bea10/nitrogen).
Only model/tokenizer code ran. `game_env.py`, `play.py` and `xspeedhack` were never
fetched/imported; the unsafe upstream checkpoint loader was not imported. NVIDIA's
noncommercial restrictions remain attached to weights and derivatives.
