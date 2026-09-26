# Why self-fed range BC rollouts are degenerate, 2026-09-25 (VUH-1346)

A read-only diagnosis (no training) of `range-bc-interim-20260925`'s seed-0 no-HUD and twin checkpoints on the same
dev. **A model property, not an evaluation bug:** the models learned to continue the previous action, not to start
one (teacher-forced hold continuation 93-96 %, hold-onset recall from idle 2.0 % no-HUD / 0.5 % twin, camera starts
from zero on 2 % of steps against the human 22 %). Self-fed, a known-idle history is an absorbing state: no hold
crosses 0.5 in 24,556 steps and the yaw median stays zero, so press-F1 is 0 and camera equals zero motion. With the
same weights, blanking the history gives the no-HUD arm press-F1 0.079. `probe` modes in `selffed/diag.py` reproduce
the report's teacher-forced and self-fed figures to four decimal places.

**It qualifies the interim reading.** The pre-registered teacher-forced press-F1 behind `range-bc-interim-20260925`'s
"Opens" counts lone press probabilities that `executor.decode_step` never executes, so that reading does not show an
executed press advantage. The interim folder stays as it landed; this folder records the qualification.

**Proposed for the real fit** (the lead's decision is recorded where the fit is pre-registered): frames-only and
self-conditioned-history (scheduled sampling) arms judged on pre-declared self-fed checks, and an executed-decode
teacher-forced press-F1 with `held_change_f1` as the headline metrics.

| File | sha256 |
|---|---|
| `fit-selffed-diag.md` | `6f44f05bbb61db528755f44c0f8da83f420e0bf55ebeb42a69b80f1a972e9722` |
| `brief-hud-review-selffed-diag.md` | `a14d11af6cc63b09f1de2dde9ee727c55619c3eace2c3da7c3a6521af895d04c` |
| `selffed/diag.py` | `f8c7bd9a77d5224c72fe74126dad7a04719cb87e2b69de6259245435dd941789` |
| `selffed/diag-model_nohud.json` | `465bfe87b16c680d217be13440e3c4ef6fc0e8ec29b2a20fa9d4fbabfd76211c` |
| `selffed/diag-history_only.json` | `b262f736bde4867acb66453d6461c531939be600e2a6819b93afed9ebb40ed2a` |
