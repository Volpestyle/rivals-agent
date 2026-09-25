# Changed-boundary reviews, 2026-09-24

Verbatim independent reviews of changes that decide what enters training, with the hand-back each reviewed.

| Review | Hand-back | Change | Verdict | Landed |
|---|---|---|---|---|
| `review-window-loss.md` (fit-review, sha256 2ba3593be76cc8c5…) | `fit-window-loss.md` (hud-review, 292fd479549ddd5c…) | the replay window-level loss in `policy/range_bc` (W1-W3), the `predict_*` KeyError fix | land | the commit that adds this folder |
| `review-idm-eval.md` (fit-review, sha256 6853c09234357e26…) | `idm-eval-fix.md` (scoreboard-fix, 2a97631732a5f099…) | `policy/idm_eval.py` edge metrics count every known onset; onset error beside rates; per-action AUC | land (minor M1-M3: rate denominators, onset-error split, AUC over answered rows) | the commit that adds these two files |
| (follow-up of `review-window-loss.md` note N4, no separate review) | `fit-window-counts.md` (hud-review, 0c9f2b2e596a58b2…) | per-action window counts in every replay eval block; human byte-identity rerun unchanged | landed by the lead after its own test runs | the commit that adds this file |
| `review-beta-nll.md` (fit-review, sha256 6f64a63301955728…) | `idm-yaw-test.md` and `idm-yaw-test-2.md` in `idm-plumbing-20260924/` | `policy/idm/train.py` beta-NLL camera loss behind `--beta-nll`, default off (branch `idm/yaw-test-20260924` @ `4e7f005`, cherry-picked) | land behind the flag; default-on needs the gate re-run, seeds on a second fold, a pitch non-inferiority margin, a per-regime calibration check | the commit after the cherry-pick |
| `review-patch-equivalence.md` (fit-review, sha256 e6b5efdf18d07ec5…) | `fit-patch-equivalence.md`, `idm-patch-equivalence.md`, `intake-patch.md` (design: `patch-equivalence-design.md`) | cohorts keyed by kit version through the pinned `data/human/patch-equivalence.json`; the IDM applies the same rule; the intake records the real Steam build | land, on two conditions met in the landing commit (file force-added; fit and IDM together); minor M1-M4 for follow-up | the commit that adds these files |
