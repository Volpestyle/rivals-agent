# Full03 yaw qualification: development readiness remains blocked

EXPLORATORY / idm-owner / VUH-1353 / 2026-09-28. The lead-authorized immediate $0 pass is complete. **Not ready to open Gate 2 or label the proposed new shard.** Full03 remains frozen; the new Mac model is preserved without promotion. No model invocation, refit, head/loss change, threshold tuning, paid work or deletion occurred. **Mac explicitly released to herdr-lead at approximately 22:49 UTC**, within the 60-minute time box begun 22:26 UTC.

## What the bounded native check established

Three approved development sources only: live Quick Match `20-06-20`, its self replay `11-10-08`, and released competitive `22-48-05` as a pixel-only refusal control. The last remains motor-pending for training. Existing exposure is disclosed in the registry; none is fresh validation.

Selection was fixed at original PTS **100?160 s**, twelve uniform samples per source at 102.5 + 5k s, independent of reader predictions. Native retained PTS were 102.504 + 5k. Human source/state/timer labels were saved before candidate reader output. These are owner development observations, not independent blind truth or an admission receipt.

| Source | Native state seen | Legible centre values | Correct / unknown / wrong | Authorized layout answers |
|---|---|---:|---:|---:|
| Live Quick Match | Gameplay, 12 samples | 12 | 12 / 0 / 0 | 0 / 12 |
| Self replay | Followed Spider-Man, spectator roster/prompt, 12 samples | 12 | 10 / 2 / 0 | 0 / 12 |
| Competitive recording | 2 hero-selection, 9 desktop/media overlays, 1 menu | Not scored as gameplay truth | Not applicable | 0 / 12 |

Replay unknowns are the visibly legible `03:48` and `03:43` at 137.504/142.504 s. The 16.7% unknown share in this tiny development sample exceeds the existing 10% T1 legible-frame bar; it is an observed deficiency, **not a fresh T1 verdict**. No timer-transition precision/recall verdict follows from five-second sampling.

Replay prompt NCC is 0.963?0.999 on all twelve frames, but the entry-specific spectator template never reaches its 0.95 threshold. Four sampled replay frames contain visible feeds; all still abstain. Live has four sampled feed-bearing frames: the exact archived cowboyboopbop?Yoitscolin entry matches at NCC 0.997, while the other three do not. That one positive correctly refuses without a complete-match scan. We did not forge MatchEvidence or reinterpret this sparse scan as complete. Thus zero authorized answers partly reflects the required guard; cue scores separately demonstrate the entry-template coverage problem. Four competitive overlay frames expose readable team clocks and return unsupported, never replay. This fixed window provides no competitive gameplay-layout coverage; it was not replaced by a favorable window.

## Paired feed events: feasible correspondence, insufficient timing evidence

Within the already selected minute, visually inspect 10 Hz crops from live 137.5?147.5 and replay 107.5?117.5 s. This adaptive development choice followed native inspection, not detector success. No camera motion or image correlation was used for alignment.

Two unique corresponding shifted arrivals are visible: S.t4rfir3?ShadowFox594 and cowboyboopbop?Yoitscolin. Their coarse live/replay shift brackets each imply replay-minus-live in **(-30.7, -30.5) s**. The original five-second samples show six shared timer values at a nominal -30 s sample offset; that only establishes coarse clock correspondence, not a subframe fitted offset. Do not infer a 0.6 s physical lag from that comparison.

A third identity, cowboyboopbop?Carsonred, arrives after existing entries in live but into an empty replay feed, so it is not a paired shifted-arrival timing anchor. Two events are below the registered 30-live/10-replay support floors and the earlier plan's proposed three-per-span minimum. A 100 ms bracket cannot test the required 8.33/16.67 ms tolerances. No K1?K3, T2/T3', alignment or Gate 2 pass is claimed. Event notes and native crop hashes are retained.

## Reconciled qualification dependencies

1. **Readers:** the layout delta did receive LAND in the appended independent review, contrary to its earlier frozen note's pending wording. Acceptance is only for an unwired prototype. Its private-construction safeguard, positive QM distinction, whole-recording identity/bounds and useful novel-entry coverage still precede wiring. Timer value utility acceptance does not clear replay timing or T2/T3'. Existing timing/scorer repair requirements remain.
2. **Fresh validation:** registry V-C has live `20260927T041331-992Z-150600-1` plus replay `20260927T043214-589Z-150600-2`. **V-Q `20260927T045943-301Z-150600-3` explicitly has no replay.** That missing Quick Match replay coverage cannot be supplied by this spent development pair or by opening sealed Gate 2. Lead/admission must resolve the missing coverage under a prospective protocol; check whether a same-patch replay still exists before asking James. No validation payload was accessed.
3. **Cuts:** current `replay_cuts.py` and its test are byte-identical to frozen `f50f57e3`/`dc181973`. Historical S1?S3 producer results and blind relabel exist. The reader review leaves cut acceptance attached to its own evidence; this pass did not locate an explicit independent cut-acceptance receipt. Reconcile that receipt before use, rather than rerunning unchanged cuts or calling them newly accepted.
4. **Camera support and uncertainty:** inspected `policy/idm/train.py` uses action-availability support plus camera total-std abstention. No frozen train-p99.5 rotation-rate / dev-p99 feature-OOD artifact or implementation was found in that prediction path or IDM modules. These are distinct gates and cannot be replaced by the action mask. Full03's saved range-dev yaw 1-sigma coverage is 0.7766/0.7200 (171533 calibrated/extrapolated) and 0.7522/0.6823 (205528); answered shares remain high. Those historical diagnostics are not replay uncertainty coverage. Specify, implement/test and freeze the missing support calculation using authorized TRAIN/dev only before any fresh qualification read; do not tune on this pair or sealed scores.
5. **Scale:** the latest camera-analysis TRAIN and calibration attempts both refused focal/defensible bounds. Full-turn gain and HUD geometry do not establish viewer FOV or historical-source angular scale. The two-FOV re-record was skipped; its existence cannot be assumed. Lead must settle a supported scale argument before true-degree source labels. This pass did not retry focal fitting.

Both sealed Gate 2 pairs stay closed. Future per-match yaw bars remain >=6,000 paired intervals; moving median <=1.25x live, direction >=live minus 5 points, and 1-sigma/answered coverage >=live minus 10 points. Preserve independent HUD alignment and all withheld-share denominators. Pitch/buttons stay unknown unless separately qualified.

## Integrity, execution and next action

The three originals were SHA-verified against their released registry identities on the PC. Only video packets were copied, without PC decoding or re-encoding. Reused original timestamps and a one-second sample of packet PTS/DTS/size/content hashes matched each original/excerpt exactly (118/118/120 packets returned by the bounded demux probe; these counts are not a dropped-frame rate). Keyframe preroll and mux tail make encoded excerpts wider than the inspected minute; no extra frames became judged evidence.

Serial Mac FFmpeg decoding used two threads and nice 10 (observed process NI 15), then the unchanged readers ran with OpenCV threads 2. Sparse extraction, reader scoring and coarse event extraction all exited 0. The first environment probe lacked cv2; an isolated environment supplied numpy 2.4.6/OpenCV-headless 5.0.0.93. An initial local packet assembly referenced a nonexistent namespace __init__.py and stopped before launch; it was corrected. No worker retry or model job occurred. No peak decoder memory measurement is claimed.

All 36 native images were independently size/hash-verified after transfer. The final archive's 214 files (including 200 event crops) were verified again on PC; SHA256 `9c20472efc8584d53b653a61276c8c26299d8181e0f240f0f7d0f703400b7b97`, 23,990,383 bytes. Data and complete logs remain under `data/idm/yaw-readiness-20260928/` and `/Users/james/dev/idm-data/yaw-readiness-20260928/`; this packet preserves results, scripts, metadata and hashes. All owned Mac phase PIDs were absent at collection and release. No DayMR, V-C/V-Q, sealed or SPIDEY payload was read; incidental desktop overlays inside the authorized competitive source were excluded and are not published as evidence images.

**Next:** lead accepts this readiness result and routes the V-Q coverage/scale decisions. IDM proposes a bounded development-only timer/layout and camera-support qualification step using these concrete failures; no new refit is justified. A competitive gameplay control remains missing from this fixed sample. SPIDEY `2026-02-17 23-51-41` remains closed pending James's decision and separately reviewed source-use admission. Later policy comparison remains native-only versus native plus an accepted shard, with the same policy/evaluation/budget. Lead received result/remaining/next and explicit Mac release for VUH-1353; publication/readback is not claimed without confirmation.
