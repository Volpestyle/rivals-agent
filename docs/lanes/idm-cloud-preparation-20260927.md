# IDM cloud preparation findings

Owner idm-owner, VUH-1353; EXPLORATORY, provisional pending independent review.

The press diagnostic landed in `b8aa599`; the isolated Modal adapter and copied guard landed in `7f403b3`. Three calibration/visual-ablation tests and three cap-reuse tests passed. The guard's four enforcement function ASTs match the original reviewed explore guard; only configuration values select $4, one arm and IDM-owned names. The upload contains 150 explicit files / 54.85 GB from the seven-session interim packet. Its first attempt failed with too many open files before compute launch; that log and exit are preserved. A retry of the same pinned packet uses an 8,192-descriptor process limit. Neither attempt provisions a GPU app.

## Accepted match -5

Built the target table from accepted receipt `e36283a5d14a4d1ad3a8b2a9bf814526c1b3f6d2a967fcd14ebcb228f8caaeb5`:

- `data/idm/cloud-20260927/match5-targets/20260927T052001-827Z-150600-5.idm.jsonl`
- SHA256 `cb522fba05f5984b99d4ac30c3e39768d2d301bf7b3987e12cc6964704a82c03`
- 31,706 target rows, 20,696 eligible 60 Hz intervals (5.75 minutes).
- Target-only decoder preflight validates receipt, steps/demo hashes and every referenced frame timestamp; 20,792 frames are planned. No video was decoded.

The preparation helper initially unpacked the builder's three return values into two names. The target had already been successfully written. The corrected helper loads and validates the existing target instead of rebuilding it; the reported hash is for those existing bytes.

Two missing integrations were exposed: decoder preparation did not pass the match-admission object, and the legacy policy step reader rejects `idm_train`. The IDM decoder now accepts the authenticated admission argument. The IDM-specific step adapter authenticates the original receipt, role, family, media and motor identity, then uses the existing human-table schema checks with a temporary header view for the old split enum. The returned session retains `idm_train`; source bytes and the policy loader are unchanged. Synthetic refusal/acceptance coverage and a real accepted -5 preparation check pass. No role is reassigned and no replay or pending identity is admitted.

`policy/idm/cloud_run.py` supplies a Linux L40S adapter using the same preflight/refit routines and a post-fit real/zero-visual press diagnostic. Optional preparation records Linux x86 decoding as a distinct backend. The generic decoder CLI remains Mac-only; there is no claim of bitwise Mac/Linux pixel equivalence.

## SSL implementation, no source run yet

`policy/idm/ssl.py` implements the memo's fixed-teacher predictive temporal model: 17 spatial cells, 384-to-192 projection, two causal four-head blocks, 768-wide feedforward layers, first eight frames predicting the next eight, ten fixed passes with warmup/cosine AdamW. The decoder is separate from the transferable encoder. No source discovery, admission or semantic labels live in this module.

`policy/idm/ssl_camera.py` provides matched generic/SSL camera branches. Its added 64-dimensional temporal input begins with zero camera weights, preserving base outputs at initialization. Synthetic checks cover causal masking through multiple blocks, no access to future feature values, stop-gradient fixed features, static copy-last zero error, timestamp refusal and initialization equivalence. These establish implementation properties, not SSL usefulness.

Whole-file metadata admission alone does not establish gameplay-only, cut-free intervals. Admission-codex owns finalized-source admission and -5 relocation. Native spot checks and exact window manifests must precede SSL extraction. All sealed, heldout and DayMR families remain excluded. No SSL loss, transfer result or Gate 2 claim exists from this preparation.
