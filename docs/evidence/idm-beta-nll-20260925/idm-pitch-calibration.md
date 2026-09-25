# scoreboard-fix: post-hoc pitch-std calibration under β-NLL (item 2 of the beta-default decision) (VUH-1353)

2026-09-25.
- **Pre-registration:** lane doc "### Post-hoc pitch-std calibration (pre-registered 2026-09-25)", LF sha256
  `e6b5d5265d6e3aff073a0fdffd45ae129d8257af1511d44c113235223fab3380`. It was sent before anything was computed and is
  unchanged.
- **Inference only:** one pass of `a4-beta` on 171533 (MPS, 13 s). There was no retraining and no code change.
- **Not done:** no commits, no Linear, no game input.

## Result: FAIL (pre-registered reading: the pitch cost stands as recorded)

**The fit** (`a4-beta` on 171533, per **predicted** band, k = max(1, the 0.683 quantile of |pitch error| / stated
std), nearest-rank):
- calibrated band: 7,357 rows, quantile 0.555, so **k = 1.000** (it already over-covers);
- extrapolated band: 1,903 rows, quantile 1.065, so **k = 1.065**.

**The judge.** Coverage is per fold (three seeds pooled), per **true** band, over answered pitch rows. Each cell reads
within 1σ′ / within 2σ′ / abstention.

| Fold | Band | Before | **After** | Needs | |
|---|---|---|---|---|---|
| 051828 | calibrated | 0.798 / 0.971 / 0.2 % | **0.800 / 0.972 / 0.2 %** | ≥ 0.70 / ≥ 0.90 | meets |
| 051828 | extrapolated | 0.599 / 0.883 / 0.6 % | **0.621 / 0.893 / 0.6 %** | ≥ 0.70 / ≥ 0.90 | **fails** |
| 205528 | calibrated | 0.846 / 0.968 / 0.4 % | **0.848 / 0.968 / 0.4 %** | ≥ 0.70 / ≥ 0.90 | meets |
| 205528 | extrapolated | 0.639 / 0.911 / 1.4 % | **0.660 / 0.919 / 1.4 %** | ≥ 0.70 / ≥ 0.90 | **fails** |

| Component | Result |
|---|---|
| (1) Coverage ≥ 0.70 / 0.90 in both bands on both folds | **not met** (the extrapolated band on both folds) |
| (2) The 1° / 3° bounds hold on every run | met (answered pitch within its bound: 0.925–1.000 per run and band) |
| (3) Yaw untouched, row for row | met (every `ans_yaw`, `std_yaw` and `mu_yaw` identical) |

- Per-run rows are in `calibrate_pitch-out.md`. In the extrapolated band, every run moves by about 0.02 at 1σ, and
  none reaches 0.70.
- **Pitch abstention is unchanged** by a k this small.

## Why a scalar per predicted band cannot close it (reported, not judged)

The extrapolated coverage failure comes from two sources, and neither can be reached by one scalar keyed by the
predicted band.

1. **Fast rows predicted as slow keep k = 1.** Of the truly-extrapolated rows, 16–27 % are predicted calibrated,
   because the predicted pitch/yaw magnitude puts them under the band. Their 1σ coverage is the worst of any cell:

   | Session (run) | True extrapolated, predicted calibrated | Within 1σ | True extrapolated, predicted extrapolated | Within 1σ |
   |---|---|---|---|---|
   | 171533 (`a4-beta`, the fit set) | 410 rows | 0.480 | 1,761 | 0.633 |
   | 051828 (T) | 2,670 | 0.390 | 8,017 | 0.617 |
   | 205528 (s0) | 4,223 | 0.467 | 11,370 | 0.700 |

2. **The fit fold under-corrects.** 171533 is the least fast-heavy session (23 % extrapolated). Its extrapolated band
   needed only k = 1.065, while the fast-heavy judge folds' correctly-classified fast rows sit at 0.62–0.70 and would
   need more.

**What might work, not proposed here as a run:**
- a band variable known at inference that catches the misclassified rows, such as the predicted total speed with a
  margin, or the model's own pitch variance;
- a fit on the fast-heavy folds themselves, which would then need a separate judge fold.

Either would be a new pre-registration. The pitch cost of the β-NLL default stays as recorded in the decision entry.

## Hashes

| File | sha256 |
|---|---|
| `a4-beta-on-171533-predictions.jsonl` (the fit set; `a4-beta` checkpoint `90aa4bef…`, Mac and PC copies equal) | `822f22dc88ef284e4a913f299af0a2dfb6e42b3d8781bc56d75ea52f96b82e5a` |
| `calibrate_pitch.py` | `5558fcd74f8e6c2191de19ffb4cbff401e4c91bbb10cca03c7401fc8fc86eaf5` |
| `calibrate_pitch-out.md` | `989244ed2113db476c890c100f099b0adfa5dc794dc02f19dae832260d51e36b` |
| `calibrate_pitch-k.json` (`{calibrated: 1.0, extrapolated: 1.0647}`) | `42bc6407dfdfe224706514dc324752eca3c5bb3f74e82c42ee59855965def143` |

- **Location:** everything is in
  `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\idm-diag\`.
- **Judge inputs:** the existing per-row predictions of T/T1/T2 on 051828 and `a1-beta-s0..2` on 205528, with the
  hashes in `idm-yaw-test.md`, `idm-yaw-test-2.md` and `idm-beta-nll-2.md`.
- **Lane doc:** it now carries the decision entry (item 1) and this pre-registration, uncommitted. Its working-tree
  LF sha256 is `b3d07d8dc7b44774b2d99ceaac0b0e7334f6add508eae1c71e9bcf73ac150af6`. That supersedes the
  `idm-beta-default.md` figure, which was taken before this section was added.

**Parked after this.** The Mac is idle.
