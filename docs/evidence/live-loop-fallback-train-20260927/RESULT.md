# Fallback native TRAIN replay: camera + FPS only

VUH-1384, live-fps for live-loop, 2026-09-27. **Do not book the fallback's
learned-versus-scripted block on this evidence. Recommend camera + FPS only.**
The fixed fallback produced **100% action-only neutral and 100% action plus raw
camera neutral** across all 3,600 selected native training frames. Every supported
held/press/release output and every raw median yaw/pitch request was zero.
This was not the earlier `cal=None` camera-zeroing artifact: this runner decodes
the raw median camera classes separately and self-feeds them unchanged.

The model's historical frozen-dev self-fed **press F1 0.0** and camera MAE
**1.224645 degrees** remain an explicit failure, as recorded in the
[fallback packet](../live-loop-fallback-20260927/RESULT.md). This new diagnostic
confirms collapse on a fixed real TRAIN window; it does not improve or supersede
the frozen-dev result, promote the model, or establish live behavior.

## Fixed source and execution

The lead named session `20260923T051828-422Z-33696-1`, and the sample was fixed
before predictions: rows `[7:3607]`, the first 3,600 rows of accepted normal-cooldown
TRAIN run `[7:12557]`. Duration is 119.9999988 seconds at the table's step length.
The existing `steps.load_denylist` and `steps.load` passed before original-media
access; the step table matched `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb`.
The original 6,892,293,372-byte MKV was stream-hashed before each decode and matched
`ad14e5bc0a1e0da23527a8f4a092e591ddf568ac925cfd0b2907e38dc94b9aaf`.
No sealed/validation/test media or other corpus source was opened.

Native PNGs at rows 7, 1807 and 3606 were inspected before inference: intact
practice-range gameplay/HUD, including combat, without menus or dialogs.
[Inspection receipt](inspection.json) pins the three images and fixed selection.
The three frames are a decoding sanity check, not a new admission judgment.

FFmpeg selected exact decoded `frame_index` ordinals through
`cache.select_expression`. Every streamed native **2560x1440 BGR** observation
passed showinfo sequence/PTS/timebase equality before entering the predictor.
First ordinal/PTS: **135 / 1146**, last: **14531 / 121113**, timebase **1/1000**.
The source was colour-checked and converted from TV-range BT.709 at native size;
the prepared compact-bgr predictor performed the checkpoint's normal view
preprocessing. There were no cached inputs, upscaled fixtures or native-frame array.

Checkpoint `2d5183cba12913a36327e0a459ec0c0b2a1238d26a7df98f7823929af3129f18`
used its original support/settings packet, normal cooldowns and unchanged `.5`
thresholds. CUDA was explicit, under the existing `PCGuard`, with game and OBS
absent, BelowNormal priority, two CPU threads, two FFmpeg threads and a 15-minute
per-command deadline. The inference/decode loop completed in **148.78 seconds**;
peak Python working set was **1,186,742,272 bytes**, below 3 GB. The decoder is a
separate bounded two-thread process; the existing RSS watchdog measures the Python
process. An existing compression process was left alone, so timings are diagnostic,
not isolated performance measurements. No live capture, input or game FPS test ran.

## Human comparison

All 3,600 human rows had known action/camera labels. Press steps and raw press
counts agree in this window: **451 all actions (3.7583/s)**, **437 supported
actions (3.6417/s)**. The model emitted **zero** presses, holds or releases in
every action, including all supported actions.

| Measure | Human | Model |
|---|---:|---:|
| Supported action-only neutral | 28.4167% | 100% |
| All-action-only neutral | 28.2222% | 100% |
| Supported action + raw-camera neutral | 9.9167% | 100% |
| All-action + raw-camera neutral | 9.9167% | 100% |
| Yaw absolute mean per step | 2.026661 degrees | 0 |
| Yaw absolute p95 per step | 9.197824 degrees | 0 |
| Yaw absolute total | 7295.981059 degrees | 0 |
| Pitch absolute mean per step | 0.863630 degrees | 0 |
| Pitch absolute p95 per step | 3.274306 degrees | 0 |
| Pitch absolute total | 3109.069495 degrees | 0 |

Action-neutral means no held or pressed semantic action; release-only output
does not count as an active control. Camera-neutral uses exact zero requested
degrees; the separately reported zero-class version agrees here.

| Action | Supported | Human presses | Human presses/s | Model presses/s |
|---|:---:|---:|---:|---:|
| move_forward | yes | 55 | 0.4583 | 0 |
| move_left | yes | 50 | 0.4167 | 0 |
| move_back | yes | 27 | 0.2250 | 0 |
| move_right | yes | 46 | 0.3833 | 0 |
| jump | yes | 106 | 0.8833 | 0 |
| web_swing | yes | 23 | 0.1917 | 0 |
| get_over_here | yes | 4 | 0.0333 | 0 |
| amazing_combo | yes | 19 | 0.1583 | 0 |
| ultimate | no | 0 | 0 | 0 |
| melee | no | 1 | 0.0083 | 0 |
| spider_power | yes | 36 | 0.3000 | 0 |
| web_cluster | yes | 71 | 0.5917 | 0 |
| team_up | no | 12 | 0.1000 | 0 |
| goh_targeting | no | 1 | 0.0083 | 0 |
| simple_swing | no | 0 | 0 | 0 |

Human yaw/pitch come from `steps.target` and the header's 0.0330738 degrees/count.
Yaw uses the slow-turn gain; linearity above that calibration speed remains a
caveat. **Pitch is derived from equal sensitivity, not independently measured.**
Actual pad rotation remains unknown until the accepted execution map exists.

The history convention is uninterrupted ideal 30-Hz self-feeding: initial prior
input `None`, recurrent state initially empty and then continuous, subsequent
prior input equal to the previous masked decoded held/press/release plus raw
requested camera classes. There is no teacher forcing, saturation, Cal, pad
state or claim that those requests executed. A neutral-gap-history second pass
was unnecessary: every emitted history after the initial step is already exactly
neutral. No thresholds or support masks were adjusted to obtain this verdict.

The maximum held-head probability anywhere was 0.364585; maximum release-head
probability was 0.259076. Even though a press-head probability reached 0.908472,
the unchanged hold/tap decoder could not emit a held action or a paired
press-and-release tap. This describes the observed decoding failure, not its
training cause. Camera probability medians independently remained the zero class.

## Verification and retained evidence

- 17 synthetic-only tests and repository Ruff checks pass in the specified private
  Python environment. Tests cover fixed source/denylist refusal, exact PTS/timebase,
  raw camera preservation, masks, true self-feeding, neutral/unknown denominators,
  process refusal, the startup timestamp correction and manifest scope.
- Post-run readback verified exactly rows 7..3606, all 3,600 per-step records, and
  the as-run source hash against the manifest. No inference was repeated for the
  final metadata-only correction.
- `run/report.json`: full measurements, including per-action hold counts,
  known denominators, raw press totals and prediction timing.
- `run/per-step.jsonl.gz`: all action/camera probabilities, decoded outputs,
  human targets/raw presses, FrameRefs and verified showinfo PTS/timebase.
- `run/selection.json` and `inspect/selection.json`: identical fixed contract;
  both SHA256 `f542bd117daa64a11b7cbed44a8703e122d27b0076f75b70854c0be03c32790a`.
- `inspect/`: three native PNGs, image hashes, original-media verification and
  FFmpeg graph/command/showinfo log. `run/` retains its corresponding media and
  decoding records plus successful job status. `run/replay-source.py` is the
  exact executed script, hash-matching `run/manifest.json`.
- [Manifest scope addendum](manifest-scope-addendum.json): the preserved original
  manifest inherited unused FPS boilerplate from `prepare()`. This addendum
  identifies those fields as non-measurements and states the actual decoded,
  self-fed replay scope. The delivered script fixes future manifest metadata;
  prediction/selection/metrics are unchanged.
- `startup-refusal.json`: the first inspect command stopped before media access
  because the status helper rejected a fractional start timestamp. The caller was
  corrected to the existing profiler's integer timestamp convention; no guard changed.

Full preprocessing/encoder/head prediction timing was p50 **23.070 ms**, p95
**26.979 ms**, p99 **29.342 ms** over 3,600 predictions. This excludes FFmpeg
delivery waits and is not desktop capture latency or live throughput.

Reproduction, using the fixed hardcoded source and new/empty attempt directories:

```powershell
$replayPython = 'C:/Users/volpe/AppData/Local/Temp/live-loop-cuda-env/Scripts/python.exe'
uv run --no-project --python $replayPython python -m pytest tests/test_replay_live_fallback_train.py -q
uv run --no-project --python $replayPython python scripts/replay_live_fallback_train.py inspect
# Inspect all three native PNGs and retain the matching inspection.json receipt.
uv run --no-project --python $replayPython python scripts/replay_live_fallback_train.py run --device cuda
```

The delivered evidence directories are immutable and cause reruns to refuse;
these commands document the run, not permission to overwrite it. The shared
`.venv` was untouched. Linear publication and the camera/FPS booking decision
remain with live-loop and the lead. No model improvement, policy acceptance,
execution-map acceptance or useful live policy behavior is claimed.
