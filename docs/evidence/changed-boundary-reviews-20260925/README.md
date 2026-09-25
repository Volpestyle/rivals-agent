# Changed-boundary reviews, 2026-09-25

Verbatim independent reviews of changes that decide what enters training or evaluation, with the hand-back each reviewed.

| Review | Hand-back | Change | Verdict | Landed |
|---|---|---|---|---|
| `review-beta-default.md` (fit-review, sha256 35983c1abcd9ad1e…) | `idm-beta-default.md` (scoreboard-fix, f46d24942ad1b625…) and the D1 doc fix `idm-beta-default-2.md` (46fd44f9171d8075…) | `policy/idm/train.py`: beta-NLL (beta 0.5) on both axes is the default camera loss, `--beta-nll 0` the plain loss; `tests/test_idm_model.py`; the lane doc's decision entry records the failed pitch calibration | land with one doc fix (D1, applied before landing); N1 breadth (A4 is one fold, one seed), N2 checkpoint provenance, N3 a future replay-label export must refuse or mark IDM pitch | `63f2d3b` |
