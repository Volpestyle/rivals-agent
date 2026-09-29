# Match transfer improves; distinguish zero pitch from fine aim

2026-09-28, 13:15 CDT outside research check-in. Advice to herdr-lead and
idm-owner / [VUH-1353](https://linear.app/vuhlp/issue/VUH-1353). No dispatch,
compute launch, split mutation or model change by the evaluator.

**Continue the authorized Mac refit.** The preceding match diagnostic answered
the intended question, and the inexpensive deadband experiment eliminated one
bounded correction. The refit is a reasonable next bet on more match coverage;
the new data is not yet an established fix for pitch.

## Delivered learning and the current bet

The [match result](../evidence/idm-range-to-match-result-20260928/report.md)
(`345d346`) shows useful yaw transfer on the fixed windows: common-row MAE is
0.3893 degrees versus 0.4371 for the prior IDM and 0.8620 for zero. Full03
improves moving-camera MAE and one-second accumulated error over the prior model
in every source on both axes. Derived pitch remains weak: pooled MAE
0.3347 versus zero's 0.3330, with material differences by source. These are
exploratory comparisons, not Gate 2 or broad labeling permission.

The [pitch deadband result](../evidence/idm-pitch-deadband-result-20260928/report.md)
(`31b7eab`) is a useful 93-second negative. None of nine nonzero candidates met
the preset TRAIN criteria; no range-dev or remainder-match inference followed.
This rejects that bounded grid under those criteria. It does not prove every
magnitude correction fails, or that a learned stillness head is now necessary.
There is no reason to keep searching cutoffs to rescue this result.

The [new refit](../evidence/idm-match-refit-mac-freeze-20260928/README.md)
adds -7/-8/-10, excludes whole -11/-12 families, and keeps their 37,980 frozen
remainder rows for the readout. Training now covers 200.976 minutes, including
about 34.050 match minutes: approximately 17% matches, up from 8% in full03.
The same architecture/recipe with more match coverage is a useful bounded test.
The readout already includes **new raw, full03, prior and zero**, with shared
answered rows. Retain that immediate full03 baseline.

I agree with retaining two whole families outside the fit instead of consuming
every available match. They remain exploratory development evidence: earlier
blocks from these families helped identify the weakness and choose this
direction. Their unread prediction windows are not an independently untouched
source domain. Existing sealed Gate 2 contracts remain separate. Do not ask
James for replacement matches merely to proceed with this run.

## New clue from the saved predictions

The report correctly defines "still" as `abs(truth) < 0.5 degrees` per 60 Hz
interval. This includes real movements approaching 30 degrees/second; it is not
synonymous with zero input. I regrouped only the already-scored 9,000 match-probe
IDs using the common full03/prior pitch mask. No inference, postprocessor or
remainder-window scoring was performed.

| Logged derived pitch | Common rows | Full03 MAE | Prior MAE | Zero MAE |
|---|---:|---:|---:|---:|
| Exactly zero | 2,627 | 0.12472 | 0.11059 | 0 |
| Nonzero, magnitude below 0.5 degrees | 4,405 | 0.24747 | 0.24495 | 0.19361 |
| Magnitude at least 0.5 degrees | 1,819 | 0.84943 | 0.92165 | 1.15135 |

Thus **62.6% of the 7,032 "still" rows contain nonzero pitch input**. Full03
worsens exact-zero MAE in four of five sources; on small nonzero input it loses
to zero in all five. The failure includes both spurious movement and inaccurate
fine movement. A detector that merely separates stationary from moving input
would address only part of it. This does not identify the cause: visual
ambiguity, temporal alignment, target calibration, training composition and
the learned output distribution remain possible contributors.

Method/provenance: saved predictions SHA256
`72cf61a0df2d015bf520b3fff91f76d37f86a40b69b5cbb46f34d83e4dc5f86c`,
under `idm-range-to-match-result-20260928/diagnostic-result/`; the five target
hashes match `data/idm/range-to-match-20260928/preparation.json`. Prediction IDs
alone selected scored rows. Counts sum to the report's 8,851 common pitch rows.
These are correlated interval summaries, not independent trials or a new
acceptance rule. Pitch degrees retain their derived-calibration qualification.

**Use this distinction when interpreting the coming result**, preserving the
frozen readout and model choices. If the refit remains weak, first inspect
exact-zero versus small-nonzero errors in saved outputs before proposing another
stillness detector or broader training run. Keep unsupported labels unknown;
improved yaw alone does not validate pitch or buttons. No new experiment is
needed while this fit is running.

## Execution and resource judgment

The run started at 13:06 CDT with epoch checkpoints. Watcher observations at
18:15:47 and 18:17:47 UTC advanced from 54,400 to 86,400 of 2,166,222 example
visits, roughly consistent with the provisional 2.3-hour fit estimate once
loading is excluded. Peak reported RSS is 95.16 GB; system swap reports
12,506.31 MiB, unchanged over these snapshots. Swap usage alone does not establish
current thrashing or attribution to this job. The planned first-epoch rate and
memory check is appropriate; no evidence here warrants stopping or restarting
the fit. No new cloud compute is running. Trust the existing checkpoint and
completion observers rather than add another monitor or review ceremony.
