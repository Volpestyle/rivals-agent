# Does the target's bearing predict James's next camera turn?

**EXPLORATORY.** 2026-09-26, research check for the range_bc camera head. The only compute was CPU decoding on the PC.
There was no training, no Mac or cloud job, no game input, no Linear write and no commit.

## TL;DR

**No. Where the target is predicts James's next camera turn only weakly. A target-bearing input would not fix the camera head.**

- **Yaw.** Over 1,454 train frames with a detected bot, the bearing of the bot nearest the crosshair correlates
  with James's summed yaw over the next 4 or 8 steps at **r = +0.13 (R² 0.017)**. The sign agrees **59%** of the time;
  shuffled bearings give 50%, with a 95th percentile of 52%. For turns above 1°, r = +0.15 and the sign agrees 60%.
- **Pitch.** r = +0.17 over the next 4 steps (R² 0.030), or +0.22 on turns above 1°. It fades to zero by 8 to 16 steps out.
- **The signal is real but small.** It beats the shuffled control by a wide margin, yet explains 2 to 5% of turn variance.
- **Almost nothing beyond the policy's history.** The previous step's camera motion is already a policy input, and alone it
  explains **R² 0.57** of the next-4-step yaw. Adding the bearing lifts that to 0.573. For pitch the lift is 0.635 to 0.639.
- **Strongest case: a still camera.** When the camera had not moved for 4 steps and the next turn exceeds 1°, the sign
  agrees 66% and r = +0.26 (n = 157). Even there R² is only 0.07.
- **The head is not starved of information.** A camera head that decodes to zero when teacher-forced is ignoring an input
  it already has, which predicts the next turn at R² 0.57. The next thing to check is the camera loss and decoding
  (zero is the modal class; see `../camera-targets/analysis.md`), not a new input.
- **The green finder is account-dependent.** Train session 035932 was played on James's main account, where enemies are
  the default red. The green finder found a target in 1% of its frames.

## Numbers

The target is the detection nearest the crosshair (screen centre). Bearing is `atan(offset / f)`, with
f = 465 × W / 1280 = 930 px at 2560 wide. The turn is the sum of the step labels (`mouse_d* × 0.0330738°`) over steps
[0, N) after the frame. Positive yaw is right; positive pitch is down, for both the bearing and the turn. The shuffled
control permutes bearings across samples 1,000 times; the shuffled columns give its mean and, in brackets, the 95th
percentile of |r| or of sign agreement.

The table covers the three green-enemy sessions: 1,800 sampled steps, 1,454 of them with a target.

| Axis | Horizon | Subset | n | r | R² | Slope (° turn per ° bearing) | Sign agrees | Shuffled r | Shuffled sign |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| yaw | next 4 | all found | 1454 | +0.133 | 0.018 | +0.099 | 0.586 | 0.000 (p95 0.051) | 0.498 (p95 0.521) |
| yaw | next 4 | turn > 1° | 983 | +0.158 | 0.025 | +0.142 | 0.607 | 0.000 (p95 0.063) | 0.498 (p95 0.524) |
| yaw | next 8 | all found | 1454 | +0.132 | 0.017 | +0.180 | 0.588 | 0.000 (p95 0.049) | 0.498 (p95 0.520) |
| yaw | next 8 | turn > 1° | 1175 | +0.148 | 0.022 | +0.225 | 0.602 | 0.000 (p95 0.057) | 0.498 (p95 0.522) |
| pitch | next 4 | all found | 1454 | +0.173 | 0.030 | +0.068 | 0.555 | 0.000 (p95 0.053) | 0.492 (p95 0.513) |
| pitch | next 4 | turn > 1° | 890 | +0.220 | 0.049 | +0.112 | 0.573 | 0.000 (p95 0.067) | 0.495 (p95 0.524) |
| pitch | next 8 | all found | 1454 | +0.170 | 0.029 | +0.121 | 0.542 | 0.000 (p95 0.050) | 0.493 (p95 0.514) |
| pitch | next 8 | turn > 1° | 1077 | +0.197 | 0.039 | +0.163 | 0.562 | 0.000 (p95 0.061) | 0.495 (p95 0.520) |

The next table asks how much the bearing adds to motion history. It fits ordinary least squares on the same 1,454 samples.

| Axis | Window | Previous step only | Previous step + bearing | Previous 4 steps only | Previous 4 steps + bearing | Bearing only |
|---|---|---:|---:|---:|---:|---:|
| yaw | next 4 | 0.571 | 0.573 | 0.393 | 0.398 | 0.018 |
| yaw | next 8 | 0.382 | 0.385 | 0.272 | 0.279 | 0.017 |
| pitch | next 4 | 0.635 | 0.639 | 0.432 | 0.439 | 0.030 |
| pitch | next 8 | 0.373 | 0.380 | 0.228 | 0.239 | 0.029 |

Other measurements:

- **Visibility.** 19.2% of sampled steps have no detected target: 17.2%, 20.3% and 20.2% in the three green-enemy sessions.
  Session 035932 has 99.0%. Turns are no smaller when no target is visible: the median |next-8 yaw| is 7.7° with no
  target and 5.5° with one.
- **Target size.** Box heights are p10 40, p50 110 and p90 265 native px. The policy's 144×256 global view shrinks them
  tenfold, to **4, 11 and 26 px**. A third (33%) of nearest targets are centred inside the native 256×256 crosshair crop
  that the policy also sees.
- **Bearing.** The median |yaw bearing| is 6.0°, with p25 at 2.3° and p75 at 17.2°.
- **Later windows.** Yaw r is +0.11 for steps [4, 12), +0.10 for [8, 16) and +0.09 for [12, 24). The pitch correlation is
  gone by [8, 16) (r = +0.07) and slightly negative by [12, 24). No reaction-delayed window beats the immediate one.
- **By bearing bin.** Bots 15-30° off-centre produce the clearest turns toward them: 66% (left) and 60% (right) of turns go toward the bot, with
  a median next-8 yaw of -5.0° (left) and +1.4° (right). Bots under 15° off-centre are close to a coin flip, at 55-60%.
- **The largest detection** as the target instead of the nearest is slightly worse: yaw r = +0.12 over the next 4 steps.
- **By session,** yaw r over the next 4 steps is +0.115, +0.087 and +0.200. All are positive; none is large.

The full output of `analyse.py`, including the tables by bearing bin, box size and window, is in
[analysis-output.md](analysis-output.md).

## What it implies for the policy's camera input

1. **A bearing feature is not the cheap, strong fix.** The measured ceiling is small, and it holds even with native-resolution
   detection that the policy cannot do itself. A linear readout of the nearest bot's bearing explains about 2% of yaw
   and about 3% of pitch over the next 4 steps, and about 0.2-0.7 points of R² beyond the history input. A richer
   target feature (every bot, a tracked target identity) might do better, but nothing here suggests a large effect.
   Test it offline against these samples before spending a fit on it.
2. **The "a few pixels" hypothesis is only partly true.** The median bot is about 11 px tall in the global view, not 2 to 3,
   and a third of them sit in the native-detail crosshair crop. The distant tenth (4 px or less) is the part that the
   global view does lose.
3. **Look at the zero decode itself.** Suppose "teacher-forced" means the history input carries the human's previous step,
   as `steps.prev_vector` does in training. Then the head has an input that explains 57% of next-4 yaw variance and still
   decodes to zero, which points at the loss, the class weighting or the decode rule. That is an inference from this
   regression, not something tested on a checkpoint: no checkpoint was opened, and the policy sees the previous camera
   step as one of 31 log-spaced classes rather than as degrees.
4. **Account colour matters for any feature built on `outline.find_enemies`.** Green enemies exist only on the account
   where Enemy Color = Green is set. On the main account (035932) the green path is blind. The red band on the outline
   path boxes the hero, the HUD and the KO banner (see [samples/main-account-035932-i1676.jpg](samples/main-account-035932-i1676.jpg));
   only the red-nameplate path is usable there.

## Limitations

- **Range play only,** in three sessions from three sittings, all on the alt account. Matches are untested.
- **Pinned focal length.** The 465 px at 1280 figure (about 108° horizontal FOV) was measured in L4's pad sessions
  (`docs/lanes/l4-controller.md`). The keyboard-and-mouse takes do not record FOV. Focal length rescales the bearing, so
  it changes the slopes and the "inside the crop" share, but not r, R² or sign agreement. The degree labels themselves are
  a slow-gain approximation, because mouse acceleration is on.
- **Sample size.** 1,454 found-target samples, each at least 0.5 s from the next. They still share sessions and nearby
  moments, so the shuffled p95 understates the true uncertainty somewhat. At this n, an r of 0.13 is robust; its size is
  known only to about ±0.05.
- **Detections are not true targets.** Every one of the 20 inspected nearest detections was a real enemy, including a
  distant humanoid bot in i11401 that was zoom-checked. But:
  - The nearest-to-crosshair bot is often not the one being fought. In i11401 the fight is with two bots lower right.
  - Recall is incomplete: visible bots went undetected in i40584 and i53707.
  - Close bots can split into fragments (three boxes on one Galacta in i7469).
  - Some boxes are a name plate alone (i24228, i15012).

  Median frames hold 2 detections. The bearing measured here is therefore a noisy stand-in for "where James is aiming";
  a true-target label could correlate better. The no-target share is the finder's recall, not true absence.
- **Samples come from one frame each.** Nothing here measures target motion, lead or which bot is tracked across frames.
- **Priority.** For the first ~75 of session 200129's samples, the probe process ran at Normal priority because the
  in-process priority call silently failed. It was set to Idle by hand, and the scripts were fixed before the other
  sessions ran. The game was not running at the time.

## Exact sessions and frames

- **Sessions.** All are registry split `train` (`data/human/session-splits.corpus.json`) and absent from
  `sealed-denylist.v2.json`. Their step files have `split: train` headers, which `probe.py` asserts. Videos are the paths
  the step rows name:

  | Session | Video | Step rows | Eligible anchors |
  |---|---|---:|---:|
  | 20260923T200129-346Z-33696-6 | `2026-09-23 15-01-29.mkv` | 48,195 | 47,896 |
  | 20260925T021320-371Z-7804-1 | `2026-09-24 21-13-20.mkv` | 65,702 | 62,091 |
  | 20260925T203745-207Z-49728-2 | `2026-09-25 15-37-45.mkv` | 85,861 | 82,714 |
  | 20260926T035932-508Z-63684-14 | `2026-09-25 22-59-32.mkv` | 55,017 | 54,214 |

  035932 is the main-account, red-enemy session. It appears in the visibility table only.
- **Not opened:** the frozen-dev sessions 171533 and 205528, the validation take 212646, and all gate2, test, sealed,
  held (032454, 033319), `idm_train` and calibration files.
- **Eligible anchors** are accepted suitability, normal regime, gap-free and camera-known, with the next 8 steps in the
  same run and equally usable.
- **Sampling.** 600 anchors per session, drawn with `random.Random(20260926)` at a minimum spacing of 15 steps.
- **Frame and label timing.** Each anchor's frame is the step row's `frame` (the last frame at or before the anchor), and
  that frame's pts was matched exactly on all 2,400 decodes. Turn windows start at the anchor's own step, so the frame
  precedes all of the motion being predicted.
- **Per-sample records.** Every sample is in `samples-<session>.jsonl`, with session, step `i`, `frame_index`, pts,
  every detection box, and the next-8 yaw and pitch. The 20 inspected overlays and `index.json` are in `samples/`.
  Left panel: the whole frame with the nearest detection in magenta and the others in yellow. Right panel: a native
  360-px crop.

## Reproduce

Run these on the PC from the repo root:

```
uv run --no-project --with av --with opencv-python-headless --with numpy python docs/research/target-bearing/probe.py <session_id> 600 20260926
uv run --no-project --with numpy python docs/research/target-bearing/analyse.py
uv run --no-project --with av --with opencv-python-headless --with numpy python docs/research/target-bearing/inspect_samples.py
```

The probe decodes with PyAV at idle priority on 2 threads, one decode at a time, and runs `perception.outline.find_enemies`
on the whole native frame. It took about 1.1-2.2 s per sample and peaked around 170 MB. Status was written to
`~/jobs/target-bearing-probe.status.json`, and the run log is `probe.log`.
