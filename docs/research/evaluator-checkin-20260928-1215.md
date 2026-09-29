# Motion coverage of the frozen match probe

2026-09-28, 12:15 CDT outside check-in. Lead adopted the previous recommendation:
the range relabeling pilot is withdrawn, and idm-owner is preparing frozen
full03/prior/zero inference on five later admitted TRAIN matches on the reserved
Mac. No additional cloud run. See [preparation report](../evidence/idm-range-to-match-preparation-20260928/report.md)
(`d9986c3`) and [VUH-1353](https://linear.app/vuhlp/issue/VUH-1353), revised
11:24 CDT. At wrap-up, the local completion watcher reported exit 0 for the four
remaining stores, following the earlier completed -7 store. Owner collection and
sample inspection precede inference; scientific results were still pending.

The implementation retains the existing motion/error slices and adds a common
answered-row comparison, including identical accumulated-error windows. That
addresses the differing abstention denominators in the previous range result.
I found no reason to interrupt the authorized comparison.

One narrow question was worth answering before its result: do the frozen first
and last 15-second blocks contain useful camera movement? I scanned only the
already-admitted target metadata, using the existing `T.usable` filter and
`abs(truth) >= 0.5 degrees/interval` moving definition. All five target hashes
matched `data/idm/range-to-match-20260928/preparation.json`; selected IDs came
unchanged from `selection.json`. No model, pixels, raw input recordings, sealed
sources, or new windows were evaluated or selected.

| Match | Selected yaw moving rows / 1,800 | Selected pitch moving rows / 1,800 | Yaw moving share in all usable rows |
|---|---:|---:|---:|
| -7 | 972 (54.0%) | 723 (40.2%) | 40.9% |
| -8 | 625 (34.7%) | 253 (14.1%) | 40.3% |
| -10 | 540 (30.0%) | 374 (20.8%) | 41.1% |
| -11 | 467 (25.9%) | 292 (16.2%) | 42.1% |
| -12 | 761 (42.3%) | 239 (13.3%) | 40.5% |

Pooled selected motion is **37.4% yaw / 20.9% pitch**, versus **41.0% / 22.5%**
across 111,340 usable rows in those five targets. The selected 9,000 rows contain
3,365 moving-yaw and 1,881 moving-pitch intervals: there is useful motion to
diagnose. These adjacent intervals are not independent trials.

The pooled resemblance hides source and block differences. For example, -10's
first block contains only 57 moving-yaw and 11 moving-pitch intervals; its last
contains 483 and 363. Conversely, -7's selected material is more active than its
whole usable session. The selected zero-motion MAE is 0.9021 degrees yaw and
0.3387 pitch, versus 0.9597 / 0.3662 over all usable rows. These are descriptive
truth statistics, not new IDM predictions. The all-usable comparison also lacks
the probe's complete-context selection condition.

**Recommendation:** finish this probe unchanged. Interpret its per-source,
moving/still and common-row comparisons before pooling; raw range-to-match MAE
alone mixes domain effects with camera-motion difficulty. Also retain the
existing calibrated/extrapolated speed slices: 35.6% of selected rows use the
extrapolated gain regime, and pitch truth remains derived. A clear failure can
guide the next correction; a good result supports the next Gate 2 step rather
than certifying all match/replay footage. Only if this bounded probe leaves a
specific decision unresolved should broader interior coverage be considered.
No extra sample selection, review gate, or worker is needed now.
