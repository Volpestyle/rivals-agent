# Pitch deadband: pre-prediction freeze

Lead accepted a065c99 unchanged. EXPLORATORY, $0 Mac, no fitting. This packet is committed before calibration or unread-match inference.

Eight TRAIN ranges supply exactly 28,800 metadata-selected calibration rows; two frozen range-dev sources supply 49,080 complete rows for a single veto. Threshold selection is TRAIN-only from the ten accepted values. Identity/no qualifying threshold stops the experiment; failed dev veto stops it without retuning.

The unread match manifest contains 98,880 rows: -7 22,500; -8 15,840; -10 22,560; -11 15,960; -12 22,020. These are all remaining complete 60-row chunks after the accepted prior-block/context/one-second-embargo/store-sample exclusions. No match predictions are read unless TRAIN selection and range-dev veto pass. Roles and canonical admission are unchanged; this is not Gate 2.

Manifest SHA256: `81304ead59639e05a46b05f6508a9caf2916226dca3c90415e723915cea3571d`. `freeze.json` binds implementation, store/target hashes and per-source counts. Preparation checked all target hashes and current match admission. Forty synthetic tests pass, including exact yaw/unknown preservation, identity, threshold edges, source weighting/ties, veto/support refusals and unread context/embargo/sample exclusion. No raw footage was opened for selection.

Runtime uses the verified previous diagnostic source snapshot plus the new owner module; the fresh Mac folder is `/Users/james/dev/idm-data/pitch-deadband-20260928`. Stored pixels are hash-verified again before each inference. The output will include the full TRAIN predictions, all threshold scores and selected rule before any dev or match pass. Inference runs niced, MPS, two CPU threads, with warn-only status and durable exit. Owner releases the reserved Mac slot at collection. No refit is authorized by this packet.
