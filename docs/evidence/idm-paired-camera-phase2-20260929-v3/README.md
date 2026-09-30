# Phase-two delta v3: preserve malformed review, use corrected successor

**Provisional, unadmitted development evidence. Await delta review before scoring.**

Preparation under frozen v2 succeeded once, yielding 4,199 frames in each span. Owner context inspection finished and the pinned `review.json` was written. Its PowerShell-generated interval list incorrectly flattened to `[120,155]` instead of `[[120,155]]`. The v2 score invocation refused at `check_review` before stores were opened, before checkpoint/model loading and before any inference. No agreement output exists. This was an owner serialization error, not a new scientific exclusion or a model result.

The original malformed review (sha256 `f6ae7929acaca4f05576bdc0d4f07bcb49a64c0832a8d3b20d53cf34907f0d5d`) remains immutable. A corrected `review-v2.json` was created exclusively on D:, with the same inspection evidence and eligibility, correct nesting and an explicit pointer to its predecessor. No prepared store or reviewed context is changed or re-decoded.

**Only executable delta:** the scorer's single permitted review filename changes from `review.json` to `review-v2.json` under the same fixed OUT directory. All access pins, gates, predictor source/masks/checkpoint, mapping, intervals, sensitivity and agreement-only outputs reuse v2. No arbitrary review path is admitted. The original ten synthetic tests still apply; a supplemental test reproduces the malformed list refusal and accepts its corrected nesting without data access.

Do not run preparation again. After the same boundary reviewer clears this one-line delta and the lead releases it, invoke only the scorer once with the corrected review's explicit hash. Previous score gate failure performed zero model inference. All prior packets and reviews remain immutable.
