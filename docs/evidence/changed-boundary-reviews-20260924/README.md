# Changed-boundary reviews, 2026-09-24

Verbatim independent reviews of changes that decide what enters training, with the hand-back each reviewed.

| Review | Hand-back | Change | Verdict | Landed |
|---|---|---|---|---|
| `review-window-loss.md` (fit-review, sha256 2ba3593be76cc8c5…) | `fit-window-loss.md` (hud-review, 292fd479549ddd5c…) | the replay window-level loss in `policy/range_bc` (W1-W3), the `predict_*` KeyError fix | land | the commit that adds this folder |
| `review-idm-eval.md` (fit-review, sha256 6853c09234357e26…) | `idm-eval-fix.md` (scoreboard-fix, 2a97631732a5f099…) | `policy/idm_eval.py` edge metrics count every known onset; onset error beside rates; per-action AUC | land (minor M1-M3: rate denominators, onset-error split, AUC over answered rows) | the commit that adds these two files |
