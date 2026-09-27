# A2b plumbing recovery ? before evaluation

Lead pre-approved this recovery on 2026-09-27. Scientific contract remains A2, the six pinned epoch-26 checkpoints and original CUDA TRAIN cutoffs in `recovery-inputs.json`, the same MPS stack and frozen judge `6f2187dd`.

The first Mac A2 attempt completed both frozen-dev feature caches, then failed before any NLL or decode inference: the recovery wrapper supplied a pathlib checkpoint and the initial evaluation JSON could not serialize it. The original output, log, exit 1 and terminal receipt remain untouched. Fix: serialize the checkpoint path as a string; the evaluator regression exercises actual Path arguments.

`recovery-features-stage.json` pins all seven completed feature-stage files (1,621,597,886 bytes) after streaming SHA-256 verification. Each array agrees with its original extraction receipt and each session receipt agrees with the completed top-level manifest. Eligible frames: 4,630 and 19,926. The receipt also pins the original MPS environment, terminal failure and independent streaming verification of the original frozen-dev pixel caches. Receipt canonical LF SHA-256: `d051df52812522d8973fec3b1e9a2dac5f1a37371cfdfd9798d553b53f66b23e`.

A2b uses a fresh output/log (`mac-evaluation-a2b`) and authenticates this committed receipt and every cached file before reuse. No refit, re-extraction, recalibration or cloud compute. CPU threads remain 2 and the Mac launcher is niced. No evaluation metrics are read until all six evaluations exist; the pre-existing persistence stop still applies. The frozen judge is unchanged. Tests: 65 synthetic tests pass on PC; Ruff passes. No sealed data is accessed.
