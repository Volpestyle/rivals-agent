# Access audit delta v2

**Provisional, unadmitted development evidence. Not executed on data; awaiting LAND.**

Delta to the immutable [v1 packet](../idm-paired-camera-access-20260929/README.md) and its [FIX review](../idm-paired-camera-access-20260929/review-v1.md):

- D1: use `human_intake.load_denylist(deny, sha256_pin=DENY)` for one authenticated LF-normalized read and schema/row validation.
- D2: normalize both compared paths with the same slash and case transformation. Synthetic tests separately refuse session ID, session group, media hash, forward-slash path and Windows backslash path matches; an unrelated source remains allowed.
- N1: explicitly use UTF-8 for all text ledger reads and audit output.
- N2: ledger hashes are **trust-on-first-use** at the first reviewed audit access. They are not pre-existing independent pins. The later mapping/inference packet must freeze and enforce these recorded hashes before execution.

Only synthetic refusal/loader tests run before review. They use fake rows and mocked bytes, never the real denylist, media or ledger. The v1 source, manifest and review receipt remain unchanged. Scope, hardcoded sources, exclusive D: output, and prohibition on decoder/inference/admission/labels are inherited from v1. The additional imported loader source is included in this delta's manifest.

This packet releases nothing by itself. Await the same independent reviewer's delta verdict and the lead's LAND before data execution. Later mapping/inference still requires its own frozen review packet.
