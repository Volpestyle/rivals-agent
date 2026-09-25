### Confirmation of pitch fix A on fresh held-out sessions (pre-registered 2026-09-25)

Pre-registered before any prediction on these sessions is looked at, under the lead's brief `brief-idm-pitch-confirm`.
Round 3's arm A passed on the judge sets it was developed on. The lead keeps the Gate 2 precondition (fast-band replay
pitch labels) open until A's **frozen** parameters pass on sessions no round has touched. **This is not a gate result.
It decides that precondition.**

**The sessions:** the three newly admitted takes (landed in `5d2ec29`), all split `train`, build `1.1.3892207`, the
same settings hash and gain as the older sessions:
- 232304 (8.77 min);
- 021320 (34.52 min);
- 025230 (3.66 min).

No IDM round, fit or checkpoint has used them.

**The frozen parameters (round 3, arm A, `pitch_fix3-params.json`; nothing is refitted, there is no arm B):**
- **Yaw-std bin edges:** 0.06059320594627363 / 0.10755754546016058 / 0.16996028513718056 / 0.351656956463779.
- **k = 1, 1, 1, 1.6005068343947064, 1.242973089376128.**
- **Applied as registered in round 3:** s′ = k_{bin(stated yaw std)} · s, a value on an edge goes up, and pitch is
  answered iff s′ ≤ its predicted regime's bound (1° / 3°). Yaw is only read.

**The checkpoints: all seven existing β-NLL checkpoints, no training.**
- T, T1, T2 (fold 051828);
- `a1-beta-s0/s1/s2` (fold 205528);
- `a4-beta` (the dev fold, whose predictions on 171533 A was fitted on).

None of them trained on these sessions: each trained on three of the four older ones. Using all seven spans both
folds, all three seeds and A's own source checkpoint. So a pass does not hinge on one checkpoint, and a failure on any
kind shows in the per-checkpoint figures.

**Data:**
- target files for the three sessions from the landed `rivals-idm-targets-v1` builder;
- frame stores from the landed decoder (media checked against `expected_media_sha256` first, niced beside hud-review's
  queue only if its per-step time degrades by no more than about 20 %);
- per-row predictions from each checkpoint on each session (21 inference passes).

**The like-for-like guard:** before scoring, the three new target files and the four training sessions must form one
cohort under the landed `idm_targets.check_cohort` (kit version under the pinned patch-equivalence file, settings,
bindings, swing mode, accel, step and frame period, calibration). If they do not, the confirmation is **refused**, not
scored, and the reason is reported.

**Judge: all of these must hold.**
1. **Coverage:** pooled over the three sessions and the seven checkpoints, per **true** gain regime band, over answered
   pitch rows under s′. Within 1σ′ ≥ **0.70** and within 2σ′ ≥ **0.90**, in **both bands**.
2. **The 1° / 3° bounds hold on every checkpoint:** pooled over the three sessions, per true regime, ≥ **90 %** of
   answered pitch rows have |error| ≤ the bound of their predicted regime.
3. **Yaw untouched,** row for row, on every checkpoint and session.

**Reported beside, not judged:**
- the same coverage before A (k = 1);
- per session, per checkpoint and per session × checkpoint coverage;
- pitch abstention per band before and after (the cost);
- yaw agreement on moving rows, as a check that the checkpoints transfer to the new build and sessions.

**The support floor:** a session whose true band has fewer than **500** evaluable pitch rows (distinct rows, before the
seven checkpoints multiply them) has that band's per-session figure reported as "under the floor" and not
interpreted. It stays in the pooled judge.

**Reading:**
- **Pass:** A is confirmed, and the Gate 2 precondition for fast-band replay pitch labels closes. The deployment change
  (A in `policy.idm.train._camera`) is written for review.
- **Fail:** A is not the fix. The pitch item needs a new direction, with these three sessions available as a second
  fold family. The failing component is named.

