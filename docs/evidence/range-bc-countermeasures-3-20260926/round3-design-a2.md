# Round 3 design: separate visual features, action history and idle-target weighting

**DRAFT — design only, VUH-1346, 2026-09-26.** Draft author: fit-review. Initial design review: admission-review (receipt below). The lead assigns implementation/review roles, approves dispatch and posts on Linear. No training, implementation, commits, Mac/cloud jobs or fresh captures are authorized by this document.

**Amendment 1 — 2026-09-26.** Addresses required findings 1–3 of review-round3-20260926.md (SHA256 0f9e905367d5975df1c445db233eea7f837f1e2199126fb85bc47a31f30ffbf5), plus the lead's compute and role-ownership additions. Shared initialization, the effective-weight audit and preflight order are amended below; the accepted scientific choices remain. The companion pre-registration supplies the exact executable contract. Exact Amendment 1 bytes are preserved in round3-design.md (the pinned original) (SHA256 29087a467ca0f9ce934189c354c46a99677208e1e8ede65bb40229e8197a427b).

**Amendment 2 — 2026-09-26, 18:58 CDT; pre-result, approved by James via the lead.** Drop N and the idle-target ablation. The train-only handoff/round3/sidecar/HANDBACK.md (SHA256 96bab3761dcb09cf3238441d4444fb4acee9b6bb5269ce673af88a8854772e0c; manifest 03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba) reports 753 of 148,963 rows weighted at k=30 (0.5055%, rounded 0.51%). Fully idle rows are 11,689 (7.85%, rounded 7.9%), almost all in shorter runs. Spending three of twelve fits on that small row share is dropped by the approved budget decision.

Record: **“idle-target imbalance: not a factor at this cohort's idle rate (0.51% of rows at k=30); contrast untested”.** This is a scope/budget disposition, not a measured causal finding. The counts precede scored-window masks and overlap; retain that audit. H/I/W still downweight at k=30 and weight=0.1, with no search. No N fits, aliases, selection outcomes or timing smoke remain in this design.

## Recommendation

Run three matched no-HUD arms on the same 80.53-minute interim cohort and frozen dev as rounds 1–2. The headline combines a frozen DINOv2-S/14 scene encoder, no previous-action input, and downweighting of sustained, physically verified idle targets. Two controls replace one component each: normalized trainable IMPALA features or weakened previous-action input. Idle weighting is shared and untested as a separate factor.

That is nine fixed-budget core fits, seeds 0/1/2 per arm, plus H's full seed-0 repeat. On the MPS branch reuse the three historical A checkpoints; on the CUDA branch rerun A's three seeds from scratch with its unchanged historical recipe on the same selected hardware as every new arm. Freeze the device branch from the separate cloud benchmark before any round-3 probe or result. Add a reader-vector arm, on the selected no-HUD recipe, only after a core arm passes S and K and the reader accuracy precheck passes. Its three seeds are a separate conditional diagnostic, not a route around the lead's no-HUD real-fit decision.

Keep S1–S4 and K unchanged. A passing result permits drafting the real fit; it does not accept a policy, start a pilot, or open validation.

## What is known and what remains a hypothesis

Round 2 landed at 1e47ea8. Neither D nor E passes S on any seed; both pass the deliberately weak K check. E's mean self-fed press-F1 is 0.071924, pooled presses are 27–42% of the human rate, and every camera fails S3. D produces 1–5% of human presses despite better hold-onset recall. These are partial changes, not successful countermeasures.

The round-1 frames-only failure does not establish that action history is necessary. The producer's B-seed-0 diagnostic found mean absolute visual features 29, maximum 738, and almost all input-to-LSTM gate preactivations beyond ±5. We should repair that numerical comparison before interpreting it as a perceptual limit. Layer normalization prevents uncontrolled feature scale at the recurrent interface; it does not prove the features contain the needed information.

James's proposal is a useful set of separable hypotheses:
- Frozen generic visual features might make useful frame evidence accessible with this amount of data.
- Removing or weakening the explicit previous-action channel might reduce copying.
- Sustained idle targets might dominate even without that channel.

VPT supports trying null-target treatment and a frame-recurrent policy; its vision encoder was not a frozen generic backbone. Its Appendix E.2 compares several null-run filters and reports that filtering helps. It also shows that factored action outputs can still overproduce null actions. We keep our action representation fixed, so a negative result does not exhaust that explanation. [VPT, appendices D/E](https://arxiv.org/html/2206.11795v1)

DINOv2 supplies pretrained spatial features, not demonstrated Rivals motor features. Its transfer to camera motion and initiation is the experiment. A comparison with IMPALA changes architecture, pretraining and whether the encoder is trainable; call it a **feature-package comparison**, not proof that pretraining alone caused an improvement. [DINOv2](https://arxiv.org/abs/2304.07193), [official models](https://github.com/facebookresearch/dinov2)

The copycat literature motivates testing reliance on histories, but does not establish that every present failure is copying. A recurrent network can learn an idle attractor without an explicit action input. [Wen et al.](https://arxiv.org/abs/2010.14876)

## Data decision: retain the interim cohort

Use precisely the five train recordings and two dev recordings pinned by rounds 1–2; no new session selection. This keeps A, the S3 camera baseline and the S4 human denominator comparable, and avoids approximately doubling every trainable-encoder arm's cost. All arms see identical eligible windows and optimizer updates. The null intervention changes loss weights, not which frames or windows reach the LSTM.

The newly admitted 180.57 train / 15.58 validation minutes establish readiness for later work, not permission to use validation for round 3. Do not open validation or sealed/test media, labels or reports. Do not use them for feature normalization, reader calibration, latency samples, null rates or hyperparameters. The frozen dev sessions remain excluded from training even when a later full-cohort manifest is built.

There is no 180-minute arm in this budget. This sacrifices a data-scale conclusion to isolate mechanisms economically. After a round-3 success, the real-fit pre-registration must explicitly pin its expanded training cohort, exclude the frozen dev, and re-establish all real-fit gates and baselines. Old metric thresholds cannot be silently recomputed from validation.

## Arms and the comparisons they support

| ID | Role | Visual feature source | Action history | Idle loss weight |
|---|---|---|---|---|
| A | Original negative control; MPS reread or same-hardware CUDA rerun | Original IMPALA | Original recipe | 1 |
| H | **Headline** | Frozen DINOv2-S/14 | Absent | 0.1 on fully idle runs of at least 30 steps |
| I | Feature-package control | Trainable IMPALA, normalized at output | Absent | Same as H |
| W | History control | Same frozen cache as H | Present; training previous-action dropout 0.8 | Same as H |
| R | Conditional reader-vector diagnostic | Selected core arm's features | Selected arm's setting | Selected arm's setting |

H versus I tests the frozen feature package against a numerically stabilized scratch encoder. H versus W tests removing history against strongly weakening it, conditional on the frozen features and weighting. Idle-target imbalance remains untested under Amendment 2. The two retained contrasts are local comparisons around H, not a full factorial estimate of all interactions. In particular, this design cannot prove which mechanism alone explains historical A.

All three new core arms use normalized recurrent inputs and no pixel augmentation. Fresh per-epoch DrQ/jitter cannot be recovered from a single deterministic feature cache. Disabling it for every matched arm avoids attributing augmentation differences to the backbone. A retains its original recipe and is a skill/sanity reference, not an augmentation-matched ablation. CUDA uses its contemporaneous three-seed A rerun for K; the historical MPS numbers remain recorded without a cross-device byte-identity claim.

The no-HUD label means no dedicated HUD pixel stream and no reader vector. The existing global frame includes small HUD pixels; it is not a claim that every HUD pixel is masked. Preserve the same scene/crop contents in all three core arms. A new HUD mask would be another intervention and is deferred.

## Feature cache and recurrent interface

Choose the small non-register DINOv2 model, not a large backbone or a video model. Use two frame views already identified by the verified global and crosshair caches; the frozen backbone weights are shared between views. Preserve spatial tokens rather than using only a global CLS vector: camera control may depend on local displacement.

The exact preprocessing, token pooling, projection and normalization are fixed in the accompanying pre-registration. The cache contains frozen per-frame features only; trainable projection weights live in each checkpoint. No normalization is fitted on dev. Every feature is bound to the original frame ordinal/PTS, source cache hash and row map. It sees only the frame used by the current causal policy step, never a future frame or target.

The intended weights are pinned now from upstream LFS metadata, without downloading or executing them in this task:
- facebook/dinov2-small revision ed25f3a31f01632728cabb09d1542f84ab7b0056.
- model.safetensors, 88,249,960 bytes.
- Expected SHA256 ae1e99fcefd534ed978cdeb8326f08030c96e28b7a81ffcbc98a857c84d14be1.
- The implementation owner must download from that exact revision and independently hash the bytes before use; no floating main revision or silent model substitution.

[Weights at the pinned revision](https://huggingface.co/facebook/dinov2-small/tree/ed25f3a31f01632728cabb09d1542f84ab7b0056)

IMPALA control I keeps its existing two image encoders, but applies per-view LayerNorm before the recurrent core. H/W apply LayerNorm after each learned projection. Both supply 512 visual values to the same 512-hidden LSTM. No absent-history zeros pass through a learned bias: the absent-history branch supplies a constant zero 64-vector without a trainable history path. W uses the same 64-dimensional history embedding, followed by normalization.

**Amendment 1: paired initialization.** For every new-arm seed, H/W projectors, common LSTM and heads must start byte-identical; I's same-shaped common LSTM/heads must match them. Construct each module on CPU float32 in its own restored RNG context with the existing initialization method. The pre-registration defines the exact SHA256-derived seed function and tags for core, heads, projectors, I encoders and W history; constructor order and added branches must not shift shared tensors. Hash every initial tensor with name/dtype/shape, test all seeds across arms and reversed construction order, and compare per-epoch ordered-window hashes. W dropout is independent of initialization and sample ordering. Historical A's construction stays unchanged.

R reconstructs its selected recipe's same-seed initial weights, not its trained checkpoint. Its enlarged first LSTM input matrix copies the original 576 columns exactly; only the appended 64 columns use a new stream. The reader MLP has another stream. Hash-test shared tensors and preserved columns against the no-HUD initialization. A generic “same seed” assertion is insufficient.

W deliberately retains the train/evaluation distinction: 80% of individual previous-action vectors are replaced by unknown during training; evaluation uses the model's actual previous executed action, without random dropout. This tests a specified weak-history intervention, not a promise that dropout trains known-idle states. D/E and one-step self-conditioning are off for every new arm.

## Fully idle means physical inactivity, not a zero camera class

The existing step rows give semantic held states, net mouse counts and unsupported press events. They cannot prove that an unmapped physical key was not already held. A zero camera class also includes small nonzero movement.

The sidecar producer supplies a train-only, hash-bound sidecar from the original raw logger/state stream. It must establish that no physical key/button was held at any time in the interval, no key/button edge or wheel event occurred, and all raw relative mouse deltas on both axes were zero. This deliberately keeps zero-net cancellation of nonzero deltas as active, rather than calling it idle. Unknown snapshots, gaps, absolute mouse input or incomplete state make the idle label unknown and retain full weight.

Maximal fully idle runs are measured within one eligible continuous run, before training windows are placed. At length at least 30 steps (approximately one second), every step of that idle run gets loss weight 0.1. Shorter idle runs and every other eligible step keep weight 1. Frames, labels, previous-action alignment, elapsed time and recurrent state are not deleted, compressed or reset.

**Amendment 1: effective-weight gate.** Before any full fit or budget approval, audit the exact scored known elements per head over the frozen windows, including burn-in masks and overlapping-window multiplicity. Report original and weighted mass and the integer count of scored elements assigned 0.1; raw idle-run counts alone cannot establish treatment. Keep k=30 and weight=0.1 regardless of the observed share.

Under Amendment 2 the audit is a correctness/provenance gate, with no control-arm disposition. Report zero or nonzero scored treatment per head; the nine-fit H/I/W queue stays fixed either way. No alias or additional fit is created. Missing/inconsistent audit blocks the queue. Keep no-idle, masked-only idle and one-scored-treated-element proof cases, without a minimum-effect threshold or search. The sidecar's 0.51% is a pre-window row rate and does not replace this audit.

This conservatively reduces sustained waiting's supervision without teaching the model never to wait. It is downweighting, not a literal reproduction of VPT's frame deletion. Dev/evaluation are completely unweighted. Positive-class weights stay derived from the original unweighted training statistics in every arm, so the comparison has one target-weighting intervention.

## Reader values: a separate diagnostic, with measured errors

R adds a small vector from the frozen native-frame HUD reader: webs, HP/max HP, ult ready/charge and readiness/charges/cooldown for swing, Get Over Here and Amazing Combo, keyed by semantic ability rather than screen position. Every field has its own known bit. Unknown and known zero must produce different vectors. A structurally absent quantity remains unknown; do not infer zero charges from a missing badge or zero cooldown from no numeral.

Reader outputs are fallible observations. They may create false-ready shortcuts, confuse zero with missing, or carry different missingness on pad and M&K. Freeze the reader and its assets; spot-check training frames against independent human labels before constructing R's full cache. Failure or insufficient support skips R; it does not trigger reader tuning inside this experiment or hold up a valid no-HUD result. Exact sampling, coverage and error bars appear in the draft.

R uses only current native pixels at the same FrameRef as the scene cache. Do not derive the vector from action labels, future cooldown transitions, smoothing with future frames, or the scaled scene cache. No forward fill. Unknowns are not targets and do not remove supervision.

The lead's decisions stand:
1. The upcoming real fit remains **no-HUD only**; the dedicated pixel-HUD arm is dropped.
2. For reader-vector eligibility, the old +0.05 margin is replaced by **P2′ passes and not worse beyond the seed range**, defined numerically in the draft.
3. That eligibility is evidence for a separately approved future reader-vector fit, not automatic substitution into this real fit.

P2′ must test the semantic reader interface on fresh pad evidence and independently labelled M&K evidence. Pixel transformation agreement, seams and untransformed-pixel baselines are no longer the relevant comparison. Preserve the known-count, zero-contradiction and low-web/spent-charge/cooldown coverage demands; replace the pixel power check with explicit wrong-layout/slot and zero-as-unknown controls. This is an explicit draft amendment requiring independent review, not an assertion that the old P2′ already passed.

## Determinism, compute and live feasibility

**Lead addition A: pre-result device choice.** After the cloud benchmark already running, the lead pins either the Mac's MPS, AWS L40S CUDA or AWS L4 CUDA in a timestamped choice receipt before any round-3 probe, fit or new score. This task runs no benchmark or cloud job. Choose from benchmark feasibility, time and approved cost; every full arm, cache extraction, H repeat and conditional R uses one chosen device type/model and pinned environment. CPU preprocessing/reference proofs are explicit exceptions. Do not mix L4 with L40S or move a subset of arms between devices.

On MPS, A's existing checkpoints and old report blocks stay byte-identical. On CUDA, rerun all three A seeds from scratch on that same hardware using the frozen original A recipe, initialization, epochs and data, and use those final T values in unchanged K. Preserve the old MPS A evidence separately. If CUDA A passes S, record a changed control regime and stop the countermeasure decision for review; do not assume a metric defect or continue under the old negative-control premise. Same-backend default-off compatibility is required on either branch.

**Amendment 1: ordered gates.** Verify weights/config/source identities and synthetic tests first; run the fixed train-only 128-frame CPU/MPS proof (CPU/CUDA on that branch); then bounded smoke/timing per distinct new path; approve the complete projected budget; build/hash/freeze the full feature cache; only then approve and launch full fits. Freeze code, judge and compute choice before probes. The train-only scored-weight audit is required before budget approval. No full extraction is paid for before numerical correctness and throughput are known.

The smoke is exactly 32 updates each for H, I and W, on fixed batches from the first eligible 96-step training window per training session, at most 480 row frames. It covers I's trainable normalized encoder and W's dropout. The pre-registration specifies seed/tag derivation and fixed ordering; repeat H's smoke and retain the full H seed-0 repeat. CUDA also times the original A path. Time evaluation on train-only/synthetic tensors scaled to frozen dev workload counts, never new dev scores. These probe checkpoints cannot be selected.

A frozen cache removes the backbone from the training graph, not from reproducibility checks. Require repeated extraction bytes, CPU-versus-selected-backend feature/logit tolerance and identical decisions, paired initialization and exact same-seed training repeats. Pin backend, precision, library versions, preprocessing, weights and cache bytes. No mixed precision or nondeterministic fallback. A failed proof blocks dependent work; tolerances cannot widen after results.

The revised nine-fit **7–14 Mac-hour** forecast is unmeasured, not a demonstrated speedup; it includes six H/W fits and three I fits, plus H's repeat. The core cap remains **16 hours of sequential elapsed compute work on the chosen machine**, including source verification, extraction/hash work, CPU proofs, bounded smoke, every per-epoch/final evaluation, full H repeat, and A reread or three CUDA A retrains. The measured forecast and a cloud dollar cap, when relevant, require lead approval before full extraction. No seed pruning or schedule shortening. The separate R cap remains 6 hours, including its precheck compute, smoke, reader cache/hash work and all fits/evaluations; forecast the actual selected recipe. An I-based R still trains its image encoders and cannot use a cheap frozen-head estimate. Human labeling/review time is additional.

Before any eventual live pilot, separately measure the entire native-frame preprocessing + two-view backbone + recurrent step + decode latency on the PC GPU, with the game rendering and normal capture load. Report warmed p50/p95/p99, peak memory, capture-to-send age, deadline misses and game-frame impact at the intended control cadence. This is a pre-pilot deployment measurement, not a round-3 model-quality gate. Failure defers deployment; it must not be solved by post-hoc feature/cadence substitutions in a judged checkpoint.

## Dispatchable ownership and review gates

**Lead addition B: role-owned deliverables.** The lead assigns panes/workers, primarily Codex. These are deliverable roles, not pane assignments or a dispatch by this document. A reviewer must be independent of the work being reviewed.

| Work | Accountable role | Expected paths/artifact | Independent gate |
|---|---|---|---|
| Frozen features, normalized policy and paired initialization | Implementer | New policy/range_bc feature-cache module; model.py, cache loading and train.py integration; pinned asset/tag/tensor-hash manifests | Reviewer checks causality, weight/row/PTS pins, frozen gradients, normalization, paired tensors/window order and default-path proofs |
| Physical-idle truth sidecar | Sidecar producer | Intake-side exporter and per-training-session immutable sidecars; no edits to frozen step tables | Reviewer checks raw-state semantics, unknown handling, gaps and unsupported controls |
| Weighted loss/history options and effective-weight gate | Implementer | train.py/model.py, exact scored-mass audit and three-arm manifest, option/mutation tests and metadata | Reviewer checks denominators, masks, zero/nonzero audit counts, absence invariance and exclusive options |
| Reader-vector schema/cache and precheck | Reader adapter | Isolated reader-cache module and manifests; frozen perception/hud.py dependency, not failed Gate 2 feed reader | Independent reviewer supplies blind labels and assesses coverage/errors, causal mapping and appended LSTM columns |
| Judge and synthetic cases | Judge author | Evidence scripts, config/device/pin checks, H/I/W outcomes, priority H,I,W and same-hardware A/K handling | Reviewer checks judge; lead pins code/test hashes before results |
| Staged numerical/smoke/timing proofs | Implementer, consuming sidecar and reader deliverables | Bounded probe receipts and full cost projection; actual selected R path forecast | Reviewer checks all new paths, seed derivation, no dev scores and proof-before-extraction chronology |
| Integration, queue and real-fit decision | Lead | Immutable code closure, device/budget receipts, launch manifests, sequential chosen-device queue and Linear result | Independent reviewer accepts amended design and implementation; lead approves budgets/launches |

The implementer alone integrates shared model/train files. Sidecar and reader roles hand back isolated artifacts/modules; they do not race edits in those files. The judge author cannot review their own judge. The reviewer role can be split among independent workers for code, blind labels and judge. Legacy default-off behavior remains byte-identical to the old implementation on the same backend; old checkpoint loading stays compatible. New variants require versioned configurations and cannot masquerade as original checkpoints.

## Rejected or deferred alternatives

- **D/E at P=1 or D+E:** spend another round on history exposure without testing the feature-package hypothesis. Combining also changes two treatments and rollout cost. Their previous failures remain recorded.
- **Unnormalized frames-only again:** repeats a demonstrated numerical defect.
- **Only headline versus A:** too many changes to identify which component mattered.
- **Idle-target ablation:** dropped by Amendment 2 at the observed 0.51% weighted-row rate; contrast untested. Keep the fixed downweighting in all three core arms.
- **Full three-factor factorial or 180-minute matrix:** too expensive for this dev diagnostic. Three core arms identify two local contrasts; interactions and the idle-target contrast remain unresolved.
- **Finetune a large backbone or add a video model:** more compute, more causality/cache questions and a larger optimization search. One small frozen frame model is a bounded first test.
- **CLS-only features:** cheap, but discards spatial detail relevant to camera/control; retain a small spatial grid.
- **Delete idle frames/windows:** can destroy physical time and recurrent context, and changes optimizer exposure. Keep all frames and weight their losses.
- **Treat semantic zero or quantized zero camera as idle:** violates James's physical-input definition.
- **Reader vector in every core arm:** confounds the three main questions and makes their launch depend on parity work.
- **Tune thresholds, epochs, seeds or filters on dev after round 3:** would make this another unregistered search. Near-misses remain failures.

Read this with fit-countermeasures-3-prereg-draft-a2.md, which specifies the executable contract and the exact outcomes. Open launch artifacts are enumerated there; they are required evidence to fill, not permission to start jobs.
