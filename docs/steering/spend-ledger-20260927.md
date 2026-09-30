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
| IDM full03, expanded refit (3 epochs, per-epoch checkpoints, guard v2) | ≈ $21.9 (metered delta) | Camera and press both improve on the pinned baseline (yaw MAE .2835 → .2488, pitch .2554 → .2359; Combo/Jump/Web precision .491/.421/.492); persistence is still better on camera; not Gate 2 | `docs/evidence/` full03 report (landing) |
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
| IDM full02, killed at 55% by our own guard | $7.65 | v1.0.5 treated one 10 s `modal billing` timeout as fatal and tore down a healthy ~10 h fit (02:08 CDT 09-28); no checkpoint existed | Guard v2 (`ead3e6d`): no custom budget code, native timeouts only, apps detached; IDM checkpoints every epoch (`05a61b4`); `rivals-compute` skill |

## Rules this ledger suggests

1. **Probe before a long run.** A $1 timing probe with per-phase times (startup, staging, hashing, training rate)
   prices the full run before launch. The IDM lane adopted it tonight.
2. **Stage data on the GPU machine's local disk, never read training frames at random from a network Volume.**
3. **A lesson goes into the toolkit or the skill for that moment the same day.** Lane notes are history.
4. **Cost comes from Modal's bill, per run, and lands in this table** when the run ends.

## Manual bill checks (the lead's process from 2026-09-28; no code queries billing)

| Time (CDT) | Metered month-to-date | Billed after credits | Next launch and its estimate | Projected total | Under $150? |
|---|---:|---:|---|---:|---|
| 09-28 02:35 | $78.24 | $48.04 | v2 shakedown, two L40S apps, $0.48 all-in (frozen estimate, 0.10 overhead included); then IDM full03 ~$26.29 | ~$105.01 | Yes |
| 09-28 02:51 | $78.33 | $48.13 | After the v2 shakedown PASS (two L40S apps; metered +$0.09 so far against the $0.48 estimate; Modal's meter can lag). Next: IDM full03, ~$26.29 | ~$104.62 | Yes |
| 09-28 10:34 | $101.89 | $70.40 | After IDM full03 finished (stopped 15:30:57Z). Since 02:51, Ephemeral Apps rose $22.27 (full03 ≈ $21.9 plus the shakedown's lagged remainder) and Volumes $1.29 (storage for the retained 114 GB IDM input and ~70 finished-run output volumes). Nothing else is launched | $101.89 | Yes |

`modal billing report` covers only complete days; use `modal billing summary` for the metered figure that includes today.

## 2026-09-30 expert footage CPU screening

| Experiment | Cost | Answer | Lesson lives in |
|---|---:|---|---|
| Public expert VOD acquisition and CPU HUD screening, first 20-hour delivery | $12.7473 reported app usage | Delivered 21.7285 gameplay hours / 3,450 admitted spans from 13 videos and four creators. Generic portrait geometry missed Simii; privately inspected native profiles restored useful recall. Known bad spans and a failed killcam source stay withheld | `docs/lanes/expert-footage.md`; `D:/rivals-expert-footage/README.md` |

The `rivals` profile / `volpestyle` workspace billing report was queried after
all eleven footage apps stopped, using `modal billing report --for today
--resolution h --json`; it includes the failed probes and retried/preempted
cohorts, not just successful calls. Its source is
`D:/rivals-expert-footage/metrics/billing-20260930.json`. CPU only, no persistent
volume; every function had a native timeout. The earlier $14.53 configured
resource ceiling was an estimate for seven then-visible apps, not actual spend.
The hourly billing command supports today's completed intervals; this supersedes
the older complete-days-only description above for that command. Billing can
lag, so later corrections belong in this dated section.

## 2026-09-30 expert footage expansion toward 50 hours

| Experiment | Cost | Answer | Lesson lives in |
|---|---:|---|---|
| Public expert CPU screening, 35-hour milestone of the expansion session | $11.5431 reported so far, additional to the first delivery | 35.7703 admitted hours / 6,378 spans / 28 videos / eight creators, versus 21.7285 hours / four creators. Each landed source batch was sent to IDM; expansion continues toward 50 hours | `docs/lanes/expert-footage.md`; `D:/rivals-expert-footage/README.md` |

This is the expansion session's app usage returned by the `rivals` profile /
`volpestyle` workspace hourly billing report at the 35-hour milestone, including
failed and retried scans. The eleven earlier-delivery app IDs are excluded to
avoid counting their $12.7473 twice. Source:
`D:/rivals-expert-footage/metrics/billing-at-35h.json`; the full workspace response
is `metrics/billing-50h-session.json` in that same external root. This is an
interim figure while additional CPU scans run, not a final bill. Every function
has timeout=7200; public download/reference/decode subprocesses also have
explicit timeouts. Ephemeral CPU apps, no GPU or persistent volume. Completed
cohorts stop automatically; the final entry will record remaining usage and
verified teardown. No other lane's apps are stopped.


Final session update after the last scan stopped (2026-09-30 09:40 CDT):

| Experiment | Cost | Answer | Lesson lives in |
|---|---:|---|---|
| Expert footage expansion, completed 50-hour delivery | $13.87555519 reported expansion usage | Crossed the target at 50.8507 hours; completed already-running final source reaches 53.2943 admitted hours / 9,350 spans / 40 videos / eight KBM creators. Each batch sent to IDM | `docs/lanes/expert-footage.md`; `D:/rivals-expert-footage/README.md` |

This final reported session total **replaces**, rather than adds to, the
$11.5431 interim figure above. The first delivery's $12.74728305 remains
separate; combined reported footage usage is $26.62283824. Filtered source:
`D:/rivals-expert-footage/metrics/billing-at-50h.json`, queried after teardown;
the hourly report can lag. It includes all twelve expansion app IDs, failed
scans and withheld sources, excluding the eleven first-delivery IDs and every
other lane's app. `metrics/modal-apps-at-50h.json` verifies all twelve expansion
apps stopped with zero tasks. All were ephemeral CPU jobs with timeout=7200,
no GPU or persistent volume; local download processes also completed. No
other lane's resources were stopped.

## 2026-09-30 whole-day Modal snapshot (lead, 13:25 CDT)

`modal billing report --for "this month"` (profile `rivals`): **$261.09 month to date**, of which **$164.81 on 2026-09-30**
(09-27 $47.30, 09-28 $48.98). By resource: H100 $95.74, L40S $72.79, CPU $53.45, memory $35.64, L4 $3.33.
Biggest apps today: policy bc2 grids $53.02, world model v2 $42.70 (+ full-01 $5.66), expert footage CPU $26.62,
IDM v2 fits $25.54 (+ labelling $5.56), offline AWR $4.24. James hit his Modal GPU limit at about 13:00 CDT; new
Modal GPU launches are paused pending his decision. Defaults from now on: 1 seed for exploration, 3 seeds only to adopt a
bundle, PC 4080 or Mac first, and no world-model training without a stated cost and a result that justifies it.
