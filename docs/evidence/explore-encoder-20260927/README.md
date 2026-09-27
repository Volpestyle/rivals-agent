# Encoder exploration, 2026-09-27 (VUH-1346)

Two completed, single-seed EXPLORATORY pairs: frozen SigLIP stock versus NitroGen
with original action history, then the same pair with explicit previous-action
input removed. Detailed results and limitations are in docs/lanes/explore-policy.md.

- history-enabled/: summary, per-arm final/collector receipts, independent terminal
  inventory, and full-packet manifest. Cost $4.21581554.
- history-disabled/: same evidence for no-history. Cost $4.20082846. All12 decode
  reports complete, no persistence stop and no skipped decodes.
- launch-fixes/: new next-launch copies implementing review F1-F3 (19d0060).

No-history NitroGen TRAIN-calibrated press F1 .308382 at .9190x human press rate
is the candidate for a separate pre-registered confirm comparison. Median camera
mean1.185917 improves over zero1.224645, but only pitch improves: yaw still loses
to zero. History-privileged persistence/AR2 use true human actions. Gap closure
with history removed is by construction and is not evidence of improvement.

Large checkpoints and full evaluations remain under the respective Mac roots
/Users/james/dev/range-bc-data/explore/{encoder-20260927,encoder-historyoff-20260927}.
Each root has result-packet.zip and per-arm collected/; hashes are in these receipts.
These receipt copies are frozen evidence. Do not edit them or the completed runs.
The lane note remains a working record and is not hash-pinned by this folder.
