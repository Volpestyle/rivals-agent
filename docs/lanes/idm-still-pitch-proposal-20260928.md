# Proposed TRAIN-only pitch correction and next refit

Owner: idm-owner / [VUH-1353](https://linear.app/vuhlp/issue/VUH-1353), 2026-09-28.
**Proposal only: no selection job, inference, fitting, decode, upload or cloud job has run for this proposal. Lead acceptance is required before compute.**

## Recommendation and limits

First try a **pitch-only deadband on frozen full03**, selected exclusively on the eight admitted TRAIN ranges. Keep yaw, weights, existing abstention, support and press outputs unchanged. It costs $0 on the Mac and directly tests whether small predicted pitch values are avoidable noise. Do not buy another full refit to answer that question.

The [completed match diagnostic](../evidence/idm-range-to-match-result-20260928/report.md) motivates this hypothesis; none of its 9,000 rows may choose the threshold, candidate or acceptance constants. A magnitude deadband cannot distinguish every real small movement from noise. It may fail, and failure is a useful result. This is not a learned stillness detector, a new pitch calibration, or a claim that suppressed predictions have become more certain.

## One bounded correction, chosen on TRAIN only

For an already-answered pitch prediction `p`, use `0 if abs(p) <= tau else p`. Preserve `None` as `None`. Preserve yaw exactly. Candidate thresholds, in degrees per 60 Hz interval, are fixed now:

`tau in {0, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50}`.

`tau=0` is the identity control. No scene/session-specific thresholds, truth-dependent switches at inference, temporal smoothing, new confidence gate or parameter search beyond this list. A correction cannot recover an abstained row. Retain the original uncertainty values for provenance but do not claim that they are calibrated for the transformed output. Report which rows were zeroed and their originally predicted magnitude, so improvement cannot hide coverage loss or aggressive suppression.

Calibration data are the eight TRAIN ranges used by full03: `051828`, `200129`, `232304`, `021320`, `025230`, `203745`, `035932`, `045729`, with their existing exact session IDs/admission/target/store pins. Neither match data nor the two range-dev sessions choose `tau`.

After acceptance, before any new predictions:

1. From metadata, enumerate chronological, non-overlapping 900-row blocks within admitted normal-regime contiguous runs with the existing complete +/-8-tick context. Select four blocks per range at block-list indices `floor(j*(B-1)/3)` for `j=0,1,2,3`. Require four distinct blocks; otherwise refuse and report rather than inventing a fallback. Freeze exact IDs and target hashes. Maximum 28,800 rows, eight source minutes; no selection by truth magnitude, positives or confidence.
2. Infer frozen full03 once on those blocks. All candidate scores are then cheap CPU arithmetic on the same predictions. Score each range separately and weight the eight sources equally, rather than allowing the longest recording to dominate.
3. A nonzero candidate qualifies only if it reduces macro still-pitch MAE by at least 5%, does not increase macro overall pitch MAE, and does not worsen either moving-pitch MAE or one-second accumulated pitch error by more than 2% in **any** calibration range. If a source has fewer than 30 answered moving rows or five complete one-second windows, the experiment is undecided; do not relax these guards. “Still” retains the existing `abs(truth) < 0.5` definition.
4. Among qualifying candidates, choose the lowest macro overall pitch MAE; exact ties choose the smaller threshold. If none qualifies, select identity and stop with a negative calibration result. These constraints are design choices fixed before this experiment, not measured optimal cutoffs.
5. Freeze the chosen rule and calibration receipt. Run it once on the existing range-dev sources `171533` and `205528`, using their normal complete rows. This is a veto, not a second tuning set: require at least 5% macro still-pitch improvement, no macro overall degradation, and <=2% degradation in moving-pitch and one-second error in each dev source. On failure, stop; do not select a different candidate using dev or matches.

The base network already fitted the TRAIN ranges, so these calibration scores are optimistic and are not an independent model generalization result. The range-dev veto and the following untouched prediction set provide separate checks. No new learned model or retraining is needed for this first attempt.

## Freeze the unread match check before predictions

Use the existing admitted stores for -7/-8/-10/-11/-12; retain their `idm_train` roles. Freeze this check manifest at the same metadata preparation step as the range calibration manifest, **before calibration predictions or later-match predictions**. Keep all five sources; do not pick easier interiors.

- Start with every otherwise eligible, context-complete row outside the exact 9,000 original IDs in the frozen selection manifest. Exclude a one-second time embargo on either side of both previously read blocks in each source. Also refuse any candidate whose full visual context intersects those blocks' visual contexts. This removes immediate boundary reuse, not only duplicate scoring IDs.
- Exclude rows whose context contains any of the fifteen store-inspection sample frame indices already viewed. This makes the visual exclusion explicit; previously decoding/storing frames is not itself a new prediction or scientific readout.
- Within each remaining admitted contiguous run, retain complete chronological, non-overlapping 60-row chunks, dropping trailing fragments. No chunk crosses a gap, admission boundary or exclusion. Freeze exact IDs, context frame ranges, source/admission/store hashes, and per-source exclusion counts. Assert disjointness from the original blocks and their context/embargo before inference. The untrimmed upper bound is 102,340 rows (111,340 usable minus 9,000); the exact smaller count is intentionally not claimed before metadata preparation.

After the TRAIN selection and range-dev veto pass, infer full03 and the prior model once on that frozen remainder. Compare corrected full03, untouched full03, prior and zero motion. All arms share the same per-axis answered mask; the correction preserves the full03 mask. Lead the report with per-source moving/still, suppression frequency and one-second slices; retain gain/speed strata and then pooling. Reuse no previous 9,000-row results to select a winner. No second threshold after this readout.

Proposed exploratory success criterion: at least 5% source-macro still-pitch MAE improvement over untouched full03; no source-macro overall or one-second degradation; moving-pitch MAE no more than 2% worse macro or 5% worse in any source. Report separately whether corrected pitch beats zero in each source; do not declare success from pooling alone. Yaw must be byte-identical to untouched full03. Failure ends this attempt and goes to the lead before another method is proposed.

These are new prediction windows from already-seen TRAIN families, not independent held-out matches. Reading their remainder is an exploratory diagnostic and does not open or replace the sealed Gate 2 pairs, reader-validation contracts, replay transfer or patch/settings checks. It supplies no permission for broad corpus labeling or button supervision.

## Mac cost and implementation work after acceptance

Recommended reservation: **one serial, niced Mac slot up to 45 minutes, $0 cloud**, with status, durable exit and collection receipts. Existing homogeneous native stores suffice: no media decode, new recording, frame extraction or original transfer. The recent two-model 9,000-row match inference completed in roughly 36 seconds including its five-store checks; extrapolating that rate is only a planning aid. Larger cold range stores, hashing, page cache and target construction can dominate. The 45-minute reservation allows these overheads; report an overrun rather than starting paid work.

Implement one small postprocessor and calibration/report path in the IDM lane. Synthetic checks cover identity, exact unknown preservation, yaw invariance, threshold edges, deterministic ties, source-balanced scoring, empty-support refusal, range-dev veto, and disjoint match contexts. Any changed data-admission boundary still requires its applicable review; this proposal changes no admission. Freeze the selected rule and readout manifest before use. No legacy `range_bc`/CM3 edits, no inherited uncertainty recalibration claim, and no change to the full03 artifact.

## Next expanded refit: scope, order and price

Only after this correction experiment reads out and the lead accepts a separate fit plan: **the same eight TRAIN ranges plus all eight currently accepted night matches -4a1/-5a1/-6/-7/-8/-10/-11/-12**, about **212.809 counted minutes** (166.926 range + 45.883 match). Current authority12 covers the receipts, and all native stores now exist. Recheck canonical current-receipt authority at freeze; no superseded receipts, partial stores, archive clips, unadmitted range fragments, sealed/test or additional sources.

Keep three epochs, seed 0, the full03 architecture/loss/order recipe and press vocabulary, with complete model/optimizer/RNG/order epoch checkpoints and verified resume. Start a fresh fit from the same initialization recipe, rather than calling a warm-start an equivalent refit. Separate the effect of extra matches from the postprocessor: report raw and corrected camera outputs, camera/press range-dev baselines, TRAIN-only press threshold calibration, and real/zero visual controls. If the pitch correction passed, its *selection protocol* stays fixed but its threshold must be selected anew using only the eight TRAIN ranges, because a new model has a new output distribution.

After the later matches enter this fit, **all their windows, including the unread-remainder diagnostic, become in-training evidence**. They cannot be reported as unseen transfer evidence for the new checkpoint. No new match holdout is silently carved from them; the lead must specify a genuinely separate transfer consumer or use the existing Gate 2 contract. The fresh refit would not itself resolve that acceptance gap.

| Route | Total pipeline plan | Additional paid cost | Qualification |
|---|---|---:|---|
| **Mac MPS, preferred** | Reserve about **6 hours** serially: scaled fit ~2.38 h, allow 45-90 min for TRAIN calibration, dev camera/press and real/zero reporting, 15-30 min for preparation/verification, then ~30% margin | **$0** | The earlier same-family three-epoch Mac fit took 54m06s for 80.53 min; this is an extrapolation, not a measured full-cohort rate. ~131.4 GB store bytes exceed physical RAM, so cache pressure can break linear scaling. Inspect the first epoch's time/memory and checkpoint before committing to the remainder of the queue slot; do not silently switch to cloud. |
| Modal L40S / 8 CPU / 32 GiB, fallback only | Planning work envelope **47,734 s (~13.26 h)** including 30% margin, plus 120 s startup/cleanup each | **About $34.49 compute; propose $35.50 including incremental storage allowance** | Not authorized by this proposal and above the remaining ~$8.42 lane estimate. Requires a new lead allocation/manual bill check and refreshed current pricing before launch. Stage verified stores locally and reuse accepted detached/checkpointed runtime. |

Modal estimate deliberately uses the completed full03 fit time, not the faster timing probe: `R <= (653842+111340)/653842 = 1.170286` (upper bound before new context trimming). Scale its measured 21,430.924-second fit by R = 25,080.305 s. Retain timing02's full post-fit inference at 6,691.981*R = 7,831.530 s, example loading 1,995.521 s, local re-verification 546.335 s, local staging 361.886 s, dev camera 302.729 s and a 600 s correction/report allowance. Base 36,718.307 s; multiply by 1.30 and round up. At the **recorded** $2.5844/resource-hour, plus 240 s startup/cleanup and $0.05 overhead, that is $34.49. These are planning assumptions, not a new throughput measurement or current invoice.

Reuse the retained 114 GB cloud input volume if a paid refit is subsequently chosen; stage the roughly 18.03 GB new stores in a separately pinned additive input packet/volume, without mutating the old freeze. Roughly 30 minutes of upload at the previously observed ~10 MB/s is host preparation, not GPU runtime; verify completion before creating a paid app. Incremental storage remains metered and needs the final retention duration in the launch estimate. No volume is written or deleted now.

## Requested decision and next owner action

Accept or amend the **45-minute/$0 pitch-correction experiment** first. Acceptance of that experiment need not authorize the six-hour refit or paid fallback. IDM owns implementation, pre-prediction manifests, TRAIN-only selection, the one range-dev veto, one unread match readout, and delivery to the lead. Until acceptance: no compute, Mac reservation, new model, threshold selection or match predictions. Gate 2 and larger-corpus labeling remain unproven.
