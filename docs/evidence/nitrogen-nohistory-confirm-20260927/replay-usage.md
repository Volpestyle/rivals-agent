# Parameterised offline comparison renderer

`policy/range_bc/offline_replay.py` takes `--spec PATH --out NEW_DIRECTORY`. The JSON spec selects an admitted clip, a hash-pinned interval receipt and one to three labelled H1-format checkpoints with their original TRAIN calibration receipts. The current spec compares James/H1/NitroGen seed 1 on the interval pinned before inference. Both model outputs are self-fed, with a 32-step warm-up; model actions never alter the recorded frames.

On the niced Mac, from the pinned source directory:

```sh
nice -n 10 /Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/mac-eval-venv/bin/python -m policy.range_bc.offline_replay --spec /Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/replay-spec.json --out /Users/james/dev/range-bc-data/explore/nitrogen-nohistory-confirm-20260927/offline-replay-parameterized
```

For another authorized comparison, create a new spec and interval receipt: choose `clip`; interval `warmup_start_row`, `display_start_row`, `display_stop_row_exclusive`, `frames`, `step_ns` and steps hash; then set each model's checkpoint/calibration paths, hashes, epoch, label and kind (`chunk` or frozen-feature `encoder`). Encoder entries name a completed feature-stage receipt with its hash and input-cohort hash. The renderer reuses and verifies features; it does not extract or train. The existing admitted-roster loader and sealed denylist remain binding. One continuous eligible run must contain the full interval and warm-up.

`device`, `fps`, `ffmpeg` and `ffprobe` are parameters. The optional judgement field pins provenance and its expected decision; it is not a new judge. Outputs: MP4, three sampled PNGs, row-pinned predictions and fixed/ TRAIN-cutoff clip metrics, ffprobe verification and hashes. The video always says **offline predictions / recorded frames, not model gameplay**. Views are the 256x144 RGB policy input enlarged, identical in all panels. Amber press flashes last five display frames only for readability; scores use the original one-frame events.

This is an offline diagnostic for existing exploratory H1 checkpoint formats, not a live adapter. The earlier unlaunched `offline_replay.py` evidence copy is retained; this parameterised module/spec supersedes it for rendering.
