"""End-to-end range behaviour cloning: frames and causal input history in, James's keys and mouse out.

Design: `docs/lanes/end-to-end-fit.md` (VUH-1359, VUH-1346). This package is the fit lane's own code:

    vocab      the fixed 12-control vocabulary and the 31-class foveated mouse bins          stdlib
    steps      the per-anchor step table contract (R2/R3): reader, runs, windows, targets    stdlib
    fixture    synthetic step tables and videos for tests                                   stdlib (+ ffmpeg)
    cache      the frame cache builder: exact ordinals, pts-checked, raw uint8 + manifest    stdlib + ffmpeg
    baselines  persistence, zero-motion and train-prior predictions                         stdlib
    metrics    held / edge / mouse / rate metrics per control                               stdlib
    gates      G1-G6 and the headline number                                               stdlib
    report     the fit report writer                                                        stdlib
    model      IMPALA encoders + LSTM + heads                                               torch
    train      data loader, loss, deterministic trainer, prediction, checkpoint             torch (+ numpy)
    bench      synthetic MPS determinism and throughput measurement                         torch

It sits under `policy/` beside `policy/execution.py`, whose `keyboard_mouse` domain, `key:<scan>:<flags>`
identities and test-split refusal it keeps. It is a subpackage, not more flat modules, because the fit lane
owns all of it and replaces execution.py's data path rather than extending it.
"""
