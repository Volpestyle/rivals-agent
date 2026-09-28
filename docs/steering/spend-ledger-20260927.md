# What the weekend's GPU money bought (2026-09-26/27)

Steering keeps this file. Costs are Modal's own billing report (`modal billing report --for "this month"`), grouped by
app name, as of 22:15 CDT on 09-27: **$66.13 of apps** ($68.35 metered with storage; $38.15 billed after $30 of
credits). Each paid run gets one line: what it cost, what it taught, and where the lesson now lives so no one pays
for it twice. A lesson that lives only in a lane note hasn't been learned by the swarm.

## Science: what each experiment answered

| Experiment | Cost | Answer | Lesson lives in |
|---|---:|---|---|
| Chunk sweep, H=1/4/8 | $23.39 | NEGATIVE: longer action chunks don't fix self-fed collapse; the heads copy their own history and ignore vision | `docs/lanes/explore-policy.md`; charter portfolio |
| Pretrained encoders, SigLIP vs NitroGen | $2.69 | The policy starts using the picture, but still collapses self-fed | explore-policy lane note |
| No-history encoders | $2.66 | The breakthrough: press F1 0.10 to 0.37 | explore-policy lane note; VUH-1346 |
| NitroGen no-history confirm, 6 fits | $7.55 | CONFIRMED over 3 seeds: F1 0.30 against 0.004 for the control; yaw still worse than zero | `docs/evidence/nitrogen-nohistory-confirm-20260927/`; VUH-1346 |
| Yaw 4x4 spatial readout | $2.57 | NEGATIVE and overfitting (train loss down, dev up); next is regularization or a smaller head | `docs/evidence/nitrogen-spatial-yaw-20260927/` |
| Yaw 4x4 with dropout p=0.5 | about $2.4 | NEGATIVE: narrows the gap to the no-dropout control (1.886 against 1.908) but stays worse than the frozen base (1.773) and zero (1.735); the yaw-residual line is closed | `docs/evidence/nitrogen-spatial-yaw-20260927/`, 4d4da44 |
| IDM press diagnostics | $2.98 | Train-calibrated thresholds lift button precision (Combo 16% to 42%, F1 0.48 against 0.01 chance) | `docs/lanes/idm-press-diagnostic-results-20260927.md` |
| IDM SSL smoke | $0.19 | Pipeline works; no science yet | IDM lane notes |
| Round 3 (DINOv2 confirm), 36 apps | $6.04 | No model answer; parked after 18 h of launch failures | steering log; compute.md shakedown rule |

About $45 bought clear answers. Two negatives (chunks, 4x4 yaw) were cheap ways to rule out ideas, which is what
exploration is for.

## Operations: money that bought nothing, and the fix

| Waste | Cost | Cause | Fix, and where it lives |
|---|---:|---|---|
| Yaw 8x8 fits: stride bug, then the false spend stop | $11.18 | A bug in the first launch; then the new toolkit's over-count stopped all runs at 22:00 | Over-count fix v1.0.5 in `cloud/modal_guard`; the Modal limit is now $200 |
| IDM expanded refit, killed at 6% | $3.04 | Random frame reads from a Modal network Volume, plus hashing every store before training; and the same false stop | **Not yet shared:** the yaw lane learned "stage to local disk" at 20:48, and the IDM lane repeated the mistake at 22:00. Belongs in `cloud/modal_guard` (stage to local disk by default) and the `modal` skill |
| Round 3 launch churn | part of $6.04, and about 18 h | A new launch layer failing one piece at a time | `docs/compute.md` shakedown rule (3b4cfad); the shared toolkit |
| Conservative holds booked as spend | $0 (but blocked work) | Reservations counted as spend; round 3's ledger showed about $40 against $6 actual | Use `modal billing report` actuals (charter improvements tracker) |

## Rules this ledger suggests

1. **Probe before a long run.** A $1 timing probe with per-phase times (startup, staging, hashing, training rate)
   prices the full run before launch. The IDM lane adopted it tonight.
2. **Stage data on the GPU machine's local disk, never read training frames at random from a network Volume.**
3. **A lesson goes into the toolkit or the skill for that moment the same day.** Lane notes are history.
4. **Cost comes from Modal's bill, per run, and lands in this table** when the run ends.
