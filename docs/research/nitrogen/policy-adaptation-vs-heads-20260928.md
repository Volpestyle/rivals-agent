# NitroGen policy adaptation versus frozen-encoder heads

2026-09-28 · explore-policy · $0 paper assessment for VUH-1346. No model execution,
weight loading, data access, benchmark or cloud job. Source inspection only.

**Recommendation: YES, worth sizing one bounded offline policy-adaptation arm once
IDM labels are qualified; no training or live launch is authorized here.** Our
experiments used NitroGen's vision weights, not its pretrained action policy.
Fine-tuning its visual/mixing/flow policy and original action encoder/decoder tests
a different hypothesis: transferable coordinated movement/camera/button behavior.
It does not establish that such behavior transfers to Spider-Man or fits 33 ms.

## What today's evidence changes

The [confirmation](../../evidence/nitrogen-nohistory-confirm-20260927/confirmation-report.md)
supports our recurrent no-action-history head: mean press F1 **0.302564** versus H1
**0.101746**. Its MPS yaw MAE **1.771697** still loses to zero **1.735184**; the camera
win is pitch-driven. On the separate matched CUDA cache, yaw is **1.772851** for
the frozen base, **1.908168** for the 4x4 residual, and **1.885650** after hidden
dropout. Dropout mitigates, but does not cure, overfitting; partial 8x8 curves show
the same pattern, with final 8x8 MAE untested. These are not interchangeable MPS/CUDA
measurements. See the [completed dropout result](../../evidence/nitrogen-yaw-dropout-20260928/results-01/INTERPRETATION.md).

Full policy adaptation could retain action priors our fresh heads discard.
Conversely, its single-image default loses our visual recurrent memory, while small
bots/HUD remain hard at 256×256. No action-history input does not prevent copying
human behavior visible in pixels. The [12-turn audit](../../evidence/intent-target-audit-20260928/report.md)
also found half the sampled turns traversal/unresolved, not clearly bot-directed;
neither model automatically solves intent ambiguity.

## Action contract: feasible, with a real adapter boundary

**Correct the old memo before sizing.** Its “21 dimensions / 16 steps” is not the
retained checkpoint configuration. The [profile's embedded checkpoint metadata](../../evidence/live-loop-profile-20260927/trained/nitrogen-cuda-compact-t2.json)
records **action_dim=25, action_horizon=18, 16 inference iterations**, and
`google/siglip2-large-patch16-256` (1024-wide, 24-layer vision). Upstream's pinned
[button list](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/nitrogen/shared.py)
contains 21 button channels, alongside four stick coordinates. The
[tokenizer](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/nitrogen/mm_tokenizers.py)
has a 16-step default and layout-dependent decoding; comments and packing order
are not uniformly consistent. Pin the actual tokenizer/modality configuration,
embodiment, named channel order, effective horizon and action cadence, then require
one-hot/neutral/axis round trips. Do not infer indices from the model card.

Proposed semantic mapping uses our [current bindings](../../../agent/pad_bindings.py)
and [executor](../../../policy/range_bc/executor.py):

| NitroGen named output | Our pad | Semantic meaning |
|---|---|---|
| Left stick x/y | lx/ly | left/right, forward/back; normalize diagonals |
| Right stick x/y | rx/ry | camera rate; our pitch degrees are down-positive, ry is up-positive |
| LEFT_SHOULDER / RIGHT_SHOULDER | LB / RB | jump / get_over_here |
| LEFT_TRIGGER / RIGHT_TRIGGER | LT / RT | web_cluster / spider_power |
| SOUTH / EAST | A / B | web_swing / amazing_combo |

The four extra `RIGHT_*` button channels require alias resolution before use, not
guessing. Mask menu/guide/D-pad and unsupported outputs. WEST→X targeting,
thumb clicks→team-up/ultimate have physical bindings but remain excluded by our
current learned-policy mask; physical availability is not authorization.

For targets, map known semantic holds/taps and calibrated camera degrees through
`pad_state`; never put mouse counts directly on a stick. Preserve IDM uncertainty
as masked targets, not neutral labels. Native outputs encode states, not separate
press/release heads: derive edges across chunk boundaries and report tap/alias
losses. Continuous movement requires a pre-stated deadzone/direction decoder for
semantic scoring. Right-stick targets and degree-space scoring depend on accepted
pad calibration; existing `Cal` defaults explicitly remain stale for James's alt
settings. Compare raw and pad-feasible camera targets. IDM labels alone do not
resolve pad gain, clipping, or their own error rate.

## PC latency: the full policy has no measured 33 ms result

[Live-loop's RTX 4080 SUPER profiles](../../evidence/live-loop-profile-20260927/RESULT.md)
measured actual custom checkpoints, compact preprocessing, two CPU threads:

| Path | Decision p50 / p95 | Replay send-age p50 |
|---|---:|---:|
| H1, CUDA | 26.5 / 30.3 ms | 48.3 ms |
| NitroGen vision + our recurrent head, CUDA | 40.5 / 44.8 ms | 71.9 ms |
| Full NitroGen policy | **Unmeasured** | **Unmeasured** |

The NitroGen sample had 30 isolated decisions: two-view tower p50 **21.68 ms**,
preprocessing **15.36 ms**. Quantiles cannot be added/subtracted to predict a new
architecture. This was the history-enabled seed-0 encoder checkpoint, not a fresh
profile of the confirmed candidate. Fixtures were upscaled 720p JPEGs; no native
capture, hardware pad delivery or game contention was measured. PC torch
2.11.0+cu128 differs from training's 2.14.0+cu130.

The [full sampler](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/nitrogen/flow_matching_transformer/nitrogen.py)
encodes vision once, then repeatedly executes VL mixing and the flow transformer.
One image may cost less than our two views, but those additional iterations are
unmeasured. The old memo's 20–80 ms estimate is not evidence of feasibility.
At 30 Hz, 18 outputs would cover 600 ms (16 would cover 533 ms), **not** imply
fresh 33 ms decisions. Async receding-horizon execution amortizes work but increases
observation age/open-loop exposure. It must preserve independent fresh-HUD checks,
neutral-on-expiry and short pad leases; never extend a lease to consume a chunk.
Measure full-policy capture-to-action p95 and game FPS before any live promotion.
Fewer flow steps or cached mixing are separate, parity/quality-tested changes.

## Integration cost, risks, and sizing decision

Compared with the completed **$2.55** cached-feature dropout campaign, full
adaptation requires a trainer, native-action target/mask adapter, chunk-boundary
evaluator and asynchronous runtime adapter. End-to-end vision updates invalidate
fixed feature caches and add activation/optimizer memory. The old memo's $20–25
training guess is not a current quote; count actual trainable parameters and
measure a capped representative workload before proposing cost. A frozen-tower
native-policy variant would be a different, explicitly named scope.

**Never import or vendor `game_env.py`, `play.py`, or `xspeedhack`, and never pause
the game.** The official harness's process manipulation is outside our scope.
Allowlist only model/tokenizer dependencies; use our in-process guarded executor,
not the upstream pickle-over-ZMQ server. Our existing loader already authenticates
`ng.pt` and uses `weights_only=True`; retain that refusal boundary, never fall back
to arbitrary pickle loading. Resolve all state/config compatibility without
relaxing it. The [feasibility memo](feasibility.md) records the non-commercial
license constraint; adaptation retains it. Nothing here changes that use scope.

**Yes to sizing, conditional on four unknowns:** qualified IDM label coverage/error
and causal split integrity; exact action layout/cadence and current pad calibration;
full-policy latency/VRAM alongside the game; and trainable scope/throughput. Keep
oracle future frames out of policy inputs even when they generate training targets.
Compare against our completed custom-head base on matched data, report yaw versus
zero, left/right, still-frame false turns, press/onset and pitch retention, and fix
the endpoint before results. Full-policy tuning can regress every action path,
unlike the frozen residual; retention must be measured, not assumed. A win would
support adaptation, not isolate action pretraining without a matched initialization
control. Proceed to a paid proposal only after sizing addresses those unknowns.
