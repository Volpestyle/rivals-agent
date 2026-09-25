# Whole-session intake, 2026-09-25: the four 2026-09-24 takes (VUH-1359, VUH-1309)

The independent per-session reviews (admission-review) and the admission lane's hand-backs (admission-owner) for the
takes James recorded on 2026-09-24, admitted on 2026-09-25 on `code-snapshot-b7d4592`:

| Session | Take | Counted min | Review | Verdicts |
|---|---|---|---|---|
| 20260925T025230-605Z-7804-2 | 21-52-30 | 3.664 | `review-session-025230.md` | `review-session-025230.verdicts.json` |
| 20260924T232304-170Z-12024-1 | 18-23-04 | 8.765 | `review-session-232304.md` (+ addendum for the edge-rule re-emission) | `.v2.verdicts.json` supersedes `.verdicts.json` for assembly |
| 20260925T021320-371Z-7804-1 | 21-13-20 | 34.516 | `review-session-021320.md` | `review-session-021320.verdicts.json` |
| 20260925T030045-211Z-7804-3 | 22-00-45, 46 s | calibration | `review-calibration-0924.md` | yaw gain speed-independent; the slow turn carries about +-0.25% uncertainty |

Tally after admission: 94.18 counted minutes of the 180 target, seven sessions, one cohort across both game builds.

Also reviewed and landed with this batch: the intake motor-step fix (`review-intake-motor.md`, `intake-motor-2.md`),
the frame-level edge rule (`intake-edge-rule.md`: a segment edge sits only on a frame the live range guard proves; no
spawn settle), the importer tolerance for one isolated duplicated composition time (`importer-dup-cts.md`,
`review-importer-dup-cts.md`), the wheel-binding audit (`bindings-wheel.md`), the calibration take
(`calibration-take-0924.md`) and the arrivals inventory (`arrivals-0924.md`). The owner hand-backs are
`admission-owner-final-14.md` to `-20.md`. Byte tables and freezes are inside each file; the session folders under
`data/human/sessions/` carry the pinned records.
