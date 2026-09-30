# Runs ledger

**This file is the one home for per-run results:** what each run cost, what it showed, whether it met the keep
criterion stated before it ran, and its best visual. The training lab board (`scripts/job_board.py`), Linear
project updates and any blog post all draw from here. Detail stays in the run's own record (evidence README, lane
note, `SITTING.md`); a row gives the one-line result and points to it.

**Add a row when a run finishes, paid or free.** Paid runs state their keep criterion before launch
(`docs/compute.md`); the row records whether it was met. Keep the column order: the board parses this table.
Billing snapshots, and the lessons about wasted money, stay in `docs/steering/spend-ledger-20260927.md`.

- **Cost:** Modal actuals from `modal billing report` where available, otherwise the owner's metered estimate,
  marked `~`.
- **Keep?:** `Yes`, `No` or `Pending`, then the reason.
- **Visual:** a stable Linear asset URL (no signature query) or a repo/local path. Third-party (expert VOD) frames
  never go on Linear or the blog; the private board may show them.

| # | Date | Run | Where | Cost | Result (one line) | Keep? | Visual |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-30 | IDM v0 demo (full03 unchanged, held-out match -11) | local | $0 | Moving-yaw MAE 0.63 vs 2.12 zero-motion; press F1 0.44–0.56; pitch weak; holds not predicted | Yes, as the baseline | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/43d872ca-342a-48b1-9de1-c145cf4f3636/8e71784d-f13d-435a-8f64-bb3a457a24af |
| 2 | 2026-09-30 | IDM VOD-domain test (full03 on 1080p60 7 Mbps and 720p60 re-encodes of -11/-12) | Mac | $0 | Compression costs only ~3% yaw and 1–3% pitch, so streamer VODs are a viable labelling target | Yes (decision) | table on VUH-1353; D:/rivals-agent-evidence/idm-vod-domain-20260930/vod-scores.json |
| 3 | 2026-09-30 | IDM v2-a fit (H100, 34 min) | Modal | ~$3 | Beats full03: moving yaw −17–19%, pitch −22–26%, press F1 up to 0.85, new held-key head | Yes (labeller for batch 1) | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/d1993056-2e60-4019-b1bd-ec53d446c3d2/58888406-af0f-4ed5-be24-a75059415c8c |
| 4 | 2026-09-30 | IDM v2-b, v2-c, v2-d fits (H100) | Modal | ~$22 (app `rivals-idm-v2` $25.54 incl. v2-a and the input volume) | The v2-c+v2-d ensemble ("v2-cd") is the best labeller: yaw −22/−23%, pitch −32/−29% vs full03; swing-hold F1 0.88 | Yes (v2-cd labeller) | numbers on VUH-1353 |
| 5 | 2026-09-30 | IDM zoom/camera-scale fit (H100, 17 min) plus per-creator check | Modal | ~$1 | All 8 creators read at James's FOV (0.993–1.000), so camera_scale = 1.0 | Yes | lane note table |
| 6 | 2026-09-30 | IDM labelling of the expert corpus (v2-a, then v2-cd) | PC + Modal L4 | ~$5.56 (app `rivals-idm-label`) | v2-a on ~27 h; v2-cd on 24+/40 videos, the rest resumes on the PC at $0 | Yes | private board `/idm-labelling` (third-party frames) |
| 7 | 2026-09-30 | Expert footage corpus (Modal CPU screening; PC downloads) | Modal + PC | $26.62 ($12.75 + $13.88) | 53.3 h of verified Spider-Man gameplay, 9,350 spans, 40 videos, 8 keyboard/mouse creators, from 218 h downloaded | Yes (VUH-1466 Done) | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/423db99f-894e-44f3-8eeb-373b3283d62b/de307089-7878-40a4-a57a-967672a1a809 |
| 8 | 2026-09-30 | Policy v0 packaging (existing NitroGen no-history checkpoint, live API) | local | $0 | p95 31 ms; buttons OK (web_swing F1 0.83); yaw at chance (47%) | No for live (baseline only) | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/78348cae-965a-487a-8e03-9c5edf2004f5/3660ff70-c5cc-42ad-990b-6f35a681d9b1 |
| 9 | 2026-09-30 | Policy bc2 yaw fit (ego-motion input; H100) | Modal | part of $53.02 (app `rivals-policy-bc2-20260930`, all policy grids) | Val yaw 0.825 vs zero 1.831; moving sign 89%; onset only 53% under median decode | Yes (base) | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/bdd1d79d-7b60-4d8b-b142-dccad196341c/1ce4c88b-2889-4b47-80aa-9ed5170f1b22 |
| 10 | 2026-09-30 | Mean-decode fix plus frame-interval input (bc2-dt) | Modal | in $53.02 | Onset sign 49–54% → 75–77% with no retrain; moving sign 93.5% | Yes | — |
| 11 | 2026-09-30 | Architecture grid H (LSTM 1024/1536, 2 layers) | Modal | in $53.02 | 2-layer 1536: val yaw 0.779, onset 79%, F1 0.295 | Yes (base for the expert runs) | — |
| 12 | 2026-09-30 | Expert-mix scaling grid i3 (own vs +93k vs +399k IDM v2-a expert steps, 3 seeds) | Modal | in $53.02 | Yaw 0.786 → 0.746, onset 79 → 83%, false turns 10.2 → 7.9%, F1 0.314 → 0.363; every mix seed beats every own seed on yaw. The core VPT-style result | Yes; bundle `bc2-mix399-s0` is the live model | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/5e31465c-8959-43b2-ade1-4ffc7fa33b61/10437f0f-a232-4338-b801-83e6221bf413 |
| 13 | 2026-09-30 | Grid i4 (469k v2-a expert steps, 3 seeds) | Modal | ~$4 | Camera plateaued (val yaw 0.755 vs 0.746); only buttons still gained (F1 0.381) | No (confirmed a plateau; could have been 1 seed or local) | — |
| 14 | 2026-09-30 | Grid j (v2-cd vs v2-a labels, same 5 DayMR shards, 3 seeds) | Modal | ~$9 (incl. 4 startup failures) | No downstream gain from the better labels (val yaw 0.797 vs 0.776) | No (should have been a 1-seed probe first) | — |
| 15 | 2026-09-30 | Motion-input dropout retrain, grid k (p = 0.3 and 0.5, 1 seed each) | Modal | ~$2.6 | Criterion (on the retained live frames: hold ≥ 0.3, turn ≥ 0.2; val yaw ≤ 0.766, F1 ≥ 0.33) not met: hold 0.04, turn 0.05. p = 0.3 kept val yaw 0.742 and raised F1 to 0.405 | No (discarded; `docs/lanes/policy.md`) | — |
| 16 | 2026-09-30 | RL reward readers (hit, KO, HP, death, fall) | local | $0 | Hit P 1.00 / R 0.98 (900 frames); KO 142/142 real; HP 67/67; all 10 non-sealed range takes labelled: James 7.0 KOs/min vs scripted 4.2 | Yes | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/df009276-401b-44f8-884b-1ae14f3a1d0c/aac28fce-28da-44ad-8afe-2f984edd30e8 |
| 17 | 2026-09-30 | Offline AWR step 0 | Modal | $4.24 | No measurable held-out shift over 3 seeds (every CI spans 0); BC metrics intact | No (a clean negative; kept only as the online-RL initialiser) | — |
| 18 | 2026-09-30 | World model full-01 (DIAMOND-style, 72×128, 10 Hz) | Modal | $5.00 (+ $0.65 probe) | Beats copy-last (+4.3 dB at 0.1 s); actions matter (+3.2 dB vs shuffled); dissolves by ~1 s | Yes, as a prototype | https://uploads.linear.app/75f1d1f0-542b-4095-9967-fd7b27093472/e32f4bc7-7353-4b4f-aa46-0e23a2554b0a/00cd24ec-6926-4732-83a4-8313e2cc2468 |
| 19 | 2026-09-30 | World model v2-noroll (144×256, 12-frame context) | Modal | $13.42 | Ties full-01; sampled frames hazy from step 1; imagined KO AUC 0.69 | No | rl/world_model/out/v2-noroll/real_vs_imagined.gif |
| 20 | 2026-09-30 | World model v2-main (+ own-rollout training) | Modal | $16.11 | Same as v2-noroll within noise; the anti-drift trick didn't help | No | rl/world_model/out/v2-main/real_vs_imagined.gif |
| 21 | 2026-09-30 | World model v3-expert (+ 21.7 h IDM-labelled expert data) | Modal | $17.52 | +0.2 dB at 2–3 s, −0.35 dB early; imagined KO AUC 0.65; 2–3 s target not met | No (pixel track stopped; latent track next, local) | rl/world_model/out/v3-expert/real_vs_imagined.gif |
| 22 | 2026-09-30 | World model probes, diagnostics and sampler sweep | Modal | ~$2.70 | The 2–3 s error is content, not camera (Spearman 0.13); more denoising steps don't help | Yes (diagnosis) | — |
| 23 | 2026-09-30 | Learned live runner plus bundle swaps | local | $0 | Built and safety-read SAFE; mocked replays p95 45–46 ms on a quiet GPU | Yes | — |
| 24 | 2026-09-30 | Live learned-01 run A (`bc2-mix399-s0`, range) | PC live | $0 | Stopped: 121 of 126 decisions stale (inference ~95 ms over the 100 ms bound), and the output idled (yaw ≈ 0, no presses). Run B held | No (found the copycat idle and the latency) | data/calibration/compat-check-20260929/learned-01-a/ |
| 25 | 2026-09-30 | Static-input augmentation retrain, grid l (1 seed) | Modal | ~$1.3 | Criterion not met on hold: on the retained live frames turn 0.465 (passes) but hold 0.178 (needs 0.3); val yaw 0.754, F1 0.369 | No (discarded; `docs/lanes/policy.md`) | — |
| 26 | 2026-09-30 | Live RL sitting 01 (frozen BC vs online RL, 20 s episodes, AWR between RL episodes) | PC live | $0 | 6 of 20 episodes, then ep 5 `range_lost` (the policy swung into the sea). BC 0 hits over 3 episodes (idle); RL 3 hits, 0 KOs over 3; 3 AWR updates. Plumbing works; aim is still the BC's idle camera | Yes, as a plumbing run | data/calibration/rl-sitting-20260930-01/curve.png; data/calibration/rl-sitting-20260930-01/takeover-check-sheet.jpg |

**Totals, 2026-09-30:** Modal was $261 month to date at the 13:25 snapshot (the spend ledger has the breakdown);
the later rows above add about $4. The cloud budget is $500 in total.
