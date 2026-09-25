# The pitch-uncertainty fix, final round: k fitted on each bin's truly fast rows, 2026-09-25 (VUH-1353)

Owner: the inverse-dynamics lane (scoreboard-fix). Next consumer: Gate 2 (replay pitch labels).

- **Pre-registration:** `docs/lanes/inverse-dynamics.md` "### Pitch-uncertainty fix, final round: k fitted on each
  bin's truly fast rows (pre-registered 2026-09-25)". Section LF sha256
  `f1385679d565c2fe48c80c2ed1f4d6890abd50af59db52f2177d8640a14e2b8e`; the frozen copy is
  `idm-pitch-fix-3-prereg-section.md`. The lead approved it before anything was computed, and it landed in `985e527`.
- **Inference-only,** on the same seven β-NLL per-row prediction files. PC only. No retraining, no model or predictor
  code change.
- **Not done:** no commits, no Linear, no game input.

## Result: arm A PASSES, so A is the fix (pre-registered reading)

| Arm | (1) Coverage ≥ 0.70 / 0.90, both true bands, both folds | (2) 1° / 3° bounds, all six runs | (3) Yaw identical row for row | Verdict |
|---|---|---|---|---|
| **A** (dev-fold fit) | **met:** 051828 extrapolated **0.718 / 0.948**, calibrated 0.881 / 0.983; 205528 extrapolated **0.756 / 0.964**, calibrated 0.906 / 0.975 | met | met | **PASS** |
| **B** (cross-fit) | not met: 051828 extrapolated **0.682** / 0.937; 205528 meets (0.760 / 0.964) | met | met | fail (moot: A passed) |

**The deployable parameters (A's dev-fold fit on `a4-beta` / 171533):**

| Yaw-std bin | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| Range of the stated yaw std (°) | < 0.0606 | 0.0606–0.1076 | 0.1076–0.1700 | 0.1700–0.3517 | ≥ 0.3517 |
| Truly fast fit rows | 0 | 0 | 18 | 553 | 1,601 |
| **k** (pitch std ×) | 1 (under 50) | 1 (under 50) | 1 (under 50) | **1.6005** | **1.2430** |

- A value on an edge goes to the upper bin.
- Applied at inference to every row by its yaw-std bin: s′ = k · s, and pitch is answered iff s′ ≤ its predicted
  regime's bound.
- The exact values are in `pitch_fix3-params.json`.

**A's fit set in-sample:** calibrated 0.890 / 0.985, extrapolated 0.740 / 0.953.

## Arm A per run and pooled (within 1σ′ / within 2σ′ / pitch abstention / answered within bound)

| Fold | Run | Band | Before | After |
|---|---|---|---|---|
| 051828 | T (`yaw-t0`) | extrapolated | 0.560 / 0.862 / 0.2 % / 0.946 | 0.693 / 0.939 / 1.4 % / 0.950 |
| 051828 | T1 | extrapolated | 0.626 / 0.901 / 0.7 % / 0.946 | 0.730 / 0.954 / 2.2 % / 0.951 |
| 051828 | T2 | extrapolated | 0.611 / 0.885 / 0.9 % / 0.938 | 0.731 / 0.951 / 2.6 % / 0.943 |
| 051828 | **pooled** | extrapolated | 0.599 / 0.883 / 0.6 % / 0.943 | **0.718 / 0.948 / 2.0 %** / 0.948 |
| 051828 | **pooled** | calibrated | 0.798 / 0.971 / 0.2 % / 0.998 | 0.881 / 0.983 / 0.8 % / 0.998 |
| 205528 | s0 | extrapolated | 0.637 / 0.928 / 3.2 % / 0.925 | 0.753 / 0.970 / **9.6 %** / 0.946 |
| 205528 | s1 | extrapolated | 0.658 / 0.907 / 0.4 % / 0.958 | 0.769 / 0.963 / 1.9 % / 0.963 |
| 205528 | s2 | extrapolated | 0.622 / 0.897 / 0.6 % / 0.954 | 0.746 / 0.958 / 2.0 % / 0.959 |
| 205528 | **pooled** | extrapolated | 0.639 / 0.911 / 1.4 % / 0.946 | **0.756 / 0.964 / 4.5 %** / 0.956 |
| 205528 | **pooled** | calibrated | 0.846 / 0.968 / 0.4 % / 0.999 | 0.906 / 0.975 / 2.2 % / 0.999 |

The per-run calibrated-band rows, and all of arm B, are in `pitch_fix3-out.md`.

## Caveats, stated as caveats, not new conditions

- **The 051828 margin is narrow:** 0.718 against 0.70 pooled. One of its seeds alone (T) reaches 0.693. The judge is
  per fold pooled, as registered.
- **This is the third pre-registered round on these same judge sets:** the calibration, round 2 and round 3. Each round
  was registered before it ran, but passing on the third leaves some risk of selection across rounds.
  **A confirmation on the three new admitted takes, as fresh held-out sessions, before fast-band replay pitch labels
  are relied on, would remove it.** I recommend it; it is your call.
- **The cost in answered rows:**
  - pitch abstention in the extrapolated band rises from 0.6 % to 2.0 % and from 1.4 % to 4.5 % (pooled);
  - it reaches 9.6 % on `a1-beta-s0`;
  - the calibrated band rises to 0.8 % and 2.2 %.
- **The k values are not monotone:** bin 3 (1.60) is above bin 4 (1.24). That fits the not-pre-registered finding
  that the fast rows predicted slow sit mostly in bin 3.
- **Deploying it** means a reviewed change to the predictor's stated pitch std: these edges and k values applied in
  `policy.idm.train._camera`. It is not made here.

## Hashes

**Scripts and outputs:**

| File | sha256 |
|---|---|
| `pitch_fix3.py` (round 2's script with only the fit rule and labels changed; the diff is below) | `6769ad60964b203dbd2198de889c547e08861fbd682eabf23d4ff44f12fe144f` |
| `make_pitch_fix3.py` (derives `pitch_fix3.py` from `pitch_fix.py` `ecea7e84…`) | `de8ff76d71dffc025bdc8032829aa5929dcd7b95462270f0e10d53674c7a8821` |
| `pitch_fix3-out.md` (every per-run row, both arms, and the non-pre-registered share table) | `6036b90a0e30f03563da4b55cfb4434bfd74581c4596f872ef39ac51ab78f854` |
| `pitch_fix3-params.json` (edges, k and fast-row counts for A and both B fits) | `6f8dba7b04336c3fd4ce5dcd2acaa8b5a6e4578678643dedb7d942b1549bcff3` |
| `idm-pitch-fix-3-prereg-section.md` (the frozen section) | `f1385679d565c2fe48c80c2ed1f4d6890abd50af59db52f2177d8640a14e2b8e` |

**The only code difference from round 2:** k is fitted over `rows ... if bin == b and r["regime"] == "extrapolated"`,
with `k = 1 if fewer than MIN_FAST (50)`. Everything else is round 2's code.

**Inputs:** unchanged from round 2 (`idm-pitch-fix.md`): `a4-beta-on-171533` `822f22dc…`, `yaw-t0/t1/t2` on 051828,
and `a1-beta-s0/s1/s2` on 205528. All are in
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\idm-diag\`.

## The lane doc

- **New LF sha256:** **`aac314f20046d5b610fc6c3487141572f3dfa1e5a87aa2c2bd5f448afb1b827a`**. It was `6780190c…`, as
  landed in `985e527`.
- **What was added:** "**Result (measured 2026-09-25): arm A PASSES**" at lines **1289–1308**, after the round-3
  section and before "### The edge head's input".
- **Pins:** a pure insertion; the round-3 section is still `f1385679`.

## For `docs/evidence/idm-beta-nll-20260925/`

- **Files:** this file (`idm-pitch-fix-3.md`) and the frozen section as `idm-pitch-fix-3-prereg.md` (the content of
  `handoff\idm-pitch-fix-3-prereg-section.md`, `f1385679…`).
- **Draft README row:**

  **Pitch-uncertainty fix, final round (`idm-pitch-fix-3.md`; pre-registered in `idm-pitch-fix-3-prereg.md`,
  f1385679):** arm A PASSES, so A is the fix. The stated pitch std is inflated per quintile bin of the stated yaw std,
  with k fitted on each bin's truly fast rows of the dev fold: k = 1, 1, 1, 1.60, 1.24 at edges
  0.061 / 0.108 / 0.170 / 0.352°. The extrapolated band reaches 0.718 / 0.948 on 051828 and 0.756 / 0.964 on 205528,
  against 0.70 / 0.90; the calibrated band meets; the bounds hold on all six runs; yaw is identical row for row. The
  cost is pitch abstention of 2.0 % and 4.5 % in the extrapolated band (9.6 % on the worst run). Arm B (cross-fit)
  fails on 051828 (0.682); that is moot. The 051828 margin is narrow, and this is the third round on these judge sets,
  so the lane recommends confirming on the new admitted takes before fast-band replay pitch labels are relied on.
  Deploying it is a reviewed predictor change, not made yet.
