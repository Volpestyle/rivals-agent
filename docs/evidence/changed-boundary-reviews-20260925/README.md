# Changed-boundary reviews, 2026-09-25

Verbatim independent reviews of changes that decide what enters training or evaluation, with the hand-back each reviewed.

| Review | Hand-back | Change | Verdict | Landed |
|---|---|---|---|---|
| `review-beta-default.md` (fit-review, sha256 35983c1abcd9ad1e…) | `idm-beta-default.md` (scoreboard-fix, f46d24942ad1b625…) and the D1 doc fix `idm-beta-default-2.md` (46fd44f9171d8075…) | `policy/idm/train.py`: beta-NLL (beta 0.5) on both axes is the default camera loss, `--beta-nll 0` the plain loss; `tests/test_idm_model.py`; the lane doc's decision entry records the failed pitch calibration | land with one doc fix (D1, applied before landing); N1 breadth (A4 is one fold, one seed), N2 checkpoint provenance, N3 a future replay-label export must refuse or mark IDM pitch | `63f2d3b` |
| `review-idm-deploy-A.md` (fit-review, Codex gpt-6-astra, sha256 3e4d22894d853d86…) | `idm-deploy-A.md` (scoreboard-fix, a59d14a5fdf4d8b6…) | `policy/idm/train.py`: pitch fix A deployed in `_camera` (pitch std × k per bin of the stated yaw std before the 1 / 3 deg bound; constants pinned to `idm-beta-nll-20260925/pitch_fix3-params.json` 6f8dba7b; every prediction and the report's abstention carry `pitch_std_calibration`); `tests/test_idm_model.py`; the lane doc's Deployed paragraph | land; N1 the lane doc's exact-equality claim needs its same-platform qualifier, N2 name the report marker as `abstention.pitch_std_calibration.name` (both fix-forward) | this commit |
