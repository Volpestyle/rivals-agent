# Review: the 2026-09-24 multi-speed calibration record (030045)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only. I decoded on the CPU with 4 threads
at below-normal priority, after the game and OBS had exited.

**The record:** `data/human/calibration/20260925T030045-211Z-7804-3/`, `calibration.json` `c84da2f9`, freeze
`artifact-hashes.json` `7e8bb3f2`, and the hand-back `calibration-take-0924.md`.

**My review aids,** all in my scratchpad:

- `cal0924.py`: own frames, own SIFT pipeline, focal 930 and 960 px
- `cal0924b.py`: the world-yaw decomposition
- `cal0924c.py`: the slow-turn frame variants
- `cal0924.json`: the results
- `rv/cal0924-*.jpg`: the frames

## Verdict: supported for the medium, fast and fastest turns; the slow turn's number is not reproduced to its stated precision

**The speed-independence claim holds.** On three of the four turns, my own measurement agrees with the record to
0.04 % or better. The spread I find across all four turns (0.37 %) is still far below the regime question's scale:
the estimator itself reads about 3 % high.

**The slow class is less certain than stated.** Its value 10,892.2 ± 0.08 % is **not reproduced**. My independent
pipeline gives **10,904-10,917**, which is **0.11-0.23 % higher**. Its stated uncertainty should be about ±0.25 %.

## The freeze

- **Equal to the pins:** all 15 folder files, plus the six externals:
  - the original, re-hashed by me as `ff6b1fa0…0aca`;
  - the logger's `metadata.json`, `inputs.jsonl` and `frames.csv`;
  - `code-snapshot-2ad0992/manifest.json`;
  - the 09-23 `calibration.json` `baa49158`.
- **Nothing unpinned:** the only file in the folder that isn't pinned is `artifact-hashes.json` itself, whose sha256 is
  `7e8bb3f2`, as stated.

## My reproduction of the still-to-still turns

**The strokes, from `inputs.jsonl` by my own gap split** (no motion packet for 0.3 s or more):

- Four rightward yaw strokes: **+10,783 / +10,927 / +10,846 / +10,868 x counts**. The last is followed by a −14
  correction stroke at 18.74-18.82 s.
- The x counts between still frames equal the record's for all four, including 10,854 for the fastest.
- All four turns are rightward, one stroke per class.
- The only non-mouse input is the closing Alt.
- The one left click (4.52 s) is inside the slow stroke, away from both still frames.

**The method.** My pipeline is independent of the snapshot `Estimator`:

- **Frames:** my own still frames, all at least 0.15 s from the nearest motion packet and different from the owner's.
- **Features:** SIFT with a 0.7 ratio test, with the HUD, the corner overlays and the hero masked.
- **Fit:** RANSAC Kabsch on unit rays.
- **Focal:** 930 px, the estimator's, and 960 px (3 % longer, the record's own scale finding).
- **Decomposition:** each rotation is also split into world yaw between two pitched views
  (`R = X(−θb)·Y(−Δψ)·X(θa)`), because the camera-frame yaw extraction mixes in pitch.

**Controls.** Four still-to-still pairs within still gaps read at most **0.0011°** of yaw, on 1,434-1,725 inliers.

| Turn | My frames (s) | Inliers | World-yaw excess (930 / 960 px) | My counts/360 | Record |
|---|---|---|---|---|---|
| **medium** | 10.25 → 14.10 | 336-359 | +1.696° / +1.625° | **10,875.8-10,877.9** | 10,880.0 |
| **fast** | 14.10 → 16.95 | 307-330 | −1.491° / −1.469° | **10,890.5-10,891.1** | 10,888.2 |
| **fastest** | 16.95 → 20.50 | 156-174 | −1.237° / −1.193° | **10,890.1-10,891.4** | 10,891.3 |
| slow | 2.45 → 10.25 | 73-81 | −4.410° / −4.271° | 10,912.5-10,916.7 | 10,892.2 |

**Medium, fast and fastest are reproduced.** The mean of my three is 10,886, within 0.01 % of the 2026-09-23 slow
closure (10,884.76). Between medium (3.8k counts/s mean) and fastest (12.1k), the gain changes by 0.13 %, in the
direction *opposite* to acceleration. So the claim that the game's mouse acceleration (on, threshold 1.00) has no
measurable effect holds on my evidence.

**The slow turn is not reproduced.**

- My pipeline reads the same excess on every frame pair I tried, **including the owner's own frames (2.298 → 9.598
  s)**: camera-frame yaw −4.14°, world yaw −4.40°, against the record's −3.61°.
- So the gap is method, not frame choice.
- **The cause is visible on the frames:**
  - the two views differ by about 8° of pitch;
  - near geometry (floor, rail, the 30 m marker) shifts with the orbit camera's vertical motion, i.e. parallax, not
    rotation;
  - both pipelines fit on few far-field inliers (116 in the record, about 75 in mine).
- A rotation-only fit is model-limited here. The disagreement of 0.5-0.8° is 0.15-0.23 % in gain.
- **Required wording change:** the record's "±0.3°, 0.08 %" for the slow turn should read about ±0.8° (±0.25 %).
  Alternatively, drop the slow class from the headline range, since the 09-23 slow closure already covers that speed.

## Is the claim, with its stated limits, supported?

**Speed-independent yaw gain: yes, from 3.8k to 12.1k counts/s mean** (peaks to about 27k), on my evidence.

- The slow class (1.8k) agrees within 0.25 % at worst.
- The 09-23 closure covers the slow end.
- **For the "extrapolated" regime, this is enough:** gain changes at the 0.1-0.3 % level are an order of magnitude
  below the estimator's own 3 % scale error.

**Coverage.**

- **On 025230 and 232304** (100 ms bins of |dx| while moving):
  - median 730-840 counts/s;
  - p99 13.6-14.2k;
  - p99.9 21.2-22.0k;
  - max 24.4k and 45.0k.
- **What that means:** the calibration's peak rates (up to about 27k) reach about p99.9 of play. The class means
  (1.8-12.1k) sit above the play median, which the 09-23 slow closure covers.
- **Against the record:** "median to about p99.9" is fair. The record's "1,040 counts/s" median uses a different bin
  definition from mine.
- The fastest 0.1 % of play, such as 232304's 45k flick, is still not covered.

**The stated limits are right, and should stay attached to any use of this record:**

- **Rightward only:** every stroke is +dx. A leftward gain is not measured.
- **One stroke per class:** there are no repeats, so the per-class spread is not a repeatability measure.
- **Pitch not established:** agreed. I didn't try to measure pitch. The record doesn't claim it, and the header keeps
  pitch = yaw by the lead's 09-23 decision.

**The header.** It is unchanged: the 09-23 v2, 0.0330738°/count. My three reproduced turns give a mean of 10,886.1
counts/360, which is 0.033070°/count and 0.01 % from it. That confirms the header's gain is right to use across speeds. Relabelling
the gain kind is the lead's call; nothing here requires a re-step.
