# Native-label NitroGen policy feasibility

2026-09-28, explore-policy, VUH-1346. **Interim: CPU contract inspection complete;
runtime decision pending the lead's PC GPU release. $0, no cloud creates, no fit.**
The live camera/FPS sitting has exclusive use of the PC GPU. No sampler, capture
or inference worker was started before that hold. This note supersedes the
[earlier memo's](policy-adaptation-vs-heads-20260928.md) requirement to qualify IDM
labels before sizing: existing native labels are sufficient for this task.

## Actual checkpoint and contract

The public `ng.pt` was acquired at revision
`584c8dded734d032f07a4bcc0ccb330e703298c4`: 1,974,723,762 bytes, SHA-256
`a266f5fb9c7dbdcdf97216558d2d82075a9a994b824cda69afa9fd3280260a81`.
Acquisition streamed the hash; inspection used `weights_only=True`, CPU mmap,
BelowNormal priority and two torch threads. No dataset or sealed source was opened.
The [CPU receipt](../../evidence/nitrogen-native-policy-feasibility-20260928/contract-cpu.json)
pins the complete checkpoint configuration and upstream source hashes.

**Actual settings:** 25 coordinates, 18 actions, 16 Euler sampling iterations;
one image, 256 visual tokens, no game-ID mapping, no action interleaving.
Tokenizer `old_layout=False` means **21 buttons followed by left x/y and right
x/y**, despite the contradictory field description. Sticks map [-1,1] to [0,1];
neutral is 0.5, and button decoding uses strictly `>0.5`.
The checkpoint also says **action_shift=3**, frame_spacing=18. Neither its config
nor the released model records the pretraining frame rate. Native 30 Hz would
place rows 3..20 at 100..666.7 ms after the observation, ending at 700 ms; the
18-row chunk itself spans 600 ms. This is a declared native interpretation,
not proof that pretraining used that cadence. Horizon length alone cannot select
the physical action rate or native observation/target alignment.

Seven groups of synthetic CPU checks passed using the actual pinned tokenizer
method bodies, without importing its package or harness:

| Boundary | Result and implication |
|---|---|
| 21 one-hot buttons and neutral axes | Exact packing/decoding round trips |
| Both sticks at -1, -0.5, 0, 0.5, 1 | Exact numeric round trips |
| Semantic mapping | jump→LEFT_SHOULDER/LB, get_over_here→RIGHT_SHOULDER/RB, web_cluster→LEFT_TRIGGER/LT, spider_power→RIGHT_TRIGGER/RT, web_swing→SOUTH/A, amazing_combo→EAST/B |
| Unknown/unsupported coordinates | Masked; 15 unsupported button channels never become known neutral targets. Missing camera calibration leaves both right-stick masks false |
| Aliases/movement | RT combines melee and Spider-Power; unknown alias masks RT unless another alias is known active. Sixteen digital direction combinations collapse to nine stick states; opposite keys are not invertible |
| Chunk boundary | A hold crossing row 18 produces one onset, not a second press at the next chunk |
| Native cadence | Row/time conversion at declared 30 Hz round-trips; no FPS inferred from checkpoint shape |

**Native semantic labels cannot all round-trip losslessly through pad states.**
Aliases lose semantic identity, opposing movement cancels, and a held state cannot
distinguish repeated within-bin taps from a continuous hold. Edge scoring must
carry previous state across chunks and disclose these losses. Current disabled
actions, menus, guide, D-pad and unresolved RIGHT_* aliases stay masked; numerical
round-trip success is not permission to send them. Degree↔right-stick validity
still requires the current accepted camera map; the historical `Cal` defaults are
stale. No physical camera round trip has been demonstrated here.

The upstream tokenizer's `_prepare_action` marks **all supplied columns known**;
an adapter must replace that mask with coordinate-level native validity. A small
gradient check confirms zero direct loss gradient at masked coordinates. That
does **not** remove their influence through the noisy action input: a training
adapter must define unknown-coordinate conditioning consistently, rather than
treat finite placeholders as observed neutral. Preserve masks through cropping,
time alignment and padding; unknown observations are not training negatives.

## Scope, memory and remaining runtime measurement

Checkpoint tensor elements total **493,631,513**. The released constructor freezes
vision layer 11 and its pooling head (25,191,424 elements), leaving **468,440,089**
trainable by its named-parameter rules. This is full released-policy adaptation,
not a fresh head on a frozen tower:

| Component | Elements |
|---|---:|
| Vision encoder | 315,956,224 |
| Flow transformer | 121,992,192 |
| Visual mixing | 50,384,896 |
| Action encoder / decoder | 3,174,400 / 1,075,225 |
| Action positions | 1,048,576 |

Arithmetic floors: weights occupy **1.839 GiB FP32** or **0.919 GiB BF16**.
FP32 parameters, gradients and two AdamW moments occupy about **7.074 GiB** with
the upstream freeze. These exclude activations, allocator, runtime and temporary
buffers; they are **not measured peak VRAM** or proof that a batch fits alongside
the game. Actual model construction will cross-check these counts.

The [prepared benchmark](../../evidence/nitrogen-native-policy-feasibility-20260928/benchmark.py)
does not run automatically. After explicit GPU release it will authenticate the
checkpoint, strictly load the complete state, and time the unchanged 16-step
sampler (FP32 parameters/BF16 autocast, CFG=1, three warmups/30 calls). It retains
CPU-readable-output p50/p95 and CUDA peak allocation/reservation. Three existing
tracked range fixtures are used, not new capture or corpus frames. Capture,
preprocessing and game contention remain outside that isolated timing. A bounded
12-update synthetic batch-1 AdamW probe sizes the released trainable scope;
real-data I/O, evaluation and checkpoint costs remain separate. It refuses game
or OBS presence and has a ten-minute local stop. **Neither measurement has run.**

## Decision gate and integration cost

**No paid arm proposed yet:** sampler latency, peak memory and update throughput
are still unmeasured. A 33 ms policy step cannot be inferred from the previous
encoder-only 40.5/44.8 ms profile or amortizing 18 actions. If the unchanged sampler
cannot meet the allowed observation-age/runtime budget, stop before writing a
trainer or live adapter; fewer sampling iterations would be a separate experiment.

If runtime is practical, the next proposal is one native-label full-policy arm,
with current pad calibration and explicitly pinned cadence/target alignment.
Use the existing admitted cohort and frozen dev sessions
`20260923T171533-187Z-33696-5` and `20260923T205528-900Z-45572-3`. Fix the endpoint,
sample schedule and decoder before fitting; compare final outputs with the
completed custom-head baseline and zero motion. Report yaw overall, moving and
left/right; false turns on zero-yaw-input intervals (and both axes zero separately);
pitch and button/onset retention. Training loss alone is not usable evidence.

The integration work is a native target/mask/alignment adapter, bounded trainer,
state-to-semantic evaluator with boundary continuity, and separately a guarded
asynchronous live adapter if earned. Planning estimate: **1–2 engineer-days** for
offline integration after these uncertainties resolve, not an elapsed-time or
compute quote. No new admission, tracker or IDM dependency is introduced. Full
vision updates cannot reuse the frozen feature cache; budget must include pixel
staging and final whole-sampler evaluation, not optimizer time alone.

A win against the custom head would support this architecture/adaptation recipe.
It would **not identify action pretraining as the cause**. That claim requires a
matched initialization control: identical vision start, data, trainable scope,
seed, schedule and endpoint, with action/mixing/flow weights freshly initialized.
No such control is run or authorized here.

Model/tokenizer sources are pinned to
[upstream 32608444](https://github.com/MineDojo/NitroGen/tree/32608444660950ffda95e1e57c79632ad65bea10/nitrogen).
`game_env.py`, `play.py` and `xspeedhack` were neither fetched nor imported. The
upstream unsafe checkpoint loader is not used. NVIDIA's noncommercial restrictions
remain attached to the checkpoint and any adaptation.
