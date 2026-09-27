# fit-countermeasures-3-prereg-draft (VUH-1346)

**DRAFT, not approved or launched.** 2026-09-26. Draft author: fit-review. Initial design review: admission-review (receipt below). The lead assigns implementation/review roles, approves dispatch and records the decision on VUH-1346. This document authorizes no training, code edit, commit, Mac/cloud job, capture or live input. The companion rationale is round3-design-a2.md.

**Amendment 1 — 2026-09-26, before implementation/results.** Incorporates required findings 1–3 of review-round3-20260926.md (SHA256 0f9e905367d5975df1c445db233eea7f837f1e2199126fb85bc47a31f30ffbf5): paired initialization (§4/§8), the effective-weight gate (§6), and bounded proofs before full extraction (§11/§12). Lead additions register MPS/CUDA control branches (§3/§12) and role-based ownership (§13). Unaffected scientific choices and gates remain as reviewed. This is still a draft, not launch approval. Amendment 1's exact prior bytes are preserved in fit-countermeasures-3-prereg-draft.md (the pinned original) (SHA256 d15a9254a8e4dfb7b28ad6b2dab38ea060cd59ef66105bc8ae24b818774ea246); Amendment 2 supersedes its null-control disposition.

**Amendment 2 — 2026-09-26, 18:58 CDT; pre-result, approved by James via the lead.** Drop arm N and its three fits. The train-only sidecar hand-back, handoff/round3/sidecar/HANDBACK.md (SHA256 96bab3761dcb09cf3238441d4444fb4acee9b6bb5269ce673af88a8854772e0c; sidecar manifest 03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba), reports 753 of 148,963 rows weighted at 0.1: 0.5055%, rounded 0.51%, at k=30. Fully idle rows total 11,689 (7.85%, rounded 7.9%); almost all are in runs shorter than 30. These are pre-window row counts, not scored loss mass.

Record: **“idle-target imbalance: not a factor at this cohort's idle rate (0.51% of rows at k=30); contrast untested”.** This is the approved scope/budget disposition, not a measured null-weighting ablation or proof of no causal effect. The H-versus-N contrast is not run or aliased. The retained core is H/I/W (nine fits, plus H's repeat); k=30 and weight=0.1 remain unchanged in all three, with no threshold search. Sidecar review and the scored-mass audit remain required; they cannot reinstate the dropped contrast in this round. S/K, cohort, compute branches, reader conditions and other accepted choices remain unchanged.

## 1. Question and fixed boundaries

Does a normalized frozen visual representation, together with removing action history and reducing sustained idle-target weight, remove the self-fed idle/latched collapse while preserving executed teacher-forced skill?

Two local contrasts separate feature package (H versus I) and history (H versus W). The idle-target contrast is untested under Amendment 2. R conditionally tests whether reader-valued HUD observations add useful information. No full-factorial or interaction claim is made.

Scope is **plumbing, dev only**. The real fit remains no-HUD only, as the lead decided. Pixel-HUD is dropped. No validation or sealed/test data is opened, named as a tuning source, fitted for normalization, sampled for prechecks or used to choose settings. A round-3 pass qualifies a configuration for a later real-fit pre-registration; it is not policy/pilot acceptance.

Round 2's “Neither works” result at 1e47ea8 stands. S1–S4 and K below are unchanged; no near-miss allowance is added. The old +0.05 reader/HUD margin is replaced by the explicitly defined seed-range non-inferiority rule below, with P2′ still required.

## 2. Cohort, immutable inputs and chronology

Use the same five interim train sessions (80.53 counted minutes) and two frozen dev sessions. Do not expand to the admitted 180.57-minute pool in this experiment: an expanded matrix roughly doubles the expensive control and loses the direct historical comparison.

| Role | Session | Step-table SHA256 |
|---|---|---|
| train | 20260923T051828-422Z-33696-1 | d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb |
| train | 20260923T200129-346Z-33696-6 | fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e |
| train | 20260924T232304-170Z-12024-1 | 8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1 |
| train | 20260925T021320-371Z-7804-1 | 841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537 |
| train | 20260925T025230-605Z-7804-2 | 84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288 |
| dev | 20260923T171533-187Z-33696-5 | dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e |
| dev | 20260923T205528-900Z-45572-3 | 941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98 |

Source cache receipt: docs/evidence/range-bc-countermeasures-2-20260926/verify-cm2.json, SHA256 d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7. Verify every source-cache byte before deriving features. Frozen step tables and caches are not rewritten.

Legacy A reference: A-reread.json, SHA256 8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9. Preserve its checkpoint pins and historical report unchanged. On MPS, reread with compatibility settings and require old stored blocks/gates to remain byte-identical. On CUDA, this remains historical evidence; the new same-hardware A runs in §3 supply K's reference. No cross-device bitwise claim is made. The legacy parity receipt e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801 is provenance only and is **not** a reader-vector P2′ pass.

Before any new full fit or new dev result:
1. Approve this amended draft after independent delta review; implement and review the changed paths.
2. Freeze the compute-branch choice from the separate cloud benchmark receipt (§3), reviewed code closure, software/config/weight pins and synthetic judge/test hashes before round-3 probes or results. No judge change after result production.
3. Follow §12's gates in order: verify weights/config and source identities; fixed train-only 128-frame numerical proof; bounded smoke/timing of each distinct path; projected budget approval; full cache build/hash/freeze; launch approval and queue.
4. The train-only sidecar and effective scored-weight audit must also pass before budget approval and any full fit. Final feature hashes are filled only after the approved full extraction. No missing hash is inferred.
5. Conditional reader manifests, precheck and selected-recipe timing/budget gate are required before R, not before the core matrix.

Train-only proof artifacts are permitted at their registered stages; all new dev result production and reads occur after the final launch freeze. A report missing a required pin or role declaration is INVALID, not a model failure or an invitation to infer a default.

## 3. Arms and order

| ID | Features | History input | Fully idle runs >=30 steps | Seeds |
|---|---|---|---|---|
| A | Original no-HUD IMPALA | Original settings | Original loss | MPS: existing 0,1,2; CUDA: rerun 0,1,2 on the chosen hardware |
| H, headline | Frozen DINOv2-S/14 | Absent | Weight 0.1 | 0,1,2 |
| I, feature control | Trainable IMPALA + per-view LayerNorm | Absent | Weight 0.1 | 0,1,2 |
| W, history control | Identical frozen features to H | Present; prev dropout 0.8 in train | Weight 0.1 | 0,1,2 |
| R, conditional reader arm | Clone of selected eligible core recipe | Same as that recipe | Same as that recipe | 0,1,2, only under section 8 |

**Compute branches (lead addition A).** The lead chooses MPS on the Mac, CUDA on one AWS L40S, or CUDA on one AWS L4 after the separately running cloud benchmark. A timestamped device-choice receipt binds that benchmark, hardware/model, backend/software lock, projected costs and the chosen branch before any round-3 probe, fit or new reader/model score exists. Choose on benchmark feasibility, time and approved cost, never on round-3 outcomes. This document launches no benchmark or cloud job.

- **MPS branch:** preserve and reread the three existing MPS A checkpoints. No A retraining.
- **CUDA branch:** retrain A from scratch for seeds 0/1/2 inside round 3, using the frozen historical A recipe, initialization/construction, data, schedule and evaluation, with only the registered hardware/backend change. A keeps its original augmentation/history/loss settings, not the matched new-arm settings. These final checkpoints on the same chosen CUDA hardware provide the full-precision T(A) values in K. Include all three A fits and evaluations in the pre-approved budget.
- Every full arm, H repeat, optional R and cache extraction uses the one selected device type and hardware model; no L4/L40S mixing or MPS/CUDA mixture. CPU preprocessing/reference proofs are explicit exceptions, not fallback training. Pin the particular hardware class and software environment for all runs. A later device change requires a reviewed pre-result amendment and a complete consistent control/arm plan; no selective continuation on another device.

Core order after preflight: MPS A reread or CUDA A seeds 0/1/2; H seed 0 and its exact determinism repeat, then H seeds 1/2; I seeds 0/1/2; W seeds 0/1/2; then judge the complete registered matrix. The repeat catches failure before the remaining new-arm fits. No score-dependent pruning, early stopping, replacement seed or extra epoch.

All new arms have self_condition=0, idle_corruption=0 and self_roll=0. Existing history-corruption options remain mutually exclusive; they are refused in these registered recipes rather than silently ignored. No stochastic decode or threshold search.

“No-HUD” means no dedicated HUD pixel stream and no reader vector. Keep current global/crosshair pixels; there is no new full-frame HUD mask in this experiment. R alone receives the reader vector. Its recipe is mechanically determined by the core winner, not manually picked after inspecting individual curves.

## 4. Common optimization and fixed numerical interface

Unless an arm cell explicitly changes it:

| Setting | Value and reason |
|---|---|
| scope / device | plumbing / one preselected MPS or CUDA branch (§3); immutable reviewed code snapshot |
| regime / lag | normal / 0; unchanged causal alignment |
| epochs | 13 complete epochs; final checkpoint only |
| batch / stride / window | 8 / 64 / 96; same eligible window schedule as prior rounds |
| minimum run / burn-in | 48 / 32; retain existing loss_mask_start rule at true run starts |
| optimizer | AdamW, lr 0.0003, weight_decay 0.0001 |
| schedule / clip | Existing schedule with 500-update warmup (capped at total updates), gradient norm clip 1.0 |
| train_fraction / max_steps | 1.0 / null |
| loss multipliers | held=1, press=1, release=1, camera=0.5 |
| class weighting | Existing capped-at-20 press/release weights from unweighted train-only counts, identical across arms |
| targets and decode | Existing 15-action vocabulary, live mask, degree classes, executor and scalar median-class semantics; no new live actions |
| precision / acceleration | float32; no AMP, compile, flash/xFormers or silent device fallback |
| augmentation, new arms | jitter=0, DrQ shift=0; common deterministic images permit one feature cache |
| recurrent state | Same 512-hidden causal LSTM and unchanged reset/run boundaries |
| history width | 64 in all core arms; absent path supplies exact zeros with no trainable history parameters |
| normalization | Per-view LayerNorm(256), eps=1e-5, affine=False, immediately before concatenation into LSTM |
| random streams | Existing CPU window-order rule; explicit independent initialization/dropout/probe streams below |

IMPALA I uses the existing two encoders (global 144x256, crosshair 128x128; channels 16/32/32, reduce 8, embed 256). Only the output normalization and registered common augmentation/history/loss choices differ from its old feature path. Do not insert normalization into A.

For H/W, each frozen feature vector passes through its own trainable Linear(6528,256), GELU, then the same LayerNorm. Initialize projections using the pinned PyTorch Linear default, biases included. Heads/LSTM retain existing initialization. These projection weights are not cached.

W alone has Linear(PREV_DIM,64), ReLU and LayerNorm(64, eps=1e-5, affine=False). Independently at each training sequence step, replace the entire prev vector by zero with probability 0.8: known bit becomes 0 too. Evaluation is deterministic and has no dropout; teacher-forced uses true previous action, self-fed uses the actual previous executor decode. This is a specified weak-history arm; it does not claim that unknown-history dropout models known-idle history.

H/I must produce identical logits/state for arbitrary changes to supplied previous-action tensors. Merely passing zeros through a learned biased history encoder does not satisfy the contract.

### Amendment 1: paired initialization and independent random streams

For new arms only, define S(seed, tag) as the first 8 bytes, interpreted unsigned little-endian and masked with (2^63-1), of SHA256 over UTF-8 `range-bc-cm3-v1|seed=<decimal seed>|tag=<tag>` (no trailing newline). Seed is 0, 1 or 2 for full fits. Each module is initialized on CPU float32 in an isolated RNG context with S(seed, tag), using its existing/pinned initialization method. Restore the ambient RNG afterward; module construction, loading a backbone and adding a branch must not advance another component's stream. No arm ID enters a shared tag.

Fixed tags are `init/core` for the LSTM, `init/head/<state_dict module name>` for each existing output head, `init/projector/global`, `init/projector/crosshair`, `init/impala/global`, `init/impala/crosshair`, and `init/history` for W. Freeze the concrete head-name/tag mapping with the reviewed code, sorted by UTF-8 name; unlisted trainable modules invalidate the configuration. Frozen DINO weights come from the pinned asset, not a random stream. This preserves initialization methods, but intentionally replaces the new arms' single ambient construction stream.

Before updates, same-seed H/W must have byte-identical projectors, LSTM and heads; I must have the same byte-identical common LSTM/heads (all core arms have 512 visual + 64 history input columns). W's history module and I's encoders have their own streams. Do not require incomparable encoder/projector tensors to match. Historical A's construction and RNG behavior stay untouched.

A tensor hash is SHA256 of its contiguous little-endian float32 CPU bytes; the receipt lists canonical tensor name, dtype, shape and hash. An aggregate SHA256 over canonical UTF-8 JSON (sorted keys, compact separators, sorted tensor-name list) binds that manifest. Test equality by tensor name/shape/hash across the named arms for every seed, reconstruct in reversed arm order, and add a dummy branch to prove shared hashes do not shift. A mutation reverting to one construction RNG must fail.

Keep the existing window shuffle exactly: independent Python random.Random(seed * 1000003 + epoch).shuffle over the identical canonical window list. Hash the ordered (session, start, loss-mask-start) tuples for every epoch and require equality across paired arms, including I/W. W's CPU dropout generator uses S(seed, `train/history-dropout`), persists in fixed batch/step order, and cannot consume the window or initialization streams. Probe RNG uses the separate §12 tags. R's expanded LSTM rule is in §8.

## 5. Frozen feature contract

Model: Hugging Face Dinov2Model, facebook/dinov2-small, non-register ViT-S/14 (384 hidden, 12 layers, 6 heads, 14-pixel patches), no classifier. Revision and expected download:
- revision ed25f3a31f01632728cabb09d1542f84ab7b0056;
- model.safetensors size 88,249,960 bytes;
- SHA256 ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1.

The expected file hash comes from upstream LFS metadata checked during drafting; actual local weight bytes have not been downloaded or verified by this task. The owner verifies them before launch. Config, implementation/library lock, safetensors loader and all preprocessing source bytes also get full hashes. Use the exact revision, trusted built-in model implementation, no remote custom code and eager attention. [Pinned model files](https://huggingface.co/facebook/dinov2-small/tree/ed25f3a31f01632728cabb09d1542f84ab7b0056)

The input is the previously verified uint8 RGB cache, not a second video decode:
- global 256x144: CPU float32 bilinear resize to 224x126, align_corners=False, antialias=True; pad 49 rows above and below to 224x224 using the RGB normalization mean times 255;
- crosshair 128x128: CPU float32 bilinear resize to 224x224 with the same flags;
- scale by 1/255, normalize RGB by mean (0.485,0.456,0.406), std (0.229,0.224,0.225);
- no default image-processor center crop, no random augmentation, no aspect-ratio squeeze of the global view;
- use last-layer normalized CLS and 16x16 patch tokens. Average each non-overlapping 4x4 patch block into a 4x4 spatial grid, row-major. Concatenate CLS then 16 grid tokens: 17*384=6528 floats per view;
- cache both views as little-endian float32, before any trainable projection.

These are declared preprocessing choices, not an upstream claim that this pooling is optimal for control. Normalization is per vector; no corpus-fitted scaler is learned. Two-view DINO features cost about 52,224 bytes per cached frame, roughly 9.1 GB for all approximately 174k rows of the seven existing tables before deduplication. Memory-map the cache; stream extraction in batches of at most 8 views. Do not load a recording's whole feature array into RAM.

The manifest binds: original media identity and relocation receipt; exact step-table/cache hashes; frame ordinal, PTS/timebase and row_frame mapping; graph/normalization/pooling; model/config/weights hashes; software/backend versions; dtype/shape; each output file hash. Train and dev caches have explicit roles. No validation/test cache is opened or created.

Backbone parameters are frozen, eval mode is enforced after every enclosing model.train() call, and feature extraction runs without autograd. Cache bytes are immutable. Only projectors, LSTM and heads train.

## 6. Train-only null sidecar and weighted objective

A step qualifies as physically fully idle only when its original raw interval (anchor, anchor+step_ns], including the state at the anchor, proves all of:
- all physical keyboard keys and mouse buttons known up throughout, including unmapped/unsupported controls;
- no press/release edges, wheel input or other control-affecting event;
- every relative mouse packet has dx=dy=0; net-zero sums formed from opposing motion do not qualify;
- valid, focused, continuous, relative-input state throughout; no gap, ambiguous snapshot or absolute mouse event.

Null classification is true/false/unknown. Unknown gets full weight. This conservative packet-level refinement implements “nothing pressed at all” without using a quantized camera class. Unsupported held keys, within-step taps and sub-bin camera motion must defeat null status. Existing semantic step rows are insufficient proof by themselves.

The sidecar producer emits a separate sidecar only for the five training sessions, with raw-log/state-provenance hashes and the frozen table hash. No alteration of existing admitted tables. Run lengths use maximal contiguous true-null runs within one eligible normal-regime run; do not cross recording, focus/gap, suitability or regime boundaries. Determine runs before tiling so window edges cannot change classification.

Fixed k=30 steps, approximately 1 second at this pipeline's cadence. H/I/W/R-with-filter: weight w_t=0.1 on every step of a true-null run of length >=30; w_t=1 otherwise. Invalid/burn-in rows remain masked out by the original masks.

For each existing loss term, use:
  sum(w_t * mask * per_element_loss) / max(1, sum(mask)).
The denominator remains the original known-element count. Only the numerator is downweighted: an entirely idle batch must have one tenth its former loss, not have the 0.1 cancel in a reweighted denominator. Broadcast the same step weight over that term's known action/axis channels. Retain BCE positive weights and the original loss multipliers. This deliberately reduces total gradient mass on idle-heavy batches; do not compensate with a learning-rate change or adaptive renormalization. No compensation based on dev, no recomputation of pos_weight from the reweighted sample, no window resampling and no state reset or frame removal. Dev losses and all evaluation metrics use original unweighted masks and rows.

Report per training session: true/false/unknown null rows, maximal-run lengths, weighted row share, total effective weight, and unweighted versus effective known mass per loss head. These are descriptive; do not select k/0.1 from the resulting rates.

### Effective-weight gate retained under Amendment 2

Before a full fit or projected-budget approval, audit the exact frozen training windows, original per-head known masks, loss_mask_start/burn-in masks and repeated occurrences of rows in overlapping windows. For each head h, report U_h=sum(mask) and E_h=sum(mask*w_t), and the exact integer count C_h of scored known elements with w_t=0.1, per session and total, for one complete epoch. Thus U_h-E_h=0.9*C_h mathematically; decide zero effect using C_h, not a floating-point epsilon. Masks and window counts are unchanged across epochs/arms, so this audits the whole schedule without running a model. Retain separate BCE positive-weight statistics unchanged; the gate concerns the applied per-element weight, not observed losses or gradients.

The audit remains a correctness/provenance gate for H/I/W and any conditional R, not an arm-selection gate. Report zero or nonzero effective treatment per head, including the case where weighted raw rows contribute only masked/burn-in elements. No share threshold is added. A missing/inconsistent audit blocks the queue; a valid all-zero audit records no effective treatment on scored elements without creating aliases or adding fits.

Keep k=30 and weight=0.1 regardless of the scored rate: no threshold search, relabeling to create treatment, window changes or compensating learning-rate change. Amendment 2's approved scope statement remains the declared result for idle-target imbalance, with the contrast untested. The nine-fit core queue is fixed independently of the audit's zero/nonzero outcome.

## 7. Metrics, S1–S4 and K: unchanged

Evaluate every seed from the beginning of each complete eligible dev run with its recurrent state carried and the original run reset. The visual trajectory remains the recorded trajectory; “self-fed” refers to action history, not environment interaction.

T = executed teacher-forced macro press-F1, late=0: a prediction at the human step or one step early counts; a one-step-late echo does not. F = self-fed macro press-F1 at +/-1 step. Executed-TF counts/rates are descriptive, never skill evidence. New reports request g1-executed; legacy G1 may remain separately reported but is not substituted for T or a round-3 gate.

| Check | A seed passes when |
|---|---|
| S1 | hold_onset_recall >=0.05 |
| S2 | pooled press_ratio in [0.5,2.0] AND at least 6 of exactly the same 10 live actions' ratios in [0.5,2.0] |
| S3 | camera_mae <=0.95 * zero_motion_camera_mae |
| S4 | any_hold_share in [0.5,1.3] * human_any_hold_share, on precisely the human-observable any-hold rows; either share None fails |

An observable human any-hold row has at least one known held live action, or all live actions known released. Model and human shares use that identical subset. Mixed unknown/no-known-held rows are excluded from both. No unknown becomes released.

An arm passes S iff >=2 of its 3 seeds pass all four checks together. It keeps skill K iff:
  mean T(arm) >= mean T(A) - [range T(A) + range T(arm)],
where range=max-min over seeds 0/1/2. An eligible core arm passes both S and K. Missing/nonfinite values or missing seeds make the arm invalid; never shrink denominators or substitute zeros.

Expected immutable dev baseline: 24,556 observable rows, zero excluded; human_any_hold_share 0.6992995601889559; zero_motion_camera_mae 1.2246451263967797 degrees. Thus S3 threshold is 1.1634128700769406 and S4 interval is [0.34964978009447795,0.9090894282456427]. Historical MPS A mean T=0.035109 (rounded), range=0.016743 (rounded); the MPS branch uses its full-precision stored T values and requires A to remain S-failing and byte-identical on prior blocks. Otherwise stop for a metric/input sanity failure. The CUDA branch instead uses the three newly trained same-hardware A T values in the identical K formula; report the difference from historical MPS A as a device/control diagnostic, not an intervention effect. Cross-device A identity is not required. If CUDA A itself passes the arm-level S gate, stop the countermeasure decision for a control-regime review: record the result honestly, do not presume it proves a metric bug or silently change the negative-control premise. The fixed dev row counts and human/zero-motion baselines above remain identical on either branch.

Reported, not judged: per-action held_change_f1, per-action onset/counts, raw and executed TF metrics, dev loss/argmin epoch, all train curves, normalized-feature and gate-preactivation diagnostics, wall/memory cost, and self-fed camera relative to the unchanged persistence 0.418 and ar2 0.376 references. Different weighted training losses are not directly comparable likelihoods; also report an unweighted train-loss diagnostic on a fixed train-only subset.

S and K are low feasibility bars. Three-seed ranges are not confidence intervals or a significance test. No claim of final competence follows from them.

## 8. Conditional reader-vector branch and amended P2′

Execute R only if at least one core arm is eligible, its no-HUD recipe has been selected by section 9, the train-only reader precheck below passes, and the separate reader budget fits. Otherwise report R=NOT RUN with the exact reason. Failure to run R does not veto a valid no-HUD core result.

### Schema and causal cache

R adds 14 scalar fields, each paired with its own known bit (28 inputs):
- webs /5; hp /1000; max_hp /1000; ult_ready (0/1); ult_charge (reader's 0..1 fill estimate);
- for each of swing, get_over_here, amazing_combo: ready (0/1), charges /3, cooldown seconds /30.

These are scale factors, not clipping limits; preserve valid values above 1. Unknown encodes (0,0); known zero encodes (0,1). No learned imputation or forward fill. Nonfinite, invalid-domain or reader-unknown values encode unknown. A structurally unavailable quantity, for example charges on an ability without a badge, is declared unavailable before scoring and stays (0,0); it is never excused post-result.

Map physical layout slots to semantic ability names using the pinned layout adapter; notably the M&K get_over_here/uppercut position mapping must not be treated as pad order. Freeze reader source/assets, adapter and schema hashes. The reader cache is generated from native current FrameRef pixels with pinned RGB-to-BGR conversion and canonical source color handling. Downscaled HUD pixels, future temporal reconciliation, targets, logger actions and dev-selected thresholds are forbidden. Same row/PTS and cache identity checks as scene features.

Use one new MLP Linear(28,64), ReLU, LayerNorm(64,eps=1e-5,affine=False) and concatenate to the LSTM input. Train R from scratch with the selected recipe's seeds and budget; do not fine-tune its dev-selected best epoch. Apply §4's streams to reconstruct the selected no-HUD recipe's initial tensors for the same seed, not its trained checkpoint. Copy its projector/encoder/history/head tensors and all LSTM recurrent weights and biases byte-for-byte. Enlarge the first-layer input matrix from 576 to 640 columns: columns [0:576] are the exact original initialized matrix, and appended reader columns [576:640] alone use S(seed, `init/reader-core-columns`) with the existing LSTM uniform bound 1/sqrt(512). Initialize the reader MLP separately with S(seed, `init/reader-mlp`) and its pinned Linear default. Never initialize the enlarged whole matrix and assume its old columns match. Hash-test the copied columns and other shared tensors against the selected core arm for all three seeds; append-only construction must not shift any shared stream. No extra reader dropout/noise augmentation is added in this comparison.

### Training-reader accuracy precheck

The reader adapter role freezes the reader before sampling. An independent reviewer supplies manual labels, without reader values shown during labeling.
- Start with 200 native frames sampled uniformly from eligible training rows, random.Random(20260928), equal allocation 40 per training session.
- For rare-state coverage, inspect up to 200 additional training frames in a second pre-drawn seeded order, without reader outputs. Stop at the first point the quotas are met; every inspected frame remains in the receipt. No use of dev/validation to fill a quota.
- Per supported field require >=20 human-legible examples; each bool needs both states with >=5 each. Require >=20 low-web (<=2), spent-swing, spent-combo and running-cooldown examples for each supported cooldown field. Overlap between quotas is allowed.
- Ready/charges/webs/HP/max HP/cooldown are exact-value checks. ult_charge is an approximate fill quantity: tolerance +/-0.05 absolute, defined before labels. Report it separately from categorical/integer exact reads.
- Among human-legible samples per supported field: correct-known / legible >=0.95; zero known-wrong values (outside the declared tolerance); hence unknowns may occupy at most 5%. On human-unreadable/absent fields, reader-known is counted as an unsafe non-abstention and also must be zero.
- Unsupported schema fields must be declared structurally unavailable from the reader/layout contract before this check; they cannot be dropped because of errors or low accuracy.
- Insufficient coverage => precheck UNDECIDED, R not run. Any error bar failure => precheck FAIL, R not run. No tuning, relabeling to reader output or second sampling attempt in this round.

Preserve both original labels and adjudication for any independent-label dispute, frozen before computing accuracy. Report denominators, unknown shares, false-ready, false-zero and low-resource errors per field/session/stratum, not just an aggregate score. This is a bounded sanity check on training observations, not held-out reader validation.

### P2′ reader parity and non-inferiority

The existing pixel-transform P2′ is not automatically applicable. Draft amendment: test the semantic vector reader separately against blinded manual gold on fresh, authorized pad captures and M&K training evidence, at native resolution. Apply the same >=20 known-supported-field floor, >=0.95 correct/legible and zero-contradiction rules to **each layout separately**, plus >=20 each low-web/spent-charge/running-cooldown state. Include both ready states, HP and ult fields. The existing ready-occlusion exception is retained as an explicit reported stratum; occluded unknown is never false. Report both the eligible ready denominator and total occluded share.

“Fresh” excludes all sources already consumed by prior parity measurements and all validation/sealed/test sources. A fresh pad capture is a separate lead-authorized live-input task, not authorized here. If unavailable, P2′=UNDECIDED.

Replace the old untransformed-pixel power check with synthetic known-zero/unknown inversions and deliberately wrong semantic slot/layout assignments on the labelled fresh sample; each must make the parity judge fail. Where a wrong-slot assignment is unobservable because all states match, the coverage/power check is undecided, not passed. No hudmap, P1 pixel-slot geometry or P3 digit-position metric is substituted for semantic parity.

Reader-vector qualification requires:
1. R passes S and K;
2. mean F(R) >= mean F(selected no-HUD) - [range F(R) + range F(selected no-HUD)];
3. P2′ reader parity passes.
Use paired seeds 0/1/2 and identical dev rows. This implements “not worse beyond the seed range”; it is not a formal non-inferiority confidence interval. The +0.05 demand is removed, but the qualification still does **not** replace the no-HUD candidate in the upcoming real fit. It supports a separately authorized future comparison only.

Reader errors propagate as input errors, not supervision. Report full-vector-unknown and per-field-unknown evaluation interventions without retraining, alongside field-stratified errors. These are robustness diagnostics, not extra selection gates. Any frozen wrong-known observations remain in the cache/result; do not repair them after seeing R's performance.

## 9. Outcomes and exact selection

Judge the entire registered core matrix first. Let eligible={H,I,W passing S and K}; all three arms require seeds 0/1/2. Selection uses F only among eligible arms:
1. Let B be the arm with largest mean F; exact ties use priority H,I,W.
2. Near ties are eligible arms X for which mean F(B)-mean F(X) <= range F(B)+range F(X).
3. Choose the first near-tied arm in fixed priority H,I,W.
This favors the headline, then normalized scratch, and lastly the explicit feedback path. Seed 0 is always the declared checkpoint candidate; never replace it by the best seed. Report if seed 0 itself fails S despite an arm's 2/3 pass; final policy acceptance is deferred to the real-fit gates.

| Outcome | Condition | Consequence for the real fit |
|---|---|---|
| Invalid / sanity failure or changed control regime | Missing pin/config/active seed, MPS A differs or passes S, CUDA A passes arm-level S, failed determinism proof, wrong dev rows | No decision or real fit; repair evidence/implementation through review |
| Headline works | H is selected | Draft no-HUD frozen features, absent history, specified idle weighting on the expanded train-only cohort |
| Feature control wins | I selected | Draft normalized IMPALA, absent history, same weighting; do not claim pretrained benefit |
| Weak history wins | W selected | Draft frozen features, specified weak history and weighting; preserve self-fed evaluation |
| Multiple work | More than one eligible | Apply fixed tie rule above; publish all seeds and contrasts |
| Live but less skilled | No eligible arm; at least one passes S but fails K | No real fit; report exact tradeoff; any new rate/epoch test needs another registration |
| Neither works | No core arm passes S | No real fit; name failures, including camera; no automatic full-rate D/E or larger-backbone retry |
| R qualifies | R passes S/K, seed-range non-inferiority and P2′ | Record reader-vector eligibility for later approved work; upcoming real fit stays selected no-HUD recipe |
| R fails / undecided / not run | Any prerequisite or reader criterion unmet | Keep selected no-HUD result; no reader promotion, no extra tuning |

For explanatory contrasts, report per-seed H-I and H-W differences in T, F and each S measure. A mean F advantage exceeding the two arms' combined F ranges can be described as larger than the observed seed spread; otherwise call it unresolved at this budget. Eligibility/selection remains the table above, not this descriptive criterion. No multiple-testing significance claim.

## 10. Proofs and judge tests before results

The implementation reviewer requires:
- **Legacy defaults:** old tiny-fixture seeded training, checkpoints, losses and TF/SF decisions byte-identical between original and amended implementations on the same pinned backend when every new option is off. MPS retains exact stored A report blocks. CUDA must pass the same-backend old-versus-new implementation proof; historical MPS checkpoint/report bytes remain frozen evidence, not a demand for cross-device training identity. New report keys may appear only in a versioned metadata section; original metric definitions do not change.
- **Paired streams:** all §4 initial tensor/window-order hashes match across the specified arms/seeds and remain stable under construction reordering/dummy branches. Test R's preserved input columns separately from its added columns. A retains the legacy construction proof.
- **Effective-weight gate:** no idle rows, only masked/burn-in idle rows, and overlapping windows with one scored treated element exercise exact zero/nonzero counts. Both zero and nonzero counts must be reported correctly, without changing the three-arm queue or introducing a minimum-share cutoff. A raw-null-count-only gate must fail.
- **Normalization:** every new arm uses the same registered norm. A synthetic feature-scale stress case must show scale-controlled LSTM input; report pre/post feature ranges and gate saturation on the train-only numerical probe. Do not tune normalization from dev curves.
- **Frozen/cache:** no backbone gradients or parameter changes; eval mode survives outer train mode. Wrong weights, dtype, shape, channel order, PTS, row order, duplicate identity with conflicting PTS, source hash or role refuses before output creation. Corrupt one cache byte to prove rehash rejection.
- **History:** absent path is invariant to arbitrary prev tensors and cannot contain learned bias leakage; W's CPU mask is reproducible, blanks known bit with content, and is off at evaluation. Change future true labels: SF output must stay identical.
- **Null:** unmapped held key; button held across intervals; press/release within one step; release-only event; wheel; opposing nonzero mouse deltas; nonzero counts mapping to camera ZERO_CLASS; unknown snapshots; gaps; 29/30/31-step runs; run crossing a training-window boundary; burn-in masks; last/first recording steps. All must exercise the exact rule. A mutation using only camera class/semantic bits must fail.
- **Weighted loss:** hand-computed weighted numerators with original masked denominators for all heads; an all-idle eligible batch gives exactly 0.1 times the original loss, within floating-point arithmetic tolerance; weights never change known masks, class weights, window count or hidden-state evolution; weight=1 gives exact old loss; dev remains unweighted. Mutations reweighting the denominator or dropping/reindexing idle rows must fail.
- **Reader:** known false/zero versus unknown; semantic pad/M&K permutation; every missing field; frame mismatch; future-frame/label substitution; structural unavailable field; raw vector/cache parity with native reader; no stale forward fill. Wrong schema/map must refuse, not auto-convert.
- **Decode/metrics:** scalar median parity including float32 boundary values on both sides of 0.5; unchanged executor/live mask; one-step executed-TF echo scores no T; S4 human/model observable denominators identical.

Judge is written and tested on synthetic reports before any new arm result. At minimum:
1. Every S threshold just below/equal/above, S2 pooled-only false pass, five versus six actions, exactly 10 named actions, S4 null/unknown denominators.
2. Seeds passing different subsets do not become an arm pass; exactly two all-S seeds do.
3. K equality passes; negative K threshold is reported as the unchanged weak bar, not silently clipped.
4. Wrong TF block/late tolerance, counts used as skill, raw versus executed block substitution all rejected.
5. All outcomes, exact F ties and seed-range ties; no best-seed substitution; conditional R uses exactly the selected recipe.
6. Missing/nonfinite metric, duplicate/missing seed, changed cohort/role/step/cache/sidecar/weights/code hash, opened validation/test, missing cache-verification receipt => INVALID.
7. Train-only null sidecar mistakenly applied to dev => INVALID. Reported fixed denominators/live action list must match A.
8. R lack of coverage, wrong-known values, unknown-as-zero, wrong layout, vacuous all-ready power sample, and missing parity receipt cannot qualify.
9. A and the accepted round-2 D/E reports reproduce the historical decisions under unchanged math; do not retrofit new-arm configuration checks onto old reports.
10. Budget/time interruption produces INCOMPLETE; it is never converted into a favorable subset result.
11. Require exactly core arms H/I/W with three seeds each and priority H,I,W; reject extra core arms, aliases or missing seeds. A and conditional R retain their separate registered requirements. Tests distinguish raw idle rows from effective scored weight. Zero and nonzero audits leave the registered queue and tie rule unchanged.
12. Reject mixed device/model receipts, a CUDA queue lacking three freshly trained A controls, a K calculation using historical MPS A for CUDA, or compute choice dated after round-3 results/probes. MPS uses the historical pinned A values; CUDA uses its complete frozen same-hardware A set. CUDA A passing S yields the registered control-regime stop.
13. Reject a full-cache/fit receipt preceding its required proof or budget approvals, or a changed seed/tag/window-order manifest. Proofs and synthetic timing must never contain new dev metrics.

## 11. Determinism and deployment boundary

Before full extraction or fits, use a fixed 128-frame train-only probe (seed 20260928, stratified evenly by session, deterministic remainder order), containing both views:
- frozen feature extraction twice on the chosen MPS or CUDA backend with identical batch grouping must give byte-identical float32 arrays;
- independently recompute on CPU: all finite, abs error <=1e-4 + 1e-4*abs(CPU value) for every cached feature;
- on the fixed initialized paired-core probe checkpoint, CPU and selected-backend logits must meet atol=1e-4, rtol=1e-4 and yield identical executed actions/camera classes on the fixed probe, including tie/boundary tests. Repeat this comparison on the bounded trained H smoke checkpoint after §12's smoke stage, before budget approval;
- repeat the bounded H smoke exactly, then full H seed 0 exactly: checkpoint bytes, non-timing loss/metric blocks and executed decisions must match on the same chosen hardware/backend;
- no backbone update, stochastic image transform or dev-fitted statistic may participate in any repeat.

These tolerances are proposed now, not measured. A failed proof blocks the queue/reading; preserve the artifacts and seek a reviewed implementation amendment before any result-based choice. CPU feature extraction is not a silent fallback. CPU/MPS and CPU/CUDA use the same declared tolerance/decision checks, not a claim of cross-backend bitwise identity. Same-backend repeatability remains required on either branch.

Pin Python, PyTorch, Transformers, safetensors, numerical libraries, OS, MPS or CUDA driver/runtime/device details, determinism settings and model implementation in the launch lock. Disable reduced-precision shortcuts and nondeterministic fallback on either branch; the reviewer must verify the chosen backend's settings and mutation tests before probes. These exact versions/code hashes are mandatory launch fields still to be supplied by the implementation owner; no pip-latest or floating code in the run.

PC live latency is **not** a round-3 gate. Before a pilot, measure batch-1 native-frame preprocess, two-view backbone, optional reader, projection/LSTM/decode and capture-to-send latency with the game rendering; report p50/p95/p99, memory, deadline misses and game-frame impact at the planned 30 Hz cadence. A deployment failure defers the pilot and needs its own design; it does not change this round's offline score.

## 12. Sequential run plan and time budget — Amendments 1–2

The separate cloud benchmark determines the device branch via §3's lead receipt. It does not authorize round-3 work. After draft approval and implementation review, execute these gates in order:

1. **Weights/config first.** Verify downloaded weight/config bytes, source identities, registry/denylist, software lock, paired initialization/window-order hashes, legacy-default proofs and the frozen synthetic judge. Pin the selected device. Produce train-only physical-idle sidecars and the §6 scored-mass audit; no dev scores. Original source-cache verification is read-only and distinct from building the new feature cache.
2. **128-frame numerical proof.** Extract only the fixed train-only probe in §11, with bounded batches, and pass repeated selected-device extraction, CPU comparison and initialized policy decision checks. Do this before any full train/dev feature extraction.
3. **Bounded smoke and timing for every path.** Use the first eligible complete 96-step training window, in frozen row order, from each of the five training sessions (at most 480 row frames, deduplicated); pin those IDs. If any session lacks such a window, refuse rather than choose a new rule. Cycle the five windows in that order to form fixed batches of 8. Run exactly 32 optimizer updates per path H, I and W, retaining the declared model/loss/history paths and schedule settings. These are discarded correctness/timing checkpoints, never candidates. Initialize using §4 with base seed 0; all smoke-only stochastic streams use S(0, `smoke/<path>/<purpose>`), with purpose `history-dropout` for W and `timing-inputs` for synthetic evaluation tensors. Repeat H's smoke from identical initial state and generator seeds. Include I's trainable normalized encoders and W's dropout/history; CPU-reference the trained H checkpoint as §11 requires. In the CUDA branch also time the unchanged legacy A path for 32 updates with its original seed-0 initialization/RNG rules, separately from paired new-arm streams.
4. **Project and approve the complete budget.** Measure selected-device extraction views/s, hashing, CPU proofs, training updates/s and peak memory. Time TF/SF evaluation with train-only/synthetic tensors and the frozen dev workload's known dimensions, run lengths and counts; do not compute/read new dev scores. Include all 13 per-epoch evaluations per fit wherever the trainer performs them, final evaluations, each active arm/seed, H's full repeat, A reread or all three CUDA A fits/evaluations, source/full-cache hashing, extraction, all probes and verification overhead. Record the estimate and already spent preflight time. The lead approves the complete forecast and cloud spend cap, if applicable, before full extraction. A forecast over the cap blocks here; no epoch/seed truncation.
5. **Full cache only after budget approval.** Build, hash and freeze the train and frozen-dev scene-feature caches from approved sources. No new dev policy scores yet. Bind all output hashes and the effective-weight audit in the immutable launch manifest. Verification failure blocks launch; it cannot trigger a different model/pooling/tolerance without review.
6. **Launch.** Lead approves the complete launch manifest, then one durable sequential queue follows §3 (niced on the Mac). One training/extraction process at a time. Use every active seed and final epoch; stop on failure as INCOMPLETE/INVALID. No unattended PC polling.
7. **Judge and conditional R.** Judge all nine core fits, plus A control evidence and H's repeat receipt. If eligible, select mechanically. Before R's full reader cache/fit, require the frozen reader precheck, copied-initialization proof, and a separate 32-update train-only R smoke/timing on the same bounded windows with S(0, `smoke/R/<purpose>`). Forecast the actual selected recipe: if I wins, R still trains both image encoders. Approve the separate R budget before full reader extraction, hash/freeze that cache, then approve the R launch. R's precheck/timing may follow core results because its selection rule and budget method are fixed here; they cannot change the core decision.
8. Hand back per-seed S/T/F/K, outcome, contrasts and the declared untested idle-target disposition, loss curves, feature/null/reader audits, timing, checkpoint/cache/code/judge hashes, verifier results and limitations.

The core hard cap is **16 hours of sequential elapsed compute work on the chosen machine**, including CPU/reference work, verification and preflight as well as accelerator runs. The conditional R branch has a separate **6-hour** cap including its precheck compute, smoke, full reader extraction/hashing, three fits and evaluations. Cloud dollar limits and exact instance identity are mandatory lead-approved receipt fields, not permission to spend inferred from these hour caps. Human labeling/review time is additional. No speedup from null weighting is assumed because every frame remains.

Revised nine-fit MPS planning estimates remain unmeasured: verification/proofs 0.5–1 h; shared extraction 1–3 h; I 3–4.5 h; six H/W fits 1.5–3 h; H repeat/A reread/evaluation 0.75–2 h; approximately 7–14 h core and 2–6 h optional R. They are not substitutes for the complete measured projection in step 4, especially all per-epoch evaluation costs. CUDA has no approved estimate yet and must include three A retrains. The nine-fit core includes only H/I/W; R based on I must not inherit a cached-head estimate.

Do not truncate epochs/seeds to meet a cap. A running budget overrun stops as incomplete, with existing artifacts retained; any continuation beyond the approved budget needs a new lead decision, not favorable partial judging.

## 13. Dispatch, open launch fields and limitations

**Lead addition B — roles, not pane assignments.** The lead assigns workers, primarily Codex, and preserves independence between a producer and its reviewer. The implementer is the sole writer/integrator for feature/model/history/loss/config and proof code; the sidecar producer owns the raw-state exporter and immutable training sidecars; the reader adapter owns the isolated semantic reader module/cache; the judge author owns the synthetic judge and cases; the reviewer checks implementation, sidecar semantics, blind reader labels and judge with no self-review. These reviewer duties may be split among independent workers. The lead owns shared integration, device/budget/launch decisions and Linear. Deliverables and gates are listed by these roles in the design document; no pane assignments or jobs have been sent by this drafting task.

Before approval becomes launchable, fill the reviewed code commit/closure, exact software lock, denylist and registry pins, actual downloaded-weight receipt, paired initialization/tag/window-order manifests, idle sidecar manifests and scored-weight audit, device/benchmark and same-hardware A branch receipt, approved time/cloud-cost budget, feature manifests, staged correctness/determinism/throughput receipts, judge/test pins and final run manifest. R additionally needs frozen reader/assets/schema, manual-label and precheck receipts; P2′ needs separately authorized fresh pad evidence. Missing fields block dependent work, not the design hand-back.

Limitations fixed now:
- Only 80.53 minutes of one player's training and heavily reused dev, not an unbiased validation result or a three-hour scaling result.
- Two core contrasts and the conditional reader comparison do not separate every interaction, architecture from pretraining, or normalization from historical recipe changes. Idle-target imbalance has no ablation in this round; the sidecar rate is not a causal-effect estimate.
- One backbone, one pooling/preprocess, one weak-history probability, one idle threshold/weight and one epoch budget; no adaptive search.
- Generic frozen features may miss precise motion/aim; an LSTM can collapse without explicit action history.
- S3 is only a modest improvement over zero motion; K can have a very low or negative bar. These stay weak feasibility gates.
- Reader errors/abstentions can be correlated with the required action and differ by layout. Unknown flags preserve uncertainty; they do not make mistaken known values harmless.
- R adds input/MLP capacity as well as reader observations. Without an extra matched-capacity placebo arm, its contrast measures that combined interface, not information alone.
- No-HUD global images still contain small HUD pixels, and self-fed replay does not generate the model's own future visual trajectory.
- Existing degree calibration/patch/context and executor limits remain; this experiment does not solve them.
- An arm pass does not authorize the real fit, validation read or live pilot; their separate reviewed registrations remain required.

## Amendment 3 — Modal CUDA and two-phase fan-out (pre-result)

2026-09-26. James chose Modal at 19:45 via the lead, before any round-3 result.
This Amendment 3 copy preserves the complete Amendment 2 text above. This section
supersedes only its provider restrictions, sequential full-fit ordering and the
MPS-only memory-reporting disposition below. Where
that text prescribes a sequential queue, non-overlapping full fits, or the former
A -> H0 -> repeat dependency, the two phases below now govern. The original -a2
file remains immutable. This is a pre-result design amendment, not launch or
spend approval; independent review and re-pinning are required before use.

**Compute choice.** In addition to the already registered MPS and AWS classes,
CUDA may use `modal:L4`, `modal:A10`, or `modal:L40S`. Choose exactly one hardware
class after the Modal benchmark and before any round-3 probe, fit or result;
freeze the timestamped choice, benchmark receipt, software/driver/runtime and
reviewed code in the launch manifest. Every fit, H0 repeat, optional R and feature
extraction uses that one class and the same pinned software environment. Container
hosts/UUIDs may differ; a hardware class is not a unique machine. CPU preprocessing
and reference proofs remain the existing explicit exceptions. No class mixing,
result-dependent device selection or selective continuation on another class.
The CUDA branch still retrains all three A controls with the unchanged legacy
recipe; historical MPS A cannot supply CUDA's K reference.

**Phase 1 — A_control_gate and H0_repeat.** Run A seeds 0/1/2, registered H seed 0,
and H seed 0 with purpose `repeat`. These five independent fits may overlap and
finish in any order, after the common launch approval. The repeat independently
reconstructs the same registered H0 initial state/seed/recipe; it does not resume
or warm-start from H0. Evaluate the A control check and H0 byte-repeat after all
five outputs are complete. A must pass the unchanged branch-specific provenance
and identity checks and remain arm-level S-failing. H0 and its repeat must match
checkpoint bytes, non-timing loss/metric blocks and executed decisions exactly.
A failed/missing control check or repeat blocks Phase 2. A passing S remains the
registered sanity/control-regime stop, not a successful intervention.

The lead pins one phase-1 gate receipt recording PASS, its completion timestamp,
the exact A0/A1/A2 and registered/repeat H0 outputs, and the named predecessor
gates `A_control_gate` and `H0_repeat`. The judge independently checks the A gate
and H0 repeat from those bound outputs; an asserted PASS cannot replace them.
The receipt must be issued no earlier than the completion of all five Phase-1
outputs and is the authorization boundary for Phase 2.

**Phase 2 — remaining H/I/W fits.** H1, H2, I0, I1, I2, W0, W1 and W2 may run in
parallel, in any order. Each starts at or after the pinned phase-1 gate receipt
time. Every fit carries the same `A_control_gate` and `H0_repeat` predecessors;
no fit may use a different control or repeat attempt. Missing, duplicate, extra
or incomplete fits cannot produce a favorable subset result. The judge requires
all 13 outputs (three A, nine H/I/W, one H0 repeat) before selection.

**Receipt integration.** Names above follow `handoff/round3/impl/FIT-RECEIPT.md`
SHA256 `68a8d6d5e4f224f4e3f535da4ec0925d932475cf7c9495bc76a4f2c2fb9155a0`.
That Amendment-2 interface currently makes registered H0 depend on
`A_control_gate`, and its repeat on `A_control_gate` plus `H0`. Those within-Phase-1
launch dependencies are superseded here: Phase-1 fits share the approved
preflight/extraction prerequisites, and their results are compared at the gate.
The repeat's completed evidence must still identify and match registered H0.
Phase-2 predecessor names stay `A_control_gate` and `H0_repeat`. The runner and
Modal orchestration must adopt this dependency delta and Amendment-3 context
before launch; this amendment does not claim the existing runner already does.

**Budget and unchanged science.** Parallel execution reduces wall time, not
charged compute. The existing 16-hour core cap is one aggregate compute-work
budget: sum every fit/container's elapsed compute, including simultaneous work,
preflight, proofs, extraction, verification, failed attempts and repeats. There
is no separate 16-hour allowance per worker. The separate six-hour R budget,
lead-approved spend caps, immutable outputs and explicit retry approvals stand.
All preflight gates still precede full extraction/launch. Only full-fit scheduling
changes to the two phases; R remains conditional on the complete core decision.

**Memory reporting — explicit MPS-only disposition.** Memory is reported, never a
performance/selection gate. The registered MPS runtime does not expose a peak
allocation counter. For every MPS arm, including A and conditional R,
`context[seed].peak_memory_bytes` may therefore be null only when
`peak_memory_status` is exactly `unmeasurable_mps`. That disposition additionally
requires finite nonnegative `sampled_driver_high_water_bytes`,
`memory_sample_source: torch.mps.driver_allocated_memory`, and
`memory_sample_interval_ms: 10`, and integer `memory_sample_count` >=1. Start
sampling before the fit/reread, poll at that fixed 10 ms interval throughout it,
take a final sample on completion, and report the actual maximum observed
driver-allocation value, sample count and interval in their separate fields.
This sampled high-water mark
may miss between-poll maxima and includes driver allocations; it must never be
renamed or substituted as a measured peak. The interval is fixed here before
results, not selected from observed memory. An existing finite numeric MPS peak
record remains acceptable without invoking this null disposition; a numeric peak
cannot simultaneously claim `unmeasurable_mps`.

CUDA has no null exception: `peak_memory_bytes` stays mandatory, finite and
nonnegative, measured with `torch.cuda.max_memory_allocated` after a reset at the
start of the fit/reread. The context must record
`peak_memory_source: torch.cuda.max_memory_allocated` and
`peak_memory_reset: true`. CUDA rejects `unmeasurable_mps` even if a sampled value
is also supplied. These are report completeness/provenance requirements only;
no memory threshold enters S, K, eligibility, tie-breaking or selection.

The A3 judge exposes `MPS_PEAK_STATUS = "unmeasurable_mps"` and
`MPS_MEMORY_SAMPLE_INTERVAL_MS = 10`, with public helper
`check_memory(context, backend)`. The runner requires Amendment 3, the externally
pinned A3 judge and this declared capability before enabling the MPS null
disposition; an older judge pin must refuse it. No source-string matching.

Everything else is unchanged: cohort, source roles and sealed-data boundary,
seeds, 13 final-checkpoint epochs, H/I/W recipes, k=30 and weight=0.1, scored-mass
audit, absent N, S1-S4, arm S, K, F, exact selection/tie order H/I/W, candidate seed
0, outcomes, reader conditions, determinism requirements and real-fit boundary.
