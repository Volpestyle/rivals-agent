# calibration-take-0924: the multi-speed take (030045). The yaw gain does not depend on speed

**Result.** The yaw gain is the same at every speed James turned.
- Four rightward turns, from 1.8k to 12.1k counts/s mean (peaks to 27k counts/s), measured still frame to still frame, give:
  - **10,880.0–10,892.2 counts per 360°**, a 0.11 % range with no trend in speed;
  - mean **10,887.9** (sd 5.6), which is **within 0.03 % of the 2026-09-23 slow closure (10,884.76)**.
- **Mouse acceleration** (on, factor 1.00, from the settings look) **has no measurable effect.**
- **For VUH-1353:** yaw degree targets above the old calibrated band no longer rest on extrapolation.
- **Header:** unchanged. The step header keeps the 09-23 calibration (v2, 0.0330738 deg/count), which this take confirms
  across speeds. Relabelling its gain kind would re-step the admitted tables, so that is your call.

Record: `data/human/calibration/20260925T030045-211Z-7804-3/`, frozen (`artifact-hashes.json` `7e8bb3f2…`).
- The check is clean.
- The freeze pins the original, the logger files, `code-snapshot-2ad0992`'s manifest and the 09-23 calibration.
- Everything decoded after OBS and the game exited, at four threads and below-normal priority.

## Yaw, per speed class

**Method.** The snapshot's camera `Estimator` fits the rotation between the still frame before a turn and the still frame
after it; that is the turn's excess over one revolution.
- Degrees = 360 + excess.
- Gain = degrees / the x counts between the two still frames.
- Both ends are still, so display latency does not enter.
- **Control:** adjacent still frames read at most 0.009° (1,267–1,350 inliers).

| Class | Mean counts/s (peak) | Still frames (s) | x counts | Excess | Turn | Counts/360 | Degrees/count |
|---|---|---|---|---|---|---|---|
| slow | 1,806 (2,720) | 2.30 → 9.60 | 10,783 | −3.61° | 356.39° | 10,892.2 | 0.0330511 |
| medium | 3,841 (6,330) | 10.00 → 13.70 | 10,927 | +1.56° | 361.56° | 10,880.0 | 0.0330884 |
| fast | 6,207 (13,250) | 13.90 → 16.50 | 10,846 | −1.40° | 358.60° | 10,888.2 | 0.0330632 |
| fastest | 12,088 (26,960) | 16.80 → 19.20 | 10,854 | −1.23° | 358.77° | 10,891.3 | 0.0330540 |

**Uncertainty.**
- Each class's gain is good to about ±0.02–0.08 %. The excess scales with the estimator's focal (about 3 % off for this
  footage, below), which means ±0.03–0.11° on excesses of 1.2–3.6°.
- The slow turn is the least certain: its still frames differ by 8.3° of pitch (197 y counts) and fit on 116 inliers.
- **Coverage against play:** these speeds span the three new play takes' yaw rates from the median (1,040 counts/s) to
  about p99.9. The 09-23 slow take covers below.

## For the inverse-dynamics lane: the estimator reads about 3 % high on this footage

The per-pair estimator (focal 465 px at 1280 wide), summed over each turn against the still-to-still truth:

| Turn | Estimator sum | Truth | Difference | Pairs fitted |
|---|---|---|---|---|
| slow | 365.0° | 356.4° | +2.4 % | 838 of 876 |
| medium | 373.1° | 361.6° | +3.2 % | 435 of 444 |
| fast | 371.9° | 358.6° | +3.7 % | 298 of 312 |
| fastest | 323.4° | 358.8° | −9.8 % | 226 of 288 |

- This is consistent with a focal about 3 % short for James's footage. A refit on this take is the IDM lane's call.
- The fastest turn fits fewer pairs, and the fitted pairs under-read: blur at about 3–7° per frame.
- **Per-pair ratio by rate band.** The ratio (estimator ÷ counts) sits at 0.032–0.036 in every band from 0 to 64k counts/s,
  with no trend beyond that bias.
- **Lag.** The yaw-vs-counts correlation is flat within ±30 ms (0.90–0.93, peak at 5–10 ms). These data do not pin the lag.

## Pitch: not established; stays derived equal to yaw

- **Still-to-still rotation fails.** Across a 64° sweep there is too little overlap (0 inliers). The orbiting camera also
  moves as it pitches, so the estimator's pitch sign flips near the limits (the 09-23 record found the same).
- **What it does show:**
  - Over the moving pairs not at a limit, the estimator's pitch per y count is 0.0333. That carries the same ~3 % scale
    error, so it is consistent with pitch = yaw.
  - Counts from leaving one pitch limit to reaching the other are **3,225–3,601 for nine sweeps from 1.6k to 13.8k
    counts/s, with no speed trend**. One 21k sweep reads 3,844, with a confounded start.
  - These are below 09-23's 4,624 by definition: motion onset at the limits blurs.
- **Conclusion:** no evidence that pitch depends on speed or differs from yaw. This take does not establish pitch.

## The take

- **Recorder:** check clean; 5,480 decoded = matched frames, 1 unwritten tail packet; the +21 ms anchor (residual 0.33 ms).
- **Media:** sha256 `ff6b1fa0…`, as registered.
- **Build:** 1.1.3892207/build25501035.
- **Settings:** unchanged, per your relay of James.
- **Input:** no movement key in the whole take. One left click at 4.52 s, during the slow turn, before its end frame; it
  does not touch either still frame.

## Bytes (`data/human/calibration/20260925T030045-211Z-7804-3/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `calibration.json` | 14,089 | `c84da2f9a132504d445f62061952ca676af754b913f772a5e46a5d54c0c09247` |
| `artifact-hashes.json` | 3,161 | `7e8bb3f2e3baf4861123a179b1be5453ca227909ca7b46e2403018b75d3649a4` |
| `analysis.json` | 9,621 | `fbd491fa327ec4003decb628514cde1c78be64ea0ea885eca56423c961363c05` |
| `pitch-runs.json` | 15,916 | `93c9833a1b26076c4eef0961acffe912774cb83954ace11864d610723df2a6d0` |
| `pairs.jsonl` | 3,549,703 | `2969e6cb4e0b15b35b32391f8c6604e1d75c91ac21ae28619d22aa2211ce275d` |
| `rest-features.npz` | 1,167,066 | `ed057c02214b0faf5d0b186e393b73185317a50dc233f31a345a28adacade8a7` |
| `estimate-meta.json` | 3,255 | `abc70a9f3fe136c6283de4f3ed4344eecd127e9438589dc8fdd7efa4046042b3` |
| `recorder-and-anchor.json` | 2,662 | `087c9d3632a03edc9b036d1c5cee13a15fab768c5a3862646b509a4457009610` |
| `strokes-20260925T030045-211Z-7804-3.json` | 5,830 | `e059aa7db59c4bea2ee1ee46575cd542cbf892c5b9420f2fa90c0ba6ce1ad895` |
| `registry.f36e9e3b5650.json` | 8,492 | `f36e9e3b565041cbd719d3d4c6b80033d66a685a599f3b6607e67bab3ee574fb` |
| `estimate.py` | 5,075 | `424ce2b3da8769d041945d5d79f6af3abf1504baed3d45fef25176311b81b986` |
| `analyze.py` | 8,380 | `f9ffecf8df89eb0511ae47f53c48273f3d3c43b0d7b09a4272c694a09e44b301` |
| `pitch.py` | 3,174 | `360ee91e08095acb2eddcd17b9464a249aafe0a46ae8ac8b4145d8ebed7d5daa` |
| `strokes.py` | 4,004 | `8b7464206bf35d80047660554501193d3d6e7ddb0ed8f8f5e0374f065a780b49` |
| `verify_recorder.py` | 1,891 | `0b9f709e01a0883a506429230c68328c31695f56041532ffddeb0568d701f225` |
| `make_calibration.py` | 8,420 | `b5f7510e4b51b8fefa3facb8707a74db2b9a270d55067f52d37070276b4b2283` |

- `estimate.py` ran once, from my scratchpad, on the same bytes.
- `analyze.py` and `pitch.py` were re-run in this folder, and their `analysis.json` is byte-identical to the scratch run's.

No commits, no Linear, nothing on the Mac.
