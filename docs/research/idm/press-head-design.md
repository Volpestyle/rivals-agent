# Candidate longer-context IDM press head

2026-09-26 · research-methods → steering lead / idm-owner · VUH-1353

**Recommendation:** test an edge-only, two-rate temporal head with frozen spatial frame features and a small trainable HUD encoder. Preserve the camera model. Give the edge head up to two seconds of future evidence, while keeping dense frames around the labelled interval. First test context length with otherwise identical models and exact human press labels. Do not simultaneously change the loss, introduce reader-generated labels, or claim that visible casts identify every physical key press.

This is a design handoff, not an implementation, experiment result, Gate 2 approval, or permission to launch. Only this document was written. No training, remote jobs, game input, Linear writes, or commits were performed. No session payloads were opened for this brief, including frozen dev 171533/205528. Evidence below comes from source code, published research, and existing repository reports, not fresh measurements of either cohort.

## What the existing evidence establishes

The [current model](../../../policy/idm/model.py) stacks 16 grey frame differences into channels, covering 17 frames at ±8 **60 Hz intervals**, or ±133 ms around the labelled interval's end. Its HUD input contains only the start/end RGB crops. Both convolutional encoders finish with spatial global average pooling; the press head has no explicit sequence of frame embeddings. Temporal information is present in the input channels, so “the model has no temporal information” would be incorrect. The limitation is short context plus early temporal mixing and lost spatial layout.

The [edge-input-2 experiment](../../evidence/idm-beta-nll-20260925/idm-edge-input-2.md) added HUD crops at +8/+16 **120 Hz video frames**, meaning +67/+133 ms. It failed its multi-seed, multi-fold criterion. That does not test a two-second window. Conversely, the failure does not prove short context is the sole cause: Amazing Combo ranking AUC was often appreciably above chance even when rate-matched onset F1 was poor. Timing, threshold transfer, rare positives, and invisible unsuccessful presses remain competing explanations. Jump already has detectable signal; preserve it as a control. Published historical fold summaries are background evidence, not authorization to reopen their now-frozen underlying sessions.

[VPT, Appendix D](https://arxiv.org/html/2206.11795v1#A4) supports the general architectural direction: its IDM combines an initial noncausal temporal convolution with per-frame visual processing and bidirectional attention. It uses 128 frames, approximately 0.5 billion weights, and avoids relying on poorly contextualized clip-edge predictions. Its 20 Hz context is 6.4 seconds. Those choices were evaluated in Minecraft with vastly more labelled data; they neither establish the optimal Rivals window nor bound the number of Rivals labels required.

## 1. Context selected from evidence, with uncertainty retained

The table uses the existing [press-lag aggregate](../../evidence/replay-hud-20260923/press-lags.json), interpreted by [replay-HUD lane §6](../../lanes/replay-hud.md). It covers four 20-second windows from 051828 and 200129. The underlying files named `validation-*.json` were **not** opened. These are inherited matched-event measurements, not newly recomputed interim/full-cohort statistics. They cannot establish that lag distributions stayed the same as the corpus grew.

| Action family | Matched first-HUD lag: n; min / median / max, seconds | Proposed context relative to interval end | Strength of justification |
|---|---|---|---|
| Amazing Combo | 12; .318 / .324 / .469 | −.20 to +.60 s | Covers the measured matched examples with a small margin; promising primary test action. |
| Get Over Here! | 5; 1.039 / 1.699 / 1.872 | −.20 to +2.00 s | Thin evidence. Inferred cooldown-start lag is instead .635 / .895 / .962 s. Preserve both timestamp meanings. |
| Team-up | 6; .260 / .316 / 1.685 | −.20 to +2.00 s | Cooldown-start lag is .002 / .004 / .010 s. Long context helps detect delayed display evidence; it does not imply the physical effect starts 1.7 s late. |
| Web Cluster | 35; .096 / .104 / 1.102 | −.20 to +1.20 s | Median already fits the short window; long tail can reflect unread frames or attribution to a later press. |
| Web-Swing / Simple Swing | 12 swing events; .008 / .319 / 1.556 | −.50 to +1.70 s | Exploratory. Charge loss does not distinguish the two inputs or reveal hold state. Many logged presses were repeats. |
| Jump and movement holds/onsets | No measured action-specific lag distribution here | −.50 to +.50 s | Engineering starting point, not a measured bound. More context may reveal locomotion, but camera motion and animation can confound it. |
| Spider-power, melee, targeting | Not measured here | −.50 to +2.00 s, exploratory only | Do not assert this window is sufficient. |
| Ultimate | One event at .0085 s | −.50 to +2.00 s, exploratory only | One match cannot size a reliable window or establish learnability. |

“Matched events” matters: the report lists 91 unmatched swing presses, 13 Web Cluster presses, eight team-up presses, and one each for pull/combo after exclusions. It attributes several to repeats, empty ammo, or cooldown. Visible evidence therefore measures a selected subset of presses. These small historical counts must not be reused as current cohort support counts.

**Concrete frame bank:** let zero denote the interval-end frame. Use dense offsets −8 through +12 at 60 Hz (21 frames), four past offsets −30, −24, −18, −12, and 18 future offsets +18, +24, …, +120. The union has **43 frames**, spanning −.5 to +2 s. Encode both global RGB and the native HUD crop at each selected timestamp. Apply the family limits above as attention masks; retain actual elapsed-time encodings, not just ordinal positions in the irregular sequence.

| Sampling alternative | Frames per anchor | Tradeoff |
|---|---:|---|
| Current-scale short context, −8…+8 ticks | 17 | Matched short-context control; inadequate future evidence for several abilities. |
| Uniform 60 Hz, −.5…+2 s | 151 | Best temporal coverage, but 3.51× as many frame tokens/crops as the two-rate design. Stronger fallback if sparse evidence aliases short events. |
| Recommended two-rate bank | 43 maximum | Dense onset neighborhood and 10 Hz outer context. Cooldown state often persists; brief effects may fall between sparse samples. This risk remains to be measured. |

This reduction is in **frames gathered per example**, not a 3.51× reduction in unique-frame extraction: sliding 60 Hz anchors collectively visit essentially every 60 Hz frame. Never run DINO separately on every overlapping window. Cache each unique source frame once.

Both arms must use the same anchors eligible for the longest window. Require every requested timestamp to lie in the same admitted, continuous, valid run; exclude insufficient-context anchors instead of padding across cuts, gaps, focus changes, or source boundaries. Report the lost minutes and positives per action. Noncausality is allowed only for this offline labeller, not for the live policy.

## 2. A small temporal architecture with an explicit parameter budget

Use the pinned DINOv2-small assets and preprocessing in [cm3_features.py](../../../policy/range_bc/cm3_features.py), but create a separate, correctly indexed IDM feature contract. The existing round-3 cache is not automatically usable: its anchor cadence is 30 Hz and its cohort includes identities forbidden here. Existing IDM [frame stores](../../../policy/idm/frames.py) contain grey global images, not the RGB global input DINO expects. Extending offset requests requires a new coverage manifest and audited timestamp/run guards, even where existing byte stores happen to contain the necessary later frames.

Proposed edge module, all dimensions fixed for costing:

1. **Global frame:** frozen DINOv2-small, roughly 22M parameters. Retain CLS plus the ordered 4×4 patch grid, 17×384 = 6,528 values per frame. Flatten in fixed spatial order and project to 128 dimensions. This preserves coarse spatial location through the projection, unlike one global mean. It can still lose tiny world effects; do not use it to replace the camera's pixel-motion pathway.
2. **HUD:** RGB 80×200; three stride-2, 3×3 convolutions with channels 16/32/32, GroupNorm and ReLU. Pool to an ordered 2×5 grid, flatten 320 values, project to 64. This learns local icon/charge evidence without asking the global DINO view to read tiny HUD marks.
3. **Temporal features:** concatenate to 192 dimensions and add fixed sinusoidal elapsed-time encoding. A 192→192, width-3 temporal convolution with LayerNorm over the dense neighborhood provides the central local-motion embedding. Use only its center output, which requires offsets −1, 0, +1; add it to each action query.
4. **Temporal attention:** 15 learned action queries, two cross-attention blocks, four heads, width 192, feed-forward width 384, two LayerNorms per block. Each query attends to the time-coded per-frame keys/values within its family window. No query-to-query mixing and no full-window key self-attention: otherwise a short-window query could indirectly receive forbidden future context through another token. Cross-attention complexity is proportional to 15×T, rather than T². Query residuals combine local motion with the selected past/future evidence.
5. **Output:** one separate 192→1 logit per action for the anchor interval. The camera branch and camera loss are entirely separate. Holds are a later independently scored extension, not silently inferred from the press logits.

| Component | Trainable parameters, proposed dimensions including biases |
|---|---:|
| Global 6,528→128 projection | 835,712 |
| HUD convolutions, GroupNorm, 320→64 projection | 35,040 |
| Local temporal convolution + LayerNorm | 111,168 |
| Two cross-attention / feed-forward blocks | 594,048 |
| 15 action queries + 15 output maps | 5,775 |
| **Proposed trainable total** | **1,581,743** |

These are architecture arithmetic, not a measured instantiated model. The count assumes no additional learned positional table, final norm, or shared output layer. The frozen backbone adds approximately 22M parameters but no optimizer state or backward activations during cached-head training.

[DINOv2](https://arxiv.org/abs/2304.07193) establishes useful frozen image and pixel representations across its evaluated tasks; it does not establish sensitivity to Rivals key onsets. A trained small RGB convolutional frame encoder is a reasonable fallback if frozen features miss the relevant change. Retaining a 4×4 spatial grid and projecting it would put such an alternative around 1M trainable parameters overall, depending on channels. It needs many more encoder evaluations during fitting and can overfit session appearance. Fine-tuning all of DINO adds roughly 22M trainable weights and expensive backward passes; neither alternative belongs in the first context comparison. No current evidence proves that increasing model size alone fixes the head.

## 3. Inputs and division of responsibility

**Use both images and HUD crops initially.** Full-frame-only sacrifices fine HUD detail; HUD-only cannot identify locomotion, distinguish a held key from a cast, or recover jumps consistently. The paired input gives the head a chance to combine animation and resource transitions. Later separate retrained HUD-only and global-only ablations can diagnose which evidence matters; zeroing a modality at inference is only an out-of-distribution sensitivity check.

**Do not feed the readers' event stream in the first experiment.** Train against James's independent human input labels. A future reader-assisted arm could add timestamped values, validity masks, event type, and uncertainty, all computed from pixels with frozen reader settings. It must beat a reader-only timing baseline against independently recorded input. Predicting labels generated by the same reader from that reader's events would largely measure reproduction of the labelling rule, not recovered human intent.

For eventual third-party labels, prefer reliable HUD-derived **successful ability events** for combo, pull, team-up and ammo changes, with explicit unknowns and timing intervals. A failed physical press may have no visible consequence; an IDM cannot reliably recover information absent from its observations. The useful independent IDM targets are jump, swing occurrence, and coarse movement/hold state where observable. Input holds/releases require their own head and independent scoring. Swing mode, automatic swing behavior, obstruction, airborne motion, and animation lock can make the inverse mapping ambiguous. Do not turn “character is swinging” into “physical Shift is held,” or turn an unseen press into a known negative. Reader ability labelling also still requires the lane's reliability checks; it is not accepted just because it is recommended here.

## 4. Targets, loss, support and event scoring

**First comparison:** retain exact 60 Hz human press-onset targets and masked binary cross-entropy. Derive targets through the existing raw-input/60 Hz contract, not by duplicating 30 Hz presses into both halves. Use the current train-only per-action positive weight, capped at 100, from [train.py](../../../policy/idm/train.py). Keep unknown labels masked, and preserve known unsuccessful presses as positives in this human-input experiment. Do not remove them based on model confidence or HUD visibility.

The statistical object is an onset event, even though the output tensor has one logit per interval. Evaluate one-to-one onset matches at the lane's existing ±2-interval tolerance, approximately ±33 ms. Do not enlarge that tolerance to two seconds merely because evidence arrives two seconds later. Report onset error as well as P/R/F1 and fire rate; ranking AUC alone is insufficient.

**Tolerance-aware training, only as a later separate arm:** an exact human onset can assign a normalized soft target over ±2 intervals rather than five full-weight positives, with care for adjacent distinct events. Alternatively marginalize an event-time distribution over its admissible interval. For reader labels, retain the full uncertainty interval and mask ambiguous neighboring rows; do not train a precise physical press target by subtracting a global median and declaring it exact. Interval-state targets belong to hold prediction, not press prediction. The current reader convention is documented in [replay-HUD §7](../../lanes/replay-hud.md); its calibration is not automatically valid on a new source.

Recount support after masks and context trimming, per action and training fold. Keep the lane's minimum training support rule (50 positives) and minimum 30 held-out onsets for a scored verdict. Below support: report **unsupported/undecided**, not a zero prediction or a failure. Earlier ultimate/melee counts describe an older cohort; this design makes no claim about their current support. If balanced sampling is later introduced, retain inclusion weights and compute threshold calibration on the original distribution. [Focal loss](https://arxiv.org/abs/1708.02002) is a possible subsequent imbalance ablation, supported originally in dense object detection; it cannot manufacture missing examples or distinguish an invisible unsuccessful press.

## 5. Cohort accounting and Mac resource envelope

James's earlier request was to compare 80.5-minute interim and 180.6-minute full admitted cohorts. The latest brief explicitly excludes frozen dev 171533 and 205528. Consequently, **180.6 minutes is a planning denominator here, not an allowed fit population**. The allowable expanded population is approximately 166.9 minutes. No empirical comparison on all 180.6 minutes is claimed or proposed under this brief.

The following arithmetic uses already-published 30 Hz row counts in the [camera analysis membership table](../camera-targets/analysis.md), multiplied by two for a nominal 60 Hz budget. These are upper planning counts, not newly built/verified IDM examples: actual input-known masks, frame coverage and long-context trimming reduce them. GB below is decimal. All costs are computed separately for each population rather than extrapolating an old action distribution.

| Planning quantity | Interim, 5 sessions | Full admitted, 10 sessions: budget only | Expanded allowed, 8 sessions |
|---|---:|---:|---:|
| Published eligible minutes | 80.5317 | 180.5578 | 166.9156 |
| Nominal 60 Hz intervals / frame budget | 289,914 | 650,008 | 600,896 |
| Global DINO cache, 6,528 floats/frame, float32 | 7.57 GB | 16.97 GB | 15.69 GB |
| Same cache if independently verified float16 storage is adopted | 3.79 GB | 8.49 GB | 7.85 GB |
| Grey global + RGB HUD unique-frame store, existing dimensions | 46.65 GB | 104.58 GB | 96.68 GB |
| RGB global + RGB HUD if both are retained raw at those dimensions | 112.11 GB | 251.35 GB | 232.36 GB |
| One-view DINO extraction at assumed 30–120 frames/s | .67–2.68 h | 1.50–6.02 h | 1.39–5.56 h |
| Three full passes of cached-head training at assumed 300–1,500 anchors/s | .16–.81 h | .36–1.81 h | .33–1.67 h |
| Three passes at historical .0029 s/example, for scale only | .70 h | 1.57 h | 1.45 h |

Prefer streamed RGB decode into a deduplicated feature cache plus native HUD bytes, rather than retaining the large raw RGB global store. Float32 cache storage matches the existing feature convention; float16 is an optional separately verified storage change, not an assumed free equivalence. Source video storage, indices, checksums, temporary files and context-edge overhead are additional.

**MPS memory estimate:** batch 16 with 43 cached global features needs about 18 MB in float32 before projection; its RGB HUD input needs about 132 MB after float conversion. The first HUD activation alone is roughly 176 MB. Including backward buffers, attention, allocator overhead and Adam, budget **2–4 GB active memory** for cached-head training, plus OS file cache. Do not preload the whole feature corpus onto MPS. Uniform 151-frame HUD processing may require roughly 6–12 GB or a smaller batch. Frozen DINO extraction is a separate phase with the existing bounded batch of at most eight views; budget roughly 2–4 GB active memory there as a provisional estimate. Measure peak allocation and resident memory in the owner's smoke run; these are not observed peaks.

**Throughput estimates are deliberately provisional.** No new MPS benchmark was run. The existing [IDM lane](../../lanes/inverse-dynamics.md) reports about 33 minutes for 170,112 stored frames and .0029 seconds per training example in its old architecture. The [later HUD experiment](../../evidence/idm-beta-nll-20260925/idm-edge-input-2.md) reports 1,095–1,211 seconds per three-epoch fit and 145 minutes for five fits plus 40 prediction passes. Neither measures the proposed DINO/HUD head. The assumed throughput ranges above must be replaced by measured decode, extraction, training and scoring rates before a full launch; there is no assured speedup from frozen features when HUD processing or disk access dominates.

**Cohort conclusion:** the proposed topology and lag-based windows do not change merely because the planning volume grows. Costs grow about 2.24× from interim to full admitted. Whether additional sessions change lag tails, action support, optimal thresholds or measured gains is **unknown**. Historical lag/edge summaries were not computed on both requested populations, so they cannot support a claim of unchanged empirical behavior. This is the explicit unresolved counterpart to the previous side-by-side requirement.

## 6. Smallest experiment that can support a useful decision

Run the following only after the owner implements and independently reviews the new context/target membership boundary. It is a train-internal design probe, not Gate 2 or a deployment result.

**Data:** use only admitted train sessions excluding 171533/205528 and every gate2/validation/test/sealed identity. Candidate held-out train folds are **051828 and 200129**, which occur in both the interim and expanded allowed sets. Hold out the entire session each time, with all caches and derived reader outputs following that session's role. These have historical combo support, but recount after the new masks; do not assume qualification from old totals. Fit on the remaining allowed sessions, never on the fold being judged. No temporal random split of overlapping windows.

**Two arms, three seeds each, two folds = 12 fits**, three epochs per fit, one fixed recipe:

- **S:** the proposed 1.58M-parameter head, global + HUD, only offsets −8…+8 at 60 Hz.
- **L:** identical head, initialization pairing, targets, anchor list, loss, optimizer, training order and training budget, with the two-rate family windows above.

Use paired seeds 0/1/2 and fixed AdamW lr 1e-3, weight decay 1e-4, batch 16, gradient clip 1 as an initial recipe, matching the existing trainer's basic scale. No checkpoint selection from held-out folds; score the predeclared final epoch. This isolates **added context conditional on the new architecture**. It does not isolate the architecture's improvement over the old pooled model. If S succeeds too, long context is not demonstrated necessary; an old-model matched rerun is a later architecture attribution experiment, not a hidden extra arm.

**Threshold and judge:** follow the [existing rate-matched protocol](../../evidence/idm-plumbing-20260924/idm-thresholds.md): set each threshold using only that fit's training probabilities and human onset rate. Freeze thresholds before held-out inference. Score every eligible known row, diagnostic abstention band off, with the existing event matcher. Compute chance F1 from 20 fixed-seed random predictions at the model's held-out firing rate on the same rows. Report per-action ΔF1 = model F1 − mean chance F1, including chance spread and threshold/fire-rate drift. Calibration passes and chance scoring belong in the compute budget.

**Primary decision:** Amazing Combo must have ≥30 eligible onsets on each fold and reach ΔF1 ≥.05 on at least two of three seeds **in each fold** under L. Require L's mean paired ΔF1 improvement over S to be ≥.03 in each fold to call longer context helpful; this extra margin is a proposed design criterion, not an existing accepted gate. Require jump pooled F1 under L to be no more than .05 below S. Report pull, team-up, swing, movement, cluster and other supported actions separately; no post-hoc choice of the best action or seed. The .05 chance bar and seed replication come from [edge-input-2](../../evidence/idm-beta-nll-20260925/idm-edge-input-2.md). Its two-fold diagnostic is distinct from the earlier four-fold signal verdict requiring three qualifying folds.

If combo is unsupported after trimming, the primary verdict is undecided. Do not substitute a better-performing action after seeing scores. A combo success alone establishes neither pull timing nor useful hold labels. High AUC with low event F1 points toward localization/calibration work; failure of both arms leaves frozen-feature sensitivity, label observability and training adequacy unresolved. It does not establish that more data cannot help.

**Staging and elapsed Mac time:** first complete both arms and all three seeds on 051828. Stop for futility if the primary criterion fails there; success requires the second fold as well. Do not present the stopped six-fit result as a two-fold success. At the provisional 300–1,500 anchors/s, all 12 three-epoch fits cost approximately **3.6–18.0 hours** on the expanded allowed cohort before calibration/evaluation. Add roughly 1.4–5.6 hours for DINO extraction, about two hours for decode at the old store's rough rate, and 1–5 hours for hashing, smoke checks and scoring: plan roughly **8–31 hours sequential Mac time**, to be replaced by the smoke forecast. No parallel queues or remote job launch is authorized by this handoff.

The same 12-fit design on the interim cohort costs about **1.5–7.7 hours fitting**, roughly **4–14 hours end to end** under the same assumptions. An explicit interim-versus-expanded replication therefore means **24 fits and approximately 12–45 hours total**, with potential cache reuse; it is not the smallest context test. Report the two populations side by side if both are run and flag changed conclusions. A literal 180.6-minute empirical counterpart remains outside this brief because it includes frozen dev. These timings are not a budget approval or a promise of quality after three epochs.

**Next consumer:** idm-owner can use the two-rate specification, independent human-target experiment and provisional budget in the Gate 2 plan. The unresolved decisions are empirical—feature sensitivity, current per-fold support, reader reliability and measured MPS cost—not a need to redesign the camera head or reopen frozen evaluation data.
