# Admission delta reviews, 2026-09-27

Independent fit-review reports copied byte-for-byte from its scratchpad. The
manifest pins each original path and raw SHA256. Admission-codex copied these
records; it did not author the review verdicts.

- `5c20c8d`: LAND, session-bound explicit PTS-anchor acceptance; F1 closed.
- `bd95447` / `b28d2e4`: LAND WITH FIXES, bounded intake plumbing; watchdog F1.
- `8593ef5`: LAND, watchdog F1 closed by Windows Job Object ownership. Real
  parent-exit 0 and 1 tests kill owned children and preserve an unrelated process.
  The later `169027a` assembly command extension is outside this review.
- `f641ef3`: LAND, four whole-file SSL sources. The exact accepted packet is
  [admission.json](../ssl-s65-admission-20260927/admission.json), SHA256
  `864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02`.
  This receipt resolves its frozen pending-review wording. World-feature SSL
  only, no semantic labels, admitted intervals or evaluation use. Native window
  inspection and a separate cut-free sampled-clip manifest remain idm-owner's.

Native parity and per-session admission remain separate evidence. In particular,
the old wrapper's null exit code for -6 is not retroactively an exit-0 success.
